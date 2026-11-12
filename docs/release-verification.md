# Main release preparation verification

Date: 2026-11-12

Merged origin/main (upstream 0.19.2) with the personal customizations. Native XIM /
Wayland text-input-v3 state is separate from the verified private Fcitx engine.
The private engine takes priority while ready; text-input-v1 remains available
on compositors without v3. Windows uses the native system input method.

## Passed locally

- Linux release build; Windows x64 cross-build and ZIP packaging with LLVM 18.
- Private Chinese input: 14 tests, protocol/candidate paging, commit, cancellation,
  client crash and engine loss restore normal keyboard input.
- Workspace folders: 31 tests. Settings search: 17 tests.
- Side diff and terminal splits; Markdown preview: 14 tests in the full run.
- Terminal tabs: all 5 tests with deterministic shell+folder labels.
- Live reload settings switch; legacy unified diff reopen; Shift-wheel: 3 tests;
  scrollbar flash after adjusting for the configured editor scroll sensitivity.
- Windows archive contents; identical documented Windows install commands;
  release YAML parsing, shell syntax, git diff whitespace checks.
- Linux archive extraction and the included portable personal launcher.

## Incomplete checks

The full tests/run.sh run did not pass and was stopped after collecting failures.
Do not describe it as a green release gate. Failures included:

- Git trust no-project expectations: also fail against the prior personal binary;
  this host has ancestor .git directories outside the isolated test repositories.
- Windows installer fixture via WSL interop: host script execution policy rejects
  temporary scripts. No system policy or input settings were changed.
- X11 auth: /tmp/.X11-unix is read-only on this WSL host.
- OpenCode 2 oversized snapshots and optional real Bun reader failures; these
  sources were unchanged by the merge and need a clean CI reproduction.
- The all-commands palette test exceeded its local 30 second limit.
- Some old UI tests used pre-customization label widths, settings positions or
  scroll distances. Those fixtures were updated; their focused reruns passed.

Windows native tests and native Linux desktop launch/input tests must run in
GitHub Actions. No new version tag or GitHub Release was created by preparation.
The normal release entry point remains tools/release.sh VERSION on main after
CI is green. The fork publishes unsigned Windows and Linux packages; macOS
signing and upstream winget submission are skipped. Optional private Fcitx
packages are downloaded by the included setup script, not bundled or installed
system-wide. Installer/updater/remote-agent release URLs point to JerryRun/rhun.
