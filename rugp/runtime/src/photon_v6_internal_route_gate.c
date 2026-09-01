#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include <stdint.h>
#include <string.h>

#include "photon_v6_internal_route_gate.h"

#if !defined(__i386__) && !defined(_M_IX86)
#error photon_v6_internal_route_gate must use the 32-bit Windows ABI.
#endif

static volatile LONG gate_calls;
static volatile LONG ordinary_allowed;
static volatile LONG japanese_rejected;
static volatile LONG ordinary_identity_rejected;
static volatile LONG special_unproven_rejected;
static volatile LONG offline_owner_rejected;
static volatile LONG invalid_rejected;

static PhotonV6RouteGateStatus finish(
    PhotonV6RouteGateDecision *decision,
    PhotonV6RouteGateStatus status,
    int allowed) {
    memset(decision, 0, sizeof(*decision));
    decision->struct_size = sizeof(*decision);
    decision->status = (uint32_t)status;
    decision->overlay_allowed = allowed ? 1U : 0U;
    decision->japanese_overlay_allowed = 0;
    decision->external_marker_consumed = 0;
    decision->special_selector_compiled = 0;
    decision->ordinary_identity_required = 1;
    return status;
}

PhotonV6RouteGateStatus photon_v6_internal_route_gate(
    const PhotonV6RouteGateRequest *request,
    PhotonV6RouteGateDecision *decision) {
    InterlockedIncrement(&gate_calls);
    if (!request || !decision ||
        request->struct_size != sizeof(*request) ||
        (request->game != PHOTON_V6_ROUTE_GAME_PF &&
         request->game != PHOTON_V6_ROUTE_GAME_PM) ||
        (request->slot != PHOTON_V6_ROUTE_SLOT_JAPANESE &&
         request->slot != PHOTON_V6_ROUTE_SLOT_TRANSLATION)) {
        if (decision) {
            InterlockedIncrement(&invalid_rejected);
            return finish(decision, PHOTON_V6_ROUTE_GATE_INVALID_ARGUMENT, 0);
        }
        InterlockedIncrement(&invalid_rejected);
        return PHOTON_V6_ROUTE_GATE_INVALID_ARGUMENT;
    }
    if (request->slot == PHOTON_V6_ROUTE_SLOT_JAPANESE) {
        InterlockedIncrement(&japanese_rejected);
        return finish(decision, PHOTON_V6_ROUTE_GATE_JAPANESE_NEVER_OVERLAY, 0);
    }
    if (request->transport ==
            PHOTON_V6_ROUTE_TRANSPORT_ORDINARY_EXACT_PAYLOAD) {
        if (request->ordinary_loader_identity_exact != 1U) {
            InterlockedIncrement(&ordinary_identity_rejected);
            return finish(decision,
                          PHOTON_V6_ROUTE_GATE_ORDINARY_IDENTITY_NOT_EXACT, 0);
        }
        InterlockedIncrement(&ordinary_allowed);
        return finish(decision,
                      PHOTON_V6_ROUTE_GATE_ALLOW_ORDINARY_TRANSLATION_PAYLOAD,
                      1);
    }
    if (request->transport ==
            PHOTON_V6_ROUTE_TRANSPORT_SPECIAL57_OWNER_OR_CONTEXT) {
        InterlockedIncrement(&special_unproven_rejected);
        return finish(decision,
                      PHOTON_V6_ROUTE_GATE_SPECIAL_INTERNAL_SELECTOR_UNPROVEN,
                      0);
    }
    if (request->transport ==
            PHOTON_V6_ROUTE_TRANSPORT_OFFLINE_EXACT_OWNER) {
        InterlockedIncrement(&offline_owner_rejected);
        return finish(decision,
                      PHOTON_V6_ROUTE_GATE_OFFLINE_OWNER_NEVER_RUNTIME_WRITE,
                      0);
    }
    InterlockedIncrement(&invalid_rejected);
    return finish(decision, PHOTON_V6_ROUTE_GATE_UNKNOWN_TRANSPORT, 0);
}

void photon_v6_internal_route_gate_query(PhotonV6RouteGateCounters *counters) {
    if (!counters) return;
    memset(counters, 0, sizeof(*counters));
    counters->struct_size = sizeof(*counters);
    counters->calls = (uint32_t)InterlockedCompareExchange(&gate_calls, 0, 0);
    counters->ordinary_allowed =
        (uint32_t)InterlockedCompareExchange(&ordinary_allowed, 0, 0);
    counters->japanese_rejected =
        (uint32_t)InterlockedCompareExchange(&japanese_rejected, 0, 0);
    counters->ordinary_identity_rejected =
        (uint32_t)InterlockedCompareExchange(&ordinary_identity_rejected, 0, 0);
    counters->special_unproven_rejected =
        (uint32_t)InterlockedCompareExchange(&special_unproven_rejected, 0, 0);
    counters->offline_owner_rejected =
        (uint32_t)InterlockedCompareExchange(&offline_owner_rejected, 0, 0);
    counters->invalid_rejected =
        (uint32_t)InterlockedCompareExchange(&invalid_rejected, 0, 0);
}
