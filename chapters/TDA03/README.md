# TDA03

## Status

- Branch: `chapter/tda03`
- Current public version: `tda03-beta0.1`
- Release: <https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/tag/tda03-beta0.1>
- Source rows: 6,913
- Patch state: released test patch

## Scope

TDA03 covers `Muv-Luv Unlimited: THE DAY AFTER episode:03`.

The beta0.1 patch includes simplified Chinese script text, UI text/assets,
video/opening subtitle assets, a font payload, and install scripts.

## Quality Notes

- beta0.1 includes multiple feedback fixes around terminology, speaker display,
  bracket/newline handling, JFK HIVE, orbital drop troops, and related wording.
- Release checks did not find hard failures such as Text ID Not Found, obvious
  missing subtitles, or severe displacement.
- TDA03 is long, so semantic review and playthrough feedback remain important.

## Maintenance Focus

- Continue JP-based semantic review and real-play feedback triage.
- Watch for terminology consistency across TDA01-03.
- Send subtitle/body changes to the TDA03 chapter workflow, not `main`.

## Related Files

- Patch source: `patch-sources/tda03_jp_cn_compare.csv`

