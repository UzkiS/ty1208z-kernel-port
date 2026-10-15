#!/usr/bin/env python3
"""Check full offline RDA staging, byte identity and corruption rejection."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fetch_wifi import VENDOR, fetch, load_lock, source_entries, verify, verify_vendor


class VendorTests(unittest.TestCase):
    def test_complete_tree_stages_without_network(self):
        lock = load_lock()
        verify_vendor(lock)
        self.assertEqual(len(lock['files']), 63)
        self.assertEqual(len(source_entries(lock)), 48)
        with tempfile.TemporaryDirectory() as directory, patch(
                'fetch_wifi.urllib.request.urlopen', side_effect=AssertionError('Network used')):
            output = Path(directory)
            for item in lock['files']:
                fetch(item, output, False)
                self.assertEqual((output / item['path']).read_bytes(),
                                 (VENDOR / item['path']).read_bytes())
                fetch(item, output, True)
                verify(item, (output / item['path']).read_bytes())

    def test_corrupt_or_missing_inputs_do_not_fall_back_to_network(self):
        item = load_lock()['files'][0]
        with tempfile.TemporaryDirectory() as directory, patch(
                'fetch_wifi.urllib.request.urlopen', side_effect=AssertionError('Network used')):
            root = Path(directory)
            source, output = root / 'vendor', root / 'output'
            source.mkdir()
            with self.assertRaises(FileNotFoundError):
                fetch(item, output, False, vendor=source)
            local = source / item['path']
            local.write_bytes(b'corrupted')
            with self.assertRaises(ValueError):
                fetch(item, output, False, vendor=source)
            self.assertFalse((output / item['path']).exists())
            (output / item['path']).parent.mkdir(parents=True, exist_ok=True)
            (output / item['path']).write_bytes(b'corrupted cache')
            with self.assertRaises(ValueError):
                fetch(item, output, False)


if __name__ == '__main__':
    unittest.main(verbosity=2)
