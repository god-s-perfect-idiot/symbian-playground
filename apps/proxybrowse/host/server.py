#!/usr/bin/env python3
"""Proxy Browse host — render the real page on macOS at E7 size, stream frames to the phone.

Nokia E7-00 logical viewport: 640×360 (landscape). Phone WRT shows JPEG frames and
POSTs tap coordinates; this process maps them onto Playwright's viewport.

Playwright's sync API is owned by one worker thread; HTTP handlers enqueue jobs.
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import socket
import threading
import time
import urllib.parse
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from typing import Any, Callable, Optional

from PIL import Image
from playwright.sync_api import sync_playwright

# Prefer the normal user browser cache (avoids sandbox / wrong-arch paths).
os.environ.setdefault(
    "PLAYWRIGHT_BROWSERS_PATH",
    str(Path.home() / "Library" / "Caches" / "ms-playwright"),
)
# Always use full Chromium — headless-shell path selection is flaky across arch/sandbox.
os.environ["PLAYWRIGHT_CHROMIUM_USE_HEADLESS_SHELL"] = "0"


def _chrome_executable() -> Optional[str]:
    root = Path(os.environ["PLAYWRIGHT_BROWSERS_PATH"])
    if not root.is_dir():
        return None
    candidates = [
        "chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
        "chrome-mac-x64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
    ]
    for child in sorted(root.glob("chromium-*"), reverse=True):
        for rel in candidates:
            path = child / rel
            if path.is_file():
                return str(path)
    return None

VIEW_W = 640
VIEW_H = 360
JPEG_QUALITY = 62
DEFAULT_URL = "https://example.com"
DEFAULT_PORT = 8765
CAPTURE_INTERVAL = 0.12


@dataclass
class _Job:
    fn: Callable[[], Any]
    result: queue.Queue  # holds ("ok", value) | ("err", Exception)


class BrowserSession:
    def __init__(self, start_url: str, headless: bool) -> None:
        self.start_url = start_url
        self.headless = headless
        self._jobs: queue.Queue[Optional[_Job]] = queue.Queue()
        self._frame_lock = threading.Lock()
        self._frame_jpeg = b""
        self._frame_seq = 0
        self._frame_ts = 0.0
        self.last_error = ""
        self._meta_url = ""
        self._meta_title = ""
        self._worker = threading.Thread(target=self._run, name="pw-worker", daemon=True)
        self._ready = threading.Event()
        self._stopped = threading.Event()

    def start(self) -> None:
        self._worker.start()
        if not self._ready.wait(timeout=60):
            raise RuntimeError("browser worker failed to start")
        if self.last_error and not self._meta_url:
            raise RuntimeError(self.last_error)

    def stop(self) -> None:
        self._jobs.put(None)
        self._worker.join(timeout=5)
        self._stopped.set()

    def _run(self) -> None:
        try:
            pw = sync_playwright().start()
            launch_kwargs: dict[str, Any] = {
                "headless": self.headless,
                "args": [
                    f"--window-size={VIEW_W},{VIEW_H + 80}",
                    "--disable-infobars",
                ],
            }
            exe = _chrome_executable()
            if exe:
                launch_kwargs["executable_path"] = exe
            browser = pw.chromium.launch(**launch_kwargs)
            context = browser.new_context(
                viewport={"width": VIEW_W, "height": VIEW_H},
                device_scale_factor=1,
                is_mobile=False,
                has_touch=True,
                user_agent=(
                    "Mozilla/5.0 (Linux; Android 4.4; Nokia E7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/90.0.0.0 Mobile Safari/537.36"
                ),
            )
            page = context.new_page()
            page.goto(self.start_url, wait_until="domcontentloaded", timeout=45000)
            self._refresh_meta(page)
            self._capture(page)
            self._ready.set()
        except Exception as exc:  # noqa: BLE001
            self.last_error = str(exc)
            self._ready.set()
            return

        next_capture = time.monotonic()
        try:
            while True:
                timeout = max(0.0, next_capture - time.monotonic())
                try:
                    job = self._jobs.get(timeout=timeout)
                except queue.Empty:
                    try:
                        self._capture(page)
                        self._refresh_meta(page)
                        self.last_error = ""
                    except Exception as exc:  # noqa: BLE001
                        self.last_error = str(exc)
                    next_capture = time.monotonic() + CAPTURE_INTERVAL
                    continue

                if job is None:
                    break
                try:
                    value = job.fn(page)
                    job.result.put(("ok", value))
                except Exception as exc:  # noqa: BLE001
                    job.result.put(("err", exc))
        finally:
            try:
                browser.close()
            except Exception:  # noqa: BLE001
                pass
            try:
                pw.stop()
            except Exception:  # noqa: BLE001
                pass

    def _call(self, fn: Callable[[Any], Any], timeout: float = 45.0) -> Any:
        job = _Job(fn=fn, result=queue.Queue(maxsize=1))
        self._jobs.put(job)
        kind, payload = job.result.get(timeout=timeout)
        if kind == "err":
            raise payload
        return payload

    def _refresh_meta(self, page: Any) -> None:
        self._meta_url = page.url
        try:
            self._meta_title = page.title()
        except Exception:  # noqa: BLE001
            self._meta_title = ""

    def _capture(self, page: Any) -> None:
        png = page.screenshot(type="png", full_page=False)
        jpeg = _png_to_jpeg(png, JPEG_QUALITY)
        with self._frame_lock:
            self._frame_jpeg = jpeg
            self._frame_seq += 1
            self._frame_ts = time.time()

    def meta(self) -> dict[str, Any]:
        with self._frame_lock:
            seq = self._frame_seq
            ts = self._frame_ts
            nbytes = len(self._frame_jpeg)
        return {
            "w": VIEW_W,
            "h": VIEW_H,
            "seq": seq,
            "ts": ts,
            "url": self._meta_url,
            "title": self._meta_title,
            "bytes": nbytes,
            "error": self.last_error,
        }

    def frame(self) -> bytes:
        with self._frame_lock:
            return self._frame_jpeg

    def navigate(self, url: str) -> dict[str, Any]:
        url = url.strip()
        if not url:
            raise ValueError("empty url")
        if "://" not in url:
            url = "https://" + url

        def op(page: Any) -> dict[str, Any]:
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            self._refresh_meta(page)
            self._capture(page)
            return self.meta()

        return self._call(op)

    def back(self) -> dict[str, Any]:
        def op(page: Any) -> dict[str, Any]:
            page.go_back(wait_until="domcontentloaded", timeout=20000)
            self._refresh_meta(page)
            self._capture(page)
            return self.meta()

        return self._call(op)

    def forward(self) -> dict[str, Any]:
        def op(page: Any) -> dict[str, Any]:
            page.go_forward(wait_until="domcontentloaded", timeout=20000)
            self._refresh_meta(page)
            self._capture(page)
            return self.meta()

        return self._call(op)

    def click(self, x: float, y: float) -> dict[str, Any]:
        x_i = max(0, min(VIEW_W - 1, int(round(x))))
        y_i = max(0, min(VIEW_H - 1, int(round(y))))

        def op(page: Any) -> dict[str, Any]:
            page.mouse.click(x_i, y_i)
            time.sleep(0.05)
            self._refresh_meta(page)
            self._capture(page)
            return {"ok": True, "x": x_i, "y": y_i, **self.meta()}

        return self._call(op)

    def scroll(self, dx: float, dy: float) -> dict[str, Any]:
        def op(page: Any) -> dict[str, Any]:
            page.mouse.wheel(int(dx), int(dy))
            time.sleep(0.03)
            self._capture(page)
            return {"ok": True, **self.meta()}

        return self._call(op)

    def type_text(self, text: str) -> dict[str, Any]:
        def op(page: Any) -> dict[str, Any]:
            page.keyboard.type(text, delay=20)
            self._capture(page)
            return {"ok": True, **self.meta()}

        return self._call(op)

    def key(self, name: str) -> dict[str, Any]:
        def op(page: Any) -> dict[str, Any]:
            page.keyboard.press(name)
            self._capture(page)
            return {"ok": True, **self.meta()}

        return self._call(op)


def _png_to_jpeg(png: bytes, quality: int) -> bytes:
    img = Image.open(BytesIO(png)).convert("RGB")
    if img.size != (VIEW_W, VIEW_H):
        img = img.resize((VIEW_W, VIEW_H), Image.Resampling.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()


def _lan_ips() -> list[str]:
    ips: list[str] = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if not ip.startswith("127."):
            ips.append(ip)
    except OSError:
        pass
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127.") and ip not in ips:
                ips.append(ip)
    except OSError:
        pass
    return ips


SESSION: Optional[BrowserSession] = None
LISTEN_PORT = DEFAULT_PORT
PHONE_UI = Path(__file__).resolve().parents[1] / "src" / "index.html"


class Handler(BaseHTTPRequestHandler):
    server_version = "ProxyBrowse/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[http] {self.address_string()} {fmt % args}")

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-store")

    def _json(self, code: int, payload: Any) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or "0")
        body = self.rfile.read(length) if length else b"{}"
        if not body:
            return {}
        return json.loads(body.decode("utf-8"))

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        assert SESSION is not None
        path = urllib.parse.urlparse(self.path).path
        if path in ("/", "/index.html"):
            html = _host_html(SESSION.meta(), _lan_ips(), LISTEN_PORT)
            raw = html.encode("utf-8")
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        if path in ("/phone", "/phone.html", "/client"):
            # Nokia Browser path — no WRT .wgz install required
            if not PHONE_UI.is_file():
                self._json(500, {"error": f"missing UI {PHONE_UI}"})
                return
            raw = PHONE_UI.read_bytes()
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        if path == "/meta":
            self._json(200, SESSION.meta())
            return
        if path in ("/frame.jpg", "/frame.jpeg"):
            data = SESSION.frame()
            if not data:
                self._json(503, {"error": "no frame yet"})
                return
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("X-Frame-Seq", str(SESSION.meta()["seq"]))
            self.end_headers()
            self.wfile.write(data)
            return
        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        assert SESSION is not None
        path = urllib.parse.urlparse(self.path).path
        try:
            data = self._read_json()
        except json.JSONDecodeError:
            self._json(400, {"error": "bad json"})
            return
        try:
            if path == "/nav":
                self._json(200, SESSION.navigate(str(data.get("url", ""))))
                return
            if path == "/back":
                self._json(200, SESSION.back())
                return
            if path == "/forward":
                self._json(200, SESSION.forward())
                return
            if path == "/click":
                self._json(200, SESSION.click(float(data["x"]), float(data["y"])))
                return
            if path == "/scroll":
                self._json(
                    200,
                    SESSION.scroll(float(data.get("dx", 0)), float(data.get("dy", 0))),
                )
                return
            if path == "/type":
                self._json(200, SESSION.type_text(str(data.get("text", ""))))
                return
            if path == "/key":
                self._json(200, SESSION.key(str(data.get("name", "Enter"))))
                return
        except Exception as exc:  # noqa: BLE001
            self._json(500, {"error": str(exc)})
            return
        self._json(404, {"error": "not found"})


def _host_html(meta: dict[str, Any], ips: list[str], port: int) -> str:
    links = "".join(
        f"<li><code>http://{ip}:{port}</code></li>" for ip in (ips or ["&lt;lan-ip&gt;"])
    )
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/><title>Proxy Browse host</title>
<style>
  body {{ font-family: ui-sans-serif, system-ui, sans-serif; margin: 24px; background: #111; color: #eee; }}
  code {{ background: #222; padding: 2px 6px; border-radius: 4px; }}
  img {{ border: 1px solid #444; width: {VIEW_W}px; height: {VIEW_H}px; background: #000; }}
  .row {{ display: flex; gap: 24px; flex-wrap: wrap; align-items: flex-start; }}
</style></head>
<body>
  <h1>Proxy Browse host</h1>
  <p>Live Chromium viewport is <strong>{VIEW_W}×{VIEW_H}</strong> (Nokia E7). Phone pulls JPEG frames and posts taps.</p>
  <div class="row">
    <div>
      <p><strong>Preferred on E7:</strong> open Nokia Browser →</p>
      <ul>{"".join(f"<li><code>http://{ip}:{port}/phone</code></li>" for ip in (ips or ["&lt;lan-ip&gt;"]))}</ul>
      <p>WRT widget host base (if .wgz installs):</p>
      <ul>{links}</ul>
      <p>Now: <code id="u">{meta.get("url","")}</code></p>
    </div>
    <div>
      <p>Preview (same stream as phone)</p>
      <img id="f" src="/frame.jpg" width="{VIEW_W}" height="{VIEW_H}" alt="frame"/>
    </div>
  </div>
  <script>
    setInterval(function() {{
      var i = document.getElementById('f');
      i.src = '/frame.jpg?t=' + Date.now();
      fetch('/meta').then(function(r){{return r.json();}}).then(function(m){{
        document.getElementById('u').textContent = m.url || '';
      }}).catch(function(){{}});
    }}, 400);
  </script>
</body></html>"""


def main() -> None:
    global SESSION, LISTEN_PORT
    ap = argparse.ArgumentParser(description="Proxy Browse macOS host for Symbian E7")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--url", default=DEFAULT_URL, help="Initial page")
    ap.add_argument("--headless", action="store_true", help="Hide Chromium window")
    args = ap.parse_args()
    LISTEN_PORT = args.port

    SESSION = BrowserSession(start_url=args.url, headless=args.headless)
    print(f"starting Chromium at {VIEW_W}x{VIEW_H} → {args.url}", flush=True)
    SESSION.start()

    httpd = ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    ips = _lan_ips()
    print(f"listening on http://0.0.0.0:{args.port}", flush=True)
    for ip in ips:
        print(f"  phone host URL: http://{ip}:{args.port}", flush=True)
    print("open that URL on the Mac for a mirrored preview; Ctrl+C to stop", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopping…")
    finally:
        httpd.server_close()
        SESSION.stop()


if __name__ == "__main__":
    main()
