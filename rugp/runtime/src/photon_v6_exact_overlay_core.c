#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include <limits.h>
#include <stdint.h>
#include <string.h>

#include "photon_v6_exact_overlay_core.h"
#include "photon_v6_exact_rgba_sidecar_loader.h"

#if !defined(__i386__) && !defined(_M_IX86)
#error photon_v6_exact_overlay_core must use the 32-bit Windows ABI.
#endif

static PhotonV6ExactOverlayStatus finish(
    PhotonV6ExactOverlayReport *report,
    PhotonV6ExactOverlayStatus status) {
    report->status = (uint32_t)status;
    return status;
}

static void prepared_zero(PhotonV6ExactOverlayPrepared *prepared) {
    if (prepared) memset(prepared, 0, sizeof(*prepared));
}

void photon_v6_exact_overlay_prepared_free(
    PhotonV6ExactOverlayPrepared *prepared) {
    if (!prepared) return;
    if (prepared->source_rgba)
        HeapFree(GetProcessHeap(), 0, prepared->source_rgba);
    if (prepared->background_rgba)
        HeapFree(GetProcessHeap(), 0, prepared->background_rgba);
    prepared_zero(prepared);
}

static int16_t retail_scale_delta(int16_t delta, uint8_t alpha) {
    int32_t product = (int32_t)delta * (int32_t)alpha;
    /* PF/PM use MMX PSRAW 7.  Spell out floor division for negative values so
     * the C result is independent of implementation-defined signed shifts. */
    if (product >= 0) return (int16_t)(product / 128);
    return (int16_t)(-(((-product) + 127) / 128));
}

static uint8_t clamp_byte(int32_t value) {
    if (value < 0) return 0;
    if (value > 255) return 255;
    return (uint8_t)value;
}

/* WIC exposes the authority PNG in the conventional 0..255 straight-alpha
 * domain.  The retail Cr6Ti compositor instead consumes a 0..128 coefficient
 * and treats bit 7 as the fully-opaque/copy sentinel.  Passing the WIC byte
 * through unchanged makes every PNG alpha >= 128 take the copy branch and was
 * the direct cause of the selected-state colour blocks and noisy edges.
 *
 * Use nearest-integer scaling across the complete 8-bit domain.  This also
 * reproduces every native Cr6Ti alpha exactly: review values 8*n map back to
 * native 4*n, while review 255 maps to the 0x80 copy sentinel. */
static uint8_t review_alpha_to_retail(uint8_t review_alpha) {
    return (uint8_t)(((uint32_t)review_alpha * 128U + 127U) / 255U);
}

/* With decoder flag byte != 0 the retail routine bypasses its MMX blend and
 * copies the decoded Cr6Ti scratch row directly into the destination.  The
 * scratch alpha is still the engine-native 0..128 value.  Alpha-state zero
 * is emitted by the decoder as the canonical all-zero transparent pixel. */
static void retail_cr6ti_direct_pixel(
    const uint8_t source[4], uint8_t output[4]) {
    uint8_t alpha = review_alpha_to_retail(source[3]);
    if (!alpha) {
        memset(output, 0, 4);
        return;
    }
    output[0] = source[0];
    output[1] = source[1];
    output[2] = source[2];
    output[3] = alpha;
}

static void retail_cr6ti_compose_pixel(
    const uint8_t source[4], const uint8_t background[4], uint8_t output[4]) {
    uint8_t alpha = review_alpha_to_retail(source[3]);
    uint32_t source_packed = (uint32_t)source[0] |
        ((uint32_t)source[1] << 8) | ((uint32_t)source[2] << 16) |
        ((uint32_t)alpha << 24);
    uint32_t channel;
    if (alpha & 0x80U) {
        output[0] = source[0];
        output[1] = source[1];
        output[2] = source[2];
        output[3] = alpha;
        return;
    }
    if (source_packed == 0) {
        memcpy(output, background, 4);
        return;
    }
    for (channel = 0; channel < 3; ++channel) {
        int16_t delta = (int16_t)((int32_t)source[channel] -
                                  (int32_t)background[channel]);
        output[channel] = clamp_byte(
            (int32_t)background[channel] +
            (int32_t)retail_scale_delta(delta, alpha));
    }
    /* The retail MMX path keeps the alpha byte from the unsigned-greater
     * packed pixel.  Alpha is the most significant byte, hence this is max A;
     * RGB only breaks ties and cannot change the masked alpha byte. */
    output[3] = alpha > background[3] ? alpha : background[3];
}

static int retail_cr6ti_compose(
    const uint8_t *source,
    const uint8_t *background,
    uint8_t *output,
    uint32_t rgba_bytes) {
    uint32_t offset;
    if (!source || !background || !output || !rgba_bytes ||
        (rgba_bytes & 3U) != 0)
        return 0;
    for (offset = 0; offset < rgba_bytes; offset += 4)
        retail_cr6ti_compose_pixel(
            source + offset, background + offset, output + offset);
    return 1;
}

static int retail_cr6ti_direct(
    const uint8_t *source, uint8_t *output, uint32_t rgba_bytes) {
    uint32_t offset;
    if (!source || !output || !rgba_bytes || (rgba_bytes & 3U) != 0)
        return 0;
    for (offset = 0; offset < rgba_bytes; offset += 4)
        retail_cr6ti_direct_pixel(source + offset, output + offset);
    return 1;
}

static PhotonV6RouteGateStatus gate_request(
    const PhotonV6ExactOverlayRequest *request,
    uint32_t identity_exact,
    PhotonV6RouteGateDecision *decision) {
    PhotonV6RouteGateRequest gate;
    memset(&gate, 0, sizeof(gate));
    gate.struct_size = sizeof(gate);
    gate.game = request->game;
    gate.slot = request->slot;
    gate.transport = request->transport;
    gate.ordinary_loader_identity_exact = identity_exact;
    return photon_v6_internal_route_gate(&gate, decision);
}

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
    PhotonV6ExactOverlayReport *report) {
    uint64_t expected_bytes;
    PhotonV6CpuSurfaceStatus read_status;
    if (!prepared || !report)
        return PHOTON_V6_EXACT_OVERLAY_INVALID_ARGUMENT;
    prepared_zero(prepared);
    prepared->struct_size = sizeof(*prepared);
    memset(report, 0, sizeof(*report));
    report->struct_size = sizeof(*report);
    report->transaction.struct_size = sizeof(report->transaction);
    expected_bytes = (uint64_t)width * (uint64_t)height * UINT64_C(4);
    if (!surface || !source_rgba || !width || !height ||
        expected_bytes == 0 || expected_bytes > UINT32_MAX ||
        source_rgba_bytes != (uint32_t)expected_bytes)
        return finish(report, PHOTON_V6_EXACT_OVERLAY_INVALID_ARGUMENT);
    report->sidecar_width = width;
    report->sidecar_height = height;
    report->sidecar_rgba_bytes = source_rgba_bytes;
    prepared->source_rgba = (uint8_t *)HeapAlloc(
        GetProcessHeap(), 0, source_rgba_bytes);
    if (!prepared->source_rgba)
        return finish(report, PHOTON_V6_EXACT_OVERLAY_SIDECAR_FAILED);
    memcpy(prepared->source_rgba, source_rgba, source_rgba_bytes);
    if ((decoder_flags & UINT32_C(0xFF)) == 0) {
        prepared->background_rgba = (uint8_t *)HeapAlloc(
            GetProcessHeap(), 0, source_rgba_bytes);
        if (!prepared->background_rgba) {
            photon_v6_exact_overlay_prepared_free(prepared);
            return finish(report,
                          PHOTON_V6_EXACT_OVERLAY_BACKGROUND_READ_FAILED);
        }
        read_status = photon_v6_cpu_surface_read_rgba(
            surface, rect_x, rect_y, width, height,
            prepared->background_rgba, source_rgba_bytes);
        if (read_status != PHOTON_V6_CPU_SURFACE_OK) {
            photon_v6_exact_overlay_prepared_free(prepared);
            return finish(report,
                          PHOTON_V6_EXACT_OVERLAY_BACKGROUND_READ_FAILED);
        }
    }
    prepared->surface = *surface;
    prepared->rect_x = rect_x;
    prepared->rect_y = rect_y;
    prepared->width = width;
    prepared->height = height;
    prepared->rgba_bytes = source_rgba_bytes;
    prepared->decoder_flags = decoder_flags;
    prepared->active = 1;
    return finish(report, PHOTON_V6_EXACT_OVERLAY_OK);
}

PhotonV6ExactOverlayStatus photon_v6_exact_overlay_prepare(
    const PhotonV6ExactOverlayRequest *request,
    PhotonV6ExactOverlayPrepared *prepared,
    PhotonV6ExactOverlayReport *report) {
    PhotonV6RouteGateDecision decision;
    PhotonV6ExactRgbaImage ordinary;
    PhotonV6RouteGateStatus gate_status;
    uint64_t expected_bytes;
    PhotonV6CpuSurfaceStatus read_status;
    memset(&ordinary, 0, sizeof(ordinary));
    if (!prepared || !report)
        return PHOTON_V6_EXACT_OVERLAY_INVALID_ARGUMENT;
    prepared_zero(prepared);
    prepared->struct_size = sizeof(*prepared);
    memset(report, 0, sizeof(*report));
    report->struct_size = sizeof(*report);
    report->transaction.struct_size = sizeof(report->transaction);
    if (!request || request->struct_size != sizeof(*request) ||
        !request->surface || !request->expected_width ||
        !request->expected_height ||
        (request->game != PHOTON_V6_ROUTE_GAME_PF &&
         request->game != PHOTON_V6_ROUTE_GAME_PM) ||
        (request->slot != PHOTON_V6_ROUTE_SLOT_JAPANESE &&
         request->slot != PHOTON_V6_ROUTE_SLOT_TRANSLATION))
        return finish(report, PHOTON_V6_EXACT_OVERLAY_INVALID_ARGUMENT);
    if (request->slot == PHOTON_V6_ROUTE_SLOT_JAPANESE ||
        request->transport !=
            PHOTON_V6_ROUTE_TRANSPORT_ORDINARY_EXACT_PAYLOAD) {
        gate_status = gate_request(request, 0, &decision);
        report->route_gate_status = (uint32_t)gate_status;
        return finish(report, PHOTON_V6_EXACT_OVERLAY_ROUTE_REJECTED);
    }
    if (!request->ordinary_bundle_root || !request->ordinary_bundle_root[0])
        return finish(report, PHOTON_V6_EXACT_OVERLAY_INVALID_ARGUMENT);
    {
        PhotonV6ExactRgbaLoadStatus load_status =
            photon_v6_exact_rgba_sidecar_load(
                request->ordinary_bundle_root,
                request->game == PHOTON_V6_ROUTE_GAME_PF
                    ? PHOTON_V6_EXACT_RGBA_GAME_PF
                    : PHOTON_V6_EXACT_RGBA_GAME_PM,
                request->payload_bytes, request->payload_fnv1a64, &ordinary);
        report->sidecar_status = (uint32_t)load_status;
        if (load_status == PHOTON_V6_EXACT_RGBA_LOAD_UNKNOWN_IDENTITY) {
            gate_status = gate_request(request, 0, &decision);
            report->route_gate_status = (uint32_t)gate_status;
            return finish(report,
                          PHOTON_V6_EXACT_OVERLAY_IDENTITY_NOT_TARGETED);
        }
        if (load_status != PHOTON_V6_EXACT_RGBA_LOAD_OK)
            return finish(report, PHOTON_V6_EXACT_OVERLAY_SIDECAR_FAILED);
    }
    gate_status = gate_request(request, 1, &decision);
    report->route_gate_status = (uint32_t)gate_status;
    if (gate_status !=
            PHOTON_V6_ROUTE_GATE_ALLOW_ORDINARY_TRANSLATION_PAYLOAD ||
        !decision.overlay_allowed) {
        photon_v6_exact_rgba_image_free(&ordinary);
        return finish(report, PHOTON_V6_EXACT_OVERLAY_ROUTE_REJECTED);
    }
    report->sidecar_width = ordinary.width;
    report->sidecar_height = ordinary.height;
    report->sidecar_rgba_bytes = ordinary.bytes;
    if (ordinary.width != request->expected_width ||
        ordinary.height != request->expected_height) {
        photon_v6_exact_rgba_image_free(&ordinary);
        return finish(report,
                      PHOTON_V6_EXACT_OVERLAY_SIDECAR_GEOMETRY_MISMATCH);
    }
    expected_bytes = (uint64_t)ordinary.width *
        (uint64_t)ordinary.height * UINT64_C(4);
    if (expected_bytes == 0 || expected_bytes > UINT32_MAX ||
        ordinary.bytes != (uint32_t)expected_bytes) {
        photon_v6_exact_rgba_image_free(&ordinary);
        return finish(report, PHOTON_V6_EXACT_OVERLAY_INVALID_ARGUMENT);
    }
    if ((request->decoder_flags & UINT32_C(0xFF)) == 0) {
        prepared->background_rgba = (uint8_t *)HeapAlloc(
            GetProcessHeap(), 0, ordinary.bytes);
        if (!prepared->background_rgba) {
            photon_v6_exact_rgba_image_free(&ordinary);
            return finish(report,
                          PHOTON_V6_EXACT_OVERLAY_BACKGROUND_READ_FAILED);
        }
        read_status = photon_v6_cpu_surface_read_rgba(
            request->surface, request->rect_x, request->rect_y,
            ordinary.width, ordinary.height, prepared->background_rgba,
            ordinary.bytes);
        if (read_status != PHOTON_V6_CPU_SURFACE_OK) {
            photon_v6_exact_rgba_image_free(&ordinary);
            photon_v6_exact_overlay_prepared_free(prepared);
            return finish(report,
                          PHOTON_V6_EXACT_OVERLAY_BACKGROUND_READ_FAILED);
        }
    }
    prepared->surface = *request->surface;
    prepared->rect_x = request->rect_x;
    prepared->rect_y = request->rect_y;
    prepared->width = ordinary.width;
    prepared->height = ordinary.height;
    prepared->rgba_bytes = ordinary.bytes;
    prepared->decoder_flags = request->decoder_flags;
    prepared->source_rgba = ordinary.pixels;
    ordinary.pixels = NULL;
    prepared->active = 1;
    return finish(report, PHOTON_V6_EXACT_OVERLAY_OK);
}

PhotonV6ExactOverlayStatus photon_v6_exact_overlay_commit_prepared(
    PhotonV6ExactOverlayPrepared *prepared,
    PhotonV6ExactOverlayReport *report) {
    uint8_t *composed;
    PhotonV6SurfaceTransactionStatus transaction_status;
    if (!prepared || prepared->struct_size != sizeof(*prepared) ||
        !prepared->active || !prepared->source_rgba ||
        !prepared->rgba_bytes || !report ||
        (((prepared->decoder_flags & UINT32_C(0xFF)) == 0) &&
         !prepared->background_rgba))
        return report
            ? finish(report, PHOTON_V6_EXACT_OVERLAY_INVALID_ARGUMENT)
            : PHOTON_V6_EXACT_OVERLAY_INVALID_ARGUMENT;
    composed = (uint8_t *)HeapAlloc(
        GetProcessHeap(), 0, prepared->rgba_bytes);
    if (!composed ||
        (((prepared->decoder_flags & UINT32_C(0xFF)) != 0)
             ? !retail_cr6ti_direct(prepared->source_rgba, composed,
                                    prepared->rgba_bytes)
             : !retail_cr6ti_compose(
                   prepared->source_rgba, prepared->background_rgba,
                   composed, prepared->rgba_bytes))) {
        if (composed) HeapFree(GetProcessHeap(), 0, composed);
        photon_v6_exact_overlay_prepared_free(prepared);
        return finish(report, PHOTON_V6_EXACT_OVERLAY_COMPOSITION_FAILED);
    }
    transaction_status = photon_v6_surface_transaction_apply(
        &prepared->surface, prepared->rect_x, prepared->rect_y,
        prepared->width, prepared->height, composed, prepared->rgba_bytes,
        &report->transaction);
    HeapFree(GetProcessHeap(), 0, composed);
    photon_v6_exact_overlay_prepared_free(prepared);
    if (transaction_status != PHOTON_V6_SURFACE_TRANSACTION_OK)
        return finish(report,
                      PHOTON_V6_EXACT_OVERLAY_SURFACE_TRANSACTION_FAILED);
    report->destination_committed = 1;
    return finish(report, PHOTON_V6_EXACT_OVERLAY_OK);
}

PhotonV6ExactOverlayStatus photon_v6_exact_overlay_apply(
    const PhotonV6ExactOverlayRequest *request,
    PhotonV6ExactOverlayReport *report) {
    PhotonV6RouteGateDecision decision;
    PhotonV6ExactRgbaImage ordinary;
    const uint8_t *pixels = NULL;
    uint32_t width = 0, height = 0, bytes = 0;
    PhotonV6RouteGateStatus gate_status;
    memset(&ordinary, 0, sizeof(ordinary));
    if (!report) return PHOTON_V6_EXACT_OVERLAY_INVALID_ARGUMENT;
    memset(report, 0, sizeof(*report));
    report->struct_size = sizeof(*report);
    report->transaction.struct_size = sizeof(report->transaction);
    if (!request || request->struct_size != sizeof(*request) ||
        !request->surface || !request->expected_width ||
        !request->expected_height ||
        (request->game != PHOTON_V6_ROUTE_GAME_PF &&
         request->game != PHOTON_V6_ROUTE_GAME_PM) ||
        (request->slot != PHOTON_V6_ROUTE_SLOT_JAPANESE &&
         request->slot != PHOTON_V6_ROUTE_SLOT_TRANSLATION))
        return finish(report, PHOTON_V6_EXACT_OVERLAY_INVALID_ARGUMENT);

    /* Japanese and currently-unproven transports are rejected before IO. */
    if (request->slot == PHOTON_V6_ROUTE_SLOT_JAPANESE ||
        request->transport !=
            PHOTON_V6_ROUTE_TRANSPORT_ORDINARY_EXACT_PAYLOAD) {
        gate_status = gate_request(request, 0, &decision);
        report->route_gate_status = (uint32_t)gate_status;
        return finish(report, PHOTON_V6_EXACT_OVERLAY_ROUTE_REJECTED);
    }
    if (!request->ordinary_bundle_root || !request->ordinary_bundle_root[0])
        return finish(report, PHOTON_V6_EXACT_OVERLAY_INVALID_ARGUMENT);

    {
        PhotonV6ExactRgbaLoadStatus load_status =
            photon_v6_exact_rgba_sidecar_load(
                request->ordinary_bundle_root,
                request->game == PHOTON_V6_ROUTE_GAME_PF
                    ? PHOTON_V6_EXACT_RGBA_GAME_PF
                    : PHOTON_V6_EXACT_RGBA_GAME_PM,
                request->payload_bytes, request->payload_fnv1a64, &ordinary);
        report->sidecar_status = (uint32_t)load_status;
        if (load_status == PHOTON_V6_EXACT_RGBA_LOAD_UNKNOWN_IDENTITY) {
            gate_status = gate_request(request, 0, &decision);
            report->route_gate_status = (uint32_t)gate_status;
            return finish(report,
                          PHOTON_V6_EXACT_OVERLAY_IDENTITY_NOT_TARGETED);
        }
        if (load_status != PHOTON_V6_EXACT_RGBA_LOAD_OK)
            return finish(report, PHOTON_V6_EXACT_OVERLAY_SIDECAR_FAILED);
    }
    gate_status = gate_request(request, 1, &decision);
    report->route_gate_status = (uint32_t)gate_status;
    if (gate_status !=
            PHOTON_V6_ROUTE_GATE_ALLOW_ORDINARY_TRANSLATION_PAYLOAD ||
        !decision.overlay_allowed) {
        photon_v6_exact_rgba_image_free(&ordinary);
        return finish(report, PHOTON_V6_EXACT_OVERLAY_ROUTE_REJECTED);
    }
    pixels = ordinary.pixels;
    width = ordinary.width;
    height = ordinary.height;
    bytes = ordinary.bytes;
    report->sidecar_width = width;
    report->sidecar_height = height;
    report->sidecar_rgba_bytes = bytes;
    if (width != request->expected_width ||
        height != request->expected_height) {
        photon_v6_exact_rgba_image_free(&ordinary);
        return finish(report,
                      PHOTON_V6_EXACT_OVERLAY_SIDECAR_GEOMETRY_MISMATCH);
    }
    if (photon_v6_surface_transaction_apply(
            request->surface, request->rect_x, request->rect_y,
            width, height, pixels, bytes, &report->transaction) !=
        PHOTON_V6_SURFACE_TRANSACTION_OK) {
        photon_v6_exact_rgba_image_free(&ordinary);
        return finish(report,
                      PHOTON_V6_EXACT_OVERLAY_SURFACE_TRANSACTION_FAILED);
    }
    report->destination_committed = 1;
    photon_v6_exact_rgba_image_free(&ordinary);
    return finish(report, PHOTON_V6_EXACT_OVERLAY_OK);
}
