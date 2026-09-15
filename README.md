# 桌面宠物

这是使用提供的猫咪照片制作的 Windows 桌面宠物。

当前开发基线为 V2.1：保留已批准猫头、猫身、逐像素 Alpha、眼球跟随、眨眼、头颈连续形变与 minimum-jerk 转头缓动；随机左右倾斜的实际幅度为 18°–30°。50° 仅作为内部姿态/网格安全校验上限，不是实际随机动作范围。

V2.1-EARS 独立测试版仅在该基线上增加左右耳各自的逐 Alpha 像素命中与按下、保持、松开反馈。透明像素通过原生窗口区域继续穿透；按住后移出、失焦、中断和退出都会撤销耳朵形变。耳朵反馈的保守幅度与时长集中在 `src/desktop_pet/ear_interaction.py`，状态为**待 Windows 实机视觉验收**；它不包含前肢、舔手、饥饿、拖放或文件喂食。
V2.1-LICK 返工中的行为合同为：公共空闲持续 60 秒后抽取 90–300 秒等待，获共享协调器授权时随机选择猫自身左侧或右侧并舔 3–20 次。普通鼠标路过和头眼跟随不算交互；单次舔舐 0.45 秒，20 次连同准备恢复不超过 13 秒。

当前分支只有等待 PR5 公共基础接入的 feature adapter 和基于真实局部层的合成接口。被用户拒收的固定坐标几何前肢/舌头已经移除；仓库尚缺经审核的原前肢、补洞、嘴、舌、遮罩和锚点资产，因此当前不提供可验收 EXE。依赖与调用链见 `docs/V2.1_GROOM_FOUNDATION_ADAPTER.md`。

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

双耳独立测试版使用 `build_ears_candidate.ps1` 构建，且只输出 `dist-ears-candidate\桌面宠物_双耳点击反馈_REPAIR-20260906.exe`。构建会嵌入产品版本、构建日期、Git 短哈希、`BASE-001` 基础标签、启用功能、未自动测试候选版渠道与 `V2.1-EARS` 文档基线；右键菜单的“调试信息”可查看这些值。按用户决定，此构建脚本与 Windows Actions 完全跳过 pytest 和旧自动验证，只执行 PyInstaller、唯一 EXE、精确文件名、大小和 SHA-256 门禁；产物等待用户 Windows 实机验收。

耳朵视觉预览不纳入 Git；如需预览，可手动使用 `tools/build_ears_preview.py --output <临时路径>` 生成。当前 Windows 候选工作流仅上传独立 EXE。

`REPAIR-20260906-V21-EARS` 已撤回此前候选完成声明。当前分支包含真实耳部动作和主窗口临时接线，但仍等待 PR5 公共 `ActivityCoordinator`/`InputRouter` 统一接入；`build_ears_candidate.ps1` 在缺少 `V21_FOUNDATION_COMMIT` 或公共 API 时拒绝生成候选。接入完成后的预留文件名为 `桌面宠物_双耳点击反馈_REPAIR-20260906.exe`。
完成公共基础与审核资产接入后，`build_idle_lick_candidate.ps1 -SkipTests` 的预定输出为 `dist-idle-lick\桌面宠物_舔手逐帧动画恢复.exe`。在此之前构建脚本会明确拒绝发布；不会继续交付旧的伪动作 EXE。

构建脚本会先验证 18 张透明动作帧（3 组动作、每组 6 帧），并核对每张归档关键帧的 SHA-256 不变；随后验证每动作 `180 中文 + 20 颜文字`、三套内置字体覆盖和 28px/40px 渲染边界，再用独立 Tcl/Tk 生命周期运行自动测试。PyInstaller 生成唯一的 `dist/桌面宠物-6帧猫耳颜文字版.exe` 后，构建脚本会使用 PyInstaller 自身的归档读取器逐字节核对 18 张关键帧、5 张气泡图、3 个字体、3 份许可、台词 JSON 和第三方说明。

最终交付的三份 SIL Open Font License 1.1 分别位于 `交付\字体许可\ZCOOLKuaiLe-OFL-1.1.txt`、`交付\字体许可\NotoSans-OFL-1.1.txt` 和 `交付\字体许可\NotoSansMath-OFL-1.1.txt`；完整第三方来源与哈希说明见 `THIRD_PARTY_NOTICES.txt`。

## V2.1 文件拖动期待反馈测试版

返工开发版使用 `build_drag_expectation_candidate.ps1` 在 Windows 构建，输出 `dist-drag-expectation-candidate\桌面宠物_期待逐帧与公共基础接入.exe`。公共基础来源记录为 PR #5 发布提交 `1a18477faa4caa28170e648437d7cb8b39612ac0`；同步的 `foundation/animation.py` Git blob 为 `a58b54aa1d3cb1bfe1b88e9554697a417e7e2dcb`。OLE 层会复制单个 `CF_HDROP` 本地绝对路径并释放 `STGMEDIUM`；多对象、目录、相对路径和网络路径被拒绝。Drop 只形成不可变预览事件，不执行复制、移动、删除、回收、打开、上传或修改文件，也不改变饥饿值。

右键菜单的一级“调试”子菜单提供“期待动画预览（3秒，不改变饥饿）”和“停止期待预览”；它不模拟或执行文件操作。动画数值集中在 `DragVisualConfig`，在 Windows 真机确认前均标记为待视觉验收。

QA 预览不纳入 Git。需要本地辅助检查时，可运行 `python tools/build_drag_expectation_preview.py --output-dir <临时目录>` 确定性生成 `before-after.png` 与 SHA-256 `stats.json`；候选发布工作流不生成或上传 QA 预览。源码边界工具仍可供开发者单独运行，但不再阻塞候选打包。

Windows workflow 在 `windows-latest` 上先运行 OLE 生命周期、异常恢复、反复触发与非破坏性回归，再构建独立单文件 EXE，并校验唯一文件、精确文件名、50 MiB 上限和 SHA-256。Windows 构建、artifact 发布、实机 OLE 验证与用户视觉验收仍是彼此独立的门禁。

**当前验收状态：** 当前分支已从 `main` 注入公共 services，并由候选窗口接入 coordinator、region、STA file worker 和只读饥饿门禁；发布来源为上述 PR #5 提交。自动回归不能替代 Windows 实机 OLE、DPI/多屏与视觉验收，完成这些独立门禁前 PR 保持开放。
