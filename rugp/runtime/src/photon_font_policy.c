#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <string.h>
#include <wchar.h>
#include "photon_font_policy.h"

int photon_font_rewrite_logfont(const LOGFONTW *requested, LOGFONTW *adjusted) {
    if (!requested || !adjusted) return 0;
    *adjusted = *requested;
    memset(adjusted->lfFaceName, 0, sizeof(adjusted->lfFaceName));
    wcsncpy(adjusted->lfFaceName, PHOTON_RUNTIME_FACE, LF_FACESIZE - 1);
    adjusted->lfFaceName[LF_FACESIZE - 1] = 0;
    return 1;
}
