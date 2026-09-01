#include <string.h>
#include "photon_optional_runtime_bridge.h"

void photon_optional_runtime_start(const PhotonV6RuntimeConfig *config,
                                   PhotonOptionalRuntimeReport *report) {
    PhotonOptionalRuntimeReport local;
    memset(&local, 0, sizeof(local));
    local.struct_size = sizeof(local);
    local.status.struct_size = sizeof(local.status);
    local.init_result = photon_v6_runtime_init(config);
    photon_v6_runtime_query(&local.status);
    if (local.init_result < 0) {
        photon_v6_runtime_shutdown();
        photon_v6_runtime_query(&local.status);
        if (local.status.hooks_installed != 0)
            local.init_result = PHOTON_V6_RUNTIME_CONTRACT_VIOLATION;
    }
    if (report) *report = local;
}

void photon_optional_runtime_refresh(PhotonOptionalRuntimeReport *report) {
    if (!report) return;
    report->struct_size = sizeof(*report);
    report->status.struct_size = sizeof(report->status);
    photon_v6_runtime_query(&report->status);
}
