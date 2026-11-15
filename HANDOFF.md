# Deadpool PS4 port: handoff notes (2026-11-15)

Folder: `C:\Users\kshla\source\repos\Deadpool-PS4`. It holds the port's code: a clone of
[CTR-NitroFueled-PC](https://github.com/GetLostIn/CTR-NitroFueled-PC) (base commit `0cf8def`, a
Windows fork of SacredFire) set up in place with `git init` + `git fetch` + `git reset --hard
origin/main`, then `git submodule update --init --recursive`, with the Deadpool changes below on
top. Repository: https://github.com/thegh0sts/Deadpool-PS4-PORT (`origin`; GetLostIn's is
`upstream`).

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

## Done (2026-11-15, commit b824519)
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

## CTR stripped (2026-11-15, branch `strip-ctr`)
Removed: the CTR patch files and the patch keys and render-scale patches in `scripts/patches.py`;
the ultrawide scripts, data and shaders; `tools/merge_update.py` and `tools/igz_merge.py` (CTR's
update merge and Alchemy archives); `src/ctr_trophies.h`; the CTR logo and icon (replaced by a
plain abstract icon, `packaging/windows/icons/port.ico`); the merge `.bat` and the Spanish
`LEEME.txt` of the portable package.
Changed: `run.py`/`run.sh` take the title, version and modules from `game_check.py`
(`--info`, `--modules`), default to `orig/CUSA03528`, no ultrawide, render-res or 60 FPS-vblank
logic. The Windows launcher is `Deadpool-PS4-PORT.exe` (target `port-launcher`): one game folder
(no base + update), Deadpool's five languages, 16:9 outputs, upscaling off or FSR 1, no trophy
list built in. The Linux launcher, in-game menu title, DLSS bridge name, portable package,
README, CONTRIBUTING and the issue template say Deadpool.
Kept on purpose:
- The CTR-tuned renderer features (FSR 3/4 and DLSS temporal upscaling, frame generation, the
  internal-resolution setting; `vk_ctr_fsr3`, `vk_ctr_framegen`): off, hidden from the launcher
  and the in-game menu unless `BB_UPSCALER_MENU=1`. They find CTR's G-buffer, depth and motion
  vectors by a CTR heuristic: retarget to UE3 or remove later.
- GPU-shim diagnostics with CTR addresses (`bbport_guest_hooks`, `bbport_heap_sites`,
  `bbport_free_check`, the Gnm census): opt-in, and each site is checked byte for byte, so they
  do nothing on Deadpool's executable. Retarget or remove when needed.
- `docs/` (SacredFire's and bbport's notes about CTR and Bloodborne) as history; `scripts/mods.py`
  and a few `tools/*.sh` still carry Bloodborne defaults (CUSA03173).
Verified here: all Python tests pass; run.sh's Python steps run on the EU dump up to
`patches.bin`; the changed GPU-shim files and the Windows launcher pass a compile (syntax)
check with the real headers (MinGW-w64 + libc++ for the launcher). Not verified: a full build.

## Imports still to write (static estimate, 29 of 445 left to the host runtime)
- libkernel: `__Ux86_64_setcontext`, `msync`, `sceKernelUtimes`, `scePthreadGet/Setschedparam`,
  `sigreturn`
- libScePosix: `sem_init/destroy/post/wait/timedwait`
- ErrorDialog (4), Http (`CreateConnection`, `CreateRequest2`, `RemoveRequestHeader`,
  `UriParse`), NpUtility `LookupCreateRequest`, InvitationDialog `Open`, ImeDialog
  `GetPanelSize`: likely fine as "not available" stubs
- AppContent `AddcontMount/Unmount`, SystemService `GetDisplaySafeAreaInfo`, VideoRecording
  `SetInfo`, GameLiveStreaming `GetCurrentStatus`, Voice `GetResourceInfo`, DiscMap `ioKMruft1ek`
  (no name in aerolib)
NpScore and NpInGameMessage are already answered as unavailable by `src/runtime_net.c` (by
prefix); `tools/module_imports.py` knows that now. An unresolved import doesn't stop loading:
it's bound to a trap that stops the game when called.

## Next
- Review and merge `strip-ctr`, then build on Windows (`bash build.sh` in MSYS2 CLANG64).
- Write the missing imports, run `--list-imports` with the built loader, then the first start.

## Rules
- Only my own dumps. Never commit or publish game files or anything derived from them
  (dump folders, `out\`, `user\`, `boot-linked.bin`).
- Commits use `17183580+thegh0sts@users.noreply.github.com`, not my email.
