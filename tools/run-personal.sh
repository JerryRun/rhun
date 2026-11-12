#!/bin/sh
# Project-local profile; preserves the user's existing installation and configuration.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
profile="$root/build/personal"
config="$profile/config/rhun/config"
if [ ! -x "$root/build/rhun" ]; then "$root/build.sh" release; fi
if [ ! -f "$config" ]; then
    mkdir -p "$profile/config/rhun" "$profile/state"
    original="$HOME/.config/rhun/config"
    if [ -n "${XDG_CONFIG_HOME:-}" ]; then original="$XDG_CONFIG_HOME/rhun/config"; fi
    if [ -f "$original" ]; then cp "$original" "$config"; fi
    cat >> "$config" <<'CONFIG'

# Personal WSL profile. Editable from Settings.
[editor]
font_size = 16
side_diff = true
[terminal]
font_size = 15
line_height = 1.15
[ui]
font_size = 14
CONFIG
    if [ -f /mnt/c/Windows/Fonts/consola.ttf ]; then
        cat >> "$config" <<'CONFIG'
[editor]
font = /mnt/c/Windows/Fonts/consola.ttf
[terminal]
font = /mnt/c/Windows/Fonts/consola.ttf
CONFIG
    fi
    if [ -f /mnt/c/Windows/Fonts/msyh.ttc ]; then
        cat >> "$config" <<'CONFIG'
[editor]
fallback_font = /mnt/c/Windows/Fonts/msyh.ttc
[ui]
font = /mnt/c/Windows/Fonts/msyh.ttc
CONFIG
    fi
fi
export XDG_CONFIG_HOME="$profile/config"
export XDG_STATE_HOME="$profile/state"
if [ -n "${WSL_INTEROP:-}" ] && [ -d /mnt/wslg ]; then
    export RHUN_WSL_WINDOW_FIX="${RHUN_WSL_WINDOW_FIX:-1}"
fi
if [ "${RHUN_INLINE_IME:-1}" != 0 ] && [ "$(uname -s)" = Linux ] &&
   [ -x "$root/build/fcitx5/root/usr/bin/fcitx5" ]; then
    exec "$root/tools/run-fcitx.sh" "$root/build/rhun" --wait "$@"
fi
exec "$root/build/rhun" "$@"
