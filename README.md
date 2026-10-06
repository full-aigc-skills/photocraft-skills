# PhotoCraft Skills

Independent source metadata: `0.1.0-dev.14`. This source includes public-workflow Session reply validation; fixed plugin/Art distribution and installed-copy acceptance are tracked separately.
Fixed-release protocol recovery acceptance passed: 288 cases across 48 standalone source skills, 24 cases in actual installed copies, four healthy revision cases, and 58 unchanged installed skill identities. See [fixed evidence](docs/evidence/codex-protocol-fault-first-use-20261007.json). Exhaustive command/GUI acceptance and the Art domain-bundle upgrade remain open.

Protocol fault repair candidate: all 12 independently copied skills pass separate empty public-runtime installation and six faulty replies after real native save (72 cases; zero skips). Requests are not replayed; unknown receipts, saved-project reopening and delivery/skill preservation are checked. [Evidence](docs/evidence/protocol-fault-first-use-20261007.json). Fixed installed release and Art bundle upgrade remain separate gates.

Fixed plugin 0.1.0-dev.13 / skills 0.1.0-dev.12 installed revision acceptance passes: isolated Codex discovers all 58 skills without loading errors; this installed domain skill completes the documented cold creation/revision plans, saved-project reopening and non-target preservation. All58 installed digests remain unchanged; current fixed release CI passes. [Fixed revision evidence](docs/evidence/codex-complete-command-revision-first-use-20261007.json). Full command/GUI/model acceptance remains open.

All 12 domain skills pass the paired revision plans when copied alone and installed from separate empty public runtimes (62.759 seconds; zero skips). [Revision evidence](docs/evidence/complete-command-revision-first-use-20261007.json). Fixed installation of the updated snapshot remains a separate gate.

The complete-command entry now includes paired executable creation/revision recipes, explicit selection prerequisites after reopening, and native persisted-state/non-target checks. Each standalone skill includes both JSON plans. [Usage](skills/photocraft-use/references/command-usage.md#7-可执行局部返工--executable-targeted-revision). Full per-command and GUI acceptance remains open.

Previous fixed Codex snapshot first use passes: five plugins / 58 skills discovered, independent public cold runtime installs for all 58 installed skills, four complete-command native samples, Art HD revision/recovery/package checks, unchanged installed digests and fixed release CI. [Evidence](docs/evidence/codex-complete-command-first-use-20261007.json). This remains bounded native acceptance; generic Skills CLI installation and exhaustive command/GUI acceptance are open.

## Complete native command entry

All 12 standalone skills now pass separate empty-runtime installation from locked public CLI archives, followed by native creation, save/reopen, domain assertions and rendered image checks (74.187 seconds; zero skips). [Cold-first-use evidence](docs/evidence/complete-commands-cold-first-use-20261007.json). This verifies this complete-command sample in every skill; exhaustive command/GUI and actual host installation remain separate.

Published development snapshot: skills dev.11 / plugin dev.12; bounded fixed-host first use passed.

All 748 commands now have verbatim parameters, skill routing, and same-session invocation through `commands.py list / describe / check / run`. Live enabled state is checked; the existing 32-operation delivery workflow remains bounded. GUI commands require explicit bridge mode. Complete registry coverage does not establish full command acceptance.

[Architecture and usage](docs/PhotoCraft-Complete-Commands-Architecture.md) · [Complete reference](skills/photocraft-use/references/command-reference.md) · [Runnable example](skills/photocraft-use/examples/commands-advanced.json)

Independent PhotoCraft skills. Implementation is in progress; this repository is not a completed plugin release.

The `photocraft-use` skill contains a self-contained Python 3.11+ bootstrap installer for the pinned official macOS arm64 CLI. It verifies the archive and executable, retains license files, atomically installs a new version, and reuses an intact installation without downloading again.

Run tests with `python3 -m unittest discover -s tests -v`. Full creative workflow and host acceptance remain pending.

Normative requirements and implementation tracking: [PhotoCraft plugin OpenSpec](https://github.com/full-aigc-plugins/photocraft-plugin/tree/main/openspec/changes/establish-v1-plugin).

[简体中文](README.zh-CN.md)

The independent skill now includes a scoped native workflow helper for raster assets, editable text, masks, native/PSD exports and immutable size variants. Live tests verify protected pixels and exact PSD roundtrip pixels for the synthetic fixture. Full plugin Harness and host acceptance remain pending.

Development version `0.1.0-dev.1` fixes concurrent first-use/reuse install-lock contention: wait up to 120 seconds, then verify and reuse; timeout preserves installations and never replays editing tasks.

Development version dev.2 includes hash-bound exchange-loss.json with every native delivery. Reports distinguish format losses, observed structure and unknown font/effect fidelity; exported derivatives never replace the retained native project.

## CLI and task skill suite

[PhotoCraft Skill Suite Architecture](docs/PhotoCraft-Skill-Suite-Architecture.md)

| Skill | Purpose |
| :--- | :--- |
| `photocraft-use` | use |
| `photocraft-cli` | cli |
| `photocraft-cli-setup` | cli setup |
| `photocraft-cli-project` | cli project |
| `photocraft-cli-layers` | cli layers |
| `photocraft-cli-selection` | cli selection |
| `photocraft-cli-masks` | cli masks |
| `photocraft-cli-adjustments` | cli adjustments |
| `photocraft-cli-retouch` | cli retouch |
| `photocraft-cli-text` | cli text |
| `photocraft-cli-resize` | cli resize |
| `photocraft-cli-export` | cli export |

`npx skills add full-aigc-skills/photocraft-skills --skill <skill-name>`

Commands use `SKILL_DIR`, the absolute directory of the `SKILL.md` actually loaded by the host. User/project `.agents/skills` and plugin-internal/cache layouts are supported; the CLI runtime is installed separately in the user data directory. Each skill was copied alone into all three layouts, including paths with spaces, and its documented script entry points ran `--help`. [Path verification](docs/evidence/installed-skill-paths.json). Existing host caches need an explicit update to receive the corrected documentation.

Version dev.5 adds explicit selection/mask prerequisites for local adjustments and target-layer selection plus distinct brush/clone/healing units. Nine focused task skills each cold-installed only their own copied skill and completed native edits with structural/pixel checks. The full regression passed 36 tests with no skips. [Evidence](docs/evidence/task-skill-first-use.json). This does not prove all 748 commands, complex retouch quality or GUI/model dispatch.

Frozen plugin dev.6 / skills dev.5 pass actual installed single-text-skill Chinese poster cold start and headline revision (1 test, 5.927 seconds). Source and protected pixels remain unchanged, PSD preserves Type text and decodes identically to PNG, unknown layers and missing fonts fail. Human acceptance remains NOT_RUN. [Architecture](docs/PhotoCraft-Chinese-Text-Architecture.md), [evidence](docs/evidence/chinese-text-first-use.json).

Source candidate dev.6 adds explicit protectedRegions for source revisions. Real native RED reproduced unauthorized protected changes being published; the fix rejects them before publication while preserving the source. All 44 tests pass with no skips; a standalone system-Python online single-skill proof passes. Fixed-plugin acceptance remains pending. [Architecture](docs/PhotoCraft-Protected-Region-Architecture.md), [proof](docs/evidence/protected-regions-first-use.json).

Fixed PhotoCraft plugin dev.7 / skills dev.6 and ArtCraft plugin dev.30 / skills dev.26 pass installed native protection/handoff proof; all 58 installed skill hashes remain unchanged. Only the scoped protection tasks are complete; overall implementation and creative acceptance remain incomplete. [Proof](docs/evidence/codex-release30-protected-native-20261006.json).

Source candidate: the PhotoCraft public workflow now supports brush stroke, clone stamp and healing brush with declared protected regions. A fresh single-skill online-native test passed; fixed release, plugin vendoring and installed-plugin revalidation are pending. See [bounded source evidence](docs/evidence/retouch-workflow-first-use.json).

Fixed PhotoCraft plugin dev.8 / skills dev.7 and ArtCraft plugin dev.31 / skills dev.27 pass installed native retouch/handoff testing (13.260s and 23.264s). All 58 installed skill hashes remain unchanged. Only scoped retouch tasks are complete; the full goal remains incomplete. [Proof](docs/evidence/codex-release31-retouch-native-20261006.json).

尺寸变体增量 / Layout variants: source-bound crop, padding and resampling records, editable role identities, and final-canvas safe-area gates. See `docs/PhotoCraft-Layout-Variant-Architecture.md` and `docs/PhotoCraft-Layout-Variant-Architecture.zh_CN.md`. Native runtime remains 0.2.0; skills development version is 0.1.0-dev.8.

Installed plugin dev.9 / skill source dev.8 supplementary first-use acceptance verifies a layered masked poster, text revision and cover, with independent Pillow decoding of each opaque PSD merged image against all PNG RGB pixels. This is separate from native layer inspection and does not claim live editing in Photoshop. [Acceptance](docs/PhotoCraft-Independent-PSD-Acceptance.md).

Image-only workflow font preconditions: [architecture](docs/PhotoCraft-Font-Preconditions-Architecture.md). Source dev.9 candidate passes public cold native image-only create/revision and independent PNG/PSD checks; actual fixed-plugin revalidation remains pending.

Fixed plugin dev.10 / source dev.9 passes actual Codex 0.153.4 installation and copied-alone image-only cold native acceptance (5.601s). All 58 discovered installed skill hashes remain unchanged. ArtCraft upgraded fixed mixed acceptance remains separate. [Proof](docs/evidence/codex-photo10-fontless-first-use-20261006.json).

Fixed installed matrix Film9 / Effect8 / Photo10 / Vector11 / Art61 passes registered PNG/JPEG Vector→Photo replacement/reuse (1 test), four-domain native first use/recovery/package (3 tests), and all 22 updated Photo/Art single-skill cold CLI starts (190.051s). All 58 installed skill hashes are preserved. SVG mixed input, dynamic transparent sequence and full creative acceptance remain open. [Proof](docs/evidence/codex-release61-vector-photo-first-use-20261006.json).

Source `0.1.0-dev.10` pins maintained CLI `0.2.0-craft.1`. Registered smart placement, replacement and relink collection preserve editable embedded content, transform and masks. Public copied-alone source cold first use passes; immutable installed plugin and Art mixed acceptance remain pending. [Evidence](docs/evidence/smart-public-source-first-use-20261006.json).

Fixed Photo plugin dev.11 / source dev.10 / maintained CLI 0.2.0-craft.1 now passes installed copied-alone smart placement/replacement/relink collection and moved revision (4.633s), PSD independent decoding and fontless regressions (two passes), twelve independent cold starts (51.647s), all 58 installed digests, public archives and four exact-tag CI runs. The default maintained runtime coexists with unchanged official 0.2.0. [Version-bound evidence](docs/evidence/codex-photocraft11-smart-first-use-20261006.json). Art mixed upgrade is verified below; full V1 remains open.

Fixed smart mixed acceptance (2026-10-06): Art plugin dev.70 / source dev.47 / runtime dev.68 and Photo plugin dev.11 / source dev.10 / maintained CLI 0.2.0-craft.1 pass one installed native test (64.957s), ten independent Art cold starts, all 58 installed digest checks, five fixed bundle rebuilds and four exact-commit CI runs. Logo replacement preserves the poster smart transform, mask and non-target layers; affected logo/poster/intro/film rebuild, independent work is reused, twelve film frames are decoded independently, corrupt-frame recovery and moved five-child package verification pass. [Evidence](docs/evidence/codex-artcraft70-smart-mixed-first-use-20261006.json). Full V1, generic Skills CLI, GUI/model dispatch, persistent external links and external PSD fidelity remain open.

Public-workflow reply validation is synchronized in the domain source candidates and has bounded native/Art protocol evidence. Fixed updated domain and Art distributions are still pending. [Candidate architecture](docs/PhotoCraft-Complete-Commands-Architecture.md) · [Evidence](docs/evidence/public-workflow-session-candidate-20261007.json).
