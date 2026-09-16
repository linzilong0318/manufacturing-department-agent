#!/usr/bin/env python3
"""校验 dtx-query-cases.md 案例库完整性：编号唯一性、连续性、交叉引用。

用法: python3 scripts/verify_cases.py [案例文件路径]
默认路径: /opt/data/skills/data-science/tdengine-query/dtx-query-cases.md
退出码: 0=PASS, 1=FAIL

适用场景：并发验收测试后、人工整理后、或追加新案例后跑一次，
确认案例编号无重复/缺失、正文"同案例N"交叉引用全部有效。
"""
import re
import sys
from collections import Counter

DEFAULT = "/opt/data/skills/data-science/tdengine-query/dtx-query-cases.md"
path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT

try:
    text = open(path, encoding="utf-8").read()
except OSError as e:
    print(f"FAIL: 无法读取 {path}: {e}")
    sys.exit(1)

ids = re.findall(r"^#\s*案例(\d+)", text, re.M)
nums = [int(n) for n in ids]
problems = []

if not nums:
    problems.append("未找到任何案例标题（应为 '# 案例N：...' 格式）")
else:
    cnt = Counter(nums)
    dups = {n: k for n, k in sorted(cnt.items()) if k > 1}
    if dups:
        problems.append("编号重复: " + ", ".join(f"案例{n}×{k}" for n, k in dups.items()))
    missing = [n for n in range(1, max(nums) + 1) if n not in nums]
    if missing:
        problems.append("编号缺失: " + ", ".join(f"案例{n}" for n in missing))

# 正文交叉引用（同案例N）必须指向存在的案例标题
known = set(nums)
refs = [int(n) for n in re.findall(r"同案例(\d+)", text)]
dangling = sorted({n for n in refs if n not in known})
if dangling:
    problems.append("悬空交叉引用(同案例): " + ", ".join(f"案例{n}" for n in dangling))

print(f"案例数: {len(nums)}")
if problems:
    print("FAIL:")
    for p in problems:
        print(f"  - {p}")
    sys.exit(1)
print("PASS: 编号唯一且连续、交叉引用全部有效")
