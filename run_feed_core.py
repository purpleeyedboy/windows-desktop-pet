"""FEED-CORE test-candidate entry point; production Drop/Hunger wiring is intentionally absent."""
import json
import tkinter as tk
from pathlib import Path

def main():
    info=json.loads((Path(__file__).resolve().parent/'BUILD_INFO_FEED_CORE.json').read_text(encoding='utf-8'))
    root=tk.Tk(); root.title('桌面宠物 - 文件喂食事务测试候选')
    root.resizable(False,False)
    tk.Label(root,text='V2.1-FEED-CORE 测试候选',font=('Microsoft YaHei UI',14,'bold')).pack(padx=28,pady=(24,8))
    tk.Label(root,text='事务核心已启用；Drop / Hunger 生产接线待 FEED-WIRING。\n本窗口不会注册第二个 DropTarget，也不会自行选择或删除文件。',justify='left').pack(padx=28,pady=8)
    tk.Label(root,text=f"版本 {info['version']} · {info['date']} · {info['git_short_hash']}").pack(pady=(8,24))
    root.mainloop()
if __name__=='__main__': main()
