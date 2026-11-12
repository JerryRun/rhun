#!/usr/bin/env python3
"""Bounded async IME helper: editor, terminal, cancellation and changed target."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
NL = chr(10)


class WslInput(unittest.TestCase):
    def run_case(self, commands, output='中文输入测试', delay=0.05, status=0):
        with tempfile.TemporaryDirectory(prefix='rhun-ime-') as tmp:
            p = Path(tmp)
            helper = p / 'helper'
            helper.write_text(NL.join(['#!/usr/bin/env python3',
                'import sys,time', 'time.sleep('+str(delay)+')',
                'sys.stdout.write('+repr(output)+')', 'sys.exit('+str(status)+')', '']))
            helper.chmod(0o755)
            config = p / 'config/rhun/config'
            config.parent.mkdir(parents=True)
            config.write_text(NL.join(['[ui]', 'sidebar=false', 'agents_panel=false',
                '[git]', 'enabled=false', '[updates]', 'check=false', '[files]',
                'restore_session=false', '[terminal]', 'shell=/bin/sh', '']))
            script = p / 'script'
            script.write_text(NL.join([*commands, 'quit', '']))
            env = dict(os.environ, HOME=tmp, XDG_CONFIG_HOME=str(p/'config'),
                       XDG_STATE_HOME=str(p/'state'), RHUN_WSL_INPUT_HELPER=str(helper))
            r = subprocess.run([str(ROOT/'build/rhun'), tmp, '--headless', '1100x800',
                '--scale', '1', '--script', str(script)], env=env, capture_output=True,
                text=True, timeout=15)
            self.assertEqual(r.returncode, 0, r.stderr)
            return r.stdout

    def test_editor(self):
        out = self.run_case(['cmd new_file', 'cmd input_chinese', 'wait 600', 'print-doc'])
        self.assertIn('中文输入测试', out)

    def test_terminal(self):
        out = self.run_case(['cmd new_terminal', 'wait 200', 'cmd input_chinese',
            'wait 500', 'key Return', 'wait 200', 'print-term'], output='echo 中文终端')
        self.assertIn('中文终端', out)

    def test_cancel(self):
        out = self.run_case(['cmd new_file', 'cmd input_chinese', 'wait 500', 'print-doc'], output='')
        self.assertEqual(out.strip(), '<eod>')

    def test_changed_document_is_not_written(self):
        out = self.run_case(['cmd new_file', 'cmd input_chinese', 'cmd new_file',
            'wait 800', 'print-doc'], delay=0.2)
        self.assertNotIn('中文输入测试', out)

    def test_failed_worker_is_not_written(self):
        out = self.run_case(['cmd new_file', 'cmd input_chinese', 'wait 600',
            'print-doc'], status=1)
        self.assertNotIn('中文输入测试', out)


if __name__ == '__main__':
    unittest.main()
