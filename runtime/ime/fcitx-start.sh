#!/bin/sh
# Started by the editor. Never changes the desktop input method or shell profile.
set -eu
config=$1
exe=$2
client=$3
bindir=$(dirname -- "$exe")
runtime=
for candidate in "$bindir/../share/rhun/ime" "$bindir/rhun-runtime/ime" \
                 "$bindir/ime-runtime" "$bindir/fcitx5/root"; do
    if [ -x "$candidate/usr/bin/fcitx5" ]; then runtime=$candidate; break; fi
done
# The developer launcher can still supply its own already-running private engine.
if [ -n "${RHUN_FCITX_BUS_ADDRESS:-}" ]; then
    exec /usr/bin/python3 -I -c "$client" "$config"
fi
if [ -z "$runtime" ]; then
    echo 'Chinese Pinyin runtime missing. Reinstall the current Linux release.' >&2
    exit 1
fi
export PYTHONHOME="$runtime/usr"
export PYTHONNOUSERSITE=1
unset PYTHONPATH
export GI_TYPELIB_PATH="$runtime/usr/lib/x86_64-linux-gnu/girepository-1.0"
exec "$runtime/lib64/ld-linux-x86-64.so.2" \
    --library-path "$runtime/usr/lib/x86_64-linux-gnu" \
    "$runtime/usr/bin/python3.12" -P -s -c "$client" "$config" "$runtime"
