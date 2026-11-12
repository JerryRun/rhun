#!/usr/bin/python3
"""A failed client/service must restore normal keys without restarting rhun."""
import os
from pathlib import Path
import signal
import socket
import subprocess
import tempfile
import time
import dbus

ROOT = Path(__file__).resolve().parents[1]

def run_case(engine_loss):
    with tempfile.TemporaryDirectory(prefix='rhun-fcitx-failure-') as tmp:
        work = Path(tmp)
        config = work/'config/rhun/config'
        config.parent.mkdir(parents=True)
        config.write_text('[ui]\nsidebar=false\nagents_panel=false\n'
            '[updates]\ncheck=false\n[git]\nenabled=false\n'
            '[files]\nrestore_session=false\nrestore_project=false\n')
        env = dict(os.environ, HOME=tmp, XDG_CONFIG_HOME=str(work/'config'),
                   XDG_STATE_HOME=str(work/'state'))
        proc = subprocess.Popen([str(ROOT/'build/rhun'), '--headless', '1000x700',
            '--control', str(work/'control'), tmp], env=env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        client = socket.socket(socket.AF_UNIX)
        client.settimeout(5)
        try:
            deadline = time.monotonic()+10
            while not (work/'control').exists():
                assert proc.poll() is None
                assert time.monotonic() < deadline
                time.sleep(.05)
            client.connect(str(work/'control'))
            reader = client.makefile('rb')
            def command(text):
                client.sendall((text+'\n').encode())
                parts = []
                while True:
                    line = reader.readline()
                    if line == b'ok\n': return b''.join(parts).decode()
                    assert line not in (b'', b'error\n'), (text, line)
                    parts.append(line)
            command('cmd new_file')
            command('wait 800')
            command('key ctrl+alt+space')
            command('wait 150')
            command('type zhongwen')
            command('wait 200')
            assert command('print-doc').strip() == '<eod>'
            if engine_loss:
                bus = dbus.bus.BusConnection(os.environ['RHUN_FCITX_BUS_ADDRESS'])
                dbus_api = dbus.Interface(bus.get_object('org.freedesktop.DBus',
                    '/org/freedesktop/DBus'), 'org.freedesktop.DBus')
                engine = int(dbus_api.GetConnectionUnixProcessID('org.fcitx.Fcitx5'))
                os.kill(engine, signal.SIGTERM)
            else:
                children = Path('/proc',str(proc.pid),'task',str(proc.pid),'children')
                for pid in children.read_text().split():
                    args = Path('/proc',pid,'cmdline').read_bytes()
                    if b'CreateInputContext' in args:
                        os.kill(int(pid), signal.SIGKILL)
                        break
                else:
                    raise AssertionError('private input client not found')
            command('wait 500')
            assert 'normal keyboard input restored' in command('print-toast')
            command('type fallback')
            assert 'fallback' in command('print-doc')
            command('quit')
            proc.wait(timeout=5)
            assert proc.returncode == 0
        finally:
            client.close()
            if proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=5)

run_case(False)
run_case(True)
print('PASS: client crash and private engine loss restore normal keyboard input')
