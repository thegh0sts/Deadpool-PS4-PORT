# Deadpool-PS4-PORT

**Deadpool (PS4, European edition CUSA03528, version 01.00) as a native PC program**, for Windows
10/11 and Linux. The game's own x86-64 code runs directly on the CPU, a small runtime replaces
the PS4 system libraries, and a renderer derived from shadPS4 translates the PS4 GPU work to Vulkan.

This is a fork of [CTR-NitroFueled-PC](https://github.com/GetLostIn/CTR-NitroFueled-PC) (GetLostIn),
the Windows fork of [SacredFire](https://github.com/T3CHNOLOG1C/SacredFire) (T3CHNOLOG1C), itself
built on [bbport](https://github.com/deadinside28/bloodborne_pc) (deadinside28). Their Crash Team
Racing profile was removed on 2026-11-15; what stays is the loader, the runtime, the Windows layer,
the renderer and the launchers.

> **No game files are included.** You need your own dump of the game.
> Not affiliated with or endorsed by Sony Interactive Entertainment, Activision, Marvel or High Moon
> Studios. *Deadpool* and *PlayStation* are trademarks of their owners, named here only to identify
> the game this software runs.

**Status: work in progress, the game does not start yet.** The game check accepts the EU dump and
the executable is prepared and linked; about 36 of the 445 imports the runtime must serve are not
written yet (`tools/module_imports.py`). See [HANDOFF.md](HANDOFF.md) for where things stand.

## Which game dumps work

- Deadpool **CUSA03528 version 01.00** (European edition), decrypted: `eboot.bin`, `sce_module`
  and `sce_sys\param.sfo` in one folder, or PS4 PKG Tool's `Image0` + `Sc0` layout (the launcher
  flattens it with hard links). `scripts/game_check.py` checks the executable's loaded image.
- Not yet: the North American edition (CUSA03245). Its profile will be added from a clean dump.
- Never: modified repacks (60 FPS, Coalesced.ini edits, PSN calls stubbed out; they carry an
  `sce_sys/changeinfo/changeinfo.xml`), encrypted files or an unextracted `.pkg`.

## How it works

- **Native execution.** The eboot is converted offline (`scripts/prepare.py`) into a flat memory
  image with the game's own PS4 libc and libSceFios2 linked in as native code
  (`scripts/link_modules.py`, the modules named by the game check). No CPU emulation.
- **A runtime** (`src/runtime_*.c`) implements the PS4 OS functions the game calls: memory,
  threads, synchronisation, files, audio, pad, saves, user service, network stubs. Imports are
  resolved by NID and library name; the names come from shadPS4's aerolib list.
- **GPU** (`gpu/`): the vendored shadPS4 video core and shader recompiler with bbport's and
  SacredFire's changes. The temporal upscalers (FSR 3/4, DLSS), frame generation and the
  internal-resolution setting were tuned on Crash Team Racing's renderer: they stay in the code,
  off and out of the menus (`BB_UPSCALER_MENU=1` shows them), until they are retargeted.

## Build and run

Windows (MSYS2 CLANG64): see [packaging/windows/README.md](packaging/windows/README.md).

```bat
git clone --recursive https://github.com/thegh0sts/Deadpool-PS4-PORT.git
cd Deadpool-PS4-PORT
bash build.sh                         &:: in the MSYS2 CLANG64 shell
out\Deadpool-PS4-PORT.exe             &:: the launcher; or: set BB_GAME_DIR=... & python run.py
```

Linux (Vulkan 1.3, SDL3; `shell.nix` lists the build dependencies):

```bash
git clone --recursive https://github.com/thegh0sts/Deadpool-PS4-PORT.git && cd Deadpool-PS4-PORT
bash build.sh
BB_GAME_DIR=/path/to/CUSA03528 bash run.sh
```

`run.sh`/`run.py` check the game, prepare the image (`out/`), compile the selected patches and
start the game. The game folder defaults to `orig/CUSA03528`, else a `Deadpool.PS4-*` folder beside the port (such as `Deadpool.PS4-EU`). Saves and the shader cache go to
`user/`, settings to `bbport.ini`; `BB_DATA_DIR` moves all of them.

Before the first start, `python3 tools/module_imports.py /path/to/CUSA03528` lists the imports
the runtime does not serve yet (a static estimate; the built loader's `--list-imports` is exact).

**In-game menu**: Insert, or L3+R3 on the pad.

## Useful variables

`BB_GAME_DIR`, `BB_USER_DIR`, `BB_DATA_DIR`, `BB_CONFIG`, `BB_SKIP_GAME_CHECK=1`, `BB_GAMEPAD`,
`BB_NEO=1` (PS4 Pro mode), `BB_FRAME_STATS=1`, `BB_CLEAR_SHADER_CACHE=1`, `BB_VK_VALIDATION=1`,
`BB_FULLSCREEN=1`, `BB_PRESENT_MODE`, `BB_TIMEOUT=N`, `BB_PATCHES_DIR`, `BB_UPSCALER_MENU=1`.

## Repository layout

| Path | Contents |
|---|---|
| `src/` | Loader (`probe.c`) and the runtime |
| `scripts/` | Preparation of the game image, module linking, game check, patch compiler, mods |
| `gpu/` | Renderer library: vendored shadPS4 video core (`gpu/VENDOR.txt`) with bbport's and SacredFire's changes, shims, ImGui menu |
| `patches/` | shadPS4/GoldHEN XML patches for the game (none yet) |
| `launcher/` | The Windows launcher (`launcher/windows`, Deadpool-PS4-PORT.exe) and the GTK4 launcher for Linux |
| `packaging/` | Windows portable package, Nix package and AppImage |
| `tools/` | Developer tools: import names, the import check, scripted runs, GPU checks |
| `tests/` | Loader, runtime, patch, game-check and renderer tests |
| `docs/` | Notes inherited from SacredFire (`docs/sacredfire/`) and bbport; they describe CTR and Bloodborne |

Tests: `python3 -m unittest discover -s tests` and `bash build.sh --test`.

## Contributing

**No game files** in issues or pull requests. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Credits and licenses

Licensed under the **GNU GPL v2 or later** ([LICENSE](LICENSE)), as the projects it is built on:

- **[GetLostIn](https://github.com/GetLostIn)**: [CTR-NitroFueled-PC](https://github.com/GetLostIn/CTR-NitroFueled-PC),
  the Windows fork this port starts from (launcher, Windows fixes, upscalers).
- **[T3CHNOLOG1C](https://github.com/T3CHNOLOG1C)**: [SacredFire](https://github.com/T3CHNOLOG1C/SacredFire).
- **[deadinside28](https://github.com/deadinside28)**: [bbport](https://github.com/deadinside28/bloodborne_pc),
  the loader, runtime and renderer SacredFire builds on.
- **[Supermedo](https://github.com/Supermedo)**: the [Windows port of bbport](https://github.com/Supermedo/bloodborne_pc)
  (branch `windows`), whose Windows layer is merged here.
- **[shadPS4](https://github.com/shadps4-emu/shadPS4)**: the video core, the shader recompiler and
  the aerolib import names.
- **[IFreemz](https://github.com/IFreemz)**: [shadPS4-Bloodborne-DLSS-FSR](https://github.com/IFreemz/shadPS4-Bloodborne-DLSS-FSR),
  the DLSS bridge (MIT, `dlss_bridge/`) and NGX loader.
- **[FireBurn/FSR-Vulkan](https://github.com/FireBurn/FSR-Vulkan)**: AMD FidelityFX FSR 3.1, FSR 3.1.6
  frame generation and FSR 4 on Vulkan (MIT); AMD FidelityFX SDK (MIT).
- **NVIDIA DLSS**: `nvngx_dlss.dll` from the [NVIDIA DLSS SDK](https://github.com/NVIDIA/DLSS),
  redistributed under its license when packaged. NVIDIA, DLSS and GeForce RTX are trademarks of
  NVIDIA Corporation. The GPL program contains no NVIDIA code: it loads the separate bridge DLL
  when present.
- [sirit](https://github.com/shadps4-emu/sirit), [half](https://half.sourceforge.net/),
  [LibAtrac9](https://github.com/Thealexbarney/LibAtrac9) (MIT), [Dear ImGui](https://github.com/ocornut/imgui)
  (MIT), DejaVu fonts, [miniz](https://github.com/richgel999/miniz) (MIT).
- CTR-NitroFueled-PC contributors MetaHeart (CPUs without MOVBE/BMI1/LZCNT) and Naif Alqurashi
  (damaged dump detection).
