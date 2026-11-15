# 项目内拼音输入验证记录


## Bounded cross-monitor maximize workaround (2026-11-16)

- The application helper records the actual native monitor before maximizing.
  If maximization unexpectedly changes monitors, it waits 200 ms and sends at
  most one native Windows monitor-move shortcut. RAIL and compositor position
  follow the normal window-manager path; no SetWindowPos or mouse relay returns.
- Scope is exactly two active monitors, the same foreground HWND, unchanged
  origin-monitor bounds, no held keys/buttons, and a one-second deadline. Recent
  typing defers correction; Windows-key input cancels it. Already-maximized
  windows are never moved back automatically. A brief visual hop remains possible.
  This is an application workaround, not a repair of WSLg's cached work area.
- Release-build verification passed four real secondary-to-primary drags followed
  by toolbar maximization, primary/secondary work-area bounds, intentional
  monitor-move preservation, and 12 actual text/arrow/text cursor-image checks
  across focus and hover switches. Tests use only disposable windows.
- Native Chinese-English-Chinese input after automatic correction committed
  the expected document contents. Four focus switches between two maximized
  windows also preserved cursor shapes and committed Chinese/English input.
  Closing a same-folder, same-file unsaved peer left the survivor's stationary
  cursor visible and its edits intact.
- Build/unit checks, Wayland cursor and IME ownership tests, 14 toggle cases,
  14 key-chord cases, and all 12 production Windows host-mode decoder cases
  passed. The release candidate is build/rhun; ~/.local/bin/rhun is unchanged.
- Native maximize bounds, toolbar/menu/editor clicks, restore/minimize/close,
  and helper shutdown passed on the release build. The test's PowerShell thread
  now uses per-monitor DPI awareness so physical render dimensions are compared
  with physical screen bounds, including on the scaled secondary display.
- An extra deliberate system-shortcut round trip exposed native bounds covering
  1080 pixels instead of the 1040-pixel work area. This separate already-maximized
  operation is outside the workaround's normal-to-maximized transition scope.
  The regression checks that the explicit move is respected, then uses an actual
  drag and fresh maximize to set up its work-area and cursor-image assertions.
- No host display, mouse, IME, registry or WSLg configuration was changed.

## Cross-monitor maximize: stale compositor work area (2026-11-16)

- This supersedes the tentative explanation that a normal cross-screen drag
  left the compositor on the wrong output. The scene dump after the real drag
  shows both the native HWND and compositor view on the primary output at
  (150,182). Normal dragging itself was synchronized.
- The installed Weston build is 04d436c7d9a0cd55fa64b6612c7fa678d6fcd077.
  Its exact rdprail-shell/shell.c was downloaded and byte-compared with the
  source used during diagnosis; they match. handle_output_move moves views but
  does not translate desktop_workarea. get_output_work_area returns that cached
  rectangle, and set_maximized_position uses its x/y directly.
- The session log on November 15 at 23:58:53 shows primary rdp-0 moving from
  (1920,0) to (0,0). Subsequent work-area notifications update only secondary
  rdp-9. The scene dump later shows primary output x=0 and client work-area x=0,
  but its cached Weston work-area x=1920. Maximizing the primary view consequently
  places it at (1920,0), on the secondary display. The missing translation and
  absent replacement primary notification explain the persistent stale origin.
- Independent control: a standard GTK 3.24 Wayland window, without any rhun
  code or helper, was dragged from secondary to primary and then maximized.
  It also moved to the secondary screen. Log: /tmp/rhun-gtk-monitor-control.log.
  The original rhun baseline likewise reproduces the same sequence in
  /tmp/rhun-drag-original.log. The X11 xmessage comparison did not complete its
  drag, so it establishes no X11 result.
- Windows-native applications do not use this WSLg work-area cache. These
  results establish an environment-specific WSLg failure affecting at least
  original rhun and standard GTK Wayland; they do not establish behavior for
  every Linux toolkit or every Windows/WSLg version.
- No production code, host configuration or installed binary was changed for
  this investigation. Only disposable control windows were manipulated.


## Primary/secondary cursor mismatch: native pointer restoration (2026-11-15)

This section supersedes the native mouse polling fix described below.

- The dual-monitor diagnostic reproduced a real cursor-image mismatch: the
  primary editor requested CUR_TEXT at (500,300), but GetCursorInfo/GetIconInfo
  returned the arrow bitmap. The correct HWND was foreground and under the
  pointer. The secondary editor changed images correctly. Earlier checks of
  application shape and non-null visibility did not detect this failure.
- The added SetWindowPos maximization workaround can move the Windows HWND
  without a corresponding compositor output/position change. Forwarding mouse
  coordinates repairs application state but cannot establish Wayland pointer
  focus or a valid pointer-enter serial for that surface. The problematic path
  was introduced by our commit 689ed5a, not the tested original baseline
  upstream/main at 3b7257be3ebf497894c654fa66c10d63f5c1c19b.
- Original and modified diagnostic builds with native positioning/pointer input
  changed actual text/arrow cursor bitmaps correctly on both monitors when moved
  through normal Windows window management. Evidence is preserved locally in
  /tmp/rhun-multimon-before.log, /tmp/rhun-multimon-original-systemmove.log and
  /tmp/rhun-native-pointer.log. These are diagnostic runs, not a full acceptance
  of the final production build.
- Removed forced HWND geometry, mouse hook/polling and mouse packets. Restored
  native Wayland motion, leave, button and wheel dispatch. Kept private Pinyin
  keyboard routing, host-mode observation and the separate hidden-cursor
  recovery for a surviving dirty window. No display, mouse or IME system
  configuration was changed; user windows and files were left untouched.
- Added tests/wsl-cursor.py --live --multi-monitor, which requires two distinct
  active monitors, maximized test windows matching their monitor work areas,
  and actual visible text/arrow/text cursor bitmap changes. It also checks
  repeated focus/hover switches. It never uses SetWindowPos for setup.
  Corrected wsl-window.py to maximize on its current output without forcing
  the native HWND out of compositor synchronization.
- Final-build validation so far: build.sh test, production Wayland cursor wire
  and IME ownership tests, 14 toggle cases, 14 chord cases, five async input
  cases, 15 private-engine editor/terminal cases, and 12 production Windows
  host-mode decoder cases passed. Python syntax and git diff --check passed.
- The Windows session later exposed only one active display. The new exact
  multi-monitor test explicitly skipped. Native window-area validation could
  not find its disposable HWND; a separate old/new startup comparison found
  neither version's window, despite both control sockets responding. Do not
  report native maximize/toolbar, final dual-monitor cursor, or live host-mode
  input acceptance as passed in that session. Do not change the host session
  or system display configuration to make these tests run.
- The corrected build is currently a local candidate; the installed executable
  remains unchanged pending native GUI acceptance. The prior records below
  refer to earlier binaries and do not establish acceptance of this candidate.


## Two maximized windows: pointer event ownership (2026-11-15)

- Attribution: the original baseline at upstream/main commit
  3b7257be3ebf497894c654fa66c10d63f5c1c19b correctly changes between text
  and arrow cursors in both maximized windows. The added WSL window workaround
  in commit 689ed5a suppresses Wayland pointer dispatch while native mouse
  forwarding owns a maximized window. This is our added path, not original code.
- Before the fix, the compositor's pointer coordinates reached (500,300), but
  the second editor's application coordinates stayed at (-10000,-10000) and
  its cursor stayed CUR_ARROW. Both HWNDs were maximized, the target was the
  foreground window, and WindowFromPoint identified that exact HWND.
- The low-level mouse hook is not a complete position observer: native
  SetCursorPos and foreground/stacking changes delivered compositor events
  without invoking the hook. A relative mouse event or click invoked it and
  restored the application coordinates. The hook was not dead; the earlier
  zero-callback counter alone did not establish a hook installation failure.
- The native helper now observes the actual pointer position and hit HWND
  during its existing event loop, emitting motion/leave only when needed.
  Hook and observation state are synchronized; button/wheel ordering and the
  primary-monitor coordinate workaround remain intact. No system settings,
  IME setters, injected pointer moves or extra input widgets are used by the fix.
- The new opt-in tests/wsl-cursor.py --live --multi-input fails against the
  preserved pre-fix binary with CUR_ARROW over the editor, and passes against
  the corrected build. It keeps both windows maximized, alternates focus four
  times, checks text/arrow/text shapes without injecting relative motion, and
  verifies actual committed Chinese-English-Chinese document contents in each.
- Chinese input attribution is still limited: both pre-fix diagnostic windows
  successfully composed and committed Chinese and followed host mode. No
  multi-window Chinese failure was established in these runs. The original
  baseline has no private Pinyin/host-state bridge, so pointer attribution
  cannot be used as proof of the reported input failure's cause.
- The same-file unsaved peer-close test also passed with the pointer stationary,
  as did native toolbar/menu/editor clicks, maximize/restore/minimize/close,
  cursor wire/IME ownership tests, and both 14-case toggle/chord test suites.
- The older fcitx-failure.py test was not validated by this run: it requires a
  separately supplied test bus and the default Conda Python lacks dbus.
- Production host-mode decoder checks also passed all 12 cases. The release
  build is installed at ~/.local/bin/rhun and its SHA-256 matches build/rhun
  (a1d6b9b3bccdd0e2fd821e70eea771797926732b22b974f4b3a3488d38b5dcd3).
  The prior installed executable is preserved at
  /tmp/rhun-before-multiwindow-pointer-fix. Running user windows were not closed.

## Stationary cursor after another dirty window closes (2026-11-15)

- Reproduced the reported sequence using two independent rhun processes in the
  same directory, opening the same file, with separate unsaved edits. Discarding
  one window while the pointer stays over the focused survivor produced Windows
  cursor flags=0 and a null cursor handle. The previous test moved the mouse
  before sampling and therefore masked this failure.
- WSLg's RAIL cursor-surface destruction path sends SYSPTR_NULL even when the
  closing surface is not the survivor's. Motion/focus-only cache invalidation
  does not repair a stationary pointer cleared after those events.
- The existing per-window helper now observes pointer visibility in its 100 ms
  observation pass. Only a null/hidden pointer directly over its own foreground
  HWND triggers a recovery packet, rate-limited to 250 ms. rhun invalidates its
  cursor cache and redraws the existing Wayland cursor surface. No global
  ShowCursor count, system cursor configuration, focus or pointer position is
  changed by recovery. Other applications and touch-suppressed cursors are
  excluded.
- tests/wsl-cursor.py --live --same-file-unsaved now checks before any motion
  after closing the dirty peer, confirms the survivor remains modified with its
  own text, and confirms the shared on-disk file was never saved. --windowed
  exercises the same sequence without maximizing. The original test remains
  available for editor/toolbar, typing and window-switch coverage.

- Final verification passed for both normal and maximized same-file unsaved
  close scenarios with the pointer stationary throughout peer exit. The
  survivor's cursor was visible with a non-null handle before any movement.
  The original cursor-switch test, production cursor/IME unit tests, shared
  module cross-platform checks and live host-mode/Settings tests also passed.
- The corrected binary is installed at ~/.local/bin/rhun and matches build/rhun.
  Existing user windows and configuration were not modified; restart loads it.

## WSLg pointer recovery (2026-11-15)

- The existing host window was observed with a null/hidden Windows cursor.
  Moving over the window restored it during inspection, so the original
  intermittent disappearance was not reproduced deterministically.
- The cursor image path committed its first buffer before assigning the cursor
  role. WSLg logged a conversion from a regular RAIL window to a cursor surface.
  Assign the role first and avoid cursor requests before a pointer-enter serial.
- Maximized windows use native mouse relay packets. Those packets now invalidate
  the cached shape on motion, so the next frame resubmits cursor image damage
  and commit even when its shape is unchanged. Keyboard focus also invalidates
  the cache. No Windows cursor settings or global ShowCursor count is changed.
- tests/linux/wayland_cursor_test.s checks the production wire request order,
  startup guard, unchanged-shape cache and explicit cursor recovery. It is wired
  into tests/run.sh with a checked expected-output fixture.
- tests/wsl-cursor.py --live passed in disposable windows: editor/toolbar,
  typing, maximize/restore, repeated window switching and another cursor-owning
  window closing. The actual pointer hit window and non-null visible cursor
  are checked at each step. Host Chinese/English typing and Settings following
  also passed; the original host mode is restored by that test.
- The local build and installed executable are updated. Existing windows are
  left running to preserve unsaved work; restart is needed to load the fix.

## WSLg host mode decoding correction (2026-11-15)

- Reproduced the failure on this host: Shift changed IMM open status between
  1 and 0, while conversion stayed at 1024 (SYMBOL) in both modes. Requiring
  NATIVE as well as open status therefore kept private input in English.
- For the WSLg SYMBOL-only proxy state, use the observed open status. Normal
  conversion values still use NATIVE; failed queries remain unknown. This only
  reads host state and changes rhun's private engine, without host IME setters
  or system configuration changes.
- Actual WSLg typing passed: host Chinese -> saved 你好, English -> saved nihao,
  Chinese -> saved 测试. The file was exactly "你好\nnihao\n测试\n".
  Host state was restored to open=1, conversion=1024 afterward.
- Live Settings disable/re-enable and persistence also passed. The test now
  searches Settings in English mode so its own query is not composed as Pinyin.
- tests/windows/host-ime-mode.ps1 exercises the production C# decoder directly,
  including SYMBOL-only, NATIVE, closed, non-Chinese and unknown states.
- Production decoder checks passed all 12 cases; the real private-engine host
  state protocol test also passed. Linux release build and diff checks passed.
- The additional maximize regression did not pass on this desktop: its window
  stayed on the secondary monitor while the test expected the primary one.
  The preserved pre-change binary reproduced the same coordinates and failure;
  no window positioning code was changed for this input fix.
- The verified build is installed at ~/.local/bin/rhun. Configuration is
  unchanged; already-running windows retain their loaded version until restart.
- This verification covers the current WSLg host; it does not establish that
  every third-party IME exposes its mode through the same IMM representation.

## Default host state following (2026-11-14)

- Scope: read Windows Chinese/English mode and select the matching mode on
  rhun's existing private Fcitx engine. This does not reuse Windows text
  composition, candidates or vocabulary.
- Read-only probe: tests/windows/host-ime-state.ps1 queries the window's IME
  open state and conversion/native bit. A Chinese keyboard profile alone is
  insufficient: the same 0x08040804 layout remained selected while Shift changed
  open=1 to open=0. Conversion remained 1025 in this desktop test, so both
  values must be considered. A failed query is unknown, not assumed English.
- Normal WSLg startup enables state following when private input is ready.
  Settings > Editor > Follow Windows input mode is enabled by default and
  changes live through the existing heartbeat. No environment flag is needed.
  Observation packets precede physical typing packets; the private engine gets
  an absolute SetCurrentIM request, not a toggle. Duplicate state requests
  preserve active Pinyin composition. No host IME setter, registry write,
  input-language profile change or system configuration change is used.
- Real WSLg validation passed twice, including a short delay after switching:
  host Chinese -> saved 你好; host English -> saved nihao; host Chinese -> saved
  测试. No rhun-specific input toggle was pressed. The final file was exactly
  "你好\nnihao\n测试\n". Host state before/after was open=1, conversion=1025;
  the test temporarily used the host's Shift gesture and restored both values.
  Diagnostics confirmed host_relay=1, 46 physical packets, host_mode=1 and
  private_mode=1.
- tests/fcitx-host-state.py also passed against the real private engine: both
  absolute modes, duplicate-state stability during composition and focus
  restoration. Existing 15 private-input, 14 Chinese-toggle, 14 key/chord and
  17 Settings-search cases passed. The real F2/Chinese-English/Settings relay
  release-reenable test still passed with host following left disabled.
- Linux release build and affected config/fcitx/wslwindow modules' Windows
  COFF assembly/macOS ARM translation passed after integration.
  The build is also installed at ~/.local/bin/rhun; the previous binary is
  backed up at /tmp/rhun-before-host-state-20261114. No release or commit/push
  is performed by this task.
- Compatibility boundary: verified only on the current host IME/profile and
  WSLg installation. Other IMEs may not report usable IMM state; an unknown
  observation releases host ownership so the independent toggle can work.
  While following known state, the private toggle shows an English explanation
  instead of allowing mode drift. Focus/reset reapplies the absolute mode.
- Settings live disable/re-enable and exit persistence passed. Turning following
  off immediately restored the independent toggle; enabling it reapplied the
  host state. Existing real F2/shortcut tests and primary-monitor maximize,
  native toolbar/menu/editor clicks, restore/minimize/close and helper shutdown
  tests passed. Settings UI 14, Settings search 17, key/chord 14, Chinese-toggle
  14 and terminal-key 15 tests passed.

## Physical shortcut recording and WSLg host relay (2026-11-14)

- Reproduced the F2 report in a real WSLg window: the old prompt expected typed
  key names and ignored physical combinations. It now records physical keys,
  modifier-only gestures and two-stroke chords. Enter saves, Escape cancels,
  Backspace clears; F2 inside the prompt switches to manual name entry.
- A separate display defect kept the overridden built-in shortcut visible after
  saving. The list now shows effective bindings, so subsequent edits target the
  current shortcut rather than the stale default.
- Suppressing Linux text-input alone did not resolve the reported Windows
  candidate window. The existing per-window WSLg helper now relays supported
  physical keys before Windows IME processing when private input is ready and
  this exact HWND has foreground focus. It forwards scan codes through the
  existing pipe, never clipboard contents or text files. Wayland translates them
  with the existing keymap and avoids duplicate delivery. Windows desktop
  shortcuts and unsupported scan codes keep their native paths.
- No registry, input-language profile, IME open/conversion state, installed
  service or system configuration is changed. Other windows pass through before
  key data is read. Disabling private input releases the relay; pipe EOF,
  HWND/process identity checks and a two-second heartbeat lease limit its life.
- Real tests pass: F2 -> Ctrl+F5 -> save -> updated list -> immediate Chinese
  toggle -> saved Chinese text -> F6 re-edit -> English toggle; Ctrl+Alt+P also
  records fully. Settings disable/re-enable returns/restores the relay and plain
  English saves without duplicate characters. Diagnostics confirm host_relay=1
  and physical-key packet delivery; this is not a headless-only assertion.
- Real main-screen maximize, toolbar/menu/editor clicks, restore/minimize/close
  and helper shutdown pass. Chinese candidates and maximized Chinese save pass.
  Regressions: 14 key/chord, 14 Chinese-toggle, 17 Settings-search, 14 Settings UI,
  15 private-input cases, and 15 terminal cases with input off and 15 with it on.
  Settings' local HTTP fixture and socket tests needed sandbox escalation.
- Exact remaining validation boundary: the target host window reported Chinese
  layout 0x08040804 but IME open status 0 at inspection time. We did not change
  it. Therefore absence of the user's host candidate popup with Windows already
  in Chinese composition mode is not claimed as visually verified.
  A separate test-owned Windows textbox could not obtain foreground focus;
  that additional cross-window GUI check was inconclusive and is not counted
  among passing tests. The relay's HWND guard remains explicitly scoped in code.
- Linux release and four affected shared modules' Windows COFF assembly/macOS
  ARM translation pass. Only build/rhun is rebuilt; no installation, commit,
  push or release is performed.

## Unified shortcuts and native IME ownership (2026-11-14)

- Original rhun already provides Keyboard Shortcuts and the [keys] registry.
  Chinese toggling and terminal copy/paste now use that registry. Settings links
  to the shared list; old individual shortcut rows are hidden, old config names
  remain readable. F2 edits the selected stroke, Enter saves, Escape cancels.
- User bindings support ordinary combinations, chords, and clean-release Shift /
  Ctrl+Shift / Alt+Shift / Ctrl+Alt gestures. Typing and other shortcuts cancel
  modifier-only gestures. Binding edits preserve context and arguments.
- Native IME suppression begins when the private helper starts, before window
  creation; it continues in private English mode and ends on disable/failure.
  Wayland v1 explicitly hides/deactivates/commits native input; v3 disables and
  commits. XIM follows ownership and rejects late native text. No system IME
  configuration, global hotkeys or Windows input language settings are changed.
- Production protocol tests pass for v1/v3 startup ownership, private English
  ownership, stale native commits, private composition preservation and native
  restoration. Existing native v1 composition/UTF-8 fixture also passes.
- Real WSLg window test passes using the bundled private runtime directly:
  Windows physical keys, visible private candidates, Chinese UTF-8 save,
  maximized typing and clean exit. It does not force the host IME into Chinese;
  absence of host candidate UI with an already-Chinese Windows IME still needs
  confirmation on that exact desktop state.
- Shortcut regressions pass: 14 key/chord cases, 11 Chinese-toggle cases,
  17 Settings-search cases and 2 Settings inventory/string cases. Terminal PTY
  tests pass in both modes (15 each). Real private Fcitx input has 15 passing
  cases; client/engine failure recovery also passes.
  Linux release build, seven changed modules' Windows assembly and macOS ARM
  translation pass. Native Windows/macOS GUI behavior is not verified here.
- Current local build is build/rhun. Installed binaries and published releases
  are unchanged. Earlier terminal-hotkey notes below describe the previous UI.

## Terminal clipboard hotkeys (2026-11-14)

- Settings > Terminal now exposes Terminal copy hotkey and Terminal paste hotkey.
  Linux/Windows defaults: copy_key=ctrl+c, paste_key=ctrl+v. Values apply live,
  persist across restarts, and accept an empty value to disable the extra binding.
- Copy only intercepts the configured key when terminal text is selected.
  Without a selection Ctrl+C reaches the program; a real sleep command was
  interrupted successfully. Ctrl+Shift+C/V and Shift+Insert stay available.
- Terminal keyboard tests pass with the private Chinese engine off and on,
  covering UTF-8/multiline bracketed paste, legacy/kitty protocols, selection
  copy, live remapping, empty shortcuts, invalid shortcuts and saved settings.
- Settings search and string save/cancel/blur regression tests pass. Linux
  release build, Windows assembly of the changed modules, macOS ARM translation
  of those modules and git diff --check pass. No native Windows GUI validation.
- The remote verification host timed out over SSH on this date. This change
  uses lightweight local headless tests; no installation or containers were
  added locally. The built binary is build/rhun; installed copies are unchanged.

## 远程安装与跨发行版验证（2026-11-13）

按用户要求在 ego@192.168.118.253 验证，未继续本机安装或创建本机容器。
远程宿主为 Ubuntu 22.04.5 LTS x86-64；无图形显示会话。
使用本次修改后的本地构建包，版本字段为 0.19.4，并非已发布的同名 GitHub 包。

- 安装包 SHA-256：5e514a016ebe95b1a886af47f6f59ec1cf0e511a9a130d562e8e70ab5374d4f2。
- 已安装程序：/home/ego/.local/bin/rhun；SHA-256：
  b36f0e72f75ab35eee57f1cc302b448cddae27037df599884af9cfaa005046f9。
- 安装参数 --chinese-input --no-modify-path --no-url-scheme；
  使用 RHUN_RELEASES_URL=file:// 指向上传的发布目录，完成校验、解包和用户目录安装。
  未安装宿主系统依赖，未修改系统输入法或 shell 配置。
- Ubuntu 宿主：直接运行已安装程序，通过应用输入事件和真实私有引擎，
  输入并保存 UTF-8“中文”；额外设置无效 PYTHONHOME/PYTHONPATH 验证隔离。
- tests/installed-ime.py：4 项通过，覆盖安装选择、设置实时切换、运行时缺失回退、
  升级与卸载配置保留；RHUN_TEST_RELEASES_URL 可复用已有包，无需重新打包。
- Debian 12 精简容器：解压直接启动和完整安装均通过，并输入、保存“中文”。
  基础镜像没有 curl/wget，完整安装验证挂载宿主已有的静态 BusyBox wget；
  未在宿主安装软件。容器软件源下载较慢的尝试已终止并移除该临时容器。
- Alpine 3.24.2（musl）容器：使用自带 BusyBox wget 完整安装通过，
  私有 glibc 加载器运行输入引擎，直接启动程序并输入、保存“中文”。
- 实测发现并修复 GNU/BusyBox wget 参数差异；新版本使用 -T，
  旧版本缺少 -T 时用 timeout，均保留失败诊断、有限重试与校验。
  tests/install-download.py：12 项通过（curl、GNU wget、旧 BusyBox，
  各覆盖 503 重试、404 失败及静默更新）；Alpine 新 BusyBox 完整安装通过。

容器完整安装使用远程临时 HTTP 服务下载同一安装包，未验证 GitHub 公网下载或 TLS。
验证为 headless 模式下的实际编辑器事件、真实拼音转换和文件保存；
不等同于图形窗口、字体显示、物理键盘和宿主输入法交互验收。
支持结论限于以上 x86-64 环境，未验证 ARM、其他发行版或本次集成的原生 Windows。
压缩包约 74 MiB，输入运行时解包后约 128 MiB。修改尚未提交或发布。

远程日志与脚本保存在 /home/ego/rhun-install-verification/，
其中 evidence/ 包含安装、输入、各容器与下载器测试日志。

## 正常安装集成验证（2026-11-13）

- 发布包内包含 Fcitx5、词库、Python、D-Bus 和所需动态库；普通安装器一同安装，
  无需 tools/setup-fcitx.sh 或 tools/run-personal.sh。
- 安装参数 --chinese-input / --no-chinese-input 只写 rhun 自身配置。
  Settings > Editor > Enable Chinese Pinyin input 可以实时启停并保存。
- tests/installed-ime.py：4 项通过。覆盖普通安装后直接启动并输入中文、
  不受外部 Conda/Python 环境影响、Settings 关闭和重新开启、缺失运行时回退、
  实际替换旧版本时保留配置，以及卸载保留配置。所有安装使用临时 HOME。
- tests/fcitx-input.py：15 项通过；tests/fcitx-failure.py：客户端崩溃和引擎丢失
  均恢复普通键盘输入。输入测试等待实际就绪，替代固定启动延时。
- tests/chinese-toggle.py：8 项通过；tests/settings-search.py：17 项通过。
- tests/settings-ui.py：14 项通过（本地 HTTP 用例因沙箱禁止 socket 单独重跑通过）；
  最终设置项清单与布尔开关往返两项再次通过。
- PATH=/usr/bin:/bin sh tests/install.sh：安装器回归全部通过，含 8 项下载测试。
- release 编译、git diff --check、Shell/Python 语法检查和 macOS 输入模块翻译通过。

本次未重新运行原生 WSLg/Windows 键盘验收或完整 tests/run.sh，未修改系统输入法配置。
修改尚未发布；已有 v0.19.4 安装包不包含本节新增集成。

## 此前的实机验证

日期：2026-11-12，WSL/Linux amd64。

产物：build/rhun，SHA-256：
ab065f42482c8f883e5b7c39d94761892b228b4b454d3aacaaac98505e56f6f7

## 已通过

- release 编译，git diff --check，启动脚本语法检查。
- tests/fcitx-input.py：12 项。编辑器提交与撤销、Esc 取消、英文切换、
  数字/鼠标选词、退格、命令/快捷键切换、切换文档、失焦、查找框、
  终端提交、终端分屏切换时取消预编辑。
- tests/fcitx-protocol.py：真实私有引擎的候选、PgUp/PgDn 翻页、提交和切换。
- tests/fcitx-failure.py：仅终止测试客户端/私有引擎，确认普通键盘自动恢复。
- tests/fcitx-live.py --live：独立 WSLg 窗口，真实 Windows 按键输入中文，
  保存为 UTF-8；最大化后继续输入并保存。最大化截图尺寸为 1920×1040。
  实测 Ctrl+Space 被宿主截获，改用应用内 Ctrl+Alt+Space 后通过。
- 个人启动器 tools/run-personal.sh：自动启动项目内引擎，输入“中文”成功。
- tests/git-auth.py：普通模式及私有引擎模式均通过；中文模式开启后进入密码框，
  token 仍按原文处理，取消流程正常。
- tests/wsl-input.py（5 项）、terminal-splits.py（1 项）、side-diff.py（1 项）、
  window-focus.py（5 项）、terminal-font.py（5 项）通过。
- 重新链接的 ime_test 和 side_alignment_test 通过。
- 测试退出后只读检查，未残留本次私有输入法引擎进程。

候选和最大化画面的实机截图位于 /tmp/rhun-fcitx-live-candidates.ppm、
/tmp/rhun-fcitx-live-maximized.ppm（临时产物，不纳入版本控制）。

## 范围

仅使用项目内解压运行时、词典、配置和私有 D-Bus；不安装系统软件，
不修改系统或用户全局输入法配置，不替换 WSLg。Windows 输入法词库不共享。
未运行整个 tests/run.sh；以上为明确执行并通过的定向验证。
此前用户已确认的主屏最大化及顶部按钮兼容处理未被本次替换。

启动和关闭方式见 personal-wsl.md。
