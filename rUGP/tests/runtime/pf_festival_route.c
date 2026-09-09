/* Local private-input regression: arguments are bundle root and PF archive.
 * Uses authenticated installed PNGs; never runs a proprietary decoder. */
#include "../../runtime/src/photon_v6_pf_native_runtime.c"
#include "photon_v6_exact_rgba_sidecar_loader.h"
#include <stdio.h>
#define CHECK(x) do { if (!(x)) { fwprintf(stderr,L"check line %d failed\n",__LINE__); return 1; } } while (0)

int wmain(int argc, wchar_t **argv) {
    const uint32_t offsets[2] = {0x1fa3b718,0x1fbdfe74};
    const uint32_t lengths[2] = {698581,88785};
    const uint64_t hashes[2] = {UINT64_C(0xF65147B1D6AFBA5A),UINT64_C(0xA3CEF04B988F1823)};
    const uint32_t full_rect = UINT32_C(0x02580320);
    const size_t surface_bytes = 800U * 600U * 4U;
    CHECK(argc == 3);
    CHECK(wcslen(argv[1]) < ARRAYSIZE(ordinary_root));
    wcscpy(ordinary_root,argv[1]);
    FILE *archive = _wfopen(argv[2], L"rb");
    CHECK(archive);
    for (int which=0; which<2; ++which) {
        BYTE *payload=HeapAlloc(GetProcessHeap(),0,lengths[which]+4);
        BYTE *memory=HeapAlloc(GetProcessHeap(),0,surface_bytes);
        PhotonV6ExactRgbaImage source={0};
        CHECK(payload && memory);
        CHECK(_fseeki64(archive,(int64_t)offsets[which]+41,SEEK_SET)==0);
        CHECK(fread(payload,1,lengths[which],archive)==lengths[which]);
        CHECK(fnv1a64(payload,lengths[which])==hashes[which]);
        CHECK(photon_v6_exact_rgba_sidecar_load(argv[1],PHOTON_V6_EXACT_RGBA_GAME_PF,lengths[which],hashes[which],&source)==0);
        for (int sign=-1; sign<=1; sign+=2) for (int padding=0;padding<=3;padding++) {
            if (padding==1) continue;
            int stride=sign*3200;
            BYTE *zero=sign<0 ? memory+599*3200 : memory;
            uint32_t lt=which ? 0x0072004a : 0;
            uint32_t rb=which ? 0x016f0132 : full_rect;
            memset(payload+lengths[which],0x9b,4); /* padding need not be zero */
            memset(memory,0x5a,surface_bytes);
            initialized=1; shutting_down=0; fatal_latch=0; native_semantic_gate_disabled=0;
            void *prepared=photon_v6_pf_crip008_direct_decode_prepare(payload,lengths[which]+padding,NULL,zero,-stride,lt,rb);
            CHECK(prepared && !fatal_latch);
            for (size_t i=0;i<surface_bytes;++i) CHECK(memory[i]==0x5a);
            photon_v6_pf_crip008_decode_commit(prepared);
            CHECK(!fatal_latch);
            for (unsigned y=0;y<600;++y) for (unsigned x=0;x<800;++x) {
                BYTE *at=zero+(intptr_t)y*stride+x*4;
                BYTE *rgba=source.pixels+(y*800+x)*4;
                int covered=!which || (x>=74 && x<306 && y>=114 && y<367);
                CHECK(at[0]==(covered ? rgba[2]:0x5a));
                CHECK(at[1]==(covered ? rgba[1]:0x5a));
                CHECK(at[2]==(covered ? rgba[0]:0x5a));
                CHECK(at[3]==(covered ? rgba[3]:0x5a));
            }
        }
        /* Unknown content, an unproved padding extent and shifted rectangles
         * must not turn into a prefix match or a partial write. */
        initialized=1; fatal_latch=0;
        CHECK(!photon_v6_pf_crip008_direct_decode_prepare(payload,lengths[which]+4,NULL,memory,-3200,which?0x0072004a:0,which?0x016f0132:full_rect));
        payload[0]^=1;
        CHECK(!photon_v6_pf_crip008_direct_decode_prepare(payload,lengths[which]+3,NULL,memory,-3200,which?0x0072004a:0,which?0x016f0132:full_rect));
        payload[0]^=1;
        if (which) CHECK(!photon_v6_pf_crip008_direct_decode_prepare(payload,lengths[which]+3,NULL,memory,-3200,0x0072004b,0x016f0132));
        photon_v6_exact_rgba_image_free(&source);
        HeapFree(GetProcessHeap(),0,payload); HeapFree(GetProcessHeap(),0,memory);
    }
    fclose(archive);
    puts("{\"passed\":true,\"full_and_partial\":true,\"padding_0_2_3\":true,\"both_pitch_signs\":true,\"outside_unchanged\":true,\"unknown_identity_rejected\":true,\"proprietary_decoder_executed\":false}");
    return 0;
}
