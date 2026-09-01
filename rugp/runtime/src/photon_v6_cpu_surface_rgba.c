#ifndef _WIN32_WINNT
#define _WIN32_WINNT 0x0601
#endif
#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include <limits.h>
#include <stdint.h>
#include <stddef.h>

#include "photon_v6_cpu_surface_rgba.h"

#if !defined(__i386__) && !defined(_M_IX86)
#error photon_v6_cpu_surface_rgba must use the 32-bit Windows ABI.
#endif

typedef struct SurfacePlan {
    uintptr_t bounds_start;
    uintptr_t bounds_end;
    uintptr_t base;
    uint32_t row_bytes;
    size_t logical_bytes;
    void *allocation_id;
} SurfacePlan;

static int protection_readable(DWORD protection) {
    DWORD base = protection & 0xFFU;
    return base == PAGE_READONLY || base == PAGE_READWRITE ||
           base == PAGE_WRITECOPY || base == PAGE_EXECUTE_READ ||
           base == PAGE_EXECUTE_READWRITE || base == PAGE_EXECUTE_WRITECOPY;
}

static int protection_writable(DWORD protection) {
    DWORD base = protection & 0xFFU;
    return base == PAGE_READWRITE || base == PAGE_WRITECOPY ||
           base == PAGE_EXECUTE_READWRITE || base == PAGE_EXECUTE_WRITECOPY;
}

static PhotonV6CpuSurfaceStatus checked_end(uintptr_t start, size_t bytes,
                                            uintptr_t *end) {
    if (!bytes || bytes > UINTPTR_MAX - start)
        return PHOTON_V6_CPU_SURFACE_OVERFLOW;
    *end = start + bytes;
    return PHOTON_V6_CPU_SURFACE_OK;
}

static PhotonV6CpuSurfaceStatus virtual_span(
    uintptr_t start, size_t bytes, int writable, void **allocation_id) {
    uintptr_t end;
    uintptr_t cursor;
    void *expected_allocation = allocation_id ? *allocation_id : NULL;
    PhotonV6CpuSurfaceStatus status = checked_end(start, bytes, &end);
    if (status != PHOTON_V6_CPU_SURFACE_OK) return status;
    cursor = start;
    while (cursor < end) {
        MEMORY_BASIC_INFORMATION info;
        uintptr_t region_end;
        if (!VirtualQuery((const void *)cursor, &info, sizeof(info)))
            return PHOTON_V6_CPU_SURFACE_MEMORY_REJECTED;
        if (info.State != MEM_COMMIT)
            return PHOTON_V6_CPU_SURFACE_MEMORY_REJECTED;
        if ((info.Protect & PAGE_GUARD) != 0)
            return PHOTON_V6_CPU_SURFACE_GUARD_REJECTED;
        if ((info.Protect & PAGE_NOACCESS) != 0 ||
            (writable ? !protection_writable(info.Protect)
                      : !protection_readable(info.Protect)))
            return PHOTON_V6_CPU_SURFACE_MEMORY_REJECTED;
        if (!expected_allocation) expected_allocation = info.AllocationBase;
        if (info.AllocationBase != expected_allocation)
            return PHOTON_V6_CPU_SURFACE_BOUNDS_REJECTED;
        if ((uintptr_t)info.BaseAddress > UINTPTR_MAX - info.RegionSize)
            return PHOTON_V6_CPU_SURFACE_OVERFLOW;
        region_end = (uintptr_t)info.BaseAddress + info.RegionSize;
        if (region_end <= cursor)
            return PHOTON_V6_CPU_SURFACE_OVERFLOW;
        cursor = region_end < end ? region_end : end;
    }
    if (allocation_id) *allocation_id = expected_allocation;
    return PHOTON_V6_CPU_SURFACE_OK;
}

static PhotonV6CpuSurfaceStatus add_signed(
    uintptr_t base, int64_t offset, uintptr_t *result) {
    if (offset >= 0) {
        uint64_t value = (uint64_t)offset;
        if (value > UINTPTR_MAX - base)
            return PHOTON_V6_CPU_SURFACE_OVERFLOW;
        *result = base + (uintptr_t)value;
    } else {
        uint64_t magnitude = (uint64_t)(-(offset + 1)) + 1U;
        if (magnitude > base)
            return PHOTON_V6_CPU_SURFACE_OVERFLOW;
        *result = base - (uintptr_t)magnitude;
    }
    return PHOTON_V6_CPU_SURFACE_OK;
}

static PhotonV6CpuSurfaceStatus row_address(
    const PhotonV6CpuSurfaceView *surface,
    uint32_t rect_x,
    uint32_t rect_y,
    uint32_t logical_y,
    uintptr_t *address) {
    uint32_t surface_y = rect_y + logical_y;
    uint32_t storage_y = surface->row_orientation ==
                                 PHOTON_V6_CPU_SURFACE_ROWS_FORWARD
                             ? surface_y
                             : surface->surface_height - 1U - surface_y;
    int64_t row_offset = (int64_t)storage_y * surface->signed_stride;
    uintptr_t row;
    PhotonV6CpuSurfaceStatus status = add_signed((uintptr_t)surface->base,
                                                 row_offset, &row);
    uint64_t x_offset = (uint64_t)rect_x * 4U;
    if (status != PHOTON_V6_CPU_SURFACE_OK) return status;
    if (x_offset > UINTPTR_MAX - row)
        return PHOTON_V6_CPU_SURFACE_OVERFLOW;
    *address = row + (uintptr_t)x_offset;
    return PHOTON_V6_CPU_SURFACE_OK;
}

static int spans_overlap(uintptr_t first, size_t first_bytes,
                         uintptr_t second, size_t second_bytes) {
    uintptr_t first_end;
    uintptr_t second_end;
    if (checked_end(first, first_bytes, &first_end) !=
            PHOTON_V6_CPU_SURFACE_OK ||
        checked_end(second, second_bytes, &second_end) !=
            PHOTON_V6_CPU_SURFACE_OK)
        return 1;
    return first < second_end && second < first_end;
}

static PhotonV6CpuSurfaceStatus build_plan(
    const PhotonV6CpuSurfaceView *surface,
    uint32_t rect_x,
    uint32_t rect_y,
    uint32_t width,
    uint32_t height,
    int surface_writable,
    SurfacePlan *plan) {
    uint64_t surface_row_bytes;
    uint64_t logical_row_bytes;
    uint64_t logical_bytes;
    uint32_t absolute_stride;
    uintptr_t first_storage_row;
    uintptr_t first_storage_end;
    uintptr_t last_storage_row;
    uintptr_t last_storage_end;
    uintptr_t minimum;
    uintptr_t maximum;
    void *allocation_id = NULL;
    PhotonV6CpuSurfaceStatus status;
    if (!surface || !plan || !surface->bounds_base || !surface->base ||
        !surface->bounds_bytes || !surface->surface_width ||
        !surface->surface_height || !width || !height ||
        surface->signed_stride == INT32_MIN)
        return PHOTON_V6_CPU_SURFACE_INVALID_ARGUMENT;
    if (surface->memory_format != PHOTON_V6_CPU_SURFACE_BGRA8_STRAIGHT)
        return PHOTON_V6_CPU_SURFACE_UNSUPPORTED_FORMAT;
    if (surface->row_orientation != PHOTON_V6_CPU_SURFACE_ROWS_FORWARD &&
        surface->row_orientation != PHOTON_V6_CPU_SURFACE_ROWS_REVERSE)
        return PHOTON_V6_CPU_SURFACE_UNSUPPORTED_ORIENTATION;
    if (rect_x > surface->surface_width ||
        width > surface->surface_width - rect_x ||
        rect_y > surface->surface_height ||
        height > surface->surface_height - rect_y)
        return PHOTON_V6_CPU_SURFACE_BOUNDS_REJECTED;

    surface_row_bytes = (uint64_t)surface->surface_width * 4U;
    logical_row_bytes = (uint64_t)width * 4U;
    if (surface_row_bytes > UINT32_MAX || logical_row_bytes > UINT32_MAX ||
        logical_row_bytes > SIZE_MAX ||
        height > SIZE_MAX / (size_t)logical_row_bytes)
        return PHOTON_V6_CPU_SURFACE_OVERFLOW;
    logical_bytes = logical_row_bytes * height;
    absolute_stride = surface->signed_stride < 0
                          ? (uint32_t)(-surface->signed_stride)
                          : (uint32_t)surface->signed_stride;
    if (absolute_stride < surface_row_bytes)
        return PHOTON_V6_CPU_SURFACE_BOUNDS_REJECTED;

    status = checked_end((uintptr_t)surface->bounds_base,
                         surface->bounds_bytes, &plan->bounds_end);
    if (status != PHOTON_V6_CPU_SURFACE_OK) return status;
    plan->bounds_start = (uintptr_t)surface->bounds_base;
    plan->base = (uintptr_t)surface->base;
    if (plan->base < plan->bounds_start || plan->base >= plan->bounds_end)
        return PHOTON_V6_CPU_SURFACE_BOUNDS_REJECTED;
    status = virtual_span(plan->bounds_start, surface->bounds_bytes,
                          surface_writable, &allocation_id);
    if (status != PHOTON_V6_CPU_SURFACE_OK) return status;

    first_storage_row = plan->base;
    status = checked_end(first_storage_row, (size_t)surface_row_bytes,
                         &first_storage_end);
    if (status != PHOTON_V6_CPU_SURFACE_OK) return status;
    status = add_signed(plan->base,
                        (int64_t)(surface->surface_height - 1U) *
                            surface->signed_stride,
                        &last_storage_row);
    if (status != PHOTON_V6_CPU_SURFACE_OK) return status;
    status = checked_end(last_storage_row, (size_t)surface_row_bytes,
                         &last_storage_end);
    if (status != PHOTON_V6_CPU_SURFACE_OK) return status;
    minimum = first_storage_row < last_storage_row
                  ? first_storage_row : last_storage_row;
    maximum = first_storage_end > last_storage_end
                  ? first_storage_end : last_storage_end;
    if (minimum < plan->bounds_start || maximum > plan->bounds_end)
        return PHOTON_V6_CPU_SURFACE_BOUNDS_REJECTED;

    plan->row_bytes = (uint32_t)logical_row_bytes;
    plan->logical_bytes = (size_t)logical_bytes;
    plan->allocation_id = allocation_id;
    return PHOTON_V6_CPU_SURFACE_OK;
}

static PhotonV6CpuSurfaceStatus preflight_rows(
    const PhotonV6CpuSurfaceView *surface,
    const SurfacePlan *plan,
    uint32_t rect_x,
    uint32_t rect_y,
    uint32_t height,
    int surface_writable,
    uintptr_t external,
    size_t external_bytes) {
    uint32_t y;
    for (y = 0; y < height; ++y) {
        uintptr_t row;
        uintptr_t row_end;
        void *allocation_id = plan->allocation_id;
        PhotonV6CpuSurfaceStatus status = row_address(
            surface, rect_x, rect_y, y, &row);
        if (status != PHOTON_V6_CPU_SURFACE_OK) return status;
        status = checked_end(row, plan->row_bytes, &row_end);
        if (status != PHOTON_V6_CPU_SURFACE_OK) return status;
        if (row < plan->bounds_start || row_end > plan->bounds_end)
            return PHOTON_V6_CPU_SURFACE_BOUNDS_REJECTED;
        status = virtual_span(row, plan->row_bytes, surface_writable,
                              &allocation_id);
        if (status != PHOTON_V6_CPU_SURFACE_OK) return status;
        if (spans_overlap(row, plan->row_bytes, external, external_bytes))
            return PHOTON_V6_CPU_SURFACE_ALIAS_REJECTED;
    }
    return PHOTON_V6_CPU_SURFACE_OK;
}

PhotonV6CpuSurfaceStatus photon_v6_cpu_surface_write_rgba(
    const PhotonV6CpuSurfaceView *surface,
    uint32_t rect_x,
    uint32_t rect_y,
    uint32_t width,
    uint32_t height,
    const uint8_t *logical_rgba,
    size_t logical_bytes) {
    SurfacePlan plan;
    PhotonV6CpuSurfaceStatus status;
    uint32_t y;
    if (!logical_rgba) return PHOTON_V6_CPU_SURFACE_INVALID_ARGUMENT;
    status = build_plan(surface, rect_x, rect_y, width, height, 1, &plan);
    if (status != PHOTON_V6_CPU_SURFACE_OK) return status;
    if (logical_bytes != plan.logical_bytes)
        return PHOTON_V6_CPU_SURFACE_INVALID_ARGUMENT;
    status = virtual_span((uintptr_t)logical_rgba, logical_bytes, 0, NULL);
    if (status != PHOTON_V6_CPU_SURFACE_OK) return status;
    status = preflight_rows(surface, &plan, rect_x, rect_y, height, 1,
                            (uintptr_t)logical_rgba, logical_bytes);
    if (status != PHOTON_V6_CPU_SURFACE_OK) return status;
    for (y = 0; y < height; ++y) {
        uintptr_t row_address_value;
        uint8_t *destination;
        const uint8_t *source = logical_rgba + (size_t)y * plan.row_bytes;
        uint32_t x;
        status = row_address(surface, rect_x, rect_y, y,
                             &row_address_value);
        if (status != PHOTON_V6_CPU_SURFACE_OK) return status;
        destination = (uint8_t *)row_address_value;
        for (x = 0; x < width; ++x) {
            destination[x * 4U] = source[x * 4U + 2U];
            destination[x * 4U + 1U] = source[x * 4U + 1U];
            destination[x * 4U + 2U] = source[x * 4U];
            destination[x * 4U + 3U] = source[x * 4U + 3U];
        }
    }
    return PHOTON_V6_CPU_SURFACE_OK;
}

PhotonV6CpuSurfaceStatus photon_v6_cpu_surface_read_rgba(
    const PhotonV6CpuSurfaceView *surface,
    uint32_t rect_x,
    uint32_t rect_y,
    uint32_t width,
    uint32_t height,
    uint8_t *output_rgba,
    size_t output_bytes) {
    SurfacePlan plan;
    PhotonV6CpuSurfaceStatus status;
    uint32_t y;
    if (!output_rgba) return PHOTON_V6_CPU_SURFACE_INVALID_ARGUMENT;
    status = build_plan(surface, rect_x, rect_y, width, height, 0, &plan);
    if (status != PHOTON_V6_CPU_SURFACE_OK) return status;
    if (output_bytes != plan.logical_bytes)
        return PHOTON_V6_CPU_SURFACE_INVALID_ARGUMENT;
    status = virtual_span((uintptr_t)output_rgba, output_bytes, 1, NULL);
    if (status != PHOTON_V6_CPU_SURFACE_OK) return status;
    status = preflight_rows(surface, &plan, rect_x, rect_y, height, 0,
                            (uintptr_t)output_rgba, output_bytes);
    if (status != PHOTON_V6_CPU_SURFACE_OK) return status;
    for (y = 0; y < height; ++y) {
        uintptr_t row_address_value;
        const uint8_t *source;
        uint8_t *destination = output_rgba + (size_t)y * plan.row_bytes;
        uint32_t x;
        status = row_address(surface, rect_x, rect_y, y,
                             &row_address_value);
        if (status != PHOTON_V6_CPU_SURFACE_OK) return status;
        source = (const uint8_t *)row_address_value;
        for (x = 0; x < width; ++x) {
            destination[x * 4U] = source[x * 4U + 2U];
            destination[x * 4U + 1U] = source[x * 4U + 1U];
            destination[x * 4U + 2U] = source[x * 4U];
            destination[x * 4U + 3U] = source[x * 4U + 3U];
        }
    }
    return PHOTON_V6_CPU_SURFACE_OK;
}
