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
