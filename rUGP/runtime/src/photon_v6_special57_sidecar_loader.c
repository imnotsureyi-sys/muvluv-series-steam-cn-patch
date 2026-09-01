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

#include "photon_v6_special57_sidecar_loader.h"
#include "photon_v6_special57_table.generated.h"

#if !defined(__i386__) && !defined(_M_IX86)
#error photon_v6_special57_sidecar_loader must use the 32-bit Windows ABI.
#endif

#define SPECIAL57_MAX_PNG_BYTES UINT32_C(268435456)
#define SPECIAL57_MAX_PATH_CHARS UINT32_C(32767)

#ifdef PHOTON_V6_SPECIAL57_TEST_HOOKS
static volatile LONG special57_corrupt_decode = 0;
void photon_v6_special57_test_corrupt_next_decode(void) {
    InterlockedExchange(&special57_corrupt_decode, 1);
}
#endif

static void image_zero(PhotonV6Special57Image *image) {
    if (image) memset(image, 0, sizeof(*image));
}

void photon_v6_special57_image_free(PhotonV6Special57Image *image) {
    if (!image) return;
    if (image->pixels) HeapFree(GetProcessHeap(), 0, image->pixels);
    image_zero(image);
}

static const PhotonV6Special57Entry *find_entry(
    PhotonV6Special57Game game, const char *source_asset_id,
    PhotonV6Special57LoadStatus *failure) {
    size_t i;
    if (game != PHOTON_V6_SPECIAL57_GAME_PF &&
        game != PHOTON_V6_SPECIAL57_GAME_PM) {
        *failure = PHOTON_V6_SPECIAL57_LOAD_UNKNOWN_GAME;
        return NULL;
    }
    for (i = 0; i < PHOTON_V6_SPECIAL57_ENTRY_COUNT; ++i) {
        const PhotonV6Special57Entry *entry = &photon_v6_special57_entries[i];
        if (entry->game == (uint32_t)game &&
            strcmp(entry->source_asset_id, source_asset_id) == 0)
            return entry;
    }
    *failure = PHOTON_V6_SPECIAL57_LOAD_UNKNOWN_SOURCE;
    return NULL;
}

static int context_exact(const PhotonV6Special57Entry *entry,
                         const char *context_identity_key) {
    if (entry->context_route)
        return context_identity_key && context_identity_key[0] &&
               strcmp(entry->context_identity_key, context_identity_key) == 0;
    return !context_identity_key || !context_identity_key[0];
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

static int relative_path_safe(const wchar_t *path) {
    const wchar_t *cursor;
    if (!path || !path[0] || path[0] == L'\\' || path[0] == L'/' ||
        wcschr(path, L':')) return 0;
    cursor = path;
    while (*cursor) {
        const wchar_t *start = cursor;
        size_t length;
        while (*cursor && *cursor != L'\\' && *cursor != L'/') ++cursor;
        length = (size_t)(cursor - start);
        if (!length || (length == 1 && start[0] == L'.') ||
            (length == 2 && start[0] == L'.' && start[1] == L'.')) return 0;
        if (*cursor) ++cursor;
    }
    return 1;
}

static wchar_t *canonical_full_path(const wchar_t *input) {
    DWORD required, written;
    wchar_t *result;
    if (!input || !input[0] || has_device_prefix(input)) return NULL;
    required = GetFullPathNameW(input, 0, NULL, NULL);
    if (!required || required > SPECIAL57_MAX_PATH_CHARS) return NULL;
    result = (wchar_t *)HeapAlloc(GetProcessHeap(), 0,
                                  ((SIZE_T)required + 1) * sizeof(wchar_t));
    if (!result) return NULL;
    written = GetFullPathNameW(input, required + 1, result, NULL);
    if (!written || written > required || written > SPECIAL57_MAX_PATH_CHARS) {
        HeapFree(GetProcessHeap(), 0, result);
        return NULL;
    }
    result[written] = L'\0';
    return result;
}

static wchar_t *extended_path(const wchar_t *canonical) {
    size_t length, prefix;
    wchar_t *result;
    if (!canonical) return NULL;
    length = wcslen(canonical);
    if (!length || length > SPECIAL57_MAX_PATH_CHARS) return NULL;
    if (canonical[0] == L'\\' && canonical[1] == L'\\') {
        prefix = 8;
        if (length > (size_t)SPECIAL57_MAX_PATH_CHARS - 6) return NULL;
        result = (wchar_t *)HeapAlloc(GetProcessHeap(), 0,
                                      (length + 7) * sizeof(wchar_t));
        if (!result) return NULL;
        memcpy(result, L"\\\\?\\UNC\\", prefix * sizeof(wchar_t));
        memcpy(result + prefix, canonical + 2, (length - 1) * sizeof(wchar_t));
    } else {
        prefix = 4;
        if (length > (size_t)SPECIAL57_MAX_PATH_CHARS - prefix) return NULL;
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
    size_t root_length, candidate_length;
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
    DWORD required = GetFinalPathNameByHandleW(handle, NULL, 0, flags), written;
    wchar_t *result;
    if (!required || required > SPECIAL57_MAX_PATH_CHARS) return NULL;
    result = (wchar_t *)HeapAlloc(GetProcessHeap(), 0,
                                  ((SIZE_T)required + 1) * sizeof(wchar_t));
    if (!result) return NULL;
    written = GetFinalPathNameByHandleW(handle, result, required + 1, flags);
    if (!written || written > required || written > SPECIAL57_MAX_PATH_CHARS) {
        HeapFree(GetProcessHeap(), 0, result);
        return NULL;
    }
    result[written] = L'\0';
    return result;
}

static wchar_t *build_candidate_path(const wchar_t *root,
                                     const wchar_t *relative) {
    size_t root_length = wcslen(root), relative_length = wcslen(relative);
    size_t capacity;
    wchar_t *candidate;
    if (!relative_path_safe(relative) ||
        root_length > SPECIAL57_MAX_PATH_CHARS - relative_length - 2) return NULL;
    capacity = root_length + relative_length + 2;
    candidate = (wchar_t *)HeapAlloc(GetProcessHeap(), 0,
                                     capacity * sizeof(wchar_t));
    if (!candidate) return NULL;
    if (_snwprintf(candidate, capacity, L"%ls\\%ls", root, relative) <= 0) {
        HeapFree(GetProcessHeap(), 0, candidate);
        return NULL;
    }
    candidate[capacity - 1] = L'\0';
    return candidate;
}

static PhotonV6Special57LoadStatus open_contained_sidecar(
    const wchar_t *bundle_root, const PhotonV6Special57Entry *entry,
    HANDLE *output_file) {
    wchar_t *root_full = NULL, *candidate_raw = NULL, *candidate_full = NULL;
    wchar_t *root_extended = NULL, *candidate_extended = NULL;
    wchar_t *root_final = NULL, *candidate_final = NULL;
    HANDLE root_handle = INVALID_HANDLE_VALUE, file_handle = INVALID_HANDLE_VALUE;
    BY_HANDLE_FILE_INFORMATION root_info;
    PhotonV6Special57LoadStatus status = PHOTON_V6_SPECIAL57_LOAD_PATH_REJECTED;
    *output_file = INVALID_HANDLE_VALUE;
    root_full = canonical_full_path(bundle_root);
    if (!root_full) goto done;
    candidate_raw = build_candidate_path(root_full, entry->relative_path);
    if (!candidate_raw) goto done;
    candidate_full = canonical_full_path(candidate_raw);
    if (!candidate_full || !path_is_strict_child(root_full, candidate_full)) goto done;
    root_extended = extended_path(root_full);
    candidate_extended = extended_path(candidate_full);
    if (!root_extended || !candidate_extended) {
        status = PHOTON_V6_SPECIAL57_LOAD_ALLOCATION_ERROR;
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
                              FILE_ATTRIBUTE_NORMAL | FILE_FLAG_SEQUENTIAL_SCAN, NULL);
    if (file_handle == INVALID_HANDLE_VALUE) {
        status = PHOTON_V6_SPECIAL57_LOAD_IO_ERROR;
        goto done;
    }
    candidate_final = final_path_from_handle(file_handle);
    if (!candidate_final || !path_is_strict_child(root_final, candidate_final)) goto done;
    *output_file = file_handle;
    file_handle = INVALID_HANDLE_VALUE;
    status = PHOTON_V6_SPECIAL57_LOAD_OK;
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

static PhotonV6Special57LoadStatus read_file_handle(
    HANDLE file, BYTE **output, DWORD *output_bytes) {
    LARGE_INTEGER size;
    BYTE *data;
    DWORD total = 0;
    *output = NULL;
    *output_bytes = 0;
    if (!GetFileSizeEx(file, &size) || size.QuadPart <= 0 ||
        size.QuadPart > SPECIAL57_MAX_PNG_BYTES)
        return PHOTON_V6_SPECIAL57_LOAD_IO_ERROR;
    data = (BYTE *)HeapAlloc(GetProcessHeap(), 0, (SIZE_T)size.QuadPart);
    if (!data) return PHOTON_V6_SPECIAL57_LOAD_ALLOCATION_ERROR;
    while (total < (DWORD)size.QuadPart) {
        DWORD chunk = 0;
        if (!ReadFile(file, data + total, (DWORD)size.QuadPart - total,
                      &chunk, NULL) || !chunk) {
            HeapFree(GetProcessHeap(), 0, data);
            return PHOTON_V6_SPECIAL57_LOAD_IO_ERROR;
        }
        total += chunk;
    }
    *output = data;
    *output_bytes = total;
    return PHOTON_V6_SPECIAL57_LOAD_OK;
}

static PhotonV6Special57LoadStatus decode_wic_rgba(
    const BYTE *png, DWORD png_bytes, const PhotonV6Special57Entry *entry,
    BYTE **output, DWORD *output_bytes) {
    HRESULT hr;
    int uninitialize = 0;
    IWICImagingFactory *factory = NULL;
    IWICBitmapDecoder *decoder = NULL;
    IWICBitmapFrameDecode *frame = NULL;
    IWICFormatConverter *converter = NULL;
    IStream *stream = NULL;
    HGLOBAL memory = NULL;
    void *locked = NULL;
    UINT frames = 0, width = 0, height = 0;
    uint64_t stride64, bytes64;
    BYTE *rgba = NULL;
    PhotonV6Special57LoadStatus status = PHOTON_V6_SPECIAL57_LOAD_DECODE_ERROR;
    *output = NULL;
    *output_bytes = 0;
    hr = CoInitializeEx(NULL, COINIT_MULTITHREADED);
    if (SUCCEEDED(hr)) uninitialize = 1;
    else if (hr != RPC_E_CHANGED_MODE) return PHOTON_V6_SPECIAL57_LOAD_COM_ERROR;
    hr = CoCreateInstance(&CLSID_WICImagingFactory, NULL, CLSCTX_INPROC_SERVER,
                          &IID_IWICImagingFactory, (void **)&factory);
    if (FAILED(hr) || !factory) {
        status = PHOTON_V6_SPECIAL57_LOAD_COM_ERROR;
        goto done;
    }
    memory = GlobalAlloc(GMEM_MOVEABLE, png_bytes);
    if (!memory) { status = PHOTON_V6_SPECIAL57_LOAD_ALLOCATION_ERROR; goto done; }
    locked = GlobalLock(memory);
    if (!locked) { status = PHOTON_V6_SPECIAL57_LOAD_ALLOCATION_ERROR; goto done; }
    memcpy(locked, png, png_bytes);
    GlobalUnlock(memory);
    locked = NULL;
    hr = CreateStreamOnHGlobal(memory, TRUE, &stream);
    if (FAILED(hr) || !stream) goto done;
    memory = NULL;
    hr = IWICImagingFactory_CreateDecoderFromStream(
        factory, stream, NULL, WICDecodeMetadataCacheOnLoad, &decoder);
    if (SUCCEEDED(hr)) hr = IWICBitmapDecoder_GetFrameCount(decoder, &frames);
    if (SUCCEEDED(hr) && frames != 1) hr = E_FAIL;
    if (SUCCEEDED(hr)) hr = IWICBitmapDecoder_GetFrame(decoder, 0, &frame);
    if (SUCCEEDED(hr)) hr = IWICBitmapFrameDecode_GetSize(frame, &width, &height);
    if (SUCCEEDED(hr) && (width != entry->width || height != entry->height)) {
        status = PHOTON_V6_SPECIAL57_LOAD_GEOMETRY_MISMATCH;
        hr = E_INVALIDARG;
    }
    if (SUCCEEDED(hr)) hr = IWICImagingFactory_CreateFormatConverter(factory, &converter);
    if (SUCCEEDED(hr)) hr = IWICFormatConverter_Initialize(
        converter, (IWICBitmapSource *)frame, &GUID_WICPixelFormat32bppRGBA,
        WICBitmapDitherTypeNone, NULL, 0.0, WICBitmapPaletteTypeCustom);
    stride64 = (uint64_t)width * 4U;
    bytes64 = stride64 * height;
    if (SUCCEEDED(hr) && (!width || !height || stride64 > UINT32_MAX ||
                          bytes64 > UINT32_MAX)) {
        status = PHOTON_V6_SPECIAL57_LOAD_ALLOCATION_ERROR;
        hr = E_OUTOFMEMORY;
    }
    if (SUCCEEDED(hr)) {
        rgba = (BYTE *)HeapAlloc(GetProcessHeap(), 0, (SIZE_T)bytes64);
        if (!rgba) { status = PHOTON_V6_SPECIAL57_LOAD_ALLOCATION_ERROR; hr = E_OUTOFMEMORY; }
    }
    if (SUCCEEDED(hr)) hr = IWICFormatConverter_CopyPixels(
        converter, NULL, (UINT)stride64, (UINT)bytes64, rgba);
    if (SUCCEEDED(hr)) {
        *output = rgba;
        *output_bytes = (DWORD)bytes64;
        rgba = NULL;
        status = PHOTON_V6_SPECIAL57_LOAD_OK;
    }
done:
    if (rgba) HeapFree(GetProcessHeap(), 0, rgba);
    if (converter) IWICFormatConverter_Release(converter);
    if (frame) IWICBitmapFrameDecode_Release(frame);
    if (decoder) IWICBitmapDecoder_Release(decoder);
    if (stream) IStream_Release(stream);
    if (locked) GlobalUnlock(memory);
    if (memory) GlobalFree(memory);
    if (factory) IWICImagingFactory_Release(factory);
    if (uninitialize) CoUninitialize();
    return status;
}

PhotonV6Special57LoadStatus photon_v6_special57_sidecar_load(
    const wchar_t *bundle_root, PhotonV6Special57Game game,
    const char *source_asset_id, const char *context_identity_key,
    uint32_t physical_payload_bytes, uint64_t physical_payload_fnv1a64,
    PhotonV6Special57Image *output) {
    PhotonV6Special57LoadStatus status = PHOTON_V6_SPECIAL57_LOAD_INTERNAL_ERROR;
    const PhotonV6Special57Entry *entry;
    HANDLE file = INVALID_HANDLE_VALUE;
    BYTE *png = NULL, *rgba = NULL;
    DWORD png_bytes = 0, rgba_bytes = 0;
    BYTE digest[32];
    PhotonV6Special57Image result;
    image_zero(&result);
    if (!output) return PHOTON_V6_SPECIAL57_LOAD_INVALID_ARGUMENT;
    image_zero(output);
    if (!bundle_root || !bundle_root[0] || !source_asset_id || !source_asset_id[0])
        return PHOTON_V6_SPECIAL57_LOAD_INVALID_ARGUMENT;
    entry = find_entry(game, source_asset_id, &status);
    if (!entry) return status;
    if (!context_exact(entry, context_identity_key))
        return PHOTON_V6_SPECIAL57_LOAD_CONTEXT_MISMATCH;
    if (entry->payload_bytes != physical_payload_bytes ||
        entry->payload_fnv1a64 != physical_payload_fnv1a64)
        return PHOTON_V6_SPECIAL57_LOAD_PHYSICAL_IDENTITY_MISMATCH;
    status = open_contained_sidecar(bundle_root, entry, &file);
    if (status != PHOTON_V6_SPECIAL57_LOAD_OK) goto done;
    status = read_file_handle(file, &png, &png_bytes);
    if (status != PHOTON_V6_SPECIAL57_LOAD_OK) goto done;
    if (!sha256_bytes(png, png_bytes, digest)) goto done;
    if (memcmp(digest, entry->png_sha256, 32) != 0) {
        status = PHOTON_V6_SPECIAL57_LOAD_PNG_HASH_MISMATCH;
        goto done;
    }
#ifdef PHOTON_V6_SPECIAL57_TEST_HOOKS
    if (InterlockedExchange(&special57_corrupt_decode, 0) && png_bytes) png[0] ^= 0xFF;
#endif
    status = decode_wic_rgba(png, png_bytes, entry, &rgba, &rgba_bytes);
    if (status != PHOTON_V6_SPECIAL57_LOAD_OK) goto done;
    if (!sha256_bytes(rgba, rgba_bytes, digest)) goto done;
    if (memcmp(digest, entry->rgba_sha256, 32) != 0) {
        status = PHOTON_V6_SPECIAL57_LOAD_RGBA_HASH_MISMATCH;
        goto done;
    }
    result.pixels = rgba;
    result.width = entry->width;
    result.height = entry->height;
    result.stride = entry->width * 4U;
    result.bytes = rgba_bytes;
    rgba = NULL;
    *output = result;
    status = PHOTON_V6_SPECIAL57_LOAD_OK;
done:
    if (rgba) HeapFree(GetProcessHeap(), 0, rgba);
    if (png) HeapFree(GetProcessHeap(), 0, png);
    if (file != INVALID_HANDLE_VALUE) CloseHandle(file);
    if (status != PHOTON_V6_SPECIAL57_LOAD_OK) image_zero(output);
    return status;
}
