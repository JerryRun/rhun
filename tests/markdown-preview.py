#!/usr/bin/env python3
"""Native Markdown previews: real context menus, live unsaved source, tabs and focus."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
EXE = Path(os.environ.get('RHUN_TEST_EXE', ROOT/'build/rhun'))


class MarkdownPreview(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='rhun-md-preview-')
        self.work = Path(self.tmp.name)
        self.project = self.work/'project'
        self.project.mkdir()
        self.file = self.project/'README.md'
        self.original = '# Heading\n\nHello **world**.\n'
        self.file.write_text(self.original)
        self.other = self.project/'other.txt'
        self.other.write_text('plain text\n')
        config = self.work/'config/rhun/config'
        config.parent.mkdir(parents=True)
        config.write_text('[ui]\nsidebar=false\nagents_panel=false\n'
                          '[updates]\ncheck=false\n[git]\nenabled=false\n'
                          '[editor]\ncursor_blink=false\n'
                          '[files]\nrestore_session=false\nrestore_project=false\n')
        self.env = dict(os.environ, HOME=str(self.work),
                        XDG_CONFIG_HOME=str(self.work/'config'),
                        XDG_STATE_HOME=str(self.work/'state'))

    def tearDown(self):
        self.tmp.cleanup()

    def run_editor(self, actions, file=None):
        script = self.work/'script'
        script.write_text('\n'.join(['wait 50', *actions, 'quit', '']))
        result = subprocess.run([str(EXE), str(self.project), str(file or self.file),
            '--headless', '1200x800', '--scale', '1', '--script', str(script)],
            env=self.env, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_context_menu_and_live_source(self):
        out = self.run_editor(['click 300 170 right', 'print-menu',
            'menu-pick Open Preview to the Side',
            'print-state', 'key ctrl+End', 'type UNSAVED', 'wait 50',
            'print-state', 'print-md-preview', 'echo DOC', 'print-doc',
            'shot ' + str(self.work/'side.ppm'),
            'cmd markdown_preview_side', 'print-tabs'])
        self.assertIn('Open Preview\nOpen Preview to the Side', out)
        self.assertIn('item text', out)
        self.assertIn('UNSAVED', out.split('DOC')[0])
        self.assertIn('UNSAVED', out.split('DOC')[1])
        self.assertIn('dirty=1', out)
        self.assertEqual(self.file.read_text(), self.original)
        self.keep_artifact('side')

    def test_preview_is_separate_readonly_and_reused(self):
        out = self.run_editor(['cmd markdown_preview', 'print-tabs', 'print-state',
            'type MUST_NOT_EDIT', 'print-md-preview', 'cmd close_tab', 'print-doc',
            'cmd markdown_preview', 'open ' + str(self.file), 'key ctrl+End',
            'type UPDATED', 'cmd markdown_preview', 'print-tabs', 'print-md-preview',
            'shot ' + str(self.work/'tab.ppm')])
        self.assertIn('README.md (Preview)', out)
        self.assertIn('tabs=2 focus=70', out)
        self.assertNotIn('MUST_NOT_EDIT', out)
        self.assertIn('UPDATED', out)
        self.assertEqual(self.file.read_text(), self.original)
        self.keep_artifact('tab')

    def test_explorer_menu_targets_inactive_markdown(self):
        out = self.run_editor(['cmd toggle_sidebar', 'wait 100', 'click 50 122 right',
            'print-menu', 'menu-pick Open Preview', 'print-tabs', 'print-md-preview'], file=self.other)
        self.assertIn('Open Preview\nOpen Preview to the Side', out)
        self.assertIn('README.md (Preview)', out)
        self.assertIn('Heading', out)
        self.assertIn('other.txt', out)

    def test_non_markdown_has_no_preview_actions(self):
        out = self.run_editor(['click 300 170 right', 'print-menu'], file=self.other)
        self.assertNotIn('Open Preview', out)

    def test_preview_focus_does_not_edit_source(self):
        out = self.run_editor(['cmd markdown_preview_side', 'click 900 200',
            'type MUST_NOT_EDIT', 'key ctrl+a', 'key ctrl+c', 'key Escape',
            'key ctrl+End', 'type SOURCE_OK', 'print-doc', 'print-md-preview'])
        self.assertNotIn('MUST_NOT_EDIT', out)
        self.assertIn('SOURCE_OK', out)
        self.assertEqual(self.file.read_text(), self.original)

    def test_preview_edit_commands_do_not_change_source(self):
        out = self.run_editor(['cmd markdown_preview_side', 'key ctrl+End',
            'type KEEP_ME', 'click 900 200', 'key ctrl+z', 'key ctrl+shift+k',
            'key ctrl+Enter', 'key ctrl+]', 'key ctrl+v',
            'key ctrl+shift+p', 'type Markdown: Close Side Preview', 'key Return',
            'print-state', 'print-doc', 'type SOURCE_OK', 'print-doc'])
        self.assertIn('KEEP_ME', out)
        self.assertIn('focus=0', out)
        self.assertIn('SOURCE_OK', out)

    def test_side_preview_close_button(self):
        out = self.run_editor(['cmd markdown_preview_side', 'click 1186 94',
            'print-state', 'click 900 200', 'print-state', 'type SOURCE_OK', 'print-doc'])
        self.assertNotIn('focus=70', out)
        self.assertIn('SOURCE_OK', out)

    def test_markdown_folder_has_no_preview_actions(self):
        (self.project/'folder.md').mkdir()
        out = self.run_editor(['cmd toggle_sidebar', 'wait 100',
            'click 50 94 right', 'print-menu'])
        self.assertNotIn('Open Preview', out)

    def test_tab_context_menu_and_uppercase_extension(self):
        path = self.project/'GUIDE.MARKDOWN'
        path.write_text('# Uppercase\n')
        out = self.run_editor(['click 50 58 right', 'print-menu',
            'menu-pick Open Preview', 'print-tabs', 'print-md-preview'], file=path)
        self.assertIn('Open Preview\nOpen Preview to the Side', out)
        self.assertIn('GUIDE.MARKDOWN (Preview)', out)
        self.assertIn('text=Uppercase', out)

    def test_oversized_document_reports_limit(self):
        self.file.write_text('a' * 1048577)
        out = self.run_editor(['cmd markdown_preview', 'print-tabs', 'print-toast'])
        self.assertIn('up to 1 MiB', out)
        self.assertNotIn('(Preview)', out)

    def test_unhandled_link_is_safe_without_extension(self):
        self.file.write_text('[custom](custom:thing)\n')
        out = self.run_editor(['cmd markdown_preview', 'key Tab', 'key Return',
            'print-tabs', 'print-md-preview'])
        self.assertIn('README.md (Preview)', out)
        self.assertIn('text=custom', out)

    def test_relative_link_opens_file(self):
        self.file.write_text('[local](other.txt)\n')
        out = self.run_editor(['cmd markdown_preview', 'key Tab', 'key Return',
            'print-state', 'print-doc'])
        self.assertIn('active=other.txt', out)
        self.assertIn('plain text', out)

    def test_source_closed_keeps_preview_safe(self):
        out = self.run_editor(['cmd markdown_preview', 'click 50 58',
            'cmd close_tab', 'print-md-preview', 'type NO_EDIT',
            'key PageDown', 'cmd close_tab', 'cmd new_file', 'print-state'])
        self.assertIn('Heading', out)
        self.assertNotIn('NO_EDIT', out)
        self.assertIn('tabs=1 active=untitled', out)

    def test_preview_scroll_and_resize(self):
        self.file.write_text('\n\n'.join('# Heading ' + str(i) for i in range(80)))
        out = self.run_editor(['cmd markdown_preview', 'key End', 'print-md-preview',
            'resize 480 500', 'key Home', 'print-md-preview',
            'open ' + str(self.file), 'cmd markdown_preview_side', 'resize 360 500',
            'print-md-preview', 'shot ' + str(self.work/'narrow.ppm')])
        scrolls = [int(line.split('scroll=')[1].split()[0]) for line in out.splitlines()
                   if line.startswith('doc scroll=')]
        self.assertGreater(scrolls[0], 0)
        self.assertEqual(scrolls[1], 0)
        self.keep_artifact('narrow')

    def keep_artifact(self, name):
        if os.environ.get('RHUN_TEST_ARTIFACT_DIR'):
            from PIL import Image
            folder = Path(os.environ['RHUN_TEST_ARTIFACT_DIR'])
            folder.mkdir(parents=True, exist_ok=True)
            Image.open(self.work/(name+'.ppm')).save(folder/('markdown-'+name+'.png'))


if __name__ == '__main__':
    unittest.main()
