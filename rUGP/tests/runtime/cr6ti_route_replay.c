/* Private artwork; real C entry/commit with synthetic owner and destination.
 * No game execution, original decoder, assembly ABI or runtime initialization. */
#if defined(PHOTON_BUILD_PM)
#include "../../runtime/src/photon_v6_pm_native_runtime.c"
#else
#include "../../runtime/src/photon_v6_pf_native_runtime.c"
#endif
#include "photon_v6_exact_rgba_sidecar_loader.h"
#include <stdio.h>

static int filled(const BYTE *p, size_t n, BYTE v) {
    for (size_t i=0;i<n;++i) if (p[i]!=v) return 0;
    return 1;
}
/* Independent numeric oracle for a uniform 0x5a background. */
static BYTE expected_channel(const BYTE *s, unsigned channel, int compose) {
    unsigned a=((unsigned)s[3]*128+127)/255;
    if (!compose) return a ? (channel==3 ? (BYTE)a : s[channel]) : 0;
    if (channel==3) return (BYTE)(a>90?a:90);
    if (a==128) return s[channel];
    int product=((int)s[channel]-90)*(int)a;
    return (BYTE)(90+(product>=0 ? product/128 : -((-product+127)/128)));
}
int wmain(int argc,wchar_t **argv) {
    if (argc!=6) return 2;
    uint32_t n=wcstoul(argv[3],NULL,10), w=wcstoul(argv[4],NULL,10), h=wcstoul(argv[5],NULL,10);
    if (!n || n>128U*1024U*1024U || !w || !h || w>16384 || h>16384 ||
        wcslen(argv[1])>=ARRAYSIZE(ordinary_root)) return 2;
    wcscpy(ordinary_root,argv[1]);
    FILE *f=_wfopen(argv[2],L"rb");
    BYTE *payload=HeapAlloc(GetProcessHeap(),0,n);
    if (!f || !payload || fread(payload,1,n,f)!=n || fgetc(f)!=EOF) return 3;
    fclose(f);
    PhotonV6ExactRgbaImage source={0};
    if (photon_v6_exact_rgba_sidecar_load(argv[1],
        (PhotonV6ExactRgbaGame)PHOTON_NATIVE_ROUTE_GAME,n,fnv1a64(payload,n),&source)!=0 ||
        source.width!=w || source.height!=h) return 4;
    InitializeCriticalSection(&state_lock); lock_ready=1;
    BYTE object[0x80]={0};
    *(void **)(object+0x18)=payload;
    *(void **)(object+0x20)=object+0x60;
    *(uint32_t *)(object+0x58)=n;
    unsigned count=0, failures=0;
    puts("{\"cases\":[");
    for (int active=0;active<2;++active)
    for (int alt=0;alt<2;++alt)
    for (int compose=0;compose<2;++compose)
    for (int sign=-1;sign<=1;sign+=2)
    for (int slack=0;slack<=16;slack+=16) {
        initialized=1; shutting_down=0; fatal_latch=0; native_semantic_gate_disabled=0;
        size_t row=(size_t)w*4+slack, span=row*h;
        BYTE *memory=HeapAlloc(GetProcessHeap(),0,span+256);
        if (!memory) return 5;
        memset(memory,0x5a,span+256);
        BYTE *zero=memory+128+(sign<0?(h-1)*row:0);
        int stride=sign*(int)row;
        bind_object(object,payload,n,fnv1a64(payload,n),1,0,NULL,NULL,NULL);
        ObjectBinding binding;
        if (!find_binding(object,&binding) || (active && !push_active(&binding))) return 6;
        uint32_t rb=w|(h<<16), a1=(uint32_t)(uintptr_t)zero, a2=(uint32_t)-stride;
        BYTE metadata[10]={0}; metadata[7]=(BYTE)compose;
        void *prepared=alt ? photon_v6_pf_alt_decode_prepare(object+0x60,metadata,a1,a2,0,rb)
            : photon_v6_pf_decode_prepare(object+0x60,a1,a2,0,rb,0,rb,compose?0:1);
        int before=filled(memory,span+256,0x5a);
        /* Simulate original decoder overwriting the canvas; composition must
         * still use the pre-decoder background captured by prepare. */
        for (uint32_t y=0;y<h;++y) memset(zero+(intptr_t)y*stride,0x33,(size_t)w*4);
        if (prepared) photon_v6_pf_decode_commit(prepared);
        if (active) pop_active();
        int pixels=1;
        for (uint32_t y=0;y<h && pixels;++y) {
            BYTE *dst=zero+(intptr_t)y*stride;
            const BYTE *src=source.pixels+(size_t)y*source.stride;
            for (uint32_t x=0;x<w && pixels;++x)
                for (unsigned c=0;c<4;++c)
                    if (dst[x*4+c]!=expected_channel(src+x*4,c==0?2:c==2?0:c,compose)) {pixels=0;break;}
            if (!filled(dst+(size_t)w*4,slack,0x5a)) pixels=0;
        }
        int guards=filled(memory,128,0x5a)&&filled(memory+128+span,128,0x5a);
        int good=prepared&&before&&pixels&&guards&&!fatal_latch;
        if (!good) ++failures;
        printf("%s{\"active\":%d,\"alt\":%d,\"compose\":%d,\"sign\":%d,\"slack\":%d,\"prepared\":%s,\"pixels_ok\":%s,\"guards_ok\":%s,\"before_clean\":%s,\"passed\":%s}",
            count++?",\n":"",active,alt,compose,sign,slack,prepared?"true":"false",
            pixels?"true":"false",guards?"true":"false",before?"true":"false",good?"true":"false");
        HeapFree(GetProcessHeap(),0,memory);
    }
    printf("\n],\"required_failures\":%u}\n",failures);
    photon_v6_exact_rgba_image_free(&source);
    HeapFree(GetProcessHeap(),0,payload); DeleteCriticalSection(&state_lock);
    return failures?1:0;
}
