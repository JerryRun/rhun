# rhun 个人 WSL 版本

项目目录中执行 ./build.sh release 编译，再执行 ./tools/run-personal.sh . 启动。
启动器首次复制原有配置，再加入个人字体设置；配置保存到
build/personal/config/rhun/config，会话保存到 build/personal/state/。
可在设置中修改，或直接编辑配置。没有安装到系统目录，不影响 Windows 安装版。

## 中文输入

Wayland 后端增加 text-input-v1 的激活、光标位置、预编辑与 UTF-8 提交支持。
实际能否直接调用 Windows 输入法还取决于 WSLg 的输入法桥接，不能只凭协议存在确认可用。
个人启动器现在可启动**仅供 rhun 使用的项目内 Fcitx5 拼音引擎**：

- **Ctrl+Alt+Space** 切换中英文，或使用命令 **Input: Toggle Chinese Pinyin**；
  输入拼音后，候选词显示在光标附近。Ctrl+Space 在未被 Windows 截获时也可用。
- 设置页面顶部点击 **Chinese / English hotkey** 直达配置，或搜索
  **输入法**、**快捷键**、**中英文切换**、**hotkey**、**chinese_toggle_key**；
  修改 **Chinese / English hotkey**；
  默认 ctrl+alt+space，Enter 确认后立即生效并保存。留空关闭应用快捷键，无效键名保留原值。
  对应配置为 [editor] chinese_toggle_key；Windows 原生版仍使用系统输入法切换键。
- **空格**选择首项，**数字键**或鼠标点击选词；PgUp/PgDn 翻页，Esc 取消。
- 编辑器、终端和普通文本框使用同一输入通道；密码/token 框跳过拼音处理。
- 预编辑不写入文件；提交后才成为可撤销的编辑。切换文件、窗格或失去焦点会取消组合。

引擎和词典解压到 build/fcitx5/root，配置、词频、缓存与运行文件保存在
build/personal/ime。使用私有 D-Bus，会话结束后退出；不安装系统软件、不改 ~/.config，
不设置全局输入法、不替换 WSLg，不连接或接管其他应用的输入法。
终端子进程仍保留原桌面 D-Bus。它使用独立的 Linux 拼音词库，不共享 Windows 输入法词库。

本项目内运行时已准备好；重新准备时可执行 ./tools/setup-fcitx.sh，脚本只下载并解压
Ubuntu amd64 的软件包。若现有系统缺少 Python D-Bus/GLib 或 dbus-run-session，脚本报错停止，
不自动安装。启动 ./tools/run-personal.sh . 后用 Ctrl+Alt+Space 开始输入。
关闭此功能：RHUN_INLINE_IME=0 ./tools/run-personal.sh .。

另外保留 Windows 输入法弹窗作为备用入口：

1. 在编辑器、终端或文本框中定位光标。
2. 按 **Ctrl+Alt+I**，或在命令面板选择 **Input: Chinese via Windows IME (WSL)**。
3. 在 Windows 原生输入框中使用中文输入法。
4. **Ctrl+Enter** 或 Insert 写入原目标，Esc 或 Cancel 取消。

支持多行，不借用剪贴板或保存内容到临时文件。期间更换文件或终端会丢弃结果，
防止写入另一个目标。该入口是弹窗方案，尚不能视为编辑区内原地中文输入已完成验收。
它要求 WSL Windows interop 和 Windows PowerShell 可用。

## 字体

个人启动器在文件存在时启用：代码和终端用 Consolas，界面和中文回退用微软雅黑。
没有这些文件时保留内置字体和系统回退；不复制或分发 Windows 字体。

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

### WSLg 主屏最大化兼容

本机测到最大化内容为 1920×1040，但 Windows 窗口顶边落在 Y=114，导致顶部留空、
底部裁切。个人版本在 WSLg Wayland 下启动专属 Windows 助手，将已最大化的窗口
校正到当前显示器的 WorkingArea；不对普通窗口应用位置或尺寸校正。

启动时用进程与时间组合标记绑定自己的窗口，握手后移除标记；允许 WSLg 在标题后
附加发行版名。同名文件的其他窗口不会参与匹配。助手随 rhun 退出结束，不改显示器布局
或系统配置。这是应用级兼容处理，尚不能据此确定 WSLg 内部偏移的根因。

窗口被校正后，WSLg 的表面输入坐标可能仍有偏移。因此助手仅在这个已校正的最大化
窗口下，以 Windows 客户区坐标发送鼠标移动、左右中键和滚轮，替代重复的 Wayland
鼠标事件；键盘继续使用原通道。使用受窗口范围限制的鼠标监听，不拦截其他应用输入。
还原为普通窗口后恢复 Wayland 鼠标通道；输入助手不可用时保留原通道。

更新后须重新启动窗口：./tools/run-personal.sh .（已有窗口仍是旧代码）。
如需关闭该兼容处理：RHUN_WSL_WINDOW_FIX=0 ./tools/run-personal.sh .。

执行 python3 tests/wsl-window.py --live 可在独立测试窗口验证主屏重复最大化、
内容尺寸、真实鼠标操作顶部工具按钮/菜单/还原/最小化/关闭、编辑区定位和助手退出；
需要 WSLg 与 Windows PowerShell。测试会临时移动鼠标操作它自己创建的独立窗口。

### 其他功能

执行 tests/run.sh 和 python3 tests/terminal-font.py。
新增覆盖中文协议提交、Windows 助手路由与取消、终端独立 PTY、Git 授权与取消、
差异行映射、编辑与保存。
项目内拼音验证：./tools/run-fcitx.sh /usr/bin/python3 tests/fcitx-protocol.py；
./tools/run-fcitx.sh /usr/bin/python3 tests/fcitx-input.py。
异常恢复：./tools/run-fcitx.sh /usr/bin/python3 tests/fcitx-failure.py。
实机输入：./tools/run-fcitx.sh /usr/bin/python3 tests/fcitx-live.py --live，
会打开唯一命名的测试窗口，用真实 Windows 按键验证中文候选、保存和最大化输入。
