#ifndef PHOTON_V6_RUNTIME_API_H
#define PHOTON_V6_RUNTIME_API_H

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define PHOTON_V6_RUNTIME_ABI_VERSION 0x00010004u

enum PhotonV6GameId {
    PHOTON_V6_GAME_INVALID = 0,
    PHOTON_V6_GAME_PF = 1,
    PHOTON_V6_GAME_PM = 2
};

enum PhotonV6RuntimeResult {
    PHOTON_V6_RUNTIME_READY = 0,
    PHOTON_V6_RUNTIME_DISABLED = 1,
    PHOTON_V6_RUNTIME_INVALID_CONFIG = -1,
    PHOTON_V6_RUNTIME_NOT_COMPILED = -2,
    PHOTON_V6_RUNTIME_INIT_FAILED_CLOSED = -3,
    PHOTON_V6_RUNTIME_CONTRACT_VIOLATION = -4
};

typedef struct PhotonV6RuntimeConfig {
    uint32_t struct_size;
    uint32_t abi_version;
    uint32_t game_id;
    uint32_t runtime_authorized;
    HMODULE self_module;
    HMODULE host_module;
    wchar_t package_root[MAX_PATH];
} PhotonV6RuntimeConfig;

typedef struct PhotonV6RuntimeStatus {
    uint32_t struct_size;
    int32_t result;
    uint32_t runtime_authorized;
    uint32_t hooks_installed;
    uint32_t init_calls;
    uint32_t shutdown_calls;
    uint32_t native_status_generation;
    uint32_t snapshot_consistent;
    uint32_t hook_inflight;
    uint32_t exact_payload_loads;
    uint32_t overlay_commits;
    uint32_t untargeted_decodes;
    uint32_t rejected_decodes;
    uint32_t fatal_latch;
    uint32_t hooks_restored_exact;
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
    int32_t native_init_detail;
    int32_t native_init_stage;
    int32_t selector_init_detail;
    int32_t last_overlay_status;
    int32_t last_overlay_route_gate_status;
    int32_t last_overlay_sidecar_status;
    int32_t last_overlay_transaction_status;
} PhotonV6RuntimeStatus;

/*
 * Replacement boundary for the exact-RGBA transport.
 *
 * Contract:
 * - init is called only after the font guard and official forwarding exports
 *   are ready; never from DllMain.
 * - before the first host mutation, an init failure may return with no hooks
 *   and exact original bytes.  Once any production mutation is committed,
 *   the process generation is permanently no-hot: every negative init and
 *   normal shutdown disables semantics but retains the pinned module, hook
 *   subset, trampolines, originals, locks, and mutation journal until the OS
 *   terminates the process.
 * - shutdown is idempotent and never restores/frees a committed production
 *   mutation from live DllMain or a running process.
 * - retry after a retained mutation is forbidden.  Repeated READY is valid
 *   only for the exact same normalized copied config and a currently healthy
 *   native snapshot; another canonical package root is rejected.
 * - an implementation must copy any config data it retains.
 */
int __cdecl photon_v6_runtime_init(const PhotonV6RuntimeConfig *config);
void __cdecl photon_v6_runtime_shutdown(void);
void __cdecl photon_v6_runtime_query(PhotonV6RuntimeStatus *status);

#ifdef __cplusplus
}
#endif

#endif
