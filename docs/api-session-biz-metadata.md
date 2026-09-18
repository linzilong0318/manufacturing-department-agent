# API Server 业务元数据注入与自定义工具设计方案

> **背景**：基于 hermes-agent 的 `/api/sessions/` 系列接口对接自研 chatbot 前端。
> **状态**：设计文档，未改动任何现有代码。
> **涉及源码**：`gateway/session_context.py`、`gateway/platforms/api_server.py`、`tools/environments/local.py`、`tools/registry.py`

---

## 1. 原始问题

在通过 skill 编排 agent 工作流时，存在这样的场景：

1. agent 在工作流中生成一个结构化 JSON 文件；
2. 需要调用后端工程师开发的业务接口，把 JSON 写入后端数据库；
3. 该业务接口的输入包括：**生成的 JSON 文件**、**当前会话的 session-id**、**当前用户的身份标识**（业务用户 id，后续还会扩展到项目 id 等多用户多项目隔离所需的元数据）。

已知 session-id 可以通过环境变量获取（skill 中引导 agent 用 terminal 工具读取环境变量），但**用户身份标识 agent 在 loop 中无从得知**——`/api/sessions/{id}/chat` 接口里只有 `message` 能传递给 LLM，而元数据不应该、也不能塞进用户消息里。

推广开来即：**如何在 agent-loop 中让 LLM / 工具层获取请求级元数据？**

---

## 2. 问题解析

### 2.1 核心原则：元数据分两类，走两条通道

主流 agent 产品（Claude Code SDK、LangGraph/LangChain、OpenAI Agents SDK、ChatGPT/Claude 网页端等）在这个问题上遵循同一条原则：

| 元数据类型 | 例子 | 通道 | LLM 可见性 |
|---|---|---|---|
| **上下文信息** | 用户昵称、偏好、时区、项目背景 | 注入 system prompt | 可见（影响"怎么表现"） |
| **授权信息** | 业务用户 id、租户 id、项目 id、凭证 | 运行时上下文 → 工具执行层（带外通道） | **绝不可见、绝不经手** |

原因：凡是 LLM 可见的内容，就可被 prompt injection 操纵。如果 user_id 由 LLM 从 prompt 读出再填进工具参数，用户在对话里说"用 user_id=42 调用"即构成越权。**身份标识必须由可信通道直达工具执行层，绕过 LLM。**

### 2.2 各产品的实现对照

| 产品 | 机制 |
|---|---|
| **Claude Code / Agent SDK** | 自定义工具通过进程内 MCP server 定义，tool handler 是宿主进程代码，闭包持有 user id / DB 连接；LLM 只看到参数 schema。授权决策在 `canUseTool` 回调。环境类信息（cwd、git 状态）用 `--append-system-prompt` 注入。 |
| **LangGraph / LangChain** | `RunnableConfig.configurable` 传入 `{"thread_id": ..., "user_id": ...}`（官方多租户文档的标准做法）；工具侧用 `InjectedToolArg` 标注的参数**从 LLM 可见 schema 中消失**，由运行时填充。 |
| **OpenAI Agents SDK** | `Runner.run(..., context=ctx)`，工具函数第一个参数收 `RunContextWrapper[T]`，context 对象携带 user_id，LLM 不可见。 |
| **网页端 chatbot（ChatGPT 等）** | 身份来自边缘层登录态，模型从头到尾看不到 user id 和凭证；工具在服务端按该用户凭证执行（连接器走 OAuth，token 存于执行层）。prompt 里只有个性化信息（上下文，非授权）。 |

**统一模式**：工具参数 = LLM 提供的业务参数；身份/授权 = 运行时从可信上下文注入。LangChain 的 `InjectedToolArg` 是这一模式最显式的表达。

### 2.3 hermes 中现成的通道

hermes 已经内置了完整的"带外通道"基础设施：

1. **contextvars 会话上下文**（`gateway/session_context.py`）：用 `contextvars.ContextVar` 存储请求级会话元数据，task-local、并发安全。文件 docstring 明确记录了为何从 `os.environ` 迁移到 contextvars——进程全局环境变量在并发消息处理时会被互相覆盖（真实事故：后台通知发错会话）。
2. **子进程环境变量桥**（`tools/environments/local.py::_inject_session_context_env`）：把 `_VAR_MAP` 中所有 ContextVar 自动注入 terminal 工具的子进程环境。这就是 skill 里能 `echo $HERMES_SESSION_ID` 的原理。带跨会话泄漏防护（ContextVar `_UNSET` 且已有宿主绑定时，剥离进程全局残留值）。
3. **工具层读取惯例**：`from gateway.session_context import get_session_env` 是全代码库工具读取会话上下文的标准方式（`cronjob_tools.py`、`send_message_tool.py` 等均如此）。

### 2.4 一个重要的边界澄清

hermes 现有的 `HERMES_SESSION_USER_ID` / `HERMES_SESSION_USER_NAME` **不是**本方案所说的业务用户身份。它表示消息来源平台的平台侧用户（如 Telegram 发送者 id、飞书 union_id），由 gateway 平台适配器从 `SessionSource` 绑定。API server 场景下业务用户身份、项目 id 等属于**新增元数据字段**，需要在 session 上下文体系中扩展，并通过 contextvars 机制注入。

---

## 3. 方案一：新增业务元数据字段并注入上下文

### 3.1 目标字段

沿用 `HERMES_SESSION_*` 命名前缀（这样可以零改动复用 `_VAR_MAP` 驱动的环境变量桥）：

| ContextVar / 环境变量 | 含义 | 来源 |
|---|---|---|
| `HERMES_SESSION_BIZ_USER_ID` | 业务用户标识 | 请求头 `X-Hermes-Biz-User-Id`（由己方后端注入） |
| `HERMES_SESSION_BIZ_PROJECT_ID` | 项目标识 | 请求头 `X-Hermes-Biz-Project-Id` |

### 3.2 数据流全景

```
浏览器 ──登录态──► 己方后端 ──API_KEY + X-Hermes-Biz-User-Id + X-Hermes-Biz-Project-Id──► hermes api_server
                                                                                              │
                                                              _parse_biz_metadata_headers（新增，校验）
                                                                                              ▼
                                                              _handle_session_chat[_stream] → _run_agent
                                                                                              ▼
                                                              _bind_api_server_session(...) 扩展参数
                                                                                              ▼
                                                              set_session_vars(biz_user_id=..., biz_project_id=...)
                                                                                              ▼
                                                        ┌─────────────────────┬─────────────────────────┐
                                                        ▼                     ▼                         ▼
                                               工具内 get_session_env   terminal 子进程 env      （可选）prompt_builder
                                               （自定义业务工具读取）    （skill 里 $VAR 读取）     （注入系统提示，仅上下文用途）
```

### 3.3 改动点一：`gateway/session_context.py`

新增 ContextVar 并挂入既有机制（以下为示意代码，未实施）：

```python
# 1) 新增 ContextVar（放在 _SESSION_PROFILE 附近）
_SESSION_BIZ_USER_ID: ContextVar = ContextVar("HERMES_SESSION_BIZ_USER_ID", default=_UNSET)
_SESSION_BIZ_PROJECT_ID: ContextVar = ContextVar("HERMES_SESSION_BIZ_PROJECT_ID", default=_UNSET)

# 2) _VAR_MAP 增加两项 —— 加了这两项，子进程环境变量桥即自动生效，local.py 无需改动
_VAR_MAP = {
    # ... 现有项 ...
    "HERMES_SESSION_BIZ_USER_ID": _SESSION_BIZ_USER_ID,
    "HERMES_SESSION_BIZ_PROJECT_ID": _SESSION_BIZ_PROJECT_ID,
}

# 3) set_session_vars() 签名扩展 keyword 参数（保持默认 ""，向后兼容），
#    tokens 列表中追加对应的 .set() 调用
def set_session_vars(
    # ... 现有参数 ...
    biz_user_id: str = "",
    biz_project_id: str = "",
    # ...
) -> list:
    tokens = [
        # ... 现有 .set() ...
        _SESSION_BIZ_USER_ID.set(biz_user_id),
        _SESSION_BIZ_PROJECT_ID.set(biz_project_id),
    ]
    # ...

# 4) clear_session_vars() 与 reset_session_vars() 的变量列表同步追加这两项
```

注意点：

- **不要**为了图省事在请求处理时写 `os.environ["HERMES_SESSION_BIZ_USER_ID"] = ...`。进程全局变量在并发请求下会串号，这正是 hermes 迁移到 contextvars 要修的问题。
- `set_session_vars` 目前每次绑定会翻转 `_session_context_engaged` 闩锁，之后 `_UNSET` 的变量在子进程 env 中会被**剥离**而非继承进程全局值——新字段自动获得这一泄漏防护。

### 3.4 改动点二：`gateway/platforms/api_server.py`

**(a) 新增请求头解析函数**，照抄 `_parse_session_key_header` 的安全模式（要求 API key 已配置、拒绝 `\r\n\x00` 控制字符、长度不超过 `_MAX_SESSION_HEADER_LEN`）：

```python
def _parse_biz_metadata_headers(self, request):
    """解析并校验 X-Hermes-Biz-User-Id / X-Hermes-Biz-Project-Id。

    与 session key 相同的安全语义：接受调用方自声明的身份 scope，
    必须以 API key 认证为前提（信任锚是 API_SERVER_KEY + 己方后端拓扑）。
    返回 ({"biz_user_id": ..., "biz_project_id": ...}, None) 或 (None, error_response)。
    """
    # 校验逻辑镜像 _parse_session_key_header，逐字段检查控制字符与长度
```

**(b) `_bind_api_server_session()` 扩展**：新增 `biz_user_id` / `biz_project_id` keyword 参数，透传给 `set_session_vars()`。该函数是所有 API-server agent 入口的统一 chokepoint，在此扩展可保证所有路由行为一致。

**(c) `_run_agent()` 扩展**：新增同名可选参数，透传给 `_bind_api_server_session()`。

**(d) 处理器接线**：`_handle_session_chat` 与 `_handle_session_chat_stream` 中，在 `_parse_session_key_header` 之后调用 `_parse_biz_metadata_headers`，并传入 `_run_agent(...)`。如需全面对齐，可同样在 `/v1/chat/completions`、`/v1/responses`、`/v1/runs` 的处理器中接线（同一 chokepoint，改动模式相同）。

### 3.5 消费侧：skill 如何使用

环境变量桥对 `_VAR_MAP` 全量生效，因此 skill 中与现有 session-id 用法完全同构：

```bash
curl -X POST https://biz-api.internal/records \
  -H "X-User-Id: $HERMES_SESSION_BIZ_USER_ID" \
  -H "X-Project-Id: $HERMES_SESSION_BIZ_PROJECT_ID" \
  -H "X-Session-Id: $HERMES_SESSION_ID" \
  -d @output.json
```

说明：`agent/skill_preprocessing.py` 的模板替换目前只支持 `${HERMES_SKILL_DIR}` 和 `${HERMES_SESSION_ID}` 两个 token。业务身份**不建议**走模板替换（会把授权信息写进 prompt 文本，违反 2.1 的原则），保持运行时从环境变量读取即可。

---

## 4. 方案二：自定义工具封装业务 API（推荐用于写库场景）

即使通过 skill 编排工作流，也不应让 agent 自由拼 curl 调用写库接口——把"调用业务 API"收敛为一个**自定义工具**，LLM 只提供业务参数，身份字段由工具实现内部从 contextvars 读取。这是 LangChain `InjectedToolArg` / Claude SDK 进程内工具的同款模式，可同时获得：

- **越权防护**：LLM 没有机会提供 user_id，prompt injection 无法跨用户写数据；
- **入参校验**：工具内先做 JSON schema 校验再调用后端，失败快速返回；
- **可测试性**：把不确定性收敛到可单测、可 code review 的普通 Python 函数；
- **可观测性**：工具调用天然进入 hermes 的 tool progress / transcript 体系。

### 4.1 工具设计示例（示意代码，未实施）

```python
# 例如 tools/biz_record_tool.py（或 plugins/<name>/ 下，见 4.3）
from gateway.session_context import get_session_env
from tools.registry import registry

BIZ_UPSERT_SCHEMA = {
    "name": "biz_upsert_record",
    "description": (
        "将当前工作流产出的结构化 JSON 记录写入业务数据库。"
        "用户身份与项目归属由系统自动绑定，无需提供。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "payload": {
                "type": "object",
                "description": "要写入的结构化 JSON 记录（业务字段）",
            },
            "dry_run": {"type": "boolean", "default": False},
        },
        "required": ["payload"],
        "additionalProperties": False,
    },
}

def _handle_biz_upsert(args: dict, **kw) -> str:
    biz_user_id = get_session_env("HERMES_SESSION_BIZ_USER_ID")
    project_id = get_session_env("HERMES_SESSION_BIZ_PROJECT_ID")
    session_id = get_session_env("HERMES_SESSION_ID")
    if not biz_user_id or not project_id:
        return "Error: 缺少业务身份上下文（biz_user_id/project_id），请确认请求头已由后端注入。"

    payload = args.get("payload")
    # 1) 服务端校验：按业务 schema 校验 payload，不合法直接返回错误说明
    # 2) 幂等：以 session_id + 业务主键做幂等键，防止 agent 重试造成重复写入
    # 3) 调用业务 API：X-User-Id / X-Project-Id / X-Session-Id 由工具内部附加
    # 4) 错误信息脱敏后返回给 LLM（不回泄内部地址、堆栈、凭证）
    ...

registry.register(
    name="biz_upsert_record",
    toolset="biz",
    schema=BIZ_UPSERT_SCHEMA,
    handler=_handle_biz_upsert,
    check_fn=lambda: True,   # 或校验业务 API 可达性 / 必要配置
)
```

参考惯例：`tools/cronjob_tools.py` 的 `registry.register(name=..., toolset=..., schema=..., handler=..., check_fn=...)`（模块 import 时注册）；工具内读取会话上下文参考其 `get_session_env("HERMES_SESSION_USER_ID")` 等用法。

### 4.2 工具 schema 设计准则

1. **schema 最小化**：只暴露 LLM 需要决策的业务参数；身份、会话、内部 URL 一律不进 schema。
2. **description 即契约**：在 description 中明确"身份由系统自动绑定"，避免 LLM 试图自己编造身份参数。
3. **服务端二次校验**：hermes 侧工具校验不替代业务 API 自身的鉴权与数据校验——业务 API 仍应以 `X-User-Id` 做数据权限判断。
4. **返回值面向 LLM 编写**：成功时返回简洁确认（含业务主键）；失败时返回 LLM 可理解、可自我修复的错误描述。

### 4.3 代码放置与启用

两种放置方式：

| 方式 | 位置 | 特点 |
|---|---|---|
| 内置工具文件 | `tools/biz_record_tool.py` | 与内置工具同机制，import 即注册 |
| 插件 | `plugins/<name>/`（plugin.yaml + 工具模块，参考 `plugins/spotify/`） | 定制代码与核心代码物理隔离，升级冲突最小，**推荐** |

启用：api_server 平台的工具集由 `config.yaml` 的 `platform_toolsets.api_server` 控制（`_create_agent` 内 `_get_platform_tools(user_config, "api_server")` 解析）。将自定义 toolset（如 `biz`）加入该列表即可仅对 API server 平台开放，不影响 CLI 等其他入口。

---

## 5. 部署拓扑与安全边界

**终端用户不得直连 hermes api_server。** 身份头是"自声明"的，hermes 无法验证其真伪，信任锚是 `API_SERVER_KEY` 加上"只有己方后端能到达 hermes"的网络拓扑：

```
浏览器 ──(己方登录态)──► 己方后端 ──(API_SERVER_KEY + X-Hermes-Biz-User-Id/Project-Id)──► hermes
                                                                                            │
                                                                                            ▼
                                                          业务 API（以 X-User-Id 做最终数据权限校验）
```

- 身份头必须由**鉴权后的己方后端**注入，不能由浏览器直接携带；
- 业务 API 收到请求后仍须按 user_id 做行级数据权限校验（纵深防御，hermes 保证的是"身份未被对话内容篡改"，业务鉴权永远是己方后端的职责）；
- 会话级数据隔离单位即 `session_id`；跨会话的长期记忆隔离使用独立的 `X-Hermes-Session-Key`（与 session_id 正交）；
- 同一 session 的 chat 请求应串行发送（前端在流式期间禁用输入即可天然满足），避免并发轮次的历史读写交错；
- 上下文压缩可能导致 session_id 轮换，前端需跟踪响应头 `X-Hermes-Session-Id` 更新记录。

---

## 6. 实施清单（建议顺序）

1. `gateway/session_context.py`：新增两个 ContextVar + `_VAR_MAP` 登记 + `set_session_vars`/`clear_session_vars`/`reset_session_vars` 同步扩展；
2. `gateway/platforms/api_server.py`：新增 `_parse_biz_metadata_headers`；扩展 `_bind_api_server_session` 与 `_run_agent`；在两个 chat 处理器中接线；
3. 验证环境变量桥：`POST /api/sessions/{id}/chat`，让 agent 在 terminal 中 `echo $HERMES_SESSION_BIZ_USER_ID` 确认注入生效（`local.py` 零改动）；
4. 编写自定义业务工具（建议放 `plugins/`），注册到 `biz` toolset 并加入 `platform_toolsets.api_server`；
5. 调整 skill 编排：写库步骤从"自由 curl"改为调用自定义工具；
6. 己方后端增加身份头注入逻辑 + 业务 API 的行级权限校验；
7. 补充测试：参考 `tests/hermes_cli/test_web_server*.py` 与 `tests/tools/test_local_env_session_leak.py` 的既有模式，覆盖头校验、contextvars 注入、并发隔离、工具内身份绑定。
