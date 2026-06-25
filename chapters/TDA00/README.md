# TDA00

## Status

- Branch: `chapter/tda00`
- Current public version: `tda00-beta0.1`
- Release: <https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/tag/tda00-beta0.1>
- Source rows: 3,713
- Patch state: released test patch

## Scope

TDA00 covers `Muv-Luv Unlimited: THE DAY AFTER episode:00`.

The beta0.1 patch includes simplified Chinese script text, UI-related text and
image assets, video/opening subtitle assets, a font payload, and install
scripts.

## Quality Notes

- Built from a frozen JP baseline with call-order, speaker, ruby, and display
  slot checks.
- Release audit did not find hard failures such as empty CN rows, Text ID Not
  Found, order mismatch, control-code damage, or English sentence fallback.
- TDA00 has less player feedback than TDA01-03, so semantic and wording issues
  may still remain.

## Maintenance Focus

- Collect real playthrough feedback with screenshots and surrounding context.
- Keep fixes grounded in the JP source text.
- Send subtitle/body changes to the TDA00 chapter workflow, not `main`.

## Related Files

- Patch source: `patch-sources/tda00_jp_cn_compare.csv`
