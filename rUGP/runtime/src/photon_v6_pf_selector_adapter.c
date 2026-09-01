#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <tlhelp32.h>

#include <stdint.h>
#include <string.h>

#include "photon_v6_pf_selector_adapter.h"

#if !defined(PHOTON_V6_PRODUCTION_PF)
#error photon_v6_pf_selector_adapter requires PHOTON_V6_PRODUCTION_PF
#endif
#if !defined(PHOTON_V6_PF_SELECTOR_ADAPTER)
#error photon_v6_pf_selector_adapter requires PHOTON_V6_PF_SELECTOR_ADAPTER
#endif
#if !defined(__i386__) && !defined(_M_IX86)
#error photon_v6_pf_selector_adapter must use the 32-bit Windows ABI
#endif

/*
 * PF production selector adapter v2.
 *
 * Authorization is a structural chain, never a timer or historical summary:
 * active BF880 graph instance -> successful CRef read -> selected resource
 * node -> exact 18837B materializer -> pending native Load -> unique post-return
 * object commit -> same-thread Surface scope -> Decode query.  State zero and
 * collision-07 always pass through to the retail renderer without overlay.
 * This production module has no external control, output, or test-input ABI.
 */

enum {
    PF_TIMESTAMP = 0x5BFBE4FF,
    PF_SIZE_OF_IMAGE = 0x00380000,
    PF_CREF_READ_RVA = 0x001CDCB0,
    PF_SELECTOR_GRAPH_ROOT_SERIALIZE_RVA = 0x000BF880,
    PF_CREF_RESOURCE_MATERIALIZER_CALLSITE_RVA = 0x0018837B,
    PF_CREF_RESOURCE_MATERIALIZER_RVA = 0x001D43D0,
    PF_TYPED_SETTER_CALLSITE_RVA = 0x000C3DE3,
    PF_CINT_SETTER_RVA = 0x001E2A80,
    PF_CVM_FLAG_OP_VTABLE_RVA = 0x0022E7B8,
    PF_CVM_FLAG_OP_EXEC_RVA = 0x000C3420,
    PF_CINT_VTABLE_RVA = 0x0023FE5C,
    PF_CINT_TYPE_METADATA_RVA = 0x00284678,
    PF_IMAGE_LANGUAGE_OWNER_METADATA_RVA = 0x00285620,
    PF_CR6TI_TYPE_DESCRIPTOR_RVA = 0x00282FA0,
    PF_CR6TI_PRIMARY_VTABLE_RVA = 0x00239DF0,
    PF_CR6TI_SECONDARY_VTABLE_RVA = 0x00239E68,
    PF_CR6TI_FACTORY_RVA = 0x0017F0C0,
    PF_CR6TI_TYPE_FUNCTION_RVA = 0x00176730,
    PF_CR6TI_NAME_METADATA_RVA = 0x00239CE0,
    PF_NULL_RESOURCE_SENTINEL_RVA = 0x002BE61C,
    MAX_GRAPH_EPOCHS = 256,
    MAX_CREF_BINDINGS = 512,
    MAX_MATERIALIZATIONS = 64,
    MAX_OBJECT_BINDINGS = 256,
    MAX_ACTIVE_SURFACES = 128,
    MAX_ORDINARY_WRITE_LEASES = 64,
    MAX_SUSPENDED_THREADS = 512,
    MAX_PAYLOAD_BYTES = 128U * 1024U * 1024U,
    RESTORE_RETRIES = 160,
    SHUTDOWN_LEASE_DRAIN_RETRIES = 10000,
    EXPECTED_HOOK_COUNT = 4
};

enum {
    ROUTE_TRANSLATION_PRIMARY = 1,
    ROUTE_TRANSLATION_SECONDARY = 2,
    ROUTE_JAPANESE_PRIMARY = 3,
    ROUTE_JAPANESE_SECONDARY = 4,
    ROUTE_C07_FORBIDDEN = 5
};

enum {
    OBJECT_BINDING_CLEAR_GRAPH_PURGE = 1,
    OBJECT_BINDING_CLEAR_NOTE_NOT_TARGET = 2,
    OBJECT_BINDING_CLEAR_NOTE_IDENTITY_REJECT = 3,
    OBJECT_BINDING_CLEAR_NOTE_TARGET_PREPARE = 4,
    OBJECT_BINDING_CLEAR_MATERIALIZER_PREPARE = 5,
    OBJECT_BINDING_CLEAR_MATERIALIZER_RETURN = 6,
    OBJECT_BINDING_CLEAR_MATERIALIZER_REJECT = 7,
    OBJECT_BINDING_CLEAR_SURFACE_REJECT = 8,
    OBJECT_BINDING_CLEAR_SURFACE_ABORT = 9,
    OBJECT_BINDING_CLEAR_SURFACE_MISMATCH = 10,
    OBJECT_BINDING_CLEAR_SURFACE_RELEASE = 11,
    OBJECT_BINDING_CLEAR_TEST_MUTATION = 12
};

typedef uintptr_t (__attribute__((thiscall)) *CRefReadFn)(
    void *self, void *archive, uint32_t raw_handle);
typedef uintptr_t (__attribute__((thiscall)) *SerializeFn)(
    void *object, void *archive);
typedef uintptr_t (__attribute__((thiscall)) *ResourceMaterializerFn)(void *node);
typedef uintptr_t (__attribute__((thiscall)) *CIntSetterFn)(
    void *self, uint32_t value);

typedef struct RouteDef {
    uint32_t raw_handle;
    uint32_t static_object_handle;
    uint32_t static_archive_ordinal;
    int target_index;
    int group_target_index;
    uint32_t role;
    const char *source_asset_id;
    const char *context_identity_key;
} RouteDef;

typedef struct TargetDef {
    uint32_t payload_bytes;
    uint64_t payload_fnv1a64;
    const char *asset_id;
    const char *payload_sha256;
} TargetDef;

typedef struct ArchiveSample {
    uint32_t mode;
    uint32_t counter;
    uintptr_t cursor;
    uintptr_t end;
} ArchiveSample;

typedef struct RouteFrame {
    DWORD tid;
    void *archive;
    void *graph_root;
    void *cref_self;
    void *resolved_node;
    uint32_t raw_handle;
    int route_index;
    LONG graph_epoch;
    LONG language_sequence;
    LONG cref_identity_sequence;
    int runtime_graph_identity_exact;
} RouteFrame;

typedef struct GraphEpochState {
    DWORD tid;
    void *archive;
    void *graph_root;
    LONG epoch;
    LONG depth;
    LONG nesting_level;
    LONG enter_sequence;
    LONG language_sequence;
    int completed;
    int active;
} GraphEpochState;

typedef struct CRefBinding {
    DWORD tid;
    void *cref_self;
    void *resolved_node;
    RouteFrame route;
    LONG identity_sequence;
    LONG endpoint_language_state;
    int graph_completion_exact;
    int active;
} CRefBinding;

typedef struct PendingLoad {
    void *object;
    const void *payload;
    uint32_t payload_bytes;
    uint64_t payload_fnv1a64;
    uint8_t payload_sha256[32];
    int target_index;
    int exact;
} PendingLoad;

typedef struct ActiveMaterialization {
    DWORD tid;
    LONG depth;
    LONG sequence;
    RouteFrame route;
    void *resource_node;
    void *object_before;
    uint32_t node_kind;
    LONG language_state;
    LONG language_sequence;
    LONG nested_load_count;
    PendingLoad pending;
    int node_invariants_exact;
    int active;
} ActiveMaterialization;

typedef struct ObjectBinding {
    DWORD tid;
    void *object;
    void *payload;
    void *resource_node;
    RouteFrame route;
    uint32_t node_kind;
    uint32_t payload_bytes;
    uint64_t payload_fnv1a64;
    uint8_t payload_sha256[32];
    int target_index;
    LONG materializer_sequence;
    LONG object_generation;
    LONG language_state;
    LONG language_sequence;
    int cached_commit;
    int active;
} ObjectBinding;

typedef struct ActiveSurface {
    DWORD tid;
    LONG depth;
    LONG sequence;
    LONG decode_count;
    LONG authorization_lease;
    LONG closing;
    ObjectBinding binding;
    int active;
} ActiveSurface;

typedef struct OrdinaryWriteLease {
    DWORD tid;
    LONG token;
    LONG language_generation;
    int active;
} OrdinaryWriteLease;

typedef struct EntryHook {
    DWORD rva;
    const BYTE *expected;
    SIZE_T length;
    void *replacement;
    BYTE original[16];
    BYTE *target;
    BYTE *trampoline;
    DWORD original_protect;
    LONG installed;
    LONG journaled;
} EntryHook;

typedef struct CallHook {
    DWORD callsite_rva;
    DWORD target_rva;
    void *replacement;
    BYTE original[5];
    BYTE replacement_bytes[5];
    BYTE *site;
    DWORD original_protect;
    LONG installed;
    LONG journaled;
} CallHook;

typedef struct SuspendedThread {
    HANDLE handle;
    DWORD eip;
} SuspendedThread;

static const BYTE EXPECT_CREF_READ[] =
    {0x55,0x8B,0xEC,0x51,0x8B,0x45,0x0C};
static const BYTE EXPECT_GRAPH_ROOT_SERIALIZE[] =
    {0x55,0x8B,0xEC,0x6A,0xFF};
static const BYTE EXPECT_GRAPH_ROOT_CREF_ARRAY_CALL_CONTEXT[] = {
    0x83,0xF8,0x11,0x72,0x3E,0x8D,0x4B,0x10,0x57,
    0xE8,0xAE,0xBD,0xFF,0xFF,0x83,0x7D,0xEC,0x13
};
static const BYTE EXPECT_MATERIALIZER_CALL_CONTEXT[] = {
    0x8B,0x0B,0x81,0xF9,0x1C,0xE6,0x6B,0x00,0x0F,0x84,0xC2,0x03,0x00,0x00,
    0xE8,0x50,0xC0,0x04,0x00,0x8D,0x95,0x4C,0xFF,0xFF,0xFF,0x52,0x8D,0x48,
    0x0C,0x8B,0x01,0xFF,0x50,0x14
};

/* object_handle and archive_ordinal are sealed static parse metadata only.
 * Runtime authorization uses the globally unique raw handle plus the live
 * graph, CRef, selected node, materializer, object, and full payload digest. */
static const RouteDef routes[] = {
    {0x0E6AD8FC,0x06F8,0x0138,0,0,ROUTE_TRANSLATION_PRIMARY,
     "pf:rio000:0x1c5e589c","612A599BB2D8C7ABCDBCF47B77B141904A64B5651F5ECC91DCBCD333D41962D6:PRIMARY:0x000006F8:0x00000138:0x0E6AD8FC"},
    {0x0E6AD6C0,0x7058,0x0013,0,0,ROUTE_TRANSLATION_SECONDARY,
     "pf:rio000:0x1c83be9c","612A599BB2D8C7ABCDBCF47B77B141904A64B5651F5ECC91DCBCD333D41962D6:SECONDARY:0x00007058:0x00000013:0x0E6AD6C0:INFORMATION_PAGE_STATE"},
    {0x0E6ADA04,0x0848,0x014D,1,1,ROUTE_TRANSLATION_PRIMARY,
     "pf:rio000:0x1c63c898","612A599BB2D8C7ABCDBCF47B77B141904A64B5651F5ECC91DCBCD333D41962D6:PRIMARY:0x00000848:0x0000014D:0x0E6ADA04"},
    {0x0E6AD58C,0x7140,0x0018,1,1,ROUTE_TRANSLATION_SECONDARY,
     "pf:rio000:0x1c86882c","612A599BB2D8C7ABCDBCF47B77B141904A64B5651F5ECC91DCBCD333D41962D6:SECONDARY:0x00007140:0x00000018:0x0E6AD58C:INFORMATION_PAGE_STATE"},
    {0x0E6ADBE8,0x3660,0x0277,2,2,ROUTE_TRANSLATION_PRIMARY,
     "pf:rio000:0x1c6fc18c","612A599BB2D8C7ABCDBCF47B77B141904A64B5651F5ECC91DCBCD333D41962D6:PRIMARY:0x00003660:0x00000277:0x0E6ADBE8"},
    {0x0E6AD694,0x7718,0x009F,2,2,ROUTE_TRANSLATION_SECONDARY,
     "pf:rio000:0x1c897908","612A599BB2D8C7ABCDBCF47B77B141904A64B5651F5ECC91DCBCD333D41962D6:SECONDARY:0x00007718:0x0000009F:0x0E6AD694:INFORMATION_PAGE_STATE"},
    {0x0E6ADC98,0x3990,0x0283,3,3,ROUTE_TRANSLATION_PRIMARY,
     "pf:rio000:0x1c75f1d8","612A599BB2D8C7ABCDBCF47B77B141904A64B5651F5ECC91DCBCD333D41962D6:PRIMARY:0x00003990:0x00000283:0x0E6ADC98"},
    {0x0E6AD560,0x7B88,0x00B6,3,3,ROUTE_TRANSLATION_SECONDARY,
     "pf:rio000:0x1c8c99d4","612A599BB2D8C7ABCDBCF47B77B141904A64B5651F5ECC91DCBCD333D41962D6:SECONDARY:0x00007B88:0x000000B6:0x0E6AD560:INFORMATION_PAGE_STATE"},
    {0x0E6ADAE0,0x3AA0,0x027B,4,4,ROUTE_TRANSLATION_PRIMARY,
     "pf:rio000:0x1c7aa5b4","612A599BB2D8C7ABCDBCF47B77B141904A64B5651F5ECC91DCBCD333D41962D6:PRIMARY:0x00003AA0:0x0000027B:0x0E6ADAE0"},
    {0x0E6AD534,0x7BF8,0x00B8,4,4,ROUTE_TRANSLATION_SECONDARY,
     "pf:rio000:0x1c8eef90","612A599BB2D8C7ABCDBCF47B77B141904A64B5651F5ECC91DCBCD333D41962D6:SECONDARY:0x00007BF8:0x000000B8:0x0E6AD534:INFORMATION_PAGE_STATE"},
    {0x0E6B0654,0xBCD8,0x09D1,5,5,ROUTE_TRANSLATION_PRIMARY,
     "pf:rio000:0x1cc0ea48","0x0000BCD8:0x000009D1:0x0E6B0654:OPTIONS_AUTOPLAY_VM_PRIMARY"},
    {0x0E6AF710,0xBDD4,0x09D8,-1,5,ROUTE_JAPANESE_SECONDARY,NULL,NULL},
    {0x0E6B146C,0xBE30,0x09D9,5,5,ROUTE_C07_FORBIDDEN,NULL,NULL},
    {0x0E6ADA30,0x069C,0x012D,-1,0,ROUTE_JAPANESE_PRIMARY,NULL,NULL},
    {0x0E6AD7C8,0x07EC,0x014C,-1,1,ROUTE_JAPANESE_PRIMARY,NULL,NULL},
    {0x0E6ADCC4,0x3604,0x0276,-1,2,ROUTE_JAPANESE_PRIMARY,NULL,NULL},
    {0x0E6ADB90,0x3934,0x0282,-1,3,ROUTE_JAPANESE_PRIMARY,NULL,NULL},
    {0x0E6AD8D0,0x3A44,0x027A,-1,4,ROUTE_JAPANESE_PRIMARY,NULL,NULL},
    {0x0E6B0F44,0xBC7C,0x09D0,-1,5,ROUTE_JAPANESE_PRIMARY,NULL,NULL}
};

static const TargetDef targets[] = {
    {172852,UINT64_C(0x9FE1D3D4D915E86C),"pf:rio000:0x1c612534","9AA2E5031E40D78ED7EAC08D30487D6259B9B7FDCB8FAEC735C0440026C8BCB9"},
    {217310,UINT64_C(0x2F9E6FCA31EFF05F),"pf:rio000:0x1c66bbe0","81EC28871996B1DA399DF68AFB9D909721ED1478C7FC3B4F1A7DA4A6888DD9AD"},
    {200680,UINT64_C(0x241021254568B28B),"pf:rio000:0x1c72e1c0","C1B4E99136E900B7D94DEC1D6A0078CD2A966795B501DD9A6DF3789857BEAC3B"},
    {155020,UINT64_C(0x45369E26D50A1DD4),"pf:rio000:0x1c7847f8","0B50C4B49D2DCA138EC25549D31DB939450FF8B42F34ACB70AC93DECCDE7F5D9"},
    {146600,UINT64_C(0x19F740FDA7919E34),"pf:rio000:0x1c7c93c8","2EB021A2CCD57D8383349E0B574A8CBF6C55BFFC4352B3749EE1057CDEF612ED"},
    {17108,UINT64_C(0xBE9B8D604DE639FC),"pf:rio000:0x1cc12558","EF0806FE035A350919E4F5F8DC9ED9197EE9D17F546D232B0E5A4A5DD8A58F0E"}
};

static BYTE *main_base;
static CRefReadFn real_cref_read;
static SerializeFn real_graph_root_serialize;
static ResourceMaterializerFn real_resource_materializer;
static CIntSetterFn real_cint_setter;
static EntryHook entry_hooks[2];
static CallHook call_hooks[2];
static SRWLOCK state_lock = SRWLOCK_INIT;
static SRWLOCK patch_lock = SRWLOCK_INIT;
static SRWLOCK telemetry_lock = SRWLOCK_INIT;
static GraphEpochState graph_epochs[MAX_GRAPH_EPOCHS];
static CRefBinding cref_bindings[MAX_CREF_BINDINGS];
static ActiveMaterialization active_materializations[MAX_MATERIALIZATIONS];
static ObjectBinding object_bindings[MAX_OBJECT_BINDINGS];
static ActiveSurface active_surfaces[MAX_ACTIVE_SURFACES];
static OrdinaryWriteLease ordinary_write_lease_slots[
    MAX_ORDINARY_WRITE_LEASES];
static void clear_object_binding_locked(void *object, void *node,
    uint32_t clear_reason);

#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
enum {
    DIAGNOSTIC_CREF_HISTORY_CAPACITY = 128,
    DIAGNOSTIC_MATERIALIZER_THREADS = 32,
    DIAGNOSTIC_MATERIALIZER_DEPTH = 32
};
typedef struct DiagnosticCRefHistory {
    DWORD tid;
    void *cref_self;
    void *resolved_node;
    void *graph_root;
    uint32_t raw_handle;
    int route_index;
    LONG graph_epoch;
    LONG language_sequence;
    LONG graph_active;
    LONG read_exact;
    LONG bind_exact;
    LONG sequence;
} DiagnosticCRefHistory;
typedef struct DiagnosticMaterializerThread {
    DWORD tid;
    void *nodes[DIAGNOSTIC_MATERIALIZER_DEPTH];
    LONG persistent[DIAGNOSTIC_MATERIALIZER_DEPTH];
    LONG node_exact[DIAGNOSTIC_MATERIALIZER_DEPTH];
    LONG route_exact[DIAGNOSTIC_MATERIALIZER_DEPTH];
    LONG route_index_plus_one[DIAGNOSTIC_MATERIALIZER_DEPTH];
    LONG raw_handle[DIAGNOSTIC_MATERIALIZER_DEPTH];
    LONG cref_identity_sequence[DIAGNOSTIC_MATERIALIZER_DEPTH];
    LONG language_sequence[DIAGNOSTIC_MATERIALIZER_DEPTH];
    LONG depth;
    int active;
} DiagnosticMaterializerThread;
static SRWLOCK diagnostic_lock = SRWLOCK_INIT;
static DiagnosticCRefHistory diagnostic_cref_history[
    DIAGNOSTIC_CREF_HISTORY_CAPACITY];
static DiagnosticMaterializerThread diagnostic_materializer_threads[
    DIAGNOSTIC_MATERIALIZER_THREADS];
static volatile LONG diagnostic_cref_history_sequence;
static volatile LONG diagnostic_special_events;
static volatile LONG diagnostic_special_top_node;
static volatile LONG diagnostic_special_cr6_object;
static volatile LONG diagnostic_special_closest_resolved;
static volatile LONG diagnostic_special_closest_delta = -1;
static volatile LONG diagnostic_special_route_index_plus_one;
static volatile LONG diagnostic_special_relation_flags;
static volatile LONG diagnostic_special_raw_handle;
static volatile LONG diagnostic_native_gate_code;
static volatile LONG diagnostic_transition_failure_bits;
static volatile LONG diagnostic_transition_requested_value;
static volatile LONG diagnostic_transition_previous_value;
static volatile LONG diagnostic_transition_stored_value;
static volatile LONG diagnostic_transition_finish_condition_bits;
static volatile LONG diagnostic_transition_self;
static volatile LONG diagnostic_transition_cint_owner;
static volatile LONG diagnostic_transition_known_this;
static volatile LONG diagnostic_transition_known_owner;
static volatile LONG diagnostic_last_special_clear_event_sequence;
static volatile LONG diagnostic_last_special_clear_reason;
static volatile LONG diagnostic_last_special_clear_object;
static volatile LONG diagnostic_last_special_clear_node;
static volatile LONG diagnostic_last_special_clear_target_plus_one;
static volatile LONG diagnostic_last_special_clear_materializer_sequence;
static volatile LONG diagnostic_last_special_clear_object_generation;
static volatile LONG diagnostic_last_special_clear_route_index_plus_one;
static volatile LONG diagnostic_last_special_clear_cref_sequence;
static volatile LONG diagnostic_last_special_clear_language_sequence;
static volatile LONG diagnostic_special_materializer_persistent;
static volatile LONG diagnostic_special_materializer_node_exact;
static volatile LONG diagnostic_special_materializer_route_exact;
static volatile LONG diagnostic_special_materializer_route_index_plus_one;
static volatile LONG diagnostic_special_materializer_raw_handle;
static volatile LONG diagnostic_special_materializer_cref_sequence;
static volatile LONG diagnostic_special_materializer_language_sequence;
static volatile LONG diagnostic_special_note_active_found;
static volatile LONG diagnostic_special_note_active_route_exact;
static volatile LONG diagnostic_special_cref_attempt_sequence;
static volatile LONG diagnostic_special_cref_attempt_graph_active;
static volatile LONG diagnostic_special_cref_attempt_read_exact;
static volatile LONG diagnostic_special_cref_attempt_bind_exact;
static volatile LONG diagnostic_special_cref_attempt_graph_root;
static volatile LONG diagnostic_special_cref_attempt_graph_epoch;
static volatile LONG diagnostic_special_cref_attempt_language_sequence;
static volatile LONG diagnostic_special_cref_attempt_cref_self;
static volatile LONG diagnostic_special_cref_attempt_resolved_node;
static volatile LONG diagnostic_special_cref_attempt_raw_handle;
static volatile LONG diagnostic_special_cref_attempt_route_index_plus_one;
/* One-process diagnostic ladder for the exact target materializer:
 * 0x0001 persistent route, 0x0002 node invariants, 0x0004 CRef sequence,
 * 0x0008 route exact, 0x0010 pushed, 0x0020 target load observed,
 * 0x0040 active materializer found, 0x0080 load-time route exact,
 * 0x0100 pending recorded, 0x0200 popped, 0x0400 returned object exact,
 * 0x0800 completion tuple exact, 0x1000 object committed,
 * 0x2000 graph completion persisted, 0x4000 durable CRef revalidated,
 * 0x10000 target surface entered, 0x20000 object binding snapshotted,
 * 0x40000 binding header/node/payload exact, 0x80000 binding route exact,
 * 0x100000 binding table exact, 0x200000 binding CRef exact,
 * 0x400000 full binding revalidation exact, 0x800000 surface pushed,
 * 0x1000000 decode surface found, 0x2000000 decode binding exact,
 * 0x4000000 authorization lease acquired, 0x8000000 decode allowed. */
static volatile LONG diagnostic_pipeline_flags;
#endif

static volatile LONG initialized;
static volatile LONG initializing;
static volatile LONG shutting_down;
static volatile LONG restoring;
static volatile LONG hooks_restored_exact = 1;
static volatile LONG hook_inflight;
static volatile LONG fatal_latch;
static volatile LONG telemetry_generation;
static volatile LONG language_state = PHOTON_V6_PF_SELECTOR_LANGUAGE_UNKNOWN;
static volatile LONG language_state_sequence;
static volatile LONG graph_epoch_sequence;
static volatile LONG graph_enter_sequence;
static volatile LONG cref_identity_sequence;
static volatile LONG materializer_sequence;
static volatile LONG object_generation_sequence;
static volatile LONG surface_sequence;
static volatile LONG language_transition_inflight;
static volatile LONG language_transition_owner_tid;
static volatile LONG lifecycle_admission_revoked;
static volatile LONG translation_write_leases;
static volatile LONG ordinary_write_leases;
static volatile LONG special_write_leases;
static volatile LONG ordinary_lease_sequence;
static volatile LONG mutation_journal_entries;
static volatile LONG restored_hook_count;
static volatile LONG module_pinned;
static volatile LONG first_mutation_committed;
static volatile LONG hooks_retained_until_process_exit;
static volatile LONG semantic_gate_disabled;
static void *volatile language_cint_this;
static void *volatile language_cint_owner;
static volatile LONG language_scan_inflight;
static volatile LONG language_scan_last_tick;

#define DECLARE_COUNTER(name) static volatile LONG name
DECLARE_COUNTER(language_bootstrap_exact_events);
DECLARE_COUNTER(language_bootstrap_conflict_rejects);
DECLARE_COUNTER(language_setter_exact_events);
DECLARE_COUNTER(global_language_generation_purges);
DECLARE_COUNTER(graph_begin_events);
DECLARE_COUNTER(graph_end_events);
DECLARE_COUNTER(graph_supersession_purges);
DECLARE_COUNTER(graph_identity_rejects);
DECLARE_COUNTER(cref_identity_events);
DECLARE_COUNTER(cref_identity_rejects);
DECLARE_COUNTER(materializer_entry_events);
DECLARE_COUNTER(materializer_load_candidates);
DECLARE_COUNTER(materializer_fresh_commits);
DECLARE_COUNTER(materializer_cached_commits);
DECLARE_COUNTER(materializer_identity_rejects);
DECLARE_COUNTER(payload_sha256_rejects);
DECLARE_COUNTER(state0_translation_endpoint_rejects);
DECLARE_COUNTER(c07_all_provider_rejects);
DECLARE_COUNTER(exact_surface_entries);
DECLARE_COUNTER(surface_identity_rejects);
DECLARE_COUNTER(exact_decode_queries);
DECLARE_COUNTER(decode_identity_rejects);
DECLARE_COUNTER(translation_special57_allows);
DECLARE_COUNTER(stale_generation_rejects);
DECLARE_COUNTER(cross_thread_rejects);
DECLARE_COUNTER(ordinary_lease_acquires);
DECLARE_COUNTER(ordinary_lease_rejects);
DECLARE_COUNTER(ordinary_lease_releases);
DECLARE_COUNTER(ordinary_lease_generation_rejects);
#undef DECLARE_COUNTER

#ifdef PHOTON_V6_PF_SELECTOR_TEST_HOOKS
static int test_target_override;
static int test_target_index;
static BYTE *test_image;
static void *test_object;
static void *test_node;
static volatile LONG test_force_post_install_census_failure;
static volatile LONG test_force_exact_digest_reject;
static volatile LONG test_no_hot_lifecycle;
static volatile LONG test_fail_install_before_ordinal = -1;
static volatile LONG test_lifecycle_claim_pause_enabled;
static volatile LONG test_lifecycle_claim_pause_reached;
static volatile LONG test_lifecycle_claim_pause_release;
static volatile LONG test_finish_transition_pause_enabled;
static volatile LONG test_finish_transition_pause_reached;
static volatile LONG test_finish_transition_pause_release;
#endif

static int no_hot_lifecycle_enabled(void) {
#ifdef PHOTON_V6_PF_SELECTOR_TEST_HOOKS
    return InterlockedCompareExchange(&test_no_hot_lifecycle,0,0)!=0;
#else
    return 1;
#endif
}

static int selector_semantics_enabled(void) {
    return InterlockedCompareExchange(&initialized,0,0)!=0 &&
        !InterlockedCompareExchange(&shutting_down,0,0) &&
        !InterlockedCompareExchange(&fatal_latch,0,0) &&
        !InterlockedCompareExchange(&semantic_gate_disabled,0,0) &&
        !InterlockedCompareExchange(&lifecycle_admission_revoked,0,0);
}

static void pin_adapter_module_or_failfast(void);
static void mark_first_mutation_committed(void);
static int enter_no_hot_retained_state(int fatal_failure);
static void lifecycle_ambiguity_failfast(void);

static uintptr_t __attribute__((cdecl,noinline,used))
hook_cref_read_counted(void *, void *, uint32_t);
static uintptr_t __attribute__((cdecl,noinline,used))
hook_graph_root_serialize_counted(void *, void *);
static uintptr_t __attribute__((cdecl,noinline,used))
hook_resource_materializer_counted(void *);
static uintptr_t __attribute__((cdecl,noinline,used))
hook_cint_setter_dispatch(void *, uint32_t, uintptr_t);
static int image_language_live_candidate_exact(
    void *object, void **owner_out, LONG *value_out);

static uintptr_t __attribute__((naked,noinline,used)) hook_cref_read_abi(void) {
    __asm__ volatile(
        "lock incl _hook_inflight\n\t"
        "pushl 8(%esp)\n\t"
        "pushl 8(%esp)\n\t"
        "pushl %ecx\n\t"
        "call _hook_cref_read_counted\n\t"
        "addl $12,%esp\n\t"
        "lock decl _hook_inflight\n\t"
        "ret $8\n\t");
}

static uintptr_t __attribute__((naked,noinline,used))
hook_graph_root_serialize_abi(void) {
    __asm__ volatile(
        "lock incl _hook_inflight\n\t"
        "pushl 4(%esp)\n\t"
        "pushl %ecx\n\t"
        "call _hook_graph_root_serialize_counted\n\t"
        "addl $8,%esp\n\t"
        "lock decl _hook_inflight\n\t"
        "ret $4\n\t");
}

static uintptr_t __attribute__((naked,noinline,used))
hook_resource_materializer_abi(void) {
    __asm__ volatile(
        "lock incl _hook_inflight\n\t"
        "pushl %ecx\n\t"
        "call _hook_resource_materializer_counted\n\t"
        "addl $4,%esp\n\t"
        "lock decl _hook_inflight\n\t"
        "ret\n\t");
}

static uintptr_t __attribute__((naked,noinline,used))
hook_cint_setter_abi(void) {
    /* Preserve the exact VM owner carried in EDI at callsite 0xC3DE3.
     * A normal C prologue is not allowed here: the optimizer may repurpose
     * EDI before an inline read.  The dispatch receives ordinary cdecl
     * arguments (self, value, entry_edi), then this shim mirrors the native
     * thiscall callee's four-byte stack cleanup. */
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
static int cref_binding_exact_locked(const RouteFrame *expected);

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
    InterlockedExchange(&fatal_latch,1);
    telemetry_end();
}

#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
typedef struct DiagnosticTransitionFailureRecord {
    uint32_t magic;
    uint32_t version;
    uint32_t failure_bits;
    uint32_t process_id;
    uint32_t thread_id;
    int32_t language_state;
    uint32_t language_sequence;
    uint32_t transition_inflight;
    uint32_t transition_owner_tid;
    uint32_t translation_leases;
    uint32_t ordinary_leases;
    uint32_t special_leases;
    uint32_t graph_begin_events;
    uint32_t graph_end_events;
    uint32_t requested_value;
    uint32_t previous_value;
    uint32_t stored_value;
    uint32_t finish_condition_bits;
    uint32_t self_pointer;
    uint32_t cint_owner;
    uint32_t known_this;
    uint32_t known_owner;
} DiagnosticTransitionFailureRecord;

typedef struct DiagnosticMaterializerFailureRecord {
    uint32_t magic;
    uint32_t version;
    uint32_t process_id;
    uint32_t thread_id;
    int32_t language_state_at_enter;
    uint32_t language_sequence_at_enter;
    int32_t language_state_current;
    uint32_t language_sequence_current;
    uint32_t condition_bits;
    uint32_t node;
    uint32_t object_before;
    uint32_t object_after;
    uint32_t object_returned;
    uint32_t completed_object_before;
    uint32_t completed_pending_object;
    uint32_t completed_nested_load_count;
    uint32_t completed_pending_exact;
    int32_t completed_pending_target;
    uint32_t completed_node_invariants_exact;
    uint32_t pushed;
    uint32_t popped;
    uint32_t identity_exact;
    int32_t route_index;
    uint32_t route_raw_handle;
    uint32_t route_cref_identity_sequence;
    uint32_t materializer_sequence;
} DiagnosticMaterializerFailureRecord;

static void diagnostic_persist_transition_failure(void) {
    static const WCHAR suffix[]=
        L"photon_pf_transition_failure.v1.bin";
    DiagnosticTransitionFailureRecord record;
    WCHAR path[MAX_PATH];
    DWORD prefix,done=0;
    HANDLE file;
    prefix=GetTempPathW(MAX_PATH,path);
    if (!prefix || prefix>=MAX_PATH ||
        prefix+sizeof(suffix)/sizeof(suffix[0])>MAX_PATH)
        return;
    memcpy(path+prefix,suffix,sizeof(suffix));
    memset(&record,0,sizeof(record));
    record.magic=UINT32_C(0x50465446);
    record.version=2;
    record.failure_bits=(uint32_t)InterlockedCompareExchange(
        &diagnostic_transition_failure_bits,0,0);
    record.process_id=GetCurrentProcessId();
    record.thread_id=GetCurrentThreadId();
    record.language_state=(int32_t)InterlockedCompareExchange(
        &language_state,0,0);
    record.language_sequence=(uint32_t)InterlockedCompareExchange(
        &language_state_sequence,0,0);
    record.transition_inflight=(uint32_t)InterlockedCompareExchange(
        &language_transition_inflight,0,0);
    record.transition_owner_tid=(uint32_t)InterlockedCompareExchange(
        &language_transition_owner_tid,0,0);
    record.translation_leases=(uint32_t)InterlockedCompareExchange(
        &translation_write_leases,0,0);
    record.ordinary_leases=(uint32_t)InterlockedCompareExchange(
        &ordinary_write_leases,0,0);
    record.special_leases=(uint32_t)InterlockedCompareExchange(
        &special_write_leases,0,0);
    record.graph_begin_events=(uint32_t)InterlockedCompareExchange(
        &graph_begin_events,0,0);
    record.graph_end_events=(uint32_t)InterlockedCompareExchange(
        &graph_end_events,0,0);
    record.requested_value=(uint32_t)InterlockedCompareExchange(
        &diagnostic_transition_requested_value,0,0);
    record.previous_value=(uint32_t)InterlockedCompareExchange(
        &diagnostic_transition_previous_value,0,0);
    record.stored_value=(uint32_t)InterlockedCompareExchange(
        &diagnostic_transition_stored_value,0,0);
    record.finish_condition_bits=(uint32_t)InterlockedCompareExchange(
        &diagnostic_transition_finish_condition_bits,0,0);
    record.self_pointer=(uint32_t)InterlockedCompareExchange(
        &diagnostic_transition_self,0,0);
    record.cint_owner=(uint32_t)InterlockedCompareExchange(
        &diagnostic_transition_cint_owner,0,0);
    record.known_this=(uint32_t)InterlockedCompareExchange(
        &diagnostic_transition_known_this,0,0);
    record.known_owner=(uint32_t)InterlockedCompareExchange(
        &diagnostic_transition_known_owner,0,0);
    file=CreateFileW(path,GENERIC_WRITE,FILE_SHARE_READ,NULL,CREATE_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,NULL);
    if (file==INVALID_HANDLE_VALUE) return;
    (void)WriteFile(file,&record,(DWORD)sizeof(record),&done,NULL);
    (void)FlushFileBuffers(file);
    CloseHandle(file);
}

static void diagnostic_persist_materializer_failure(
    const ActiveMaterialization *completed, void *node, void *object_before,
    void *object_after, void *object, LONG state, LONG sequence,
    int pushed, int popped, int identity_exact) {
    static const WCHAR suffix[]=
        L"photon_pf_materializer_failure.v1.bin";
    DiagnosticMaterializerFailureRecord record;
    WCHAR path[MAX_PATH];
    DWORD prefix,done=0;
    HANDLE file;
    uint32_t conditions=0;
    prefix=GetTempPathW(MAX_PATH,path);
    if (!prefix || prefix>=MAX_PATH ||
        prefix+sizeof(suffix)/sizeof(suffix[0])>MAX_PATH)
        return;
    memcpy(path+prefix,suffix,sizeof(suffix));
    memset(&record,0,sizeof(record));
    if (object) conditions|=UINT32_C(0x0001);
    if (popped) conditions|=UINT32_C(0x0002);
    if (object_after==object) conditions|=UINT32_C(0x0004);
    if (state==InterlockedCompareExchange(&language_state,0,0))
        conditions|=UINT32_C(0x0008);
    if (sequence==InterlockedCompareExchange(&language_state_sequence,0,0))
        conditions|=UINT32_C(0x0010);
    if (completed && completed->node_invariants_exact)
        conditions|=UINT32_C(0x0020);
    if (!object_before) conditions|=UINT32_C(0x0040);
    if (object_before==object) conditions|=UINT32_C(0x0080);
    if (completed && completed->nested_load_count==0)
        conditions|=UINT32_C(0x0100);
    if (completed && completed->nested_load_count==1)
        conditions|=UINT32_C(0x0200);
    if (completed && completed->pending.object==object)
        conditions|=UINT32_C(0x0400);
    if (completed && completed->pending.exact)
        conditions|=UINT32_C(0x0800);
    if (completed && completed->pending.target_index>=0 &&
        completed->pending.target_index<6)
        conditions|=UINT32_C(0x1000);
    if (identity_exact) conditions|=UINT32_C(0x2000);
    record.magic=UINT32_C(0x50464D46);
    record.version=1;
    record.process_id=GetCurrentProcessId();
    record.thread_id=GetCurrentThreadId();
    record.language_state_at_enter=(int32_t)state;
    record.language_sequence_at_enter=(uint32_t)sequence;
    record.language_state_current=(int32_t)InterlockedCompareExchange(
        &language_state,0,0);
    record.language_sequence_current=(uint32_t)InterlockedCompareExchange(
        &language_state_sequence,0,0);
    record.condition_bits=conditions;
    record.node=(uint32_t)(uintptr_t)node;
    record.object_before=(uint32_t)(uintptr_t)object_before;
    record.object_after=(uint32_t)(uintptr_t)object_after;
    record.object_returned=(uint32_t)(uintptr_t)object;
    if (completed) {
        record.completed_object_before=(uint32_t)(uintptr_t)
            completed->object_before;
        record.completed_pending_object=(uint32_t)(uintptr_t)
            completed->pending.object;
        record.completed_nested_load_count=(uint32_t)
            completed->nested_load_count;
        record.completed_pending_exact=(uint32_t)completed->pending.exact;
        record.completed_pending_target=(int32_t)
            completed->pending.target_index;
        record.completed_node_invariants_exact=(uint32_t)
            completed->node_invariants_exact;
        record.route_index=(int32_t)completed->route.route_index;
        record.route_raw_handle=completed->route.raw_handle;
        record.route_cref_identity_sequence=(uint32_t)
            completed->route.cref_identity_sequence;
        record.materializer_sequence=(uint32_t)completed->sequence;
    }
    record.pushed=(uint32_t)pushed;
    record.popped=(uint32_t)popped;
    record.identity_exact=(uint32_t)identity_exact;
    file=CreateFileW(path,GENERIC_WRITE,FILE_SHARE_READ,NULL,CREATE_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,NULL);
    if (file==INVALID_HANDLE_VALUE) return;
    (void)WriteFile(file,&record,(DWORD)sizeof(record),&done,NULL);
    (void)FlushFileBuffers(file);
    CloseHandle(file);
}
#endif

static int range_readable(const void *pointer, SIZE_T count) {
    uintptr_t at=(uintptr_t)pointer,end=at+count;
    if (!pointer || !count || end<at) return 0;
    while (at<end) {
        MEMORY_BASIC_INFORMATION info;
        uintptr_t next;
        if (!VirtualQuery((const void *)at,&info,sizeof(info)) ||
            info.State!=MEM_COMMIT || (info.Protect&(PAGE_NOACCESS|PAGE_GUARD)))
            return 0;
        next=(uintptr_t)info.BaseAddress+info.RegionSize;
        if (next<=at) return 0;
        at=next<end?next:end;
    }
    return 1;
}

static int page_protection_exact(const void *pointer, SIZE_T count,
    DWORD expected) {
    uintptr_t at=(uintptr_t)pointer,end=at+count;
    if (!pointer || !count || !expected || end<at) return 0;
    while (at<end) {
        MEMORY_BASIC_INFORMATION info;
        uintptr_t next;
        if (!VirtualQuery((const void *)at,&info,sizeof(info)) ||
            info.State!=MEM_COMMIT || info.Protect!=expected) return 0;
        next=(uintptr_t)info.BaseAddress+info.RegionSize;
        if (next<=at) return 0;
        at=next<end?next:end;
    }
    return 1;
}

static uint32_t safe_u32(const void *base, SIZE_T offset) {
    const BYTE *at=(const BYTE *)base+offset;
    return range_readable(at,4)?*(const uint32_t *)at:UINT32_MAX;
}

static uint16_t safe_u16(const void *base, SIZE_T offset) {
    const BYTE *at=(const BYTE *)base+offset;
    return range_readable(at,2)?*(const uint16_t *)at:UINT16_MAX;
}

static uintptr_t safe_pointer(const void *base, SIZE_T offset) {
    const BYTE *at=(const BYTE *)base+offset;
    return range_readable(at,sizeof(void *))?
        (uintptr_t)*(void * const *)at:0;
}

static ArchiveSample sample_archive(void *archive) {
    ArchiveSample sample;
    memset(&sample,0,sizeof(sample));
    sample.mode=safe_u32(archive,0x20);
    sample.cursor=safe_pointer(archive,0x30);
    sample.end=safe_pointer(archive,0x34);
    sample.counter=safe_u32(archive,0x3C);
    return sample;
}

static DWORD main_rva(uintptr_t value) {
    uintptr_t base=(uintptr_t)main_base;
    return value>=base && value<base+PF_SIZE_OF_IMAGE?
        (DWORD)(value-base):UINT32_MAX;
}

static uint64_t fnv1a64(const BYTE *data, uint32_t size) {
    uint64_t hash=UINT64_C(14695981039346656037);
    uint32_t index;
    for (index=0;index<size;++index) {
        hash^=data[index];
        hash*=UINT64_C(1099511628211);
    }
    return hash;
}

typedef struct Sha256Context {
    uint32_t state[8];
    uint64_t bits;
    BYTE block[64];
    size_t used;
} Sha256Context;

static uint32_t sha256_rotr(uint32_t value, unsigned count) {
    return (value>>count)|(value<<(32U-count));
}

static void sha256_transform(Sha256Context *context, const BYTE block[64]) {
    static const uint32_t constants[64] = {
        0x428A2F98U,0x71374491U,0xB5C0FBCFU,0xE9B5DBA5U,0x3956C25BU,0x59F111F1U,0x923F82A4U,0xAB1C5ED5U,
        0xD807AA98U,0x12835B01U,0x243185BEU,0x550C7DC3U,0x72BE5D74U,0x80DEB1FEU,0x9BDC06A7U,0xC19BF174U,
        0xE49B69C1U,0xEFBE4786U,0x0FC19DC6U,0x240CA1CCU,0x2DE92C6FU,0x4A7484AAU,0x5CB0A9DCU,0x76F988DAU,
        0x983E5152U,0xA831C66DU,0xB00327C8U,0xBF597FC7U,0xC6E00BF3U,0xD5A79147U,0x06CA6351U,0x14292967U,
        0x27B70A85U,0x2E1B2138U,0x4D2C6DFCU,0x53380D13U,0x650A7354U,0x766A0ABBU,0x81C2C92EU,0x92722C85U,
        0xA2BFE8A1U,0xA81A664BU,0xC24B8B70U,0xC76C51A3U,0xD192E819U,0xD6990624U,0xF40E3585U,0x106AA070U,
        0x19A4C116U,0x1E376C08U,0x2748774CU,0x34B0BCB5U,0x391C0CB3U,0x4ED8AA4AU,0x5B9CCA4FU,0x682E6FF3U,
        0x748F82EEU,0x78A5636FU,0x84C87814U,0x8CC70208U,0x90BEFFFAU,0xA4506CEBU,0xBEF9A3F7U,0xC67178F2U
    };
    uint32_t words[64];
    uint32_t a,b,c,d,e,f,g,h;
    size_t index;
    for (index=0;index<16;++index) {
        words[index]=((uint32_t)block[index*4]<<24)|
            ((uint32_t)block[index*4+1]<<16)|
            ((uint32_t)block[index*4+2]<<8)|(uint32_t)block[index*4+3];
    }
    for (index=16;index<64;++index) {
        uint32_t s0=sha256_rotr(words[index-15],7)^
            sha256_rotr(words[index-15],18)^(words[index-15]>>3);
        uint32_t s1=sha256_rotr(words[index-2],17)^
            sha256_rotr(words[index-2],19)^(words[index-2]>>10);
        words[index]=words[index-16]+s0+words[index-7]+s1;
    }
    a=context->state[0]; b=context->state[1]; c=context->state[2];
    d=context->state[3]; e=context->state[4]; f=context->state[5];
    g=context->state[6]; h=context->state[7];
    for (index=0;index<64;++index) {
        uint32_t s1=sha256_rotr(e,6)^sha256_rotr(e,11)^sha256_rotr(e,25);
        uint32_t choice=(e&f)^((~e)&g);
        uint32_t temp1=h+s1+choice+constants[index]+words[index];
        uint32_t s0=sha256_rotr(a,2)^sha256_rotr(a,13)^sha256_rotr(a,22);
        uint32_t majority=(a&b)^(a&c)^(b&c);
        uint32_t temp2=s0+majority;
        h=g; g=f; f=e; e=d+temp1; d=c; c=b; b=a; a=temp1+temp2;
    }
    context->state[0]+=a; context->state[1]+=b;
    context->state[2]+=c; context->state[3]+=d;
    context->state[4]+=e; context->state[5]+=f;
    context->state[6]+=g; context->state[7]+=h;
}

static void sha256_digest(const BYTE *data, size_t size, BYTE output[32]) {
    Sha256Context context;
    size_t index;
    memset(&context,0,sizeof(context));
    context.state[0]=0x6A09E667U; context.state[1]=0xBB67AE85U;
    context.state[2]=0x3C6EF372U; context.state[3]=0xA54FF53AU;
    context.state[4]=0x510E527FU; context.state[5]=0x9B05688CU;
    context.state[6]=0x1F83D9ABU; context.state[7]=0x5BE0CD19U;
    while (size) {
        size_t take=64-context.used;
        if (take>size) take=size;
        memcpy(context.block+context.used,data,take);
        context.used+=take; data+=take; size-=take;
        context.bits+=(uint64_t)take*8U;
        if (context.used==64) {
            sha256_transform(&context,context.block);
            context.used=0;
        }
    }
    context.block[context.used++]=0x80;
    if (context.used>56) {
        memset(context.block+context.used,0,64-context.used);
        sha256_transform(&context,context.block);
        context.used=0;
    }
    memset(context.block+context.used,0,56-context.used);
    for (index=0;index<8;++index)
        context.block[63-index]=(BYTE)(context.bits>>(index*8));
    sha256_transform(&context,context.block);
    for (index=0;index<8;++index) {
        output[index*4]=(BYTE)(context.state[index]>>24);
        output[index*4+1]=(BYTE)(context.state[index]>>16);
        output[index*4+2]=(BYTE)(context.state[index]>>8);
        output[index*4+3]=(BYTE)context.state[index];
    }
}

static int digest_matches_hex(const BYTE digest[32], const char *hex) {
    static const char digits[]="0123456789ABCDEF";
    size_t index;
    if (!digest || !hex || strlen(hex)!=64) return 0;
    for (index=0;index<32;++index)
        if (hex[index*2]!=digits[digest[index]>>4] ||
            hex[index*2+1]!=digits[digest[index]&15]) return 0;
    return 1;
}

static int find_route(uint32_t raw_handle) {
    size_t index;
    for (index=0;index<sizeof(routes)/sizeof(routes[0]);++index)
        if (routes[index].raw_handle==raw_handle) return (int)index;
    return -1;
}

static int route_table_unique(void) {
    size_t left,right;
    for (left=0;left<sizeof(routes)/sizeof(routes[0]);++left) {
        if (!routes[left].raw_handle || !routes[left].static_object_handle ||
            !routes[left].static_archive_ordinal ||
            routes[left].group_target_index<0 ||
            routes[left].group_target_index>=6) return 0;
        for (right=left+1;right<sizeof(routes)/sizeof(routes[0]);++right)
            if (routes[left].raw_handle==routes[right].raw_handle) return 0;
    }
    return 1;
}

static int find_target_exact(uint32_t bytes, uint64_t hash,
    const BYTE digest[32]) {
    size_t index;
#ifdef PHOTON_V6_PF_SELECTOR_TEST_HOOKS
    static const BYTE abc_sha[32] = {
        0xBA,0x78,0x16,0xBF,0x8F,0x01,0xCF,0xEA,
        0x41,0x41,0x40,0xDE,0x5D,0xAE,0x22,0x23,
        0xB0,0x03,0x61,0xA3,0x96,0x17,0x7A,0x9C,
        0xB4,0x10,0xFF,0x61,0xF2,0x00,0x15,0xAD
    };
    if (InterlockedCompareExchange(&test_force_exact_digest_reject,0,0))
        return -1;
    if (test_target_override && bytes==3 &&
        hash==UINT64_C(0xE71FA2190541574B) &&
        memcmp(digest,abc_sha,32)==0 && test_target_index>=0 &&
        test_target_index<6) return test_target_index;
#endif
    for (index=0;index<sizeof(targets)/sizeof(targets[0]);++index)
        if (targets[index].payload_bytes==bytes &&
            targets[index].payload_fnv1a64==hash &&
            digest_matches_hex(digest,targets[index].payload_sha256))
            return (int)index;
    return -1;
}

/* This is classification for a deny tombstone only.  It can never authorize
 * a binding: the full SHA-256 predicate above remains mandatory for every
 * commit.  Size+FNV identifies a tracked special transport whose digest has
 * failed and therefore must not be allowed to fall through to ordinary. */
static int find_target_deny_tombstone(uint32_t bytes, uint64_t hash) {
    int found=-1;
    size_t index;
#ifdef PHOTON_V6_PF_SELECTOR_TEST_HOOKS
    if (test_target_override && bytes==3 &&
        hash==UINT64_C(0xE71FA2190541574B) && test_target_index>=0 &&
        test_target_index<6) return test_target_index;
#endif
    for (index=0;index<sizeof(targets)/sizeof(targets[0]);++index) {
        if (targets[index].payload_bytes!=bytes ||
            targets[index].payload_fnv1a64!=hash) continue;
        if (found>=0) return -1;
        found=(int)index;
    }
    return found;
}

static int route_is_translation_provider(const RouteDef *route,
    int target_index) {
    int translation_role;
    if (!route || target_index<0 || target_index>=6 ||
        route->target_index!=target_index || !route->source_asset_id ||
        !route->context_identity_key) return 0;
    translation_role=route->role==ROUTE_TRANSLATION_PRIMARY ||
        route->role==ROUTE_TRANSLATION_SECONDARY;
    if (!translation_role) return 0;
    if (target_index!=5) return 1;
    /* Collision-07 is not a generally shareable target.  Runtime evidence
     * proves only the exact Translation primary materializer used by the
     * inactive selected Auto-Read button.  Keep the alias and both Japanese
     * providers fail-closed even though they reach the same physical payload. */
    return route->role==ROUTE_TRANSLATION_PRIMARY &&
        route->raw_handle==UINT32_C(0x0E6B0654) &&
        strcmp(route->source_asset_id,"pf:rio000:0x1cc0ea48")==0 &&
        strcmp(route->context_identity_key,
            "0x0000BCD8:0x000009D1:0x0E6B0654:OPTIONS_AUTOPLAY_VM_PRIMARY")==0;
}

static uint32_t route_provider_role(const RouteDef *route) {
    if (!route) return PHOTON_V6_PF_SELECTOR_PROVIDER_NONE;
    if (route->role==ROUTE_TRANSLATION_PRIMARY)
        return PHOTON_V6_PF_SELECTOR_PROVIDER_TRANSLATION_PRIMARY;
    if (route->role==ROUTE_TRANSLATION_SECONDARY)
        return PHOTON_V6_PF_SELECTOR_PROVIDER_TRANSLATION_SECONDARY;
    if (route->role==ROUTE_JAPANESE_PRIMARY)
        return PHOTON_V6_PF_SELECTOR_PROVIDER_JAPANESE_PRIMARY;
    if (route->role==ROUTE_JAPANESE_SECONDARY)
        return PHOTON_V6_PF_SELECTOR_PROVIDER_JAPANESE_SECONDARY;
    if (route->role==ROUTE_C07_FORBIDDEN)
        return PHOTON_V6_PF_SELECTOR_PROVIDER_C07_FORBIDDEN;
    return PHOTON_V6_PF_SELECTOR_PROVIDER_NONE;
}

static int resource_node_kind_exact(uint32_t kind) {
    return kind==1 || kind==2 || kind==3 || kind==4 || kind==5;
}

static int resource_node_invariants_exact(void *node, uint32_t *kind_out) {
    uint32_t kind=safe_u32(node,0x18);
    void *descriptor=main_base+PF_CR6TI_TYPE_DESCRIPTOR_RVA;
    if (kind_out) *kind_out=kind;
    if (!main_base || !range_readable(node,0x2C) ||
        safe_pointer(node,0x14)!=(uintptr_t)descriptor ||
        safe_pointer(descriptor,0)!=(uintptr_t)(main_base+PF_CR6TI_NAME_METADATA_RVA) ||
        safe_u32(descriptor,4)!=0x60 ||
        safe_u32(descriptor,8)!=UINT32_C(0xE0000004) ||
        safe_pointer(descriptor,0x0C)!=(uintptr_t)(main_base+PF_CR6TI_FACTORY_RVA) ||
        safe_pointer(descriptor,0x10)!=(uintptr_t)(main_base+PF_CR6TI_TYPE_FUNCTION_RVA))
        return 0;
    return resource_node_kind_exact(kind);
}

static int cr6_object_invariants_exact(void *object) {
    return main_base && object &&
        object!=(void *)(main_base+PF_NULL_RESOURCE_SENTINEL_RVA) &&
        range_readable(object,0x60) &&
        safe_pointer(object,0)==
            (uintptr_t)(main_base+PF_CR6TI_PRIMARY_VTABLE_RVA) &&
        safe_pointer(object,0x0C)==
            (uintptr_t)(main_base+PF_CR6TI_SECONDARY_VTABLE_RVA);
}

static int lease_census_exact_locked(void) {
    LONG total=InterlockedCompareExchange(&translation_write_leases,0,0);
    LONG ordinary=InterlockedCompareExchange(&ordinary_write_leases,0,0);
    LONG special=InterlockedCompareExchange(&special_write_leases,0,0);
    size_t index;
    LONG active_ordinary=0,active_special=0;
    for (index=0;index<MAX_ORDINARY_WRITE_LEASES;++index)
        if (ordinary_write_lease_slots[index].active) active_ordinary++;
    for (index=0;index<MAX_ACTIVE_SURFACES;++index) {
        ActiveSurface *surface=&active_surfaces[index];
        if (!surface->authorization_lease) continue;
        if (!surface->active || !surface->tid || surface->sequence<=0 ||
            !surface->binding.active) return 0;
        active_special++;
    }
    return total>=0 && ordinary>=0 && special>=0 &&
        total==ordinary+special && ordinary==active_ordinary &&
        special==active_special;
}

static int current_thread_owns_write_lease_locked(void) {
    DWORD tid=GetCurrentThreadId();
    size_t index;
    for (index=0;index<MAX_ORDINARY_WRITE_LEASES;++index)
        if (ordinary_write_lease_slots[index].active &&
            ordinary_write_lease_slots[index].tid==tid) return 1;
    for (index=0;index<MAX_ACTIVE_SURFACES;++index)
        if (active_surfaces[index].active &&
            active_surfaces[index].authorization_lease &&
            active_surfaces[index].tid==tid) return 1;
    return 0;
}

static int special_lease_acquire_locked(ActiveSurface *surface) {
    if (InterlockedCompareExchange(&lifecycle_admission_revoked,0,0) ||
        InterlockedCompareExchange(&language_transition_inflight,0,0))
        return 0;
    if (!surface || !surface->active || !surface->tid ||
        surface->sequence<=0 || !surface->binding.active ||
        surface->authorization_lease) {
        set_fatal();
        return 0;
    }
    surface->authorization_lease=1;
    InterlockedIncrement(&special_write_leases);
    InterlockedIncrement(&translation_write_leases);
    if (!lease_census_exact_locked()) {
        InterlockedDecrement(&translation_write_leases);
        InterlockedDecrement(&special_write_leases);
        surface->authorization_lease=0;
        set_fatal();
        return 0;
    }
    return 1;
}

static int special_lease_release_locked(ActiveSurface *surface) {
    if (!surface || !surface->active || !surface->authorization_lease ||
        !surface->tid || surface->sequence<=0 || !surface->binding.active) {
        set_fatal();
        return 0;
    }
    if (InterlockedCompareExchange(&special_write_leases,0,0)<=0 ||
        InterlockedCompareExchange(&translation_write_leases,0,0)<=0) {
        set_fatal();
        return 0;
    }
    surface->authorization_lease=0;
    InterlockedDecrement(&special_write_leases);
    InterlockedDecrement(&translation_write_leases);
    if (!lease_census_exact_locked()) {
        set_fatal();
        return 0;
    }
    return 1;
}

static int purge_graph_epoch_locked(DWORD tid, void *graph_root, LONG epoch) {
    int active_scope_seen=0;
    size_t index;
    /* GraphEpochState is only the serializer's transient stack/archive.  A
     * completed CRef is a longer-lived engine object: PF can materialize its
     * still-selected node after a later sibling graph has superseded this
     * archive entry.  Retain that completed proof; a new exact CRef for the
     * same self/node and endpoint, or a changed live tagged pointer revokes
     * it.  Language transitions make it dormant until its captured endpoint
     * returns.  An uncompleted CRef may never escape its graph. */
    for (index=0;index<MAX_CREF_BINDINGS;++index)
        if (cref_bindings[index].active && cref_bindings[index].tid==tid &&
            cref_bindings[index].route.graph_root==graph_root &&
            cref_bindings[index].route.graph_epoch==epoch &&
            !cref_bindings[index].graph_completion_exact)
            memset(&cref_bindings[index],0,sizeof(cref_bindings[index]));
    for (index=0;index<MAX_OBJECT_BINDINGS;++index)
        if (object_bindings[index].active && object_bindings[index].tid==tid &&
            object_bindings[index].route.graph_root==graph_root &&
            object_bindings[index].route.graph_epoch==epoch)
            clear_object_binding_locked(
                object_bindings[index].object,
                object_bindings[index].resource_node,
                OBJECT_BINDING_CLEAR_GRAPH_PURGE);
    for (index=0;index<MAX_MATERIALIZATIONS;++index)
        if (active_materializations[index].active &&
            active_materializations[index].tid==tid &&
            active_materializations[index].route.graph_root==graph_root &&
            active_materializations[index].route.graph_epoch==epoch) {
            active_scope_seen=1;
            memset(&active_materializations[index],0,
                sizeof(active_materializations[index]));
        }
    for (index=0;index<MAX_ACTIVE_SURFACES;++index)
        if (active_surfaces[index].active && active_surfaces[index].tid==tid &&
            active_surfaces[index].binding.route.graph_root==graph_root &&
            active_surfaces[index].binding.route.graph_epoch==epoch) {
            active_scope_seen=1;
            if (active_surfaces[index].authorization_lease)
                (void)special_lease_release_locked(&active_surfaces[index]);
            memset(&active_surfaces[index],0,sizeof(active_surfaces[index]));
        }
    return active_scope_seen;
}

static LONG graph_root_begin(void *graph_root, void *archive) {
    GraphEpochState *state=NULL,*free_slot=NULL,*evict_slot=NULL;
    DWORD tid=GetCurrentThreadId();
    LONG maximum_nesting=0,new_nesting,generation,epoch=0;
    size_t index;
    AcquireSRWLockExclusive(&state_lock);
    generation=InterlockedCompareExchange(&language_state_sequence,0,0);
    if (InterlockedCompareExchange(&lifecycle_admission_revoked,0,0)!=0 ||
        InterlockedCompareExchange(&language_transition_inflight,0,0)!=0 ||
        InterlockedCompareExchange(&fatal_latch,0,0)!=0 ||
        InterlockedCompareExchange(&translation_write_leases,0,0)!=0)
        goto done;
    for (index=0;index<MAX_GRAPH_EPOCHS;++index) {
        GraphEpochState *at=&graph_epochs[index];
        if (at->active && at->tid==tid && at->graph_root==graph_root &&
            at->archive==archive && at->depth>0)
            state=at;
        if (at->active && at->tid==tid &&
            at->depth>0 && at->nesting_level>maximum_nesting)
            maximum_nesting=at->nesting_level;
    }
    if (state) {
        if (state->language_sequence==generation) state->depth++;
        else state=NULL;
        goto done;
    }
    new_nesting=maximum_nesting+1;
    /* A new graph at level N supersedes every completed sibling/descendant
     * at level >=N on this thread, irrespective of archive.  Active ancestors
     * remain the only legal parent stack. */
    for (index=0;index<MAX_GRAPH_EPOCHS;++index) {
        GraphEpochState *at=&graph_epochs[index];
        if (!at->active || at->tid!=tid || !at->completed || at->depth!=0 ||
            at->nesting_level<new_nesting) continue;
        if (purge_graph_epoch_locked(at->tid,at->graph_root,at->epoch))
            set_fatal();
        memset(at,0,sizeof(*at));
        telemetry_increment(&graph_supersession_purges);
    }
    for (index=0;index<MAX_GRAPH_EPOCHS;++index) {
        GraphEpochState *at=&graph_epochs[index];
        if (!at->active && !free_slot) free_slot=at;
        if (at->active && at->completed && at->depth==0 &&
            (!evict_slot || at->enter_sequence<evict_slot->enter_sequence))
            evict_slot=at;
    }
    state=free_slot?free_slot:evict_slot;
    if (state && state->active) {
        if (purge_graph_epoch_locked(state->tid,state->graph_root,state->epoch))
            set_fatal();
        telemetry_increment(&graph_supersession_purges);
    }
    if (state) {
        memset(state,0,sizeof(*state));
        state->tid=tid; state->archive=archive;
        state->graph_root=graph_root;
        state->epoch=InterlockedIncrement(&graph_epoch_sequence);
        state->enter_sequence=InterlockedIncrement(&graph_enter_sequence);
        state->nesting_level=new_nesting; state->depth=1;
        state->language_sequence=generation;
        MemoryBarrier();
        state->active=1;
    }
done:
    epoch=state?state->epoch:0;
    ReleaseSRWLockExclusive(&state_lock);
    if (!epoch) {
        telemetry_increment(&graph_identity_rejects);
        set_fatal();
    } else telemetry_increment(&graph_begin_events);
    return epoch;
}

static int graph_root_end(void *graph_root, void *archive, LONG epoch) {
    DWORD tid=GetCurrentThreadId();
    LONG generation;
    int exact=0;
    size_t left,right;
    AcquireSRWLockExclusive(&state_lock);
    generation=InterlockedCompareExchange(&language_state_sequence,0,0);
    if (InterlockedCompareExchange(&translation_write_leases,0,0)!=0)
        goto graph_end_done;
    for (left=0;left<MAX_GRAPH_EPOCHS;++left) {
        GraphEpochState *state=&graph_epochs[left];
        int unique_top=1;
        if (!state->active || state->tid!=tid ||
            state->graph_root!=graph_root || state->archive!=archive ||
            state->epoch!=epoch || state->depth<=0 ||
            state->language_sequence!=generation ||
            InterlockedCompareExchange(
                &language_transition_inflight,0,0)!=0) continue;
        for (right=0;right<MAX_GRAPH_EPOCHS;++right) {
            GraphEpochState *other=&graph_epochs[right];
            if (other==state || !other->active || other->tid!=tid ||
                other->depth<=0) continue;
            if (other->nesting_level>=state->nesting_level) {
                unique_top=0; break;
            }
        }
        if (!unique_top) break;
        state->depth--;
        if (!state->depth) {
            state->completed=1;
            /* Persist the successful graph-end proof on every exact CRef
             * discovered by this graph.  The live CRef pointer is checked
             * again here, so a changed/freed selection is never promoted. */
            for (right=0;right<MAX_CREF_BINDINGS;++right) {
                CRefBinding *binding=&cref_bindings[right];
                uintptr_t tagged;
                if (!binding->active || binding->tid!=state->tid ||
                    binding->route.archive!=state->archive ||
                    binding->route.graph_root!=state->graph_root ||
                    binding->route.graph_epoch!=state->epoch ||
                    binding->route.language_sequence!=state->language_sequence ||
                    !binding->route.runtime_graph_identity_exact)
                    continue;
                tagged=safe_pointer(binding->cref_self,0);
                if ((void *)(tagged&~(uintptr_t)3)==binding->resolved_node) {
                    binding->graph_completion_exact=1;
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
                    InterlockedOr(&diagnostic_pipeline_flags,0x2000);
#endif
                } else
                    memset(binding,0,sizeof(*binding));
            }
        }
        exact=1; break;
    }
graph_end_done:
    ReleaseSRWLockExclusive(&state_lock);
    if (exact) telemetry_increment(&graph_end_events);
    else {
        telemetry_increment(&graph_identity_rejects);
        set_fatal();
    }
    return exact;
}

static int active_graph_snapshot(void *archive, void **graph_root,
    LONG *epoch, LONG *language_generation) {
    DWORD tid=GetCurrentThreadId();
    GraphEpochState *best=NULL;
    LONG generation;
    void *selected_root=NULL;
    LONG selected_epoch=0,selected_generation=0;
    int ambiguous=0,matched=0;
    size_t index;
    AcquireSRWLockShared(&state_lock);
    generation=InterlockedCompareExchange(&language_state_sequence,0,0);
    for (index=0;index<MAX_GRAPH_EPOCHS;++index) {
        GraphEpochState *at=&graph_epochs[index];
        if (!at->active || at->tid!=tid || at->depth<=0 ||
            at->language_sequence!=generation) continue;
        if (!best || at->nesting_level>best->nesting_level) {
            best=at; ambiguous=0;
        } else if (at->nesting_level==best->nesting_level &&
            (at->graph_root!=best->graph_root || at->epoch!=best->epoch))
            ambiguous=1;
    }
    /* The active graph is a single global stack per thread.  Archive is
     * checked only after choosing its unique top; filtering by archive first
     * would incorrectly reuse an outer A while a nested B is active. */
    if (best && !ambiguous && best->archive==archive &&
        InterlockedCompareExchange(&lifecycle_admission_revoked,0,0)==0 &&
        InterlockedCompareExchange(&language_transition_inflight,0,0)==0 &&
        InterlockedCompareExchange(&fatal_latch,0,0)==0) {
        selected_root=best->graph_root;
        selected_epoch=best->epoch;
        selected_generation=best->language_sequence;
        matched=1;
    }
    ReleaseSRWLockShared(&state_lock);
    if (matched) {
        if (graph_root) *graph_root=selected_root;
        if (epoch) *epoch=selected_epoch;
        if (language_generation) *language_generation=selected_generation;
    }
    if (ambiguous) {
        telemetry_increment(&graph_identity_rejects);
        set_fatal();
    }
    if (best && !ambiguous && !matched)
        telemetry_increment(&graph_identity_rejects);
    return matched;
}

static int validate_cref_read(const RouteDef *route, void *self,
    void *archive, void *graph_root, LONG epoch,
    const ArchiveSample *before, const ArchiveSample *after,
    uintptr_t result, void *resolved) {
    return route && self && archive && graph_root && epoch>0 && before && after &&
        result==(uintptr_t)archive && before->mode==3 &&
        before->mode==after->mode && before->end==after->end &&
        before->cursor && before->end && before->cursor<before->end &&
        after->cursor>before->cursor && after->cursor<=after->end &&
        range_readable(self,sizeof(uintptr_t)) && resolved &&
        resolved!=(void *)(main_base+PF_NULL_RESOURCE_SENTINEL_RVA) &&
        find_route(route->raw_handle)>=0;
}

static int graph_epoch_active_exact_locked(const RouteFrame *route) {
    size_t index;
    if (!route || route->graph_epoch<=0 || !route->graph_root ||
        route->language_sequence!=
            InterlockedCompareExchange(&language_state_sequence,0,0) ||
        InterlockedCompareExchange(&lifecycle_admission_revoked,0,0)!=0 ||
        InterlockedCompareExchange(&language_transition_inflight,0,0)!=0 ||
        InterlockedCompareExchange(&fatal_latch,0,0)!=0)
        return 0;
    for (index=0;index<MAX_GRAPH_EPOCHS;++index) {
        GraphEpochState *state=&graph_epochs[index];
        if (state->active && state->tid==route->tid &&
            state->archive==route->archive &&
            state->graph_root==route->graph_root &&
            state->epoch==route->graph_epoch && state->depth>0 &&
            !state->completed &&
            state->language_sequence==route->language_sequence)
            return 1;
    }
    return 0;
}

static int language_endpoint_exact(LONG state) {
    return state==PHOTON_V6_PF_SELECTOR_LANGUAGE_JAPANESE ||
        state==PHOTON_V6_PF_SELECTOR_LANGUAGE_TRANSLATION;
}

/* Validate the engine-owned CRef identity without consulting the current
 * language generation.  This is the durable part of a completed proof: the
 * exact route shape plus the still-live tagged pointer.  PF retains selected
 * CRefs across image-language changes even when it does not issue a second
 * CRef read after returning to the original endpoint. */
static int cref_binding_shape_live_exact_locked(const CRefBinding *binding) {
    const RouteFrame *route;
    uintptr_t tagged;
    size_t route_count=sizeof(routes)/sizeof(routes[0]);
    if (!binding || !binding->active ||
        !binding->tid || !binding->cref_self || !binding->resolved_node ||
        binding->identity_sequence<=0)
        return 0;
    route=&binding->route;
    if (route->tid!=binding->tid || route->cref_self!=binding->cref_self ||
        route->resolved_node!=binding->resolved_node ||
        route->cref_identity_sequence!=binding->identity_sequence ||
        !route->archive || !route->graph_root || route->graph_epoch<=0 ||
        !route->runtime_graph_identity_exact || route->route_index<0 ||
        (size_t)route->route_index>=route_count ||
        routes[route->route_index].raw_handle!=route->raw_handle ||
        route->language_sequence<=0 ||
        !language_endpoint_exact(binding->endpoint_language_state))
        return 0;
    tagged=safe_pointer(binding->cref_self,0);
    if ((void *)(tagged&~(uintptr_t)3)!=binding->resolved_node) return 0;
    return 1;
}

/* Validate the current endpoint authority.  An uncompleted binding still
 * cannot escape its exact active graph.  A completed binding may outlive that
 * transient graph, but it can authorize only the endpoint on which its proof
 * was captured and only after its generation has been made current. */
static int cref_binding_live_exact_locked(const CRefBinding *binding) {
    const RouteFrame *route;
    if (!cref_binding_shape_live_exact_locked(binding)) return 0;
    route=&binding->route;
    if (binding->endpoint_language_state!=
            InterlockedCompareExchange(&language_state,0,0) ||
        route->language_sequence!=
            InterlockedCompareExchange(&language_state_sequence,0,0))
        return 0;
    if (!binding->graph_completion_exact &&
        !graph_epoch_active_exact_locked(route))
        return 0;
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
    InterlockedOr(&diagnostic_pipeline_flags,0x4000);
#endif
    return 1;
}

static int bind_cref_identity(RouteFrame *route) {
    CRefBinding *slot=NULL,*free_slot=NULL;
    LONG endpoint_state,endpoint_sequence;
    int ambiguous=0;
    size_t index;
    AcquireSRWLockExclusive(&state_lock);
    endpoint_state=InterlockedCompareExchange(&language_state,0,0);
    endpoint_sequence=InterlockedCompareExchange(
        &language_state_sequence,0,0);
    if (InterlockedCompareExchange(&lifecycle_admission_revoked,0,0)!=0 ||
        InterlockedCompareExchange(&translation_write_leases,0,0)!=0 ||
        !language_endpoint_exact(endpoint_state) ||
        !route || route->language_sequence!=endpoint_sequence ||
        !graph_epoch_active_exact_locked(route)) goto done;
    for (index=0;index<MAX_CREF_BINDINGS;++index) {
        CRefBinding *at=&cref_bindings[index];
        if (!at->active) {
            if (!free_slot) free_slot=at;
            continue;
        }
        if (!cref_binding_shape_live_exact_locked(at)) {
            memset(at,0,sizeof(*at));
            if (!free_slot) free_slot=at;
            continue;
        }
        /* Completed identities from the other image-language endpoint remain
         * dormant.  They are disjoint authorities even when PF reuses the
         * same CRef self/node and will be considered only after that endpoint
         * becomes current again. */
        if (at->endpoint_language_state!=endpoint_state) continue;
        if (at->tid!=route->tid ||
            (at->cref_self!=route->cref_self &&
             at->resolved_node!=route->resolved_node)) continue;
        if (at->resolved_node==route->resolved_node &&
            at->route.graph_epoch==route->graph_epoch &&
            at->route.graph_root==route->graph_root &&
            at->route.route_index!=route->route_index)
            ambiguous=1;
        /* A newly observed exact CRef revokes every older pointer generation
         * that shares its self or selected node.  It is never merged. */
        memset(at,0,sizeof(*at));
        if (!free_slot) free_slot=at;
    }
    if (!ambiguous) slot=free_slot;
    if (slot) {
        memset(slot,0,sizeof(*slot));
        slot->tid=route->tid;
        slot->cref_self=route->cref_self;
        slot->resolved_node=route->resolved_node;
        slot->identity_sequence=InterlockedIncrement(&cref_identity_sequence);
        slot->endpoint_language_state=endpoint_state;
        route->cref_identity_sequence=slot->identity_sequence;
        slot->route=*route;
        MemoryBarrier();
        slot->active=1;
    }
done:
    ReleaseSRWLockExclusive(&state_lock);
    if (!slot) {
        telemetry_increment(&cref_identity_rejects);
        set_fatal();
    }
    return slot!=NULL;
}

/* Return 1 for one current exact node, 0 for none, -1 for ambiguity. */
static int cref_route_for_node(void *node, RouteFrame *route) {
    CRefBinding *best=NULL;
    DWORD tid=GetCurrentThreadId();
    LONG current_state,current_sequence,newest_identity=0;
    int ambiguous=0;
    size_t index;
    AcquireSRWLockExclusive(&state_lock);
    if (InterlockedCompareExchange(&lifecycle_admission_revoked,0,0)!=0 ||
        InterlockedCompareExchange(&language_transition_inflight,0,0)!=0 ||
        InterlockedCompareExchange(&fatal_latch,0,0)!=0 ||
        InterlockedCompareExchange(&translation_write_leases,0,0)!=0)
        goto done;
    current_state=InterlockedCompareExchange(&language_state,0,0);
    current_sequence=InterlockedCompareExchange(
        &language_state_sequence,0,0);
    if (!language_endpoint_exact(current_state) || current_sequence<=0)
        goto done;
    for (index=0;index<MAX_CREF_BINDINGS;++index) {
        CRefBinding *at=&cref_bindings[index];
        if (!at->active || at->tid!=tid || !node ||
            at->route.graph_epoch<=0) continue;
        if (!cref_binding_shape_live_exact_locked(at)) {
            memset(at,0,sizeof(*at));
            telemetry_increment(&stale_generation_rejects);
            continue;
        }
        if (at->endpoint_language_state!=current_state) continue;
        if (at->route.language_sequence!=current_sequence) {
            /* A generation may be rebased only from a completed proof for the
             * same endpoint.  No graph, route, CRef, node, or identity field
             * is synthesized or changed. */
            if (!at->graph_completion_exact) {
                memset(at,0,sizeof(*at));
                telemetry_increment(&stale_generation_rejects);
                continue;
            }
            at->route.language_sequence=current_sequence;
        }
        if (!cref_binding_live_exact_locked(at)) {
            memset(at,0,sizeof(*at));
            telemetry_increment(&stale_generation_rejects);
            continue;
        }
        if (node!=at->resolved_node) continue;
        if (!best || at->identity_sequence>newest_identity) {
            best=at; newest_identity=at->identity_sequence;
        }
    }
    if (best) {
        for (index=0;index<MAX_CREF_BINDINGS;++index) {
            CRefBinding *at=&cref_bindings[index];
            if (!at->active || at==best || at->tid!=tid ||
                at->resolved_node!=node ||
                at->endpoint_language_state!=current_state) continue;
            if (cref_binding_live_exact_locked(at)) ambiguous=1;
        }
        if (!ambiguous && route) *route=best->route;
    }
done:
    ReleaseSRWLockExclusive(&state_lock);
    if (ambiguous) {
        telemetry_increment(&cref_identity_rejects);
        set_fatal();
    }
    return ambiguous?-1:(best?1:0);
}

static void clear_object_binding_locked(void *object, void *node,
    uint32_t clear_reason) {
    size_t index;
    for (index=0;index<MAX_OBJECT_BINDINGS;++index)
        if (object_bindings[index].active &&
            ((!object || object_bindings[index].object==object) ||
             (node && object_bindings[index].resource_node==node))) {
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
            if (object_bindings[index].target_index>=0 &&
                object_bindings[index].target_index<6) {
                InterlockedExchange(&diagnostic_last_special_clear_reason,
                    (LONG)clear_reason);
                InterlockedExchange(&diagnostic_last_special_clear_object,
                    (LONG)(uintptr_t)object_bindings[index].object);
                InterlockedExchange(&diagnostic_last_special_clear_node,
                    (LONG)(uintptr_t)object_bindings[index].resource_node);
                InterlockedExchange(
                    &diagnostic_last_special_clear_target_plus_one,
                    (LONG)(object_bindings[index].target_index+1));
                InterlockedExchange(
                    &diagnostic_last_special_clear_materializer_sequence,
                    object_bindings[index].materializer_sequence);
                InterlockedExchange(
                    &diagnostic_last_special_clear_object_generation,
                    object_bindings[index].object_generation);
                InterlockedExchange(
                    &diagnostic_last_special_clear_route_index_plus_one,
                    (LONG)(object_bindings[index].route.route_index+1));
                InterlockedExchange(
                    &diagnostic_last_special_clear_cref_sequence,
                    object_bindings[index].route.cref_identity_sequence);
                InterlockedExchange(
                    &diagnostic_last_special_clear_language_sequence,
                    object_bindings[index].language_sequence);
                MemoryBarrier();
                InterlockedIncrement(
                    &diagnostic_last_special_clear_event_sequence);
            }
#else
            (void)clear_reason;
#endif
            memset(&object_bindings[index],0,sizeof(object_bindings[index]));
        }
}

static int clear_object_binding(void *object, void *node,
    uint32_t clear_reason) {
    int cleared=0;
    AcquireSRWLockExclusive(&state_lock);
    if (InterlockedCompareExchange(&translation_write_leases,0,0)==0) {
        clear_object_binding_locked(object,node,clear_reason);
        cleared=1;
    }
    ReleaseSRWLockExclusive(&state_lock);
    if (!cleared) set_fatal();
    return cleared;
}

static int push_materialization(void *node, const RouteFrame *route,
    void *object_before, uint32_t node_kind, LONG state,
    LONG state_sequence, LONG sequence) {
    ActiveMaterialization *slot=NULL;
    LONG depth=0;
    DWORD tid=GetCurrentThreadId();
    size_t index;
    AcquireSRWLockExclusive(&state_lock);
    if (!route || route->route_index<0 ||
        InterlockedCompareExchange(&lifecycle_admission_revoked,0,0)!=0 ||
        InterlockedCompareExchange(&language_transition_inflight,0,0)!=0 ||
        InterlockedCompareExchange(&fatal_latch,0,0)!=0 ||
        InterlockedCompareExchange(&translation_write_leases,0,0)!=0 ||
        state_sequence!=InterlockedCompareExchange(
            &language_state_sequence,0,0) ||
        route->language_sequence!=state_sequence ||
        !cref_binding_exact_locked(route)) goto done;
    for (index=0;index<MAX_MATERIALIZATIONS;++index) {
        ActiveMaterialization *at=&active_materializations[index];
        if (at->active && at->tid==tid && at->depth>depth) depth=at->depth;
        if (!at->active && !slot) slot=at;
    }
    if (slot) {
        memset(slot,0,sizeof(*slot));
        slot->tid=tid; slot->depth=depth+1;
        slot->sequence=sequence; slot->route=*route;
        slot->resource_node=node; slot->object_before=object_before;
        slot->node_kind=node_kind; slot->language_state=state;
        slot->language_sequence=state_sequence;
        slot->pending.target_index=-1;
        slot->node_invariants_exact=1;
        MemoryBarrier();
        slot->active=1;
    }
done:
    ReleaseSRWLockExclusive(&state_lock);
    if (!slot) set_fatal();
    return slot!=NULL;
}

static int active_materialization_snapshot(ActiveMaterialization *output) {
    ActiveMaterialization *best=NULL;
    DWORD tid=GetCurrentThreadId();
    size_t index;
    AcquireSRWLockShared(&state_lock);
    if (InterlockedCompareExchange(&lifecycle_admission_revoked,0,0)!=0 ||
        InterlockedCompareExchange(&translation_write_leases,0,0)!=0)
        goto done;
    for (index=0;index<MAX_MATERIALIZATIONS;++index) {
        ActiveMaterialization *at=&active_materializations[index];
        if (at->active && at->tid==tid &&
            at->language_sequence==InterlockedCompareExchange(
                &language_state_sequence,0,0) &&
            at->route.language_sequence==at->language_sequence &&
            InterlockedCompareExchange(
                &language_transition_inflight,0,0)==0 &&
            (!best || at->depth>best->depth)) best=at;
    }
    if (best && output) *output=*best;
done:
    ReleaseSRWLockShared(&state_lock);
    return best!=NULL;
}

static int record_pending_load(LONG sequence, const PendingLoad *pending) {
    ActiveMaterialization *best=NULL;
    DWORD tid=GetCurrentThreadId();
    size_t index;
    AcquireSRWLockExclusive(&state_lock);
    if (InterlockedCompareExchange(&lifecycle_admission_revoked,0,0)!=0 ||
        InterlockedCompareExchange(&translation_write_leases,0,0)!=0)
        goto done;
    for (index=0;index<MAX_MATERIALIZATIONS;++index) {
        ActiveMaterialization *at=&active_materializations[index];
        if (at->active && at->tid==tid && at->sequence==sequence &&
            at->language_sequence==InterlockedCompareExchange(
                &language_state_sequence,0,0) &&
            at->route.language_sequence==at->language_sequence &&
            InterlockedCompareExchange(
                &language_transition_inflight,0,0)==0 &&
            (!best || at->depth>best->depth)) best=at;
    }
    if (best) {
        best->nested_load_count++;
        if (best->nested_load_count==1 && pending) best->pending=*pending;
        else best->node_invariants_exact=0;
        if (!pending || !pending->exact) best->node_invariants_exact=0;
    }
done:
    ReleaseSRWLockExclusive(&state_lock);
    return best!=NULL;
}

static int pop_materialization(LONG sequence,
    ActiveMaterialization *output) {
    ActiveMaterialization *best=NULL;
    DWORD tid=GetCurrentThreadId();
    size_t index;
    AcquireSRWLockExclusive(&state_lock);
    if (InterlockedCompareExchange(&translation_write_leases,0,0)!=0)
        goto done;
    for (index=0;index<MAX_MATERIALIZATIONS;++index) {
        ActiveMaterialization *at=&active_materializations[index];
        if (at->active && at->tid==tid &&
            (!best || at->depth>best->depth)) best=at;
    }
    if (best && best->sequence==sequence) {
        if (output) *output=*best;
        memset(best,0,sizeof(*best));
    } else best=NULL;
done:
    ReleaseSRWLockExclusive(&state_lock);
    if (!best) set_fatal();
    return best!=NULL;
}

static int payload_identity(void *object, const void **payload_out,
    uint32_t *bytes_out, uint64_t *hash_out, BYTE digest[32],
    int *target_out) {
    const void *payload;
    uint32_t bytes;
    uint64_t hash;
    int target;
    if (!cr6_object_invariants_exact(object)) return 0;
    payload=(const void *)safe_pointer(object,0x18);
    bytes=safe_u32(object,0x58);
    if (!bytes || bytes>MAX_PAYLOAD_BYTES || !range_readable(payload,bytes))
        return 0;
    hash=fnv1a64((const BYTE *)payload,bytes);
    sha256_digest((const BYTE *)payload,bytes,digest);
    target=find_target_exact(bytes,hash,digest);
    if (target<0) return 0;
    if (payload_out) *payload_out=payload;
    if (bytes_out) *bytes_out=bytes;
    if (hash_out) *hash_out=hash;
    if (target_out) *target_out=target;
    return 1;
}

static int payload_deny_tombstone(void *object, const void **payload_out,
    uint32_t *bytes_out, uint64_t *hash_out, BYTE digest[32],
    int *target_out) {
    const void *payload;
    uint32_t bytes;
    uint64_t hash;
    int target;
    if (!cr6_object_invariants_exact(object)) return 0;
    payload=(const void *)safe_pointer(object,0x18);
    bytes=safe_u32(object,0x58);
    if (!bytes || bytes>MAX_PAYLOAD_BYTES || !range_readable(payload,bytes))
        return 0;
    hash=fnv1a64((const BYTE *)payload,bytes);
    target=find_target_deny_tombstone(bytes,hash);
    if (target<0) return 0;
    sha256_digest((const BYTE *)payload,bytes,digest);
    if (payload_out) *payload_out=payload;
    if (bytes_out) *bytes_out=bytes;
    if (hash_out) *hash_out=hash;
    if (target_out) *target_out=target;
    return 1;
}

static int cref_binding_exact_locked(const RouteFrame *expected) {
    int matched=0;
    size_t index;
    if (!expected || !expected->resolved_node) return 0;
    for (index=0;index<MAX_CREF_BINDINGS;++index) {
        CRefBinding *at=&cref_bindings[index];
        if (!at->active || at->tid!=expected->tid ||
            at->resolved_node!=expected->resolved_node) continue;
        if (!cref_binding_live_exact_locked(at)) continue;
        if (at->cref_self==expected->cref_self &&
            at->identity_sequence==expected->cref_identity_sequence &&
            at->route.route_index==expected->route_index &&
            at->route.cref_identity_sequence==
                expected->cref_identity_sequence &&
            at->route.graph_epoch==expected->graph_epoch &&
            at->route.graph_root==expected->graph_root &&
            at->route.archive==expected->archive &&
            at->route.tid==expected->tid &&
            at->route.raw_handle==expected->raw_handle &&
            at->route.language_sequence==expected->language_sequence)
            matched++;
    }
    return matched==1;
}

static int object_binding_same_identity(
    const ObjectBinding *left, const ObjectBinding *right) {
    if (!left || !right || !left->active || !right->active) return 0;
    return left->tid==right->tid && left->object==right->object &&
        left->payload==right->payload &&
        left->resource_node==right->resource_node &&
        left->route.tid==right->route.tid &&
        left->route.archive==right->route.archive &&
        left->route.graph_root==right->route.graph_root &&
        left->route.cref_self==right->route.cref_self &&
        left->route.resolved_node==right->route.resolved_node &&
        left->route.raw_handle==right->route.raw_handle &&
        left->route.route_index==right->route.route_index &&
        left->route.graph_epoch==right->route.graph_epoch &&
        left->route.language_sequence==right->route.language_sequence &&
        left->route.cref_identity_sequence==
            right->route.cref_identity_sequence &&
        left->route.runtime_graph_identity_exact==
            right->route.runtime_graph_identity_exact &&
        left->node_kind==right->node_kind &&
        left->payload_bytes==right->payload_bytes &&
        left->payload_fnv1a64==right->payload_fnv1a64 &&
        memcmp(left->payload_sha256,right->payload_sha256,32)==0 &&
        left->target_index==right->target_index &&
        left->materializer_sequence==right->materializer_sequence &&
        left->object_generation==right->object_generation &&
        left->language_state==right->language_state &&
        left->language_sequence==right->language_sequence &&
        left->cached_commit==right->cached_commit;
}

static int object_binding_current_exact_locked(
    const ObjectBinding *expected) {
    int matched=0,conflict=0;
    size_t index;
    if (!expected || !expected->active || !expected->object ||
        expected->object_generation<=0) return 0;
    for (index=0;index<MAX_OBJECT_BINDINGS;++index) {
        ObjectBinding *at=&object_bindings[index];
        if (!at->active || at->object!=expected->object) continue;
        if (object_binding_same_identity(at,expected)) matched++;
        else conflict=1;
    }
    return matched==1 && !conflict;
}

static void publish_object_binding_locked(ObjectBinding *slot,
    const ObjectBinding *candidate) {
    ObjectBinding committed;
    if (!slot || !candidate || candidate->active || !candidate->object ||
        candidate->object_generation<=0) return;
    committed=*candidate;
    committed.active=0;
    memset(slot,0,sizeof(*slot));
    *slot=committed;
    MemoryBarrier();
    slot->active=1;
}

static int route_still_exact(const RouteFrame *expected) {
    int exact;
    if (!expected || !expected->resolved_node) return 0;
    AcquireSRWLockShared(&state_lock);
    exact=expected->tid==GetCurrentThreadId() &&
        expected->language_sequence==InterlockedCompareExchange(
            &language_state_sequence,0,0) &&
        InterlockedCompareExchange(&lifecycle_admission_revoked,0,0)==0 &&
        InterlockedCompareExchange(&language_transition_inflight,0,0)==0 &&
        InterlockedCompareExchange(&fatal_latch,0,0)==0 &&
        cref_binding_exact_locked(expected);
    ReleaseSRWLockShared(&state_lock);
    return exact;
}

#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
static void diagnostic_record_cref(const RouteFrame *route, int graph_active,
    int read_exact, int bind_exact) {
    DiagnosticCRefHistory *slot;
    LONG sequence;
    if (!route || !route->resolved_node || route->route_index<0) return;
    sequence=InterlockedIncrement(&diagnostic_cref_history_sequence);
    AcquireSRWLockExclusive(&diagnostic_lock);
    slot=&diagnostic_cref_history[
        ((uint32_t)sequence-1U)%DIAGNOSTIC_CREF_HISTORY_CAPACITY];
    memset(slot,0,sizeof(*slot));
    slot->tid=route->tid;
    slot->cref_self=route->cref_self;
    slot->resolved_node=route->resolved_node;
    slot->graph_root=route->graph_root;
    slot->raw_handle=route->raw_handle;
    slot->route_index=route->route_index;
    slot->graph_epoch=route->graph_epoch;
    slot->language_sequence=route->language_sequence;
    slot->graph_active=(LONG)graph_active;
    slot->read_exact=(LONG)read_exact;
    slot->bind_exact=(LONG)bind_exact;
    slot->sequence=sequence;
    ReleaseSRWLockExclusive(&diagnostic_lock);
}

static void diagnostic_materializer_push(void *node) {
    DiagnosticMaterializerThread *slot=NULL,*free_slot=NULL;
    DWORD tid=GetCurrentThreadId();
    size_t index;
    AcquireSRWLockExclusive(&diagnostic_lock);
    for (index=0;index<DIAGNOSTIC_MATERIALIZER_THREADS;++index) {
        DiagnosticMaterializerThread *at=&diagnostic_materializer_threads[index];
        if (at->active && at->tid==tid) { slot=at; break; }
        if (!at->active && !free_slot) free_slot=at;
    }
    if (!slot) slot=free_slot;
    if (slot) {
        if (!slot->active) {
            memset(slot,0,sizeof(*slot));
            slot->tid=tid;
            slot->active=1;
        }
        if (slot->depth<0 || slot->depth>=DIAGNOSTIC_MATERIALIZER_DEPTH)
            slot->depth=0;
        slot->nodes[slot->depth++]=node;
    }
    ReleaseSRWLockExclusive(&diagnostic_lock);
}

static void diagnostic_materializer_set_top_ladder(void *node,
    int persistent, int node_exact, int route_exact,
    const RouteFrame *route) {
    DWORD tid=GetCurrentThreadId();
    size_t index;
    AcquireSRWLockExclusive(&diagnostic_lock);
    for (index=0;index<DIAGNOSTIC_MATERIALIZER_THREADS;++index) {
        DiagnosticMaterializerThread *slot=&diagnostic_materializer_threads[index];
        LONG top;
        if (!slot->active || slot->tid!=tid || slot->depth<=0) continue;
        top=slot->depth-1;
        if (slot->nodes[top]!=node) break;
        slot->persistent[top]=(LONG)persistent;
        slot->node_exact[top]=(LONG)node_exact;
        slot->route_exact[top]=(LONG)route_exact;
        slot->route_index_plus_one[top]=route?(LONG)(route->route_index+1):0;
        slot->raw_handle[top]=route?(LONG)route->raw_handle:0;
        slot->cref_identity_sequence[top]=
            route?route->cref_identity_sequence:0;
        slot->language_sequence[top]=route?route->language_sequence:0;
        break;
    }
    ReleaseSRWLockExclusive(&diagnostic_lock);
}

static void diagnostic_materializer_pop(void *node) {
    DWORD tid=GetCurrentThreadId();
    size_t index;
    AcquireSRWLockExclusive(&diagnostic_lock);
    for (index=0;index<DIAGNOSTIC_MATERIALIZER_THREADS;++index) {
        DiagnosticMaterializerThread *slot=&diagnostic_materializer_threads[index];
        if (!slot->active || slot->tid!=tid) continue;
        if (slot->depth>0 &&
            slot->nodes[slot->depth-1]==node) {
            slot->nodes[--slot->depth]=NULL;
            if (!slot->depth) memset(slot,0,sizeof(*slot));
        } else memset(slot,0,sizeof(*slot));
        break;
    }
    ReleaseSRWLockExclusive(&diagnostic_lock);
}

static void diagnostic_capture_special_load(void *cr6_object) {
    DiagnosticCRefHistory selected;
    void *top_node=NULL;
    DWORD tid=GetCurrentThreadId();
    uintptr_t closest_delta=UINTPTR_MAX;
    uint32_t relation_flags=0;
    LONG top_persistent=0,top_node_exact=0,top_route_exact=0;
    LONG top_route_index_plus_one=0,top_raw_handle=0;
    LONG top_cref_sequence=0,top_language_sequence=0;
    size_t index;
    memset(&selected,0,sizeof(selected));
    AcquireSRWLockShared(&diagnostic_lock);
    for (index=0;index<DIAGNOSTIC_MATERIALIZER_THREADS;++index) {
        DiagnosticMaterializerThread *slot=&diagnostic_materializer_threads[index];
        if (slot->active && slot->tid==tid && slot->depth>0) {
            LONG top=slot->depth-1;
            top_node=slot->nodes[top];
            top_persistent=slot->persistent[top];
            top_node_exact=slot->node_exact[top];
            top_route_exact=slot->route_exact[top];
            top_route_index_plus_one=slot->route_index_plus_one[top];
            top_raw_handle=slot->raw_handle[top];
            top_cref_sequence=slot->cref_identity_sequence[top];
            top_language_sequence=slot->language_sequence[top];
            break;
        }
    }
    if (top_node) {
        for (index=0;index<DIAGNOSTIC_CREF_HISTORY_CAPACITY;++index) {
            DiagnosticCRefHistory *at=&diagnostic_cref_history[index];
            uintptr_t left,right,delta;
            if (!at->sequence || at->tid!=tid || !at->resolved_node) continue;
            left=(uintptr_t)top_node;
            right=(uintptr_t)at->resolved_node;
            delta=left>right?left-right:right-left;
            if (delta<closest_delta ||
                (delta==closest_delta && at->sequence>selected.sequence)) {
                closest_delta=delta;
                selected=*at;
            }
        }
    }
    ReleaseSRWLockShared(&diagnostic_lock);
    if (top_node && selected.sequence) {
        uintptr_t top_first=safe_pointer(top_node,0);
        uintptr_t resolved_first=safe_pointer(selected.resolved_node,0);
        uintptr_t cref_first=safe_pointer(selected.cref_self,0);
        if (top_node==selected.resolved_node) relation_flags|=UINT32_C(1);
        if ((void *)top_first==selected.resolved_node) relation_flags|=UINT32_C(2);
        if ((void *)resolved_first==top_node) relation_flags|=UINT32_C(4);
        if ((void *)top_first==cr6_object) relation_flags|=UINT32_C(8);
        if (top_node==cr6_object) relation_flags|=UINT32_C(16);
        if ((void *)resolved_first==cr6_object) relation_flags|=UINT32_C(32);
        if (selected.cref_self==top_node) relation_flags|=UINT32_C(64);
        if ((void *)(cref_first&~(uintptr_t)3)==selected.resolved_node)
            relation_flags|=UINT32_C(128);
    }
    InterlockedIncrement(&diagnostic_special_events);
    InterlockedExchange(&diagnostic_special_top_node,(LONG)(uintptr_t)top_node);
    InterlockedExchange(&diagnostic_special_cr6_object,
        (LONG)(uintptr_t)cr6_object);
    InterlockedExchange(&diagnostic_special_closest_resolved,
        (LONG)(uintptr_t)selected.resolved_node);
    InterlockedExchange(&diagnostic_special_closest_delta,
        selected.sequence?(LONG)(uint32_t)closest_delta:-1);
    InterlockedExchange(&diagnostic_special_route_index_plus_one,
        selected.sequence?(LONG)(selected.route_index+1):0);
    InterlockedExchange(&diagnostic_special_relation_flags,(LONG)relation_flags);
    InterlockedExchange(&diagnostic_special_raw_handle,
        selected.sequence?(LONG)selected.raw_handle:0);
    InterlockedExchange(&diagnostic_special_materializer_persistent,
        top_persistent);
    InterlockedExchange(&diagnostic_special_materializer_node_exact,
        top_node_exact);
    InterlockedExchange(&diagnostic_special_materializer_route_exact,
        top_route_exact);
    InterlockedExchange(
        &diagnostic_special_materializer_route_index_plus_one,
        top_route_index_plus_one);
    InterlockedExchange(&diagnostic_special_materializer_raw_handle,
        top_raw_handle);
    InterlockedExchange(&diagnostic_special_materializer_cref_sequence,
        top_cref_sequence);
    InterlockedExchange(&diagnostic_special_materializer_language_sequence,
        top_language_sequence);
    InterlockedExchange(&diagnostic_special_cref_attempt_sequence,
        selected.sequence);
    InterlockedExchange(&diagnostic_special_cref_attempt_graph_active,
        selected.graph_active);
    InterlockedExchange(&diagnostic_special_cref_attempt_read_exact,
        selected.read_exact);
    InterlockedExchange(&diagnostic_special_cref_attempt_bind_exact,
        selected.bind_exact);
    InterlockedExchange(&diagnostic_special_cref_attempt_graph_root,
        (LONG)(uintptr_t)selected.graph_root);
    InterlockedExchange(&diagnostic_special_cref_attempt_graph_epoch,
        selected.graph_epoch);
    InterlockedExchange(&diagnostic_special_cref_attempt_language_sequence,
        selected.language_sequence);
    InterlockedExchange(&diagnostic_special_cref_attempt_cref_self,
        (LONG)(uintptr_t)selected.cref_self);
    InterlockedExchange(&diagnostic_special_cref_attempt_resolved_node,
        (LONG)(uintptr_t)selected.resolved_node);
    InterlockedExchange(&diagnostic_special_cref_attempt_raw_handle,
        (LONG)selected.raw_handle);
    InterlockedExchange(&diagnostic_special_cref_attempt_route_index_plus_one,
        selected.sequence?(LONG)(selected.route_index+1):0);
}
#endif

static int binding_revalidate_mode(const ObjectBinding *binding,
    int allow_transition_latch) {
    const void *payload=NULL;
    uint32_t bytes=0,current_kind=UINT32_MAX;
    uint64_t hash=0;
    BYTE digest[32];
    int target=-1;
    LONG state,sequence;
    const RouteDef *route;
    if (!binding || !binding->active || !binding->object ||
        (!allow_transition_latch && InterlockedCompareExchange(
            &lifecycle_admission_revoked,0,0)!=0) ||
        (!allow_transition_latch && InterlockedCompareExchange(
            &language_transition_inflight,0,0)!=0) ||
        InterlockedCompareExchange(&fatal_latch,0,0)!=0 ||
        binding->tid!=GetCurrentThreadId() || binding->object_generation<=0 ||
        binding->materializer_sequence<=0 || !binding->resource_node ||
        safe_pointer(binding->resource_node,0)!=(uintptr_t)binding->object ||
        !resource_node_invariants_exact(binding->resource_node,&current_kind) ||
        current_kind!=binding->node_kind ||
        !payload_identity(binding->object,&payload,&bytes,&hash,digest,&target))
        return 0;
    state=InterlockedCompareExchange(&language_state,0,0);
    sequence=InterlockedCompareExchange(&language_state_sequence,0,0);
    route=binding->route.route_index>=0?&routes[binding->route.route_index]:NULL;
    if (!(payload==binding->payload && bytes==binding->payload_bytes &&
        hash==binding->payload_fnv1a64 &&
        memcmp(digest,binding->payload_sha256,32)==0 &&
        target==binding->target_index && target>=0 && target<6 &&
        state==PHOTON_V6_PF_SELECTOR_LANGUAGE_TRANSLATION &&
        state==binding->language_state &&
        sequence==binding->language_sequence &&
        (allow_transition_latch || InterlockedCompareExchange(
            &language_transition_inflight,0,0)==0) &&
        InterlockedCompareExchange(&fatal_latch,0,0)==0 &&
        route_is_translation_provider(route,target)))
        return 0;
    AcquireSRWLockShared(&state_lock);
    target=object_binding_current_exact_locked(binding) &&
        cref_binding_exact_locked(&binding->route);
    ReleaseSRWLockShared(&state_lock);
    return target &&
        (allow_transition_latch || InterlockedCompareExchange(
            &lifecycle_admission_revoked,0,0)==0) &&
        (allow_transition_latch || InterlockedCompareExchange(
            &language_transition_inflight,0,0)==0) &&
        InterlockedCompareExchange(&fatal_latch,0,0)==0;
}

static int binding_revalidate_exact(const ObjectBinding *binding) {
    return binding_revalidate_mode(binding,0);
}

static int binding_revalidate_for_release(const ObjectBinding *binding) {
    return binding_revalidate_mode(binding,1);
}

#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
static void diagnostic_surface_binding_ladder(void *object,
    const ObjectBinding *binding) {
    const void *payload=NULL;
    uint32_t bytes=0,current_kind=UINT32_MAX;
    uint64_t hash=0;
    BYTE digest[32];
    int target=-1,table_exact=0,cref_exact=0;
    LONG state,sequence;
    const RouteDef *route;
    if ((LONG)(uintptr_t)object!=InterlockedCompareExchange(
            &diagnostic_special_cr6_object,0,0)) return;
    InterlockedOr(&diagnostic_pipeline_flags,0x00010000);
    if (!binding || !binding->active) return;
    InterlockedOr(&diagnostic_pipeline_flags,0x00020000);
    if (!binding->object || binding->tid!=GetCurrentThreadId() ||
        binding->object_generation<=0 || binding->materializer_sequence<=0 ||
        !binding->resource_node ||
        safe_pointer(binding->resource_node,0)!=(uintptr_t)binding->object ||
        !resource_node_invariants_exact(binding->resource_node,&current_kind) ||
        current_kind!=binding->node_kind ||
        !payload_identity(binding->object,&payload,&bytes,&hash,digest,&target))
        return;
    InterlockedOr(&diagnostic_pipeline_flags,0x00040000);
    state=InterlockedCompareExchange(&language_state,0,0);
    sequence=InterlockedCompareExchange(&language_state_sequence,0,0);
    route=binding->route.route_index>=0?&routes[binding->route.route_index]:NULL;
    if (payload!=binding->payload || bytes!=binding->payload_bytes ||
        hash!=binding->payload_fnv1a64 ||
        memcmp(digest,binding->payload_sha256,32)!=0 ||
        target!=binding->target_index || target<0 || target>=6 ||
        state!=PHOTON_V6_PF_SELECTOR_LANGUAGE_TRANSLATION ||
        state!=binding->language_state || sequence!=binding->language_sequence ||
        InterlockedCompareExchange(&language_transition_inflight,0,0)!=0 ||
        InterlockedCompareExchange(&fatal_latch,0,0)!=0 ||
        !route_is_translation_provider(route,target)) return;
    InterlockedOr(&diagnostic_pipeline_flags,0x00080000);
    AcquireSRWLockShared(&state_lock);
    table_exact=object_binding_current_exact_locked(binding);
    cref_exact=cref_binding_exact_locked(&binding->route);
    ReleaseSRWLockShared(&state_lock);
    if (table_exact) InterlockedOr(&diagnostic_pipeline_flags,0x00100000);
    if (cref_exact) InterlockedOr(&diagnostic_pipeline_flags,0x00200000);
    if (table_exact && cref_exact &&
        InterlockedCompareExchange(&lifecycle_admission_revoked,0,0)==0 &&
        InterlockedCompareExchange(&language_transition_inflight,0,0)==0 &&
        InterlockedCompareExchange(&fatal_latch,0,0)==0)
        InterlockedOr(&diagnostic_pipeline_flags,0x00400000);
}

static void diagnostic_persist_surface_failure(void *object,
    const ObjectBinding *binding, int binding_found, int binding_exact,
    int push_result) {
    static const WCHAR suffix[]=L"photon_pf_surface_failure.v4.bin";
    typedef struct DiagnosticSurfaceFailureRecord {
        uint32_t magic,version,process_id,thread_id,condition_bits;
        uint32_t object,binding_object,resource_node,binding_payload;
        uint32_t current_payload,binding_payload_bytes,current_payload_bytes;
        uint32_t binding_payload_hash_low,binding_payload_hash_high;
        uint32_t current_payload_hash_low,current_payload_hash_high;
        int32_t binding_target,current_target;
        int32_t binding_language_state,current_language_state;
        uint32_t binding_language_sequence,current_language_sequence;
        uint32_t materializer_sequence,object_generation;
        uint32_t binding_node_kind,current_node_kind;
        int32_t route_index;
        uint32_t route_raw_handle,route_cref_identity_sequence;
        uint32_t last_clear_event_sequence,last_clear_reason;
        uint32_t last_clear_object,last_clear_node;
        int32_t last_clear_target;
        uint32_t last_clear_materializer_sequence;
        uint32_t last_clear_object_generation;
        int32_t last_clear_route_index;
        uint32_t last_clear_cref_identity_sequence;
        uint32_t last_clear_language_sequence;
        uint32_t top_materializer_persistent;
        uint32_t top_materializer_node_exact;
        uint32_t top_materializer_route_exact;
        int32_t top_materializer_route_index;
        uint32_t top_materializer_raw_handle;
        uint32_t top_materializer_cref_identity_sequence;
        uint32_t top_materializer_language_sequence;
        uint32_t note_active_found,note_active_route_exact;
        uint32_t cref_attempt_sequence,cref_attempt_graph_active;
        uint32_t cref_attempt_read_exact,cref_attempt_bind_exact;
        uint32_t cref_attempt_graph_root,cref_attempt_graph_epoch;
        uint32_t cref_attempt_language_sequence,cref_attempt_cref_self;
        uint32_t cref_attempt_resolved_node,cref_attempt_raw_handle;
        int32_t cref_attempt_route_index;
    } DiagnosticSurfaceFailureRecord;
    DiagnosticSurfaceFailureRecord record;
    const void *payload=NULL;
    uint32_t bytes=0,current_kind=UINT32_MAX,conditions=0;
    uint64_t hash=0;
    BYTE digest[32];
    int target=-1,table_exact=0,cref_exact=0;
    const RouteDef *route=NULL;
    WCHAR path[MAX_PATH];
    DWORD prefix,done=0;
    HANDLE file;
    memset(&record,0,sizeof(record));
    memset(digest,0,sizeof(digest));
    if (binding_found) conditions|=UINT32_C(0x00000001);
    if (binding && binding->active) conditions|=UINT32_C(0x00000002);
    if (binding && binding->object==object) conditions|=UINT32_C(0x00000004);
    if (binding && binding->tid==GetCurrentThreadId())
        conditions|=UINT32_C(0x00000008);
    if (binding && binding->object_generation>0)
        conditions|=UINT32_C(0x00000010);
    if (binding && binding->materializer_sequence>0)
        conditions|=UINT32_C(0x00000020);
    if (binding && binding->resource_node)
        conditions|=UINT32_C(0x00000040);
    if (binding && binding->resource_node &&
        safe_pointer(binding->resource_node,0)==(uintptr_t)binding->object)
        conditions|=UINT32_C(0x00000080);
    if (binding && binding->resource_node &&
        resource_node_invariants_exact(binding->resource_node,&current_kind))
        conditions|=UINT32_C(0x00000100);
    if (binding && current_kind==binding->node_kind)
        conditions|=UINT32_C(0x00000200);
    if (payload_identity(object,&payload,&bytes,&hash,digest,&target))
        conditions|=UINT32_C(0x00000400);
    if (binding && payload==binding->payload)
        conditions|=UINT32_C(0x00000800);
    if (binding && bytes==binding->payload_bytes)
        conditions|=UINT32_C(0x00001000);
    if (binding && hash==binding->payload_fnv1a64)
        conditions|=UINT32_C(0x00002000);
    if (binding && memcmp(digest,binding->payload_sha256,32)==0)
        conditions|=UINT32_C(0x00004000);
    if (binding && target==binding->target_index)
        conditions|=UINT32_C(0x00008000);
    if (target>=0 && target<6) conditions|=UINT32_C(0x00010000);
    if (InterlockedCompareExchange(&language_state,0,0)==
            PHOTON_V6_PF_SELECTOR_LANGUAGE_TRANSLATION)
        conditions|=UINT32_C(0x00020000);
    if (binding && InterlockedCompareExchange(&language_state,0,0)==
            binding->language_state)
        conditions|=UINT32_C(0x00040000);
    if (binding && InterlockedCompareExchange(&language_state_sequence,0,0)==
            binding->language_sequence)
        conditions|=UINT32_C(0x00080000);
    if (!InterlockedCompareExchange(&language_transition_inflight,0,0))
        conditions|=UINT32_C(0x00100000);
    if (!InterlockedCompareExchange(&fatal_latch,0,0))
        conditions|=UINT32_C(0x00200000);
    if (binding && binding->route.route_index>=0 &&
        (size_t)binding->route.route_index<sizeof(routes)/sizeof(routes[0])) {
        route=&routes[binding->route.route_index];
        if (route_is_translation_provider(route,target))
            conditions|=UINT32_C(0x00400000);
    }
    if (binding && binding->active) {
        AcquireSRWLockShared(&state_lock);
        table_exact=object_binding_current_exact_locked(binding);
        cref_exact=cref_binding_exact_locked(&binding->route);
        ReleaseSRWLockShared(&state_lock);
    }
    if (table_exact) conditions|=UINT32_C(0x00800000);
    if (cref_exact) conditions|=UINT32_C(0x01000000);
    if (!InterlockedCompareExchange(&lifecycle_admission_revoked,0,0))
        conditions|=UINT32_C(0x02000000);
    if (binding_exact) conditions|=UINT32_C(0x04000000);
    if (push_result>0) conditions|=UINT32_C(0x08000000);
    if (!((binding && binding->active && binding->target_index>=0 &&
           binding->target_index<6) ||
          (target>=0 && target<6))) return;
    record.magic=UINT32_C(0x50465346);
    record.version=4;
    record.process_id=GetCurrentProcessId();
    record.thread_id=GetCurrentThreadId();
    record.condition_bits=conditions;
    record.object=(uint32_t)(uintptr_t)object;
    if (binding) {
        record.binding_object=(uint32_t)(uintptr_t)binding->object;
        record.resource_node=(uint32_t)(uintptr_t)binding->resource_node;
        record.binding_payload=(uint32_t)(uintptr_t)binding->payload;
        record.binding_payload_bytes=binding->payload_bytes;
        record.binding_payload_hash_low=(uint32_t)binding->payload_fnv1a64;
        record.binding_payload_hash_high=(uint32_t)
            (binding->payload_fnv1a64>>32);
        record.binding_target=(int32_t)binding->target_index;
        record.binding_language_state=(int32_t)binding->language_state;
        record.binding_language_sequence=(uint32_t)binding->language_sequence;
        record.materializer_sequence=(uint32_t)binding->materializer_sequence;
        record.object_generation=(uint32_t)binding->object_generation;
        record.binding_node_kind=binding->node_kind;
        record.route_index=(int32_t)binding->route.route_index;
        record.route_raw_handle=binding->route.raw_handle;
        record.route_cref_identity_sequence=(uint32_t)
            binding->route.cref_identity_sequence;
    }
    record.current_payload=(uint32_t)(uintptr_t)payload;
    record.current_payload_bytes=bytes;
    record.current_payload_hash_low=(uint32_t)hash;
    record.current_payload_hash_high=(uint32_t)(hash>>32);
    record.current_target=(int32_t)target;
    record.current_language_state=(int32_t)InterlockedCompareExchange(
        &language_state,0,0);
    record.current_language_sequence=(uint32_t)InterlockedCompareExchange(
        &language_state_sequence,0,0);
    record.current_node_kind=current_kind;
    record.last_clear_event_sequence=(uint32_t)InterlockedCompareExchange(
        &diagnostic_last_special_clear_event_sequence,0,0);
    record.last_clear_reason=(uint32_t)InterlockedCompareExchange(
        &diagnostic_last_special_clear_reason,0,0);
    record.last_clear_object=(uint32_t)InterlockedCompareExchange(
        &diagnostic_last_special_clear_object,0,0);
    record.last_clear_node=(uint32_t)InterlockedCompareExchange(
        &diagnostic_last_special_clear_node,0,0);
    record.last_clear_target=(int32_t)InterlockedCompareExchange(
        &diagnostic_last_special_clear_target_plus_one,0,0)-1;
    record.last_clear_materializer_sequence=(uint32_t)
        InterlockedCompareExchange(
            &diagnostic_last_special_clear_materializer_sequence,0,0);
    record.last_clear_object_generation=(uint32_t)InterlockedCompareExchange(
        &diagnostic_last_special_clear_object_generation,0,0);
    record.last_clear_route_index=(int32_t)InterlockedCompareExchange(
        &diagnostic_last_special_clear_route_index_plus_one,0,0)-1;
    record.last_clear_cref_identity_sequence=(uint32_t)
        InterlockedCompareExchange(
            &diagnostic_last_special_clear_cref_sequence,0,0);
    record.last_clear_language_sequence=(uint32_t)InterlockedCompareExchange(
        &diagnostic_last_special_clear_language_sequence,0,0);
    record.top_materializer_persistent=(uint32_t)InterlockedCompareExchange(
        &diagnostic_special_materializer_persistent,0,0);
    record.top_materializer_node_exact=(uint32_t)InterlockedCompareExchange(
        &diagnostic_special_materializer_node_exact,0,0);
    record.top_materializer_route_exact=(uint32_t)InterlockedCompareExchange(
        &diagnostic_special_materializer_route_exact,0,0);
    record.top_materializer_route_index=(int32_t)InterlockedCompareExchange(
        &diagnostic_special_materializer_route_index_plus_one,0,0)-1;
    record.top_materializer_raw_handle=(uint32_t)InterlockedCompareExchange(
        &diagnostic_special_materializer_raw_handle,0,0);
    record.top_materializer_cref_identity_sequence=(uint32_t)
        InterlockedCompareExchange(
            &diagnostic_special_materializer_cref_sequence,0,0);
    record.top_materializer_language_sequence=(uint32_t)
        InterlockedCompareExchange(
            &diagnostic_special_materializer_language_sequence,0,0);
    record.note_active_found=(uint32_t)InterlockedCompareExchange(
        &diagnostic_special_note_active_found,0,0);
    record.note_active_route_exact=(uint32_t)InterlockedCompareExchange(
        &diagnostic_special_note_active_route_exact,0,0);
    record.cref_attempt_sequence=(uint32_t)InterlockedCompareExchange(
        &diagnostic_special_cref_attempt_sequence,0,0);
    record.cref_attempt_graph_active=(uint32_t)InterlockedCompareExchange(
        &diagnostic_special_cref_attempt_graph_active,0,0);
    record.cref_attempt_read_exact=(uint32_t)InterlockedCompareExchange(
        &diagnostic_special_cref_attempt_read_exact,0,0);
    record.cref_attempt_bind_exact=(uint32_t)InterlockedCompareExchange(
        &diagnostic_special_cref_attempt_bind_exact,0,0);
    record.cref_attempt_graph_root=(uint32_t)InterlockedCompareExchange(
        &diagnostic_special_cref_attempt_graph_root,0,0);
    record.cref_attempt_graph_epoch=(uint32_t)InterlockedCompareExchange(
        &diagnostic_special_cref_attempt_graph_epoch,0,0);
    record.cref_attempt_language_sequence=(uint32_t)InterlockedCompareExchange(
        &diagnostic_special_cref_attempt_language_sequence,0,0);
    record.cref_attempt_cref_self=(uint32_t)InterlockedCompareExchange(
        &diagnostic_special_cref_attempt_cref_self,0,0);
    record.cref_attempt_resolved_node=(uint32_t)InterlockedCompareExchange(
        &diagnostic_special_cref_attempt_resolved_node,0,0);
    record.cref_attempt_raw_handle=(uint32_t)InterlockedCompareExchange(
        &diagnostic_special_cref_attempt_raw_handle,0,0);
    record.cref_attempt_route_index=(int32_t)InterlockedCompareExchange(
        &diagnostic_special_cref_attempt_route_index_plus_one,0,0)-1;
    prefix=GetTempPathW(MAX_PATH,path);
    if (!prefix || prefix>=MAX_PATH ||
        prefix+sizeof(suffix)/sizeof(suffix[0])>MAX_PATH) return;
    memcpy(path+prefix,suffix,sizeof(suffix));
    file=CreateFileW(path,GENERIC_WRITE,FILE_SHARE_READ,NULL,CREATE_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,NULL);
    if (file==INVALID_HANDLE_VALUE) return;
    (void)WriteFile(file,&record,(DWORD)sizeof(record),&done,NULL);
    (void)FlushFileBuffers(file);
    CloseHandle(file);
}
#endif

static int bind_committed_object(const ActiveMaterialization *materializer,
    void *object, int cached) {
    const void *payload=NULL;
    uint32_t bytes=0,current_kind=UINT32_MAX;
    uint64_t hash=0;
    BYTE digest[32];
    int target=-1;
    LONG state,sequence;
    const RouteDef *route;
    ObjectBinding candidate,*slot=NULL,*free_slot=NULL;
    int commit_guard=0;
    size_t index;
    if (!materializer || !object ||
        InterlockedCompareExchange(&lifecycle_admission_revoked,0,0)!=0 ||
        InterlockedCompareExchange(&language_transition_inflight,0,0)!=0 ||
        InterlockedCompareExchange(&fatal_latch,0,0)!=0 ||
        InterlockedCompareExchange(&translation_write_leases,0,0)!=0 ||
        materializer->tid!=GetCurrentThreadId() ||
        materializer->sequence<=0 ||
        (cached && (materializer->object_before!=object ||
                    materializer->nested_load_count!=0)) ||
        (!cached && (materializer->object_before!=NULL ||
                     materializer->nested_load_count!=1 ||
                     materializer->pending.object!=object ||
                     !materializer->pending.exact)) ||
        safe_pointer(materializer->resource_node,0)!=(uintptr_t)object ||
        !resource_node_invariants_exact(materializer->resource_node,&current_kind) ||
        current_kind!=materializer->node_kind ||
        !route_still_exact(&materializer->route) ||
        !payload_identity(object,&payload,&bytes,&hash,digest,&target)) {
        telemetry_increment(&materializer_identity_rejects);
        return 0;
    }
    if (!cached && (payload!=materializer->pending.payload ||
        bytes!=materializer->pending.payload_bytes ||
        hash!=materializer->pending.payload_fnv1a64 ||
        memcmp(digest,materializer->pending.payload_sha256,32)!=0 ||
        target!=materializer->pending.target_index)) {
        telemetry_increment(&payload_sha256_rejects);
        return 0;
    }
    state=InterlockedCompareExchange(&language_state,0,0);
    sequence=InterlockedCompareExchange(&language_state_sequence,0,0);
    route=materializer->route.route_index>=0?
        &routes[materializer->route.route_index]:NULL;
    if (state!=materializer->language_state ||
        sequence!=materializer->language_sequence ||
        InterlockedCompareExchange(&language_transition_inflight,0,0)!=0 ||
        InterlockedCompareExchange(&fatal_latch,0,0)!=0) {
        telemetry_increment(&stale_generation_rejects);
        return 0;
    }
    if ((target==5 || (route && route->group_target_index==5)) &&
        !route_is_translation_provider(route,target)) {
        telemetry_increment(&c07_all_provider_rejects);
        return 0;
    }
    if (state==PHOTON_V6_PF_SELECTOR_LANGUAGE_JAPANESE) {
        telemetry_increment(&state0_translation_endpoint_rejects);
        return 0;
    }
    if (state!=PHOTON_V6_PF_SELECTOR_LANGUAGE_TRANSLATION ||
        !route_is_translation_provider(route,target) ||
        materializer->route.cref_identity_sequence<=0 ||
        !materializer->route.runtime_graph_identity_exact) {
        telemetry_increment(&materializer_identity_rejects);
        return 0;
    }
    AcquireSRWLockExclusive(&state_lock);
    if (InterlockedCompareExchange(&lifecycle_admission_revoked,0,0)==0 &&
        InterlockedCompareExchange(&language_transition_inflight,0,0)==0 &&
        InterlockedCompareExchange(&fatal_latch,0,0)==0 &&
        InterlockedCompareExchange(&translation_write_leases,0,0)==0 &&
        sequence==InterlockedCompareExchange(
            &language_state_sequence,0,0) &&
        materializer->route.language_sequence==sequence &&
        cref_binding_exact_locked(&materializer->route) &&
        payload_identity(object,&payload,&bytes,&hash,digest,&target) &&
        (cached || (payload==materializer->pending.payload &&
         bytes==materializer->pending.payload_bytes &&
         hash==materializer->pending.payload_fnv1a64 &&
         memcmp(digest,materializer->pending.payload_sha256,32)==0 &&
         target==materializer->pending.target_index)))
        commit_guard=1;
    if (!commit_guard) goto commit_done;
    for (index=0;index<MAX_OBJECT_BINDINGS;++index) {
        if (object_bindings[index].active &&
            object_bindings[index].object==object) {
            slot=&object_bindings[index]; break;
        }
        if (!object_bindings[index].active && !free_slot)
            free_slot=&object_bindings[index];
    }
    if (!slot) slot=free_slot;
    if (slot) {
        memset(&candidate,0,sizeof(candidate));
        candidate.tid=GetCurrentThreadId();
        candidate.object=object; candidate.payload=(void *)payload;
        candidate.resource_node=materializer->resource_node;
        candidate.route=materializer->route;
        candidate.node_kind=current_kind;
        candidate.payload_bytes=bytes; candidate.payload_fnv1a64=hash;
        memcpy(candidate.payload_sha256,digest,32);
        candidate.target_index=target;
        candidate.materializer_sequence=materializer->sequence;
        candidate.object_generation=
            InterlockedIncrement(&object_generation_sequence);
        candidate.language_state=state;
        candidate.language_sequence=sequence;
        candidate.cached_commit=cached;
        candidate.active=0;
        publish_object_binding_locked(slot,&candidate);
    }
commit_done:
    ReleaseSRWLockExclusive(&state_lock);
    if (!commit_guard) {
        telemetry_increment(&stale_generation_rejects);
        return 0;
    }
    if (!slot) {
        set_fatal();
        return 0;
    }
    telemetry_increment(cached?&materializer_cached_commits:
        &materializer_fresh_commits);
    return 1;
}

static int binding_snapshot(void *object, ObjectBinding *output) {
    DWORD tid=GetCurrentThreadId();
    int found=0,cross_thread=0;
    size_t index;
    AcquireSRWLockShared(&state_lock);
    if (InterlockedCompareExchange(&lifecycle_admission_revoked,0,0)!=0 ||
        InterlockedCompareExchange(&language_transition_inflight,0,0)!=0 ||
        InterlockedCompareExchange(&fatal_latch,0,0)!=0) goto done;
    for (index=0;index<MAX_OBJECT_BINDINGS;++index) {
        ObjectBinding *at=&object_bindings[index];
        if (!at->active || at->object!=object) continue;
        if (at->tid!=tid) { cross_thread=1; continue; }
        if (at->language_sequence!=InterlockedCompareExchange(
                &language_state_sequence,0,0) ||
            at->route.language_sequence!=at->language_sequence) continue;
        if (found) { found=-1; break; }
        if (output) *output=*at;
        found=1;
    }
done:
    ReleaseSRWLockShared(&state_lock);
    if (cross_thread) telemetry_increment(&cross_thread_rejects);
    if (found<0) set_fatal();
    return found==1;
}

static int purge_all_runtime_identity(LONG new_state) {
    int active_seen=0;
    size_t index;
    if (InterlockedCompareExchange(&translation_write_leases,0,0)!=0 ||
        InterlockedCompareExchange(&ordinary_write_leases,0,0)!=0 ||
        InterlockedCompareExchange(&special_write_leases,0,0)!=0) {
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
        InterlockedOr(&diagnostic_transition_failure_bits,0x0001);
#endif
        set_fatal();
        return 0;
    }
    AcquireSRWLockExclusive(&state_lock);
    telemetry_begin();
    if (!lease_census_exact_locked()) {
        active_seen=1;
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
        InterlockedOr(&diagnostic_transition_failure_bits,0x0002);
#endif
    }
    for (index=0;index<MAX_GRAPH_EPOCHS;++index)
        if (graph_epochs[index].active && graph_epochs[index].depth>0) {
            active_seen=1;
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
            InterlockedOr(&diagnostic_transition_failure_bits,
                graph_epochs[index].tid==GetCurrentThreadId()?0x000C:0x0004);
#endif
        }
    for (index=0;index<MAX_MATERIALIZATIONS;++index)
        if (active_materializations[index].active) {
            active_seen=1;
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
            InterlockedOr(&diagnostic_transition_failure_bits,
                active_materializations[index].tid==GetCurrentThreadId()?
                    0x0030:0x0010);
#endif
        }
    for (index=0;index<MAX_ACTIVE_SURFACES;++index)
        if (active_surfaces[index].active) {
            active_seen=1;
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
            InterlockedOr(&diagnostic_transition_failure_bits,
                active_surfaces[index].tid==GetCurrentThreadId()?
                    0x00C0:0x0040);
#endif
        }
    for (index=0;index<MAX_ORDINARY_WRITE_LEASES;++index)
        if (ordinary_write_lease_slots[index].active) {
            active_seen=1;
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
            InterlockedOr(&diagnostic_transition_failure_bits,
                ordinary_write_lease_slots[index].tid==GetCurrentThreadId()?
                    0x0300:0x0100);
#endif
        }
    /* PF keeps completed CRef objects alive across an image-language setter
     * and may not read them again on returning to the original endpoint.
     * Preserve only those completed proofs whose exact tagged pointer still
     * resolves to the same node.  Every transient graph/materialization/
     * object/surface identity is still purged below. */
    for (index=0;index<MAX_CREF_BINDINGS;++index) {
        CRefBinding *binding=&cref_bindings[index];
        if (!binding->active) continue;
        if (active_seen || !binding->graph_completion_exact ||
            !cref_binding_shape_live_exact_locked(binding))
            memset(binding,0,sizeof(*binding));
    }
    memset(graph_epochs,0,sizeof(graph_epochs));
    memset(active_materializations,0,sizeof(active_materializations));
    memset(object_bindings,0,sizeof(object_bindings));
    memset(active_surfaces,0,sizeof(active_surfaces));
    memset(ordinary_write_lease_slots,0,sizeof(ordinary_write_lease_slots));
    InterlockedIncrement(&object_generation_sequence);
    InterlockedExchange(&language_state,new_state);
    InterlockedIncrement(&language_state_sequence);
    InterlockedIncrement(&global_language_generation_purges);
    telemetry_end();
    ReleaseSRWLockExclusive(&state_lock);
    if (active_seen) set_fatal();
    return !active_seen;
}

static int begin_language_transition(LONG expected_previous) {
    int census_exact=0;
    int claimed=0;
    AcquireSRWLockExclusive(&state_lock);
    if (!InterlockedCompareExchange(&lifecycle_admission_revoked,0,0) &&
        InterlockedCompareExchange(&language_transition_inflight,1,0)==0) {
        InterlockedExchange(&language_transition_owner_tid,
            (LONG)GetCurrentThreadId());
        claimed=1;
    }
    ReleaseSRWLockExclusive(&state_lock);
    if (!claimed) {
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
        InterlockedOr(&diagnostic_transition_failure_bits,0x1000);
#endif
        return 0;
    }
    /* Latch first, then drain both ordinary transactions and special Decode
     * scopes.  There is deliberately no timeout that could let the native
     * setter cross a still-live Translation write.  A leak remains blocked;
     * exact same-thread lease ownership returns with the latch retained so
     * the dispatch hard-fails instead of self-deadlocking or calling native. */
    for (;;) {
        if (InterlockedCompareExchange(&translation_write_leases,0,0)==0) {
            AcquireSRWLockShared(&state_lock);
            census_exact=lease_census_exact_locked() &&
                InterlockedCompareExchange(&ordinary_write_leases,0,0)==0 &&
                InterlockedCompareExchange(&special_write_leases,0,0)==0;
            ReleaseSRWLockShared(&state_lock);
            if (census_exact) break;
            set_fatal();
            return 0;
        }
        AcquireSRWLockShared(&state_lock);
        census_exact=lease_census_exact_locked();
        if (census_exact && current_thread_owns_write_lease_locked()) {
            ReleaseSRWLockShared(&state_lock);
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
            InterlockedOr(&diagnostic_transition_failure_bits,0x2000);
#endif
            set_fatal();
            return 0;
        }
        ReleaseSRWLockShared(&state_lock);
        if (!census_exact) {
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
            InterlockedOr(&diagnostic_transition_failure_bits,0x4000);
#endif
            set_fatal();
            return 0;
        }
        Sleep(1);
    }
    if (InterlockedCompareExchange(&language_state,0,0)!=expected_previous) {
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
        InterlockedOr(&diagnostic_transition_failure_bits,0x0400);
#endif
        set_fatal();
        return 0;
    }
    if (
        !purge_all_runtime_identity(PHOTON_V6_PF_SELECTOR_LANGUAGE_UNKNOWN)) {
        /* Retain the transition latch.  The dispatch must not call native
         * code after any relevant transition failure. */
        set_fatal();
        return 0;
    }
    return 1;
}

static int begin_language_bootstrap(void) {
    int census_exact;
    int claimed=0;
    AcquireSRWLockExclusive(&state_lock);
    if (!InterlockedCompareExchange(&lifecycle_admission_revoked,0,0) &&
        InterlockedCompareExchange(&language_transition_inflight,1,0)==0) {
        InterlockedExchange(&language_transition_owner_tid,
            (LONG)GetCurrentThreadId());
        claimed=1;
    }
    ReleaseSRWLockExclusive(&state_lock);
    if (!claimed) return 0;
    AcquireSRWLockShared(&state_lock);
    census_exact=lease_census_exact_locked() &&
        InterlockedCompareExchange(&translation_write_leases,0,0)==0 &&
        InterlockedCompareExchange(&ordinary_write_leases,0,0)==0 &&
        InterlockedCompareExchange(&special_write_leases,0,0)==0;
    ReleaseSRWLockShared(&state_lock);
    if (!census_exact || InterlockedCompareExchange(&language_state,0,0)!=
            PHOTON_V6_PF_SELECTOR_LANGUAGE_UNKNOWN ||
        !purge_all_runtime_identity(
            PHOTON_V6_PF_SELECTOR_LANGUAGE_UNKNOWN)) {
        set_fatal();
        return 0;
    }
    return 1;
}

static int finish_language_transition(LONG value, int exact,
    int bootstrap, void *self, void *owner) {
    int committed=0;
    AcquireSRWLockExclusive(&state_lock);
    telemetry_begin();
    if (exact && (value==PHOTON_V6_PF_SELECTOR_LANGUAGE_JAPANESE ||
                  value==PHOTON_V6_PF_SELECTOR_LANGUAGE_TRANSLATION) &&
        InterlockedCompareExchange(&language_transition_inflight,0,0)==1 &&
        InterlockedCompareExchange(&language_transition_owner_tid,0,0)==
            (LONG)GetCurrentThreadId() &&
        InterlockedCompareExchange(&language_state,0,0)==
            PHOTON_V6_PF_SELECTOR_LANGUAGE_UNKNOWN) {
        InterlockedExchange(&language_state,value);
        InterlockedIncrement(&language_state_sequence);
        if (bootstrap) {
            InterlockedExchangePointer(
                (void *volatile *)&language_cint_this,self);
            InterlockedExchangePointer(
                (void *volatile *)&language_cint_owner,owner);
            InterlockedIncrement(&language_bootstrap_exact_events);
        } else InterlockedIncrement(&language_setter_exact_events);
        committed=1;
    } else {
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
        InterlockedOr(&diagnostic_transition_failure_bits,0x8000);
#endif
        InterlockedIncrement(&language_bootstrap_conflict_rejects);
        InterlockedExchange(&fatal_latch,1);
    }
    /* Only a proven post-return native store may reopen the gate.  Failed
     * completion retains the latch until failfast/reset, never exposing an
     * UNKNOWN or stale Translation generation to writers.  Owner and latch
     * are cleared under the same state lock used by lifecycle admission, so
     * shutdown can never observe the transient owner==0/latch==1 pair. */
    if (committed) {
#ifdef PHOTON_V6_PF_SELECTOR_TEST_HOOKS
        if (InterlockedCompareExchange(
                &test_finish_transition_pause_enabled,0,0)) {
            InterlockedExchange(&test_finish_transition_pause_reached,1);
            while (!InterlockedCompareExchange(
                    &test_finish_transition_pause_release,0,0)) Sleep(1);
        }
#endif
        InterlockedExchange(&language_transition_owner_tid,0);
        MemoryBarrier();
        InterlockedExchange(&language_transition_inflight,0);
    }
    telemetry_end();
    ReleaseSRWLockExclusive(&state_lock);
    return committed;
}

/*
 * PF can restore the image-language CInt from persisted UI state before the
 * authenticated 0xC3DE3 VM action callsite is hooked.  The value is therefore
 * recovered only from the unique live heap object whose complete CInt/type/
 * owner record is sealed below.  A vtable match alone is deliberately
 * insufficient: the owner metadata hashes and _$unrefix marker distinguish
 * this exact Image Language variable from the other generic CInt instances.
 *
 * This mirror never authorizes a resource by itself.  It is combined with the
 * exact graph/CRef/raw-handle/materializer chain before any special endpoint
 * can write pixels.  Zero or multiple candidates stay UNKNOWN and fail closed.
 */
static int image_language_live_candidate_exact(void *object, void **owner_out,
    LONG *value_out) {
    static const WCHAR owner_marker[] = L"_$unrefix";
    void *owner;
    uintptr_t marker;
    uint32_t value;
    if (!object || !main_base ||
        safe_u32(object,0)!=(uint32_t)(uintptr_t)
            (main_base+PF_CINT_VTABLE_RVA) ||
        safe_u32(object,12)!=(uint32_t)(uintptr_t)
            (main_base+PF_CINT_TYPE_METADATA_RVA)) return 0;
    value=safe_u32(object,16);
    owner=(void *)safe_pointer(object,4);
    if (value>1 || !owner || safe_pointer(owner,0)!=(uintptr_t)object ||
        safe_u32(owner,0x10)!=0 ||
        safe_u32(owner,0x14)!=(uint32_t)(uintptr_t)
            (main_base+PF_IMAGE_LANGUAGE_OWNER_METADATA_RVA) ||
        safe_u32(owner,0x1C)!=UINT32_C(0xC1080300) ||
        safe_u32(owner,0x20)!=UINT32_C(0xA2FC9536) ||
        safe_u32(owner,0x24)!=UINT32_C(0xE7B699FE) ||
        safe_u32(owner,0x28)!=0 ||
        safe_u32(main_base+PF_CINT_TYPE_METADATA_RVA,4)!=4 ||
        (safe_u32(main_base+PF_CINT_TYPE_METADATA_RVA,8)&
            UINT32_C(0x7FFFFFFF))!=UINT32_C(0x16000000)) return 0;
    marker=safe_pointer(owner,8);
    if (!marker || !range_readable((const void *)marker,
            sizeof(owner_marker)) ||
        memcmp((const void *)marker,owner_marker,sizeof(owner_marker))!=0)
        return 0;
    if (owner_out) *owner_out=owner;
    if (value_out) *value_out=(LONG)value;
    return 1;
}

static int scan_unique_live_image_language(void **object_out,
    void **owner_out, LONG *value_out) {
    SYSTEM_INFO system_info;
    uintptr_t cursor,maximum;
    void *matched_object=NULL,*matched_owner=NULL;
    LONG matched_value=PHOTON_V6_PF_SELECTOR_LANGUAGE_UNKNOWN;
    unsigned matches=0;
    if (!object_out || !owner_out || !value_out || !main_base) return 0;
    GetSystemInfo(&system_info);
    cursor=(uintptr_t)system_info.lpMinimumApplicationAddress;
    maximum=(uintptr_t)system_info.lpMaximumApplicationAddress;
    while (cursor<maximum) {
        MEMORY_BASIC_INFORMATION info;
        uintptr_t begin,end,at,next;
        DWORD protection;
        if (VirtualQuery((const void *)cursor,&info,sizeof(info))!=
            sizeof(info)) break;
        begin=(uintptr_t)info.BaseAddress;
        if (info.RegionSize>UINTPTR_MAX-begin) break;
        next=begin+info.RegionSize;
        if (next<=cursor) break;
        protection=info.Protect&UINT32_C(0xFF);
        if (info.State==MEM_COMMIT && info.Type==MEM_PRIVATE &&
            !(info.Protect&(PAGE_GUARD|PAGE_NOACCESS)) &&
            (protection==PAGE_READWRITE || protection==PAGE_WRITECOPY ||
             protection==PAGE_EXECUTE_READWRITE ||
             protection==PAGE_EXECUTE_WRITECOPY)) {
            begin=(begin+3U)&~(uintptr_t)3U;
            end=next;
            for (at=begin;at<=end && end-at>=20U;at+=4U) {
                void *owner=NULL;
                LONG value=PHOTON_V6_PF_SELECTOR_LANGUAGE_UNKNOWN;
                if (*(const uint32_t *)at!=(uint32_t)(uintptr_t)
                        (main_base+PF_CINT_VTABLE_RVA) ||
                    !image_language_live_candidate_exact(
                        (void *)at,&owner,&value)) continue;
                matched_object=(void *)at;
                matched_owner=owner;
                matched_value=value;
                if (++matches>1U) break;
            }
        }
        if (matches>1U) break;
        cursor=next;
    }
    if (matches!=1U) return 0;
    *object_out=matched_object;
    *owner_out=matched_owner;
    *value_out=matched_value;
    return 1;
}

static int refresh_live_image_language(int force_scan) {
    void *known_this,*known_owner,*found_this=NULL,*found_owner=NULL;
    LONG current,value=PHOTON_V6_PF_SELECTOR_LANGUAGE_UNKNOWN;
    DWORD now;
    int exact=0;
    if (!InterlockedCompareExchange(&initialized,0,0) ||
        InterlockedCompareExchange(&shutting_down,0,0) ||
        InterlockedCompareExchange(&fatal_latch,0,0) ||
        InterlockedCompareExchange(&lifecycle_admission_revoked,0,0))
        return 0;
    known_this=InterlockedCompareExchangePointer(
        (void *volatile *)&language_cint_this,NULL,NULL);
    known_owner=InterlockedCompareExchangePointer(
        (void *volatile *)&language_cint_owner,NULL,NULL);
    current=InterlockedCompareExchange(&language_state,0,0);
    if (known_this) {
        if (!image_language_live_candidate_exact(
                known_this,&found_owner,&value) ||
            found_owner!=known_owner || current<0 || current>1) {
            telemetry_increment(&language_bootstrap_conflict_rejects);
            set_fatal();
            return 0;
        }
        if (value==current) return 1;
        if (!begin_language_transition(current)) return 0;
        return finish_language_transition(
            value,1,0,known_this,known_owner);
    }
    if (current!=PHOTON_V6_PF_SELECTOR_LANGUAGE_UNKNOWN) {
        telemetry_increment(&language_bootstrap_conflict_rejects);
        set_fatal();
        return 0;
    }
    now=GetTickCount();
    if (!force_scan) {
        DWORD previous=(DWORD)InterlockedCompareExchange(
            &language_scan_last_tick,0,0);
        if (previous && (DWORD)(now-previous)<250U) return 0;
    }
    if (InterlockedCompareExchange(&language_scan_inflight,1,0)!=0) return 0;
    InterlockedExchange(&language_scan_last_tick,(LONG)now);
    exact=scan_unique_live_image_language(
        &found_this,&found_owner,&value);
    if (exact && begin_language_bootstrap())
        exact=finish_language_transition(
            value,1,1,found_this,found_owner);
    else if (!exact)
        telemetry_increment(&language_bootstrap_conflict_rejects);
    InterlockedExchange(&language_scan_inflight,0);
    return exact;
}

static void decision_initialize(PhotonV6PfSelectorDecision *decision,
    uint32_t code) {
    if (!decision) return;
    memset(decision,0,sizeof(*decision));
    decision->struct_size=sizeof(*decision);
    decision->abi_version=PHOTON_V6_PF_SELECTOR_ADAPTER_ABI;
    decision->decision=code;
    decision->language_state=InterlockedCompareExchange(&language_state,0,0);
    decision->language_state_sequence=(uint32_t)
        InterlockedCompareExchange(&language_state_sequence,0,0);
    decision->language_state_known=
        InterlockedCompareExchange(&language_transition_inflight,0,0)==0 &&
        InterlockedCompareExchange(&fatal_latch,0,0)==0 &&
        (decision->language_state==PHOTON_V6_PF_SELECTOR_LANGUAGE_JAPANESE ||
         decision->language_state==PHOTON_V6_PF_SELECTOR_LANGUAGE_TRANSLATION);
    decision->target_index=PHOTON_V6_PF_SELECTOR_NO_TARGET;
}

static void decision_set_deny_tombstone(
    PhotonV6PfSelectorDecision *decision, uint32_t code, int target,
    uint32_t bytes, uint64_t hash, const BYTE digest[32]) {
    if (!decision || target<0 || target>=6) return;
    decision->decision=code;
    decision->target_index=(uint32_t)target;
    decision->payload_bytes=bytes;
    decision->payload_fnv1a64=hash;
    if (digest) memcpy(decision->payload_sha256,digest,32);
    decision->translation_overlay_allowed=0;
    decision->japanese_overlay_allowed=0;
}

static void decision_set_binding_deny_tombstone(
    PhotonV6PfSelectorDecision *decision, uint32_t code,
    const ObjectBinding *binding) {
    if (!binding || !binding->active) return;
    decision_set_deny_tombstone(decision,code,binding->target_index,
        binding->payload_bytes,binding->payload_fnv1a64,
        binding->payload_sha256);
    decision->selected_cr6_object=(uintptr_t)binding->object;
    decision->selected_resource_node=(uintptr_t)binding->resource_node;
}

static void decision_from_binding(const ObjectBinding *binding,
    LONG surface, int decode, PhotonV6PfSelectorDecision *decision) {
    const RouteDef *route;
    decision_initialize(decision,decode?
        PHOTON_V6_PF_SELECTOR_ALLOW_SPECIAL57_TRANSLATION:
        PHOTON_V6_PF_SELECTOR_SPECIAL57_SURFACE_SCOPE);
    if (!binding || !decision) return;
    route=binding->route.route_index>=0?&routes[binding->route.route_index]:NULL;
    decision->target_index=(uint32_t)binding->target_index;
    decision->provider_role=route_provider_role(route);
    decision->raw_handle=binding->route.raw_handle;
    decision->branch_identity_exact=1;
    decision->target_payload_exact=1;
    decision->materializer_commit_exact=1;
    decision->graph_epoch_current=1;
    decision->surface_scope_exact=surface>0;
    decision->decode_scope_exact=decode?1U:0U;
    decision->translation_overlay_allowed=decode?1U:0U;
    decision->japanese_overlay_allowed=0;
    decision->selected_cref_identity_sequence=
        (uint32_t)binding->route.cref_identity_sequence;
    decision->selected_materializer_sequence=
        (uint32_t)binding->materializer_sequence;
    decision->selected_surface_sequence=(uint32_t)surface;
    decision->object_generation=(uint32_t)binding->object_generation;
    decision->graph_root=(uintptr_t)binding->route.graph_root;
    decision->selected_resource_node=(uintptr_t)binding->resource_node;
    decision->selected_cr6_object=(uintptr_t)binding->object;
    decision->payload_bytes=binding->payload_bytes;
    decision->payload_fnv1a64=binding->payload_fnv1a64;
    memcpy(decision->payload_sha256,binding->payload_sha256,32);
    decision->special_source_asset_id=route?route->source_asset_id:NULL;
    decision->special_context_identity_key=route?
        route->context_identity_key:NULL;
}

static int push_surface(const ObjectBinding *binding, LONG *sequence) {
    ActiveSurface *slot=NULL;
    LONG depth=0;
    DWORD tid=GetCurrentThreadId();
    size_t index;
    AcquireSRWLockExclusive(&state_lock);
    if (!binding || !binding->active ||
        InterlockedCompareExchange(&lifecycle_admission_revoked,0,0)!=0 ||
        InterlockedCompareExchange(&language_transition_inflight,0,0)!=0 ||
        InterlockedCompareExchange(&fatal_latch,0,0)!=0 ||
        InterlockedCompareExchange(&translation_write_leases,0,0)!=0 ||
        binding->language_sequence!=InterlockedCompareExchange(
            &language_state_sequence,0,0) ||
        binding->route.language_sequence!=binding->language_sequence ||
        !object_binding_current_exact_locked(binding) ||
        !cref_binding_exact_locked(&binding->route)) goto done;
    for (index=0;index<MAX_ACTIVE_SURFACES;++index) {
        ActiveSurface *at=&active_surfaces[index];
        if (at->active && at->tid==tid && at->depth>depth) depth=at->depth;
        if (!at->active && !slot) slot=at;
    }
    if (slot) {
        memset(slot,0,sizeof(*slot)); slot->tid=tid;
        slot->depth=depth+1;
        slot->sequence=InterlockedIncrement(&surface_sequence);
        slot->binding=*binding;
        MemoryBarrier();
        slot->active=1;
        if (sequence) *sequence=slot->sequence;
    }
done:
    ReleaseSRWLockExclusive(&state_lock);
    if (!slot) set_fatal();
    return slot!=NULL;
}

static int surface_snapshot(ActiveSurface *output, int count_decode) {
    ActiveSurface *top=NULL;
    DWORD tid=GetCurrentThreadId();
    size_t index;
    AcquireSRWLockExclusive(&state_lock);
    if (InterlockedCompareExchange(&lifecycle_admission_revoked,0,0)!=0)
        goto surface_snapshot_done;
    for (index=0;index<MAX_ACTIVE_SURFACES;++index) {
        ActiveSurface *at=&active_surfaces[index];
        if (at->active && !at->closing && at->tid==tid &&
            at->binding.language_sequence==InterlockedCompareExchange(
                &language_state_sequence,0,0) &&
            at->binding.route.language_sequence==
                at->binding.language_sequence &&
            InterlockedCompareExchange(
                &language_transition_inflight,0,0)==0 &&
            (!top || at->depth>top->depth)) top=at;
    }
    if (top) {
        if (count_decode) top->decode_count++;
        if (output) *output=*top;
    }
surface_snapshot_done:
    ReleaseSRWLockExclusive(&state_lock);
    return top!=NULL;
}

static int acquire_surface_authorization_lease(LONG sequence) {
    ActiveSurface *top=NULL;
    DWORD tid=GetCurrentThreadId();
    int acquired=0;
    size_t index;
    AcquireSRWLockExclusive(&state_lock);
    if (InterlockedCompareExchange(&lifecycle_admission_revoked,0,0)!=0)
        goto surface_lease_done;
    for (index=0;index<MAX_ACTIVE_SURFACES;++index) {
        ActiveSurface *at=&active_surfaces[index];
        if (at->active && !at->closing && at->tid==tid &&
            (!top || at->depth>top->depth)) top=at;
    }
    if (top && top->sequence==sequence &&
        InterlockedCompareExchange(&language_transition_inflight,0,0)==0 &&
        InterlockedCompareExchange(&fatal_latch,0,0)==0 &&
        object_binding_current_exact_locked(&top->binding) &&
        cref_binding_exact_locked(&top->binding.route) &&
        top->binding.language_sequence==InterlockedCompareExchange(
            &language_state_sequence,0,0) &&
        top->binding.route.language_sequence==
            top->binding.language_sequence) {
        if (!top->authorization_lease) {
            (void)special_lease_acquire_locked(top);
            if (top->authorization_lease && (InterlockedCompareExchange(
                    &language_transition_inflight,0,0)!=0 ||
                InterlockedCompareExchange(&fatal_latch,0,0)!=0)) {
                (void)special_lease_release_locked(top);
            }
        }
        acquired=top->authorization_lease!=0;
    }
surface_lease_done:
    ReleaseSRWLockExclusive(&state_lock);
    return acquired;
}

static int abort_top_surface(void) {
    ActiveSurface *top=NULL;
    DWORD tid=GetCurrentThreadId();
    size_t index;
    AcquireSRWLockExclusive(&state_lock);
    for (index=0;index<MAX_ACTIVE_SURFACES;++index) {
        ActiveSurface *at=&active_surfaces[index];
        if (at->active && at->tid==tid &&
            (!top || at->depth>top->depth)) top=at;
    }
    if (top) {
        clear_object_binding_locked(top->binding.object,
                                    top->binding.resource_node,
                                    OBJECT_BINDING_CLEAR_SURFACE_ABORT);
        if (top->authorization_lease)
            (void)special_lease_release_locked(top);
        memset(top,0,sizeof(*top));
    }
    ReleaseSRWLockExclusive(&state_lock);
    return top!=NULL;
}

static int mark_surface_closing(void *object, ActiveSurface *output) {
    ActiveSurface *top=NULL;
    DWORD tid=GetCurrentThreadId();
    int result=0;
    size_t index;
    AcquireSRWLockExclusive(&state_lock);
    for (index=0;index<MAX_ACTIVE_SURFACES;++index) {
        ActiveSurface *at=&active_surfaces[index];
        if (at->active && at->tid==tid &&
            (!top || at->depth>top->depth)) top=at;
    }
    if (top && top->binding.object==object && !top->closing) {
        top->closing=1;
        MemoryBarrier();
        if (output) *output=*top;
        result=1;
    } else if (top) {
        clear_object_binding_locked(top->binding.object,
                                    top->binding.resource_node,
                                    OBJECT_BINDING_CLEAR_SURFACE_MISMATCH);
        if (top->authorization_lease)
            (void)special_lease_release_locked(top);
        memset(top,0,sizeof(*top));
        result=-1;
    }
    ReleaseSRWLockExclusive(&state_lock);
    return result;
}

static int finish_surface_close(LONG sequence) {
    ActiveSurface *matched=NULL;
    DWORD tid=GetCurrentThreadId();
    int exact=0;
    size_t index;
    AcquireSRWLockExclusive(&state_lock);
    for (index=0;index<MAX_ACTIVE_SURFACES;++index) {
        ActiveSurface *at=&active_surfaces[index];
        if (!at->active || !at->closing || at->tid!=tid ||
            at->sequence!=sequence) continue;
        if (matched) {
            matched=NULL;
            break;
        }
        matched=at;
    }
    if (matched) {
        exact=!matched->authorization_lease ||
            special_lease_release_locked(matched);
        memset(matched,0,sizeof(*matched));
    }
    ReleaseSRWLockExclusive(&state_lock);
    return matched!=NULL && exact;
}

static int exact_image_language_action_stack(void) {
    static const DWORD expected[] = {
        0x000C3DE8,0x000412C2,0x00040599,0x00121288,0x0012B6C7
    };
    void *frames[32];
    USHORT count=CaptureStackBackTrace(1,32,frames,NULL);
    size_t found=0,index;
    for (index=0;index<count && found<sizeof(expected)/sizeof(expected[0]);
         ++index)
        if (main_rva((uintptr_t)frames[index])==expected[found]) ++found;
    return found==sizeof(expected)/sizeof(expected[0]);
}

static int known_language_setter_fields_exact(
    void *known_this, void *self, void *known_owner, uint32_t cint_owner,
    uint32_t cint_vtable, uint32_t cint_type, uint32_t previous,
    uint32_t value, LONG current) {
    /* Once bootstrap has sealed the image-language CInt identity, that
     * identity is the semantic authority.  The engine legitimately reaches
     * the same native setter through more than one VM/action stack, so a
     * particular caller stack cannot remain part of the transition identity.
     * Keep the object, owner, native type, stored value and shadow state exact
     * before revoking old render leases and allowing the native write. */
    return known_this && known_this==self && known_owner &&
        known_owner==(void *)(uintptr_t)cint_owner &&
        cint_vtable==(uint32_t)(uintptr_t)(main_base+PF_CINT_VTABLE_RVA) &&
        cint_type==UINT32_C(0x16000000) && previous<=1 && value<=1 &&
        current==(LONG)previous;
}

static int known_language_live_setter_fields_exact(
    void *known_this, void *self, void *known_owner, uint32_t cint_owner,
    int live_candidate_exact, uint32_t previous, uint32_t value,
    LONG current) {
    /* PF re-enters the image-language picker with the already-sealed CInt.
     * On that path the generic VM metadata read can be transiently
     * unavailable even though the complete live Image Language record (CInt,
     * type metadata, owner hashes and _$unrefix marker) revalidates exactly.
     * Treat that independent full-record proof as authoritative only for the
     * same sealed object/owner and a boolean stored value.  UNKNOWN permits a
     * lifecycle re-bootstrap; otherwise the shadow must still equal storage. */
    return live_candidate_exact && known_this && known_this==self &&
        known_owner && known_owner==(void *)(uintptr_t)cint_owner &&
        previous<=1 && value<=1 &&
        (current==PHOTON_V6_PF_SELECTOR_LANGUAGE_UNKNOWN ||
         current==(LONG)previous);
}

static int known_language_call_is_anomalous(void *known_this, void *self,
    uint32_t vm_command, int action_stack_exact, int action_candidate) {
    if (!known_this || action_candidate) return 0;
    /* Calls on the proven CInt are always relevant.  A different CInt is
     * relevant when it arrives through the exact image-language action stack
     * and command; structural/self drift on that path must revoke before the
     * native store rather than becoming an ignored unrelated setter. */
    return known_this==self ||
        (action_stack_exact && vm_command==UINT32_C(0x237));
}

static int exact_image_language_bootstrap_stack(void) {
    static const DWORD expected[] = {
        0x000C3DE8,0x000412C2,0x0003D7F4,0x0003D406,0x00005F53
    };
    void *frames[32];
    USHORT count=CaptureStackBackTrace(1,32,frames,NULL);
    size_t found=0,index;
    for (index=0;index<count && found<sizeof(expected)/sizeof(expected[0]);
         ++index)
        if (main_rva((uintptr_t)frames[index])==expected[found]) ++found;
    return found==sizeof(expected)/sizeof(expected[0]);
}

static int image_language_bootstrap_fields_exact(
    DWORD vm_vtable_rva, DWORD vm_exec_rva, uint32_t vm_command,
    uint32_t vm_source, uint16_t vm_opcode, DWORD cint_vtable_rva,
    int target_owner_same, uint32_t cint_type, int stack_exact) {
    return vm_vtable_rva==PF_CVM_FLAG_OP_VTABLE_RVA &&
        vm_exec_rva==PF_CVM_FLAG_OP_EXEC_RVA && vm_command==0x22 &&
        vm_source==0x06 && vm_opcode==0 &&
        cint_vtable_rva==PF_CINT_VTABLE_RVA && target_owner_same &&
        cint_type==UINT32_C(0x16000000) && stack_exact;
}

static uintptr_t __attribute__((cdecl,noinline,used))
hook_graph_root_serialize_counted(void *object, void *archive) {
    uintptr_t result;
    LONG epoch=0;
    if (!selector_semantics_enabled()) {
        result=real_graph_root_serialize(object,archive);
        return result;
    }
    (void)refresh_live_image_language(0);
    epoch=graph_root_begin(object,archive);
    result=real_graph_root_serialize(object,archive);
    if (epoch>0) (void)graph_root_end(object,archive,epoch);
    return result;
}

static int verify_image(BYTE *base) {
    IMAGE_DOS_HEADER *dos;
    IMAGE_NT_HEADERS32 *nt;
    if (!base || !range_readable(base,sizeof(IMAGE_DOS_HEADER))) return 0;
    dos=(IMAGE_DOS_HEADER *)base;
    if (dos->e_magic!=IMAGE_DOS_SIGNATURE || dos->e_lfanew<=0 ||
        !range_readable(base+dos->e_lfanew,sizeof(IMAGE_NT_HEADERS32)))
        return 0;
    nt=(IMAGE_NT_HEADERS32 *)(base+dos->e_lfanew);
    return nt->Signature==IMAGE_NT_SIGNATURE &&
        nt->OptionalHeader.Magic==IMAGE_NT_OPTIONAL_HDR32_MAGIC &&
        nt->FileHeader.TimeDateStamp==PF_TIMESTAMP &&
        nt->OptionalHeader.SizeOfImage==PF_SIZE_OF_IMAGE;
}

static int query_protection(const void *address, DWORD *protection) {
    MEMORY_BASIC_INFORMATION info;
    if (!address || !protection ||
        !VirtualQuery(address,&info,sizeof(info)) ||
        info.State!=MEM_COMMIT || (info.Protect&(PAGE_NOACCESS|PAGE_GUARD)))
        return 0;
    *protection=info.Protect;
    return *protection!=0;
}

static int make_relative(BYTE output[5], BYTE opcode, const BYTE *site,
    const void *destination) {
    intptr_t displacement=(const BYTE *)destination-(site+5);
    if (displacement<INT32_MIN || displacement>INT32_MAX) return 0;
    output[0]=opcode;
    *(int32_t *)(output+1)=(int32_t)displacement;
    return 1;
}

static uintptr_t align_up_address(uintptr_t value, uintptr_t alignment) {
    uintptr_t mask;
    if (!alignment || (alignment & (alignment - 1U))) return UINTPTR_MAX;
    mask = alignment - 1U;
    if (value > UINTPTR_MAX - mask) return UINTPTR_MAX;
    return (value + mask) & ~mask;
}

static BYTE *allocate_executable_in_range(uintptr_t begin, uintptr_t end,
    SIZE_T bytes, uintptr_t granularity) {
    uintptr_t cursor = align_up_address(begin, granularity);
    if (cursor == UINTPTR_MAX || end <= cursor || bytes > end - cursor)
        return NULL;
    while (cursor < end) {
        MEMORY_BASIC_INFORMATION info;
        uintptr_t region_begin, region_end, candidate, next;
        BYTE *allocation;
        if (VirtualQuery((const void *)cursor, &info, sizeof(info)) !=
            sizeof(info)) return NULL;
        region_begin = (uintptr_t)info.BaseAddress;
        if (info.RegionSize > UINTPTR_MAX - region_begin) return NULL;
        region_end = region_begin + info.RegionSize;
        next = region_end;
        if (info.State == MEM_FREE) {
            candidate = align_up_address(
                region_begin > cursor ? region_begin : cursor, granularity);
            if (candidate != UINTPTR_MAX && candidate < end &&
                bytes <= end - candidate && bytes <= region_end - candidate) {
                allocation = (BYTE *)VirtualAlloc((void *)candidate, bytes,
                    MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
                if (allocation) return allocation;
            }
        }
        if (next <= cursor) return NULL;
        cursor = align_up_address(next, granularity);
        if (cursor == UINTPTR_MAX) return NULL;
    }
    return NULL;
}

static BYTE *allocate_executable_near(const BYTE *anchor, SIZE_T bytes) {
    SYSTEM_INFO info;
    uintptr_t target, minimum, maximum, window, preferred, allocation_granularity;
    BYTE *result;
    if (!anchor || !bytes) return NULL;
    GetSystemInfo(&info);
    allocation_granularity = (uintptr_t)info.dwAllocationGranularity;
    if (!allocation_granularity) return NULL;
    target = (uintptr_t)anchor;
    window = (uintptr_t)INT32_MAX - UINT32_C(0x10000);
    minimum = (uintptr_t)info.lpMinimumApplicationAddress;
    maximum = (uintptr_t)info.lpMaximumApplicationAddress;
    if (target > window && target - window > minimum)
        minimum = target - window;
    if (target <= UINTPTR_MAX - window && target + window < maximum)
        maximum = target + window;
    if (maximum <= minimum || bytes > maximum - minimum) return NULL;

    preferred = align_up_address(
        (uintptr_t)main_base + PF_SIZE_OF_IMAGE, allocation_granularity);
    if (preferred != UINTPTR_MAX && preferred >= minimum && preferred < maximum) {
        result = allocate_executable_in_range(
            preferred, maximum, bytes, allocation_granularity);
        if (result) return result;
        if (preferred > minimum)
            return allocate_executable_in_range(
                minimum, preferred, bytes, allocation_granularity);
        return NULL;
    }
    return allocate_executable_in_range(
        minimum, maximum, bytes, allocation_granularity);
}

static int prepare_entry_hook(EntryHook *hook) {
    if (!hook || !main_base || hook->length>sizeof(hook->original)) return 0;
    hook->target=main_base+hook->rva;
    if (hook->rva==PF_SELECTOR_GRAPH_ROOT_SERIALIZE_RVA &&
        (!range_readable(main_base+0x000BF994,
            sizeof(EXPECT_GRAPH_ROOT_CREF_ARRAY_CALL_CONTEXT)) ||
         memcmp(main_base+0x000BF994,EXPECT_GRAPH_ROOT_CREF_ARRAY_CALL_CONTEXT,
            sizeof(EXPECT_GRAPH_ROOT_CREF_ARRAY_CALL_CONTEXT))!=0)) return 0;
    if (!range_readable(hook->target,hook->length) ||
        memcmp(hook->target,hook->expected,hook->length)!=0 ||
        !query_protection(hook->target,&hook->original_protect)) return 0;
    memcpy(hook->original,hook->target,hook->length);
    hook->trampoline=allocate_executable_near(hook->target,hook->length+5);
    if (!hook->trampoline) return 0;
    memcpy(hook->trampoline,hook->original,hook->length);
    if (!make_relative(hook->trampoline+hook->length,0xE9,
        hook->trampoline+hook->length,hook->target+hook->length)) return 0;
    return FlushInstructionCache(GetCurrentProcess(),hook->trampoline,
        hook->length+5)!=0;
}

static int prepare_call_hook(CallHook *hook) {
    int32_t relative;
    if (!hook || !main_base) return 0;
    hook->site=main_base+hook->callsite_rva;
    if (hook->callsite_rva==PF_CREF_RESOURCE_MATERIALIZER_CALLSITE_RVA) {
        const BYTE *context=main_base+0x0018836D;
        if (!range_readable(context,sizeof(EXPECT_MATERIALIZER_CALL_CONTEXT)) ||
            memcmp(context,EXPECT_MATERIALIZER_CALL_CONTEXT,4)!=0 ||
            *(const uint32_t *)(context+4)!=(uint32_t)(uintptr_t)
                (main_base+PF_NULL_RESOURCE_SENTINEL_RVA) ||
            memcmp(context+8,EXPECT_MATERIALIZER_CALL_CONTEXT+8,
                sizeof(EXPECT_MATERIALIZER_CALL_CONTEXT)-8)!=0) return 0;
    }
    if (!range_readable(hook->site,5) || hook->site[0]!=0xE8 ||
        !query_protection(hook->site,&hook->original_protect)) return 0;
    relative=*(const int32_t *)(hook->site+1);
    if (hook->site+5+relative!=main_base+hook->target_rva) return 0;
    memcpy(hook->original,hook->site,5);
    return make_relative(hook->replacement_bytes,0xE8,hook->site,
        hook->replacement);
}

static void free_trampolines(void) {
    size_t index;
    for (index=0;index<sizeof(entry_hooks)/sizeof(entry_hooks[0]);++index)
        if (entry_hooks[index].trampoline) {
            VirtualFree(entry_hooks[index].trampoline,0,MEM_RELEASE);
            entry_hooks[index].trampoline=NULL;
        }
}

static int prepare_hooks(void) {
    memset(entry_hooks,0,sizeof(entry_hooks));
    memset(call_hooks,0,sizeof(call_hooks));
    entry_hooks[0].rva=PF_CREF_READ_RVA;
    entry_hooks[0].expected=EXPECT_CREF_READ;
    entry_hooks[0].length=sizeof(EXPECT_CREF_READ);
    entry_hooks[0].replacement=(void *)hook_cref_read_abi;
    entry_hooks[1].rva=PF_SELECTOR_GRAPH_ROOT_SERIALIZE_RVA;
    entry_hooks[1].expected=EXPECT_GRAPH_ROOT_SERIALIZE;
    entry_hooks[1].length=sizeof(EXPECT_GRAPH_ROOT_SERIALIZE);
    entry_hooks[1].replacement=(void *)hook_graph_root_serialize_abi;
    call_hooks[0].callsite_rva=PF_CREF_RESOURCE_MATERIALIZER_CALLSITE_RVA;
    call_hooks[0].target_rva=PF_CREF_RESOURCE_MATERIALIZER_RVA;
    call_hooks[0].replacement=(void *)hook_resource_materializer_abi;
    call_hooks[1].callsite_rva=PF_TYPED_SETTER_CALLSITE_RVA;
    call_hooks[1].target_rva=PF_CINT_SETTER_RVA;
    call_hooks[1].replacement=(void *)hook_cint_setter_abi;
    for (size_t index=0;index<sizeof(entry_hooks)/sizeof(entry_hooks[0]);++index)
        if (!prepare_entry_hook(&entry_hooks[index])) {
            int result = -31 - (int)index;
            free_trampolines(); return result;
        }
    for (size_t index=0;index<sizeof(call_hooks)/sizeof(call_hooks[0]);++index)
        if (!prepare_call_hook(&call_hooks[index])) {
            int result = -33 - (int)index;
            free_trampolines(); return result;
        }
    real_cref_read=(CRefReadFn)entry_hooks[0].trampoline;
    real_graph_root_serialize=(SerializeFn)entry_hooks[1].trampoline;
    real_resource_materializer=(ResourceMaterializerFn)
        (main_base+PF_CREF_RESOURCE_MATERIALIZER_RVA);
    real_cint_setter=(CIntSetterFn)(main_base+PF_CINT_SETTER_RVA);
    return 0;
}

static int install_mutation(void *address, SIZE_T bytes,
    const void *expected, const void *replacement, DWORD original_protect,
    volatile LONG *installed, volatile LONG *journaled) {
    DWORD observed=0,ignored=0;
    BOOL protection_restored,flushed;
    if (!address || !bytes || !expected || !replacement ||
        !original_protect || memcmp(address,expected,bytes)!=0)
        return 0;
#ifdef PHOTON_V6_PF_SELECTOR_TEST_HOOKS
    {
        LONG fail_at=InterlockedCompareExchange(
            &test_fail_install_before_ordinal,0,0);
        if (fail_at>0 &&
            InterlockedDecrement(&test_fail_install_before_ordinal)==0) {
            InterlockedExchange(&test_fail_install_before_ordinal,-1);
            return 0;
        }
    }
#endif
    /* The production module is pinned before the first byte can change. */
    if (no_hot_lifecycle_enabled()) pin_adapter_module_or_failfast();
    if (
        !VirtualProtect(address,bytes,PAGE_EXECUTE_READWRITE,&observed))
        return 0;
    if (observed!=original_protect) {
        (void)VirtualProtect(address,bytes,observed,&ignored);
        (void)FlushInstructionCache(GetCurrentProcess(),address,bytes);
        return 0;
    }
    memcpy(address,replacement,bytes);
    mark_first_mutation_committed();
    if (InterlockedCompareExchange(journaled,1,0)==0)
        InterlockedIncrement(&mutation_journal_entries);
    InterlockedExchange(installed,1);
    protection_restored=VirtualProtect(address,bytes,original_protect,&ignored);
    flushed=FlushInstructionCache(GetCurrentProcess(),address,bytes);
    if (!(protection_restored && flushed &&
        page_protection_exact(address,bytes,original_protect) &&
        memcmp(address,replacement,bytes)==0)) {
        if (no_hot_lifecycle_enabled()) lifecycle_ambiguity_failfast();
        return 0;
    }
    return 1;
}

#ifdef PHOTON_V6_PF_SELECTOR_TEST_HOOKS
static int restore_mutation(void *address, SIZE_T bytes,
    const void *replacement, const void *original, DWORD original_protect,
    volatile LONG *installed) {
    DWORD observed=0,ignored=0;
    BOOL restored,flushed;
    if (!InterlockedCompareExchange(installed,0,0))
        return memcmp(address,original,bytes)==0 &&
            page_protection_exact(address,bytes,original_protect);
    if (memcmp(address,original,bytes)==0) {
        if (!page_protection_exact(address,bytes,original_protect)) {
            if (!VirtualProtect(address,bytes,original_protect,&ignored) ||
                !FlushInstructionCache(GetCurrentProcess(),address,bytes))
                return 0;
        }
    } else {
        if (memcmp(address,replacement,bytes)!=0 ||
            !VirtualProtect(address,bytes,PAGE_EXECUTE_READWRITE,&observed))
            return 0;
        memcpy(address,original,bytes);
        restored=VirtualProtect(address,bytes,original_protect,&ignored);
        flushed=FlushInstructionCache(GetCurrentProcess(),address,bytes);
        if (!restored || !flushed) return 0;
    }
    if (memcmp(address,original,bytes)!=0 ||
        !page_protection_exact(address,bytes,original_protect)) return 0;
    InterlockedExchange(installed,0);
    InterlockedIncrement(&restored_hook_count);
    return 1;
}
#endif

static LONG installed_hook_count(void) {
    LONG count=0;
    size_t index;
    for (index=0;index<sizeof(entry_hooks)/sizeof(entry_hooks[0]);++index)
        if (entry_hooks[index].installed) ++count;
    for (index=0;index<sizeof(call_hooks)/sizeof(call_hooks[0]);++index)
        if (call_hooks[index].installed) ++count;
    return count;
}

static LONG journaled_hook_count(void) {
    LONG count=0;
    size_t index;
    for (index=0;index<sizeof(entry_hooks)/sizeof(entry_hooks[0]);++index)
        if (entry_hooks[index].journaled) ++count;
    for (index=0;index<sizeof(call_hooks)/sizeof(call_hooks[0]);++index)
        if (call_hooks[index].journaled) ++count;
    return count;
}

static int entry_detour_bytes(const EntryHook *hook, BYTE output[16]) {
    if (!hook || hook->length<5 || hook->length>16) return 0;
    memset(output,0x90,hook->length);
    return make_relative(output,0xE9,hook->target,hook->replacement);
}

static int hook_sites_installed_exact(void) {
    BYTE detour[16];
    size_t index;
    for (index=0;index<sizeof(entry_hooks)/sizeof(entry_hooks[0]);++index) {
        EntryHook *hook=&entry_hooks[index];
        if (!hook->installed || !entry_detour_bytes(hook,detour) ||
            memcmp(hook->target,detour,hook->length)!=0 ||
            !page_protection_exact(hook->target,hook->length,
                hook->original_protect)) return 0;
    }
    for (index=0;index<sizeof(call_hooks)/sizeof(call_hooks[0]);++index) {
        CallHook *hook=&call_hooks[index];
        if (!hook->installed ||
            memcmp(hook->site,hook->replacement_bytes,5)!=0 ||
            !page_protection_exact(hook->site,5,hook->original_protect))
            return 0;
    }
    return 1;
}

static int hook_sites_restored_exact(void) {
    size_t index;
    for (index=0;index<sizeof(entry_hooks)/sizeof(entry_hooks[0]);++index) {
        EntryHook *hook=&entry_hooks[index];
        if (hook->installed || !hook->target ||
            memcmp(hook->target,hook->original,hook->length)!=0 ||
            !page_protection_exact(hook->target,hook->length,
                hook->original_protect)) return 0;
    }
    for (index=0;index<sizeof(call_hooks)/sizeof(call_hooks[0]);++index) {
        CallHook *hook=&call_hooks[index];
        if (hook->installed || !hook->site ||
            memcmp(hook->site,hook->original,5)!=0 ||
            !page_protection_exact(hook->site,5,hook->original_protect))
            return 0;
    }
    return 1;
}

static int install_hooks_unquiesced(void) {
    BYTE detour[16];
    size_t index;
    for (index=0;index<sizeof(entry_hooks)/sizeof(entry_hooks[0]);++index) {
        EntryHook *hook=&entry_hooks[index];
        if (!entry_detour_bytes(hook,detour) ||
            !install_mutation(hook->target,hook->length,hook->original,detour,
                hook->original_protect,&hook->installed,&hook->journaled))
            return 0;
    }
    for (index=0;index<sizeof(call_hooks)/sizeof(call_hooks[0]);++index) {
        CallHook *hook=&call_hooks[index];
        if (!install_mutation(hook->site,5,hook->original,
                hook->replacement_bytes,hook->original_protect,
                &hook->installed,&hook->journaled)) return 0;
    }
    return hook_sites_installed_exact() &&
        installed_hook_count()==EXPECTED_HOOK_COUNT &&
        InterlockedCompareExchange(&mutation_journal_entries,0,0)==
            EXPECTED_HOOK_COUNT;
}

#ifdef PHOTON_V6_PF_SELECTOR_TEST_HOOKS
static int restore_hooks_unquiesced(void) {
    BYTE detour[16];
    int good=1;
    size_t index=sizeof(call_hooks)/sizeof(call_hooks[0]);
    while (index-->0) {
        CallHook *hook=&call_hooks[index];
        if (hook->installed &&
            !restore_mutation(hook->site,5,hook->replacement_bytes,
                hook->original,hook->original_protect,&hook->installed))
            good=0;
    }
    index=sizeof(entry_hooks)/sizeof(entry_hooks[0]);
    while (index-->0) {
        EntryHook *hook=&entry_hooks[index];
        if (!entry_detour_bytes(hook,detour)) { good=0; continue; }
        if (hook->installed &&
            !restore_mutation(hook->target,hook->length,detour,
                hook->original,hook->original_protect,&hook->installed))
            good=0;
    }
    return good && installed_hook_count()==0 && hook_sites_restored_exact();
}
#endif

static int suspend_other_threads(SuspendedThread *threads, int capacity) {
    HANDLE snapshot=CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD,0);
    THREADENTRY32 entry;
    DWORD pid=GetCurrentProcessId(),own=GetCurrentThreadId();
    int count=0,failed=0;
    if (snapshot==INVALID_HANDLE_VALUE) return -1;
    memset(&entry,0,sizeof(entry)); entry.dwSize=sizeof(entry);
    if (Thread32First(snapshot,&entry)) do {
        HANDLE thread;
        CONTEXT context;
        if (entry.th32OwnerProcessID!=pid || entry.th32ThreadID==own) continue;
        if (count>=capacity) { failed=1; break; }
        thread=OpenThread(THREAD_SUSPEND_RESUME|THREAD_GET_CONTEXT,FALSE,
            entry.th32ThreadID);
        if (!thread || SuspendThread(thread)==(DWORD)-1) {
            if (thread) CloseHandle(thread);
            failed=1; break;
        }
        memset(&context,0,sizeof(context)); context.ContextFlags=CONTEXT_CONTROL;
        if (!GetThreadContext(thread,&context)) {
            ResumeThread(thread); CloseHandle(thread); failed=1; break;
        }
        threads[count].handle=thread; threads[count].eip=context.Eip; ++count;
    } while (Thread32Next(snapshot,&entry));
    CloseHandle(snapshot);
    if (failed) {
        while (count-->0) {
            ResumeThread(threads[count].handle);
            CloseHandle(threads[count].handle);
        }
        return -1;
    }
    return count;
}

static int resume_threads(SuspendedThread *threads, int count) {
    int good=1;
    while (count-->0) {
        if (ResumeThread(threads[count].handle)==(DWORD)-1) good=0;
        CloseHandle(threads[count].handle);
    }
    return good;
}

static int eip_inside(DWORD eip, const void *start, SIZE_T bytes) {
    return (uintptr_t)eip>=(uintptr_t)start &&
        (uintptr_t)eip<(uintptr_t)start+bytes;
}

static int patch_contexts_safe(const SuspendedThread *threads, int count) {
    int index;
    size_t hook_index;
    if (InterlockedCompareExchange(&hook_inflight,0,0)!=0) return 0;
    for (index=0;index<count;++index) {
        for (hook_index=0;
             hook_index<sizeof(entry_hooks)/sizeof(entry_hooks[0]);
             ++hook_index) {
            EntryHook *hook=&entry_hooks[hook_index];
            if (eip_inside(threads[index].eip,hook->target,hook->length) ||
                threads[index].eip==(DWORD)(uintptr_t)hook->replacement ||
                (hook->trampoline && eip_inside(threads[index].eip,
                    hook->trampoline,hook->length+5))) return 0;
        }
        for (hook_index=0;
             hook_index<sizeof(call_hooks)/sizeof(call_hooks[0]);
             ++hook_index)
            if (eip_inside(threads[index].eip,call_hooks[hook_index].site,5) ||
                threads[index].eip==(DWORD)(uintptr_t)
                    call_hooks[hook_index].replacement)
                return 0;
    }
    return 1;
}

static int quiescent_install(void) {
    SuspendedThread threads[MAX_SUSPENDED_THREADS];
    int count=suspend_other_threads(threads,MAX_SUSPENDED_THREADS);
    int good=count>=0 && patch_contexts_safe(threads,count) &&
        install_hooks_unquiesced();
#ifdef PHOTON_V6_PF_SELECTOR_TEST_HOOKS
    if (!good && installed_hook_count() && !no_hot_lifecycle_enabled())
        good=restore_hooks_unquiesced() && 0;
#endif
    if (count>=0 && !resume_threads(threads,count)) good=0;
    return good;
}

#ifdef PHOTON_V6_PF_SELECTOR_TEST_HOOKS
static int quiescent_restore_once(void) {
    SuspendedThread threads[MAX_SUSPENDED_THREADS];
    int count=suspend_other_threads(threads,MAX_SUSPENDED_THREADS);
    int good=count>=0 && patch_contexts_safe(threads,count) &&
        restore_hooks_unquiesced();
    if (count>=0 && !resume_threads(threads,count)) good=0;
    return good;
}
#endif

static int wait_for_counted_hooks_to_exit(void) {
    int retry;
    for (retry=0;retry<RESTORE_RETRIES*25;++retry) {
        if (InterlockedCompareExchange(&hook_inflight,0,0)==0) return 1;
        Sleep(1);
    }
    return InterlockedCompareExchange(&hook_inflight,0,0)==0;
}

#ifdef PHOTON_V6_PF_SELECTOR_TEST_HOOKS
static int rollback_post_install_failure(void) {
    int exact=0,retry;
    AcquireSRWLockExclusive(&patch_lock);
    for (retry=0;retry<RESTORE_RETRIES;++retry) {
        if (InterlockedCompareExchange(&hook_inflight,0,0)==0 &&
            quiescent_restore_once()) { exact=1; break; }
        Sleep(25);
    }
    ReleaseSRWLockExclusive(&patch_lock);
    exact=exact && wait_for_counted_hooks_to_exit() &&
        installed_hook_count()==0 &&
        journaled_hook_count()==EXPECTED_HOOK_COUNT &&
        InterlockedCompareExchange(&restored_hook_count,0,0)==
            EXPECTED_HOOK_COUNT && hook_sites_restored_exact();
    if (exact) {
        free_trampolines();
        InterlockedExchange(&hooks_restored_exact,1);
        main_base=NULL;
    }
    return exact;
}
#endif

static void pin_adapter_module_or_failfast(void) {
    HMODULE self=NULL,pinned=NULL;
    const void *anchor=(const void *)&photon_v6_pf_selector_adapter_init;
    if (!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS |
            GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
            (LPCWSTR)anchor,&self) || !self ||
        !GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS |
            GET_MODULE_HANDLE_EX_FLAG_PIN,(LPCWSTR)anchor,&pinned) ||
        !pinned || pinned!=self) {
        RaiseFailFastException(NULL,NULL,0);
        TerminateProcess(GetCurrentProcess(),UINT32_C(0xE00057A4));
    }
    InterlockedExchange(&module_pinned,1);
}

static void mark_first_mutation_committed(void) {
    InterlockedExchange(&first_mutation_committed,1);
    if (no_hot_lifecycle_enabled()) {
        if (!InterlockedCompareExchange(&module_pinned,0,0))
            pin_adapter_module_or_failfast();
        InterlockedExchange(&hooks_retained_until_process_exit,1);
    }
}

static int lifecycle_latch_and_drain_write_leases(void) {
    DWORD tid=GetCurrentThreadId();
    int admission_closed=0;
    int lifecycle_owns_transition=0;

    /* Lifecycle admission is a separate, irreversible process-generation
     * gate.  Close it under the same lock used by both lease classes and by
     * language-transition acquisition.  Release paths deliberately ignore
     * this gate so already-admitted writers can drain. */
    AcquireSRWLockExclusive(&state_lock);
    if (!InterlockedCompareExchange(&lifecycle_admission_revoked,0,0))
        InterlockedExchange(&lifecycle_admission_revoked,1);
    admission_closed=
        InterlockedCompareExchange(&lifecycle_admission_revoked,0,0)==1;
    if (!admission_closed || !lease_census_exact_locked() ||
        current_thread_owns_write_lease_locked() ||
        (InterlockedCompareExchange(
             &language_transition_inflight,0,0)==1 &&
         InterlockedCompareExchange(
             &language_transition_owner_tid,0,0)==(LONG)tid)) {
        ReleaseSRWLockExclusive(&state_lock);
        return 0;
    }
    ReleaseSRWLockExclusive(&state_lock);

    for (;;) {
        int exact,owns;
        LONG total,transition,owner;
        AcquireSRWLockExclusive(&state_lock);
        admission_closed=
            InterlockedCompareExchange(&lifecycle_admission_revoked,0,0)==1;
        exact=lease_census_exact_locked();
        owns=current_thread_owns_write_lease_locked();
        total=InterlockedCompareExchange(&translation_write_leases,0,0);
        transition=InterlockedCompareExchange(
            &language_transition_inflight,0,0);
        owner=InterlockedCompareExchange(&language_transition_owner_tid,0,0);
        if (!admission_closed || !exact || owns ||
            (transition!=0 && transition!=1) ||
            (transition==0 && owner!=0) ||
            (transition==1 && owner==0) ||
            (transition==1 && owner==(LONG)tid &&
             !lifecycle_owns_transition)) {
            ReleaseSRWLockExclusive(&state_lock);
            return 0;
        }
#ifdef PHOTON_V6_PF_SELECTOR_TEST_HOOKS
        if (transition==0 && !lifecycle_owns_transition &&
            InterlockedCompareExchange(
                &test_lifecycle_claim_pause_enabled,0,0) &&
            InterlockedCompareExchange(
                &test_lifecycle_claim_pause_reached,1,0)==0) {
            ReleaseSRWLockExclusive(&state_lock);
            while (!InterlockedCompareExchange(
                    &test_lifecycle_claim_pause_release,0,0)) Sleep(1);
            continue;
        }
#endif
        if (transition==0 &&
            InterlockedCompareExchange(&language_transition_inflight,1,0)==0) {
            InterlockedExchange(&language_transition_owner_tid,(LONG)tid);
            lifecycle_owns_transition=1;
        }
        if (lifecycle_owns_transition && total==0 &&
            lease_census_exact_locked() &&
            InterlockedCompareExchange(&lifecycle_admission_revoked,0,0)==1 &&
            InterlockedCompareExchange(
                &language_transition_inflight,0,0)==1 &&
            InterlockedCompareExchange(
                &language_transition_owner_tid,0,0)==(LONG)tid) {
            ReleaseSRWLockExclusive(&state_lock);
            return 1;
        }
        ReleaseSRWLockExclusive(&state_lock);
        Sleep(1);
    }
}

static int enter_no_hot_retained_state(int fatal_failure) {
    if (InterlockedCompareExchange(&first_mutation_committed,0,0) ||
        installed_hook_count()!=0 || journaled_hook_count()!=0) {
        pin_adapter_module_or_failfast();
        InterlockedExchange(&hooks_retained_until_process_exit,1);
    }
    /* Revocation is ordered before semantic pass-through.  Existing ordinary
     * and special writers retain their release path while the latch blocks
     * new leases and relevant native language stores. */
    if (!lifecycle_latch_and_drain_write_leases()) {
        set_fatal();
#ifndef PHOTON_V6_PF_SELECTOR_TEST_HOOKS
        RaiseFailFastException(NULL,NULL,0);
        TerminateProcess(GetCurrentProcess(),UINT32_C(0xE00057A7));
#endif
        return 0;
    }
    AcquireSRWLockExclusive(&state_lock);
    if (InterlockedCompareExchange(&lifecycle_admission_revoked,0,0)!=1 ||
        InterlockedCompareExchange(&language_transition_inflight,0,0)!=1 ||
        InterlockedCompareExchange(&language_transition_owner_tid,0,0)!=
            (LONG)GetCurrentThreadId() ||
        InterlockedCompareExchange(&translation_write_leases,0,0)!=0 ||
        InterlockedCompareExchange(&ordinary_write_leases,0,0)!=0 ||
        InterlockedCompareExchange(&special_write_leases,0,0)!=0 ||
        !lease_census_exact_locked()) {
        ReleaseSRWLockExclusive(&state_lock);
        set_fatal();
#ifndef PHOTON_V6_PF_SELECTOR_TEST_HOOKS
        RaiseFailFastException(NULL,NULL,0);
        TerminateProcess(GetCurrentProcess(),UINT32_C(0xE00057A8));
#endif
        return 0;
    }
    InterlockedExchange(&semantic_gate_disabled,1);
    InterlockedExchange(&shutting_down,1);
    InterlockedExchange(&initialized,0);
    ReleaseSRWLockExclusive(&state_lock);
    if (fatal_failure) set_fatal();
    return 1;
}

static void lifecycle_ambiguity_failfast(void) {
    /* Called with peer threads potentially suspended by install.  Never take
     * state/telemetry locks here: initialization has not published semantics
     * and therefore has no leases to drain. */
    pin_adapter_module_or_failfast();
    InterlockedExchange(&hooks_retained_until_process_exit,1);
    InterlockedExchange(&lifecycle_admission_revoked,1);
    InterlockedExchange(&language_transition_owner_tid,
        (LONG)GetCurrentThreadId());
    InterlockedExchange(&language_transition_inflight,1);
    InterlockedExchange(&semantic_gate_disabled,1);
    InterlockedExchange(&shutting_down,1);
    InterlockedExchange(&initialized,0);
    InterlockedExchange(&fatal_latch,1);
#ifndef PHOTON_V6_PF_SELECTOR_TEST_HOOKS
    RaiseFailFastException(NULL,NULL,0);
    TerminateProcess(GetCurrentProcess(),UINT32_C(0xE00057A6));
#endif
}

static void reset_runtime_state(void) {
    AcquireSRWLockExclusive(&state_lock);
    memset(graph_epochs,0,sizeof(graph_epochs));
    memset(cref_bindings,0,sizeof(cref_bindings));
    memset(active_materializations,0,sizeof(active_materializations));
    memset(object_bindings,0,sizeof(object_bindings));
    memset(active_surfaces,0,sizeof(active_surfaces));
    memset(ordinary_write_lease_slots,0,sizeof(ordinary_write_lease_slots));
    ReleaseSRWLockExclusive(&state_lock);
    telemetry_begin();
    InterlockedExchange(&language_state,
        PHOTON_V6_PF_SELECTOR_LANGUAGE_UNKNOWN);
    InterlockedExchange(&language_state_sequence,0);
    InterlockedExchange(&graph_epoch_sequence,0);
    InterlockedExchange(&graph_enter_sequence,0);
    InterlockedExchange(&cref_identity_sequence,0);
    InterlockedExchange(&materializer_sequence,0);
    InterlockedExchange(&object_generation_sequence,0);
    InterlockedExchange(&surface_sequence,0);
    InterlockedExchange(&language_transition_inflight,0);
    InterlockedExchange(&language_transition_owner_tid,0);
    InterlockedExchange(&lifecycle_admission_revoked,0);
    InterlockedExchange(&translation_write_leases,0);
    InterlockedExchange(&ordinary_write_leases,0);
    InterlockedExchange(&special_write_leases,0);
    InterlockedExchange(&ordinary_lease_sequence,0);
    InterlockedExchangePointer((void *volatile *)&language_cint_this,NULL);
    InterlockedExchangePointer((void *volatile *)&language_cint_owner,NULL);
    InterlockedExchange(&language_scan_inflight,0);
    InterlockedExchange(&language_scan_last_tick,0);
    InterlockedExchange(&language_bootstrap_exact_events,0);
    InterlockedExchange(&language_bootstrap_conflict_rejects,0);
    InterlockedExchange(&language_setter_exact_events,0);
    InterlockedExchange(&global_language_generation_purges,0);
    InterlockedExchange(&graph_begin_events,0);
    InterlockedExchange(&graph_end_events,0);
    InterlockedExchange(&graph_supersession_purges,0);
    InterlockedExchange(&graph_identity_rejects,0);
    InterlockedExchange(&cref_identity_events,0);
    InterlockedExchange(&cref_identity_rejects,0);
    InterlockedExchange(&materializer_entry_events,0);
    InterlockedExchange(&materializer_load_candidates,0);
    InterlockedExchange(&materializer_fresh_commits,0);
    InterlockedExchange(&materializer_cached_commits,0);
    InterlockedExchange(&materializer_identity_rejects,0);
    InterlockedExchange(&payload_sha256_rejects,0);
    InterlockedExchange(&state0_translation_endpoint_rejects,0);
    InterlockedExchange(&c07_all_provider_rejects,0);
    InterlockedExchange(&exact_surface_entries,0);
    InterlockedExchange(&surface_identity_rejects,0);
    InterlockedExchange(&exact_decode_queries,0);
    InterlockedExchange(&decode_identity_rejects,0);
    InterlockedExchange(&translation_special57_allows,0);
    InterlockedExchange(&stale_generation_rejects,0);
    InterlockedExchange(&cross_thread_rejects,0);
    InterlockedExchange(&ordinary_lease_acquires,0);
    InterlockedExchange(&ordinary_lease_rejects,0);
    InterlockedExchange(&ordinary_lease_releases,0);
    InterlockedExchange(&ordinary_lease_generation_rejects,0);
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
    InterlockedExchange(&diagnostic_pipeline_flags,0);
    InterlockedExchange(&diagnostic_native_gate_code,0);
    InterlockedExchange(&diagnostic_transition_failure_bits,0);
    InterlockedExchange(&diagnostic_transition_requested_value,0);
    InterlockedExchange(&diagnostic_transition_previous_value,0);
    InterlockedExchange(&diagnostic_transition_stored_value,0);
    InterlockedExchange(&diagnostic_transition_finish_condition_bits,0);
    InterlockedExchange(&diagnostic_transition_self,0);
    InterlockedExchange(&diagnostic_transition_cint_owner,0);
    InterlockedExchange(&diagnostic_transition_known_this,0);
    InterlockedExchange(&diagnostic_transition_known_owner,0);
    InterlockedExchange(&diagnostic_last_special_clear_event_sequence,0);
    InterlockedExchange(&diagnostic_last_special_clear_reason,0);
    InterlockedExchange(&diagnostic_last_special_clear_object,0);
    InterlockedExchange(&diagnostic_last_special_clear_node,0);
    InterlockedExchange(&diagnostic_last_special_clear_target_plus_one,0);
    InterlockedExchange(
        &diagnostic_last_special_clear_materializer_sequence,0);
    InterlockedExchange(&diagnostic_last_special_clear_object_generation,0);
    InterlockedExchange(
        &diagnostic_last_special_clear_route_index_plus_one,0);
    InterlockedExchange(&diagnostic_last_special_clear_cref_sequence,0);
    InterlockedExchange(&diagnostic_last_special_clear_language_sequence,0);
    InterlockedExchange(&diagnostic_special_materializer_persistent,0);
    InterlockedExchange(&diagnostic_special_materializer_node_exact,0);
    InterlockedExchange(&diagnostic_special_materializer_route_exact,0);
    InterlockedExchange(
        &diagnostic_special_materializer_route_index_plus_one,0);
    InterlockedExchange(&diagnostic_special_materializer_raw_handle,0);
    InterlockedExchange(&diagnostic_special_materializer_cref_sequence,0);
    InterlockedExchange(&diagnostic_special_materializer_language_sequence,0);
    InterlockedExchange(&diagnostic_special_note_active_found,0);
    InterlockedExchange(&diagnostic_special_note_active_route_exact,0);
#endif
    InterlockedExchange(&fatal_latch,0);
    telemetry_end();
}

int __attribute__((cdecl)) photon_v6_pf_selector_adapter_note_load(
    void *cr6_object, const void *payload, uint32_t payload_bytes,
    uint64_t payload_fnv1a64, PhotonV6PfSelectorDecision *decision) {
    ActiveMaterialization active;
    PendingLoad pending;
    ObjectBinding stale_binding;
    uint64_t actual_hash;
    BYTE digest[32];
    int target=-1,weak_target=-1,recorded=0,stale_found=0;
    int active_found=0,active_route_exact=0;
    LONG state,sequence;
    const RouteDef *selected_route=NULL;
    InterlockedIncrement(&hook_inflight);
    decision_initialize(decision,PHOTON_V6_PF_SELECTOR_NOT_SPECIAL);
    if (!decision || !cr6_object || !payload || !payload_bytes ||
        payload_bytes>MAX_PAYLOAD_BYTES || !range_readable(payload,payload_bytes)) {
        if (decision) decision->decision=
            PHOTON_V6_PF_SELECTOR_REJECT_INVALID_ARGUMENT;
        InterlockedDecrement(&hook_inflight);
        return 0;
    }
    if (!InterlockedCompareExchange(&initialized,0,0) ||
        InterlockedCompareExchange(&shutting_down,0,0) ||
        InterlockedCompareExchange(&fatal_latch,0,0) ||
        InterlockedCompareExchange(&lifecycle_admission_revoked,0,0) ||
        InterlockedCompareExchange(&language_transition_inflight,0,0)) {
        decision->decision=PHOTON_V6_PF_SELECTOR_REJECT_FATAL_LATCHED;
        InterlockedDecrement(&hook_inflight);
        return 0;
    }
    actual_hash=fnv1a64((const BYTE *)payload,payload_bytes);
    sha256_digest((const BYTE *)payload,payload_bytes,digest);
    memset(&stale_binding,0,sizeof(stale_binding));
    stale_found=binding_snapshot(cr6_object,&stale_binding);
    weak_target=find_target_deny_tombstone(payload_bytes,actual_hash);
    target=find_target_exact(payload_bytes,actual_hash,digest);
    if (target<0) {
        if (weak_target>=0) {
            decision_set_deny_tombstone(decision,
                PHOTON_V6_PF_SELECTOR_REJECT_PAYLOAD_IDENTITY,weak_target,
                payload_bytes,actual_hash,digest);
            telemetry_increment(&payload_sha256_rejects);
        } else if (stale_found) {
            decision_set_binding_deny_tombstone(decision,
                PHOTON_V6_PF_SELECTOR_REJECT_PAYLOAD_IDENTITY,
                &stale_binding);
            telemetry_increment(&stale_generation_rejects);
        } else if (actual_hash!=payload_fnv1a64)
            telemetry_increment(&payload_sha256_rejects);
        clear_object_binding(cr6_object,NULL,
            OBJECT_BINDING_CLEAR_NOTE_NOT_TARGET);
        InterlockedDecrement(&hook_inflight);
        return 0;
    }
    decision->target_index=(uint32_t)target;
    decision->payload_bytes=payload_bytes;
    decision->payload_fnv1a64=actual_hash;
    memcpy(decision->payload_sha256,digest,32);
    if (actual_hash!=payload_fnv1a64 ||
        safe_pointer(cr6_object,0x18)!=(uintptr_t)payload ||
        safe_u32(cr6_object,0x58)!=payload_bytes ||
        !cr6_object_invariants_exact(cr6_object)) {
        decision->decision=PHOTON_V6_PF_SELECTOR_REJECT_PAYLOAD_IDENTITY;
        telemetry_increment(&payload_sha256_rejects);
        clear_object_binding(cr6_object,NULL,
            OBJECT_BINDING_CLEAR_NOTE_IDENTITY_REJECT);
        InterlockedDecrement(&hook_inflight);
        return 0;
    }
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
    diagnostic_capture_special_load(cr6_object);
    InterlockedOr(&diagnostic_pipeline_flags,0x0020);
#endif
    clear_object_binding(cr6_object,NULL,
        OBJECT_BINDING_CLEAR_NOTE_TARGET_PREPARE);
    memset(&active,0,sizeof(active));
    active_found=active_materialization_snapshot(&active);
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
    if (active_found) InterlockedOr(&diagnostic_pipeline_flags,0x0040);
#endif
    active_route_exact=active_found && route_still_exact(&active.route);
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
    InterlockedExchange(&diagnostic_special_note_active_found,active_found);
    InterlockedExchange(&diagnostic_special_note_active_route_exact,
        active_route_exact);
    if (active_route_exact) InterlockedOr(&diagnostic_pipeline_flags,0x0080);
#endif
    if (!active_found || !active_route_exact) {
        decision->decision=PHOTON_V6_PF_SELECTOR_REJECT_CAUSAL_IDENTITY;
        telemetry_increment(&materializer_identity_rejects);
        InterlockedDecrement(&hook_inflight);
        return 0;
    }
    state=InterlockedCompareExchange(&language_state,0,0);
    sequence=InterlockedCompareExchange(&language_state_sequence,0,0);
    memset(&pending,0,sizeof(pending));
    pending.object=cr6_object; pending.payload=payload;
    pending.payload_bytes=payload_bytes; pending.payload_fnv1a64=actual_hash;
    memcpy(pending.payload_sha256,digest,32);
    pending.target_index=target;
    pending.exact=state==active.language_state &&
        sequence==active.language_sequence;
    recorded=record_pending_load(active.sequence,&pending);
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
    if (recorded&&pending.exact)
        InterlockedOr(&diagnostic_pipeline_flags,0x0100);
#endif
    telemetry_increment(&materializer_load_candidates);
    selected_route=&routes[active.route.route_index];
    decision->raw_handle=active.route.raw_handle;
    decision->provider_role=route_provider_role(selected_route);
    decision->special_source_asset_id=selected_route->source_asset_id;
    decision->special_context_identity_key=selected_route->context_identity_key;
    decision->selected_cref_identity_sequence=
        (uint32_t)active.route.cref_identity_sequence;
    decision->selected_materializer_sequence=(uint32_t)active.sequence;
    decision->graph_root=(uintptr_t)active.route.graph_root;
    decision->selected_resource_node=(uintptr_t)active.resource_node;
    decision->selected_cr6_object=(uintptr_t)cr6_object;
    decision->target_payload_exact=recorded&&pending.exact?1U:0U;
    if ((target==5 ||
         routes[active.route.route_index].group_target_index==5) &&
        !route_is_translation_provider(selected_route,target)) {
        decision->decision=PHOTON_V6_PF_SELECTOR_REJECT_C07_ALL_PROVIDERS;
        telemetry_increment(&c07_all_provider_rejects);
    } else if (state==PHOTON_V6_PF_SELECTOR_LANGUAGE_JAPANESE) {
        decision->decision=
            PHOTON_V6_PF_SELECTOR_REJECT_JAPANESE_TRANSLATION_ENDPOINT;
        telemetry_increment(&state0_translation_endpoint_rejects);
    } else if (state!=PHOTON_V6_PF_SELECTOR_LANGUAGE_TRANSLATION) {
        decision->decision=PHOTON_V6_PF_SELECTOR_REJECT_UNKNOWN_LANGUAGE;
    } else {
        /* Pending only: an exact candidate is still not a pixel authorization. */
        decision->decision=PHOTON_V6_PF_SELECTOR_REJECT_CAUSAL_IDENTITY;
    }
    InterlockedDecrement(&hook_inflight);
    return recorded&&pending.exact;
}

int __attribute__((cdecl)) photon_v6_pf_selector_adapter_surface_enter(
    void *cr6_object, PhotonV6PfSelectorDecision *decision) {
    ObjectBinding binding;
    LONG sequence=0;
    const void *payload=NULL;
    uint32_t bytes=0;
    uint64_t hash=0;
    BYTE digest[32];
    int target=-1,binding_found,binding_exact;
    InterlockedIncrement(&hook_inflight);
    decision_initialize(decision,PHOTON_V6_PF_SELECTOR_NOT_SPECIAL);
    if (!decision || !cr6_object) {
        if (decision) decision->decision=
            PHOTON_V6_PF_SELECTOR_REJECT_INVALID_ARGUMENT;
        InterlockedDecrement(&hook_inflight);
        return 0;
    }
    if (!InterlockedCompareExchange(&initialized,0,0) ||
        InterlockedCompareExchange(&shutting_down,0,0) ||
        InterlockedCompareExchange(&fatal_latch,0,0) ||
        InterlockedCompareExchange(&lifecycle_admission_revoked,0,0) ||
        InterlockedCompareExchange(&language_transition_inflight,0,0)) {
        decision->decision=PHOTON_V6_PF_SELECTOR_REJECT_FATAL_LATCHED;
        InterlockedDecrement(&hook_inflight);
        return 0;
    }
    memset(&binding,0,sizeof(binding));
    binding_found=binding_snapshot(cr6_object,&binding);
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
    diagnostic_surface_binding_ladder(cr6_object,
        binding_found?&binding:NULL);
#endif
    binding_exact=binding_found && binding_revalidate_exact(&binding);
    if (!binding_found || !binding_exact) {
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
        diagnostic_persist_surface_failure(cr6_object,&binding,binding_found,
            binding_exact,0);
#endif
        clear_object_binding(cr6_object,NULL,
            OBJECT_BINDING_CLEAR_SURFACE_REJECT);
        if (binding.active) {
            decision_set_binding_deny_tombstone(decision,
                PHOTON_V6_PF_SELECTOR_REJECT_CAUSAL_IDENTITY,&binding);
            telemetry_increment(&stale_generation_rejects);
        } else if (payload_identity(
                cr6_object,&payload,&bytes,&hash,digest,&target) ||
            payload_deny_tombstone(
                cr6_object,&payload,&bytes,&hash,digest,&target)) {
            decision->target_index=(uint32_t)target;
            decision->payload_bytes=bytes;
            decision->payload_fnv1a64=hash;
            memcpy(decision->payload_sha256,digest,32);
            if (target==5) {
                decision->decision=
                    PHOTON_V6_PF_SELECTOR_REJECT_C07_ALL_PROVIDERS;
                telemetry_increment(&c07_all_provider_rejects);
            } else if (decision->language_state==
                PHOTON_V6_PF_SELECTOR_LANGUAGE_JAPANESE) {
                decision->decision=
                    PHOTON_V6_PF_SELECTOR_REJECT_JAPANESE_TRANSLATION_ENDPOINT;
                telemetry_increment(&state0_translation_endpoint_rejects);
            } else {
                decision->decision=
                    PHOTON_V6_PF_SELECTOR_REJECT_CAUSAL_IDENTITY;
                telemetry_increment(&surface_identity_rejects);
            }
        }
        InterlockedDecrement(&hook_inflight);
        return 0;
    }
    if (!push_surface(&binding,&sequence)) {
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
        diagnostic_persist_surface_failure(cr6_object,&binding,binding_found,
            binding_exact,0);
#endif
        decision->decision=PHOTON_V6_PF_SELECTOR_REJECT_CAUSAL_IDENTITY;
        telemetry_increment(&surface_identity_rejects);
        InterlockedDecrement(&hook_inflight);
        return 0;
    }
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
    if ((LONG)(uintptr_t)cr6_object==InterlockedCompareExchange(
            &diagnostic_special_cr6_object,0,0))
        InterlockedOr(&diagnostic_pipeline_flags,0x00800000);
#endif
    decision_from_binding(&binding,sequence,0,decision);
    telemetry_increment(&exact_surface_entries);
    InterlockedDecrement(&hook_inflight);
    return 1;
}

int __attribute__((cdecl)) photon_v6_pf_selector_adapter_decode_query(
    PhotonV6PfSelectorDecision *decision) {
    ActiveSurface surface;
    int surface_found,binding_exact,lease_exact;
    InterlockedIncrement(&hook_inflight);
    decision_initialize(decision,PHOTON_V6_PF_SELECTOR_NOT_SPECIAL);
    if (!decision) {
        InterlockedDecrement(&hook_inflight);
        return 0;
    }
    if (!InterlockedCompareExchange(&initialized,0,0) ||
        InterlockedCompareExchange(&shutting_down,0,0) ||
        InterlockedCompareExchange(&fatal_latch,0,0) ||
        InterlockedCompareExchange(&lifecycle_admission_revoked,0,0) ||
        InterlockedCompareExchange(&language_transition_inflight,0,0)) {
        decision->decision=PHOTON_V6_PF_SELECTOR_REJECT_FATAL_LATCHED;
        InterlockedDecrement(&hook_inflight);
        return 0;
    }
    memset(&surface,0,sizeof(surface));
    surface_found=surface_snapshot(&surface,1);
    if (!surface_found) {
        InterlockedDecrement(&hook_inflight);
        return 0;
    }
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
    if ((LONG)(uintptr_t)surface.binding.object==InterlockedCompareExchange(
            &diagnostic_special_cr6_object,0,0))
        InterlockedOr(&diagnostic_pipeline_flags,0x01000000);
#endif
    binding_exact=surface.sequence>0 &&
        binding_revalidate_exact(&surface.binding);
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
    if (binding_exact && (LONG)(uintptr_t)surface.binding.object==
            InterlockedCompareExchange(&diagnostic_special_cr6_object,0,0))
        InterlockedOr(&diagnostic_pipeline_flags,0x02000000);
#endif
    lease_exact=binding_exact &&
        acquire_surface_authorization_lease(surface.sequence);
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
    if (lease_exact && (LONG)(uintptr_t)surface.binding.object==
            InterlockedCompareExchange(&diagnostic_special_cr6_object,0,0))
        InterlockedOr(&diagnostic_pipeline_flags,0x04000000);
#endif
    if (!binding_exact || !lease_exact) {
        (void)abort_top_surface();
        decision->decision=PHOTON_V6_PF_SELECTOR_REJECT_CAUSAL_IDENTITY;
        telemetry_increment(&decode_identity_rejects);
        set_fatal();
        InterlockedDecrement(&hook_inflight);
        return 0;
    }
    decision_from_binding(&surface.binding,surface.sequence,1,decision);
    telemetry_increment(&exact_decode_queries);
    telemetry_increment(&translation_special57_allows);
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
    if ((LONG)(uintptr_t)surface.binding.object==InterlockedCompareExchange(
            &diagnostic_special_cr6_object,0,0))
        InterlockedOr(&diagnostic_pipeline_flags,0x08000000);
#endif
    InterlockedDecrement(&hook_inflight);
    return 1;
}

#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
void __attribute__((cdecl))
photon_v6_pf_selector_adapter_diagnostic_native_gate(uint32_t code) {
    if (code)
        InterlockedCompareExchange(
            &diagnostic_native_gate_code,(LONG)code,0);
}
#endif

void __attribute__((cdecl)) photon_v6_pf_selector_adapter_surface_leave(
    void *cr6_object) {
    ActiveSurface surface;
    int popped,release_exact=0,close_exact=0;
    InterlockedIncrement(&hook_inflight);
    memset(&surface,0,sizeof(surface));
    popped=mark_surface_closing(cr6_object,&surface);
    if (popped>0)
        release_exact=binding_revalidate_for_release(&surface.binding);
    if (popped>0)
        close_exact=finish_surface_close(surface.sequence);
    if (popped<=0) {
        telemetry_increment(&surface_identity_rejects);
        set_fatal();
    } else if (!release_exact || !close_exact) {
        clear_object_binding(cr6_object,NULL,
            OBJECT_BINDING_CLEAR_SURFACE_RELEASE);
        telemetry_increment(&surface_identity_rejects);
        set_fatal();
    }
    InterlockedDecrement(&hook_inflight);
}

int __attribute__((cdecl)) photon_v6_pf_selector_adapter_language_query(
    int32_t *output_state, uint32_t *output_sequence,
    uint32_t *allow_translation) {
    LONG state,sequence;
    int allowed;
    if (!output_state || !output_sequence || !allow_translation) return 0;
    (void)refresh_live_image_language(0);
    /* Diagnostic coherent snapshot only.  Pixel writes must use the lease API
     * below; this snapshot can become stale immediately after return. */
    AcquireSRWLockShared(&state_lock);
    state=InterlockedCompareExchange(&language_state,0,0);
    sequence=InterlockedCompareExchange(&language_state_sequence,0,0);
    allowed=InterlockedCompareExchange(&initialized,0,0) &&
        !InterlockedCompareExchange(&shutting_down,0,0) &&
        !InterlockedCompareExchange(&fatal_latch,0,0) &&
        !InterlockedCompareExchange(&lifecycle_admission_revoked,0,0) &&
        !InterlockedCompareExchange(&language_transition_inflight,0,0) &&
        state==PHOTON_V6_PF_SELECTOR_LANGUAGE_TRANSLATION && sequence>0;
    *output_state=(int32_t)state;
    *output_sequence=(uint32_t)sequence;
    *allow_translation=allowed?1U:0U;
    ReleaseSRWLockShared(&state_lock);
    return allowed;
}

int __attribute__((cdecl)) photon_v6_pf_selector_adapter_ordinary_lease_acquire(
    uint32_t *lease_token, uint32_t *language_generation) {
    OrdinaryWriteLease *slot=NULL;
    LONG token=0,generation=0;
    int acquired=0;
    size_t index;
    InterlockedIncrement(&hook_inflight);
    if (lease_token) *lease_token=0;
    if (language_generation) *language_generation=0;
    if (!lease_token || !language_generation) goto done;
    AcquireSRWLockExclusive(&state_lock);
    generation=InterlockedCompareExchange(&language_state_sequence,0,0);
    if (!InterlockedCompareExchange(&initialized,0,0) ||
        InterlockedCompareExchange(&shutting_down,0,0) ||
        InterlockedCompareExchange(&fatal_latch,0,0) ||
        InterlockedCompareExchange(&lifecycle_admission_revoked,0,0) ||
        InterlockedCompareExchange(&language_transition_inflight,0,0) ||
        InterlockedCompareExchange(&language_state,0,0)!=
            PHOTON_V6_PF_SELECTOR_LANGUAGE_TRANSLATION ||
        generation<=0 || !lease_census_exact_locked()) goto unlock;
    for (index=0;index<MAX_ORDINARY_WRITE_LEASES;++index)
        if (!ordinary_write_lease_slots[index].active) {
            slot=&ordinary_write_lease_slots[index]; break;
        }
    if (!slot) goto unlock;
    token=InterlockedIncrement(&ordinary_lease_sequence);
    if (token<=0) { set_fatal(); goto unlock; }
    memset(slot,0,sizeof(*slot));
    slot->tid=GetCurrentThreadId();
    slot->token=token;
    slot->language_generation=generation;
    MemoryBarrier();
    slot->active=1;
    InterlockedIncrement(&ordinary_write_leases);
    InterlockedIncrement(&translation_write_leases);
    if (!lease_census_exact_locked() ||
        InterlockedCompareExchange(&lifecycle_admission_revoked,0,0)!=0 ||
        InterlockedCompareExchange(&language_transition_inflight,0,0)!=0 ||
        InterlockedCompareExchange(&fatal_latch,0,0)!=0 ||
        InterlockedCompareExchange(&language_state,0,0)!=
            PHOTON_V6_PF_SELECTOR_LANGUAGE_TRANSLATION ||
        generation!=InterlockedCompareExchange(
            &language_state_sequence,0,0)) {
        memset(slot,0,sizeof(*slot));
        InterlockedDecrement(&ordinary_write_leases);
        InterlockedDecrement(&translation_write_leases);
        if (!lease_census_exact_locked()) set_fatal();
        slot=NULL;
        goto unlock;
    }
    *lease_token=(uint32_t)token;
    *language_generation=(uint32_t)generation;
    acquired=1;
unlock:
    ReleaseSRWLockExclusive(&state_lock);
done:
    telemetry_increment(acquired?&ordinary_lease_acquires:
        &ordinary_lease_rejects);
    InterlockedDecrement(&hook_inflight);
    return acquired;
}

int __attribute__((cdecl)) photon_v6_pf_selector_adapter_ordinary_lease_validate(
    uint32_t lease_token, uint32_t language_generation) {
    DWORD tid=GetCurrentThreadId();
    int exact=0;
    size_t index;
    InterlockedIncrement(&hook_inflight);
    AcquireSRWLockShared(&state_lock);
    if (lease_token && language_generation &&
        InterlockedCompareExchange(&initialized,0,0) &&
        !InterlockedCompareExchange(&shutting_down,0,0) &&
        !InterlockedCompareExchange(&fatal_latch,0,0) &&
        !InterlockedCompareExchange(&lifecycle_admission_revoked,0,0) &&
        !InterlockedCompareExchange(&language_transition_inflight,0,0) &&
        InterlockedCompareExchange(&language_state,0,0)==
            PHOTON_V6_PF_SELECTOR_LANGUAGE_TRANSLATION &&
        (LONG)language_generation==InterlockedCompareExchange(
            &language_state_sequence,0,0)) {
        for (index=0;index<MAX_ORDINARY_WRITE_LEASES;++index) {
            OrdinaryWriteLease *at=&ordinary_write_lease_slots[index];
            if (!at->active || at->tid!=tid ||
                at->token!=(LONG)lease_token ||
                at->language_generation!=(LONG)language_generation) continue;
            if (exact) { exact=0; break; }
            exact=1;
        }
    }
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
    DWORD tid=GetCurrentThreadId();
    OrdinaryWriteLease *matched=NULL;
    size_t index;
    InterlockedIncrement(&hook_inflight);
    AcquireSRWLockExclusive(&state_lock);
    for (index=0;index<MAX_ORDINARY_WRITE_LEASES;++index) {
        OrdinaryWriteLease *at=&ordinary_write_lease_slots[index];
        if (!at->active || at->tid!=tid ||
            at->token!=(LONG)lease_token ||
            at->language_generation!=(LONG)language_generation) continue;
        if (matched) { matched=NULL; break; }
        matched=at;
    }
    if (matched && InterlockedCompareExchange(
            &ordinary_write_leases,0,0)>0 &&
        InterlockedCompareExchange(&translation_write_leases,0,0)>0) {
        memset(matched,0,sizeof(*matched));
        InterlockedDecrement(&ordinary_write_leases);
        InterlockedDecrement(&translation_write_leases);
        if (!lease_census_exact_locked()) {
            telemetry_increment(&ordinary_lease_rejects);
            set_fatal();
        } else telemetry_increment(&ordinary_lease_releases);
    } else {
        telemetry_increment(&ordinary_lease_rejects);
        telemetry_increment(&ordinary_lease_generation_rejects);
        set_fatal();
    }
    ReleaseSRWLockExclusive(&state_lock);
    InterlockedDecrement(&hook_inflight);
}

int __attribute__((cdecl)) photon_v6_pf_selector_adapter_init(
    BYTE *verified_main_base) {
    int installed=0,restored=0;
    int prepare_result;
#ifdef PHOTON_V6_PF_SELECTOR_TEST_HOOKS
    int retry;
#endif
    if (!verified_main_base || InterlockedCompareExchange(&initialized,0,0) ||
        installed_hook_count()!=0 ||
        InterlockedCompareExchange(&hooks_retained_until_process_exit,0,0) ||
        InterlockedCompareExchange(&fatal_latch,0,0)) return -1;
    if (no_hot_lifecycle_enabled() &&
        (InterlockedCompareExchange(&first_mutation_committed,0,0) ||
         journaled_hook_count()!=0)) return -1;
    if (InterlockedCompareExchange(&initializing,1,0)!=0) return -1;
    if (InterlockedCompareExchange(&initialized,0,0) ||
        installed_hook_count()!=0 ||
        InterlockedCompareExchange(&hooks_retained_until_process_exit,0,0) ||
        InterlockedCompareExchange(&fatal_latch,0,0)) {
        InterlockedExchange(&initializing,0);
        return -1;
    }
    if (no_hot_lifecycle_enabled() &&
        (InterlockedCompareExchange(&first_mutation_committed,0,0) ||
         journaled_hook_count()!=0)) {
        InterlockedExchange(&initializing,0);
        return -1;
    }
    main_base=verified_main_base;
    if (!verify_image(main_base) || !route_table_unique()) {
        main_base=NULL;
        InterlockedExchange(&initializing,0);
        return -2;
    }
    reset_runtime_state();
    InterlockedExchange(&shutting_down,0);
    InterlockedExchange(&restoring,0);
    InterlockedExchange(&hooks_restored_exact,0);
    InterlockedExchange(&mutation_journal_entries,0);
    InterlockedExchange(&restored_hook_count,0);
    InterlockedExchange(&first_mutation_committed,0);
    InterlockedExchange(&semantic_gate_disabled,0);
    prepare_result=prepare_hooks();
    if (prepare_result != 0) {
        InterlockedExchange(&hooks_restored_exact,1);
        main_base=NULL;
        InterlockedExchange(&initializing,0);
        return prepare_result;
    }
    if (no_hot_lifecycle_enabled()) pin_adapter_module_or_failfast();
    AcquireSRWLockExclusive(&patch_lock);
    installed=quiescent_install();
#ifdef PHOTON_V6_PF_SELECTOR_TEST_HOOKS
    if (!installed && installed_hook_count()!=0 &&
        !no_hot_lifecycle_enabled()) {
        for (retry=0;retry<RESTORE_RETRIES;++retry) {
            if (InterlockedCompareExchange(&hook_inflight,0,0)==0 &&
                quiescent_restore_once()) { restored=1; break; }
            Sleep(25);
        }
    } else if (!installed) restored=hook_sites_restored_exact();
#else
    if (!installed)
        restored=installed_hook_count()==0 && journaled_hook_count()==0 &&
            hook_sites_restored_exact();
#endif
    ReleaseSRWLockExclusive(&patch_lock);
    if (restored && !wait_for_counted_hooks_to_exit()) restored=0;
    if (!installed) {
        if (no_hot_lifecycle_enabled() &&
            (InterlockedCompareExchange(&first_mutation_committed,0,0) ||
             installed_hook_count()!=0 || journaled_hook_count()!=0)) {
            (void)enter_no_hot_retained_state(1);
        } else if (restored && installed_hook_count()==0) {
            free_trampolines();
            InterlockedExchange(&hooks_restored_exact,1);
            memset(entry_hooks,0,sizeof(entry_hooks));
            memset(call_hooks,0,sizeof(call_hooks));
            main_base=NULL;
        } else {
            set_fatal();
            pin_adapter_module_or_failfast();
        }
        InterlockedExchange(&initializing,0);
        return -4;
    }
    if (!hook_sites_installed_exact() ||
        installed_hook_count()!=EXPECTED_HOOK_COUNT ||
        InterlockedCompareExchange(&mutation_journal_entries,0,0)!=
            EXPECTED_HOOK_COUNT
#ifdef PHOTON_V6_PF_SELECTOR_TEST_HOOKS
        || InterlockedCompareExchange(
            &test_force_post_install_census_failure,0,0)!=0
#endif
        ) {
        set_fatal();
        if (no_hot_lifecycle_enabled()) {
            (void)enter_no_hot_retained_state(1);
            InterlockedExchange(&initializing,0);
            return -5;
        }
#ifdef PHOTON_V6_PF_SELECTOR_TEST_HOOKS
        if (!rollback_post_install_failure()) {
            /* A caller may treat a nonzero init result as permission to unload.
             * If any detour cannot be proven restored, pin this module so the
             * surviving fail-closed pass-through hooks can never dangle. */
            pin_adapter_module_or_failfast();
            InterlockedExchange(&initializing,0);
            return -6;
        }
        InterlockedExchange(&initializing,0);
        return -5;
#else
        lifecycle_ambiguity_failfast();
        InterlockedExchange(&initializing,0);
        return -5;
#endif
    }
    InterlockedExchange(&semantic_gate_disabled,0);
    InterlockedExchange(&initialized,1);
    (void)refresh_live_image_language(1);
    InterlockedExchange(&initializing,0);
    return 0;
}

void __attribute__((cdecl)) photon_v6_pf_selector_adapter_shutdown(void) {
#ifdef PHOTON_V6_PF_SELECTOR_TEST_HOOKS
    int retry;
#endif
    if (!InterlockedCompareExchange(&initialized,0,0) &&
        InterlockedCompareExchange(
            &hooks_retained_until_process_exit,0,0) &&
        InterlockedCompareExchange(&semantic_gate_disabled,0,0) &&
        InterlockedCompareExchange(&lifecycle_admission_revoked,0,0))
        return;
    if (!InterlockedCompareExchange(&initialized,0,0) &&
        installed_hook_count()==0) return;
    if (InterlockedCompareExchange(&restoring,1,0)!=0) return;
    if (no_hot_lifecycle_enabled() &&
        (InterlockedCompareExchange(&first_mutation_committed,0,0) ||
         installed_hook_count()!=0 || journaled_hook_count()!=0)) {
        if (!enter_no_hot_retained_state(0)) {
            InterlockedExchange(&restoring,0);
            return;
        }
        InterlockedExchange(&hooks_restored_exact,0);
        InterlockedExchange(&hooks_retained_until_process_exit,1);
        pin_adapter_module_or_failfast();
        if (!wait_for_counted_hooks_to_exit()) set_fatal();
        InterlockedExchange(&restoring,0);
        return;
    }
#ifndef PHOTON_V6_PF_SELECTOR_TEST_HOOKS
    /* Production can reach this point only if lifecycle state was corrupted:
     * every successful install has first_mutation_committed set. */
    lifecycle_ambiguity_failfast();
    InterlockedExchange(&restoring,0);
    return;
#else
    {
    int exact=0;
    LONG journal;
    InterlockedExchange(&shutting_down,1);
    InterlockedExchange(&semantic_gate_disabled,1);
    (void)InterlockedCompareExchange(&language_transition_inflight,1,0);
    for (retry=0;retry<SHUTDOWN_LEASE_DRAIN_RETRIES;++retry) {
        if (InterlockedCompareExchange(&translation_write_leases,0,0)==0)
            break;
        Sleep(1);
    }
    AcquireSRWLockExclusive(&patch_lock);
    for (retry=0;retry<RESTORE_RETRIES;++retry) {
        if (InterlockedCompareExchange(&hook_inflight,0,0)==0 &&
            InterlockedCompareExchange(&translation_write_leases,0,0)==0 &&
            quiescent_restore_once()) { exact=1; break; }
        Sleep(25);
    }
    ReleaseSRWLockExclusive(&patch_lock);
    if (exact && !wait_for_counted_hooks_to_exit()) exact=0;
    journal=InterlockedCompareExchange(&mutation_journal_entries,0,0);
    exact=exact && journal==EXPECTED_HOOK_COUNT &&
        InterlockedCompareExchange(&restored_hook_count,0,0)==journal &&
        installed_hook_count()==0 && hook_sites_restored_exact();
    if (exact) {
        free_trampolines();
        InterlockedExchange(&hooks_restored_exact,1);
        InterlockedExchange(&initialized,0);
        main_base=NULL;
    } else {
        set_fatal();
        /* Either a detour or a counted replacement frame may still exist.
         * Pin the containing combined module so caller unload cannot create
         * a dangling instruction pointer. */
        pin_adapter_module_or_failfast();
    }
    InterlockedExchange(&restoring,0);
    }
#endif
}

void __attribute__((cdecl)) photon_v6_pf_selector_adapter_query(
    PhotonV6PfSelectorStatus *status) {
    LONG before=0,after=0;
    unsigned attempt;
    if (!status) return;
    memset(status,0,sizeof(*status));
    status->struct_size=sizeof(*status);
    status->abi_version=PHOTON_V6_PF_SELECTOR_ADAPTER_ABI;
    status->initialized=(uint32_t)
        InterlockedCompareExchange(&initialized,0,0);
    status->hooks_installed=(uint32_t)installed_hook_count();
    status->expected_hook_count=EXPECTED_HOOK_COUNT;
    status->hook_inflight=(uint32_t)
        InterlockedCompareExchange(&hook_inflight,0,0);
    status->hooks_restored_exact=(uint32_t)
        InterlockedCompareExchange(&hooks_restored_exact,0,0);
    status->mutation_journal_entries=(uint32_t)
        InterlockedCompareExchange(&mutation_journal_entries,0,0);
    status->restored_hook_count=(uint32_t)
        InterlockedCompareExchange(&restored_hook_count,0,0);
    for (attempt=0;attempt<128;++attempt) {
        before=InterlockedCompareExchange(&telemetry_generation,0,0);
        if (before&1) { after=before; continue; }
        status->language_state=InterlockedCompareExchange(&language_state,0,0);
        status->language_state_sequence=(uint32_t)
            InterlockedCompareExchange(&language_state_sequence,0,0);
        status->language_state_known=
            status->language_state==PHOTON_V6_PF_SELECTOR_LANGUAGE_JAPANESE ||
            status->language_state==PHOTON_V6_PF_SELECTOR_LANGUAGE_TRANSLATION;
#define SNAPSHOT_FIELD(name) status->name=(uint32_t)InterlockedCompareExchange(&name,0,0)
        SNAPSHOT_FIELD(language_bootstrap_exact_events);
        SNAPSHOT_FIELD(language_bootstrap_conflict_rejects);
        SNAPSHOT_FIELD(language_setter_exact_events);
        SNAPSHOT_FIELD(global_language_generation_purges);
        SNAPSHOT_FIELD(graph_begin_events);
        SNAPSHOT_FIELD(graph_end_events);
        SNAPSHOT_FIELD(graph_supersession_purges);
        SNAPSHOT_FIELD(graph_identity_rejects);
        SNAPSHOT_FIELD(cref_identity_events);
        SNAPSHOT_FIELD(cref_identity_rejects);
        SNAPSHOT_FIELD(materializer_entry_events);
        SNAPSHOT_FIELD(materializer_load_candidates);
        SNAPSHOT_FIELD(materializer_fresh_commits);
        SNAPSHOT_FIELD(materializer_cached_commits);
        SNAPSHOT_FIELD(materializer_identity_rejects);
        SNAPSHOT_FIELD(payload_sha256_rejects);
        SNAPSHOT_FIELD(state0_translation_endpoint_rejects);
        SNAPSHOT_FIELD(c07_all_provider_rejects);
        SNAPSHOT_FIELD(exact_surface_entries);
        SNAPSHOT_FIELD(surface_identity_rejects);
        SNAPSHOT_FIELD(exact_decode_queries);
        SNAPSHOT_FIELD(decode_identity_rejects);
        SNAPSHOT_FIELD(translation_special57_allows);
        SNAPSHOT_FIELD(stale_generation_rejects);
        SNAPSHOT_FIELD(cross_thread_rejects);
        SNAPSHOT_FIELD(ordinary_lease_acquires);
        SNAPSHOT_FIELD(ordinary_lease_rejects);
        SNAPSHOT_FIELD(ordinary_lease_releases);
        SNAPSHOT_FIELD(ordinary_lease_generation_rejects);
        SNAPSHOT_FIELD(fatal_latch);
#undef SNAPSHOT_FIELD
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
        status->translation_special57_allows=(uint32_t)
            InterlockedCompareExchange(&diagnostic_special_events,0,0);
        status->state0_translation_endpoint_rejects=(uint32_t)
            InterlockedCompareExchange(&diagnostic_special_top_node,0,0);
        status->c07_all_provider_rejects=(uint32_t)
            InterlockedCompareExchange(&diagnostic_special_cr6_object,0,0);
        status->exact_surface_entries=(uint32_t)
            InterlockedCompareExchange(&diagnostic_special_closest_resolved,0,0);
        status->exact_decode_queries=(uint32_t)
            InterlockedCompareExchange(&diagnostic_native_gate_code,0,0);
        status->surface_identity_rejects=(uint32_t)
            InterlockedCompareExchange(
                &diagnostic_special_route_index_plus_one,0,0);
        status->decode_identity_rejects=(uint32_t)
            InterlockedCompareExchange(&diagnostic_special_relation_flags,0,0);
        status->materializer_cached_commits=(uint32_t)
            InterlockedCompareExchange(&diagnostic_special_raw_handle,0,0);
        status->materializer_fresh_commits=(uint32_t)
            InterlockedCompareExchange(&diagnostic_pipeline_flags,0,0);
#endif
        after=InterlockedCompareExchange(&telemetry_generation,0,0);
        if (before==after && !(after&1)) {
            status->snapshot_consistent=1; break;
        }
    }
    AcquireSRWLockShared(&state_lock);
    status->translation_write_leases_active=(uint32_t)
        InterlockedCompareExchange(&translation_write_leases,0,0);
    status->ordinary_write_leases_active=(uint32_t)
        InterlockedCompareExchange(&ordinary_write_leases,0,0);
    status->special_write_leases_active=(uint32_t)
        InterlockedCompareExchange(&special_write_leases,0,0);
    if (!lease_census_exact_locked()) status->snapshot_consistent=0;
    ReleaseSRWLockShared(&state_lock);
    status->status_generation=(uint32_t)after;
    status->no_hot_lifecycle=no_hot_lifecycle_enabled()?1U:0U;
    status->module_pinned=(uint32_t)
        InterlockedCompareExchange(&module_pinned,0,0);
    status->first_mutation_committed=(uint32_t)
        InterlockedCompareExchange(&first_mutation_committed,0,0);
    status->hooks_retained_until_process_exit=(uint32_t)
        InterlockedCompareExchange(&hooks_retained_until_process_exit,0,0);
    status->semantic_gate_disabled=(uint32_t)
        InterlockedCompareExchange(&semantic_gate_disabled,0,0);
    status->lifecycle_admission_revoked=(uint32_t)
        InterlockedCompareExchange(&lifecycle_admission_revoked,0,0);
    status->unload_safe=status->hooks_installed==0 &&
        status->hook_inflight==0 && status->hooks_restored_exact==1 &&
        !status->hooks_retained_until_process_exit;
    status->result=status->fatal_latch?-1:0;
}

#ifdef PHOTON_V6_PF_SELECTOR_TEST_HOOKS
static void test_write_pointer(void *base, SIZE_T offset, uintptr_t value) {
    *(uintptr_t *)((BYTE *)base+offset)=value;
}

void photon_v6_pf_selector_test_force_post_install_census_failure(
    uint32_t enabled) {
    InterlockedExchange(&test_force_post_install_census_failure,
                        enabled?1:0);
}

void photon_v6_pf_selector_test_set_no_hot_lifecycle(uint32_t enabled) {
    InterlockedExchange(&test_no_hot_lifecycle,enabled?1:0);
}

void photon_v6_pf_selector_test_fail_install_before_ordinal(int32_t ordinal) {
    InterlockedExchange(&test_fail_install_before_ordinal,(LONG)ordinal);
}

void photon_v6_pf_selector_test_force_fatal(void) {
    set_fatal();
}

void photon_v6_pf_selector_test_emit_benign_telemetry(void) {
    telemetry_increment(&cref_identity_rejects);
}

static volatile LONG test_no_hot_passthrough_calls;

typedef struct TestNoHotLeaseWorker {
    volatile LONG acquired;
    volatile LONG released;
    LONG special;
    LONG exact;
    uint32_t token;
    uint32_t generation;
} TestNoHotLeaseWorker;

typedef struct TestNoHotShutdownWorker {
    volatile LONG entered;
    volatile LONG done;
    LONGLONG elapsed_microseconds;
} TestNoHotShutdownWorker;

typedef struct TestNoHotHeldSetterWorker {
    volatile LONG entered;
    volatile LONG began;
    volatile LONG finish_allowed;
    volatile LONG done;
    volatile LONG native_setter_calls;
    LONG finished;
} TestNoHotHeldSetterWorker;

static DWORD WINAPI test_no_hot_shutdown_worker(void *opaque) {
    TestNoHotShutdownWorker *worker=(TestNoHotShutdownWorker *)opaque;
    LARGE_INTEGER started,ended,frequency;
    QueryPerformanceFrequency(&frequency);
    QueryPerformanceCounter(&started);
    InterlockedExchange(&worker->entered,1);
    photon_v6_pf_selector_adapter_shutdown();
    QueryPerformanceCounter(&ended);
    worker->elapsed_microseconds=frequency.QuadPart>0?
        (ended.QuadPart-started.QuadPart)*INT64_C(1000000)/
            frequency.QuadPart:0;
    InterlockedExchange(&worker->done,1);
    return 0;
}

static DWORD WINAPI test_no_hot_held_setter_worker(void *opaque) {
    TestNoHotHeldSetterWorker *worker=
        (TestNoHotHeldSetterWorker *)opaque;
    InterlockedExchange(&worker->entered,1);
    if (begin_language_transition(
            PHOTON_V6_PF_SELECTOR_LANGUAGE_TRANSLATION)) {
        InterlockedExchange(&worker->began,1);
        while (!InterlockedCompareExchange(&worker->finish_allowed,0,0))
            Sleep(1);
        InterlockedIncrement(&worker->native_setter_calls);
        worker->finished=finish_language_transition(
            PHOTON_V6_PF_SELECTOR_LANGUAGE_JAPANESE,1,0,
            test_object,test_object);
    }
    InterlockedExchange(&worker->done,1);
    return 0;
}

static DWORD WINAPI test_no_hot_lease_worker(void *opaque) {
    TestNoHotLeaseWorker *worker=(TestNoHotLeaseWorker *)opaque;
    if (worker->special) {
        PhotonV6PfSelectorDecision entered,decoded;
        memset(&entered,0,sizeof(entered));
        memset(&decoded,0,sizeof(decoded));
        worker->exact=photon_v6_pf_selector_adapter_surface_enter(
            test_object,&entered)==1 &&
            photon_v6_pf_selector_adapter_decode_query(&decoded)==1;
        InterlockedExchange(&worker->acquired,1);
        Sleep(150);
        if (worker->exact)
            photon_v6_pf_selector_adapter_surface_leave(test_object);
    } else {
        worker->exact=photon_v6_pf_selector_adapter_ordinary_lease_acquire(
            &worker->token,&worker->generation)==1;
        InterlockedExchange(&worker->acquired,1);
        Sleep(150);
        if (worker->exact)
            photon_v6_pf_selector_adapter_ordinary_lease_release(
                worker->token,worker->generation);
    }
    InterlockedExchange(&worker->released,1);
    return 0;
}

static uintptr_t __attribute__((thiscall)) test_no_hot_passthrough_setter(
    void *self, uint32_t value) {
    (void)self;
    InterlockedIncrement(&test_no_hot_passthrough_calls);
    return (uintptr_t)(value^UINT32_C(0x57A40000));
}

static uintptr_t __attribute__((thiscall)) test_no_hot_passthrough_cref(
    void *self, void *archive, uint32_t raw_handle) {
    (void)self; (void)archive; (void)raw_handle;
    InterlockedIncrement(&test_no_hot_passthrough_calls);
    return UINT32_C(0x57A40011);
}

static uintptr_t __attribute__((thiscall)) test_no_hot_passthrough_graph(
    void *object, void *archive) {
    (void)object; (void)archive;
    InterlockedIncrement(&test_no_hot_passthrough_calls);
    return UINT32_C(0x57A40012);
}

static uintptr_t __attribute__((thiscall)) test_no_hot_passthrough_materializer(
    void *node) {
    (void)node;
    InterlockedIncrement(&test_no_hot_passthrough_calls);
    return UINT32_C(0x57A40013);
}

static uint64_t test_runtime_identity_digest(void) {
    uint64_t value=fnv1a64((const BYTE *)graph_epochs,sizeof(graph_epochs));
    value^=fnv1a64((const BYTE *)cref_bindings,sizeof(cref_bindings));
    value^=fnv1a64((const BYTE *)active_materializations,
        sizeof(active_materializations));
    value^=fnv1a64((const BYTE *)object_bindings,sizeof(object_bindings));
    value^=fnv1a64((const BYTE *)active_surfaces,sizeof(active_surfaces));
    value^=fnv1a64((const BYTE *)ordinary_write_lease_slots,
        sizeof(ordinary_write_lease_slots));
    return value;
}

int photon_v6_pf_selector_test_no_hot_lifecycle_predicate(uint32_t mode) {
    enum { PF_IMAGE_BYTES = 0x00380000 };
    BYTE *image=(BYTE *)VirtualAlloc(NULL,PF_IMAGE_BYTES,
        MEM_RESERVE|MEM_COMMIT,PAGE_EXECUTE_READWRITE);
    PhotonV6PfSelectorStatus status;
    CRefReadFn saved_cref;
    SerializeFn saved_graph;
    ResourceMaterializerFn saved_materializer;
    CIntSetterFn saved_setter;
    LONG generation_before,generation_after;
    uint64_t identity_before,identity_after;
    uintptr_t cref_passthrough,graph_passthrough,materializer_passthrough;
    uintptr_t setter_passthrough;
    TestNoHotLeaseWorker ordinary_worker;
    TestNoHotShutdownWorker shutdown_worker;
    TestNoHotHeldSetterWorker held_setter_worker;
    HANDLE ordinary_thread=NULL,shutdown_thread=NULL,setter_thread=NULL;
    int same_tid_rejected=1;
    int init_result,expected_result,exact;
    if (!image || mode<1 || mode>7 ||
        !photon_v6_pf_selector_test_synthesize_image(image,PF_IMAGE_BYTES))
        return 0;
    photon_v6_pf_selector_test_set_no_hot_lifecycle(1);
    photon_v6_pf_selector_test_fail_install_before_ordinal(
        mode==2?2:-1);
    photon_v6_pf_selector_test_force_post_install_census_failure(mode==3);
    init_result=photon_v6_pf_selector_adapter_init(image);
    photon_v6_pf_selector_test_force_post_install_census_failure(0);
    expected_result=mode==2?-4:(mode==3?-5:0);
    if (init_result!=expected_result) return 0;
    memset(&ordinary_worker,0,sizeof(ordinary_worker));
    memset(&shutdown_worker,0,sizeof(shutdown_worker));
    memset(&held_setter_worker,0,sizeof(held_setter_worker));
    InterlockedExchange(&test_lifecycle_claim_pause_enabled,0);
    InterlockedExchange(&test_lifecycle_claim_pause_reached,0);
    InterlockedExchange(&test_lifecycle_claim_pause_release,0);
    InterlockedExchange(&test_finish_transition_pause_enabled,0);
    InterlockedExchange(&test_finish_transition_pause_reached,0);
    InterlockedExchange(&test_finish_transition_pause_release,0);
    if (mode==7) {
        uint32_t token=0,generation=0;
        LONG special_before,special_after;
        int retry,ordinary_rejected,special_rejected,setter_rejected;
        photon_v6_pf_selector_test_reset();
        if (!photon_v6_pf_selector_test_set_language(
                PHOTON_V6_PF_SELECTOR_LANGUAGE_TRANSLATION)) return 0;
        InterlockedExchange(&test_lifecycle_claim_pause_enabled,1);
        setter_thread=CreateThread(NULL,0,test_no_hot_held_setter_worker,
            &held_setter_worker,0,NULL);
        if (!setter_thread) return 0;
        for (retry=0;retry<1000;++retry) {
            if (InterlockedCompareExchange(&held_setter_worker.began,0,0))
                break;
            Sleep(1);
        }
        if (!InterlockedCompareExchange(&held_setter_worker.began,0,0) ||
            InterlockedCompareExchange(&language_transition_inflight,0,0)!=1 ||
            InterlockedCompareExchange(&language_transition_owner_tid,0,0)==0)
            return 0;
        InterlockedExchange(&test_finish_transition_pause_enabled,1);
        InterlockedExchange(&held_setter_worker.finish_allowed,1);
        for (retry=0;retry<1000;++retry) {
            if (InterlockedCompareExchange(
                    &test_finish_transition_pause_reached,0,0)==1) break;
            Sleep(1);
        }
        if (InterlockedCompareExchange(
                &test_finish_transition_pause_reached,0,0)!=1 ||
            InterlockedCompareExchange(&held_setter_worker.done,0,0)!=0 ||
            InterlockedCompareExchange(&language_transition_inflight,0,0)!=1 ||
            InterlockedCompareExchange(&language_transition_owner_tid,0,0)==0)
            return 0;
        shutdown_thread=CreateThread(NULL,0,test_no_hot_shutdown_worker,
            &shutdown_worker,0,NULL);
        if (!shutdown_thread) return 0;
        Sleep(10);
        if (InterlockedCompareExchange(&shutdown_worker.done,0,0)!=0 ||
            InterlockedCompareExchange(&lifecycle_admission_revoked,0,0)!=0)
            return 0;
        InterlockedExchange(&test_finish_transition_pause_release,1);
        for (retry=0;retry<1000;++retry) {
            if (InterlockedCompareExchange(
                    &lifecycle_admission_revoked,0,0)==1) break;
            Sleep(1);
        }
        if (InterlockedCompareExchange(
                &lifecycle_admission_revoked,0,0)!=1 ||
            InterlockedCompareExchange(&shutdown_worker.done,0,0)!=0 ||
            InterlockedCompareExchange(&semantic_gate_disabled,0,0)!=0 ||
            InterlockedCompareExchange(&initialized,0,0)!=1) return 0;
        for (retry=0;retry<1000;++retry) {
            if (InterlockedCompareExchange(
                    &test_lifecycle_claim_pause_reached,0,0)==1) break;
            Sleep(1);
        }
        if (InterlockedCompareExchange(
                &test_lifecycle_claim_pause_reached,0,0)!=1 ||
            InterlockedCompareExchange(&held_setter_worker.done,0,0)!=1 ||
            InterlockedCompareExchange(&shutdown_worker.done,0,0)!=0 ||
            InterlockedCompareExchange(&language_transition_inflight,0,0)!=0)
            return 0;
        ordinary_rejected=
            !photon_v6_pf_selector_adapter_ordinary_lease_acquire(
                &token,&generation) && token==0 && generation==0;
        AcquireSRWLockExclusive(&state_lock);
        special_before=InterlockedCompareExchange(&special_write_leases,0,0);
        special_rejected=!special_lease_acquire_locked(NULL);
        special_after=InterlockedCompareExchange(&special_write_leases,0,0);
        ReleaseSRWLockExclusive(&state_lock);
        setter_rejected=!begin_language_transition(
            PHOTON_V6_PF_SELECTOR_LANGUAGE_JAPANESE);
        if (!ordinary_rejected || !special_rejected ||
            special_before!=0 || special_after!=0 || !setter_rejected ||
            InterlockedCompareExchange(&translation_write_leases,0,0)!=0)
            return 0;
        InterlockedExchange(&test_lifecycle_claim_pause_release,1);
        if (WaitForSingleObject(setter_thread,2000)!=WAIT_OBJECT_0 ||
            WaitForSingleObject(shutdown_thread,2000)!=WAIT_OBJECT_0)
            return 0;
        CloseHandle(setter_thread); CloseHandle(shutdown_thread);
        setter_thread=NULL; shutdown_thread=NULL;
        if (!held_setter_worker.finished ||
            held_setter_worker.native_setter_calls!=1 ||
            !shutdown_worker.done ||
            InterlockedCompareExchange(&translation_write_leases,0,0)!=0 ||
            InterlockedCompareExchange(&ordinary_write_leases,0,0)!=0 ||
            InterlockedCompareExchange(&special_write_leases,0,0)!=0)
            return 0;
    } else if (mode==5 || mode==6) {
        PhotonV6PfSelectorDecision committed,entered,decoded;
        uint32_t token=0,generation=0;
        int special_open=0,ordinary_open=0;
        memset(&committed,0,sizeof(committed));
        memset(&entered,0,sizeof(entered));
        memset(&decoded,0,sizeof(decoded));
        photon_v6_pf_selector_test_reset();
        if (!photon_v6_pf_selector_test_set_language(
                PHOTON_V6_PF_SELECTOR_LANGUAGE_TRANSLATION)) return 0;
        if (mode==5) {
            ordinary_open=photon_v6_pf_selector_adapter_ordinary_lease_acquire(
                &token,&generation)==1;
            if (!ordinary_open) return 0;
        } else {
            if (!photon_v6_pf_selector_test_run_causal_scenario(
                    0,0,0,0,&committed) ||
                !photon_v6_pf_selector_adapter_surface_enter(
                    test_object,&entered) ||
                !photon_v6_pf_selector_adapter_decode_query(&decoded))
                return 0;
            special_open=1;
        }
        InterlockedExchange(&test_no_hot_passthrough_calls,0);
        same_tid_rejected=!enter_no_hot_retained_state(0) &&
            InterlockedCompareExchange(&semantic_gate_disabled,0,0)==0 &&
            InterlockedCompareExchange(&initialized,0,0)==1 &&
            InterlockedCompareExchange(&lifecycle_admission_revoked,0,0)==1 &&
            InterlockedCompareExchange(&language_transition_inflight,0,0)==0 &&
            InterlockedCompareExchange(&fatal_latch,0,0)==1 &&
            InterlockedCompareExchange(&test_no_hot_passthrough_calls,0,0)==0;
        if (ordinary_open)
            photon_v6_pf_selector_adapter_ordinary_lease_release(
                token,generation);
        if (special_open)
            photon_v6_pf_selector_adapter_surface_leave(test_object);
        if (!same_tid_rejected) return 0;
        photon_v6_pf_selector_adapter_shutdown();
    } else if (mode==4) {
        PhotonV6PfSelectorDecision committed,entered,decoded;
        int retry;
        memset(&committed,0,sizeof(committed));
        memset(&entered,0,sizeof(entered));
        memset(&decoded,0,sizeof(decoded));
        photon_v6_pf_selector_test_reset();
        if (!photon_v6_pf_selector_test_set_language(
                PHOTON_V6_PF_SELECTOR_LANGUAGE_TRANSLATION) ||
            !photon_v6_pf_selector_test_run_causal_scenario(
                0,0,0,0,&committed) ||
            !photon_v6_pf_selector_adapter_surface_enter(
                test_object,&entered) ||
            !photon_v6_pf_selector_adapter_decode_query(&decoded)) return 0;
        ordinary_thread=CreateThread(NULL,0,test_no_hot_lease_worker,
            &ordinary_worker,0,NULL);
        if (!ordinary_thread) { SetLastError(401); return 0; }
        for (retry=0;retry<1000;++retry) {
            if (InterlockedCompareExchange(&ordinary_worker.acquired,0,0)) break;
            Sleep(1);
        }
        if (!ordinary_worker.exact ||
            InterlockedCompareExchange(&translation_write_leases,0,0)!=2)
            { SetLastError(402); return 0; }
        shutdown_thread=CreateThread(NULL,0,test_no_hot_shutdown_worker,
            &shutdown_worker,0,NULL);
        if (!shutdown_thread) { SetLastError(403); return 0; }
        for (retry=0;retry<1000;++retry) {
            if (InterlockedCompareExchange(
                    &language_transition_inflight,0,0)==1) break;
            Sleep(1);
        }
        if (InterlockedCompareExchange(
                &language_transition_inflight,0,0)!=1 ||
            InterlockedCompareExchange(&shutdown_worker.done,0,0)!=0)
            { SetLastError(404); return 0; }
        Sleep(150);
        photon_v6_pf_selector_adapter_surface_leave(test_object);
        if (WaitForSingleObject(ordinary_thread,2000)!=WAIT_OBJECT_0 ||
            WaitForSingleObject(shutdown_thread,2000)!=WAIT_OBJECT_0)
            { SetLastError(405); return 0; }
        CloseHandle(ordinary_thread); CloseHandle(shutdown_thread);
        ordinary_thread=NULL; shutdown_thread=NULL;
        if (!ordinary_worker.released || !shutdown_worker.done ||
            shutdown_worker.elapsed_microseconds<INT64_C(75000) ||
            InterlockedCompareExchange(&translation_write_leases,0,0)!=0)
            { SetLastError(406); return 0; }
    } else {
        photon_v6_pf_selector_adapter_shutdown();
    }
    if (mode==4) photon_v6_pf_selector_adapter_shutdown();
    memset(&status,0,sizeof(status));
    photon_v6_pf_selector_adapter_query(&status);
    exact=status.no_hot_lifecycle==1 && status.module_pinned==1 &&
        status.first_mutation_committed==1 &&
        status.hooks_retained_until_process_exit==1 &&
        status.semantic_gate_disabled==1 &&
        status.lifecycle_admission_revoked==1 && status.unload_safe==0 &&
        status.initialized==0 && status.hooks_restored_exact==0 &&
        status.hooks_installed==(mode==2?1U:4U) &&
        status.mutation_journal_entries==(mode==2?1U:4U) &&
        status.restored_hook_count==0 && same_tid_rejected;
    if (!exact) { SetLastError(407); return 0; }
    /* A late counted replacement observes the disabled semantic gate and
     * invokes only its prepared native target.  No selector telemetry may
     * change after shutdown. */
    saved_cref=real_cref_read; saved_graph=real_graph_root_serialize;
    saved_materializer=real_resource_materializer;
    saved_setter=real_cint_setter;
    real_cref_read=test_no_hot_passthrough_cref;
    real_graph_root_serialize=test_no_hot_passthrough_graph;
    real_resource_materializer=test_no_hot_passthrough_materializer;
    real_cint_setter=test_no_hot_passthrough_setter;
    InterlockedExchange(&test_no_hot_passthrough_calls,0);
    generation_before=InterlockedCompareExchange(&telemetry_generation,0,0);
    identity_before=test_runtime_identity_digest();
    cref_passthrough=hook_cref_read_counted(image,image,0);
    graph_passthrough=hook_graph_root_serialize_counted(image,image);
    materializer_passthrough=hook_resource_materializer_counted(image);
    setter_passthrough=hook_cint_setter_dispatch(image,1,0);
    identity_after=test_runtime_identity_digest();
    generation_after=InterlockedCompareExchange(&telemetry_generation,0,0);
    real_cref_read=saved_cref; real_graph_root_serialize=saved_graph;
    real_resource_materializer=saved_materializer;
    real_cint_setter=saved_setter;
    exact=exact && cref_passthrough==UINT32_C(0x57A40011) &&
        graph_passthrough==UINT32_C(0x57A40012) &&
        materializer_passthrough==UINT32_C(0x57A40013) &&
        setter_passthrough==(uintptr_t)(UINT32_C(0x57A40000)^1U) &&
        InterlockedCompareExchange(&test_no_hot_passthrough_calls,0,0)==4 &&
        generation_before==generation_after && identity_before==identity_after;
    /* Retry is permanently rejected after any retained mutation. */
    exact=exact && photon_v6_pf_selector_adapter_init(image)==-1;
    if (!exact) SetLastError(408);
    return exact;
}

int photon_v6_pf_selector_test_synthesize_image(BYTE *image, uint32_t bytes) {
    IMAGE_DOS_HEADER *dos;
    IMAGE_NT_HEADERS32 *nt;
    BYTE call[5];
    if (!image || bytes<PF_SIZE_OF_IMAGE) return 0;
    memset(image,0,PF_SIZE_OF_IMAGE);
    dos=(IMAGE_DOS_HEADER *)image;
    nt=(IMAGE_NT_HEADERS32 *)(image+0x100);
    dos->e_magic=IMAGE_DOS_SIGNATURE;
    dos->e_lfanew=0x100;
    nt->Signature=IMAGE_NT_SIGNATURE;
    nt->FileHeader.Machine=IMAGE_FILE_MACHINE_I386;
    nt->FileHeader.TimeDateStamp=PF_TIMESTAMP;
    nt->OptionalHeader.Magic=IMAGE_NT_OPTIONAL_HDR32_MAGIC;
    nt->OptionalHeader.SizeOfImage=PF_SIZE_OF_IMAGE;
    memcpy(image+PF_CREF_READ_RVA,EXPECT_CREF_READ,sizeof(EXPECT_CREF_READ));
    memcpy(image+PF_SELECTOR_GRAPH_ROOT_SERIALIZE_RVA,
        EXPECT_GRAPH_ROOT_SERIALIZE,sizeof(EXPECT_GRAPH_ROOT_SERIALIZE));
    memcpy(image+0x000BF994,EXPECT_GRAPH_ROOT_CREF_ARRAY_CALL_CONTEXT,
        sizeof(EXPECT_GRAPH_ROOT_CREF_ARRAY_CALL_CONTEXT));
    memcpy(image+0x0018836D,EXPECT_MATERIALIZER_CALL_CONTEXT,
        sizeof(EXPECT_MATERIALIZER_CALL_CONTEXT));
    *(uint32_t *)(image+0x0018836D+4)=
        (uint32_t)(uintptr_t)(image+PF_NULL_RESOURCE_SENTINEL_RVA);
    if (!make_relative(call,0xE8,image+PF_TYPED_SETTER_CALLSITE_RVA,
        image+PF_CINT_SETTER_RVA)) return 0;
    memcpy(image+PF_TYPED_SETTER_CALLSITE_RVA,call,sizeof(call));
    return 1;
}

void photon_v6_pf_selector_test_reset(void) {
    if (!test_image)
        test_image=(BYTE *)VirtualAlloc(NULL,PF_SIZE_OF_IMAGE,
            MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);
    if (!test_image) {
        set_fatal(); return;
    }
    memset(test_image,0,PF_SIZE_OF_IMAGE);
    main_base=test_image;
    test_object=test_image+0x00300000;
    test_node=test_image+0x00300100;
    test_write_pointer(test_image+PF_CR6TI_TYPE_DESCRIPTOR_RVA,0,
        (uintptr_t)(test_image+PF_CR6TI_NAME_METADATA_RVA));
    *(uint32_t *)(test_image+PF_CR6TI_TYPE_DESCRIPTOR_RVA+4)=0x60;
    *(uint32_t *)(test_image+PF_CR6TI_TYPE_DESCRIPTOR_RVA+8)=
        UINT32_C(0xE0000004);
    test_write_pointer(test_image+PF_CR6TI_TYPE_DESCRIPTOR_RVA,0x0C,
        (uintptr_t)(test_image+PF_CR6TI_FACTORY_RVA));
    test_write_pointer(test_image+PF_CR6TI_TYPE_DESCRIPTOR_RVA,0x10,
        (uintptr_t)(test_image+PF_CR6TI_TYPE_FUNCTION_RVA));
    test_write_pointer(test_object,0,
        (uintptr_t)(test_image+PF_CR6TI_PRIMARY_VTABLE_RVA));
    test_write_pointer(test_object,0x0C,
        (uintptr_t)(test_image+PF_CR6TI_SECONDARY_VTABLE_RVA));
    test_write_pointer(test_object,0x18,(uintptr_t)(test_image+0x00300200));
    memcpy(test_image+0x00300200,"abc",3);
    *(uint32_t *)((BYTE *)test_object+0x58)=3;
    test_write_pointer(test_node,0,(uintptr_t)test_object);
    test_write_pointer(test_node,0x14,
        (uintptr_t)(test_image+PF_CR6TI_TYPE_DESCRIPTOR_RVA));
    /* Retail PF special-57 materialization uses CR6TI node kind 4. */
    *(uint32_t *)((BYTE *)test_node+0x18)=4;
    reset_runtime_state();
    InterlockedExchange(&initialized,1);
    InterlockedExchange(&shutting_down,0);
    InterlockedExchange(&hooks_restored_exact,1);
    test_target_override=1;
    test_target_index=0;
    InterlockedExchange(&test_force_exact_digest_reject,0);
}

int photon_v6_pf_selector_test_resource_kind_predicate(uint32_t kind) {
    return resource_node_kind_exact(kind);
}

int photon_v6_pf_selector_test_use_payload(
    const void *payload, uint32_t payload_bytes) {
    BYTE digest[32];
    uint64_t hash;
    int target;
    if (!test_object || !payload || !payload_bytes ||
        payload_bytes>MAX_PAYLOAD_BYTES ||
        !range_readable(payload,payload_bytes)) return 0;
    hash=fnv1a64((const BYTE *)payload,payload_bytes);
    sha256_digest((const BYTE *)payload,payload_bytes,digest);
    target=find_target_exact(payload_bytes,hash,digest);
    if (target<0) return 0;
    test_write_pointer(test_object,0x18,(uintptr_t)payload);
    *(uint32_t *)((BYTE *)test_object+0x58)=payload_bytes;
    test_target_override=0;
    test_target_index=target;
    return 1;
}

int photon_v6_pf_selector_test_bootstrap_predicate(uint32_t mutation_mask) {
    DWORD vm_vtable=PF_CVM_FLAG_OP_VTABLE_RVA;
    DWORD vm_exec=PF_CVM_FLAG_OP_EXEC_RVA;
    uint32_t command=0x22,source=0x06,cint_type=UINT32_C(0x16000000);
    uint16_t opcode=0;
    DWORD cint_vtable=PF_CINT_VTABLE_RVA;
    int owner_same=1,stack=1;
    if (mutation_mask&(1U<<0)) vm_vtable++;
    if (mutation_mask&(1U<<1)) vm_exec++;
    if (mutation_mask&(1U<<2)) command++;
    if (mutation_mask&(1U<<3)) source++;
    if (mutation_mask&(1U<<4)) opcode++;
    if (mutation_mask&(1U<<5)) cint_vtable++;
    if (mutation_mask&(1U<<6)) owner_same=0;
    if (mutation_mask&(1U<<7)) cint_type++;
    if (mutation_mask&(1U<<8)) stack=0;
    return image_language_bootstrap_fields_exact(vm_vtable,vm_exec,command,
        source,opcode,cint_vtable,owner_same,cint_type,stack);
}

int photon_v6_pf_selector_test_set_language(int32_t value) {
    if (value!=PHOTON_V6_PF_SELECTOR_LANGUAGE_JAPANESE &&
        value!=PHOTON_V6_PF_SELECTOR_LANGUAGE_TRANSLATION) return 0;
    if (InterlockedCompareExchange(&language_state,0,0)==
        PHOTON_V6_PF_SELECTOR_LANGUAGE_UNKNOWN) {
        InterlockedExchange(&language_state,value);
        InterlockedIncrement(&language_state_sequence);
    } else if (!purge_all_runtime_identity(value)) return 0;
    return !InterlockedCompareExchange(&fatal_latch,0,0);
}

/* The combined native/selector fixture exercises the native gate, whose
 * coherent language query deliberately revalidates the exact live CInt and
 * owner identity.  The selector-only helper above changes just the logical
 * state for isolated state-machine tests; this integration helper additionally
 * synthesizes the same sealed CInt/owner shape used by retail PF. */
int photon_v6_pf_selector_test_set_language_live(int32_t value) {
    static const WCHAR owner_marker[]=L"_$unrefix";
    BYTE *cint;
    BYTE *owner;
    BYTE *marker;
    void *resolved_owner=NULL;
    LONG resolved_value=PHOTON_V6_PF_SELECTOR_LANGUAGE_UNKNOWN;
    if (!test_image || !photon_v6_pf_selector_test_set_language(value))
        return 0;
    cint=test_image+0x00300400;
    owner=test_image+0x00300500;
    marker=test_image+0x00300580;
    memset(cint,0,0x20);
    memset(owner,0,0x30);
    memcpy(marker,owner_marker,sizeof(owner_marker));
    test_write_pointer(cint,0,
        (uintptr_t)(test_image+PF_CINT_VTABLE_RVA));
    test_write_pointer(cint,4,(uintptr_t)owner);
    test_write_pointer(cint,12,
        (uintptr_t)(test_image+PF_CINT_TYPE_METADATA_RVA));
    *(uint32_t *)(cint+16)=(uint32_t)value;
    test_write_pointer(owner,0,(uintptr_t)cint);
    test_write_pointer(owner,8,(uintptr_t)marker);
    *(uint32_t *)(owner+0x10)=0;
    test_write_pointer(owner,0x14,
        (uintptr_t)(test_image+PF_IMAGE_LANGUAGE_OWNER_METADATA_RVA));
    *(uint32_t *)(owner+0x1C)=UINT32_C(0xC1080300);
    *(uint32_t *)(owner+0x20)=UINT32_C(0xA2FC9536);
    *(uint32_t *)(owner+0x24)=UINT32_C(0xE7B699FE);
    *(uint32_t *)(owner+0x28)=0;
    *(uint32_t *)(test_image+PF_CINT_TYPE_METADATA_RVA+4)=4;
    *(uint32_t *)(test_image+PF_CINT_TYPE_METADATA_RVA+8)=
        UINT32_C(0x16000000);
    InterlockedExchangePointer(
        (void *volatile *)&language_cint_this,cint);
    InterlockedExchangePointer(
        (void *volatile *)&language_cint_owner,owner);
    return image_language_live_candidate_exact(
               cint,&resolved_owner,&resolved_value) &&
        resolved_owner==owner && resolved_value==value;
}

int photon_v6_pf_selector_test_sha256_abc(void) {
    static const BYTE expected[32] = {
        0xBA,0x78,0x16,0xBF,0x8F,0x01,0xCF,0xEA,
        0x41,0x41,0x40,0xDE,0x5D,0xAE,0x22,0x23,
        0xB0,0x03,0x61,0xA3,0x96,0x17,0x7A,0x9C,
        0xB4,0x10,0xFF,0x61,0xF2,0x00,0x15,0xAD
    };
    BYTE digest[32];
    sha256_digest((const BYTE *)"abc",3,digest);
    return memcmp(digest,expected,32)==0 &&
        fnv1a64((const BYTE *)"abc",3)==UINT64_C(0xE71FA2190541574B);
}

int photon_v6_pf_selector_test_run_causal_scenario(
    uint32_t target_index, uint32_t secondary_provider, uint32_t cached,
    uint32_t mutation_mask, PhotonV6PfSelectorDecision *decision) {
    void *archive,*graph_root,*cref_self,*returned_object,*selected_root=NULL;
    RouteFrame frame;
    ActiveMaterialization completed;
    ObjectBinding binding;
    PhotonV6PfSelectorDecision pending_decision;
    LONG epoch,selected_epoch=0,selected_generation=0;
    LONG sequence,state,state_sequence;
    uint32_t kind=0;
    const void *scenario_payload;
    uint32_t scenario_bytes;
    uint64_t scenario_hash;
    BYTE scenario_digest[32];
    int route_index,committed=0,note_load_exact=0;
    if (!test_image || target_index>=6 || !decision) return 0;
    scenario_payload=(const void *)safe_pointer(test_object,0x18);
    scenario_bytes=safe_u32(test_object,0x58);
    if (!scenario_payload || !scenario_bytes ||
        !range_readable(scenario_payload,scenario_bytes)) return 0;
    scenario_hash=fnv1a64((const BYTE *)scenario_payload,scenario_bytes);
    sha256_digest((const BYTE *)scenario_payload,scenario_bytes,scenario_digest);
    test_target_override=scenario_bytes==3 &&
        memcmp(scenario_payload,"abc",3)==0;
    test_target_index=(int)target_index;
    archive=test_image+0x00301000;
    graph_root=test_image+0x00302000;
    cref_self=test_image+0x00303000;
    test_write_pointer(cref_self,0,(uintptr_t)test_node);
    if (target_index<5) {
        route_index=(int)(target_index*2U+(secondary_provider?1U:0U));
        if (secondary_provider==2) route_index=13+(int)target_index;
    } else route_index=secondary_provider==2?18:
        secondary_provider==1?12:10;
    epoch=graph_root_begin(graph_root,archive);
    if (epoch<=0 ||
        !active_graph_snapshot(archive,&selected_root,&selected_epoch,
            &selected_generation) || selected_root!=graph_root ||
        selected_epoch!=epoch) return 0;
    memset(&frame,0,sizeof(frame));
    frame.tid=GetCurrentThreadId(); frame.archive=archive;
    frame.graph_root=graph_root; frame.cref_self=cref_self;
    frame.resolved_node=test_node; frame.raw_handle=routes[route_index].raw_handle;
    frame.route_index=route_index; frame.graph_epoch=epoch;
    frame.language_sequence=selected_generation;
    frame.runtime_graph_identity_exact=1;
    if (!bind_cref_identity(&frame) || !graph_root_end(graph_root,archive,epoch))
        return 0;
    if (mutation_mask&PHOTON_V6_PF_SELECTOR_TEST_MUTATE_ROUTE_AMBIGUITY) {
        RouteFrame conflict=frame;
        int conflict_index=route_index==0?1:0;
        conflict.route_index=conflict_index;
        conflict.raw_handle=routes[conflict_index].raw_handle;
        conflict.cref_identity_sequence=0;
        (void)bind_cref_identity(&conflict);
        return 0;
    }
    if (mutation_mask&PHOTON_V6_PF_SELECTOR_TEST_MUTATE_GRAPH) {
        AcquireSRWLockExclusive(&state_lock);
        /* Corrupt the durable graph-completion witness itself.  Merely
         * superseding the transient GraphEpochState is a valid PF lifetime
         * transition and is tested positively below. */
        for (size_t index=0;index<MAX_CREF_BINDINGS;++index)
            if (cref_bindings[index].active &&
                cref_bindings[index].identity_sequence==
                    frame.cref_identity_sequence)
                cref_bindings[index].graph_completion_exact=0;
        ReleaseSRWLockExclusive(&state_lock);
    }
    if (mutation_mask&PHOTON_V6_PF_SELECTOR_TEST_MUTATE_CREF)
        test_write_pointer(cref_self,0,
            (uintptr_t)(test_image+PF_NULL_RESOURCE_SENTINEL_RVA));
    if (mutation_mask&PHOTON_V6_PF_SELECTOR_TEST_MUTATE_SUPERSEDED) {
        void *new_root=test_image+0x00302100;
        void *different_archive=test_image+0x00301100;
        LONG next=graph_root_begin(new_root,different_archive);
        (void)graph_root_end(new_root,different_archive,next);
    }
    if (mutation_mask&PHOTON_V6_PF_SELECTOR_TEST_MUTATE_NODE_ABA) {
        void *new_root=test_image+0x00302200;
        void *different_archive=test_image+0x00301200;
        RouteFrame replacement=frame;
        LONG next=graph_root_begin(new_root,different_archive);
        replacement.archive=different_archive;
        replacement.graph_root=new_root;
        replacement.graph_epoch=next;
        replacement.cref_identity_sequence=0;
        if (!bind_cref_identity(&replacement) ||
            !graph_root_end(new_root,different_archive,next)) return 0;
    }
    if (!resource_node_invariants_exact(test_node,&kind)) return 0;
    state=InterlockedCompareExchange(&language_state,0,0);
    state_sequence=InterlockedCompareExchange(&language_state_sequence,0,0);
    sequence=InterlockedIncrement(&materializer_sequence);
    if (cached) test_write_pointer(test_node,0,(uintptr_t)test_object);
    else test_write_pointer(test_node,0,0);
    if (!push_materialization(test_node,&frame,
        cached?test_object:NULL,kind,state,state_sequence,sequence)) return 0;
    if (!cached) {
        test_write_pointer(test_node,0,(uintptr_t)test_object);
        memset(&pending_decision,0,sizeof(pending_decision));
        if (mutation_mask&
            PHOTON_V6_PF_SELECTOR_TEST_MUTATE_LOAD_SHA_TOMBSTONE)
            InterlockedExchange(&test_force_exact_digest_reject,1);
        note_load_exact=photon_v6_pf_selector_adapter_note_load(test_object,
            scenario_payload,scenario_bytes,scenario_hash,
            &pending_decision);
        InterlockedExchange(&test_force_exact_digest_reject,0);
        if (note_load_exact &&
            (!pending_decision.special_source_asset_id ||
             !pending_decision.special_context_identity_key ||
             strcmp(pending_decision.special_source_asset_id,
                    routes[route_index].source_asset_id)!=0 ||
             strcmp(pending_decision.special_context_identity_key,
                    routes[route_index].context_identity_key)!=0))
            return 0;
        if (mutation_mask&PHOTON_V6_PF_SELECTOR_TEST_MUTATE_MULTIPLE_LOADS)
            (void)photon_v6_pf_selector_adapter_note_load(test_object,
                scenario_payload,scenario_bytes,scenario_hash,
                &pending_decision);
    }
    if (mutation_mask&PHOTON_V6_PF_SELECTOR_TEST_MUTATE_PAYLOAD_SHA)
        ((BYTE *)scenario_payload)[0]^=0x20;
    if (mutation_mask&PHOTON_V6_PF_SELECTOR_TEST_MUTATE_LANGUAGE_SEQUENCE)
        InterlockedIncrement(&language_state_sequence);
    if (mutation_mask&PHOTON_V6_PF_SELECTOR_TEST_MUTATE_NODE)
        test_write_pointer(test_node,0x14,0);
    if (mutation_mask&PHOTON_V6_PF_SELECTOR_TEST_MUTATE_OBJECT)
        test_write_pointer(test_object,0,0);
    memset(&completed,0,sizeof(completed));
    if (!pop_materialization(sequence,&completed)) return 0;
    if (mutation_mask&PHOTON_V6_PF_SELECTOR_TEST_MUTATE_CROSS_THREAD)
        completed.tid^=UINT32_C(0x40000000);
    returned_object=(mutation_mask&
        PHOTON_V6_PF_SELECTOR_TEST_MUTATE_RETURN_OBJECT)?
        (test_image+0x00300400):test_object;
    committed=bind_committed_object(&completed,returned_object,cached!=0);
    memset(&binding,0,sizeof(binding));
    if (committed && binding_snapshot(test_object,&binding) &&
        binding_revalidate_exact(&binding)) {
        decision_from_binding(&binding,0,0,decision);
        decision->decision=PHOTON_V6_PF_SELECTOR_REJECT_CAUSAL_IDENTITY;
        decision->surface_scope_exact=0;
        decision->translation_overlay_allowed=0;
        return 1;
    }
    decision_initialize(decision,
        target_index==5 && !route_is_translation_provider(
            &routes[route_index],(int)target_index)?
            PHOTON_V6_PF_SELECTOR_REJECT_C07_ALL_PROVIDERS:
        state==PHOTON_V6_PF_SELECTOR_LANGUAGE_JAPANESE?
            PHOTON_V6_PF_SELECTOR_REJECT_JAPANESE_TRANSLATION_ENDPOINT:
            PHOTON_V6_PF_SELECTOR_REJECT_CAUSAL_IDENTITY);
    decision->target_index=target_index;
    decision->selected_cr6_object=(uintptr_t)test_object;
    decision->selected_resource_node=(uintptr_t)test_node;
    decision->payload_bytes=scenario_bytes;
    decision->payload_fnv1a64=scenario_hash;
    memcpy(decision->payload_sha256,scenario_digest,32);
    return 0;
}

int photon_v6_pf_selector_test_surface_decode_roundtrip(
    uint32_t mutation_mask, PhotonV6PfSelectorDecision *decision) {
    PhotonV6PfSelectorDecision entered,decoded;
    void *object=test_object;
    int entered_ok,decoded_ok,same_sequence;
    if (!test_image || !decision) return 0;
    if (mutation_mask&PHOTON_V6_PF_SELECTOR_TEST_MUTATE_SURFACE_OBJECT)
        object=test_image+0x00300400;
    memset(&entered,0,sizeof(entered));
    entered_ok=photon_v6_pf_selector_adapter_surface_enter(object,&entered);
    if (!entered_ok) { *decision=entered; return 0; }
    if (mutation_mask&PHOTON_V6_PF_SELECTOR_TEST_MUTATE_SURFACE_LEAVE_OBJECT) {
        PhotonV6PfSelectorDecision after;
        photon_v6_pf_selector_adapter_surface_leave(
            test_image+0x00300400);
        memset(&after,0,sizeof(after));
        decoded_ok=photon_v6_pf_selector_adapter_decode_query(&after);
        *decision=after;
        return decoded_ok?1:0;
    }
    if (mutation_mask&PHOTON_V6_PF_SELECTOR_TEST_MUTATE_SURFACE_SEQUENCE) {
        AcquireSRWLockExclusive(&state_lock);
        for (size_t index=0;index<MAX_ACTIVE_SURFACES;++index)
            if (active_surfaces[index].active &&
                active_surfaces[index].tid==GetCurrentThreadId())
                active_surfaces[index].sequence++;
        ReleaseSRWLockExclusive(&state_lock);
    }
    if (mutation_mask&PHOTON_V6_PF_SELECTOR_TEST_MUTATE_LANGUAGE_SEQUENCE)
        InterlockedIncrement(&language_state_sequence);
    if (mutation_mask&PHOTON_V6_PF_SELECTOR_TEST_MUTATE_DECODE_REVALIDATION)
        test_write_pointer(test_object,0,0);
    memset(&decoded,0,sizeof(decoded));
    decoded_ok=photon_v6_pf_selector_adapter_decode_query(&decoded);
    if (mutation_mask&PHOTON_V6_PF_SELECTOR_TEST_MUTATE_DECODE_REVALIDATION) {
        PhotonV6PfSelectorDecision retried;
        test_write_pointer(test_object,0,
            (uintptr_t)(test_image+PF_CR6TI_PRIMARY_VTABLE_RVA));
        memset(&retried,0,sizeof(retried));
        if (photon_v6_pf_selector_adapter_decode_query(&retried)) decoded_ok=1;
        *decision=retried;
        return decoded_ok?1:0;
    }
    same_sequence=decoded_ok && entered.selected_surface_sequence==
        decoded.selected_surface_sequence;
    photon_v6_pf_selector_adapter_surface_leave(object);
    *decision=decoded;
    return entered_ok && decoded_ok && same_sequence &&
        entered.translation_overlay_allowed==0 &&
        entered.decision==PHOTON_V6_PF_SELECTOR_SPECIAL57_SURFACE_SCOPE &&
        decoded.translation_overlay_allowed==1 &&
        decoded.decision==PHOTON_V6_PF_SELECTOR_ALLOW_SPECIAL57_TRANSLATION;
}

int photon_v6_pf_selector_test_nested_archive_top_predicate(void) {
    void *archive_a,*archive_b,*root_a,*root_b,*selected=NULL;
    LONG epoch_a,epoch_b,selected_epoch=0;
    int exact=1;
    photon_v6_pf_selector_test_reset();
    archive_a=test_image+0x00301000;
    archive_b=test_image+0x00301100;
    root_a=test_image+0x00302000;
    root_b=test_image+0x00302100;
    epoch_a=graph_root_begin(root_a,archive_a);
    exact=exact && epoch_a>0 &&
        active_graph_snapshot(archive_a,&selected,&selected_epoch,NULL) &&
        selected==root_a && selected_epoch==epoch_a;
    epoch_b=graph_root_begin(root_b,archive_b);
    exact=exact && epoch_b>0 &&
        !active_graph_snapshot(archive_a,&selected,&selected_epoch,NULL) &&
        active_graph_snapshot(archive_b,&selected,&selected_epoch,NULL) &&
        selected==root_b && selected_epoch==epoch_b;
    exact=exact && graph_root_end(root_b,archive_b,epoch_b) &&
        active_graph_snapshot(archive_a,&selected,&selected_epoch,NULL) &&
        selected==root_a && selected_epoch==epoch_a &&
        graph_root_end(root_a,archive_a,epoch_a);
    return exact;
}

int photon_v6_pf_selector_test_sibling_graph_supersession_predicate(void) {
    void *archive_a,*archive_b,*archive_c,*root_a,*root_b,*root_c;
    void *selected=NULL,*cref_self;
    LONG epoch_a,epoch_b,epoch_c,selected_epoch=0,generation=0;
    RouteFrame route;
    int exact=1;
    photon_v6_pf_selector_test_reset();
    (void)photon_v6_pf_selector_test_set_language(
        PHOTON_V6_PF_SELECTOR_LANGUAGE_TRANSLATION);
    archive_a=test_image+0x00301000;
    archive_b=test_image+0x00301100;
    archive_c=test_image+0x00301200;
    root_a=test_image+0x00302000;
    root_b=test_image+0x00302100;
    root_c=test_image+0x00302200;
    cref_self=test_image+0x00303000;
    test_write_pointer(cref_self,0,(uintptr_t)test_node);
    epoch_a=graph_root_begin(root_a,archive_a);
    epoch_b=graph_root_begin(root_b,archive_b);
    exact=exact && epoch_a>0 && epoch_b>0 &&
        active_graph_snapshot(archive_b,&selected,&selected_epoch,
            &generation) && selected==root_b && selected_epoch==epoch_b;
    memset(&route,0,sizeof(route));
    route.tid=GetCurrentThreadId(); route.archive=archive_b;
    route.graph_root=root_b; route.cref_self=cref_self;
    route.resolved_node=test_node; route.raw_handle=routes[0].raw_handle;
    route.route_index=0; route.graph_epoch=epoch_b;
    route.language_sequence=generation;
    route.runtime_graph_identity_exact=1;
    exact=exact && bind_cref_identity(&route) &&
        graph_root_end(root_b,archive_b,epoch_b) && route_still_exact(&route);
    epoch_c=graph_root_begin(root_c,archive_c);
    exact=exact && epoch_c>0 && route_still_exact(&route) &&
        graph_root_end(root_c,archive_c,epoch_c) && route_still_exact(&route);
    test_write_pointer(cref_self,0,
        (uintptr_t)(test_image+PF_NULL_RESOURCE_SENTINEL_RVA));
    exact=exact && !route_still_exact(&route) &&
        graph_root_end(root_a,archive_a,epoch_a);
    return exact;
}

int photon_v6_pf_selector_test_active_graph_cref_predicate(void) {
    void *archive,*root,*selected=NULL,*cref_self;
    LONG epoch,selected_epoch=0,generation=0;
    RouteFrame bound,found;
    int exact;
    photon_v6_pf_selector_test_reset();
    if (!photon_v6_pf_selector_test_set_language(
            PHOTON_V6_PF_SELECTOR_LANGUAGE_TRANSLATION)) return 0;
    archive=test_image+0x00301000;
    root=test_image+0x00302000;
    cref_self=test_image+0x00303000;
    test_write_pointer(cref_self,0,(uintptr_t)test_node);
    epoch=graph_root_begin(root,archive);
    if (epoch<=0 ||
        !active_graph_snapshot(archive,&selected,&selected_epoch,&generation) ||
        selected!=root || selected_epoch!=epoch) return 0;
    memset(&bound,0,sizeof(bound));
    bound.tid=GetCurrentThreadId(); bound.archive=archive;
    bound.graph_root=root; bound.cref_self=cref_self;
    bound.resolved_node=test_node; bound.raw_handle=routes[0].raw_handle;
    bound.route_index=0; bound.graph_epoch=epoch;
    bound.language_sequence=generation;
    bound.runtime_graph_identity_exact=1;
    if (!bind_cref_identity(&bound)) return 0;
    memset(&found,0,sizeof(found));
    exact=cref_route_for_node(test_node,&found)==1 &&
        found.cref_identity_sequence==bound.cref_identity_sequence &&
        route_still_exact(&found);
    exact=exact && graph_root_end(root,archive,epoch);
    memset(&found,0,sizeof(found));
    exact=exact && cref_route_for_node(test_node,&found)==1 &&
        found.cref_identity_sequence==bound.cref_identity_sequence &&
        route_still_exact(&found);
    return exact;
}

int photon_v6_pf_selector_test_endpoint_dormant_cref_predicate(void) {
    void *archive,*root,*selected=NULL,*cref_self;
    LONG epoch,selected_epoch=0,generation=0,current_generation;
    RouteFrame bound,found;
    int exact;
    photon_v6_pf_selector_test_reset();
    if (!photon_v6_pf_selector_test_set_language(
            PHOTON_V6_PF_SELECTOR_LANGUAGE_TRANSLATION)) return 0;
    archive=test_image+0x00301000;
    root=test_image+0x00302000;
    cref_self=test_image+0x00303000;
    test_write_pointer(cref_self,0,(uintptr_t)test_node);
    epoch=graph_root_begin(root,archive);
    if (epoch<=0 ||
        !active_graph_snapshot(archive,&selected,&selected_epoch,&generation) ||
        selected!=root || selected_epoch!=epoch) return 0;
    memset(&bound,0,sizeof(bound));
    bound.tid=GetCurrentThreadId(); bound.archive=archive;
    bound.graph_root=root; bound.cref_self=cref_self;
    bound.resolved_node=test_node; bound.raw_handle=routes[0].raw_handle;
    bound.route_index=0; bound.graph_epoch=epoch;
    bound.language_sequence=generation;
    bound.runtime_graph_identity_exact=1;
    if (!bind_cref_identity(&bound) ||
        !graph_root_end(root,archive,epoch)) return 0;
    memset(&found,0,sizeof(found));
    exact=cref_route_for_node(test_node,&found)==1 &&
        found.cref_identity_sequence==bound.cref_identity_sequence &&
        route_still_exact(&found);
    exact=exact && photon_v6_pf_selector_test_set_language(
        PHOTON_V6_PF_SELECTOR_LANGUAGE_JAPANESE);
    memset(&found,0,sizeof(found));
    exact=exact && cref_route_for_node(test_node,&found)==0 &&
        !route_still_exact(&bound) &&
        InterlockedCompareExchange(&fatal_latch,0,0)==0;
    exact=exact && photon_v6_pf_selector_test_set_language(
        PHOTON_V6_PF_SELECTOR_LANGUAGE_TRANSLATION);
    current_generation=InterlockedCompareExchange(
        &language_state_sequence,0,0);
    memset(&found,0,sizeof(found));
    exact=exact && cref_route_for_node(test_node,&found)==1 &&
        found.cref_identity_sequence==bound.cref_identity_sequence &&
        found.route_index==bound.route_index &&
        found.raw_handle==bound.raw_handle &&
        found.language_sequence==current_generation &&
        route_still_exact(&found) &&
        InterlockedCompareExchange(&fatal_latch,0,0)==0;
    return exact;
}

int photon_v6_pf_selector_test_language_generation_aba_predicate(void) {
    void *archive,*root,*selected=NULL,*cref_self;
    LONG epoch,selected_epoch=0,generation=0;
    RouteFrame stale;
    int transition_started,bound;
    photon_v6_pf_selector_test_reset();
    (void)photon_v6_pf_selector_test_set_language(
        PHOTON_V6_PF_SELECTOR_LANGUAGE_TRANSLATION);
    archive=test_image+0x00301000;
    root=test_image+0x00302000;
    cref_self=test_image+0x00303000;
    test_write_pointer(cref_self,0,(uintptr_t)test_node);
    epoch=graph_root_begin(root,archive);
    if (epoch<=0 ||
        !active_graph_snapshot(archive,&selected,&selected_epoch,&generation) ||
        selected!=root || selected_epoch!=epoch) return 0;
    memset(&stale,0,sizeof(stale));
    stale.tid=GetCurrentThreadId(); stale.archive=archive;
    stale.graph_root=root; stale.cref_self=cref_self;
    stale.resolved_node=test_node; stale.raw_handle=routes[0].raw_handle;
    stale.route_index=0; stale.graph_epoch=epoch;
    stale.language_sequence=generation;
    stale.runtime_graph_identity_exact=1;
    transition_started=begin_language_transition(
        PHOTON_V6_PF_SELECTOR_LANGUAGE_TRANSLATION);
    bound=bind_cref_identity(&stale);
    return !transition_started && !bound &&
        InterlockedCompareExchange(&fatal_latch,0,0)==1;
}

int photon_v6_pf_selector_test_route_ambiguity_predicate(void) {
    PhotonV6PfSelectorDecision decision;
    photon_v6_pf_selector_test_reset();
    (void)photon_v6_pf_selector_test_set_language(
        PHOTON_V6_PF_SELECTOR_LANGUAGE_TRANSLATION);
    memset(&decision,0,sizeof(decision));
    return !photon_v6_pf_selector_test_run_causal_scenario(0,0,0,
        PHOTON_V6_PF_SELECTOR_TEST_MUTATE_ROUTE_AMBIGUITY,&decision) &&
        InterlockedCompareExchange(&fatal_latch,0,0)==1;
}

int photon_v6_pf_selector_test_node_aba_predicate(void) {
    PhotonV6PfSelectorDecision decision;
    photon_v6_pf_selector_test_reset();
    (void)photon_v6_pf_selector_test_set_language(
        PHOTON_V6_PF_SELECTOR_LANGUAGE_TRANSLATION);
    memset(&decision,0,sizeof(decision));
    return !photon_v6_pf_selector_test_run_causal_scenario(0,0,0,
        PHOTON_V6_PF_SELECTOR_TEST_MUTATE_NODE_ABA,&decision);
}

int photon_v6_pf_selector_test_transition_latch_predicate(
    uint32_t abnormal_store) {
    PhotonV6PfSelectorDecision decision;
    int began,allowed,finished;
    memset(&decision,0,sizeof(decision));
    began=begin_language_transition(
        PHOTON_V6_PF_SELECTOR_LANGUAGE_TRANSLATION);
    allowed=photon_v6_pf_selector_adapter_surface_enter(test_object,&decision);
    finished=finish_language_transition(
        PHOTON_V6_PF_SELECTOR_LANGUAGE_JAPANESE,
        abnormal_store?0:1,0,test_object,test_object);
    return began && !allowed && (abnormal_store?!finished:finished) &&
        (abnormal_store?
            InterlockedCompareExchange(&fatal_latch,0,0)==1:
            InterlockedCompareExchange(&language_state,0,0)==
                PHOTON_V6_PF_SELECTOR_LANGUAGE_JAPANESE);
}

int photon_v6_pf_selector_test_known_language_identity_drift_predicate(void) {
    void *known=(void *)(uintptr_t)UINT32_C(0x11110000);
    void *different=(void *)(uintptr_t)UINT32_C(0x22220000);
    return known_language_call_is_anomalous(
               known,different,UINT32_C(0x237),1,0) &&
        known_language_call_is_anomalous(
               known,known,UINT32_C(0x100),0,0) &&
        !known_language_call_is_anomalous(
               known,different,UINT32_C(0x100),1,0) &&
        !known_language_call_is_anomalous(
               known,different,UINT32_C(0x237),1,1);
}

int photon_v6_pf_selector_test_known_language_setter_predicate(void) {
    void *known=(void *)(uintptr_t)UINT32_C(0x11110000);
    void *different=(void *)(uintptr_t)UINT32_C(0x22220000);
    void *owner=(void *)(uintptr_t)UINT32_C(0x33330000);
    uint32_t vtable=(uint32_t)(uintptr_t)(main_base+PF_CINT_VTABLE_RVA);
    uint32_t type=UINT32_C(0x16000000);
    return known_language_setter_fields_exact(
               known,known,owner,(uint32_t)(uintptr_t)owner,
               vtable,type,1,0,1) &&
        known_language_setter_fields_exact(
               known,known,owner,(uint32_t)(uintptr_t)owner,
               vtable,type,1,1,1) &&
        !known_language_setter_fields_exact(
               known,different,owner,(uint32_t)(uintptr_t)owner,
               vtable,type,1,0,1) &&
        !known_language_setter_fields_exact(
               known,known,owner,UINT32_C(0x44440000),
               vtable,type,1,0,1) &&
        !known_language_setter_fields_exact(
               known,known,owner,(uint32_t)(uintptr_t)owner,
               vtable+4,type,1,0,1) &&
        !known_language_setter_fields_exact(
               known,known,owner,(uint32_t)(uintptr_t)owner,
               vtable,type^1U,1,0,1) &&
        !known_language_setter_fields_exact(
               known,known,owner,(uint32_t)(uintptr_t)owner,
               vtable,type,2,0,1) &&
        !known_language_setter_fields_exact(
               known,known,owner,(uint32_t)(uintptr_t)owner,
               vtable,type,1,2,1) &&
        !known_language_setter_fields_exact(
               known,known,owner,(uint32_t)(uintptr_t)owner,
               vtable,type,1,0,0);
}

int photon_v6_pf_selector_test_known_language_live_setter_predicate(void) {
    void *known=(void *)(uintptr_t)UINT32_C(0x11110000);
    void *different=(void *)(uintptr_t)UINT32_C(0x22220000);
    void *owner=(void *)(uintptr_t)UINT32_C(0x33330000);
    return known_language_live_setter_fields_exact(
               known,known,owner,(uint32_t)(uintptr_t)owner,1,1,1,1) &&
        known_language_live_setter_fields_exact(
               known,known,owner,(uint32_t)(uintptr_t)owner,1,1,0,
               PHOTON_V6_PF_SELECTOR_LANGUAGE_UNKNOWN) &&
        !known_language_live_setter_fields_exact(
               known,different,owner,(uint32_t)(uintptr_t)owner,1,1,0,1) &&
        !known_language_live_setter_fields_exact(
               known,known,owner,UINT32_C(0x44440000),1,1,0,1) &&
        !known_language_live_setter_fields_exact(
               known,known,owner,(uint32_t)(uintptr_t)owner,0,1,0,1) &&
        !known_language_live_setter_fields_exact(
               known,known,owner,(uint32_t)(uintptr_t)owner,1,1,2,1) &&
        !known_language_live_setter_fields_exact(
               known,known,owner,(uint32_t)(uintptr_t)owner,1,1,0,0);
}

int photon_v6_pf_selector_test_object_binding_splice_predicate(void) {
    ObjectBinding original,replacement,expected,current;
    ObjectBinding *slot=NULL;
    int original_rejected,same_thread_exact,cross_thread_rejected;
    size_t index;
    memset(&original,0,sizeof(original));
    if (!binding_snapshot(test_object,&original) ||
        !binding_revalidate_exact(&original)) return 0;

    /* Same-object reentry replaces every causal field as one locked record.
     * A pre-reentry snapshot must not be accepted after publication. */
    replacement=original;
    replacement.active=0;
    replacement.materializer_sequence=InterlockedIncrement(
        &materializer_sequence);
    replacement.object_generation=InterlockedIncrement(
        &object_generation_sequence);
    AcquireSRWLockExclusive(&state_lock);
    for (index=0;index<MAX_OBJECT_BINDINGS;++index)
        if (object_bindings[index].active &&
            object_bindings[index].object==test_object) {
            slot=&object_bindings[index]; break;
        }
    if (slot) publish_object_binding_locked(slot,&replacement);
    ReleaseSRWLockExclusive(&state_lock);
    if (!slot) return 0;
    expected=replacement; expected.active=1;
    original_rejected=!binding_revalidate_exact(&original);
    same_thread_exact=binding_revalidate_exact(&expected);

    /* A simulated cross-thread replacement likewise invalidates the prior
     * token; it can never be spliced with this thread's route snapshot. */
    replacement=expected;
    replacement.active=0;
    replacement.tid^=UINT32_C(0x40000000);
    replacement.materializer_sequence=InterlockedIncrement(
        &materializer_sequence);
    replacement.object_generation=InterlockedIncrement(
        &object_generation_sequence);
    AcquireSRWLockExclusive(&state_lock);
    publish_object_binding_locked(slot,&replacement);
    current=*slot;
    ReleaseSRWLockExclusive(&state_lock);
    cross_thread_rejected=!binding_revalidate_exact(&expected) &&
        current.active && current.tid==replacement.tid &&
        current.object_generation==replacement.object_generation &&
        current.materializer_sequence==replacement.materializer_sequence &&
        memcmp(current.payload_sha256,replacement.payload_sha256,32)==0;
    return original_rejected && same_thread_exact && cross_thread_rejected;
}

int photon_v6_pf_selector_test_authorization_lease_mutation_predicate(void) {
    PhotonV6PfSelectorDecision entered,decoded;
    ObjectBinding before,after;
    int mutation_blocked,preserved,lease_held,lease_released;
    memset(&before,0,sizeof(before));
    memset(&entered,0,sizeof(entered));
    memset(&decoded,0,sizeof(decoded));
    if (!binding_snapshot(test_object,&before) ||
        !photon_v6_pf_selector_adapter_surface_enter(test_object,&entered) ||
        !photon_v6_pf_selector_adapter_decode_query(&decoded)) return 0;
    lease_held=InterlockedCompareExchange(
        &translation_write_leases,0,0)==1 &&
        InterlockedCompareExchange(&special_write_leases,0,0)==1 &&
        InterlockedCompareExchange(&ordinary_write_leases,0,0)==0;
    mutation_blocked=!clear_object_binding(test_object,NULL,
        OBJECT_BINDING_CLEAR_TEST_MUTATION);
    memset(&after,0,sizeof(after));
    AcquireSRWLockShared(&state_lock);
    preserved=object_binding_current_exact_locked(&before);
    if (preserved)
        for (size_t index=0;index<MAX_OBJECT_BINDINGS;++index)
            if (object_bindings[index].active &&
                object_bindings[index].object==test_object) {
                after=object_bindings[index]; break;
            }
    ReleaseSRWLockShared(&state_lock);
    photon_v6_pf_selector_adapter_surface_leave(test_object);
    lease_released=InterlockedCompareExchange(
        &translation_write_leases,0,0)==0 &&
        InterlockedCompareExchange(&special_write_leases,0,0)==0;
    return lease_held && mutation_blocked && preserved &&
        object_binding_same_identity(&before,&after) && lease_released &&
        InterlockedCompareExchange(&fatal_latch,0,0)==1;
}

int photon_v6_pf_selector_test_lease_census_corruption_predicate(void) {
    PhotonV6PfSelectorDecision committed,entered,decoded;
    ActiveSurface *authorized=NULL;
    LONG saved_sequence=0;
    int ordinary_drift_rejected=0,special_flag_drift_rejected=0;
    int special_counter_drift_rejected=0,special_shape_drift_rejected=0;
    int baseline_exact=0,restored_exact=0,terminal_exact=0;
    size_t index;
    memset(&committed,0,sizeof(committed));
    memset(&entered,0,sizeof(entered));
    memset(&decoded,0,sizeof(decoded));
    photon_v6_pf_selector_test_reset();
    if (!photon_v6_pf_selector_test_set_language(
            PHOTON_V6_PF_SELECTOR_LANGUAGE_TRANSLATION)) return 0;

    /* A counter with no published lease slot is never a valid census. */
    AcquireSRWLockExclusive(&state_lock);
    baseline_exact=lease_census_exact_locked();
    InterlockedIncrement(&ordinary_write_leases);
    InterlockedIncrement(&translation_write_leases);
    ordinary_drift_rejected=!lease_census_exact_locked();
    InterlockedDecrement(&translation_write_leases);
    InterlockedDecrement(&ordinary_write_leases);
    restored_exact=lease_census_exact_locked();
    ReleaseSRWLockExclusive(&state_lock);
    if (!baseline_exact || !ordinary_drift_rejected || !restored_exact)
        return 0;

    if (!photon_v6_pf_selector_test_run_causal_scenario(
            0,0,0,0,&committed) ||
        !photon_v6_pf_selector_adapter_surface_enter(test_object,&entered) ||
        !photon_v6_pf_selector_adapter_decode_query(&decoded)) return 0;

    AcquireSRWLockExclusive(&state_lock);
    baseline_exact=lease_census_exact_locked();
    for (index=0;index<MAX_ACTIVE_SURFACES;++index)
        if (active_surfaces[index].active &&
            active_surfaces[index].authorization_lease) {
            if (authorized) {
                authorized=NULL;
                break;
            }
            authorized=&active_surfaces[index];
        }
    if (authorized) {
        authorized->authorization_lease=0;
        special_flag_drift_rejected=!lease_census_exact_locked();
        authorized->authorization_lease=1;

        InterlockedIncrement(&special_write_leases);
        InterlockedIncrement(&translation_write_leases);
        special_counter_drift_rejected=!lease_census_exact_locked();
        InterlockedDecrement(&translation_write_leases);
        InterlockedDecrement(&special_write_leases);

        saved_sequence=authorized->sequence;
        authorized->sequence=0;
        special_shape_drift_rejected=!lease_census_exact_locked();
        authorized->sequence=saved_sequence;
        restored_exact=lease_census_exact_locked();
    }
    ReleaseSRWLockExclusive(&state_lock);
    photon_v6_pf_selector_adapter_surface_leave(test_object);
    AcquireSRWLockShared(&state_lock);
    terminal_exact=lease_census_exact_locked() &&
        InterlockedCompareExchange(&translation_write_leases,0,0)==0 &&
        InterlockedCompareExchange(&ordinary_write_leases,0,0)==0 &&
        InterlockedCompareExchange(&special_write_leases,0,0)==0;
    ReleaseSRWLockShared(&state_lock);
    return baseline_exact && authorized && special_flag_drift_rejected &&
        special_counter_drift_rejected && special_shape_drift_rejected &&
        restored_exact && terminal_exact &&
        InterlockedCompareExchange(&fatal_latch,0,0)==0;
}

typedef struct TestLanguageTransitionWorker {
    volatile LONG entered;
    volatile LONG done;
    volatile LONG native_setter_calls;
    LONG began;
    LONG finished;
} TestLanguageTransitionWorker;

static DWORD WINAPI test_language_transition_worker(void *opaque) {
    TestLanguageTransitionWorker *worker=
        (TestLanguageTransitionWorker *)opaque;
    InterlockedExchange(&worker->entered,1);
    worker->began=begin_language_transition(
        PHOTON_V6_PF_SELECTOR_LANGUAGE_TRANSLATION);
    if (worker->began) {
        InterlockedIncrement(&worker->native_setter_calls);
        worker->finished=finish_language_transition(
            PHOTON_V6_PF_SELECTOR_LANGUAGE_JAPANESE,1,0,
            test_object,test_object);
    }
    InterlockedExchange(&worker->done,1);
    return 0;
}

int photon_v6_pf_selector_test_generation_bound_write_lease_predicate(void) {
    PhotonV6PfSelectorDecision committed,entered,decoded;
    PhotonV6PfSelectorStatus status;
    TestLanguageTransitionWorker worker;
    HANDLE thread=NULL;
    uint32_t old_token=0,old_generation=0,new_token=0,new_generation=0;
    int surface_open=0,ordinary_open=0,exact=1,retry;
    memset(&committed,0,sizeof(committed));
    memset(&entered,0,sizeof(entered));
    memset(&decoded,0,sizeof(decoded));
    memset(&worker,0,sizeof(worker));
    photon_v6_pf_selector_test_reset();
    if (!photon_v6_pf_selector_test_set_language(
            PHOTON_V6_PF_SELECTOR_LANGUAGE_TRANSLATION) ||
        !photon_v6_pf_selector_test_run_causal_scenario(
            0,0,0,0,&committed) ||
        !photon_v6_pf_selector_adapter_surface_enter(test_object,&entered))
        return 0;
    surface_open=1;
    if (!photon_v6_pf_selector_adapter_decode_query(&decoded) ||
        !photon_v6_pf_selector_adapter_ordinary_lease_acquire(
            &old_token,&old_generation)) exact=0;
    else ordinary_open=1;
    exact=exact && old_token!=0 && old_generation!=0 &&
        decoded.language_state_sequence==old_generation &&
        InterlockedCompareExchange(&translation_write_leases,0,0)==2 &&
        InterlockedCompareExchange(&ordinary_write_leases,0,0)==1 &&
        InterlockedCompareExchange(&special_write_leases,0,0)==1;
    if (exact) thread=CreateThread(NULL,0,test_language_transition_worker,
        &worker,0,NULL);
    exact=exact && thread!=NULL;
    for (retry=0;thread && retry<1000;++retry) {
        if (InterlockedCompareExchange(
                &language_transition_inflight,0,0)==1) break;
        Sleep(1);
    }
    exact=exact && InterlockedCompareExchange(
        &language_transition_inflight,0,0)==1 &&
        InterlockedCompareExchange(&worker.done,0,0)==0 &&
        !photon_v6_pf_selector_adapter_ordinary_lease_validate(
            old_token,old_generation);
    if (ordinary_open) {
        photon_v6_pf_selector_adapter_ordinary_lease_release(
            old_token,old_generation);
        ordinary_open=0;
    }
    Sleep(5);
    exact=exact && InterlockedCompareExchange(&worker.done,0,0)==0 &&
        InterlockedCompareExchange(&translation_write_leases,0,0)==1 &&
        InterlockedCompareExchange(&ordinary_write_leases,0,0)==0 &&
        InterlockedCompareExchange(&special_write_leases,0,0)==1;
    if (surface_open) {
        photon_v6_pf_selector_adapter_surface_leave(test_object);
        surface_open=0;
    }
    if (thread) {
        exact=exact && WaitForSingleObject(thread,2000)==WAIT_OBJECT_0;
        CloseHandle(thread);
    }
    exact=exact && worker.began==1 && worker.finished==1 &&
        InterlockedCompareExchange(&worker.native_setter_calls,0,0)==1 &&
        InterlockedCompareExchange(&language_state,0,0)==
            PHOTON_V6_PF_SELECTOR_LANGUAGE_JAPANESE &&
        InterlockedCompareExchange(&translation_write_leases,0,0)==0 &&
        InterlockedCompareExchange(&ordinary_write_leases,0,0)==0 &&
        InterlockedCompareExchange(&special_write_leases,0,0)==0;
    exact=exact && begin_language_transition(
        PHOTON_V6_PF_SELECTOR_LANGUAGE_JAPANESE) &&
        finish_language_transition(
            PHOTON_V6_PF_SELECTOR_LANGUAGE_TRANSLATION,1,0,
            test_object,test_object);
    exact=exact && !photon_v6_pf_selector_adapter_ordinary_lease_validate(
        old_token,old_generation) &&
        photon_v6_pf_selector_adapter_ordinary_lease_acquire(
            &new_token,&new_generation) &&
        new_token!=0 && new_token!=old_token &&
        new_generation!=0 && new_generation!=old_generation &&
        photon_v6_pf_selector_adapter_ordinary_lease_validate(
            new_token,new_generation);
    if (new_token)
        photon_v6_pf_selector_adapter_ordinary_lease_release(
            new_token,new_generation);
    memset(&status,0,sizeof(status));
    photon_v6_pf_selector_adapter_query(&status);
    exact=exact && status.snapshot_consistent==1 &&
        status.translation_write_leases_active==0 &&
        status.ordinary_write_leases_active==0 &&
        status.special_write_leases_active==0 &&
        status.ordinary_lease_acquires>=2 &&
        status.ordinary_lease_releases>=2 &&
        status.ordinary_lease_generation_rejects>=2 &&
        status.fatal_latch==0;
    return exact;
}

int photon_v6_pf_selector_test_long_lease_setter_barrier_predicate(void) {
    TestLanguageTransitionWorker worker;
    PhotonV6PfSelectorStatus status;
    HANDLE thread=NULL;
    uint32_t token=0,generation=0;
    int lease_open=0,exact=1,retry;
    memset(&worker,0,sizeof(worker));
    photon_v6_pf_selector_test_reset();
    if (!photon_v6_pf_selector_test_set_language(
            PHOTON_V6_PF_SELECTOR_LANGUAGE_TRANSLATION) ||
        !photon_v6_pf_selector_adapter_ordinary_lease_acquire(
            &token,&generation)) return 0;
    lease_open=1;
    thread=CreateThread(NULL,0,test_language_transition_worker,&worker,0,NULL);
    exact=thread!=NULL;
    for (retry=0;thread && retry<1000;++retry) {
        if (InterlockedCompareExchange(
                &language_transition_inflight,0,0)==1) break;
        Sleep(1);
    }
    /* Exceed the superseded v4.7 ten-second drain timeout.  The native setter
     * surrogate must still be untouched and Japanese must not be committed. */
    if (thread) Sleep(10250);
    exact=exact && InterlockedCompareExchange(
        &language_transition_inflight,0,0)==1 &&
        InterlockedCompareExchange(&worker.done,0,0)==0 &&
        InterlockedCompareExchange(&worker.native_setter_calls,0,0)==0 &&
        InterlockedCompareExchange(&language_state,0,0)==
            PHOTON_V6_PF_SELECTOR_LANGUAGE_TRANSLATION &&
        InterlockedCompareExchange(&translation_write_leases,0,0)==1 &&
        InterlockedCompareExchange(&ordinary_write_leases,0,0)==1 &&
        InterlockedCompareExchange(&special_write_leases,0,0)==0 &&
        !photon_v6_pf_selector_adapter_ordinary_lease_validate(
            token,generation);
    if (lease_open) {
        photon_v6_pf_selector_adapter_ordinary_lease_release(token,generation);
        lease_open=0;
    }
    if (thread) {
        exact=exact && WaitForSingleObject(thread,3000)==WAIT_OBJECT_0;
        CloseHandle(thread);
    }
    exact=exact && worker.began==1 && worker.finished==1 &&
        InterlockedCompareExchange(&worker.native_setter_calls,0,0)==1 &&
        InterlockedCompareExchange(&language_state,0,0)==
            PHOTON_V6_PF_SELECTOR_LANGUAGE_JAPANESE &&
        InterlockedCompareExchange(&translation_write_leases,0,0)==0 &&
        InterlockedCompareExchange(&language_transition_inflight,0,0)==0;
    /* Explicit audited recovery path: a second drained transition restores
     * Translation and reopens the latch without deadlock. */
    exact=exact && begin_language_transition(
        PHOTON_V6_PF_SELECTOR_LANGUAGE_JAPANESE) &&
        finish_language_transition(
            PHOTON_V6_PF_SELECTOR_LANGUAGE_TRANSLATION,1,0,
            test_object,test_object);
    memset(&status,0,sizeof(status));
    photon_v6_pf_selector_adapter_query(&status);
    return exact && status.snapshot_consistent==1 &&
        status.language_state==PHOTON_V6_PF_SELECTOR_LANGUAGE_TRANSLATION &&
        status.translation_write_leases_active==0 &&
        status.ordinary_write_leases_active==0 &&
        status.special_write_leases_active==0 && status.fatal_latch==0;
}

int photon_v6_pf_selector_test_same_thread_setter_reentry_predicate(void) {
    PhotonV6PfSelectorDecision committed,entered,decoded;
    uint32_t token=0,generation=0;
    LONG native_setter_calls=0;
    int ordinary_began,special_began,ordinary_exact,special_exact;

    /* Ordinary lease owned by this setter thread must return to the dispatch
     * hard-failure path immediately, with the latch retained and no store. */
    photon_v6_pf_selector_test_reset();
    if (!photon_v6_pf_selector_test_set_language(
            PHOTON_V6_PF_SELECTOR_LANGUAGE_TRANSLATION) ||
        !photon_v6_pf_selector_adapter_ordinary_lease_acquire(
            &token,&generation)) return 0;
    ordinary_began=begin_language_transition(
        PHOTON_V6_PF_SELECTOR_LANGUAGE_TRANSLATION);
    if (ordinary_began) InterlockedIncrement(&native_setter_calls);
    ordinary_exact=!ordinary_began && native_setter_calls==0 &&
        InterlockedCompareExchange(&language_transition_inflight,0,0)==1 &&
        InterlockedCompareExchange(&language_state,0,0)==
            PHOTON_V6_PF_SELECTOR_LANGUAGE_TRANSLATION &&
        InterlockedCompareExchange(&fatal_latch,0,0)==1;
    photon_v6_pf_selector_adapter_ordinary_lease_release(token,generation);
    ordinary_exact=ordinary_exact &&
        InterlockedCompareExchange(&translation_write_leases,0,0)==0;

    /* The same invariant applies to a Decode-authorized special Surface. */
    memset(&committed,0,sizeof(committed));
    memset(&entered,0,sizeof(entered));
    memset(&decoded,0,sizeof(decoded));
    photon_v6_pf_selector_test_reset();
    if (!photon_v6_pf_selector_test_set_language(
            PHOTON_V6_PF_SELECTOR_LANGUAGE_TRANSLATION) ||
        !photon_v6_pf_selector_test_run_causal_scenario(
            0,0,0,0,&committed) ||
        !photon_v6_pf_selector_adapter_surface_enter(test_object,&entered) ||
        !photon_v6_pf_selector_adapter_decode_query(&decoded)) return 0;
    native_setter_calls=0;
    special_began=begin_language_transition(
        PHOTON_V6_PF_SELECTOR_LANGUAGE_TRANSLATION);
    if (special_began) InterlockedIncrement(&native_setter_calls);
    special_exact=!special_began && native_setter_calls==0 &&
        InterlockedCompareExchange(&language_transition_inflight,0,0)==1 &&
        InterlockedCompareExchange(&language_state,0,0)==
            PHOTON_V6_PF_SELECTOR_LANGUAGE_TRANSLATION &&
        InterlockedCompareExchange(&fatal_latch,0,0)==1;
    photon_v6_pf_selector_adapter_surface_leave(test_object);
    special_exact=special_exact &&
        InterlockedCompareExchange(&translation_write_leases,0,0)==0 &&
        InterlockedCompareExchange(&special_write_leases,0,0)==0;
    return ordinary_exact && special_exact;
}
#endif




static uintptr_t __attribute__((cdecl,noinline,used))
hook_cref_read_counted(void *self, void *archive, uint32_t raw_handle) {
    ArchiveSample before,after;
    uintptr_t result,tagged;
    void *resolved,*graph_root=NULL;
    LONG graph_epoch=0,graph_language_sequence=0;
    int route_index;
    if (!selector_semantics_enabled())
        return real_cref_read(self,archive,raw_handle);
    before=sample_archive(archive);
    result=real_cref_read(self,archive,raw_handle);
    after=sample_archive(archive);
    if (!selector_semantics_enabled()) return result;
    route_index=find_route(raw_handle);
    if (route_index>=0) {
        RouteFrame frame;
        int bind_exact=0;
        int graph_active=active_graph_snapshot(archive,&graph_root,&graph_epoch,
            &graph_language_sequence);
        tagged=safe_pointer(self,0);
        resolved=(void *)(tagged&~(uintptr_t)3);
        memset(&frame,0,sizeof(frame));
        frame.tid=GetCurrentThreadId(); frame.archive=archive;
        frame.graph_root=graph_root; frame.cref_self=self;
        frame.resolved_node=resolved; frame.raw_handle=raw_handle;
        frame.route_index=route_index; frame.graph_epoch=graph_epoch;
        frame.language_sequence=graph_language_sequence;
        frame.runtime_graph_identity_exact=graph_active &&
            validate_cref_read(&routes[route_index],self,archive,graph_root,
                graph_epoch,&before,&after,result,resolved);
        if (frame.runtime_graph_identity_exact)
            bind_exact=bind_cref_identity(&frame);
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
        diagnostic_record_cref(&frame,graph_active,
            frame.runtime_graph_identity_exact,bind_exact);
#endif
        if (bind_exact) {
            telemetry_increment(&cref_identity_events);
        } else telemetry_increment(&cref_identity_rejects);
    }
    return result;
}

static uintptr_t __attribute__((cdecl,noinline,used))
hook_resource_materializer_counted(void *node) {
    RouteFrame route;
    ActiveMaterialization completed;
    uintptr_t result;
    void *object_before,*object_after,*object;
    uint32_t node_kind=UINT32_MAX;
    LONG state,sequence,materializer_id=0;
    int persistent,node_exact,route_exact=0,pushed=0,popped=0,identity_exact=0;
    if (!selector_semantics_enabled()) {
        result=real_resource_materializer(node);
        return result;
    }
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
    diagnostic_materializer_push(node);
#endif
    telemetry_increment(&materializer_entry_events);
    memset(&route,0,sizeof(route));
    persistent=cref_route_for_node(node,&route);
    node_exact=resource_node_invariants_exact(node,&node_kind);
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
    if (persistent==1) InterlockedOr(&diagnostic_pipeline_flags,0x0001);
    if (persistent==1 && node_exact)
        InterlockedOr(&diagnostic_pipeline_flags,0x0002);
    if (persistent==1 && node_exact && route.cref_identity_sequence>0)
        InterlockedOr(&diagnostic_pipeline_flags,0x0004);
#endif
    route_exact=persistent==1 && node_exact &&
        route.cref_identity_sequence>0 && route_still_exact(&route);
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
    diagnostic_materializer_set_top_ladder(node,persistent,node_exact,
        route_exact,persistent==1?&route:NULL);
    if (route_exact) InterlockedOr(&diagnostic_pipeline_flags,0x0008);
#endif
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
    /*
     * Diagnostic-only materializer ladder.  These counters normally remain
     * zero before a successful special-57 decode, so the diagnostic runtime
     * temporarily uses them to expose exactly how far a live CRef identity
     * travels through the materializer hook:
     *
     * translation_special57_allows      persistent route lookup nonzero
     * state0_translation_endpoint_rejects persistent route lookup exact
     * c07_all_provider_rejects          resource-node invariants exact
     * exact_surface_entries             route still exact before push
     * exact_decode_queries              active materialization pushed
     * surface_identity_rejects          active materialization popped
     * decode_identity_rejects           returned object matches node slot
     */
    if (persistent!=0) telemetry_increment(&translation_special57_allows);
    if (persistent==1)
        telemetry_increment(&state0_translation_endpoint_rejects);
    if (persistent==1 && node_exact)
        telemetry_increment(&c07_all_provider_rejects);
    if (persistent==1 && node_exact && route.cref_identity_sequence>0 &&
        route_still_exact(&route))
        telemetry_increment(&exact_surface_entries);
#endif
    object_before=(void *)safe_pointer(node,0);
    clear_object_binding(object_before,node,
        OBJECT_BINDING_CLEAR_MATERIALIZER_PREPARE);
    state=InterlockedCompareExchange(&language_state,0,0);
    sequence=InterlockedCompareExchange(&language_state_sequence,0,0);
    if (route_exact) {
        materializer_id=InterlockedIncrement(&materializer_sequence);
        pushed=push_materialization(node,&route,object_before,node_kind,
            state,sequence,materializer_id);
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
        if (pushed) {
            telemetry_increment(&exact_decode_queries);
            InterlockedOr(&diagnostic_pipeline_flags,0x0010);
        }
#endif
    } else if (persistent!=0 || node_exact) {
        telemetry_increment(&materializer_identity_rejects);
    }
    result=real_resource_materializer(node);
    object=(void *)result;
    object_after=(void *)safe_pointer(node,0);
    clear_object_binding(object,NULL,
        OBJECT_BINDING_CLEAR_MATERIALIZER_RETURN);
    memset(&completed,0,sizeof(completed));
    if (pushed) popped=pop_materialization(materializer_id,&completed);
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
    if (popped) {
        telemetry_increment(&surface_identity_rejects);
        InterlockedOr(&diagnostic_pipeline_flags,0x0200);
    }
    if (popped && object && object_after==object) {
        telemetry_increment(&decode_identity_rejects);
        InterlockedOr(&diagnostic_pipeline_flags,0x0400);
    }
#endif
    if (popped && object && object_after==object &&
        state==InterlockedCompareExchange(&language_state,0,0) &&
        sequence==InterlockedCompareExchange(&language_state_sequence,0,0) &&
        completed.node_invariants_exact &&
        ((completed.object_before==NULL && completed.nested_load_count==1 &&
          completed.pending.object==object) ||
         (completed.object_before==object && completed.nested_load_count==0))) {
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
        InterlockedOr(&diagnostic_pipeline_flags,0x0800);
#endif
        identity_exact=bind_committed_object(&completed,object,
            completed.object_before==object);
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
        if (identity_exact) InterlockedOr(&diagnostic_pipeline_flags,0x1000);
#endif
    }
    if (pushed && !identity_exact) {
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
        diagnostic_persist_materializer_failure(&completed,node,object_before,
            object_after,object,state,sequence,pushed,popped,identity_exact);
#endif
        AcquireSRWLockExclusive(&state_lock);
        clear_object_binding_locked(object,NULL,
            OBJECT_BINDING_CLEAR_MATERIALIZER_REJECT);
        ReleaseSRWLockExclusive(&state_lock);
        telemetry_increment(&materializer_identity_rejects);
    }
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
    diagnostic_materializer_pop(node);
#endif
    return result;
}

static uintptr_t relevant_setter_hard_failure(uint32_t previous) {
    set_fatal();
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
    diagnostic_persist_transition_failure();
#endif
#ifndef PHOTON_V6_PF_SELECTOR_TEST_HOOKS
    /* A relevant native setter may never run after transition acquisition or
     * drain failure.  Production terminates instead of exposing a torn native
     * language value while an old pixel writer can still exist. */
    RaiseFailFastException(NULL,NULL,0);
    TerminateProcess(GetCurrentProcess(),UINT32_C(0xE00057A5));
#endif
    return (uintptr_t)previous;
}

static uintptr_t __attribute__((cdecl,noinline,used))
hook_cint_setter_dispatch(void *self, uint32_t value, uintptr_t vm_this) {
    uintptr_t result;
    uint32_t vm_vtable,vm_command,vm_source,vm_target,vm_exec;
    uint32_t cint_vtable,cint_owner,cint_meta,previous,stored,cint_type;
    uint16_t vm_opcode;
    int bootstrap_exact,bootstrap_owner_exact=0;
    int transition_started=0;
    int action_stack_exact;
    int bootstrap_candidate=0,action_candidate=0,known_anomaly=0;
    int live_setter_candidate=0;
    int relevant_call=0;
    void *known_this,*known_owner,*sealed_owner=NULL;
    LONG sealed_value=PHOTON_V6_PF_SELECTOR_LANGUAGE_UNKNOWN;
    if (InterlockedCompareExchange(&lifecycle_admission_revoked,0,0) &&
        InterlockedCompareExchange(&initialized,0,0) &&
        !InterlockedCompareExchange(&semantic_gate_disabled,0,0)) {
        previous=safe_u32(self,0x10);
        return relevant_setter_hard_failure(previous);
    }
    if (!selector_semantics_enabled())
        return real_cint_setter(self,value);
    vm_vtable=safe_u32((void *)vm_this,0);
    vm_command=safe_u32((void *)vm_this,8);
    vm_source=safe_u32((void *)vm_this,12);
    vm_target=safe_u32((void *)vm_this,16);
    vm_opcode=safe_u16((void *)vm_this,24);
    vm_exec=vm_vtable!=UINT32_MAX?
        safe_u32((void *)(uintptr_t)vm_vtable,0x1C):UINT32_MAX;
    cint_vtable=safe_u32(self,0);
    cint_owner=safe_u32(self,4);
    cint_meta=safe_u32(self,12);
    previous=safe_u32(self,0x10);
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
    InterlockedExchange(&diagnostic_transition_requested_value,(LONG)value);
    InterlockedExchange(&diagnostic_transition_previous_value,(LONG)previous);
    InterlockedExchange(&diagnostic_transition_self,(LONG)(uintptr_t)self);
    InterlockedExchange(&diagnostic_transition_cint_owner,(LONG)cint_owner);
#endif
    cint_type=cint_meta!=UINT32_MAX?
        safe_u32((void *)(uintptr_t)cint_meta,8)&UINT32_C(0x7FFFFFFF):
        UINT32_MAX;
    bootstrap_exact=image_language_bootstrap_fields_exact(
        main_rva(vm_vtable),main_rva(vm_exec),vm_command,vm_source,vm_opcode,
        main_rva(cint_vtable),vm_target==cint_owner,cint_type,
        exact_image_language_bootstrap_stack());
    bootstrap_owner_exact=image_language_live_candidate_exact(
            self,&sealed_owner,&sealed_value) &&
        sealed_owner==(void *)(uintptr_t)cint_owner &&
        sealed_value==(LONG)previous;
    action_stack_exact=exact_image_language_action_stack();
    known_this=InterlockedCompareExchangePointer(
        (void *volatile *)&language_cint_this,NULL,NULL);
    known_owner=InterlockedCompareExchangePointer(
        (void *volatile *)&language_cint_owner,NULL,NULL);
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
    InterlockedExchange(
        &diagnostic_transition_known_this,(LONG)(uintptr_t)known_this);
    InterlockedExchange(
        &diagnostic_transition_known_owner,(LONG)(uintptr_t)known_owner);
#endif
    if (InterlockedCompareExchange(&initialized,0,0) &&
        !InterlockedCompareExchange(&shutting_down,0,0)) {
        LONG current=InterlockedCompareExchange(&language_state,0,0);
        live_setter_candidate=known_language_live_setter_fields_exact(
            known_this,self,known_owner,cint_owner,bootstrap_owner_exact,
            previous,value,current);
        bootstrap_candidate=(!known_this || live_setter_candidate) &&
            (bootstrap_exact || bootstrap_owner_exact) && value<=1 &&
            current==PHOTON_V6_PF_SELECTOR_LANGUAGE_UNKNOWN;
        action_candidate=known_language_setter_fields_exact(
            known_this,self,known_owner,cint_owner,cint_vtable,cint_type,
            previous,value,current) ||
            (live_setter_candidate && current==(LONG)previous);
        known_anomaly=known_language_call_is_anomalous(
            known_this,self,vm_command,action_stack_exact,
            action_candidate || bootstrap_candidate);
        if (bootstrap_candidate)
            transition_started=begin_language_bootstrap();
        else if (action_candidate)
            transition_started=begin_language_transition((LONG)previous);
        else if (known_anomaly) {
            /* Any unrecognized call on the proven language CInt revokes the
             * shadow before native code can change storage. */
            transition_started=begin_language_transition(current);
            if (!transition_started) set_fatal();
        }
        relevant_call=bootstrap_candidate || action_candidate || known_anomaly;
    }
    if (relevant_call && !transition_started)
        return relevant_setter_hard_failure(previous);
    result=real_cint_setter(self,value);
    stored=safe_u32(self,0x10);
#if defined(PHOTON_V6_NATIVE_DIAGNOSTIC_TRACE)
    {
        LONG condition_bits=0;
        if (stored==value) condition_bits|=0x0001;
        if (value<=1) condition_bits|=0x0002;
        if (bootstrap_candidate) condition_bits|=0x0004;
        if (bootstrap_exact) condition_bits|=0x0008;
        if (bootstrap_owner_exact) condition_bits|=0x0010;
        if (!known_this) condition_bits|=0x0020;
        if (action_candidate) condition_bits|=0x0040;
        if (known_this==self) condition_bits|=0x0080;
        if (known_owner==(void *)(uintptr_t)cint_owner)
            condition_bits|=0x0100;
        if (known_anomaly) condition_bits|=0x0200;
        if (range_readable(self,0x14)) condition_bits|=0x0400;
        if (live_setter_candidate) condition_bits|=0x0800;
        InterlockedExchange(&diagnostic_transition_stored_value,(LONG)stored);
        InterlockedExchange(
            &diagnostic_transition_finish_condition_bits,condition_bits);
    }
#endif
    if (transition_started) {
        int exact=stored==value && value<=1 &&
            ((bootstrap_candidate &&
              (bootstrap_exact || bootstrap_owner_exact) &&
              (!known_this || live_setter_candidate)) ||
             (action_candidate && known_this==self && known_owner==
                (void *)(uintptr_t)cint_owner));
        if (known_anomaly) exact=0;
        if (!finish_language_transition((LONG)value,exact,
                bootstrap_candidate,self,(void *)(uintptr_t)cint_owner))
            return relevant_setter_hard_failure(previous);
    } else if (known_anomaly || bootstrap_candidate || action_candidate) {
        return relevant_setter_hard_failure(previous);
    }
    return result;
}
