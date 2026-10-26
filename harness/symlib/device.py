from __future__ import annotations

import json
import plistlib
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from .paths import E7_PID, NOKIA_VID, PHONE_DEVDROP, PHONE_DROP, VOLUME_CANDIDATES


class DeviceError(RuntimeError):
    pass


@dataclass
class UsbDevice:
    present: bool
    product: str = ""
    serial: str = ""
    vid: int = 0
    pid: int = 0
    mass_storage: bool = False


@dataclass
class Volume:
    name: str
    mount_point: str
    disk: str = ""
    media_name: str = ""
    size_gb: float = 0.0
    used_gb: float = 0.0
    accessible: bool = False


def _run(cmd: list[str], check: bool = True, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=check, text=True, capture_output=True, timeout=timeout)


def _osascript(script: str, timeout: int = 120) -> str:
    r = _run(["osascript", "-e", script], check=False, timeout=timeout)
    if r.returncode != 0:
        err = (r.stderr or r.stdout or "").strip()
        raise DeviceError(f"AppleScript failed: {err}")
    return (r.stdout or "").strip()


def usb_status() -> UsbDevice:
    try:
        import usb.core  # type: ignore
    except ImportError as e:
        raise DeviceError("pyusb missing; use repo .venv (`./sym` handles this)") from e

    dev = usb.core.find(idVendor=NOKIA_VID, idProduct=E7_PID)
    if dev is None:
        any_n = usb.core.find(idVendor=NOKIA_VID)
        if any_n is None:
            return UsbDevice(present=False)
        return UsbDevice(
            present=True,
            product=getattr(any_n, "product", None) or f"Nokia:{any_n.idProduct:04x}",
            serial=getattr(any_n, "serial_number", None) or "",
            vid=int(any_n.idVendor),
            pid=int(any_n.idProduct),
            mass_storage=False,
        )

    msc = False
    try:
        for cfg in dev:
            for intf in cfg:
                if int(intf.bInterfaceClass) == 8:
                    msc = True
    except Exception:
        msc = True

    return UsbDevice(
        present=True,
        product=getattr(dev, "product", None) or "E7-00",
        serial=getattr(dev, "serial_number", None) or "",
        vid=int(dev.idVendor),
        pid=int(dev.idProduct),
        mass_storage=msc,
    )


def usb_reset() -> None:
    import usb.core  # type: ignore

    dev = usb.core.find(idVendor=NOKIA_VID, idProduct=E7_PID)
    if dev is None:
        raise DeviceError("Nokia E7-00 not on USB")
    try:
        dev.reset()
    except Exception as e:
        raise DeviceError(f"USB reset failed: {e}") from e


def _volume_from_mount(name: str) -> Optional[Volume]:
    mp = f"/Volumes/{name}"
    if not Path(mp).exists():
        return None
    try:
        raw = subprocess.check_output(["diskutil", "info", "-plist", mp])
        pl = plistlib.loads(raw)
    except Exception:
        return Volume(name=name, mount_point=mp, accessible=_can_list_mount(name))

    media = str(pl.get("MediaName") or "")
    disk_id = str(pl.get("DeviceIdentifier") or "")
    # MediaName often lives on the whole disk, not the volume
    if not media and disk_id:
        # disk11s1 → disk11 (do not split on every "s")
        whole = ""
        if disk_id.startswith("disk"):
            import re as _re

            m = _re.fullmatch(r"(disk\d+)(s\d+)?", disk_id)
            whole = m.group(1) if m else ""
        if whole:
            try:
                wraw = subprocess.check_output(["diskutil", "info", "-plist", whole])
                media = str(plistlib.loads(wraw).get("MediaName") or "")
            except Exception:
                pass
    total = float(pl.get("TotalSize") or 0)
    fre = float(pl.get("FreeSpace") or 0)
    fs = str(pl.get("FilesystemName") or pl.get("FilesystemUserVisibleName") or "")
    is_phone = media == "S60" or name in VOLUME_CANDIDATES
    if not is_phone and name != "NO NAME":
        if not usb_status().present:
            return None
        if "FAT" not in fs.upper() and "MS-DOS" not in fs.upper():
            return None

    return Volume(
        name=name,
        mount_point=mp,
        disk=disk_id,
        media_name=media,
        size_gb=round(total / 1e9, 2) if total else 0.0,
        used_gb=round((total - fre) / 1e9, 2) if total else 0.0,
        accessible=_can_list_mount(name),
    )


def _can_list_mount(volume_name: str) -> bool:
    mp = Path("/Volumes") / volume_name
    try:
        next(mp.iterdir())
        return True
    except Exception:
        pass
    try:
        _osascript(f'tell application "Finder" to count items of disk "{volume_name}"')
        return True
    except DeviceError:
        return False


def list_volumes() -> list[Volume]:
    try:
        names = [n for n in Path("/Volumes").iterdir() if n.name != "Macintosh HD"]
    except Exception:
        return []
    out: list[Volume] = []
    for n in names:
        v = _volume_from_mount(n.name)
        if v:
            out.append(v)
    return out


def find_volume(wait: float = 0) -> Optional[Volume]:
    deadline = time.time() + max(0.0, wait)
    while True:
        vols = list_volumes()
        for pref in VOLUME_CANDIDATES:
            for v in vols:
                if v.name == pref or v.media_name == "S60":
                    return v
        if vols:
            return vols[0]
        if time.time() >= deadline:
            return None
        time.sleep(0.4)


def _try_mount_phone_disk() -> None:
    r = _run(["diskutil", "list", "-plist", "physical"], check=False)
    if r.returncode != 0 or not r.stdout:
        return
    try:
        pl = plistlib.loads(r.stdout.encode())
    except Exception:
        raw = subprocess.check_output(["diskutil", "list", "-plist", "physical"])
        pl = plistlib.loads(raw)
    for disk in pl.get("AllDisksAndPartitions", []):
        for part in disk.get("Partitions", []) or []:
            content = str(part.get("Content") or "")
            name = str(part.get("VolumeName") or "")
            ident = str(part.get("DeviceIdentifier") or "")
            if not ident:
                continue
            if "FAT" in content.upper() or name in VOLUME_CANDIDATES or name == "NO NAME":
                _run(["diskutil", "mount", ident], check=False)


def ensure_volume(timeout: float = 30, reset_if_missing: bool = True) -> Volume:
    vol = find_volume(wait=1.5)
    if vol:
        return vol
    if reset_if_missing and usb_status().present:
        usb_reset()
        time.sleep(2.5)
        _try_mount_phone_disk()
        vol = find_volume(wait=timeout)
        if vol:
            return vol
    raise DeviceError(
        "Phone mass storage not mounted. Unlock phone, choose Mass storage, "
        "then run: ./sym remount"
    )


def unmount_volume() -> Volume:
    """Eject phone mass storage so the E7 can use its own disk (cable stays in)."""
    vol = find_volume()
    if not vol:
        raise DeviceError("Phone volume not mounted (already free for phone use)")
    target = vol.disk or vol.mount_point
    r = _run(["diskutil", "eject", target], check=False)
    if r.returncode != 0:
        # Fallback: unmount volume only (keeps disk attached)
        r2 = _run(["diskutil", "unmount", "force", vol.mount_point], check=False)
        if r2.returncode != 0:
            err = (r.stderr or r2.stderr or r.stdout or r2.stdout or "").strip()
            raise DeviceError(f"eject failed: {err}")
    # Confirm gone (brief wait for DiskArbitration)
    deadline = time.time() + 8
    while time.time() < deadline:
        if find_volume() is None:
            return vol
        time.sleep(0.3)
    if find_volume() is not None:
        raise DeviceError(f"volume still mounted at {vol.mount_point}")
    return vol


def remount_volume(timeout: float = 25) -> Volume:
    """USB reset + remount mass storage without unplugging."""
    usb = usb_status()
    if not usb.present:
        raise DeviceError(
            "Nokia E7-00 not on USB. Keep cable plugged; unlock phone; Mass storage"
        )
    try:
        usb_reset()
    except DeviceError:
        # Still try to mount whatever disk is already presented
        pass
    time.sleep(2.5)
    _try_mount_phone_disk()
    vol = find_volume(wait=timeout)
    if vol:
        return vol
    # Second chance: ensure_volume may reset again
    return ensure_volume(timeout=timeout, reset_if_missing=True)


def phone_ls(path: str = "") -> list[str]:
    vol = ensure_volume()
    if not path:
        out = _osascript(f'tell application "Finder" to get name of every item of disk "{vol.name}"')
    else:
        parts = [p for p in path.replace("\\", "/").split("/") if p]
        folder_ref = f'disk "{vol.name}"'
        for p in parts:
            folder_ref = f'folder "{p}" of {folder_ref}'
        out = _osascript(f'tell application "Finder" to get name of every item of {folder_ref}')
    if not out:
        return []
    return [x.strip() for x in out.split(",") if x.strip()]


def phone_mkdir(path: str) -> None:
    vol = ensure_volume()
    parts = [p for p in path.replace("\\", "/").split("/") if p]
    walked: list[str] = []
    for part in parts:
        parent = _folder_ref(vol.name, walked)
        existing = phone_ls("/".join(walked))
        if part not in existing:
            _osascript(
                f'tell application "Finder" to make new folder at {parent} with properties {{name:"{part}"}}'
            )
        walked.append(part)


def _folder_ref(vol_name: str, parts: list[str]) -> str:
    ref = f'disk "{vol_name}"'
    for p in parts:
        ref = f'folder "{p}" of {ref}'
    return ref


def phone_push(local: Path, dest_dir: str = PHONE_DEVDROP) -> str:
    local = local.resolve()
    if not local.is_file():
        raise DeviceError(f"not a file: {local}")
    vol = ensure_volume()
    phone_mkdir(dest_dir)
    parts = [p for p in dest_dir.replace("\\", "/").split("/") if p]
    folder_ref = _folder_ref(vol.name, parts)
    posix = str(local)
    script = f'''
set src to POSIX file "{posix}" as alias
tell application "Finder"
  set dest to {folder_ref}
  duplicate src to dest with replacing
end tell
'''
    _osascript(script, timeout=300)
    return f"{dest_dir}/{local.name}"


def phone_pull(remote_rel: str, dest: Path) -> Path:
    vol = ensure_volume()
    parts = [p for p in remote_rel.replace("\\", "/").split("/") if p]
    if not parts:
        raise DeviceError("remote path required")
    name = parts[-1]
    folder_ref = _folder_ref(vol.name, parts[:-1])
    dest = dest.resolve()
    if dest.suffix == "" or dest.is_dir():
        dest.mkdir(parents=True, exist_ok=True)
        dest_dir = dest
        final = dest_dir / name
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest_dir = dest.parent
        final = dest

    script = f'''
tell application "Finder"
  set f to file "{name}" of {folder_ref}
  set destFolder to POSIX file "{dest_dir}" as alias
  duplicate f to destFolder with replacing
end tell
'''
    _osascript(script, timeout=300)
    pulled = dest_dir / name
    if final != pulled and pulled.exists():
        pulled.replace(final)
    return final


def status_dict() -> dict:
    usb = usb_status()
    vol = find_volume()
    return {
        "usb": asdict(usb),
        "volume": asdict(vol) if vol else None,
        "drop": PHONE_DEVDROP,
        "installs": PHONE_DROP,
    }


def status_json() -> str:
    return json.dumps(status_dict(), indent=2)
