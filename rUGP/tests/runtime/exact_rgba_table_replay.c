/* Local package regression. Compile with the actual delivery include root.
 * Exercises production binary search and authenticated PNG decode for every
 * key. Arguments: PF|PM and that package's PhotonR2Assets/v6 directory. */
#include "../../runtime/src/photon_v6_exact_rgba_sidecar_loader.c"
#include <stdio.h>

int wmain(int argc, wchar_t **argv) {
    if (argc != 3 || (wcscmp(argv[1], L"PF") && wcscmp(argv[1], L"PM"))) return 2;
    int pf = !wcscmp(argv[1], L"PF");
    PhotonV6ExactRgbaGame game = pf ? PHOTON_V6_EXACT_RGBA_GAME_PF : PHOTON_V6_EXACT_RGBA_GAME_PM;
    const PhotonV6ExactRgbaEntry *table = pf ? photon_v6_pf_exact_rgba : photon_v6_pm_exact_rgba;
    uint32_t count = pf ? photon_v6_pf_exact_rgba_count : photon_v6_pm_exact_rgba_count;
    uint32_t missing = 0, decoded = 0, load_failed = 0;
    for (uint32_t i = 0; i < count; ++i) {
        PhotonV6ExactRgbaLoadStatus failure = PHOTON_V6_EXACT_RGBA_LOAD_UNKNOWN_IDENTITY;
        if (find_entry(game, table[i].payload_bytes, table[i].payload_fnv1a64, &failure) != &table[i]) {
            ++missing;
            continue;
        }
        PhotonV6ExactRgbaImage image = {0};
        if (photon_v6_exact_rgba_sidecar_load(argv[2], game, table[i].payload_bytes,
                table[i].payload_fnv1a64, &image) == 0) ++decoded;
        else ++load_failed;
        photon_v6_exact_rgba_image_free(&image);
    }
    printf("{\"entries\":%lu,\"unreachable\":%lu,\"decoded\":%lu,\"load_failed\":%lu}\n",
           (unsigned long)count, (unsigned long)missing, (unsigned long)decoded, (unsigned long)load_failed);
    return (missing || load_failed) ? 1 : 0;
}
