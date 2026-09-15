# 期待独立候选接入记录

目标：恢复原任务五张真实表情帧，接到已修复公共基础，保留默认素材与跟随，并交由 Windows 构建。

## 已恢复的证据

- 原任务：`task_e_6a9ab4b2c2688322b8c95fce65a90c13`。
- 原清单默认图 SHA-256：`48f710b9811ebf6edc60764bc7a52fd1af4274a761589677df365450d8a2fec7`。
- `tools/build_drag_expression_frames.py` 重建结果与云端五个 PNG 哈希完全一致；`assets/drag-expectation/v1/frames.pack.json` 是唯一提交的图形文本载体。
- `tools/build_expectation_assets.py` 将变动区合成到真实公共基础中性帧；`assets/expectation/runtime/` 仅为构建输出。EXE 只携带五张运行 PNG 及清单，不携带源图包和 QA 副本。

## 实际接线

- `main` 创建一次 `ApplicationServices`、一次 `HungerService(SharedHungerState(...))`，替换诊断 DropTarget 后传同一个 services 给 `ExpectationWindow`。
- `DragExpectationRuntime` 通过 `services.file_worker.submit` 和 `file.result` 校验，不另建工作线程、状态库或时钟；唯一共享 Coordinator 授权 `DRAG_PREVIEW`。
- 同一会话从身体移入头部会重新评估；离开头部、取消、满值、异步验证晚到均不复活旧动画。受保护事务不能被期待或菜单抢占。
- Drop 返回 None，仅发布冻结 `ExpectationDrop`；总集成可注入 `consume_drop`，在 FEED 侧重新校验与确认。独立候选不回收或奖励。
- 正常离开播放 150ms 退场，显式取消及事务抢占立即清除图层；旧定时器受会话版本和 Coordinator token 双重校验。

## 验证与限制

复现命令：

```text
python tools/build_expectation_assets.py --preview <临时目录>
python tests/test_drag_expression_frames_unit.py
python tools/verify_drag_runtime.py
python tools/verify_graphic_animation_contract.py
```

Windows 构建脚本执行前三项相关运行门禁与 PyInstaller；Actions 另用临时状态、独立 mutex、自身进程树、可见 Tk 窗口和 after_idle 就绪标记验证启动，检查未产生文件事务或奖励，并输出唯一 EXE 的 SHA-256。回调异常会写入启动诊断并令门禁失败。

本轮没有运行真实用户文件操作或真实鼠标拖动，也没有宣称用户视觉通过。独立 EXPECT 只验证共享 Health/tear 状态恢复；HUNGER 表情显示与 FEED 消费者需在总应用中复用既有实例。预览时暂由图形帧显示中性方向的眼部表情，结束后恢复既有跟随。
