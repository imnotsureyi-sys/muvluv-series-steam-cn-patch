#ifndef _WIN32_WINNT
#define _WIN32_WINNT 0x0601
#endif
#define WIN32_LEAN_AND_MEAN
#define COBJMACROS
#include <windows.h>
#include <objbase.h>
#include <objidl.h>
#include <wincodec.h>
#include <wincrypt.h>

#include <limits.h>
#include <stdint.h>
#include <string.h>
#include <wchar.h>

#include "photon_v6_exact_rgba_sidecar_loader.h"
#include "photon_v6_pf_exact_rgba_table.generated.h"
#include "photon_v6_pm_exact_rgba_table.generated.h"

#if !defined(__i386__) && !defined(_M_IX86)
#error photon_v6_exact_rgba_sidecar_loader must use the 32-bit Windows ABI.
#endif

#define PHOTON_V6_MAX_PNG_BYTES UINT32_C(268435456)
#define PHOTON_V6_MAX_PATH_CHARS UINT32_C(32767)

#ifdef PHOTON_V6_LOADER_TEST_HOOKS
static volatile LONG photon_v6_test_corrupt_decode = 0;

void photon_v6_exact_rgba_test_corrupt_next_decode(void) {
    InterlockedExchange(&photon_v6_test_corrupt_decode, 1);
}
#endif

static void image_zero(PhotonV6ExactRgbaImage *image) {
    if (image) memset(image, 0, sizeof(*image));
}

void photon_v6_exact_rgba_image_free(PhotonV6ExactRgbaImage *image) {
    if (!image) return;
    if (image->pixels) HeapFree(GetProcessHeap(), 0, image->pixels);
    image_zero(image);
}

static const PhotonV6ExactRgbaEntry *find_entry(
    PhotonV6ExactRgbaGame game,
    uint32_t payload_bytes,
    uint64_t payload_fnv1a64,
    PhotonV6ExactRgbaLoadStatus *failure) {
    const PhotonV6ExactRgbaEntry *table = NULL;
    uint32_t count = 0;
    uint32_t low = 0;
    uint32_t high;
    if (game == PHOTON_V6_EXACT_RGBA_GAME_PF) {
        table = photon_v6_pf_exact_rgba;
        count = photon_v6_pf_exact_rgba_count;
    } else if (game == PHOTON_V6_EXACT_RGBA_GAME_PM) {
        table = photon_v6_pm_exact_rgba;
        count = photon_v6_pm_exact_rgba_count;
    } else {
        *failure = PHOTON_V6_EXACT_RGBA_LOAD_UNKNOWN_GAME;
        return NULL;
    }
    high = count;
    while (low < high) {
        uint32_t middle = low + (high - low) / 2;
        const PhotonV6ExactRgbaEntry *candidate = &table[middle];
        if (candidate->payload_bytes < payload_bytes ||
            (candidate->payload_bytes == payload_bytes &&
             candidate->payload_fnv1a64 < payload_fnv1a64)) {
            low = middle + 1;
        } else {
            high = middle;
        }
    }
    if (low < count && table[low].payload_bytes == payload_bytes &&
        table[low].payload_fnv1a64 == payload_fnv1a64) {
        return &table[low];
    }
    *failure = PHOTON_V6_EXACT_RGBA_LOAD_UNKNOWN_IDENTITY;
    return NULL;
}

static int sha256_bytes(const BYTE *data, DWORD bytes, BYTE output[32]) {
    HCRYPTPROV provider = 0;
    HCRYPTHASH hash = 0;
    DWORD output_bytes = 32;
    int ok = data && output &&
             CryptAcquireContextW(&provider, NULL, NULL, PROV_RSA_AES,
                                  CRYPT_VERIFYCONTEXT) &&
             CryptCreateHash(provider, CALG_SHA_256, 0, 0, &hash) &&
             CryptHashData(hash, data, bytes, 0) &&
             CryptGetHashParam(hash, HP_HASHVAL, output, &output_bytes, 0) &&
             output_bytes == 32;
    if (hash) CryptDestroyHash(hash);
    if (provider) CryptReleaseContext(provider, 0);
    return ok;
}

static int has_device_prefix(const wchar_t *path) {
    return path &&
        ((path[0] == L'\\' && path[1] == L'\\' &&
          (path[2] == L'?' || path[2] == L'.') && path[3] == L'\\') ||
         (path[0] == L'\\' && path[1] == L'?' && path[2] == L'?' &&
          path[3] == L'\\'));
}

static wchar_t *canonical_full_path(const wchar_t *input) {
    DWORD required;
    DWORD written;
    wchar_t *result;
    if (!input || !input[0] || has_device_prefix(input)) return NULL;
    required = GetFullPathNameW(input, 0, NULL, NULL);
    if (!required || required > PHOTON_V6_MAX_PATH_CHARS) return NULL;
    result = (wchar_t *)HeapAlloc(GetProcessHeap(), 0,
                                  ((SIZE_T)required + 1) * sizeof(wchar_t));
    if (!result) return NULL;
    written = GetFullPathNameW(input, required + 1, result, NULL);
    if (!written || written > required || written > PHOTON_V6_MAX_PATH_CHARS) {
        HeapFree(GetProcessHeap(), 0, result);
        return NULL;
    }
    result[written] = L'\0';
    return result;
}

static wchar_t *extended_path(const wchar_t *canonical) {
    size_t length;
    size_t prefix;
    wchar_t *result;
    if (!canonical) return NULL;
    length = wcslen(canonical);
    if (!length || length > PHOTON_V6_MAX_PATH_CHARS) return NULL;
    if (canonical[0] == L'\\' && canonical[1] == L'\\') {
        prefix = 8;
        if (length > (size_t)PHOTON_V6_MAX_PATH_CHARS - 6) return NULL;
        result = (wchar_t *)HeapAlloc(GetProcessHeap(), 0,
                                      (length + 7) * sizeof(wchar_t));
        if (!result) return NULL;
        memcpy(result, L"\\\\?\\UNC\\", prefix * sizeof(wchar_t));
        memcpy(result + prefix, canonical + 2,
               (length - 1) * sizeof(wchar_t));
    } else {
        prefix = 4;
        if (length > (size_t)PHOTON_V6_MAX_PATH_CHARS - prefix) return NULL;
        result = (wchar_t *)HeapAlloc(GetProcessHeap(), 0,
                                      (length + prefix + 1) * sizeof(wchar_t));
        if (!result) return NULL;
        memcpy(result, L"\\\\?\\", prefix * sizeof(wchar_t));
        memcpy(result + prefix, canonical, (length + 1) * sizeof(wchar_t));
    }
    return result;
}

static size_t without_trailing_separators(const wchar_t *path) {
    size_t length = wcslen(path);
    while (length && (path[length - 1] == L'\\' || path[length - 1] == L'/'))
        --length;
    return length;
}

static int path_is_strict_child(const wchar_t *root, const wchar_t *candidate) {
    size_t root_length;
    size_t candidate_length;
    int comparison;
    if (!root || !candidate) return 0;
    root_length = without_trailing_separators(root);
    candidate_length = wcslen(candidate);
    if (!root_length || root_length > INT_MAX || candidate_length <= root_length)
        return 0;
    comparison = CompareStringOrdinal(root, (int)root_length,
                                      candidate, (int)root_length, TRUE);
    return comparison == CSTR_EQUAL &&
           (candidate[root_length] == L'\\' || candidate[root_length] == L'/');
}

static wchar_t *final_path_from_handle(HANDLE handle) {
    DWORD flags = FILE_NAME_NORMALIZED | VOLUME_NAME_DOS;
    DWORD required = GetFinalPathNameByHandleW(handle, NULL, 0, flags);
    DWORD written;
    wchar_t *result;
    if (!required || required > PHOTON_V6_MAX_PATH_CHARS) return NULL;
    result = (wchar_t *)HeapAlloc(GetProcessHeap(), 0,
                                  ((SIZE_T)required + 1) * sizeof(wchar_t));
    if (!result) return NULL;
    written = GetFinalPathNameByHandleW(handle, result, required + 1, flags);
    if (!written || written > required || written > PHOTON_V6_MAX_PATH_CHARS) {
        HeapFree(GetProcessHeap(), 0, result);
        return NULL;
    }
    result[written] = L'\0';
    return result;
}

static wchar_t *build_candidate_path(const wchar_t *canonical_root,
                                     PhotonV6ExactRgbaGame game,
                                     uint32_t payload_bytes,
                                     uint64_t payload_fnv1a64) {
    const wchar_t *game_name = game == PHOTON_V6_EXACT_RGBA_GAME_PF
                                   ? L"PF" : L"PM";
    size_t root_length = wcslen(canonical_root);
    size_t capacity;
    wchar_t *candidate;
    int written;
    if (root_length > (size_t)PHOTON_V6_MAX_PATH_CHARS - 64) return NULL;
    capacity = root_length + 64;
    candidate = (wchar_t *)HeapAlloc(GetProcessHeap(), 0,
                                     capacity * sizeof(wchar_t));
    if (!candidate) return NULL;
    written = _snwprintf(candidate, capacity,
                         L"%ls\\sidecars\\%ls\\%010lu_%016llX.png",
                         canonical_root, game_name, (unsigned long)payload_bytes,
                         (unsigned long long)payload_fnv1a64);
    if (written <= 0 || (size_t)written >= capacity) {
        HeapFree(GetProcessHeap(), 0, candidate);
        return NULL;
    }
    candidate[written] = L'\0';
    return candidate;
}

static PhotonV6ExactRgbaLoadStatus open_contained_sidecar(
    const wchar_t *bundle_root,
    PhotonV6ExactRgbaGame game,
    uint32_t payload_bytes,
    uint64_t payload_fnv1a64,
    HANDLE *output_file) {
    wchar_t *root_full = NULL;
    wchar_t *candidate_raw = NULL;
    wchar_t *candidate_full = NULL;
    wchar_t *root_extended = NULL;
    wchar_t *candidate_extended = NULL;
    wchar_t *root_final = NULL;
    wchar_t *candidate_final = NULL;
    HANDLE root_handle = INVALID_HANDLE_VALUE;
    HANDLE file_handle = INVALID_HANDLE_VALUE;
    BY_HANDLE_FILE_INFORMATION root_info;
    PhotonV6ExactRgbaLoadStatus status = PHOTON_V6_EXACT_RGBA_LOAD_PATH_REJECTED;
    *output_file = INVALID_HANDLE_VALUE;

    root_full = canonical_full_path(bundle_root);
    if (!root_full) goto done;
    candidate_raw = build_candidate_path(root_full, game, payload_bytes,
                                         payload_fnv1a64);
    if (!candidate_raw) {
        status = PHOTON_V6_EXACT_RGBA_LOAD_ALLOCATION_ERROR;
        goto done;
    }
    candidate_full = canonical_full_path(candidate_raw);
    if (!candidate_full || !path_is_strict_child(root_full, candidate_full))
        goto done;
    root_extended = extended_path(root_full);
    candidate_extended = extended_path(candidate_full);
    if (!root_extended || !candidate_extended) {
        status = PHOTON_V6_EXACT_RGBA_LOAD_ALLOCATION_ERROR;
        goto done;
    }
    root_handle = CreateFileW(root_extended, FILE_READ_ATTRIBUTES,
                              FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                              NULL, OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS, NULL);
    if (root_handle == INVALID_HANDLE_VALUE) goto done;
    if (!GetFileInformationByHandle(root_handle, &root_info) ||
        !(root_info.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY)) goto done;
    root_final = final_path_from_handle(root_handle);
    if (!root_final) goto done;

    file_handle = CreateFileW(candidate_extended, GENERIC_READ, FILE_SHARE_READ,
                              NULL, OPEN_EXISTING,
                              FILE_ATTRIBUTE_NORMAL | FILE_FLAG_SEQUENTIAL_SCAN,
                              NULL);
    if (file_handle == INVALID_HANDLE_VALUE) {
        status = PHOTON_V6_EXACT_RGBA_LOAD_IO_ERROR;
        goto done;
    }
    candidate_final = final_path_from_handle(file_handle);
    if (!candidate_final || !path_is_strict_child(root_final, candidate_final)) {
        status = PHOTON_V6_EXACT_RGBA_LOAD_PATH_REJECTED;
        goto done;
    }
    *output_file = file_handle;
    file_handle = INVALID_HANDLE_VALUE;
    status = PHOTON_V6_EXACT_RGBA_LOAD_OK;

done:
    if (file_handle != INVALID_HANDLE_VALUE) CloseHandle(file_handle);
    if (root_handle != INVALID_HANDLE_VALUE) CloseHandle(root_handle);
    if (candidate_final) HeapFree(GetProcessHeap(), 0, candidate_final);
    if (root_final) HeapFree(GetProcessHeap(), 0, root_final);
    if (candidate_extended) HeapFree(GetProcessHeap(), 0, candidate_extended);
    if (root_extended) HeapFree(GetProcessHeap(), 0, root_extended);
    if (candidate_full) HeapFree(GetProcessHeap(), 0, candidate_full);
    if (candidate_raw) HeapFree(GetProcessHeap(), 0, candidate_raw);
    if (root_full) HeapFree(GetProcessHeap(), 0, root_full);
    return status;
}

static PhotonV6ExactRgbaLoadStatus read_file_handle(
    HANDLE file, BYTE **output, DWORD *output_bytes) {
    LARGE_INTEGER size;
    BYTE *data = NULL;
    DWORD total = 0;
    *output = NULL;
    *output_bytes = 0;
    if (!GetFileSizeEx(file, &size) || size.QuadPart <= 0 ||
        size.QuadPart > PHOTON_V6_MAX_PNG_BYTES)
        return PHOTON_V6_EXACT_RGBA_LOAD_IO_ERROR;
    data = (BYTE *)HeapAlloc(GetProcessHeap(), 0, (SIZE_T)size.QuadPart);
    if (!data) return PHOTON_V6_EXACT_RGBA_LOAD_ALLOCATION_ERROR;
    while (total < (DWORD)size.QuadPart) {
        DWORD chunk = 0;
        if (!ReadFile(file, data + total, (DWORD)size.QuadPart - total,
                      &chunk, NULL) || !chunk) {
            HeapFree(GetProcessHeap(), 0, data);
            return PHOTON_V6_EXACT_RGBA_LOAD_IO_ERROR;
        }
        total += chunk;
    }
    *output = data;
    *output_bytes = total;
    return PHOTON_V6_EXACT_RGBA_LOAD_OK;
}

static PhotonV6ExactRgbaLoadStatus decode_wic_rgba(
    const BYTE *png,
    DWORD png_bytes,
    const PhotonV6ExactRgbaEntry *entry,
    BYTE **output,
    DWORD *output_bytes) {
    HRESULT com_status;
    int uninitialize = 0;
    IWICImagingFactory *factory = NULL;
    IWICBitmapDecoder *decoder = NULL;
    IWICBitmapFrameDecode *frame = NULL;
    IWICFormatConverter *converter = NULL;
    IStream *stream = NULL;
    HGLOBAL memory = NULL;
    void *memory_bytes = NULL;
    UINT frame_count = 0;
    UINT width = 0;
    UINT height = 0;
    uint64_t stride64;
    uint64_t bytes64;
    BYTE *rgba = NULL;
    PhotonV6ExactRgbaLoadStatus status = PHOTON_V6_EXACT_RGBA_LOAD_DECODE_ERROR;
    *output = NULL;
    *output_bytes = 0;

    com_status = CoInitializeEx(NULL, COINIT_MULTITHREADED);
    if (SUCCEEDED(com_status)) {
        uninitialize = 1;
    } else if (com_status != RPC_E_CHANGED_MODE) {
        return PHOTON_V6_EXACT_RGBA_LOAD_COM_ERROR;
    }
    com_status = CoCreateInstance(&CLSID_WICImagingFactory, NULL,
                                  CLSCTX_INPROC_SERVER,
                                  &IID_IWICImagingFactory,
                                  (void **)&factory);
    if (FAILED(com_status) || !factory) {
        status = PHOTON_V6_EXACT_RGBA_LOAD_COM_ERROR;
        goto done;
    }
    memory = GlobalAlloc(GMEM_MOVEABLE, png_bytes);
    if (!memory) {
        status = PHOTON_V6_EXACT_RGBA_LOAD_ALLOCATION_ERROR;
        goto done;
    }
    memory_bytes = GlobalLock(memory);
    if (!memory_bytes) {
        status = PHOTON_V6_EXACT_RGBA_LOAD_ALLOCATION_ERROR;
        goto done;
    }
    memcpy(memory_bytes, png, png_bytes);
    GlobalUnlock(memory);
    memory_bytes = NULL;
    com_status = CreateStreamOnHGlobal(memory, TRUE, &stream);
    if (FAILED(com_status) || !stream) goto done;
    memory = NULL;
    com_status = IWICImagingFactory_CreateDecoderFromStream(
        factory, stream, NULL, WICDecodeMetadataCacheOnLoad, &decoder);
    if (SUCCEEDED(com_status) && !decoder) com_status = E_FAIL;
    if (SUCCEEDED(com_status))
        com_status = IWICBitmapDecoder_GetFrameCount(decoder, &frame_count);
    if (SUCCEEDED(com_status) && frame_count != 1) com_status = E_FAIL;
    if (SUCCEEDED(com_status))
        com_status = IWICBitmapDecoder_GetFrame(decoder, 0, &frame);
    if (SUCCEEDED(com_status) && !frame) com_status = E_FAIL;
    if (SUCCEEDED(com_status))
        com_status = IWICBitmapFrameDecode_GetSize(frame, &width, &height);
    if (SUCCEEDED(com_status) &&
        (width != entry->width || height != entry->height)) {
        status = PHOTON_V6_EXACT_RGBA_LOAD_GEOMETRY_MISMATCH;
        com_status = E_INVALIDARG;
    }
    if (SUCCEEDED(com_status))
        com_status = IWICImagingFactory_CreateFormatConverter(factory, &converter);
    if (SUCCEEDED(com_status) && !converter) com_status = E_FAIL;
    if (SUCCEEDED(com_status))
        com_status = IWICFormatConverter_Initialize(
            converter, (IWICBitmapSource *)frame, &GUID_WICPixelFormat32bppRGBA,
            WICBitmapDitherTypeNone, NULL, 0.0, WICBitmapPaletteTypeCustom);
    stride64 = (uint64_t)width * 4U;
    bytes64 = stride64 * height;
    if (SUCCEEDED(com_status) &&
        (!width || !height || stride64 > UINT32_MAX || bytes64 > UINT32_MAX)) {
        status = PHOTON_V6_EXACT_RGBA_LOAD_ALLOCATION_ERROR;
        com_status = E_OUTOFMEMORY;
    }
    if (SUCCEEDED(com_status)) {
        rgba = (BYTE *)HeapAlloc(GetProcessHeap(), 0, (SIZE_T)bytes64);
        if (!rgba) {
            status = PHOTON_V6_EXACT_RGBA_LOAD_ALLOCATION_ERROR;
            com_status = E_OUTOFMEMORY;
        }
    }
    if (SUCCEEDED(com_status))
        com_status = IWICFormatConverter_CopyPixels(
            converter, NULL, (UINT)stride64, (UINT)bytes64, rgba);
    if (SUCCEEDED(com_status)) {
        *output = rgba;
        *output_bytes = (DWORD)bytes64;
        rgba = NULL;
        status = PHOTON_V6_EXACT_RGBA_LOAD_OK;
    }

done:
    if (rgba) HeapFree(GetProcessHeap(), 0, rgba);
    if (converter) IWICFormatConverter_Release(converter);
    if (frame) IWICBitmapFrameDecode_Release(frame);
    if (decoder) IWICBitmapDecoder_Release(decoder);
    if (stream) IStream_Release(stream);
    if (memory_bytes) GlobalUnlock(memory);
    if (memory) GlobalFree(memory);
    if (factory) IWICImagingFactory_Release(factory);
    if (uninitialize) CoUninitialize();
    return status;
}

PhotonV6ExactRgbaLoadStatus photon_v6_exact_rgba_sidecar_load(
    const wchar_t *bundle_root,
    PhotonV6ExactRgbaGame game,
    uint32_t payload_bytes,
    uint64_t payload_fnv1a64,
    PhotonV6ExactRgbaImage *output) {
    PhotonV6ExactRgbaLoadStatus status = PHOTON_V6_EXACT_RGBA_LOAD_INTERNAL_ERROR;
    const PhotonV6ExactRgbaEntry *entry;
    HANDLE file = INVALID_HANDLE_VALUE;
    BYTE *png = NULL;
    DWORD png_bytes = 0;
    BYTE observed_sha[32];
    BYTE *rgba = NULL;
    DWORD rgba_bytes = 0;
    PhotonV6ExactRgbaImage result;
    image_zero(&result);
    if (!output) return PHOTON_V6_EXACT_RGBA_LOAD_INVALID_ARGUMENT;
    image_zero(output);
    if (!bundle_root || !bundle_root[0])
        return PHOTON_V6_EXACT_RGBA_LOAD_INVALID_ARGUMENT;
    entry = find_entry(game, payload_bytes, payload_fnv1a64, &status);
    if (!entry) return status;
    status = open_contained_sidecar(bundle_root, game, payload_bytes,
                                    payload_fnv1a64, &file);
    if (status != PHOTON_V6_EXACT_RGBA_LOAD_OK) goto done;
    status = read_file_handle(file, &png, &png_bytes);
    if (status != PHOTON_V6_EXACT_RGBA_LOAD_OK) goto done;
    if (!sha256_bytes(png, png_bytes, observed_sha)) {
        status = PHOTON_V6_EXACT_RGBA_LOAD_INTERNAL_ERROR;
        goto done;
    }
    if (memcmp(observed_sha, entry->png_sha256, 32) != 0) {
        status = PHOTON_V6_EXACT_RGBA_LOAD_PNG_HASH_MISMATCH;
        goto done;
    }
#ifdef PHOTON_V6_LOADER_TEST_HOOKS
    if (InterlockedExchange(&photon_v6_test_corrupt_decode, 0) && png_bytes)
        png[0] ^= 0xFF;
#endif
    status = decode_wic_rgba(png, png_bytes, entry, &rgba, &rgba_bytes);
    if (status != PHOTON_V6_EXACT_RGBA_LOAD_OK) goto done;
    if (!sha256_bytes(rgba, rgba_bytes, observed_sha)) {
        status = PHOTON_V6_EXACT_RGBA_LOAD_INTERNAL_ERROR;
        goto done;
    }
    if (memcmp(observed_sha, entry->logical_rgba_sha256, 32) != 0) {
        status = PHOTON_V6_EXACT_RGBA_LOAD_RGBA_HASH_MISMATCH;
        goto done;
    }
    result.pixels = rgba;
    result.width = entry->width;
    result.height = entry->height;
    result.stride = entry->width * 4U;
    result.bytes = rgba_bytes;
    rgba = NULL;
    *output = result;
    status = PHOTON_V6_EXACT_RGBA_LOAD_OK;

done:
    if (rgba) HeapFree(GetProcessHeap(), 0, rgba);
    if (png) HeapFree(GetProcessHeap(), 0, png);
    if (file != INVALID_HANDLE_VALUE) CloseHandle(file);
    if (status != PHOTON_V6_EXACT_RGBA_LOAD_OK) image_zero(output);
    return status;
}
