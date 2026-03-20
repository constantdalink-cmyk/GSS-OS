"""HOW-code 双螺旋进化"""
from gate import gate
from ai_client import ask
import lib_manager

def handle(name: str):
    code = ask(f"Create tool named {name}", is_creator=True)
    allowed = gate.review(f"HOW-code Creation: {name}", "AI wants to create a new executable.", code)
    if allowed:
        lib_manager.register_tool(name, code)