# Agent playbook — Symbian E7 harness

This repo is a **tight build/deploy loop** for a USB-connected **Nokia E7-00** (Symbian^3 / S60).
Always drive work through `./sym`. Do not invent alternate toolchains or copy files onto `/Volumes/…` with shell `cp`.

## First actions every session

```bash
./sym doctor          # must print "doctor: ready"
./sym apps            # list apps
./sym help            # this playbook summary
```

If doctor fails: fix USB/volume/SDK using hints below, then continue. Do not ask the user to re-explain the harness.

## UI mockup gate (required)

Before implementing or redesigning an app UI (WRT or native), agents **must**:

1. Write / update `apps/<name>/mockup.html` — phone-sized preview (E7 is **640×360** landscape). Keep it simple; no purple “AI landing page” chrome.
2. Show that mockup to the user for **approval** (open the file or render it in chat).
3. Only after explicit approval: implement, build, and `./sym deploy <name>`.

`./sym new` scaffolds a stub `mockup.html`. Iterate the mockup first; treat code as secondary until the UX is signed off.

## Golden loop

| Goal | Commands |
|------|----------|
| Fast HTML/JS app | `./sym new <name>` → **mockup approval** → edit `apps/<name>/src/` → `./sym deploy <name>` or `./sym iterate <name>` |
| Native C++ SIS | `./sym new <name> --type native` → **mockup approval** → edit sources → `./sym build <name>` → `./sym deploy <name>` |
| Proxy web browser | Mac: `./sym proxybrowse`. Phone (preferred): Nokia Browser → `http://&lt;mac-lan-ip&gt;:8765/phone`. Optional WRT: `./sym deploy proxybrowse` (if install says Feature not supported, use Browser path) |
| Push existing file | `./sym deploy --artifact out/<file>` |
| Smoke device I/O | `./sym test` or `./sym test <name>` |

**App names are bare** (`hello`, not `apps/hello`). Artifacts land in `out/`. Phone drop folder: `Installs/devdrop`.

On phone after deploy: **File Manager → Installs → devdrop → open the package**.

## App types

| type | scaffold | artifact | when |
|------|----------|----------|------|
| `wrt` (default) | HTML/JS widget | `out/<name>.wgz` | preferred for UI iteration |
| `native` | Symbian C++ MMP | `out/<name>.sisx` (+ `.sis`) | needs SDK image |
| `payload` | raw files | `out/<name>.zip` | ad-hoc drops |

Each app: `apps/<name>/app.yaml` + type-specific tree. Prefer editing an existing app over scaffolding duplicates.

## Device rules (macOS)

1. Phone **unlocked**, USB **Mass storage** (not PC Suite / MTP).
2. Volume usually mounts as `/Volumes/NO NAME` (FAT / media name `S60`).
3. **Never** use shell `cp`/`ls` on the volume — TCC blocks Cursor/Terminal. Use:
   - `./sym ls [path]`
   - `./sym push <file> [--dest Installs/devdrop]`
   - `./sym pull <remote> [--dest out/pull]`
4. Flaky USB → `./sym remount` (or `./sym reset-usb` then `./sym ensure`).
5. After deploy, free the phone without unplugging: `./sym unmount` → use File Mgr on E7 → `./sym remount` when you need Mac I/O again.
6. FAT rejects leading-dot filenames (e.g. `.probe`). Harness already avoids them.

## Native SDK (Docker)

Image: `symbian-sdk:s3` (GnuPoc + CodeSourcery GCCE + Symbian^3 + OpenSSL 1.0.2 + patched Perl tools).

Runtime: **Colima x86_64** (not Docker Desktop ARM). Harness auto-sets `DOCKER_HOST` to `~/.colima/docker.sock`.

```bash
./sym sdk status                 # docker/colima/image/vendor
./sym sdk setup                  # only if image MISSING (long; needs ≥20GB free)
./sym sdk shell                  # interactive EPOCROOT
./sym build <native-app>         # abld gcce urel → makesis → signsis
```

**Do not** rebuild the image unless `./sym sdk status` shows `image: false`, vendor changed, or Dockerfile/install script changed. Rebuilds take ~30–45+ minutes and need free disk.

Vendor bits live under `sdk/vendor/` (gitignored; fetched by `./sym sdk fetch`).

### Native layout conventions

- `group/bld.inf` + `group/<name>.mmp`
- `src/main.cpp`, `data/*.rss`, `pkg/<name>.pkg`
- MMP must include `\epoc32\include\mw` (and usually `platform`, `app`)
- PKG format (makesis-4):

```
&EN
#{"Title"},(0xUID),1,0,0,TYPE=SA
%{"SymDev"}
:"Title"
"epoc32\release\gcce\urel\<name>.exe"-"!:\sys\bin\<name>.exe"
…
```

## Harness code map

| Path | Role |
|------|------|
| `./sym` | Entrypoint (bootstraps `.venv` + pyusb) |
| `harness/symlib/cli.py` | CLI |
| `harness/symlib/device.py` | USB + Finder volume I/O |
| `harness/symlib/app.py` | scaffold / build / load |
| `harness/symlib/sdk.py` | Colima/Docker/native build |
| `harness/symlib/native_template.py` | native scaffold |
| `sdk/Dockerfile` + `install-in-container.sh` | image build |
| `apps/` | user apps (`apps/<name>/mockup.html` = UI approval preview) |
| `out/` | build artifacts (gitignored) |

## Failure cheat-sheet

| Symptom | Fix |
|---------|-----|
| `volume: MISSING` | Unlock phone, Mass storage, `./sym remount` |
| Need phone UI / install after deploy | `./sym unmount` (cable stays in), then later `./sym remount` |
| Finder / `-8082` / TCC | Use `./sym push` only; no leading-dot names |
| `docker=NO` / `colima=NO` | `colima start --arch x86_64` (or `./sym sdk setup`) |
| `image MISSING` | `./sym sdk setup` (watch disk: need tens of GB free) |
| `defined(%hash)` / Perl errors in abld | Image should already be patched; if rebuilding, `install-in-container.sh` applies fixes |
| makesis OpenSSL errors | Image must use OpenSSL **1.0.2** at `/opt/openssl-1.0` |
| `avkon.rh: No such file` | Add `SYSTEMINCLUDE \epoc32\include\mw` to MMP |
| `pkg: Expected } read ,` | Vendor line is `%{"SymDev"}` (one string) |
| Disk full mid-docker-build | Free space; `colima delete` only as last resort (loses image) |

## Do / don't

**Do**

- Run `./sym doctor` before claiming device/SDK issues
- Ship `apps/<name>/mockup.html` and get UI approval before coding the real app
- Prefer WRT for UI experiments; native only when SIS/C++ is required
- Keep changes inside `apps/<name>/` unless fixing the harness itself
- Deploy with `./sym deploy <name>`; tell user to open File Mgr on phone

**Don't**

- Bypass `./sym` for phone file I/O
- Rebuild SDK image casually
- Pass `apps/foo` as the app argument (bare `foo`)
- Commit `sdk/vendor/`, `.venv/`, or huge binaries
- Implement UI (WRT or SIS) without an approved mockup
- Use purple/generic “AI landing page” patterns for WRT UI — keep widgets simple and phone-sized

## Minimal verify

```bash
./sym doctor
./sym test hello          # or whatever WRT app exists
./sym build hello_sis     # if native image present
./sym deploy hello_sis --artifact out/hello_sis.sisx
```
