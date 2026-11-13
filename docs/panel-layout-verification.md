# Panel layout verification

Verified on 2026-11-13 against the local changes based on 0f10351.

## Behavior

- Explore, Changes and Graph share the existing sidebar registry, including extension views.
- All three built-in sidebar lists retain the original normal/small UI font hierarchy and regular weight; Interface font size controls both tiers globally.
- Explore starts expanded; both Git blocks start collapsed. All three disclosures work independently.
- Changes keeps branch, commit input, changes and repository actions together. Narrow widths use an icon toolbar.
- Graph uses the original global UI font tiers: normal UI face for subjects and filenames, small UI face for author/path/status metadata. Explore filenames and Changes body/actions also use the original normal UI face; section headings retain the existing small face. All tiers are derived from Interface font size ([ui] font_size). Click or Enter/Space toggles inline changed files; Right expands and Left collapses. Multiple nodes retain independent disclosures, including after log refresh. File rows show a file icon, basename, muted directory and right-aligned status; subjects and paths have hover tooltips. File clicks open historical diffs.
- Graph geometry uses a 10 px lane pitch, 8 px commit dots and 2 px strokes at 1x scale. Inline file continuations share the same lane positions and stroke; row height stays 24 px. Commit text follows each row's occupied lanes with a fixed gap instead of reserving the widest graph column for every row. Inline file labels use the same local indentation. Merge-graph screenshots are saved as timeline-local-labels.png and timeline-local-labels-expanded.png.
- Ctrl+Shift+G toggles Changes; Ctrl+B toggles the whole sidebar. The title bar Git button is removed.
- Collapsing Changes or hiding the sidebar releases commit-message focus. Graph focus does not edit the document.
- The terminal docks at Bottom or Right using its header button, Settings, or palette commands.
- Dock movement preserves shell sessions and the split tree. Position, bottom height and right width are saved.

## Build checks

- Linux release build: passed; executable at build/rhun.
- Windows x64 cross-build: passed; executable at build/windows/rhun.exe.
- macOS ARM64: translation and Apple-target assembly passed for the affected shared assembly units, including a final recheck of the six sidebar-related units. Native macOS linking and runtime behavior were not verified locally.

## Automated checks

- tests/panel-layout.py: 25 tests passed, including independent disclosures, default states, compact action tooltips, commit subject tooltips, the removed title bar button, commit creation, timeline navigation, row-local label indentation beside merge branches, inline expand/collapse, simultaneous disclosures, async navigation, pending request cancellation across repository switches, empty commits, long paths, scrolling past 48 files, light theme at 2x scale, focus protection, dock resizing and persistence, live shell and split preservation, narrow windows, large scale, Settings search and command palette capacity.
- tests/markdown-preview.py: 15 tests passed.
- tests/terminal-splits.py, tests/terminal-panel.py and tests/side-diff.py: passed.
- tests/tooltips.py: all 9 tests passed, including narrow Source Control layouts at larger UI fonts.
- tests/settings-search.py: 17 tests passed.
- Settings inventory and every choice segment: passed, including terminal.position.
- Source Control menus, commit wrapping, reset operations, untracked files, repository switching and reopened historical diff coverage: passed.
- tests/ext-views-tree.py: all 40 tests passed; existing extension sidebar views retain their behavior.
- Commit message caret blink: passed.
- Git, Source Control, initial commit and untracked folder UI scripts: passed twice with matching output; their four expected snapshots were updated for the new layout.
- git diff --check: passed.

The palette shortcut cache is now sized from the actual command table. The new commands exposed the old fixed 256-entry limit; the palette and Markdown regression tests cover the repair.

## Visual artifacts

Refresh local PNGs with:

```sh
RHUN_TEST_ARTIFACT_DIR=build/verification/panels python3 tests/panel-layout.py
```

The resulting three-block sidebar, default collapsed states, expanded timeline, commit details, large-font narrow sidebar, right terminal and bottom terminal screenshots were reviewed. Tests use isolated temporary repositories and configuration directories. No system configuration was changed and no running user window was restarted.

After restoring the original font tiers, Linux and Windows release builds passed, along with all 25 panel layout tests and 9 tooltip tests. A visual comparison at Interface font size 13 and 16 confirmed that all three sections follow the global setting; see sidebar-global-font-comparison.png in the artifact directory.

## Recent workspaces

The project menu combines recent folder sessions and named workspace files in one newest-first list (up to 9 entries). Workspaces carry a (Workspace) suffix, persist independently of files.restore_session, and reopen the definition with all folders. Current and missing entries are omitted. History is stored in per-user rhun state without changing system settings.

- tests/recent-workspaces.py: 10 tests passed, covering restart, Save As, same-primary workspaces, Unicode/spaces/percent paths, deduplication, ordering, deleted/current/invalid files, the item limit and the (WORKSPACE) title suffix for single/multiple folders and Save As.
- Original recent-folder UI snapshot: passed unchanged.
- Workspace-file and same-project reopening regression tests: passed.
