/* Synthetic host contract and sidecar transaction test. No game decoder is executed. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <wchar.h>

#include "photon_v6_exact_rgba_sidecar_loader.h"
#include "photon_v6_pm_native_runtime.h"
#include "photon_v6_runtime_api.h"

#if !defined(__i386__) && !defined(_M_IX86)
#error photon_v6_pm_crip008_ordinary_fixture requires x86
#endif

#define CHECK(value) do { if (!(value)) { \
    fprintf(stderr, "fixture check failed at line %d: %s\n", \
            __LINE__, #value); return 1; } } while (0)

enum {
    IMAGE_BYTES = 0x00386000,
    LOAD_SLOT = 0x0023C334,
    LOAD_TARGET = 0x0017FB30,
    SURFACE_SLOT = 0x0023C300,
    SURFACE_TARGET = 0x001801E0,
    RECT_SLOT = 0x0023C308,
    RECT_TARGET = 0x001803F0,
    CR6_DECODE_SITE = 0x00180CEE,
    CR6_DECODE_TARGET = 0x0017EB80,
    CR6_ALT_DECODE_SITE0 = 0x0018093C,
    CR6_ALT_DECODE_SITE1 = 0x00180A29,
    CRIP008_DECODE_SITE = 0x0017B460,
    CRIP008_DIRECT_DECODE_SITE0 = 0x00179218,
    CRIP008_DIRECT_DECODE_SITE1 = 0x001792F1,
    COOKIE = 0x0026F014,
    RECORD_PAYLOAD_OFFSET = 0x29
};

void photon_v6_native_test_set_main_base(void *base);
void *__attribute__((cdecl)) photon_v6_pm_crip008_direct_decode_prepare(
    const BYTE *payload, uint32_t payload_bytes, const void *flags_table,
    BYTE *destination, int32_t decoder_pitch,
    uint32_t target_left_top, uint32_t target_right_bottom);
void __attribute__((cdecl)) photon_v6_pm_crip008_decode_commit(void *opaque);

static const BYTE decode_prefix[] = {
    0x55,0x8B,0xEC,0x83,0xEC,0x14,0xA1
};
static const BYTE decode_suffix[] = {
    0x33,0xC5,0x89,0x45,0xFC,0x0F,0xBF,0x45,0x14,0x8B,0xD1,
    0x0F,0xBF,0x4D,0x10,0x53,0x2B,0xC1,0x56,0x57,0x3D
};
static const BYTE cr6_call[] = {0xE8,0x8D,0xDE,0xFF,0xFF};
static const BYTE cr6_alt_call0[] = {0xE8,0x0F,0xDB,0xFF,0xFF};
static const BYTE cr6_alt_call1[] = {0xE8,0x22,0xDA,0xFF,0xFF};
static const BYTE crip008_call[] = {0xE8,0x2B,0x00,0x00,0x00};
static const BYTE crip008_direct_call0[] = {0xE8,0x23,0x15,0x00,0x00};
static const BYTE crip008_direct_call1[] = {0xE8,0x4A,0x14,0x00,0x00};


static uint64_t fnv1a64(const BYTE *data, uint32_t bytes) {
    uint64_t value = UINT64_C(14695981039346656037);
    uint32_t index;
    for (index = 0; index < bytes; ++index) {
        value ^= data[index];
        value *= UINT64_C(1099511628211);
    }
    return value;
}

static BYTE *read_payload(const wchar_t *archive,
                          uint32_t record_offset,
                          uint32_t payload_bytes) {
    HANDLE file;
    LARGE_INTEGER size, offset;
    BYTE *payload;
    DWORD read = 0;
    file = CreateFileW(archive, GENERIC_READ, FILE_SHARE_READ, NULL,
                       OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE || !GetFileSizeEx(file, &size)) {
        if (file != INVALID_HANDLE_VALUE) CloseHandle(file);
        return NULL;
    }
    offset.QuadPart = (LONGLONG)record_offset + RECORD_PAYLOAD_OFFSET;
    if (size.QuadPart < offset.QuadPart + payload_bytes) {
        CloseHandle(file);
        return NULL;
    }
    payload = (BYTE *)HeapAlloc(
        GetProcessHeap(), HEAP_ZERO_MEMORY, payload_bytes + 4U);
    if (!payload || !SetFilePointerEx(file, offset, NULL, FILE_BEGIN) ||
        !ReadFile(file, payload, payload_bytes, &read, NULL) ||
        read != payload_bytes) {
        if (payload) HeapFree(GetProcessHeap(), 0, payload);
        payload = NULL;
    }
    CloseHandle(file);
    return payload;
}

int photon_v6_pm_selector_test_synthesize_image(BYTE *, uint32_t);
void photon_v6_native_test_set_no_hot_lifecycle(LONG);
static int synthesize(BYTE *image) {
    IMAGE_DOS_HEADER *dos = (IMAGE_DOS_HEADER *)image;
    IMAGE_NT_HEADERS32 *nt = (IMAGE_NT_HEADERS32 *)(image + 0x100);
    BYTE *decoder = image + CR6_DECODE_TARGET;
    if (!photon_v6_pm_selector_test_synthesize_image(image, IMAGE_BYTES)) return 0;
    dos->e_magic = IMAGE_DOS_SIGNATURE;
    dos->e_lfanew = 0x100;
    nt->Signature = IMAGE_NT_SIGNATURE;
    nt->FileHeader.Machine = IMAGE_FILE_MACHINE_I386;
    nt->FileHeader.TimeDateStamp = 0x5D319898;
    nt->OptionalHeader.Magic = IMAGE_NT_OPTIONAL_HDR32_MAGIC;
    nt->OptionalHeader.SizeOfImage = IMAGE_BYTES;
    memcpy(decoder, decode_prefix, sizeof(decode_prefix));
    *(uint32_t *)(decoder + sizeof(decode_prefix)) =
        (uint32_t)(uintptr_t)(image + COOKIE);
    memcpy(decoder + sizeof(decode_prefix) + sizeof(uint32_t),
           decode_suffix, sizeof(decode_suffix));
    *(void **)(image + LOAD_SLOT) = image + LOAD_TARGET;
    *(void **)(image + SURFACE_SLOT) = image + SURFACE_TARGET;
    *(void **)(image + RECT_SLOT) = image + RECT_TARGET;
    memcpy(image + CR6_DECODE_SITE, cr6_call, sizeof(cr6_call));
    memcpy(image + CR6_ALT_DECODE_SITE0, cr6_alt_call0,
           sizeof(cr6_alt_call0));
    memcpy(image + CR6_ALT_DECODE_SITE1, cr6_alt_call1,
           sizeof(cr6_alt_call1));
    memcpy(image + CRIP008_DECODE_SITE, crip008_call,
           sizeof(crip008_call));
    memcpy(image + CRIP008_DIRECT_DECODE_SITE0, crip008_direct_call0,
           sizeof(crip008_direct_call0));
    memcpy(image + CRIP008_DIRECT_DECODE_SITE1, crip008_direct_call1,
           sizeof(crip008_direct_call1));
    return 1;
}

static int all_byte(const BYTE *data, size_t bytes, BYTE value) {
    size_t index;
    for (index = 0; index < bytes; ++index)
        if (data[index] != value) return 0;
    return 1;
}

static int surface_equals_rgba(const BYTE *logical_row_zero,
                               int32_t signed_stride,
                               const BYTE *rgba, uint32_t width, uint32_t height) {
    uint32_t x, y;
    for (y = 0; y < height; ++y) {
        const BYTE *actual = logical_row_zero + (intptr_t)y * signed_stride;
        const BYTE *expected = rgba + (size_t)y * width * 4;
        for (x = 0; x < width; ++x) {
            if (actual[x * 4U + 0U] != expected[x * 4U + 2U] ||
                actual[x * 4U + 1U] != expected[x * 4U + 1U] ||
                actual[x * 4U + 2U] != expected[x * 4U + 0U] ||
                actual[x * 4U + 3U] != expected[x * 4U + 3U])
                return 0;
        }
    }
    return 1;
}


void *__attribute__((cdecl)) photon_v6_pm_crip008_decode_prepare(
    const BYTE *, uint32_t, const void *, BYTE *, int32_t,
    uint32_t, uint32_t, uint32_t, uint32_t, int32_t);

int wmain(int argc, wchar_t **argv) {
    CHECK(argc == 7);
    uint32_t offset = wcstoul(argv[3], NULL, 0);
    uint32_t n = wcstoul(argv[4], NULL, 0);
    uint32_t width = wcstoul(argv[5], NULL, 0);
    uint32_t height = wcstoul(argv[6], NULL, 0);
    CHECK(width == 8 && height == 6 && n == 64 && offset == 0);
    CHECK(wcslen(argv[1]) < MAX_PATH);
    uint32_t row = width * 4, rect = width | (height << 16);
    size_t bytes = (size_t)row * height;
    BYTE *payload = read_payload(argv[2], offset, n);
    CHECK(payload);
    PhotonV6ExactRgbaImage expected = {0};
    PhotonV6PmNativeStatus status = {0};
    CHECK(photon_v6_exact_rgba_sidecar_load(
        argv[1], PHOTON_V6_EXACT_RGBA_GAME_PM, n,
        fnv1a64(payload, n), &expected) == 0);
    CHECK(expected.width == width && expected.height == height);
    BYTE *image = VirtualAlloc(NULL, IMAGE_BYTES,
        MEM_RESERVE | MEM_COMMIT, PAGE_EXECUTE_READWRITE);
    BYTE *surface = HeapAlloc(GetProcessHeap(), 0, bytes);
    CHECK(image && surface && synthesize(image));
    photon_v6_native_test_set_main_base(image);
    photon_v6_native_test_set_no_hot_lifecycle(1);

    PhotonV6RuntimeConfig cfg = {0};
    cfg.struct_size = sizeof(cfg);
    cfg.abi_version = PHOTON_V6_RUNTIME_ABI_VERSION;
    cfg.game_id = PHOTON_V6_GAME_PM;
    cfg.runtime_authorized = 1;
    cfg.self_module = GetModuleHandleW(NULL);
    cfg.host_module = GetModuleHandleW(NULL);
    wcsncpy(cfg.package_root, argv[1], MAX_PATH - 1);
    int init_result = photon_v6_runtime_init(&cfg);
    if (init_result != PHOTON_V6_RUNTIME_READY) {
        status.struct_size = sizeof(status);
        photon_v6_pm_native_runtime_query(&status);
        fprintf(stderr, "production result=%d native=%u expected=%u selector=%u gate_disabled=%u\n",
            init_result, status.native_hooks_installed,
            status.native_expected_hook_count, status.selector_hooks_installed,
            status.semantic_gate_disabled);
        return 70;
    }
    CHECK(photon_v6_runtime_init(&cfg) == PHOTON_V6_RUNTIME_READY);

    for (int direct = 0; direct < 2; direct++) {
        for (int neg = 0; neg < 2; neg++) {
            BYTE *zero = neg ? surface + (height - 1) * row : surface;
            int32_t stride = neg ? -(int32_t)row : (int32_t)row;
            memset(surface, 0xA5, bytes);
            void *prepared = direct
                ? photon_v6_pm_crip008_direct_decode_prepare(
                    payload, n, NULL, zero, -stride, 0, rect)
                : photon_v6_pm_crip008_decode_prepare(
                    payload, n, NULL, zero, -stride, 0, rect, 0, rect, 0);
            CHECK(prepared && all_byte(surface, bytes, 0xA5));
            photon_v6_pm_crip008_decode_commit(prepared);
            CHECK(surface_equals_rgba(zero, stride, expected.pixels, width, height));
        }
    }
    memset(surface, 0x45, bytes);
    CHECK(!photon_v6_pm_crip008_decode_prepare(
        payload, n, NULL, surface, row, 0, rect, 1, rect, 0));
    CHECK(all_byte(surface, bytes, 0x45));
    status.struct_size = sizeof(status);
    photon_v6_pm_native_runtime_query(&status);
    CHECK(!status.fatal_latch && status.overlay_commits == 4 &&
          status.native_hooks_installed == 9);
    photon_v6_runtime_shutdown();
    printf("{\"passed\":true,\"direct_and_indexed\":true,\"positive_and_negative_pitch\":true}\n");
    return 0;
}
