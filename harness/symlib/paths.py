from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APPS = ROOT / "apps"
OUT = ROOT / "out"
HARNESS = ROOT / "harness"
VENV_PYTHON = ROOT / ".venv" / "bin" / "python"

# Mass-storage drop folder on the phone (created on first deploy)
PHONE_DROP = "Installs"
PHONE_DEVDROP = "Installs/devdrop"

NOKIA_VID = 0x0421
E7_PID = 0x0333
VOLUME_CANDIDATES = ("NO NAME", "E7-00", "Nokia E7", "S60")
