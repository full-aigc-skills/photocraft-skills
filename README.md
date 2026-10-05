# PhotoCraft Skills

Independent PhotoCraft skills. Implementation is in progress; this repository is not a completed plugin release.

The `photocraft-use` skill contains a self-contained Python 3.11+ bootstrap installer for the pinned official macOS arm64 CLI. It verifies the archive and executable, retains license files, atomically installs a new version, and reuses an intact installation without downloading again.

Run tests with `python3 -m unittest discover -s tests -v`. Full creative workflow and host acceptance remain pending.

Normative requirements and implementation tracking: [PhotoCraft plugin OpenSpec](https://github.com/full-aigc-plugins/photocraft-plugin/tree/main/openspec/changes/establish-v1-plugin).

[简体中文](README.zh-CN.md)

The independent skill now includes a scoped native workflow helper for raster assets, editable text, masks, native/PSD exports and immutable size variants. Live tests verify protected pixels and exact PSD roundtrip pixels for the synthetic fixture. Full plugin Harness and host acceptance remain pending.

Development version `0.1.0-dev.1` fixes concurrent first-use/reuse install-lock contention: wait up to 120 seconds, then verify and reuse; timeout preserves installations and never replays editing tasks.

Development version dev.2 includes hash-bound exchange-loss.json with every native delivery. Reports distinguish format losses, observed structure and unknown font/effect fidelity; exported derivatives never replace the retained native project.
