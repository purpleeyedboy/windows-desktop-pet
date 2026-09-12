"""Non-blocking owned 30-second FEED confirmation window."""
from __future__ import annotations
import tkinter as tk
from datetime import datetime, timedelta, timezone
from pathlib import Path
from desktop_pet.foundation.persistence import AtomicJsonStore


class TkFeedConfirmation:
    def __init__(self, owner, timeout_ms: int = 30_000, *, preference_path: Path | None = None):
        self.owner = owner
        self.timeout_ms = timeout_ms
        self.window = None
        self._callback = None
        self._remember = None
        self._generation = 0
        self._store = (AtomicJsonStore(preference_path, schema="feed-confirmation-preference",
            version=1, validator=lambda data: type(data.get("skip_confirmation")) is bool)
            if preference_path is not None else None)
        self._skip_confirmation = bool(self._store and self._store.load(
            default={"skip_confirmation": False})["skip_confirmation"])

    def show(self, prepared, current_hunger: int, callback):
        self.cancel()
        self._callback = callback
        generation = self._generation
        if self._skip_confirmation:
            # Revalidation can request a refreshed quote; defer rather than recurse.
            self.owner.after(0, lambda: self._finish(True)
                if generation == self._generation else None)
            return
        window = tk.Toplevel(self.owner)
        self.window = window
        self._callback = callback
        window.title("确认文件喂食")
        window.transient(self.owner)
        window.protocol("WM_DELETE_WINDOW", lambda: self._finish(False))
        window.bind("<Escape>", lambda _event: self._finish(False))
        quote = prepared.quote
        modified = (datetime(1601, 1, 1, tzinfo=timezone.utc) +
                    timedelta(microseconds=prepared.snapshot.modified_100ns // 10)).astimezone()
        text = (
            f"完整路径：{prepared.snapshot.canonical_path}\n"
            f"文件大小：{prepared.snapshot.size_bytes} 字节\n"
            f"修改时间：{modified:%Y-%m-%d %H:%M:%S %Z}\n"
            f"当前饥饿值：{current_hunger / 1000:.3f}\n"
            f"理论奖励：{quote.theoretical_units / 1000:.3f}\n"
            f"实际奖励：{quote.actual_units / 1000:.3f}\n"
            f"溢出：{quote.overflow_units / 1000:.3f}\n\n"
            "确认后将移入 Windows 回收站；无法证明回收成功时不会奖励。"
        )
        if quote.enhanced_warning:
            text = "⚠ 高风险：大文件或奖励溢出比例较高，请再次核对。\n\n" + text
        tk.Label(window, text=text, justify="left").pack(padx=18, pady=12)
        self._remember = tk.BooleanVar(master=window, value=False)
        tk.Checkbutton(window, text="以后不再提示（后续文件喂食直接移入回收站）",
                       variable=self._remember).pack(padx=18, pady=(0, 10))
        buttons = tk.Frame(window); buttons.pack(pady=(0, 12))
        tk.Button(buttons, text="确认", command=lambda: self._finish(True)).pack(side="left", padx=6)
        tk.Button(buttons, text="取消", command=lambda: self._finish(False)).pack(side="left", padx=6)
        window.after(self.timeout_ms, lambda: self._finish(False)
                     if generation == self._generation else None)

    def cancel(self):
        if self._callback is not None or self.window is not None:
            self._finish(False)

    def _finish(self, accepted: bool):
        if accepted and self._remember is not None and self._remember.get():
            try:
                if self._store is not None:
                    self._store.save({"skip_confirmation": True}, durable=True)
                self._skip_confirmation = True
            except OSError:
                # This confirmation is valid; retry preference saving next time.
                self._skip_confirmation = False
        self._remember = None
        self._generation += 1
        callback, window = self._callback, self.window
        self._callback = None; self.window = None
        if window is not None and window.winfo_exists():
            window.destroy()
        if callback is not None:
            callback(bool(accepted))
