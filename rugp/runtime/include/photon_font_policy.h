#ifndef PHOTON_FONT_POLICY_H
#define PHOTON_FONT_POLICY_H

#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#ifdef __cplusplus
extern "C" {
#endif

#define PHOTON_RUNTIME_FACE L"PhotonR2"

/*
 * Copy a caller-owned LOGFONTW and change only its lfFaceName field.
 * Every layout and style field (including height, width, weight, italic,
 * underline, strikeout, charset and quality) is preserved bit-for-bit.
 */
int photon_font_rewrite_logfont(const LOGFONTW *requested, LOGFONTW *adjusted);

#ifdef __cplusplus
}
#endif

#endif
