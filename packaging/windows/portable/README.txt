Deadpool PS4 Port - portable package for 64-bit Windows 10 (1903+) / 11
======================================================================
A native port of Deadpool (PS4, European edition CUSA03528, version 01.00).
The game's own code runs directly on your CPU and its graphics go through Vulkan.

WORK IN PROGRESS: the game does not start yet. See HANDOFF.md in the source repository.

REQUIREMENTS (not included: you bring them)
-------------------------------------------
1. Your own dump of the game: CUSA03528, version 01.00, decrypted (eboot.bin, sce_module and
   sce_sys\param.sfo), or extracted with PS4 PKG Tool (Image0 and Sc0: the launcher prepares it).
   Not accepted: another edition (the North American CUSA03245 is not supported yet), an
   unextracted .pkg, encrypted files, or a modified repack (a 60 FPS / no-PSN rebuild with
   sce_sys\changeinfo\changeinfo.xml).
2. A GPU with Vulkan 1.3 and up-to-date drivers.
Python is included (the python\ folder): nothing to install.

GETTING STARTED
---------------
1. Open Deadpool-PS4-PORT.exe (the launcher).
2. Choose your game folder. The launcher checks it and says what it found.
3. Press PLAY. The first start is slow (shaders are compiled and cached in user\).
Without the launcher: put the game in .\CUSA03528 (or set BB_GAME_DIR) and run
"Play without the launcher.bat".

In game, the Insert key or L3+R3 opens the port's menu.

Files: last_run.log has the output of the last start; your saves are in user\savedata\.
