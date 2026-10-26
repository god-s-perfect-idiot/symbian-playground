---
name: e7-remount
description: >-
  Unmount and remount the Nokia E7-00 mass-storage volume without unplugging
  USB. Use when the user wants to free the phone for File Mgr / install / normal
  use after deploy, remount for Mac push/pull, or mentions unmount, remount,
  eject, reattach, or using the phone without unplugging.
---

# E7 unmount / remount (no unplug)

Mass storage locks the phone’s disk while mounted on the Mac. Eject to use the
E7; remount when the harness needs `./sym push|pull|deploy|ls` again. **Never**
shell `diskutil` / `cp` / `ls` on `/Volumes/…` — use `./sym` only.

## Commands

```bash
./sym unmount   # eject volume → phone can use storage; cable stays in
./sym remount   # USB reset + remount mass storage
./sym doctor    # verify usb + volume after either step
```

`./sym reset-usb` / `./sym ensure` remain aliases-ish of the remount path; prefer
`./sym remount`.

## When to run what

| Goal | Action |
|------|--------|
| Just deployed; install on phone | `./sym unmount` → tell user: File Mgr → Installs/devdrop |
| User finished on phone; need Mac I/O | Unlock phone, USB **Mass storage**, then `./sym remount` |
| Volume flaky / missing | `./sym remount` then `./sym doctor` |
| Still missing after remount | `./sym reset-usb`; if USB absent: cable / unlock / Mass storage |

## Agent workflow

1. Run the matching `./sym` command (do not invent Finder eject scripts).
2. Confirm with `./sym doctor` (expect `volume: OK` after remount, `MISSING` after unmount).
3. After **unmount**: remind user the cable can stay plugged; open **File Mgr → Installs/devdrop** on the unlocked E7.
4. After **remount**: resume `./sym ls|push|pull|deploy` as usual.

## Do / don't

- **Do** keep the USB cable plugged for both steps.
- **Do** require phone unlocked + Mass storage before remount.
- **Don't** unplug/replug as the first fix.
- **Don't** touch `/Volumes/NO NAME` with shell `cp`/`ls` (macOS TCC).
