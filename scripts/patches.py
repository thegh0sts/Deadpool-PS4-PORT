"""Compile selected shadPS4/GoldHEN XML patches into out/patches.bin for the loader.

Patch addresses are PS4 virtual addresses (eboot base 0x400000); the loader's image places eboot
vaddr 0 at image offset 0. Only literal writes are supported (bytes, bytes16/32/64, float32/64,
utf8, utf16); pattern ("mask") patches are rejected and the patch is skipped whole.

A line may carry Signature="41 8b ?? ..." (hex bytes, ?? for any byte) and SignatureOffset (where
the write goes, from the signature's start). The write goes to Address when the signature matches
there; otherwise to the one place in the executable where it matches. No match, or more than one:
the patch is skipped whole, with a log line.

Patch files: patches/*.xml in the checkout (none bundled; the port's own fixes are BUILTIN_PATCHES) and any folder named with
--patches-dir. A patch is applied when the in-game menu or the launcher turned its bbport.ini key
on (GAME_PATCH_KEYS), when patches.json lists it under "enabled", or when its file marks it
isEnabled and patches.json does not disable it.
"""
import argparse
import json
import re
import struct
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

EBOOT_BASE=0x400000
TITLE_ID='CUSA03528'
APP_VERSION='01.00'
# bbport.ini keys (the in-game menu, the launcher) -> "<file>/<patch name>". None for Deadpool yet.
GAME_PATCH_KEYS={}
# The port's own fixes, applied with --builtin NAME (not listed as patches in the launcher).
# name -> [(Address, bytes, Signature, SignatureOffset)], as a patch XML line would give them.
BUILTIN_PATCHES={
    # Unreal Engine 3's FEngineLoop::Tick sleeps until 1 / GetMaxTickRate() (30 for Deadpool)
    # has passed since the last frame: "jbe <skip the wait>" after "if (MaxTickRate > 0)" becomes
    # a jmp. run.py/run.sh with BB_FPS=uncap (the launcher's "Unlock the frame rate"), which
    # also ignores the game's flip rate.
    'unlock_fps': [(0x00b8848e, bytes.fromhex('e9f500000090'),
                    'ff 90 a8 02 00 00 c5 f0 57 c9 c5 f8 2e c1 0f 86 f4 00 00 00', 14)],
    # illusion's "60 FPS Unlock" for Deadpool 01.00 (illusion0001/PS4-PS5-Game-Patch,
    # Deadpool-Orbis.xml): the game asks sceVideoOutSetFlipRate(handle, 1), a flip every 2nd
    # vblank; this makes it 0. The engine then paces itself at 60 consistently (its menus too),
    # unlike unlock_fps, which skips the engine's wait and leaves the menus' animations broken.
    # "mov $0x1,%esi" before the call: its immediate's first byte.
    'flip_rate_60': [(0x00b41aa1, bytes([0]),
                      '83 39 00 74 0c be 01 00 00 00 89 c7 e8', 6)],
}


def read_settings(path):
    """bbport.ini as a dict (key=value lines; # comments)."""
    settings={}
    if path.exists():
        for line in path.read_text().splitlines():
            key,sep,value=line.partition('=')
            if sep and not line.startswith('#'): settings[key.strip()]=value.strip()
    return settings


def eboot_segments(elf):
    """(start, end) of eboot.elf's load segments: patches must land inside one."""
    phoff,=struct.unpack_from('<Q',elf,0x20)
    phentsize,phnum=struct.unpack_from('<HH',elf,0x36)
    segments=[]
    for i in range(phnum):
        kind,_,_,vaddr,_,_,memsz,_=struct.unpack_from('<IIQQQQQQ',elf,phoff+i*phentsize)
        if kind==1: segments.append((vaddr,vaddr+memsz))
    return segments


def load_segments(elf):
    """[(vaddr, file offset, file size)] of eboot.elf's load segments (signature search)."""
    phoff,=struct.unpack_from('<Q',elf,0x20)
    phentsize,phnum=struct.unpack_from('<HH',elf,0x36)
    found=[]
    for i in range(phnum):
        kind,_,offset,vaddr,_,filesz,_,_=struct.unpack_from('<IIQQQQQQ',elf,phoff+i*phentsize)
        if kind==1: found.append((vaddr,offset,filesz))
    return found


def signature_regex(text):
    tokens=text.split()
    if not tokens: raise ValueError('empty signature')
    return re.compile(b''.join(b'.' if t=='??' else re.escape(bytes([int(t,16)])) for t in tokens),re.S)


def locate(line, offset, elf):
    """The image offset a signed line writes to (see the module docstring)."""
    rx=signature_regex(line.get('Signature'))
    shift=int(line.get('SignatureOffset','0'),0)
    loads=load_segments(elf)
    def at(vaddr):
        for start,pos,size in loads:
            if start<=vaddr and vaddr-start<size: return pos+vaddr-start
    pos=at(offset-shift)
    if pos is not None and rx.match(elf,pos): return offset
    hits=[]
    for start,pos,size in loads:
        hits+=[start+m.start()-pos for m in rx.finditer(elf,pos,pos+size)]
        if len(hits)>1: break
    if len(hits)!=1:
        raise ValueError(f'patch site for {line.get("Address")} not found ({len(hits)} signature matches)')
    return hits[0]+shift


def encode(line):
    kind,value=line.get('Type'),line.get('Value')
    if kind=='bytes': return bytes.fromhex(value.replace(' ',''))
    if kind in ('bytes16','bytes32','bytes64'):
        return int(value,0).to_bytes(int(kind[5:])//8,'little')
    if kind=='float32': return struct.pack('<f',float(value))
    if kind=='float64': return struct.pack('<d',float(value))
    if kind=='utf8': return value.encode()+b'\0'
    if kind=='utf16': return value.encode('utf-16-le')+b'\0\0'
    raise ValueError(f'unsupported patch type {kind!r}')


def external_patches(directory, app_version=APP_VERSION, title_id=TITLE_ID):
    """[(key, file, metadata)] of eboot patches for this version in directory/*.xml.
    key is "<file name>/<patch name>" (the launcher's selection, patches.json). Files whose
    <TitleID> list does not name title_id are skipped (a file without one applies to any game)."""
    found=[]
    directory=Path(directory)
    for path in sorted(directory.glob('*.xml')) if directory.is_dir() else []:
        try:
            root=ET.parse(path).getroot()
        except ET.ParseError as error:
            print(f'Patches: {path.name}: {error}',file=sys.stderr)
            continue
        ids={e.text.strip() for e in root.iter('ID') if e.text}
        if ids and title_id not in ids: continue
        for meta in root.iter('Metadata'):
            if meta.get('AppVer')==app_version and meta.get('AppElf','eboot.bin')=='eboot.bin':
                found.append((f'{path.name}/{meta.get("Name")}',path,meta))
    return found


def external_selection(found, config, ini=None, extra=()):
    """Selected patches: patches.json {"enabled": [...], "disabled": [...]} overrides each file's
    isEnabled; bbport.ini patch_* keys (GAME_PATCH_KEYS, the in-game menu) add to it."""
    settings={}
    if config and Path(config).is_file():
        settings=json.loads(Path(config).read_text())
    enabled,disabled=set(settings.get('enabled',[])),set(settings.get('disabled',[]))
    for key in extra: enabled.add(key); disabled.discard(key)
    for key,patch in GAME_PATCH_KEYS.items():
        if (ini or {}).get(key)=='1': enabled.add(patch); disabled.discard(patch)
    return [(key,path,meta) for key,path,meta in found
            if key in enabled or (key not in disabled and meta.get('isEnabled','false').lower()=='true')]


def compile_external(selected, segments, elf=None):
    """Writes of the selected patches; a patch with unsupported lines is skipped whole. elf (the
    eboot.elf bytes) is needed for lines with a Signature."""
    writes=[]
    for key,_,meta in selected:
        try:
            ours=[]
            for line in meta.iter('Line'):
                offset=int(line.get('Address') or '',0)-EBOOT_BASE
                data=encode(line)
                if line.get('Signature'):
                    if elf is None: raise ValueError('signature without the executable')
                    moved=locate(line,offset,elf)
                    if moved!=offset: print(f'Patches: {key}: {line.get("Address")} found at {moved+EBOOT_BASE:#010x}')
                    offset=moved
                if not any(start<=offset and offset+len(data)<=end for start,end in segments):
                    raise ValueError(f'address {line.get("Address")} is outside the eboot')
                ours.append((offset,data))
        except ValueError as error:
            print(f'Patches: skipped {key}: {error}',file=sys.stderr)
            continue
        writes+=ours
        print(f'Patches: external {key} ({len(ours)} writes)')
    return writes


def screen_size_lines(value):
    """screen_size=WxH: the game's screen size (GScreenWidth/GScreenHeight, 1920x1080), set once
    by a small function that stores the two constants. Every render target, the display buffers
    and the view follow it; the port's presenter fits the frame to the window by its aspect.
    The instructions are "movl $0x780,(%rax)" and "movl $0x438,(%rax)" 13 bytes apart."""
    width,height=(int(v) for v in value.lower().split('x'))
    if not (640<=width<=7680 and 360<=height<=4320): raise ValueError(f'screen size {value} out of range')
    signature='c7 00 80 07 00 00 48 8d 05 ?? ?? ?? ?? c7 00 38 04 00 00'
    return [(0x00b58bb9,width.to_bytes(4,'little'),signature,2),
            (0x00b58bc6,height.to_bytes(4,'little'),signature,15)]


# Hor+ for screens wider than 16:9. The player's view (ULocalPlayer::CalcSceneView, image
# +0x2dc4b1) builds FPerspectiveMatrix with M00 = 1.0 / tan(FOV/2) and M11 from the view's
# width and height: the horizontal FOV is kept, so a wider screen loses the top and bottom.
# The 1.0 is "vmovss <1.0>(%rip),%xmm1"; pointing that load at 16H/(9W) widens the horizontal
# FOV by the screen's extra width and keeps the vertical FOV of 16:9. The constant is shared
# with other code, so the load is pointed at another read-only float of that value (exact, or
# within 0.1%). Cutscenes with a constrained aspect ratio use their own branch (pillarboxed).
HOR_PLUS_SITE=(0x006dc57b,'c5 fa 10 0d ?? ?? ?? ?? c5 f2 5e c8 c5 fa 10 54 24 74 c5 ea 59 c0 '
                          'c5 fa 10 94 24 84 00 00 00',0)


def find_float(elf, value, tolerance=1e-3):
    """Image offset of a 4-byte-aligned float equal to value (else the nearest within tolerance,
    relative), or None. Only the read-only data after the code in the executable load segment is
    searched (from the last RET-padded function on, where the compiler's float literals live), so
    a code byte that happens to match is never used: code can be rewritten at load."""
    phoff,=struct.unpack_from('<Q',elf,0x20)
    phentsize,phnum=struct.unpack_from('<HH',elf,0x36)
    exact=struct.pack('<f',value)
    for i in range(phnum):
        kind,flags,offset,vaddr,_,filesz,_,_=struct.unpack_from('<IIQQQQQQ',elf,phoff+i*phentsize)
        if kind!=1 or flags&2 or not flags&1: continue
        data=elf[offset:offset+filesz]
        # The PLT (16-byte stubs: jmp *GOT; push index; jmp PLT0) is the last code: the
        # literals follow it.
        stubs=[m.end() for m in re.finditer(rb'\xff\x25....\x68....\xe9....',data,re.S)]
        start=max(stubs) if stubs else len(data)//2
        start+=(-(vaddr+start))%4
        best=None
        for j in range(start,len(data)-3,4):
            if data[j:j+4]==exact: return vaddr+j
            v,=struct.unpack_from('<f',data,j)
            if v==v and abs(v-value)<=tolerance*value and (best is None or abs(v-value)<best[0]):
                best=(abs(v-value),vaddr+j)
        if best: return best[1]
    return None


def hor_plus_writes(value, elf):
    """[(image offset, bytes)] for Hor+ at screen_size=WxH (none at 16:9 or narrower)."""
    width,height=(int(v) for v in value.lower().split('x'))
    if width*9<=height*16: return []
    address,signature,shift=HOR_PLUS_SITE
    site=locate({'Address':hex(address),'Signature':signature,'SignatureOffset':str(shift)},
                address-EBOOT_BASE,elf)
    constant=find_float(elf,16*height/(9*width))
    if constant is None: raise ValueError(f'no constant near {16*height/(9*width):.6f} for Hor+')
    return [(site+4,struct.pack('<i',constant-(site+8)))]


def compile_builtin(names, segments, elf):
    """Writes of the named BUILTIN_PATCHES (an unknown name, or a site not found: skipped).
    A name may carry a value: screen_size=2560x1080."""
    writes=[]
    for name in names:
        lines=BUILTIN_PATCHES.get(name)
        if name.startswith('screen_size='):
            try:
                lines=screen_size_lines(name.partition('=')[2])
            except ValueError as error:
                print(f'Patches: {name}: {error}',file=sys.stderr)
                continue
        if lines is None:
            print(f'Patches: no built-in patch {name!r}',file=sys.stderr)
            continue
        try:
            ours=[]
            for address,data,signature,shift in lines:
                line={'Address':hex(address),'Signature':signature,'SignatureOffset':str(shift)}
                offset=locate(line,address-EBOOT_BASE,elf)
                if not any(start<=offset and offset+len(data)<=end for start,end in segments):
                    raise ValueError(f'address {address:#x} is outside the eboot')
                ours.append((offset,data))
            if name.startswith('screen_size='):
                ours+=hor_plus_writes(name.partition('=')[2],elf)
        except ValueError as error:
            print(f'Patches: skipped built-in {name}: {error}',file=sys.stderr)
            continue
        writes+=ours
        print(f'Patches: built-in {name} ({len(ours)} writes)')
    return writes


def write_blob(out, writes):
    """out/patches.bin (BBPATCH2: the patch base, so the loader can rebase pointers written into
    relocated slots)."""
    blob=struct.pack('<8sQQ',b'BBPATCH2',EBOOT_BASE,len(writes))
    for offset,data in writes: blob+=struct.pack('<QQ',offset,len(data))+data
    (out/'patches.bin').write_bytes(blob)


def main():
    root=Path(__file__).resolve().parent.parent
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--patches-dir',type=Path,default=root/'patches',help='patch XML files (shadPS4 format)')
    p.add_argument('--patches-config',type=Path,help='patches.json: enabled/disabled patches')
    p.add_argument('--app-version',default=APP_VERSION)
    p.add_argument('--title-id',default=TITLE_ID,help='the game (patch files naming other ids are skipped)')
    p.add_argument('--out',type=Path,default=root/'out')
    p.add_argument('--settings',type=Path,default=root/'bbport.ini')
    p.add_argument('--enable',action='append',default=[],metavar='KEY',
                   help='also apply this patch file entry ("<file>/<patch name>")')
    p.add_argument('--builtin',action='append',default=[],metavar='NAME',
                   help='apply a built-in fix (BUILTIN_PATCHES; run.py: unlock_fps with BB_FPS=uncap)')
    p.add_argument('--external-only',action='store_true',help='accepted for older callers (the only mode)')
    a=p.parse_args()
    elf=(a.out/'eboot.elf').read_bytes()
    segments=eboot_segments(elf)
    found=external_patches(a.patches_dir,a.app_version,a.title_id)
    settings=read_settings(a.settings)
    writes=compile_builtin(a.builtin,segments,elf)
    writes+=compile_external(external_selection(found,a.patches_config,settings,a.enable),segments,elf)
    write_blob(a.out,writes)
    print(f'Patches: {len(writes)} writes from {len(found)} available patches')


if __name__=='__main__':
    main()
