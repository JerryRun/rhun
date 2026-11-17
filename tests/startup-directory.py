#!/usr/bin/env python3
"""Startup chooses cwd or its unique workspace; last-project restoration remains opt-in."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
EXE = Path(os.environ.get('RHUN_TEST_EXE', ROOT / 'build/rhun')).resolve()


class StartupDirectory(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='rhun-startup-')
        self.home = Path(self.tmp.name).resolve()
        self.current, self.previous, self.lib = [self.home / name for name in
                                                ('current café', 'previous', 'lib')]
        for folder in (self.current, self.previous, self.lib):
            folder.mkdir()
        self.config = self.home / 'config/rhun/config'
        self.config.parent.mkdir(parents=True)
        self.marker = self.home / 'state/rhun/last-project'
        self.marker.parent.mkdir(parents=True)
        self.marker.write_text(self.previous.as_posix(), encoding='utf-8')
        self.env = dict(os.environ, HOME=self.home.as_posix(),
                        XDG_CONFIG_HOME=(self.home / 'config').as_posix(),
                        XDG_STATE_HOME=(self.home / 'state').as_posix())
        self.configure()

    def tearDown(self):
        self.tmp.cleanup()

    def configure(self, restore=None, tabs=False):
        setting = '' if restore is None else f'restore_project={str(restore).lower()}\n'
        self.config.write_text('[ui]\nsidebar=true\nagents_panel=false\n[files]\n'
                               f'{setting}restore_session={str(tabs).lower()}\n'
                               '[git]\nenabled=false\n[updates]\ncheck=false\n',
                               encoding='utf-8')

    def run_editor(self, paths=(), actions=(), cwd=None):
        script = self.home / 'commands.rsc'
        script.write_text('\n'.join(['wait 60', *actions, 'print-project', 'print-workspace',
                                     'print-folders', 'print-state', 'quit', '']), encoding='utf-8')
        result = subprocess.run([str(EXE), *map(str, paths), '--headless', '1000x700',
                                 '--scale', '1', '--script', str(script)], cwd=cwd or self.current,
                                env=self.env, capture_output=True, text=True, encoding='utf-8',
                                timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.replace('\\', '/')

    def workspace(self, name='团队 workspace', text=None):
        file = self.current / (name + '.rhun-workspace')
        file.write_text(text if text is not None else '[folders]\npath = .\npath = ../lib\n',
                        encoding='utf-8')
        return file

    def assert_project(self, output, folder):
        self.assertIn(f'project=~/{folder.name}\n', output)

    def assert_workspace(self, output, file):
        self.assertIn(f'workspace={file.as_posix()} title={file.stem} (WORKSPACE)\n', output)
        self.assertIn(f'name=lib path={self.lib.as_posix()}', output)

    def test_default_opens_current_directory_instead_of_last_project(self):
        output = self.run_editor()
        self.assert_project(output, self.current)
        self.assertIn(f'workspace= title={self.current.name}\n', output)

    def test_disabled_restore_opens_current_directory(self):
        self.configure(restore=False)
        self.assert_project(self.run_editor(), self.current)

    def test_enabled_restore_keeps_previous_behavior(self):
        self.configure(restore=True)
        self.assert_project(self.run_editor(), self.previous)

    def test_unique_definition_opens_as_named_workspace(self):
        file = self.workspace()
        self.assert_workspace(self.run_editor(), file)

    def test_disabled_restore_discovers_workspace(self):
        self.configure(restore=False)
        file = self.workspace()
        self.assert_workspace(self.run_editor(), file)

    def test_enabled_restore_precedes_workspace_in_cwd(self):
        self.configure(restore=True)
        self.workspace()
        output = self.run_editor()
        self.assert_project(output, self.previous)
        self.assertIn('workspace= title=previous\n', output)

    def test_unavailable_previous_project_falls_back_to_current_workspace(self):
        self.configure(restore=True)
        file = self.workspace()
        for marker in (self.home / 'missing', None, ''):
            with self.subTest(marker=marker):
                if marker is None:
                    self.marker.unlink()
                else:
                    self.marker.write_text(str(marker), encoding='utf-8')
                self.assert_workspace(self.run_editor(), file)

    def test_explicit_dot_and_folder_discover_workspace_even_with_restore_enabled(self):
        self.configure(restore=True)
        file = self.workspace()
        for path, cwd in (('.', self.current), (self.current, self.previous),
                          (Path('..') / self.current.name, self.previous)):
            with self.subTest(path=path):
                self.assert_workspace(self.run_editor([path], cwd=cwd), file)

    def test_workspace_primary_can_be_another_directory(self):
        file = self.workspace(text='[folders]\npath = ../previous\npath = ../lib\n')
        output = self.run_editor()
        self.assert_project(output, self.previous)
        self.assert_workspace(output, file)

    def test_multiple_definitions_require_explicit_selection(self):
        self.workspace('one')
        second = self.workspace('two')
        output = self.run_editor()
        self.assert_project(output, self.current)
        self.assertIn(f'workspace= title={self.current.name}\n', output)
        self.assert_workspace(self.run_editor([second]), second)

    def test_invalid_or_oversized_definition_falls_back_to_directory(self):
        for text in ('not a workspace', '[folders]\npath = ../missing\n', 'x' * 65537):
            with self.subTest(size=len(text)):
                self.workspace(text=text)
                output = self.run_editor()
                self.assert_project(output, self.current)
                self.assertIn(f'workspace= title={self.current.name}\n', output)

    def test_directories_with_workspace_suffix_are_ignored(self):
        (self.current / 'fake.rhun-workspace').mkdir()
        file = self.workspace()
        self.assert_workspace(self.run_editor(), file)

    def test_workspace_in_child_directory_is_not_discovered(self):
        child = self.current / 'child'
        child.mkdir()
        (child / 'nested.rhun-workspace').write_text('[folders]\npath = ..\n', encoding='utf-8')
        output = self.run_editor()
        self.assert_project(output, self.current)
        self.assertIn(f'workspace= title={self.current.name}\n', output)

    def test_empty_window_bypasses_both_startup_modes(self):
        self.workspace()
        for restore in (False, True):
            self.configure(restore=restore)
            output = self.run_editor(['--empty'])
            self.assertIn('project=\n', output)
            self.assertIn('tabs=0 ', output)

    def test_explicit_file_bypasses_workspace_discovery_and_last_project(self):
        self.configure(restore=True)
        self.workspace()
        file = self.current / 'notes.txt'
        file.write_text('notes\n', encoding='utf-8')
        output = self.run_editor([file])
        self.assertIn('tabs=1 active=notes.txt ', output)
        self.assertIn('workspace= title=' + self.current.name + '\n', output)
        self.assertNotIn('name=lib path=', output)

    def test_explicit_multiple_folders_bypass_discovery(self):
        self.workspace()
        output = self.run_editor([self.current, self.previous])
        self.assert_project(output, self.current)
        self.assertIn(f'workspace= title={self.current.name} + previous\n', output)
        self.assertIn('name=previous path=', output)
        self.assertNotIn('name=lib path=', output)

    def test_session_restoration_follows_selected_workspace(self):
        self.configure(tabs=True)
        self.workspace()
        file = self.lib / 'restored.txt'
        file.write_text('restore me\n', encoding='utf-8')
        self.run_editor(actions=[f'open {file.as_posix()}'])
        # Replace the last-project marker to prove cwd discovery chooses the session.
        self.marker.write_text(self.previous.as_posix(), encoding='utf-8')
        self.assertIn('tabs=1 active=restored.txt ', self.run_editor())


if __name__ == '__main__':
    unittest.main(verbosity=2)
