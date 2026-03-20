"""硬冻结关卡：未审查代码不可能进入可执行能力闭包"""
import tkinter as tk
from tkinter import scrolledtext
import threading

class Gate:
    def __init__(self):
        self.result = None
        self.lock = threading.Event()
    
    def review(self, title: str, detail: str, code: str = None) -> bool:
        self.result = None
        self.lock.clear()
        threading.Thread(target=self._window, args=(title, detail, code), daemon=True).start()
        self.lock.wait() # Kernel-level Hard Freeze
        return self.result
    
    def _window(self, title, detail, code):
        root = tk.Tk()
        root.title("⚠️ GSS-OS Security Hard Freeze")
        root.attributes("-topmost", True)
        root.protocol("WM_DELETE_WINDOW", lambda: None)
        
        tk.Label(root, text=f"⚠️ {title}", font=("Arial", 14, "bold"), fg="red").pack(pady=10)
        tk.Label(root, text=detail, font=("Arial", 11)).pack(padx=20)
        tk.Label(root, text="🔴 SYSTEM FROZEN PENDING HUMAN APPROVAL", fg="red").pack(pady=5)
        
        if code:
            box = scrolledtext.ScrolledText(root, width=60, height=15, bg="#1e1e1e", fg="lime")
            box.pack(padx=15, pady=5)
            box.insert("1.0", code)
            box.config(state="disabled")
        
        bf = tk.Frame(root)
        bf.pack(pady=10)
        tk.Button(bf, text="✅ ALLOW", bg="green", fg="white", command=lambda: self._resolve(root, True)).pack(side="left", padx=10)
        tk.Button(bf, text="❌ DENY", bg="red", fg="white", command=lambda: self._resolve(root, False)).pack(side="left", padx=10)
        root.mainloop()
        
    def _resolve(self, root, res):
        self.result = res
        self.lock.set()
        root.destroy()

gate = Gate()