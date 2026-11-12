#!/usr/bin/env python3
"""scroll_sensitivity scales every scroll delta; fast_scroll_sensitivity applies
while alt is held (issue #47)."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
EXE = Path(os.environ.get('RHUN_TEST_EXE', ROOT / 'build/rhun')).resolve()

CONFIG = ('[ui]\nsidebar = true\nsidebar_width = 240\nagents_panel = false\n{extra}'
          '[editor]\ncursor_blink = false\n'
          '[files]\nrestore_session = false\nrestore_project = false\n'
          '[updates]\ncheck = false\n[git]\nenabled = false\n')


class ScrollSensitivity(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='rhun-scroll-')
        self.work = Path(self.tmp.name).resolve()
        self.proj = self.work / 'proj'
        self.proj.mkdir()
        self.file = self.proj / 'words.txt'
        self.file.write_text('\n'.join('word%d some text to scroll over' % i
                                       for i in range(200)), encoding='utf-8')
        self.config = self.work / 'config/rhun/config'
        self.config.parent.mkdir(parents=True)
        self.env = dict(os.environ, HOME=self.work.as_posix(),
                        XDG_CONFIG_HOME=(self.work / 'config').as_posix(),
                        XDG_STATE_HOME=(self.work / 'state').as_posix())

    def tearDown(self):
        self.tmp.cleanup()

    def run_editor(self, actions):
        script = self.work / 'actions.rsc'
        script.write_text('\n'.join([*actions, 'quit']) + '\n', encoding='utf-8')
        result = subprocess.run([str(EXE), self.proj.as_posix(), self.file.as_posix(),
                                 '--headless', '1000x700', '--scale', '1',
                                 '--script', script.as_posix()],
                                env=self.env, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        return result.stdout.decode('utf-8')

    def scroll_offset(self, scroll_cmd, extra='', editor_extra=''):
        self.config.write_text(CONFIG.format(extra=extra) + '[editor]\n' + editor_extra,
                               encoding='utf-8')
        commands = scroll_cmd if isinstance(scroll_cmd, list) else [scroll_cmd]
        out = self.run_editor(['wait 200', 'move 500 400', *commands, 'wait 60', 'print-scroll'])
        return int(dict(part.split('=') for part in out.split())['y'])

    def test_default_scrolls(self):
        self.assertGreater(self.scroll_offset('scroll 600'), 0)

    def test_editor_default_is_half_previous_speed(self):
        default = self.scroll_offset('scroll 600')
        previous = self.scroll_offset('scroll 600', editor_extra='scroll_sensitivity=1\n')
        self.assertAlmostEqual(default/previous, .5, delta=.02)

    def test_editor_sensitivity_changes_independently(self):
        base = self.scroll_offset('scroll 600')
        slower = self.scroll_offset('scroll 600', editor_extra='scroll_sensitivity=0.2\n')
        self.assertAlmostEqual(slower/base, .4, delta=.02)

    def test_editor_small_steps_add_up(self):
        small = self.scroll_offset(['scroll 1'] * 120)
        combined = self.scroll_offset('scroll 120')
        self.assertAlmostEqual(small/combined, 1, delta=.05)

    def test_wrapped_editor_uses_same_smaller_step(self):
        # Wrapped print-scroll reports whole source lines, so use a delta large enough that
        # line rounding does not obscure the multiplier.
        default = self.scroll_offset('scroll 600', editor_extra='word_wrap=true\n')
        previous = self.scroll_offset('scroll 600',
            editor_extra='word_wrap=true\nscroll_sensitivity=1\n')
        self.assertAlmostEqual(default/previous, .5, delta=.05)

    def test_reverse_steps_return_to_start(self):
        offset = self.scroll_offset(['scroll 1']*120 + ['scroll -1']*120)
        self.assertEqual(offset, 0)

    def test_sensitivity_scales_the_delta(self):
        base = self.scroll_offset('scroll 600')
        triple = self.scroll_offset('scroll 600', 'scroll_sensitivity = 3\n')
        self.assertAlmostEqual(triple / base, 3, delta=0.05)

    def test_alt_uses_fast_sensitivity(self):
        base = self.scroll_offset('scroll 600')
        fast = self.scroll_offset('scroll 600 alt')
        self.assertAlmostEqual(fast / base, 4, delta=0.05)

    def test_fast_sensitivity_is_configurable(self):
        # a small delta keeps the 8x result inside the document's scroll range
        base = self.scroll_offset('scroll 100')
        fast = self.scroll_offset('scroll 100 alt', 'fast_scroll_sensitivity = 8\n')
        self.assertAlmostEqual(fast / base, 8, delta=0.05)

    def test_sensitivity_below_one_slows_down(self):
        base = self.scroll_offset('scroll 600')
        slow = self.scroll_offset('scroll 600', 'scroll_sensitivity = 0.5\n')
        self.assertAlmostEqual(slow / base, 0.5, delta=0.05)

    def test_small_steps_add_up(self):
        # a trackpad's one-pixel steps: at 0.5 every other one scrolls a pixel instead of none
        base = self.scroll_offset(['scroll 1'] * 120)
        slow = self.scroll_offset(['scroll 1'] * 120, 'scroll_sensitivity = 0.5\n')
        fast = self.scroll_offset(['scroll 1'] * 120, 'scroll_sensitivity = 1.5\n')
        self.assertGreater(base, 0)
        self.assertAlmostEqual(slow / base, 0.5, delta=0.05)
        self.assertAlmostEqual(fast / base, 1.5, delta=0.05)


if __name__ == '__main__':
    unittest.main()
