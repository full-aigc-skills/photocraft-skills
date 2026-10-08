# PhotoCraft supervised conversion candidate

Source dev.42 includes the independent run/batch/convert supervisor and maintained craft.4 patch. Public cli.py still uses locked craft.1. Publication does not activate the candidate runtime or establish fixed-installation or complete PC-TX-005 acceptance.

The supervisor validates the entire plan, then queries read-only --supervision-info. Missing protocol, requested subcommand or acknowledgment contract returns supervision_unavailable / not_executed before sending an edit. Capability metadata does not prove binary provenance: callers must still verify runtime identity and checksum.

Conversion preserves native files::open/save, formats and quality semantics. A strictly validated open receipt requires acknowledgment 1 before saving; save requires acknowledgment 2 before success. Duplicate keys, nonfinite values, wrong paths and extra frames stop acknowledgments without replay. If saving already happened, the original output and unknown receipt are retained.

Build with scripts/build_smart_runtime.py --manifest supervised-convert-patch.json --version 0.2.0-craft.4, then set CRAFT_SUPERVISED_BINARY for runtime/tests. Default builds are offline and public locks remain unchanged.

Thirty focused tests and 58 maintained Rust tests pass, including refusal of the old public runtime before editing, four conversion formats and six actual post-save faults. Complete source regression and release evidence are tracked in the plugin repository. Droplet, streaming, public entry integration, persistent recovery, fixed installation and the complete command matrix remain open; task9.6 stays unchecked.
