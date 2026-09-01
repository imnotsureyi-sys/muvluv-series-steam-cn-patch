#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <tlhelp32.h>
#include <wincrypt.h>

#include <limits.h>
#include <stdint.h>
#include <string.h>
#include <wchar.h>
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
#include <stdio.h>
#endif

#include "photon_pf_decoder_surface_view.h"
#include "photon_v6_exact_overlay_core.h"
#include "photon_v6_pf_native_runtime.h"

#if (defined(PHOTON_V6_PRODUCTION_PF) && PHOTON_V6_PRODUCTION_PF && \
     defined(PHOTON_V6_PF_SELECTOR_ADAPTER) && \
     PHOTON_V6_PF_SELECTOR_ADAPTER) || \
    (defined(PHOTON_V6_PRODUCTION_PM) && PHOTON_V6_PRODUCTION_PM && \
     defined(PHOTON_V6_PM_SELECTOR_ADAPTER) && \
     PHOTON_V6_PM_SELECTOR_ADAPTER)
#define PHOTON_NATIVE_SELECTOR_ENABLED 1
#include "photon_v6_pf_selector_adapter.h"
#include "photon_v6_special57_sidecar_loader.h"
#else
#define PHOTON_NATIVE_SELECTOR_ENABLED 0
#endif

#if !defined(__i386__) && !defined(_M_IX86)
#error photon_v6_pf_native_runtime must use the 32-bit Windows ABI.
#endif

/*
 * The hook engine is shared verbatim by PF and PM.  PF compiles this source
 * directly; the PM translation unit supplies the pinned PM image constants
 * and symbol aliases before including it.  Keeping the mutation/quiescence
 * implementation single-sourced prevents restore semantics from drifting.
 */
#ifndef PHOTON_NATIVE_TIMESTAMP
#define PHOTON_NATIVE_TIMESTAMP UINT32_C(0x5BFBE4FF)
#endif
#ifndef PHOTON_NATIVE_SIZE_OF_IMAGE
#define PHOTON_NATIVE_SIZE_OF_IMAGE UINT32_C(0x00380000)
#endif
#ifndef PHOTON_NATIVE_CR6_LOAD_SLOT_RVA
#define PHOTON_NATIVE_CR6_LOAD_SLOT_RVA UINT32_C(0x00239E04)
#endif
#ifndef PHOTON_NATIVE_CR6_LOAD_RVA
#define PHOTON_NATIVE_CR6_LOAD_RVA UINT32_C(0x0017DEE0)
#endif
#ifndef PHOTON_NATIVE_CR6_SURFACE_SLOT_RVA
#define PHOTON_NATIVE_CR6_SURFACE_SLOT_RVA UINT32_C(0x00239E84)
#endif
#ifndef PHOTON_NATIVE_CR6_SURFACE_RVA
#define PHOTON_NATIVE_CR6_SURFACE_RVA UINT32_C(0x0017E590)
#endif
#ifndef PHOTON_NATIVE_CR6_RECT_SLOT_RVA
#define PHOTON_NATIVE_CR6_RECT_SLOT_RVA UINT32_C(0x00239E8C)
#endif
#ifndef PHOTON_NATIVE_CR6_RECT_RVA
#define PHOTON_NATIVE_CR6_RECT_RVA UINT32_C(0x0017E7A0)
#endif
#ifndef PHOTON_NATIVE_CR6_DECODE_CALLSITE_RVA
#define PHOTON_NATIVE_CR6_DECODE_CALLSITE_RVA UINT32_C(0x0017F09E)
#endif
#ifndef PHOTON_NATIVE_CR6_DECODE_RVA
#define PHOTON_NATIVE_CR6_DECODE_RVA UINT32_C(0x0017CF30)
#endif
#ifndef PHOTON_NATIVE_HAS_CR6_ALT_EXACT_OVERLAY
#define PHOTON_NATIVE_HAS_CR6_ALT_EXACT_OVERLAY 1
#endif
#ifndef PHOTON_NATIVE_CR6_ALT_DECODE_CALLSITE0_RVA
#define PHOTON_NATIVE_CR6_ALT_DECODE_CALLSITE0_RVA UINT32_C(0x0017ECEC)
#endif
#ifndef PHOTON_NATIVE_CR6_ALT_DECODE_CALLSITE1_RVA
#define PHOTON_NATIVE_CR6_ALT_DECODE_CALLSITE1_RVA UINT32_C(0x0017EDD9)
#endif
#ifndef PHOTON_NATIVE_CR6_ALT_DECODE_RVA
#define PHOTON_NATIVE_CR6_ALT_DECODE_RVA UINT32_C(0x0017C800)
#endif
#ifndef PHOTON_NATIVE_SECURITY_COOKIE_RVA
#define PHOTON_NATIVE_SECURITY_COOKIE_RVA UINT32_C(0x0026D014)
#endif
#ifndef PHOTON_NATIVE_ROUTE_GAME
#define PHOTON_NATIVE_ROUTE_GAME PHOTON_V6_ROUTE_GAME_PF
#endif
#ifndef PHOTON_NATIVE_SPECIAL_TARGET_COUNT
#define PHOTON_NATIVE_SPECIAL_TARGET_COUNT UINT32_C(6)
#endif
#ifndef PHOTON_NATIVE_SPECIAL_VALID_TARGET_COUNT
#define PHOTON_NATIVE_SPECIAL_VALID_TARGET_COUNT UINT32_C(6)
#endif
#ifndef PHOTON_NATIVE_SPECIAL_SIDECAR_GAME
#define PHOTON_NATIVE_SPECIAL_SIDECAR_GAME PHOTON_V6_SPECIAL57_GAME_PF
#endif
#ifndef PHOTON_NATIVE_SELECTOR_EXPECTED_HOOK_COUNT
#define PHOTON_NATIVE_SELECTOR_EXPECTED_HOOK_COUNT UINT32_C(4)
#endif
#ifndef PHOTON_NATIVE_HAS_CRIP008_EXACT_OVERLAY
#define PHOTON_NATIVE_HAS_CRIP008_EXACT_OVERLAY 1
#endif
#ifndef PHOTON_NATIVE_CRIP008_ORDINARY_TABLE
#define PHOTON_NATIVE_CRIP008_ORDINARY_TABLE 1
#endif
#ifndef PHOTON_NATIVE_CRIP008_DECODE_CALLSITE_RVA
#define PHOTON_NATIVE_CRIP008_DECODE_CALLSITE_RVA UINT32_C(0x00179810)
#endif
#ifndef PHOTON_NATIVE_CRIP008_DECODE_RVA
#define PHOTON_NATIVE_CRIP008_DECODE_RVA UINT32_C(0x00179840)
#endif
#ifndef PHOTON_NATIVE_HAS_CRIP008_DIRECT_EXACT_OVERLAY
#define PHOTON_NATIVE_HAS_CRIP008_DIRECT_EXACT_OVERLAY \
    PHOTON_NATIVE_CRIP008_ORDINARY_TABLE
#endif
#ifndef PHOTON_NATIVE_CRIP008_DIRECT_DECODE_CALLSITE0_RVA
#define PHOTON_NATIVE_CRIP008_DIRECT_DECODE_CALLSITE0_RVA \
    UINT32_C(0x001775D8)
#endif
#ifndef PHOTON_NATIVE_CRIP008_DIRECT_DECODE_CALLSITE1_RVA
#define PHOTON_NATIVE_CRIP008_DIRECT_DECODE_CALLSITE1_RVA \
    UINT32_C(0x001776B1)
#endif
#ifndef PHOTON_NATIVE_CRIP008_DIRECT_DECODE_RVA
#define PHOTON_NATIVE_CRIP008_DIRECT_DECODE_RVA UINT32_C(0x00178AF0)
#endif
#ifndef PHOTON_NATIVE_EXPECTED_HOOK_COUNT
#define PHOTON_NATIVE_EXPECTED_HOOK_COUNT UINT32_C(9)
#endif

#if defined(PHOTON_V6_PM_SELECTOR_TEST_HOOKS)
/* The shared native-runtime fault harness has three neutral selector controls.
 * PM supplies test-only implementations without broadening the production
 * selector ABI or changing the independently sealed PF selector header. */
void photon_v6_pf_selector_test_reset(void);
void photon_v6_pf_selector_test_force_fatal(void);
void photon_v6_pf_selector_test_emit_benign_telemetry(void);
#endif

enum {
    PF_TIMESTAMP = PHOTON_NATIVE_TIMESTAMP,
    PF_SIZE_OF_IMAGE = PHOTON_NATIVE_SIZE_OF_IMAGE,
    PF_CR6_LOAD_SLOT_RVA = PHOTON_NATIVE_CR6_LOAD_SLOT_RVA,
    PF_CR6_LOAD_RVA = PHOTON_NATIVE_CR6_LOAD_RVA,
    PF_CR6_SURFACE_SLOT_RVA = PHOTON_NATIVE_CR6_SURFACE_SLOT_RVA,
    PF_CR6_SURFACE_RVA = PHOTON_NATIVE_CR6_SURFACE_RVA,
    PF_CR6_RECT_SLOT_RVA = PHOTON_NATIVE_CR6_RECT_SLOT_RVA,
    PF_CR6_RECT_RVA = PHOTON_NATIVE_CR6_RECT_RVA,
    PF_CR6_DECODE_CALLSITE_RVA = PHOTON_NATIVE_CR6_DECODE_CALLSITE_RVA,
    PF_CR6_DECODE_RVA = PHOTON_NATIVE_CR6_DECODE_RVA,
#if PHOTON_NATIVE_HAS_CR6_ALT_EXACT_OVERLAY
    PF_CR6_ALT_DECODE_CALLSITE0_RVA =
        PHOTON_NATIVE_CR6_ALT_DECODE_CALLSITE0_RVA,
    PF_CR6_ALT_DECODE_CALLSITE1_RVA =
        PHOTON_NATIVE_CR6_ALT_DECODE_CALLSITE1_RVA,
    PF_CR6_ALT_DECODE_RVA = PHOTON_NATIVE_CR6_ALT_DECODE_RVA,
#endif
    PF_SECURITY_COOKIE_RVA = PHOTON_NATIVE_SECURITY_COOKIE_RVA,
    /*
     * PF/PM can materialize substantially more than 256 Cr6Ti objects before
     * the option/title sub-pages are opened (704 was observed in the PF live
     * session that produced zero overlay commits).  A full table used to drop
     * every later object silently, which disconnected those surfaces from the
     * decoder hook.  Keep enough resident identities for the complete retail
     * corpus and retain a live-object recovery path below for cache churn.
     */
    MAX_BINDINGS = 4096,
    MAX_ACTIVE = 64,
    MAX_SUSPENDED = 512,
    RESTORE_RETRIES = 80
};

typedef uintptr_t (__attribute__((thiscall)) *LoadFn)(void *, void *);
typedef uintptr_t (__attribute__((thiscall)) *SurfaceFn)(
    void *, void *, uintptr_t, uintptr_t, void *);

typedef struct PointerHook {
    DWORD slot_rva;
    DWORD target_rva;
    void *replacement;
    void *original;
    void **slot;
    DWORD protection;
    LONG installed;
    LONG journaled;
} PointerHook;

typedef struct CallHook {
    BYTE *site;
    BYTE original[5];
    BYTE replacement[5];
    DWORD protection;
    LONG installed;
    LONG journaled;
} CallHook;

typedef struct ObjectBinding {
    void *object;
    void *decoder;
    void *payload;
    uint32_t payload_bytes;
    uint64_t payload_fnv1a64;
    uint32_t selector_special57_tracked;
    uint8_t selector_payload_sha256[32];
    const char *selector_special_source_asset_id;
    const char *selector_special_context_identity_key;
    LONG active;
} ObjectBinding;

typedef struct ActiveBinding {
    DWORD tid;
    ObjectBinding binding;
    LONG depth;
    LONG active;
} ActiveBinding;

typedef struct SuspendedThread {
    HANDLE handle;
    DWORD tid;
    DWORD eip;
} SuspendedThread;

extern void photon_v6_pf_hook_load_abi(void);
extern void photon_v6_pf_hook_load_counted(void);
extern void photon_v6_pf_hook_load_end(void);
extern void photon_v6_pf_hook_surface_abi(void);
extern void photon_v6_pf_hook_surface_counted(void);
extern void photon_v6_pf_hook_surface_end(void);
extern void photon_v6_pf_hook_rect_abi(void);
extern void photon_v6_pf_hook_rect_counted(void);
extern void photon_v6_pf_hook_rect_end(void);
extern void photon_v6_pf_hook_decode_abi(void);
extern void photon_v6_pf_hook_decode_counted(void);
extern void photon_v6_pf_hook_decode_end(void);
#if PHOTON_NATIVE_HAS_CR6_ALT_EXACT_OVERLAY
extern void photon_v6_pf_hook_alt_decode_abi(void);
extern void photon_v6_pf_hook_alt_decode_counted(void);
extern void photon_v6_pf_hook_alt_decode_end(void);
#endif
#if PHOTON_NATIVE_HAS_CRIP008_EXACT_OVERLAY
extern void photon_v6_pf_hook_crip008_decode_abi(void);
extern void photon_v6_pf_hook_crip008_decode_counted(void);
extern void photon_v6_pf_hook_crip008_decode_end(void);
#endif
#if PHOTON_NATIVE_HAS_CRIP008_DIRECT_EXACT_OVERLAY
extern void photon_v6_pf_hook_crip008_direct_decode_abi(void);
extern void photon_v6_pf_hook_crip008_direct_decode_counted(void);
extern void photon_v6_pf_hook_crip008_direct_decode_end(void);
#endif

volatile LONG photon_v6_pf_hook_inflight;
void *photon_v6_pf_real_decode_raw;
#if PHOTON_NATIVE_HAS_CR6_ALT_EXACT_OVERLAY
void *photon_v6_pf_real_alt_decode_raw;
#endif
#if PHOTON_NATIVE_HAS_CRIP008_EXACT_OVERLAY
void *photon_v6_pf_real_crip008_decode_raw;
#endif
#if PHOTON_NATIVE_HAS_CRIP008_DIRECT_EXACT_OVERLAY
void *photon_v6_pf_real_crip008_direct_decode_raw;
#endif

static BYTE *main_base;
static LoadFn real_load;
static SurfaceFn real_surface, real_rect;
static CRITICAL_SECTION state_lock;
static SRWLOCK telemetry_write_lock = SRWLOCK_INIT;
static volatile LONG telemetry_generation;
static volatile LONG lock_ready, initializing, initialized, shutting_down;
static volatile LONG restored_exact = 1;
static volatile LONG native_module_pinned;
static volatile LONG native_first_mutation_committed;
static volatile LONG native_hooks_retained_until_process_exit;
static volatile LONG native_semantic_gate_disabled;
static volatile LONG native_mutation_journal_entries;
static volatile LONG exact_payload_loads, overlay_commits;
static volatile LONG untargeted_decodes, rejected_decodes, fatal_latch;
static volatile LONG native_init_detail, native_init_stage;
static volatile LONG selector_init_detail;
static volatile LONG last_overlay_status = -1;
static volatile LONG last_overlay_route_gate_status = -1;
static volatile LONG last_overlay_sidecar_status = -1;
static volatile LONG last_overlay_transaction_status = -1;
static wchar_t ordinary_root[32768];
static ObjectBinding bindings[MAX_BINDINGS];
static ActiveBinding active_bindings[MAX_ACTIVE];
static LONG binding_write_cursor;

static int range_readable(const void *pointer, SIZE_T count);

#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
/*
 * Local-only diagnostic instrumentation.  Production builds do not define
 * PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE, so they retain no file-writing import or
 * runtime path.  The trace is deliberately placed inside the already-bound
 * exact-RGBA bundle root and is removed after the controlled capture.
 */
static SRWLOCK diagnostic_trace_lock = SRWLOCK_INIT;
static volatile LONG diagnostic_trace_ordinal;

static void diagnostic_trace_event(
    const char *event,
    const ObjectBinding *binding,
    void *decoder,
    uint32_t binding_source,
    uint32_t a1,
    int32_t pitch,
    uint32_t a3,
    uint32_t a4,
    uint32_t a5,
    uint32_t a6,
    uint32_t a7,
    const PhotonV6ExactOverlayReport *report,
    LONG overlay_status) {
    wchar_t path[32768];
    char line[2048];
    HANDLE file;
    DWORD written = 0;
    LONG ordinal;
    int path_length;
    if (!event || !ordinary_root[0]) return;
    ordinal = InterlockedIncrement(&diagnostic_trace_ordinal);
    if (ordinal > 8192) return;
    path_length = swprintf(
        path, sizeof(path) / sizeof(path[0]),
        L"%ls\\photon_v6_native_image_trace.ndjson", ordinary_root);
    if (path_length <= 0 ||
        (size_t)path_length >= sizeof(path) / sizeof(path[0])) return;
    snprintf(
        line, sizeof(line),
        "{\"event\":\"%s\",\"ordinal\":%ld,\"tick\":%llu,"
        "\"pid\":%lu,\"tid\":%lu,\"binding_source\":%lu,"
        "\"decoder\":\"0x%08lX\",\"object\":\"0x%08lX\","
        "\"payload\":\"0x%08lX\",\"payload_bytes\":%lu,"
        "\"payload_fnv1a64\":\"%016llX\",\"surface\":\"0x%08lX\","
        "\"pitch\":%ld,\"target_left_top\":\"%08lX\","
        "\"target_right_bottom\":\"%08lX\","
        "\"clip_left_top\":\"%08lX\",\"clip_right_bottom\":\"%08lX\","
        "\"flags\":\"%08lX\",\"overlay_status\":%ld,"
        "\"route_gate_status\":%lu,\"sidecar_status\":%lu,"
        "\"transaction_status\":%lu,\"destination_committed\":%lu,"
        "\"original_rgba_fnv1a64\":\"%016llX\","
        "\"requested_rgba_fnv1a64\":\"%016llX\","
        "\"readback_rgba_fnv1a64\":\"%016llX\"}",
        event, ordinal, (unsigned long long)GetTickCount64(),
        GetCurrentProcessId(), GetCurrentThreadId(),
        (unsigned long)binding_source,
        (unsigned long)(uintptr_t)decoder,
        (unsigned long)(uintptr_t)(binding ? binding->object : NULL),
        (unsigned long)(uintptr_t)(binding ? binding->payload : NULL),
        (unsigned long)(binding ? binding->payload_bytes : 0),
        (unsigned long long)(binding ? binding->payload_fnv1a64 : 0),
        (unsigned long)a1, (long)pitch, (unsigned long)a3,
        (unsigned long)a4, (unsigned long)a5, (unsigned long)a6,
        (unsigned long)a7, (long)overlay_status,
        (unsigned long)(report ? report->route_gate_status : UINT32_MAX),
        (unsigned long)(report ? report->sidecar_status : UINT32_MAX),
        (unsigned long)(report ? report->transaction.status : UINT32_MAX),
        (unsigned long)(report ? report->destination_committed : 0),
        (unsigned long long)(report ?
            report->transaction.original_rgba_fnv1a64 : 0),
        (unsigned long long)(report ?
            report->transaction.requested_rgba_fnv1a64 : 0),
        (unsigned long long)(report ?
            report->transaction.readback_rgba_fnv1a64 : 0));
    AcquireSRWLockExclusive(&diagnostic_trace_lock);
    file = CreateFileW(
        path, FILE_APPEND_DATA,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        NULL, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file != INVALID_HANDLE_VALUE) {
        WriteFile(file, line, (DWORD)strlen(line), &written, NULL);
        WriteFile(file, "\r\n", 2, &written, NULL);
        FlushFileBuffers(file);
        CloseHandle(file);
    }
    ReleaseSRWLockExclusive(&diagnostic_trace_lock);
}

/*
 * Bounded CRip008 payload capture for the controlled PF date-card audit.
 * The direct decoder does not receive the archive-level payload identity used
 * by the ordinary table, so the diagnostic build preserves each distinct
 * 800x600 input exactly once.  Production builds compile this function out.
 */
static void diagnostic_dump_crip008_payload(
    const BYTE *payload, uint32_t payload_bytes, uint64_t payload_fnv1a64) {
    wchar_t path[32768];
    HANDLE file;
    DWORD written = 0;
    uint32_t total = 0;
    int path_length;
    if (!ordinary_root[0] || !payload || !payload_bytes ||
        payload_bytes > 128U * 1024U * 1024U ||
        !range_readable(payload, payload_bytes)) return;
    path_length = swprintf(
        path, sizeof(path) / sizeof(path[0]),
        L"%ls\\crip008-live-%010lu-%016llX.bin", ordinary_root,
        (unsigned long)payload_bytes,
        (unsigned long long)payload_fnv1a64);
    if (path_length <= 0 ||
        (size_t)path_length >= sizeof(path) / sizeof(path[0])) return;
    AcquireSRWLockExclusive(&diagnostic_trace_lock);
    file = CreateFileW(
        path, GENERIC_WRITE, FILE_SHARE_READ, NULL, CREATE_NEW,
        FILE_ATTRIBUTE_NORMAL, NULL);
    if (file != INVALID_HANDLE_VALUE) {
        while (total < payload_bytes) {
            DWORD chunk = payload_bytes - total;
            if (!WriteFile(file, payload + total, chunk, &written, NULL) ||
                !written) break;
            total += written;
        }
        FlushFileBuffers(file);
        CloseHandle(file);
        if (total != payload_bytes) DeleteFileW(path);
    }
    ReleaseSRWLockExclusive(&diagnostic_trace_lock);
}
#endif

#if PHOTON_NATIVE_SELECTOR_ENABLED && defined(PHOTON_V6_NATIVE_TEST_HOOKS)
static volatile LONG native_test_selector_lifecycle_bypass;

void photon_v6_native_test_selector_bypass_lifecycle(LONG enabled) {
    InterlockedExchange(&native_test_selector_lifecycle_bypass,
                        enabled ? 1 : 0);
}
#endif

/*
 * Writers are serialized, while readers use telemetry_generation as a
 * bounded seqlock.  A reader never owns a lock, so the hook quiescence path
 * cannot suspend a guardian thread that is holding a telemetry read lock.
 */
static void telemetry_increment(volatile LONG *counter) {
    AcquireSRWLockExclusive(&telemetry_write_lock);
    InterlockedIncrement(&telemetry_generation); /* odd: mutation in flight */
    InterlockedIncrement(counter);
    InterlockedIncrement(&telemetry_generation); /* even: committed */
    ReleaseSRWLockExclusive(&telemetry_write_lock);
}

static void telemetry_set_fatal(void) {
    AcquireSRWLockExclusive(&telemetry_write_lock);
    if (!InterlockedCompareExchange(&fatal_latch, 0, 0)) {
        InterlockedIncrement(&telemetry_generation);
        InterlockedExchange(&fatal_latch, 1);
        InterlockedIncrement(&telemetry_generation);
    }
    ReleaseSRWLockExclusive(&telemetry_write_lock);
}

static void telemetry_reject_fatal(void) {
    AcquireSRWLockExclusive(&telemetry_write_lock);
    InterlockedIncrement(&telemetry_generation);
    InterlockedIncrement(&rejected_decodes);
    InterlockedExchange(&fatal_latch, 1);
    InterlockedIncrement(&telemetry_generation);
    ReleaseSRWLockExclusive(&telemetry_write_lock);
}

static void telemetry_reset(void) {
    AcquireSRWLockExclusive(&telemetry_write_lock);
    InterlockedIncrement(&telemetry_generation);
    InterlockedExchange(&restored_exact, 0);
    InterlockedExchange(&exact_payload_loads, 0);
    InterlockedExchange(&overlay_commits, 0);
    InterlockedExchange(&untargeted_decodes, 0);
    InterlockedExchange(&rejected_decodes, 0);
    InterlockedExchange(&fatal_latch, 0);
    InterlockedIncrement(&telemetry_generation);
    ReleaseSRWLockExclusive(&telemetry_write_lock);
}

static void telemetry_set_restored_exact(void) {
    AcquireSRWLockExclusive(&telemetry_write_lock);
    if (!InterlockedCompareExchange(&restored_exact, 0, 0)) {
        InterlockedIncrement(&telemetry_generation);
        InterlockedExchange(&restored_exact, 1);
        InterlockedIncrement(&telemetry_generation);
    }
    ReleaseSRWLockExclusive(&telemetry_write_lock);
}

#ifdef PHOTON_V6_NATIVE_TEST_HOOKS
static BYTE *native_test_main_base;
static volatile LONG native_test_fail_write_ordinal = -1;
static volatile LONG native_test_no_hot_lifecycle;
static volatile LONG native_test_passthrough_calls;
static volatile LONG native_test_fail_after_resume;
static volatile LONG native_test_probe_unpublished_semantics;
static volatile LONG native_test_unpublished_probe_checks;
static volatile LONG native_test_unpublished_probe_failures;
int photon_v6_native_test_gate_off_passthrough_predicate(void);
#if PHOTON_NATIVE_SELECTOR_ENABLED
static wchar_t native_test_special_root[MAX_PATH];
static volatile LONG native_test_ordinary_gate_attempts;
static volatile LONG native_test_force_selector_fatal_before_publish;
static volatile LONG native_test_force_selector_benign_before_publish;
static volatile LONG native_test_selector_query_drift;
#endif

void photon_v6_native_test_set_main_base(void *base) {
    native_test_main_base = (BYTE *)base;
}

#if PHOTON_NATIVE_SELECTOR_ENABLED
int photon_v6_native_test_set_special_root(const wchar_t *root) {
    size_t length;
    if (!root) { native_test_special_root[0]=0; return 1; }
    length=wcslen(root);
    if (!length || length>=MAX_PATH) return 0;
    memcpy(native_test_special_root,root,(length+1)*sizeof(wchar_t));
    return 1;
}

LONG photon_v6_native_test_ordinary_gate_count(void) {
    return InterlockedCompareExchange(&native_test_ordinary_gate_attempts,0,0);
}

void photon_v6_native_test_force_selector_fatal_before_publish(LONG enabled) {
    InterlockedExchange(&native_test_force_selector_fatal_before_publish,
        enabled?1:0);
}

void photon_v6_native_test_force_selector_benign_before_publish(LONG enabled) {
    InterlockedExchange(&native_test_force_selector_benign_before_publish,
        enabled?1:0);
}

void photon_v6_native_test_force_selector_query_drift(LONG mode) {
    InterlockedExchange(&native_test_selector_query_drift,mode);
}
#endif

void photon_v6_native_test_fail_write_at(LONG ordinal) {
    InterlockedExchange(&native_test_fail_write_ordinal, ordinal);
}

void photon_v6_native_test_set_no_hot_lifecycle(LONG enabled) {
    InterlockedExchange(&native_test_no_hot_lifecycle,enabled?1:0);
}

void photon_v6_native_test_fail_after_resume_once(LONG enabled) {
    InterlockedExchange(&native_test_fail_after_resume,enabled?1:0);
}

void photon_v6_native_test_probe_unpublished_semantics(LONG enabled) {
    InterlockedExchange(&native_test_probe_unpublished_semantics,enabled?1:0);
    InterlockedExchange(&native_test_unpublished_probe_checks,0);
    InterlockedExchange(&native_test_unpublished_probe_failures,0);
}

LONG photon_v6_native_test_unpublished_probe_checks(void) {
    return InterlockedCompareExchange(
        &native_test_unpublished_probe_checks,0,0);
}

LONG photon_v6_native_test_unpublished_probe_failures(void) {
    return InterlockedCompareExchange(
        &native_test_unpublished_probe_failures,0,0);
}

void photon_v6_native_test_emit_safe_telemetry(
    LONG loads, LONG overlays, LONG untargeted) {
    while (loads-- > 0) telemetry_increment(&exact_payload_loads);
    while (overlays-- > 0) telemetry_increment(&overlay_commits);
    while (untargeted-- > 0) telemetry_increment(&untargeted_decodes);
}

void photon_v6_native_test_emit_reject_fatal(void) {
    telemetry_reject_fatal();
}
#endif

static uint32_t installed_hook_count(void);

static int native_no_hot_lifecycle_enabled(void) {
#ifdef PHOTON_V6_NATIVE_TEST_HOOKS
    return InterlockedCompareExchange(&native_test_no_hot_lifecycle,0,0)!=0;
#else
    return 1;
#endif
}

static int native_semantics_enabled(void) {
    return InterlockedCompareExchange(&initialized,0,0)!=0 &&
        !InterlockedCompareExchange(&shutting_down,0,0) &&
        !InterlockedCompareExchange(&fatal_latch,0,0) &&
        !InterlockedCompareExchange(&native_semantic_gate_disabled,0,0);
}

static void pin_native_module_or_failfast(void) {
    HMODULE self=NULL,pinned=NULL;
    const void *anchor=(const void *)&photon_v6_pf_native_runtime_init;
    if (!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS |
            GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
            (LPCWSTR)anchor,&self) || !self ||
        !GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS |
            GET_MODULE_HANDLE_EX_FLAG_PIN,(LPCWSTR)anchor,&pinned) ||
        !pinned || pinned!=self) {
        RaiseFailFastException(NULL,NULL,0);
        TerminateProcess(GetCurrentProcess(),UINT32_C(0xE00057B4));
    }
    InterlockedExchange(&native_module_pinned,1);
}

static void native_mark_first_mutation(void) {
    InterlockedExchange(&native_first_mutation_committed,1);
    if (native_no_hot_lifecycle_enabled()) {
        if (!InterlockedCompareExchange(&native_module_pinned,0,0))
            pin_native_module_or_failfast();
        InterlockedExchange(&native_hooks_retained_until_process_exit,1);
    }
}

static void native_enter_no_hot_retained_state(int fatal_failure) {
    pin_native_module_or_failfast();
    InterlockedExchange(&native_hooks_retained_until_process_exit,1);
    InterlockedExchange(&native_semantic_gate_disabled,1);
    InterlockedExchange(&shutting_down,1);
    InterlockedExchange(&initialized,0);
    if (fatal_failure) telemetry_set_fatal();
}

static void native_lifecycle_ambiguity_failfast(void) {
    /* write_exact runs while peer threads may be suspended.  Initialization
     * has no published overlay semantics yet, so use lock-free terminal
     * latches and fail fast instead of touching a possibly-owned SRW lock. */
    pin_native_module_or_failfast();
    InterlockedExchange(&native_hooks_retained_until_process_exit,1);
    InterlockedExchange(&native_semantic_gate_disabled,1);
    InterlockedExchange(&shutting_down,1);
    InterlockedExchange(&initialized,0);
    InterlockedExchange(&fatal_latch,1);
#ifndef PHOTON_V6_NATIVE_TEST_HOOKS
    RaiseFailFastException(NULL,NULL,0);
    TerminateProcess(GetCurrentProcess(),UINT32_C(0xE00057B6));
#endif
}

static PointerHook pointer_hooks[] = {
    {PF_CR6_LOAD_SLOT_RVA, PF_CR6_LOAD_RVA,
        (void *)photon_v6_pf_hook_load_abi, NULL, NULL, 0, 0, 0},
    {PF_CR6_SURFACE_SLOT_RVA, PF_CR6_SURFACE_RVA,
        (void *)photon_v6_pf_hook_surface_abi, NULL, NULL, 0, 0, 0},
    {PF_CR6_RECT_SLOT_RVA, PF_CR6_RECT_RVA,
        (void *)photon_v6_pf_hook_rect_abi, NULL, NULL, 0, 0, 0},
};
static CallHook decode_hook;
#if PHOTON_NATIVE_HAS_CR6_ALT_EXACT_OVERLAY
static CallHook alt_decode_hooks[2];
#endif
#if PHOTON_NATIVE_HAS_CRIP008_EXACT_OVERLAY
static CallHook crip008_decode_hook;
#endif
#if PHOTON_NATIVE_HAS_CRIP008_DIRECT_EXACT_OVERLAY
static CallHook crip008_direct_decode_hooks[2];
#endif

static int range_readable(const void *pointer, SIZE_T count) {
    uintptr_t start = (uintptr_t)pointer, end = start + count;
    if (!pointer || !count || end < start) return 0;
    while (start < end) {
        MEMORY_BASIC_INFORMATION info;
        uintptr_t next;
        if (!VirtualQuery((const void *)start, &info, sizeof(info)) ||
            info.State != MEM_COMMIT ||
            (info.Protect & (PAGE_NOACCESS | PAGE_GUARD))) return 0;
        next = (uintptr_t)info.BaseAddress + info.RegionSize;
        if (next <= start) return 0;
        start = next < end ? next : end;
    }
    return 1;
}

static uintptr_t safe_pointer(const void *base, SIZE_T offset) {
    const BYTE *at = (const BYTE *)base + offset;
    return range_readable(at, sizeof(void *))
        ? (uintptr_t)*(void * const *)at : 0;
}

static uint32_t safe_u32(const void *base, SIZE_T offset) {
    const BYTE *at = (const BYTE *)base + offset;
    return range_readable(at, 4) ? *(const uint32_t *)at : UINT32_MAX;
}

static uint64_t fnv1a64(const BYTE *data, SIZE_T bytes) {
    uint64_t value = UINT64_C(14695981039346656037);
    SIZE_T index;
    for (index = 0; index < bytes; ++index) {
        value ^= data[index];
        value *= UINT64_C(1099511628211);
    }
    return value;
}

#if PHOTON_NATIVE_HAS_CRIP008_EXACT_OVERLAY && \
    !PHOTON_NATIVE_CRIP008_ORDINARY_TABLE
static int native_sha256_bytes(const BYTE *data, DWORD bytes,
                               BYTE output[32]) {
    HCRYPTPROV provider = 0;
    HCRYPTHASH hash = 0;
    DWORD output_bytes = 32;
    int ok = data && output && bytes &&
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
#endif

static int verify_image(void) {
    IMAGE_DOS_HEADER *dos = (IMAGE_DOS_HEADER *)main_base;
    IMAGE_NT_HEADERS32 *nt;
    static const BYTE prefix[] = {0x55,0x8B,0xEC,0x83,0xEC,0x14,0xA1};
    static const BYTE suffix[] = {
        0x33,0xC5,0x89,0x45,0xFC,0x0F,0xBF,0x45,0x14,0x8B,0xD1,
        0x0F,0xBF,0x4D,0x10,0x53,0x2B,0xC1,0x56,0x57,0x3D};
    const BYTE *decoder;
    if (!range_readable(dos, sizeof(*dos)) ||
        dos->e_magic != IMAGE_DOS_SIGNATURE) return 0;
    nt = (IMAGE_NT_HEADERS32 *)(main_base + dos->e_lfanew);
    if (!range_readable(nt, sizeof(*nt)) ||
        nt->Signature != IMAGE_NT_SIGNATURE ||
        nt->OptionalHeader.Magic != IMAGE_NT_OPTIONAL_HDR32_MAGIC ||
        nt->FileHeader.TimeDateStamp != PF_TIMESTAMP ||
        nt->OptionalHeader.SizeOfImage != PF_SIZE_OF_IMAGE) return 0;
    decoder = main_base + PF_CR6_DECODE_RVA;
    return range_readable(decoder, sizeof(prefix) + 4 + sizeof(suffix)) &&
        memcmp(decoder, prefix, sizeof(prefix)) == 0 &&
        *(const uint32_t *)(decoder + sizeof(prefix)) ==
            (uint32_t)(uintptr_t)(main_base + PF_SECURITY_COOKIE_RVA) &&
        memcmp(decoder + sizeof(prefix) + 4, suffix, sizeof(suffix)) == 0;
}

static int protection_exact(const void *address, DWORD expected) {
    MEMORY_BASIC_INFORMATION info;
    return VirtualQuery(address, &info, sizeof(info)) == sizeof(info) &&
        info.State == MEM_COMMIT && info.Protect == expected;
}

static int prepare_hooks(void) {
    size_t index;
    static const BYTE call_expected[5] = {0xE8,0x8D,0xDE,0xFF,0xFF};
    for (index = 0; index < sizeof(pointer_hooks) / sizeof(pointer_hooks[0]);
         ++index) {
        MEMORY_BASIC_INFORMATION info;
        PointerHook *hook = &pointer_hooks[index];
        hook->slot = (void **)(main_base + hook->slot_rva);
        if (!range_readable(hook->slot, sizeof(void *)) ||
            *hook->slot != main_base + hook->target_rva ||
            VirtualQuery(hook->slot, &info, sizeof(info)) != sizeof(info))
            return 0;
        hook->original = *hook->slot;
        hook->protection = info.Protect;
    }
    decode_hook.site = main_base + PF_CR6_DECODE_CALLSITE_RVA;
    if (!range_readable(decode_hook.site, 5) ||
        memcmp(decode_hook.site, call_expected, 5) != 0) return 0;
    {
        MEMORY_BASIC_INFORMATION info;
        intptr_t delta = (BYTE *)photon_v6_pf_hook_decode_abi -
            (decode_hook.site + 5);
        if (delta < INT32_MIN || delta > INT32_MAX ||
            VirtualQuery(decode_hook.site, &info, sizeof(info)) != sizeof(info))
            return 0;
        memcpy(decode_hook.original, call_expected, 5);
        decode_hook.replacement[0] = 0xE8;
        *(int32_t *)(decode_hook.replacement + 1) = (int32_t)delta;
        decode_hook.protection = info.Protect;
    }
#if PHOTON_NATIVE_HAS_CR6_ALT_EXACT_OVERLAY
    {
        static const BYTE alt_expected[2][5] = {
            {0xE8,0x0F,0xDB,0xFF,0xFF},
            {0xE8,0x22,0xDA,0xFF,0xFF},
        };
        static const DWORD alt_sites[2] = {
            PF_CR6_ALT_DECODE_CALLSITE0_RVA,
            PF_CR6_ALT_DECODE_CALLSITE1_RVA,
        };
        size_t alt_index;
        for (alt_index = 0; alt_index < 2; ++alt_index) {
            CallHook *hook = &alt_decode_hooks[alt_index];
            MEMORY_BASIC_INFORMATION info;
            intptr_t delta;
            hook->site = main_base + alt_sites[alt_index];
            if (!range_readable(hook->site, 5) ||
                memcmp(hook->site, alt_expected[alt_index], 5) != 0 ||
                VirtualQuery(hook->site, &info, sizeof(info)) != sizeof(info))
                return 0;
            delta = (BYTE *)photon_v6_pf_hook_alt_decode_abi -
                (hook->site + 5);
            if (delta < INT32_MIN || delta > INT32_MAX) return 0;
            memcpy(hook->original, alt_expected[alt_index], 5);
            hook->replacement[0] = 0xE8;
            *(int32_t *)(hook->replacement + 1) = (int32_t)delta;
            hook->protection = info.Protect;
        }
    }
#endif
#if PHOTON_NATIVE_HAS_CRIP008_EXACT_OVERLAY
    {
        static const BYTE crip_expected[5] = {0xE8,0x2B,0x00,0x00,0x00};
        MEMORY_BASIC_INFORMATION info;
        intptr_t delta;
        crip008_decode_hook.site =
            main_base + PHOTON_NATIVE_CRIP008_DECODE_CALLSITE_RVA;
        if (!range_readable(crip008_decode_hook.site, 5) ||
            memcmp(crip008_decode_hook.site, crip_expected, 5) != 0 ||
            VirtualQuery(crip008_decode_hook.site, &info, sizeof(info)) !=
                sizeof(info))
            return 0;
        delta = (BYTE *)photon_v6_pf_hook_crip008_decode_abi -
            (crip008_decode_hook.site + 5);
        if (delta < INT32_MIN || delta > INT32_MAX) return 0;
        memcpy(crip008_decode_hook.original, crip_expected, 5);
        crip008_decode_hook.replacement[0] = 0xE8;
        *(int32_t *)(crip008_decode_hook.replacement + 1) =
            (int32_t)delta;
        crip008_decode_hook.protection = info.Protect;
    }
#endif
#if PHOTON_NATIVE_HAS_CRIP008_DIRECT_EXACT_OVERLAY
    {
        static const BYTE direct_expected[2][5] = {
            {0xE8,0x13,0x15,0x00,0x00},
            {0xE8,0x3A,0x14,0x00,0x00},
        };
        static const DWORD direct_sites[2] = {
            PHOTON_NATIVE_CRIP008_DIRECT_DECODE_CALLSITE0_RVA,
            PHOTON_NATIVE_CRIP008_DIRECT_DECODE_CALLSITE1_RVA,
        };
        size_t direct_index;
        for (direct_index = 0; direct_index < 2; ++direct_index) {
            CallHook *hook = &crip008_direct_decode_hooks[direct_index];
            MEMORY_BASIC_INFORMATION info;
            intptr_t delta;
            hook->site = main_base + direct_sites[direct_index];
            if (!range_readable(hook->site, 5) ||
                memcmp(hook->site, direct_expected[direct_index], 5) != 0 ||
                VirtualQuery(hook->site, &info, sizeof(info)) != sizeof(info))
                return 0;
            delta = (BYTE *)photon_v6_pf_hook_crip008_direct_decode_abi -
                (hook->site + 5);
            if (delta < INT32_MIN || delta > INT32_MAX) return 0;
            memcpy(hook->original, direct_expected[direct_index], 5);
            hook->replacement[0] = 0xE8;
            *(int32_t *)(hook->replacement + 1) = (int32_t)delta;
            hook->protection = info.Protect;
        }
    }
#endif
    return 1;
}

static int write_exact(void *address, SIZE_T bytes, const void *expected,
                       const void *replacement, DWORD protection) {
    DWORD observed = 0, ignored = 0;
    int postwrite_ok;
#ifdef PHOTON_V6_NATIVE_TEST_HOOKS
    LONG fail_at = InterlockedCompareExchange(
        &native_test_fail_write_ordinal, 0, 0);
    if (fail_at > 0 &&
        InterlockedDecrement(&native_test_fail_write_ordinal) == 0) {
        InterlockedExchange(&native_test_fail_write_ordinal, -1);
        return 0;
    }
#endif
    if (memcmp(address, expected, bytes) != 0) return 0;
    if (native_no_hot_lifecycle_enabled() &&
        !InterlockedCompareExchange(&native_module_pinned,0,0))
        pin_native_module_or_failfast();
    if (!VirtualProtect(address, bytes, PAGE_EXECUTE_READWRITE, &observed))
        return 0;
    if (observed != protection || memcmp(address, expected, bytes) != 0) {
        VirtualProtect(address, bytes, observed, &ignored);
        return 0;
    }
    memcpy(address, replacement, bytes);
    native_mark_first_mutation();
    postwrite_ok = VirtualProtect(address, bytes, protection, &ignored) &&
        FlushInstructionCache(GetCurrentProcess(), address, bytes) &&
        protection_exact(address, protection) &&
        memcmp(address, replacement, bytes) == 0;
    if (postwrite_ok) return 1;

    if (native_no_hot_lifecycle_enabled()) {
        native_lifecycle_ambiguity_failfast();
        return -1;
    }

    /* A failed protection/cache/readback step is rolled back immediately. */
    if (!VirtualProtect(address, bytes, PAGE_EXECUTE_READWRITE, &observed))
        return -1;
    memcpy(address, expected, bytes);
    if (!FlushInstructionCache(GetCurrentProcess(), address, bytes) ||
        !VirtualProtect(address, bytes, protection, &ignored) ||
        !protection_exact(address, protection) ||
        memcmp(address, expected, bytes) != 0)
        return -1;
    return 0;
}

static int eip_inside(DWORD eip, const void *start, const void *end) {
    return (uintptr_t)eip >= (uintptr_t)start &&
           (uintptr_t)eip < (uintptr_t)end;
}

static int unsafe_eip(DWORD eip) {
    if (eip_inside(eip, decode_hook.site, decode_hook.site + 5) ||
        eip_inside(eip, photon_v6_pf_hook_decode_abi,
                    photon_v6_pf_hook_decode_end) ||
        eip_inside(eip, photon_v6_pf_hook_load_abi,
                    photon_v6_pf_hook_load_end) ||
        eip_inside(eip, photon_v6_pf_hook_surface_abi,
                    photon_v6_pf_hook_surface_end) ||
        eip_inside(eip, photon_v6_pf_hook_rect_abi,
                    photon_v6_pf_hook_rect_end)) return 1;
#if PHOTON_NATIVE_HAS_CR6_ALT_EXACT_OVERLAY
    {
        size_t index;
        for (index = 0; index < 2; ++index)
            if (eip_inside(eip, alt_decode_hooks[index].site,
                           alt_decode_hooks[index].site + 5)) return 1;
        if (eip_inside(eip, photon_v6_pf_hook_alt_decode_abi,
                       photon_v6_pf_hook_alt_decode_end)) return 1;
    }
#endif
#if PHOTON_NATIVE_HAS_CRIP008_EXACT_OVERLAY
    if (eip_inside(eip, crip008_decode_hook.site,
                   crip008_decode_hook.site + 5) ||
        eip_inside(eip, photon_v6_pf_hook_crip008_decode_abi,
                   photon_v6_pf_hook_crip008_decode_end)) return 1;
#endif
#if PHOTON_NATIVE_HAS_CRIP008_DIRECT_EXACT_OVERLAY
    {
        size_t index;
        for (index = 0; index < 2; ++index)
            if (eip_inside(eip, crip008_direct_decode_hooks[index].site,
                           crip008_direct_decode_hooks[index].site + 5))
                return 1;
        if (eip_inside(eip, photon_v6_pf_hook_crip008_direct_decode_abi,
                       photon_v6_pf_hook_crip008_direct_decode_end)) return 1;
    }
#endif
    return 0;
}

static int suspend_others(SuspendedThread threads[MAX_SUSPENDED], int *count) {
    HANDLE snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0);
    THREADENTRY32 entry;
    DWORD pid = GetCurrentProcessId(), own = GetCurrentThreadId();
    int used = 0, good = 1;
    if (snapshot == INVALID_HANDLE_VALUE) return 0;
    memset(&entry, 0, sizeof(entry));
    entry.dwSize = sizeof(entry);
    if (Thread32First(snapshot, &entry)) do {
        HANDLE thread;
        CONTEXT context;
        if (entry.th32OwnerProcessID != pid || entry.th32ThreadID == own)
            continue;
        if (used >= MAX_SUSPENDED) { good = 0; break; }
        thread = OpenThread(THREAD_SUSPEND_RESUME | THREAD_GET_CONTEXT,
                            FALSE, entry.th32ThreadID);
        if (!thread || SuspendThread(thread) == (DWORD)-1) {
            if (thread) CloseHandle(thread);
            good = 0; break;
        }
        memset(&context, 0, sizeof(context));
        context.ContextFlags = CONTEXT_CONTROL;
        if (!GetThreadContext(thread, &context)) {
            ResumeThread(thread); CloseHandle(thread); good = 0; break;
        }
        threads[used].handle = thread;
        threads[used].tid = entry.th32ThreadID;
        threads[used].eip = context.Eip;
        ++used;
    } while (Thread32Next(snapshot, &entry));
    CloseHandle(snapshot);
    *count = used;
    return good;
}

static int resume_all(SuspendedThread *threads, int count) {
    int good = 1;
    while (count-- > 0) {
        if (ResumeThread(threads[count].handle) == (DWORD)-1) good = 0;
        CloseHandle(threads[count].handle);
    }
    return good;
}

static int contexts_safe(const SuspendedThread *threads, int count) {
    int index;
    for (index = 0; index < count; ++index)
        if (unsafe_eip(threads[index].eip)) return 0;
    return InterlockedCompareExchange(&photon_v6_pf_hook_inflight, 0, 0) == 0;
}

static void journal_pointer_hook(PointerHook *hook) {
    if (InterlockedCompareExchange(&hook->journaled,1,0)==0)
        InterlockedIncrement(&native_mutation_journal_entries);
    InterlockedExchange(&hook->installed,1);
}

static void journal_call_hook(CallHook *hook) {
    if (InterlockedCompareExchange(&hook->journaled,1,0)==0)
        InterlockedIncrement(&native_mutation_journal_entries);
    InterlockedExchange(&hook->installed,1);
}

#ifdef PHOTON_V6_NATIVE_TEST_HOOKS
static int probe_unpublished_semantics_exact(void) {
    int exact;
    if (!InterlockedCompareExchange(
            &native_test_probe_unpublished_semantics,0,0)) return 1;
    InterlockedIncrement(&native_test_unpublished_probe_checks);
    exact=photon_v6_native_test_gate_off_passthrough_predicate();
    if (!exact) InterlockedIncrement(&native_test_unpublished_probe_failures);
    return exact;
}
#endif

static int install_all(void) {
    SuspendedThread threads[MAX_SUSPENDED];
    int count = 0, good = suspend_others(threads, &count);
    size_t index;
    if (good && !contexts_safe(threads, count)) good = 0;
    for (index = 0; good &&
         index < sizeof(pointer_hooks) / sizeof(pointer_hooks[0]); ++index) {
        PointerHook *hook = &pointer_hooks[index];
        int write_result = write_exact(
            hook->slot, sizeof(void *), &hook->original,
            &hook->replacement, hook->protection);
        if (write_result != 1) {
            good = 0;
            if (write_result < 0) {
                telemetry_set_fatal();
                if (memcmp(hook->slot, &hook->replacement,
                           sizeof(void *)) == 0)
                    journal_pointer_hook(hook);
            }
        } else {
            journal_pointer_hook(hook);
#ifdef PHOTON_V6_NATIVE_TEST_HOOKS
            if (!probe_unpublished_semantics_exact()) good=0;
#endif
        }
    }
    if (good) {
        int write_result = write_exact(
            decode_hook.site, 5, decode_hook.original,
            decode_hook.replacement, decode_hook.protection);
        if (write_result != 1) {
            good = 0;
            if (write_result < 0) {
                telemetry_set_fatal();
                if (memcmp(decode_hook.site, decode_hook.replacement, 5) == 0)
                    journal_call_hook(&decode_hook);
            }
        } else {
            journal_call_hook(&decode_hook);
#ifdef PHOTON_V6_NATIVE_TEST_HOOKS
            if (!probe_unpublished_semantics_exact()) good=0;
#endif
        }
    }
#if PHOTON_NATIVE_HAS_CR6_ALT_EXACT_OVERLAY
    for (index = 0; good && index < 2; ++index) {
        CallHook *hook = &alt_decode_hooks[index];
        int write_result = write_exact(
            hook->site, 5, hook->original,
            hook->replacement, hook->protection);
        if (write_result != 1) {
            good = 0;
            if (write_result < 0) {
                telemetry_set_fatal();
                if (memcmp(hook->site, hook->replacement, 5) == 0)
                    journal_call_hook(hook);
            }
        } else {
            journal_call_hook(hook);
#ifdef PHOTON_V6_NATIVE_TEST_HOOKS
            if (!probe_unpublished_semantics_exact()) good=0;
#endif
        }
    }
#endif
#if PHOTON_NATIVE_HAS_CRIP008_EXACT_OVERLAY
    if (good) {
        int write_result = write_exact(
            crip008_decode_hook.site, 5, crip008_decode_hook.original,
            crip008_decode_hook.replacement, crip008_decode_hook.protection);
        if (write_result != 1) {
            good = 0;
            if (write_result < 0) {
                telemetry_set_fatal();
                if (memcmp(crip008_decode_hook.site,
                           crip008_decode_hook.replacement, 5) == 0)
                    journal_call_hook(&crip008_decode_hook);
            }
        } else {
            journal_call_hook(&crip008_decode_hook);
#ifdef PHOTON_V6_NATIVE_TEST_HOOKS
            if (!probe_unpublished_semantics_exact()) good=0;
#endif
        }
    }
#endif
#if PHOTON_NATIVE_HAS_CRIP008_DIRECT_EXACT_OVERLAY
    for (index = 0; good && index < 2; ++index) {
        CallHook *hook = &crip008_direct_decode_hooks[index];
        int write_result = write_exact(
            hook->site, 5, hook->original,
            hook->replacement, hook->protection);
        if (write_result != 1) {
            good = 0;
            if (write_result < 0) {
                telemetry_set_fatal();
                if (memcmp(hook->site, hook->replacement, 5) == 0)
                    journal_call_hook(hook);
            }
        } else {
            journal_call_hook(hook);
#ifdef PHOTON_V6_NATIVE_TEST_HOOKS
            if (!probe_unpublished_semantics_exact()) good=0;
#endif
        }
    }
#endif
#ifdef PHOTON_V6_NATIVE_TEST_HOOKS
    if (!good && !native_no_hot_lifecycle_enabled()) {
#if PHOTON_NATIVE_HAS_CRIP008_DIRECT_EXACT_OVERLAY
        for (index = 2; index-- > 0;) {
            CallHook *hook = &crip008_direct_decode_hooks[index];
            if (hook->installed) {
                int write_result = write_exact(
                    hook->site, 5, hook->replacement,
                    hook->original, hook->protection);
                if (write_result == 1)
                    InterlockedExchange(&hook->installed, 0);
                else if (write_result < 0)
                    telemetry_set_fatal();
            }
        }
#endif
#if PHOTON_NATIVE_HAS_CRIP008_EXACT_OVERLAY
        if (crip008_decode_hook.installed) {
            int write_result = write_exact(
                crip008_decode_hook.site, 5,
                crip008_decode_hook.replacement,
                crip008_decode_hook.original,
                crip008_decode_hook.protection);
            if (write_result == 1)
                InterlockedExchange(&crip008_decode_hook.installed, 0);
            else if (write_result < 0)
                telemetry_set_fatal();
        }
#endif
#if PHOTON_NATIVE_HAS_CR6_ALT_EXACT_OVERLAY
        for (index = 2; index-- > 0;) {
            CallHook *hook = &alt_decode_hooks[index];
            if (hook->installed) {
                int write_result = write_exact(
                    hook->site, 5, hook->replacement,
                    hook->original, hook->protection);
                if (write_result == 1)
                    InterlockedExchange(&hook->installed, 0);
                else if (write_result < 0)
                    telemetry_set_fatal();
            }
        }
#endif
        if (decode_hook.installed) {
            int write_result = write_exact(
                decode_hook.site, 5, decode_hook.replacement,
                decode_hook.original, decode_hook.protection);
            if (write_result == 1)
                InterlockedExchange(&decode_hook.installed, 0);
            else if (write_result < 0)
                telemetry_set_fatal();
        }
        for (index = sizeof(pointer_hooks) / sizeof(pointer_hooks[0]);
             index-- > 0;) {
            PointerHook *hook = &pointer_hooks[index];
            if (hook->installed) {
                int write_result = write_exact(
                    hook->slot, sizeof(void *), &hook->replacement,
                    &hook->original, hook->protection);
                if (write_result == 1)
                    InterlockedExchange(&hook->installed, 0);
                else if (write_result < 0)
                    telemetry_set_fatal();
            }
        }
    }
#endif
    if (!resume_all(threads, count)) good = 0;
#ifdef PHOTON_V6_NATIVE_TEST_HOOKS
    if (good && !probe_unpublished_semantics_exact()) good=0;
    if (InterlockedExchange(&native_test_fail_after_resume,0)) good=0;
#endif
    return good;
}

#ifdef PHOTON_V6_NATIVE_TEST_HOOKS
static int restore_all_once(void) {
    SuspendedThread threads[MAX_SUSPENDED];
    int count = 0, good = suspend_others(threads, &count);
    size_t index;
    if (good && !contexts_safe(threads, count)) good = 0;
#if PHOTON_NATIVE_HAS_CRIP008_DIRECT_EXACT_OVERLAY
    {
        size_t direct_index;
        for (direct_index = 2; good && direct_index-- > 0;) {
            CallHook *hook = &crip008_direct_decode_hooks[direct_index];
            if (hook->installed) {
                int write_result = write_exact(
                    hook->site, 5, hook->replacement,
                    hook->original, hook->protection);
                good = write_result == 1;
                if (good) InterlockedExchange(&hook->installed, 0);
                else if (write_result < 0) telemetry_set_fatal();
            }
        }
    }
#endif
#if PHOTON_NATIVE_HAS_CRIP008_EXACT_OVERLAY
    if (good && crip008_decode_hook.installed) {
        int write_result = write_exact(
            crip008_decode_hook.site, 5,
            crip008_decode_hook.replacement,
            crip008_decode_hook.original,
            crip008_decode_hook.protection);
        good = write_result == 1;
        if (good) InterlockedExchange(&crip008_decode_hook.installed, 0);
        else if (write_result < 0) telemetry_set_fatal();
    }
#endif
#if PHOTON_NATIVE_HAS_CR6_ALT_EXACT_OVERLAY
    {
        size_t alt_index;
        for (alt_index = 2; good && alt_index-- > 0;) {
            CallHook *hook = &alt_decode_hooks[alt_index];
            if (hook->installed) {
                int write_result = write_exact(
                    hook->site, 5, hook->replacement,
                    hook->original, hook->protection);
                good = write_result == 1;
                if (good) InterlockedExchange(&hook->installed, 0);
                else if (write_result < 0) telemetry_set_fatal();
            }
        }
    }
#endif
    if (good && decode_hook.installed) {
        int write_result = write_exact(
            decode_hook.site, 5, decode_hook.replacement,
            decode_hook.original, decode_hook.protection);
        good = write_result == 1;
        if (good) InterlockedExchange(&decode_hook.installed, 0);
        else if (write_result < 0) telemetry_set_fatal();
    }
    for (index = sizeof(pointer_hooks) / sizeof(pointer_hooks[0]);
         good && index-- > 0;) {
        PointerHook *hook = &pointer_hooks[index];
        if (hook->installed) {
            int write_result = write_exact(
                hook->slot, sizeof(void *), &hook->replacement,
                &hook->original, hook->protection);
            good = write_result == 1;
            if (good) InterlockedExchange(&hook->installed, 0);
            else if (write_result < 0)
                telemetry_set_fatal();
        }
    }
    if (!resume_all(threads, count)) good = 0;
    return good;
}
#endif

static uint32_t installed_hook_count(void) {
    uint32_t count = decode_hook.installed ? 1U : 0U;
#if PHOTON_NATIVE_HAS_CR6_ALT_EXACT_OVERLAY
    size_t alt_index;
    for (alt_index = 0; alt_index < 2; ++alt_index)
        if (alt_decode_hooks[alt_index].installed) ++count;
#endif
#if PHOTON_NATIVE_HAS_CRIP008_EXACT_OVERLAY
    if (crip008_decode_hook.installed) ++count;
#endif
#if PHOTON_NATIVE_HAS_CRIP008_DIRECT_EXACT_OVERLAY
    {
        size_t direct_index;
        for (direct_index = 0; direct_index < 2; ++direct_index)
            if (crip008_direct_decode_hooks[direct_index].installed) ++count;
    }
#endif
    size_t index;
    for (index = 0; index < sizeof(pointer_hooks) / sizeof(pointer_hooks[0]);
         ++index) if (pointer_hooks[index].installed) ++count;
    return count;
}

static int find_binding(void *object, ObjectBinding *output) {
    int found = 0, index;
    EnterCriticalSection(&state_lock);
    for (index = 0; index < MAX_BINDINGS; ++index) {
        if (bindings[index].active && bindings[index].object == object) {
            *output = bindings[index]; found = 1; break;
        }
    }
    LeaveCriticalSection(&state_lock);
    return found;
}

static int find_binding_by_decoder(void *decoder, ObjectBinding *output) {
    int found = 0, index;
    EnterCriticalSection(&state_lock);
    for (index = 0; index < MAX_BINDINGS; ++index) {
        if (bindings[index].active && bindings[index].decoder == decoder) {
            *output = bindings[index]; found = 1; break;
        }
    }
    LeaveCriticalSection(&state_lock);
    return found;
}

static int binding_live_header_exact(const ObjectBinding *binding) {
    if (!binding || !binding->active || !binding->object ||
        !binding->payload || !binding->payload_bytes) return 0;
    return safe_pointer(binding->object, 0x18) ==
            (uintptr_t)binding->payload &&
        safe_u32(binding->object, 0x58) == binding->payload_bytes &&
        (!binding->decoder || safe_pointer(binding->object, 0x20) ==
            (uintptr_t)binding->decoder) &&
        range_readable(binding->payload, binding->payload_bytes);
}

static int snapshot_live_binding(void *object, ObjectBinding *output) {
    BYTE *payload;
    uint32_t bytes;
    if (!object || !output) return 0;
    bytes = safe_u32(object, 0x58);
    payload = (BYTE *)safe_pointer(object, 0x18);
    if (!bytes || bytes > 128U * 1024U * 1024U ||
        !range_readable(payload, bytes)) return 0;
    memset(output, 0, sizeof(*output));
    output->object = object;
    output->decoder = (void *)safe_pointer(object, 0x20);
    output->payload = payload;
    output->payload_bytes = bytes;
    output->payload_fnv1a64 = fnv1a64(payload, bytes);
    output->active = 1;
    return 1;
}

static void bind_object(void *object, void *payload, uint32_t bytes,
    uint64_t hash, int valid,
    uint32_t selector_special57_tracked,
    const uint8_t selector_payload_sha256[32],
    const char *selector_special_source_asset_id,
    const char *selector_special_context_identity_key) {
    ObjectBinding *free_slot = NULL;
    int index;
    EnterCriticalSection(&state_lock);
    for (index = 0; index < MAX_BINDINGS; ++index) {
        if (bindings[index].active && bindings[index].object == object) {
            free_slot = &bindings[index]; break;
        }
        if (!bindings[index].active && !free_slot) free_slot = &bindings[index];
    }
    if (!free_slot && valid) {
        /* The active decoder scope owns a value snapshot, not a pointer into
         * this table, so replacing an old cache entry is safe. */
        if (binding_write_cursor < 0 || binding_write_cursor >= MAX_BINDINGS)
            binding_write_cursor = 0;
        free_slot = &bindings[binding_write_cursor++];
    }
    if (free_slot) {
        memset(free_slot, 0, sizeof(*free_slot));
        if (valid) {
            free_slot->object = object;
            free_slot->decoder = (void *)safe_pointer(object, 0x20);
            free_slot->payload = payload;
            free_slot->payload_bytes = bytes;
            free_slot->payload_fnv1a64 = hash;
            free_slot->selector_special57_tracked=
                selector_special57_tracked?1U:0U;
            if (selector_special57_tracked && selector_payload_sha256)
                memcpy(free_slot->selector_payload_sha256,
                    selector_payload_sha256,32);
            if (selector_special57_tracked) {
                free_slot->selector_special_source_asset_id =
                    selector_special_source_asset_id;
                free_slot->selector_special_context_identity_key =
                    selector_special_context_identity_key;
            }
            free_slot->active = 1;
        }
    }
    LeaveCriticalSection(&state_lock);
}

static int push_active(const ObjectBinding *binding) {
    DWORD tid = GetCurrentThreadId();
    ActiveBinding *free_slot = NULL;
    LONG maximum_depth = 0;
    int index;
    EnterCriticalSection(&state_lock);
    for (index = 0; index < MAX_ACTIVE; ++index) {
        if (active_bindings[index].active &&
            active_bindings[index].tid == tid &&
            active_bindings[index].depth > maximum_depth)
            maximum_depth = active_bindings[index].depth;
        if (!active_bindings[index].active && !free_slot)
            free_slot = &active_bindings[index];
    }
    if (free_slot) {
        free_slot->tid = tid;
        free_slot->binding = *binding;
        free_slot->depth = maximum_depth + 1;
        free_slot->active = 1;
    }
    LeaveCriticalSection(&state_lock);
    if (!free_slot) telemetry_set_fatal();
    return free_slot != NULL;
}

static void pop_active(void) {
    DWORD tid = GetCurrentThreadId();
    ActiveBinding *top = NULL;
    int index;
    EnterCriticalSection(&state_lock);
    for (index = 0; index < MAX_ACTIVE; ++index) {
        if (active_bindings[index].active &&
            active_bindings[index].tid == tid &&
            (!top || active_bindings[index].depth > top->depth))
            top = &active_bindings[index];
    }
    if (top) memset(top, 0, sizeof(*top));
    LeaveCriticalSection(&state_lock);
}

static int current_active(ObjectBinding *output) {
    DWORD tid = GetCurrentThreadId();
    ActiveBinding *top = NULL;
    int found = 0, index;
    EnterCriticalSection(&state_lock);
    for (index = 0; index < MAX_ACTIVE; ++index) {
        if (active_bindings[index].active &&
            active_bindings[index].tid == tid &&
            active_bindings[index].depth > 0 &&
            (!top || active_bindings[index].depth > top->depth))
            top = &active_bindings[index];
    }
    if (top) { *output = top->binding; found = 1; }
    LeaveCriticalSection(&state_lock);
    return found;
}

#if PHOTON_NATIVE_SELECTOR_ENABLED
static int selector_string_equal(const char *left, const char *right) {
    if (!left || !right) return left == right;
    return strcmp(left, right) == 0;
}

static int selector_translation_provider_exact(
    const PhotonV6PfSelectorDecision *decision) {
    int translation_role,c07_primary_identity;
    if (!decision ||
        decision->target_index>=PHOTON_NATIVE_SPECIAL_VALID_TARGET_COUNT)
        return 0;
    translation_role=decision->provider_role==
            PHOTON_V6_PF_SELECTOR_PROVIDER_TRANSLATION_PRIMARY ||
        decision->provider_role==
            PHOTON_V6_PF_SELECTOR_PROVIDER_TRANSLATION_SECONDARY;
    if (!translation_role) return 0;
    c07_primary_identity=decision->raw_handle==UINT32_C(0x0E6B0654) &&
        selector_string_equal(decision->special_source_asset_id,
            "pf:rio000:0x1cc0ea48") &&
        selector_string_equal(decision->special_context_identity_key,
            "0x0000BCD8:0x000009D1:0x0E6B0654:OPTIONS_AUTOPLAY_VM_PRIMARY");
    if (decision->target_index!=5) return !c07_primary_identity;
    /* Target 5 is collision-07.  Only the runtime-proven inactive-selected
     * Auto-Read primary branch is authorized; a forged secondary decision or
     * another shared provider must still fail this independent native gate. */
    return decision->provider_role==
            PHOTON_V6_PF_SELECTOR_PROVIDER_TRANSLATION_PRIMARY &&
        c07_primary_identity;
}

static int selector_decision_is_special(
    const PhotonV6PfSelectorDecision *decision) {
    return decision && decision->struct_size == sizeof(*decision) &&
        decision->abi_version == PHOTON_V6_PF_SELECTOR_ADAPTER_ABI &&
        decision->target_index < PHOTON_NATIVE_SPECIAL_TARGET_COUNT;
}

static int selector_digest_nonzero(const uint8_t digest[32]) {
    uint8_t combined=0;
    size_t index;
    if (!digest) return 0;
    for (index=0;index<32;++index) combined|=digest[index];
    return combined!=0;
}

static int selector_translation_language_exact(
    const PhotonV6PfSelectorDecision *expected);

static int selector_decision_allows_special(
    const ObjectBinding *binding,
    const PhotonV6PfSelectorDecision *decision) {
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
#define SELECTOR_GATE_EXACT(condition,code) do { \
    if (!(condition)) { \
        photon_v6_pf_selector_adapter_diagnostic_native_gate(code); \
        return 0; \
    } \
} while (0)
    SELECTOR_GATE_EXACT(selector_decision_is_special(decision),1);
    SELECTOR_GATE_EXACT(binding,2);
    SELECTOR_GATE_EXACT(binding->active,3);
    SELECTOR_GATE_EXACT(binding->selector_special57_tracked==1,4);
    SELECTOR_GATE_EXACT(decision->decision==
        PHOTON_V6_PF_SELECTOR_ALLOW_SPECIAL57_TRANSLATION,5);
    SELECTOR_GATE_EXACT(decision->language_state==
        PHOTON_V6_PF_SELECTOR_LANGUAGE_TRANSLATION,6);
    SELECTOR_GATE_EXACT(decision->language_state_known==1,7);
    SELECTOR_GATE_EXACT(decision->target_index<
        PHOTON_NATIVE_SPECIAL_VALID_TARGET_COUNT,8);
    SELECTOR_GATE_EXACT(selector_translation_provider_exact(decision),9);
    SELECTOR_GATE_EXACT(decision->raw_handle!=0,10);
    SELECTOR_GATE_EXACT(decision->branch_identity_exact==1,11);
    SELECTOR_GATE_EXACT(decision->target_payload_exact==1,12);
    SELECTOR_GATE_EXACT(decision->materializer_commit_exact==1,13);
    SELECTOR_GATE_EXACT(decision->graph_epoch_current==1,14);
    SELECTOR_GATE_EXACT(decision->surface_scope_exact==1,15);
    SELECTOR_GATE_EXACT(decision->decode_scope_exact==1,16);
    SELECTOR_GATE_EXACT(decision->translation_overlay_allowed==1,17);
    SELECTOR_GATE_EXACT(decision->japanese_overlay_allowed==0,18);
    SELECTOR_GATE_EXACT(decision->selected_cref_identity_sequence!=0,19);
    SELECTOR_GATE_EXACT(decision->selected_materializer_sequence!=0,20);
    SELECTOR_GATE_EXACT(decision->selected_surface_sequence!=0,21);
    SELECTOR_GATE_EXACT(decision->object_generation!=0,22);
    SELECTOR_GATE_EXACT(decision->graph_root!=0,23);
    SELECTOR_GATE_EXACT(decision->selected_resource_node!=0,24);
    SELECTOR_GATE_EXACT(decision->selected_cr6_object==
        (uintptr_t)binding->object,25);
    SELECTOR_GATE_EXACT(decision->payload_bytes==binding->payload_bytes,26);
    SELECTOR_GATE_EXACT(decision->payload_fnv1a64==binding->payload_fnv1a64,27);
    SELECTOR_GATE_EXACT(selector_digest_nonzero(decision->payload_sha256),28);
    SELECTOR_GATE_EXACT(memcmp(decision->payload_sha256,
        binding->selector_payload_sha256,32)==0,29);
    SELECTOR_GATE_EXACT(selector_translation_language_exact(decision),30);
    SELECTOR_GATE_EXACT(selector_string_equal(
        decision->special_source_asset_id,
        binding->selector_special_source_asset_id),31);
    SELECTOR_GATE_EXACT(selector_string_equal(
        decision->special_context_identity_key,
        binding->selector_special_context_identity_key),32);
    SELECTOR_GATE_EXACT(decision->special_source_asset_id &&
        decision->special_source_asset_id[0],33);
#undef SELECTOR_GATE_EXACT
    return 1;
#else
    return selector_decision_is_special(decision) &&
        binding && binding->active && binding->selector_special57_tracked==1 &&
        decision->decision ==
            PHOTON_V6_PF_SELECTOR_ALLOW_SPECIAL57_TRANSLATION &&
        decision->language_state ==
            PHOTON_V6_PF_SELECTOR_LANGUAGE_TRANSLATION &&
        decision->language_state_known == 1 &&
        decision->target_index < PHOTON_NATIVE_SPECIAL_VALID_TARGET_COUNT &&
        selector_translation_provider_exact(decision) &&
        decision->raw_handle!=0 &&
        decision->branch_identity_exact == 1 &&
        decision->target_payload_exact == 1 &&
        decision->materializer_commit_exact == 1 &&
        decision->graph_epoch_current == 1 &&
        decision->surface_scope_exact == 1 &&
        decision->decode_scope_exact == 1 &&
        decision->translation_overlay_allowed == 1 &&
        decision->japanese_overlay_allowed == 0 &&
        decision->selected_cref_identity_sequence != 0 &&
        decision->selected_materializer_sequence != 0 &&
        decision->selected_surface_sequence != 0 &&
        decision->object_generation != 0 &&
        decision->graph_root != 0 &&
        decision->selected_resource_node != 0 &&
        decision->selected_cr6_object == (uintptr_t)binding->object &&
        decision->payload_bytes == binding->payload_bytes &&
        decision->payload_fnv1a64 == binding->payload_fnv1a64 &&
        selector_digest_nonzero(decision->payload_sha256) &&
        memcmp(decision->payload_sha256,
               binding->selector_payload_sha256,32)==0 &&
        selector_translation_language_exact(decision) &&
        selector_string_equal(decision->special_source_asset_id,
            binding->selector_special_source_asset_id) &&
        selector_string_equal(decision->special_context_identity_key,
            binding->selector_special_context_identity_key) &&
        decision->special_source_asset_id &&
        decision->special_source_asset_id[0];
#endif
}

static int selector_decision_same(
    const PhotonV6PfSelectorDecision *left,
    const PhotonV6PfSelectorDecision *right) {
    return left && right &&
        left->struct_size == right->struct_size &&
        left->abi_version == right->abi_version &&
        left->decision == right->decision &&
        left->language_state == right->language_state &&
        left->language_state_sequence == right->language_state_sequence &&
        left->language_state_known == right->language_state_known &&
        left->target_index == right->target_index &&
        left->provider_role == right->provider_role &&
        left->raw_handle == right->raw_handle &&
        left->branch_identity_exact == right->branch_identity_exact &&
        left->target_payload_exact == right->target_payload_exact &&
        left->materializer_commit_exact == right->materializer_commit_exact &&
        left->graph_epoch_current == right->graph_epoch_current &&
        left->surface_scope_exact == right->surface_scope_exact &&
        left->decode_scope_exact == right->decode_scope_exact &&
        left->translation_overlay_allowed ==
            right->translation_overlay_allowed &&
        left->japanese_overlay_allowed == right->japanese_overlay_allowed &&
        left->selected_cref_identity_sequence ==
            right->selected_cref_identity_sequence &&
        left->selected_materializer_sequence ==
            right->selected_materializer_sequence &&
        left->selected_surface_sequence ==
            right->selected_surface_sequence &&
        left->object_generation == right->object_generation &&
        left->graph_root == right->graph_root &&
        left->selected_resource_node == right->selected_resource_node &&
        left->selected_cr6_object == right->selected_cr6_object &&
        left->payload_bytes == right->payload_bytes &&
        left->payload_fnv1a64 == right->payload_fnv1a64 &&
        memcmp(left->payload_sha256,right->payload_sha256,
               sizeof(left->payload_sha256)) == 0 &&
        left->special_source_asset_id == right->special_source_asset_id &&
        left->special_context_identity_key ==
            right->special_context_identity_key &&
        selector_string_equal(left->special_source_asset_id,
                              right->special_source_asset_id) &&
        selector_string_equal(left->special_context_identity_key,
                              right->special_context_identity_key);
}

static int selector_translation_language_exact(
    const PhotonV6PfSelectorDecision *expected) {
    int32_t state = PHOTON_V6_PF_SELECTOR_LANGUAGE_UNKNOWN;
    uint32_t sequence = 0, allowed = 0;
    return photon_v6_pf_selector_adapter_language_query(
        &state, &sequence, &allowed) == 1 &&
        state == PHOTON_V6_PF_SELECTOR_LANGUAGE_TRANSLATION &&
        allowed == 1 &&
        (!expected ||
         (expected->language_state == state &&
          expected->language_state_sequence == sequence));
}

/*
 * The public route gate continues to reject special transports.  The selector
 * first proves the active Translation owner/action chain, then this prepare
 * phase loads its exact sidecar and captures the predecode destination when
 * the retail Cr6Ti call is in source-over mode.  The later commit phase repeats
 * the selector/language proof immediately before the only surface write.
 */
static int selector_prepare_special57(
    const ObjectBinding *binding,
    const PhotonV6PfSelectorDecision *selected,
    const PhotonPfDerivedSurface *derived,
    uint32_t width,
    uint32_t height,
    uint32_t decoder_flags,
    PhotonV6ExactOverlayPrepared *prepared,
    PhotonV6ExactOverlayReport *report) {
    PhotonV6Special57Image image;
    PhotonV6PfSelectorDecision prepare_decision;
    PhotonV6Special57LoadStatus load_status;
    PhotonV6ExactOverlayStatus overlay_status;
    uint64_t expected_bytes;
    int result = -1;
    memset(&image, 0, sizeof(image));
    memset(&prepare_decision, 0, sizeof(prepare_decision));
    if (!binding || !derived || !prepared || !report ||
        !selector_decision_allows_special(binding,selected))
        return 0;
    expected_bytes = (uint64_t)width * (uint64_t)height * UINT64_C(4);
    if (width > UINT32_MAX / 4U || expected_bytes > UINT32_MAX)
        return 0;
    load_status = photon_v6_special57_sidecar_load(
#if defined(PHOTON_V6_NATIVE_TEST_HOOKS)
        native_test_special_root[0]?native_test_special_root:ordinary_root,
#else
        ordinary_root,
#endif
        PHOTON_NATIVE_SPECIAL_SIDECAR_GAME,
        selected->special_source_asset_id,
        selected->special_context_identity_key,
        selected->payload_bytes, selected->payload_fnv1a64, &image);
    if (load_status != PHOTON_V6_SPECIAL57_LOAD_OK || !image.pixels ||
        image.width != width || image.height != height ||
        image.stride != width * 4U ||
        image.bytes != (uint32_t)expected_bytes)
        goto done;
    if (photon_v6_pf_selector_adapter_decode_query(&prepare_decision) != 1 ||
        !selector_decision_same(selected, &prepare_decision) ||
        !selector_decision_allows_special(binding,&prepare_decision) ||
        !selector_translation_language_exact(&prepare_decision)) {
        result = 0;
        goto done;
    }
    overlay_status = photon_v6_cr6ti_surface_prepare_rgba(
        &derived->view, 0, 0, width, height, image.pixels, image.bytes,
        decoder_flags, prepared, report);
    if (overlay_status != PHOTON_V6_EXACT_OVERLAY_OK) {
        result = -1;
        goto done;
    }
    result = 1;
done:
    photon_v6_special57_image_free(&image);
    return result;
}

static int selector_commit_special57(
    const ObjectBinding *binding,
    const PhotonV6PfSelectorDecision *selected,
    PhotonV6ExactOverlayPrepared *prepared,
    PhotonV6ExactOverlayReport *report) {
    PhotonV6PfSelectorDecision commit_decision;
    PhotonV6ExactOverlayStatus overlay_status;
    memset(&commit_decision, 0, sizeof(commit_decision));
    if (!binding || !prepared || !report) return -1;
    if (photon_v6_pf_selector_adapter_decode_query(&commit_decision) != 1 ||
        !selector_decision_same(selected, &commit_decision) ||
        !selector_decision_allows_special(binding,&commit_decision) ||
        !selector_translation_language_exact(&commit_decision)) {
        photon_v6_exact_overlay_prepared_free(prepared);
        return 0;
    }
    overlay_status = photon_v6_exact_overlay_commit_prepared(
        prepared, report);
    return overlay_status == PHOTON_V6_EXACT_OVERLAY_OK ? 1 : -1;
}
#endif

uintptr_t __attribute__((fastcall)) photon_v6_pf_hook_load_impl(
    void *object, void *edx, void *stream) {
    uintptr_t result;
    uint32_t bytes;
    uint64_t payload_hash = 0;
    BYTE *payload;
    int readable;
    uint32_t selector_special=0;
#if PHOTON_NATIVE_SELECTOR_ENABLED
    PhotonV6PfSelectorDecision selector_decision;
#endif
    (void)edx;
    result = real_load(object, stream);
    if (!native_semantics_enabled()) {
        InterlockedDecrement(&photon_v6_pf_hook_inflight);
        return result;
    }
    bytes = safe_u32(object, 0x58);
    payload = (BYTE *)safe_pointer(object, 0x18);
    readable = bytes > 0 && bytes <= 128U * 1024U * 1024U &&
        range_readable(payload, bytes);
    if (readable) payload_hash = fnv1a64(payload, bytes);
#if PHOTON_NATIVE_SELECTOR_ENABLED
    memset(&selector_decision, 0, sizeof(selector_decision));
    (void)photon_v6_pf_selector_adapter_note_load(
        object, readable ? payload : NULL, readable ? bytes : 0,
        payload_hash, &selector_decision);
    selector_special=selector_decision_is_special(&selector_decision)?1U:0U;
#endif
    bind_object(object, payload, bytes, payload_hash, readable,selector_special,
#if PHOTON_NATIVE_SELECTOR_ENABLED
        selector_special?selector_decision.payload_sha256:NULL,
        selector_special?selector_decision.special_source_asset_id:NULL,
        selector_special?selector_decision.special_context_identity_key:NULL
#else
        NULL,NULL,NULL
#endif
    );
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
    {
        ObjectBinding diagnostic_binding;
        memset(&diagnostic_binding, 0, sizeof(diagnostic_binding));
        diagnostic_binding.object = object;
        diagnostic_binding.decoder = (void *)safe_pointer(object, 0x20);
        diagnostic_binding.payload = payload;
        diagnostic_binding.payload_bytes = readable ? bytes : 0;
        diagnostic_binding.payload_fnv1a64 = readable ? payload_hash : 0;
        diagnostic_trace_event(
            readable ? "load" : "load_unreadable", &diagnostic_binding,
            diagnostic_binding.decoder, 0, 0, 0, 0, 0, 0, 0, 0,
            NULL,
#if PHOTON_NATIVE_SELECTOR_ENABLED
            (LONG)selector_decision.decision
#else
            -1
#endif
        );
    }
#endif
    if (readable) telemetry_increment(&exact_payload_loads);
    InterlockedDecrement(&photon_v6_pf_hook_inflight);
    return result;
}

static uintptr_t surface_common(SurfaceFn original, void *secondary,
    void *a1, uintptr_t a2, uintptr_t a3, void *a4) {
    void *object = (BYTE *)secondary - 0x0C;
    ObjectBinding binding;
    int bound;
    int pushed = 0;
#if PHOTON_NATIVE_SELECTOR_ENABLED
    PhotonV6PfSelectorDecision selector_decision;
    int selector_entered = 0;
#endif
    uintptr_t result;
    if (!native_semantics_enabled())
        return original(secondary,a1,a2,a3,a4);
#if PHOTON_NATIVE_SELECTOR_ENABLED
    memset(&selector_decision, 0, sizeof(selector_decision));
    selector_entered=photon_v6_pf_selector_adapter_surface_enter(
        object, &selector_decision)==1;
#endif
    bound=find_binding(object,&binding);
    if (bound && !binding_live_header_exact(&binding)) bound=0;
    if (!bound && snapshot_live_binding(object,&binding)) {
#if PHOTON_NATIVE_SELECTOR_ENABLED
        if (selector_entered && selector_decision_is_special(
                &selector_decision)) {
            binding.selector_special57_tracked=1;
            memcpy(binding.selector_payload_sha256,
                selector_decision.payload_sha256,32);
            binding.selector_special_source_asset_id =
                selector_decision.special_source_asset_id;
            binding.selector_special_context_identity_key =
                selector_decision.special_context_identity_key;
        }
#endif
        bind_object(binding.object, binding.payload, binding.payload_bytes,
            binding.payload_fnv1a64, 1,
            binding.selector_special57_tracked,
            binding.selector_special57_tracked?
                binding.selector_payload_sha256:NULL,
            binding.selector_special57_tracked?
                binding.selector_special_source_asset_id:NULL,
            binding.selector_special57_tracked?
                binding.selector_special_context_identity_key:NULL);
        bound=1;
    }
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
    if (bound) {
        diagnostic_trace_event(
            original == real_surface ? "surface_method_enter" :
                "rect_method_enter",
            &binding, binding.decoder, 1,
            (uint32_t)(uintptr_t)a1, (int32_t)a2, (uint32_t)a3,
            0, 0, 0, (uint32_t)(uintptr_t)a4, NULL, -1);
    }
#endif
    if (bound) pushed = push_active(&binding);
    result = original(secondary, a1, a2, a3, a4);
    if (pushed) pop_active();
#if PHOTON_NATIVE_SELECTOR_ENABLED
    if (selector_entered)
        photon_v6_pf_selector_adapter_surface_leave(object);
#endif
    return result;
}

uintptr_t __attribute__((fastcall)) photon_v6_pf_hook_surface_impl(
    void *secondary, void *edx, void *surface, uintptr_t x,
    uintptr_t y, void *options) {
    uintptr_t result;
    (void)edx;
    result = surface_common(real_surface, secondary, surface, x, y, options);
    InterlockedDecrement(&photon_v6_pf_hook_inflight);
    return result;
}

uintptr_t __attribute__((fastcall)) photon_v6_pf_hook_rect_impl(
    void *secondary, void *edx, void *rect, uintptr_t options,
    uintptr_t flags, void *surface) {
    uintptr_t result;
    (void)edx;
    result = surface_common(real_rect, secondary, rect, options, flags, surface);
    InterlockedDecrement(&photon_v6_pf_hook_inflight);
    return result;
}

typedef enum PhotonV6PfPreparedDecodeKind {
    PHOTON_V6_PF_PREPARED_ORDINARY = 1,
    PHOTON_V6_PF_PREPARED_SPECIAL57 = 2
} PhotonV6PfPreparedDecodeKind;

typedef struct PhotonV6PfPreparedDecode {
    uint32_t kind;
    ObjectBinding binding;
    PhotonPfDerivedSurface derived;
    PhotonV6ExactOverlayPrepared ordinary;
    PhotonV6ExactOverlayReport report;
    uint32_t binding_source;
    void *decoder;
    uint32_t args[7];
#if PHOTON_NATIVE_SELECTOR_ENABLED
    PhotonV6PfSelectorDecision selector_decision;
#endif
} PhotonV6PfPreparedDecode;

void *__attribute__((cdecl)) photon_v6_pf_decode_prepare(
    void *decoder, uint32_t a1, uint32_t a2, uint32_t a3, uint32_t a4,
    uint32_t a5, uint32_t a6, uint32_t a7) {
    ObjectBinding binding;
    PhotonPfDecoderSurfaceArgs args;
    PhotonPfDerivedSurface derived;
    PhotonV6ExactOverlayRequest request;
    PhotonV6PfPreparedDecode *prepared = NULL;
    PhotonV6ExactOverlayStatus overlay_status;
    uint32_t binding_source = 0;
    uint32_t left = (uint16_t)(a3 & 0xFFFFU);
    uint32_t top = (uint16_t)(a3 >> 16);
    uint32_t right = (uint16_t)(a4 & 0xFFFFU);
    uint32_t bottom = (uint16_t)(a4 >> 16);
#if PHOTON_NATIVE_SELECTOR_ENABLED
    PhotonV6PfSelectorDecision selector_decision;
    int selector_allowed;
#endif
    if (!native_semantics_enabled()) return NULL;
    if (InterlockedCompareExchange(&shutting_down, 0, 0) ||
        InterlockedCompareExchange(&fatal_latch, 0, 0)) {
        telemetry_increment(&untargeted_decodes); return NULL;
    }
    if (current_active(&binding)) {
        binding_source = 1;
    } else {
        /* The retail caller loads ECX from [Cr6-object+0x20] before calling
         * the native decoder.  It is a decoder object, not the compressed
         * payload pointer at +0x18.  Some UI paths reach the decoder without
         * entering either hooked surface vtable method, so the active-scope
         * lookup is legitimately empty there.  Recover by the exact decoder
         * member relation and re-hash the original payload before allowing a
         * write. */
        if (!decoder || !find_binding_by_decoder(decoder,&binding) ||
            binding.decoder != decoder ||
            !binding_live_header_exact(&binding) ||
            fnv1a64((const BYTE *)binding.payload,binding.payload_bytes) !=
                binding.payload_fnv1a64) {
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
            diagnostic_trace_event(
                "decode_binding_miss", NULL, decoder, 0, a1, (int32_t)a2,
                a3, a4, a5, a6, a7, NULL, -1);
#endif
            telemetry_increment(&untargeted_decodes); return NULL;
        }
        binding_source = 2;
    }
    if (left != 0 || top != 0 || !right || !bottom) {
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
        diagnostic_trace_event(
            "decode_rect_rejected", &binding, decoder, binding_source,
            a1, (int32_t)a2, a3, a4, a5, a6, a7, NULL, -1);
#endif
        telemetry_increment(&rejected_decodes); return NULL;
    }
    memset(&args, 0, sizeof(args));
    args.pixel_zero_zero = (BYTE *)(uintptr_t)a1;
    args.decoder_pitch = (int32_t)a2;
    args.target_left_top = a3;
    args.target_right_bottom = a4;
    args.clip_left_top = a5;
    args.clip_right_bottom = a6;
    args.flags = a7;
    memset(&derived, 0, sizeof(derived));
    if (photon_pf_derive_full_surface(&args, right, bottom, &derived) !=
        PHOTON_PF_DECODER_SURFACE_OK) {
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
        diagnostic_trace_event(
            "decode_surface_rejected", &binding, decoder, binding_source,
            a1, (int32_t)a2, a3, a4, a5, a6, a7, NULL, -1);
#endif
        telemetry_increment(&rejected_decodes); return NULL;
    }
#if PHOTON_NATIVE_SELECTOR_ENABLED
    memset(&selector_decision, 0, sizeof(selector_decision));
    selector_allowed = photon_v6_pf_selector_adapter_decode_query(
        &selector_decision);
    if (binding.selector_special57_tracked) {
        /* A load classified as one of the six tracked physical endpoints is
         * permanently dominated by the selector.  Any missing/stale/negative
         * decision is a deny tombstone and must never fall through to the
         * ordinary exact-payload gate. */
        if (selector_allowed != 1 ||
            !selector_decision_allows_special(&binding,&selector_decision)) {
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
            if (selector_allowed != 1)
                photon_v6_pf_selector_adapter_diagnostic_native_gate(34);
#endif
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
            diagnostic_trace_event(
                "decode_special_denied", &binding, decoder, binding_source,
                a1, (int32_t)a2, a3, a4, a5, a6, a7, NULL, -1);
#endif
            telemetry_increment(&untargeted_decodes);
            return NULL;
        }
        prepared = (PhotonV6PfPreparedDecode *)HeapAlloc(
            GetProcessHeap(), HEAP_ZERO_MEMORY, sizeof(*prepared));
        if (!prepared) {
            telemetry_reject_fatal();
            return NULL;
        }
        prepared->kind = PHOTON_V6_PF_PREPARED_SPECIAL57;
        prepared->binding = binding;
        prepared->derived = derived;
        prepared->binding_source = binding_source;
        prepared->decoder = decoder;
        prepared->args[0] = a1; prepared->args[1] = a2;
        prepared->args[2] = a3; prepared->args[3] = a4;
        prepared->args[4] = a5; prepared->args[5] = a6;
        prepared->args[6] = a7;
        prepared->selector_decision = selector_decision;
        {
            int special_result = selector_prepare_special57(
                &prepared->binding, &prepared->selector_decision,
                &prepared->derived, right, bottom, a7,
                &prepared->ordinary, &prepared->report);
            if (special_result != 1) {
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
                diagnostic_trace_event(
                    special_result == 0 ? "decode_special_prepare_denied" :
                        "decode_special_prepare_fatal",
                    &binding, decoder, binding_source, a1, (int32_t)a2,
                    a3, a4, a5, a6, a7, &prepared->report,
                    (LONG)special_result);
#endif
                if (special_result == 0)
                    telemetry_increment(&untargeted_decodes);
                else
                    telemetry_reject_fatal();
                photon_v6_exact_overlay_prepared_free(&prepared->ordinary);
                HeapFree(GetProcessHeap(), 0, prepared);
                return NULL;
            }
        }
        return prepared;
    }
    /* A special decision paired with an untracked native load is an identity
     * conflict, not an ordinary candidate. */
    if (selector_decision_is_special(&selector_decision)) {
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
        diagnostic_trace_event(
            "decode_special_conflict", &binding, decoder, binding_source,
            a1, (int32_t)a2, a3, a4, a5, a6, a7, NULL, -1);
#endif
        telemetry_increment(&untargeted_decodes);
        return NULL;
    }
#endif
    memset(&request, 0, sizeof(request));
    request.struct_size = sizeof(request);
    request.game = PHOTON_NATIVE_ROUTE_GAME;
    request.slot = PHOTON_V6_ROUTE_SLOT_TRANSLATION;
    request.transport = PHOTON_V6_ROUTE_TRANSPORT_ORDINARY_EXACT_PAYLOAD;
    request.ordinary_bundle_root = ordinary_root;
    request.payload_bytes = binding.payload_bytes;
    request.payload_fnv1a64 = binding.payload_fnv1a64;
    request.surface = &derived.view;
    request.expected_width = right;
    request.expected_height = bottom;
    request.decoder_flags = a7;
    prepared = (PhotonV6PfPreparedDecode *)HeapAlloc(
        GetProcessHeap(), HEAP_ZERO_MEMORY, sizeof(*prepared));
    if (!prepared) {
        telemetry_reject_fatal();
        return NULL;
    }
    prepared->kind = PHOTON_V6_PF_PREPARED_ORDINARY;
    prepared->binding = binding;
    prepared->derived = derived;
    prepared->binding_source = binding_source;
    prepared->decoder = decoder;
    prepared->args[0] = a1; prepared->args[1] = a2;
    prepared->args[2] = a3; prepared->args[3] = a4;
    prepared->args[4] = a5; prepared->args[5] = a6;
    prepared->args[6] = a7;
    /* Ordinary identities are themselves the write authority.  The generated
     * table admits only (a) custom Translation payloads proven absent from the
     * complete official PF/PM corpus, or (b) immutable official Translation
     * targets proven one-to-one, non-shared with Japanese, geometry-exact, and
     * free of out-of-scope aliases.  Consequently the PF language snapshot is
     * neither needed nor reliable here.  The 57 shared/conflicting identities
     * above remain selector-dominated and never reach this branch. */
#if PHOTON_NATIVE_SELECTOR_ENABLED && defined(PHOTON_V6_NATIVE_TEST_HOOKS)
    InterlockedIncrement(&native_test_ordinary_gate_attempts);
#endif
    overlay_status=photon_v6_exact_overlay_prepare(
        &request, &prepared->ordinary, &prepared->report);
    InterlockedExchange(&last_overlay_status, (LONG)overlay_status);
    InterlockedExchange(&last_overlay_route_gate_status,
                        (LONG)prepared->report.route_gate_status);
    InterlockedExchange(&last_overlay_sidecar_status,
                        (LONG)prepared->report.sidecar_status);
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
    if (overlay_status != PHOTON_V6_EXACT_OVERLAY_OK)
        diagnostic_trace_event(
            overlay_status == PHOTON_V6_EXACT_OVERLAY_IDENTITY_NOT_TARGETED ?
                "decode_ordinary_identity_not_targeted" :
                "decode_ordinary_prepare_failed",
            &binding, decoder, binding_source, a1, (int32_t)a2,
            a3, a4, a5, a6, a7, &prepared->report,
            (LONG)overlay_status);
#endif
    switch (overlay_status) {
    case PHOTON_V6_EXACT_OVERLAY_OK:
        return prepared;
    case PHOTON_V6_EXACT_OVERLAY_IDENTITY_NOT_TARGETED:
        telemetry_increment(&untargeted_decodes); break;
    default:
        telemetry_reject_fatal();
        break;
    }
    photon_v6_exact_overlay_prepared_free(&prepared->ordinary);
    HeapFree(GetProcessHeap(), 0, prepared);
    return NULL;
}

void __attribute__((cdecl)) photon_v6_pf_decode_commit(void *opaque) {
    PhotonV6PfPreparedDecode *prepared =
        (PhotonV6PfPreparedDecode *)opaque;
    if (!prepared) return;
#if PHOTON_NATIVE_SELECTOR_ENABLED
    if (prepared->kind == PHOTON_V6_PF_PREPARED_SPECIAL57) {
        int special_result = selector_commit_special57(
            &prepared->binding, &prepared->selector_decision,
            &prepared->ordinary, &prepared->report);
        if (special_result == 1)
            telemetry_increment(&overlay_commits);
        else if (special_result == 0)
            telemetry_increment(&untargeted_decodes);
        else
            telemetry_reject_fatal();
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
        diagnostic_trace_event(
            special_result == 1 ? "decode_special_commit" :
                (special_result == 0 ? "decode_special_untargeted" :
                    "decode_special_fatal"),
            &prepared->binding, prepared->decoder,
            prepared->binding_source, prepared->args[0],
            (int32_t)prepared->args[1], prepared->args[2],
            prepared->args[3], prepared->args[4], prepared->args[5],
            prepared->args[6], &prepared->report, (LONG)special_result);
#endif
        photon_v6_exact_overlay_prepared_free(&prepared->ordinary);
        HeapFree(GetProcessHeap(), 0, prepared);
        return;
    }
#endif
    if (prepared->kind == PHOTON_V6_PF_PREPARED_ORDINARY) {
        PhotonV6ExactOverlayStatus overlay_status =
            photon_v6_exact_overlay_commit_prepared(
                &prepared->ordinary, &prepared->report);
        InterlockedExchange(&last_overlay_status, (LONG)overlay_status);
        InterlockedExchange(&last_overlay_transaction_status,
                            (LONG)prepared->report.transaction.status);
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
        diagnostic_trace_event(
            overlay_status == PHOTON_V6_EXACT_OVERLAY_OK ?
                "decode_ordinary_composited_commit" :
                "decode_ordinary_composited_failed",
            &prepared->binding, prepared->decoder,
            prepared->binding_source, prepared->args[0],
            (int32_t)prepared->args[1], prepared->args[2],
            prepared->args[3], prepared->args[4], prepared->args[5],
            prepared->args[6], &prepared->report, (LONG)overlay_status);
#endif
        if (overlay_status == PHOTON_V6_EXACT_OVERLAY_OK)
            telemetry_increment(&overlay_commits);
        else
            telemetry_reject_fatal();
    } else {
        telemetry_reject_fatal();
    }
    photon_v6_exact_overlay_prepared_free(&prepared->ordinary);
    HeapFree(GetProcessHeap(), 0, prepared);
}

void __attribute__((cdecl)) photon_v6_pf_decode_apply(
    void *decoder, uint32_t a1, uint32_t a2, uint32_t a3, uint32_t a4,
    uint32_t a5, uint32_t a6, uint32_t a7) {
    void *prepared = photon_v6_pf_decode_prepare(
        decoder, a1, a2, a3, a4, a5, a6, a7);
    photon_v6_pf_decode_commit(prepared);
}

#if PHOTON_NATIVE_HAS_CR6_ALT_EXACT_OVERLAY
/*
 * Cr6Ti kind=2 uses a second, four-stack-argument decoder reached from the
 * two exact callsites inside the retail clipped/full-surface helper.  Its
 * first four arguments have the same pixel-zero, pitch, left/top and
 * right/bottom semantics as the ordinary seven-argument decoder; the clip is
 * necessarily that same rectangle.  The metadata byte at +7 selects the
 * retail compositing branch unless kind byte +9 selects the independent
 * direct decoder.  Normalize that branch to the existing exact-overlay core
 * so both decoder families share the same identity, geometry and transaction
 * gates.
 */
void *__attribute__((cdecl)) photon_v6_pf_alt_decode_prepare(
    void *decoder, void *metadata, uint32_t a1, uint32_t a2,
    uint32_t a3, uint32_t a4) {
    uint32_t decoder_flags = 1;
    if (metadata && range_readable(metadata, 10)) {
        const BYTE *bytes = (const BYTE *)metadata;
        if (bytes[9] != 2 && bytes[7] != 0) decoder_flags = 0;
    }
    return photon_v6_pf_decode_prepare(
        decoder, a1, a2, a3, a4, a3, a4, decoder_flags);
}
#endif

#if PHOTON_NATIVE_HAS_CRIP008_EXACT_OVERLAY
#if PHOTON_NATIVE_CRIP008_ORDINARY_TABLE
/*
 * PF date cards and a small set of other full-frame resources use CRip008
 * kind=3 rather than either Cr6Ti decoder family.  They still use the same
 * authenticated ordinary Translation identity table: payload length/FNV is
 * the authority, the sidecar loader proves the sealed PNG and exact geometry,
 * and the post-retail write uses the same transactional readback boundary.
 *
 * CRip008 already writes conventional straight-alpha BGRA, so this path must
 * not run the Cr6Ti 0..128 alpha-domain composition transform.  prepare() is
 * deliberately invoked with the direct-copy flag only to authenticate and
 * retain the conventional RGBA sidecar; commit applies those bytes directly
 * after the retail decoder returns.
 */
typedef struct PhotonV6PfCrip008OrdinaryPrepared {
    const BYTE *payload;
    uint32_t payload_bytes;
    uint64_t payload_fnv1a64;
    PhotonV6ExactOverlayPrepared ordinary;
    PhotonV6ExactOverlayReport report;
    ObjectBinding binding;
    uint32_t args[7];
} PhotonV6PfCrip008OrdinaryPrepared;

/*
 * The PF direct CRip008 caller passes the authenticated archive payload in
 * ECX and its decoder buffer extent in EDX.  Live captures prove that this
 * extent is not stable: the exact archive payload is followed by either two
 * or three allocation-padding bytes, depending on the buffer made for that
 * decode.  Those bytes are outside the archive payload and are not reliably
 * initialized (some calls contain zeros, others contain allocator residue).
 * Hashing the whole extent therefore makes the same retail asset acquire a
 * different identity between calls and runs.
 *
 * Keep the full caller extent in PhotonV6PfCrip008OrdinaryPrepared so commit
 * can still detect any post-prepare mutation.  For the sidecar lookup only,
 * retry the narrowly proven 800x600 date-card shape after removing exactly
 * two or three trailing extent bytes.  A retry is accepted only when the
 * resulting length/FNV pair is already present in the sealed ordinary table;
 * there is no prefix, fuzzy, filename, or visual matching fallback.
 */
static PhotonV6ExactOverlayStatus pf_crip008_prepare_archive_identity(
    const BYTE *payload, uint32_t payload_bytes,
    uint32_t rect_width, uint32_t rect_height,
    PhotonV6ExactOverlayRequest *request,
    PhotonV6ExactOverlayPrepared *prepared,
    PhotonV6ExactOverlayReport *report) {
    PhotonV6ExactOverlayStatus status;
    uint32_t trim_bytes;
    if (!payload || !request || !prepared || !report)
        return PHOTON_V6_EXACT_OVERLAY_INVALID_ARGUMENT;
    status = photon_v6_exact_overlay_prepare(request, prepared, report);
    if (status != PHOTON_V6_EXACT_OVERLAY_IDENTITY_NOT_TARGETED ||
        rect_width != 800U || rect_height != 600U ||
        payload_bytes < 120002U || payload_bytes > 130003U)
        return status;
    for (trim_bytes = 2U; trim_bytes <= 3U; ++trim_bytes) {
        uint32_t candidate_bytes;
        if (payload_bytes <= trim_bytes) break;
        candidate_bytes = payload_bytes - trim_bytes;
        request->payload_bytes = candidate_bytes;
        request->payload_fnv1a64 = fnv1a64(payload, candidate_bytes);
        status = photon_v6_exact_overlay_prepare(
            request, prepared, report);
        if (status != PHOTON_V6_EXACT_OVERLAY_IDENTITY_NOT_TARGETED)
            return status;
    }
    return status;
}

static int pf_crip008_unpack_pair(
    uint32_t packed, uint32_t *x, uint32_t *y) {
    int32_t signed_x = (int16_t)(packed & UINT32_C(0xFFFF));
    int32_t signed_y = (int16_t)(packed >> 16);
    if (!x || !y || signed_x < 0 || signed_y < 0) return 0;
    *x = (uint32_t)signed_x;
    *y = (uint32_t)signed_y;
    return 1;
}

static int pf_crip008_surface_general(
    BYTE *destination, int32_t decoder_pitch,
    uint32_t target_left_top, uint32_t target_right_bottom,
    uint32_t clip_left_top, uint32_t clip_right_bottom,
    PhotonV6CpuSurfaceView *surface,
    uint32_t *rect_x, uint32_t *rect_y,
    uint32_t *rect_width, uint32_t *rect_height) {
    PhotonPfDecoderSurfaceArgs args;
    PhotonPfDerivedSurface derived;
    uint32_t left, top, right, bottom;
    uint32_t clip_left, clip_top, clip_right, clip_bottom;
    if (!destination || !surface || !rect_x || !rect_y || !rect_width ||
        !rect_height ||
        !pf_crip008_unpack_pair(target_left_top, &left, &top) ||
        !pf_crip008_unpack_pair(target_right_bottom, &right, &bottom) ||
        !pf_crip008_unpack_pair(clip_left_top, &clip_left, &clip_top) ||
        !pf_crip008_unpack_pair(clip_right_bottom, &clip_right, &clip_bottom) ||
        left != 0 || top != 0 || !right || !bottom ||
        right > 16384 || bottom > 16384 ||
        clip_left != left || clip_top != top ||
        clip_right != right || clip_bottom != bottom)
        return 0;
    memset(&args, 0, sizeof(args));
    args.pixel_zero_zero = destination;
    args.decoder_pitch = decoder_pitch;
    args.target_left_top = target_left_top;
    args.target_right_bottom = target_right_bottom;
    args.clip_left_top = clip_left_top;
    args.clip_right_bottom = clip_right_bottom;
    args.flags = 1;
    memset(&derived, 0, sizeof(derived));
    if (photon_pf_derive_full_surface(&args, right, bottom, &derived) !=
        PHOTON_PF_DECODER_SURFACE_OK) return 0;
    *surface = derived.view;
    *rect_x = 0;
    *rect_y = 0;
    *rect_width = right;
    *rect_height = bottom;
    return 1;
}

void *__attribute__((cdecl)) photon_v6_pf_crip008_decode_prepare(
    const BYTE *payload, uint32_t payload_bytes, const void *flags_table,
    BYTE *destination, int32_t stride,
    uint32_t target_left_top, uint32_t target_right_bottom,
    uint32_t clip_left_top, uint32_t clip_right_bottom, int32_t mode) {
    PhotonV6PfCrip008OrdinaryPrepared *prepared = NULL;
    PhotonV6ExactOverlayRequest request;
    PhotonV6CpuSurfaceView surface;
    PhotonV6ExactOverlayStatus overlay_status;
    uint32_t rect_x, rect_y, rect_width, rect_height;
    uint64_t payload_hash;
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
    ObjectBinding diagnostic_binding;
#endif
    (void)flags_table;
    if (!native_semantics_enabled() ||
        InterlockedCompareExchange(&shutting_down, 0, 0) ||
        InterlockedCompareExchange(&fatal_latch, 0, 0) || !payload ||
        !payload_bytes || payload_bytes > 128U * 1024U * 1024U ||
        !range_readable(payload, payload_bytes))
        return NULL;
    payload_hash = fnv1a64(payload, payload_bytes);
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
    memset(&diagnostic_binding, 0, sizeof(diagnostic_binding));
    diagnostic_binding.payload = (void *)payload;
    diagnostic_binding.payload_bytes = payload_bytes;
    diagnostic_binding.payload_fnv1a64 = payload_hash;
    diagnostic_binding.active = 1;
#endif
    if (!pf_crip008_surface_general(
            destination, stride, target_left_top, target_right_bottom,
            clip_left_top, clip_right_bottom, &surface,
            &rect_x, &rect_y, &rect_width, &rect_height)) {
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
        diagnostic_trace_event(
            "crip008_surface_rejected", &diagnostic_binding,
            (void *)payload, 3, (uint32_t)(uintptr_t)destination, stride,
            target_left_top, target_right_bottom,
            clip_left_top, clip_right_bottom,
            (uint32_t)mode, NULL, -1);
#endif
        telemetry_increment(&untargeted_decodes);
        return NULL;
    }
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
    if (rect_width == 800U && rect_height == 600U &&
        payload_bytes >= 120000U && payload_bytes <= 130000U)
        diagnostic_dump_crip008_payload(
            payload, payload_bytes, payload_hash);
#endif
    prepared = (PhotonV6PfCrip008OrdinaryPrepared *)HeapAlloc(
        GetProcessHeap(), HEAP_ZERO_MEMORY, sizeof(*prepared));
    if (!prepared) {
        telemetry_reject_fatal();
        return NULL;
    }
    prepared->payload = payload;
    prepared->payload_bytes = payload_bytes;
    prepared->payload_fnv1a64 = payload_hash;
    prepared->binding.payload = (void *)payload;
    prepared->binding.payload_bytes = payload_bytes;
    prepared->binding.payload_fnv1a64 = payload_hash;
    prepared->binding.active = 1;
    prepared->args[0] = (uint32_t)(uintptr_t)destination;
    prepared->args[1] = (uint32_t)stride;
    prepared->args[2] = target_left_top;
    prepared->args[3] = target_right_bottom;
    prepared->args[4] = clip_left_top;
    prepared->args[5] = clip_right_bottom;
    prepared->args[6] = (uint32_t)mode;
    memset(&request, 0, sizeof(request));
    request.struct_size = sizeof(request);
    request.game = PHOTON_NATIVE_ROUTE_GAME;
    request.slot = PHOTON_V6_ROUTE_SLOT_TRANSLATION;
    request.transport = PHOTON_V6_ROUTE_TRANSPORT_ORDINARY_EXACT_PAYLOAD;
    request.ordinary_bundle_root = ordinary_root;
    request.payload_bytes = payload_bytes;
    request.payload_fnv1a64 = payload_hash;
    request.surface = &surface;
    request.rect_x = rect_x;
    request.rect_y = rect_y;
    request.expected_width = rect_width;
    request.expected_height = rect_height;
    request.decoder_flags = 1;
    overlay_status = pf_crip008_prepare_archive_identity(
        payload, payload_bytes, rect_width, rect_height,
        &request, &prepared->ordinary, &prepared->report);
    InterlockedExchange(&last_overlay_status, (LONG)overlay_status);
    InterlockedExchange(&last_overlay_route_gate_status,
                        (LONG)prepared->report.route_gate_status);
    InterlockedExchange(&last_overlay_sidecar_status,
                        (LONG)prepared->report.sidecar_status);
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
    if (overlay_status != PHOTON_V6_EXACT_OVERLAY_OK)
        diagnostic_trace_event(
            overlay_status == PHOTON_V6_EXACT_OVERLAY_IDENTITY_NOT_TARGETED ?
                "crip008_ordinary_identity_not_targeted" :
                "crip008_ordinary_prepare_failed",
            &prepared->binding, (void *)payload, 3,
            prepared->args[0], stride, prepared->args[2],
            prepared->args[3], prepared->args[4], prepared->args[5],
            prepared->args[6], &prepared->report, (LONG)overlay_status);
#endif
    switch (overlay_status) {
    case PHOTON_V6_EXACT_OVERLAY_OK:
        telemetry_increment(&exact_payload_loads);
        return prepared;
    case PHOTON_V6_EXACT_OVERLAY_IDENTITY_NOT_TARGETED:
        telemetry_increment(&untargeted_decodes);
        break;
    default:
        telemetry_reject_fatal();
        break;
    }
    photon_v6_exact_overlay_prepared_free(&prepared->ordinary);
    HeapFree(GetProcessHeap(), 0, prepared);
    return NULL;
}

void *__attribute__((cdecl)) photon_v6_pf_crip008_direct_decode_prepare(
    const BYTE *payload, uint32_t payload_bytes, const void *flags_table,
    BYTE *destination, int32_t decoder_pitch,
    uint32_t target_left_top, uint32_t target_right_bottom) {
    return photon_v6_pf_crip008_decode_prepare(
        payload, payload_bytes, flags_table, destination, decoder_pitch,
        target_left_top, target_right_bottom,
        target_left_top, target_right_bottom, 1);
}

void __attribute__((cdecl)) photon_v6_pf_crip008_decode_commit(void *opaque) {
    PhotonV6PfCrip008OrdinaryPrepared *prepared =
        (PhotonV6PfCrip008OrdinaryPrepared *)opaque;
    PhotonV6SurfaceTransactionStatus transaction_status;
    PhotonV6ExactOverlayStatus overlay_status;
    int payload_exact;
    if (!prepared) return;
    payload_exact = native_semantics_enabled() &&
        !InterlockedCompareExchange(&shutting_down, 0, 0) &&
        !InterlockedCompareExchange(&fatal_latch, 0, 0) &&
        prepared->payload && prepared->payload_bytes &&
        prepared->payload_bytes <= 128U * 1024U * 1024U &&
        range_readable(prepared->payload, prepared->payload_bytes) &&
        fnv1a64(prepared->payload, prepared->payload_bytes) ==
            prepared->payload_fnv1a64;
    if (payload_exact) {
        transaction_status = photon_v6_surface_transaction_apply(
            &prepared->ordinary.surface,
            prepared->ordinary.rect_x, prepared->ordinary.rect_y,
            prepared->ordinary.width, prepared->ordinary.height,
            prepared->ordinary.source_rgba, prepared->ordinary.rgba_bytes,
            &prepared->report.transaction);
        overlay_status = transaction_status ==
                PHOTON_V6_SURFACE_TRANSACTION_OK ?
            PHOTON_V6_EXACT_OVERLAY_OK :
            PHOTON_V6_EXACT_OVERLAY_SURFACE_TRANSACTION_FAILED;
        prepared->report.status = (uint32_t)overlay_status;
        prepared->report.destination_committed =
            overlay_status == PHOTON_V6_EXACT_OVERLAY_OK ? 1U : 0U;
        InterlockedExchange(&last_overlay_transaction_status,
                            (LONG)transaction_status);
        InterlockedExchange(&last_overlay_status, (LONG)overlay_status);
        if (overlay_status == PHOTON_V6_EXACT_OVERLAY_OK)
            telemetry_increment(&overlay_commits);
        else
            telemetry_reject_fatal();
    } else {
        overlay_status = PHOTON_V6_EXACT_OVERLAY_INVALID_ARGUMENT;
        prepared->report.status = (uint32_t)overlay_status;
        prepared->report.destination_committed = 0;
        telemetry_reject_fatal();
    }
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
    diagnostic_trace_event(
        overlay_status == PHOTON_V6_EXACT_OVERLAY_OK ?
            "crip008_ordinary_commit" : "crip008_ordinary_commit_failed",
        &prepared->binding, (void *)prepared->payload, 3,
        prepared->args[0], (int32_t)prepared->args[1], prepared->args[2],
        prepared->args[3], prepared->args[4], prepared->args[5],
        prepared->args[6], &prepared->report, (LONG)overlay_status);
#endif
    photon_v6_exact_overlay_prepared_free(&prepared->ordinary);
    HeapFree(GetProcessHeap(), 0, prepared);
}
#else
/*
 * PM has one V6 endpoint whose retail object is CRip008 kind=3 instead of
 * Cr6Ti.  Its decoder ABI is independently pinned at PM RVA 0x0017B460:
 * ECX=payload, EDX=payload bytes, followed by eight caller-clean stack
 * arguments.  The Japanese record remains untouched.  Only the exact retail
 * Translation endpoint (length + FNV + SHA-256), while the authenticated PM
 * image-language state is Translation, can hold a generation-bound lease and
 * replace the post-decode CPU surface with the sealed V6 PNG.
 */
typedef struct PhotonV6PmCrip008Prepared {
    const BYTE *payload;
    uint32_t payload_bytes;
    uint64_t payload_fnv1a64;
    uint32_t lease_token;
    uint32_t language_generation;
    PhotonV6Special57Image image;
    PhotonV6CpuSurfaceView surface;
} PhotonV6PmCrip008Prepared;

static const BYTE photon_v6_pm_crip008_payload_sha256[32] = {
    0x63,0xCD,0x97,0xA1,0x0C,0x17,0x50,0xFA,
    0x34,0x9F,0x70,0x13,0x31,0x01,0x52,0x5A,
    0x76,0x26,0xBA,0x13,0x3E,0x0C,0x8B,0xB5,
    0x87,0xC1,0x59,0xD3,0x5A,0xF5,0xDE,0xF1
};

static int pm_crip008_payload_exact(const BYTE *payload, uint32_t bytes,
                                    uint64_t *hash_output) {
    BYTE digest[32];
    uint64_t hash;
    if (!payload || bytes != PHOTON_NATIVE_CRIP008_PAYLOAD_BYTES ||
        !range_readable(payload, bytes)) return 0;
    hash = fnv1a64(payload, bytes);
    if (hash != PHOTON_NATIVE_CRIP008_PAYLOAD_FNV1A64 ||
        !native_sha256_bytes(payload, bytes, digest) ||
        memcmp(digest, photon_v6_pm_crip008_payload_sha256,
               sizeof(digest)) != 0) return 0;
    if (hash_output) *hash_output = hash;
    return 1;
}

static int pm_crip008_surface_exact(
    BYTE *destination, int32_t stride, int32_t x0, int32_t x1,
    int32_t y0, int32_t y1, PhotonV6CpuSurfaceView *surface) {
    uint32_t absolute_stride;
    uint64_t span;
    intptr_t last_offset;
    BYTE *bounds_base;
    if (!destination || !surface || stride == INT32_MIN ||
        x0 != 0 || y0 != 0 ||
        x1 != (int32_t)PHOTON_NATIVE_CRIP008_WIDTH ||
        y1 != (int32_t)PHOTON_NATIVE_CRIP008_HEIGHT)
        return 0;
    absolute_stride = stride < 0 ? (uint32_t)(-stride) : (uint32_t)stride;
    if (absolute_stride < PHOTON_NATIVE_CRIP008_WIDTH * 4U) return 0;
    span = (uint64_t)(PHOTON_NATIVE_CRIP008_HEIGHT - 1U) *
        absolute_stride + (uint64_t)PHOTON_NATIVE_CRIP008_WIDTH * 4U;
    if (!span || span > SIZE_MAX) return 0;
    last_offset = (intptr_t)(PHOTON_NATIVE_CRIP008_HEIGHT - 1U) *
        (intptr_t)stride;
    if ((last_offset < 0 && (uintptr_t)(-last_offset) >
            (uintptr_t)destination) ||
        (last_offset > 0 && (uintptr_t)last_offset >
            UINTPTR_MAX - (uintptr_t)destination)) return 0;
    bounds_base = stride < 0 ? destination + last_offset : destination;
    memset(surface, 0, sizeof(*surface));
    surface->bounds_base = bounds_base;
    surface->bounds_bytes = (size_t)span;
    surface->base = destination;
    surface->signed_stride = stride;
    surface->surface_width = PHOTON_NATIVE_CRIP008_WIDTH;
    surface->surface_height = PHOTON_NATIVE_CRIP008_HEIGHT;
    surface->memory_format = PHOTON_V6_CPU_SURFACE_BGRA8_STRAIGHT;
    surface->row_orientation = PHOTON_V6_CPU_SURFACE_ROWS_FORWARD;
    return 1;
}

void *__attribute__((cdecl)) photon_v6_pf_crip008_decode_prepare(
    const BYTE *payload, uint32_t payload_bytes, const void *flags_table,
    BYTE *destination, int32_t stride, int32_t x0, int32_t x1,
    int32_t y0, int32_t y1, int32_t mode) {
    PhotonV6PmCrip008Prepared *prepared = NULL;
    PhotonV6Special57LoadStatus load_status;
    int32_t language_state = PHOTON_V6_PF_SELECTOR_LANGUAGE_UNKNOWN;
    uint32_t language_sequence = 0, allow_translation = 0;
    uint64_t payload_hash = 0;
    (void)flags_table;
    (void)mode;
    if (!native_semantics_enabled() ||
        InterlockedCompareExchange(&shutting_down, 0, 0) ||
        InterlockedCompareExchange(&fatal_latch, 0, 0) ||
        !pm_crip008_payload_exact(payload, payload_bytes, &payload_hash))
        return NULL;
    if (photon_v6_pf_selector_adapter_language_query(
            &language_state, &language_sequence, &allow_translation) != 1 ||
        language_state != PHOTON_V6_PF_SELECTOR_LANGUAGE_TRANSLATION ||
        allow_translation != 1) return NULL;
    prepared = (PhotonV6PmCrip008Prepared *)HeapAlloc(
        GetProcessHeap(), HEAP_ZERO_MEMORY, sizeof(*prepared));
    if (!prepared) {
        telemetry_reject_fatal();
        return NULL;
    }
    if (!photon_v6_pf_selector_adapter_ordinary_lease_acquire(
            &prepared->lease_token, &prepared->language_generation) ||
        prepared->language_generation != language_sequence ||
        !photon_v6_pf_selector_adapter_ordinary_lease_validate(
            prepared->lease_token, prepared->language_generation) ||
        !pm_crip008_surface_exact(destination, stride, x0, x1, y0, y1,
                                  &prepared->surface))
        goto reject;
    prepared->payload = payload;
    prepared->payload_bytes = payload_bytes;
    prepared->payload_fnv1a64 = payload_hash;
    load_status = photon_v6_special57_sidecar_load(
        ordinary_root, PHOTON_V6_SPECIAL57_GAME_PM,
        "pm:rio000:0x64e21260",
        "PM_CRIP008:11953:DB6996887D84269A:63CD97A10C1750FA349F70133101525A7626BA133E0C8BB587C159D35AF5DEF1",
        payload_bytes, payload_hash, &prepared->image);
    InterlockedExchange(&last_overlay_sidecar_status, (LONG)load_status);
    if (load_status != PHOTON_V6_SPECIAL57_LOAD_OK ||
        !prepared->image.pixels ||
        prepared->image.width != PHOTON_NATIVE_CRIP008_WIDTH ||
        prepared->image.height != PHOTON_NATIVE_CRIP008_HEIGHT ||
        prepared->image.stride != PHOTON_NATIVE_CRIP008_WIDTH * 4U ||
        prepared->image.bytes != PHOTON_NATIVE_CRIP008_WIDTH *
            PHOTON_NATIVE_CRIP008_HEIGHT * 4U) {
        telemetry_reject_fatal();
        goto reject;
    }
    telemetry_increment(&exact_payload_loads);
    return prepared;

reject:
    if (prepared->lease_token)
        photon_v6_pf_selector_adapter_ordinary_lease_release(
            prepared->lease_token, prepared->language_generation);
    photon_v6_special57_image_free(&prepared->image);
    HeapFree(GetProcessHeap(), 0, prepared);
    return NULL;
}

void __attribute__((cdecl)) photon_v6_pf_crip008_decode_commit(void *opaque) {
    PhotonV6PmCrip008Prepared *prepared =
        (PhotonV6PmCrip008Prepared *)opaque;
    PhotonV6SurfaceTransactionReport report;
    PhotonV6SurfaceTransactionStatus status;
    int32_t language_state = PHOTON_V6_PF_SELECTOR_LANGUAGE_UNKNOWN;
    uint32_t language_sequence = 0, allow_translation = 0;
    uint64_t payload_hash = 0;
    int exact = 0;
    if (!prepared) return;
    memset(&report, 0, sizeof(report));
    exact = native_semantics_enabled() &&
        photon_v6_pf_selector_adapter_ordinary_lease_validate(
            prepared->lease_token, prepared->language_generation) == 1 &&
        photon_v6_pf_selector_adapter_language_query(
            &language_state, &language_sequence, &allow_translation) == 1 &&
        language_state == PHOTON_V6_PF_SELECTOR_LANGUAGE_TRANSLATION &&
        allow_translation == 1 &&
        language_sequence == prepared->language_generation &&
        pm_crip008_payload_exact(prepared->payload,
                                 prepared->payload_bytes, &payload_hash) &&
        payload_hash == prepared->payload_fnv1a64;
    if (exact) {
        status = photon_v6_surface_transaction_apply(
            &prepared->surface, 0, 0,
            PHOTON_NATIVE_CRIP008_WIDTH, PHOTON_NATIVE_CRIP008_HEIGHT,
            prepared->image.pixels, prepared->image.bytes, &report);
        InterlockedExchange(&last_overlay_transaction_status, (LONG)status);
        InterlockedExchange(&last_overlay_status,
            status == PHOTON_V6_SURFACE_TRANSACTION_OK ?
                PHOTON_V6_EXACT_OVERLAY_OK :
                PHOTON_V6_EXACT_OVERLAY_SURFACE_TRANSACTION_FAILED);
        if (status == PHOTON_V6_SURFACE_TRANSACTION_OK)
            telemetry_increment(&overlay_commits);
        else
            telemetry_reject_fatal();
    } else {
        telemetry_increment(&untargeted_decodes);
    }
    photon_v6_pf_selector_adapter_ordinary_lease_release(
        prepared->lease_token, prepared->language_generation);
    photon_v6_special57_image_free(&prepared->image);
    HeapFree(GetProcessHeap(), 0, prepared);
}
#endif
#endif

#ifdef PHOTON_V6_NATIVE_TEST_HOOKS
static uintptr_t __attribute__((thiscall)) native_test_load_passthrough(
    void *object, void *stream) {
    (void)object; (void)stream;
    InterlockedIncrement(&native_test_passthrough_calls);
    return UINT32_C(0x57B40001);
}

static uintptr_t __attribute__((thiscall)) native_test_surface_passthrough(
    void *secondary, void *a1, uintptr_t a2, uintptr_t a3, void *a4) {
    (void)secondary; (void)a1; (void)a2; (void)a3; (void)a4;
    InterlockedIncrement(&native_test_passthrough_calls);
    return UINT32_C(0x57B40002);
}

int photon_v6_native_test_binding_capacity_decoder_recovery(void) {
    enum { TEST_OBJECT_BYTES = 0x80, TEST_EXTRA_BINDINGS = 32 };
    BYTE *objects;
    size_t total = (size_t)(MAX_BINDINGS + TEST_EXTRA_BINDINGS) *
        TEST_OBJECT_BYTES;
    ObjectBinding recovered;
    int index, exact = 0;
    objects = (BYTE *)HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, total);
    if (!objects || !InterlockedCompareExchange(&lock_ready,0,0)) {
        if (objects) HeapFree(GetProcessHeap(),0,objects);
        return 0;
    }
    EnterCriticalSection(&state_lock);
    memset(bindings,0,sizeof(bindings));
    binding_write_cursor=0;
    LeaveCriticalSection(&state_lock);
    for (index=0;index<MAX_BINDINGS+TEST_EXTRA_BINDINGS;++index) {
        BYTE *object=objects+(size_t)index*TEST_OBJECT_BYTES;
        BYTE *payload=object+0x70;
        void *decoder=object+0x60;
        *payload=(BYTE)(index+1);
        *(void **)(object+0x18)=payload;
        *(void **)(object+0x20)=decoder;
        *(uint32_t *)(object+0x58)=1;
        bind_object(object,payload,1,fnv1a64(payload,1),1,0,
            NULL,NULL,NULL);
    }
    {
        BYTE *late=objects+(size_t)(MAX_BINDINGS+TEST_EXTRA_BINDINGS-1)*
            TEST_OBJECT_BYTES;
        void *decoder=*(void **)(late+0x20);
        exact=find_binding_by_decoder(decoder,&recovered) &&
            recovered.object==late && recovered.decoder==decoder &&
            binding_live_header_exact(&recovered) &&
            fnv1a64((const BYTE *)recovered.payload,
                    recovered.payload_bytes)==recovered.payload_fnv1a64 &&
            !find_binding_by_decoder(recovered.payload,&recovered);
    }
    EnterCriticalSection(&state_lock);
    memset(bindings,0,sizeof(bindings));
    binding_write_cursor=0;
    LeaveCriticalSection(&state_lock);
    HeapFree(GetProcessHeap(),0,objects);
    return exact;
}

int photon_v6_native_test_gate_off_passthrough_predicate(void) {
    ObjectBinding binding_snapshot_copy[MAX_BINDINGS];
    ActiveBinding active_snapshot_copy[MAX_ACTIVE];
    wchar_t root_snapshot[sizeof(ordinary_root)/sizeof(ordinary_root[0])];
    LoadFn saved_load=real_load;
    SurfaceFn saved_surface=real_surface,saved_rect=real_rect;
    BYTE object[0x80];
    LONG generation=InterlockedCompareExchange(&telemetry_generation,0,0);
    LONG loads=InterlockedCompareExchange(&exact_payload_loads,0,0);
    LONG overlays=InterlockedCompareExchange(&overlay_commits,0,0);
    LONG untargeted=InterlockedCompareExchange(&untargeted_decodes,0,0);
    LONG rejected=InterlockedCompareExchange(&rejected_decodes,0,0);
    LONG fatal=InterlockedCompareExchange(&fatal_latch,0,0);
    LONG inflight=InterlockedCompareExchange(&photon_v6_pf_hook_inflight,0,0);
    uintptr_t load_result,surface_result,rect_result;
    int exact;
    if (native_semantics_enabled() || inflight!=0) return 0;
    memcpy(binding_snapshot_copy,bindings,sizeof(bindings));
    memcpy(active_snapshot_copy,active_bindings,sizeof(active_bindings));
    memcpy(root_snapshot,ordinary_root,sizeof(ordinary_root));
    memset(object,0,sizeof(object));
    real_load=native_test_load_passthrough;
    real_surface=native_test_surface_passthrough;
    real_rect=native_test_surface_passthrough;
    InterlockedExchange(&native_test_passthrough_calls,0);
    InterlockedIncrement(&photon_v6_pf_hook_inflight);
    load_result=photon_v6_pf_hook_load_impl(object,NULL,NULL);
    InterlockedIncrement(&photon_v6_pf_hook_inflight);
    surface_result=photon_v6_pf_hook_surface_impl(
        object+0x0C,NULL,NULL,0,0,NULL);
    InterlockedIncrement(&photon_v6_pf_hook_inflight);
    rect_result=photon_v6_pf_hook_rect_impl(
        object+0x0C,NULL,NULL,0,0,NULL);
    photon_v6_pf_decode_apply(NULL,0,0,0,0,0,0,0);
    real_load=saved_load; real_surface=saved_surface; real_rect=saved_rect;
    exact=load_result==UINT32_C(0x57B40001) &&
        surface_result==UINT32_C(0x57B40002) &&
        rect_result==UINT32_C(0x57B40002) &&
        InterlockedCompareExchange(&native_test_passthrough_calls,0,0)==3 &&
        InterlockedCompareExchange(&photon_v6_pf_hook_inflight,0,0)==inflight &&
        InterlockedCompareExchange(&telemetry_generation,0,0)==generation &&
        InterlockedCompareExchange(&exact_payload_loads,0,0)==loads &&
        InterlockedCompareExchange(&overlay_commits,0,0)==overlays &&
        InterlockedCompareExchange(&untargeted_decodes,0,0)==untargeted &&
        InterlockedCompareExchange(&rejected_decodes,0,0)==rejected &&
        InterlockedCompareExchange(&fatal_latch,0,0)==fatal &&
        memcmp(binding_snapshot_copy,bindings,sizeof(bindings))==0 &&
        memcmp(active_snapshot_copy,active_bindings,
            sizeof(active_bindings))==0 &&
        memcmp(root_snapshot,ordinary_root,sizeof(ordinary_root))==0;
    return exact;
}
#endif

#if PHOTON_NATIVE_SELECTOR_ENABLED && defined(PHOTON_V6_NATIVE_TEST_HOOKS)
int photon_v6_native_test_selector_decode(
    void *object, uint32_t payload_bytes, uint64_t payload_fnv1a64,
    const PhotonV6PfSelectorDecision *load_identity,
    uint8_t *bgra_surface, uint32_t width, uint32_t height,
    uint32_t decoder_flags,
    PhotonV6PfSelectorDecision *decoded_identity) {
    ObjectBinding binding;
    PhotonV6PfSelectorDecision surface_decision,decode_decision;
    uint64_t row_bytes = (uint64_t)width * 4U;
    uint32_t packed;
    int pushed,selector_scope;
    if (!object || !bgra_surface || !width || !height ||
        width > UINT16_MAX || height > UINT16_MAX ||
        row_bytes > INT32_MAX ||
        !InterlockedCompareExchange(&initialized, 0, 0)) return 0;
    memset(&surface_decision, 0, sizeof(surface_decision));
    memset(&decode_decision, 0, sizeof(decode_decision));
    bind_object(object, NULL, payload_bytes, payload_fnv1a64, 1,
        selector_decision_is_special(load_identity)?1U:0U,
        selector_decision_is_special(load_identity)?
            load_identity->payload_sha256:NULL,
        selector_decision_is_special(load_identity)?
            load_identity->special_source_asset_id:NULL,
        selector_decision_is_special(load_identity)?
            load_identity->special_context_identity_key:NULL);
    telemetry_increment(&exact_payload_loads);
    if (!find_binding(object, &binding)) return 0;
    pushed = push_active(&binding);
    selector_scope=photon_v6_pf_selector_adapter_surface_enter(
        object, &surface_decision)==1;
    (void)photon_v6_pf_selector_adapter_decode_query(&decode_decision);
    if (decoded_identity) *decoded_identity=decode_decision;
    packed = width | (height << 16);
    photon_v6_pf_decode_apply(
        NULL, (uint32_t)(uintptr_t)bgra_surface,
        (uint32_t)(-(int32_t)row_bytes), 0, packed, 0, packed,
        decoder_flags);
    if (pushed) pop_active();
    if (selector_scope)
        photon_v6_pf_selector_adapter_surface_leave(object);
    return 1;
}

int photon_v6_native_test_selector_decision_allows(
    const PhotonV6PfSelectorDecision *decision, void *object,
    uint32_t payload_bytes, uint64_t payload_fnv1a64,
    const uint8_t expected_payload_sha256[32],
    const char *expected_source_asset_id,
    const char *expected_context_identity_key, uint32_t special_tracked) {
    ObjectBinding binding;
    memset(&binding,0,sizeof(binding));
    binding.active=1;
    binding.object=object;
    binding.payload_bytes=payload_bytes;
    binding.payload_fnv1a64=payload_fnv1a64;
    binding.selector_special57_tracked=special_tracked?1U:0U;
    if (special_tracked && expected_payload_sha256)
        memcpy(binding.selector_payload_sha256,expected_payload_sha256,32);
    if (special_tracked) {
        binding.selector_special_source_asset_id =
            expected_source_asset_id;
        binding.selector_special_context_identity_key =
            expected_context_identity_key;
    }
    return selector_decision_allows_special(&binding,decision);
}

int photon_v6_native_test_selector_provider_exact(
    const PhotonV6PfSelectorDecision *decision) {
    return selector_translation_provider_exact(decision);
}

int photon_v6_native_test_selector_decision_same(
    const PhotonV6PfSelectorDecision *left,
    const PhotonV6PfSelectorDecision *right) {
    return selector_decision_same(left,right);
}

int photon_v6_native_test_selector_decision_is_special(
    const PhotonV6PfSelectorDecision *decision) {
    return selector_decision_is_special(decision);
}
#endif

#if PHOTON_NATIVE_SELECTOR_ENABLED
static int selector_restored_and_absent(
    PhotonV6PfSelectorStatus *status_output) {
    PhotonV6PfSelectorStatus status;
    memset(&status, 0, sizeof(status));
    status.struct_size = sizeof(status);
    photon_v6_pf_selector_adapter_query(&status);
    if (status_output) *status_output = status;
    return status.hooks_installed == 0 && status.hook_inflight == 0 &&
        status.hooks_restored_exact == 1 &&
        status.snapshot_consistent == 1;
}

static int selector_retained_and_disabled(
    PhotonV6PfSelectorStatus *status_output) {
    PhotonV6PfSelectorStatus status;
    memset(&status,0,sizeof(status));
    status.struct_size=sizeof(status);
    photon_v6_pf_selector_adapter_query(&status);
    if (status_output) *status_output=status;
    return status.no_hot_lifecycle==1 && status.module_pinned==1 &&
        status.hooks_retained_until_process_exit==1 &&
        status.semantic_gate_disabled==1 &&
        status.lifecycle_admission_revoked==1 && status.unload_safe==0 &&
        status.hooks_restored_exact==0;
}

static int selector_publish_invariants_exact(
    const PhotonV6PfSelectorStatus *status) {
    return status && status->struct_size==sizeof(*status) &&
        status->abi_version==PHOTON_V6_PF_SELECTOR_ADAPTER_ABI &&
        status->initialized==1 &&
        status->hooks_installed==PHOTON_NATIVE_SELECTOR_EXPECTED_HOOK_COUNT &&
        status->expected_hook_count==PHOTON_NATIVE_SELECTOR_EXPECTED_HOOK_COUNT &&
        status->hook_inflight==0 &&
        status->hooks_restored_exact==0 &&
        status->mutation_journal_entries==
            PHOTON_NATIVE_SELECTOR_EXPECTED_HOOK_COUNT &&
        status->restored_hook_count==0 &&
        status->snapshot_consistent==1 && !(status->status_generation&1U) &&
        status->fatal_latch==0 && status->semantic_gate_disabled==0 &&
        status->lifecycle_admission_revoked==0 &&
        status->translation_write_leases_active==0 &&
        status->ordinary_write_leases_active==0 &&
        status->special_write_leases_active==0 &&
        status->no_hot_lifecycle==1 && status->module_pinned==1 &&
        status->first_mutation_committed==1 &&
        status->hooks_retained_until_process_exit==1 && status->unload_safe==0;
}

static int selector_query_lifecycle_compatible(
    const PhotonV6PfSelectorStatus *first,
    const PhotonV6PfSelectorStatus *second) {
    return first && second &&
        first->struct_size==sizeof(*first) &&
        second->struct_size==sizeof(*second) &&
        first->abi_version==PHOTON_V6_PF_SELECTOR_ADAPTER_ABI &&
        second->abi_version==PHOTON_V6_PF_SELECTOR_ADAPTER_ABI &&
        first->snapshot_consistent==1 && second->snapshot_consistent==1 &&
        !(first->status_generation&1U) && !(second->status_generation&1U) &&
        first->initialized==second->initialized &&
        first->hooks_installed==second->hooks_installed &&
        first->hooks_restored_exact==second->hooks_restored_exact &&
        first->expected_hook_count==second->expected_hook_count &&
        first->mutation_journal_entries==
            second->mutation_journal_entries &&
        first->restored_hook_count==second->restored_hook_count &&
        first->fatal_latch==second->fatal_latch &&
        first->semantic_gate_disabled==second->semantic_gate_disabled &&
        first->lifecycle_admission_revoked==
            second->lifecycle_admission_revoked &&
        first->no_hot_lifecycle==second->no_hot_lifecycle &&
        first->module_pinned==second->module_pinned &&
        first->first_mutation_committed==
            second->first_mutation_committed &&
        first->hooks_retained_until_process_exit==
            second->hooks_retained_until_process_exit &&
        first->unload_safe==second->unload_safe;
}

static int selector_ready_for_native_publish(
    PhotonV6PfSelectorStatus *status_output) {
    PhotonV6PfSelectorStatus first,second;
    memset(&first,0,sizeof(first));
    memset(&second,0,sizeof(second));
    first.struct_size=sizeof(first);
    second.struct_size=sizeof(second);
    photon_v6_pf_selector_adapter_query(&first);
#if defined(PHOTON_V6_NATIVE_TEST_HOOKS)
    if (InterlockedExchange(
            &native_test_force_selector_benign_before_publish,0))
        photon_v6_pf_selector_test_emit_benign_telemetry();
    if (InterlockedExchange(
            &native_test_force_selector_fatal_before_publish,0))
        photon_v6_pf_selector_test_force_fatal();
#endif
    MemoryBarrier();
    photon_v6_pf_selector_adapter_query(&second);
    if (status_output) *status_output=second;
    return selector_publish_invariants_exact(&first) &&
        selector_publish_invariants_exact(&second);
}

static void selector_shutdown_if_active(void) {
#if defined(PHOTON_V6_NATIVE_TEST_HOOKS)
    if (InterlockedCompareExchange(
            &native_test_selector_lifecycle_bypass, 0, 0))
        return;
#endif
    photon_v6_pf_selector_adapter_shutdown();
}
#endif

int photon_v6_pf_native_runtime_init(const wchar_t *ordinary_bundle_root) {
    size_t length,index;
    InterlockedExchange(&native_init_stage, 1);
    InterlockedExchange(&native_init_detail, 0);
    InterlockedExchange(&selector_init_detail, 0);
    InterlockedExchange(&last_overlay_status, -1);
    InterlockedExchange(&last_overlay_route_gate_status, -1);
    InterlockedExchange(&last_overlay_sidecar_status, -1);
    InterlockedExchange(&last_overlay_transaction_status, -1);
    if (!ordinary_bundle_root || !ordinary_bundle_root[0]) {
        InterlockedExchange(&native_init_detail, -1); return -1;
    }
    if (native_no_hot_lifecycle_enabled() &&
        (InterlockedCompareExchange(
            &native_hooks_retained_until_process_exit,0,0) ||
         InterlockedCompareExchange(&native_first_mutation_committed,0,0) ||
         installed_hook_count()!=0 ||
         InterlockedCompareExchange(
            &native_mutation_journal_entries,0,0) ||
         InterlockedCompareExchange(&fatal_latch,0,0))) {
        InterlockedExchange(&native_init_detail, -1); return -1;
    }
    if (InterlockedCompareExchange(&initializing,1,0)!=0) {
        InterlockedExchange(&native_init_detail, -1); return -1;
    }
    if (InterlockedCompareExchange(&initialized,0,0) ||
        (native_no_hot_lifecycle_enabled() &&
        (InterlockedCompareExchange(
            &native_hooks_retained_until_process_exit,0,0) ||
         InterlockedCompareExchange(&native_first_mutation_committed,0,0) ||
         installed_hook_count()!=0 ||
         InterlockedCompareExchange(
             &native_mutation_journal_entries,0,0) ||
         InterlockedCompareExchange(&fatal_latch,0,0)))) {
        InterlockedExchange(&initializing,0);
        InterlockedExchange(&native_init_detail, -1);
        return -1;
    }
    length = wcslen(ordinary_bundle_root);
    if (length >= sizeof(ordinary_root) / sizeof(ordinary_root[0])) {
        InterlockedExchange(&initializing,0);
        InterlockedExchange(&native_init_detail, -2); return -2;
    }
    memcpy(ordinary_root, ordinary_bundle_root,
           (length + 1) * sizeof(wchar_t));
    InterlockedExchange(&native_init_stage, 2);
#ifdef PHOTON_V6_NATIVE_TEST_HOOKS
    main_base = native_test_main_base
        ? native_test_main_base : (BYTE *)GetModuleHandleW(NULL);
#else
    main_base = (BYTE *)GetModuleHandleW(NULL);
#endif
    if (!main_base || !verify_image()) {
        InterlockedExchange(&initializing,0);
        InterlockedExchange(&native_init_detail, -3); return -3;
    }
    InterlockedExchange(&native_init_stage, 3);
    InterlockedExchange(&shutting_down, 0);
    InterlockedExchange(&native_semantic_gate_disabled,0);
    InterlockedExchange(&native_first_mutation_committed,0);
    InterlockedExchange(&native_mutation_journal_entries,0);
    InterlockedExchange(&binding_write_cursor,0);
    for (index=0;index<sizeof(pointer_hooks)/sizeof(pointer_hooks[0]);++index)
        InterlockedExchange(&pointer_hooks[index].journaled,0);
    InterlockedExchange(&decode_hook.journaled,0);
#if PHOTON_NATIVE_HAS_CR6_ALT_EXACT_OVERLAY
    for (index = 0; index < 2; ++index)
        InterlockedExchange(&alt_decode_hooks[index].journaled, 0);
#endif
#if PHOTON_NATIVE_HAS_CRIP008_EXACT_OVERLAY
    InterlockedExchange(&crip008_decode_hook.journaled,0);
#endif
#if PHOTON_NATIVE_HAS_CRIP008_DIRECT_EXACT_OVERLAY
    for (index = 0; index < 2; ++index)
        InterlockedExchange(&crip008_direct_decode_hooks[index].journaled,0);
#endif
    telemetry_reset();
#if PHOTON_NATIVE_SELECTOR_ENABLED && defined(PHOTON_V6_NATIVE_TEST_HOOKS)
    InterlockedExchange(&native_test_ordinary_gate_attempts,0);
#endif
    memset(bindings, 0, sizeof(bindings));
    memset(active_bindings, 0, sizeof(active_bindings));
    InitializeCriticalSection(&state_lock);
    InterlockedExchange(&lock_ready, 1);
    if (!prepare_hooks()) {
        telemetry_set_restored_exact();
        DeleteCriticalSection(&state_lock);
        InterlockedExchange(&lock_ready, 0);
        InterlockedExchange(&initializing,0);
        InterlockedExchange(&native_init_detail, -4);
        return -4;
    }
    InterlockedExchange(&native_init_stage, 4);
    real_load = (LoadFn)pointer_hooks[0].original;
    real_surface = (SurfaceFn)pointer_hooks[1].original;
    real_rect = (SurfaceFn)pointer_hooks[2].original;
    photon_v6_pf_real_decode_raw = main_base + PF_CR6_DECODE_RVA;
#if PHOTON_NATIVE_HAS_CR6_ALT_EXACT_OVERLAY
    photon_v6_pf_real_alt_decode_raw =
        main_base + PF_CR6_ALT_DECODE_RVA;
#endif
#if PHOTON_NATIVE_HAS_CRIP008_EXACT_OVERLAY
    photon_v6_pf_real_crip008_decode_raw =
        main_base + PHOTON_NATIVE_CRIP008_DECODE_RVA;
#endif
#if PHOTON_NATIVE_HAS_CRIP008_DIRECT_EXACT_OVERLAY
    photon_v6_pf_real_crip008_direct_decode_raw =
        main_base + PHOTON_NATIVE_CRIP008_DIRECT_DECODE_RVA;
#endif
#if PHOTON_NATIVE_SELECTOR_ENABLED
#if defined(PHOTON_V6_NATIVE_TEST_HOOKS)
    if (InterlockedCompareExchange(
            &native_test_selector_lifecycle_bypass, 0, 0)) {
        photon_v6_pf_selector_test_reset();
    } else
#endif
    {
        int selector_result = photon_v6_pf_selector_adapter_init(main_base);
        InterlockedExchange(&selector_init_detail, selector_result);
        if (selector_result != 0) {
        selector_shutdown_if_active();
        if (selector_restored_and_absent(NULL)) {
            telemetry_set_restored_exact();
            DeleteCriticalSection(&state_lock);
            InterlockedExchange(&lock_ready, 0);
        } else if (native_no_hot_lifecycle_enabled() &&
            selector_retained_and_disabled(NULL)) {
            native_enter_no_hot_retained_state(1);
        } else {
            telemetry_set_fatal();
        }
        InterlockedExchange(&initializing,0);
        InterlockedExchange(&native_init_detail, -6);
        return -6;
        }
    }
    InterlockedExchange(&native_init_stage, 5);
#endif
    if (native_no_hot_lifecycle_enabled()) pin_native_module_or_failfast();
    if (!install_all()) {
        if (native_no_hot_lifecycle_enabled() &&
            (InterlockedCompareExchange(
                &native_first_mutation_committed,0,0) ||
             installed_hook_count()!=0)) {
            InterlockedExchange(&native_semantic_gate_disabled,1);
            InterlockedExchange(&shutting_down,1);
        }
        #if PHOTON_NATIVE_SELECTOR_ENABLED
        selector_shutdown_if_active();
        #endif
        if (native_no_hot_lifecycle_enabled() &&
            (InterlockedCompareExchange(
                &native_first_mutation_committed,0,0) ||
             installed_hook_count()!=0 ||
             InterlockedCompareExchange(
                &native_mutation_journal_entries,0,0)
#if PHOTON_NATIVE_SELECTOR_ENABLED
             || selector_retained_and_disabled(NULL)
#endif
             )) {
            native_enter_no_hot_retained_state(1);
            InterlockedExchange(&initializing,0);
            InterlockedExchange(&native_init_detail, -5);
            return -5;
        }
        if (!installed_hook_count()
#if PHOTON_NATIVE_SELECTOR_ENABLED
            && selector_restored_and_absent(NULL)
#endif
            ) {
            telemetry_set_restored_exact();
            DeleteCriticalSection(&state_lock);
            InterlockedExchange(&lock_ready, 0);
        }
        InterlockedExchange(&initializing,0);
        InterlockedExchange(&native_init_detail, -5);
        return -5;
    }
    if (installed_hook_count()!=PHOTON_NATIVE_EXPECTED_HOOK_COUNT ||
        InterlockedCompareExchange(&native_mutation_journal_entries,0,0)!=
            (LONG)PHOTON_NATIVE_EXPECTED_HOOK_COUNT ||
        InterlockedCompareExchange(&fatal_latch,0,0)) {
        if (native_no_hot_lifecycle_enabled()) {
#if PHOTON_NATIVE_SELECTOR_ENABLED
            selector_shutdown_if_active();
#endif
            native_enter_no_hot_retained_state(1);
        } else telemetry_set_fatal();
        InterlockedExchange(&initializing,0);
        InterlockedExchange(&native_init_detail, -5);
        return -5;
    }
    InterlockedExchange(&native_init_stage, 6);
#if PHOTON_NATIVE_SELECTOR_ENABLED
#if defined(PHOTON_V6_NATIVE_TEST_HOOKS)
    if (!InterlockedCompareExchange(
            &native_test_selector_lifecycle_bypass,0,0)) {
#endif
        if (!selector_ready_for_native_publish(NULL)) {
            selector_shutdown_if_active();
            native_enter_no_hot_retained_state(1);
            InterlockedExchange(&initializing,0);
            InterlockedExchange(&native_init_detail, -7);
            return -7;
        }
#if defined(PHOTON_V6_NATIVE_TEST_HOOKS)
    }
#endif
#endif
    MemoryBarrier();
    InterlockedExchange(&initialized,1);
    InterlockedExchange(&initializing,0);
    InterlockedExchange(&native_init_stage, 7);
    InterlockedExchange(&native_init_detail, 0);
    return 0;
}

void photon_v6_pf_native_runtime_shutdown(void) {
#ifdef PHOTON_V6_NATIVE_TEST_HOOKS
    int retry;
    int native_restored = 0;
#else
    int retry;
#endif
    if (!InterlockedCompareExchange(&initialized, 0, 0) &&
        !InterlockedCompareExchange(
            &native_hooks_retained_until_process_exit,0,0) &&
        installed_hook_count()==0) return;
    if (native_no_hot_lifecycle_enabled() &&
        (InterlockedCompareExchange(&native_first_mutation_committed,0,0) ||
         InterlockedCompareExchange(
            &native_hooks_retained_until_process_exit,0,0) ||
         installed_hook_count()!=0 ||
         InterlockedCompareExchange(
            &native_mutation_journal_entries,0,0))) {
        InterlockedExchange(&native_semantic_gate_disabled,1);
        InterlockedExchange(&shutting_down,1);
#if PHOTON_NATIVE_SELECTOR_ENABLED
        selector_shutdown_if_active();
#endif
        native_enter_no_hot_retained_state(0);
        for (retry=0;retry<RESTORE_RETRIES*25;++retry) {
            if (InterlockedCompareExchange(
                    &photon_v6_pf_hook_inflight,0,0)==0) break;
            Sleep(1);
        }
        /* A late entrant is safe because bytes/trampolines/module remain
         * pinned; a nonzero census is diagnostic, never unload authority. */
        return;
    }
#ifndef PHOTON_V6_NATIVE_TEST_HOOKS
    /* A successful production install always commits at least one mutation;
     * reaching a non-retained shutdown path is lifecycle corruption. */
    native_lifecycle_ambiguity_failfast();
    return;
#else
    InterlockedExchange(&shutting_down, 1);
    for (retry = 0; retry < RESTORE_RETRIES; ++retry) {
        if (InterlockedCompareExchange(&photon_v6_pf_hook_inflight, 0, 0) == 0 &&
            restore_all_once()) {
            native_restored = 1; break;
        }
        Sleep(25);
    }
#if PHOTON_NATIVE_SELECTOR_ENABLED
    if (native_restored) {
        selector_shutdown_if_active();
        if (selector_restored_and_absent(NULL))
            telemetry_set_restored_exact();
        else
            telemetry_set_fatal();
    }
#else
    if (native_restored) telemetry_set_restored_exact();
#endif
    if (InterlockedCompareExchange(&restored_exact, 0, 0))
    {
        if (InterlockedExchange(&lock_ready, 0))
            DeleteCriticalSection(&state_lock);
        InterlockedExchange(&initialized, 0);
    }
#endif
}

void photon_v6_pf_native_runtime_query(PhotonV6PfNativeStatus *status) {
    LONG before = 0, after = 0;
    unsigned attempt;
#if PHOTON_NATIVE_SELECTOR_ENABLED
    PhotonV6PfSelectorStatus selector_status;
    PhotonV6PfSelectorStatus selector_status_after;
#endif
    if (!status) return;
    memset(status, 0, sizeof(*status));
    status->struct_size = sizeof(*status);
    status->native_initialized=(uint32_t)
        InterlockedCompareExchange(&initialized,0,0);
    status->native_initializing=(uint32_t)
        InterlockedCompareExchange(&initializing,0,0);
    status->native_shutting_down=(uint32_t)
        InterlockedCompareExchange(&shutting_down,0,0);
    status->native_expected_hook_count=PHOTON_NATIVE_EXPECTED_HOOK_COUNT;
    status->native_hooks_installed=installed_hook_count();
    status->native_init_detail=(int32_t)
        InterlockedCompareExchange(&native_init_detail,0,0);
    status->native_init_stage=(int32_t)
        InterlockedCompareExchange(&native_init_stage,0,0);
    status->selector_init_detail=(int32_t)
        InterlockedCompareExchange(&selector_init_detail,0,0);
    status->last_overlay_status=(int32_t)
        InterlockedCompareExchange(&last_overlay_status,0,0);
    status->last_overlay_route_gate_status=(int32_t)
        InterlockedCompareExchange(&last_overlay_route_gate_status,0,0);
    status->last_overlay_sidecar_status=(int32_t)
        InterlockedCompareExchange(&last_overlay_sidecar_status,0,0);
    status->last_overlay_transaction_status=(int32_t)
        InterlockedCompareExchange(&last_overlay_transaction_status,0,0);
    status->hooks_installed = status->native_hooks_installed;
    status->hook_inflight =
        (uint32_t)InterlockedCompareExchange(&photon_v6_pf_hook_inflight, 0, 0);
#if PHOTON_NATIVE_SELECTOR_ENABLED
    memset(&selector_status, 0, sizeof(selector_status));
    memset(&selector_status_after, 0, sizeof(selector_status_after));
    selector_status.struct_size = sizeof(selector_status);
    photon_v6_pf_selector_adapter_query(&selector_status);
#if defined(PHOTON_V6_NATIVE_TEST_HOOKS)
    switch (InterlockedExchange(&native_test_selector_query_drift,0)) {
        case 1: photon_v6_pf_selector_test_emit_benign_telemetry(); break;
        case 2: photon_v6_pf_selector_test_force_fatal(); break;
        case 3: photon_v6_pf_selector_adapter_shutdown(); break;
        default: break;
    }
#endif
    status->selector_abi_version = selector_status.abi_version;
    status->selector_initialized = selector_status.initialized;
    status->selector_hooks_installed = selector_status.hooks_installed;
    status->selector_hook_inflight = selector_status.hook_inflight;
    status->selector_hooks_restored_exact =
        selector_status.hooks_restored_exact;
    status->selector_snapshot_consistent = selector_status.snapshot_consistent;
    status->selector_status_generation = selector_status.status_generation;
    status->selector_language_state = selector_status.language_state;
    status->selector_language_state_sequence =
        selector_status.language_state_sequence;
    status->selector_language_state_known = selector_status.language_state_known;
    status->selector_language_bootstrap_exact_events =
        selector_status.language_bootstrap_exact_events;
    status->selector_language_bootstrap_conflict_rejects =
        selector_status.language_bootstrap_conflict_rejects;
    status->selector_language_setter_exact_events =
        selector_status.language_setter_exact_events;
    status->selector_language_graph_discovery_successes =
        selector_status.graph_begin_events;
    status->selector_language_graph_discovery_rejects =
        selector_status.surface_identity_rejects;
    status->selector_cref_identity_events = selector_status.cref_identity_events;
    status->selector_vm_execute_identity_events =
        selector_status.materializer_entry_events;
    status->selector_exact_load_bindings =
        selector_status.materializer_fresh_commits;
    status->selector_cached_surface_bindings =
        selector_status.materializer_cached_commits;
    status->selector_translation_special57_allows =
        selector_status.translation_special57_allows;
    status->selector_japanese_translation_endpoint_rejects =
        selector_status.state0_translation_endpoint_rejects;
    status->selector_causal_identity_rejects =
        selector_status.decode_identity_rejects;
    status->selector_c07_alias_rejects =
        selector_status.c07_all_provider_rejects;
    status->selector_exact_surface_entries =
        selector_status.exact_surface_entries;
    status->selector_exact_decode_queries =
        selector_status.exact_decode_queries;
    status->selector_fatal_latch = selector_status.fatal_latch;
    status->selector_expected_hook_count =
        selector_status.expected_hook_count;
    status->selector_mutation_journal_entries =
        selector_status.mutation_journal_entries;
    status->selector_restored_hook_count =
        selector_status.restored_hook_count;
    status->selector_global_language_generation_purges =
        selector_status.global_language_generation_purges;
    status->selector_graph_begin_events = selector_status.graph_begin_events;
    status->selector_graph_end_events = selector_status.graph_end_events;
    status->selector_graph_supersession_purges =
        selector_status.graph_supersession_purges;
    status->selector_graph_identity_rejects =
        selector_status.graph_identity_rejects;
    status->selector_cref_identity_rejects =
        selector_status.cref_identity_rejects;
    status->selector_materializer_entry_events =
        selector_status.materializer_entry_events;
    status->selector_materializer_load_candidates =
        selector_status.materializer_load_candidates;
    status->selector_materializer_fresh_commits =
        selector_status.materializer_fresh_commits;
    status->selector_materializer_cached_commits =
        selector_status.materializer_cached_commits;
    status->selector_materializer_identity_rejects =
        selector_status.materializer_identity_rejects;
    status->selector_payload_sha256_rejects =
        selector_status.payload_sha256_rejects;
    status->selector_state0_translation_endpoint_rejects =
        selector_status.state0_translation_endpoint_rejects;
    status->selector_c07_all_provider_rejects =
        selector_status.c07_all_provider_rejects;
    status->selector_surface_identity_rejects =
        selector_status.surface_identity_rejects;
    status->selector_decode_identity_rejects =
        selector_status.decode_identity_rejects;
    status->selector_stale_generation_rejects =
        selector_status.stale_generation_rejects;
    status->selector_cross_thread_rejects =
        selector_status.cross_thread_rejects;
    status->selector_translation_write_leases_active =
        selector_status.translation_write_leases_active;
    status->selector_ordinary_write_leases_active =
        selector_status.ordinary_write_leases_active;
    status->selector_special_write_leases_active =
        selector_status.special_write_leases_active;
    status->selector_ordinary_lease_acquires =
        selector_status.ordinary_lease_acquires;
    status->selector_ordinary_lease_rejects =
        selector_status.ordinary_lease_rejects;
    status->selector_ordinary_lease_releases =
        selector_status.ordinary_lease_releases;
    status->selector_ordinary_lease_generation_rejects =
        selector_status.ordinary_lease_generation_rejects;
    status->selector_no_hot_lifecycle=selector_status.no_hot_lifecycle;
    status->selector_module_pinned=selector_status.module_pinned;
    status->selector_first_mutation_committed=
        selector_status.first_mutation_committed;
    status->selector_hooks_retained_until_process_exit=
        selector_status.hooks_retained_until_process_exit;
    status->selector_semantic_gate_disabled=
        selector_status.semantic_gate_disabled;
    status->selector_lifecycle_admission_revoked=
        selector_status.lifecycle_admission_revoked;
    status->selector_unload_safe=selector_status.unload_safe;
    status->hooks_installed += selector_status.hooks_installed;
    status->hook_inflight += selector_status.hook_inflight;
#endif
    for (attempt = 0; attempt < 128; ++attempt) {
        before = InterlockedCompareExchange(&telemetry_generation, 0, 0);
        if (before & 1) { after = before; continue; }
        status->exact_payload_loads =
            (uint32_t)InterlockedCompareExchange(&exact_payload_loads, 0, 0);
        status->overlay_commits =
            (uint32_t)InterlockedCompareExchange(&overlay_commits, 0, 0);
        status->untargeted_decodes =
            (uint32_t)InterlockedCompareExchange(&untargeted_decodes, 0, 0);
        status->rejected_decodes =
            (uint32_t)InterlockedCompareExchange(&rejected_decodes, 0, 0);
        status->fatal_latch =
            (uint32_t)InterlockedCompareExchange(&fatal_latch, 0, 0);
        status->hooks_restored_exact =
            (uint32_t)InterlockedCompareExchange(&restored_exact, 0, 0);
        after = InterlockedCompareExchange(&telemetry_generation, 0, 0);
        if (before == after && !(after & 1)) {
            status->snapshot_consistent = 1;
            break;
        }
    }
    status->status_generation = (uint32_t)after;
    status->no_hot_lifecycle=native_no_hot_lifecycle_enabled()?1U:0U;
    status->module_pinned=(uint32_t)
        InterlockedCompareExchange(&native_module_pinned,0,0);
    status->first_mutation_committed=(uint32_t)
        InterlockedCompareExchange(&native_first_mutation_committed,0,0);
    status->hooks_retained_until_process_exit=(uint32_t)
        InterlockedCompareExchange(
            &native_hooks_retained_until_process_exit,0,0);
    status->semantic_gate_disabled=(uint32_t)
        InterlockedCompareExchange(&native_semantic_gate_disabled,0,0);
    status->mutation_journal_entries=(uint32_t)
        InterlockedCompareExchange(&native_mutation_journal_entries,0,0);
#if PHOTON_NATIVE_SELECTOR_ENABLED
    selector_status_after.struct_size = sizeof(selector_status_after);
    photon_v6_pf_selector_adapter_query(&selector_status_after);
    status->selector_snapshot_consistent =
        selector_query_lifecycle_compatible(
            &selector_status,&selector_status_after);
    status->snapshot_consistent = status->snapshot_consistent &&
        status->selector_snapshot_consistent;
    status->hooks_restored_exact = status->hooks_restored_exact &&
        selector_status.hooks_restored_exact &&
        selector_status_after.hooks_restored_exact;
    status->fatal_latch = status->fatal_latch || selector_status.fatal_latch ||
        selector_status_after.fatal_latch;
#endif
    status->unload_safe=status->hooks_installed==0 &&
        status->hook_inflight==0 && status->hooks_restored_exact==1 &&
        !status->hooks_retained_until_process_exit
#if PHOTON_NATIVE_SELECTOR_ENABLED
        && status->selector_unload_safe==1
#endif
        ;
    status->result = status->fatal_latch ? -1 : 0;
}
