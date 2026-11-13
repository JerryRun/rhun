#!/usr/bin/env python3
"""Modifier-only Chinese toggle configuration and clean-release dispatch."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
EXE = Path(os.environ.get('RHUN_TEST_EXE', ROOT / 'build/rhun')).resolve()
UNAVAILABLE = 'Inline Chinese input unavailable; normal keyboard input restored.'


class ChineseToggle(unittest.TestCase):
    def run_editor(self, actions, shortcut='ctrl+shift'):
        with tempfile.TemporaryDirectory(prefix='rhun-toggle-') as tmp:
            work = Path(tmp)
            config = work / 'config/rhun/config'
            config.parent.mkdir(parents=True)
            config.write_text('[ui]\nsidebar=false\nagents_panel=false\n'
                              '[updates]\ncheck=false\n[git]\nenabled=false\n'
                              '[files]\nrestore_session=false\nrestore_project=false\n'
                              '[editor]\nchinese_toggle_key=' + shortcut + '\n')
            script = work / 'commands'
            script.write_text('\n'.join(['cmd new_file', *actions, 'quit', '']))
            env = dict(os.environ, HOME=tmp, XDG_CONFIG_HOME=str(work / 'config'),
                       XDG_STATE_HOME=str(work / 'state'))
            env.pop('RHUN_FCITX_ROOT', None)
            result = subprocess.run([str(EXE), tmp, '--headless', '1000x700',
                                     '--scale', '1', '--script', str(script)], env=env,
                                    capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            return result.stdout, config.read_text()

    def test_config_keeps_modifier_only_value_and_replaces_default(self):
        out, _ = self.run_editor(['print-keys'])
        self.assertIn('ctrl+shift toggle_chinese source=builtin', out)
        self.assertNotIn('ctrl+alt+space toggle_chinese', out)

    def test_clean_release_toggles_once(self):
        out, _ = self.run_editor(['modifiers ctrl', 'modifiers ctrl+shift', 'print-toast',
                                  'modifiers ctrl', 'print-toast', 'modifiers none'])
        self.assertEqual(out.splitlines(), ['toast=', 'toast=' + UNAVAILABLE])

    def test_shift_first_also_toggles(self):
        out, _ = self.run_editor(['modifiers shift', 'modifiers ctrl+shift',
                                  'modifiers shift', 'print-toast'])
        self.assertIn(UNAVAILABLE, out)

    def test_typing_shortcut_and_extra_modifier_cancel_toggle(self):
        for middle in (['key ctrl+shift+p'], ['modifiers ctrl+shift+alt']):
            with self.subTest(middle=middle):
                out, _ = self.run_editor(['modifiers ctrl', 'modifiers ctrl+shift',
                    *middle, 'modifiers ctrl', 'modifiers none', 'print-toast'])
                self.assertNotIn(UNAVAILABLE, out)

    def test_focus_or_click_cancels_pending_gesture(self):
        for middle in (['focus out', 'focus in'], ['click 500 400']):
            with self.subTest(middle=middle):
                out, _ = self.run_editor(['modifiers ctrl', 'modifiers ctrl+shift',
                    *middle, 'modifiers ctrl', 'modifiers none', 'print-toast'])
                self.assertNotIn(UNAVAILABLE, out)

    def test_settings_save_and_rebind_modifier_only(self):
        out, config = self.run_editor(['cmd settings', 'type chinese_toggle_key',
            'click 750 348', 'key ctrl+a', 'type ctrl+shift', 'key Return',
            'print-keys', 'cmd close_tab', 'modifiers ctrl', 'modifiers ctrl+shift',
            'modifiers ctrl', 'print-toast'], shortcut='ctrl+alt+space')
        self.assertIn('chinese_toggle_key = ctrl+shift', config)
        self.assertIn('ctrl+shift toggle_chinese source=builtin', out)
        self.assertNotIn('ctrl+alt+space toggle_chinese', out)
        self.assertIn(UNAVAILABLE, out)

    def test_invalid_settings_value_keeps_previous_and_shows_feedback(self):
        out, _ = self.run_editor(['cmd settings', 'type chinese_toggle_key',
            'click 750 348', 'key ctrl+a', 'type ctrl+garbage', 'key Return',
            'print-toast', 'print-keys'])
        self.assertIn('Invalid shortcut.', out)
        self.assertIn('ctrl+shift toggle_chinese source=builtin', out)

    def test_empty_disables_and_single_modifier_stays_invalid(self):
        out, _ = self.run_editor(['print-keys', 'modifiers ctrl+shift',
                                  'modifiers none', 'print-toast'], shortcut='')
        self.assertNotIn('toggle_chinese source=', out)
        self.assertNotIn(UNAVAILABLE, out)
        out, _ = self.run_editor(['print-keys'], shortcut='ctrl')
        self.assertIn('ctrl+alt+space toggle_chinese', out)


if __name__ == '__main__':
    unittest.main()
