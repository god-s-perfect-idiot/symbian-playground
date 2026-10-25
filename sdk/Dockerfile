# Symbian^3 native toolchain for the sym harness (linux/amd64).
FROM --platform=linux/amd64 debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive \
    EPOCROOT=/opt/symbian/epocroot/ \
    PATH=/opt/openssl-1.0/bin:/opt/symbian/gnupoc:/opt/symbian/csl-gcc/bin:/opt/symbian/epocroot/epoc32/tools:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

RUN dpkg --add-architecture i386 \
 && apt-get update && apt-get install -y --no-install-recommends \
      bash ca-certificates curl wget unzip zip xz-utils \
      build-essential flex bison texinfo \
      perl python3 \
      cabextract p7zip-full unshield \
      zlib1g-dev \
      git file procps \
      libc6:i386 libstdc++6:i386 zlib1g:i386 libncurses5:i386 \
 && rm -rf /var/lib/apt/lists/*

# OpenSSL 1.0.2 — gnupoc makesis-4 accesses EVP_PKEY internals removed in 1.1+.
RUN curl -fsSL -o /tmp/openssl.tgz https://github.com/openssl/openssl/releases/download/OpenSSL_1_0_2u/openssl-1.0.2u.tar.gz \
 && tar -C /tmp -xzf /tmp/openssl.tgz \
 && cd /tmp/openssl-1.0.2u \
 && ./config --prefix=/opt/openssl-1.0 --openssldir=/opt/openssl-1.0/ssl shared zlib \
 && make -j"$(nproc)" \
 && make install_sw \
 && rm -rf /tmp/openssl-1.0.2u /tmp/openssl.tgz

COPY install-in-container.sh /tmp/install-in-container.sh
COPY vendor/ /tmp/vendor/
RUN chmod +x /tmp/install-in-container.sh \
 && bash /tmp/install-in-container.sh \
 && rm -rf /tmp/vendor /tmp/install-in-container.sh

WORKDIR /work
CMD ["bash", "-lc", "echo EPOCROOT=$EPOCROOT; command -v makesis; command -v arm-none-symbianelf-g++; bash"]
