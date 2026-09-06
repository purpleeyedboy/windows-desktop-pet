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

## V2.1-DRAG 独立增量

- 候选文件名：`桌面宠物_文件拖动期待反馈修复.exe`；基础标签仍为 `BASE-001 / V2.1`。
- 当前仅启用既有认可基线；文件拖动期待反馈列为 `incomplete_features`。一级“调试”子菜单含开始/结束演示，文档基线为本文件。
- OLE 边界现调用 `GetData(CF_HDROP/TYMED_HGLOBAL)`，复制单个本地盘绝对路径和数量后立即 `ReleaseStgMedium`；多对象、目录、相对/网络/设备路径均拒绝，不把 `IDataObject` 留给异步代码。
- Copy 仅是光标反馈。程序不复制、移动、删除、回收、打开、上传、读取或修改文件，也不改变饥饿值；未实现耳朵、前肢、舔手、饥饿或文件喂食。
- 临时 compositor 使用 0.15 秒目标 120% 的局部眼区、按眼宽 1.5% 颤抖、真实 Alpha 轮廓高亮和独立 Alpha 粒子；不写入认可素材。独立眼层和共享 Coordinator Recovery 尚待 PR5 接线及实机视觉复核。
- 版本化 adapter 已防止取消/换对象后的异步结果复活；完整中断恢复、最新 Health/泪眼恢复和实际注销链仍待公共基础接线验证。
- 构建元数据版本为 `2.1-drag-repair-dev.1`，日期 `2026-09-06`；打包时注入实际 Git 短哈希，foundation 标记为 `NOT_INTEGRATED`。

### V2.1-DRAG 验证状态

- V2.1-DRAG 聚焦自动测试：28 项通过、2 项 Windows 跳过；既有眼球运行时/闲置转头/头颈形变门禁：175 项通过。Python 编译、既有 158 个认可素材的 SHA-256 前后清单对比和 `git diff --check`：通过。
- 开发者可独立运行 `tools/verify_drag_source_diff.py` 检查相对 `c3b218d` 的源码 diff 与既有 158 个 `assets/` 文件；运行 #33963393479 证明该工具在 Windows cp1252/浅克隆环境不可靠，因此它不再属于候选打包门禁。QA PNG 不纳入 Git，候选发布工作流也不生成或上传 QA 预览。
- 容器完整测试因缺少 PyInstaller/NumPy 在 3 个文件收集时报错；排除这些依赖文件后为 586 项通过、3 项跳过、12 项失败、42 项错误（737.66 秒），仍受无 DISPLAY、临时目录限制以及既有视觉金图与当前认可素材不一致影响。这些结果只记录，不将其写作通过，也不删除测试或修改金图。
- Windows workflow 保留手动打包路线，但当前 artifact 明示 `Foundation integration: NOT COMPLETE` 与 `Not an acceptance candidate`。
- Windows 分层窗口 OLE 实机拖入、透明区域穿透及真实桌面视觉验收：**尚不可开始**。Linux 预览不作为 Windows OLE/EXE 或人工视觉通过证据。
- REPAIR-20260906 已撤回“功能完成”结论：当前仓库没有 PR5 foundation API/基础提交。PR #11 已添加共享服务 Protocol、版本化 adapter、实际 `CF_HDROP` 单路径提取与 `STGMEDIUM` 释放，并禁止未注入 adapter 时注册旧 format-only 目标；`main` 注入、共享异步文件策略、协调器 Recovery/泪眼联动及 Windows 证据仍未完成，所以修复版仅为 foundation-blocked 开发构建。
- 转头角度不属于本增量门禁且未调整；旧视觉回归失败只记录，不删测试、不改金图。

## 验证与状态

- BASE-001 聚焦自动测试：35 项通过（角度、minimum-jerk、运行时集成、版本、依赖声明、Windows 工作流契约）。
- Python 编译、素材 158 文件 SHA-256 前后清单对比和 `git diff --check`：通过。
- 云容器完整收集受缺少 PyInstaller/NumPy 且网络 403 阻止安装影响；排除三个依赖收集文件后的历史套件结果为 568 通过、3 跳过、15 失败、42 错误，其中包含无 DISPLAY 的 Tk 测试和当前已批准素材与旧黄金基准不一致。以上不被写作通过，也不作为 Windows 验收。
- Windows Actions：待提交/PR 后在 `windows-latest` 手动或 PR 触发构建，校验唯一 EXE、输出 SHA-256 并上传 artifact。
- Windows EXE 真实运行与桌面视觉验收：**待用户验收**。Linux 云容器结果不作为 Windows EXE 或视觉验收证据。
- Git：BASE-001 实现提交为 `5a7338d8d8c53b880a4a05ea783b1352df4add18`；PR 因当前容器没有 GitHub 凭据/远端而待创建。
