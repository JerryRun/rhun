#!/usr/bin/python3
"""Private Fcitx5 D-Bus client. Binary pipes belong exclusively to one rhun.

No global input grabs, system bus, clipboard, or surrounding document text.
Requests are eight little-endian u32s; replies have type/generation/length/aux.
"""
import os
import struct
import sys

import dbus
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

DBusGMainLoop(set_as_default=True)
BUS_NAME = 'org.fcitx.Fcitx5'
IC_IFACE = 'org.fcitx.Fcitx.InputContext1'
CAPS = (1 << 1) | (1 << 4) | (1 << 35) | (1 << 37) | (1 << 39)
HEADER = struct.Struct('<IIII')
REQUEST = struct.Struct('<8I')


class Client:
    def __init__(self):
        self.bus = dbus.bus.BusConnection(os.environ['RHUN_FCITX_BUS_ADDRESS'])
        self.generation = 0
        self.pending = bytearray()
        self.ic = None
        self.preedit = ''
        self.has_candidates = False
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
            else:
                self.ic.FocusOut()
            self.send(2)
            self.send(4)
        elif op == 1:
            # App shortcuts bypass Fcitx except its explicit Ctrl+Space toggle.
            shortcut = mods & (4 | 8 | 64) and not (key == 32 and mods == 4)
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
        elif op == 4:
            self.ic.ProcessKeyEvent(dbus.UInt32(32), dbus.UInt32(0),
                dbus.UInt32(4), dbus.Boolean(False), dbus.UInt32(0), timeout=2)

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
        Client().run()
    except (BrokenPipeError, KeyboardInterrupt):
        pass
    except Exception as error:
        print('rhun Fcitx5: ' + str(error), file=sys.stderr)
        raise SystemExit(1)
