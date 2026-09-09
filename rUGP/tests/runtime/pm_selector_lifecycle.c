/* Replay the album-entry setter shape using synthetic objects, not game data. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
static USHORT WINAPI fixture_stack(ULONG, ULONG, PVOID *, PULONG);
#undef CaptureStackBackTrace
#define CaptureStackBackTrace fixture_stack
#include "../../runtime/src/photon_v6_pm_selector_adapter.c"
#undef CaptureStackBackTrace

#define CHECK(x) do { if (!(x)) { fprintf(stderr, "line %d: %s\n", __LINE__, #x); return 1; } } while (0)
static int ignore_store;
static unsigned calls;
static uintptr_t __attribute__((thiscall)) store_value(void *self, uint32_t value) {
    ++calls;
    if (!ignore_store) ((uint32_t *)self)[4] = value;
    return UINT32_C(0x12345678);
}
static USHORT WINAPI fixture_stack(ULONG skip, ULONG count, PVOID *frames, PULONG hash) {
    static const uint32_t rvas[] = {0x43132, 0x42409, 0x122EB8, 0x12D327};
    unsigned i;
    (void)skip; (void)hash;
    for (i = 0; i < count && i < ARRAYSIZE(rvas); ++i) frames[i] = main_base + rvas[i];
    return (USHORT)i;
}
int main(void) {
    uint32_t meta[4] = {0, 0, 0x16000000, 0};
    uint32_t object[5] = {0};
    uint32_t vm[7] = {0};
    uint32_t token = 0, generation = 0;
    LONG old_generation;
    main_base = VirtualAlloc(NULL, PM_SIZE_OF_IMAGE, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    CHECK(main_base);
    *(uint32_t *)(main_base + PM_CVM_FLAG_OP_VTABLE_RVA + 0x1c) =
        (uint32_t)(uintptr_t)(main_base + PM_CVM_FLAG_OP_EXEC_RVA);
    object[0] = (uint32_t)(uintptr_t)(main_base + PM_CINT_VTABLE_RVA);
    object[1] = (uint32_t)(uintptr_t)meta;
    object[3] = (uint32_t)(uintptr_t)meta;
    object[4] = 1;
    vm[0] = (uint32_t)(uintptr_t)(main_base + PM_CVM_FLAG_OP_VTABLE_RVA);
    vm[2] = 0x237;
    vm[4] = object[1];
    reset_state();
    initialized = 1;
    real_cint_setter = store_value;
    CHECK(hook_cint_setter_dispatch(object, 1, (uintptr_t)vm) == 0x12345678);
    CHECK(language_cint_this == object && language_state == 1 && !fatal_latch);
    old_generation = language_state_sequence;
    /* Dump: same this/owner, metadata type now 0x16000001, previous 1 -> 0. */
    meta[2] = 0x16000001;
    CHECK(hook_cint_setter_dispatch(object, 0, (uintptr_t)vm) == 0x12345678);
    CHECK(object[4] == 0 && calls == 2 && !fatal_latch);
    CHECK(!language_cint_this && !language_cint_owner && !language_transition_inflight);
    CHECK(language_state == PHOTON_V6_PF_SELECTOR_LANGUAGE_UNKNOWN);
    CHECK(language_state_sequence > old_generation);
    CHECK(!photon_v6_pf_selector_adapter_ordinary_lease_acquire(&token, &generation));
    /* Reopen the language control: exact Japanese/Translation actions work. */
    meta[2] = 0x16000000;
    CHECK(hook_cint_setter_dispatch(object, 0, (uintptr_t)vm) == 0x12345678);
    CHECK(language_state == 0 && !fatal_latch);
    CHECK(!photon_v6_pf_selector_adapter_ordinary_lease_acquire(&token, &generation));
    CHECK(hook_cint_setter_dispatch(object, 1, (uintptr_t)vm) == 0x12345678);
    CHECK(language_state == 1 && !fatal_latch);
    CHECK(photon_v6_pf_selector_adapter_ordinary_lease_acquire(&token, &generation));
    photon_v6_pf_selector_adapter_ordinary_lease_release(token, generation);
    CHECK(!fatal_latch);
    /* Exact identity plus a failed engine write still fails closed. */
    ignore_store = 1;
    (void)hook_cint_setter_dispatch(object, 0, (uintptr_t)vm);
    CHECK(fatal_latch && object[4] == 1);
    /* An owned lease must prevent revocation/store, rather than deadlocking. */
    reset_state();
    initialized = 1;
    ignore_store = 0;
    (void)hook_cint_setter_dispatch(object, 1, (uintptr_t)vm);
    CHECK(photon_v6_pf_selector_adapter_ordinary_lease_acquire(&token, &generation));
    meta[2] = 0x16000001;
    calls = 0;
    (void)hook_cint_setter_dispatch(object, 0, (uintptr_t)vm);
    CHECK(fatal_latch && object[4] == 1 && calls == 0);
    puts("{\"passed\":true,\"album_identity_drift\":true,\"unknown_denies_translation\":true,\"exact_rebind\":true,\"failed_store_rejected\":true,\"owned_lease_rejected\":true}");
    return 0;
}
