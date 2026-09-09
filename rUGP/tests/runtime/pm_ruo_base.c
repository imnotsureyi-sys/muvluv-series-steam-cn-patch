/* Synthetic memory only. Inject Win32 failures around the production helper. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <string.h>

static unsigned protect_calls, flush_calls, fail_protect, fail_flush;
static BOOL test_protect(LPVOID address, SIZE_T size, DWORD mode, PDWORD old) {
    if (++protect_calls == fail_protect) return FALSE;
    return VirtualProtect(address, size, mode, old);
}
static BOOL test_flush(HANDLE process, LPCVOID address, SIZE_T size) {
    if (++flush_calls == fail_flush) return FALSE;
    return FlushInstructionCache(process, address, size);
}
#define VirtualProtect test_protect
#define FlushInstructionCache test_flush
#include "photon_pm_ruo_base_fix.h"
#undef VirtualProtect
#undef FlushInstructionCache

#define CHECK(expr) do { if (!(expr)) { fprintf(stderr, "RUO check failed at %d: %s\n", __LINE__, #expr); return 1; } } while (0)

int main(void) {
    static const BYTE original[8] = {0x05,0xff,0xff,0xff,0x7f,0x83,0xd2,0x01};
    SIZE_T length = PHOTON_PM_RUO_BASE_RVA + 16;
    BYTE *host = VirtualAlloc(NULL, length, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    CHECK(host);
    BYTE *site = host + PHOTON_PM_RUO_BASE_RVA;
    CHECK(!photon_pm_fix_ruo_base(NULL, length));
    CHECK(!photon_pm_fix_ruo_base(host, PHOTON_PM_RUO_BASE_RVA + 7));
    CHECK(!photon_pm_fix_ruo_base(host, length));
    CHECK(!protect_calls && !flush_calls);
    for (unsigned scenario = 0; scenario < 5; ++scenario) {
        DWORD previous;
        CHECK(VirtualProtect(host, length, PAGE_READWRITE, &previous));
        memset(host, 0xA5, length);
        memcpy(site, original, sizeof(original));
        CHECK(VirtualProtect(host, length, PAGE_EXECUTE_READ, &previous));
        protect_calls = flush_calls = 0;
        fail_protect = scenario == 1 ? 1 : scenario == 3 ? 2 : scenario == 4 ? 3 : 0;
        fail_flush = scenario == 2 || scenario == 4 ? 1 : 0;
        int result = photon_pm_fix_ruo_base(host, length);
        CHECK(result == (scenario == 0));
        CHECK(site[-1] == 0xA5 && site[8] == 0xA5);
        if (scenario == 0) {
            CHECK(site[4] == 0xFF);
            CHECK(!memcmp(site, original, 4) && !memcmp(site + 5, original + 5, 3));
            unsigned calls = protect_calls;
            CHECK(photon_pm_fix_ruo_base(host, length) && protect_calls == calls);
        } else if (scenario != 4) {
            CHECK(!memcmp(site, original, sizeof(original)));
        } else {
            /* A failed rollback protection call cannot promise restoration.
             * Failure must still propagate to the startup guard. */
            CHECK(site[4] == 0xFF);
        }
    }
    CHECK(VirtualFree(host, 0, MEM_RELEASE));
    puts("{\"passed\":true,\"scenarios\":8,\"game_started\":false}");
    return 0;
}
