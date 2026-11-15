# Main release preparation verification

## 0.19.6 CI regression correction (2026-11-16)

The 0.19.5 Windows release gate failed keys, config-strings and agents/metadata.
The key registry test must respect terminal-only paste and selection-only copy
conditions. The string ownership test must use a valid shortcut instead of
"value" for terminal hotkeys. The Agents Settings test used row offsets which
included hidden shortcut rows; it now filters by agents.codex before clicking.
The Agents failure also reproduced on Linux. These corrections retain the
runtime validation and focus guards, and do not disable any release checks.

All three corrected checks passed with native Windows executables in an isolated
temporary directory. The complete Linux Agents suite passed 81 tests with seven
platform skips; all 15 terminal key tests passed. The full Linux/Windows CI suites
must pass before the new release is published. The failed v0.19.5 tag is retained.

## 0.19.5 release preparation (2026-11-16)

This release includes the app-private Linux Pinyin runtime and installer option,
shared keyboard-shortcut editing, terminal copy/paste bindings, host input-mode
observation, and the WSLg cursor and bounded maximize-monitor fixes. Windows
continues to use its native system input method. No host configuration is changed.

The user accepted the latest dual-monitor build. Disposable-window regressions
verified actual cross-screen dragging and maximization, native cursor bitmaps,
Chinese/English document commits, unsaved-peer cursor recovery, toolbar controls,
and helper shutdown. These host-specific checks are recorded in ime-verification.md.
Linux cursor and IME ownership wire tests are part of tests/run.sh. GitHub Actions
remains responsible for the full native Linux/Windows release suites and publishing
the packages only when both platform jobs succeed.

Local preflight passed the Linux test build, Windows x64 release cross-build
and ZIP packaging, both Linux wire-test output fixtures, 14 Chinese-toggle
cases, 14 chord cases, 15 terminal-key cases, 14 Settings UI cases, 17 Settings
search cases, and the installed-runtime tests (4 cases). Download checks passed
8 cases with 4 BusyBox-dependent skips. Python/shell syntax, workflow YAML and
git diff whitespace checks passed. This is focused verification, not a claim
that the full native CI suites have already passed.

The older preparation notes below describe the 0.19.2 merge and do not describe
the bundled-input packaging used by 0.19.5.

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

## macOS build compatibility follow-up

The extension workflow for 31b17cc failed in its macOS Build step. Local
reproduction found shared assembly that tools/arm64.py could not translate:
LOOP, REP MOVSQ, and label-length immediates. These now use supported equivalent
instructions and explicit start/end label differences. No CI job was disabled.

- All 355 shared application, test and generated-asset translation units passed
  tools/arm64.py and Clang assembly for arm64-apple-macos12.
- All five native src/mac assembly files also passed Apple-target assembly.
- Linux test and release builds and the Windows x64 release cross-build passed.
- Terminal splits, editable side diff and the alignment/ownership unit test passed.
- All 15 Markdown preview tests passed, including a new regression for editing
  an open preview beyond the 1 MiB limit.

These are cross-compilation and focused local checks. macOS framework linking
and native extension execution still require a successful GitHub Actions run.

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
