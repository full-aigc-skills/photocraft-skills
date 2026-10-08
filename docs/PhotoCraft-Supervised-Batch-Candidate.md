# Supervised native batch candidate

This candidate advances PC-TX-005 / task 9.6. Maintained runtime `0.2.0-craft.3` adds batch boundaries to the previous run candidate. Public skills dev.41, plugin dev.47, runtime craft.1, `cli.py` and managed snapshots are unchanged.

Before creating output directories, native supervision emits `batch_plan`, binding sorted input/target files and normalized actions. The supervisor independently derives this plan from the pinned f114f621 codec rules and rejects omissions, changed actions and mismatches. AVIF is not readable in that build and is excluded, along with directories and unsupported extensions.

Each file retains a fresh trusted-local native session. Opening, every action and saving require individual acknowledgments. Only a validated save with its expected returned path produces the legacy `ok    input -> target` line. The final bound `batch_complete` counts produce the legacy summary. Extension selection, explicit format/quality, valid path spelling and action metadata retain native semantics; MCP permission rules are not substituted.

Any malformed, ambiguous or explicit failure stops the supervised batch, retaining prior files and receipts without replay. Ordinary batch without the supervision flag retains per-file failure continuation and its original output. Real-native comparative tests cover both modes. Already-buffered extra reply frames are now rejected before accepting or acknowledging a preceding result, and save replies naming another path are rejected.

```bash
python3 -I -B scripts/build_smart_runtime.py \
  --repository ../../research/photocraft \
  --output /absolute/new-candidate-directory \
  --manifest supervised-batch-patch.json --version 0.2.0-craft.3
CRAFT_SUPERVISED_BINARY=/absolute/candidate/photocraft-cli \
  python3 -I -B -m unittest discover -s runtime/tests -p 'test_*.py' -v
```

The combined patch preserves scoped smart content and previous run supervision. Research is read-only. Only darwin-arm64 was built and tested. All 58 Rust build tests and 20 focused run/batch tests pass. The ten batch methods include preflight and codec selection, sorted fresh sessions, failure/EOF stopping, legacy output and quality, empty input and valid path aliases, incomplete-plan rejection, and six malformed actual post-save replies. Each save fault checks reopening the retained file, unchanged original hashes, no later file/edit calls and no final summary.

An initial alias fixture used an absent output directory ending in `/.`; pinned Rust rejects that combination even without supervision. The fixture now uses an existing directory and first verifies ordinary native batch before comparing supervised output. Neither implementation nor acceptance requirements were relaxed.

This remains an internal candidate API. Callers must bind the supported binary and provenance before dispatch: older CLIs ignore unknown supervision flags and may edit before an attempted compatibility check. Public integration needs capability/source gating, fixed locks and durable recovery receipts. Fixed installation, droplet internals, MCP/serve streaming and complete entry/command matrices remain open. Task 9.6 is not closed and public runtime locks are unchanged.
