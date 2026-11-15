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
    def run_editor(self, actions, shortcut='ctrl+shift', bindings=''):
        with tempfile.TemporaryDirectory(prefix='rhun-toggle-') as tmp:
            work = Path(tmp)
            config = work / 'config/rhun/config'
            config.parent.mkdir(parents=True)
            config.write_text('[ui]\nsidebar=false\nagents_panel=false\n'
                              '[updates]\ncheck=false\n[git]\nenabled=false\n'
                              '[files]\nrestore_session=false\nrestore_project=false\n'
                              '[editor]\nchinese_toggle_key=' + shortcut + '\n[keys]\n' + bindings)
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

    def test_unified_editor_save_and_rebind_modifier_only(self):
        out, config = self.run_editor(['cmd keyboard_shortcuts', 'type Chinese Pinyin',
            'key F2', 'key F2', 'type ctrl+shift', 'key Return', 'print-keys', 'key Escape',
            'modifiers ctrl', 'modifiers ctrl+shift', 'modifiers ctrl', 'print-toast'],
            shortcut='ctrl+alt+space')
        self.assertIn('ctrl+shift = toggle_chinese', config)
        self.assertIn('ctrl+shift toggle_chinese source=user', out)
        self.assertIn('ctrl+alt+space = none', config)
        self.assertIn(UNAVAILABLE, out)

    def test_invalid_unified_value_keeps_previous_and_shows_feedback(self):
        out, _ = self.run_editor(['cmd keyboard_shortcuts', 'type Chinese Pinyin',
            'key F2', 'key F2', 'type ctrl+garbage', 'key Return', 'print-toast',
            'key Escape', 'print-keys'])
        self.assertIn('Invalid shortcut.', out)
        self.assertIn('ctrl+shift toggle_chinese source=builtin', out)

    def test_physical_recording_survives_modifier_release_and_updates_list(self):
        out, config = self.run_editor(['cmd keyboard_shortcuts', 'type Chinese Pinyin',
            'key F2', 'modifiers ctrl', 'modifiers ctrl+alt', 'key ctrl+alt+p',
            'modifiers ctrl', 'modifiers none', 'print-palette', 'key Return',
            'type Chinese Pinyin', 'print-palette', 'key F2', 'key F6', 'key Return',
            'type Chinese Pinyin', 'print-palette', 'key Escape', 'key F6', 'print-toast'])
        self.assertIn('field=Ctrl+Alt+P', out)
        self.assertIn('> Ctrl+Alt+P  Input: Toggle Chinese Pinyin', out)
        self.assertIn('> F6  Input: Toggle Chinese Pinyin', out)
        self.assertNotIn('  Ctrl+Shift  Input: Toggle Chinese Pinyin', out)
        self.assertIn('F6 = toggle_chinese', config)
        self.assertIn('Ctrl+Alt+P = none', config)
        self.assertIn(UNAVAILABLE, out)

    def test_record_modifier_only_without_running_current_toggle(self):
        out, config = self.run_editor(['cmd keyboard_shortcuts', 'type Chinese Pinyin',
            'key F2', 'modifiers ctrl', 'modifiers ctrl+shift', 'modifiers ctrl',
            'modifiers none', 'print-palette', 'print-toast', 'key Return',
            'key Escape', 'modifiers ctrl+shift', 'modifiers none', 'print-toast'])
        self.assertIn('field=Ctrl+Shift', out)
        self.assertEqual(out.count(UNAVAILABLE), 1, out)
        self.assertIn('Ctrl+Shift = toggle_chinese', config)

    def test_record_chord_cancel_and_clear(self):
        out, config = self.run_editor(['cmd keyboard_shortcuts', 'type Chinese Pinyin',
            'key F2', 'key ctrl+k', 'key ctrl+t', 'print-palette', 'key Escape',
            'cmd keyboard_shortcuts', 'type Chinese Pinyin', 'key F2',
            'key BackSpace', 'key Return', 'type Chinese Pinyin', 'print-palette'])
        self.assertIn('field=Ctrl+K Ctrl+T', out)
        self.assertIn('ctrl+shift = none', config)
        self.assertNotIn('  Input: Toggle Chinese Pinyin', out.split('field=\n')[-1])

    def test_unified_user_key_and_shift_alone(self):
        for stroke, actions in [
            ('alt+shift+p', ['key alt+shift+p']),
            ('F6', ['key F6']),
            ('shift', ['modifiers shift', 'modifiers none']),
            ('alt+shift', ['modifiers alt', 'modifiers alt+shift', 'modifiers none']),
        ]:
            with self.subTest(stroke=stroke):
                out, _ = self.run_editor([*actions, 'print-toast'],
                    bindings=stroke+' = toggle_chinese\n')
                self.assertIn(UNAVAILABLE, out)

    def test_shift_typing_and_shortcuts_never_toggle(self):
        for actions in [
            ['modifiers shift', 'key shift+a', 'modifiers none'],
            ['modifiers shift', 'modifiers ctrl+shift', 'key ctrl+shift+p',
             'modifiers shift', 'modifiers none'],
            ['modifiers shift', 'click 500 400', 'modifiers none'],
        ]:
            with self.subTest(actions=actions):
                out, _ = self.run_editor([*actions, 'print-toast'],
                    bindings='shift = toggle_chinese\n')
                self.assertNotIn(UNAVAILABLE, out)

    def test_unified_cancel_and_reedit_persist_one_binding(self):
        edit = ['cmd keyboard_shortcuts', 'type Chinese Pinyin', 'key F2', 'key F2']
        out, config = self.run_editor([
            *edit, 'type F6', 'key Escape', 'print-keys',
            *edit, 'type alt+shift+p', 'key Return', 'key Escape',
            *edit, 'type F6', 'key Return', 'key Escape',
            'key F6', 'print-toast'])
        self.assertIn('F6 = toggle_chinese', config)
        self.assertEqual(config.count('F6 = toggle_chinese'), 1)
        self.assertIn(UNAVAILABLE, out)

    def test_empty_disables_and_single_modifier_stays_invalid(self):
        out, _ = self.run_editor(['print-keys', 'modifiers ctrl+shift',
                                  'modifiers none', 'print-toast'], shortcut='')
        self.assertNotIn('toggle_chinese source=', out)
        self.assertNotIn(UNAVAILABLE, out)
        out, _ = self.run_editor(['print-keys'], shortcut='ctrl')
        self.assertIn('ctrl+alt+space toggle_chinese', out)


if __name__ == '__main__':
    unittest.main()
