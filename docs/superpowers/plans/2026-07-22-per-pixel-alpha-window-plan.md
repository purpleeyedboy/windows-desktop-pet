# Per-Pixel Alpha Window Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Tk color-key transparency with Win32 per-pixel Alpha while preserving every desktop-pet interaction and producing a verified double-clickable EXE.

**Architecture:** Tk remains the owner of the native top-level, event loop, menu, input bindings, timers, and bubble. A focused `LayeredWindowRenderer` converts Pillow RGBA to premultiplied BGRA and calls `UpdateLayeredWindow`; `PetWindow` injects that renderer and never uses `ImageTk`, a character Label, or a color key.

**Tech Stack:** Python 3.12, ctypes Win32/GDI/User32, Tkinter, Pillow, pytest, PyInstaller.

## Global Constraints

- Target Windows 10/11 and use `UpdateLayeredWindow(..., ULW_ALPHA)` with 32-bit top-down DIB data.
- Preserve smooth LANCZOS semi-transparent edges; do not binarize Alpha or composite against a key color.
- Remove character-window `#ff00ff`, `-transparentcolor`, `LWA_COLORKEY`, `ImageTk.PhotoImage`, and Tk character `Label` paths.
- The speech bubble is an opaque white borderless tool window and does not call `-transparentcolor`.
- Keep borderless, default topmost, drag, click action cycle, wheel sizing, size menu, topmost toggle, bubble placement, single-instance, and exit behavior.
- Use a 33ms animation interval for each 30-frame action, approximately one second total.
- Every GDI DC, bitmap selection, bitmap, and screen DC acquired during render is restored or released on both success and failure.
- Runtime dependencies remain Tkinter, Pillow, and the standard library; OpenCV/Numpy stay outside the EXE.
- Final evidence includes unit tests, real 90-frame validation, PyInstaller build, process launch, single-window check, layered-style check, color-key absence, and visual edge checks at small/medium/large sizes.

---

### Task 1: Premultiplied BGRA and Win32 Renderer

**Files:** Create `src/desktop_pet/layered_window.py` and `tests/test_layered_window.py`.

**Interfaces:** `rgba_to_premultiplied_bgra(image: Image.Image) -> bytes`; `LayeredWindowRenderer(hwnd: int)` with `render(image, x, y)`, `set_topmost(enabled)`, and `is_layered()`.

- [ ] **Step 1: Write failing conversion and style tests**

```python
def test_rgba_to_premultiplied_bgra_uses_integer_rounding():
    image = Image.new("RGBA", (2, 1))
    image.putdata([(200, 100, 50, 128), (9, 8, 7, 0)])
    assert rgba_to_premultiplied_bgra(image) == bytes((25, 50, 100, 128, 0, 0, 0, 0))

@pytest.mark.skipif(os.name != "nt", reason="Windows layered window contract")
def test_renderer_applies_layered_toolwindow_style(tk_root):
    renderer = LayeredWindowRenderer(tk_root.winfo_id())
    assert renderer.is_layered() is True
```

- [ ] **Step 2: Verify RED**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_layered_window.py -q`

Expected: missing `desktop_pet.layered_window`.

- [ ] **Step 3: Implement conversion and ctypes structures**

```python
def rgba_to_premultiplied_bgra(image: Image.Image) -> bytes:
    rgba = image.convert("RGBA")
    output = bytearray(rgba.width * rgba.height * 4)
    for offset, (red, green, blue, alpha) in enumerate(rgba.getdata()):
        base = offset * 4
        output[base:base+4] = bytes(((blue*alpha+127)//255,
                                     (green*alpha+127)//255,
                                     (red*alpha+127)//255, alpha))
    return bytes(output)
```

Define `POINT`, `SIZE`, `BLENDFUNCTION`, `BITMAPINFOHEADER`, and `BITMAPINFO`. Configure exact `argtypes/restype` for `GetDC`, `ReleaseDC`, `CreateCompatibleDC`, `DeleteDC`, `CreateDIBSection`, `SelectObject`, `DeleteObject`, `UpdateLayeredWindow`, `GetWindowLongPtrW`, `SetWindowLongPtrW`, and `SetWindowPos`.

- [ ] **Step 4: Implement resource-safe render**

```python
def render(self, image: Image.Image, x: int, y: int) -> None:
    pixels = rgba_to_premultiplied_bgra(image)
    screen_dc = self._user32.GetDC(None)
    memory_dc = bitmap = old_bitmap = None
    try:
        memory_dc = self._gdi32.CreateCompatibleDC(screen_dc)
        bitmap, bits = self._create_top_down_dib(screen_dc, image.size)
        ctypes.memmove(bits, pixels, len(pixels))
        old_bitmap = self._gdi32.SelectObject(memory_dc, bitmap)
        destination, size, source = POINT(x, y), SIZE(*image.size), POINT(0, 0)
        blend = BLENDFUNCTION(0, 0, 255, 1)
        if not self._user32.UpdateLayeredWindow(
                self.hwnd, screen_dc, byref(destination), byref(size),
                memory_dc, byref(source), 0, byref(blend), ULW_ALPHA):
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        if old_bitmap: self._gdi32.SelectObject(memory_dc, old_bitmap)
        if bitmap: self._gdi32.DeleteObject(bitmap)
        if memory_dc: self._gdi32.DeleteDC(memory_dc)
        if screen_dc: self._user32.ReleaseDC(None, screen_dc)
```

Set `WS_EX_LAYERED | WS_EX_TOOLWINDOW` without `WS_EX_TRANSPARENT`. `set_topmost` uses `SetWindowPos` with `HWND_TOPMOST` or `HWND_NOTOPMOST`, `SWP_NOMOVE|SWP_NOSIZE|SWP_NOACTIVATE`.

- [ ] **Step 5: Verify GREEN and commit**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_layered_window.py -q`

Expected: pure conversion passes and Windows style test passes.

```powershell
git add src/desktop_pet/layered_window.py tests/test_layered_window.py
git commit -m "feat: add per-pixel alpha renderer"
```

### Task 2: PetWindow Renderer Integration

**Files:** Modify `src/desktop_pet/window.py`, `tests/test_window.py`; create `tests/fakes.py`.

**Interfaces:** `PetWindow(root, frames, renderer_factory=LayeredWindowRenderer)`; `_window_rect: Rect` is authoritative; `_apply_image(image, anchor=None)` resizes with LANCZOS then calls `renderer.render`.

- [ ] **Step 1: Write failing fake-renderer tests**

```python
class FakeRenderer:
    def __init__(self, hwnd: int): self.calls, self.topmost = [], True
    def render(self, image: Image.Image, x: int, y: int) -> None:
        self.calls.append((image.copy(), x, y))
    def set_topmost(self, enabled: bool) -> None: self.topmost = enabled

def test_window_uses_rgba_renderer_without_character_label(tk_root, loaded_frames):
    renderer = FakeRenderer(tk_root.winfo_id())
    window = PetWindow(tk_root, loaded_frames, renderer_factory=lambda _: renderer)
    rendered, x, y = renderer.calls[-1]
    assert rendered.mode == "RGBA"
    assert rendered.height == 280
    assert not hasattr(window, "label")

def test_bindings_are_on_root(tk_root, loaded_frames):
    window = PetWindow(tk_root, loaded_frames, renderer_factory=FakeRenderer)
    assert tk_root.bind("<ButtonPress-1>")
    assert tk_root.bind("<MouseWheel>")
```

- [ ] **Step 2: Verify RED**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_window.py -q`

Expected: constructor lacks `renderer_factory` and still creates `label`.

- [ ] **Step 3: Replace the color-key display path**

```python
def _apply_image(self, image: Image.Image,
                 anchor: tuple[int, int] | None = None) -> None:
    width = max(1, round(image.width*self.display_height/image.height))
    resized = image.resize((width, self.display_height), Image.Resampling.LANCZOS)
    if anchor is None:
        x, y = self._window_rect.x, self._window_rect.y
    else:
        x, y = anchor[0]-width//2, anchor[1]-self.display_height
    self._window_rect = Rect(x, y, width, self.display_height)
    self.root.geometry(f"{width}x{self.display_height}{format_position(x, y)}")
    self.renderer.render(resized, x, y)
```

Remove `ImageTk`, `TRANSPARENT_KEY`, root background configuration, `-transparentcolor`, `Label`, `_photo`, and label bindings. Bind all five events on `root`. Drag updates `_window_rect`, root geometry, and rerenders the current resized image so the layered surface moves with Tk state.

- [ ] **Step 4: Cover preserved interactions**

Extend tests so wheel preserves foot-center anchor, drag does not trigger click, short release cycles jump/squash/shake, menu labels remain `小/中/大/始终置顶/退出`, and `set_always_on_top(False)` updates both renderer and bubble.

```python
def test_wheel_resize_preserves_foot_center(tk_root, loaded_frames):
    renderer = FakeRenderer(tk_root.winfo_id())
    window = PetWindow(tk_root, loaded_frames, renderer_factory=lambda _: renderer)
    before = window._anchor()
    window._on_wheel(SimpleNamespace(delta=120))
    assert window._anchor() == before

def test_topmost_updates_renderer_and_bubble(tk_root, loaded_frames):
    renderer = FakeRenderer(tk_root.winfo_id())
    window = PetWindow(tk_root, loaded_frames, renderer_factory=lambda _: renderer)
    window.set_always_on_top(False)
    assert renderer.topmost is False
    assert window.always_on_top is False
```

- [ ] **Step 5: Verify GREEN and commit**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_window.py tests\test_model.py -q`

Expected: all pass with the fake renderer; no real GDI calls are required by these tests.

```powershell
git add src/desktop_pet/window.py tests/test_window.py tests/fakes.py
git commit -m "refactor: render pet through layered window"
```

### Task 3: Opaque Bubble and 33ms Animation

**Files:** Modify `src/desktop_pet/bubble.py`, `src/desktop_pet/animation.py`, `tests/test_window.py`, `tests/test_animation.py`.

**Interfaces:** `BubbleWindow` uses a white opaque canvas and no color-key attribute; `AnimationController(..., interval_ms=33)`.

- [ ] **Step 1: Write failing bubble and timing tests**

```python
def test_bubble_has_no_transparent_color_key(tk_root):
    bubble = BubbleWindow(tk_root)
    assert bubble.window.cget("background") == "#ffffff"
    assert bubble.canvas.cget("background") == "#ffffff"
    bubble.destroy()

def test_default_interval_is_thirty_three_ms():
    scheduler = RecordingScheduler()
    controller = AnimationController({"jump": 30}, scheduler,
                                     lambda *_: None, lambda _: None)
    controller.play("jump")
    assert scheduler.delays == [33]
```

- [ ] **Step 2: Verify RED**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_window.py::test_bubble_has_no_transparent_color_key tests\test_animation.py::test_default_interval_is_thirty_three_ms -q`

Expected: bubble is magenta and interval is 90ms.

- [ ] **Step 3: Implement opaque bubble and timing**

Set both Toplevel and Canvas backgrounds to `#ffffff`; retain `overrideredirect`, toolwindow, topmost synchronization, dark border/text, outside-pet placement, and 1800ms hide timer. Delete `TRANSPARENT_KEY` and every `-transparentcolor` call. Change the controller default to `interval_ms=33`.

- [ ] **Step 4: Verify GREEN and scan forbidden paths**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_animation.py tests\test_window.py -q`

Run: `Select-String -Path src\desktop_pet\*.py -Pattern 'transparentcolor|#ff00ff|LWA_COLORKEY|ImageTk'`

Expected: tests pass and scan returns no matches.

- [ ] **Step 5: Commit**

```powershell
git add src/desktop_pet/bubble.py src/desktop_pet/animation.py tests/test_window.py tests/test_animation.py
git commit -m "fix: remove color-key transparency"
```

### Task 4: Build, Launch, and EXE Acceptance

**Files:** Create `tools/inspect_running_pet.py`, `tests/test_inspect_running_pet.py`, `qa/exe-smoke.json`, and size screenshots; modify `build.ps1` only if required to run the complete suite.

**Interfaces:** `inspect_process(pid: int) -> dict[str, object]` reports visible HWNDs, window rectangle, extended style, layered flag, and color-key flag when queryable.

- [ ] **Step 1: Write failing style-decoding test**

```python
def test_decode_window_style_reports_layered_without_colorkey():
    result = decode_window_style(WS_EX_LAYERED | WS_EX_TOOLWINDOW, 0)
    assert result == {"layered": True, "toolwindow": True,
                      "transparent_input": False, "color_key": False}
```

- [ ] **Step 2: Verify RED, implement inspector, verify GREEN**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_inspect_running_pet.py -q`

Expected RED: missing inspector module; expected GREEN after implementation: pass.

The inspector enumerates visible top-level HWNDs owned by the PID, captures title and rectangle, reads `GWL_EXSTYLE`, calls `GetLayeredWindowAttributes` when available, and writes JSON. It never moves, closes, or modifies another process.

- [ ] **Step 3: Run complete tests and build**

```powershell
.\.venv\Scripts\python.exe -m pytest -q
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

Expected: all tests pass; asset validator reports 90 frames; exactly one `dist\桌面宠物.exe` is produced; PyInstaller reports no missing Tk, Numpy, or OpenCV runtime modules.

- [ ] **Step 4: Launch and gather objective smoke evidence**

Start the EXE, wait for its visible window, then inspect the captured PID:

```powershell
$petProcess = Start-Process -FilePath '.\dist\桌面宠物.exe' -PassThru
Start-Sleep -Seconds 2
.\.venv\Scripts\python.exe -m tools.inspect_running_pet --pid $petProcess.Id --output qa\exe-smoke.json
```

Expected JSON: one visible pet HWND, title `桌面宠物`, `layered=true`, `toolwindow=true`, `transparent_input=false`, and `color_key=false`. Launching a second EXE leaves only the first visible window because the mutex rejects the second instance.

- [ ] **Step 5: Visual and interaction acceptance**

Capture small (`180`), medium (`280`), and large (`420`) screenshots. Inspect ears, back, tail, feet, and semi-transparent fur at 100% and 400%: no pink, purple, cyan, green, or blue halo. Exercise drag, three successive click actions, wheel resize, each size menu item, topmost off/on, bubble placement, and Exit. Record each check in `qa/exe-smoke.json` under `manual_checks` without marking an unperformed check true.

- [ ] **Step 6: Commit final acceptance artifacts**

```powershell
git add tools/inspect_running_pet.py tests/test_inspect_running_pet.py qa build.ps1
git commit -m "build: verify layered desktop pet executable"
```
