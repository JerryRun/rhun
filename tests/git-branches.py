#!/usr/bin/env python3
"""The Git branch picker operates on the selected repository and preserves edits on refusal."""
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
EXE = Path(os.environ.get('RHUN_TEST_EXE', ROOT / 'build/rhun')).resolve()


class BranchPicker(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='rhun-branches-')
        self.home = Path(self.tmp.name)
        self.repo = self.home / 'repo 中文'
        self.repo.mkdir()
        self.env = dict(os.environ, HOME=str(self.home),
                        XDG_CONFIG_HOME=str(self.home / 'config'),
                        XDG_STATE_HOME=str(self.home / 'state'), GIT_CONFIG_NOSYSTEM='1')
        config = self.home / 'config/rhun/config'
        config.parent.mkdir(parents=True)
        config.write_text('[ui]\nsidebar=false\nagents_panel=false\n'
                          '[files]\nrestore_session=false\nrestore_project=false\n'
                          '[updates]\ncheck=false\n[editor]\ncursor_blink=false\n', encoding='utf-8')
        self.init_repo(self.repo)
        self.file = self.repo / 'sample.txt'

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args, repo=None):
        result = subprocess.run(['git', '-C', str(repo or self.repo), *args], env=self.env,
                                capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def init_repo(self, repo):
        self.git('init', '-q', repo=repo)
        self.git('symbolic-ref', 'HEAD', 'refs/heads/main', repo=repo)
        self.git('config', 'user.name', 'Test', repo=repo)
        self.git('config', 'user.email', 'test@example.invalid', repo=repo)
        (repo / 'sample.txt').write_text('initial\n', encoding='utf-8')
        self.git('add', '.', repo=repo)
        self.git('commit', '-qm', 'Initial', repo=repo)

    def run_editor(self, actions, projects=None, size='1200x800', scale='1'):
        script = self.home / 'commands'
        script.write_text('\n'.join(['wait-git', *actions, 'quit', '']), encoding='utf-8')
        args = projects or [self.repo, self.file]
        result = subprocess.run([str(EXE), *map(str, args), '--headless', size, '--scale', scale,
                                 '--script', str(script)], env=self.env,
                                capture_output=True, text=True, encoding='utf-8', timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def pick(self, name):
        return ['cmd git_switch_branch', 'wait-git', f'type {name}',
                'print-palette', 'key Return', 'wait-git', 'print-git', 'print-scm']

    def test_filter_and_switch_preserve_literal_names_and_exclude_remote_refs(self):
        branch = 'feat/中文-$literal;quote\'name'
        self.git('branch', branch)
        self.git('update-ref', 'refs/remotes/origin/remote-only', 'HEAD')
        out = self.run_editor(['cmd git_switch_branch', 'wait-git', 'print-palette',
                               f'type {branch}', 'print-palette', 'key Return', 'wait-git',
                               'print-git', 'print-scm'])
        self.assertIn('choose=Switch local branch', out)
        self.assertIn('> ' + branch, out)
        self.assertNotIn('remote-only', out)
        self.assertEqual(self.git('symbolic-ref', '--short', 'HEAD').strip(), branch)
        self.assertNotIn('error=', out)

    def test_click_branch_row_opens_list_and_mouse_selects(self):
        self.git('branch', 'feature')
        shot = self.home / 'branch-picker.ppm'
        # Close Explore so Changes starts directly below its disclosure header.
        out = self.run_editor(['cmd git_history', 'wait-git', 'click 30 54',
                               'click 80 112', 'wait-git', 'print-palette',
                               'type feature', f'shot {shot}', 'click 500 110',
                               'wait-git', 'print-palette', 'print-git'])
        self.assertIn('choose=Switch local branch', out)
        self.assertEqual(self.git('symbolic-ref', '--short', 'HEAD').strip(), 'feature')
        self.assertIn('none', out)
        artifacts = os.environ.get('RHUN_TEST_ARTIFACT_DIR')
        if artifacts:
            from PIL import Image
            target = Path(artifacts)
            target.mkdir(parents=True, exist_ok=True)
            Image.open(shot).save(target / 'branch-picker.png')

    def test_current_branch_and_escape_leave_draft_and_changes(self):
        self.git('branch', 'feature')
        self.file.write_text('local change\n', encoding='utf-8')
        before = self.git('status', '--porcelain')
        out = self.run_editor(['cmd git_history', 'wait-git', 'key Return',
                               'type Keep this commit draft',
                               'cmd git_switch_branch', 'wait-git', 'type feature',
                               'key Escape', 'print-palette',
                               *self.pick('main'), 'print-scm'])
        self.assertEqual(self.git('symbolic-ref', '--short', 'HEAD').strip(), 'main')
        self.assertEqual(self.git('status', '--porcelain'), before)
        self.assertIn('Keep this commit draft', out)
        self.assertIn('none', out)

    def test_conflicting_edits_are_not_discarded_or_stashed(self):
        self.git('checkout', '-qb', 'feature')
        self.file.write_text('branch change\n', encoding='utf-8')
        self.git('commit', '-qam', 'Feature')
        self.git('checkout', '-q', 'main')
        self.file.write_text('staged local change\n', encoding='utf-8')
        self.git('add', '.')
        self.file.write_text('unstaged local change\n', encoding='utf-8')
        untracked = self.repo / 'keep.txt'
        untracked.write_text('untracked\n', encoding='utf-8')
        before = self.git('status', '--porcelain')
        out = self.run_editor(['key ctrl+End', 'type UNSAVED', *self.pick('feature'), 'print-doc'])
        self.assertEqual(self.git('symbolic-ref', '--short', 'HEAD').strip(), 'main')
        self.assertEqual(self.git('status', '--porcelain'), before)
        self.assertEqual(self.file.read_text(encoding='utf-8'), 'unstaged local change\n')
        self.assertEqual(untracked.read_text(encoding='utf-8'), 'untracked\n')
        self.assertEqual(self.git('stash', 'list'), '')
        self.assertIn('UNSAVED', out)
        self.assertIn('error=Your local changes', out)

    def test_branch_checked_out_in_another_worktree_reports_error(self):
        self.git('branch', 'occupied')
        self.git('worktree', 'add', str(self.home / 'linked'), 'occupied')
        out = self.run_editor(self.pick('occupied'))
        self.assertEqual(self.git('symbolic-ref', '--short', 'HEAD').strip(), 'main')
        self.assertIn('already', out)
        self.assertIn('error=', out)

    def test_selected_workspace_repository_receives_the_switch(self):
        other = self.home / 'other'
        other.mkdir()
        self.init_repo(other)
        self.git('branch', 'only-first')
        self.git('branch', 'only-second', repo=other)
        out = self.run_editor(['repo-show 1', 'wait 100', 'wait-git',
                               'cmd git_switch_branch', 'wait-git', 'print-palette',
                               'type only-second', 'key Return', 'wait-git', 'print-repos'],
                              projects=[self.repo, other])
        self.assertIn('only-second', out)
        self.assertNotIn('only-first', out)
        self.assertEqual(self.git('symbolic-ref', '--short', 'HEAD').strip(), 'main')
        self.assertEqual(self.git('symbolic-ref', '--short', 'HEAD', repo=other).strip(), 'only-second')

    def test_repository_change_closes_stale_branch_list(self):
        other = self.home / 'other'
        other.mkdir()
        self.init_repo(other)
        self.git('branch', 'first-only')
        out = self.run_editor(['cmd git_switch_branch', 'wait-git', 'print-palette',
                               'repo-show 1', 'wait 100', 'wait-git', 'print-palette',
                               'key Return', 'wait-git'], projects=[self.repo, other])
        self.assertIn('first-only', out)
        self.assertIn('none', out)
        self.assertEqual(self.git('symbolic-ref', '--short', 'HEAD', repo=other).strip(), 'main')

    def test_many_branches_are_searchable(self):
        for i in range(80):
            self.git('branch', f'feature/{i:03}')
        out = self.run_editor(self.pick('feature/079'))
        self.assertIn('> feature/079', out)
        self.assertEqual(self.git('symbolic-ref', '--short', 'HEAD').strip(), 'feature/079')

    def test_keyboard_navigation_switches_without_typing(self):
        self.git('branch', 'aaa')
        self.git('branch', 'zzz')
        out = self.run_editor(['cmd git_switch_branch', 'wait-git', 'print-palette',
                               'key Down', 'key Down', 'print-palette',
                               'key Return', 'wait-git', 'print-git'])
        selected = [line[2:] for line in out.splitlines() if line.startswith('> ')]
        self.assertEqual(len(selected), 2, out)
        self.assertNotEqual(selected[0], selected[1], out)
        self.assertEqual(self.git('symbolic-ref', '--short', 'HEAD').strip(), selected[-1], out)

    def test_detached_head_and_branch_named_like_a_file(self):
        self.git('branch', 'sample.txt')
        self.git('checkout', '-q', '--detach')
        out = self.run_editor(self.pick('sample.txt'))
        self.assertEqual(self.git('symbolic-ref', '--short', 'HEAD').strip(), 'sample.txt')
        self.assertEqual(self.file.read_text(encoding='utf-8'), 'initial\n')
        self.assertNotIn('error=', out)

    def test_switch_reloads_changed_files_and_keeps_unsaved_edits(self):
        self.git('checkout', '-qb', 'feature')
        self.file.write_text('feature content\n', encoding='utf-8')
        self.git('commit', '-qam', 'Feature')
        self.git('checkout', '-q', 'main')
        out = self.run_editor([*self.pick('feature'), 'wait 200', 'print-doc',
                               'key Escape', 'key ctrl+End', 'type UNSAVED',
                               *self.pick('main'), 'wait 200', 'print-doc'])
        self.assertEqual(self.git('symbolic-ref', '--short', 'HEAD').strip(), 'main')
        self.assertEqual(self.file.read_text(encoding='utf-8'), 'initial\n')
        self.assertIn('feature content', out)
        self.assertIn('UNSAVED', out)

    def test_light_theme_and_large_scale_show_complete_current_branch(self):
        branch = 'feature/' + 'long-name-' * 12
        self.git('checkout', '-qb', branch)
        with (self.home / 'config/rhun/config').open('a', encoding='utf-8') as config:
            config.write('[ui]\nfollow_system=false\ntheme=rhun-light\n')
        shot = self.home / 'branch-picker-light.ppm'
        out = self.run_editor(['cmd git_switch_branch', 'wait-git', 'print-palette',
                               f'shot {shot}', 'key Escape'], size='1600x1000', scale='2')
        self.assertIn(branch, out)
        artifacts = os.environ.get('RHUN_TEST_ARTIFACT_DIR')
        if artifacts:
            from PIL import Image
            target = Path(artifacts)
            target.mkdir(parents=True, exist_ok=True)
            Image.open(shot).save(target / 'branch-picker-light.png')

    def test_empty_repository_has_empty_branch_list(self):
        empty = self.home / 'empty'
        empty.mkdir()
        self.git('init', '-q', repo=empty)
        self.git('symbolic-ref', 'HEAD', 'refs/heads/main', repo=empty)
        out = self.run_editor(['cmd git_switch_branch', 'wait-git', 'print-palette',
                               'key Return', 'key Escape', 'print-palette'], projects=[empty])
        self.assertIn('choose=No local branches', out)
        self.assertIn('none', out)
        self.assertEqual(self.git('branch', repo=empty), '')

    @unittest.skipIf(os.name == 'nt', 'Uses a POSIX Git wrapper to delay the query')
    def test_cancel_during_loading_does_not_replace_another_palette(self):
        real_git = shutil.which('git')
        folder = self.home / 'bin'
        folder.mkdir()
        wrapper = folder / 'git'
        wrapper.write_text('#!/bin/sh\nfor arg; do\n'
                           '  if [ "$arg" = for-each-ref ]; then sleep 0.3; fi\n'
                           'done\nexec ' + shlex.quote(real_git) + ' "$@"\n', encoding='utf-8')
        wrapper.chmod(0o755)
        self.env['PATH'] = str(folder) + os.pathsep + self.env['PATH']
        out = self.run_editor(['cmd git_switch_branch', 'key Escape',
                               'cmd command_palette', 'type Settings', 'wait-git', 'print-palette'])
        self.assertIn('field=Settings', out)
        self.assertNotIn('choose=', out)
        self.assertEqual(self.git('symbolic-ref', '--short', 'HEAD').strip(), 'main')

    @unittest.skipIf(os.name == 'nt', 'Uses a POSIX Git wrapper to simulate a query failure')
    def test_query_error_closes_loading_list_and_reports_failure(self):
        real_git = shutil.which('git')
        folder = self.home / 'bin'
        folder.mkdir()
        wrapper = folder / 'git'
        wrapper.write_text('#!/bin/sh\nfor arg; do\n'
                           '  if [ "$arg" = for-each-ref ]; then\n'
                           '    echo "fatal: Branch list unavailable" >&2; exit 128\n'
                           '  fi\ndone\nexec ' + shlex.quote(real_git) + ' "$@"\n', encoding='utf-8')
        wrapper.chmod(0o755)
        self.env['PATH'] = str(folder) + os.pathsep + self.env['PATH']
        out = self.run_editor(['cmd git_switch_branch', 'wait-git', 'print-palette', 'print-scm'])
        self.assertIn('none', out)
        self.assertIn('error=Branch list unavailable', out)


if __name__ == '__main__':
    unittest.main()
