# Version-bound release records

## 0.1.0-dev.60

Converge duplicated execution payloads into one built-in **photocraft-harness** skill: the 13 domain skills drop their per-skill scripts/ copies (12 documented entry points plus execution-contract JSON now exist once) and route execution by skill name via `HARNESS_DIR`; no unreferenced scripts were found, so the shared payload is preserved byte-for-byte. Suite registration, sync, command-coverage and release-identity generators and the tests are updated for the new layout. Full regression passes 373 tests (85 explicit opt-in skips). Target-platform and host acceptance remain open.

