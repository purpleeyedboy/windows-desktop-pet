"""FEED-CORE simulation candidate; it never selects, moves, or deletes user files."""
from __future__ import annotations

import json
import sys
import tkinter as tk
from pathlib import Path

from desktop_pet.feed_core.simulation import run_safe_demo


def _build_report_text(report: dict[str, object]) -> str:
    return (
        "模拟事务状态：{state}\n"
        "模拟回收调用：{simulator_calls}\n"
        "模拟源文件仍存在：{source_still_exists}\n"
        "模拟奖励提交：{reward_commits}\n"
        "未注册真实 DropTarget；未选择、移动或删除真实文件。"
    ).format(**report)


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    report = run_safe_demo()
    self_test_output = None
    if "--self-test-output" in argv:
        index = argv.index("--self-test-output")
        if index + 1 >= len(argv):
            return 2
        self_test_output = Path(argv[index + 1])
    if "--self-test" in argv or self_test_output is not None:
        encoded_report = json.dumps(report, ensure_ascii=False, sort_keys=True)
        if self_test_output is not None:
            self_test_output.write_text(encoded_report + "\n", encoding="utf-8")
        else:
            print(encoded_report)
        return 0 if report == {
            "mode": "SIMULATION",
            "state": "Completed",
            "simulator_calls": 1,
            "source_still_exists": True,
            "reward_commits": 1,
            "animation_calls": 1,
        } else 1
    info = json.loads(
        (Path(__file__).resolve().parent / "BUILD_INFO_FEED_CORE.json").read_text(encoding="utf-8")
    )
    root = tk.Tk()
    root.title("桌面宠物 - 文件喂食事务模拟候选")
    root.resizable(False, False)
    tk.Label(root, text="V2.1-FEED-CORE 模拟模式", font=("Microsoft YaHei UI", 14, "bold"), fg="#9b3d00").pack(padx=28, pady=(24, 8))
    tk.Label(root, text="仅演示 feed_core 事务状态机；不会操作用户文件。", justify="left").pack(padx=28, pady=4)
    tk.Label(root, text=_build_report_text(report), justify="left").pack(padx=28, pady=8)
    tk.Label(root, text=f"版本 {info['version']} · {info['date']} · {info['git_short_hash']}").pack(pady=(8, 24))
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
