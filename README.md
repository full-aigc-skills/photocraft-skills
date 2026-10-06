# PhotoCraft Skills

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
