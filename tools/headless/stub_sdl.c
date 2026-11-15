#define _GNU_SOURCE
/* Headless development build (tools/headless/build.sh): the SDL3 functions the runtime calls, with
 * no gamepads, no keyboard and no audio device (the runtime's own fallbacks apply). Compiled
 * against SDL3's real headers, so the signatures are checked. */
#include <SDL3/SDL.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>

static Uint8 no_keys[SDL_SCANCODE_COUNT];
bool SDL_InitSubSystem(SDL_InitFlags flags) { (void)flags; return false; }
void SDL_QuitSubSystem(SDL_InitFlags flags) { (void)flags; }
SDL_InitFlags SDL_WasInit(SDL_InitFlags flags) { (void)flags; return 0; }
const char *SDL_GetError(void) { return "headless build: no SDL"; }
void SDL_free(void *mem) { free(mem); }
int SDL_strcasecmp(const char *a, const char *b) { return strcasecmp(a, b); }
char *SDL_strcasestr(const char *haystack, const char *needle) { return strcasestr(haystack, needle); }
SDL_JoystickID *SDL_GetGamepads(int *count) { if (count) *count = 0; return calloc(1, sizeof(SDL_JoystickID)); }
SDL_Gamepad *SDL_OpenGamepad(SDL_JoystickID id) { (void)id; return NULL; }
void SDL_CloseGamepad(SDL_Gamepad *g) { (void)g; }
bool SDL_GamepadConnected(SDL_Gamepad *g) { (void)g; return false; }
SDL_JoystickID SDL_GetGamepadID(SDL_Gamepad *g) { (void)g; return 0; }
const char *SDL_GetGamepadName(SDL_Gamepad *g) { (void)g; return "none"; }
const char *SDL_GetGamepadNameForID(SDL_JoystickID id) { (void)id; return "none"; }
SDL_GUID SDL_GetGamepadGUIDForID(SDL_JoystickID id) { (void)id; SDL_GUID g; memset(&g, 0, sizeof g); return g; }
void SDL_GUIDToString(SDL_GUID guid, char *out, int size) { (void)guid; if (out && size > 0) out[0] = 0; }
bool SDL_GetGamepadButton(SDL_Gamepad *g, SDL_GamepadButton b) { (void)g; (void)b; return false; }
Sint16 SDL_GetGamepadAxis(SDL_Gamepad *g, SDL_GamepadAxis a) { (void)g; (void)a; return 0; }
SDL_GamepadButton SDL_GetGamepadButtonFromString(const char *s) { (void)s; return SDL_GAMEPAD_BUTTON_INVALID; }
int SDL_GetNumGamepadTouchpads(SDL_Gamepad *g) { (void)g; return 0; }
int SDL_GetNumGamepadTouchpadFingers(SDL_Gamepad *g, int t) { (void)g; (void)t; return 0; }
bool SDL_GetGamepadTouchpadFinger(SDL_Gamepad *g, int t, int f, bool *down, float *x, float *y, float *p) {
    (void)g; (void)t; (void)f; if (down) *down = false; if (x) *x = 0; if (y) *y = 0; if (p) *p = 0; return false;
}
bool SDL_RumbleGamepad(SDL_Gamepad *g, Uint16 lo, Uint16 hi, Uint32 ms) { (void)g; (void)lo; (void)hi; (void)ms; return false; }
const bool *SDL_GetKeyboardState(int *numkeys) { if (numkeys) *numkeys = SDL_SCANCODE_COUNT; return (const bool *)no_keys; }
SDL_Scancode SDL_GetScancodeFromName(const char *name) { (void)name; return SDL_SCANCODE_UNKNOWN; }
const char *SDL_GetCurrentAudioDriver(void) { return NULL; }
SDL_AudioStream *SDL_OpenAudioDeviceStream(SDL_AudioDeviceID dev, const SDL_AudioSpec *spec, SDL_AudioStreamCallback cb, void *ud) {
    (void)dev; (void)spec; (void)cb; (void)ud; return NULL;
}
void SDL_DestroyAudioStream(SDL_AudioStream *s) { (void)s; }
bool SDL_PutAudioStreamData(SDL_AudioStream *s, const void *buf, int len) { (void)s; (void)buf; (void)len; return false; }
int SDL_GetAudioStreamQueued(SDL_AudioStream *s) { (void)s; return 0; }
bool SDL_ResumeAudioStreamDevice(SDL_AudioStream *s) { (void)s; return false; }
