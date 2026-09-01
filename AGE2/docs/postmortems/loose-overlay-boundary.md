# LocalAppData loose-overlay boundary

## Question

Early investigation treated `pack.bin` and `%LOCALAPPDATA%\ancr\<game>\data\root`
as if the latter were an automatic unpacked copy of the former. That model is
wrong and leads to unsafe uninstall advice.

## Decisive evidence

The five audited AGE2 patch installers write game-scoped files under
`%LOCALAPPDATA%\ancr\tda00|tda01|tda02|tda03|tm\data\root` while leaving the
Steam `obb/pack.bin` unchanged. Only paths explicitly written or produced by
the game appear there; a clean run does not materialize every FPD member. Steam
file verification repairs Steam-managed installation files but does not remove
this per-user overlay.

## Production rule

- Treat `pack.bin` as the packed baseline and `data/root` as a separate,
  higher-priority loose-file namespace.
- Preserve the exact relative resource path below `root`; a loose file does
  not work merely because its basename matches.
- Build and uninstall from a complete manifest of files created by the patch.
- Never delete the whole `data`, `data/user`, save, progress or unrelated
  overlay tree to remove one patch.

## Remaining boundary

The historical five beta packages predate complete installed-file manifests,
so their rollback is backup-based and documented centrally in the player
guide. This observation proves the supported overlay behavior; it is not a
claim that every AGE2/FUZZ title uses the same LocalAppData layout.
