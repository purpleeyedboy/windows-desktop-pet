# V2.1-DRAG 视觉检查记录

- `before-after.png` 不再纳入 Git；`tools/build_drag_expectation_preview.py` 在测试临时目录或 Actions 的 `$RUNNER_TEMP` 中生成，左侧为现有中性帧，右侧为 phase 1 的期待态临时合成。
- 自动检查覆盖输出尺寸与 Alpha 逐字节不变、两眼区域和头部区域发生可见变化。
- 生成结果为 1024×768 RGBA，并附带含 SHA-256 的 `stats.json`；当前高亮、眼睛倍率、颤抖、粒子数值均为候选值。
- Windows 分层窗口中的实际透明穿透、OLE 光标反馈、动画节奏与真实桌面视觉接受状态：**待用户验收**。
- 本报告不声称 Windows EXE 构建、实机 OLE 行为或人工视觉门禁已通过。
