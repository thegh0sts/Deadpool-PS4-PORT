from paths import ROOT
import os
import struct
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import game_check
from test_prepare import fixture


def param_sfo(entries):
    """A minimal param.sfo with UTF-8 string entries."""
    keys = b''.join(k.encode() + b'\0' for k in entries)
    values = [v.encode() + b'\0' for v in entries.values()]
    count = len(entries)
    key_table = 20 + 16 * count
    data_table = key_table + len(keys)
    data = bytearray(struct.pack('<4sIIII', b'\0PSF', 0x101, key_table, data_table, count))
    key_off = data_off = 0
    for key, value in zip(entries, values):
        data += struct.pack('<HHIII', key_off, 0x204, len(value), len(value), data_off)
        key_off += len(key) + 1
        data_off += len(value)
    return bytes(data + keys + b''.join(values))


class GameCheckTests(unittest.TestCase):
    def game(self, title, version, eboot=None):
        path = Path(self.tmp.name)
        (path / 'sce_sys').mkdir(exist_ok=True)
        (path / 'sce_sys/param.sfo').write_bytes(param_sfo({'APP_VER': version, 'TITLE_ID': title}))
        (path / 'eboot.bin').write_bytes(fixture() if eboot is None else eboot)
        return path

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ.pop('BB_SKIP_GAME_CHECK', None)

    def tearDown(self):
        self.tmp.cleanup()

    def supported(self, game):
        """game_check.SUPPORTED with the fixture's image standing in for the EU executable."""
        return {game_check.image_sha256(game): game_check.SUPPORTED[game_check.SUPPORTED_IMAGE]}

    def test_supported_image_passes(self):
        game = self.game('CUSA03528', '01.00')
        with mock.patch.object(game_check, 'SUPPORTED', self.supported(game)):
            self.assertIsNone(game_check.problem(game))
            profile = game_check.profile(game)
            self.assertEqual((profile['name'], profile['title'], profile['version']), ('deadpool', 'CUSA03528', '01.00'))
            self.assertEqual(profile['modules'], ('libc.prx', 'libSceFios2.prx'))

    def test_another_executable_with_the_supported_title_is_modified(self):
        # Same title and version, another executable: a patched eboot.bin.
        game = self.game('CUSA03528', '01.00')
        self.assertEqual(game_check.problem(game), ('modified', 'CUSA03528', '01.00'))
        self.assertIsNone(game_check.profile(game))

    def test_changeinfo_marks_a_repack(self):
        # Community repacks carry sce_sys/changeinfo/changeinfo.xml (60fps, network calls stubbed).
        game = self.game('CUSA03245', '01.00')
        (game / 'sce_sys/changeinfo').mkdir()
        (game / 'sce_sys/changeinfo/changeinfo.xml').write_text('<changeinfo/>')
        self.assertEqual(game_check.problem(game)[0], 'modified')
        self.assertIn('repack', game_check.explain(*game_check.problem(game)))

    def test_north_american_edition_is_not_supported_yet(self):
        game = self.game('CUSA03245', '01.00')
        self.assertEqual(game_check.problem(game), ('unsupported_edition', 'CUSA03245', '01.00'))
        self.assertIn('North America', game_check.explain(*game_check.problem(game)))

    def test_other_title(self):
        # Crash Team Racing (the game this fork comes from) is no longer a profile.
        self.assertEqual(game_check.problem(self.game('CUSA13795', '01.21'))[0], 'other_title')

    def test_unreadable_executable(self):
        self.assertEqual(game_check.problem(self.game('CUSA03528', '01.00', b'junk'))[0], 'unreadable')

    def test_profile_guess_with_the_check_skipped(self):
        game = self.game('CUSA03528', '01.00')
        self.assertIsNone(game_check.profile(game))
        with mock.patch.dict(os.environ, {'BB_SKIP_GAME_CHECK': '1'}):
            self.assertEqual(game_check.profile(game)['name'], 'deadpool')
            self.assertIsNone(game_check.profile(self.game('CUSA13795', '01.21')))

    def test_skip_switch(self):
        os.environ['BB_SKIP_GAME_CHECK'] = '1'
        self.assertIsNone(game_check.problem(self.game('CUSA13795', '01.00')))

    def test_pkg_tool_layout_needs_preparing(self):
        # PS4 PKG Tool: Image0 holds eboot.bin and sce_module, Sc0 the sce_sys files. A copied
        # eboot.bin and param.sfo alone do not make it runnable (sce_module stays in Image0).
        game = self.game('CUSA03528', '01.00')
        (game / 'Image0').mkdir()
        (game / 'Image0/eboot.bin').write_bytes(fixture())
        self.assertEqual(game_check.problem(game)[0], 'split_layout')
        self.assertIn('Image0', game_check.explain('split_layout', '?', '?'))
        (game / 'sce_module').mkdir()
        with mock.patch.object(game_check, 'SUPPORTED', self.supported(game)):
            self.assertIsNone(game_check.problem(game))

    def test_every_problem_is_explained(self):
        for kind in ('modified', 'unsupported_edition', 'other_title', 'unreadable'):
            self.assertIn('CUSA03245', game_check.explain(kind, 'CUSA03245', '01.00'))
        for kind in ('modified', 'unsupported_edition', 'other_title'):
            self.assertIn('CUSA03528', game_check.explain(kind, 'CUSA00000', '01.00'))


if __name__ == '__main__':
    unittest.main()
