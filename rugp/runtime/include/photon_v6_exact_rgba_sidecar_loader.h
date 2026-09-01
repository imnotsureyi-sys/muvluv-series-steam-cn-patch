#ifndef PHOTON_V6_EXACT_RGBA_SIDECAR_LOADER_H
#define PHOTON_V6_EXACT_RGBA_SIDECAR_LOADER_H

#include <stdint.h>
#include <wchar.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum PhotonV6ExactRgbaGame {
    PHOTON_V6_EXACT_RGBA_GAME_PF = 1,
    PHOTON_V6_EXACT_RGBA_GAME_PM = 2
} PhotonV6ExactRgbaGame;

typedef enum PhotonV6ExactRgbaLoadStatus {
    PHOTON_V6_EXACT_RGBA_LOAD_OK = 0,
    PHOTON_V6_EXACT_RGBA_LOAD_INVALID_ARGUMENT = 1,
    PHOTON_V6_EXACT_RGBA_LOAD_UNKNOWN_GAME = 2,
    PHOTON_V6_EXACT_RGBA_LOAD_UNKNOWN_IDENTITY = 3,
    PHOTON_V6_EXACT_RGBA_LOAD_PATH_REJECTED = 4,
    PHOTON_V6_EXACT_RGBA_LOAD_IO_ERROR = 5,
    PHOTON_V6_EXACT_RGBA_LOAD_PNG_HASH_MISMATCH = 6,
    PHOTON_V6_EXACT_RGBA_LOAD_COM_ERROR = 7,
    PHOTON_V6_EXACT_RGBA_LOAD_DECODE_ERROR = 8,
    PHOTON_V6_EXACT_RGBA_LOAD_GEOMETRY_MISMATCH = 9,
    PHOTON_V6_EXACT_RGBA_LOAD_RGBA_HASH_MISMATCH = 10,
    PHOTON_V6_EXACT_RGBA_LOAD_ALLOCATION_ERROR = 11,
    PHOTON_V6_EXACT_RGBA_LOAD_INTERNAL_ERROR = 12
} PhotonV6ExactRgbaLoadStatus;

typedef struct PhotonV6ExactRgbaImage {
    uint8_t *pixels;
    uint32_t width;
    uint32_t height;
    uint32_t stride;
    uint32_t bytes;
} PhotonV6ExactRgbaImage;

/*
 * bundle_root is supplied by the caller and must contain:
 *   sidecars\\PF\\<payload_bytes>_<payload_fnv1a64>.png
 *   sidecars\\PM\\<payload_bytes>_<payload_fnv1a64>.png
 *
 * On every non-OK result, output is all zeroes.  A successful image must be
 * released with photon_v6_exact_rgba_image_free before the structure is reused.
 */
PhotonV6ExactRgbaLoadStatus photon_v6_exact_rgba_sidecar_load(
    const wchar_t *bundle_root,
    PhotonV6ExactRgbaGame game,
    uint32_t payload_bytes,
    uint64_t payload_fnv1a64,
    PhotonV6ExactRgbaImage *output);

void photon_v6_exact_rgba_image_free(PhotonV6ExactRgbaImage *image);

#ifdef PHOTON_V6_LOADER_TEST_HOOKS
/* Fixture-only: corrupts one verified in-memory PNG immediately before WIC. */
void photon_v6_exact_rgba_test_corrupt_next_decode(void);
#endif

#ifdef __cplusplus
}
#endif

#endif
