/* Private-input, game-free replay of the compiled prepare/commit code.
 * Deliberately does not install hooks or execute a proprietary decoder/ABI. */
#if defined(PHOTON_BUILD_PM)
#include "../../runtime/src/photon_v6_pm_native_runtime.c"
#else
#include "../../runtime/src/photon_v6_pf_native_runtime.c"
#endif
#include "photon_v6_exact_rgba_sidecar_loader.h"
#include <stdio.h>

static int filled(const BYTE *p, size_t n, BYTE value) {
    for (size_t i=0;i<n;++i) if (p[i]!=value) return 0;
    return 1;
}
static void reset_replay(void) {
    initialized=1; shutting_down=0; fatal_latch=0; native_semantic_gate_disabled=0;
}
static void *prepare_case(int direct, BYTE *payload, uint32_t bytes,
    BYTE *zero, int stride, uint32_t lt, uint32_t rb) {
    if (direct) return photon_v6_pf_crip008_direct_decode_prepare(
        payload,bytes,NULL,zero,-stride,lt,rb);
    return photon_v6_pf_crip008_decode_prepare(
        payload,bytes,NULL,zero,-stride,lt,rb,lt,rb,1);
}

int wmain(int argc, wchar_t **argv) {
    if (argc!=10) return 2;
    uint32_t n=wcstoul(argv[3],NULL,10), w=wcstoul(argv[4],NULL,10),
        h=wcstoul(argv[5],NULL,10), x0=wcstoul(argv[6],NULL,10),
        y0=wcstoul(argv[7],NULL,10), dw=wcstoul(argv[8],NULL,10),
        dh=wcstoul(argv[9],NULL,10);
    if (!n || n>128U*1024U*1024U || !w || !h || w>16384 || h>16384 ||
        !dw || !dh || x0>w || y0>h || dw>w-x0 || dh>h-y0 ||
        wcslen(argv[1])>=ARRAYSIZE(ordinary_root)) return 2;
    wcscpy(ordinary_root,argv[1]);
    FILE *f=_wfopen(argv[2],L"rb");
    BYTE *payload=HeapAlloc(GetProcessHeap(),0,(size_t)n+4);
    if (!f || !payload || fread(payload,1,n,f)!=n) return 3;
    if (fgetc(f)!=EOF) return 3;
    fclose(f);
    memset(payload+n,0x9b,4);
    PhotonV6ExactRgbaImage source={0};
    if (photon_v6_exact_rgba_sidecar_load(argv[1],
        (PhotonV6ExactRgbaGame)PHOTON_NATIVE_ROUTE_GAME,n,
        fnv1a64(payload,n),&source)!=0 || source.width!=w || source.height!=h) return 4;
    uint32_t lt=x0|(y0<<16), rb=(x0+dw)|((y0+dh)<<16);
    unsigned failures=0, number=0;
    puts("{\"cases\":[");
    for (int direct=0;direct<2;++direct)
    for (int sign=-1;sign<=1;sign+=2)
    for (int slack=0;slack<=16;slack+=16)
    for (int variant=0;variant<6;++variant) {
        /* 0=exact, 1/2=extra 2/3 bytes, 3=extra 4, 4=wrong identity,
         * 5=payload changes between prepare and commit. */
        uint32_t extra=variant==1?2U:variant==2?3U:variant==3?4U:0U;
        size_t row=(size_t)w*4+(size_t)slack;
        size_t span=row*h, bytes=span+256;
        BYTE *memory=HeapAlloc(GetProcessHeap(),0,bytes);
        if (!memory) return 5;
        memset(memory,0x5a,bytes);
        BYTE *zero=memory+128+(sign<0?(h-1)*row:0);
        int stride=sign*(int)row;
        reset_replay();
        if (variant==4) payload[0]^=1;
        void *prepared=prepare_case(direct,payload,n+extra,zero,stride,lt,rb);
        if (variant==4) payload[0]^=1;
        int before_clean=filled(memory,bytes,0x5a);
        if (variant==5) payload[n-1]^=1;
        if (prepared) photon_v6_pf_crip008_decode_commit(prepared);
        if (variant==5) payload[n-1]^=1;
        int expected_reject=variant==3 || variant==4;
        int verify_copy=prepared && variant!=5;
        int pixels_ok=1;
        for (uint32_t y=0;y<h && pixels_ok;++y) {
            BYTE *actual=zero+(intptr_t)y*stride;
            const BYTE *expected=source.pixels+(size_t)y*source.stride;
            for (uint32_t x=0;x<w;++x) {
                int covered=verify_copy && x>=x0 && x<x0+dw && y>=y0 && y<y0+dh;
                if (actual[x*4]!=(covered?expected[x*4+2]:0x5a) ||
                    actual[x*4+1]!=(covered?expected[x*4+1]:0x5a) ||
                    actual[x*4+2]!=(covered?expected[x*4]:0x5a) ||
                    actual[x*4+3]!=(covered?expected[x*4+3]:0x5a)) { pixels_ok=0; break; }
            }
            if (!filled(actual+w*4,(size_t)slack,0x5a)) pixels_ok=0;
        }
        int guards_ok=filled(memory,128,0x5a)&&filled(memory+128+span,128,0x5a);
        int mutation_ok=variant!=5 || (prepared && fatal_latch);
        int required_ok=(variant!=0 || prepared) && (!expected_reject || !prepared);
        int fatal_ok=variant==5 || !fatal_latch;
        int safe=before_clean&&pixels_ok&&guards_ok&&mutation_ok&&required_ok&&fatal_ok;
        if (!safe) ++failures;
        printf("%s{\"direct\":%d,\"stride_sign\":%d,\"row_slack\":%d,\"variant\":%d,\"prepared\":%s,\"before_clean\":%s,\"pixels_ok\":%s,\"guards_ok\":%s,\"fatal\":%ld,\"passed\":%s}",
            number++?",\n":"",direct,sign,slack,variant,prepared?"true":"false",
            before_clean?"true":"false",pixels_ok?"true":"false",guards_ok?"true":"false",(long)fatal_latch,safe?"true":"false");
        HeapFree(GetProcessHeap(),0,memory);
    }
    printf("\n],\"required_failures\":%u,\"runtime_initialization_exercised\":false,\"assembly_wrapper_executed\":false,\"proprietary_decoder_executed\":false}\n",failures);
    photon_v6_exact_rgba_image_free(&source);
    HeapFree(GetProcessHeap(),0,payload);
    return failures?1:0;
}
