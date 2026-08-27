# 桌面宠物 6 帧无粉边版 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付一个复用逐像素 Alpha 窗口、每组动作严格 6 帧、可直接双击运行且不覆盖 30 帧版的独立 EXE。

**Architecture:** 保留当前 `LayeredWindowRenderer` 和交互层，只把运行时资源根切换到 `assets/keyframes`，把帧契约改为 6，并恢复 90 ms 节奏。构建验证器以 direct 布局核对 18 张关键帧哈希，PyInstaller 仅收集这 18 张动作图片。

**Tech Stack:** Python 3.12、Tkinter、Pillow、Win32 ctypes、Pytest、PyInstaller、PowerShell。

## Global Constraints

- 不改动现有 `codex/desktop-pet` 30 帧分支和未跟踪 QA 文件。
- 三组动作各为 `00.png` 至 `05.png`，每张 `512×768 RGBA`。
- 主窗口必须继续使用 `UpdateLayeredWindow(..., ULW_ALPHA)`，不得恢复 `-transparentcolor`。
- 成品名必须为 `桌面宠物-6帧无粉边版.exe`。
- 不把 NumPy 或 OpenCV 打进 EXE。

---

### Task 1: 6 帧运行时契约与节奏

**Files:**
- Modify: `tests/test_assets.py`
- Modify: `tests/test_animation.py`
- Modify: `src/desktop_pet/assets.py`
- Modify: `src/desktop_pet/animation.py`

**Interfaces:**
- Consumes: `asset_path(*parts: str) -> Path` 和 `assets/keyframes/<action>/<00..05>.png`。
- Produces: `runtime_frame_root() -> Path`、`FRAME_COUNT = 6`、默认动画间隔 `90` ms。

- [ ] **Step 1: 写失败测试**：要求素材加载器只接受 6 帧、默认素材根为 `assets/keyframes`，并要求控制器默认调度 90 ms。
- [ ] **Step 2: 运行目标测试并确认失败**：执行 `python -m pytest tests/test_assets.py tests/test_animation.py -q`，预期因当前 30 帧契约和 33 ms 默认值失败。
- [ ] **Step 3: 最小实现**：把 `FRAME_COUNT` 改为 6，新增 `runtime_frame_root()` 并用于默认加载；把 `AnimationController` 默认间隔改为 90 ms。
- [ ] **Step 4: 运行目标测试并确认通过**：同一命令必须 0 失败。

### Task 2: 6 帧哈希验证与构建打包

**Files:**
- Modify: `tests/test_validate_assets.py`
- Modify: `tests/test_build_script.py`
- Modify: `tools/validate_assets.py`
- Modify: `build.ps1`
- Modify: `desktop_pet.spec`
- Modify: `README.md`

**Interfaces:**
- Consumes: `assets/keyframes/manifest.json` 中每张图片的 `sha256`。
- Produces: `validate_assets(..., frame_count=6, keyframe_layout="direct")` 和只含 18 帧的独立 EXE。

- [ ] **Step 1: 写失败测试**：构造临时 6 帧目录和 direct 清单，要求验证器接受 18 帧并拒绝缺帧/哈希变化；要求构建脚本使用 6 帧 direct 模式，spec 收集 `assets/keyframes` 且 EXE 使用独立名称。
- [ ] **Step 2: 运行目标测试并确认失败**：执行 `python -m pytest tests/test_validate_assets.py tests/test_build_script.py -q`。
- [ ] **Step 3: 最小实现**：为验证器增加 `frame_count` 与 `keyframe_layout` 参数和 CLI；direct 模式用同名文件核对清单哈希。更新构建脚本、spec 和 README。
- [ ] **Step 4: 运行目标测试并确认通过**：同一命令必须 0 失败。

### Task 3: 透明轮廓、完整回归与交付

**Files:**
- Modify: `tests/test_clean_colored_edges.py`
- Create: `qa/six-frame-alpha-validation.json`
- Output: `dist/桌面宠物-6帧无粉边版.exe`

**Interfaces:**
- Consumes: 18 张正式关键帧、逐像素 Alpha 渲染器和构建脚本。
- Produces: 残边统计、测试证据、EXE 哈希和启动探针结果。

- [ ] **Step 1: 写失败测试**：把正式关键帧残边复扫范围改为三组各 6 张，并断言检测总数为 0。
- [ ] **Step 2: 运行残边与分层窗口测试**：执行 `python -m pytest tests/test_clean_colored_edges.py tests/test_layered_window.py tests/test_window.py -q`。
- [ ] **Step 3: 运行完整测试和素材验证**：执行 97 项回归及 `tools/validate_assets.py assets/keyframes --frame-count 6 --keyframe-layout direct --keyframe-root assets/keyframes --report qa/six-frame-alpha-validation.json`。
- [ ] **Step 4: 构建并探测 EXE**：运行 `build.ps1`，启动发布 EXE，检查单实例、逐像素 Alpha 标志、无颜色键、初始/滚轮尺寸和正常退出。
- [ ] **Step 5: 生成交付证据**：记录 EXE 完整路径、字节数、SHA-256、分支和提交号。
