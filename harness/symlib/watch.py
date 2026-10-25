from __future__ import annotations

import time
from pathlib import Path
from typing import Callable


def watch_paths(paths: list[Path], on_change: Callable[[], None], debounce: float = 0.6) -> None:
    """Poll mtimes (no extra deps). Ctrl-C to stop."""
    stamp: dict[str, float] = {}

    def snapshot() -> dict[str, float]:
        out: dict[str, float] = {}
        for root in paths:
            if root.is_file():
                out[str(root)] = root.stat().st_mtime
                continue
            if not root.is_dir():
                continue
            for p in root.rglob("*"):
                if p.is_file() and not any(part.startswith(".") for part in p.parts):
                    try:
                        out[str(p)] = p.stat().st_mtime
                    except OSError:
                        pass
        return out

    stamp = snapshot()
    pending = False
    last_fire = 0.0
    while True:
        time.sleep(0.35)
        now = snapshot()
        if now != stamp:
            stamp = now
            pending = True
        if pending and (time.time() - last_fire) >= debounce:
            pending = False
            last_fire = time.time()
            on_change()
