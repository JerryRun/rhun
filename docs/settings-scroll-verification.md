# 编辑器滚动与输入热键入口验证

日期：2026-11-12。未修改系统设置、系统输入法、PowerShell profile 或个人启动器。

## 修改

- 代码编辑区鼠标滚轮/触控板默认倍率改为 0.5，仅影响编辑区。
  Settings 的 Editor scroll sensitivity 可调 0.1–2.0，步长 0.1；1.0 恢复此前速度。
  配置为 [editor] scroll_sensitivity，与全局倍率相乘，Alt 快速滚动仍有效。
  保留两个轴的不足一像素余量，避免小幅触控板输入被取整丢失。
  折行和 Git 双栏源码沿用相同倍率；拖动滚动条仍直接按位置定位。
- Settings 标题右侧增加 Chinese / English hotkey 直达入口，点击筛选到可编辑配置。
  保留 editor.chinese_toggle_key，并支持搜索 hotkey、输入法、快捷键、中英文切换。
  Enter 保存后立即重绑；默认 Ctrl+Alt+Space。Windows 原生版继续使用系统输入法。

## 验证

- Linux release、Windows x64 release 编译成功，Windows portable ZIP 重新打包。
- tests/scroll-sensitivity.py：11 项，含默认减半、独立倍率、全局与 Alt 倍率、
  小幅输入累积、折行、反向滚动。
- tests/editor-hscroll.py：12 项，含拖动、轨道点击、横向边界、自动隐藏、长行。
  使用隔离实例与本地控制 socket，不操作用户现有窗口。
- tests/settings-search.py：17 项，含顶部直达、窄窗口、中文关键词、编辑与保存。
- tests/settings-ui.py：设置清单、全部字符串提交/取消/失焦保存、全部数字步进与边界。
- 私有 Fcitx tests/fcitx-input.py：14 项，含自定义热键、设置页修改后立即重绑、
  编辑区/终端中文输入、组合取消和撤销。仅使用项目内引擎与私有 D-Bus。
- tests/markdown-preview.py：14 项；terminal-splits.py、side-diff.py 回归通过。
- Windows 原生 rhun.com 无界面实测：滚动步进、顶部入口、中文搜索、配置修改与保存。
  配置使用 Windows 临时目录，日志位于 build/windows/settings-scroll-check/。
  最初放在 WSL UNC 路径的隔离配置未能保存，转 Windows 本地临时配置验证通过；
  该 UNC 保存问题不在本轮修改范围，不将其计为通过。
- tests/windows-package.py、git diff --check 通过。

截图：build/verification/settings-scroll/，已查看热键入口及 Windows 配置截图。
未执行完整 tests/run.sh，也未改变系统级配置或自动重启用户窗口。

## 产物指纹

- build/rhun：e21299a2b4c62bffa23c9e4c43487884aefb62493877185f957a9212a9814290
- build/windows/rhun.exe：1cff52170decd42751c4fad8ca05eed42e35427e9d5beba7c7751536739b1f6d
- build/windows/rhun-0.19.1-windows-x86_64.zip：8a8235d399818d2887e22b6623bc94d01db57d4e804566468fbd7d344cfd437e
