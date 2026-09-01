#ifndef PHOTON_V6_SPECIAL57_SIDECAR_LOADER_H
#define PHOTON_V6_SPECIAL57_SIDECAR_LOADER_H

#include <stdint.h>
#include <wchar.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum PhotonV6Special57Game {
    PHOTON_V6_SPECIAL57_GAME_PF = 1,
    PHOTON_V6_SPECIAL57_GAME_PM = 2
} PhotonV6Special57Game;

typedef enum PhotonV6Special57LoadStatus {
    PHOTON_V6_SPECIAL57_LOAD_OK = 0,
    PHOTON_V6_SPECIAL57_LOAD_INVALID_ARGUMENT = 1,
    PHOTON_V6_SPECIAL57_LOAD_UNKNOWN_GAME = 2,
    PHOTON_V6_SPECIAL57_LOAD_UNKNOWN_SOURCE = 3,
    PHOTON_V6_SPECIAL57_LOAD_CONTEXT_MISMATCH = 4,
    PHOTON_V6_SPECIAL57_LOAD_PHYSICAL_IDENTITY_MISMATCH = 5,
    PHOTON_V6_SPECIAL57_LOAD_PATH_REJECTED = 6,
    PHOTON_V6_SPECIAL57_LOAD_IO_ERROR = 7,
    PHOTON_V6_SPECIAL57_LOAD_PNG_HASH_MISMATCH = 8,
    PHOTON_V6_SPECIAL57_LOAD_COM_ERROR = 9,
    PHOTON_V6_SPECIAL57_LOAD_DECODE_ERROR = 10,
    PHOTON_V6_SPECIAL57_LOAD_GEOMETRY_MISMATCH = 11,
    PHOTON_V6_SPECIAL57_LOAD_RGBA_HASH_MISMATCH = 12,
    PHOTON_V6_SPECIAL57_LOAD_ALLOCATION_ERROR = 13,
    PHOTON_V6_SPECIAL57_LOAD_INTERNAL_ERROR = 14
} PhotonV6Special57LoadStatus;

typedef struct PhotonV6Special57Image {
    uint8_t *pixels;
    uint32_t width;
    uint32_t height;
    uint32_t stride;
    uint32_t bytes;
} PhotonV6Special57Image;

/*
 * The caller must already have authenticated the Translation action/state.
 * A context-route row additionally requires its exact context_identity_key.
 * The physical endpoint bytes/FNV are checked independently, so a logical
 * source can never select an image merely because it shares an archive slot.
 * On failure output is all zeroes.
 */
PhotonV6Special57LoadStatus photon_v6_special57_sidecar_load(
    const wchar_t *bundle_root,
    PhotonV6Special57Game game,
    const char *source_asset_id,
    const char *context_identity_key,
    uint32_t physical_payload_bytes,
    uint64_t physical_payload_fnv1a64,
    PhotonV6Special57Image *output);

void photon_v6_special57_image_free(PhotonV6Special57Image *image);

#ifdef PHOTON_V6_SPECIAL57_TEST_HOOKS
void photon_v6_special57_test_corrupt_next_decode(void);
#endif

#ifdef __cplusplus
}
#endif

#endif
