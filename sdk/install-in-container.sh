#!/usr/bin/env bash
# Runs inside the Docker image build. Expects /tmp/vendor populated.
set -euo pipefail

VENDOR=/tmp/vendor
GNUPOC_TGZ=$(ls "$VENDOR"/gnupoc-package*.tar.gz "$VENDOR"/gnupoc-package*.tgz 2>/dev/null | head -1 || true)
# also allow a checked-out tree
GNUPOC_DIR="$VENDOR/gnupoc-package"
CSL_TGZ=$(ls "$VENDOR"/gnu-csl-arm-*-arm-none-symbianelf-i686-pc-linux-gnu.tar.bz2 2>/dev/null | head -1 || true)
SDK_ZIP=$(ls "$VENDOR"/Symbian_3_SDK*.zip "$VENDOR"/symbian_3_sdk*.zip "$VENDOR"/Nokia_Symbian_Belle*.zip 2>/dev/null | head -1 || true)

mkdir -p /opt/symbian

if [[ -z "${CSL_TGZ}" ]]; then
  echo "ERROR: missing CodeSourcery GCC tarball in vendor/" >&2
  exit 1
fi
if [[ -z "${SDK_ZIP}" ]]; then
  echo "ERROR: missing Symbian SDK zip in vendor/" >&2
  exit 1
fi

echo "==> installing CSL GCC from $(basename "$CSL_TGZ")"
mkdir -p /opt/symbian/csl-gcc
tar -C /opt/symbian/csl-gcc -xjf "$CSL_TGZ"
# tarball often has a single top-level dir; flatten if needed
if [[ ! -x /opt/symbian/csl-gcc/bin/arm-none-symbianelf-g++ ]]; then
  inner=$(find /opt/symbian/csl-gcc -maxdepth 2 -type f -name 'arm-none-symbianelf-g++' | head -1 || true)
  if [[ -n "$inner" ]]; then
    top=$(dirname "$(dirname "$inner")")
    shopt -s dotglob
    mv "$top"/* /opt/symbian/csl-gcc/ 2>/dev/null || true
    shopt -u dotglob
  fi
fi
test -x /opt/symbian/csl-gcc/bin/arm-none-symbianelf-g++

echo "==> unpacking gnupoc"
mkdir -p /opt/symbian/src
if [[ -n "$GNUPOC_TGZ" ]]; then
  tar -C /opt/symbian/src -xzf "$GNUPOC_TGZ"
  GP=$(find /opt/symbian/src -maxdepth 2 -type d -name 'gnupoc-package*' | head -1)
elif [[ -d "$GNUPOC_DIR" ]]; then
  cp -a "$GNUPOC_DIR" /opt/symbian/src/gnupoc-package
  GP=/opt/symbian/src/gnupoc-package
else
  echo "ERROR: missing gnupoc-package in vendor/" >&2
  exit 1
fi
cd "$GP/tools"
# Modern g++ rejects (char* > 0); patch if still present
if grep -q 'foundPath > 0' bmconv-1.1.0-2/src/pbmcomp.cpp 2>/dev/null; then
  sed -i 's/foundPath > 0/foundPath != 0/' bmconv-1.1.0-2/src/pbmcomp.cpp
fi
export CXXFLAGS="${CXXFLAGS:-} -fpermissive -Wno-write-strings -Wno-deprecated"
export CFLAGS="${CFLAGS:-} -fpermissive"
./install_eka2_tools /opt/symbian/csl-gcc

echo "==> building makesis-4 against OpenSSL 1.0.2"
cd "$GP/tools/makesis-4/src"
make clean || true
make \
  CFLAGS="-Wall -I../include -DTEST -ggdb -fpermissive -I/opt/openssl-1.0/include" \
  LDFLAGS="-L/opt/openssl-1.0/lib -Wl,-rpath,/opt/openssl-1.0/lib" \
  LIBS="-lz -lcrypto"
cp makesis signsis makekeys /opt/symbian/csl-gcc/bin/
echo "/opt/openssl-1.0/lib" > /etc/ld.so.conf.d/openssl10.conf
ldconfig

echo "==> installing SDK $(basename "$SDK_ZIP") → /opt/symbian/epocroot"
mkdir -p /opt/symbian/epocroot
cd "$GP/sdks"

# Prefer Symbian^3 installer; fall back to Belle / S60 5th naming
if [[ -x ./install_gnupoc_symbian3 ]]; then
  ./install_gnupoc_symbian3 "$SDK_ZIP" /opt/symbian/epocroot
elif [[ -x ./install_gnupoc_s60_50 ]]; then
  ./install_gnupoc_s60_50 "$SDK_ZIP" /opt/symbian/epocroot
else
  echo "ERROR: no suitable install_gnupoc_* script found" >&2
  ls -la
  exit 1
fi

# Ensure trailing slash semantics used by Symbian tools
# (EPOCROOT must end with /)
test -d /opt/symbian/epocroot/epoc32

echo "==> patching epoc32 perl tools for Perl 5.22+"
TOOLS=/opt/symbian/epocroot/epoc32/tools
# defined(%hash) removed in modern Perl — use exists + boolean hash
perl -i -pe 's/defined\s+%\{/%{/g; s/defined\s+%([A-Za-z_]+)/%$1/g' \
  "$TOOLS/e32plat.pm" "$TOOLS/romutl.pm" "$TOOLS/htmlscanlog.pl"
perl -i -pe 's/if \(%\{\$Plat\{\$BSF\}\}\)/if (exists \$Plat{\$BSF} \&\& %{\$Plat{\$BSF}})/g; s/if \(%\{\$Plat\{\$root\}\}\)/if (exists \$Plat{\$root} \&\& %{\$Plat{\$root}})/g; s/if \(%\{\$Plat\{\$ASSP\}\}\)/if (exists \$Plat{\$ASSP} \&\& %{\$Plat{\$ASSP}})/g' \
  "$TOOLS/e32plat.pm" "$TOOLS/romutl.pm"
# Linux EPOCROOT has no Windows drive letter
perl -i -pe 's/my \$MacroHRHLocation_Drive = lc\(\$1\);/my \$MacroHRHLocation_Drive = defined(\$1) ? lc(\$1) : "";/' \
  "$TOOLS/e32variant.pm"
perl -i -pe 's/my \$paths_drive = lc\(\$1\);/my \$paths_drive = defined(\$1) ? lc(\$1) : "";/' \
  "$TOOLS/e32variant.pm"

echo "==> installing gnupoc wrappers"
cd "$GP/sdks"
./install_wrapper /opt/symbian/gnupoc
# Point wrappers at our toolchain paths
sed -i 's|^EKA2TOOLS=.*|EKA2TOOLS=/opt/symbian/csl-gcc/bin|' /opt/symbian/gnupoc/gnupoc-common.sh || true
grep -q EKA2TOOLS /opt/symbian/gnupoc/gnupoc-common.sh || \
  echo 'EKA2TOOLS=/opt/symbian/csl-gcc/bin' >> /opt/symbian/gnupoc/gnupoc-common.sh

# Self-signed cert for SISX (developer use / jailbroken devices).
# makekeys shells out to openssl dsaparam/req — must use OpenSSL 1.0.2.
mkdir -p /opt/symbian/certs
cd /opt/symbian/certs
export PATH=/opt/openssl-1.0/bin:/opt/symbian/csl-gcc/bin:$PATH
if [[ -x /opt/symbian/csl-gcc/bin/makekeys ]]; then
  printf '%s\n' IN State City SymDev Dev SymDev 'dev@sym.local' \
    | /opt/symbian/csl-gcc/bin/makekeys -cert -expdays 3650 key.key cert.cer \
    || true
fi
# Fallback openssl self-signed material for open signsis variants
openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 3650 -nodes \
  -subj "/CN=SymDev/O=SymDev/C=IN" 2>/dev/null || true

cat >/etc/profile.d/symbian-env.sh <<'EOF'
export EPOCROOT=/opt/symbian/epocroot/
export PATH=/opt/openssl-1.0/bin:/opt/symbian/gnupoc:/opt/symbian/csl-gcc/bin:/opt/symbian/epocroot/epoc32/tools:$PATH
EOF

echo "==> SDK install complete"
ls /opt/symbian/csl-gcc/bin/arm-none-symbianelf-g++
ls /opt/symbian/epocroot/epoc32/tools/makesis* 2>/dev/null || ls /opt/symbian/csl-gcc/bin/makesis
which makesis || true
