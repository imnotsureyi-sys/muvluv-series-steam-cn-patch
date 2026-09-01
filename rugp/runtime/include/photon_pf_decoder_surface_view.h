#ifndef PHOTON_PF_DECODER_SURFACE_VIEW_H
#define PHOTON_PF_DECODER_SURFACE_VIEW_H

#include <stdint.h>

#include "photon_v6_cpu_surface_rgba.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef enum PhotonPfDecoderSurfaceStatus {
    PHOTON_PF_DECODER_SURFACE_OK = 0,
    PHOTON_PF_DECODER_SURFACE_INVALID_ARGUMENT = 1,
    PHOTON_PF_DECODER_SURFACE_TARGET_REJECTED = 2,
    PHOTON_PF_DECODER_SURFACE_CLIP_REJECTED = 3,
    PHOTON_PF_DECODER_SURFACE_STRIDE_REJECTED = 4,
    PHOTON_PF_DECODER_SURFACE_OVERFLOW = 5
} PhotonPfDecoderSurfaceStatus;

typedef struct PhotonPfDecoderSurfaceArgs {
    uint8_t *pixel_zero_zero;
    int32_t decoder_pitch;
    uint32_t target_left_top;
    uint32_t target_right_bottom;
    uint32_t clip_left_top;
    uint32_t clip_right_bottom;
    uint32_t flags;
} PhotonPfDecoderSurfaceArgs;

typedef struct PhotonPfDerivedSurface {
    PhotonV6CpuSurfaceView view;
    uint32_t target_left;
    uint32_t target_top;
    uint32_t target_right;
    uint32_t target_bottom;
    uint32_t clip_left;
    uint32_t clip_top;
    uint32_t clip_right;
    uint32_t clip_bottom;
} PhotonPfDerivedSurface;

/*
 * Derive the CPU surface from the real PF decoder arguments.
 *
 * Static disassembly of PF RVA 0x0017F09E/0x0017CF30 proves that arg1 is
 * surface(0,0), arg2 is the decoder pitch, args3/4 are the target rectangle,
 * and args5/6 are the clip rectangle.  The retail decoder advances a logical
 * row with `destination -= decoder_pitch`, so the only valid surface stride is
 * `-decoder_pitch`.  This function intentionally has no base/row candidates.
 *
 * The exact full-surface observer is stricter than a general blit reader: it
 * accepts only a zero-origin target of the expected size and a clip equal to
 * that full target.  That gate prevents hashing untouched or stale pixels.
 */
PhotonPfDecoderSurfaceStatus photon_pf_derive_full_surface(
    const PhotonPfDecoderSurfaceArgs *args,
    uint32_t expected_width,
    uint32_t expected_height,
    PhotonPfDerivedSurface *output);

#ifdef __cplusplus
}
#endif

#endif
