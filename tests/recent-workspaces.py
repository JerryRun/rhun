#!/usr/bin/env python3
"""Recent workspace files in the project menu, independent of session restoration."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
EXE = Path(os.environ.get('RHUN_TEST_EXE', ROOT / 'build/rhun')).resolve()


class RecentWorkspaces(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='rhun-recent-workspaces-')
        self.home = Path(self.tmp.name)
        self.repo, self.lib, self.other = [self.home / n for n in ('repo', 'lib', 'other')]
        for folder in (self.repo, self.lib, self.other):
            folder.mkdir()
        self.state = self.home / 'state/rhun'
        config = self.home / 'config/rhun/config'
        config.parent.mkdir(parents=True)
        config.write_text('[ui]\nsidebar=true\nagents_panel=false\n'
                          '[updates]\ncheck=false\n[git]\nenabled=false\n'
                          '[files]\nrestore_session=false\nrestore_project=false\n')
        self.env = dict(os.environ, HOME=str(self.home),
                        XDG_CONFIG_HOME=str(self.home / 'config'),
                        XDG_STATE_HOME=str(self.home / 'state'))

    def tearDown(self):
        self.tmp.cleanup()

    def workspace(self, name='team', folders=None):
        file = self.home / (name + '.rhun-workspace')
        file.write_text('[folders]\n' + ''.join(f'path = {p}\n' for p in
                                               (folders or (self.repo, self.lib))))
        return file

    def run_editor(self, start, actions=()):
        script = self.home / 'commands'
        script.write_text('\n'.join(['wait 60', *actions, 'quit', '']))
        r = subprocess.run([str(EXE), str(start), '--headless', '1000x700', '--scale', '1',
                            '--script', str(script)], env=self.env, capture_output=True,
                           text=True, timeout=20)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def menu(self):
        return ['click 60 20', 'print-menu']

    def label(self, path):
        return '~/' + str(path.relative_to(self.home)) + ' (Workspace)'

    def test_workspace_title_marks_single_and_multiple_folder_workspaces(self):
        for name, folders in (('single', (self.repo,)), ('team', (self.repo, self.lib))):
            with self.subTest(name=name):
                ws = self.workspace(name, folders)
                out = self.run_editor(ws, ['print-workspace'])
                self.assertEqual(out.strip(), f'workspace={ws} title={name} (WORKSPACE)')

    def test_workspace_title_suffix_follows_save_as_and_clears_for_plain_folder(self):
        ws = self.repo / 'saved.rhun-workspace'
        out = self.run_editor(self.repo, ['print-workspace', 'workspace-save saved',
            'print-workspace', f'open {self.other}', 'print-workspace'])
        self.assertEqual(out.splitlines(), ['workspace= title=repo',
            f'workspace={ws} title=saved (WORKSPACE)', 'workspace= title=other'])

    def test_restart_remembers_workspace_with_session_restore_disabled(self):
        ws = self.workspace()
        self.run_editor(ws)
        out = self.run_editor(self.other, [*self.menu(), f'menu-pick {self.label(ws)}',
                                          'wait 60', 'print-workspace', 'print-folders'])
        self.assertIn(self.label(ws), out)
        self.assertIn(f'workspace={ws} title=team', out)
        self.assertIn(f'name=repo path={self.repo}', out)
        self.assertIn(f'name=lib path={self.lib}', out)

    def test_newly_saved_workspace_is_available_without_restarting(self):
        ws = self.repo / 'saved.rhun-workspace'
        out = self.run_editor(self.repo, [f'folder-add {self.lib}', 'workspace-save saved',
            f'open {self.other}', *self.menu(), f'menu-pick {self.label(ws)}',
            'wait 60', 'print-workspace', 'print-folders'])
        self.assertIn(self.label(ws), out)
        self.assertIn(f'workspace={ws} title=saved', out)
        self.assertIn(f'name=lib path={self.lib}', out)

    def test_workspaces_sharing_primary_folder_keep_distinct_definitions(self):
        first = self.workspace('first', (self.repo, self.lib))
        second = self.workspace('second', (self.repo, self.other))
        self.run_editor(first)
        self.run_editor(second)
        out = self.run_editor(self.lib, [*self.menu(),
            f'menu-pick {self.label(first)}', 'wait 60', 'print-workspace', 'print-folders',
            *self.menu(), f'menu-pick {self.label(second)}', 'wait 60',
            'print-workspace', 'print-folders'])
        self.assertIn(f'workspace={first} title=first', out)
        self.assertIn(f'workspace={second} title=second', out)
        groups = [line for line in out.splitlines() if line.startswith('folder=')]
        self.assertEqual([line.split(' name=')[1].split(' path=')[0] for line in groups],
                         ['repo', 'lib', 'repo', 'other'])

    def test_unicode_spaces_and_percent_names_roundtrip(self):
        ws = self.workspace('我的 50%工作区')
        self.run_editor(ws)
        out = self.run_editor(self.other, [*self.menu(), f'menu-pick {self.label(ws)}',
                                          'wait 60', 'print-workspace'])
        self.assertIn(f'workspace={ws} title=我的 50%工作区', out)
        self.assertEqual(out.count(self.label(ws)), 1)

    def test_current_and_deleted_workspaces_are_not_listed(self):
        current, deleted = self.workspace('current'), self.workspace('deleted')
        self.run_editor(deleted)
        self.run_editor(current)
        deleted.unlink()
        out = self.run_editor(current, self.menu())
        self.assertNotIn(self.label(current), out)
        self.assertNotIn(self.label(deleted), out)

    def test_invalid_workspace_is_not_remembered(self):
        ws = self.workspace('invalid', (self.home / 'missing',))
        self.run_editor(ws)
        self.assertEqual(list(self.state.glob('*.workspace')), [])
        self.assertNotIn(self.label(ws), self.run_editor(self.other, self.menu()))

    def test_reopening_updates_order_without_duplicates_and_keeps_folder_recents(self):
        first, second = self.workspace('first'), self.workspace('second')
        self.run_editor(first)
        self.run_editor(second)
        old_folder = self.home / 'old-folder'
        old_folder.mkdir()
        if os.name == 'nt':
            key = ''.join(f'%{ord(c):02X}' if c in '%:/\\<>"|?*' or ord(c) < 32 else c
                          for c in str(old_folder))
        else:
            key = str(old_folder).replace('%', '%%25').replace('/', '%')
        session = self.state / (key + '.session')
        session.write_text('')
        os.utime(session, ns=(1_000_000_000, 1_000_000_000))
        self.run_editor(first)
        out = self.run_editor(self.other, self.menu())
        self.assertLess(out.index(self.label(first)), out.index(self.label(second)))
        self.assertLess(out.index(self.label(second)), out.index('~/old-folder'))
        self.assertEqual(out.count(self.label(first)), 1)
        self.assertEqual(len(list(self.state.glob('*.workspace'))), 2)

    def test_recent_menu_keeps_existing_nine_item_limit(self):
        files = [self.workspace(f'team-{i:02}') for i in range(11)]
        self.run_editor(self.other, [f'open {p}' for p in files])
        out = self.run_editor(self.other, self.menu())
        self.assertEqual(out.count(' (Workspace)'), 9)
        self.assertNotIn(self.label(files[0]), out)
        self.assertNotIn(self.label(files[1]), out)
        self.assertLess(out.index(self.label(files[-1])), out.index(self.label(files[-2])))


if __name__ == '__main__':
    unittest.main(verbosity=2)
