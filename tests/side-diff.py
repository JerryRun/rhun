#!/usr/bin/env python3
"""Editable aligned comparison: real git base, deletions, additions, map, and saving."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
NL = chr(10)


class SideDiff(unittest.TestCase):
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
            result = subprocess.run([str(ROOT/'build/rhun'), str(repo), str(f),
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
