# Deadpool PS4 port: handoff notes (2026-11-15)

Folder: `C:\Users\kshla\source\repos\Deadpool-PS4`. It holds the port's code: a clone of
[CTR-NitroFueled-PC](https://github.com/GetLostIn/CTR-NitroFueled-PC) (base commit `0cf8def`, a
Windows fork of SacredFire) set up in place with `git init` + `git fetch` + `git reset --hard
origin/main`, then `git submodule update --init --recursive`, with the Deadpool changes below on
top, not committed yet. `origin` still points at GetLostIn's repository: point it at your own
before pushing.

## The dump (my own)
| Folder | Title ID | Content ID | App ver | Firmware |
|---|---|---|---|---|
| `Deadpool.PS4-EU` | CUSA03528 | EP0002-CUSA03528_00-DEADPOOLPS400000 | 01.00 | 2.70 |

- `eboot.bin` (58,181,818 bytes), loaded-image SHA-256
  `a5ec3f24a2951e75f2dafb741b8ebd2c80200e5fd1bd8a26addc78ba0ff3e30d` (the hash `game_check.py`
  keys on). Entry 0xb75010, image 42,768,944 bytes, 547 imported symbols, 37 required modules.
- `sce_module`: libc, libSceFace, libSceFios2, libSceHand, libSceS3DConversion, libSceSmart. The
  executable needs only **libc and libSceFios2** (its DT_NEEDED list); the other four (camera,
  stereo 3D) ship unused. So the profile's `modules` is `libc.prx, libSceFios2.prx`, not all six.
- Languages: English, French, Spanish, German, Italian. `TransGame\` is Unreal Engine 3 data.

**The EU dump is the one we work with.** The US folder (CUSA03245) was a community repack, not a
console dump: its `sce_sys/changeinfo/changeinfo.xml` lists a 60fps patch (illusion0001),
Coalesced.ini edits (Wasterlander121) and PSN/network calls disabled (CyB1K, the 32 `xor eax,eax;
ret` stubs), and it was rebuilt in 2021 for firmware 4.50. Its Coalesced.ini and Coalesced.int/
FRA/ESN were edited too, and it lacks German and Italian. It is no longer in the folder. A US profile
needs a clean dump; `game_check.py` refuses any folder with a changeinfo.xml as `modified`.

## Why this base
The SacredFire ports named before (NHL 19/20/21, Madden 17, UFC 3) are EA Ignite engine games;
Deadpool is UE3. CTR-NitroFueled-PC has the Windows layer (loader, memory, TLS, exceptions,
files, timers), the launcher and the shadPS4-derived Vulkan renderer.

## Done (2026-11-15, uncommitted)
- `scripts/game_check.py`: the Crash Team Racing profiles replaced by Deadpool EU (`name`
  `deadpool`). Problems reported: `modified` (repack / patched eboot), `unsupported_edition` (US,
  until a clean dump), `other_title`, `unreadable`, `split_layout`. The CTR-only checks (1.21
  update, 6.72+ variant, IGA archive damage) are gone. `tests/test_game_check.py` rewritten; the
  whole Python test suite passes.
- `run.sh`, `run.py`: default profile name `deadpool` instead of `ctr`.
- `tools/module_imports.py GAME_DIR`: prepares and links the dump, names the imports
  (needs `out/aerolib.inl` from shadPS4, fetched once, or `--aerolib`) and lists those the
  runtime's sources don't serve. A static estimate: the built probe's `--list-imports` is exact.
- `.gitignore`: the dump folders, `eboot.bin`, `*.prx`, `*.sprx`, `boot*.bin` (plus the existing
  `out/`, `user/`).

## Imports still to write (static estimate, 36 of 445 left to the host runtime)
- libkernel: `__Ux86_64_setcontext`, `msync`, `sceKernelUtimes`, `scePthreadGet/Setschedparam`,
  `sigreturn`
- libScePosix: `sem_init/destroy/post/wait/timedwait`
- Online and dialogs, likely fine as "not available" stubs: NpScore (5), ErrorDialog (4),
  Http (4), NpManager in-game messages (2), NpUtility, InvitationDialog, ImeDialog panel size
- AppContent `AddcontMount/Unmount`, SystemService `GetDisplaySafeAreaInfo`, VideoRecording
  `SetInfo`, GameLiveStreaming `GetCurrentStatus`, Voice `GetResourceInfo`, DiscMap `ioKMruft1ek`
  (no name in aerolib)
An unresolved import doesn't stop loading: it's bound to a trap that stops the game when called.

## Next
- Commit the changes above, then strip the CTR-specific parts: `TITLE_ID` and paths in
  `run.py`/`run.sh`, `patches/` and `scripts/patches.py` (CTR patch files), ultrawide scripts,
  `scripts/merge_update.py` (Deadpool has no update), `src/ctr_trophies.h`, launcher texts,
  README, the executable/launcher names.
- Write the missing imports, build, run `--list-imports`, then the first start.

## Rules
- Only my own dumps. Never commit or publish game files or anything derived from them
  (dump folders, `out\`, `user\`, `boot-linked.bin`).
- Commits use `17183580+thegh0sts@users.noreply.github.com`, not my email.
