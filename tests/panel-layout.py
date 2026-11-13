#!/usr/bin/env python3
"""Shared Explore/Changes/Graph sidebar and movable terminal dock."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
EXE = Path(os.environ.get('RHUN_TEST_EXE', ROOT / 'build/rhun')).resolve()


class PanelLayout(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='rhun-panels-')
        self.home = Path(self.tmp.name)
        self.repo = self.home / 'repo'
        self.repo.mkdir()
        self.env = dict(os.environ, HOME=str(self.home),
                        XDG_CONFIG_HOME=str(self.home / 'config'),
                        XDG_STATE_HOME=str(self.home / 'state'), PS1='$ ')
        self.git('init', '-q', '-b', 'main')
        self.git('config', 'user.name', 'Test')
        self.git('config', 'user.email', 'test@example.invalid')
        self.file = self.repo / 'example.txt'
        self.file.write_text('first\nsecond\nthird\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'Initial sample')
        self.file.write_text('first\nchanged\nthird\n')
        self.config = self.home / 'config/rhun/config'
        self.config.parent.mkdir(parents=True)
        self.config.write_text('[ui]\nsidebar=false\nagents_panel=false\n'
                               '[updates]\ncheck=false\n[editor]\ncursor_blink=false\n'
                               '[files]\nrestore_session=false\nrestore_project=false\n'
                               '[terminal]\nshell=/bin/sh\nheight=260\nwidth=420\n')

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.repo), *args], env=self.env,
                              capture_output=True, text=True, check=True).stdout

    def run_editor(self, actions, size='1280x800', scale='1'):
        script = self.home / 'commands'
        script.write_text('\n'.join(['wait-git', *actions, 'quit', '']))
        r = subprocess.run([str(EXE), str(self.repo), str(self.file), '--headless',
                            size, '--scale', scale, '--script', str(script)],
                           env=self.env, capture_output=True, text=True, timeout=25)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def shot(self, name):
        return 'shot ' + str(self.home / (name + '.ppm'))

    def keep(self, *names):
        folder = os.environ.get('RHUN_TEST_ARTIFACT_DIR')
        if folder:
            from PIL import Image
            folder = Path(folder)
            folder.mkdir(parents=True, exist_ok=True)
            for name in names:
                Image.open(self.home / (name + '.ppm')).save(folder / (name + '.png'))

    def test_git_panel_keeps_editor_and_defaults_to_collapsed_timeline(self):
        out = self.run_editor(['cmd git_history', 'wait-git', 'print-tabs',
            'print-panels', self.shot('git-panel'), 'click 100 760', 'wait 50',
            'print-panels', self.shot('git-timeline'), 'cmd toggle_git_history',
            'print-panels', 'print-tabs', 'print-doc'])
        self.assertEqual(out.count('tabs=*example.txt'), 2, out)
        self.assertIn('git=1 timeline=0', out)
        self.assertIn('git=1 timeline=1', out)
        self.assertIn('git=0 timeline=1', out)
        self.assertIn('first\nchanged\nthird', out)
        self.keep('git-panel', 'git-timeline')

    def test_commit_message_and_commit_still_work_in_panel(self):
        out = self.run_editor(['cmd git_history', 'wait-git', 'key Return',
            'type Commit from panel', 'print-scm', 'key ctrl+Return', 'wait-git',
            'print-scm', 'print-tabs'])
        self.assertIn('Commit from panel', out)
        self.assertEqual(self.git('log', '-1', '--format=%s').strip(), 'Commit from panel')
        self.assertEqual(self.git('status', '--porcelain'), '')
        self.assertIn('tabs=*example.txt', out)

    def test_timeline_keyboard_navigation_and_commit_details(self):
        out = self.run_editor(['cmd git_history', 'wait-git',
            'cmd git_toggle_timeline', 'key Home', 'key Down', 'key Return',
            'wait-git', 'print-gitlog', 'key ctrl+a', 'key ctrl+shift+k',
            'key ctrl+x', 'key ctrl+z', 'print-state', self.shot('git-details'),
            'key Escape', 'key ctrl+End', 'type EDITOR_OK', 'print-doc'])
        self.assertIn('focus=71', out)
        self.assertIn('line=1 col=1 sel=0 dirty=0', out)
        self.assertIn('Initial sample', out)
        self.assertIn('A example.txt', out)
        self.assertIn('EDITOR_OK', out)
        self.keep('git-details')

    def test_timeline_file_opens_historical_diff(self):
        out = self.run_editor(['cmd git_history', 'wait-git',
            'cmd git_toggle_timeline', 'key Down', 'key Return', 'wait-git',
            'click 80 618', 'wait-git', 'print-tabs', 'print-doc'])
        self.assertIn('example.txt (', out)
        self.assertIn('first', out)
        self.assertIn('second', out)

    def timeline_only(self):
        return ['cmd git_history', 'wait-git', 'click 30 54',
                'cmd toggle_git_history', 'cmd git_toggle_timeline', 'wait-git']

    def hover_tip(self, x, y):
        return ['move 600 400', 'wait 60', f'move {x} {y}',
                'wait 650', 'print-tip']

    def add_timeline_commit(self, path='src/nested/feature.go', message='Feature sample'):
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('package example\n')
        self.git('add', path)
        self.git('commit', '-qm', message)
        return target

    def test_timeline_click_expands_in_place_and_click_again_collapses(self):
        out = self.run_editor([*self.timeline_only(), 'click 80 160', 'wait-git',
            self.shot('timeline-expanded'), *self.hover_tip(80, 184),
            'click 80 160', 'wait-git', self.shot('timeline-collapsed'),
            *self.hover_tip(80, 184), 'print-tabs', 'print-state'])
        tips = [line for line in out.splitlines() if line.startswith('tip=')]
        self.assertEqual(tips, ['tip=example.txt', 'tip='], out)
        self.assertIn('tabs=*example.txt', out)
        self.assertIn('line=1 col=1 sel=0 dirty=0', out)
        from PIL import Image, ImageChops
        a = Image.open(self.home / 'timeline-expanded.ppm')
        b = Image.open(self.home / 'timeline-collapsed.ppm')
        self.assertIsNotNone(ImageChops.difference(a, b).crop((30, 172, 230, 196)).getbbox())
        self.keep('timeline-expanded', 'timeline-collapsed')

    def test_timeline_labels_follow_local_branch_width_and_expanded_files(self):
        # Stable dates/order, including a merge and a branch through only middle rows.
        fixture = self.home / 'merge-fixture'
        fixture.mkdir()
        subprocess.run(['sh', str(ROOT / 'tests/data/git.setup'),
                        str(fixture), str(self.home / 'fixture-state')],
                       env=self.env, capture_output=True, check=True)
        self.repo = fixture / 'repo'
        self.file = self.repo / 'a.txt'
        self.run_editor([*self.timeline_only(), self.shot('timeline-local-labels'),
            'key Down', 'key Return', 'wait-git',
            self.shot('timeline-local-labels-expanded')])
        from PIL import Image
        image = Image.open(self.home / 'timeline-local-labels.ppm').convert('RGB')
        def first_text_x(y):
            for x in range(17, 120):
                for py in range(y + 3, y + 21):
                    r, g, b = image.getpixel((x, py))
                    if min(r, g, b) > 130 and max(r, g, b) - min(r, g, b) < 20:
                        return x
            self.fail(f'No text found in commit row at {y}')
        # Work tree (lane 0) uses less indent than the merge and branch rows.
        self.assertLess(first_text_x(124), first_text_x(148))
        self.assertLess(first_text_x(244), first_text_x(196))
        self.keep('timeline-local-labels', 'timeline-local-labels-expanded')

    def test_timeline_multiple_nodes_expand_independently_and_keep_correct_files(self):
        self.add_timeline_commit()
        out = self.run_editor([*self.timeline_only(), 'click 80 160', 'wait-git',
            'click 80 208', 'wait-git', self.shot('timeline-multiple'),
            *self.hover_tip(80, 184), *self.hover_tip(80, 232),
            'click 80 160', 'wait-git', *self.hover_tip(80, 208),
            'click 80 208', 'wait-git', 'print-tabs', 'print-doc'])
        tips = [line for line in out.splitlines() if line.startswith('tip=')]
        self.assertEqual(tips, ['tip=src/nested/feature.go',
                               'tip=example.txt', 'tip=example.txt'], out)
        self.assertIn('example.txt (', out)
        self.assertIn('second', out)
        self.keep('timeline-multiple')

    def test_timeline_keyboard_disclosure_and_navigation_keep_document_unchanged(self):
        self.add_timeline_commit()
        out = self.run_editor([*self.timeline_only(), 'key Down', 'key Right',
            'wait-git', *self.hover_tip(80, 184), 'key Left',
            *self.hover_tip(80, 184), 'key space', 'wait-git',
            *self.hover_tip(80, 184), 'key Down', 'key Return', 'wait-git',
            *self.hover_tip(80, 232), 'key PageDown', 'key Home',
            'key End', 'print-state', 'print-doc'])
        tips = [line for line in out.splitlines() if line.startswith('tip=')]
        self.assertEqual(tips, ['tip=src/nested/feature.go', 'tip=Initial sample',
                               'tip=src/nested/feature.go', 'tip=example.txt'], out)
        self.assertIn('line=1 col=1 sel=0 dirty=0', out)
        self.assertIn('first\nchanged\nthird', out)

    def test_timeline_empty_commit_and_long_file_paths(self):
        path = 'src/very-long-directory/' + 'long-filename-' * 8 + '.go'
        self.add_timeline_commit(path, 'A long commit subject ' * 12)
        self.git('commit', '--allow-empty', '-qm', 'Empty sample')
        out = self.run_editor([*self.timeline_only(), 'click 80 160', 'wait-git',
            'click 80 208', 'wait-git', *self.hover_tip(80, 232),
            self.shot('timeline-long-path'), 'click 80 232', 'wait-git',
            'print-tabs', 'print-doc', 'print-state'])
        self.assertIn('tip=' + path, out)
        self.assertIn('package example', out)
        from PIL import Image, ImageChops
        a = Image.open(self.home / 'timeline-long-path.ppm')
        self.assertIsNotNone(ImageChops.difference(a.crop((48, 172, 228, 196)),
                           Image.new(a.mode, (180, 24), a.getpixel((239, 210)))).getbbox())
        self.keep('timeline-long-path')

    def test_timeline_scroll_reaches_file_beyond_viewport_and_reveals_next_node(self):
        for i in range(48):
            target = self.repo / f'src/file-{i:02}.txt'
            target.parent.mkdir(exist_ok=True)
            target.write_text(f'file {i}\n')
        self.git('add', 'src')
        self.git('commit', '-qm', 'Many files')
        out = self.run_editor([*self.timeline_only(), 'click 80 160', 'wait-git',
            'move 80 650', 'scroll 2000', 'wait 60',
            *self.hover_tip(80, 738), 'click 80 738', 'wait-git',
            'print-tabs', 'print-doc', 'click 80 762', 'key Home',
            'print-gitlog', 'print-state'])
        self.assertIn('tip=src/file-47.txt', out)
        self.assertIn('file-47.txt (', out)
        self.assertIn('file 47', out)
        self.assertIn('Uncommitted changes 1 <', out)
        self.assertIn('dirty=0', out)

    def test_timeline_expansion_survives_head_refresh_and_async_navigation(self):
        self.add_timeline_commit()
        out = self.run_editor([*self.timeline_only(), 'click 80 160',
            'key Down', 'key Return', 'key Up', 'wait-git',
            *self.hover_tip(80, 184), *self.hover_tip(80, 232),
            'cmd git_history', 'wait-git', *self.hover_tip(80, 510),
            'print-state'])
        tips = [line for line in out.splitlines() if line.startswith('tip=')]
        self.assertEqual(tips, ['tip=src/nested/feature.go', 'tip=example.txt',
                               'tip=src/nested/feature.go'], out)
        self.assertIn('line=1 col=1 sel=0 dirty=0', out)

    def test_timeline_pending_files_are_discarded_when_repository_changes(self):
        other = self.home / 'other-repo'
        other.mkdir()
        (other / 'other.txt').write_text('other repository\n')
        for args in (('init', '-q', '-b', 'main'), ('add', '.'),
                     ('-c', 'user.name=Other', '-c', 'user.email=other@example.invalid',
                      'commit', '-qm', 'Other repository')):
            subprocess.run(['git', '-C', str(other), *args], env=self.env,
                           capture_output=True, check=True)
        out = self.run_editor([f'folder-add {other}', 'wait-git',
            *self.timeline_only(), 'click 80 160', 'repo-show 1', 'wait-git',
            'cmd git_toggle_timeline', 'wait-git', 'click 80 160', 'wait-git',
            *self.hover_tip(80, 184), 'print-gitlog', 'repo-show 0', 'wait-git',
            'cmd git_toggle_timeline', 'wait-git', 'click 80 160', 'wait-git',
            *self.hover_tip(80, 184), 'print-state'])
        tips = [line for line in out.splitlines() if line.startswith('tip=')]
        self.assertEqual(tips, ['tip=other.txt', 'tip=example.txt'], out)
        self.assertIn('Other repository', out)
        self.assertIn('line=1 col=1 sel=0 dirty=0', out)

    def test_timeline_light_theme_and_large_scale(self):
        self.add_timeline_commit(message='A commit title that exceeds the narrow sidebar')
        with self.config.open('a') as config:
            config.write('[ui]\ntheme=rhun-light\nfont_size=24\nsidebar_width=180\n')
        out = self.run_editor(['cmd git_history', 'wait-git',
            'cmd git_toggle_timeline', 'key Down', 'key Right', 'wait-git',
            self.shot('timeline-light-large-font'), 'print-state',
            'resize 640 400', 'wait 60', 'key End', 'key Left',
            self.shot('timeline-scale-two'), 'print-state'], scale='2')
        self.assertEqual(out.count('line=1 col=1 sel=0 dirty=0'), 2, out)
        self.keep('timeline-light-large-font', 'timeline-scale-two')

    def test_history_header_collapses_without_hiding_explorer(self):
        out = self.run_editor(['cmd git_history', 'wait-git', 'click 30 407',
            'print-panels', 'print-tabs', 'print-doc'])
        self.assertIn('explorer=1 agents=0 term=0 git=0', out)
        self.assertIn('tabs=*example.txt', out)

    def test_three_blocks_default_states_and_independent_disclosures(self):
        out = self.run_editor(['cmd toggle_sidebar', 'wait 80', 'print-sidebar',
            self.shot('shared-sidebar-default'), 'click 30 732', 'wait 80',
            'print-sidebar', self.shot('shared-sidebar-history'),
            'click 30 760', 'wait 80', 'print-sidebar',
            self.shot('shared-sidebar-all'), 'click 30 54', 'wait 80',
            'print-sidebar', 'print-tabs'])
        blocks = [line for line in out.splitlines() if ' title=' in line]
        self.assertEqual([line.split(' title=')[0] for line in blocks],
                         ['explorer', 'git-history', 'timeline'] * 4)
        self.assertIn('collapsed', blocks[1])
        self.assertIn('collapsed', blocks[2])
        self.assertNotIn('collapsed', blocks[3])
        self.assertNotIn('collapsed', blocks[4])
        self.assertIn('collapsed', blocks[5])
        self.assertTrue(all('collapsed' not in line for line in blocks[6:9]))
        self.assertIn('collapsed', blocks[9])
        self.assertTrue(all('collapsed' not in line for line in blocks[10:12]))
        self.assertIn('tabs=*example.txt', out)
        self.keep('shared-sidebar-default', 'shared-sidebar-history', 'shared-sidebar-all')

    def test_hidden_sidebar_and_collapsed_history_stop_message_input(self):
        out = self.run_editor(['cmd git_history', 'wait-git', 'key Return', 'type Draft',
            'click 30 407', 'type x', 'print-scm', 'print-state',
            'cmd git_history', 'wait-git', 'key Return', 'type Still here',
            'cmd toggle_sidebar', 'type y', 'print-scm', 'print-tabs'])
        self.assertIn('message=Draft', out)
        self.assertNotIn('Draftx', out)
        self.assertNotIn('Still herey', out)

    def test_narrow_sidebar_and_large_ui_font_do_not_edit_document(self):
        with self.config.open('a') as config:
            config.write('[ui]\nfont_size=24\nsidebar_width=160\n')
        out = self.run_editor(['cmd git_history', 'cmd git_toggle_timeline',
            'key Down', 'key Return', 'wait-git', self.shot('shared-sidebar-large-font'),
            'resize 700 450', 'wait 50', 'print-state', 'print-sidebar'])
        self.assertIn('line=1 col=1 sel=0 dirty=0', out)
        self.assertIn('title=Changes', out)
        self.assertIn('title=Graph', out)
        self.keep('shared-sidebar-large-font')

    def test_compact_git_actions_expose_their_commands(self):
        actions = ['cmd git_history', 'wait-git', 'click 30 54', 'wait 60']
        for x in (34, 90, 145, 200):
            actions += ['move 600 400', 'wait 60', f'move {x} 232',
                        'wait 650', 'print-tip']
        out = self.run_editor(actions)
        for command in ('git -c pull.rebase=false pull --no-edit', 'git push',
                        'git fetch', 'git reset --hard -q && git clean -f -d -q'):
            self.assertIn('tip=' + command, out)

    def test_commit_subject_tooltip_and_removed_titlebar_git_button(self):
        out = self.run_editor(['cmd git_toggle_timeline', 'wait-git',
            'print-panels', 'move 80 496', 'wait 650', 'print-tip',
            'move 600 400', 'wait 60', 'move 968 20', 'wait 650', 'print-tip'])
        self.assertIn('tip=Initial sample', out)
        self.assertIn('explorer=1 agents=0 term=0 git=0 timeline=1', out)
        self.assertTrue(out.endswith('tip=\n'), out)

    def test_terminal_button_moves_dock_and_keeps_shell(self):
        out = self.run_editor(['cmd new_terminal', 'wait 200',
            'type echo DOCK_READY', 'key Return', 'wait-term DOCK_READY',
            'click 1232 528', 'wait 50', 'print-panels', 'print-terminals',
            'print-term', self.shot('terminal-right'),
            'click 1232 54', 'wait 50', 'print-panels', 'print-terminals',
            self.shot('terminal-bottom')])
        self.assertIn('terminal_position=1', out)
        self.assertIn('terminal_position=0', out)
        self.assertEqual(out.count('kind=shell'), 2, out)
        self.assertIn('DOCK_READY', out)
        self.assertIn('position = bottom', self.config.read_text())
        self.keep('terminal-right', 'terminal-bottom')

    def test_right_dock_drag_and_persistence(self):
        out = self.run_editor(['cmd new_terminal', 'cmd terminal_move_right',
            'wait 100', 'move 859 400', 'down', 'move 759 400', 'wait 50',
            'up', 'print-state', 'print-panels'])
        self.assertIn('line=1 col=1 sel=0 dirty=0', out)
        self.assertIn('terminal_position=1', out)
        config = self.config.read_text()
        self.assertIn('position = right', config)
        self.assertRegex(config, r'(?m)^width = 52[01]$')
        out = self.run_editor(['cmd new_terminal', 'print-panels'])
        self.assertIn('terminal_position=1', out)

    def test_terminal_splits_keep_sessions_when_dock_moves(self):
        out = self.run_editor(['cmd new_terminal', 'wait 100', 'type echo LEFT',
            'key Return', 'wait-term LEFT', 'cmd split_terminal_down', 'wait 100',
            'type echo RIGHT', 'key Return', 'wait-term RIGHT',
            'cmd terminal_move_right', 'print-term', 'cmd next_terminal_pane',
            'print-term', 'cmd terminal_move_bottom', 'print-terminals',
            'print-state', 'print-panels'])
        self.assertIn('LEFT', out)
        self.assertIn('RIGHT', out)
        self.assertEqual(out.count('kind=shell'), 2, out)
        self.assertIn('terminal_position=0', out)
        self.assertIn('line=1 col=1 sel=0 dirty=0', out)

    def test_right_dock_survives_narrow_window_and_large_scale(self):
        out = self.run_editor(['cmd new_terminal', 'cmd terminal_move_right',
            'cmd split_terminal_down', 'resize 500 360', 'wait 100',
            'print-state', 'print-panels', 'cmd terminal_move_bottom',
            'resize 320 240', 'wait 100', 'print-panels'], scale='2')
        self.assertIn('terminal_position=1', out)
        self.assertIn('terminal_position=0', out)
        self.assertIn('line=1 col=1 sel=0 dirty=0', out)

    def test_command_palette_remains_safe_with_all_builtin_commands(self):
        out = self.run_editor(['cmd command_palette', 'type Terminal: Move Panel to Right',
            'key Return', 'cmd new_terminal', 'print-panels',
            'cmd command_palette', 'key Escape', 'print-state'])
        self.assertIn('terminal_position=1', out)
        self.assertIn('line=1 col=1 sel=0 dirty=0', out)

    def test_position_is_searchable_in_settings(self):
        out = self.run_editor(['cmd settings', 'type terminal position', 'print-settings'])
        self.assertIn('terminal.position', out)


if __name__ == '__main__':
    unittest.main(verbosity=2)
