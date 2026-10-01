# Acceptance evidence

Each requirement needs implementation plus matching verification scope. Status is not inferred
from a task returning success, a manifest loading, or a process staying alive.

| Requirement | Current status | Required evidence |
| --- | --- | --- |
| Maa Win32 native input/screenshot | Capture verified; live input blocked by game HIGH vs Maa MEDIUM integrity | Running game capture and recognized click with page postcondition |
| PI V2 labels and EN/JP resources | Maa resources parsed; interface schema checked; MXU UI pending | Actual Maa parser + MXU UI |
| Variable cover/background recognition | Actual Maa saved-frame replay: reference, changed cover, unknown | Four supplied frames + live frame; negative and changed-art replay |
| Saved teams / deployment / rotation | Library selector replay passed; profiles/checkpoints persist; actual deployment/rotation pending | Save/restart persistence + two different confirmed dungeon teams |
| Five hard floors | Not verified | Floor 1..5 battle and completion observations |
| Rewards then repeat | Not verified | Reward receipt and next-run entry with next team |
| Gifts / enemy buffs / theme pack selection | Floor-gift OCR/icon candidates + five actual Maa derived replays passed; enemy buffs/pack integration pending | Live selection quota, confirmation, acquisition and next-floor postcondition |
| Human-paced jitter and bounded sessions | Finite Maa node hits; inset clicks/delays, bounded setup/stop jobs and monotonic CLI deadline tested | Full-run cancellation and timeout checks still required |
| Stamina conversion / refill budgets | Pure budget boundaries passed; no spending implementation yet | Zero-spend default, budget boundaries and balance postconditions |
| Mail / daily rewards | Design | Claimed/empty mailbox and mission reward evidence |
| GitHub update / rate-limit resume | Real metadata request: no Release; cache/backoff restart tests passed. Downloader/installer pending | Cached state + retry deadline + checked staged install/rollback |
| Windows package | Not built | Clean portable build + installed version/config preservation |
| FGO error option and Release | Error option built/installed, config preserved; actual GUI exit + public Release pending | Option persistence/error action; full release gate + published asset |

## 2026-10-01 evidence

- 39 tests passed (policies, profile/ordered run persistence, Windows identity,
  team positions, EN/JP strings, GitHub deadlines and error/cache behavior;
  includes a real Windows two-process controller-lock exclusion test).
- Actual Maa 5.12.2 parser/OCR/Pipeline: three navigation replay cases and six team
  library cases passed. The #2 title change and resource dialog are derived fixtures.
  Already selected, missing slot, stuck click, paid dialog and unknown behavior are
  verified offline. User frame #2 is the Sinners library, not dungeon deployment.
- Live read-only Windows process identity: game integrity RID 12288; controller
  RID 8192. Earlier Seize calls did not change the page. All task entries now check
  identity/privileges before input. No new live click attempted after this finding.
- `build/native-replay-verification.json`, `build/team-replay-verification.json`,
  `build/windows-preflight.json` are local evidence, excluded from release.
- FGO prepublish audit returned ready with a missing-project-license warning;
  this is a privacy/source-tree audit, not full-suite or release validation.
- FGO's full current Python suite subsequently passed 710 tests after stale
  controller-scenario timing/retry assertions were corrected. Production behavior
  unchanged. Error options, license and release package/publishing are still pending.

## Runtime bounds refresh

- 43 tests pass, including finite pending setup/stop jobs, timeout cancellation,
  interrupted sessions and the distinction between task status and dungeon clear.
- CLI setup/load time now consumes the same monotonic session budget; wall-clock
  changes cannot extend it. If a stop does not complete, `stop_confirmed` remains
  false and the controller lease stays held until the process exits.
- Game PID40196 is still HIGH integrity RID12288; the inspected Python controller
  is MEDIUM RID8192. This is a read-only refresh, not a new live attempt.

## Floor-gift recognition refresh

- 48 tests pass. Imported 332 public cropped gift icons from pinned LALC with
  per-file hashes/source paths and keyword groups. Only local reward labels,
  ownership strips and gift icons are considered; covers/identities are not.
- The production recognizer supports `FLOOR_GIFTS` / `gift_mode: recommend` with
  a configured team. Owned is associated by column, block-list wins, uncertain
  titles/icons and overlapping candidates are refused. The default rank remains
  unowned preferred → unowned other → owned. Each ranking retains target/provenance
  and explicitly sets `selected=false`, `reward_received=false`.
- Actual Maa OCR/CustomRecognition/Click routing passed five derived public-icon
  cases: preferred, owned preferred, all blocked, paid zero-input and icon-only
  identity with the JP resource. This does not verify Japanese rendered text,
  selection quota, reward confirmation/receipt or a live floor transition.
  The helper is not yet wired into the full dungeon loop.
- Three navigation and six team-library Maa replay regressions passed. Private
  local result: `build/gift-replay-verification.json`.
- Original FGO installation is now clean 36e2f79, with nine configuration files
  preserved and a retained rollback directory. Packaged Agent replay passed;
  GUI error-option/exit and public Release remain unverified/unpublished.
