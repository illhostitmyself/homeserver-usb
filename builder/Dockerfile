FROM debian:trixie
RUN apt-get update && apt-get install -y --no-install-recommends \
      live-build xorriso squashfs-tools mtools dosfstools zstd ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /build
