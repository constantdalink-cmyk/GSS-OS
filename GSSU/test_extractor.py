import sys
sys.path.insert(0, r'E:\GSSU')
from extractor import locate_function, read_function, replace_function

code = open(r'C:\Users\rwxh5\Documents\GSSU_WORK\gssu_20260323_030612.txt', encoding='utf-8').read()

# 测试1：定位 add
start, end = locate_function(code, 'add')
print(f'add 函数范围: L{start}-L{end}')

# 测试2：读取 add 函数
func_text = read_function(code, 'add')
print(f'add 函数内容:')
print(func_text)

# 测试3：替换 add 函数
new_add = 'def add(*args):\n    return sum(args)'
new_code = replace_function(code, 'add', new_add)
print(f'替换后前10行:')
print('\n'.join(new_code.splitlines()[:10]))