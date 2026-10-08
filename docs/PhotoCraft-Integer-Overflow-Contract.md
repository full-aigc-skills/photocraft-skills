# PhotoCraft integer overflow contract

Source dev.43 validates numeric token text against the native finite f64 range before constructing Python values. This catches positive/negative integer overflow at every parsed depth and avoids Python's long-integer conversion limit hiding the precise field path. Finite large integers keep their original integer type; no 64-bit limit is introduced.

Three focused methods cover parser/MCP/tool-reply semantics, finite legacy values, and52 public-entry cases across13 independently copied skills (positive/negative401-digit and5000-digit literals). Invalid inputs return nonfinite_json_value, validation / not_executed, retryable=false and correct_plan with the exact fieldPath. Installer/session counters remain zero; original bytes, runtime and output directories remain unchanged.

The original RED records installation attempts after accepted overflow. A second RED records lost field paths on5000-digit literals. GREEN and full source regression are separate from immutable release and installed-copy acceptance, which are recorded in the plugin repository. This bounded fix does not close task9.6 or complete V1.
