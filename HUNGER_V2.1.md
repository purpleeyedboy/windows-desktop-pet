# REPAIR-20260906-V21-HUNGER

- 版本：V2.1-HUNGER 返工测试版；日期：2026-09-06。
- 饥饿单位：`0..100000`；`1000 = 1%`，从满值严格按真实 UTC 经过 120 分钟归零。
- Health 边界：Normal `20000..100000`、Hungry `10000..19999`、SevereHungry `1000..9999`、CriticalHungry `0..999`，无额外滞回。
- 表现：Hungry/SevereHungry 使用 0.35 秒张嘴、最长 1 秒保持、0.35 秒闭嘴的独立嘴内部与舌层；Severe 保持段和 Critical 使用夸张泪层。局部层每帧按当前头部姿态锚点重新合成，不修改确认素材。
- 状态：唯一正式路径 `%LOCALAPPDATA%/DesktopPet/state.json`；旧 `hunger-v1.json` 只读迁移并保留原文件，不双写。奖励、OperationId 与新锚点同一原子提交。
- 调试：一级“调试”菜单，直接二级包含 100/20/19.9/10/9.9/1/0.9/0%、时间 +30/+60/+120 分钟、重播和内部状态。调试时钟为真实 UTC 加进程内正偏移，不修改系统时间。
- 公共基础入口使用真实 `desktop_pet.foundation.services.create_application_services(BuildInfo)` / `ApplicationServices`。`SharedHungerStatePort` 只投影共享状态字典并调用同一个 `AtomicJsonStore.save`，不创建第二套队列、Clock 或正式状态文件；饥饿活动使用同一个 `RuntimeContext` / `ActivityCoordinator`。
- 当前状态：公共基础已按源码交接接入；候选仍为**未自动测试、等待用户 Windows 实机验收**。程序绘制嘴舌是功能 fallback，不宣称视觉完成。
- Windows workflow 不运行 pytest/旧自动测试；云端证据仅限语法、导入、临时状态演练和临时预览，不冒充 Windows 验收。
- 公共基础源码交接来源标识为 `e178f371bd2da1c0b4e892609acfdf79bfcab450`；这是逐文件 blob 已核验的来源记录，不伪称为当前分支 Git 祖先。
- 嘴层审查：旧版确实是单色几何椭圆，不能作为已验收动作。本轮改为窄纵向开口、羽化 Alpha、内部纵向光影、独立舌层与高光，并按当前头姿态逐帧重建；它仍是程序局部层，最终观感明确等待用户 Windows 实机验收，不宣称已获视觉接受。
- 精度：业务重锚点同时保存 `HungerDecayRemainder`，因此反复正常关闭不会因整数除法截断而延长 120 分钟满值到零的周期。
- 喂食接口：`HungerService.apply_reward(operation_id: str, units: int, *, now_utc: int | None = None) -> tuple[HungerSnapshot, bool]`。奖励、锚点、`LastFeedUtc` 与最近 32 个 `OperationId` 先在副本中组装，再由一次 `commit_hunger` 原子提交；提交失败不发布内存状态，可用同一 ID 安全重试。
