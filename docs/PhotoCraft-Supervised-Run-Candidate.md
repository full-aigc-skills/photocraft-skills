# Supervised native run candidate

This candidate advances PC-TX-005 / task 9.6 in `establish-v1-plugin`. Public skills dev.41, plugin dev.47 and runtime `0.2.0-craft.1` remain unchanged. Public `cli.py` does not yet dispatch through the candidate supervisor.

The original CLI executes all run commands inside one process. Inspecting stdout afterward cannot reliably stop its next edit. Routing through current MCP would change trusted-local paths, capability permissions and file-bearing commands. The maintained patch therefore adds an explicit `--supervised` mode to the original `Headless::trusted_local` session, preserving ordinary run behavior.

After creation, opening, each command and final saving, native code emits a `photocraft-supervised-run/v1` event with a sequence, tool, exact request arguments, result or error, and visibility flag. A successful event requires the exact ASCII line `continue <sequence>\n` before native code continues. EOF, rejection, stale sequences, extra data and oversized acknowledgments stop execution. A reported operation has already executed; lost confirmation does not prove that it was unexecuted and never rolls back saved files. Native errors stop immediately.

The candidate `cli_supervisor.py` derives the expected event sequence from preflighted argv, rejects unsafe JSON and mismatched identities, and reuses workflow reply validation. Only validated results produce legacy `{"command":...,"result":...}` output and acknowledgments. Exceptions retain validated receipts and the last attempt without retrying. Callers must verify the runtime lock and persist recovery records when integrating this internal candidate interface.

The combined patch includes the previous scoped smart-content patch and pins upstream `f114f621799a96dc9f28ffb8faa01da680b64947`. Research remains unchanged. Candidate runtime version is `0.2.0-craft.2`, darwin-arm64 only.

```bash
python3 -I -B scripts/build_smart_runtime.py \
  --repository ../../research/photocraft \
  --output /absolute/new-candidate-directory \
  --manifest supervised-run-patch.json --version 0.2.0-craft.2
CRAFT_SUPERVISED_BINARY=/absolute/candidate/photocraft-cli \
  python3 -I -B -m unittest discover -s runtime/tests -p 'test_*.py' -v
```

Builds default to offline; explicit `--online` permits Cargo dependency downloads. Automation and CLI Rust tests run before packaging. The build receipt binds upstream, patch, Cargo.lock and artifact hashes.

Ten focused tests cover acknowledgments and native failures, healthy creation and save-as revision, legacy output, malformed actual replies, stopping subsequent edits, and retaining/reopening a saved project after a malformed save reply. Two additional actual `file.saveACopy` PSD cases inject duplicate-key and semantic errors after writing: later edits/final saves are zero and both the original `.pcraft` and saved PSD remain intact. This is limited content evidence, not external-editor PSD fidelity acceptance.

Public CLI integration and durable recovery receipts, batch/droplet internals, MCP/serve streaming, fixed-release installation and the complete entry/command matrices remain open. Public locks, tags, managed plugin snapshots and marketplace eligibility are unchanged; task 9.6 remains unchecked.
