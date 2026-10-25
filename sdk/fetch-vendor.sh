#!/usr/bin/env bash
# Download gnupoc + CSL GCC + Symbian^3 SDK into sdk/vendor/
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
VENDOR="$ROOT/vendor"
mkdir -p "$VENDOR"
cd "$VENDOR"

fetch() {
  local url="$1" out="$2"
  if [[ -f "$out" ]]; then
    echo "have $out"
    return 0
  fi
  echo "fetch $out"
  curl -L --fail --retry 3 --continue-at - -o "$out.partial" "$url"
  mv "$out.partial" "$out"
}

echo "==> gnupoc-package (git archive)"
if [[ ! -d gnupoc-package/.git ]]; then
  rm -rf gnupoc-package
  git clone --depth 1 https://github.com/mstorsjo/gnupoc-package.git gnupoc-package
else
  echo "have gnupoc-package"
fi

echo "==> CodeSourcery GCCE (prebuilt linux i686)"
fetch \
  "https://www.martin.st/symbian/gnu-csl-arm-2005Q1C-arm-none-symbianelf-i686-pc-linux-gnu.tar.bz2" \
  "gnu-csl-arm-2005Q1C-arm-none-symbianelf-i686-pc-linux-gnu.tar.bz2"

echo "==> Symbian^3 SDK"
# Prefer Internet Archive item nokia_sdks_n_dev_tools
SDK_NAME="symbian_3_sdk_v1_0_en.zip"
if [[ ! -f "$SDK_NAME" && ! -f "Symbian_3_SDK_v1_0_en.zip" ]]; then
  # try a few mirrors
  urls=(
    "https://archive.org/download/nokia_sdks_n_dev_tools/symbian_3_sdk_v1_0_en.zip"
    "https://archive.org/download/nokia_sdks_n_dev_tools/Symbian_3_SDK_v1_0_en.zip"
    "https://katastrophos.net/symbian/mirrors/delight/SDKs/Symbian_3_SDK_v1_0_en.zip"
  )
  ok=0
  for u in "${urls[@]}"; do
    echo "try $u"
    if curl -L --fail --retry 2 -o "$SDK_NAME.partial" "$u"; then
      mv "$SDK_NAME.partial" "$SDK_NAME"
      ok=1
      break
    fi
    rm -f "$SDK_NAME.partial"
  done
  if [[ "$ok" -ne 1 ]]; then
    echo "ERROR: could not download Symbian^3 SDK." >&2
    echo "Place Symbian_3_SDK_v1_0_en.zip (or symbian_3_sdk_v1_0_en.zip) into:" >&2
    echo "  $VENDOR" >&2
    exit 1
  fi
else
  echo "have SDK zip"
fi

echo "==> vendor ready:"
ls -lh "$VENDOR" | sed -n '1,40p'
