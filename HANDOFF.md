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

## First boot (2026-11-15, branch `first-boot`)
Run here with the headless build (`tools/headless/build.sh`: the real loader and runtime, stand-ins
for the GPU library, SDL3 and the Vulkan check; `--cpu-only`), on the EU dump:
- Fixed: the runtime read the libc param at SceProcParam +0x30 (the stack size for this SDK) and
  crashed before the game's entry; it now follows shadPS4's layout (+0x38) and checks the block.
- Deadpool then runs its C++ static initialisation (1,125 handlers), starts 11 threads (8 pool
  threads, Fios), loads its system modules, logs user 1 in, allocates 3.4 GB of direct memory
  and stops at its first graphics call, `sceGnmDrawInitDefaultHardwareState200`, which the real
  GPU library provides.
- Implemented (all checked against the Windows headers too): POSIX semaphores (`sem_*`, with a
  test: `sema-test --posix`), `scePthreadGet/Setschedparam`, `msync`/`sceKernelMsync`,
  `sceKernelUtimes`/`utimes`, `select` offline (the classic sleep), AppContent add-on
  mount/unmount, the error dialog, `sceInvitationDialogOpen`, `sceImeDialogGetPanelSize`, the
  display safe area, live-streaming status, video-recording SetInfo, voice resource info, and the
  older PSN/HTTP request calls Deadpool uses (signed out / unplugged, as the rest).
- Loader report (`--list-imports`): 391 runtime, 178 native, 65 unresolved: 62 graphics
  (GnmDriver, VideoOut, `sceKernelCreateEqueue`: the GPU library's) and `sigreturn`,
  `__Ux86_64_setcontext` (exception unwinding only; shadPS4 has neither).
- The runtime's C tests did not link against `runtime_net.c` any more (it calls the loader's image
  accessors); `tools/headless/stub_probe.c` provides them for test builds.

## Next
- Build on Windows (`bash build.sh` in MSYS2 CLANG64) and start the game: the next stops are
  graphics (shadPS4's GnmDriver/VideoOut on UE3's command buffers) and the game data
  (`TransGame/`, read through Fios).
- Headless, to go further without a GPU: a null GPU in `tools/headless` (Gnm calls accepted,
  VideoOut flips completed, kernel event queues) would let the CPU side run into loading.

## Rules
- Only my own dumps. Never commit or publish game files or anything derived from them
  (dump folders, `out\`, `user\`, `boot-linked.bin`).
- Commits use `17183580+thegh0sts@users.noreply.github.com`, not my email.

## Title-screen corruption (2026-11-15)

Black wedges and grey slabs on alternating frames. The frame capture showed UE3 clearing stencil
with a compute shader (b4539088c3c6baca) that writes zeros over the stencil plane of the
960x540 and 1920x1080 D32S8 depth targets. The texture cache never applied that write to the
depth images' stencil aspect, so the light-volume stencil was never cleared and shadow
projections darkened everything outside each light. Fix: `TextureCache::RefreshStencil`
(texture_cache.cpp) copies the GPU-written stencil bytes into the depth image when it is next
bound (`Runtime::UploadStencil`). The log says "Stencil sync: ..." the first 4 times it fires.
The copy is linear (no detiling): exact for fills, not for patterned stencil data.

The "Guest write check: EOS fence" lines are expected for UE3 and are now reported 4 times only.

Update: the wedges were not the stencil (that fix stays: it is correct, but changed nothing
visible). Live bisection with `BB_TOGGLE_FILE` found them: bit 4096 (PreparedResources) or 8192
(DrawPreparation) off removes them. The draw-preparation workers read each draw's vertex V#s
through the user-data pointer from guest memory ahead of the GPU thread, and that read is not
covered by the flattened-user-data check. UE3 writes the V# tables into command buffers it
reuses every other frame, so the workers read a stale table: meshes drawn from the wrong
streams. `ResolveVertexBuffers` now compares the worker's V#s with the in-order ones and falls
back on any difference ("Draw preparation: stale vertex V#s ..." in the log).

Title-screen UI (logo, brush stroke, button icon missing): the Scaleform UI's vertex shader
9f40cdb7 fetches 16-bit SINT positions whose V# selects w = SEL_1. The recompiler filled that
with the bits of 1.0f, which the shader then converts as an integer (1065353216.0), so every
such quad collapsed. `ApplySwizzle` now takes `integer` (vertex fetch of SINT/UINT formats
without conversion) and uses integer 1. `Shader::Profile::port_recompiler_revision` was added
so pipeline caches from older builds are rebuilt (bump it when the recompiler output changes).
Not changed yet: the same float-one default in buffer-format loads (lower_buffer_format_to_raw)
and storage image reads.

Occlusion queries (first level: huge light coronas/lens flares everywhere): ZPASS_DONE events
were answered by a stand-in counter (always "millions visible"); answering "nothing visible"
instead (toggle-file experiment bit 1) culled almost the whole level, so UE3 uses the queries
for visibility culling as well as corona fading. `vk_occlusion.{h,cpp}` implements them with
Vulkan occlusion queries: the event at A begins a query, the one at A+8 ends it; the scheduler's
CarriedScope ends and restarts the Vulkan query at render pass / command buffer boundaries, and
the summed count is written to render backend 0's end word after the GPU finishes
(SignalAfterGpu). BB_OCCLUSION=0 restores the stand-in.

## Ultrawide 21:9 (first build, untested)

Launcher: Settings > Display > "Game resolution" (launcher.ini `screen_size`) sets
`BB_SCREEN_SIZE` (run.py / run.sh -> scripts/patches.py `--builtin screen_size=WxH`). Offered:
1920x1080 (original), 2560x1080, 3440x1440, 3840x1600.

- Screen size: the game's GScreenWidth/GScreenHeight (0x24e0578 / 0x24e057c) are set once, to
  1920x1080, by the function at image+0x758bb0; nothing else hard-codes 1080p. The RHI init
  (image+0x741950) sizes the back buffers from them (0x24e0904 / 0x24e0908), so the display
  buffers follow and the port's presenter fits the frame to the window by its aspect.
- Hor+: the player's view (image+0x2dc4b1, ULocalPlayer::CalcSceneView's FPerspectiveMatrix)
  keeps the horizontal FOV: M00 = 1.0 / tan(FOV/2), M11 from the view's width and height. The
  load of that 1.0 (image+0x2dc57b, "vmovss <1.0>(%rip),%xmm1"; the constant is shared) is pointed
  at a read-only float equal to 16H/(9W) (exact for 2560x1080; within 0.03% for the others),
  searched for in the literals after the PLT. The vertical FOV stays that of 16:9.
- The constrained-aspect branch (0x278 flag 2, aspect at 0x280: cutscene cameras) is left as it
  is: those cameras should come out pillarboxed.
- Unknown until tested: the HUD and menus (Scaleform: centred at 16:9 or stretched), Bink videos
  (likely stretched), GPU memory at 3840x1600 (render targets ~3x those of 1080p), other
  projections that may need the same change (0x2dd2b3: fixed 45-degree FOV; 0x2e8c02; 0x3bc3a1).

## Keyboard and mouse (parked)

The launcher's Keyboard page was removed and keyboard/mouse bindings are on hold until the user
has the official PC controls of Deadpool to copy. The runtime still has its default keys
(src/runtime_pad.c bind_defaults, bbport.ini key.* lines); the launcher's KeyboardTab() is kept,
unused, for when the page comes back with Deadpool's actions.

## Frame rate by level (BB_FPS=auto, default)
Skipping UE3's FEngineLoop::Tick wait (`unlock_fps`) stretches and skews the main menu's
animations. `src/runtime_fps.c` switches that wait live instead: the `jbe` after GetMaxTickRate
(image+0x78848f, located by signature) becomes `jno` (always taken after ucomiss, so no wait) in
gameplay and goes back to `jbe` in the main menu. The level comes from the map packages the game
opens (`<name>_m.xxx`): `UI_FrontEnd_m`, `UI_FrontEnd_xtra_m` and the menu's backdrops `UI_Apartment_ART_m` /
`UI_Centerpiec_ART_m` are the menu; other `UI_` maps (death, challenge screens) change nothing; any
other map is gameplay. The log says `FPS auto: ...` on each switch. The pause menu is fine unlocked (tested). Untested: the in-game frame pacing of cutscenes. Other modes: `uncap` (always
unlocked), `60` (illusion's flip-rate patch), `30`.
