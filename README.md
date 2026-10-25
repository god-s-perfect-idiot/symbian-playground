# Symbian E7 harness

Build, push, and iterate apps on a USB-connected **Nokia E7-00** (Symbian^3 / S60) from macOS.

Everything goes through **`./sym`**. Do not copy files onto `/Volumes/…` with shell `cp`/`ls` — macOS TCC blocks that; the harness uses Finder under the hood.

Agents / automation: start with [`AGENTS.md`](AGENTS.md). This README is the human setup + day-to-day guide.

---

## What you get

| Piece | Role |
|-------|------|
| `./sym` | CLI entrypoint (bootstraps `.venv`, runs `harness/symlib`) |
| WRT apps | HTML/JS widgets → `.wgz` (fast UI loop) |
| Native apps | Symbian C++ → `.sis` / `.sisx` via Docker image `symbian-sdk:s3` |
| Device I/O | `ls` / `push` / `pull` / `deploy` onto phone mass-storage |
| `proxybrowse` | Optional Mac-side proxy browser for the phone |

Included sample apps under `apps/`:

| App | Type | Notes |
|-----|------|-------|
| `hello` | WRT | Minimal HTML widget |
| `hello_sis` | native | Minimal C++ SIS |
| `pomodoro` | native | Timer example |
| `proxybrowse` | WRT + host | Phone UI + Mac proxy server |

---

## Requirements

### Always (WRT + device I/O)

- macOS (tested path; volume access is Finder/TCC-based)
- Python 3
- USB cable + **Nokia E7-00** unlocked, USB mode **Mass storage** (not PC Suite / MTP)
- Phone volume typically mounts as `/Volumes/NO NAME` (FAT, media name `S60`)

`./sym` creates `.venv` and installs `requirements.txt` (`pyusb`) on first run.

### Native SIS builds only

- [Colima](https://github.com/abiosoft/colima) **x86_64** + Docker CLI (`brew install colima docker`)
- ~20GB+ free disk for the SDK image (first `./sym sdk setup` is slow: 30–45+ minutes)
- Vendor SDK bits under `sdk/vendor/` (gitignored; fetched by the harness)

Do **not** use Docker Desktop ARM as the runtime — the harness points `DOCKER_HOST` at `~/.colima/docker.sock`.

---

## Setup

```bash
git clone git@github.com:god-s-perfect-idiot/symbian-playground.git
cd symbian-playground

# First command bootstraps .venv
./sym doctor          # must print "doctor: ready" when phone + tools are OK
./sym help
./sym apps
```

### Phone

1. Unlock the E7.
2. Connect USB → choose **Mass storage**.
3. Confirm `./sym doctor` sees the volume (not `volume: MISSING`).
4. If flaky: `./sym reset-usb` then `./sym ensure`.

### Native SDK (only if you need `.sisx`)

```bash
./sym sdk status      # docker / colima / image / vendor
./sym sdk setup       # fetch vendor + build image — once, long, disk-hungry
```

Rebuild the image only when `./sym sdk status` shows `image: false`, or when `sdk/Dockerfile` / `sdk/install-in-container.sh` / vendor intentionally change. Details: [`sdk/README.md`](sdk/README.md).

---

## Quick start

### 1. WRT widget (preferred for UI)

```bash
./sym new mywidget                  # scaffolds apps/mywidget (type: wrt)
# edit apps/mywidget/src/index.html (+ info.plist as needed)
./sym deploy mywidget               # → out/mywidget.wgz → Installs/devdrop
# or watch-rebuild-push:
./sym iterate mywidget
```

On the phone: **File Manager → Installs → devdrop → open the `.wgz`**.

App names are **bare** (`mywidget`), never `apps/mywidget`.

### 2. Native C++ SIS

```bash
./sym new myapp --type native
# edit apps/myapp/src/main.cpp, data/*.rss, group/*.mmp, pkg/*.pkg
./sym build myapp                   # abld gcce urel → makesis → signsis
./sym deploy myapp                  # → out/myapp.sisx → Installs/devdrop
```

Install from **File Mgr → Installs → devdrop** on the unlocked phone.

### 3. Smoke-test device I/O

```bash
./sym test                          # USB + push probe
./sym test hello                    # also builds/deploys hello if present
```

### 4. Proxy browse (optional)

```bash
./sym proxybrowse                   # Mac host: Chromium frames + click API
# On phone (preferred): Nokia Browser → http://<mac-lan-ip>:8765/phone
# Optional WRT package: ./sym deploy proxybrowse
#   (if install says "Feature not supported", use the Browser URL path)
```

---

## App types

| Type | Scaffold | Artifact | When to use |
|------|----------|----------|-------------|
| `wrt` (default) | `apps/<name>/src/` HTML/JS + `info.plist` | `out/<name>.wgz` | Fast UI iteration |
| `native` | MMP / RSS / PKG / C++ | `out/<name>.sisx` (+ `.sis`) | Needs SIS or native APIs |
| `payload` | Arbitrary files | `out/<name>.zip` | Ad-hoc drops |

Each app has `apps/<name>/app.yaml`:

```yaml
name: hello
type: wrt
uid: 0xEF372E8E
title: Hello E7
```

Prefer editing an existing app over scaffolding duplicates.

### WRT layout

```
apps/<name>/
  app.yaml
  src/
    index.html
    info.plist      # DisplayName, Identifier, MainHTML, AllowNetworkAccess, …
```

Keep widgets simple and phone-sized (E7 landscape ~640×360 class). Avoid heavy “landing page” layouts.

### Native layout

```
apps/<name>/
  app.yaml
  group/bld.inf
  group/<name>.mmp
  src/main.cpp
  data/*.rss
  pkg/<name>.pkg
```

MMP must include `\epoc32\include\mw` (and usually `platform`, `app`). PKG vendor line for makesis-4:

```
%{"SymDev"}
```

(one string — a comma-split vendor line breaks the package tool).

---

## Device I/O (macOS)

Never use shell `cp`/`ls` on the phone volume.

| Command | Purpose |
|---------|---------|
| `./sym ls [path]` | List on-device path |
| `./sym push <file> [--dest Installs/devdrop]` | Copy file to phone |
| `./sym pull <remote> [--dest out/pull]` | Copy from phone |
| `./sym deploy <name>` | Build + push artifact to `Installs/devdrop` |
| `./sym deploy --artifact out/foo.sisx` | Push an existing build |
| `./sym reset-usb` / `./sym ensure` | Recover flaky USB / remount |

FAT rejects leading-dot filenames (e.g. `.probe`); the harness already avoids those.

---

## CLI cheat-sheet

```bash
./sym doctor
./sym apps
./sym new <name> [--type wrt|native|payload]
./sym build <name>
./sym deploy <name>
./sym deploy --artifact out/<file>
./sym iterate <name>                 # watch → rebuild → deploy
./sym test [name]
./sym ls [path] | push | pull | reset-usb | ensure
./sym sdk status | setup | shell | fetch | build-image
./sym proxybrowse [--port 8765] [--url …] [--headless]
./sym help
```

Artifacts land in `out/` (gitignored). Phone drop folder: **`Installs/devdrop`**.

---

## Native SDK image

Image tag: **`symbian-sdk:s3`**.

Contents (see [`sdk/README.md`](sdk/README.md)):

- GnuPoc + patched host tools (`makesis`, `bldmake`, `abld`, …)
- CodeSourcery GCCE (`arm-none-symbianelf-g++`)
- Symbian^3 under `/opt/symbian/epocroot/`
- OpenSSL **1.0.2** at `/opt/openssl-1.0` (required by makesis-4)
- Dev certs under `/opt/symbian/certs/`

```bash
./sym sdk status
./sym sdk setup                 # fetch vendor if needed + build image
./sym sdk shell                 # interactive EPOCROOT
./sym build <native-app>
```

Vendor tree `sdk/vendor/` is **not** committed. Fetch via `./sym sdk fetch` / `sdk/fetch-vendor.sh`.

---

## Repo layout

```
./sym                         # entrypoint
AGENTS.md                     # agent/ops playbook
apps/                         # user apps (edit here for features)
harness/symlib/               # CLI, device I/O, scaffold, SDK glue
  cli.py
  device.py
  app.py
  sdk.py
  native_template.py
sdk/
  Dockerfile
  install-in-container.sh
  fetch-vendor.sh
  vendor/                     # gitignored SDK blobs
out/                          # build artifacts (gitignored)
requirements.txt
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `volume: MISSING` | Unlock phone, Mass storage, `./sym reset-usb` |
| Finder / `-8082` / TCC | Use `./sym push` only; no leading-dot names |
| `docker=NO` / `colima=NO` | `colima start --arch x86_64` (or `./sym sdk setup`) |
| `image MISSING` | `./sym sdk setup` (watch free disk) |
| `defined(%hash)` / Perl in abld | Image should already be patched; rebuild only if Dockerfile/install changed |
| makesis OpenSSL errors | Image must use OpenSSL **1.0.2** at `/opt/openssl-1.0` |
| `avkon.rh: No such file` | Add `SYSTEMINCLUDE \epoc32\include\mw` to MMP |
| `pkg: Expected } read ,` | Vendor line is `%{"SymDev"}` (single string) |
| Disk full mid-docker-build | Free space; `colima delete` only as last resort (loses image) |

---

## Development notes

**Do**

- Run `./sym doctor` before debugging device/SDK issues
- Prefer WRT for UI experiments; native only when SIS/C++ is required
- Keep product changes under `apps/<name>/` unless fixing the harness
- After deploy, install from **File Mgr → Installs → devdrop** on the phone

**Don't**

- Bypass `./sym` for phone file I/O
- Rebuild the SDK image casually
- Pass `apps/foo` as the app argument (use bare `foo`)
- Commit `sdk/vendor/`, `.venv/`, or large binaries (`out/`, `.sis` / `.sisx` are ignored)

### Minimal verify

```bash
./sym doctor
./sym test hello
./sym build hello_sis          # if native image present
./sym deploy hello_sis
```
