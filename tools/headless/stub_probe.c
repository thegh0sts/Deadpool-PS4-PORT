/* Headless test builds: the loader's image accessors (src/probe.c), for linking the runtime's C
 * tests without the loader. No game image is loaded in a test. */
#include <string.h>
#include "runtime.h"
uintptr_t runtime_probe_image(uint64_t *size) { if (size) *size = 0; return 0; }
void runtime_probe_read_image(uintptr_t address, void *data, uint64_t size) { (void)address; memset(data, 0, size); }
int runtime_probe_write_image(uintptr_t address, const void *data, uint64_t size) { (void)address; (void)data; (void)size; return 0; }
