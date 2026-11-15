#!/usr/bin/env python3
"""The game files this port runs, keyed on the executable's loaded image.

Profile: Deadpool (High Moon Studios, Unreal Engine 3), the European edition CUSA03528 version
01.00 (EP0002-CUSA03528_00-DEADPOOLPS400000, firmware 2.70). The check compares the loaded
executable image, whose hash is the same whatever tool dumped it (the SELF headers around it
differ). BB_SKIP_GAME_CHECK=1 skips it.

The North American edition (CUSA03245) runs the same 01.00 build; its profile will be added from a
clean dump. Community repacks of the game (60 FPS, Coalesced.ini edits, network calls stubbed out
with `xor eax,eax; ret`) change the executable and carry an sce_sys/changeinfo/changeinfo.xml that
a console dump of the game has not: they are refused as 'modified'.

Forked from CTR-NitroFueled-PC (GetLostIn), itself a fork of SacredFire; its Crash Team Racing
profiles were removed on 2026-11-15.
"""
import hashlib
import os
import sys
from pathlib import Path

# image sha256 -> profile. `name` is what the runtime and the GPU menu read (BB_GAME_PROFILE);
# `modules` are the sce_module PRXs link_modules.py links natively (the executable imports only
# these two: libSceFace, libSceHand, libSceSmart and libSceS3DConversion ship with the game but
# are not in its DT_NEEDED list); `patches` says whether patches.py has a patch file for it.
SUPPORTED = {
    'a5ec3f24a2951e75f2dafb741b8ebd2c80200e5fd1bd8a26addc78ba0ff3e30d': dict(
        name='deadpool', title='CUSA03528', version='01.00', game='Deadpool (EU)',
        content_id='EP0002-CUSA03528_00-DEADPOOLPS400000',
        languages=('English', 'French', 'Spanish', 'German', 'Italian'),
        modules=('libc.prx', 'libSceFios2.prx'), patches=False),
}
BY_TITLE = {p['title']: p for p in SUPPORTED.values()}
# Editions of the game whose clean image is not known yet: recognised by title so the message can
# say so, never run.
KNOWN_TITLES = {
    'CUSA03245': 'Deadpool (North America)',
}
SUPPORTED_TITLE = 'CUSA03528'
SUPPORTED_VERSION = '01.00'
SUPPORTED_IMAGE = 'a5ec3f24a2951e75f2dafb741b8ebd2c80200e5fd1bd8a26addc78ba0ff3e30d'


def image_sha256(game):
    """The SHA-256 of eboot.bin's loaded image (its loadable segments at their addresses)."""
    from prepare import parse_self, span  # same directory
    elf, header, ph, _segments, _missing = parse_self((Path(game) / 'eboot.bin').read_bytes())
    loads = [p for p in ph if p['type'] in (1, 0x61000010)]
    image = bytearray(max(p['vaddr'] + p['memsz'] for p in loads))
    for p in loads:
        image[p['vaddr']:p['vaddr'] + p['filesz']] = span(elf, p['offset'], p['filesz'])
    return hashlib.sha256(image).hexdigest()


def profile(game, image_hash=None):
    """The profile dict for a supported game folder, else None (BB_SKIP_GAME_CHECK=1: a profile
    guessed from param.sfo's TITLE_ID when one exists, so run.sh can still branch)."""
    try:
        image_hash = image_hash or image_sha256(game)
    except (OSError, ValueError, IndexError, StopIteration, KeyError):
        image_hash = None
    if image_hash in SUPPORTED:
        return dict(SUPPORTED[image_hash])
    if os.environ.get('BB_SKIP_GAME_CHECK') != '1':
        return None
    return BY_TITLE.get(sfo_info(game).get('TITLE_ID'))


def sfo_info(game):
    from prepare import sfo
    try:
        return sfo((Path(game) / 'sce_sys/param.sfo').read_bytes())
    except (OSError, ValueError, IndexError):
        return {}


def split_layout(game):
    """True for a PS4 PKG Tool dump (the files in Image0, sce_sys in Sc0) that was not flattened,
    including one fixed by hand only as far as eboot.bin and param.sfo."""
    game = Path(game)
    return (game / 'Image0/eboot.bin').is_file() and not (game / 'sce_module').is_dir()


def changeinfo(game):
    """The text of sce_sys/changeinfo/changeinfo.xml, or None. A console dump of 01.00 has none;
    repacks list their changes there."""
    try:
        return (Path(game) / 'sce_sys/changeinfo/changeinfo.xml').read_text('utf-8', 'replace')
    except OSError:
        return None


def problem(game, image_hash=None):
    """None for a supported game, else (kind, title, version): kind is 'split_layout' (Image0 +
    Sc0 not flattened), 'unreadable', 'modified' (a repack: changeinfo.xml, or a known title with
    another executable), 'unsupported_edition' (an edition whose clean image is not known yet) or
    'other_title' (another game)."""
    if os.environ.get('BB_SKIP_GAME_CHECK') == '1':
        return None
    if split_layout(game):
        return 'split_layout', '?', '?'
    info = sfo_info(game)
    title, version = info.get('TITLE_ID', '?'), info.get('APP_VER', '?')
    try:
        image_hash = image_hash or image_sha256(game)
    except (OSError, ValueError, IndexError, StopIteration, KeyError):
        return 'unreadable', title, version
    if image_hash in SUPPORTED:
        return None
    if changeinfo(game) is not None or title in BY_TITLE:
        return 'modified', title, version
    if title in KNOWN_TITLES:
        return 'unsupported_edition', title, version
    return 'other_title', title, version


def explain(kind, title, version):
    """What is wrong and what to do, for the log (English)."""
    found = f'Found {title} version {version} (sce_sys/param.sfo).'
    supported = ', '.join(f"{q['game']} {q['title']} {q['version']}" for q in SUPPORTED.values())
    return {
        'modified': f'{found} The executable is not the original one: this looks like a modified '
                    'repack (patched eboot.bin, a changeinfo.xml listing community changes). '
                    f'Dump the game again from your own disc or installation. Supported: {supported}.',
        'unsupported_edition': f'{found} This edition ({KNOWN_TITLES.get(title, title)}) is not '
                               f'supported yet. Supported: {supported}.',
        'other_title': f'{found} Supported: {supported}.',
        'split_layout': 'The game folder has the PS4 PKG Tool layout (Image0 and Sc0): choose it in the '
                        'launcher and press "Prepare the game", or copy everything in Image0 to the game folder '
                        'and everything in Sc0 to its sce_sys folder.',
        'unreadable': f'{found} eboot.bin could not be read as a decrypted PS4 executable: dump '
                      'the game again.',
    }[kind]


if __name__ == '__main__':
    # game_check.py GAME_DIR: prints the profile name (run.sh branches on it), or fails with the reason.
    # game_check.py --info GAME_DIR: prints "TITLE_ID APP_VER" (run.py passes them to patches.py).
    # game_check.py --modules GAME_DIR: the sce_module PRXs to link natively (link_modules.py).
    args = sys.argv[1:]
    if args[:1] == ['--info']:
        info = sfo_info(Path(args[1]) if len(args) > 1 else Path('.'))
        print(info.get('TITLE_ID', SUPPORTED_TITLE), info.get('APP_VER', SUPPORTED_VERSION))
        sys.exit()
    if args[:1] == ['--modules']:
        found = profile(Path(args[1]) if len(args) > 1 else Path('.')) or SUPPORTED[SUPPORTED_IMAGE]
        print(' '.join(found['modules']))
        sys.exit()
    game = Path(args[0]) if args else Path('.')
    found = problem(game)
    if found:
        sys.exit('Unsupported game files: ' + explain(*found))
    found = profile(game)
    print(found['name'] if found else 'unknown')
