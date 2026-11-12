# 项目内拼音输入验证记录

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
