# 桌面宠物

这是使用提供的猫咪照片制作的 Windows 桌面宠物。

## 运行

双击 `dist/桌面宠物.exe` 即可运行，无需安装 Python。程序默认无边框、透明并始终置顶；重复双击不会创建第二只桌宠。

## 操作

- 左键点击：依次播放跳跃、压扁回弹、左右抖动。
- 左键拖动：移动桌宠。
- 鼠标滚轮：连续调整大小。
- 右键：选择小、中、大尺寸，切换“始终置顶”，或退出。

每次互动会随机显示一条简短中文白色气泡，气泡自动避开角色和屏幕边缘，并在约 1.8 秒后隐藏。

## 重新构建

项目开发依赖安装在 `.venv`。在项目根目录运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

构建脚本会先验证 18 张透明动作帧并运行无需桌面会话的自动测试，然后生成 `dist/桌面宠物.exe`。窗口测试需在交互式 PowerShell 中运行：先设置当前 Python 的 `TCL_LIBRARY` 与 `TK_LIBRARY`，再执行 `python -m pytest tests/test_window.py -q`。
