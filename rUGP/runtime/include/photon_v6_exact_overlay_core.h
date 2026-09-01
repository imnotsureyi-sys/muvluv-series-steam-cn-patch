#ifndef PHOTON_V6_EXACT_OVERLAY_CORE_H
#define PHOTON_V6_EXACT_OVERLAY_CORE_H

#include <stdint.h>
#include <wchar.h>

#include "photon_v6_cpu_surface_rgba.h"
#include "photon_v6_internal_route_gate.h"
#include "photon_v6_surface_transaction.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef enum PhotonV6ExactOverlayStatus {
    PHOTON_V6_EXACT_OVERLAY_OK = 0,
    PHOTON_V6_EXACT_OVERLAY_INVALID_ARGUMENT = 1,
    PHOTON_V6_EXACT_OVERLAY_ROUTE_REJECTED = 2,
    PHOTON_V6_EXACT_OVERLAY_IDENTITY_NOT_TARGETED = 3,
    PHOTON_V6_EXACT_OVERLAY_SIDECAR_FAILED = 4,
    PHOTON_V6_EXACT_OVERLAY_SURFACE_TRANSACTION_FAILED = 5,
    PHOTON_V6_EXACT_OVERLAY_SIDECAR_GEOMETRY_MISMATCH = 6,
    PHOTON_V6_EXACT_OVERLAY_BACKGROUND_READ_FAILED = 7,
    PHOTON_V6_EXACT_OVERLAY_COMPOSITION_FAILED = 8
} PhotonV6ExactOverlayStatus;

typedef struct PhotonV6ExactOverlayRequest {
    uint32_t struct_size;
    uint32_t game;
    uint32_t slot;
    uint32_t transport;
    const wchar_t *ordinary_bundle_root;
    const wchar_t *special57_bundle_root;
    uint32_t payload_bytes;
    uint64_t payload_fnv1a64;
    const char *special_source_asset_id;
    const char *special_context_identity_key;
    const PhotonV6CpuSurfaceView *surface;
    uint32_t rect_x;
    uint32_t rect_y;
    uint32_t expected_width;
    uint32_t expected_height;
    /* Low byte of the retail Cr6Ti decoder's seventh argument.  A non-zero
     * value selects its direct-copy path; zero selects source-over. */
    uint32_t decoder_flags;
} PhotonV6ExactOverlayRequest;

typedef struct PhotonV6ExactOverlayReport {
    uint32_t struct_size;
    uint32_t status;
    uint32_t route_gate_status;
    uint32_t sidecar_status;
    uint32_t sidecar_width;
    uint32_t sidecar_height;
    uint32_t sidecar_rgba_bytes;
    uint32_t destination_committed;
    PhotonV6SurfaceTransactionReport transaction;
} PhotonV6ExactOverlayReport;

/*
 * A Cr6Ti decoder call has two exact destination modes selected by the low
 * byte of its seventh argument.  Zero composites the decoded source over the
 * old destination; non-zero copies the decoded scratch row directly.  In
 * both modes the scratch alpha uses the engine-native 0..128 domain.
 *
 * The native callsite wrapper uses this opaque preparation object in two
 * phases.  prepare() authenticates and loads the exact sidecar and snapshots
 * the destination before the retail decoder runs.  commit_prepared() then
 * converts the authority PNG's conventional 0..255 straight alpha into that
 * 0..128/copy-sentinel domain, reproduces the selected direct-copy or
 * source-over operation, and commits the resulting destination bytes
 * transactionally.
 */
typedef struct PhotonV6ExactOverlayPrepared {
    uint32_t struct_size;
    uint32_t active;
    PhotonV6CpuSurfaceView surface;
    uint32_t rect_x;
    uint32_t rect_y;
    uint32_t width;
    uint32_t height;
    uint32_t rgba_bytes;
    uint32_t decoder_flags;
    uint8_t *source_rgba;
    uint8_t *background_rgba;
} PhotonV6ExactOverlayPrepared;

PhotonV6ExactOverlayStatus photon_v6_exact_overlay_prepare(
    const PhotonV6ExactOverlayRequest *request,
    PhotonV6ExactOverlayPrepared *prepared,
    PhotonV6ExactOverlayReport *report);

/*
 * Prepare an already-authenticated RGBA sidecar for the same retail Cr6Ti
 * direct/copy or source-over operation used by the ordinary payload path.
 * This helper deliberately performs no route inference: callers must first
 * prove the exact Translation selector/owner identity.  The source bytes are
 * copied and, for the source-over mode, the predecode destination is captured
 * before the retail decoder can modify it.
 */
PhotonV6ExactOverlayStatus photon_v6_cr6ti_surface_prepare_rgba(
    const PhotonV6CpuSurfaceView *surface,
    uint32_t rect_x,
    uint32_t rect_y,
    uint32_t width,
    uint32_t height,
    const uint8_t *source_rgba,
    uint32_t source_rgba_bytes,
    uint32_t decoder_flags,
    PhotonV6ExactOverlayPrepared *prepared,
    PhotonV6ExactOverlayReport *report);

PhotonV6ExactOverlayStatus photon_v6_exact_overlay_commit_prepared(
    PhotonV6ExactOverlayPrepared *prepared,
    PhotonV6ExactOverlayReport *report);

void photon_v6_exact_overlay_prepared_free(
    PhotonV6ExactOverlayPrepared *prepared);

/*
 * Internal non-exported composition boundary used by the eventual native
 * decode hook.  It never infers a slot or action from UI text.  The route gate
 * runs before a sidecar can be committed, and the transaction is the only
 * surface write path.
 */
PhotonV6ExactOverlayStatus photon_v6_exact_overlay_apply(
    const PhotonV6ExactOverlayRequest *request,
    PhotonV6ExactOverlayReport *report);

#ifdef __cplusplus
}
#endif

#endif
