"""
GSS-OS 演示级 GUI 中枢
解决 OS 竞态条件，完美隔离认知与执行。
"""
import tkinter as tk
from tkinter import scrolledtext
import threading, time
import lib_manager
from prompt import build
from parser import parse
from executor import run as execute
from ai_client import ask

class GSS_GUI:
    def __init__(self, root):
        self.root = root
        self.root.title("GSS-OS Architecture Demo")
        self.root.geometry("900x500")
        self.root.configure(bg="#0d1117")
        self.root.attributes("-topmost", True)
        
        top = tk.Frame(root, bg="#0d1117")
        top.pack(fill="x", padx=10, pady=10)
        tk.Label(top, text="User Task: ", fg="#58a6ff", bg="#0d1117", font=("Consolas", 12, "bold")).pack(side="left")
        self.entry = tk.Entry(top, font=("Arial", 12), bg="#161b22", fg="white", insertbackground="white")
        self.entry.pack(side="left", fill="x", expand=True, padx=5)
        self.entry.bind("<Return>", self.start_task)
        
        mid = tk.Frame(root, bg="#0d1117")
        mid.pack(fill="both", expand=True, padx=10, pady=5)
        
        lf = tk.Frame(mid, bg="#0d1117")
        lf.pack(side="left", fill="both", expand=True, padx=(0,5))
        tk.Label(lf, text="🧠 Cognitive Layer (CoT)", fg="#d2a8ff", bg="#0d1117", font=("Consolas", 10)).pack(anchor="w")
        self.log_think = scrolledtext.ScrolledText(lf, bg="#161b22", fg="#d2a8ff", font=("Arial", 10))
        self.log_think.pack(fill="both", expand=True)

        rf = tk.Frame(mid, bg="#0d1117")
        rf.pack(side="right", fill="both", expand=True, padx=(5,0))
        tk.Label(rf, text="⚡ Execution Layer (Atomic Ops)", fg="#3fb950", bg="#0d1117", font=("Consolas", 10)).pack(anchor="w")
        self.log_exec = scrolledtext.ScrolledText(rf, bg="#161b22", fg="#3fb950", font=("Consolas", 10))
        self.log_exec.pack(fill="both", expand=True)

    def append(self, widget, text):
        self.root.after(0, lambda: widget.insert(tk.END, text + "\n"))
        self.root.after(0, lambda: widget.see(tk.END))

    def start_task(self, event=None):
        task = self.entry.get().strip()
        if not task: return
        self.entry.delete(0, tk.END)
        self.append(self.log_think, f"\n>>> {task}")
        threading.Thread(target=self.process, args=(task,), daemon=True).start()

    def process(self, task):
        prompt = build(task)
        self.append(self.log_think, "⏳ LLM Predicting...")
        resp = ask(prompt)
        actions = parse(resp)
        
        for act in actions:
            if act["type"] == "think":
                self.append(self.log_think, f"💡 {act['content']}")
                time.sleep(0.3)
            else:
                cmd = act["content"]
                if cmd.startswith("say "):
                    self.append(self.log_think, f"🗣️ {cmd[4:]}")
                else:
                    self.append(self.log_exec, f"▶ {cmd}")
                    execute(cmd)
                    time.sleep(0.6) # 防黑屏节流阀

if __name__ == "__main__":
    lib_manager.init()
    root = tk.Tk()
    app = GSS_GUI(root)
    root.mainloop()