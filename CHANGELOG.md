# Router 更新日志

## [Unreleased] - 2026-04-16

### 📝 文档更新

- **新增配置文件详细文档** (`CONFIG.md`)
  - 详细说明 `config.json` 所有配置项
  - 包含 `server`、`target`、`logging`、`features` 四大配置模块
  - 添加 `compress_log_data` 功能详解
  - 提供常见配置场景示例

- **更新 README.md**
  - 添加 CONFIG.md 文档引用链接
  - 简化配置说明部分

### 🐛 Bug 修复

- **修复 Smart Streaming thinking 内容丢失** (`stream_handlers.py`)
  - 添加 `thinking_buffer` 变量累积 thinking 内容
  - 确保 thinking 块内容正确传递

---

## [Unreleased] - 2026-04-13

### 🏗️ 代码重构

- **handlers.py 文件分割** (`handlers.py`, `base_handler.py`, `anthropic_handler.py`, `stream_handlers.py`)
  - 将 `handlers.py` 分割成多个功能明确的模块
  - `base_handler.py`：包含基础HTTP请求处理逻辑
  - `anthropic_handler.py`：包含处理Anthropic请求的逻辑
  - `stream_handlers.py`：包含流式处理的逻辑
  - 简化了 `handlers.py` 文件，使其导入并使用新创建的模块
  - 创建了 `__init__.py` 文件，导出主要的类和方法

### 🐛 Bug 修复

- **修复导入问题** (`handlers.py`, `base_handler.py`, `anthropic_handler.py`, `stream_handlers.py`, `processors.py`, `stream_processor.py`, `utils.py`, `logger.py`)
  - 将相对导入改为绝对导入，确保直接运行 `router_server.py` 时不会报错
  - 修复了 `anthropic_handler.py` 文件中缺少 `LOG_ALL_TRAFFIC`、`COMPRESS_LOG_DATA` 和 `compress_log_data` 的导入问题

### 🆕 新功能

- **新增混合流式模式 (Smart Streaming)** (`handlers.py`, `config.json`)
  - 新增配置项 `smart_streaming`，默认 `false`
  - **thinking 块**：实时流式转发，每个 delta 立即发送
  - **tool_use 块**：实时流式转发
  - **text 块**：智能流式转发（见下方状态机实现）
  - 保留原有 `legacy` 模式，通过配置切换

- **text 块智能流式转发** (`handlers.py`)
  - 使用状态机实现，4个状态：`NORMAL` → `MATCHING` → `BUFFERING_THINK` / `BUFFERING_TOOL`
  - **NORMAL 状态**：普通文本直接流式转发，检测到 `<` 进入 MATCHING
  - **MATCHING 状态**：累积字符判断是否匹配 `<think` 或 `<tool_call`
    - 匹配成功 → 进入对应缓冲状态
    - 匹配失败 → 将累积字符发送，回到 NORMAL
  - **BUFFERING_THINK 状态**：缓冲直到 `</think`，处理后发送（或移除）
  - **BUFFERING_TOOL 状态**：缓冲直到 `</tool_call`，解析为 tool_use 块
  - 优化：NORMAL 状态下无 `<` 的 delta 直接转发，避免逐字符处理

- **新增流式处理日志标记** (`handlers.py`)
  - `[SMART MODE] >>> FORWARD: text block #N (smart streaming)`
  - `[SMART MODE] >>> FORWARD: thinking block #N (immediate)`
  - `[SMART MODE] >>> FORWARD: content_block_stop for text`
  - 便于调试和监控流式处理流程

### 🐛 Bug 修复

- **修复 thinking 块中 tool_call 处理** (`processors.py`, `stream_processor.py`, `xml_parser.py`)
  - 当模型错误地将 `tool_call` 放在 `thinking` 块中时，现在会正确解析为 `tool_use` 块
  - 从 `thinking` 内容中移除已解析的 `tool_call` XML，保留纯思考内容
  - 记录错误日志到 `router_error.log`，便于后续分析
  - 同时支持非流式和流式响应处理

### 🆕 新功能

- **新增 `remove_parsed_tool_calls_from_thinking` 函数** (`xml_parser.py`)
  - 从 thinking 内容中移除已解析的 tool_call XML 标签
  - 清理多余空白行，保留其余思考内容

### 📝 技术细节

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `handlers.py` | 代码重构 | 简化文件，导入并使用新创建的模块 |
| `base_handler.py` | 代码重构 | 提取基础HTTP请求处理逻辑 |
| `anthropic_handler.py` | 代码重构 | 提取处理Anthropic请求的逻辑 |
| `stream_handlers.py` | 代码重构 | 提取流式处理的逻辑 |
| `__init__.py` | 代码重构 | 导出主要的类和方法 |
| `handlers.py` | 新功能 | `_stream_smart()` 智能流式转发方法 |
| `handlers.py` | 新功能 | `_stream_legacy()` 原有模式保留 |
| `handlers.py` | 新功能 | `_send_sse_event()` SSE事件发送辅助方法 |
| `handlers.py` | 新功能 | text 块状态机处理逻辑 |
| `processors.py` | Bug 修复 | thinking 块中 tool_call 处理 |
| `stream_processor.py` | Bug 修复 | 流式模式下 thinking 块中 tool_call 处理 |
| `xml_parser.py` | 新功能 | 新增 `remove_parsed_tool_calls_from_thinking` 函数 |
| `config.json` | 配置 | 新增 `smart_streaming` 开关 |
| `config.py` | 配置 | 新增 `SMART_STREAMING` 常量 |

### 状态机流程图

```
┌─────────┐    收到 '<'    ┌───────────┐
│ NORMAL  │ ──────────────>│ MATCHING  │
│ (流式)  │                │ (判断中)  │
└────┬────┘                └─────┬─────┘
     │                           │
     │ 无 '<' 的 delta           │ 匹配 <think
     │ 直接转发                   │
     │                           ▼
     │                    ┌──────────────┐
     │                    │BUFFERING_THINK│
     │                    │ 缓冲到 </think│
     │                    └──────┬───────┘
     │                           │
     │                           │ 处理完成
     │                           ▼
     │                    ┌──────────────┐
     │                    │   NORMAL     │
     │                    └──────────────┘
     │                           
     │                           │ 匹配 <tool_call
     │                           ▼
     │                    ┌──────────────┐
     │                    │BUFFERING_TOOL│
     │                    │缓冲到 </tool_call│
     │                    └──────┬───────┘
     │                           │
     │                           │ 解析为 tool_use
     │                           ▼
     │                    ┌──────────────┐
     │                    │   NORMAL     │
     │                    └──────────────┘
     │                           
     │ 匹配失败                   
     │ (如 <div>, <span>)        
     └────────────────────────────┘
```

---

## [Unreleased] - 2026-04-09

### 🆕 新功能

- **新增 `count_tokens` 端点拦截** (`handlers.py`)
  - Claude Code 自动压缩上下文时会调用 `POST /v1/messages/count_tokens`
  - LM Studio 不支持此端点，导致请求失败后 Agent 停止执行任务
  - Router 现在直接拦截该请求，返回 mock 响应 `{"input_tokens": <estimated>}`
  - Token 数按请求体字符数 / 4 粗估，满足 Claude Code 判断是否需要压缩的需求

## [Unreleased] - 2026-04-08

### 🐛 Bug 修复

#### P0 - 严重问题

- **修复 `handle_anthropic_direct` 变量作用域 Bug** (`handlers.py`)
  - 在 `try` 块前初始化 `request_data` 和 `target_url` 变量
  - 避免 `json.loads` 失败时 `except` 块抛出 `UnboundLocalError`

- **修复 `compress_log_data` 破坏性修改原对象 Bug** (`utils.py`)
  - 使用列表拼接和 `list()` 创建新对象，避免修改原始数据
  - 防止压缩后的数据影响后续处理逻辑

#### P1 - 重要问题

- **修复双重 JSON 序列化 Bug** (`utils.py`)
  - `changes` 类型日志直接写入已序列化的 JSON 字符串
  - 避免二次 `json.dumps()` 导致日志中出现转义字符串

- **修复 `stop_reason` 缺少 `"end_turn"` 处理** (`stop_reason_fixer.py`)
  - 在两处检查列表中添加 `"end_turn"` 值
  - 确保 LM Studio 返回 `end_turn` 时也能正确修复为 `tool_use`

- **修复日志文件路径硬编码** (`utils.py`, `processors.py`)
  - 使用 `pathlib.Path(__file__).parent / "logs"` 基于脚本所在目录的绝对路径
  - 自动创建 `logs` 目录，避免从其他目录启动服务时路径错误
  - 统一导出 `MESSAGE_LOG_FILE` 和 `ERROR_LOG_FILE` 常量供其他模块使用

#### P2 - 中等问题

- **修复 OpenAI 响应只处理第一个工具调用** (`processors.py`)
  - 改用 OpenAI 标准的 `tool_calls` 数组格式（而非旧的 `function_call`）
  - 支持多个工具调用，遍历所有 `parsed_tools` 并生成对应的 `tool_calls` 条目
  - 每个工具调用添加 `id` 和 `type` 字段，符合 OpenAI API 规范
  - 记录日志输出创建的工具调用数量

### 📝 技术细节

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `handlers.py` | Bug 修复 | 变量作用域修复 |
| `utils.py` | Bug 修复 + 改进 | 数据拷贝、序列化、日志路径 |
| `processors.py` | 功能改进 | 多工具调用支持、日志路径 |
| `stop_reason_fixer.py` | Bug 修复 | 添加 end_turn 处理 |

### ⚠️ 注意事项

- OpenAI 格式的 `tool_calls` 数组修改**尚未在实际环境中测试**
- 当前仅测试了 Anthropic 格式 (`/v1/messages`)
- 如需使用 OpenAI 格式，建议先进行充分测试
