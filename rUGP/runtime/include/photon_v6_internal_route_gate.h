#ifndef PHOTON_V6_INTERNAL_ROUTE_GATE_H
#define PHOTON_V6_INTERNAL_ROUTE_GATE_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum PhotonV6RouteGame {
    PHOTON_V6_ROUTE_GAME_PF = 1,
    PHOTON_V6_ROUTE_GAME_PM = 2
} PhotonV6RouteGame;

typedef enum PhotonV6RouteSlot {
    PHOTON_V6_ROUTE_SLOT_JAPANESE = 1,
    PHOTON_V6_ROUTE_SLOT_TRANSLATION = 2
} PhotonV6RouteSlot;

typedef enum PhotonV6RouteTransport {
    PHOTON_V6_ROUTE_TRANSPORT_ORDINARY_EXACT_PAYLOAD = 1,
    PHOTON_V6_ROUTE_TRANSPORT_SPECIAL57_OWNER_OR_CONTEXT = 2,
    PHOTON_V6_ROUTE_TRANSPORT_OFFLINE_EXACT_OWNER = 3
} PhotonV6RouteTransport;

typedef enum PhotonV6RouteGateStatus {
    PHOTON_V6_ROUTE_GATE_ALLOW_ORDINARY_TRANSLATION_PAYLOAD = 0,
    PHOTON_V6_ROUTE_GATE_INVALID_ARGUMENT = 1,
    PHOTON_V6_ROUTE_GATE_JAPANESE_NEVER_OVERLAY = 2,
    PHOTON_V6_ROUTE_GATE_ORDINARY_IDENTITY_NOT_EXACT = 3,
    PHOTON_V6_ROUTE_GATE_SPECIAL_INTERNAL_SELECTOR_UNPROVEN = 4,
    PHOTON_V6_ROUTE_GATE_OFFLINE_OWNER_NEVER_RUNTIME_WRITE = 5,
    PHOTON_V6_ROUTE_GATE_UNKNOWN_TRANSPORT = 6
} PhotonV6RouteGateStatus;

typedef struct PhotonV6RouteGateRequest {
    uint32_t struct_size;
    uint32_t game;
    uint32_t slot;
    uint32_t transport;
    uint32_t ordinary_loader_identity_exact;
    uint32_t reserved[3];
} PhotonV6RouteGateRequest;

typedef struct PhotonV6RouteGateDecision {
    uint32_t struct_size;
    uint32_t status;
    uint32_t overlay_allowed;
    uint32_t japanese_overlay_allowed;
    uint32_t external_marker_consumed;
    uint32_t special_selector_compiled;
    uint32_t ordinary_identity_required;
    uint32_t reserved;
} PhotonV6RouteGateDecision;

typedef struct PhotonV6RouteGateCounters {
    uint32_t struct_size;
    uint32_t calls;
    uint32_t ordinary_allowed;
    uint32_t japanese_rejected;
    uint32_t ordinary_identity_rejected;
    uint32_t special_unproven_rejected;
    uint32_t offline_owner_rejected;
    uint32_t invalid_rejected;
} PhotonV6RouteGateCounters;

/*
 * Production v1 boundary.
 *
 * This API deliberately has no action marker, nonce, context string, source
 * asset ID, language global, or caller-provided "authenticated" flag.  The
 * only enabled route is the ordinary exact-payload table already accepted by
 * the frozen V6 runtime resource index as requiring no special evidence.
 * Japanese and every special57/offline-exact route are rejected.
 *
 * A later internal selector must replace this compilation unit after its own
 * native owner/action/context evidence is sealed.  It must not add an
 * externally forgeable authorization parameter to this interface.
 */
PhotonV6RouteGateStatus photon_v6_internal_route_gate(
    const PhotonV6RouteGateRequest *request,
    PhotonV6RouteGateDecision *decision);

void photon_v6_internal_route_gate_query(PhotonV6RouteGateCounters *counters);

#ifdef __cplusplus
}
#endif

#endif
