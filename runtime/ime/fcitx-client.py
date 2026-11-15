#!/usr/bin/python3
"""Private Fcitx5 D-Bus client. Binary pipes belong exclusively to one rhun.

No global input grabs, system bus, clipboard, or surrounding document text.
Requests are eight little-endian u32s; replies have type/generation/length/aux.
"""
import os
from pathlib import Path
import select
import signal
import struct
import subprocess
import sys
import tempfile
import time

# The release includes its own Python bindings; never depend on Conda or system IME setup.
if len(sys.argv) > 2:
    sys.path.insert(0, str(Path(sys.argv[2]) / 'usr/lib/python3/dist-packages'))

import dbus
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

DBusGMainLoop(set_as_default=True)
BUS_NAME = 'org.fcitx.Fcitx5'
IC_IFACE = 'org.fcitx.Fcitx.InputContext1'
CAPS = (1 << 1) | (1 << 4) | (1 << 35) | (1 << 37) | (1 << 39)
HEADER = struct.Struct('<IIII')
REQUEST = struct.Struct('<8I')
ENGINE = None
BUS = None
SESSION = None
LOG = None


def stop_private_engine():
    for process in (ENGINE, BUS):
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
    if LOG is not None:
        LOG.close()
    if SESSION is not None:
        SESSION.cleanup()


def start_private_engine():
    global ENGINE, BUS, SESSION, LOG
    if os.environ.get('RHUN_FCITX_BUS_ADDRESS'):
        return
    if len(sys.argv) < 3:
        raise RuntimeError('Chinese Pinyin runtime is not installed')
    runtime = Path(sys.argv[2]).resolve()
    state = Path(sys.argv[1]) / 'ime'
    state.mkdir(parents=True, exist_ok=True)
    SESSION = tempfile.TemporaryDirectory(prefix='rhun-ime-')
    session = Path(SESSION.name)
    profile = state / 'config/fcitx5/profile'
    profile.parent.mkdir(parents=True, exist_ok=True)
    if not profile.exists():
        profile.write_text('[Groups/0]\nName=Default\nDefault Layout=us\n'
            'DefaultIM=pinyin\n[Groups/0/Items/0]\nName=keyboard-us\nLayout=\n'
            '[Groups/0/Items/1]\nName=pinyin\nLayout=\n[GroupOrder]\n0=Default\n')
    for folder in ('data', 'cache', 'home'):
        (state / folder).mkdir(exist_ok=True)
    env = dict(os.environ, HOME=str(state / 'home'), XDG_CONFIG_HOME=str(state / 'config'),
        XDG_DATA_HOME=str(state / 'data'), XDG_CACHE_HOME=str(state / 'cache'),
        XDG_RUNTIME_DIR=str(session), XDG_CONFIG_DIRS=str(state / 'config'),
        XDG_DATA_DIRS=str(runtime / 'usr/share'),
        FCITX_CONFIG_HOME=str(profile.parent), FCITX_CONFIG_DIRS=str(profile.parent),
        FCITX_DATA_HOME=str(state / 'data/fcitx5'),
        FCITX_DATA_DIRS=str(runtime / 'usr/share/fcitx5'),
        FCITX_ADDON_DIRS=str(runtime / 'usr/lib/x86_64-linux-gnu/fcitx5'),
        LIBIME_MODEL_DIRS=str(runtime / 'usr/lib/x86_64-linux-gnu/libime'))
    # No display/input grabs; candidates are rendered by rhun. The desktop bus is untouched.
    for key in ('DBUS_SESSION_BUS_ADDRESS', 'DISPLAY', 'WAYLAND_DISPLAY',
                'DBUS_STARTER_ADDRESS', 'DBUS_STARTER_BUS_TYPE', 'LD_PRELOAD', 'LD_LIBRARY_PATH'):
        env.pop(key, None)
    loader = [str(runtime / 'lib64/ld-linux-x86-64.so.2'), '--library-path',
              str(runtime / 'usr/lib/x86_64-linux-gnu')]
    LOG = (state / 'engine.log').open('ab', buffering=0)
    bus_config = session / 'bus.conf'
    bus_config.write_text('<busconfig><type>session</type><listen>unix:tmpdir=' +
        str(session) + '</listen><auth>EXTERNAL</auth><policy context="default">'
        '<allow send_destination="*"/><allow receive_sender="*"/>'
        '<allow own="*"/></policy></busconfig>')
    BUS = subprocess.Popen(loader + [str(runtime / 'usr/bin/dbus-daemon'),
        '--nofork', '--nopidfile', '--print-address=1', '--config-file=' + str(bus_config)],
        env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=LOG)
    if not select.select([BUS.stdout], [], [], 5)[0]:
        raise RuntimeError('Private input bus did not start; see ' + str(state / 'engine.log'))
    address = BUS.stdout.readline().decode().strip()
    BUS.stdout.close()
    if not address:
        raise RuntimeError('Private input bus failed; see ' + str(state / 'engine.log'))
    env['DBUS_SESSION_BUS_ADDRESS'] = address
    ENGINE = subprocess.Popen(loader + [str(runtime / 'usr/bin/fcitx5'), '-D', '--keep',
        '--disable', 'all', '--enable', 'dbus,dbusfrontend,keyboard,pinyin,punctuation'],
        cwd=runtime, env=env, stdin=subprocess.DEVNULL, stdout=LOG, stderr=LOG)
    bus = dbus.bus.BusConnection(address)
    deadline = time.monotonic() + 8
    try:
        while not bus.name_has_owner(BUS_NAME):
            if ENGINE.poll() is not None or time.monotonic() > deadline:
                raise RuntimeError('Private Pinyin engine failed; see ' + str(state / 'engine.log'))
            time.sleep(.05)
    finally:
        bus.close()
    os.environ['RHUN_FCITX_BUS_ADDRESS'] = address


class Client:
    def __init__(self):
        self.bus = dbus.bus.BusConnection(os.environ['RHUN_FCITX_BUS_ADDRESS'])
        self.generation = 0
        self.pending = bytearray()
        self.ic = None
        self.preedit = ''
        self.has_candidates = False
        self.host_mode = None
        self.controller = dbus.Interface(self.bus.get_object(BUS_NAME, '/controller'),
                                        'org.fcitx.Fcitx.Controller1')
        self.loop = GLib.MainLoop()
        im = dbus.Interface(self.bus.get_object(BUS_NAME,
            '/org/freedesktop/portal/inputmethod'), 'org.fcitx.Fcitx.InputMethod1')
        path, _ = im.CreateInputContext(dbus.Array([
            dbus.Struct(('program', 'rhun')),
            dbus.Struct(('display', 'wayland:rhun-private'))], signature='(ss)'), timeout=3)
        self.ic = dbus.Interface(self.bus.get_object(BUS_NAME, path), IC_IFACE)
        self.ic.SetSupportedCapability(dbus.UInt64(CAPS))
        self.ic.SetCapability(dbus.UInt64(CAPS))
        self.ic.connect_to_signal('CommitString', self.commit)
        self.ic.connect_to_signal('UpdateFormattedPreedit', self.update_preedit)
        self.ic.connect_to_signal('UpdateClientSideUI', self.panel)
        self.ic.connect_to_signal('ForwardKey', self.forward)
        self.ic.connect_to_signal('CurrentIM', self.current_im)
        self.bus.add_signal_receiver(self.owner_changed, signal_name='NameOwnerChanged',
            dbus_interface='org.freedesktop.DBus', arg0=BUS_NAME)
        # Pinyin loads dictionaries lazily on first activation. Warm this private
        # context before readiness, including engines supplied by developer tests.
        self.ic.FocusIn(timeout=2)
        for _ in range(2):
            self.ic.ProcessKeyEvent(dbus.UInt32(32), dbus.UInt32(0),
                dbus.UInt32(4), dbus.Boolean(False), dbus.UInt32(0), timeout=8)
        self.ic.Reset(timeout=2)
        self.ic.FocusOut(timeout=2)
        os.set_blocking(0, False)
        GLib.io_add_watch(0, GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR, self.read)
        self.send(0)

    def send(self, kind, payload=b'', aux=0):
        if isinstance(payload, str):
            payload = payload.encode('utf-8')[:4096].decode('utf-8', 'ignore').encode('utf-8')
        data = HEADER.pack(kind, self.generation, len(payload), aux) + payload
        while data:
            data = data[os.write(1, data):]

    def commit(self, text):
        self.send(3, str(text))

    def update_preedit(self, parts, cursor):
        self.preedit = ''.join(str(p[0]) for p in parts)
        self.send(2, self.preedit)

    def panel(self, preedit, cursor, aux_up, aux_down, candidates, selected,
              layout, has_prev, has_next):
        # Client-side rendering keeps candidates beside rhun's caret, including WSLg.
        title = ''.join(str(p[0]) for p in preedit)
        self.send(2, title or self.preedit)
        rows = [str(label).strip() + ' ' + str(text) for label, text in candidates[:10]]
        self.has_candidates = bool(rows)
        if rows and (has_prev or has_next):
            rows.append('PgUp / PgDn')
        self.send(4, '\n'.join(rows), max(0, int(selected)))

    def forward(self, key, state, release):
        if not release:
            cp = int(key) if int(key) < 0x100 else 0
            self.send(1, struct.pack('<5I', int(key), cp, int(state), 0, 0))

    def current_im(self, name, unique, language):
        self.send(5, aux=int(str(unique) == 'pinyin'))

    def apply_host_mode(self):
        if self.host_mode is None:
            return
        desired = 'pinyin' if self.host_mode else 'keyboard-us'
        if str(self.controller.CurrentInputMethod(timeout=2)) != desired:
            self.ic.Reset(timeout=2)
            self.preedit = ''
            self.has_candidates = False
            self.controller.SetCurrentIM(desired, timeout=2)
            self.send(2)
            self.send(4)

    def request(self, values):
        op, generation, key, cp, mods, base, latin, extra = values
        if generation != self.generation:
            self.ic.Reset()
            self.generation = generation
            self.preedit = ''
        if op == 2:
            self.ic.Reset()
            if key:
                self.ic.FocusIn()
                self.apply_host_mode()
            else:
                self.ic.FocusOut()
            self.send(2)
            self.send(4)
        elif op == 1:
            # App shortcuts bypass Fcitx except its explicit Ctrl+Space toggle.
            shortcut = mods & (4 | 8 | 64) and not (key == 32 and mods == 4 and self.host_mode is None)
            handled = False
            if not shortcut and self.has_candidates and key in (0xff55, 0xff56):
                (self.ic.PrevPage if key == 0xff55 else self.ic.NextPage)()
                handled = True
            elif not shortcut:
                # Batch commits/preedit with this request. A later target reset
                # cannot accidentally relabel an old queued commit signal.
                events, handled = self.ic.ProcessKeyEventBatch(
                    dbus.UInt32(key), dbus.UInt32(0), dbus.UInt32(mods),
                    dbus.Boolean(False), dbus.UInt32(0), timeout=2)
                for kind, value in events:
                    if kind == 0:
                        self.commit(value)
                    elif kind == 1:
                        self.update_preedit(*value)
                    elif kind == 2:
                        self.forward(*value)
            if not handled:
                self.send(1, struct.pack('<5I', key, cp, mods, base, latin))
        elif op == 3:
            self.ic.SelectCandidate(dbus.Int32(key))
        elif op == 4 and self.host_mode is None:
            self.ic.ProcessKeyEvent(dbus.UInt32(32), dbus.UInt32(0),
                dbus.UInt32(4), dbus.Boolean(False), dbus.UInt32(0), timeout=2)
        elif op == 5:
            # Set an absolute mode on this app's private engine only. Repeated
            # host observations cannot toggle it back or disturb composition.
            self.host_mode = bool(key) if key <= 1 else None
            self.apply_host_mode()
            self.send(6, aux=int(self.host_mode) if self.host_mode is not None else 0xFFFFFFFF)

    def read(self, fd, condition):
        try:
            data = os.read(0, 8192)
        except BlockingIOError:
            return True
        if not data:
            self.loop.quit()
            return False
        self.pending.extend(data)
        self.consume()
        return True

    def owner_changed(self, name, old, new):
        if not new:
            self.loop.quit()

    def consume(self):
        if len(self.pending) < REQUEST.size:
            return False
        values = REQUEST.unpack(self.pending[:REQUEST.size])
        del self.pending[:REQUEST.size]
        try:
            self.request(values)
        except Exception as error:
            print('rhun Fcitx5: ' + str(error), file=sys.stderr)
            self.loop.quit()
            return False
        # Let D-Bus dispatch candidate updates before the next request/reset.
        if len(self.pending) >= REQUEST.size:
            GLib.idle_add(self.consume)
        return False

    def run(self):
        try:
            self.loop.run()
        finally:
            try:
                self.ic.DestroyIC(timeout=.5)
            except dbus.DBusException:
                pass


if __name__ == '__main__':
    try:
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
        start_private_engine()
        Client().run()
    except (BrokenPipeError, KeyboardInterrupt):
        pass
    except Exception as error:
        print('rhun Fcitx5: ' + str(error), file=sys.stderr)
        raise SystemExit(1)
    finally:
        stop_private_engine()
