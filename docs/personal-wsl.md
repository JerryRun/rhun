# rhun 个人 WSL 版本

发布版正常安装后直接执行 rhun .，或解压发布包执行 bin/rhun .。
中文输入在 Settings > Editor > Enable Chinese Pinyin input 中开启，
也可在安装时指定 --chinese-input；无需额外启动脚本。
源码开发时执行 ./build.sh release；准备发布运行时使用
/usr/bin/python3 tools/package-ime.py，然后同样直接运行 build/rhun .。
tools/run-personal.sh 仅保留给开发测试使用独立配置，不是安装版的启动要求。

## 中文输入

WSLg defaults to following the Windows Chinese/English mode when private input
is enabled. Start normally with rhun .; no environment flag is required.
Settings > Editor > Follow Windows input mode controls this immediately.
Only the state is shared; composition, candidates and vocabulary remain private.
If the host state is unavailable, the independent rhun shortcut remains available.
Disable following to use the custom rhun toggle intentionally.

Wayland 后端增加 text-input-v1 的激活、光标位置、预编辑与 UTF-8 提交支持。
实际能否直接调用 Windows 输入法还取决于 WSLg 的输入法桥接，不能只凭协议存在确认可用。
Settings 开关可直接启动**仅供 rhun 使用的应用内 Fcitx5 拼音引擎**：

- 关闭 **Follow Windows input mode** 后，**Ctrl+Alt+Space** 切换中英文，或使用命令 **Input: Toggle Chinese Pinyin**；
  输入拼音后，候选词显示在光标附近。Ctrl+Space 在未被 Windows 截获时也可用。
- 设置页面顶部点击 **Keyboard Shortcuts**，或从命令面板打开同名入口。
  搜索 **Input: Toggle Chinese Pinyin**，选中绑定后按 **F2**，直接按新组合键，Enter 保存。
  弹窗内再按 F2 可切换为手工输入名称；Backspace 清空，保存后禁用。
  默认 ctrl+alt+space，支持普通组合键及 shift、ctrl+shift、alt+shift、ctrl+alt。
  纯修饰键在未参与打字或其他快捷键的情况下，松开时切换。
  留空禁用所选绑定；Esc 取消；统一写入 [keys]，旧 [editor] chinese_toggle_key 仍兼容。
  Windows 原生版继续使用系统输入法切换键。
- **空格**选择首项，**数字键**或鼠标点击选词；PgUp/PgDn 翻页，Esc 取消。
- 编辑器、终端和普通文本框使用同一输入通道；密码/token 框跳过拼音处理。
- 预编辑不写入文件；提交后才成为可撤销的编辑。切换文件、窗格或失去焦点会取消组合。

发布包包含引擎、词典、Python 与 D-Bus，普通安装会一同安装到 share/rhun/。
配置、词频与缓存保存在 rhun 自身配置目录的 ime/ 下。使用私有 D-Bus，退出后结束；
不安装系统软件，不设置全局输入法、不替换 WSLg，不连接或接管其他应用的输入法。
终端子进程仍保留原桌面 D-Bus。它使用独立的 Linux 拼音词库，不共享 Windows 输入法词库。

WSLg 下私有输入就绪后，现有窗口助手仅在当前 rhun 窗口获焦时转发物理按键，
避免这些按键同时进入宿主输入法；内部中文和英文模式均使用该通道。
不修改宿主输入法配置、语言或开关状态。关闭功能、离开窗口或退出时停止转发。
宿主已处于中文组合状态时的候选框场景仍缺少该桌面状态下的直接验收，详见验证记录。

开启或关闭 Settings 中的 Enable Chinese Pinyin input 立即生效并保存。
WSLg 开启后默认跟随宿主中英文状态。正常安装无需下载或配置额外组件。

另外保留 Windows 输入法弹窗作为备用入口：

1. 在编辑器、终端或文本框中定位光标。
2. 按 **Ctrl+Alt+I**，或在命令面板选择 **Input: Chinese via Windows IME (WSL)**。
3. 在 Windows 原生输入框中使用中文输入法。
4. **Ctrl+Enter** 或 Insert 写入原目标，Esc 或 Cancel 取消。

支持多行，不借用剪贴板或保存内容到临时文件。期间更换文件或终端会丢弃结果，
防止写入另一个目标。该入口是弹窗方案，尚不能视为编辑区内原地中文输入已完成验收。
它要求 WSL Windows interop 和 Windows PowerShell 可用。

## 字体

个人启动器默认使用内置 Iosevka，缺失的中文字形由系统字体回退显示；不额外内置 Droid。
不再自动设置 Windows 字体路径，避免启动时同步读取跨盘字体。现有用户自定义路径仍可使用，
不复制或分发 Windows 字体。

配置项：[editor] font、fallback_font、font_size；[terminal] font、font_size、line_height；
[ui] font、font_size。Windows 字体路径在 /mnt/c/Windows/Fonts/。
支持 glyf TrueType TTF/TTC，TTC 使用第一个字体面；不支持 CFF/OTF 轮廓。

## 终端分屏

| 操作 | 快捷键 / 命令面板 |
| --- | --- |
| 左右分屏 | Ctrl+Alt+L / Terminal: Split Right |
| 上下分屏 | Ctrl+Alt+J / Terminal: Split Down |
| 切到下一个窗格 | Ctrl+Alt+N / Terminal: Focus Next Pane |
| 只显示当前窗格 | Terminal: Show Active Pane Only |

终端右键菜单也有入口；点击窗格切换输入目标，拖动分隔线调整大小。
每个新窗格启动独立 shell，支持嵌套。关闭 shell 后合并窗格；只显示当前窗格保留其他会话。
当前分屏布局不跨应用重启恢复。
分屏之间使用与其他区域一致的 1 像素分隔线，拖拽命中范围仍保留。
活动窗格不再绘制底部高亮条；终端标签的选中高亮条继续保留。
终端标签为 shell+当前目录名，例如 bash+rhun；切换目录后约半秒刷新，程序任务仍保留原名称。
Windows 支持 cmd/PowerShell：PowerShell 仅在本次终端会话的提示符附加目录报告，
不会写入 PowerShell profile 或修改系统配置。

## 编辑器滚动

代码编辑区的鼠标滚轮/触控板默认速度调整为原来的一半，保留小幅触控板输入的累积。
Settings 搜索 **Editor scroll sensitivity** 可调整：默认 **0.5**，设为 **1.0** 恢复此前速度。
对应配置为 [editor] scroll_sensitivity；范围 0.1–2.0，每次调整 0.1。
它与 [ui] scroll_sensitivity 的全局倍率相乘；Alt 仍可快速滚动。
只改变编辑区滚轮步进，面板滚动速度和拖动滚动条的比例保持原有行为。

## 工作区右键操作

- 单独打开一个 Git 工程后，在左侧文件树空白处右击，选择 **Add Folder to Workspace**。
  先选择要添加的工程目录；首次再选择工作区保存目录（**Save Workspace in ...**），
  最后确认工作区文件名（**Save the workspace as**）。取消任一步或保存失败，目录不会加入工作区。
- 已有以当前工程为首个有效目录的工作区定义时直接复用；打开工作区后也可以从空白处继续添加。
- 顶部项目标签和窗口标题显示工作区名称。即使只剩一个工程，也保留一级工程目录行。
- 右击一级工程目录，选择 **Remove Folder from Workspace**。只移出工作区，不删除磁盘文件。
  至少保留一个目录；移除首个工程时，如有未保存文件会先询问，取消则保留原工作区。
- 添加和移除后自动更新当前工作区定义文件，扩展设置保留。通过“打开文件”选择
  `.rhun-workspace` 即可恢复整个组合。普通父目录不会自动发现其子工程的 Git 仓库。
- 新增菜单、提示、设置说明保持原版英文风格；中英文切换设置仍支持中文关键词搜索，关键词不显示在界面。

## 文件差异

从 Explorer 打开文件始终显示普通编辑区。从 Git 面板的 Changes 点击已跟踪文本文件，
显示左侧只读 HEAD、右侧可编辑工作区；Git: Open Changes 命令使用相同入口。
再次从 Explorer 打开同一个文件会返回普通编辑，复用当前文档并保留未保存内容和撤销历史。
增删行留白对齐，共享纵向滚动；最右侧显示全文件差异分布，点击跳到最近变更。
右侧保留原文档与撤销历史，留白不进入保存内容。包括已暂存和未暂存的变更。
未跟踪文件、没有 HEAD 的仓库、原有统一 diff 标签和过窄窗口使用普通视图。

命令 **Git: Toggle Side-by-Side Comparison** 切换，配置为 [editor] side_diff = true/false。
比较模式暂不折行、折叠，基线侧暂不支持文本选择；差异过多时使用粗粒度对齐。
差异地图是彩色变更分布条，不是代码缩略图。

## Markdown 预览

在 Explorer 中右击 Markdown 文件，或在 Markdown 源码编辑区、文件标签上右击：

- **Open Preview**：打开独立的只读预览标签，名称为 README.md (Preview)；
  重复打开同一文档会复用预览标签。
- **Open Preview to the Side**：左侧源码、右侧预览；修改未保存的源码也会立即更新。
  点击右上角 ×，或执行 **Markdown: Close Side Preview**，恢复完整源码编辑区。

命令面板也提供两个打开入口。支持 .md、.markdown、.mdown（不区分大小写）。
使用应用已有的原生 Markdown 渲染器，支持标题、列表、引用、代码块、表格、链接与图片；
相对链接和图片以源文件目录为基准。预览中可选择/复制文字，用方向键、PageUp/PageDown、
Home/End 滚动，Tab 选择链接、Enter 打开。侧边预览获得焦点时，Esc 返回源码编辑。
关闭源码后，独立预览保留最后一次已渲染的内容。

单个预览支持最大 1 MiB 的源码；不执行 HTML/JavaScript，不新增 Mermaid 或数学公式引擎。
没有修改系统配置，也不需要安装浏览器或额外预览扩展。

## Git 授权

本地仓库从 GUI 发起 push/fetch/pull，需要凭据时通过应用内弹窗询问。
用户名明文，密码或 token 遮罩；Esc 取消。已有 credential helper 仍先工作。
服务端要求 token 时在密码框填写 token。没有新增凭据持久化。
远端 SSH 窗口内运行的 Git 暂未接入本地 askpass 通道。

## 验证

### WSLg native window and pointer handling

Normal window positioning and all mouse events stay on the original
Wayland/WSLg path. The earlier Windows SetWindowPos correction and native mouse
relay have been removed: they could leave the Windows HWND and compositor on
different outputs, producing an arrow cursor over the primary-screen editor.

The process-specific Windows helper remains for private Pinyin key routing,
read-only host input-state observation and hidden-cursor recovery after a peer
window closes. On exactly two active monitors, it also detects an unexpected
monitor change during normal-to-maximized transitions. After 200 ms it may send
one native Windows monitor-move shortcut to the same foreground window, keeping
RAIL and compositor geometry synchronized. This bounded workaround does not
write HWND geometry or forward mouse input. It cancels on lost focus, display
layout changes, or a user Windows-key operation; held keys/buttons and recent
typing defer it until its one-second deadline. Already-maximized monitor moves
remain under user control. A brief visual jump may occur; the underlying WSLg
work-area cache is not repaired. No system configuration is changed.
Existing windows must be restarted to load a new build.
RHUN_WSL_WINDOW_FIX=0 disables this entire helper, including private key routing.

Run python3 tests/wsl-window.py --live for repeated native maximization,
content dimensions, toolbar/menu/editor clicks and window controls. Its setup
uses the current monitor without forcing an HWND position.
Run python3 tests/wsl-cursor.py --live --multi-monitor for two maximized windows
on distinct primary/secondary displays. It compares actual Windows cursor
bitmaps over the editor and toolbar, including focus and hover changes. It also
repeats actual secondary-to-primary drags followed by toolbar maximization and
checks that explicit monitor moves are not undone. Test
windows move through the normal Windows shortcut; fewer than two active displays
is an explicit skip. Both tests touch only their disposable windows and briefly
move the pointer. Missing native windows or suppressed cursors are failures,
not passing results. Current verification limits are recorded in
ime-verification.md.

### 其他功能

执行 tests/run.sh 和 python3 tests/terminal-font.py。
新增覆盖中文协议提交、Windows 助手路由与取消、终端独立 PTY、Git 授权与取消、
差异行映射、编辑与保存。
项目内拼音验证：./tools/run-fcitx.sh /usr/bin/python3 tests/fcitx-protocol.py；
./tools/run-fcitx.sh /usr/bin/python3 tests/fcitx-input.py。
异常恢复：./tools/run-fcitx.sh /usr/bin/python3 tests/fcitx-failure.py。
实机输入：./tools/run-fcitx.sh /usr/bin/python3 tests/fcitx-live.py --live，
会打开唯一命名的测试窗口，用真实 Windows 按键验证中文候选、保存和最大化输入。

## Shared sidebar and terminal docking

The left sidebar contains Explore, Changes and Graph. Explore starts
expanded; both Git blocks start collapsed and can be opened independently.
Changes contains commit actions and changes. Graph contains the compact
commit graph with single-line subject/author rows. Click a commit to expand or collapse its changed files directly below it. Ctrl+Shift+G toggles Changes;
Git: Toggle Graph toggles the graph. The title bar Git button is removed.
Narrow panels use icon actions with command tooltips and compact inline file rows. Enter/Space toggles commit files; Right expands and Left collapses.

The terminal header includes Move Panel to Right / Bottom. Settings > Terminal >
Terminal position provides the same choice. The position and separate width/height
are saved in the project-local profile. Running terminals and their split layout
stay alive when moved. No system settings are changed.


## Terminal shell startup

Terminal clipboard shortcuts use **Keyboard Shortcuts**, available from the Settings
header or command palette. Search for **Terminal: Copy Selection** or **Terminal: Paste**,
select a binding and press F2, then press the new shortcut. Enter saves, Escape
cancels, and Backspace clears the selected binding. F2 inside the prompt switches
between key recording and typing a shortcut name. Changes use the original [keys]
mechanism and apply immediately.

    [keys]
    ctrl+alt+c = terminal_copy when terminalFocus && terminalHasSelection
    ctrl+c = none when terminalFocus && terminalHasSelection
    ctrl+alt+v = terminal_paste when terminalFocus
    ctrl+v = none when terminalFocus

Linux/Windows default to Ctrl+C with a selection and Ctrl+V. Without a selection,
Ctrl+C still interrupts the program. Ctrl+Shift+C/V and Shift+Insert are listed in
the same shortcut editor. Existing [terminal] copy_key/paste_key values are still
read for compatibility. macOS keeps Command+C/V by default. UTF-8 and multiline
text use bracketed paste when enabled by the terminal program.

The terminal preserves the user's Bash startup files. Conda hook generation and
automatic environment activation, plus NVM's automatic Node selection, can delay
the first prompt even though the terminal pane is already open.

Optional manual change in ~/.bashrc: replace the entire conda init block with
loading the installed shell functions directly:

    . "$HOME/soft/miniconda3/etc/profile.d/conda.sh"

This keeps conda activate/deactivate available without generating the hook or
activating base for each new terminal. When needed, run conda activate ENV_NAME.
Activation itself still has its own cost. An environment inherited from the parent
process is not deactivated by this change.

Replace the NVM script loading line with:

    [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh" --no-use

Keep export NVM_DIR and the existing completion line. Node on the inherited PATH
remains available; use nvm use VERSION (or nvm use for a project .nvmrc) when needed.
The slow automatic manpath discovery then occurs only when selecting a version.
These are instructions only: rhun does not edit ~/.bashrc, .condarc or system PATH.
