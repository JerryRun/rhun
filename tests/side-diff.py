#!/usr/bin/env python3
"""Editable aligned comparison: real git base, deletions, additions, map, and saving."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
EXE = Path(os.environ.get('RHUN_TEST_EXE', ROOT / 'build/rhun')).resolve()
NL = chr(10)


class SideDiff(unittest.TestCase):
    def test_baseline_tabs_render_like_equivalent_spaces(self):
        with tempfile.TemporaryDirectory(prefix='rhun-side-tabs-') as tmp:
            p = Path(tmp)
            repo = p / 'repo'
            repo.mkdir()
            def git(*args):
                subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True)
            git('init', '-q', '-b', 'main')
            git('config', 'user.name', 'Test')
            git('config', 'user.email', 'test@example.invalid')
            source = repo / 'sample.txt'
            config = p / 'config/rhun/config'
            config.parent.mkdir(parents=True)
            env = dict(os.environ, HOME=tmp, XDG_CONFIG_HOME=str(p/'config'),
                       XDG_STATE_HOME=str(p/'state'))
            # Leading, nested and inline tabs, including one after a wide Unicode character.
            rows = ['anchor', '\treturn value', '\t\tnested', ' \tspaced',
                    'abc\tvalue\tend', 'é\taccent', '界\twide',
                    'a' * 100 + '\tlong tail', 'old', '']
            for width in (2, 4, 8):
                with self.subTest(tab_width=width):
                    config.write_text(NL.join(['[ui]', 'sidebar=false', 'agents_panel=false',
                        '[editor]', f'tab_width={width}', 'whitespace=false', 'indent_guides=false',
                        'cursor_blink=false', '[files]', 'restore_session=false',
                        '[updates]', 'check=false', '']), encoding='utf-8')
                    images = []
                    scrolled = []
                    for name in ('tabs', 'spaces'):
                        baseline = []
                        for row in rows:
                            expanded, col = '', 0
                            for char in row:
                                if char == '\t':
                                    count = width - col % width
                                    expanded += ' ' * count
                                    col += count
                                else:
                                    expanded += char
                                    col += 2 if char == '界' else 1
                            baseline.append(row if name == 'tabs' else expanded)
                        source.write_text(NL.join(baseline), encoding='utf-8')
                        git('add', '.')
                        git('commit', '--allow-empty', '-qm', f'{name}-{width}')
                        baseline[-2] = 'new'
                        source.write_text(NL.join(baseline), encoding='utf-8')
                        shot = p / f'{name}-{width}.ppm'
                        scroll_shot = p / f'{name}-{width}-scrolled.ppm'
                        script = p / 'commands'
                        script.write_text(NL.join(['wait-git', 'wait 300', 'cmd git_changes',
                            'wait-git', 'wait 100', f'shot {shot}',
                            'key ctrl+End', 'key Up', 'key Up', 'key End', 'wait 60',
                            f'shot {scroll_shot}', 'quit', '']), encoding='utf-8')
                        result = subprocess.run([str(EXE), str(repo), str(source), '--headless',
                            '1200x800', '--scale', '1', '--script', str(script)], env=env,
                            capture_output=True, text=True, encoding='utf-8', timeout=20)
                        self.assertEqual(result.returncode, 0, result.stderr)
                        with Image.open(shot) as image:
                            images.append(image.crop((0, 100, 590, 500)).tobytes())
                            if os.environ.get('RHUN_TEST_ARTIFACT_DIR'):
                                artifacts = Path(os.environ['RHUN_TEST_ARTIFACT_DIR'])
                                artifacts.mkdir(parents=True, exist_ok=True)
                                image.save(artifacts / f'baseline-{name}-{width}.png')
                        with Image.open(scroll_shot) as image:
                            scrolled.append(image.crop((0, 100, 590, 500)).tobytes())
                    self.assertEqual(images[0], images[1],
                                     'HEAD tabs must occupy the same cells as expanded spaces')
                    self.assertEqual(scrolled[0], scrolled[1],
                                     'Horizontal scrolling must preserve tab stop alignment')
                    self.assertNotEqual(images[0], scrolled[0],
                                        'The long-line case must actually scroll horizontally')

    def test_edit_and_toggle(self):
        with tempfile.TemporaryDirectory(prefix='rhun-side-') as tmp:
            p = Path(tmp)
            repo = p / 'repo'
            repo.mkdir()
            def git(*args):
                subprocess.run(['git', '-C', str(repo), *args], check=True,
                               capture_output=True)
            git('init', '-q', '-b', 'main')
            git('config', 'user.name', 'Test')
            git('config', 'user.email', 'test@example.invalid')
            f = repo / 'sample.txt'
            f.write_text(NL.join(['alpha', 'delete one', 'delete two', 'beta',
                                  'old value', 'gamma', 'last', '']))
            git('add', '.')
            git('commit', '-qm', 'base')
            working = NL.join(['alpha', 'beta', 'new value', 'extra new',
                               'gamma', 'last', ''])
            f.write_text(working)
            config = p / 'config/rhun/config'
            config.parent.mkdir(parents=True)
            config.write_text(NL.join(['[ui]', 'sidebar=false', 'agents_panel=false',
                '[files]', 'restore_session=false', '[updates]', 'check=false', '']))
            script = p / 'script'
            script.write_text(NL.join(['wait-git', 'wait 300',
                'shot ' + str(p/'normal.ppm'),
                'cmd toggle_git_history', 'click 30 54', 'wait 100', 'click 80 302',
                'cmd toggle_git_history', 'cmd toggle_sidebar',
                'wait-git', 'wait 100', 'print-state',
                'shot ' + str(p/'diff.ppm'), 'click 740 200', 'type TEST',
                'print-doc', 'print-state',
                # Click the real Explorer row: reuse the live buffer, leave comparison mode.
                'cmd toggle_sidebar', 'cmd focus_explorer', 'click 50 82', 'cmd toggle_sidebar',
                'wait 100', 'print-state', 'print-doc',
                'shot ' + str(p/'reopened.ppm'),
                'cmd save', 'cmd toggle_side_diff', 'print-doc', 'quit', '']))
            env = dict(os.environ, HOME=tmp, XDG_CONFIG_HOME=str(p/'config'),
                       XDG_STATE_HOME=str(p/'state'))
            result = subprocess.run([str(EXE), str(repo), str(f),
                '--headless', '1200x800', '--scale', '1', '--script', str(script)],
                env=env, capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('TEST', result.stdout)
            self.assertNotIn('delete one', f.read_text())
            self.assertEqual(f.read_text().replace('TEST', ''), working)
            self.assertEqual(result.stdout.count('tabs=1 active=sample.txt'), 3, result.stdout)
            self.assertNotIn('sample.txt (changes)', result.stdout)
            # The central full-height rule is specific to the side-by-side comparison.
            diff = Image.open(p/'diff.ppm')
            normal = Image.open(p/'normal.ppm')
            reopened = Image.open(p/'reopened.ppm')
            self.assertNotEqual(diff.getpixel((593, 600)), normal.getpixel((593, 600)))
            self.assertEqual(normal.getpixel((593, 600)), reopened.getpixel((593, 600)))
            if os.environ.get('RHUN_TEST_ARTIFACT_DIR'):
                artifacts = Path(os.environ['RHUN_TEST_ARTIFACT_DIR'])
                artifacts.mkdir(parents=True, exist_ok=True)
                for name in ('normal', 'diff', 'reopened'):
                    Image.open(p/(name + '.ppm')).save(artifacts/('file-' + name + '.png'))


if __name__ == '__main__':
    unittest.main()
