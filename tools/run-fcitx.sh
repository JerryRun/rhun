#!/bin/sh
# Private input engine: no installation, global bus, input grabs or user config.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
runtime="$root/build/fcitx5/root"
state="$root/build/personal/ime"
if [ "${1:-}" != --private ]; then
    export RHUN_PARENT_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-}"
    exec dbus-run-session -- "$0" --private "$@"
fi
shift
mkdir -p "$state/config/fcitx5" "$state/data" "$state/cache" "$state/home" "$state/run"
chmod 700 "$state/run"
if [ ! -f "$state/config/fcitx5/profile" ]; then
    cat > "$state/config/fcitx5/profile" <<'PROFILE'
[Groups/0]
Name=Default
Default Layout=us
DefaultIM=pinyin
[Groups/0/Items/0]
Name=keyboard-us
Layout=
[Groups/0/Items/1]
Name=pinyin
Layout=
[GroupOrder]
0=Default
PROFILE
fi
(
    cd "$runtime"
    export HOME="$state/home"
    export XDG_RUNTIME_DIR="$state/run"
    export XDG_CONFIG_HOME="$state/config" XDG_DATA_HOME="$state/data" XDG_CACHE_HOME="$state/cache"
    export XDG_CONFIG_DIRS="$state/config" XDG_DATA_DIRS="$runtime/usr/share"
    export FCITX_CONFIG_HOME="$state/config/fcitx5" FCITX_CONFIG_DIRS="$state/config/fcitx5"
    export FCITX_DATA_HOME="$state/data/fcitx5" FCITX_DATA_DIRS="$runtime/usr/share/fcitx5"
    export FCITX_ADDON_DIRS="$runtime/usr/lib/x86_64-linux-gnu/fcitx5"
    export LIBIME_MODEL_DIRS="$runtime/usr/lib/x86_64-linux-gnu/libime"
    export LD_LIBRARY_PATH="$runtime/usr/lib/x86_64-linux-gnu"
    exec "$runtime/usr/bin/fcitx5" -D --keep --disable all --enable dbus,dbusfrontend,keyboard,pinyin,punctuation
) > "$state/engine.log" 2>&1 &
engine=$!
cleanup() {
    kill "$engine" 2>/dev/null || true
    wait "$engine" 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 130' INT TERM HUP
/usr/bin/python3 - <<'PY'
import dbus, time
bus = dbus.SessionBus()
for _ in range(100):
    if bus.name_has_owner('org.fcitx.Fcitx5'):
        break
    time.sleep(.05)
else:
    raise SystemExit('Private Fcitx5 failed to start; see build/personal/ime/engine.log')
PY
export RHUN_FCITX_ROOT="$runtime"
export RHUN_FCITX_BUS_ADDRESS="$DBUS_SESSION_BUS_ADDRESS"
# Keep the user's original desktop bus for rhun and its terminal children.
if [ -n "${RHUN_PARENT_BUS_ADDRESS:-}" ]; then
    export DBUS_SESSION_BUS_ADDRESS="$RHUN_PARENT_BUS_ADDRESS"
else
    unset DBUS_SESSION_BUS_ADDRESS
fi
"$@"
