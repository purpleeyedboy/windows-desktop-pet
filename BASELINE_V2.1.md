# 桌面宠物 V2.1 基线记录

## CORE-ACTIVITY-RECOVERY-20260910 活动恢复契约复核

- 公共 `AnimationChannels` 现保证物理播放、取消或恢复回调抛出异常时，仍释放对应的共享活动令牌并回到逻辑待机；原始异常继续向调用方传播，避免把物理失败伪装为成功。
- 取消通道只调用一次物理取消；随后仅在通道仍由同一令牌持有时清除所有权并执行公共中性恢复。迟到 `recover()` 不得删除同通道替代活动，回调重入后也会再次核对所有权；既有活动/版本/取消 ID/动画 ID 四字段身份契约不变。
- `tools/verify_graphic_animation_contract.py` 已把播放异常、取消异常、显式恢复异常和旧令牌恢复不影响替代活动纳入 Windows 打包前门禁，并继续覆盖真实窗口队列、活动通道、逐帧播放器、抢占、超时与中性帧恢复。
- 功能分支兼容契约：继续使用 `ActivityCoordinator.request_activity()` 获得令牌，以同一令牌调用 `AnimationChannels.play()`，只通过 `complete()`、`cancel()` 或 `recover()` 结束；不得直接写 `RuntimeSnapshot` 或绕过通道。功能分支应以本修复提交为共同基础 SHA；具体 SHA 随提交与 PR 回报，不以循环自引用写入本文件。
- 本项不改变活动优先级、认可素材、动作时序或 About 机器字段。Windows Actions 构建成功、artifact 下载复核、Windows 实机运行和视觉验收仍分别记录，不能相互替代。

## ABOUT-LOCALIZATION-20260910 关于界面返工

- Windows 按当前用户的系统界面语言（非区域格式）选择中文或英文；所有中文地区语言归入中文，其他语言与检测失败使用英文。
- 关于入口、标题、版本字段、布尔值、公共基础功能名及运行活动提供中文/英文呈现，作者固定 `Alex&Xixi`；技术版本号、Git 提交与基线编号保留原值。机器接口 `BuildInfo.as_fields()` 不变。
- `tools/verify_about_localization.py` 标准库 headless 验证先因模块缺失失败，实施后 4 项通过（包含中文地区、英文/日文、检测失败、所有 Activity、机器字段不变和真实窗口 About 接线）；接入 Windows 打包前门禁，不执行旧 pytest。
- 仅更改关于呈现；猫咪素材、动画与文件处理未改变。Windows 原生语言读取和真实窗口视觉待 Windows 实机验收，EXE 尚待 Actions 构建，不宣称完成实机验收。
## 2026-09-10 耳朵发布契约复核

- 延续 `2.1.1-test` / 耳朵防触摸候选；父提交 `227497fb571da4af20b9acdc33a3d40294fc91e1`。
- 修复旧 SHA、基础提交、预览尺寸及 headless 测试接口断言；13 项聚焦测试和 3 项真实运行校验通过。
- 158 个基线素材 hash 保持不变；本次未更换动画，无新的视觉批准。完整旧测试套件与 Windows 实机验收不宣称通过。详见 `docs/ear-touch-20260910.md`。

## 2026-09-10 双耳防误触与中断闭环

- 猫自身左右耳分别覆盖按下候选、同耳松开确认；按住不播放，移出后松开不触发。
- 移出窗口、失焦、打开菜单和退出均取消正在播放的耳动作并恢复精确中性帧；透明像素继续不进入 Win32 输入区域。
- 未修改已验收头、眼、身体或耳朵 raster 数据。Linux 预览只用于自动/人工证据检查，Windows EXE 构建与 Windows 实机视觉验收继续作为两个独立门禁。

## 2026-09-11 公共基础发布来源与 Windows 自动化门禁

- 公共基础恢复修复的当前已发布来源提交为 `1a18477faa4caa28170e648437d7cb8b39612ac0`。本分支按用户提供并核验的完整文件同步 `foundation/animation.py`，其 Git blob 为 `a58b54aa1d3cb1bfe1b88e9554697a417e7e2dcb`；来源清单保留最初 29 文件交接记录，并单列这次真实覆盖，不把换标签冒充同步。
- 同步后的动画通道在播放、取消或恢复回调异常时仍释放逻辑和通道所有权，旧 token 的恢复调用不会清除新活动。既有双耳接线及已验收素材保持不变。
- Windows workflow 在打包前运行上述公共动画恢复回归，以及左右耳按住/释放、指针离开、失焦、菜单中断、迟到回调和透明区穿透回归；通过后仍只构建并上传一个耳朵单功能 EXE。自动化、Windows 构建/artifact、实机交互和视觉验收继续分别记录，后两项仍待用户完成。
## FOUNDATION-RECOVERY-20260911 增量

- 更正上一轮仅记录来源而未同步文件的问题：现已实际同步公共基础 CORE `1a18477faa4caa28170e648437d7cb8b39612ac0` 的 `foundation/animation.py`，其 Git blob 为 `a58b54aa1d3cb1bfe1b88e9554697a417e7e2dcb`；本候选保留现有饥饿、真实图形帧、共享状态和 400 条文案功能。
- Windows 候选工作流增加隔离饥饿验收，覆盖 UTC/离线重启、保存失败与奖励幂等、文案唯一性及交互抢占恢复；通过后才构建和上传唯一单文件 EXE。
- 代码与像素自动化证据、Windows 构建、artifact、Windows 实机运行和用户视觉验收继续分项记录；基础 Actions 与本分支 Actions 的远端结果不得由本地验证替代。

## HUNGER-VALIDATION-20260910 增量

- 基于 `5293ccb32aa9e123b6a3cdfa6e5c35bec7d05850` 继续验证四档饥饿、离线重启、奖励幂等及交互抢占恢复。
- 修复关闭 checkpoint 两次读取 UTC 的竞态：现在一次取时同时用于衰减快照和新锚点，避免时钟在两次读取之间前进时少扣饥饿值。
- 更新已过期的独立存储/旧绘制动画测试，使饥饿测试覆盖当前公共 `ApplicationServices`、真实图形帧及候选 EXE 契约；饥饿相关测试为 28 项通过。
- 四档语料合计 400 句且全局无重复；每档各 100 句、长度上限及严重/危急档禁用嬉笑结尾均有自动化检查。
- 来源重建后图形门禁验证五个去重运行时 PNG、640×768 固定锚点、首尾中性帧、限定嘴/泪可变区域、逐像素轮廓 Alpha 和区域外 RGB 不变；这些是自动化像素证据，不代替 Windows 实机视觉判断。
- Linux 容器没有 PowerShell/Windows 运行时且仓库没有远端，无法在本地构建 Windows EXE 或产生 Actions run/artifact；Windows 构建成功、artifact 下载/哈希和用户实机视觉验收继续分别保持待处理，PR 保持开放。

## HUNGER-CORPUS-20260910 增量

- 继承 PR #6 提交 `fa32a782bea1ef03e6b4815c80673ee44b292b16`，本节随语料增量提交记录。
- 四档各 100 句独立短中文语料，移除 10×10 拼接及严重档嬉笑；最长不超过 18 字符。
- TDD：去模板化测试先红（实际仅 10 个主句），改后 7 项反馈测试全绿；共享状态验证通过。
- 保持 20%/每降 2%、严格低于 10%、低于 1% 常驻及满值跨入规则。
- 仅文字质量增量；全猫饥饿动画、Windows 实机及视觉验收仍未完成，不替换批准素材，不合并 PR。
## 2026-09-09：期待真实帧与公共基础接入

- 当前独立候选：`桌面宠物_期待逐帧与公共基础接入.exe`，版本 `2.1-expect-frames.1`。以下新增记录取代旧的 `NOT_INTEGRATED` 状态；旧轮次结果保留作历史。
- 公共文件使用 PR5 `f617765` 与后续本地 `6af8446`，包含实际单一状态、时钟、协调器、STA 文件工作线程、图形恢复及受保护事务菜单修复；`eye_runtime.py` 和 `layered_window.py` 配套接口一并导入。
- 从原期待云端任务取回生成脚本和清单，本地重建五张源 PNG；五个 SHA-256 与原任务清单逐张精确一致。源图包以文本保存，原 158 个认可素材不变。
- 已将源帧相对默认姿态的局部变化预先合成到真实 640×768 中性画布；运行帧 0 与实际中性图逐像素相同，未变动身体区域保留，避免切换时脸部/画布跳动。运行 PNG 由脚本还原且不重复提交。
- 进入用 0→1→2→3，前三步各 50ms；悬停 3/4 各 100ms；离开用 2→1→0 各 50ms。取消、失焦、异常、事务抢占和 Drop 立即恢复；粒子单独绘制，角色表情只读实际帧。
- 唯一 OLE owner 使用真实 CF_HDROP 路径复制与释放，在共享 STA 线程读取文件身份和大小；无回收、移动、复制、文件内容读取或奖励。完整单文件头部命中且未满饱腹时才显示 Copy。异步结果会重新检查当前会话、坐标、饥饿和活动优先级。
- Drop 只发出一次复制值事件供后续 FEED 消费。独立 EXPECT 版本不包含 FEED 消费者，也不重复启动 HUNGER 图形播放器；共享健康/tear 恢复已验证，泪眼画面联动留给总集成。
- 二级调试入口提供 3 秒期待动画预览，不改饥饿状态或真实文件；正常跟随在预览结束后恢复。
- 本地通过：真实源帧哈希还原、五帧 RGBA/画布/像素校验、原中性图一致、身体区域不变、共享拖放生命周期与迟到回调/满值/极端饥饿/优先级/一次性交接门禁、公共图形合同、Python 编译与 diff 检查。
- 画面已查看全部五帧黑白底联系表，身体位置稳定；眼部变化较细微，源素材为预先加工眼层生成的图形帧。Windows 构建、实际 OLE、DPI/多屏及用户视觉验收仍待新候选验证，不能用本地门禁代替。

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

## V2.1-EARS 独立增量

- 基础标签：`BASE-001`；文档基线：`V2.1-EARS`；测试版文件名：`桌面宠物_双耳点击反馈_REPAIR-20260906.exe`。
- 唯一新增功能是左右耳独立点击反馈：当前合成帧的 Alpha 与左右耳保守多边形相交形成精确遮罩，透明像素不命中；按下、保持、松开以及快速连点均由可取消状态机处理。
- 按住移出、窗口失焦、用户触发其他动作、运行时中断和退出统一恢复中性态；逐帧原生 Alpha 输入区域避免透明窗口背景形成大矩形鼠标拦截。
- 未修改转头角度、minimum-jerk、猫头、猫身、眼睛、Alpha 源素材、头颈或眼球跟随；仍未实现前肢、舔手、饥饿、拖放和文件喂食。
- 耳朵参数因正文没有指定数值，集中记录在 `EarFeedbackConfig`，采用保守测试值并标记为**待 Windows 实机视觉验收**；不得把自动像素测试写作用户视觉批准。
- 按用户决定，Windows Actions 与 `build_ears_candidate.ps1` 完全跳过 pytest、旧自动测试和旧资源验证，直接执行 PyInstaller；随后只校验唯一 EXE、精确文件名、50 MiB 大小上限与 SHA-256，并上传单文件 artifact。产物明确标记为**未自动测试、等待用户 Windows 实机验收的候选版**。
- Linux 自动证据：双耳/打包/元数据/Alpha 输入区域聚焦测试 18 项通过，耳朵窗口生命周期聚焦测试 6 项通过；头眼与 V2.1 相关回归 323 项通过、3 项平台跳过、1 项既有眼部 Alpha 金图失败。完整收集另受环境缺少 PyInstaller/NumPy 且网络代理 403 阻止安装影响，产生 3 个收集错误。旧失败只记录，未删除测试或修改金图。
- PR 二进制门禁：相对 V2.1 基线的全部变更必须是文本；耳朵预览仅在需要时生成到测试或人工指定的临时目录，不进入当前 Windows 候选工作流。全部 158 个既有 `assets/` 文件以 Git blob 哈希逐项锁定，双耳逐像素命中、DPI、透明边缘与独立 EXE 契约继续由发布契约测试覆盖。
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
- INTEGRATE-20260906 第二轮：请求的 PR5 提交 `1a02fe9680f28dda07add8b96c78445e0b3c0f59` 不在本地对象库；Git fetch、raw 和 codeload 均被代理 403 拒绝，web retrieval 返回 401。未读取 `docs/v21-runtime-api.md`，因此没有将猜测接口冒充实际 `create_application_services` / `ApplicationServices` 接线；详见 `qa/drag-expectation/pr5-fetch-blocked-20260906.md`。
- 转头角度不属于本增量门禁且未调整；旧视觉回归失败只记录，不删测试、不改金图。

## 验证与状态

- BASE-001 聚焦自动测试：35 项通过（角度、minimum-jerk、运行时集成、版本、依赖声明、Windows 工作流契约）。
- Python 编译、素材 158 文件 SHA-256 前后清单对比和 `git diff --check`：通过。
- 云容器完整收集受缺少 PyInstaller/NumPy 且网络 403 阻止安装影响；排除三个依赖收集文件后的历史套件结果为 568 通过、3 跳过、15 失败、42 错误，其中包含无 DISPLAY 的 Tk 测试和当前已批准素材与旧黄金基准不一致。以上不被写作通过，也不作为 Windows 验收。
- Windows Actions：待更新 PR #9 后在 `windows-latest` 构建未自动测试候选版，校验唯一 EXE、精确文件名、大小与 SHA-256 并上传 artifact；不把打包成功写作自动功能测试通过。
- Windows EXE 真实运行与桌面视觉验收：**待用户验收**。Linux 云容器结果不作为 Windows EXE 或视觉验收证据。
- Git：BASE-001 实现提交为 `5a7338d8d8c53b880a4a05ea783b1352df4add18`；PR 因当前容器没有 GitHub 凭据/远端而待创建。
- Git：BASE-001 实现提交为 `5a7338d8d8c53b880a4a05ea783b1352df4add18`；本增量停在可更新现有 PR #9 分支的提交状态，不自动合并。

## REPAIR-20260906-V21-EARS

- 用户已拒收此前 7 个 EXE；此前“功能完成、仅待打包/验收”的结论撤回。
- 已修复本分支可独立完成的耳部实质：猫自身左右命名、动态头姿 landmark 映射、按下候选到松开确认、DPI 系统拖动阈值、三次抖动、外甩减速、缓出恢复、5% 内回弹、0.55 秒总时长、0.5 秒冷却、忙时忽略、取消令牌上下文与精确中性恢复。
- `ear_asset_manifest.json` 是文本资产清单，记录素材 ID、版本、512×768 尺寸、耳根、层序、Alpha 规则、人工遮罩与安全恢复姿态；原认可素材文件未改写。
- 云端实际调用探针已走通 `PetWindow` 按下候选 → 松开确认 → `EarFeatureAdapter` → 局部纹理合成 → renderer → 精确中性态，共观察到 27 次渲染提交；动态头姿探针观察了中心、+18° 和 -18° 下的独立耳区映射。它们不是 Windows 实机验收。
- **未完成公共依赖：** 当前没有 PR5 `ActivityCoordinator`/`InputRouter` 基础提交。现有 `_request_ear_action()` 是待总控替换的临时接线点；公共活动优先级、CriticalHungry/InputGate、四元完成核验和统一 Recovery 未接入前，不得发布为可验收完成版。
- Windows 打包脚本要求 `V21_FOUNDATION_COMMIT` 与真实 `docs/v21-runtime-api.md`；缺失时主动失败，不生成候选。取得 PR5 后还必须按文档补上 `create_application_services`/`ApplicationServices` 初始化验证。候选文件名预留为 `桌面宠物_双耳点击反馈_REPAIR-20260906.exe`。

## INTEGRATE-20260907 公共基础与双耳接线

- PR5 源码补丁交接标识为 `e178f371bd2da1c0b4e892609acfdf79bfcab450`，基准为 `c3b218df9dd0cfc84d96231701e771f0382388e1`；29 个重建文件均以 `git hash-object` 与交接 blob 逐项一致。`docs/v2.1-ears-foundation-source.json` 记录来源和 blob 清单；它不伪称当前 Git 历史包含远端提交。
- `main()` 通过真实 `create_application_services(BuildInfo.load_embedded())` 创建唯一 `ApplicationServices` 并注入 `PetWindow`。普通耳点击与调试耳命令都发布 `input.ear`，由唯一运行时队列消费，再由 `ActivityCoordinator` 发放带活动版本、取消 ID、动画 ID 的令牌。
- 双耳共用 `EAR_ACTION` 活动和 `ears` 动画通道；活动中再次点击被忽略，完整中性恢复后执行 0.5 秒 adapter 冷却。Critical health 与更高优先级活动拒绝耳动作；高优先级抢占经协调器 recovery 取消定时器并恢复精确零角。
- 命中遮罩仍由文本人工多边形与当前合成帧 Alpha 相交，并通过当前头部 compositor 的逐帧映射重建；耳动画保持三次抖动、外甩减速、缓出恢复与不超过 5% 的回弹。
- 已修复耳候选的实际身份打包路径：PyInstaller 同一份 `build_identity.json` 同时供 `BuildInfo` 与运行状态读取，包含测试/调试标志；工作流固定记录已核验的 PR5 来源提交，不依赖未配置的仓库变量。
- Linux 仅进行语法、导入、临时目录调用链、素材哈希和静态打包契约检查；按用户授权未运行 pytest。Windows PyInstaller、实际 Alpha 命中、动画观感与用户实机验收仍待 Actions/用户执行。


## V2.1-PAWS 独立增量

- 基础标签：`BASE-001`；统一起点：`c3b218d`；文档基线：`BASELINE_V2.1.md`。
- 启用功能仅为“双前肢按压鼠标”：两个独立、非矩形、可审查 JSON row-RLE 逐像素 Alpha 遮罩在运行时确定性还原；按下、保持、推动、松开、取消与用户抢占状态；物理虚拟桌面边界和既有 `ClipCursor` 交集；所有终止路径执行幂等释放。
- 测试版调试入口：右键一级“调试”菜单的直接二级命令“左前肢按压/右前肢按压”，与正常前肢点击调用同一业务入口；目标文件名为 `桌面宠物_双前肢按压鼠标_20260906修复候选.exe`。未启用耳朵、舔手、饥饿、拖放或文件喂食。
- 本候选版依用户决定明确标记为**未自动测试**：候选 PowerShell 与 Windows Actions 完全跳过 pytest 和旧测试，只执行 PyInstaller 打包、唯一 EXE、精确文件名、大小和 SHA-256 检查。真实 Windows 桌面运行与功能验收由用户本人执行。
- 已认可猫头、猫身、眼睛、Alpha、头颈、眼球跟随和转头角度没有调整；旧视觉回归失败只记录，不删除测试、不修改金图。
- 相对 `c3b218d` 的发布差异必须全为文本；既有 158 项 `assets/` 基线 SHA-256 由 `assets/v2.1-baseline.sha256` 固定，源码门禁可独立验证，但依用户决定不在本次候选构建或 Actions 中运行。PAWS 预览 PNG 不跟踪，可按需由脚本写入临时目录。
- Windows Actions 候选打包：待 PR #10 更新后运行；自动测试：**未运行**；Windows 实机功能与视觉验收：**待用户本人验收**。

### REPAIR-20260906

- 已撤销旧候选的完成判断：正常窗口前肢 Alpha 点击现接入按下候选、系统 DPI 拖动阈值、同侧松开与单爪业务入口；超阈值只拖窗口，动作锁期间其它爪点击被消费且不排队。
- 单爪阶段固定为抬起 0.12 秒、停顿 0.08 秒、按压 0.16 秒、恢复 0.24 秒、冷却 0.6 秒；每帧从默认图像与固定锚点合成，只变换选中爪，并以邻近上肢纹理补原位置。
- PAWS 光标接口现仅允许读取/设置位置及读取显示器、裁剪区和指针标称高度；已移除按键合成、光标捕获和 `ClipCursor` 修改。总位移按 `clamp(14 × height / 32, 8, 28)` 计算且只沿屏幕 y 正向，用户偏差超过 4 物理像素后不拉回、不重试。
- PR5 公共 `ActivityCoordinator`/`InputRouter`/权限策略尚未进入本分支；所需窄接口记录于 `docs/V21_PAWS_FOUNDATION_API.md`。在统一基础提交接入前，本分支不得描述为可验收完成版。
## 已撤回的 V2.1-CORE 未接线增量记录

- 基础标签：`V2.1-CORE`；启用功能仅为 `common-foundation`。
- 当时仅新增了未连接运行程序的公共契约；该状态已被用户拒收，并由下方 REPAIR-20260906 接线替代。
- 明确未新增耳朵、前肢、舔手、饥饿、拖放、喂食、自主动画或生产用户文件处理。测试持久化仅使用 pytest 临时目录。
- 调试时间和状态注入仅允许测试版或显式调试开关；生产随机源使用系统熵且没有固定种子。
- 原未接线候选名为 `桌面宠物_V2.1公共基础架构.exe`，已被 REPAIR-20260906 撤回，不得再交付。修复候选版本资源包含产品版本、UTC 构建日期、Git 短哈希、基础提交、基础标签、启用功能、测试版状态、调试菜单状态和 `BASE-001` 文档基线。
- Windows Actions 的真实构建、唯一 EXE 大小/SHA-256、下载复核及真实桌面视觉验收均须在提交和 PR 后分别记录；Linux 不作为 EXE 或视觉通过证据。
- 两项旧视觉金图回归仍是已知基线问题；不得通过删除或放宽测试、更新金图或修改已认可素材掩盖。
- 本增量聚焦门禁：28 项通过；Python 编译、158 个素材文件相对起点 SHA-256、`git diff --check` 均通过。容器完整收集仍缺 PyInstaller/NumPy；排除三个依赖收集文件后的检查点为 584 通过、3 跳过、12 失败、42 错误，失败包括既有素材/金图差异、无 DISPLAY 的 Tk 测试及依赖 NumPy 的 QA，不写作通过。
- 旧单功能 EXE 已撤回。Windows 工作流仍明确以 `build_v21_core.ps1 -SkipTests` 构建；旧基线自动测试不再阻塞修复候选 EXE 打包和 artifact 上传，但其已知失败仍保留且不修改。

## REPAIR-20260906 公共基础接线候选

- 撤回“仅提供未调用抽象即可完成”的旧判断。真实入口现在由 `main()` 创建一个 `ApplicationServices`，并注入 `PetWindow`；窗口点击、菜单、移动、动画完成、区域更新、调试、OLE 生命周期、状态保存和退出均调用共享运行时。
- 状态采用唯一 Tk 串行事件队列和唯一 `ActivityCoordinator`，Health、Activity、Eye、Mouth、Tear、Particle、InputGate 正交；活动令牌携带版本、取消 ID 和动画 ID，旧完成回调不能覆盖当前活动。
- Windows 使用 PerMonitorV2/asInvoker manifest；当前 Alpha 生成原生窗口命中区并扩展 16 个物理像素。OLE 注册只提供诊断和拒绝 drop 的公共能力，不读取或操作用户文件。
- 测试版右键菜单提供“关于 / 运行状态”和一级“调试”；调试打开一个可滚动二级列表。后续六项功能未接入的命令明确禁用，不伪造动画。
- 新候选名：`桌面宠物_公共基础接线与版本识别修复.exe`。该候选未经旧 pytest/逐像素套件门禁，仍须 Windows 构建检查和用户实机验收；不能称为已验收完成版。
- REPAIR 静态/临时目录证据：入口接线审查、Python 编译、事件优先级与物理恢复、四字段播放身份、损坏存储/备份/日志、STA 工作队列关闭、manifest XML 和 158 项素材 SHA-256 均已检查；按授权未运行 pytest。
- 尚未完成的外部门禁：本容器不能验证 Windows OLE 消息、PerMonitorV2 多屏切换、Alpha/16px 原生命中、旧实例激活、真实菜单键盘操作、PyInstaller EXE 启动和用户视觉验收。饥饿、舔手、喂食、耳朵、前肢、期待仍由 PR6～PR11 接入，本候选中明确禁用，不得当作已完成功能。

## CORE-DATA-REPAIR-20260907 数据恢复增量

- 统一数据目录改为 `%LOCALAPPDATA%/DesktopPet`，固定包含 `state.json`、`state.backup.json`、`settings.json`、`feed-journal.jsonl`、`logs/` 和 `recovery/`。
- 加载顺序固定为正式状态、有效备份、脱敏事务日志；正式与备份双损坏时，日志中的未完成事务恢复到 `pending_transaction`，启动必须进入 `TransactionReview`，不能默认为无事务。
- 保存前先验证候选状态；只把验证通过的旧正式状态原子写入备份。损坏正式状态不会覆盖有效备份，损坏输入保留到 `recovery/`。
- `SharedState.commit/update` 是唯一共享提交入口：先完成持久化，成功后才发布新内存快照；兼容的 `ApplicationServices.close(state=None)` 忽略旧调用者副本并保存当前最新快照。
- 旧 `%LOCALAPPDATA%/DesktopPetV21` 文件仅在新目标缺失时复制迁移，不删除、不改写、不覆盖旧文件；普通日志采用 2 MiB、5 备份轮转并脱敏完整路径。

## FRAME-CONTRACT-20260907 逐帧图形播放器增量

- 撤销“不得新增动作素材”的错误门禁；默认认可素材仍按哈希锁定，但六个功能分支可新增真实 RGBA 全帧或带逐帧补洞层的局部帧。
- 真实 `AnimationController → PetWindow` 播放链现读取 `AnimationSequence/FrameStep`：帧序、每帧毫秒、有限循环段、源画布锚点和 full/local 模式均显式声明；取消、超时或中断继续通过活动令牌恢复认可默认帧。
- `assets/keyframes/playback.json` 已把现有 jump/squash/shake 图形帧接入新时序接口；它只证明公共播放器真实可达，绝不冒充舔手、耳朵、前肢、饥饿嘴部、进食或期待动作。
- 公共播放器证据位于 `qa/v21-frame-player/`：18 帧联系表、连续 GIF 和逐帧 SHA/时长报告。六项新功能的正式动作帧当前仍缺失，必须由对应 PR 提供并经用户验收后才可报告动画完成。

## GRAPHIC-ACTIVITY-REPAIR-20260909 图形活动接线修复

- 修复窗口播放器把所有活动硬限为 `BODY_ACTION` 的阻塞：舔手、普通/严重饥饿和进食现使用各自真实活动令牌播放，不改写为身体活动。拖放期待须保留实时眼球跟随，不接入会暂停眼球的全帧身体通道。
- 自定义动作完成时先验证活动/版本/取消 ID/动画 ID，再恢复认可默认帧；迟到完成回调不得覆盖新动作，取消和超时同时恢复播放器与活动状态。
- `verify_graphic_animation_contract.py` 新增真实窗口请求→串行队列→活动通道→逐帧播放器→完成/中断恢复门禁。修复前已复现功能活动被拒和默认帧未恢复；修复后两项现有 non-pytest 门禁通过。Windows 构建即使使用 `-SkipTests` 仍执行这两项轻量门禁，不运行旧 pytest 整套。
- 此增量仅修公共播放链，不代表六项素材或 Windows EXE 视觉验收通过；Windows 构建与用户实机验收另记。
- 尚未完成的外部门禁：本容器不能验证 Windows OLE 消息、PerMonitorV2 多屏切换、Alpha/16px 原生命中、旧实例激活、真实菜单键盘操作、PyInstaller EXE 启动和用户视觉验收。该段 CORE 候选中的耳朵入口已由上方 V2.1-EARS 接线替代；饥饿、舔手、喂食、前肢、期待仍由其他功能分支接入。
# PAWS rework checkpoint 2026-09-10

PR #10 follow-up: pointer displacement is now 2.5x (35 nominal, 20–70 bounds).
Complete-cat frame import/runtime support has focused automated coverage.
New art and Windows/user visual acceptance remain pending; existing animation
art is unchanged. See `qa/v2.1-paws/rework-2026-09-10.md` for evidence and limits.

## PAWS-CI-CONTRACT-20260910

- PR #10 base `5f68d7176c5666c4cebb9995725de91239837ef8`: reproduced the CI runtime assertion expecting y=114 after starting at y=100. The approved 2.5x displacement is 35 px, so the independent acceptance endpoint is y=135; all per-step x/y bounds remain asserted.
- CI-identical `python tools/verify_paws_runtime.py` now passes, including queue/window playback, preemption, stale callbacks, pointer takeover and 158 immutable baseline assets. Focused paw press/compositor/full-frame import/release suite: 25 passed (existing Pillow deprecation warnings).
- New exact candidate filename: `桌面宠物_双前肢位移2.5倍与校验修复_20260910候选.exe`; build, spec, version resource, smoke test, Actions upload and release checks agree. Previous EXEs remain untouched.
- This checkpoint is Linux automated evidence only. Windows build/artifact and user visual acceptance remain separate gates. Existing animation art is unchanged; this is NOT a full-cat animation repair release.

## PAWS-2.5X-BOUNDARY-20260910

- Candidate identity is `PAWS-2.5X-BOUNDARY-20260910`, product version `2.1.3-paws`, exact EXE `桌面宠物_双前肢位移2.5倍_释放与边界验证_20260910候选.exe`, and artifact `v2.1-paws-2.5x-boundary-candidate` with 14-day retention.
- Focused regression coverage records same-paw mouse release, release while a physical button remains down, input cancellation/takeover, focus-loss cancellation wiring, idempotent exit after cancellation-notification failure, cursor API failures, 2.5x endpoint scaling, negative-coordinate DPI/multi-monitor coordinates, monitor/ClipCursor intersection, and invalid native rectangles.
- Native bounds with zero or inverted width/height now fail closed before clamping. Cancellation establishes the idle/closed terminal state even if the external ownership callback fails, preventing focus loss or shutdown from leaving the PAWS controller active.
- Actions writes `candidate-evidence.json` beside the sole EXE with the full commit, run URL, byte length, SHA-256, automated-build result, and separate pending Windows-desktop acceptance field. A successful Actions build is not Windows interaction or visual acceptance.
- Linux cannot produce or honestly validate the Windows single-file EXE. The workflow build, isolated Tk startup, artifact hash, real Windows DPI/multi-display interaction, and user visual acceptance remain separate evidence gates until an Actions run and physical review exist.

## 已撤回的独立增量结论

- 2026-09-05 所记录的 `桌面宠物_饥饿值与饥饿动画.exe` 候选结论已由用户实机拒收并撤回；它不得继续作为当前交付或完成证据。
- Windows Actions 仍完全跳过 pytest/旧自动测试；当前返工状态以下节为准。

## REPAIR-20260906-V21-HUNGER 状态

- 撤回此前饥饿功能完成结论：旧 0..10000/冻结调试时钟/几何弧线实现已返工。
- 新实现使用 0..100000、真实 UTC 120 分钟衰减、四态边界、嘴内部/舌头/姿态锚定泪层与统一状态 adapter。
- PR5 foundation commit 尚未统一；当前为功能分支修复代码，不发布为可验收完成版。最终 Windows 验收由用户本人执行。

## V2.1-LICK 独立增量

- 行为合同：明确交互空闲 60 秒后抽取 `90..300` 秒等待；普通鼠标经过/头眼跟随不重置。生产一轮 `3..20` 次，调试构造固定 3 次。
- 用户认可的单侧 12 帧整帧原稿以每行不超过 120 字符的 Base64 文本保存；不镜像整猫伪造另一侧，不提交 PNG/GIF/派生帧。
- 基础审计：当前分支及可见 refs 中没有 `RuntimeContext`、`ActivityCoordinator` 或健康服务；不把局部播放器冒充公共基础，也不另建全局状态机。候选沿用现有 `RuntimeEyeSession` 的唯一 tick、`following/playing` 所有权与输入中断路径。
- 构建：解码后核验原 PNG SHA，确定性生成并检查 12 帧，将生成帧装入独立候选 `桌面宠物_舔手逐帧动画恢复.exe`；验收候选通过明确测试元数据开放“调试 → 左前爪舔手（3次）”，生产默认关闭。
- 保留范围：canonical idle SHA 保持 `48f710b9811ebf6edc60764bc7a52fd1af4274a761589677df365450d8a2fec7`；未修改已认可头身眼素材、转头角度或 minimum-jerk。
- 远端事实：当前仓库未配置 remote/remote refs，不能把本地提交或 `make_pr` 元数据记录视为已推送。
- 待完成门：Windows Actions 构建、候选实际大小/SHA-256 与用户 Windows 实机视觉验收。Linux 容器不替代这些门；不合并。
- Windows run `34304052388` 构建成功，实际 EXE SHA-256 为 `712bdfbbf38ab9adabe4899a414f66c5cdebdf5eaf1b28012ed6e8eaf1ab4be5ff`，但因 `04.png` 缩小及脚部碎片被视觉拒收；本地已按每格主体连通域修复，等待新 Windows artifact 复核。
# 2026-09-10 resumed grooming asset work

PR12 adds an opt-in full-cat RGBA importer path; legacy manifests and approved
images are unchanged. Seven focused tests pass (full-frame input and prior QA).
New generated grooming art was rejected for RGB checkerboard and identity drift.
This is NOT a completed animation repair and has no new Windows visual approval.
# EXPECT 后续修复记录（2026-09-10）

版本范围：V2.1-EXPECT。退出帧渲染/调度失败，以及退场期间拖回窗口时的取消/渲染/调度失败，均立即释放期待活动并恢复默认显示；菜单与普通动作不抢占期待，受保护事务仍可抢占且期待不会复活。不更改批准素材、文件安全区域或外围首次触发限制。自动证据：退出/重入异常与仲裁定向回归 6 项通过、`verify_drag_runtime.py` 通过。Windows 构建与用户视觉验收尚待本提交后验证；全猫口水新帧未接入。

## 2026-09-11：PR #5 发布来源与 Windows 回归门禁

- 公共基础 PR #5 的最新正式发布来源为完整提交 `1a18477faa4caa28170e648437d7cb8b39612ac0`。已按核验完整源文件同步 `src/desktop_pet/foundation/animation.py`，同步后 Git blob 为 `a58b54aa1d3cb1bfe1b88e9554697a417e7e2dcb`；播放、取消或恢复回调异常均释放逻辑所有权，旧 token 的恢复不能清除替代活动。
- Windows workflow 在构建前运行 CORE 动画播放/取消/恢复异常、旧 token 隔离、OLE 进入/离开/Drop、退出与重入回调异常恢复、重复/迟到触发、头部限定交接以及不修改共享饥饿状态的自动回归。候选仍不安装 FEED consumer，因此不会移动、删除或回收文件；`CF_HDROP` 只复制路径值并及时释放 OLE medium。
- 自动代码验证、Windows 构建、artifact 上传、Windows 实机 OLE/DPI/多屏验证和用户视觉验收分别记录。后四项必须等待真实 Actions/Windows 证据，不以 Linux 测试或元数据替代。

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
