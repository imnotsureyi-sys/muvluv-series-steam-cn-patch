#ifndef _WIN32_WINNT
#define _WIN32_WINNT 0x0601
#endif
#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include <limits.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#include "photon_v6_surface_transaction.h"

#if !defined(__i386__) && !defined(_M_IX86)
#error photon_v6_surface_transaction must use the 32-bit Windows ABI.
#endif

enum {
    REPORT_VERSION_SIZE = sizeof(PhotonV6SurfaceTransactionReport)
};

#ifdef PHOTON_V6_SURFACE_TRANSACTION_TEST_HOOKS
static volatile LONG test_fault = PHOTON_V6_SURFACE_TRANSACTION_TEST_NONE;

void photon_v6_surface_transaction_test_fault(
    PhotonV6SurfaceTransactionTestFault fault) {
    InterlockedExchange(&test_fault, (LONG)fault);
}
#endif

static uint64_t fnv1a64(const uint8_t *bytes, size_t count) {
    uint64_t value = UINT64_C(14695981039346656037);
    size_t index;
    for (index = 0; index < count; ++index) {
        value ^= bytes[index];
        value *= UINT64_C(1099511628211);
    }
    return value;
}

static void zero_report(PhotonV6SurfaceTransactionReport *report) {
    if (!report) return;
    memset(report, 0, sizeof(*report));
    report->struct_size = REPORT_VERSION_SIZE;
    report->status = PHOTON_V6_SURFACE_TRANSACTION_INVALID_ARGUMENT;
}

static PhotonV6SurfaceTransactionStatus finish(
    PhotonV6SurfaceTransactionReport *report,
    PhotonV6SurfaceTransactionStatus status,
    PhotonV6CpuSurfaceStatus surface_status) {
    if (report) {
        report->status = (uint32_t)status;
        report->surface_status = (uint32_t)surface_status;
    }
    return status;
}

static int checked_logical_bytes(uint32_t width, uint32_t height,
                                 size_t *bytes) {
    uint64_t row;
    uint64_t total;
    if (!width || !height || !bytes) return 0;
    row = (uint64_t)width * 4U;
    total = row * height;
    if (row > SIZE_MAX || total > SIZE_MAX || total > UINT32_MAX) return 0;
    *bytes = (size_t)total;
    return 1;
}

static PhotonV6SurfaceTransactionStatus rollback_snapshot(
    const PhotonV6CpuSurfaceView *surface,
    uint32_t rect_x,
    uint32_t rect_y,
    uint32_t width,
    uint32_t height,
    const uint8_t *snapshot,
    size_t logical_bytes,
    uint8_t *readback,
    PhotonV6SurfaceTransactionReport *report,
    PhotonV6SurfaceTransactionStatus original_status,
    PhotonV6CpuSurfaceStatus original_surface_status) {
    PhotonV6CpuSurfaceView restore_view;
    const PhotonV6CpuSurfaceView *restore_surface = surface;
    PhotonV6CpuSurfaceStatus status;
    report->rollback_attempted = 1;
#ifdef PHOTON_V6_SURFACE_TRANSACTION_TEST_HOOKS
    if ((InterlockedCompareExchange(&test_fault, 0, 0) &
         PHOTON_V6_SURFACE_TRANSACTION_TEST_ROLLBACK_REJECTED) != 0) {
        restore_view = *surface;
        restore_view.memory_format = (PhotonV6CpuSurfaceFormat)UINT32_MAX;
        restore_surface = &restore_view;
    }
#else
    (void)restore_view;
#endif
    status = photon_v6_cpu_surface_write_rgba(
        restore_surface, rect_x, rect_y, width, height, snapshot,
        logical_bytes);
    if (status != PHOTON_V6_CPU_SURFACE_OK)
        return finish(report, PHOTON_V6_SURFACE_TRANSACTION_ROLLBACK_FAILED,
                      status);
    status = photon_v6_cpu_surface_read_rgba(
        surface, rect_x, rect_y, width, height, readback, logical_bytes);
    if (status != PHOTON_V6_CPU_SURFACE_OK)
        return finish(report, PHOTON_V6_SURFACE_TRANSACTION_ROLLBACK_FAILED,
                      status);
    report->restored_rgba_fnv1a64 = fnv1a64(readback, logical_bytes);
    if (memcmp(snapshot, readback, logical_bytes) != 0)
        return finish(report, PHOTON_V6_SURFACE_TRANSACTION_ROLLBACK_FAILED,
                      PHOTON_V6_CPU_SURFACE_OK);
    report->rollback_succeeded = 1;
    report->destination_committed = 0;
    return finish(report, original_status, original_surface_status);
}

PhotonV6SurfaceTransactionStatus photon_v6_surface_transaction_apply(
    const PhotonV6CpuSurfaceView *surface,
    uint32_t rect_x,
    uint32_t rect_y,
    uint32_t width,
    uint32_t height,
    const uint8_t *logical_rgba,
    size_t logical_bytes,
    PhotonV6SurfaceTransactionReport *report) {
    HANDLE heap = GetProcessHeap();
    uint8_t *snapshot = NULL;
    uint8_t *readback = NULL;
    uint8_t *fault_pixels = NULL;
    const uint8_t *write_pixels = logical_rgba;
    size_t expected_bytes = 0;
    PhotonV6CpuSurfaceStatus surface_status =
        PHOTON_V6_CPU_SURFACE_INVALID_ARGUMENT;
    PhotonV6SurfaceTransactionStatus result =
        PHOTON_V6_SURFACE_TRANSACTION_INVALID_ARGUMENT;
    zero_report(report);
    if (!surface || !logical_rgba || !report ||
        !checked_logical_bytes(width, height, &expected_bytes) ||
        logical_bytes != expected_bytes)
        return finish(report, PHOTON_V6_SURFACE_TRANSACTION_INVALID_ARGUMENT,
                      surface_status);
    report->logical_bytes = (uint32_t)logical_bytes;
    report->requested_rgba_fnv1a64 = fnv1a64(logical_rgba, logical_bytes);
    snapshot = (uint8_t *)HeapAlloc(heap, 0, logical_bytes);
    readback = (uint8_t *)HeapAlloc(heap, 0, logical_bytes);
    if (!snapshot || !readback) {
        result = PHOTON_V6_SURFACE_TRANSACTION_ALLOCATION_ERROR;
        goto cleanup;
    }
    surface_status = photon_v6_cpu_surface_read_rgba(
        surface, rect_x, rect_y, width, height, snapshot, logical_bytes);
    if (surface_status != PHOTON_V6_CPU_SURFACE_OK) {
        result = PHOTON_V6_SURFACE_TRANSACTION_SNAPSHOT_READ_FAILED;
        goto cleanup;
    }
    report->original_rgba_fnv1a64 = fnv1a64(snapshot, logical_bytes);
#ifdef PHOTON_V6_SURFACE_TRANSACTION_TEST_HOOKS
    if ((InterlockedCompareExchange(&test_fault, 0, 0) &
         PHOTON_V6_SURFACE_TRANSACTION_TEST_READBACK_MISMATCH) != 0) {
        fault_pixels = (uint8_t *)HeapAlloc(heap, 0, logical_bytes);
        if (!fault_pixels) {
            result = PHOTON_V6_SURFACE_TRANSACTION_ALLOCATION_ERROR;
            goto cleanup;
        }
        memcpy(fault_pixels, logical_rgba, logical_bytes);
        fault_pixels[0] ^= 0x01U;
        write_pixels = fault_pixels;
    }
#endif
    surface_status = photon_v6_cpu_surface_write_rgba(
        surface, rect_x, rect_y, width, height, write_pixels, logical_bytes);
    if (surface_status != PHOTON_V6_CPU_SURFACE_OK) {
        result = PHOTON_V6_SURFACE_TRANSACTION_WRITE_FAILED;
        goto cleanup;
    }
    surface_status = photon_v6_cpu_surface_read_rgba(
        surface, rect_x, rect_y, width, height, readback, logical_bytes);
    if (surface_status != PHOTON_V6_CPU_SURFACE_OK) {
        result = rollback_snapshot(
            surface, rect_x, rect_y, width, height, snapshot, logical_bytes,
            readback, report, PHOTON_V6_SURFACE_TRANSACTION_READBACK_FAILED,
            surface_status);
        goto cleanup;
    }
    report->readback_rgba_fnv1a64 = fnv1a64(readback, logical_bytes);
    if (memcmp(logical_rgba, readback, logical_bytes) != 0) {
        result = rollback_snapshot(
            surface, rect_x, rect_y, width, height, snapshot, logical_bytes,
            readback, report, PHOTON_V6_SURFACE_TRANSACTION_READBACK_MISMATCH,
            PHOTON_V6_CPU_SURFACE_OK);
        goto cleanup;
    }
    report->destination_committed = 1;
    result = PHOTON_V6_SURFACE_TRANSACTION_OK;
cleanup:
    if (fault_pixels) HeapFree(heap, 0, fault_pixels);
    if (readback) HeapFree(heap, 0, readback);
    if (snapshot) HeapFree(heap, 0, snapshot);
    if (report->rollback_attempted) return result;
    return finish(report, result, surface_status);
}
