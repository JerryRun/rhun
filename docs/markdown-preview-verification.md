# Markdown 预览与终端高亮调整验证

日期：2026-11-12。本轮没有修改系统配置、全局输入法、PowerShell profile 或个人启动器。

## 交付

- 去除选中终端窗格的底部高亮条，保留终端标签选中条与 1px 分隔线。
- Markdown 的 Explorer 文件菜单、编辑区右键菜单、文件标签菜单增加
  Open Preview 和 Open Preview to the Side。
- 独立预览使用单独的只读标签，重复打开同一源文档会复用；侧边预览左侧源码、
  右侧渲染，未保存编辑即时更新。右上角 × 或 Markdown: Close Side Preview 关闭侧栏。
- 复用原生 Markdown 渲染器，支持已有标题、列表、表格、代码、链接、图片与文本选择。
  预览采用独立焦点，阻止输入、撤销和删除等编辑命令误改源码。
- 源码关闭后独立预览保留最后一次渲染快照，通过文档 ID 查找避免引用已释放文档。
- 支持 .md、.markdown、.mdown，大小写不敏感；预览源码上限 1 MiB。

## 已通过

- Linux release 和 Windows x64 release 编译、Windows portable ZIP 打包。
- tests/markdown-preview.py：14 项。覆盖三处右键菜单、未保存编辑实时更新、
  独立标签复用、只读焦点、编辑快捷键防护、命令面板恢复焦点、关闭按钮、相对链接、
  无扩展接收者的链接、源码关闭、滚动与窄窗口、大小写扩展名、目录过滤、大小限制。
- tests/terminal-splits.py：独立 PTY、目录标题、嵌套分屏、点击焦点、关闭合并；
  像素断言确认标签选中条保留、窗格底部条移除、水平/垂直分隔线仍为 1px。
- tests/markdown.py：16 项原生解析/布局/链接回归。
  其中性能时限项在并发测试时曾超时，停止并发后整组重新运行通过。
- tests/ext-menus.py：15 项；tests/ext-views-doc.py：12 项。
- tests/side-diff.py：Git 面板打开双栏、编辑保存、Explorer 回到普通编辑。
- tests/save.py：42 项；tests/readonly-save.py：13 项；tests/keys-chords.py：12 项。
  只读 diff 保存测试改为使用已删除文件，符合此前 Git Changes 改为可编辑双栏的行为，
  继续验证统一只读 diff 的 Vim :wq 关闭流程。
- Windows 原生 rhun.com 无界面实测：右键入口、侧边预览、未保存内容更新、只读防护、
  独立预览标签与关闭；正常退出。隔离配置及日志位于 build/windows/markdown-check/。
- tests/windows-package.py；git diff --check。

截图已查看：build/verification/markdown/ 下的 markdown-side.png、markdown-tab.png、
markdown-narrow.png、terminal-splits.png、windows-side.png、windows-tab.png。

本轮未运行完整 tests/run.sh，也未自动操作用户现有 WSLg 窗口。
预览不执行 HTML/JavaScript，未增加 Mermaid 或数学公式渲染引擎。

## 产物指纹

- build/rhun：5dbbbfdc376291f749638fe9c2317d3d0346bf024d5a139f6bbea551ec221285
- build/windows/rhun.exe：422246435adc19bd90c3525c4b46a0cd4b6de24751a68e3867df0bbf9bd23303
- build/windows/rhun-0.19.1-windows-x86_64.zip：dc3b76488126198b57695e8b0a2620a7fc7a1be3f95128c10170583983c07f6d

docs/refinements-verification.md 和 docs/ime-verification.md 是此前构建的记录。
