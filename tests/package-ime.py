#!/usr/bin/env python3
"""Pinyin downloads use one private APT source/index set and fail closed."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('package_ime', ROOT / 'tools/package-ime.py')
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


class PackageIndexes(unittest.TestCase):
    def test_update_and_download_share_private_indexes(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / 'debs'
            directory.mkdir()
            calls = []

            def run(args, **kwargs):
                self.assertTrue(kwargs['check'])
                options = dict(a.split('=', 1) for a in args if '=' in a)
                sources = Path(options['Dir::Etc::SourceList'])
                self.assertIn('noble main restricted universe multiverse', sources.read_text())
                self.assertIn('noble-updates', sources.read_text())
                self.assertIn('noble-security', sources.read_text())
                self.assertEqual(options['Dir::State::status'], '/dev/null')
                self.assertTrue(Path(options['Dir::State::lists']).is_relative_to(directory.parent))
                self.assertTrue(Path(options['Dir::State::lists'], 'partial').is_dir())
                config = Path(args[args.index('-c') + 1]).read_text()
                self.assertIn('#clear APT::Update::Post-Invoke;', config)
                calls.append((args, kwargs))

            with patch.object(package.subprocess, 'run', side_effect=run):
                package.download_packages(directory)
            self.assertEqual(len(calls), 2)
            first, second = calls
            self.assertEqual(first[0][-2:], ['--error-on=any', 'update'])
            index = second[0].index('download')
            self.assertEqual(first[0][:-2], second[0][:index])
            self.assertEqual(second[0][index + 1:], package.PACKAGES)
            self.assertEqual(second[1]['cwd'], directory)
            self.assertEqual(list(directory.parent.iterdir()), [directory])

    def test_failed_update_never_downloads_stale_indexes(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / 'debs'
            directory.mkdir()
            with patch.object(package.subprocess, 'run',
                              side_effect=subprocess.CalledProcessError(100, 'apt-get')) as run:
                with self.assertRaises(subprocess.CalledProcessError):
                    package.download_packages(directory)
            self.assertEqual(run.call_count, 1)
            self.assertEqual(list(directory.parent.iterdir()), [directory])


if __name__ == '__main__':
    unittest.main()
