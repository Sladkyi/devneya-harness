#!/bin/bash
set -eu

if [ -x ./devneya ]; then
    exec ./devneya
fi

case "$(uname -m)" in
    x86_64) binary=./dist/linux-x64/devneya ;;
    aarch64) binary=./dist/linux-arm64/devneya ;;
    *) binary= ;;
esac
if [ -n "$binary" ] && [ -x "$binary" ]; then
    exec "$binary"
fi

echo 'Extract the Linux devneya executable next to start.cmd, then run chmod +x devneya in WSL.' >&2
exit 1
