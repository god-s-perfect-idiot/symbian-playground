from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from .paths import OUT, ROOT

SDK_DIR = ROOT / "sdk"
VENDOR = SDK_DIR / "vendor"
IMAGE = os.environ.get("SYM_SDK_IMAGE", "symbian-sdk:s3")
DOCKERFILE = SDK_DIR / "Dockerfile"


class SdkError(RuntimeError):
    pass


@dataclass
class SdkStatus:
    docker: bool
    colima: bool
    image: bool
    image_name: str
    vendor_sdk: bool
    vendor_csl: bool
    vendor_gnupoc: bool


def _run(cmd: list[str], check: bool = True, cwd: Optional[Path] = None, timeout: Optional[int] = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        check=check,
        text=True,
        capture_output=True,
        cwd=str(cwd) if cwd else None,
        timeout=timeout,
    )


def _colima_docker_socks() -> list[Path]:
    home = Path.home()
    return [
        home / ".colima" / "docker.sock",
        home / ".colima" / "default" / "docker.sock",
    ]


def ensure_docker_host() -> None:
    """Point DOCKER_HOST at Colima when the default Docker context is down."""
    if os.environ.get("DOCKER_HOST"):
        return
    # Prefer an existing listening Colima socket
    for sock in _colima_docker_socks():
        if sock.exists():
            os.environ["DOCKER_HOST"] = f"unix://{sock}"
            return


def docker_ok() -> bool:
    ensure_docker_host()
    r = _run(["docker", "info"], check=False)
    return r.returncode == 0


def colima_ok() -> bool:
    if not shutil.which("colima"):
        return False
    r = _run(["colima", "status"], check=False)
    text = ((r.stdout or "") + (r.stderr or "")).lower()
    return r.returncode == 0 and ("running" in text or "is running" in text)


def ensure_runtime() -> None:
    ensure_docker_host()
    if docker_ok():
        return
    if not shutil.which("colima"):
        raise SdkError(
            "Docker daemon not running and colima not installed. "
            "Install: brew install colima docker && colima start --arch x86_64"
        )
    print("starting colima (x86_64)…")
    r = _run(
        ["colima", "start", "--cpu", "4", "--memory", "6", "--disk", "40", "--arch", "x86_64"],
        check=False,
        timeout=600,
    )
    ensure_docker_host()
    if r.returncode != 0 and not docker_ok():
        raise SdkError(f"colima start failed:\n{r.stderr or r.stdout}")
    # wait for docker
    for _ in range(30):
        ensure_docker_host()
        if docker_ok():
            return
        time.sleep(1)
    raise SdkError("Docker still unavailable after colima start")


def image_present() -> bool:
    if not docker_ok():
        return False
    r = _run(["docker", "image", "inspect", IMAGE], check=False)
    return r.returncode == 0


def vendor_flags() -> tuple[bool, bool, bool]:
    sdk = any(VENDOR.glob("*ymbian*3*sdk*.zip")) or any(VENDOR.glob("Symbian_3_SDK*.zip")) or any(
        VENDOR.glob("Nokia_Symbian_Belle*.zip")
    )
    csl = any(VENDOR.glob("gnu-csl-arm-*.tar.bz2"))
    gnupoc = (VENDOR / "gnupoc-package").is_dir() or any(VENDOR.glob("gnupoc-package*.tar.gz"))
    return sdk, csl, gnupoc


def status() -> SdkStatus:
    sdk, csl, gnupoc = vendor_flags()
    return SdkStatus(
        docker=docker_ok(),
        colima=colima_ok(),
        image=image_present(),
        image_name=IMAGE,
        vendor_sdk=sdk,
        vendor_csl=csl,
        vendor_gnupoc=gnupoc,
    )


def status_json() -> str:
    return json.dumps(asdict(status()), indent=2)


def fetch_vendor() -> None:
    script = SDK_DIR / "fetch-vendor.sh"
    if not script.is_file():
        raise SdkError(f"missing {script}")
    print(f"fetching SDK vendor into {VENDOR} …")
    # stream output
    proc = subprocess.Popen(
        ["bash", str(script)],
        cwd=str(SDK_DIR),
    )
    rc = proc.wait()
    if rc != 0:
        raise SdkError(f"fetch-vendor.sh failed ({rc})")


def build_image(no_cache: bool = False) -> None:
    ensure_runtime()
    sdk, csl, gnupoc = vendor_flags()
    if not (sdk and csl and gnupoc):
        raise SdkError(
            "vendor incomplete — run: ./sym sdk fetch\n"
            f"  sdk={sdk} csl={csl} gnupoc={gnupoc}"
        )
    cmd = [
        "docker",
        "build",
        "--platform",
        "linux/amd64",
        "-t",
        IMAGE,
        "-f",
        str(DOCKERFILE),
        str(SDK_DIR),
    ]
    if no_cache:
        cmd.insert(2, "--no-cache")
    print("building", IMAGE, "… (first build is long)")
    proc = subprocess.Popen(cmd)
    rc = proc.wait()
    if rc != 0:
        raise SdkError(f"docker build failed ({rc})")


def setup(no_cache: bool = False) -> None:
    ensure_runtime()
    sdk, csl, gnupoc = vendor_flags()
    if not (sdk and csl and gnupoc):
        fetch_vendor()
    if not image_present() or no_cache:
        build_image(no_cache=no_cache)
    else:
        print(f"image ready: {IMAGE}")


def docker_run(
    args: list[str],
    *,
    work: Optional[Path] = None,
    interactive: bool = False,
    entry: Optional[list[str]] = None,
) -> int:
    ensure_runtime()
    if not image_present():
        raise SdkError(f"image {IMAGE} missing — run: ./sym sdk setup")
    work = (work or ROOT).resolve()
    cmd = [
        "docker",
        "run",
        "--rm",
        "--platform",
        "linux/amd64",
        "-v",
        f"{work}:/work",
        "-w",
        "/work",
        "-e",
        "EPOCROOT=/opt/symbian/epocroot/",
    ]
    if interactive:
        cmd += ["-it"]
    cmd.append(IMAGE)
    if entry:
        cmd += entry
    else:
        cmd += args
    print("+", " ".join(cmd))
    return subprocess.call(cmd)


def shell() -> int:
    return docker_run([], interactive=True, entry=["bash", "-l"])


def native_build(app_root: Path, app_name: str, uid: str, title: str) -> Path:
    """Build native app inside SDK container → out/<name>.sisx (or .sis)."""
    ensure_runtime()
    if not image_present():
        raise SdkError("SDK image missing — run: ./sym sdk setup")

    OUT.mkdir(parents=True, exist_ok=True)
    # Script executed inside container with /work = repo root
    rel = app_root.resolve().relative_to(ROOT.resolve())
    script = f"""
set -euo pipefail
source /etc/profile.d/symbian-env.sh || true
export EPOCROOT=/opt/symbian/epocroot/
export PATH=/opt/openssl-1.0/bin:/opt/symbian/gnupoc:/opt/symbian/csl-gcc/bin:${{EPOCROOT}}epoc32/tools:$PATH
APP=/work/{rel.as_posix()}
cd "$APP"

if [[ -f group/bld.inf ]]; then
  cd group
  bldmake bldfiles
  abld build gcce urel
  cd ..
elif [[ -f src/bld.inf ]]; then
  cd src
  bldmake bldfiles
  abld build gcce urel
  cd ..
else
  echo "No bld.inf under group/ or src/ — cannot compile" >&2
  exit 2
fi

PKG=$(ls pkg/*.pkg 2>/dev/null | head -1 || true)
if [[ -z "$PKG" ]]; then
  echo "missing pkg/*.pkg" >&2
  exit 2
fi

mkdir -p /work/out
SIS=/work/out/{app_name}.sis
SISX=/work/out/{app_name}.sisx
makesis -d"$EPOCROOT" "$PKG" "$SIS"

# Ensure developer certs exist (image may predate makekeys fix)
if [[ ! -f /opt/symbian/certs/cert.cer || ! -f /opt/symbian/certs/key.key ]]; then
  mkdir -p /opt/symbian/certs
  printf '%s\\n' IN State City SymDev Dev SymDev 'dev@sym.local' \\
    | /opt/symbian/csl-gcc/bin/makekeys -cert -expdays 3650 \\
      /opt/symbian/certs/key.key /opt/symbian/certs/cert.cer || true
fi
if command -v signsis >/dev/null 2>&1 && [[ -f /opt/symbian/certs/cert.cer ]]; then
  signsis "$SIS" "$SISX" /opt/symbian/certs/cert.cer /opt/symbian/certs/key.key none || \\
  signsis "$SIS" "$SISX" /opt/symbian/certs/cert.cer /opt/symbian/certs/key.key || true
fi
if [[ -f "$SISX" ]]; then
  echo "ARTIFACT $SISX"
else
  echo "ARTIFACT $SIS"
fi
"""
    cmd = [
        "docker",
        "run",
        "--rm",
        "--platform",
        "linux/amd64",
        "-v",
        f"{ROOT.resolve()}:/work",
        "-w",
        "/work",
        IMAGE,
        "bash",
        "-lc",
        script,
    ]
    print("+ docker run … native build", app_name)
    proc = subprocess.run(cmd, text=True, capture_output=True)
    print(proc.stdout)
    if proc.returncode != 0:
        print(proc.stderr, flush=True)
        raise SdkError(f"native build failed ({proc.returncode})")
    # parse ARTIFACT line
    artifact: Optional[Path] = None
    for line in (proc.stdout or "").splitlines():
        if line.startswith("ARTIFACT "):
            artifact = Path(line.split(" ", 1)[1].strip())
            # map container path to host
            if str(artifact).startswith("/work/"):
                artifact = ROOT / str(artifact)[len("/work/") :]
    if artifact is None:
        # fallback
        for cand in (OUT / f"{app_name}.sisx", OUT / f"{app_name}.sis"):
            if cand.is_file():
                artifact = cand
                break
    if artifact is None or not artifact.is_file():
        raise SdkError("build finished but no .sis/.sisx in out/")
    return artifact
