"""格子域：将二维图像降维为一维代数坐标"""
import tkinter as tk
import pyautogui

class Grid:
    def __init__(self):
        self.level = 2
        self.root = None
    
    def get_size(self): return 2 ** self.level, 2 ** self.level
    def set_level(self, level: int): self.level = max(1, min(8, level))
    
    def cell_to_pixel(self, cell: str):
        rows, cols = self.get_size()
        sw, sh = pyautogui.size()
        col_str = "".join([c for c in cell if c.isalpha()]).upper()
        row_str = "".join([c for c in cell if c.isdigit()])
        if not col_str or not row_str: return None, None
        
        c = 0
        for ch in col_str: c = c * 26 + (ord(ch) - ord('A'))
        r = int(row_str) - 1
        
        if 0 <= c < cols and 0 <= r < rows:
            return int((sw/cols)*c + (sw/cols)/2), int((sh/rows)*r + (sh/rows)/2)
        return None, None
    
    def show(self):
        if self.root: self.hide()
        self.root = tk.Tk()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"{sw}x{sh}+0+0")
        self.root.attributes("-alpha", 0.3, "-topmost", True)
        self.root.overrideredirect(True)
        
        canvas = tk.Canvas(self.root, width=sw, height=sh, bg="black", highlightthickness=0)
        canvas.pack()
        rows, cols = self.get_size()
        cw, ch = sw / cols, sh / rows
        labels = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        
        for r in range(rows):
            for c in range(cols):
                canvas.create_rectangle(c*cw, r*ch, (c+1)*cw, (r+1)*ch, outline="lime", width=1)
                if cw > 25 and ch > 15:
                    lbl = f"{labels[c]}{r+1}" if c < 26 else f"{c+1},{r+1}"
                    canvas.create_text(c*cw+15, r*ch+10, text=lbl, fill="lime", font=("Consolas", max(8, int(ch/5))))
        self.root.after(3000, self.hide)
        self.root.mainloop()
    
    def hide(self):
        if self.root:
            self.root.destroy()
            self.root = None

grid = Grid()