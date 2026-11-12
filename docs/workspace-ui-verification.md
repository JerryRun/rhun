# 工作区右键流程验证

验证日期：2026-11-12。

## 本次行为

- Git 工程根目录：左侧空白处右键显示“Add Folder to Workspace”。普通父目录不自动发现子仓库。
- 首次添加：先选择工程目录，再选择工作区保存目录（Save Workspace in ...），最后确认文件名（Save the workspace as）；取消任一步或写入失败不加入目录。
- 当前工程目录已有适用定义：复用首个有效目录与当前工程一致的定义，不打开无关工作区。
- 顶部项目标签和窗口标题使用工作区名；中文名称已验证。
- 一级目录右键显示“Remove Folder from Workspace”；仅移出工作区，不删除磁盘文件。至少保留一个目录。
- 增删自动更新定义并保留扩展设置；移除首个工程后保留工作区文件与名称。
- 首个工程移除被未保存文件询问取消时，文件及工作区保持原状，不将未完成切换带入下次操作。
- Windows 另存为接受原生反斜杠路径及中文名称。

新增界面文字使用英文；中文设置搜索词作为隐藏别名保留，不出现在设置说明中。

## 检查结果

- Linux release 编译成功。
- tests/workspace-folders.py：31 项通过（含新增 10 项）。
- tests/file-launch.py：14 项通过。
- tests/readonly-save.py：13 项通过。
- tests/new-window.py：3 项通过。
- tests/settings-search.py：17 项通过，中文关键词搜索保留。
- tests/settings-ui.py：13 项通过，本地 HTTP 测试脱离沙箱单独重跑通过。
- tests/explorer-create.py、tests/explorer-delete.py：全部通过。
- Windows release 编译成功；Windows 进程 headless UI 脚本验证英文菜单、先选工程再选保存目录及文件名、中文工作区标题、移除首个工程和自动保存，正斜杠及原生反斜杠路径均通过。
- tests/windows-package.py 和 git diff --check 通过。

Linux 截图位于 build/verification/workspace/；Windows 截图及输出位于 build/windows/workspace-check/。
已检查 Linux 另存为截图和 Windows 一级目录右键截图，标题、英文菜单及保存目录选择正常显示。
测试仅使用隔离配置和临时目录，未修改系统配置、未关闭或重启用户窗口；不代表真实桌面鼠标操作验收。

## 构建指纹

- build/rhun: 0e6234bfc2260dc1a36ccf36a635f002acbb060103796a64c538f5ad64402d24
- build/windows/rhun.exe: b86ad579dc02a44fe46789b7ed69c89ecf14548ad9e4254d27f861e3bd01fd2a
- build/windows/rhun-0.19.1-windows-x86_64.zip: 8265c9bcff9d3f23fcb8ff3ebc0a7e0897cff02a1a70b99953e6c8186961a54c
