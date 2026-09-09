# REPAIR-20260906-V21-HUNGER

- 版本：V2.1-HUNGER 返工测试版；日期：2026-09-06。
- 饥饿单位：`0..100000`；`1000 = 1%`，从满值严格按真实 UTC 经过 120 分钟归零。
- Health 边界：Normal `20000..100000`、Hungry `10000..19999`、SevereHungry `1000..9999`、CriticalHungry `0..999`，无额外滞回。
- 表现合同：Hungry/SevereHungry 使用 0.35 秒张嘴、1 秒保持、0.35 秒闭嘴的逐帧整幅 RGBA 姿态；Severe 保持段和 Critical 使用美术绘制的眼泪姿态。活动帧整幅替换显示以避免新旧嘴重叠，中断后恢复当前实时默认姿态；不修改确认素材。
- 状态：唯一正式路径 `%LOCALAPPDATA%/DesktopPet/state.json`；旧 `hunger-v1.json` 只读迁移并保留原文件，不双写。奖励、OperationId 与新锚点同一原子提交。
- 调试：一级“调试”菜单，直接二级包含 100/20/19.9/10/9.9/1/0.9/0%、时间 +30/+60/+120 分钟、重播和内部状态。调试时钟为真实 UTC 加进程内正偏移，不修改系统时间。
- 公共基础入口使用真实 `desktop_pet.foundation.services.create_application_services(BuildInfo)` / `ApplicationServices`。`SharedHungerStatePort` 只投影共享状态字典并调用同一个 `AtomicJsonStore.save`，不创建第二套队列、Clock 或正式状态文件；饥饿活动使用同一个 `RuntimeContext` / `ActivityCoordinator`。
- 当前状态：公共基础已按源码交接接入。旧程序几何嘴舌/泪滴已从运行路径移除；真实逐帧素材尚缺，因此当前构建脚本会明确拒绝打包，不能作为候选 EXE。素材接入后仍须标记为未自动测试并等待用户 Windows 实机验收。
- Windows workflow 不运行 pytest/旧自动测试；云端证据仅限语法、导入、临时状态演练和临时预览，不冒充 Windows 验收。
- 公共基础源码交接来源标识为 `e178f371bd2da1c0b4e892609acfdf79bfcab450`；这是逐文件 blob 已核验的来源记录，不伪称为当前分支 Git 祖先。
- 嘴层审查：旧版程序椭圆/多边形实现已删除。`HungerFrameLibrary` 只接受带逐帧阶段、时长与 SHA-256 的真实 RGBA 整幅 PNG 序列；没有素材时启动/打包均可见失败，不再显示几何替代品或旧跳跃。
- 精度：业务重锚点同时保存 `HungerDecayRemainder`，因此反复正常关闭不会因整数除法截断而延长 120 分钟满值到零的周期。
- 喂食接口：`HungerService.apply_reward(operation_id: str, units: int, *, now_utc: int | None = None) -> tuple[HungerSnapshot, bool]`。奖励、锚点、`LastFeedUtc` 与最近 32 个 `OperationId` 先在副本中组装，再由一次 `commit_hunger` 原子提交；提交失败不发布内存状态，可用同一 ID 安全重试。
