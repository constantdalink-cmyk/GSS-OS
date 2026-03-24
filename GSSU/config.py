"""GSS-OS 配置"""

AI_MODE = "openai"
OPENAI_KEY = "35b5d4d694ce4aa99b33413ac7362da1.ySIgJ1BfuGo70WWh"
OPENAI_MODEL = "glm-4-flash"
OPENAI_BASE_URL = "https://open.bigmodel.cn/api/paas/v4/"

MAX_STEPS = 20
MAX_HISTORY = 6
MAX_APPS = 4
DANGEROUS_KEYS = ["Alt+F4", "Win+L", "Ctrl+Alt+Del"]

import os

WORKSPACE_DIR = os.path.normpath(os.path.join(os.path.expanduser("~"), "Documents", "GSSU_WORK"))