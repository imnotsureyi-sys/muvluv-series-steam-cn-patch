/* Compile the actual selector preconditions in their own translation unit. */
#if defined(PHOTON_BUILD_PM)
#include "../../runtime/src/photon_v6_pm_selector_adapter.c"
#else
#include "../../runtime/src/photon_v6_pf_selector_adapter.c"
#endif

static int prepare_offline(void) {
#if defined(PHOTON_BUILD_PM)
    return prepare_hook();
#else
    int okay=prepare_hooks()==0;
    free_trampolines();
    return okay;
#endif
}

int selector_sites_offline(BYTE *image) {
#if defined(PHOTON_BUILD_PM)
    uint32_t sites[]={PM_TYPED_SETTER_CALLSITE_RVA};
#else
    uint32_t sites[]={PF_CREF_READ_RVA,PF_SELECTOR_GRAPH_ROOT_SERIALIZE_RVA,
        PF_CREF_RESOURCE_MATERIALIZER_CALLSITE_RVA,PF_TYPED_SETTER_CALLSITE_RVA};
#endif
    main_base=image;
    if (!verify_image(image) || !prepare_offline()) return 0;
    for (unsigned i=0;i<sizeof(sites)/sizeof(sites[0]);++i) {
        image[sites[i]]^=1;
        int rejected=!prepare_offline();
        image[sites[i]]^=1;
        if (!rejected) return 0;
    }
    return prepare_offline() ? (int)(sizeof(sites)/sizeof(sites[0])) : 0;
}
