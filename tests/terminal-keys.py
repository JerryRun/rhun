#!/usr/bin/env python3
"""Keys a program in the terminal receives (issue 54). A program that turns on the kitty keyboard
protocol the way Pi does (CSI > 7 u, CSI ? u, then DA) learns that rhun keeps flag 1 and gets
Shift+Enter as CSI 13;2u, Alt+Enter as CSI 13;3u and Escape as CSI 27 u; plain Enter stays CR.
Without the protocol, and after the program pops its flags, keys are the legacy bytes again."""
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
EXE = Path(os.environ.get('RHUN_TEST_EXE', ROOT / 'build/rhun')).resolve()

# prints the negotiation reply and each key it reads, made readable (ESC, ^M), until q; READY and END
# carry the run's number, so a run does not wait on the text of the one before
READER = r'''
import os, sys, termios, tty
kitty = sys.argv[1] in ('kitty', 'kitty-paste')
paste = sys.argv[1] in ('bracketed', 'kitty-paste')
run = sys.argv[2]
old = termios.tcgetattr(0)
tty.setraw(0)
def show(data):
    return ''.join('ESC' if c == 27 else '^' + chr(c + 64) if c < 32 else chr(c) for c in data)
def say(text):
    os.write(1, (text + '\r\n').encode())
try:
    if paste:
        os.write(1, b'\x1b[?2004h')
    if kitty:
        os.write(1, b'\x1b[>7u\x1b[?u\x1b[c')
        reply = b''
        while not reply.endswith(b'c'):
            reply += os.read(0, 64)
        say('R:' + show(reply))
    say('READY' + run)
    while True:
        data = os.read(0, 64)
        if data == b'q':
            break
        say('K:' + (data.hex() if paste else show(data)))
finally:
    if paste:
        os.write(1, b'\x1b[?2004l')
    if kitty:
        os.write(1, b'\x1b[<u')
    termios.tcsetattr(0, termios.TCSADRAIN, old)
    say('END' + run)
'''


@unittest.skipIf(os.name == 'nt', 'the control socket is Unix only')
class TerminalKeys(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='rhun-keys-', dir='/tmp')
        self.work = Path(self.tmp.name).resolve()
        self.project = self.work / 'project'
        self.project.mkdir()
        self.reader_py = self.work / 'reader.py'
        self.reader_py.write_text(READER, encoding='utf-8')
        config = self.work / 'config/rhun/config'
        config.parent.mkdir(parents=True)
        config.write_text('[files]\nrestore_session = false\nrestore_project = false\n'
                          '[updates]\ncheck = false\n[git]\nenabled = false\n'
                          '[editor]\ncursor_blink = false\nchinese_input = '
                          + os.environ.get('RHUN_TEST_CHINESE_INPUT', 'false') + '\n'
                          '[ui]\nagents_panel = false\nsidebar = false\n'
                          '[terminal]\nshell = /bin/sh\nheight = 600\n', encoding='utf-8')
        self.env = dict(os.environ, HOME=str(self.work), XDG_CONFIG_HOME=str(self.work / 'config'),
                        XDG_STATE_HOME=str(self.work / 'state'), PS1='$ ', ENV='', HISTFILE='/dev/null')
        self.start_editor()

    def start_editor(self):
        control = self.work / 'control'
        control.unlink(missing_ok=True)
        self.process = subprocess.Popen([str(EXE), str(self.project), '--headless', '1280x800',
                                         '--scale', '1', '--control', str(control)], env=self.env,
                                        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        self.client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.client.settimeout(15)
        deadline = time.monotonic() + 10
        while True:
            try:
                self.client.connect(str(control))
                break
            except (FileNotFoundError, ConnectionRefusedError):
                if self.process.poll() is not None or time.monotonic() > deadline:
                    self.fail('editor did not start')
                time.sleep(0.01)
        self.reader = self.client.makefile('r', encoding='utf-8')
        if os.environ.get('RHUN_TEST_CHINESE_INPUT') == 'true':
            self.command('wait-input')
        self.command('cmd toggle_terminal')
        self.command('wait 300')

    def tearDown(self):
        if self.process.poll() is None:
            self.process.terminate()
            self.process.wait(timeout=10)
        self.reader.close()
        self.client.close()
        self.process.stderr.close()
        for _ in range(50):
            try:
                self.tmp.cleanup()
                return
            except OSError:
                time.sleep(0.1)
        self.tmp.cleanup()

    def command(self, line):
        self.client.sendall((line + '\n').encode('utf-8'))
        output = []
        while True:
            reply = self.reader.readline()
            if reply == 'ok\n':
                return ''.join(output)
            self.assertNotIn(reply, ('', 'error\n'), line)
            output.append(reply)

    def read_keys(self, mode, keys, before_keys=None):
        """Runs the reader, presses keys, and returns its reply line and what each key sent."""
        self.runs = getattr(self, 'runs', 0) + 1
        self.command(f'type {sys.executable} {self.reader_py.as_posix()} {mode} {self.runs}')
        self.command('key Return')
        self.command(f'wait-term READY{self.runs}')
        if before_keys:
            before_keys()
        for key in keys:
            self.command('key ' + key)
            self.command('wait 50')
        self.command('type q')
        self.command(f'wait-term END{self.runs}')
        lines = self.command('print-term').splitlines()
        start = max(i for i, line in enumerate(lines) if 'reader.py' in line)
        reply = next((l[2:].strip() for l in lines[start:] if l.startswith('R:')), None)
        return reply, [l[2:].strip() for l in lines[start:] if l.startswith('K:')]

    def test_kitty_protocol_keys(self):
        reply, sent = self.read_keys('kitty', ['shift+Return', 'alt+Return', 'Return', 'Escape',
                                               'alt+x', 'shift+Tab'])
        self.assertTrue(reply.startswith('ESC[?1u'), reply)
        self.assertEqual(sent, ['ESC[13;2u', 'ESC[13;3u', '^M', 'ESC[27u', 'ESC[120;3u',
                                'ESC[9;2u'])

    def test_legacy_keys_without_the_protocol(self):
        _, sent = self.read_keys('legacy', ['shift+Return', 'alt+Return', 'Return', 'Escape',
                                            'shift+Tab'])
        self.assertEqual(sent, ['^M', 'ESC^M', '^M', 'ESC', 'ESC[Z'])

    def test_keys_are_legacy_again_after_the_program_pops_its_flags(self):
        self.read_keys('kitty', ['shift+Return'])
        _, sent = self.read_keys('legacy', ['shift+Return'])
        self.assertEqual(sent, ['^M'])

    def copy_text(self, text):
        self.command('cmd toggle_terminal')
        document = self.work / 'clipboard.txt'
        document.write_text(text, encoding='utf-8')
        self.command(f'open {document}')
        self.command('key ctrl+a')
        self.command('key ctrl+c')
        self.command('wait 150')
        self.command('cmd toggle_terminal')

    def change_hotkey(self, name, value):
        self.command('cmd keyboard_shortcuts')
        self.command('type Terminal: ' + ('Copy Selection' if name == 'copy_key' else 'Paste'))
        # The optional Ctrl+C/V binding follows the conventional alternatives.
        listing = [row for row in self.command('print-palette').splitlines()
                   if 'Terminal: ' in row]
        rows = [row.lstrip('> ').split('  ', 1)[0] for row in listing]
        wanted = getattr(self, '_hotkeys', {}).get(name, 'Ctrl+C' if name == 'copy_key' else 'Ctrl+V')
        self.assertIn(wanted, rows, listing)
        current = next(i for i, row in enumerate(listing) if row.startswith('>'))
        offset = rows.index(wanted) - current
        for _ in range(abs(offset)):
            self.command('key Down' if offset > 0 else 'key Up')
        self.command('key F2')
        self.command('key F2')  # manual name entry, including invalid-value tests
        self.command('key BackSpace')
        if value:
            self.command('type ' + value)
        self.command('key Return')
        self.last_hotkey_toast = self.command('print-toast')
        if 'Invalid shortcut.' not in self.last_hotkey_toast:
            self._hotkeys = getattr(self, '_hotkeys', {})
            self._hotkeys[name] = '+'.join(part.capitalize() for part in value.split('+'))
        self.command('key Escape')
        self.command('wait 100')

    def select_ready(self):
        self.command('wait 80')
        lines = self.command('print-term').splitlines()
        text = 'READY' + str(self.runs)
        row = next(i for i, line in enumerate(lines) if line.strip() == text)
        start = self.command(f'print-term-cell {row} 0').split()
        end = self.command(f'print-term-cell {row} {len(text) - 1}').split()
        self.command('move ' + ' '.join(start))
        self.command('down')
        self.command('move ' + ' '.join(end))
        self.command('up')
        self.command('wait 80')

    def pasted_editor_text(self):
        self.command('cmd toggle_terminal')
        self.command('cmd new_file')
        self.command('key ctrl+v')
        self.command('wait 150')
        return self.command('print-doc')

    def test_ctrl_c_without_selection_reaches_the_program(self):
        _, sent = self.read_keys('legacy', ['ctrl+c'])
        self.assertEqual(sent, ['^C'])

    def test_application_shortcuts_remain_available_in_terminal(self):
        self.command('key ctrl+shift+p')
        self.command('wait 150')
        self.assertIn('field=', self.command('print-palette'))
        self.command('key Escape')

    def test_ctrl_c_interrupts_a_running_shell_command(self):
        self.command("type sleep 20; echo STOP$((7+8))")
        self.command('key Return')
        self.command('wait 100')
        self.command('key ctrl+c')
        self.command('type echo RES$((4+5))')
        self.command('key Return')
        self.command('wait-term RES9')
        output = self.command('print-term')
        self.assertIn('RES9', output)
        self.assertNotIn('STOP15', output)

    @unittest.skipIf(sys.platform == 'darwin', 'macOS defaults to Command clipboard shortcuts')
    def test_hotkeys_save_and_reload(self):
        self.change_hotkey('copy_key', 'ctrl+alt+c')
        self.change_hotkey('paste_key', 'ctrl+alt+v')
        self.command('quit')
        self.process.wait(timeout=10)
        self.reader.close()
        self.client.close()
        self.process.stderr.close()
        config = (self.work / 'config/rhun/config').read_text()
        self.assertIn('ctrl+alt+c = terminal_copy when terminalFocus && terminalHasSelection', config)
        self.assertIn('ctrl+alt+v = terminal_paste when terminalFocus', config)
        self.start_editor()
        self.copy_text('persisted paste')
        _, sent = self.read_keys('legacy', ['ctrl+alt+v'])
        self.assertEqual(''.join(sent), 'persisted paste')

    @unittest.skipIf(sys.platform == 'darwin', 'macOS defaults to Command+C')
    def test_ctrl_c_copies_selection_without_sending_interrupt(self):
        self.copy_text('old clipboard')
        _, sent = self.read_keys('legacy', ['ctrl+c'], self.select_ready)
        self.assertEqual(sent, [])
        self.assertIn('READY1', self.pasted_editor_text())

    @unittest.skipIf(sys.platform == 'darwin', 'macOS defaults to Command clipboard shortcuts')
    def test_unified_remap_paste_live_and_clear_to_restore_program_ctrl_v(self):
        self.copy_text('remapped paste')
        self.change_hotkey('paste_key', 'ctrl+alt+v')
        _, sent = self.read_keys('legacy', ['ctrl+v', 'ctrl+alt+v'])
        self.assertEqual(''.join(sent), '^Vremapped paste')
        self.change_hotkey('paste_key', '')
        _, sent = self.read_keys('legacy', ['ctrl+v', 'ctrl+alt+v', 'ctrl+shift+v'])
        self.assertEqual(''.join(sent), '^VESC^Vremapped paste')

    @unittest.skipIf(sys.platform == 'darwin', 'macOS defaults to Command+C')
    def test_unified_remap_copy_live(self):
        self.copy_text('old clipboard')
        self.change_hotkey('copy_key', 'ctrl+alt+c')
        _, sent = self.read_keys('legacy', ['ctrl+alt+c'], self.select_ready)
        self.assertEqual(sent, [])
        self.assertIn('READY1', self.pasted_editor_text())

    @unittest.skipIf(sys.platform == 'darwin', 'macOS defaults to Command+C')
    def test_empty_copy_shortcut_keeps_ctrl_c_for_program_with_selection(self):
        self.copy_text('old clipboard')
        self.change_hotkey('copy_key', '')
        _, sent = self.read_keys('legacy', ['ctrl+c'], self.select_ready)
        self.assertEqual(sent, ['^C'])
        self.assertIn('old clipboard', self.pasted_editor_text())

    @unittest.skipIf(sys.platform == 'darwin', 'macOS defaults to Command clipboard shortcuts')
    def test_unified_reject_invalid_paste_key(self):
        self.copy_text('still works')
        for shortcut in ('ctrl', 'ctrl+garbage', 'ctrl+v+garbage'):
            with self.subTest(shortcut=shortcut):
                self.change_hotkey('paste_key', shortcut)
                self.assertIn('Invalid shortcut.', self.last_hotkey_toast)
        _, sent = self.read_keys('legacy', ['ctrl+v'])
        self.assertEqual(''.join(sent), 'still works')

    @unittest.skipIf(sys.platform == 'darwin', 'macOS Control+V remains a program key')
    def test_ctrl_v_pastes_text_in_legacy_terminal(self):
        self.copy_text('paste text')
        _, sent = self.read_keys('legacy', ['ctrl+v'])
        self.assertEqual(''.join(sent), 'paste text')

    @unittest.skipIf(sys.platform == 'darwin', 'macOS uses Command for clipboard shortcuts')
    def test_paste_shortcuts_preserve_bracketed_chinese_and_multiline_text(self):
        text = '中文\nsecond line'
        self.copy_text(text)
        expected = b'\x1b[200~' + text.encode('utf-8').replace(b'\n', b'\r') + b'\x1b[201~'
        for mode, shortcut in [('bracketed', 'ctrl+v'), ('kitty-paste', 'ctrl+v'),
                               ('bracketed', 'ctrl+shift+v'), ('bracketed', 'shift+Insert')]:
            with self.subTest(mode=mode, shortcut=shortcut):
                _, sent = self.read_keys(mode, [shortcut])
                self.assertEqual(bytes.fromhex(''.join(sent)), expected)

    @unittest.skipIf(sys.platform == 'darwin', 'macOS uses Command for clipboard shortcuts')
    def test_ctrl_alt_v_still_reaches_the_program(self):
        self.copy_text('must not paste')
        _, sent = self.read_keys('legacy', ['ctrl+alt+v'])
        self.assertEqual(''.join(sent), 'ESC^V')


if __name__ == '__main__':
    unittest.main()
