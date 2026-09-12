"""Non-blocking owned 30-second FEED confirmation window."""
from __future__ import annotations
import tkinter as tk


class TkFeedConfirmation:
    def __init__(self, owner, timeout_ms: int = 30_000):
        self.owner = owner
        self.timeout_ms = timeout_ms
        self.window = None
        self._callback = None

    def show(self, prepared, current_hunger: int, callback):
        self.cancel()
        window = tk.Toplevel(self.owner)
        self.window = window
        self._callback = callback
        window.title("确认文件喂食")
        window.transient(self.owner)
        window.protocol("WM_DELETE_WINDOW", lambda: self._finish(False))
        window.bind("<Escape>", lambda _event: self._finish(False))
        quote = prepared.quote
        text = (
            f"完整路径：{prepared.snapshot.canonical_path}\n"
            f"文件大小：{prepared.snapshot.size_bytes} 字节\n"
            f"修改时间：{prepared.snapshot.modified_100ns} (100ns UTC ticks)\n"
            f"当前饥饿值：{current_hunger / 1000:.3f}\n"
            f"理论奖励：{quote.theoretical_units / 1000:.3f}\n"
            f"实际奖励：{quote.actual_units / 1000:.3f}\n"
            f"溢出：{quote.overflow_units / 1000:.3f}\n\n"
            "确认后将移入 Windows 回收站；无法证明回收成功时不会奖励。"
        )
        if quote.enhanced_warning:
            text = "⚠ 高风险：大文件或奖励溢出比例较高，请再次核对。\n\n" + text
        tk.Label(window, text=text, justify="left").pack(padx=18, pady=12)
        buttons = tk.Frame(window); buttons.pack(pady=(0, 12))
        tk.Button(buttons, text="确认", command=lambda: self._finish(True)).pack(side="left", padx=6)
        tk.Button(buttons, text="取消", command=lambda: self._finish(False)).pack(side="left", padx=6)
        window.after(self.timeout_ms, lambda: self._finish(False))

    def cancel(self):
        if self.window is not None:
            self._finish(False)

    def _finish(self, accepted: bool):
        callback, window = self._callback, self.window
        self._callback = None; self.window = None
        if window is not None and window.winfo_exists():
            window.destroy()
        if callback is not None:
            callback(bool(accepted))
