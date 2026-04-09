# Router 更新日志

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
