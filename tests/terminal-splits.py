#!/usr/bin/env python3
"""Real independent PTYs, split geometry, focus, nested panes, and close/merge."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


class TerminalSplits(unittest.TestCase):
    def test_split_focus_resize_and_close(self):
        with tempfile.TemporaryDirectory(prefix='rhun-splits-') as t:
            home = Path(t)
            folder = home / '目录 with space'
            folder.mkdir()
            config = home / 'config/rhun/config'
            config.parent.mkdir(parents=True)
            config.write_text(chr(10).join(['[ui]', 'sidebar=false', 'agents_panel=false',
                '[git]', 'enabled=false', '[updates]', 'check=false', '[terminal]',
                'shell=/bin/sh', 'height=400', '']))
            env = dict(os.environ, HOME=t, XDG_CONFIG_HOME=str(home/'config'),
                       XDG_STATE_HOME=str(home/'state'), PS1='$ ')
            commands = ['cmd new_terminal', 'wait 200', 'type echo LEFT', 'key Return',
                'wait 200', 'cmd split_terminal_right', 'wait 200', 'type echo RIGHT',
                'key Return', 'wait 200', 'print-term', 'echo TITLES_BEFORE',
                'print-terminals', 'type cd "' + str(folder) + '"', 'key Return',
                'wait 650', 'print-terminals', 'echo FOCUS_LEFT',
                'cmd next_terminal_pane', 'print-term', 'echo NESTED',
                'cmd split_terminal_down', 'wait 200', 'type echo BOTTOM', 'key Return',
                'wait 200', 'print-term', 'print-terminals', 'resize 800 700',
                'wait 100', 'shot '+str(home/'split.ppm'),
                'click 600 550', 'type echo CLICK_RIGHT', 'key Return',
                'wait 200', 'echo CLICKED', 'print-term', 'cmd kill_terminal',
                'wait 200', 'print-terminals', 'cmd unsplit_terminal', 'wait 50', 'quit']
            script = home/'script'
            script.write_text(chr(10).join(commands)+chr(10))
            r = subprocess.run([str(ROOT/'build/rhun'), t, '--headless', '1200x800',
                '--scale', '1', '--script', str(script)], env=env, capture_output=True,
                text=True, timeout=20)
            self.assertEqual(r.returncode, 0, r.stderr)
            right, rest = r.stdout.split('FOCUS_LEFT', 1)
            left, bottom = rest.split('NESTED', 1)
            self.assertIn('RIGHT', right)
            self.assertNotIn('LEFT', right)
            self.assertIn('title=sh+' + home.name, right)
            self.assertIn('title=sh+目录 with space', right)
            self.assertIn('LEFT', left)
            self.assertNotIn('RIGHT', left)
            self.assertIn('BOTTOM', bottom)
            self.assertEqual(bottom.count('kind=shell'), 5)
            self.assertIn('CLICK_RIGHT', bottom.split('CLICKED', 1)[1])
            shot = Image.open(home/'split.ppm')
            accent = shot.getpixel((400, 300))  # selected tab's underline remains
            self.assertNotEqual(accent, shot.getpixel((50, 672)))
            self.assertEqual(shot.getpixel((50, 672)), shot.getpixel((50, 600)))
            self.assertEqual(shot.getpixel((398, 600)), shot.getpixel((400, 600)))
            self.assertNotEqual(shot.getpixel((399, 600)), shot.getpixel((400, 600)))
            self.assertEqual(shot.getpixel((200, 487)), shot.getpixel((200, 489)))
            self.assertNotEqual(shot.getpixel((200, 488)), shot.getpixel((200, 489)))
            self.assertTrue((home/'split.ppm').stat().st_size > 1000)
            if os.environ.get('RHUN_TEST_ARTIFACT_DIR'):
                artifacts = Path(os.environ['RHUN_TEST_ARTIFACT_DIR'])
                artifacts.mkdir(parents=True, exist_ok=True)
                Image.open(home/'split.ppm').save(artifacts/'terminal-splits.png')


if __name__ == '__main__':
    unittest.main()
