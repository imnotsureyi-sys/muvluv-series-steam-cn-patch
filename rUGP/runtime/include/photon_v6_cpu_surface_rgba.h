#ifndef PHOTON_V6_CPU_SURFACE_RGBA_H
#define PHOTON_V6_CPU_SURFACE_RGBA_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum PhotonV6CpuSurfaceFormat {
    PHOTON_V6_CPU_SURFACE_BGRA8_STRAIGHT = 1
} PhotonV6CpuSurfaceFormat;

typedef enum PhotonV6CpuSurfaceRowOrientation {
    PHOTON_V6_CPU_SURFACE_ROWS_FORWARD = 1,
    PHOTON_V6_CPU_SURFACE_ROWS_REVERSE = 2
} PhotonV6CpuSurfaceRowOrientation;

typedef enum PhotonV6CpuSurfaceStatus {
    PHOTON_V6_CPU_SURFACE_OK = 0,
    PHOTON_V6_CPU_SURFACE_INVALID_ARGUMENT = 1,
    PHOTON_V6_CPU_SURFACE_UNSUPPORTED_FORMAT = 2,
    PHOTON_V6_CPU_SURFACE_UNSUPPORTED_ORIENTATION = 3,
    PHOTON_V6_CPU_SURFACE_OVERFLOW = 4,
    PHOTON_V6_CPU_SURFACE_BOUNDS_REJECTED = 5,
    PHOTON_V6_CPU_SURFACE_MEMORY_REJECTED = 6,
    PHOTON_V6_CPU_SURFACE_GUARD_REJECTED = 7,
    PHOTON_V6_CPU_SURFACE_ALIAS_REJECTED = 8
} PhotonV6CpuSurfaceStatus;

typedef struct PhotonV6CpuSurfaceView {
    /* Caller-declared containing span; all accessed rows must stay inside it. */
    uint8_t *bounds_base;
    size_t bounds_bytes;

    /* Address of storage row 0, pixel 0.  Negative stride is supported. */
    uint8_t *base;
    int32_t signed_stride;
    uint32_t surface_width;
    uint32_t surface_height;

    PhotonV6CpuSurfaceFormat memory_format;
    PhotonV6CpuSurfaceRowOrientation row_orientation;
} PhotonV6CpuSurfaceView;

/*
 * logical_rgba is tightly packed, top-to-bottom, straight-alpha RGBA.
 * The destination is straight-alpha BGRA.  RGB is never premultiplied.
 * On any non-OK return, no destination byte is modified.
 */
PhotonV6CpuSurfaceStatus photon_v6_cpu_surface_write_rgba(
    const PhotonV6CpuSurfaceView *surface,
    uint32_t rect_x,
    uint32_t rect_y,
    uint32_t width,
    uint32_t height,
    const uint8_t *logical_rgba,
    size_t logical_bytes);

/*
 * Reads the selected straight-alpha BGRA rectangle into tightly packed,
 * top-to-bottom straight-alpha RGBA.  On failure output_rgba is unchanged.
 */
PhotonV6CpuSurfaceStatus photon_v6_cpu_surface_read_rgba(
    const PhotonV6CpuSurfaceView *surface,
    uint32_t rect_x,
    uint32_t rect_y,
    uint32_t width,
    uint32_t height,
    uint8_t *output_rgba,
    size_t output_bytes);

#ifdef __cplusplus
}
#endif

#endif
