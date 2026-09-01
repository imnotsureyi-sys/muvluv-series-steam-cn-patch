#ifndef PHOTON_V6_PF_SELECTOR_ADAPTER_H
#define PHOTON_V6_PF_SELECTOR_ADAPTER_H

#include <windows.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ABI v2 is the first production ABI backed by the exact PF resource-graph
 * and 0x18837B materializer causal chain. ABI v1 (CVmImage/time/triplet) is
 * intentionally incompatible and must never be accepted by a caller. */
#define PHOTON_V6_PF_SELECTOR_ADAPTER_ABI UINT32_C(0x00020009)
#define PHOTON_V6_PF_SELECTOR_LANGUAGE_UNKNOWN INT32_C(-1)
#define PHOTON_V6_PF_SELECTOR_LANGUAGE_JAPANESE INT32_C(0)
#define PHOTON_V6_PF_SELECTOR_LANGUAGE_TRANSLATION INT32_C(1)
#define PHOTON_V6_PF_SELECTOR_NO_TARGET UINT32_MAX

typedef enum PhotonV6PfSelectorDecisionCode {
    PHOTON_V6_PF_SELECTOR_NOT_SPECIAL = 0,
    PHOTON_V6_PF_SELECTOR_SPECIAL57_SURFACE_SCOPE = 1,
    PHOTON_V6_PF_SELECTOR_ALLOW_SPECIAL57_TRANSLATION = 2,
    PHOTON_V6_PF_SELECTOR_JAPANESE_NEVER_OVERLAY = 3,
    PHOTON_V6_PF_SELECTOR_REJECT_UNKNOWN_LANGUAGE = 4,
    PHOTON_V6_PF_SELECTOR_REJECT_CAUSAL_IDENTITY = 5,
    PHOTON_V6_PF_SELECTOR_REJECT_C07_ALL_PROVIDERS = 6,
    PHOTON_V6_PF_SELECTOR_REJECT_JAPANESE_TRANSLATION_ENDPOINT = 7,
    PHOTON_V6_PF_SELECTOR_REJECT_PAYLOAD_IDENTITY = 8,
    PHOTON_V6_PF_SELECTOR_REJECT_SUPERSEDED_GRAPH = 9,
    PHOTON_V6_PF_SELECTOR_REJECT_THREAD_IDENTITY = 10,
    PHOTON_V6_PF_SELECTOR_REJECT_FATAL_LATCHED = 11,
    PHOTON_V6_PF_SELECTOR_REJECT_INVALID_ARGUMENT = 12
} PhotonV6PfSelectorDecisionCode;

typedef enum PhotonV6PfSelectorProviderRole {
    PHOTON_V6_PF_SELECTOR_PROVIDER_NONE = 0,
    PHOTON_V6_PF_SELECTOR_PROVIDER_TRANSLATION_PRIMARY = 1,
    PHOTON_V6_PF_SELECTOR_PROVIDER_TRANSLATION_SECONDARY = 2,
    PHOTON_V6_PF_SELECTOR_PROVIDER_JAPANESE_PRIMARY = 3,
    PHOTON_V6_PF_SELECTOR_PROVIDER_JAPANESE_SECONDARY = 4,
    PHOTON_V6_PF_SELECTOR_PROVIDER_C07_FORBIDDEN = 5
} PhotonV6PfSelectorProviderRole;

/* All string pointers refer to immutable adapter tables. No allocation crosses
 * the ABI. payload_sha256 is the exact physical endpoint digest, not a label. */
typedef struct PhotonV6PfSelectorDecision {
    uint32_t struct_size;
    uint32_t abi_version;
    uint32_t decision;
    int32_t language_state;
    uint32_t language_state_sequence;
    uint32_t language_state_known;
    uint32_t target_index;
    uint32_t provider_role;
    uint32_t raw_handle;
    uint32_t branch_identity_exact;
    uint32_t target_payload_exact;
    uint32_t materializer_commit_exact;
    uint32_t graph_epoch_current;
    uint32_t surface_scope_exact;
    uint32_t decode_scope_exact;
    uint32_t translation_overlay_allowed;
    uint32_t japanese_overlay_allowed;
    uint32_t selected_cref_identity_sequence;
    uint32_t selected_materializer_sequence;
    uint32_t selected_surface_sequence;
    uint32_t object_generation;
    uintptr_t graph_root;
    uintptr_t selected_resource_node;
    uintptr_t selected_cr6_object;
    uint32_t payload_bytes;
    uint64_t payload_fnv1a64;
    uint8_t payload_sha256[32];
    const char *special_source_asset_id;
    const char *special_context_identity_key;
} PhotonV6PfSelectorDecision;

typedef struct PhotonV6PfSelectorStatus {
    uint32_t struct_size;
    uint32_t abi_version;
    int32_t result;
    uint32_t initialized;
    uint32_t hooks_installed;
    uint32_t expected_hook_count;
    uint32_t hook_inflight;
    uint32_t hooks_restored_exact;
    uint32_t mutation_journal_entries;
    uint32_t restored_hook_count;
    uint32_t snapshot_consistent;
    uint32_t status_generation;
    int32_t language_state;
    uint32_t language_state_sequence;
    uint32_t language_state_known;
    uint32_t language_bootstrap_exact_events;
    uint32_t language_bootstrap_conflict_rejects;
    uint32_t language_setter_exact_events;
    uint32_t global_language_generation_purges;
    uint32_t graph_begin_events;
    uint32_t graph_end_events;
    uint32_t graph_supersession_purges;
    uint32_t graph_identity_rejects;
    uint32_t cref_identity_events;
    uint32_t cref_identity_rejects;
    uint32_t materializer_entry_events;
    uint32_t materializer_load_candidates;
    uint32_t materializer_fresh_commits;
    uint32_t materializer_cached_commits;
    uint32_t materializer_identity_rejects;
    uint32_t payload_sha256_rejects;
    uint32_t state0_translation_endpoint_rejects;
    uint32_t c07_all_provider_rejects;
    uint32_t exact_surface_entries;
    uint32_t surface_identity_rejects;
    uint32_t exact_decode_queries;
    uint32_t decode_identity_rejects;
    uint32_t translation_special57_allows;
    uint32_t stale_generation_rejects;
    uint32_t cross_thread_rejects;
    uint32_t translation_write_leases_active;
    uint32_t ordinary_write_leases_active;
    uint32_t special_write_leases_active;
    uint32_t ordinary_lease_acquires;
    uint32_t ordinary_lease_rejects;
    uint32_t ordinary_lease_releases;
    uint32_t ordinary_lease_generation_rejects;
    /* Production lifecycle is deliberately no-hot.  Once any hook mutation
     * is committed, the combined module, detours, original call targets, and
     * trampolines are retained until process exit. */
    uint32_t no_hot_lifecycle;
    uint32_t module_pinned;
    uint32_t first_mutation_committed;
    uint32_t hooks_retained_until_process_exit;
    uint32_t semantic_gate_disabled;
    /* Irreversible for a no-hot process generation.  It is closed under the
     * selector state lock before lifecycle drain begins, and dominates every
     * ordinary/special admission and relevant language setter. */
    uint32_t lifecycle_admission_revoked;
    uint32_t unload_safe;
    uint32_t fatal_latch;
} PhotonV6PfSelectorStatus;

/* PF-only production lifecycle. verified_main_base must already be the exact,
 * authenticated retail PF main image. init installs only the four selector
 * hooks; Cr6 Load/Surface/Decode stay owned by the combined native runtime. */
int __attribute__((cdecl)) photon_v6_pf_selector_adapter_init(
    BYTE *verified_main_base);
void __attribute__((cdecl)) photon_v6_pf_selector_adapter_shutdown(void);
void __attribute__((cdecl)) photon_v6_pf_selector_adapter_query(
    PhotonV6PfSelectorStatus *status);

/* note_load is pending-only and can never authorize pixels. It must be called
 * after native Cr6 Load returns while exact 0x18837B materializer is nested. */
int __attribute__((cdecl)) photon_v6_pf_selector_adapter_note_load(
    void *cr6_object, const void *payload, uint32_t payload_bytes,
    uint64_t payload_fnv1a64, PhotonV6PfSelectorDecision *decision);

/* surface_enter creates a scope but never authorizes a write. Only a matching
 * decode_query inside that same surface invocation can return ALLOW. */
int __attribute__((cdecl)) photon_v6_pf_selector_adapter_surface_enter(
    void *cr6_object, PhotonV6PfSelectorDecision *decision);
void __attribute__((cdecl)) photon_v6_pf_selector_adapter_surface_leave(
    void *cr6_object);
int __attribute__((cdecl)) photon_v6_pf_selector_adapter_decode_query(
    PhotonV6PfSelectorDecision *decision);

#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
/* Diagnostic builds expose only the first native post-adapter gate failure.
 * Production builds neither export nor call this helper. */
void __attribute__((cdecl))
photon_v6_pf_selector_adapter_diagnostic_native_gate(uint32_t code);
#endif

/* Ordinary overlays remain dominated by the same exact native language state.
 * Unknown, Japanese, fatal, and shutdown states return allow_translation=0. */
int __attribute__((cdecl)) photon_v6_pf_selector_adapter_language_query(
    int32_t *language_state, uint32_t *language_state_sequence,
    uint32_t *allow_translation);

/* Ordinary pixel writes require a generation-bound lease.  The caller must
 * acquire and validate immediately before the write, hold the lease across
 * the entire sidecar/readback/transaction operation, then release it on every
 * exit path.  A language transition latches first, rejects new leases, and
 * cannot commit until all ordinary and special leases have drained. */
int __attribute__((cdecl)) photon_v6_pf_selector_adapter_ordinary_lease_acquire(
    uint32_t *lease_token, uint32_t *language_generation);
int __attribute__((cdecl)) photon_v6_pf_selector_adapter_ordinary_lease_validate(
    uint32_t lease_token, uint32_t language_generation);
void __attribute__((cdecl)) photon_v6_pf_selector_adapter_ordinary_lease_release(
    uint32_t lease_token, uint32_t language_generation);

#ifdef PHOTON_V6_PF_SELECTOR_TEST_HOOKS
enum {
    PHOTON_V6_PF_SELECTOR_TEST_MUTATE_GRAPH = 1U << 0,
    PHOTON_V6_PF_SELECTOR_TEST_MUTATE_CREF = 1U << 1,
    PHOTON_V6_PF_SELECTOR_TEST_MUTATE_NODE = 1U << 2,
    PHOTON_V6_PF_SELECTOR_TEST_MUTATE_OBJECT = 1U << 3,
    PHOTON_V6_PF_SELECTOR_TEST_MUTATE_PAYLOAD_SHA = 1U << 4,
    PHOTON_V6_PF_SELECTOR_TEST_MUTATE_MULTIPLE_LOADS = 1U << 5,
    PHOTON_V6_PF_SELECTOR_TEST_MUTATE_RETURN_OBJECT = 1U << 6,
    PHOTON_V6_PF_SELECTOR_TEST_MUTATE_LANGUAGE_SEQUENCE = 1U << 7,
    PHOTON_V6_PF_SELECTOR_TEST_MUTATE_CROSS_THREAD = 1U << 8,
    PHOTON_V6_PF_SELECTOR_TEST_MUTATE_SUPERSEDED = 1U << 9,
    PHOTON_V6_PF_SELECTOR_TEST_MUTATE_SURFACE_OBJECT = 1U << 10,
    PHOTON_V6_PF_SELECTOR_TEST_MUTATE_SURFACE_SEQUENCE = 1U << 11,
    PHOTON_V6_PF_SELECTOR_TEST_MUTATE_ROUTE_AMBIGUITY = 1U << 12,
    PHOTON_V6_PF_SELECTOR_TEST_MUTATE_NODE_ABA = 1U << 13,
    PHOTON_V6_PF_SELECTOR_TEST_MUTATE_SURFACE_LEAVE_OBJECT = 1U << 14,
    PHOTON_V6_PF_SELECTOR_TEST_MUTATE_DECODE_REVALIDATION = 1U << 15,
    PHOTON_V6_PF_SELECTOR_TEST_MUTATE_LOAD_SHA_TOMBSTONE = 1U << 16
};
void photon_v6_pf_selector_test_reset(void);
int photon_v6_pf_selector_test_resource_kind_predicate(uint32_t kind);
int photon_v6_pf_selector_test_bootstrap_predicate(uint32_t mutation_mask);
int photon_v6_pf_selector_test_set_language(int32_t language_state);
int photon_v6_pf_selector_test_set_language_live(int32_t language_state);
int photon_v6_pf_selector_test_use_payload(
    const void *payload, uint32_t payload_bytes);
int photon_v6_pf_selector_test_run_causal_scenario(
    uint32_t target_index, uint32_t secondary_provider, uint32_t cached,
    uint32_t mutation_mask, PhotonV6PfSelectorDecision *decision);
int photon_v6_pf_selector_test_surface_decode_roundtrip(
    uint32_t mutation_mask, PhotonV6PfSelectorDecision *decision);
int photon_v6_pf_selector_test_nested_archive_top_predicate(void);
int photon_v6_pf_selector_test_sibling_graph_supersession_predicate(void);
int photon_v6_pf_selector_test_active_graph_cref_predicate(void);
int photon_v6_pf_selector_test_endpoint_dormant_cref_predicate(void);
int photon_v6_pf_selector_test_language_generation_aba_predicate(void);
int photon_v6_pf_selector_test_route_ambiguity_predicate(void);
int photon_v6_pf_selector_test_node_aba_predicate(void);
int photon_v6_pf_selector_test_object_binding_splice_predicate(void);
int photon_v6_pf_selector_test_authorization_lease_mutation_predicate(void);
int photon_v6_pf_selector_test_lease_census_corruption_predicate(void);
int photon_v6_pf_selector_test_generation_bound_write_lease_predicate(void);
int photon_v6_pf_selector_test_long_lease_setter_barrier_predicate(void);
int photon_v6_pf_selector_test_same_thread_setter_reentry_predicate(void);
int photon_v6_pf_selector_test_transition_latch_predicate(
    uint32_t abnormal_store);
int photon_v6_pf_selector_test_known_language_identity_drift_predicate(void);
int photon_v6_pf_selector_test_known_language_setter_predicate(void);
int photon_v6_pf_selector_test_known_language_live_setter_predicate(void);
void photon_v6_pf_selector_test_force_post_install_census_failure(
    uint32_t enabled);
void photon_v6_pf_selector_test_set_no_hot_lifecycle(uint32_t enabled);
void photon_v6_pf_selector_test_fail_install_before_ordinal(int32_t ordinal);
void photon_v6_pf_selector_test_force_fatal(void);
void photon_v6_pf_selector_test_emit_benign_telemetry(void);
int photon_v6_pf_selector_test_no_hot_lifecycle_predicate(uint32_t mode);
int photon_v6_pf_selector_test_synthesize_image(BYTE *image, uint32_t bytes);
int photon_v6_pf_selector_test_sha256_abc(void);
#endif

#ifdef __cplusplus
}
#endif

#endif
