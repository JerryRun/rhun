# 个人版本四项优化验证

日期：2026-11-12。未修改系统设置、全局输入法或 PowerShell profile。

## 交付

- 设置：Editor / Chinese / English toggle shortcut，搜索 chinese_toggle_key。
  默认 ctrl+alt+space，Enter 确认后立即重新绑定并保存；原快捷键随之释放。
  Windows 原生版保持系统输入法；此项用于 Linux/WSL 的私有拼音引擎。
- Explorer 打开普通编辑；Git 面板 Changes 打开 HEAD/工作区双栏和右侧差异地图。
  复用现有工作文档；再次从 Explorer 打开返回普通编辑，保留未保存内容及撤销历史。
  已删除/二进制文件沿用只读 Git diff；提交历史保留原有视图。
- 分屏分隔线宽度为 1 个界面像素，保留较宽的拖拽命中范围；活动窗格底部高亮。
- shell 标签为 shell+当前目录名，每 500ms 检查更新。任务标签保留原有名称。
  Linux 读取 shell 的 /proc/PID/cwd；Windows cmd 使用只读进程目录查询，
  PowerShell 在当前会话提示符发送 OSC 7，未写入任何 profile 文件。

## 已通过

- Linux release 与 Windows x64 release 编译；Windows portable ZIP 打包与内容测试。
- tests/fcitx-input.py：14 项，使用真实项目内私有 Fcitx。
  包含自定义键替换默认键、设置页面即时重绑、中英文提交、终端输入、撤销和组合取消。
- tests/settings-search.py：14 项；settings-ui.py 的设置清单及全部字符串提交/取消/失焦保存测试。
- tests/side-diff.py：真实 Git 面板 Changes 点击打开双栏，右侧编辑保存，
  实际点击 Explorer 文件行回到普通编辑并保留未保存内容。
- tests/terminal-splits.py：独立 PTY、中文带空格目录标题更新、嵌套分屏、
  鼠标切换输入目标、关闭合并；截图像素检查水平/垂直 1px 线和底部高亮。
- 重新链接的 term_test、terminal-cwd-test、config_strings_test、side_alignment_test、keys_test。
  OSC 7 检查包含百分号 UTF-8 解码、普通标题不覆盖目录，以及无效元数据处理。
- Windows 本机无界面进程实测：cmd.exe 和 powershell.exe 终端均从 Temp 切到 Windows，
  标签对应从 shell+Temp 更新为 shell+Windows，正常退出。
- git diff --check。

截图位于 build/verification/refinements/：terminal-splits.png、file-normal.png、
file-diff.png、file-reopened.png。此轮没有重新跑全部 tests/run.sh 或 WSLg 实机按键测试。
此前 docs/ime-verification.md 属于上一个构建的验证记录。

## 产物指纹

- build/rhun：8ca43b3ab4117c513398a3260e756c8dc502b602094637dc2d55bf1a0b431699
- build/windows/rhun.exe：a64db42a3dd9802b75bd87287127995480e0e8d28184c20bc344f8d394895b2d
- build/windows/rhun-0.19.1-windows-x86_64.zip
