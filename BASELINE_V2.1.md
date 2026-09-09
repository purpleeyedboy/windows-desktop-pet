# 桌面宠物 V2.1 基线记录

## 文档与代码基线

- 基线编号：`BASE-001`。
- 文档版本：V2.1。
- 继承代码提交：`e01800c5030803580f6e227f689f05540bd04700`（minimum-jerk 与既有候选基线）；本记录及实现由后续 BASE-001 提交闭环。
- 测试版文件名：`桌面宠物_最终素材与转头角度基线修正版.exe`。

## 已启用且必须保留

- 用户已批准的猫头、猫身与眼部素材；逐像素 Alpha。
- 连续眼球跟随、自然眨眼、头颈连续形变。
- minimum-jerk 接近、弧线和回中缓动。
- 左右实际随机倾斜范围：最小 18°、最大 30°。
- 内部姿态与网格安全校验上限：50°；它不属于实际随机动作范围，未被缩减。

## 明确未实现

V2.1 耳朵、前肢、舔手、饥饿、拖放和喂食功能均不在 BASE-001 范围内，也未在本基线中实现。

## 验证与状态

- BASE-001 聚焦自动测试：35 项通过（角度、minimum-jerk、运行时集成、版本、依赖声明、Windows 工作流契约）。
- Python 编译、素材 158 文件 SHA-256 前后清单对比和 `git diff --check`：通过。
- 云容器完整收集受缺少 PyInstaller/NumPy 且网络 403 阻止安装影响；排除三个依赖收集文件后的历史套件结果为 568 通过、3 跳过、15 失败、42 错误，其中包含无 DISPLAY 的 Tk 测试和当前已批准素材与旧黄金基准不一致。以上不被写作通过，也不作为 Windows 验收。
- Windows Actions：待提交/PR 后在 `windows-latest` 手动或 PR 触发构建，校验唯一 EXE、输出 SHA-256 并上传 artifact。
- Windows EXE 真实运行与桌面视觉验收：**待用户验收**。Linux 云容器结果不作为 Windows EXE 或视觉验收证据。
- Git：BASE-001 实现提交为 `5a7338d8d8c53b880a4a05ea783b1352df4add18`；PR 因当前容器没有 GitHub 凭据/远端而待创建。

## V2.1-FEED-CORE 独立候选

- 功能标签：`V2.1-FEED-CORE`；版本 `2.1.0`；日期 `2026-09-04`。
- 新增文件验证、逐次确认、IFileOperation/专用 STA 回收适配器、版本化事务审计、NeedsReview 崩溃恢复，以及幂等奖励与动画回调边界。
- DRAG 仅为不注册 DropTarget 的标准 Drop 事件 adapter；HUNGER 仅为幂等奖励 fake。生产接线留待 FEED-WIRING，因此该 EXE 如实标为测试候选。
- 候选文件名：`桌面宠物_文件喂食与回收站事务.exe`。Windows Actions 负责测试、唯一 EXE、大小、SHA-256 和 artifact 门禁。
- 既有认可素材、运动、转头角度、旧测试及金图均未修改；真实 Windows 构建、IFileOperation opt-in E2E 与用户桌面验收仍为待执行门禁。


### PR #8 候选修正

- 候选 EXE 现在直接导入并运行 `feed_core` 的临时目录模拟事务，界面醒目标注模拟模式；不注册 DropTarget、不提供文件选择，也不移动或删除任何真实文件。
- PyInstaller 明确收集完整事务核心，构建后验证嵌入 PYZ 模块并运行冻结 EXE `--self-test`；Windows 门禁仍待 Actions 执行。
- 确认前后及 STA 执行前复核稳定身份与关键元数据；等待有明确超时/取消，未知结果进入 NeedsReview。奖励仅接受含凭证且经验证的回收结果。
- 本轮删除了真实回收站 E2E 测试入口；自动测试仅使用模拟器、内存替身和测试创建的临时目录。


## V2.1-FEED-CORE 实机高风险候选接线（2026-09-05）

- 候选入口改为真实桌宠 `run_desktop_pet.py`，由唯一 Windows OLE `IDropTarget` 接收单文件，且 DropEffect 只返回 Copy；喂食区限定于桌宠头部。
- 只允许本地固定磁盘、0–1 GiB 普通文件，并拒绝目录、网络/虚拟路径、重解析点、云占位、可移动盘、程序自身、仓库/素材与系统保护对象。
- 松开后逐次显示文件名、大小和修改时间确认；仅实时验证 IFileOperation 成功后幂等增加饥饿值并显示反馈。极度饥饿不会禁用喂食或退出。
- `桌面宠物_文件喂食与回收站事务.exe` 明确为未经过自动测试、等待用户 Windows 实机验收的高风险候选；Actions 刻意跳过 pytest，只执行编译、资源/归档、唯一 EXE、大小、SHA-256 与上传门禁。
- Windows 构建、真实拖放/回收站行为和用户验收尚未在本 Linux 环境完成；不得将代码检查写成实机通过。


## REPAIR-20260906-V21-FEED 状态

- 已撤回“功能完成”结论，并删除私有 HungerMeter、事务协调器/日志、模拟器、阻塞确认及无 ProgressSink 的回收实现；不再用矩形头部命中或 jump 冒充喂食表现。
- 已实现面向 PR5 公共基础的只读 Protocol adapter：OLE 回调只复制路径、坐标和共享 Clock 的 UTC 时间，并提交唯一 InputRouter；区域命中依赖 InteractionRegionService 的 Alpha 区域。
- 当前仓库尚无 PR5 foundation API、PR11 期待反馈 adapter、共享 HungerService/StateStore/ActivityCoordinator，也没有可信 IFileOperationProgressSink 与独立嘴/舌素材动画。因此构建脚本主动失败，禁止发布可验收候选。
- 公共基础统一并完成上述依赖后，才允许输出 `桌面宠物_文件喂食与回收站事务修复.exe`；Windows 实机验收仍待用户执行。

### INTEGRATE-20260906 第二轮

- 尝试读取 PR5 `codex-od26j1` 与提交 `1a02fe9680f28dda07add8b96c78445e0b3c0f59`，但 GitHub HTTPS fetch 被容器代理以 403 拒绝；该对象也不在本地对象库，故未声称接入该 SHA。
- 在现有 foundation adapter 上新增 FEED 业务 handler/ports：定点奖励计价、Prepared 持久化前置、确认后 FILE_ID_INFO 重验、元数据变化重新确认、可信凭据后 RecycleConfirmed、原子奖励与 Completed、缺证据 NeedsReview。
- 新增非阻塞拥有窗 30 秒确认 adapter、Windows 句柄 FILE_ID_INFO 检查 adapter，以及严格组合 PostDeleteItem/PerformOperations/aborted/new-item 证据的凭据 assembler。
- 尚缺实际 PR5 API 适配、PR6 HungerService、PR11 期待层、COM IFileOperationProgressSink vtable/消息泵接线和嘴/舌素材动画；构建继续 fail-closed，不发布候选。

## FEED-ANIMATION-RECOVERY-20260909 状态

- 本轮附件彩色源（1024×1536 RGB，SHA-256 `ba65bc204a76af8f21fc1c1250eb98e9df69edd6553df8e8b17c5671da45ece5`）与遮罩源（1024×1536 RGB，SHA-256 `5b1d87426305fe457dcf6be2d5dae290db646b991119f18ca6b7687cd37468ff`）现合并为唯一无损文本源 `assets/feed/v1/source/feed-sources.base64.txt`；每行不超过 120 字符，解码后先校验原 PNG SHA。未跟踪 PNG、逐帧输出、GIF 或联系表。
- 构建工具按遮罩六个大连通主体而非机械 3×2 等格定位，隔离相邻主体，统一到 672×768 RGBA、猫高 524、脚底 y=736、中心 x=336；原 512×768 canonical 的 `(80,0)` 偏移及 SHA-256 `48f710b9811ebf6edc60764bc7a52fd1af4274a761589677df365450d8a2fec7` 写入精简 manifest。
- 成功表现使用实际全幅猫帧：半张嘴、三次大口开合、眯眼舔上唇、眯眼舔嘴角，然后恢复最新头眼姿态；播放期间眼睛/头部刷新只更新恢复候选而不覆盖动作，中断亦恢复。未加入吞咽、几何嘴形或旧 jump 替代。
- 事务触发边界未新建状态机或饥饿系统：改用公共入口 `desktop_pet.foundation.services.create_application_services(build_info)`，并要求 `desktop_pet.foundation.runtime.RuntimeContext`；共享 InputRouter/ActivityCoordinator/HungerService/StateStore、可信 IFileOperationProgressSink 回执和原子幂等奖励仍决定正式动画触发。菜单另有明确标注“不回收文件”的独立动画调试入口，它不提交 FeedDrop、不给奖励，也不伪造成功。
- 本地对象库没有 `30393b441360518ac07137ce31852b171fb8a6cb`、`856171c` 或公共基础 `e178f371`；Git HTTPS 读取仍被代理 403 拒绝。当前检出直接缺少 `src/desktop_pet/foundation/services.py` 和 `src/desktop_pet/foundation/runtime.py`（以及它们在 `e178f371` 中的同包传递依赖），构建门禁保持 fail-closed；未再等待或引用不存在的 `foundation/api.py`。
- 独立 Windows 候选名改为 `桌面宠物_文件进食动画恢复候选.exe`。Windows Actions 构建、归档内六帧核验、EXE SHA-256、真实 Windows 回收/COM 行为和用户桌面视觉验收均待执行；Linux 预览不等同 Windows 或用户验收。
- 远端待提取实现基线为 `878b384`，本轮修复提交为 `c1b2733`。聚焦 Linux 自动检查为 71 通过、3 跳过；编译、业务/恢复脚本、确定性重建、base64 行宽、解码源素材 SHA、JSON 与 `git diff --check` 通过。黑/白/棋盘底联系表已从实际生成帧写入忽略目录并人工检查，未再见相邻主体碎片；最终 Windows 桌面视觉接受仍为待用户验收。
