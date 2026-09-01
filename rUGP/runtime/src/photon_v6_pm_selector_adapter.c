#ifndef _WIN32_WINNT
#define _WIN32_WINNT 0x0601
#endif
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <tlhelp32.h>
#include <wincrypt.h>

#include <stdint.h>
#include <string.h>

#include "photon_v6_pf_selector_adapter.h"
#include "photon_v6_pm_special40_table.generated.h"

#if !defined(PHOTON_V6_PRODUCTION_PM)
#error photon_v6_pm_selector_adapter requires PHOTON_V6_PRODUCTION_PM
#endif
#if !defined(PHOTON_V6_PM_SELECTOR_ADAPTER)
#error photon_v6_pm_selector_adapter requires PHOTON_V6_PM_SELECTOR_ADAPTER
#endif
#if !defined(__i386__) && !defined(_M_IX86)
#error photon_v6_pm_selector_adapter must use the 32-bit Windows ABI
#endif

/*
 * PM selector adapter v1.
 *
 * PM's exact CInt image-language setter is instruction-for-instruction
 * equivalent to PF's authenticated setter path.  This adapter hooks only that
 * setter and binds the 39 Cr6Ti exceptional endpoints by complete physical
 * identity (length + FNV-1a + SHA-256).  State 0 is Japanese official and can
 * never authorize a sidecar; state 1 is Translation.  Unknown state, a torn
 * transition, a stale object generation, or any identity disagreement fails
 * closed.  The remaining CRip008 endpoint has a distinct ABI and is not
 * claimed by this module.
 */

enum {
    PM_TIMESTAMP = 0x5D319898,
    PM_SIZE_OF_IMAGE = 0x00386000,
    PM_TYPED_SETTER_CALLSITE_RVA = 0x000C5A93,
    PM_CINT_SETTER_RVA = 0x001E4710,
    PM_CVM_FLAG_OP_VTABLE_RVA = 0x00230D30,
    PM_CVM_FLAG_OP_EXEC_RVA = 0x000C50D0,
    PM_CINT_VTABLE_RVA = 0x002424E0,
    PM_CR6TI_PRIMARY_VTABLE_RVA = 0x0023C320,
    PM_CR6TI_SECONDARY_VTABLE_RVA = 0x0023C2E4,
    PM_MAX_OBJECT_BINDINGS = 256,
    PM_MAX_ACTIVE_SURFACES = 128,
    PM_MAX_ORDINARY_LEASES = 64,
    PM_MAX_SUSPENDED_THREADS = 512,
    PM_MAX_PAYLOAD_BYTES = 128U * 1024U * 1024U,
    PM_TRANSITION_DRAIN_RETRIES = 10000,
    PM_EXPECTED_HOOK_COUNT = 1
};

typedef uintptr_t (__attribute__((thiscall)) *CIntSetterFn)(
    void *self, uint32_t value);

typedef struct PmObjectBinding {
    void *object;
    const BYTE *payload;
    uint32_t payload_bytes;
    uint64_t payload_fnv1a64;
    BYTE payload_sha256[32];
    uint32_t target_index;
    LONG language_generation;
    LONG object_generation;
    int active;
} PmObjectBinding;

typedef struct PmActiveSurface {
    DWORD tid;
    LONG sequence;
    LONG decode_queries;
    LONG special_lease;
    PmObjectBinding binding;
    int active;
} PmActiveSurface;

typedef struct PmOrdinaryLease {
    DWORD tid;
    LONG token;
    LONG language_generation;
    int active;
} PmOrdinaryLease;

typedef struct PmCallHook {
    BYTE *site;
    BYTE original[5];
    BYTE replacement[5];
    DWORD original_protect;
    LONG installed;
    LONG journaled;
} PmCallHook;

typedef struct PmSuspendedThread {
    HANDLE handle;
    DWORD eip;
} PmSuspendedThread;

static BYTE *main_base;
static CIntSetterFn real_cint_setter;
static PmCallHook setter_hook;
static SRWLOCK state_lock = SRWLOCK_INIT;
static SRWLOCK telemetry_lock = SRWLOCK_INIT;
static PmObjectBinding object_bindings[PM_MAX_OBJECT_BINDINGS];
static PmActiveSurface active_surfaces[PM_MAX_ACTIVE_SURFACES];
static PmOrdinaryLease ordinary_leases[PM_MAX_ORDINARY_LEASES];

static volatile LONG initialized;
static volatile LONG initializing;
static volatile LONG shutting_down;
static volatile LONG hook_inflight;
static volatile LONG fatal_latch;
static volatile LONG telemetry_generation;
static volatile LONG language_state = PHOTON_V6_PF_SELECTOR_LANGUAGE_UNKNOWN;
static volatile LONG language_state_sequence;
static volatile LONG language_transition_inflight;
static volatile LONG language_transition_owner_tid;
static volatile LONG lifecycle_admission_revoked;
static volatile LONG translation_write_leases;
static volatile LONG ordinary_write_lease_count;
static volatile LONG special_write_lease_count;
static volatile LONG ordinary_lease_sequence;
static volatile LONG object_generation_sequence;
static volatile LONG surface_sequence;
static volatile LONG binding_write_cursor;
static volatile LONG module_pinned;
static volatile LONG first_mutation_committed;
static volatile LONG hooks_retained_until_process_exit;
static volatile LONG semantic_gate_disabled;
static volatile LONG mutation_journal_entries;
static void *volatile language_cint_this;
static void *volatile language_cint_owner;

#define PM_COUNTER(name) static volatile LONG name
PM_COUNTER(language_bootstrap_exact_events);
PM_COUNTER(language_bootstrap_conflict_rejects);
PM_COUNTER(language_setter_exact_events);
PM_COUNTER(global_language_generation_purges);
PM_COUNTER(payload_sha256_rejects);
PM_COUNTER(state0_translation_endpoint_rejects);
PM_COUNTER(exact_surface_entries);
PM_COUNTER(surface_identity_rejects);
PM_COUNTER(exact_decode_queries);
PM_COUNTER(decode_identity_rejects);
PM_COUNTER(translation_special57_allows);
PM_COUNTER(stale_generation_rejects);
PM_COUNTER(cross_thread_rejects);
PM_COUNTER(ordinary_lease_acquires);
PM_COUNTER(ordinary_lease_rejects);
PM_COUNTER(ordinary_lease_releases);
PM_COUNTER(ordinary_lease_generation_rejects);

static void telemetry_begin(void) {
    AcquireSRWLockExclusive(&telemetry_lock);
    InterlockedIncrement(&telemetry_generation);
}

static void telemetry_end(void) {
    InterlockedIncrement(&telemetry_generation);
    ReleaseSRWLockExclusive(&telemetry_lock);
}

static void telemetry_increment(volatile LONG *counter) {
    telemetry_begin();
    InterlockedIncrement(counter);
    telemetry_end();
}

static void set_fatal(void) {
    telemetry_begin();
    InterlockedExchange(&fatal_latch, 1);
    telemetry_end();
}

static int range_readable(const void *pointer, SIZE_T count) {
    uintptr_t at = (uintptr_t)pointer;
    uintptr_t end = at + count;
    if (!pointer || !count || end < at) return 0;
    while (at < end) {
        MEMORY_BASIC_INFORMATION info;
        uintptr_t next;
        if (!VirtualQuery((const void *)at, &info, sizeof(info)) ||
            info.State != MEM_COMMIT ||
            (info.Protect & (PAGE_NOACCESS | PAGE_GUARD))) return 0;
        next = (uintptr_t)info.BaseAddress + info.RegionSize;
        if (next <= at) return 0;
        at = next < end ? next : end;
    }
    return 1;
}

static uint32_t safe_u32(const void *base, SIZE_T offset) {
    const BYTE *at = (const BYTE *)base + offset;
    return range_readable(at, 4) ? *(const uint32_t *)at : UINT32_MAX;
}

static uint16_t safe_u16(const void *base, SIZE_T offset) {
    const BYTE *at = (const BYTE *)base + offset;
    return range_readable(at, 2) ? *(const uint16_t *)at : UINT16_MAX;
}

static uintptr_t safe_pointer(const void *base, SIZE_T offset) {
    const BYTE *at = (const BYTE *)base + offset;
    return range_readable(at, sizeof(void *)) ?
        (uintptr_t)*(void *const *)at : 0;
}

static DWORD main_rva(uintptr_t value) {
    uintptr_t base = (uintptr_t)main_base;
    return value >= base && value < base + PM_SIZE_OF_IMAGE ?
        (DWORD)(value - base) : UINT32_MAX;
}

static uint64_t fnv1a64(const BYTE *data, uint32_t bytes) {
    uint64_t hash = UINT64_C(14695981039346656037);
    uint32_t index;
    for (index = 0; index < bytes; ++index) {
        hash ^= data[index];
        hash *= UINT64_C(1099511628211);
    }
    return hash;
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

static int verify_image(BYTE *base) {
    IMAGE_DOS_HEADER *dos;
    IMAGE_NT_HEADERS32 *nt;
    DWORD loaded_image_base;
    if (!base || !range_readable(base, sizeof(IMAGE_DOS_HEADER))) return 0;
    dos = (IMAGE_DOS_HEADER *)base;
    if (dos->e_magic != IMAGE_DOS_SIGNATURE || dos->e_lfanew <= 0 ||
        !range_readable(base + dos->e_lfanew, sizeof(IMAGE_NT_HEADERS32)))
        return 0;
    nt = (IMAGE_NT_HEADERS32 *)(base + dos->e_lfanew);
    loaded_image_base = nt->OptionalHeader.ImageBase;
    return nt->Signature == IMAGE_NT_SIGNATURE &&
        nt->FileHeader.Machine == IMAGE_FILE_MACHINE_I386 &&
        nt->FileHeader.TimeDateStamp == PM_TIMESTAMP &&
        nt->OptionalHeader.Magic == IMAGE_NT_OPTIONAL_HDR32_MAGIC &&
        nt->OptionalHeader.SizeOfImage == PM_SIZE_OF_IMAGE &&
        (loaded_image_base == UINT32_C(0x00400000) ||
         loaded_image_base == (DWORD)(uintptr_t)base);
}

static int cr6_object_exact(void *object) {
    return object && main_base && range_readable(object, 0x60) &&
        safe_pointer(object, 0) ==
            (uintptr_t)(main_base + PM_CR6TI_PRIMARY_VTABLE_RVA) &&
        safe_pointer(object, 0x0C) ==
            (uintptr_t)(main_base + PM_CR6TI_SECONDARY_VTABLE_RVA);
}

static int target_weak(uint32_t bytes, uint64_t hash) {
    size_t index;
    for (index = 0; index < PHOTON_V6_PM_SPECIAL_CR6_TARGET_COUNT; ++index)
        if (photon_v6_pm_special_cr6_targets[index].payload_bytes == bytes &&
            photon_v6_pm_special_cr6_targets[index].payload_fnv1a64 == hash)
            return (int)index;
    return -1;
}

static int target_exact(uint32_t bytes, uint64_t hash,
                        const BYTE digest[32]) {
    int index = target_weak(bytes, hash);
    return index >= 0 && memcmp(
        photon_v6_pm_special_cr6_targets[index].payload_sha256,
        digest, 32) == 0 ? index : -1;
}

static int selector_semantics_enabled(void) {
    return InterlockedCompareExchange(&initialized, 0, 0) != 0 &&
        !InterlockedCompareExchange(&shutting_down, 0, 0) &&
        !InterlockedCompareExchange(&fatal_latch, 0, 0) &&
        !InterlockedCompareExchange(&semantic_gate_disabled, 0, 0) &&
        !InterlockedCompareExchange(&lifecycle_admission_revoked, 0, 0);
}

static int exact_action_stack(void) {
    static const DWORD expected[] = {
        0x000C5A98, 0x00042F72, 0x00042249, 0x00122F38, 0x0012D377
    };
    void *frames[32];
    USHORT count = CaptureStackBackTrace(1, 32, frames, NULL);
    size_t found = 0, index;
    for (index = 0; index < count && found < ARRAYSIZE(expected); ++index)
        if (main_rva((uintptr_t)frames[index]) == expected[found]) ++found;
    return found == ARRAYSIZE(expected);
}

static int exact_bootstrap_stack(void) {
    static const DWORD expected[] = {
        0x000C5A98, 0x00042F72, 0x0003F4A4, 0x0003F0B6, 0x00007C03
    };
    void *frames[32];
    USHORT count = CaptureStackBackTrace(1, 32, frames, NULL);
    size_t found = 0, index;
    for (index = 0; index < count && found < ARRAYSIZE(expected); ++index)
        if (main_rva((uintptr_t)frames[index]) == expected[found]) ++found;
    return found == ARRAYSIZE(expected);
}

static void clear_runtime_identity_locked(void) {
    memset(object_bindings, 0, sizeof(object_bindings));
    memset(active_surfaces, 0, sizeof(active_surfaces));
    InterlockedIncrement(&global_language_generation_purges);
}

static int active_surface_count_locked(void) {
    size_t index;
    int count = 0;
    for (index = 0; index < PM_MAX_ACTIVE_SURFACES; ++index)
        if (active_surfaces[index].active) ++count;
    return count;
}

static int current_thread_owns_lease_locked(void) {
    DWORD tid = GetCurrentThreadId();
    size_t index;
    for (index = 0; index < PM_MAX_ACTIVE_SURFACES; ++index)
        if (active_surfaces[index].active &&
            active_surfaces[index].tid == tid &&
            active_surfaces[index].special_lease) return 1;
    for (index = 0; index < PM_MAX_ORDINARY_LEASES; ++index)
        if (ordinary_leases[index].active && ordinary_leases[index].tid == tid)
            return 1;
    return 0;
}

static int lease_census_exact_locked(void) {
    LONG ordinary = 0, special = 0;
    size_t index;
    for (index = 0; index < PM_MAX_ACTIVE_SURFACES; ++index)
        if (active_surfaces[index].active &&
            active_surfaces[index].special_lease) ++special;
    for (index = 0; index < PM_MAX_ORDINARY_LEASES; ++index)
        if (ordinary_leases[index].active) ++ordinary;
    return ordinary == InterlockedCompareExchange(
               &ordinary_write_lease_count, 0, 0) &&
        special == InterlockedCompareExchange(
               &special_write_lease_count, 0, 0) &&
        ordinary + special == InterlockedCompareExchange(
               &translation_write_leases, 0, 0);
}

static int begin_language_transition(LONG expected_previous, int bootstrap) {
    DWORD tid = GetCurrentThreadId();
    int claimed = 0, retry;
    AcquireSRWLockExclusive(&state_lock);
    if (!InterlockedCompareExchange(&lifecycle_admission_revoked, 0, 0) &&
        InterlockedCompareExchange(&language_transition_inflight, 1, 0) == 0 &&
        !current_thread_owns_lease_locked()) {
        InterlockedExchange(&language_transition_owner_tid, (LONG)tid);
        claimed = 1;
    }
    ReleaseSRWLockExclusive(&state_lock);
    if (!claimed) return 0;
    for (retry = 0; retry < PM_TRANSITION_DRAIN_RETRIES; ++retry) {
        int ready;
        AcquireSRWLockExclusive(&state_lock);
        ready = lease_census_exact_locked() &&
            InterlockedCompareExchange(&translation_write_leases, 0, 0) == 0 &&
            active_surface_count_locked() == 0 &&
            InterlockedCompareExchange(&language_state, 0, 0) ==
                expected_previous;
        if (ready) {
            clear_runtime_identity_locked();
            ReleaseSRWLockExclusive(&state_lock);
            return 1;
        }
        ReleaseSRWLockExclusive(&state_lock);
        Sleep(1);
    }
    (void)bootstrap;
    set_fatal();
    return 0;
}

static int finish_language_transition(LONG value, int exact, int bootstrap,
                                      void *self, void *owner) {
    int committed = 0;
    AcquireSRWLockExclusive(&state_lock);
    if (exact && value >= 0 && value <= 1 &&
        InterlockedCompareExchange(&language_transition_inflight, 0, 0) == 1 &&
        InterlockedCompareExchange(&language_transition_owner_tid, 0, 0) ==
            (LONG)GetCurrentThreadId()) {
        InterlockedExchange(&language_state, value);
        InterlockedIncrement(&language_state_sequence);
        if (bootstrap) {
            InterlockedExchangePointer(
                (void *volatile *)&language_cint_this, self);
            InterlockedExchangePointer(
                (void *volatile *)&language_cint_owner, owner);
            telemetry_increment(&language_bootstrap_exact_events);
        } else {
            telemetry_increment(&language_setter_exact_events);
        }
        InterlockedExchange(&language_transition_owner_tid, 0);
        MemoryBarrier();
        InterlockedExchange(&language_transition_inflight, 0);
        committed = 1;
    } else {
        telemetry_increment(&language_bootstrap_conflict_rejects);
        set_fatal();
    }
    ReleaseSRWLockExclusive(&state_lock);
    return committed;
}

static uintptr_t relevant_setter_failure(uint32_t previous) {
    set_fatal();
#if !defined(PHOTON_V6_PM_SELECTOR_TEST_HOOKS)
    RaiseFailFastException(NULL, NULL, 0);
    TerminateProcess(GetCurrentProcess(), UINT32_C(0xE0005841));
#endif
    return (uintptr_t)previous;
}

static uintptr_t __attribute__((cdecl,noinline,used))
hook_cint_setter_dispatch(void *self, uint32_t value, uintptr_t vm_this) {
    uint32_t vm_vtable, vm_command, vm_source, vm_target, vm_exec;
    uint32_t cint_vtable, cint_owner, cint_meta, cint_type, previous, stored;
    uint16_t vm_opcode;
    void *known_this, *known_owner;
    int bootstrap_exact, action_exact, bootstrap_candidate, action_candidate;
    int known_anomaly, transition_started = 0;
    uintptr_t result;
    if (!selector_semantics_enabled()) return real_cint_setter(self, value);
    vm_vtable = safe_u32((void *)vm_this, 0);
    vm_command = safe_u32((void *)vm_this, 8);
    vm_source = safe_u32((void *)vm_this, 12);
    vm_target = safe_u32((void *)vm_this, 16);
    vm_opcode = safe_u16((void *)vm_this, 24);
    vm_exec = vm_vtable != UINT32_MAX ?
        safe_u32((void *)(uintptr_t)vm_vtable, 0x1C) : UINT32_MAX;
    cint_vtable = safe_u32(self, 0);
    cint_owner = safe_u32(self, 4);
    cint_meta = safe_u32(self, 12);
    previous = safe_u32(self, 0x10);
    cint_type = cint_meta != UINT32_MAX ?
        safe_u32((void *)(uintptr_t)cint_meta, 8) & UINT32_C(0x7FFFFFFF) :
        UINT32_MAX;
    bootstrap_exact =
        main_rva(vm_vtable) == PM_CVM_FLAG_OP_VTABLE_RVA &&
        main_rva(vm_exec) == PM_CVM_FLAG_OP_EXEC_RVA &&
        vm_command == 0x22 && vm_source == 0x06 && vm_opcode == 0 &&
        main_rva(cint_vtable) == PM_CINT_VTABLE_RVA &&
        vm_target == cint_owner && cint_type == UINT32_C(0x16000000) &&
        exact_bootstrap_stack();
    action_exact =
        main_rva(vm_vtable) == PM_CVM_FLAG_OP_VTABLE_RVA &&
        main_rva(vm_exec) == PM_CVM_FLAG_OP_EXEC_RVA &&
        vm_command == 0x237 && vm_opcode == 0 &&
        main_rva(cint_vtable) == PM_CINT_VTABLE_RVA &&
        vm_target == cint_owner && cint_type == UINT32_C(0x16000000) &&
        exact_action_stack();
    known_this = InterlockedCompareExchangePointer(
        (void *volatile *)&language_cint_this, NULL, NULL);
    known_owner = InterlockedCompareExchangePointer(
        (void *volatile *)&language_cint_owner, NULL, NULL);
    bootstrap_candidate = !known_this && bootstrap_exact && value <= 1 &&
        InterlockedCompareExchange(&language_state, 0, 0) ==
            PHOTON_V6_PF_SELECTOR_LANGUAGE_UNKNOWN;
    action_candidate = known_this == self && known_owner &&
        known_owner == (void *)(uintptr_t)cint_owner && action_exact &&
        previous <= 1 && value <= 1 && previous != value &&
        InterlockedCompareExchange(&language_state, 0, 0) == (LONG)previous;
    known_anomaly = known_this && !action_candidate &&
        (known_this == self || (action_exact && vm_command == 0x237));
    if (bootstrap_candidate)
        transition_started = begin_language_transition(
            PHOTON_V6_PF_SELECTOR_LANGUAGE_UNKNOWN, 1);
    else if (action_candidate)
        transition_started = begin_language_transition((LONG)previous, 0);
    else if (known_anomaly)
        transition_started = begin_language_transition(
            InterlockedCompareExchange(&language_state, 0, 0), 0);
    if ((bootstrap_candidate || action_candidate || known_anomaly) &&
        !transition_started) return relevant_setter_failure(previous);
    result = real_cint_setter(self, value);
    stored = safe_u32(self, 0x10);
    if (transition_started) {
        int exact = stored == value && value <= 1 && !known_anomaly &&
            ((bootstrap_candidate && !known_this) ||
             (action_candidate && known_this == self &&
              known_owner == (void *)(uintptr_t)cint_owner));
        if (!finish_language_transition((LONG)value, exact,
                bootstrap_candidate, self, (void *)(uintptr_t)cint_owner))
            return relevant_setter_failure(previous);
    }
    return result;
}

static uintptr_t __attribute__((naked,noinline,used)) hook_cint_setter_abi(void) {
    __asm__ volatile(
        "lock incl _hook_inflight\n\t"
        "pushl %edi\n\t"
        "pushl 8(%esp)\n\t"
        "pushl %ecx\n\t"
        "call _hook_cint_setter_dispatch\n\t"
        "addl $12,%esp\n\t"
        "lock decl _hook_inflight\n\t"
        "ret $4\n\t");
}

static int make_relative(BYTE output[5], BYTE opcode,
                         const void *site, const void *target) {
    intptr_t delta = (const BYTE *)target - ((const BYTE *)site + 5);
    int32_t relative = (int32_t)delta;
    if ((intptr_t)relative != delta) return 0;
    output[0] = opcode;
    memcpy(output + 1, &relative, 4);
    return 1;
}

static int page_protection(void *address, DWORD *protection) {
    MEMORY_BASIC_INFORMATION info;
    if (!VirtualQuery(address, &info, sizeof(info)) ||
        info.State != MEM_COMMIT ||
        (info.Protect & (PAGE_GUARD | PAGE_NOACCESS))) return 0;
    *protection = info.Protect;
    return 1;
}

static void pin_module_or_failfast(void) {
    HMODULE self = NULL, pinned = NULL;
    const void *anchor = (const void *)&photon_v6_pf_selector_adapter_init;
    if (!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS |
            GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
            (LPCWSTR)anchor, &self) || !self ||
        !GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS |
            GET_MODULE_HANDLE_EX_FLAG_PIN, (LPCWSTR)anchor, &pinned) ||
        pinned != self) {
        RaiseFailFastException(NULL, NULL, 0);
        TerminateProcess(GetCurrentProcess(), UINT32_C(0xE0005842));
    }
    InterlockedExchange(&module_pinned, 1);
}

static int prepare_hook(void) {
    int32_t displacement;
    setter_hook.site = main_base + PM_TYPED_SETTER_CALLSITE_RVA;
    if (!range_readable(setter_hook.site, 5) || setter_hook.site[0] != 0xE8 ||
        !page_protection(setter_hook.site, &setter_hook.original_protect))
        return 0;
    displacement = *(const int32_t *)(setter_hook.site + 1);
    if (setter_hook.site + 5 + displacement !=
        main_base + PM_CINT_SETTER_RVA) return 0;
    if (memcmp(setter_hook.site, "\xE8\x78\xEC\x11\x00", 5) != 0 ||
        safe_pointer(main_base + PM_CVM_FLAG_OP_VTABLE_RVA, 0x1C) !=
            (uintptr_t)(main_base + PM_CVM_FLAG_OP_EXEC_RVA)) return 0;
    memcpy(setter_hook.original, setter_hook.site, 5);
    return make_relative(setter_hook.replacement, 0xE8,
                         setter_hook.site, hook_cint_setter_abi);
}

static int install_hook_unquiesced(void) {
    DWORD observed = 0, ignored = 0;
    BOOL protected_back, flushed;
    pin_module_or_failfast();
    if (memcmp(setter_hook.site, setter_hook.original, 5) != 0 ||
        !VirtualProtect(setter_hook.site, 5, PAGE_EXECUTE_READWRITE,
                        &observed)) return 0;
    if (observed != setter_hook.original_protect) {
        VirtualProtect(setter_hook.site, 5, observed, &ignored);
        return 0;
    }
    memcpy(setter_hook.site, setter_hook.replacement, 5);
    InterlockedExchange(&first_mutation_committed, 1);
    InterlockedExchange(&hooks_retained_until_process_exit, 1);
    InterlockedExchange(&setter_hook.journaled, 1);
    InterlockedIncrement(&mutation_journal_entries);
    InterlockedExchange(&setter_hook.installed, 1);
    protected_back = VirtualProtect(setter_hook.site, 5,
                                    setter_hook.original_protect, &ignored);
    flushed = FlushInstructionCache(GetCurrentProcess(), setter_hook.site, 5);
    return protected_back && flushed &&
        memcmp(setter_hook.site, setter_hook.replacement, 5) == 0;
}

static int suspend_other_threads(PmSuspendedThread *threads, int capacity) {
    HANDLE snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0);
    THREADENTRY32 entry;
    DWORD pid = GetCurrentProcessId(), own = GetCurrentThreadId();
    int count = 0, failed = 0;
    if (snapshot == INVALID_HANDLE_VALUE) return -1;
    memset(&entry, 0, sizeof(entry));
    entry.dwSize = sizeof(entry);
    if (Thread32First(snapshot, &entry)) do {
        HANDLE thread;
        CONTEXT context;
        if (entry.th32OwnerProcessID != pid || entry.th32ThreadID == own)
            continue;
        if (count >= capacity) { failed = 1; break; }
        thread = OpenThread(THREAD_SUSPEND_RESUME | THREAD_GET_CONTEXT,
                            FALSE, entry.th32ThreadID);
        if (!thread || SuspendThread(thread) == (DWORD)-1) {
            if (thread) CloseHandle(thread);
            failed = 1;
            break;
        }
        memset(&context, 0, sizeof(context));
        context.ContextFlags = CONTEXT_CONTROL;
        if (!GetThreadContext(thread, &context)) {
            ResumeThread(thread);
            CloseHandle(thread);
            failed = 1;
            break;
        }
        threads[count].handle = thread;
        threads[count].eip = context.Eip;
        ++count;
    } while (Thread32Next(snapshot, &entry));
    CloseHandle(snapshot);
    if (failed) {
        while (count-- > 0) {
            ResumeThread(threads[count].handle);
            CloseHandle(threads[count].handle);
        }
        return -1;
    }
    return count;
}

static int resume_threads(PmSuspendedThread *threads, int count) {
    int good = 1;
    while (count-- > 0) {
        if (ResumeThread(threads[count].handle) == (DWORD)-1) good = 0;
        CloseHandle(threads[count].handle);
    }
    return good;
}

static int quiescent_install(void) {
    PmSuspendedThread threads[PM_MAX_SUSPENDED_THREADS];
    int count = suspend_other_threads(threads, PM_MAX_SUSPENDED_THREADS);
    int index, safe = count >= 0;
    for (index = 0; safe && index < count; ++index)
        if ((uintptr_t)threads[index].eip >= (uintptr_t)setter_hook.site &&
            (uintptr_t)threads[index].eip < (uintptr_t)setter_hook.site + 5)
            safe = 0;
    if (safe) safe = install_hook_unquiesced();
    if (safe) {
        InterlockedExchange(&initialized, 1);
        MemoryBarrier();
    }
    if (count >= 0 && !resume_threads(threads, count)) safe = 0;
    return safe;
}

static void decision_initialize(PhotonV6PfSelectorDecision *decision,
                                uint32_t code) {
    if (!decision) return;
    memset(decision, 0, sizeof(*decision));
    decision->struct_size = sizeof(*decision);
    decision->abi_version = PHOTON_V6_PF_SELECTOR_ADAPTER_ABI;
    decision->decision = code;
    decision->language_state =
        InterlockedCompareExchange(&language_state, 0, 0);
    decision->language_state_sequence = (uint32_t)
        InterlockedCompareExchange(&language_state_sequence, 0, 0);
    decision->language_state_known =
        !InterlockedCompareExchange(&language_transition_inflight, 0, 0) &&
        !InterlockedCompareExchange(&fatal_latch, 0, 0) &&
        (decision->language_state ==
             PHOTON_V6_PF_SELECTOR_LANGUAGE_JAPANESE ||
         decision->language_state ==
             PHOTON_V6_PF_SELECTOR_LANGUAGE_TRANSLATION);
    decision->target_index = PHOTON_V6_PF_SELECTOR_NO_TARGET;
}

static void decision_from_binding(const PmObjectBinding *binding,
                                  LONG surface_id, int decode,
                                  PhotonV6PfSelectorDecision *decision) {
    const PhotonV6PmSpecialCr6Target *target =
        &photon_v6_pm_special_cr6_targets[binding->target_index];
    decision_initialize(decision,
        decode ? PHOTON_V6_PF_SELECTOR_ALLOW_SPECIAL57_TRANSLATION :
                 PHOTON_V6_PF_SELECTOR_SPECIAL57_SURFACE_SCOPE);
    decision->target_index = binding->target_index;
    decision->provider_role =
        PHOTON_V6_PF_SELECTOR_PROVIDER_TRANSLATION_PRIMARY;
    decision->raw_handle = target->stable_identity;
    decision->branch_identity_exact = 1;
    decision->target_payload_exact = 1;
    decision->materializer_commit_exact = 1;
    decision->graph_epoch_current = 1;
    decision->surface_scope_exact = surface_id > 0 ? 1U : 0U;
    decision->decode_scope_exact = decode ? 1U : 0U;
    decision->translation_overlay_allowed = decode ? 1U : 0U;
    decision->japanese_overlay_allowed = 0;
    decision->selected_cref_identity_sequence =
        (uint32_t)binding->object_generation;
    decision->selected_materializer_sequence =
        (uint32_t)binding->object_generation;
    decision->selected_surface_sequence = (uint32_t)surface_id;
    decision->object_generation = (uint32_t)binding->object_generation;
    decision->graph_root = (uintptr_t)(main_base + PM_CVM_FLAG_OP_VTABLE_RVA);
    decision->selected_resource_node = (uintptr_t)binding->payload;
    decision->selected_cr6_object = (uintptr_t)binding->object;
    decision->payload_bytes = binding->payload_bytes;
    decision->payload_fnv1a64 = binding->payload_fnv1a64;
    memcpy(decision->payload_sha256, binding->payload_sha256, 32);
    decision->special_source_asset_id = target->source_asset_id;
    decision->special_context_identity_key = target->context_identity_key;
}

static int binding_live_exact(const PmObjectBinding *binding) {
    BYTE digest[32];
    if (!binding || !binding->active || !cr6_object_exact(binding->object) ||
        binding->language_generation !=
            InterlockedCompareExchange(&language_state_sequence, 0, 0) ||
        safe_pointer(binding->object, 0x18) != (uintptr_t)binding->payload ||
        safe_u32(binding->object, 0x58) != binding->payload_bytes ||
        !range_readable(binding->payload, binding->payload_bytes) ||
        fnv1a64(binding->payload, binding->payload_bytes) !=
            binding->payload_fnv1a64 ||
        !sha256_bytes(binding->payload, binding->payload_bytes, digest))
        return 0;
    return memcmp(digest, binding->payload_sha256, 32) == 0 &&
        target_exact(binding->payload_bytes, binding->payload_fnv1a64,
                     digest) == (int)binding->target_index;
}

static void clear_object_locked(void *object) {
    size_t index;
    for (index = 0; index < PM_MAX_OBJECT_BINDINGS; ++index)
        if (object_bindings[index].active &&
            object_bindings[index].object == object)
            memset(&object_bindings[index], 0, sizeof(object_bindings[index]));
}

static int bind_object(void *object, const BYTE *payload, uint32_t bytes,
                       uint64_t hash, const BYTE digest[32],
                       uint32_t target_index, PmObjectBinding *output) {
    PmObjectBinding *slot = NULL;
    LONG cursor;
    size_t index;
    AcquireSRWLockExclusive(&state_lock);
    clear_object_locked(object);
    for (index = 0; index < PM_MAX_OBJECT_BINDINGS; ++index)
        if (!object_bindings[index].active) { slot = &object_bindings[index]; break; }
    if (!slot) {
        cursor = InterlockedIncrement(&binding_write_cursor);
        slot = &object_bindings[(uint32_t)cursor % PM_MAX_OBJECT_BINDINGS];
    }
    memset(slot, 0, sizeof(*slot));
    slot->object = object;
    slot->payload = payload;
    slot->payload_bytes = bytes;
    slot->payload_fnv1a64 = hash;
    memcpy(slot->payload_sha256, digest, 32);
    slot->target_index = target_index;
    slot->language_generation =
        InterlockedCompareExchange(&language_state_sequence, 0, 0);
    slot->object_generation = InterlockedIncrement(&object_generation_sequence);
    MemoryBarrier();
    slot->active = 1;
    if (output) *output = *slot;
    ReleaseSRWLockExclusive(&state_lock);
    return 1;
}

static int binding_snapshot(void *object, PmObjectBinding *output) {
    PmObjectBinding *match = NULL;
    size_t index;
    AcquireSRWLockShared(&state_lock);
    for (index = 0; index < PM_MAX_OBJECT_BINDINGS; ++index) {
        PmObjectBinding *at = &object_bindings[index];
        if (!at->active || at->object != object) continue;
        if (match) { match = NULL; break; }
        match = at;
    }
    if (match && output) *output = *match;
    ReleaseSRWLockShared(&state_lock);
    return match != NULL;
}

int __attribute__((cdecl)) photon_v6_pf_selector_adapter_note_load(
    void *cr6_object, const void *payload, uint32_t payload_bytes,
    uint64_t payload_fnv1a64, PhotonV6PfSelectorDecision *decision) {
    BYTE digest[32];
    uint64_t hash;
    int weak, exact;
    PmObjectBinding binding;
    InterlockedIncrement(&hook_inflight);
    decision_initialize(decision, PHOTON_V6_PF_SELECTOR_NOT_SPECIAL);
    if (!decision || !cr6_object || !payload || !payload_bytes ||
        payload_bytes > PM_MAX_PAYLOAD_BYTES ||
        !range_readable(payload, payload_bytes) ||
        !selector_semantics_enabled()) {
        InterlockedDecrement(&hook_inflight);
        return 0;
    }
    hash = fnv1a64((const BYTE *)payload, payload_bytes);
    if (!sha256_bytes((const BYTE *)payload, payload_bytes, digest)) {
        set_fatal();
        InterlockedDecrement(&hook_inflight);
        return 0;
    }
    weak = target_weak(payload_bytes, hash);
    exact = target_exact(payload_bytes, hash, digest);
    if (weak < 0) {
        AcquireSRWLockExclusive(&state_lock);
        clear_object_locked(cr6_object);
        ReleaseSRWLockExclusive(&state_lock);
        InterlockedDecrement(&hook_inflight);
        return 0;
    }
    decision->target_index = (uint32_t)weak;
    decision->payload_bytes = payload_bytes;
    decision->payload_fnv1a64 = hash;
    memcpy(decision->payload_sha256, digest, 32);
    if (exact != weak || hash != payload_fnv1a64 ||
        !cr6_object_exact(cr6_object) ||
        safe_pointer(cr6_object, 0x18) != (uintptr_t)payload ||
        safe_u32(cr6_object, 0x58) != payload_bytes) {
        AcquireSRWLockExclusive(&state_lock);
        clear_object_locked(cr6_object);
        ReleaseSRWLockExclusive(&state_lock);
        decision->decision = PHOTON_V6_PF_SELECTOR_REJECT_PAYLOAD_IDENTITY;
        telemetry_increment(&payload_sha256_rejects);
        InterlockedDecrement(&hook_inflight);
        return 0;
    }
    memset(&binding, 0, sizeof(binding));
    bind_object(cr6_object, (const BYTE *)payload, payload_bytes, hash,
                digest, (uint32_t)exact, &binding);
    decision_from_binding(&binding, 0, 0, decision);
    if (decision->language_state ==
            PHOTON_V6_PF_SELECTOR_LANGUAGE_JAPANESE) {
        decision->decision =
            PHOTON_V6_PF_SELECTOR_REJECT_JAPANESE_TRANSLATION_ENDPOINT;
        telemetry_increment(&state0_translation_endpoint_rejects);
    } else if (decision->language_state !=
            PHOTON_V6_PF_SELECTOR_LANGUAGE_TRANSLATION) {
        decision->decision = PHOTON_V6_PF_SELECTOR_REJECT_UNKNOWN_LANGUAGE;
    }
    InterlockedDecrement(&hook_inflight);
    return 1;
}

int __attribute__((cdecl)) photon_v6_pf_selector_adapter_surface_enter(
    void *cr6_object, PhotonV6PfSelectorDecision *decision) {
    PmObjectBinding binding;
    PmActiveSurface *slot = NULL;
    LONG sequence;
    size_t index;
    memset(&binding, 0, sizeof(binding));
    InterlockedIncrement(&hook_inflight);
    decision_initialize(decision, PHOTON_V6_PF_SELECTOR_NOT_SPECIAL);
    if (!decision || !cr6_object || !selector_semantics_enabled() ||
        InterlockedCompareExchange(&language_transition_inflight, 0, 0) ||
        !binding_snapshot(cr6_object, &binding) ||
        !binding_live_exact(&binding)) {
        if (decision && binding.active) {
            decision->target_index = binding.target_index;
            decision->decision = PHOTON_V6_PF_SELECTOR_REJECT_CAUSAL_IDENTITY;
            telemetry_increment(&stale_generation_rejects);
        }
        InterlockedDecrement(&hook_inflight);
        return 0;
    }
    AcquireSRWLockExclusive(&state_lock);
    for (index = 0; index < PM_MAX_ACTIVE_SURFACES; ++index)
        if (!active_surfaces[index].active) { slot = &active_surfaces[index]; break; }
    if (slot && !InterlockedCompareExchange(
            &language_transition_inflight, 0, 0)) {
        sequence = InterlockedIncrement(&surface_sequence);
        memset(slot, 0, sizeof(*slot));
        slot->tid = GetCurrentThreadId();
        slot->sequence = sequence;
        slot->binding = binding;
        MemoryBarrier();
        slot->active = 1;
    } else {
        sequence = 0;
    }
    ReleaseSRWLockExclusive(&state_lock);
    if (!slot || sequence <= 0) {
        telemetry_increment(&surface_identity_rejects);
        InterlockedDecrement(&hook_inflight);
        return 0;
    }
    decision_from_binding(&binding, sequence, 0, decision);
    if (decision->language_state ==
            PHOTON_V6_PF_SELECTOR_LANGUAGE_JAPANESE)
        decision->decision =
            PHOTON_V6_PF_SELECTOR_REJECT_JAPANESE_TRANSLATION_ENDPOINT;
    else if (decision->language_state !=
            PHOTON_V6_PF_SELECTOR_LANGUAGE_TRANSLATION)
        decision->decision = PHOTON_V6_PF_SELECTOR_REJECT_UNKNOWN_LANGUAGE;
    telemetry_increment(&exact_surface_entries);
    InterlockedDecrement(&hook_inflight);
    return 1;
}

int __attribute__((cdecl)) photon_v6_pf_selector_adapter_decode_query(
    PhotonV6PfSelectorDecision *decision) {
    PmActiveSurface snapshot;
    PmActiveSurface *match = NULL;
    DWORD tid = GetCurrentThreadId();
    size_t index;
    int allowed = 0;
    InterlockedIncrement(&hook_inflight);
    decision_initialize(decision, PHOTON_V6_PF_SELECTOR_NOT_SPECIAL);
    if (!decision || !selector_semantics_enabled()) {
        InterlockedDecrement(&hook_inflight);
        return 0;
    }
    memset(&snapshot, 0, sizeof(snapshot));
    AcquireSRWLockExclusive(&state_lock);
    for (index = 0; index < PM_MAX_ACTIVE_SURFACES; ++index) {
        PmActiveSurface *at = &active_surfaces[index];
        if (!at->active || at->tid != tid) continue;
        if (!match || at->sequence > match->sequence) match = at;
    }
    if (match && !InterlockedCompareExchange(
            &language_transition_inflight, 0, 0) &&
        InterlockedCompareExchange(&language_state, 0, 0) ==
            PHOTON_V6_PF_SELECTOR_LANGUAGE_TRANSLATION &&
        match->binding.language_generation ==
            InterlockedCompareExchange(&language_state_sequence, 0, 0) &&
        lease_census_exact_locked()) {
        if (!match->special_lease) {
            match->special_lease = 1;
            InterlockedIncrement(&special_write_lease_count);
            InterlockedIncrement(&translation_write_leases);
        }
        match->decode_queries++;
        snapshot = *match;
        allowed = lease_census_exact_locked();
    } else if (match) {
        snapshot = *match;
    }
    ReleaseSRWLockExclusive(&state_lock);
    if (!match) {
        telemetry_increment(&cross_thread_rejects);
        InterlockedDecrement(&hook_inflight);
        return 0;
    }
    if (!binding_live_exact(&snapshot.binding)) {
        telemetry_increment(&decode_identity_rejects);
        set_fatal();
        InterlockedDecrement(&hook_inflight);
        return 0;
    }
    decision_from_binding(&snapshot.binding, snapshot.sequence,
                          allowed, decision);
    if (!allowed) {
        if (decision->language_state ==
                PHOTON_V6_PF_SELECTOR_LANGUAGE_JAPANESE) {
            decision->decision =
                PHOTON_V6_PF_SELECTOR_REJECT_JAPANESE_TRANSLATION_ENDPOINT;
            telemetry_increment(&state0_translation_endpoint_rejects);
        } else {
            decision->decision = PHOTON_V6_PF_SELECTOR_REJECT_UNKNOWN_LANGUAGE;
        }
        telemetry_increment(&decode_identity_rejects);
        InterlockedDecrement(&hook_inflight);
        return 0;
    }
    telemetry_increment(&exact_decode_queries);
    telemetry_increment(&translation_special57_allows);
    InterlockedDecrement(&hook_inflight);
    return 1;
}

void __attribute__((cdecl)) photon_v6_pf_selector_adapter_surface_leave(
    void *cr6_object) {
    PmActiveSurface *match = NULL;
    DWORD tid = GetCurrentThreadId();
    size_t index;
    int exact = 0;
    InterlockedIncrement(&hook_inflight);
    AcquireSRWLockExclusive(&state_lock);
    for (index = 0; index < PM_MAX_ACTIVE_SURFACES; ++index) {
        PmActiveSurface *at = &active_surfaces[index];
        if (!at->active || at->tid != tid ||
            at->binding.object != cr6_object) continue;
        if (!match || at->sequence > match->sequence) match = at;
    }
    if (match) {
        if (match->special_lease &&
            InterlockedCompareExchange(&special_write_lease_count, 0, 0) > 0 &&
            InterlockedCompareExchange(&translation_write_leases, 0, 0) > 0) {
            InterlockedDecrement(&special_write_lease_count);
            InterlockedDecrement(&translation_write_leases);
        }
        memset(match, 0, sizeof(*match));
        exact = lease_census_exact_locked();
    }
    ReleaseSRWLockExclusive(&state_lock);
    if (!match || !exact) {
        telemetry_increment(&surface_identity_rejects);
        set_fatal();
    }
    InterlockedDecrement(&hook_inflight);
}

int __attribute__((cdecl)) photon_v6_pf_selector_adapter_language_query(
    int32_t *output_state, uint32_t *output_sequence,
    uint32_t *allow_translation) {
    LONG state, sequence;
    int allowed;
    if (!output_state || !output_sequence || !allow_translation) return 0;
    AcquireSRWLockShared(&state_lock);
    state = InterlockedCompareExchange(&language_state, 0, 0);
    sequence = InterlockedCompareExchange(&language_state_sequence, 0, 0);
    allowed = selector_semantics_enabled() &&
        !InterlockedCompareExchange(&language_transition_inflight, 0, 0) &&
        state == PHOTON_V6_PF_SELECTOR_LANGUAGE_TRANSLATION && sequence > 0;
    *output_state = state;
    *output_sequence = (uint32_t)sequence;
    *allow_translation = allowed ? 1U : 0U;
    ReleaseSRWLockShared(&state_lock);
    return allowed;
}

int __attribute__((cdecl)) photon_v6_pf_selector_adapter_ordinary_lease_acquire(
    uint32_t *lease_token, uint32_t *language_generation) {
    PmOrdinaryLease *slot = NULL;
    LONG generation, token;
    size_t index;
    int acquired = 0;
    if (lease_token) *lease_token = 0;
    if (language_generation) *language_generation = 0;
    if (!lease_token || !language_generation) return 0;
    InterlockedIncrement(&hook_inflight);
    AcquireSRWLockExclusive(&state_lock);
    generation = InterlockedCompareExchange(&language_state_sequence, 0, 0);
    if (selector_semantics_enabled() &&
        !InterlockedCompareExchange(&language_transition_inflight, 0, 0) &&
        InterlockedCompareExchange(&language_state, 0, 0) ==
            PHOTON_V6_PF_SELECTOR_LANGUAGE_TRANSLATION &&
        lease_census_exact_locked()) {
        for (index = 0; index < PM_MAX_ORDINARY_LEASES; ++index)
            if (!ordinary_leases[index].active) { slot = &ordinary_leases[index]; break; }
        if (slot) {
            token = InterlockedIncrement(&ordinary_lease_sequence);
            memset(slot, 0, sizeof(*slot));
            slot->tid = GetCurrentThreadId();
            slot->token = token;
            slot->language_generation = generation;
            slot->active = 1;
            InterlockedIncrement(&ordinary_write_lease_count);
            InterlockedIncrement(&translation_write_leases);
            acquired = lease_census_exact_locked();
            if (acquired) {
                *lease_token = (uint32_t)token;
                *language_generation = (uint32_t)generation;
            }
        }
    }
    ReleaseSRWLockExclusive(&state_lock);
    telemetry_increment(acquired ? &ordinary_lease_acquires :
                                   &ordinary_lease_rejects);
    InterlockedDecrement(&hook_inflight);
    return acquired;
}

int __attribute__((cdecl)) photon_v6_pf_selector_adapter_ordinary_lease_validate(
    uint32_t lease_token, uint32_t language_generation) {
    DWORD tid = GetCurrentThreadId();
    size_t index;
    int exact = 0;
    InterlockedIncrement(&hook_inflight);
    AcquireSRWLockShared(&state_lock);
    if (selector_semantics_enabled() &&
        !InterlockedCompareExchange(&language_transition_inflight, 0, 0) &&
        (LONG)language_generation ==
            InterlockedCompareExchange(&language_state_sequence, 0, 0))
        for (index = 0; index < PM_MAX_ORDINARY_LEASES; ++index)
            if (ordinary_leases[index].active &&
                ordinary_leases[index].tid == tid &&
                ordinary_leases[index].token == (LONG)lease_token &&
                ordinary_leases[index].language_generation ==
                    (LONG)language_generation) { exact = 1; break; }
    ReleaseSRWLockShared(&state_lock);
    if (!exact) {
        telemetry_increment(&ordinary_lease_rejects);
        telemetry_increment(&ordinary_lease_generation_rejects);
    }
    InterlockedDecrement(&hook_inflight);
    return exact;
}

void __attribute__((cdecl)) photon_v6_pf_selector_adapter_ordinary_lease_release(
    uint32_t lease_token, uint32_t language_generation) {
    DWORD tid = GetCurrentThreadId();
    size_t index;
    int released = 0;
    InterlockedIncrement(&hook_inflight);
    AcquireSRWLockExclusive(&state_lock);
    for (index = 0; index < PM_MAX_ORDINARY_LEASES; ++index) {
        PmOrdinaryLease *at = &ordinary_leases[index];
        if (!at->active || at->tid != tid ||
            at->token != (LONG)lease_token ||
            at->language_generation != (LONG)language_generation) continue;
        memset(at, 0, sizeof(*at));
        InterlockedDecrement(&ordinary_write_lease_count);
        InterlockedDecrement(&translation_write_leases);
        released = lease_census_exact_locked();
        break;
    }
    ReleaseSRWLockExclusive(&state_lock);
    if (released) telemetry_increment(&ordinary_lease_releases);
    else {
        telemetry_increment(&ordinary_lease_rejects);
        telemetry_increment(&ordinary_lease_generation_rejects);
        set_fatal();
    }
    InterlockedDecrement(&hook_inflight);
}

static void reset_state(void) {
    AcquireSRWLockExclusive(&state_lock);
    memset(object_bindings, 0, sizeof(object_bindings));
    memset(active_surfaces, 0, sizeof(active_surfaces));
    memset(ordinary_leases, 0, sizeof(ordinary_leases));
    InterlockedExchange(&language_state,
        PHOTON_V6_PF_SELECTOR_LANGUAGE_UNKNOWN);
    InterlockedExchange(&language_state_sequence, 0);
    InterlockedExchange(&language_transition_inflight, 0);
    InterlockedExchange(&language_transition_owner_tid, 0);
    InterlockedExchange(&lifecycle_admission_revoked, 0);
    InterlockedExchange(&translation_write_leases, 0);
    InterlockedExchange(&ordinary_write_lease_count, 0);
    InterlockedExchange(&special_write_lease_count, 0);
    InterlockedExchange(&ordinary_lease_sequence, 0);
    InterlockedExchange(&object_generation_sequence, 0);
    InterlockedExchange(&surface_sequence, 0);
    InterlockedExchange(&binding_write_cursor, 0);
    InterlockedExchangePointer((void *volatile *)&language_cint_this, NULL);
    InterlockedExchangePointer((void *volatile *)&language_cint_owner, NULL);
    ReleaseSRWLockExclusive(&state_lock);
    InterlockedExchange(&fatal_latch, 0);
    InterlockedExchange(&telemetry_generation, 0);
#define PM_RESET_COUNTER(name) InterlockedExchange(&(name), 0)
    PM_RESET_COUNTER(language_bootstrap_exact_events);
    PM_RESET_COUNTER(language_bootstrap_conflict_rejects);
    PM_RESET_COUNTER(language_setter_exact_events);
    PM_RESET_COUNTER(global_language_generation_purges);
    PM_RESET_COUNTER(payload_sha256_rejects);
    PM_RESET_COUNTER(state0_translation_endpoint_rejects);
    PM_RESET_COUNTER(exact_surface_entries);
    PM_RESET_COUNTER(surface_identity_rejects);
    PM_RESET_COUNTER(exact_decode_queries);
    PM_RESET_COUNTER(decode_identity_rejects);
    PM_RESET_COUNTER(translation_special57_allows);
    PM_RESET_COUNTER(stale_generation_rejects);
    PM_RESET_COUNTER(cross_thread_rejects);
    PM_RESET_COUNTER(ordinary_lease_acquires);
    PM_RESET_COUNTER(ordinary_lease_rejects);
    PM_RESET_COUNTER(ordinary_lease_releases);
    PM_RESET_COUNTER(ordinary_lease_generation_rejects);
#undef PM_RESET_COUNTER
}

int __attribute__((cdecl)) photon_v6_pf_selector_adapter_init(
    BYTE *verified_main_base) {
    if (!verified_main_base ||
        InterlockedCompareExchange(&initialized, 0, 0) ||
        InterlockedCompareExchange(&initializing, 1, 0) != 0 ||
        InterlockedCompareExchange(&first_mutation_committed, 0, 0) ||
        InterlockedCompareExchange(&hooks_retained_until_process_exit, 0, 0))
        return -1;
    main_base = verified_main_base;
    if (!verify_image(main_base) ||
        PHOTON_V6_PM_SPECIAL_CR6_TARGET_COUNT != 39) {
        main_base = NULL;
        InterlockedExchange(&initializing, 0);
        return -2;
    }
    memset(&setter_hook, 0, sizeof(setter_hook));
    reset_state();
    InterlockedExchange(&shutting_down, 0);
    InterlockedExchange(&semantic_gate_disabled, 0);
    InterlockedExchange(&mutation_journal_entries, 0);
    if (!prepare_hook()) {
        main_base = NULL;
        InterlockedExchange(&initializing, 0);
        return -3;
    }
    real_cint_setter = (CIntSetterFn)(main_base + PM_CINT_SETTER_RVA);
    if (!quiescent_install()) {
        if (InterlockedCompareExchange(&first_mutation_committed, 0, 0)) {
            InterlockedExchange(&semantic_gate_disabled, 1);
            InterlockedExchange(&lifecycle_admission_revoked, 1);
            InterlockedExchange(&shutting_down, 1);
        }
        InterlockedExchange(&initializing, 0);
        return -4;
    }
    InterlockedExchange(&initializing, 0);
    return 0;
}

void __attribute__((cdecl)) photon_v6_pf_selector_adapter_shutdown(void) {
    int retry;
    if (!InterlockedCompareExchange(&first_mutation_committed, 0, 0)) return;
    AcquireSRWLockExclusive(&state_lock);
    InterlockedExchange(&lifecycle_admission_revoked, 1);
    InterlockedExchange(&language_transition_inflight, 1);
    InterlockedExchange(&language_transition_owner_tid,
                        (LONG)GetCurrentThreadId());
    ReleaseSRWLockExclusive(&state_lock);
    for (retry = 0; retry < PM_TRANSITION_DRAIN_RETRIES; ++retry) {
        int drained;
        AcquireSRWLockExclusive(&state_lock);
        drained = lease_census_exact_locked() &&
            InterlockedCompareExchange(&translation_write_leases, 0, 0) == 0 &&
            active_surface_count_locked() == 0;
        if (drained) clear_runtime_identity_locked();
        ReleaseSRWLockExclusive(&state_lock);
        if (drained) break;
        Sleep(1);
    }
    if (retry == PM_TRANSITION_DRAIN_RETRIES) set_fatal();
    InterlockedExchange(&semantic_gate_disabled, 1);
    InterlockedExchange(&shutting_down, 1);
    InterlockedExchange(&initialized, 0);
}

void __attribute__((cdecl)) photon_v6_pf_selector_adapter_query(
    PhotonV6PfSelectorStatus *status) {
    LONG before, after;
    unsigned attempt;
    if (!status) return;
    memset(status, 0, sizeof(*status));
    status->struct_size = sizeof(*status);
    status->abi_version = PHOTON_V6_PF_SELECTOR_ADAPTER_ABI;
    for (attempt = 0; attempt < 128; ++attempt) {
        before = InterlockedCompareExchange(&telemetry_generation, 0, 0);
        if (before & 1) continue;
        status->initialized = (uint32_t)
            InterlockedCompareExchange(&initialized, 0, 0);
        status->hooks_installed = (uint32_t)
            InterlockedCompareExchange(&setter_hook.installed, 0, 0);
        status->expected_hook_count = PM_EXPECTED_HOOK_COUNT;
        status->hook_inflight = (uint32_t)
            InterlockedCompareExchange(&hook_inflight, 0, 0);
        status->hooks_restored_exact =
            status->hooks_installed ? 0U : 1U;
        status->mutation_journal_entries = (uint32_t)
            InterlockedCompareExchange(&mutation_journal_entries, 0, 0);
        status->restored_hook_count = 0;
        status->language_state =
            InterlockedCompareExchange(&language_state, 0, 0);
        status->language_state_sequence = (uint32_t)
            InterlockedCompareExchange(&language_state_sequence, 0, 0);
        status->language_state_known =
            !InterlockedCompareExchange(&language_transition_inflight, 0, 0) &&
            (status->language_state ==
                 PHOTON_V6_PF_SELECTOR_LANGUAGE_JAPANESE ||
             status->language_state ==
                 PHOTON_V6_PF_SELECTOR_LANGUAGE_TRANSLATION);
#define PM_STATUS_COUNTER(field, source) \
        status->field = (uint32_t)InterlockedCompareExchange(&(source), 0, 0)
        PM_STATUS_COUNTER(language_bootstrap_exact_events,
                          language_bootstrap_exact_events);
        PM_STATUS_COUNTER(language_bootstrap_conflict_rejects,
                          language_bootstrap_conflict_rejects);
        PM_STATUS_COUNTER(language_setter_exact_events,
                          language_setter_exact_events);
        PM_STATUS_COUNTER(global_language_generation_purges,
                          global_language_generation_purges);
        PM_STATUS_COUNTER(payload_sha256_rejects, payload_sha256_rejects);
        PM_STATUS_COUNTER(state0_translation_endpoint_rejects,
                          state0_translation_endpoint_rejects);
        PM_STATUS_COUNTER(exact_surface_entries, exact_surface_entries);
        PM_STATUS_COUNTER(surface_identity_rejects, surface_identity_rejects);
        PM_STATUS_COUNTER(exact_decode_queries, exact_decode_queries);
        PM_STATUS_COUNTER(decode_identity_rejects, decode_identity_rejects);
        PM_STATUS_COUNTER(translation_special57_allows,
                          translation_special57_allows);
        PM_STATUS_COUNTER(stale_generation_rejects, stale_generation_rejects);
        PM_STATUS_COUNTER(cross_thread_rejects, cross_thread_rejects);
        PM_STATUS_COUNTER(ordinary_lease_acquires, ordinary_lease_acquires);
        PM_STATUS_COUNTER(ordinary_lease_rejects, ordinary_lease_rejects);
        PM_STATUS_COUNTER(ordinary_lease_releases, ordinary_lease_releases);
        PM_STATUS_COUNTER(ordinary_lease_generation_rejects,
                          ordinary_lease_generation_rejects);
#undef PM_STATUS_COUNTER
        status->translation_write_leases_active = (uint32_t)
            InterlockedCompareExchange(&translation_write_leases, 0, 0);
        status->ordinary_write_leases_active = (uint32_t)
            InterlockedCompareExchange(&ordinary_write_lease_count, 0, 0);
        status->special_write_leases_active = (uint32_t)
            InterlockedCompareExchange(&special_write_lease_count, 0, 0);
        status->fatal_latch = (uint32_t)
            InterlockedCompareExchange(&fatal_latch, 0, 0);
        status->no_hot_lifecycle = 1;
        status->module_pinned = (uint32_t)
            InterlockedCompareExchange(&module_pinned, 0, 0);
        status->first_mutation_committed = (uint32_t)
            InterlockedCompareExchange(&first_mutation_committed, 0, 0);
        status->hooks_retained_until_process_exit = (uint32_t)
            InterlockedCompareExchange(
                &hooks_retained_until_process_exit, 0, 0);
        status->semantic_gate_disabled = (uint32_t)
            InterlockedCompareExchange(&semantic_gate_disabled, 0, 0);
        status->lifecycle_admission_revoked = (uint32_t)
            InterlockedCompareExchange(&lifecycle_admission_revoked, 0, 0);
        status->unload_safe = 0;
        after = InterlockedCompareExchange(&telemetry_generation, 0, 0);
        if (before == after && !(after & 1)) {
            status->snapshot_consistent = 1;
            status->status_generation = (uint32_t)after;
            break;
        }
    }
    status->result = status->fatal_latch ? -1 : 0;
}

#ifdef PHOTON_V6_PM_SELECTOR_TEST_HOOKS
void photon_v6_pf_selector_test_reset(void) {
    reset_state();
}

void photon_v6_pf_selector_test_force_fatal(void) {
    set_fatal();
}

void photon_v6_pf_selector_test_emit_benign_telemetry(void) {
    telemetry_increment(&surface_identity_rejects);
}

int photon_v6_pm_selector_test_synthesize_image(BYTE *image,
                                                 uint32_t bytes) {
    IMAGE_DOS_HEADER *dos;
    IMAGE_NT_HEADERS32 *nt;
    BYTE *callsite;
    int32_t displacement;
    if (!image || bytes < PM_SIZE_OF_IMAGE) return 0;
    memset(image, 0, bytes);
    dos = (IMAGE_DOS_HEADER *)image;
    dos->e_magic = IMAGE_DOS_SIGNATURE;
    dos->e_lfanew = 0x100;
    nt = (IMAGE_NT_HEADERS32 *)(image + dos->e_lfanew);
    nt->Signature = IMAGE_NT_SIGNATURE;
    nt->FileHeader.Machine = IMAGE_FILE_MACHINE_I386;
    nt->FileHeader.TimeDateStamp = PM_TIMESTAMP;
    nt->OptionalHeader.Magic = IMAGE_NT_OPTIONAL_HDR32_MAGIC;
    nt->OptionalHeader.ImageBase = UINT32_C(0x00400000);
    nt->OptionalHeader.SizeOfImage = PM_SIZE_OF_IMAGE;
    callsite = image + PM_TYPED_SETTER_CALLSITE_RVA;
    displacement = (int32_t)(PM_CINT_SETTER_RVA -
        (PM_TYPED_SETTER_CALLSITE_RVA + 5));
    callsite[0] = 0xE8;
    memcpy(callsite + 1, &displacement, sizeof(displacement));
    *(uint32_t *)(image + PM_CVM_FLAG_OP_VTABLE_RVA + 0x1C) =
        (uint32_t)(uintptr_t)(image + PM_CVM_FLAG_OP_EXEC_RVA);
    return verify_image(image);
}

int photon_v6_pm_selector_test_set_language(int32_t state) {
    int exact = 0;
    if (state != PHOTON_V6_PF_SELECTOR_LANGUAGE_JAPANESE &&
        state != PHOTON_V6_PF_SELECTOR_LANGUAGE_TRANSLATION) return 0;
    AcquireSRWLockExclusive(&state_lock);
    if (InterlockedCompareExchange(&initialized, 0, 0) == 1 &&
        !InterlockedCompareExchange(&language_transition_inflight, 0, 0) &&
        lease_census_exact_locked() &&
        InterlockedCompareExchange(&translation_write_leases, 0, 0) == 0) {
        clear_runtime_identity_locked();
        InterlockedExchange(&language_state, state);
        InterlockedIncrement(&language_state_sequence);
        exact = 1;
    }
    ReleaseSRWLockExclusive(&state_lock);
    return exact;
}
#endif
