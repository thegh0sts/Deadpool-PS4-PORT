#!/usr/bin/env python3
"""Which of the game's imports the runtime does not serve yet, before building anything.

Prepares and links the executable into OUT (scripts/prepare.py, scripts/link_modules.py with the
profile's modules), names its imports from shadPS4's aerolib.inl (tools/gen_import_names.py;
OUT/aerolib.inl, fetched once, or --aerolib), then looks each import up in the runtime's sources:
src/ (symbol names in the export tables and resolvers, NID literals, the PSN service prefixes
runtime_net.c answers as unavailable) and gpu/ (shadPS4 LIB_FUNCTION registrations). Prints the imports nothing serves, grouped by library.

This is a static estimate from the sources. The built probe gives the exact answer:
`out/sacredfire out/boot-linked.bin --import-names out/import_names.txt --list-imports`
(runtime / native / unresolved per import). An unresolved import does not stop loading: it is
bound to a trap that stops the game when it is first called.

Usage: tools/module_imports.py GAME_DIR [--out OUT] [--aerolib PATH]
"""
import argparse
import collections
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ('src/*.c', 'src/*.h', 'gpu/shim/**/*.c', 'gpu/shim/**/*.cpp', 'gpu/shim/**/*.h')
GPU_SOURCES = ('gpu/shadps4/**/*.cpp', 'gpu/shim/**/*.cpp')


def served_names():
    """(symbol names, NIDs, symbol prefixes) the runtime's sources serve."""
    text = ''.join(p.read_text(errors='replace') for pattern in SOURCES for p in ROOT.glob(pattern)
                   if p.name != 'import_names.inc')
    symbols = set(re.findall(r'"([A-Za-z_][A-Za-z0-9_]*)"', text))
    nids = set(re.findall(r'"([A-Za-z0-9+/-]{11})(?:#[^"]*)?"', text))
    gpu = ''.join(p.read_text(errors='replace') for pattern in GPU_SOURCES for p in ROOT.glob(pattern))
    nids |= set(re.findall(r'LIB_FUNCTION\(\s*"([A-Za-z0-9+/-]{11})"', gpu))
    # runtime_net.c: whole PSN services answered "unavailable" by symbol prefix.
    net = (ROOT / 'src' / 'runtime_net.c').read_text(errors='replace')
    prefixes = tuple(re.findall(r'\{"(sce[A-Za-z0-9]+)","[^"]*",\(int32_t\)0x', net))
    return symbols, nids, prefixes


def run(*args):
    result = subprocess.run([sys.executable, *map(str, args)], cwd=ROOT, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if result.returncode:
        sys.exit(result.stdout)
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('game', type=Path)
    parser.add_argument('--out', type=Path, default=ROOT / 'out')
    parser.add_argument('--aerolib', type=Path)
    args = parser.parse_args()

    sys.path.insert(0, str(ROOT / 'scripts'))
    import game_check  # noqa: E402
    profile = game_check.profile(args.game) or game_check.SUPPORTED[game_check.SUPPORTED_IMAGE]
    args.out.mkdir(parents=True, exist_ok=True)
    env_skip = os.environ.get('BB_SKIP_GAME_CHECK')
    run('scripts/prepare.py', args.game, '--out', args.out)
    run('scripts/link_modules.py', args.game, '--out', args.out, '--modules', *profile['modules'])
    run('tools/gen_import_names.py', '--out', args.out, *(['--aerolib', args.aerolib] if args.aerolib else []))

    symbols, nids, prefixes = served_names()
    total = len(json.loads((args.out / 'link.json').read_text())['unresolved_imports'])
    missing = collections.defaultdict(list)
    for line in (args.out / 'import_names.txt').read_text().splitlines():
        if line.startswith('#') or not line.strip():
            continue
        nid, library, symbol = line.split()[:3]
        if symbol not in symbols and nid not in nids and not (prefixes and symbol.startswith(prefixes)):
            missing[library].append(symbol if symbol != '?' else f'? ({nid})')
    count = sum(map(len, missing.values()))
    print(f"{profile['game']} {profile['title']}: {total} imports left to the host runtime after linking "
          f"{', '.join(profile['modules'])}; {count} not found in the runtime's sources"
          + (' (BB_SKIP_GAME_CHECK set)' if env_skip == '1' else ''))
    for library in sorted(missing, key=lambda name: (-len(missing[name]), name)):
        print(f'  {library} ({len(missing[library])}): ' + ', '.join(sorted(missing[library])))


if __name__ == '__main__':
    main()
