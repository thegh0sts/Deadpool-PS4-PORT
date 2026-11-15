/* Headless development build (tools/headless/build.sh): the GPU library's C interface without a
 * GPU. Nothing is resolved here, so the game's GnmDriver/VideoOut/kernel event queue imports
 * stay unresolved and stop the game when it first calls them; the CPU side runs until then. */
#include <stdint.h>
#include "gpu/bbgpu.h"
void bbgpu_register_kernel(void) {}
int bbgpu_init(const BbGpuConfig *config) { (void)config; return 0; }
uintptr_t bbgpu_resolve(const char *scoped_nid) { (void)scoped_nid; return 0; }
int bbgpu_handle_fault(void *ucontext, void *address) { (void)ucontext; (void)address; return 0; }
void bbgpu_dump_guest_writes(void *ucontext) { (void)ucontext; }
int bbgpu_text_input_begin(const char *initial_utf8, const char *prompt_utf8) { (void)initial_utf8; (void)prompt_utf8; return 0; }
int bbgpu_text_input_poll(char *out_utf8, uint64_t size) { (void)out_utf8; (void)size; return 2; }
int bbgpu_overlay_captures_input(void) { return 0; }
int bbgpu_pad_rescan_take(void) { return 0; }
void bbgpu_notify(const char *title_utf8, const char *name_utf8, const char *detail_utf8, int kind,
                  const void *png, uint64_t png_size) {
    (void)title_utf8; (void)name_utf8; (void)detail_utf8; (void)kind; (void)png; (void)png_size;
}
void bbgpu_patch_image(unsigned char *image, uint64_t size) { (void)image; (void)size; }
unsigned bbgpu_symbol_count(void) { return 0; }
int vulkan_smoke(void) { return 1; }
