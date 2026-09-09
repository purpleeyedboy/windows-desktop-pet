# REPAIR-20260906-V21-HUNGER

- 版本：V2.1-HUNGER 返工测试版；日期：2026-09-06。
- 饥饿单位：`0..100000`；`1000 = 1%`，从满值严格按真实 UTC 经过 120 分钟归零。
- Health 边界：Normal `20000..100000`、Hungry `10000..19999`、SevereHungry `1000..9999`、CriticalHungry `0..999`，无额外滞回。
- 表现：Hungry/SevereHungry 使用 0.35 秒张嘴、最长 1 秒保持、0.35 秒闭嘴的独立嘴内部与舌层；Severe 保持段和 Critical 使用夸张泪层。局部层每帧按当前头部姿态锚点重新合成，不修改确认素材。
- 状态：唯一正式路径 `%LOCALAPPDATA%/DesktopPet/state.json`；旧 `hunger-v1.json` 只读迁移并保留原文件，不双写。奖励、OperationId 与新锚点同一原子提交。
- 调试：一级“调试”菜单，直接二级包含 100/20/19.9/10/9.9/1/0.9/0%、时间 +30/+60/+120 分钟、重播和内部状态。调试时钟为真实 UTC 加进程内正偏移，不修改系统时间。
- 公共基础入口已改为 PR5 公布的 `desktop_pet.foundation.services.create_application_services()` / `ApplicationServices`，不再依赖先前猜测的 `create_foundation_services`。共享 StateStore 的 hunger adapter 与 ActivityCoordinator 的精确字段仍必须在取得 `docs/v21-runtime-api.md` 后逐项核对；本分支不实现第二套 ActivityCoordinator、事件队列、Clock 或 StateStore。
- 当前状态：**未完成统一基础接入，禁止标为可验收成品**。候选构建保持仅打包路线；接入同一 PR5 foundation commit 后，才生成 `桌面宠物_修复饥饿衰减与张嘴流泪.exe` 供用户 Windows 实机验收。
- Windows workflow 不运行 pytest/旧自动测试；云端证据仅限语法、导入、临时状态演练和临时预览，不冒充 Windows 验收。
- 2026-09-06 本容器执行 `git fetch https://github.com/purpleeyedboy/windows-desktop-pet.git codex-od26j1` 得到 `CONNECT tunnel failed, response 403`，浏览 raw/GitHub 入口亦返回 401；本地对象库不存在 `1a02fe9680f28dda07add8b96c78445e0b3c0f59`。因此不得声称该 SHA 或精确 API 已接入。
- 嘴层审查：旧版确实是单色几何椭圆，不能作为已验收动作。本轮改为窄纵向开口、羽化 Alpha、内部纵向光影、独立舌层与高光，并按当前头姿态逐帧重建；它仍是程序局部层，最终观感明确等待用户 Windows 实机验收，不宣称已获视觉接受。
- 精度：业务重锚点同时保存 `HungerDecayRemainder`，因此反复正常关闭不会因整数除法截断而延长 120 分钟满值到零的周期。
