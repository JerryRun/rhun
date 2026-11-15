#!/usr/bin/env python3
"""Install a release in scratch HOME and type Chinese through the normal binary.

Uses the packaged engine, Python and D-Bus, without the personal launcher or
system input method changes. Also exercises Settings enable/disable/re-enable.
"""
import configparser
import hashlib
import os
from pathlib import Path
import socket
import subprocess
import tarfile
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / 'build/ime-runtime'
VERSION = (ROOT / 'VERSION').read_text().strip()


class InstalledInput(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Reuse a built release for remote/distro checks without repacking it.
        cls.fixture = None
        external = os.environ.get('RHUN_TEST_RELEASES_URL')
        if external:
            cls.url = external
            return
        if not (RUNTIME / 'usr/bin/python3.12').is_file():
            raise RuntimeError('Run /usr/bin/python3 tools/package-ime.py first')
        cls.fixture = tempfile.TemporaryDirectory(prefix='rhun-ime-release-')
        base = Path(cls.fixture.name)
        release = base / 'releases/download' / ('v' + VERSION)
        release.mkdir(parents=True)
        latest = base / 'releases/latest/download'
        latest.mkdir(parents=True)
        (latest / 'VERSION').write_text(VERSION)
        archive = release / ('rhun-' + VERSION + '-linux-x86_64.tar.gz')
        name = 'rhun-' + VERSION
        with tarfile.open(archive, 'w:gz', compresslevel=1) as tar:
            tar.add(ROOT / 'build/rhun', name + '/bin/rhun')
            tar.add(RUNTIME, name + '/share/rhun/ime')
            tar.add(ROOT / 'assets/rhun.desktop', name + '/share/applications/rhun.desktop')
            tar.add(ROOT / 'assets/rhun-url-handler.desktop',
                    name + '/share/applications/rhun-url-handler.desktop')
        (release / 'SHA256SUMS').write_text(hashlib.sha256(archive.read_bytes()).hexdigest()
                                           + '  ' + archive.name + '\n')
        cls.url = (base / 'releases').as_uri()

    @classmethod
    def tearDownClass(cls):
        if cls.fixture is not None:
            cls.fixture.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='rhun-installed-ime-')
        self.work = Path(self.tmp.name)
        self.config = self.work / 'config/rhun/config'
        self.config.parent.mkdir(parents=True)
        self.config.write_text('[ui]\nsidebar=false\nagents_panel=false\n'
            '[git]\nenabled=false\n[updates]\ncheck=false\n'
            '[files]\nrestore_session=false\nrestore_project=false\n'
            '[terminal]\nshell=/bin/sh\n')
        self.env = {key: value for key, value in os.environ.items()
                    if not key.startswith('RHUN_FCITX') and key not in
                    ('PYTHONHOME', 'PYTHONPATH', 'DBUS_SESSION_BUS_ADDRESS')}
        self.env.update(HOME=str(self.work), XDG_CONFIG_HOME=str(self.work / 'config'),
            XDG_STATE_HOME=str(self.work / 'state'), XDG_DATA_HOME=str(self.work / 'data'),
            RHUN_RELEASES_URL=self.url, XDG_CURRENT_DESKTOP='', PATH='/usr/bin:/bin')
        self.exe = self.work / '.local/bin/rhun'

    def tearDown(self):
        # The app closes its input pipe; the helper then stops its engine/bus and
        # saves the user dictionary before the temporary HOME is removed.
        for attempt in range(30):
            try:
                self.tmp.cleanup()
                break
            except OSError:
                if attempt == 29:
                    raise
                time.sleep(.1)

    def install(self, *args):
        result = subprocess.run(['sh', str(ROOT / 'install.sh'), '--no-modify-path',
            '--no-url-scheme', *args], env=self.env, capture_output=True, text=True, timeout=45)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def run_editor(self, actions):
        control = self.work / 'control'
        control.unlink(missing_ok=True)
        proc = subprocess.Popen([str(self.exe), '--headless', '1000x800', '--scale', '1',
            '--control', str(control), str(self.work)], env=self.env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        client = socket.socket(socket.AF_UNIX)
        client.settimeout(15)
        output = []
        try:
            deadline = time.monotonic() + 12
            while not control.exists():
                self.assertIsNone(proc.poll())
                self.assertLess(time.monotonic(), deadline)
                time.sleep(.02)
            client.connect(str(control))
            reader = client.makefile('rb')
            def command(action):
                client.sendall((action + '\n').encode())
                parts = []
                while True:
                    line = reader.readline()
                    if line == b'ok\n':
                        return b''.join(parts).decode()
                    self.assertNotIn(line, (b'', b'error\n'), action)
                    parts.append(line)
            command('focus in')
            command('cmd new_file')
            for action in actions:
                if action == 'wait-ime':
                    deadline = time.monotonic() + 12
                    while command('print-input').strip() != '1':
                        log = self.config.parent / 'ime/engine.log'
                        diagnostics = log.read_text(errors='replace')[-4000:] if log.exists() else ''
                        self.assertLess(time.monotonic(), deadline,
                            'Pinyin startup timed out: ' + command('print-toast') + diagnostics)
                        command('wait 50')
                else:
                    output.append(command(action))
            command('quit')
            _, self.last_diagnostics = proc.communicate(timeout=8)
            self.assertEqual(proc.returncode, 0, self.last_diagnostics)
        finally:
            client.close()
            if proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=5)
        log = self.config.parent / 'ime/engine.log'
        if log.exists():
            self.last_diagnostics += log.read_text(errors='replace')[-5000:]
        return ''.join(output)

    def enabled(self):
        config = configparser.ConfigParser(strict=False)
        config.read(self.config)
        return config.getboolean('editor', 'chinese_input', fallback=False)

    def test_install_choice_and_normal_launch(self):
        self.install('--chinese-input')
        self.assertTrue(self.enabled())
        self.assertTrue((self.work / '.local/share/rhun/ime/usr/bin/fcitx5').is_file())
        # Hostile Python environment cannot redirect the bundled interpreter.
        self.env.update(PYTHONHOME='/missing/conda', PYTHONPATH='/missing/python')
        out = self.run_editor(['wait-ime', 'key ctrl+alt+space', 'wait 120',
            'type zhongwen', 'wait 300', 'print-doc', 'key space', 'wait 200', 'print-doc'])
        self.assertIn('中文', out, self.last_diagnostics)
        self.assertNotIn('zhongwen', out)
        self.install()
        self.assertTrue(self.enabled(), 'ordinary reinstall must preserve the input choice')
        self.install('--no-chinese-input')
        self.assertFalse(self.enabled())
        self.assertIn('English', self.run_editor(['type English', 'print-doc']))

    def test_settings_enable_disable_and_reenable(self):
        self.install()
        self.assertFalse(self.enabled())
        # The filtered boolean switch is in the first row. Toggle while the app is open.
        out = self.run_editor(['cmd settings', 'type chinese_input', 'click 827 348',
            'wait-ime', 'cmd new_file', 'key ctrl+alt+space', 'wait 120',
            'type zhongwen', 'wait 300', 'key space', 'wait 200', 'print-doc'])
        self.assertTrue(self.enabled(), out + self.config.read_text())
        self.assertIn('中文', out, self.last_diagnostics)
        out = self.run_editor(['wait-ime', 'cmd settings', 'type chinese_input', 'wait 200',
            'click 827 348', 'wait 300', 'cmd new_file', 'type English', 'print-doc',
            'cmd settings', 'key ctrl+a', 'type chinese_input', 'wait 200', 'click 827 348',
            'wait-ime', 'cmd new_file', 'key ctrl+alt+space', 'wait 120',
            'type ceshi', 'wait 300', 'key space', 'wait 200', 'print-doc'])
        self.assertTrue(self.enabled())
        self.assertIn('English', out)
        self.assertIn('测试', out)

    def test_missing_runtime_restores_keyboard(self):
        self.install('--chinese-input')
        (self.work / '.local/share/rhun/ime').unlink()
        out = self.run_editor(['wait 1000', 'print-toast', 'type fallback', 'print-doc'])
        self.assertIn('normal keyboard input restored', out)
        self.assertIn('fallback', out)

    def test_update_and_uninstall_preserve_config(self):
        self.install('--chinese-input')
        # Exercise a real replacement, rather than the same-version no-op path.
        self.exe.write_text('#!/bin/sh\necho "rhun 0.0.0"\n')
        (self.work / '.local/share/rhun/ime').unlink()
        self.install('--update', '--target', str(self.exe), '--version', VERSION)
        self.assertTrue(self.enabled())
        self.assertTrue((self.work / '.local/share/rhun/ime/usr/bin/fcitx5').is_file())
        self.install('--uninstall')
        self.assertFalse(self.exe.exists())
        self.assertFalse((self.work / '.local/share/rhun/ime').exists())
        self.assertTrue(self.enabled())


if __name__ == '__main__':
    unittest.main()
