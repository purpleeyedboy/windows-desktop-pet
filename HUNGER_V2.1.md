# V2.1 饥饿真实帧与公共基础接入候选版

- 饥饿单位 `0..100000`，满值按真实 UTC 在 120 分钟归零；20%、10%、1% 分界保持不变。重锚点保留整数衰减余数。
- `main()` 只创建一个 `ApplicationServices`，随后向公共 `PetWindow` 和饥饿模块注入同一个实例。`HungerService` 是饥饿业务 owner；持久化经过 `SharedHungerState` 写入 `services.state` 的 `hunger` 字段，不另建文件或存储器。
- `hunger` 内部记录 `StateVersion`、`HungerAnchorUnits`、`HungerAnchorUtc`、`HungerDecayRemainder`、`FirstLaunchUtc`、`LastFeedUtc`、`AppliedOperationIds`。同次提交更新公共 `hunger_anchor_utc_seconds` 和 `recent_operation_ids`，保留最新窗口、待处理事务等其他字段。
- 奖励接口仍为 `HungerService.apply_reward(operation_id, units) -> (snapshot, applied)`。喂食模块必须注入同一个服务；不能绕过 owner 直接改锚点。写入成功才更新内存，重复 ID 不加奖，失败可重试。
- 公共基础来自 `f617765b1aeb1be9cf9d73ce1dd04f5f4e426421`；逐帧活动与菜单优先级修复来自 `6af84461332787ee6eb16ffe945a56083bbd1d89`（包括 e361579 的活动播放修复）。活动异常恢复实现已按公共基础 CORE `1a18477faa4caa28170e648437d7cb8b39612ac0` 的已核验 blob `a58b54aa1d3cb1bfe1b88e9554697a417e7e2dcb` 实际同步，不只是记录标签；`docs/hunger-foundation-provenance.json` 保存逐文件来源提交、Git blob 与 SHA-256，构建前逐项核验。
- 嘴部与眼泪表现使用恢复任务产生的真实 RGBA 图形帧。四张表情只取原生成素材的嘴部和眼泪，以真实运行默认图为固定底板；整张 alpha 和限定区域以外的 RGB 都逐像素保持一致，避免切换时缩身、变脸或头部移位。普通/严重饥饿分别使用 `NORMAL_HUNGER_ANIMATION` / `SEVERE_HUNGER_ANIMATION`，由公共窗口、通道与逐帧播放器播放。程序绘制嘴形的旧路径不接入此入口。
- 极度饥饿表情只在空闲时显示；拖放期待、右键菜单和喂食抢占后隐藏。Critical 不允许身体/舔手动作，继续保留喂食、菜单和退出权限。
- 退出先保存饥饿 checkpoint，再让公共基础关闭 worker/OLE 与保存最新共享状态。公共基础忽略旧启动快照，防止覆盖已经提交的奖励或事务。
- Windows 工作流先运行隔离的饥饿回归（UTC/离线恢复、保存失败与奖励幂等、400 条文案、交互抢占恢复），再运行来源核验、隔离临时状态演练、公共逐帧播放检查并构建单一 EXE；不运行与本候选无关的旧整套测试。Windows EXE 构建成功仍不等于素材视觉验收通过。
