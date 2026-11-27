#!/usr/bin/env python3
"""Built-in definition lookup through the editor, without a language provider."""
import sys
import unittest

lang = __import__('langfeat-query')
CLICK_MOD = 'cmd' if sys.platform == 'darwin' else 'ctrl'


class BuiltinDefinitions(lang.Lang):
    def setUp(self):
        super().setUp()
        self.config = self.work / 'config/rhun/config'
        self.empty_extensions = self.work / 'empty-extensions'
        self.empty_extensions.mkdir()

    def enable(self):
        self.config.write_text(self.config.read_text().replace(
            '[editor]\n', '[editor]\nbuiltin_definitions = true\n'))

    def edit(self, actions, file='use.s'):
        return self.run_editor(actions, exts=self.empty_extensions, files=(file,))

    def write(self, name, content):
        path = self.proj / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
        return path.as_posix()

    def state(self, output):
        return next(line for line in reversed(output) if line.startswith('tabs='))

    def test_setting_is_off_by_default_and_can_be_toggled_in_settings(self):
        self.write('use.s', 'anchor\n')
        self.write('def.s', 'FN anchor\n')
        lookup = ['key F12', 'wait 350', 'print-state', 'print-toast']
        out = self.edit(lookup)
        self.assertIn('active=use.s', self.state(out))
        self.assertIn('toast=No extension finds definitions in this file', out)
        self.edit(['cmd settings', 'type builtin_definitions', 'click 827 348'])
        self.assertIn('builtin_definitions = true', self.config.read_text())
        self.assertIn('active=def.s line=1', self.state(self.edit(lookup)))

    def test_functions_and_globals_in_supported_languages(self):
        self.enable()
        cases = (
            ('s', 's', 'FN example\n', 'status_value: .long 0\n'),
            ('c', 'c', 'static int example(int x)\n{\n    return x;\n}\n', 'int status_value = 5;\n'),
            ('cpp', 'h', 'inline int example() { return 0; }\n', 'unsigned status_value;\n'),
            ('py', 'py', 'async def example():\n    pass\n', 'status_value: int = 1\n'),
            ('go', 'go', 'func (x Point) example() {}\n', 'var (\n    status_value int\n)\n'),
            ('rs', 'rs', 'pub(crate) async fn example() {}\n', 'pub static mut status_value: i32 = 1;\n'),
            ('js', 'ts', 'export default async function example() {}\n', 'export const status_value = 1;\n'),
        )
        for index, (suffix, definition_suffix, function, variable) in enumerate(cases):
            with self.subTest(language=suffix):
                name, global_name = f'example_{index}', f'status_value_{index}'
                source = f'use.{suffix}'
                target = f'definition-{index}.{definition_suffix}'
                self.write(source, f'{name}\n{global_name}\n')
                self.write(target, function.replace('example', name) + variable.replace('status_value', global_name))
                out = self.edit(['key F12', 'wait 350', 'print-state'], source)
                self.assertIn(f'active={target} line=1 ', self.state(out))
                out = self.edit(['key Down', 'key Home', 'key F12', 'wait 350', 'print-state'], source)
                line = (function + variable).splitlines().index(
                    next(row for row in variable.splitlines() if 'status_value' in row)) + 1
                self.assertIn(f'active={target} line={line} ', self.state(out))

    def test_ctrl_click_and_multi_match_picker(self):
        self.enable()
        self.write('use.s', '    call anchor\n')
        self.write('a.s', '# Comment\nFN anchor\n')
        self.write('nested/b.s', 'anchor: .byte 0\n')
        out = self.edit(['print-point 1 12'])
        x, y = next(row for row in out if row.startswith('point ')).split()[1:]
        out = self.edit([f'click {x} {y} {CLICK_MOD}', 'wait 350', 'print-palette',
                         'key Down', 'key Return', 'print-state'])
        self.assertIn('> a.s:2', out)
        self.assertIn('  nested/b.s:1', out)
        self.assertIn('active=b.s line=1 col=7 sel=6', self.state(out))

    def test_ignores_comments_strings_local_variables_and_c_prototypes(self):
        self.enable()
        self.write('use.c', 'example\n')
        self.write('unrelated.c', '/*\nint example() {}\n*/\nextern int example;\n'
                                  'int example(int x);\nint other() {\n    int example = 1;\n}\n'
                                  'const char *s = "int example() {}";\n')
        self.write('real.c', 'static int example(int x)\n{\n    return x;\n}\n')
        self.write('node_modules/excluded.c', 'int example = 1;\n')
        out = self.edit(['key F12', 'wait 350', 'print-state'], 'use.c')
        self.assertIn('active=real.c line=1', self.state(out))

    def test_assembler_local_labels_and_javascript_dollar_names(self):
        self.enable()
        self.write('use.s', 'jmp .Lagain\n    nop\n.Lagain:\n    ret\n')
        self.write('other.s', '.Lagain:\n    ret\n')
        out = self.edit(['key Right'] * 4 + ['key F12', 'wait 350', 'print-state'])
        self.assertIn('active=use.s line=3 col=8 sel=7', self.state(out))
        self.write('use.js', '$start();\n')
        self.write('defs.js', 'const $start = () => 1;\n')
        out = self.edit(['key F12', 'wait 350', 'print-state'], 'use.js')
        self.assertIn('active=defs.js line=1 col=13 sel=6', self.state(out))

    def test_next_lookup_reuses_unchanged_files_and_reads_the_live_buffer(self):
        self.enable()
        use = self.write('use.s', 'anchor\n')
        self.write('def.s', 'FN anchor\n')
        out = self.edit(['key F12', 'wait 350', 'print-state',
                         'key ctrl+Home', 'key Return',
                         f'open {use}', 'key F12', 'wait 350', 'print-state'])
        states = [row for row in out if row.startswith('tabs=')]
        self.assertIn('active=def.s line=1', states[0])
        self.assertIn('active=def.s line=2', states[1])
        self.assertIn('dirty=1', states[1])

    def test_running_definition_provider_takes_priority(self):
        self.enable()
        self.write('b.rs', 'fn total() {}\n')
        root = self.provider({'hello': 'hello 1 definition', 'answers': {
            'definition': {'body': '1\n' + lang.loc('{path}', 3, 5, 3, 10, 'total')}}},
            'definition = *.rs\n')
        out = self.run_lang(root, ['key Down', 'key Home'] + ['key Right'] * 8 +
                            ['key F12', 'wait 350', 'print-state'])
        self.assertIn('active=a.rs line=3 col=10 sel=5', self.state(out))


if __name__ == '__main__':
    unittest.main()
