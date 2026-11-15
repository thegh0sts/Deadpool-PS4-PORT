#!/usr/bin/env bash
# Headless development build: the real loader and runtime (src/) linked against stand-ins for the
# GPU library, SDL3 and the Vulkan check (tools/headless/stub_*.c). The game's CPU side runs with
# --cpu-only until its first graphics import, without a GPU, window, gamepad or sound. For finding
# missing imports and runtime bugs on a machine that cannot build the GPU library.
# Warnings are not errors here (compilers differ from the release toolchains).
# Needs: a C compiler and SDL3's headers (SDL3_INCLUDE, default: pkg-config sdl3).
# Output: out/headless/sacredfire-headless.
set -euo pipefail
cd -- "$(dirname -- "$0")/../.."
CC=${CC:-cc}
sdl=${SDL3_INCLUDE:-$(pkg-config --cflags-only-I sdl3 2>/dev/null | sed 's/^-I//;s/ .*//')}
[[ -n $sdl && -f $sdl/SDL3/SDL.h ]] || { echo 'Set SDL3_INCLUDE to the folder holding SDL3/SDL.h.' >&2; exit 1; }
mkdir -p out/headless
"$CC" -std=c11 -O2 -g -Wall -Wextra -Werror -mgeneral-regs-only -c src/isa_emulate.c -o out/headless/isa_emulate.o
if [[ ! -f out/headless/libatrac9.a ]]; then
    rm -rf out/headless/atrac9 && mkdir -p out/headless/atrac9
    for source in third_party/LibAtrac9/C/src/*.c; do
        "$CC" -std=c99 -O2 -g -w -c "$source" -o "out/headless/atrac9/$(basename "${source%.c}").o"
    done
    ar rcs out/headless/libatrac9.a out/headless/atrac9/*.o
fi
runtime=(src/runtime*.c)
"$CC" -std=c11 -O2 -g -Wall -Wextra -pthread -no-pie -I"$sdl" -I. -Isrc src/probe.c "${runtime[@]}" \
    src/cpu_check.c src/isa_rewrite.c out/headless/isa_emulate.o tools/headless/stub_bbgpu.c \
    tools/headless/stub_sdl.c out/headless/libatrac9.a -lm -o out/headless/sacredfire-headless
echo "Built out/headless/sacredfire-headless"
