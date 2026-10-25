from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from . import __version__
from .app import build_app, list_apps, load_app, normalize_app_name, scaffold
from .device import (
    DeviceError,
    ensure_volume,
    find_volume,
    phone_ls,
    phone_pull,
    phone_push,
    status_dict,
    status_json,
    usb_reset,
    usb_status,
)
from .paths import APPS, OUT, PHONE_DEVDROP, ROOT
from .watch import watch_paths

HELP_TEXT = """\
Symbian E7 harness — use ./sym for everything (see AGENTS.md).

  ./sym doctor                         # USB + volume + SDK
  ./sym apps                           # list apps
  ./sym new <name> [--type wrt|native|payload]
  ./sym build <name>                   # → out/<artifact>
  ./sym deploy <name>                  # build + push Installs/devdrop
  ./sym deploy --artifact out/foo.sisx
  ./sym iterate <name>                 # watch → rebuild → deploy
  ./sym test [name]                    # smoke USB + push (+ optional build)
  ./sym ls [path] | push | pull | reset-usb | ensure
  ./sym sdk status | setup | shell
  ./sym proxybrowse [--port 8765] [--url …] [--headless]
                   # macOS host: Chromium @ 640×360, JPEG frames + click API

App names are bare (hello), not apps/hello.
Phone: unlocked, Mass storage. After deploy → File Mgr → Installs/devdrop.
Native SIS needs Colima x86_64 image symbian-sdk:s3 (do not rebuild casually).
"""


def _die(msg: str, code: int = 1) -> None:
    print(f"error: {msg}", file=sys.stderr)
    raise SystemExit(code)


def _app_arg(name: str) -> str:
    return normalize_app_name(name) if name else name


def cmd_help(_: argparse.Namespace) -> None:
    print(HELP_TEXT, end="")
    agents = ROOT / "AGENTS.md"
    if agents.is_file():
        print(f"playbook: {agents}")


def cmd_status(_: argparse.Namespace) -> None:
    print(status_json())


def cmd_doctor(_: argparse.Namespace) -> None:
    from .sdk import status as sdk_status

    ok = True
    usb = usb_status()
    print(f"usb: {'OK' if usb.present else 'MISSING'}  {usb.product}  {usb.serial}")
    if not usb.present:
        ok = False
        print("hint: unlock phone, USB Mass storage, cable; then ./sym reset-usb")
    vol = find_volume()
    if vol:
        print(
            f"volume: OK  {vol.name}  media={vol.media_name or '?'}  "
            f"{vol.used_gb}/{vol.size_gb} GB  accessible={vol.accessible}"
        )
    else:
        print("volume: MISSING  (mass storage not mounted)")
        ok = False
        print("hint: ./sym reset-usb && ./sym ensure")
    print(f"apps dir: {APPS}  ({len(list_apps())} apps)")
    print(f"out dir:  {OUT}")
    print(f"drop:     {PHONE_DEVDROP}")
    try:
        import usb.core  # noqa: F401

        print("pyusb: OK")
    except ImportError:
        print("pyusb: MISSING")
        ok = False
    s = sdk_status()
    print(
        f"sdk: docker={'OK' if s.docker else 'NO'}  "
        f"colima={'OK' if s.colima else 'NO'}  "
        f"image={'OK' if s.image else 'MISSING'} ({s.image_name})"
    )
    print(
        f"sdk vendor: sdk_zip={'OK' if s.vendor_sdk else 'MISSING'}  "
        f"csl={'OK' if s.vendor_csl else 'MISSING'}  "
        f"gnupoc={'OK' if s.vendor_gnupoc else 'MISSING'}"
    )
    if not s.docker or not s.colima:
        print("hint: colima start --arch x86_64   # or ./sym sdk setup")
    if not s.image:
        print("hint: ./sym sdk setup   # fetch SDK + build Docker image (slow)")
    if not ok:
        _die("doctor found problems", 2)
    print("doctor: ready")
    print("next: ./sym apps | ./sym deploy <app> | ./sym help | see AGENTS.md")

def cmd_sdk(ns: argparse.Namespace) -> None:
    from . import sdk as sdkmod

    try:
        if ns.sdk_cmd == "status":
            print(sdkmod.status_json())
        elif ns.sdk_cmd == "fetch":
            sdkmod.fetch_vendor()
        elif ns.sdk_cmd == "build-image":
            sdkmod.build_image(no_cache=getattr(ns, "no_cache", False))
        elif ns.sdk_cmd == "setup":
            sdkmod.setup(no_cache=getattr(ns, "no_cache", False))
        elif ns.sdk_cmd == "shell":
            raise SystemExit(sdkmod.shell())
        else:
            _die(f"unknown sdk command: {ns.sdk_cmd}")
    except sdkmod.SdkError as e:
        _die(str(e))


def cmd_reset_usb(_: argparse.Namespace) -> None:
    usb_reset()
    print("usb reset issued; waiting for volume…")
    vol = ensure_volume(timeout=25, reset_if_missing=False)
    print(f"mounted: {vol.name} ({vol.mount_point}) media={vol.media_name}")


def cmd_ensure(_: argparse.Namespace) -> None:
    vol = ensure_volume()
    print(f"{vol.name}\t{vol.mount_point}\t{vol.media_name}")


def cmd_ls(ns: argparse.Namespace) -> None:
    items = phone_ls(ns.path or "")
    for it in items:
        print(it)


def cmd_push(ns: argparse.Namespace) -> None:
    path = Path(ns.file)
    remote = phone_push(path, ns.dest or PHONE_DEVDROP)
    print(remote)


def cmd_pull(ns: argparse.Namespace) -> None:
    dest = Path(ns.dest or (OUT / "pull"))
    out = phone_pull(ns.remote, dest)
    print(out)


def cmd_new(ns: argparse.Namespace) -> None:
    name = _app_arg(ns.name)
    meta = scaffold(name, app_type=ns.type, title=ns.title)
    print(f"created apps/{meta.name}  type={meta.type}  uid={meta.uid}")
    if meta.type == "wrt":
        print(f"next: edit apps/{meta.name}/src then ./sym deploy {meta.name}")
    elif meta.type == "native":
        print(f"next: ./sym build {meta.name} && ./sym deploy {meta.name}")
    else:
        print(f"next: add files under apps/{meta.name}/ then ./sym deploy {meta.name}")


def cmd_apps(_: argparse.Namespace) -> None:
    for name in list_apps():
        m = load_app(name)
        print(f"{m.name}\t{m.type}\t{m.uid}\t{m.title}")


def cmd_build(ns: argparse.Namespace) -> None:
    out = build_app(_app_arg(ns.app))
    print(out)


def cmd_deploy(ns: argparse.Namespace) -> None:
    if ns.artifact:
        artifact = Path(ns.artifact)
    else:
        if not ns.app:
            _die("deploy needs <app> or --artifact")
        artifact = build_app(_app_arg(ns.app))
    if not artifact.is_file():
        _die(f"artifact missing: {artifact}")
    dest = ns.dest or PHONE_DEVDROP
    remote = phone_push(artifact, dest)
    print(f"deployed: {remote}")
    print("on phone: open File Mgr → Installs/devdrop → run the package")
    if artifact.suffix.lower() == ".wgz":
        print("tip: .wgz installs via Web Runtime / File Manager")


def cmd_iterate(ns: argparse.Namespace) -> None:
    """Build + deploy once, then rebuild/deploy on src changes."""
    app_name = _app_arg(ns.app)
    app = load_app(app_name)
    watch_root = app.root / "src"
    if not watch_root.exists():
        watch_root = app.root

    def once() -> None:
        t0 = time.time()
        try:
            artifact = build_app(app_name)
            remote = phone_push(artifact, ns.dest or PHONE_DEVDROP)
            dt = time.time() - t0
            print(f"[{time.strftime('%H:%M:%S')}] OK  {artifact.name} → {remote}  ({dt:.1f}s)")
        except (DeviceError, Exception) as e:
            print(f"[{time.strftime('%H:%M:%S')}] FAIL  {e}", file=sys.stderr)

    print(f"iterate {app_name}  watching {watch_root}  Ctrl-C to stop")
    once()
    watch_paths([watch_root, app.root / "app.yaml"], once, debounce=ns.debounce)


def cmd_test(ns: argparse.Namespace) -> None:
    """Smoke-test harness + device path (not on-device unit tests)."""
    failures = 0
    usb = usb_status()
    if not usb.present:
        print("FAIL usb")
        failures += 1
    else:
        print("PASS usb", usb.serial)

    try:
        vol = ensure_volume(timeout=10)
        print("PASS volume", vol.name, vol.media_name)
    except DeviceError as e:
        print("FAIL volume", e)
        failures += 1
        raise SystemExit(1)

    # push a tiny marker and list
    OUT.mkdir(parents=True, exist_ok=True)
    # FAT/Symbian volumes reject leading-dot names via Finder (-8082)
    marker = OUT / "sym_harness_probe.txt"
    marker.write_text(f"sym harness probe {time.time()}\n", encoding="utf-8")
    try:
        remote = phone_push(marker, PHONE_DEVDROP)
        print("PASS push", remote)
        names: list[str] = []
        for _ in range(8):
            names = phone_ls(PHONE_DEVDROP)
            if marker.name in names:
                break
            time.sleep(0.35)
        if marker.name not in names:
            print("FAIL ls missing marker", names[:10])
            failures += 1
        else:
            print("PASS ls", PHONE_DEVDROP)
    except DeviceError as e:
        print("FAIL push/ls", e)
        failures += 1

    if ns.app:
        try:
            out = build_app(_app_arg(ns.app))
            print("PASS build", out)
            remote = phone_push(out, PHONE_DEVDROP)
            print("PASS deploy", remote)
        except Exception as e:
            print("FAIL build/deploy", e)
            failures += 1

    if failures:
        _die(f"{failures} test failure(s)", 1)
    print("test: OK")


def cmd_proxybrowse(ns: argparse.Namespace) -> None:
    """Run the macOS Proxy Browse host (real page @ E7 640×360)."""
    import os
    import subprocess

    script = APPS / "proxybrowse" / "host" / "server.py"
    if not script.is_file():
        _die(f"missing {script}")
    py = ROOT / ".venv" / "bin" / "python"
    if not py.is_file():
        _die("missing .venv — run ./sym once to bootstrap")
    env = os.environ.copy()
    env.setdefault(
        "PLAYWRIGHT_BROWSERS_PATH",
        str(Path.home() / "Library" / "Caches" / "ms-playwright"),
    )
    env["PLAYWRIGHT_CHROMIUM_USE_HEADLESS_SHELL"] = "0"
    cmd = [str(py), str(script), "--port", str(ns.port), "--url", ns.url]
    if ns.headless:
        cmd.append("--headless")
    raise SystemExit(subprocess.call(cmd, env=env))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sym",
        description="Tight Symbian E7 build / deploy harness (see AGENTS.md)",
        epilog="Run `./sym help` for the agent cheat-sheet.",
    )
    p.add_argument("--version", action="version", version=f"sym {__version__}")
    sp = p.add_subparsers(dest="cmd", required=True)

    sp.add_parser("help", help="Agent cheat-sheet (AGENTS.md)").set_defaults(func=cmd_help)
    sp.add_parser("status", help="JSON status of USB + volume").set_defaults(func=cmd_status)
    sp.add_parser("doctor", help="Check toolchain + device").set_defaults(func=cmd_doctor)
    sp.add_parser("reset-usb", help="USB reset (remount mass storage)").set_defaults(func=cmd_reset_usb)
    sp.add_parser("ensure", help="Ensure phone volume is mounted").set_defaults(func=cmd_ensure)

    p_ls = sp.add_parser("ls", help="List phone folder via Finder")
    p_ls.add_argument("path", nargs="?", default="")
    p_ls.set_defaults(func=cmd_ls)

    p_push = sp.add_parser("push", help="Push file to phone")
    p_push.add_argument("file")
    p_push.add_argument("--dest", default=PHONE_DEVDROP)
    p_push.set_defaults(func=cmd_push)

    p_pull = sp.add_parser("pull", help="Pull file from phone")
    p_pull.add_argument("remote")
    p_pull.add_argument("--dest", default=str(OUT / "pull"))
    p_pull.set_defaults(func=cmd_pull)

    p_new = sp.add_parser("new", help="Scaffold app under apps/")
    p_new.add_argument("name")
    p_new.add_argument("--type", choices=["wrt", "native", "payload"], default="wrt")
    p_new.add_argument("--title")
    p_new.set_defaults(func=cmd_new)

    sp.add_parser("apps", help="List apps").set_defaults(func=cmd_apps)

    p_build = sp.add_parser("build", help="Build app artifact into out/")
    p_build.add_argument("app")
    p_build.set_defaults(func=cmd_build)

    p_deploy = sp.add_parser("deploy", help="Build (unless --artifact) and push to phone")
    p_deploy.add_argument("app", nargs="?", default="")
    p_deploy.add_argument("--artifact", help="Skip build; push this file")
    p_deploy.add_argument("--dest", default=PHONE_DEVDROP)
    p_deploy.set_defaults(func=cmd_deploy)

    p_it = sp.add_parser("iterate", help="Watch sources; rebuild + deploy on change")
    p_it.add_argument("app")
    p_it.add_argument("--dest", default=PHONE_DEVDROP)
    p_it.add_argument("--debounce", type=float, default=0.6)
    p_it.set_defaults(func=cmd_iterate)

    p_test = sp.add_parser("test", help="Smoke-test device push path")
    p_test.add_argument("app", nargs="?", default="")
    p_test.set_defaults(func=cmd_test)

    p_sdk = sp.add_parser("sdk", help="Symbian native SDK (Docker/gnupoc)")
    ssp = p_sdk.add_subparsers(dest="sdk_cmd", required=True)
    ssp.add_parser("status", help="SDK / Docker / vendor status").set_defaults(func=cmd_sdk)
    ssp.add_parser("fetch", help="Download gnupoc + GCCE + Symbian^3 SDK").set_defaults(func=cmd_sdk)
    p_bi = ssp.add_parser("build-image", help="docker build symbian-sdk image")
    p_bi.add_argument("--no-cache", action="store_true")
    p_bi.set_defaults(func=cmd_sdk)
    p_su = ssp.add_parser("setup", help="fetch (if needed) + build image")
    p_su.add_argument("--no-cache", action="store_true")
    p_su.set_defaults(func=cmd_sdk)
    ssp.add_parser("shell", help="Interactive shell in SDK container").set_defaults(func=cmd_sdk)

    p_pb = sp.add_parser(
        "proxybrowse",
        help="Start macOS proxy browser host (E7 640×360 → phone JPEG)",
    )
    p_pb.add_argument("--port", type=int, default=8765)
    p_pb.add_argument("--url", default="https://example.com")
    p_pb.add_argument("--headless", action="store_true")
    p_pb.set_defaults(func=cmd_proxybrowse)

    return p


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    # allow `sym deploy app` without empty app when --artifact set
    parser = build_parser()
    ns = parser.parse_args(argv)
    if ns.cmd == "deploy" and not ns.artifact and not ns.app:
        _die("deploy needs <app> or --artifact")
    if ns.cmd == "deploy" and ns.artifact and not ns.app:
        ns.app = ""  # unused
    try:
        ns.func(ns)
    except DeviceError as e:
        _die(str(e))
    except FileNotFoundError as e:
        _die(str(e))
    except FileExistsError as e:
        _die(str(e))
    except ValueError as e:
        _die(str(e))
    except KeyboardInterrupt:
        print()
        raise SystemExit(130) from None


if __name__ == "__main__":
    main()
