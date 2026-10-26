from __future__ import annotations

import os
import re
import shutil
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .paths import APPS, OUT

# Symbian WRT installer is picky: FAT/MS-DOS zip metadata + pre-2020 mtimes
# avoid odd failures ("Feature not supported") on device.
_WGZ_MTIME = (2014, 6, 1, 12, 0, 0)


@dataclass
class AppMeta:
    name: str
    type: str  # wrt | native | payload
    uid: str
    title: str
    root: Path

    @property
    def dist_name(self) -> str:
        if self.type == "wrt":
            return f"{self.name}.wgz"
        if self.type == "native":
            return f"{self.name}.sis"
        return f"{self.name}.sis"


def _parse_yaml_lite(text: str) -> dict[str, str]:
    """Minimal KEY: value parser (no deps)."""
    out: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        out[k.strip()] = v.strip().strip("\"'")
    return out


def normalize_app_name(name: str) -> str:
    """Accept `hello`, `apps/hello`, or trailing slashes."""
    n = name.strip().rstrip("/")
    if n.startswith("apps/"):
        n = n[len("apps/") :]
    return Path(n).name


def load_app(name: str) -> AppMeta:
    name = normalize_app_name(name)
    root = APPS / name
    meta_path = root / "app.yaml"
    if not meta_path.is_file():
        known = ", ".join(list_apps()) or "(none)"
        raise FileNotFoundError(f"app not found: {name} ({meta_path}). known: {known}")
    raw = _parse_yaml_lite(meta_path.read_text())
    return AppMeta(
        name=raw.get("name", name),
        type=raw.get("type", "wrt"),
        uid=raw.get("uid", "0xE0000001"),
        title=raw.get("title", name),
        root=root,
    )


def list_apps() -> list[str]:
    if not APPS.is_dir():
        return []
    return sorted(p.name for p in APPS.iterdir() if (p / "app.yaml").is_file())


def allocate_uid(name: str) -> str:
    """Deterministic unprotected UID in 0xExxxxxxx range from name."""
    h = 0
    for ch in name:
        h = (h * 131 + ord(ch)) & 0x0FFFFFFF
    return f"0xE{h:07X}"


def scaffold(name: str, app_type: str = "wrt", title: Optional[str] = None) -> AppMeta:
    if not re.fullmatch(r"[a-z][a-z0-9_]{1,31}", name):
        raise ValueError("name must be lowercase [a-z][a-z0-9_]{1,31}")
    root = APPS / name
    if root.exists():
        raise FileExistsError(f"apps/{name} already exists")
    root.mkdir(parents=True)
    uid = allocate_uid(name)
    title = title or name.replace("_", " ").title()
    (root / "app.yaml").write_text(
        f"""name: {name}
type: {app_type}
uid: {uid}
title: {title}
""",
        encoding="utf-8",
    )
    if app_type == "wrt":
        src = root / "src"
        src.mkdir()
        (src / "info.plist").write_text(
            f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Nokia//DTD PLIST 1.0//EN" "http://www.nokia.com/nokia_dtd/plist1.0.dtd">
<plist version="1.0">
<dict>
  <key>DisplayName</key>
  <string>{title}</string>
  <key>Identifier</key>
  <string>com.symdev.{name}</string>
  <key>Version</key>
  <string>1.0.0</string>
  <key>MainHTML</key>
  <string>index.html</string>
  <key>AllowNetworkAccess</key>
  <false/>
</dict>
</plist>
""",
            encoding="utf-8",
        )
        (src / "index.html").write_text(
            f"""<!DOCTYPE html>
<html>
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>
  <title>{title}</title>
  <style>
    body {{ margin: 0; font-family: sans-serif; background: #0b1020; color: #e8eefc; }}
    main {{ padding: 24px; }}
    h1 {{ font-size: 22px; margin: 0 0 8px; }}
    p {{ opacity: 0.85; }}
    button {{
      margin-top: 16px; padding: 10px 16px; border: 0; border-radius: 6px;
      background: #3d7eff; color: white; font-size: 16px;
    }}
  </style>
</head>
<body>
  <main>
    <h1>{title}</h1>
    <p>Running on device via sym harness.</p>
    <button onclick="document.getElementById('n').textContent = (+document.getElementById('n').textContent) + 1">
      Tap: <span id="n">0</span>
    </button>
  </main>
</body>
</html>
""",
            encoding="utf-8",
        )
    elif app_type == "native":
        from .native_template import write_native_app

        write_native_app(root, name, uid, title)
    else:
        (root / "payload").mkdir()
        (root / "payload" / "README.txt").write_text(
            "Drop prebuilt files here; sym build packs them for deploy.\n",
            encoding="utf-8",
        )

    # UI mockup stub — agents must flesh this out and get approval before coding UI
    (root / "mockup.html").write_text(
        f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{title} — UI mockup (E7)</title>
  <style>
    body {{ margin: 0; font-family: sans-serif; background: #111; color: #eee; }}
    .note {{ padding: 16px; font-size: 13px; opacity: 0.8; max-width: 40rem; }}
    .phone {{
      width: min(100%, 640px); aspect-ratio: 640 / 360; margin: 0 16px 24px;
      background: #1a1a1a; border: 1px solid #333; display: flex;
      align-items: center; justify-content: center; font-size: 18px;
    }}
  </style>
</head>
<body>
  <p class="note">Stub mockup for <strong>{title}</strong>. Replace with a real E7 640×360 UI preview and get approval before implementing (see AGENTS.md).</p>
  <div class="phone">{title}</div>
</body>
</html>
""",
        encoding="utf-8",
    )

    return load_app(name)


def build_wrt(app: AppMeta) -> Path:
    src = app.root / "src"
    if not (src / "index.html").is_file() or not (src / "info.plist").is_file():
        raise FileNotFoundError(f"{app.name}: need src/index.html and src/info.plist")
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / f"{app.name}.wgz"
    if out.exists():
        out.unlink()
    # wgz == zip of src contents at archive root (Symbian-safe ZIP, no __MACOSX)
    files = sorted(
        p for p in src.rglob("*") if p.is_file() and not p.name.startswith(".")
    )
    if not files:
        raise FileNotFoundError(f"{app.name}: src/ is empty")
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=False) as zf:
        for path in files:
            rel = path.relative_to(src).as_posix()
            info = zipfile.ZipInfo(rel, date_time=_WGZ_MTIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 0  # MS-DOS
            info.external_attr = 0o644 << 16
            zf.writestr(info, path.read_bytes())
    ts = time.mktime(_WGZ_MTIME + (0, 0, -1))
    os.utime(out, (ts, ts))
    return out


def build_payload(app: AppMeta) -> Path:
    """Zip payload folder as a deployable blob (install manually / via x-plore)."""
    payload = app.root / "payload"
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / f"{app.name}.zip"
    if out.exists():
        out.unlink()
    archive = shutil.make_archive(str(out.with_suffix("")), "zip", root_dir=payload)
    Path(archive).replace(out)
    return out


def build_native(app: AppMeta) -> Path:
    from .sdk import SdkError, native_build

    try:
        return native_build(app.root, app.name, app.uid, app.title)
    except SdkError as e:
        raise RuntimeError(str(e)) from e


def build_app(name: str) -> Path:
    app = load_app(name)
    if app.type == "wrt":
        return build_wrt(app)
    if app.type == "payload":
        return build_payload(app)
    if app.type == "native":
        return build_native(app)
    raise ValueError(f"unknown app type: {app.type}")
