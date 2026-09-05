# 桌面宠物

这是使用提供的猫咪照片制作的 Windows 桌面宠物。

当前开发基线为 V2.1：保留已批准猫头、猫身、逐像素 Alpha、眼球跟随、眨眼、头颈连续形变与 minimum-jerk 转头缓动；随机左右倾斜的实际幅度为 18°–30°。50° 仅作为内部姿态/网格安全校验上限，不是实际随机动作范围。

## 运行

双击 `dist/桌面宠物-6帧猫耳颜文字版.exe` 即可运行，无需安装 Python。程序使用 Windows 逐像素 Alpha 显示平滑透明轮廓，默认无边框并始终置顶；重复双击不会创建第二只桌宠。

## 操作

- 左键点击：依次播放跳跃、压扁回弹、左右抖动。
- 左键拖动：移动桌宠。
- 鼠标滚轮：连续调整大小。
- 右键：选择小、中、大尺寸，切换“始终置顶”，或退出。

每次互动会显示统一的“猫耳蝴蝶结”图片气泡：背景与四向尾巴使用 PNG；中文使用内置站酷快乐体按 28px 绘制，纯颜文字使用内置 Noto Sans 与 Noto Sans Math 按 40px 逐字符确定性回退绘制。所有字体直接随 EXE 打包，不安装或调用系统字体。气泡会自动选择上、下、左、右位置以避开角色和屏幕边缘，并在约 1.8 秒后隐藏。

跳跃、压扁回弹、左右抖动各有独立的 200 句台词库，每个动作固定为 180 句中文和 20 条纯颜文字，共 600 句且全局不重复。每次成功点击只会从本次触发动作自己的台词库随机抽取 1 句，同一动作不会连续重复上一句。

## 重新构建

项目开发依赖安装在 `.venv`。在项目根目录运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

V2.1 候选版在 Windows 上使用 `build_eye_follow_candidate.ps1` 构建，输出 `dist-eye-follow-candidate\桌面宠物_最终素材与转头角度基线修正版.exe`。Linux 云容器中的测试和编译检查不能替代 Windows EXE 构建或真实桌面视觉验收。

构建脚本会先验证 18 张透明动作帧（3 组动作、每组 6 帧），并核对每张归档关键帧的 SHA-256 不变；随后验证每动作 `180 中文 + 20 颜文字`、三套内置字体覆盖和 28px/40px 渲染边界，再用独立 Tcl/Tk 生命周期运行自动测试。PyInstaller 生成唯一的 `dist/桌面宠物-6帧猫耳颜文字版.exe` 后，构建脚本会使用 PyInstaller 自身的归档读取器逐字节核对 18 张关键帧、5 张气泡图、3 个字体、3 份许可、台词 JSON 和第三方说明。

最终交付的三份 SIL Open Font License 1.1 分别位于 `交付\字体许可\ZCOOLKuaiLe-OFL-1.1.txt`、`交付\字体许可\NotoSans-OFL-1.1.txt` 和 `交付\字体许可\NotoSansMath-OFL-1.1.txt`；完整第三方来源与哈希说明见 `THIRD_PARTY_NOTICES.txt`。

## V2.1 文件拖动期待反馈测试版

独立候选版使用 `build_drag_expectation_candidate.ps1` 在 Windows 构建，唯一输出为 `dist-drag-expectation-candidate\桌面宠物_文件拖动期待反馈.exe`。它只在合法的 OLE 文件拖动进入猫咪有效像素感应区时返回 Copy 光标反馈并显示双眼放大/颤抖、粒子和头部高亮；Drop 始终返回 None。Copy 仅表示期待反馈，程序不复制、移动、删除、回收、打开、上传或修改文件，也不读取文件路径、不改变饥饿值。

右键菜单中的“调试：拖动期待态”只播放同一瞬态效果，便于实机视觉验收，不模拟或执行文件操作。动画数值集中在 `DragVisualConfig`，在 Windows 真机确认前均标记为待视觉验收。

QA 预览不纳入 Git。需要本地辅助检查时，可运行 `python tools/build_drag_expectation_preview.py --output-dir <临时目录>` 确定性生成 `before-after.png` 与 SHA-256 `stats.json`；候选发布工作流不生成或上传 QA 预览。源码边界工具仍可供开发者单独运行，但不再阻塞候选打包。

PR #11 的 Windows Actions 明确不运行 pytest，而是直接调用 `.\build_drag_expectation_candidate.ps1 -SkipTests`。该候选版标记为“未运行自动测试、等待用户 Windows 实机验收”；候选路径不执行旧视觉、基线差异或归档内容门禁，只运行 PyInstaller，并校验唯一 EXE、精确文件名、50 MiB 大小上限和 SHA-256 后上传 `桌面宠物_文件拖动期待反馈.exe`。
