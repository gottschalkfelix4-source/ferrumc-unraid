#!/bin/sh
set -eu
version=$(jq -er '.version' /tmp/upstream.json)
repo=$(jq -er '.repository' /tmp/upstream.json)
target=$(jq -er --arg arch "$TARGETARCH" '.assets[$arch].target' /tmp/upstream.json)
checksum=$(jq -er --arg arch "$TARGETARCH" '.assets[$arch].sha256' /tmp/upstream.json)
archive="ferrumc-${version}-${target}.tar.gz"
cd /tmp
curl --fail --location --retry 3 --proto '=https' --tlsv1.2 \
    "https://github.com/${repo}/releases/download/${version}/${archive}" -o "$archive"
printf '%s  %s\n' "$checksum" "$archive" | sha256sum -c -
mkdir /out
tar -xzf "$archive" -C /out ferrumc
chmod 0755 /out/ferrumc

