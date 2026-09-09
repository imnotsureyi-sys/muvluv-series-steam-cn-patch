#ifndef PHOTON_PM_RUO_BASE_FIX_H
#define PHOTON_PM_RUO_BASE_FIX_H
/* Exact PM host only, called after its full on-disk SHA-256 guard.
 * Move RUO virtual start from 6 GiB (inside .004) to 8 GiB.
 * No disk EXE mutation, resource edits or work inside DllMain. */
#include <windows.h>
#include <string.h>
#define PHOTON_PM_RUO_BASE_RVA 0x1DE2FEu
static int photon_pm_fix_ruo_base(BYTE *host, SIZE_T image_bytes) {
    static const BYTE expected[8] = {0x05,0xff,0xff,0xff,0x7f,0x83,0xd2,0x01};
    static const BYTE patched[8] = {0x05,0xff,0xff,0xff,0xff,0x83,0xd2,0x01};
    BYTE *instruction;
    DWORD old_protection, ignored;
    BOOL flushed, restored;
    if (!host || image_bytes < PHOTON_PM_RUO_BASE_RVA + sizeof(expected)) return 0;
    instruction = host + PHOTON_PM_RUO_BASE_RVA;
    if (memcmp(instruction, patched, sizeof(patched)) == 0) return 1;
    if (memcmp(instruction, expected, sizeof(expected)) != 0) return 0;
    if (!VirtualProtect(instruction + 4, 1, PAGE_EXECUTE_READWRITE, &old_protection)) return 0;
    instruction[4] = patched[4];
    flushed = FlushInstructionCache(GetCurrentProcess(), instruction, sizeof(patched));
    restored = VirtualProtect(instruction + 4, 1, old_protection, &ignored);
    if (!flushed || !restored || memcmp(instruction, patched, sizeof(patched)) != 0) {
        if (VirtualProtect(instruction + 4, 1, PAGE_EXECUTE_READWRITE, &ignored)) {
            instruction[4] = expected[4];
            FlushInstructionCache(GetCurrentProcess(), instruction, sizeof(expected));
            VirtualProtect(instruction + 4, 1, old_protection, &ignored);
        }
        return 0;
    }
    return 1;
}
#endif
