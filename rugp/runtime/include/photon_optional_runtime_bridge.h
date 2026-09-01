#ifndef PHOTON_OPTIONAL_RUNTIME_BRIDGE_H
#define PHOTON_OPTIONAL_RUNTIME_BRIDGE_H

#include "photon_v6_runtime_api.h"

typedef struct PhotonOptionalRuntimeReport {
    uint32_t struct_size;
    int32_t init_result;
    PhotonV6RuntimeStatus status;
} PhotonOptionalRuntimeReport;

/* This bridge never turns an image-runtime failure into a font/forwarder failure. */
void photon_optional_runtime_start(const PhotonV6RuntimeConfig *config,
                                   PhotonOptionalRuntimeReport *report);

/* Refreshes the query snapshot without changing the retained init result. */
void photon_optional_runtime_refresh(PhotonOptionalRuntimeReport *report);

#endif
