/*
 * PF/PM PhotonR2 font guard plus an optional exact-image transport boundary.
 *
 * This proxy remains the Ages3ResT.dll forwarding surface.  The mandatory
 * font path is the already validated self-contained v2 design.  The image
 * runtime is deliberately optional: its disabled implementation cannot
 * install a hook, and any future implementation must fail closed without
 * preventing font setup or calls to the official private DLL.
 *
 * DllMain intentionally does no file, registry, font, hook, thread, or loader
 * work.  Initialization begins on the first official plugin export call.
 */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <wincrypt.h>
#include <stdint.h>
#include <string.h>
#include <wchar.h>

#if defined(PHOTON_BUILD_PF) && defined(PHOTON_BUILD_PM)
#error Select exactly one game configuration.
#elif defined(PHOTON_BUILD_PF)
#include "photon_combined_pf.generated.h"
#elif defined(PHOTON_BUILD_PM)
#include "photon_combined_pm.generated.h"
#else
#error Define PHOTON_BUILD_PF or PHOTON_BUILD_PM.
#endif

#include "photon_font_policy.h"
#include "photon_optional_runtime_bridge.h"

typedef void *(__cdecl *PluginFn)(void);
typedef int (__cdecl *PluginAgesFn)(void);
typedef HFONT (WINAPI *CreateFontIndirectWFn)(const LOGFONTW *);

enum GuardStatus {
    GUARD_OK = 0,
    GUARD_BAD_HOST = 1,
    GUARD_BAD_PRIVATE_DLL = 2,
    GUARD_BAD_FONT = 3,
    GUARD_REGISTRY_OPEN_FAILED = 4,
    GUARD_ROUTE_WRITE_FAILED = 5,
    GUARD_PRIVATE_LOAD_FAILED = 6,
    GUARD_EXPORT_RESOLVE_FAILED = 7,
    GUARD_THREAD_START_FAILED = 8,
    GUARD_FONT_HOOK_FAILED = 9,
    GUARD_STATUS_WRITE_FAILED = 10
};

static HMODULE g_self;
static HMODULE g_private;
static PluginFn g_plugin;
static PluginAgesFn g_plugin_ages;
static volatile LONG g_init_state;
static volatile LONG g_error_shown;
static volatile LONG g_guardian_started;
static volatile LONG g_reassertions;
static volatile LONG g_font_hook_active;
static volatile LONG g_font_calls;
static volatile LONG g_face_rewrites;
static volatile LONG g_status_dirty;
static volatile LONG g_image_runtime_started;
static volatile LONG g_snapshot_write_errors;
static SRWLOCK g_registry_status_lock = SRWLOCK_INIT;
static DWORD g_registry_status_sequence;
static PhotonV6RuntimeStatus g_last_published_image_status;
static int32_t g_last_published_image_init_result;
static int g_have_published_image_status;
static CreateFontIndirectWFn g_real_CreateFontIndirectW;
static PhotonOptionalRuntimeReport g_image_report;

static const wchar_t *const ROUTE_KEY = PHOTON_ROUTE_KEY;
static const wchar_t *const PRIVATE_NAME = L"Ages3ResT.PhotonR2.private.dll";
static const wchar_t *const FONT_NAME = L"PhotonR2-Regular.ttf";
static const struct {
    const wchar_t *name;
    const wchar_t *value;
} ROUTES[] = {
    {L"strStandardFont", L"PhotonR2%#24%$-B%$-A"},
    {L"strStandardFont_ANSI", L"PhotonR2%#24%$-B%$-A"},
    {L"strStandardFont_GB2312", L"PhotonR2%#24%$-B%$-A"},
    {L"strLowSpecFont", L"PhotonR2%#16%$-B"}
};

static int append_text(wchar_t *buffer, size_t capacity, const wchar_t *suffix) {
    size_t a = wcslen(buffer), b = wcslen(suffix);
    if (a + b + 1 > capacity) return 0;
    memcpy(buffer + a, suffix, (b + 1) * sizeof(wchar_t));
    return 1;
}

static int module_directory(wchar_t out[MAX_PATH]) {
    DWORD n = GetModuleFileNameW(g_self, out, MAX_PATH);
    wchar_t *slash;
    if (!n || n >= MAX_PATH) return 0;
    slash = wcsrchr(out, L'\\');
    if (!slash) return 0;
    slash[1] = 0;
    return 1;
}

static int parse_sha256(const char *text, BYTE out[32]) {
    int i;
    for (i = 0; i < 32; ++i) {
        char a = text[i * 2], b = text[i * 2 + 1];
        int hi = a >= '0' && a <= '9' ? a - '0' :
                 a >= 'A' && a <= 'F' ? a - 'A' + 10 :
                 a >= 'a' && a <= 'f' ? a - 'a' + 10 : -1;
        int lo = b >= '0' && b <= '9' ? b - '0' :
                 b >= 'A' && b <= 'F' ? b - 'A' + 10 :
                 b >= 'a' && b <= 'f' ? b - 'a' + 10 : -1;
        if (hi < 0 || lo < 0) return 0;
        out[i] = (BYTE)((hi << 4) | lo);
    }
    return text[64] == 0;
}

static int sha256_file(const wchar_t *path, BYTE out[32]) {
    HANDLE file = INVALID_HANDLE_VALUE;
    HCRYPTPROV provider = 0;
    HCRYPTHASH hash = 0;
    BYTE buffer[65536];
    DWORD got, size = 32;
    int ok = 0;
    file = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_DELETE,
                       NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) goto done;
    if (!CryptAcquireContextW(&provider, NULL, NULL, PROV_RSA_AES,
                              CRYPT_VERIFYCONTEXT)) goto done;
    if (!CryptCreateHash(provider, CALG_SHA_256, 0, 0, &hash)) goto done;
    for (;;) {
        if (!ReadFile(file, buffer, sizeof(buffer), &got, NULL)) goto done;
        if (!got) break;
        if (!CryptHashData(hash, buffer, got, 0)) goto done;
    }
    if (!CryptGetHashParam(hash, HP_HASHVAL, out, &size, 0) || size != 32)
        goto done;
    ok = 1;
done:
    if (hash) CryptDestroyHash(hash);
    if (provider) CryptReleaseContext(provider, 0);
    if (file != INVALID_HANDLE_VALUE) CloseHandle(file);
    return ok;
}

static int verify_sha256(const wchar_t *path, const char *expected) {
    BYTE actual[32], wanted[32];
    return parse_sha256(expected, wanted) && sha256_file(path, actual) &&
           memcmp(actual, wanted, 32) == 0;
}

static int equal_ascii_ci(const char *left, const char *right) {
    while (*left && *right) {
        char a = *left++, b = *right++;
        if (a >= 'A' && a <= 'Z') a = (char)(a + ('a' - 'A'));
        if (b >= 'A' && b <= 'Z') b = (char)(b + ('a' - 'A'));
        if (a != b) return 0;
    }
    return *left == 0 && *right == 0;
}

static HFONT WINAPI hook_CreateFontIndirectW(const LOGFONTW *requested) {
    LOGFONTW adjusted;
    if (!requested) return g_real_CreateFontIndirectW(requested);
    if (!photon_font_rewrite_logfont(requested, &adjusted))
        return g_real_CreateFontIndirectW(requested);
    InterlockedIncrement(&g_font_calls);
    if (_wcsicmp(requested->lfFaceName, PHOTON_RUNTIME_FACE) != 0)
        InterlockedIncrement(&g_face_rewrites);
    InterlockedExchange(&g_status_dirty, 1);
    return g_real_CreateFontIndirectW(&adjusted);
}

static int install_host_font_hook(void) {
    BYTE *base = (BYTE *)GetModuleHandleW(NULL);
    IMAGE_DOS_HEADER *dos;
    IMAGE_NT_HEADERS32 *nt;
    IMAGE_IMPORT_DESCRIPTOR *descriptor;
    DWORD rva;
    int matches = 0;
    if (!base) return 0;
    dos = (IMAGE_DOS_HEADER *)base;
    if (dos->e_magic != IMAGE_DOS_SIGNATURE) return 0;
    nt = (IMAGE_NT_HEADERS32 *)(base + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE ||
        nt->OptionalHeader.Magic != IMAGE_NT_OPTIONAL_HDR32_MAGIC) return 0;
    rva = nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT].VirtualAddress;
    if (!rva) return 0;
    descriptor = (IMAGE_IMPORT_DESCRIPTOR *)(base + rva);
    for (; descriptor->Name; ++descriptor) {
        const char *dll_name = (const char *)(base + descriptor->Name);
        IMAGE_THUNK_DATA32 *names;
        IMAGE_THUNK_DATA32 *slots;
        if (!descriptor->OriginalFirstThunk ||
            !equal_ascii_ci(dll_name, "gdi32.dll")) continue;
        names = (IMAGE_THUNK_DATA32 *)(base + descriptor->OriginalFirstThunk);
        slots = (IMAGE_THUNK_DATA32 *)(base + descriptor->FirstThunk);
        for (; names->u1.AddressOfData; ++names, ++slots) {
            IMAGE_IMPORT_BY_NAME *import;
            void *current;
            DWORD old_protect = 0, ignored = 0;
            if (IMAGE_SNAP_BY_ORDINAL32(names->u1.Ordinal)) continue;
            import = (IMAGE_IMPORT_BY_NAME *)(base + names->u1.AddressOfData);
            if (strcmp((const char *)import->Name, "CreateFontIndirectW") != 0)
                continue;
            current = (void *)(uintptr_t)slots->u1.Function;
            if (current == (void *)hook_CreateFontIndirectW) {
                ++matches;
                continue;
            }
            if (matches != 0 || !current) return 0;
            g_real_CreateFontIndirectW = (CreateFontIndirectWFn)current;
            if (!VirtualProtect(&slots->u1.Function, sizeof(DWORD), PAGE_READWRITE,
                                &old_protect)) return 0;
            slots->u1.Function = (DWORD)(uintptr_t)hook_CreateFontIndirectW;
            VirtualProtect(&slots->u1.Function, sizeof(DWORD), old_protect,
                           &ignored);
            FlushInstructionCache(GetCurrentProcess(), &slots->u1.Function,
                                  sizeof(DWORD));
            ++matches;
        }
    }
    if (matches != 1 || !g_real_CreateFontIndirectW) return 0;
    InterlockedExchange(&g_font_hook_active, 1);
    InterlockedExchange(&g_status_dirty, 1);
    return 1;
}

static int set_dword_checked(HKEY key, const wchar_t *name, DWORD value) {
    return RegSetValueExW(key, name, 0, REG_DWORD, (const BYTE *)&value,
                          (DWORD)sizeof(value)) == ERROR_SUCCESS;
}

static int refresh_image_status_changed(void) {
    int changed = 0;
    AcquireSRWLockExclusive(&g_registry_status_lock);
    if (InterlockedCompareExchange(&g_image_runtime_started, 0, 0)) {
        photon_optional_runtime_refresh(&g_image_report);
        changed = !g_have_published_image_status ||
            g_last_published_image_init_result != g_image_report.init_result ||
            memcmp(&g_last_published_image_status, &g_image_report.status,
                   sizeof(g_image_report.status)) != 0;
    }
    ReleaseSRWLockExclusive(&g_registry_status_lock);
    return changed;
}

/*
 * The registry snapshot uses an odd/even sequence protocol.  Readers accept
 * telemetry only when sequence_before == sequence_after and both are even.
 * A failed field write deliberately leaves the registry sequence odd.
 */
static int write_status(HKEY key, DWORD status) {
    static const wchar_t version[] = PHOTON_GUARD_VERSION;
    DWORD pid = GetCurrentProcessId();
    DWORD active = g_guardian_started ? 1u : 0u;
    DWORD reassertions = (DWORD)g_reassertions;
    DWORD hook_active = (DWORD)g_font_hook_active;
    DWORD font_calls = (DWORD)g_font_calls;
    DWORD face_rewrites = (DWORD)g_face_rewrites;
    DWORD sequence_start, sequence_committed, snapshot_tick = GetTickCount();
    DWORD image_started, write_errors;
    int ok = 1;
    AcquireSRWLockExclusive(&g_registry_status_lock);
    image_started = (DWORD)InterlockedCompareExchange(
        &g_image_runtime_started, 0, 0);
    if (image_started) photon_optional_runtime_refresh(&g_image_report);
    write_errors = (DWORD)InterlockedCompareExchange(
        &g_snapshot_write_errors, 0, 0);
    sequence_start = g_registry_status_sequence + 1u;
    sequence_committed = g_registry_status_sequence + 2u;
    if (!set_dword_checked(key, L"PhotonV6RuntimeSnapshotSequence",
                           sequence_start)) {
        ok = 0;
    } else {
#define WRITE_SNAPSHOT_DWORD(name, value) \
        do { if (!set_dword_checked(key, (name), (DWORD)(value))) ok = 0; } while (0)
        if (RegSetValueExW(key, L"PhotonR2SteamGuardVersion", 0, REG_SZ,
                          (const BYTE *)version, (DWORD)sizeof(version)) !=
            ERROR_SUCCESS) ok = 0;
        WRITE_SNAPSHOT_DWORD(L"PhotonR2SteamGuardLastResult", status);
        WRITE_SNAPSHOT_DWORD(L"PhotonR2SteamGuardLastPid", pid);
        WRITE_SNAPSHOT_DWORD(L"PhotonR2SteamGuardGuardianActive", active);
        WRITE_SNAPSHOT_DWORD(L"PhotonR2SteamGuardReassertions", reassertions);
        WRITE_SNAPSHOT_DWORD(L"PhotonR2SteamGuardFontHookActive", hook_active);
        WRITE_SNAPSHOT_DWORD(L"PhotonR2SteamGuardFontCalls", font_calls);
        WRITE_SNAPSHOT_DWORD(L"PhotonR2SteamGuardFaceRewrites", face_rewrites);
        WRITE_SNAPSHOT_DWORD(L"PhotonV6RuntimeStarted", image_started);
        WRITE_SNAPSHOT_DWORD(L"PhotonV6RuntimeAuthorized",
                             g_image_report.status.runtime_authorized);
        WRITE_SNAPSHOT_DWORD(L"PhotonV6RuntimeHooksInstalled",
                             g_image_report.status.hooks_installed);
        WRITE_SNAPSHOT_DWORD(L"PhotonV6RuntimeResult",
                             g_image_report.status.result);
        WRITE_SNAPSHOT_DWORD(L"PhotonV6RuntimeInitResult",
                             g_image_report.init_result);
        WRITE_SNAPSHOT_DWORD(L"PhotonV6RuntimeInitCalls",
                             g_image_report.status.init_calls);
        WRITE_SNAPSHOT_DWORD(L"PhotonV6RuntimeShutdownCalls",
                             g_image_report.status.shutdown_calls);
        WRITE_SNAPSHOT_DWORD(L"PhotonV6RuntimeNativeGeneration",
                             g_image_report.status.native_status_generation);
        WRITE_SNAPSHOT_DWORD(L"PhotonV6RuntimeSnapshotConsistent",
                             g_image_report.status.snapshot_consistent);
        WRITE_SNAPSHOT_DWORD(L"PhotonV6RuntimeHookInflight",
                             g_image_report.status.hook_inflight);
        WRITE_SNAPSHOT_DWORD(L"PhotonV6RuntimeExactPayloadLoads",
                             g_image_report.status.exact_payload_loads);
        WRITE_SNAPSHOT_DWORD(L"PhotonV6RuntimeOverlayCommits",
                             g_image_report.status.overlay_commits);
        WRITE_SNAPSHOT_DWORD(L"PhotonV6RuntimeUntargetedDecodes",
                             g_image_report.status.untargeted_decodes);
        WRITE_SNAPSHOT_DWORD(L"PhotonV6RuntimeRejectedDecodes",
                             g_image_report.status.rejected_decodes);
        WRITE_SNAPSHOT_DWORD(L"PhotonV6RuntimeFatalLatch",
                             g_image_report.status.fatal_latch);
        WRITE_SNAPSHOT_DWORD(L"PhotonV6RuntimeHooksRestoredExact",
                             g_image_report.status.hooks_restored_exact);
        WRITE_SNAPSHOT_DWORD(L"PhotonV6SelectorAbiVersion",
                             g_image_report.status.selector_abi_version);
        WRITE_SNAPSHOT_DWORD(L"PhotonV6SelectorInitialized",
                             g_image_report.status.selector_initialized);
        WRITE_SNAPSHOT_DWORD(L"PhotonV6SelectorHooksInstalled",
                             g_image_report.status.selector_hooks_installed);
        WRITE_SNAPSHOT_DWORD(L"PhotonV6SelectorHookInflight",
                             g_image_report.status.selector_hook_inflight);
        WRITE_SNAPSHOT_DWORD(L"PhotonV6SelectorHooksRestoredExact",
                             g_image_report.status.selector_hooks_restored_exact);
        WRITE_SNAPSHOT_DWORD(L"PhotonV6SelectorSnapshotConsistent",
                             g_image_report.status.selector_snapshot_consistent);
        WRITE_SNAPSHOT_DWORD(L"PhotonV6SelectorStatusGeneration",
                             g_image_report.status.selector_status_generation);
        WRITE_SNAPSHOT_DWORD(L"PhotonV6SelectorLanguageState",
                             g_image_report.status.selector_language_state);
        WRITE_SNAPSHOT_DWORD(L"PhotonV6SelectorLanguageStateSequence",
                             g_image_report.status.selector_language_state_sequence);
        WRITE_SNAPSHOT_DWORD(L"PhotonV6SelectorLanguageStateKnown",
                             g_image_report.status.selector_language_state_known);
        WRITE_SNAPSHOT_DWORD(L"PhotonV6SelectorLanguageBootstrapExactEvents",
                             g_image_report.status.selector_language_bootstrap_exact_events);
        WRITE_SNAPSHOT_DWORD(L"PhotonV6SelectorLanguageBootstrapConflictRejects",
                             g_image_report.status.selector_language_bootstrap_conflict_rejects);
        WRITE_SNAPSHOT_DWORD(L"PhotonV6SelectorLanguageSetterExactEvents",
                             g_image_report.status.selector_language_setter_exact_events);
        WRITE_SNAPSHOT_DWORD(L"PhotonV6SelectorGraphDiscoverySuccesses",
                             g_image_report.status.selector_language_graph_discovery_successes);
        WRITE_SNAPSHOT_DWORD(L"PhotonV6SelectorGraphDiscoveryRejects",
                             g_image_report.status.selector_language_graph_discovery_rejects);
        WRITE_SNAPSHOT_DWORD(L"PhotonV6SelectorCRefIdentityEvents",
                             g_image_report.status.selector_cref_identity_events);
        WRITE_SNAPSHOT_DWORD(L"PhotonV6SelectorVmExecuteIdentityEvents",
                             g_image_report.status.selector_vm_execute_identity_events);
        WRITE_SNAPSHOT_DWORD(L"PhotonV6SelectorExactLoadBindings",
                             g_image_report.status.selector_exact_load_bindings);
        WRITE_SNAPSHOT_DWORD(L"PhotonV6SelectorCachedSurfaceBindings",
                             g_image_report.status.selector_cached_surface_bindings);
        WRITE_SNAPSHOT_DWORD(L"PhotonV6SelectorTranslationSpecial57Allows",
                             g_image_report.status.selector_translation_special57_allows);
        WRITE_SNAPSHOT_DWORD(L"PhotonV6SelectorJapaneseEndpointRejects",
                             g_image_report.status.selector_japanese_translation_endpoint_rejects);
        WRITE_SNAPSHOT_DWORD(L"PhotonV6SelectorCausalIdentityRejects",
                             g_image_report.status.selector_causal_identity_rejects);
        WRITE_SNAPSHOT_DWORD(L"PhotonV6SelectorC07AliasRejects",
                             g_image_report.status.selector_c07_alias_rejects);
        WRITE_SNAPSHOT_DWORD(L"PhotonV6SelectorExactSurfaceEntries",
                             g_image_report.status.selector_exact_surface_entries);
        WRITE_SNAPSHOT_DWORD(L"PhotonV6SelectorExactDecodeQueries",
                             g_image_report.status.selector_exact_decode_queries);
        WRITE_SNAPSHOT_DWORD(L"PhotonV6SelectorFatalLatch",
                             g_image_report.status.selector_fatal_latch);
        WRITE_SNAPSHOT_DWORD(L"PhotonV6RuntimeNativeInitDetail",
                             g_image_report.status.native_init_detail);
        WRITE_SNAPSHOT_DWORD(L"PhotonV6RuntimeNativeInitStage",
                             g_image_report.status.native_init_stage);
        WRITE_SNAPSHOT_DWORD(L"PhotonV6RuntimeSelectorInitDetail",
                             g_image_report.status.selector_init_detail);
        WRITE_SNAPSHOT_DWORD(L"PhotonV6RuntimeLastOverlayStatus",
                             g_image_report.status.last_overlay_status);
        WRITE_SNAPSHOT_DWORD(L"PhotonV6RuntimeLastOverlayRouteGateStatus",
                             g_image_report.status.last_overlay_route_gate_status);
        WRITE_SNAPSHOT_DWORD(L"PhotonV6RuntimeLastOverlaySidecarStatus",
                             g_image_report.status.last_overlay_sidecar_status);
        WRITE_SNAPSHOT_DWORD(L"PhotonV6RuntimeLastOverlayTransactionStatus",
                             g_image_report.status.last_overlay_transaction_status);
        WRITE_SNAPSHOT_DWORD(L"PhotonV6RuntimeSnapshotTick", snapshot_tick);
        WRITE_SNAPSHOT_DWORD(L"PhotonV6RuntimeSnapshotWriteErrors",
                             write_errors);
#undef WRITE_SNAPSHOT_DWORD
        if (ok && !set_dword_checked(key,
                L"PhotonV6RuntimeSnapshotSequence", sequence_committed))
            ok = 0;
    }
    g_registry_status_sequence = sequence_committed;
    if (ok) {
        g_last_published_image_status = g_image_report.status;
        g_last_published_image_init_result = g_image_report.init_result;
        g_have_published_image_status = 1;
    } else {
        InterlockedIncrement(&g_snapshot_write_errors);
        InterlockedExchange(&g_status_dirty, 1);
    }
    ReleaseSRWLockExclusive(&g_registry_status_lock);
    return ok;
}

static int write_routes(int force_status) {
    HKEY key = NULL;
    DWORD i, status = GUARD_OK, changed = 0;
    LONG status_dirty;
    LONG result = RegOpenKeyExW(HKEY_CURRENT_USER, ROUTE_KEY, 0,
                                KEY_QUERY_VALUE | KEY_SET_VALUE, &key);
    if (result != ERROR_SUCCESS) return GUARD_REGISTRY_OPEN_FAILED;
    if (refresh_image_status_changed()) InterlockedExchange(&g_status_dirty, 1);
    for (i = 0; i < sizeof(ROUTES) / sizeof(ROUTES[0]); ++i) {
        wchar_t current[128];
        DWORD kind = 0, current_bytes = (DWORD)sizeof(current);
        DWORD wanted_bytes =
            (DWORD)((wcslen(ROUTES[i].value) + 1) * sizeof(wchar_t));
        result = RegQueryValueExW(key, ROUTES[i].name, NULL, &kind,
                                  (BYTE *)current, &current_bytes);
        if (result != ERROR_SUCCESS || kind != REG_SZ ||
            current_bytes != wanted_bytes ||
            memcmp(current, ROUTES[i].value, wanted_bytes) != 0) {
            result = RegSetValueExW(key, ROUTES[i].name, 0, REG_SZ,
                                    (const BYTE *)ROUTES[i].value,
                                    wanted_bytes);
            if (result != ERROR_SUCCESS) {
                status = GUARD_ROUTE_WRITE_FAILED;
                break;
            }
            ++changed;
        }
    }
    if (changed) InterlockedExchangeAdd(&g_reassertions, (LONG)changed);
    status_dirty = InterlockedExchange(&g_status_dirty, 0);
    if ((force_status || changed || status != GUARD_OK || status_dirty) &&
        !write_status(key, status) && status == GUARD_OK)
        status = GUARD_STATUS_WRITE_FAILED;
    RegCloseKey(key);
    return (int)status;
}

static DWORD WINAPI guardian_thread(LPVOID unused) {
    HKEY key = NULL;
    HANDLE event = NULL;
    DWORD started = GetTickCount();
    (void)unused;
    if (RegOpenKeyExW(HKEY_CURRENT_USER, ROUTE_KEY, 0, KEY_NOTIFY, &key) !=
        ERROR_SUCCESS) return 0;
    event = CreateEventW(NULL, TRUE, FALSE, NULL);
    if (!event) {
        RegCloseKey(key);
        return 0;
    }
    for (;;) {
        DWORD elapsed, timeout;
        write_routes(0);
        ResetEvent(event);
        if (RegNotifyChangeKeyValue(key, FALSE, REG_NOTIFY_CHANGE_LAST_SET,
                                    event, TRUE) != ERROR_SUCCESS) break;
        elapsed = GetTickCount() - started;
        timeout = elapsed < 30000u ? 25u : 500u;
        WaitForSingleObject(event, timeout);
    }
    CloseHandle(event);
    RegCloseKey(key);
    return 0;
}

static int start_guardian(void) {
    HANDLE thread;
    if (InterlockedCompareExchange(&g_guardian_started, 1, 0) != 0) return 1;
    thread = CreateThread(NULL, 0, guardian_thread, NULL, 0, NULL);
    if (!thread) {
        InterlockedExchange(&g_guardian_started, 0);
        return 0;
    }
    CloseHandle(thread);
    write_routes(1);
    return 1;
}

static void start_optional_image_runtime(const wchar_t package_root[MAX_PATH]) {
    PhotonV6RuntimeConfig config;
    memset(&config, 0, sizeof(config));
    config.struct_size = sizeof(config);
    config.abi_version = PHOTON_V6_RUNTIME_ABI_VERSION;
    config.game_id = PHOTON_V6_GAME_ID;
    config.runtime_authorized = PHOTON_V6_RUNTIME_AUTHORIZED;
    config.self_module = g_self;
    config.host_module = GetModuleHandleW(NULL);
    wcsncpy(config.package_root, package_root, MAX_PATH - 1);
    config.package_root[MAX_PATH - 1] = 0;
    photon_optional_runtime_start(&config, &g_image_report);
    InterlockedExchange(&g_image_runtime_started, 1);
    InterlockedExchange(&g_status_dirty, 1);
}

static int initialize_guard(void) {
    wchar_t private_path[MAX_PATH];
    wchar_t host_path[MAX_PATH];
    wchar_t font_path[MAX_PATH];
    wchar_t package_root[MAX_PATH];
    int status;
    if (!GetModuleFileNameW(NULL, host_path, MAX_PATH) ||
        !verify_sha256(host_path, PHOTON_GAME_EXE_SHA256))
        return GUARD_BAD_HOST;
    if (!module_directory(private_path) ||
        !append_text(private_path, MAX_PATH, PRIVATE_NAME) ||
        !verify_sha256(private_path, PHOTON_PRIVATE_DLL_SHA256))
        return GUARD_BAD_PRIVATE_DLL;
    if (!module_directory(font_path) ||
        !append_text(font_path, MAX_PATH, FONT_NAME) ||
        !verify_sha256(font_path, PHOTON_FONT_SHA256) ||
        AddFontResourceExW(font_path, FR_PRIVATE | FR_NOT_ENUM, NULL) == 0)
        return GUARD_BAD_FONT;
    status = write_routes(1);
    if (status != GUARD_OK) return status;
    if (!install_host_font_hook()) return GUARD_FONT_HOOK_FAILED;
    write_routes(1);
    g_private = LoadLibraryW(private_path);
    if (!g_private) return GUARD_PRIVATE_LOAD_FAILED;
    g_plugin = (PluginFn)GetProcAddress(g_private, "PluginThisLibrary");
    g_plugin_ages =
        (PluginAgesFn)GetProcAddress(g_private, "PluginThisLibrary_Ages3Res");
    if (!g_plugin || !g_plugin_ages) return GUARD_EXPORT_RESOLVE_FAILED;

    /* The installer owns all image-runtime resources below a versioned root.
     * Keep that contract here instead of making either loader guess relative
     * to the game directory.  Ordinary sidecars then resolve below
     * sidecars\\PF|PM and the special route table resolves below payload\\PF|PM.
     * Image transport remains optional and cannot block the validated
     * font/official-forward path. */
    if (module_directory(package_root) &&
        append_text(package_root, MAX_PATH, L"PhotonR2Assets\\v6"))
        start_optional_image_runtime(package_root);

    if (!start_guardian()) return GUARD_THREAD_START_FAILED;
    return GUARD_OK;
}

static int ensure_initialized(void) {
    LONG state = InterlockedCompareExchange(&g_init_state, 1, 0);
    if (state == 0) {
        int status = initialize_guard();
        InterlockedExchange(&g_init_state, status == GUARD_OK ? 2 : -status);
        return status == GUARD_OK;
    }
    while (state == 1) {
        Sleep(0);
        state = InterlockedCompareExchange(&g_init_state, 1, 1);
    }
    return state == 2;
}

static void show_failure_once(void) {
    if (InterlockedCompareExchange(&g_error_shown, 1, 0) == 0) {
        MessageBoxW(NULL, PHOTON_FAILURE_MESSAGE, PHOTON_FAILURE_TITLE,
                    MB_OK | MB_ICONERROR | MB_TASKMODAL);
    }
}

__declspec(dllexport) void *__cdecl PluginThisLibrary(void) {
    void *result;
    if (!ensure_initialized()) {
        show_failure_once();
        return NULL;
    }
    result = g_plugin();
    write_routes(1);
    return result;
}

__declspec(dllexport) int __cdecl PluginThisLibrary_Ages3Res(void) {
    int result;
    if (!ensure_initialized()) {
        show_failure_once();
        return 0;
    }
    result = g_plugin_ages();
    write_routes(1);
    return result;
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        g_self = instance;
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
