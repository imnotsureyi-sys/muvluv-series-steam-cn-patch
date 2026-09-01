#include "photon_pf_decoder_surface_view.h"

#include <limits.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

static int unpack_nonnegative_pair(uint32_t packed, uint32_t *x, uint32_t *y) {
    int32_t sx = (int16_t)(packed & UINT32_C(0xFFFF));
    int32_t sy = (int16_t)(packed >> 16);
    if (sx < 0 || sy < 0) return 0;
    *x = (uint32_t)sx;
    *y = (uint32_t)sy;
    return 1;
}

PhotonPfDecoderSurfaceStatus photon_pf_derive_full_surface(
    const PhotonPfDecoderSurfaceArgs *args,
    uint32_t expected_width,
    uint32_t expected_height,
    PhotonPfDerivedSurface *output) {
    if (!args || !output || !args->pixel_zero_zero ||
        !expected_width || !expected_height) {
        return PHOTON_PF_DECODER_SURFACE_INVALID_ARGUMENT;
    }

    PhotonPfDerivedSurface derived;
    memset(&derived, 0, sizeof(derived));
    if (!unpack_nonnegative_pair(args->target_left_top,
            &derived.target_left, &derived.target_top) ||
        !unpack_nonnegative_pair(args->target_right_bottom,
            &derived.target_right, &derived.target_bottom)) {
        return PHOTON_PF_DECODER_SURFACE_TARGET_REJECTED;
    }
    if (derived.target_left != 0 || derived.target_top != 0 ||
        derived.target_right != expected_width ||
        derived.target_bottom != expected_height) {
        return PHOTON_PF_DECODER_SURFACE_TARGET_REJECTED;
    }
    if (!unpack_nonnegative_pair(args->clip_left_top,
            &derived.clip_left, &derived.clip_top) ||
        !unpack_nonnegative_pair(args->clip_right_bottom,
            &derived.clip_right, &derived.clip_bottom)) {
        return PHOTON_PF_DECODER_SURFACE_CLIP_REJECTED;
    }
    if (derived.clip_left != derived.target_left ||
        derived.clip_top != derived.target_top ||
        derived.clip_right != derived.target_right ||
        derived.clip_bottom != derived.target_bottom) {
        return PHOTON_PF_DECODER_SURFACE_CLIP_REJECTED;
    }
    if (args->decoder_pitch == 0 || args->decoder_pitch == INT32_MIN) {
        return PHOTON_PF_DECODER_SURFACE_STRIDE_REJECTED;
    }

    int32_t signed_stride = -args->decoder_pitch;
    uint64_t row_bytes = (uint64_t)expected_width * UINT64_C(4);
    uint64_t abs_stride = signed_stride < 0
        ? (uint64_t)(-(int64_t)signed_stride)
        : (uint64_t)signed_stride;
    if (row_bytes > SIZE_MAX || abs_stride < row_bytes) {
        return PHOTON_PF_DECODER_SURFACE_STRIDE_REJECTED;
    }

    int64_t last_delta = (int64_t)signed_stride *
        (int64_t)(expected_height - 1U);
    uintptr_t first = (uintptr_t)args->pixel_zero_zero;
    uintptr_t last = 0;
    if (last_delta < 0) {
        uint64_t magnitude = (uint64_t)(-last_delta);
        if (magnitude > (uint64_t)first) {
            return PHOTON_PF_DECODER_SURFACE_OVERFLOW;
        }
        last = first - (uintptr_t)magnitude;
    } else {
        uint64_t delta = (uint64_t)last_delta;
        if (delta > (uint64_t)UINTPTR_MAX - (uint64_t)first) {
            return PHOTON_PF_DECODER_SURFACE_OVERFLOW;
        }
        last = first + (uintptr_t)delta;
    }

    uintptr_t low = first < last ? first : last;
    uintptr_t high = first < last ? last : first;
    uint64_t span = (uint64_t)(high - low) + row_bytes;
    if (span > SIZE_MAX || span == 0) {
        return PHOTON_PF_DECODER_SURFACE_OVERFLOW;
    }

    derived.view.bounds_base = (uint8_t *)low;
    derived.view.bounds_bytes = (size_t)span;
    derived.view.base = args->pixel_zero_zero;
    derived.view.signed_stride = signed_stride;
    derived.view.surface_width = expected_width;
    derived.view.surface_height = expected_height;
    derived.view.memory_format = PHOTON_V6_CPU_SURFACE_BGRA8_STRAIGHT;
    derived.view.row_orientation = PHOTON_V6_CPU_SURFACE_ROWS_FORWARD;
    *output = derived;
    return PHOTON_PF_DECODER_SURFACE_OK;
}
