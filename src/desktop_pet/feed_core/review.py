"""Non-blocking, owned UI for unresolved FEED transactions."""
from __future__ import annotations

from dataclasses import dataclass
import tkinter as tk

from .recovery import RecoveryPhase


@dataclass(frozen=True)
class ReviewItem:
    operation_id: str
    reason: str
    has_trusted_receipt: bool


class NeedsReviewController:
    def __init__(self, recovery, open_location, request_exit, present):
        self.recovery = recovery
        self._open_location = open_location
        self._request_exit = request_exit
        self._present = present

    def refresh(self):
        items = tuple(
            ReviewItem(
                record.operation_id,
                str(getattr(record, "reason", "outcome_unknown")),
                self.recovery._receipt_matches(record),
            )
            for record in self.recovery.store.incomplete_feed_transactions()
            if self.recovery._phase(record) is RecoveryPhase.NEEDS_REVIEW
        )
        self._present(items)
        return items

    def claim(self, operation_id: str) -> bool:
        changed = self.recovery.resolve(operation_id, claim_reward=True)
        self.refresh()
        return changed

    def discard(self, operation_id: str) -> bool:
        changed = self.recovery.resolve(operation_id, claim_reward=False)
        self.refresh()
        return changed

    def open_recycle_bin(self) -> None:
        self._open_location("shell:RecycleBinFolder")

    def exit_application(self) -> None:
        self._request_exit()


class TkNeedsReviewWindow:
    """A modeless Toplevel; it never performs file operations itself."""

    def __init__(self, owner, controller):
        self.owner = owner
        self.controller = controller
        self.window = None
        self.items = ()

    def show(self):
        if self.window is not None and self.window.winfo_exists():
            self.window.deiconify(); self.window.lift()
            self.controller.refresh()
            return
        window = tk.Toplevel(self.owner)
        self.window = window
        window.title("文件喂食需要人工复核")
        window.transient(self.owner)
        window.protocol("WM_DELETE_WINDOW", window.withdraw)
        tk.Label(window, justify="left", text=(
            "存在结果不确定的回收事务；新喂食已暂停。\n"
            "程序不会自动重试、恢复文件或操作其他回收站项目。"
        )).pack(padx=16, pady=10)
        self.listbox = tk.Listbox(window, width=68, height=8)
        self.listbox.pack(fill="both", expand=True, padx=16)
        buttons = tk.Frame(window); buttons.pack(padx=16, pady=12)
        tk.Button(buttons, text="打开回收站", command=self.controller.open_recycle_bin).pack(side="left", padx=3)
        tk.Button(buttons, text="确认领取奖励", command=lambda: self._resolve(True)).pack(side="left", padx=3)
        tk.Button(buttons, text="不领取并清除记录", command=lambda: self._resolve(False)).pack(side="left", padx=3)
        tk.Button(buttons, text="退出", command=self.controller.exit_application).pack(side="left", padx=3)
        self.controller.refresh()

    def present(self, items):
        self.items = tuple(items)
        if self.window is None or not self.window.winfo_exists():
            return
        self.listbox.delete(0, "end")
        for item in self.items:
            receipt = "有可信凭据" if item.has_trusted_receipt else "缺少可信凭据"
            self.listbox.insert("end", f"事务 {item.operation_id[:12]}… | {receipt} | {item.reason}")

    def _resolve(self, claim):
        selected = self.listbox.curselection()
        if not selected:
            return
        operation_id = self.items[selected[0]].operation_id
        if claim:
            self.controller.claim(operation_id)
        else:
            self.controller.discard(operation_id)
