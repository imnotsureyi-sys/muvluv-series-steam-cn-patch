#ifndef PHOTON_V6_PF_NATIVE_RUNTIME_H
#define PHOTON_V6_PF_NATIVE_RUNTIME_H

#include <stdint.h>
#include <wchar.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct PhotonV6PfNativeStatus {
    uint32_t struct_size;
    int32_t result;
    uint32_t hooks_installed;
    uint32_t hook_inflight;
    uint32_t exact_payload_loads;
    uint32_t overlay_commits;
    uint32_t untargeted_decodes;
    uint32_t rejected_decodes;
    uint32_t fatal_latch;
    uint32_t hooks_restored_exact;
    uint32_t status_generation;
    uint32_t snapshot_consistent;
    uint32_t selector_abi_version;
    uint32_t selector_initialized;
    uint32_t selector_hooks_installed;
    uint32_t selector_hook_inflight;
    uint32_t selector_hooks_restored_exact;
    uint32_t selector_snapshot_consistent;
    uint32_t selector_status_generation;
    int32_t selector_language_state;
    uint32_t selector_language_state_sequence;
    uint32_t selector_language_state_known;
    uint32_t selector_language_bootstrap_exact_events;
    uint32_t selector_language_bootstrap_conflict_rejects;
    uint32_t selector_language_setter_exact_events;
    uint32_t selector_language_graph_discovery_successes;
    uint32_t selector_language_graph_discovery_rejects;
    uint32_t selector_cref_identity_events;
    uint32_t selector_vm_execute_identity_events;
    uint32_t selector_exact_load_bindings;
    uint32_t selector_cached_surface_bindings;
    uint32_t selector_translation_special57_allows;
    uint32_t selector_japanese_translation_endpoint_rejects;
    uint32_t selector_causal_identity_rejects;
    uint32_t selector_c07_alias_rejects;
    uint32_t selector_exact_surface_entries;
    uint32_t selector_exact_decode_queries;
    uint32_t selector_fatal_latch;
    /* ABI-v2 graph/materializer selector telemetry.  Legacy VM/time fields
     * above are retained only for binary layout compatibility and stay zero. */
    uint32_t selector_expected_hook_count;
    uint32_t selector_mutation_journal_entries;
    uint32_t selector_restored_hook_count;
    uint32_t selector_global_language_generation_purges;
    uint32_t selector_graph_begin_events;
    uint32_t selector_graph_end_events;
    uint32_t selector_graph_supersession_purges;
    uint32_t selector_graph_identity_rejects;
    uint32_t selector_cref_identity_rejects;
    uint32_t selector_materializer_entry_events;
    uint32_t selector_materializer_load_candidates;
    uint32_t selector_materializer_fresh_commits;
    uint32_t selector_materializer_cached_commits;
    uint32_t selector_materializer_identity_rejects;
    uint32_t selector_payload_sha256_rejects;
    uint32_t selector_state0_translation_endpoint_rejects;
    uint32_t selector_c07_all_provider_rejects;
    uint32_t selector_surface_identity_rejects;
    uint32_t selector_decode_identity_rejects;
    uint32_t selector_stale_generation_rejects;
    uint32_t selector_cross_thread_rejects;
    uint32_t selector_translation_write_leases_active;
    uint32_t selector_ordinary_write_leases_active;
    uint32_t selector_special_write_leases_active;
    uint32_t selector_ordinary_lease_acquires;
    uint32_t selector_ordinary_lease_rejects;
    uint32_t selector_ordinary_lease_releases;
    uint32_t selector_ordinary_lease_generation_rejects;
    uint32_t no_hot_lifecycle;
    uint32_t module_pinned;
    uint32_t first_mutation_committed;
    uint32_t hooks_retained_until_process_exit;
    uint32_t semantic_gate_disabled;
    uint32_t unload_safe;
    uint32_t mutation_journal_entries;
    uint32_t selector_no_hot_lifecycle;
    uint32_t selector_module_pinned;
    uint32_t selector_first_mutation_committed;
    uint32_t selector_hooks_retained_until_process_exit;
    uint32_t selector_semantic_gate_disabled;
    uint32_t selector_lifecycle_admission_revoked;
    uint32_t selector_unload_safe;
    uint32_t native_initialized;
    uint32_t native_initializing;
    uint32_t native_shutting_down;
    uint32_t native_expected_hook_count;
    uint32_t native_hooks_installed;
    int32_t native_init_detail;
    int32_t native_init_stage;
    int32_t selector_init_detail;
    int32_t last_overlay_status;
    int32_t last_overlay_route_gate_status;
    int32_t last_overlay_sidecar_status;
    int32_t last_overlay_transaction_status;
} PhotonV6PfNativeStatus;

int photon_v6_pf_native_runtime_init(const wchar_t *ordinary_bundle_root);
void photon_v6_pf_native_runtime_shutdown(void);
void photon_v6_pf_native_runtime_query(PhotonV6PfNativeStatus *status);

#ifdef __cplusplus
}
#endif

#endif
