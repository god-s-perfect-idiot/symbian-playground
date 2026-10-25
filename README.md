# Symbian E7 harness

Tight build/deploy loop for a USB-connected **Nokia E7-00** (Symbian^3).

**Agents:** read [`AGENTS.md`](AGENTS.md) first — it is the operational playbook.

```bash
./sym doctor                 # USB + volume + SDK
./sym help                   # command cheat-sheet
./sym new hello              # WRT widget (fast)
./sym deploy hello           # → out/hello.wgz → Installs/devdrop
./sym iterate hello          # rebuild + push on save

./sym new hellosis --type native
./sym deploy hellosis        # → out/hellosis.sisx (needs Docker/Colima image)
```

## App types

| type | artifact | notes |
|------|----------|--------|
| `wrt` (default) | `.wgz` | HTML/JS — fastest iteration |
| `native` | `.sis` / `.sisx` | C++ via Colima `symbian-sdk:s3` |
| `payload` | `.zip` | pack arbitrary files |

## Device

- Unlock the phone; USB mode **Mass storage**.
- Volume flaky → `./sym reset-usb`.
- macOS TCC blocks direct `/Volumes/…` access from Terminal/Cursor — always use `./sym` push/ls/pull (Finder under the hood).

## Native SDK

```bash
./sym sdk status             # should show docker/colima/image OK
./sym sdk setup              # once: fetch vendor + build image (slow, needs free disk)
./sym sdk shell
```

On the phone: **File Manager → Installs → devdrop → open the package**.
