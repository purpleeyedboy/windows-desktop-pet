# REPAIR-20260906-V21-HUNGER

- 版本：V2.1-HUNGER 返工测试版；日期：2026-09-06。
- 饥饿单位：`0..100000`；`1000 = 1%`，从满值严格按真实 UTC 经过 120 分钟归零。
- Health 边界：Normal `20000..100000`、Hungry `10000..19999`、SevereHungry `1000..9999`、CriticalHungry `0..999`，无额外滞回。
- 表现：Hungry/SevereHungry 使用 0.35 秒张嘴、最长 1 秒保持、0.35 秒闭嘴的独立嘴内部与舌层；Severe 保持段和 Critical 使用夸张泪层。局部层每帧按当前头部姿态锚点重新合成，不修改确认素材。
- 状态：唯一正式路径 `%LOCALAPPDATA%/DesktopPet/state.json`；旧 `hunger-v1.json` 只读迁移并保留原文件，不双写。奖励、OperationId 与新锚点同一原子提交。
- 调试：一级“调试”菜单，直接二级包含 100/20/19.9/10/9.9/1/0.9/0%、时间 +30/+60/+120 分钟、重播和内部状态。调试时钟为真实 UTC 加进程内正偏移，不修改系统时间。
- 公共基础依赖：要求 PR5 提供 `desktop_pet.foundation.create_foundation_services(root)`，其中共享 StateStore 暴露 `%LOCALAPPDATA%/DesktopPet/state.json`、`atomic_commits=true`、`load_hunger/commit_hunger`；ActivityCoordinator 暴露 `publish_health`、`begin(activity, priority, animation_id, state_version)`、`is_current`、`complete`、`cancel(token, recovery_anchor)`、`input_allowed`、`status_text`。本分支不实现第二套 ActivityCoordinator、事件队列、Clock 或 StateStore。
- 当前状态：**未完成统一基础接入，禁止标为可验收成品**。候选构建保持仅打包路线；接入同一 PR5 foundation commit 后，才生成 `桌面宠物_修复饥饿衰减与张嘴流泪.exe` 供用户 Windows 实机验收。
- Windows workflow 不运行 pytest/旧自动测试；云端证据仅限语法、导入、临时状态演练和临时预览，不冒充 Windows 验收。
