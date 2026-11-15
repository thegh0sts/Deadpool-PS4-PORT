/* BB_FPS=auto: the engine's own 30 FPS wait on in the main menu, off in gameplay.
 *
 * Skipping UE3's FEngineLoop::Tick wait (scripts/patches.py unlock_fps) leaves the main menu's
 * Scaleform animations stretched and skewed, so the wait is switched live instead of patched out:
 *
 *   call [rax+0x2a8]        ; GetMaxTickRate
 *   vxorps xmm1,xmm1,xmm1
 *   vucomiss xmm0,xmm1
 *   jbe skip_wait           ; 0f 86 rel32: no cap -> no wait
 *
 * jbe <-> jno is one byte (0x86 <-> 0x81). ucomiss always clears OF, so jno is always taken:
 * the wait is skipped. A one-byte store cannot be seen half-written by the game thread.
 *
 * The level comes from the files the game opens: a map package is <name>_m.xxx (lightmaps
 * _m_LM, text _m_LOC_int). UI_FrontEnd_m / UI_FrontEnd_xtra_m are the main menu; any other map
 * is gameplay. Until the first map (logos, intro) the wait stays on. */
#include "runtime.h"
#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <windows.h>
#else
#include <sys/mman.h>
#include <unistd.h>
#endif

static const unsigned char signature[]={0xff,0x90,0xa8,0x02,0x00,0x00, 0xc5,0xf0,0x57,0xc9, 0xc5,0xf8,0x2e,0xc1, 0x0f,0x86,0xf4,0x00,0x00,0x00};
enum { JBE=0x86, JNO=0x81, OPCODE=15, KNOWN=0x788480 };
static int enabled=-1;            /* BB_FPS_AUTO=1 */
static unsigned char *site;       /* the jbe's second opcode byte; NULL: not found */
static volatile int unlocked;     /* the state written last */

/* Bytes readable from p, up to max (0: p is not readable). */
static uint64_t readable_run(const unsigned char *p, uint64_t max) {
#ifdef _WIN32
    MEMORY_BASIC_INFORMATION m;
    if (!VirtualQuery(p,&m,sizeof(m)) || m.State!=MEM_COMMIT || (m.Protect&(PAGE_GUARD|PAGE_NOACCESS)) ||
        !(m.Protect&(PAGE_READONLY|PAGE_READWRITE|PAGE_EXECUTE_READ|PAGE_EXECUTE_READWRITE|PAGE_WRITECOPY|PAGE_EXECUTE_WRITECOPY)))
        return 0;
    uint64_t run=(uint64_t)((const unsigned char *)m.BaseAddress+m.RegionSize-p);
    return run<max ? run : max;
#else
    (void)p; (void)max;
    return 0;  /* only the known offset is checked */
#endif
}
static int readable(const unsigned char *p, uint64_t n) {
#ifdef _WIN32
    while (n) {
        uint64_t run=readable_run(p,n);
        if (!run) return 0;
        p+=run; n-=run;
    }
    return 1;
#else
    (void)p; (void)n;
    return 1;
#endif
}

static void write_site(unsigned char value) {
#ifdef _WIN32
    DWORD old;
    if (!VirtualProtect(site,1,PAGE_EXECUTE_READWRITE,&old)) { printf("FPS auto: VirtualProtect failed\n"); return; }
    *(volatile unsigned char *)site=value;
    VirtualProtect(site,1,old,&old);
    FlushInstructionCache(GetCurrentProcess(),site,1);
#else
    long page=sysconf(_SC_PAGESIZE);
    void *start=(void *)((uintptr_t)site&~(uintptr_t)(page-1));
    if (mprotect(start,(size_t)page,PROT_READ|PROT_WRITE|PROT_EXEC)) { printf("FPS auto: mprotect failed\n"); return; }
    *(volatile unsigned char *)site=value;
    mprotect(start,(size_t)page,PROT_READ|PROT_EXEC);
#endif
}

static int init(void) {
    if (enabled>=0) return enabled;
    const char *e=getenv("BB_FPS_AUTO");
    enabled=e && e[0]=='1';
    if (!enabled) return 0;
    uint64_t size=0;
    unsigned char *image=(unsigned char *)runtime_probe_image(&size), *found=NULL;
    int matches=0;
    /* CUSA03528 01.00: image+0x788480. The image has unmapped gaps between its segments, so
     * another build is searched for only in readable memory. */
    if (image && size>KNOWN+sizeof(signature) && readable(image+KNOWN,sizeof(signature)) &&
        !memcmp(image+KNOWN,signature,sizeof(signature))) { found=image+KNOWN; matches=1; }
    for (uint64_t i=0; !found && image && size>=sizeof(signature) && i<=size-sizeof(signature); ) {
        uint64_t run=readable_run(image+i,size-i);
        if (!run) { i+=4096-((uintptr_t)(image+i)&4095); continue; }
        for (uint64_t j=0; j+sizeof(signature)<=run; ++j)
            if (image[i+j]==signature[0] && !memcmp(image+i+j,signature,sizeof(signature))) {
                if (!found) found=image+i+j;
                ++matches;
            }
        i+=run;
    }
    if (matches!=1) {
        printf("FPS auto: the engine's frame limiter was not found (%d matches); the frame rate stays as the game sets it\n",matches);
        enabled=0;
        return 0;
    }
    site=found+OPCODE;
    printf("FPS auto: engine frame limiter at image+0x%llx; 30 FPS in the main menu, unlocked in gameplay\n",
           (unsigned long long)(found-image));
    return 1;
}

/* Lowercase basename of a guest path, or NULL when it is not a map package (<name>_m.xxx). */
static int map_name(const char *guest, char *out, size_t size) {
    const char *base=strrchr(guest,'/');
    base=base ? base+1 : guest;
    size_t n=strlen(base);
    if (n+1>size || n<7) return 0;
    for (size_t i=0;i<=n;++i) out[i]=(char)tolower((unsigned char)base[i]);
    return !strcmp(out+n-6,"_m.xxx");
}

void runtime_fps_note_open(const char *guest) {
    if (!guest || !init() || !site) return;
    char name[256];
    if (!map_name(guest,name,sizeof(name))) return;
    int game=strncmp(name,"ui_frontend",11)!=0;
    if (__atomic_exchange_n(&unlocked,game,__ATOMIC_SEQ_CST)==game) return;
    write_site(game ? JNO : JBE);
    printf("FPS auto: %s (%s)\n",game ? "gameplay, unlocked" : "main menu, 30 FPS",name);
    fflush(stdout);
}
