#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include <stdint.h>
#include <string.h>
#include <wchar.h>

#include "photon_v6_runtime_api.h"

#if defined(PHOTON_V6_PRODUCTION_PF) == defined(PHOTON_V6_PRODUCTION_PM)
#error Select exactly one production game.
#endif

#ifndef PHOTON_V6_PRODUCTION_AUTHORIZED
#define PHOTON_V6_PRODUCTION_AUTHORIZED 0
#endif

#if PHOTON_V6_PRODUCTION_PF
#include "photon_v6_pf_native_runtime.h"
#include "photon_v6_pf_selector_adapter.h"
typedef PhotonV6PfNativeStatus PhotonV6NativeStatus;
#define PHOTON_PRODUCTION_SELECTOR_ENABLED 1
#define PHOTON_PRODUCTION_SELECTOR_HOOK_COUNT UINT32_C(4)
#define PHOTON_PRODUCTION_NATIVE_HOOK_COUNT UINT32_C(9)
#define PHOTON_NATIVE_GAME_ID PHOTON_V6_GAME_PF
#define photon_native_init photon_v6_pf_native_runtime_init
#define photon_native_shutdown photon_v6_pf_native_runtime_shutdown
#define photon_native_query photon_v6_pf_native_runtime_query
#else
#include "photon_v6_pm_native_runtime.h"
#if defined(PHOTON_V6_PM_SELECTOR_ADAPTER) && PHOTON_V6_PM_SELECTOR_ADAPTER
#include "photon_v6_pf_selector_adapter.h"
#define PHOTON_PRODUCTION_SELECTOR_ENABLED 1
#define PHOTON_PRODUCTION_SELECTOR_HOOK_COUNT UINT32_C(1)
#define PHOTON_PRODUCTION_NATIVE_HOOK_COUNT UINT32_C(7)
#else
#define PHOTON_PRODUCTION_SELECTOR_ENABLED 0
#define PHOTON_PRODUCTION_SELECTOR_HOOK_COUNT UINT32_C(0)
#define PHOTON_PRODUCTION_NATIVE_HOOK_COUNT UINT32_C(7)
#endif
typedef PhotonV6PmNativeStatus PhotonV6NativeStatus;
#define PHOTON_NATIVE_GAME_ID PHOTON_V6_GAME_PM
#define photon_native_init photon_v6_pm_native_runtime_init
#define photon_native_shutdown photon_v6_pm_native_runtime_shutdown
#define photon_native_query photon_v6_pm_native_runtime_query
#endif

static volatile LONG runtime_state;
static volatile LONG init_calls;
static volatile LONG shutdown_calls;
static volatile LONG contract_violation;
static PhotonV6RuntimeConfig retained_config;

static int canonical_package_root(
    const wchar_t *root, wchar_t output[MAX_PATH]) {
    DWORD attributes;
    DWORD written;
    size_t length;
    if (!root || !root[0]) return 0;
    length = wcsnlen(root, MAX_PATH);
    if (!length || length >= MAX_PATH) return 0;
    written=GetFullPathNameW(root,MAX_PATH,output,NULL);
    if (!written || written>=MAX_PATH) return 0;
    length=wcslen(output);
    while (length>3 &&
        (output[length-1]==L'\\' || output[length-1]==L'/'))
        output[--length]=L'\0';
    attributes = GetFileAttributesW(output);
    return attributes != INVALID_FILE_ATTRIBUTES &&
           (attributes & FILE_ATTRIBUTE_DIRECTORY) != 0;
}

static int owns_self_module(HMODULE module) {
    HMODULE observed = NULL;
    if (!module || !GetModuleHandleExW(
            GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS |
                GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
            (const wchar_t *)(uintptr_t)&photon_v6_runtime_init,
            &observed)) return 0;
    return observed == module;
}

static int normalize_config(
    const PhotonV6RuntimeConfig *input, PhotonV6RuntimeConfig *output) {
    wchar_t canonical[MAX_PATH];
    if (!input || !output || input->struct_size!=sizeof(*input) ||
        input->abi_version!=PHOTON_V6_RUNTIME_ABI_VERSION ||
        input->game_id!=PHOTON_NATIVE_GAME_ID ||
        input->runtime_authorized!=1 ||
        input->host_module!=GetModuleHandleW(NULL) ||
        !owns_self_module(input->self_module) ||
        !canonical_package_root(input->package_root,canonical)) return 0;
    memset(output,0,sizeof(*output));
    output->struct_size=sizeof(*output);
    output->abi_version=PHOTON_V6_RUNTIME_ABI_VERSION;
    output->game_id=PHOTON_NATIVE_GAME_ID;
    output->runtime_authorized=1;
    output->self_module=input->self_module;
    output->host_module=input->host_module;
    memcpy(output->package_root,canonical,
        (wcslen(canonical)+1)*sizeof(wchar_t));
    return 1;
}

static int native_status_ready_exact(const PhotonV6NativeStatus *status) {
    if (!status || status->struct_size!=sizeof(*status) ||
        status->result!=0 || status->fatal_latch!=0 ||
        status->snapshot_consistent!=1 ||
        status->native_initialized!=1 || status->native_initializing!=0 ||
        status->native_shutting_down!=0 ||
        status->native_expected_hook_count!=PHOTON_PRODUCTION_NATIVE_HOOK_COUNT ||
        status->native_hooks_installed!=PHOTON_PRODUCTION_NATIVE_HOOK_COUNT ||
        status->no_hot_lifecycle!=1 || status->module_pinned!=1 ||
        status->first_mutation_committed!=1 ||
        status->hooks_retained_until_process_exit!=1 ||
        status->semantic_gate_disabled!=0 || status->unload_safe!=0 ||
        status->mutation_journal_entries!=PHOTON_PRODUCTION_NATIVE_HOOK_COUNT ||
        status->hooks_restored_exact!=0) return 0;
#if PHOTON_PRODUCTION_SELECTOR_ENABLED
    return status->hooks_installed==PHOTON_PRODUCTION_NATIVE_HOOK_COUNT+
            PHOTON_PRODUCTION_SELECTOR_HOOK_COUNT &&
        status->selector_abi_version==PHOTON_V6_PF_SELECTOR_ADAPTER_ABI &&
        status->selector_initialized==1 &&
        status->selector_hooks_installed==PHOTON_PRODUCTION_SELECTOR_HOOK_COUNT &&
        status->selector_hooks_restored_exact==0 &&
        status->selector_snapshot_consistent==1 &&
        status->selector_fatal_latch==0 &&
        status->selector_expected_hook_count==PHOTON_PRODUCTION_SELECTOR_HOOK_COUNT &&
        status->selector_mutation_journal_entries==
            PHOTON_PRODUCTION_SELECTOR_HOOK_COUNT &&
        status->selector_restored_hook_count==0 &&
        status->selector_no_hot_lifecycle==1 &&
        status->selector_module_pinned==1 &&
        status->selector_first_mutation_committed==1 &&
        status->selector_hooks_retained_until_process_exit==1 &&
        status->selector_semantic_gate_disabled==0 &&
        status->selector_lifecycle_admission_revoked==0 &&
        status->selector_unload_safe==0;
#else
    return status->hooks_installed==PHOTON_PRODUCTION_NATIVE_HOOK_COUNT;
#endif
}

static int native_ready_stable(PhotonV6NativeStatus *output) {
    PhotonV6NativeStatus first,second;
    memset(&first,0,sizeof(first));
    memset(&second,0,sizeof(second));
    first.struct_size=sizeof(first);
    second.struct_size=sizeof(second);
    photon_native_query(&first);
    MemoryBarrier();
    photon_native_query(&second);
    if (output) *output=second;
    return native_status_ready_exact(&first) &&
        native_status_ready_exact(&second) &&
        first.native_initialized==second.native_initialized &&
        first.native_hooks_installed==second.native_hooks_installed &&
        first.semantic_gate_disabled==second.semantic_gate_disabled &&
        first.fatal_latch==second.fatal_latch;
}

static int native_status_retained_exact(const PhotonV6NativeStatus *status) {
    if (!status || status->struct_size!=sizeof(*status) ||
        status->snapshot_consistent!=1 || status->native_initialized!=0 ||
        status->native_initializing!=0 || status->native_shutting_down!=1 ||
        status->native_expected_hook_count!=PHOTON_PRODUCTION_NATIVE_HOOK_COUNT ||
        status->native_hooks_installed==0 || status->no_hot_lifecycle!=1 ||
        status->module_pinned!=1 || status->first_mutation_committed!=1 ||
        status->hooks_retained_until_process_exit!=1 ||
        status->semantic_gate_disabled!=1 || status->unload_safe!=0 ||
        status->hooks_restored_exact!=0) return 0;
#if PHOTON_PRODUCTION_SELECTOR_ENABLED
    return status->selector_no_hot_lifecycle==1 &&
        status->selector_module_pinned==1 &&
        status->selector_hooks_retained_until_process_exit==1 &&
        status->selector_semantic_gate_disabled==1 &&
        status->selector_lifecycle_admission_revoked==1 &&
        status->selector_unload_safe==0;
#else
    return 1;
#endif
}

static int native_status_pristine_exact(const PhotonV6NativeStatus *status) {
    if (!status || status->struct_size!=sizeof(*status) ||
        status->result!=0 || status->fatal_latch!=0 ||
        status->snapshot_consistent!=1 || status->native_initialized!=0 ||
        status->native_initializing!=0 || status->native_shutting_down!=0 ||
        status->native_expected_hook_count!=PHOTON_PRODUCTION_NATIVE_HOOK_COUNT ||
        status->native_hooks_installed!=0 || status->hooks_installed!=0 ||
        status->hook_inflight!=0 || status->mutation_journal_entries!=0 ||
        status->module_pinned!=0 ||
        status->first_mutation_committed!=0 ||
        status->hooks_retained_until_process_exit!=0 ||
        status->semantic_gate_disabled!=0 || status->hooks_restored_exact!=1 ||
        status->unload_safe!=1) return 0;
#if PHOTON_PRODUCTION_SELECTOR_ENABLED
    return status->selector_initialized==0 &&
        status->selector_hooks_installed==0 &&
        status->selector_hook_inflight==0 &&
        status->selector_hooks_restored_exact==1 &&
        status->selector_snapshot_consistent==1 &&
        status->selector_fatal_latch==0 &&
        status->selector_mutation_journal_entries==0 &&
        status->selector_module_pinned==0 &&
        status->selector_first_mutation_committed==0 &&
        status->selector_hooks_retained_until_process_exit==0 &&
        status->selector_semantic_gate_disabled==0 &&
        status->selector_lifecycle_admission_revoked==0;
#else
    return 1;
#endif
}

static int native_pristine_stable(PhotonV6NativeStatus *output) {
    PhotonV6NativeStatus first,second;
    memset(&first,0,sizeof(first));
    memset(&second,0,sizeof(second));
    first.struct_size=sizeof(first);
    second.struct_size=sizeof(second);
    photon_native_query(&first);
    MemoryBarrier();
    photon_native_query(&second);
    if (output) *output=second;
    return native_status_pristine_exact(&first) &&
        native_status_pristine_exact(&second);
}

int __cdecl photon_v6_runtime_init(const PhotonV6RuntimeConfig *config) {
    PhotonV6RuntimeConfig normalized;
    PhotonV6NativeStatus native_status;
    LONG observed;
    int result;
    InterlockedIncrement(&init_calls);
    if (!normalize_config(config,&normalized))
        return PHOTON_V6_RUNTIME_INVALID_CONFIG;
    if (!PHOTON_V6_PRODUCTION_AUTHORIZED)
        return PHOTON_V6_RUNTIME_DISABLED;
    observed = InterlockedCompareExchange(&runtime_state, 1, 0);
    if (observed == 2) {
        if (memcmp(&normalized,&retained_config,sizeof(normalized))!=0)
            return PHOTON_V6_RUNTIME_INIT_FAILED_CLOSED;
        MemoryBarrier();
        if (!native_ready_stable(&native_status) ||
            InterlockedCompareExchange(&runtime_state,0,0)!=2 ||
            memcmp(&normalized,&retained_config,sizeof(normalized))!=0) {
            if (InterlockedCompareExchange(&runtime_state,4,2)==2) {
                photon_native_shutdown();
                InterlockedExchange(&contract_violation,1);
            }
            return PHOTON_V6_RUNTIME_CONTRACT_VIOLATION;
        }
        return PHOTON_V6_RUNTIME_READY;
    }
    if (observed != 0) return PHOTON_V6_RUNTIME_INIT_FAILED_CLOSED;
    memcpy(&retained_config,&normalized,sizeof(retained_config));
    result = photon_native_init(retained_config.package_root);
    if (result != 0) {
        photon_native_shutdown();
        memset(&native_status, 0, sizeof(native_status));
        native_status.struct_size = sizeof(native_status);
        photon_native_query(&native_status);
        if (native_status_retained_exact(&native_status)) {
            /* Any mutation makes this process generation permanently
             * non-retryable.  The pinned pass-through hooks and all original
             * targets stay live until process exit. */
            InterlockedExchange(&contract_violation, 1);
            InterlockedExchange(&runtime_state, 4);
            return PHOTON_V6_RUNTIME_CONTRACT_VIOLATION;
        }
        if (native_pristine_stable(&native_status)) {
            memset(&retained_config,0,sizeof(retained_config));
            InterlockedExchange(&runtime_state,0);
            return PHOTON_V6_RUNTIME_INIT_FAILED_CLOSED;
        }
        /* Only a double-sampled, exact restored/absent native state may
         * reopen initialization.  Any ambiguity retains config and latches
         * this process generation closed, even if one torn snapshot reported
         * zero hooks. */
        InterlockedExchange(&contract_violation,1);
        InterlockedExchange(&runtime_state,4);
        return PHOTON_V6_RUNTIME_CONTRACT_VIOLATION;
    }
    if (!native_ready_stable(&native_status)) {
        photon_native_shutdown();
        InterlockedExchange(&contract_violation,1);
        InterlockedExchange(&runtime_state,4);
        return PHOTON_V6_RUNTIME_CONTRACT_VIOLATION;
    }
    MemoryBarrier();
    InterlockedExchange(&runtime_state, 2);
    return PHOTON_V6_RUNTIME_READY;
}

void __cdecl photon_v6_runtime_shutdown(void) {
    PhotonV6NativeStatus native_status;
    LONG state;
    InterlockedIncrement(&shutdown_calls);
    state = InterlockedCompareExchange(&runtime_state, 3, 2);
    if (state != 2) return;
    photon_native_shutdown();
    memset(&native_status, 0, sizeof(native_status));
    native_status.struct_size = sizeof(native_status);
    photon_native_query(&native_status);
    if (native_status_retained_exact(&native_status)) {
        /* Normal production shutdown is semantic-only.  Do not clear the
         * retained config or reopen initialization: installed no-hot
         * replacements still depend on their prepared originals/locks. */
        InterlockedExchange(&runtime_state, 4);
        return;
    }
    if (native_pristine_stable(&native_status)) {
        memset(&retained_config,0,sizeof(retained_config));
        InterlockedExchange(&runtime_state,0);
        return;
    }
    InterlockedExchange(&contract_violation,1);
    InterlockedExchange(&runtime_state,4);
}

void __cdecl photon_v6_runtime_query(PhotonV6RuntimeStatus *status) {
    PhotonV6NativeStatus native_status;
    LONG state;
    if (!status) return;
    memset(status, 0, sizeof(*status));
    status->struct_size = sizeof(*status);
    status->runtime_authorized =
        PHOTON_V6_PRODUCTION_AUTHORIZED ? 1U : 0U;
    status->init_calls =
        (uint32_t)InterlockedCompareExchange(&init_calls, 0, 0);
    status->shutdown_calls =
        (uint32_t)InterlockedCompareExchange(&shutdown_calls, 0, 0);
    state = InterlockedCompareExchange(&runtime_state, 0, 0);
    memset(&native_status, 0, sizeof(native_status));
    native_status.struct_size = sizeof(native_status);
    photon_native_query(&native_status);
    status->hooks_installed = native_status.hooks_installed;
    status->native_status_generation = native_status.status_generation;
    status->snapshot_consistent = native_status.snapshot_consistent;
    status->hook_inflight = native_status.hook_inflight;
    status->exact_payload_loads = native_status.exact_payload_loads;
    status->overlay_commits = native_status.overlay_commits;
    status->untargeted_decodes = native_status.untargeted_decodes;
    status->rejected_decodes = native_status.rejected_decodes;
    status->fatal_latch = native_status.fatal_latch;
    status->hooks_restored_exact = native_status.hooks_restored_exact;
    status->selector_abi_version = native_status.selector_abi_version;
    status->selector_initialized = native_status.selector_initialized;
    status->selector_hooks_installed = native_status.selector_hooks_installed;
    status->selector_hook_inflight = native_status.selector_hook_inflight;
    status->selector_hooks_restored_exact =
        native_status.selector_hooks_restored_exact;
    status->selector_snapshot_consistent =
        native_status.selector_snapshot_consistent;
    status->selector_status_generation =
        native_status.selector_status_generation;
    status->selector_language_state = native_status.selector_language_state;
    status->selector_language_state_sequence =
        native_status.selector_language_state_sequence;
    status->selector_language_state_known =
        native_status.selector_language_state_known;
    status->selector_language_bootstrap_exact_events =
        native_status.selector_language_bootstrap_exact_events;
    status->selector_language_bootstrap_conflict_rejects =
        native_status.selector_language_bootstrap_conflict_rejects;
    status->selector_language_setter_exact_events =
        native_status.selector_language_setter_exact_events;
    status->selector_language_graph_discovery_successes =
        native_status.selector_language_graph_discovery_successes;
    status->selector_language_graph_discovery_rejects =
        native_status.selector_language_graph_discovery_rejects;
    status->selector_cref_identity_events =
        native_status.selector_cref_identity_events;
    status->selector_vm_execute_identity_events =
        native_status.selector_vm_execute_identity_events;
    status->selector_exact_load_bindings =
        native_status.selector_exact_load_bindings;
    status->selector_cached_surface_bindings =
        native_status.selector_cached_surface_bindings;
    status->selector_translation_special57_allows =
        native_status.selector_translation_special57_allows;
    status->selector_japanese_translation_endpoint_rejects =
        native_status.selector_japanese_translation_endpoint_rejects;
    status->selector_causal_identity_rejects =
        native_status.selector_causal_identity_rejects;
    status->selector_c07_alias_rejects =
        native_status.selector_c07_alias_rejects;
    status->selector_exact_surface_entries =
        native_status.selector_exact_surface_entries;
    status->selector_exact_decode_queries =
        native_status.selector_exact_decode_queries;
    status->selector_fatal_latch = native_status.selector_fatal_latch;
    status->native_init_detail = native_status.native_init_detail;
    status->native_init_stage = native_status.native_init_stage;
    status->selector_init_detail = native_status.selector_init_detail;
    status->last_overlay_status = native_status.last_overlay_status;
    status->last_overlay_route_gate_status =
        native_status.last_overlay_route_gate_status;
    status->last_overlay_sidecar_status =
        native_status.last_overlay_sidecar_status;
    status->last_overlay_transaction_status =
        native_status.last_overlay_transaction_status;
    if (InterlockedCompareExchange(&contract_violation, 0, 0))
        status->result = PHOTON_V6_RUNTIME_CONTRACT_VIOLATION;
    else if (native_status.fatal_latch)
        status->result = PHOTON_V6_RUNTIME_CONTRACT_VIOLATION;
    else if (!PHOTON_V6_PRODUCTION_AUTHORIZED)
        status->result = PHOTON_V6_RUNTIME_DISABLED;
    else if (state == 2 && native_status_ready_exact(&native_status))
        status->result = PHOTON_V6_RUNTIME_READY;
    else
        status->result = PHOTON_V6_RUNTIME_INIT_FAILED_CLOSED;
}
