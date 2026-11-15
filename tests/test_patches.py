from paths import ROOT  # noqa: F401 (sets up the import path)
import json
import struct
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from patches import (EBOOT_BASE, GAME_PATCH_KEYS, compile_external, eboot_segments, encode,
                     external_patches, external_selection, read_settings, write_blob)

SEGMENTS = [(0, 0x6000000)]

EXTERNAL = """<?xml version="1.0"?>
<Patch>
  <TitleID><ID>CUSA03528</ID></TitleID>
  <Metadata Title="Deadpool" Name="On" Author="x" PatchVer="1.0" AppVer="01.00" AppElf="eboot.bin" isEnabled="true">
    <PatchList><Line Type="bytes" Address="0x00500000" Value="9090"/></PatchList>
  </Metadata>
  <Metadata Title="Deadpool" Name="Off" Author="x" PatchVer="1.0" AppVer="01.00" AppElf="eboot.bin">
    <PatchList><Line Type="bytes32" Address="0x00500010" Value="0x11223344"/></PatchList>
  </Metadata>
  <Metadata Title="Deadpool" Name="Mask" Author="x" PatchVer="1.0" AppVer="01.00" AppElf="eboot.bin" isEnabled="true">
    <PatchList><Line Type="mask" Address="" Value="90 90"/></PatchList>
  </Metadata>
  <Metadata Title="Deadpool" Name="Old" Author="x" PatchVer="1.0" AppVer="01.98" AppElf="eboot.bin" isEnabled="true">
    <PatchList><Line Type="bytes" Address="0x00500020" Value="90"/></PatchList>
  </Metadata>
</Patch>
"""


class ExternalPatchTests(unittest.TestCase):
    def test_selection_filters_version_title_and_mask_patches(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / 'extra.xml').write_text(EXTERNAL)
            (folder / 'other.xml').write_text(EXTERNAL.replace('CUSA03528', 'CUSA99999'))
            found = external_patches(folder)
            self.assertEqual([key for key, _, _ in found], ['extra.xml/On', 'extra.xml/Off', 'extra.xml/Mask'])
            # isEnabled selects On and Mask; Mask is skipped whole for its unsupported line.
            writes = compile_external(external_selection(found, None), SEGMENTS)
            self.assertEqual(writes, [(0x100000, b'\x90\x90')])
            config = folder / 'patches.json'
            config.write_text(json.dumps({'enabled': ['extra.xml/Off'], 'disabled': ['extra.xml/On']}))
            writes = compile_external(external_selection(found, config), SEGMENTS)
            self.assertEqual(writes, [(0x100010, b'\x44\x33\x22\x11')])

    def test_out_of_segment_patch_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / 'extra.xml').write_text(EXTERNAL)
            found = external_patches(folder)
            self.assertEqual(compile_external(external_selection(found, None), [(0, 0x1000)]), [])

    def test_encode_types(self):
        import xml.etree.ElementTree as ET
        line = ET.fromstring('<Line Type="float32" Address="0x400000" Value="1.0"/>')
        self.assertEqual(encode(line), struct.pack('<f', 1.0))
        line = ET.fromstring('<Line Type="utf8" Address="0x400000" Value="ab"/>')
        self.assertEqual(encode(line), b'ab\0')
        with self.assertRaises(ValueError):
            encode(ET.fromstring('<Line Type="mask" Address="" Value="90"/>'))

    def test_eboot_segments_and_blob(self):
        elf = bytearray(120)
        struct.pack_into('<Q', elf, 0x20, 64)
        struct.pack_into('<HH', elf, 0x36, 56, 1)
        struct.pack_into('<IIQQQQQQ', elf, 64, 1, 0, 0, 0x1000, 0, 0, 0x2000, 0)
        self.assertEqual(eboot_segments(bytes(elf)), [(0x1000, 0x3000)])
        with tempfile.TemporaryDirectory() as tmp:
            write_blob(Path(tmp), [(0x10, b'\x90')])
            blob = (Path(tmp) / 'patches.bin').read_bytes()
            self.assertEqual(blob[:24], struct.pack('<8sQQ', b'BBPATCH2', EBOOT_BASE, 1))
            self.assertEqual(blob[24:], struct.pack('<QQ', 0x10, 1) + b'\x90')


def tiny_elf(code, vaddr=0x1000, offset=0x100):
    """An ELF64 header with one load segment holding code at vaddr (file offset offset)."""
    elf = bytearray(offset) + code
    struct.pack_into('<Q', elf, 0x20, 64)
    struct.pack_into('<HH', elf, 0x36, 56, 1)
    struct.pack_into('<IIQQQQQQ', elf, 64, 1, 5, offset, vaddr, vaddr, len(code), len(code), 0x10)
    return bytes(elf)


class SignatureTests(unittest.TestCase):
    SIGNED = """<?xml version="1.0"?><Patch><TitleID><ID>CUSA03528</ID></TitleID>
      <Metadata Title="Deadpool" Name="S" Author="x" AppVer="01.00" AppElf="eboot.bin" isEnabled="true">
        <PatchList><Line Type="bytes" Address="{address}" Value="9090" Signature="aa bb ?? dd" SignatureOffset="0x2"/></PatchList>
      </Metadata></Patch>"""

    def writes(self, elf, address):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'p.xml').write_text(self.SIGNED.format(address=hex(address)))
            found = external_patches(Path(tmp))
            return compile_external(external_selection(found, None), eboot_segments(elf), elf)

    def test_signature_at_the_address(self):
        elf = tiny_elf(b'\0' * 16 + b'\xaa\xbb\x01\xdd' + b'\0' * 12)
        self.assertEqual(self.writes(elf, EBOOT_BASE + 0x1012), [(0x1012, b'\x90\x90')])

    def test_signature_moved(self):
        # Another build: the same code at another address.
        elf = tiny_elf(b'\0' * 4 + b'\xaa\xbb\x07\xdd' + b'\0' * 24)
        self.assertEqual(self.writes(elf, EBOOT_BASE + 0x1012), [(0x1006, b'\x90\x90')])

    def test_signature_missing_or_ambiguous_skips_the_patch(self):
        self.assertEqual(self.writes(tiny_elf(b'\0' * 32), EBOOT_BASE + 0x1012), [])
        twice = tiny_elf(b'\xaa\xbb\x00\xdd' * 2 + b'\0' * 24)
        self.assertEqual(self.writes(twice, EBOOT_BASE + 0x1012), [])


class GamePatchTests(unittest.TestCase):
    def test_bundled_patches(self):
        # Only the frame rate unlock, off unless asked for (run.py --enable with BB_FPS=uncap).
        self.assertEqual(GAME_PATCH_KEYS, {})
        found = external_patches(ROOT / 'patches')
        self.assertEqual([key for key, _, _ in found], ['Deadpool.xml/Unlock frame rate'])
        self.assertEqual(external_selection(found, None), [])
        selected = external_selection(found, None, extra=['Deadpool.xml/Unlock frame rate'])
        self.assertEqual([key for key, _, _ in selected], ['Deadpool.xml/Unlock frame rate'])
        line = next(selected[0][2].iter('Line'))
        self.assertEqual(int(line.get('Address'), 0) - EBOOT_BASE, 0x78848e)
        self.assertEqual(encode(line), bytes.fromhex('e9f500000090'))

    def test_ini_keys_select_patches(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'extra.xml').write_text(EXTERNAL)
            found = external_patches(Path(tmp))
            keys = {'patch_test': 'extra.xml/Off'}
            with unittest.mock.patch.dict(GAME_PATCH_KEYS, keys):
                selected = external_selection(found, None, {'patch_test': '1'})
            self.assertIn('extra.xml/Off', [key for key, _, _ in selected])

    def test_read_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            ini = Path(tmp) / 'bbport.ini'
            ini.write_text('# comment\npatch_60fps=1\nfps_counter = 0\n')
            self.assertEqual(read_settings(ini), {'patch_60fps': '1', 'fps_counter': '0'})
            self.assertEqual(read_settings(Path(tmp) / 'missing.ini'), {})


if __name__ == '__main__':
    unittest.main()
