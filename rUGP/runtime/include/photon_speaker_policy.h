#ifndef PHOTON_SPEAKER_POLICY_H
#define PHOTON_SPEAKER_POLICY_H
#include <wchar.h>
typedef int (__fastcall *PhotonSpeakerMatch)(const wchar_t *, const wchar_t *);
int photon_speaker_match(const wchar_t *name, const wchar_t *aliases, PhotonSpeakerMatch original);
/* Call only after the enclosing proxy has verified the exact host SHA-256. */
int photon_install_speaker_hook(void);
#endif
