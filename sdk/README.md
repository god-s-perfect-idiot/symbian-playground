# Native Symbian SDK image

Built by `./sym sdk setup` → Docker image `symbian-sdk:s3`.

**Do not rebuild casually.** Check `./sym sdk status` first.

## Contents

- GnuPoc wrappers + patched host tools (`makesis`, `bldmake`, `abld`, …)
- CodeSourcery GCCE (`arm-none-symbianelf-g++`)
- Symbian^3 SDK under `/opt/symbian/epocroot/`
- OpenSSL **1.0.2** at `/opt/openssl-1.0` (required by makesis-4)
- Perl 5.36 patches for `defined(%hash)` in `e32plat.pm` / `romutl.pm`
- Dev certs in `/opt/symbian/certs/` (`cert.cer` / `key.key`)

## Rebuild (rare)

Needs Colima **x86_64**, ~20GB+ free disk, vendor under `sdk/vendor/`:

```bash
./sym sdk fetch                 # if vendor missing
./sym sdk build-image --no-cache
```

Install script: `install-in-container.sh`. Dockerfile: `Dockerfile`.
