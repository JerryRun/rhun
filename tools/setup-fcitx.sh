#!/bin/sh
# Download/extract Ubuntu packages locally. Never install packages or set up IM.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
case "$(dpkg --print-architecture)" in
    amd64) ;;
    *) echo 'This local runtime currently requires Ubuntu amd64.' >&2; exit 1 ;;
esac
command -v dbus-run-session >/dev/null
/usr/bin/python3 -c 'import dbus; from gi.repository import GLib'
mkdir -p "$root/build/fcitx5/debs" "$root/build/fcitx5/root"
cd "$root/build/fcitx5/debs"
# apt-get download only reads package indexes and writes .debs here.
# No sudo, apt update, apt install, dpkg -i, services or global config.
apt-get download fcitx5 fcitx5-data fcitx5-modules libfcitx5utils2 \
    libfcitx5config6 libfcitx5core7 fcitx5-pinyin fcitx5-chinese-addons-data \
    fcitx5-module-punctuation libime-data libime-data-language-model \
    libimecore0 libimepinyin0 libboost-iostreams1.83.0 libxcb-ewmh2 \
    libxcb-imdkit1 libenchant-2-2 libaspell15 libhunspell-1.7-0
for deb in ./*.deb; do
    dpkg-deb -x "$deb" "$root/build/fcitx5/root"
done
echo 'Project-local Fcitx5 runtime ready in build/fcitx5/root.'
