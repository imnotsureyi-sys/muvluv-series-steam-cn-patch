#ifndef PHOTON_V6_SURFACE_TRANSACTION_H
#define PHOTON_V6_SURFACE_TRANSACTION_H

#include <stddef.h>
#include <stdint.h>

#include "photon_v6_cpu_surface_rgba.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef enum PhotonV6SurfaceTransactionStatus {
    PHOTON_V6_SURFACE_TRANSACTION_OK = 0,
    PHOTON_V6_SURFACE_TRANSACTION_INVALID_ARGUMENT = 1,
    PHOTON_V6_SURFACE_TRANSACTION_OVERFLOW = 2,
    PHOTON_V6_SURFACE_TRANSACTION_ALLOCATION_ERROR = 3,
    PHOTON_V6_SURFACE_TRANSACTION_SNAPSHOT_READ_FAILED = 4,
    PHOTON_V6_SURFACE_TRANSACTION_WRITE_FAILED = 5,
    PHOTON_V6_SURFACE_TRANSACTION_READBACK_FAILED = 6,
    PHOTON_V6_SURFACE_TRANSACTION_READBACK_MISMATCH = 7,
    PHOTON_V6_SURFACE_TRANSACTION_ROLLBACK_FAILED = 8
} PhotonV6SurfaceTransactionStatus;

typedef struct PhotonV6SurfaceTransactionReport {
    uint32_t struct_size;
    uint32_t status;
    uint32_t surface_status;
    uint32_t rollback_attempted;
    uint32_t rollback_succeeded;
    uint32_t destination_committed;
    uint32_t logical_bytes;
    uint64_t requested_rgba_fnv1a64;
    uint64_t readback_rgba_fnv1a64;
    uint64_t original_rgba_fnv1a64;
    uint64_t restored_rgba_fnv1a64;
} PhotonV6SurfaceTransactionReport;

/*
 * Applies a verified, tightly-packed, top-to-bottom straight-alpha RGBA image
 * to one CPU surface rectangle as a bounded transaction:
 *
 *   snapshot -> write -> readback -> byte-for-byte comparison
 *
 * Every failure after the first write attempts to restore the snapshot and
 * then reads it back for a second byte-for-byte comparison.  The function
 * reports OK only when the requested RGBA bytes were read back exactly.  A
 * rollback failure is explicit and is never hidden behind the original error.
 *
 * No game file, archive, authority, registry value, or Japanese slot is read
 * or written by this module.  Route/language authentication is the caller's
 * responsibility and must complete before this function is called.
 */
PhotonV6SurfaceTransactionStatus photon_v6_surface_transaction_apply(
    const PhotonV6CpuSurfaceView *surface,
    uint32_t rect_x,
    uint32_t rect_y,
    uint32_t width,
    uint32_t height,
    const uint8_t *logical_rgba,
    size_t logical_bytes,
    PhotonV6SurfaceTransactionReport *report);

#ifdef PHOTON_V6_SURFACE_TRANSACTION_TEST_HOOKS
typedef enum PhotonV6SurfaceTransactionTestFault {
    PHOTON_V6_SURFACE_TRANSACTION_TEST_NONE = 0,
    PHOTON_V6_SURFACE_TRANSACTION_TEST_READBACK_MISMATCH = 1,
    PHOTON_V6_SURFACE_TRANSACTION_TEST_ROLLBACK_REJECTED = 2
} PhotonV6SurfaceTransactionTestFault;

void photon_v6_surface_transaction_test_fault(
    PhotonV6SurfaceTransactionTestFault fault);
#endif

#ifdef __cplusplus
}
#endif

#endif
