/* Resolve Chinese names against the currently active native colour entry.
 * No text, palette, saved state, CArray size or 32-WCHAR alias buffer is edited.
 * Original lookup always wins; the fallback only supplies a reviewed JP alias.
 */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <string.h>
#include <wchar.h>
#include "photon_speaker_policy.h"
#include "photon_speaker_aliases.h"

static PhotonSpeakerMatch g_original;

int photon_speaker_match(const wchar_t *name, const wchar_t *aliases, PhotonSpeakerMatch original) {
    size_t i;
    int matched = original(name, aliases);
    if (matched) return matched;
    for (i = 0; i < sizeof(PHOTON_SPEAKER_ALIASES) / sizeof(PHOTON_SPEAKER_ALIASES[0]); ++i) {
        if (wcscmp(name, PHOTON_SPEAKER_ALIASES[i].chinese) == 0 &&
            original(PHOTON_SPEAKER_ALIASES[i].japanese, aliases)) return 1;
    }
    return 0;
}

static int __fastcall hook_speaker_match(const wchar_t *name, const wchar_t *aliases) {
    return photon_speaker_match(name, aliases, g_original);
}

int photon_install_speaker_hook(void) {
    BYTE *base = (BYTE *)GetModuleHandleW(NULL), *site;
    DWORD old_protect, ignored;
    uint32_t relative;
    static const BYTE prefix[] = {0x8b,0x10,0x8b,0x45,0x08,0x8b,0x08,0xe8};
#if defined(PHOTON_BUILD_PF)
    const uint32_t call_rva = 0x000b4feau, matcher_rva = 0x000b4e80u;
#elif defined(PHOTON_BUILD_PM)
    const uint32_t call_rva = 0x000b6c8au, matcher_rva = 0x000b6b30u;
#else
#error Select a reviewed Photon host.
#endif
    if (!base) return 0;
    site = base + call_rva;
    memcpy(&relative, site + 1, sizeof(relative));
    if (memcmp(site - 7, prefix, sizeof(prefix)) != 0 ||
        relative != matcher_rva - call_rva - 5u) return 0;
    g_original = (PhotonSpeakerMatch)(base + matcher_rva);
    if (!VirtualProtect(site, 5, PAGE_EXECUTE_READWRITE, &old_protect)) return 0;
    relative = (uint32_t)(uintptr_t)hook_speaker_match - (uint32_t)(uintptr_t)(site + 5);
    memcpy(site + 1, &relative, sizeof(relative));
    FlushInstructionCache(GetCurrentProcess(), site, 5);
    if (!VirtualProtect(site, 5, old_protect, &ignored)) return 0;
    return 1;
}
