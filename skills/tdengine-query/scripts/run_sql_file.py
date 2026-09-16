#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
REST 提交 SQL 文件到 TDengine（3.4.2.2 实测可用的降级路径，2026-08-18）。

适用：MCP query 工具反复报 `[0x127] Invalid timestamp format`（根因多为手写时间戳污染，
见 references/sql-hygiene.md 技术1），或 SQL 很长（14 线 UNION ALL / 多气表）时，
把程序化生成的 SQL 写进文件，由此脚本经 REST 提交——SQL 全文来自文件，天然杜绝手工转录错位。

凭据来自 /opt/data/.env 的 TDENGINE_*（脚本内无任何明文凭据），运行时由外层注入 env，
或直接 source .env 后执行。本脚本不含明文密码，可安全入库。

用法：
  # 方式A（推荐）：env 注入 + curl 提交（保留反引号，反引号会被 shell 消费，须 --data-binary @file）
  DB=$(grep -E '^TDENGINE_DB=' /opt/data/.env | cut -d= -f2)
  HOST=$(grep -E '^TDENGINE_HOST=' /opt/data/.env | cut -d= -f2)
  PORT=$(grep -E '^TDENGINE_PORT=' /opt/data/.env | cut -d= -f2)
  USER=$(grep -E '^TDENGINE_USER=' /opt/data/.env | cut -d= -f2)
  PASS=$(grep -E '^TDENGINE_PASS=' /opt/data/.env | cut -d= -f2)
  curl -s -u "$USER:$PASS" -X POST "http://$HOST:$PORT/rest/sql/$DB" \
       --data-binary @/path/to/your.sql

  # 方式B（Python requests，保留反引号，比 curl 更稳）：见下方 submit_sql_file()

注意：
  - 长 SQL 用 execute_code + strftime/日期对象动态生成（skilk.md Step 2b），写到文件，
    再跑本脚本——绝不手写信 SQL 字面量进 curl 命令。
  - REST 报 9728 = 反引号被 shell 消费（用 --data-binary @file）；9750 = URL 缺数据库名。
"""

import json
import os


def load_env_creds():
    """从 /opt/data/.env 读 TDengine 连接（TDENGINE_DB/HOST/PORT/USER/PASS），不打印值。"""
    env = {}
    with open('/opt/data/.env') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            env[k] = v.strip().strip('"').strip("'")
    return env


def submit_sql_file(sql_path, env=None):
    """
    用 Python requests 把 SQL 文件提交到 REST（保留反引号）。
    env: 可选 dict，覆盖 .env 中的连接参数（便于测试隔离）。
    返回 (http_ok, parsed_json)。parsed_json: {rows, data:[...], ...}。
    """
    env = env or load_env_creds()
    DB = env['TDENGINE_DB']; HOST = env['TDENGINE_HOST']; PORT = env['TDENGINE_PORT']
    USER = env['TDENGINE_USER']; PASS = env['TDENGINE_PASS']
    import base64
    import urllib.request
    with open(sql_path) as f:
        sql = f.read()
    url = f"http://{HOST}:{PORT}/rest/sql/{DB}"
    token = (USER + ':' + PASS).encode()
    req = urllib.request.Request(url, data=sql.encode('utf-8'), method='POST')
    req.add_header('Authorization', 'Basic ' + base64.b64encode(token).decode())
    req.add_header('Content-Type', 'text/plain')
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return True, json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return False, {"code": e.code, "msg": e.read().decode('utf-8')}


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print('用法: python run_sql_file.py <sql文件路径>')
        sys.exit(2)
    ok, parsed = submit_sql_file(sys.argv[1])
    print('HTTP', parsed.get('code', '?'), 'rows', parsed.get('rows', '?'))
    # 只打印表头与数据行，避免 URL/凭据外泄
    for r in parsed.get('data', []):
        print(r)