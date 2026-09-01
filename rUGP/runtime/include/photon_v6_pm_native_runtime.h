#ifndef PHOTON_V6_PM_NATIVE_RUNTIME_H
#define PHOTON_V6_PM_NATIVE_RUNTIME_H

#include "photon_v6_pf_native_runtime.h"

#ifdef __cplusplus
extern "C" {
#endif

/* PF and PM deliberately share one status ABI.  PM now exposes the selector
 * lifecycle and identity counters as well, so truncating this structure to
 * the pre-selector PM layout would make readiness checks read past the end. */
typedef PhotonV6PfNativeStatus PhotonV6PmNativeStatus;

int photon_v6_pm_native_runtime_init(const wchar_t *ordinary_bundle_root);
void photon_v6_pm_native_runtime_shutdown(void);
void photon_v6_pm_native_runtime_query(PhotonV6PmNativeStatus *status);

#ifdef __cplusplus
}
#endif

#endif
