#!/usr/bin/python3
"""End-to-end private Fcitx keys through rhun's actual input/event loop."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import dbus

ROOT = Path(__file__).resolve().parents[1]


class FcitxInput(unittest.TestCase):
    def run_editor(self, actions, shortcut=None):
        # Each test uses the English start state on this test run's private bus.
        bus = dbus.bus.BusConnection(os.environ['RHUN_FCITX_BUS_ADDRESS'])
        controller = dbus.Interface(bus.get_object('org.fcitx.Fcitx5', '/controller'),
                                    'org.fcitx.Fcitx.Controller1')
        controller.Deactivate()
        with tempfile.TemporaryDirectory(prefix='rhun-fcitx-') as tmp:
            work = Path(tmp)
            config = work/'config/rhun/config'
            config.parent.mkdir(parents=True)
            config.write_text('[ui]\nsidebar=false\nagents_panel=false\n'
                '[editor]\n'
                '[git]\nenabled=false\n[updates]\ncheck=false\n'
                '[files]\nrestore_session=false\nrestore_project=false\n'
                '[terminal]\nshell=/bin/sh\n')
            if shortcut is not None:
                with config.open('a') as stream:
                    stream.write('[editor]\nchinese_toggle_key=' + shortcut + '\n')
            script = work/'actions'
            script.write_text('\n'.join(['cmd new_file', 'wait 1800', *actions,
                'wait 200', 'quit', '']))
            env = dict(os.environ, HOME=tmp, XDG_CONFIG_HOME=str(work/'config'),
                       XDG_STATE_HOME=str(work/'state'))
            run = subprocess.run([str(ROOT/'build/rhun'), tmp, '--headless',
                '1100x800', '--scale', '1', '--script', str(script)], env=env,
                capture_output=True, text=True, timeout=20)
            self.assertEqual(run.returncode, 0, run.stderr)
            return run.stdout

    def test_editor_commit_and_undo(self):
        out = self.run_editor(['key ctrl+space', 'wait 80', 'type zhongwen',
            'wait 350', 'echo preedit', 'print-doc',
            'shot /tmp/rhun-fcitx-candidates.ppm', 'key space', 'wait 200',
            'echo committed', 'print-doc', 'key ctrl+z', 'wait 100', 'print-doc'])
        self.assertIn('preedit\n\n<eod>', out)
        self.assertIn('committed\n中文', out)
        self.assertNotIn('zhongwen', out)
        self.assertTrue(out.rstrip().endswith('<eod>'), out)

    def test_cancel_and_english(self):
        out = self.run_editor(['key ctrl+space', 'wait 80', 'type ceshi',
            'wait 200', 'key Escape', 'wait 100', 'print-doc',
            'key ctrl+space', 'wait 100', 'type English', 'wait 200', 'print-doc'])
        self.assertTrue(out.lstrip().startswith('<eod>'), out)
        self.assertIn('English', out)
        self.assertNotIn('ceshi', out)

    def test_changed_document_discards_composition(self):
        out = self.run_editor(['key ctrl+space', 'wait 80', 'type zhongwen',
            'wait 200', 'cmd new_file', 'wait 100', 'key space', 'wait 100', 'print-doc'])
        self.assertNotIn('中文', out)
        self.assertNotIn('zhongwen', out)

    def test_digit_selection(self):
        out = self.run_editor(['key ctrl+space', 'wait 80', 'type zhongwen',
            'wait 200', 'key 2', 'wait 150', 'print-doc'])
        self.assertIn('中温', out)

    def test_application_toggle_shortcut(self):
        out = self.run_editor(['key ctrl+alt+space', 'wait 100', 'type zhongwen',
            'wait 200', 'key space', 'wait 150', 'print-doc'])
        self.assertIn('中文', out)

    def test_toggle_command(self):
        out = self.run_editor(['cmd toggle_chinese', 'wait 100', 'type zhongwen',
            'wait 200', 'key space', 'wait 150', 'print-doc'])
        self.assertIn('中文', out)

    def test_configured_toggle_replaces_default(self):
        out = self.run_editor(['print-keys', 'key ctrl+alt+p', 'wait 100',
            'type zhongwen', 'wait 200', 'key space', 'wait 150', 'print-doc',
            'key ctrl+alt+p', 'wait 100', 'type English', 'wait 150', 'print-doc'],
            shortcut='ctrl+alt+p')
        self.assertIn('ctrl+alt+p toggle_chinese source=builtin', out)
        self.assertNotIn('ctrl+alt+space toggle_chinese', out)
        self.assertIn('中文English', out)

    def test_modifier_only_shortcut_commits_chinese(self):
        out = self.run_editor(['print-keys', 'modifiers ctrl', 'modifiers ctrl+shift',
            'modifiers ctrl', 'modifiers none', 'wait 120', 'type zhongwen',
            'wait 250', 'key space', 'wait 180', 'print-doc',
            'modifiers shift', 'modifiers ctrl+shift', 'modifiers shift',
            'modifiers none', 'wait 120', 'type English', 'wait 180', 'print-doc'],
            shortcut='ctrl+shift')
        self.assertIn('ctrl+shift toggle_chinese source=builtin', out)
        self.assertNotIn('ctrl+alt+space toggle_chinese', out)
        self.assertIn('中文English', out)

    def test_settings_edit_rebinds_immediately(self):
        out = self.run_editor(['cmd settings', 'type chinese_toggle_key',
            'wait 200', 'print-settings', 'click 750 348', 'wait 100', 'key ctrl+a',
            'wait 100', 'type ctrl+alt+p', 'wait 200',
            'shot /tmp/rhun-shortcut-edited.ppm', 'key Return', 'wait 100',
            'print-keys', 'cmd close_tab', 'key ctrl+alt+p',
            'wait 100', 'type zhongwen', 'wait 200', 'key space', 'wait 150',
            'print-doc'])
        self.assertIn('editor.chinese_toggle_key', out)
        self.assertIn('ctrl+alt+p toggle_chinese source=builtin', out)
        self.assertNotIn('ctrl+alt+space toggle_chinese', out)
        self.assertIn('中文', out)

    def test_click_selection(self):
        out = self.run_editor(['key ctrl+space', 'wait 80', 'type zhongwen',
            'wait 200', 'click 85 166', 'wait 200', 'print-doc'])
        self.assertIn('中温', out)

    def test_window_focus_discards_composition(self):
        out = self.run_editor(['key ctrl+space', 'wait 80', 'type zhongwen',
            'wait 200', 'focus out', 'wait 100', 'focus in', 'wait 100',
            'key space', 'wait 150', 'print-doc'])
        self.assertNotIn('中文', out)
        self.assertNotIn('zhongwen', out)

    def test_backspace(self):
        out = self.run_editor(['key ctrl+space', 'wait 80', 'type zhongwenx',
            'wait 200', 'key BackSpace', 'wait 100', 'key space',
            'wait 150', 'print-doc'])
        self.assertIn('中文', out)

    def test_terminal_commit(self):
        out = self.run_editor(['cmd new_terminal', 'wait 250', 'type echo ',
            'wait 150', 'key ctrl+space', 'wait 80', 'type zhongwen', 'wait 200',
            'key space', 'wait 200', 'key Return', 'wait 300', 'print-term'])
        self.assertIn('中文', out)
        self.assertNotIn('zhongwen', out)

    def test_terminal_pane_switch_discards_composition(self):
        out = self.run_editor(['cmd new_terminal', 'wait 200',
            'cmd split_terminal_right', 'wait 200', 'print-terminals', 'key ctrl+alt+space',
            'wait 100', 'type zhongwen', 'wait 200',
            'key ctrl+alt+n', 'wait 150', 'key space', 'wait 150', 'print-term'])
        self.assertNotIn('中文', out)
        self.assertNotIn('zhongwen', out)
        self.assertEqual(out.count('kind=shell'), 2, out)

    def test_find_field(self):
        out = self.run_editor(['type baseline', 'wait 100', 'cmd find',
            'wait 100', 'key ctrl+space', 'wait 80', 'type zhongwen', 'wait 150',
            'key space', 'wait 150', 'shot /tmp/rhun-fcitx-find.ppm',
            'key Escape', 'wait 100', 'print-doc'])
        self.assertIn('baseline', out)
        self.assertNotIn('中文', out)

if __name__ == '__main__':
    unittest.main()
