# Router 中转服务设计

## 背景

根据 [BUGS Running Qwen 3.5 in agentic setups](../BUGS%20Running%20Qwen%203.5%20in%20agentic%20setups%20(coding%20agents,%20function%20calling%20loops).txt)，当前有两个解决方案：

1. **方法 2**: Add a client-side safety net - 3 small functions that catch what servers miss
2. **方法 3**: Set compat flags (Pi SDK / OpenAI-compatible clients)

## 设计思路

由于当前使用的是 Claude Code（OpenCode）这类集成好的 Agent 工具，无法控制其 API 调用格式。因此需要构建一个**中转服务**，位于：

```
Claude Code (Agent) <-> Router <-> 推理应用 (LM Studio)
```

## 功能需求

### 1. 下行处理 (Router → Agent)

对返回给 Agent 的消息进行 **方法 2** 处理，修复工具调用相关的格式问题。

### 2. 上行处理 (Agent → Router)

对 Agent 发送的消息进行 **方法 3** 转码，转换成 Qwen 能够识别的格式。

### 非流式处理设计

**强制禁用流式传输**，采用非流式处理方案：

- **原因**：流式传输无法保证 XML 工具调用和 think 标签的完整性处理
- **实现**：Router 自动将请求中的 `stream=true` 改为 `stream=false`，适用于所有请求类型（Anthropic Messages API 和 OpenAI Chat Completions API）
- **具体实现**：在 `handle_anthropic_direct` 和 `handle_openai_compat` 方法中，都会在转发请求前设置 `request_data['stream'] = False`
- **兼容性**：Claude Code 支持非流式模式，会自动适配
- **优势**：简化处理流程，确保消息处理的完整性和正确性

## 流式传输未来优化

### 当前限制

当前实现完全禁用了流式传输，这会影响用户体验，特别是对于长文本生成。

### 未来优化方向

1. **基于标签检测的流式传输**：
   - 实时发送普通文本
   - 检测到工具调用标签时开始缓存
   - 工具调用完整后处理并发送

2. **技术挑战**：
   - 内容完整性：确保 XML 工具调用的完整解析
   - 边界检测：准确识别工具调用的开始和结束
   - 实时性与正确性的平衡

3. **参考文档**：
   - 详细的流式传输分析请参考 `StreamingAnalysis.md`

## 部署架构

```
                    ┌─────────────────┐
                    │  Claude Code    │
                    │   (Agent)       │
                    └────────┬────────┘
                             │
                   (暴露端口给 Agent)
                             │
                    ┌────────▼────────┐
                    │     Router      │
                    │  (中转服务)      │
                    │                 │
                    │ • 下行：方法 2 修复  │
                    │ • 上行：方法 3 转码 │
                    └────────┬────────┘
                             │
                   (配置推理 APP 地址)
                             │
                    ┌────────▼────────┐
                    │  LM Studio      │
                    │  (推理后端)     │
                    └─────────────────┘
```

## 实现状态

- [x] 基础中转功能
- [x] 配置推理 APP 的地址和端口
- [x] 下行消息按方法 2 处理（XML工具调用解析、Think标签移除、Finish Reason修复）
- [x] 上行消息按方法 3 转码（兼容标志设置）
- [x] 非流式处理设计（强制 stream=false）
- [x] 日志记录功能
- [x] OpenAI 兼容接口支持
- [x] 功能拆分：消息处理函数拆分为独立文件
- [x] 配置系统：添加 config.json 配置文件
- [x] 日志优化：添加压缩功能，避免重复内容

> **注**: 当前仅针对 Qwen 模型进行优化，所有处理函数已实现并测试通过。

##### 开发记录

### 文件拆分

#### 第一次功能拆分（基础功能）

将消息处理函数拆分为独立文件，避免代码截断问题：

- **xml_parser.py** - `parse_qwen_xml_tools`：解析 Qwen XML 格式的工具调用
- **think_remover.py** - `strip_think_tags`：移除 think 标签及其内容
- **stop_reason_fixer.py** - `fix_stop_reason`：修复 finish_reason
- **compatibility_flags.py** - `add_compatibility_flags`：添加兼容标志

#### 第二次文件拆分（架构优化）

将主服务文件 `router_server.py` 拆分为多个功能模块，解决代码复杂度问题：

- **config.py**：配置管理，负责配置加载和默认值定义
- **logger.py**：日志管理，负责日志配置和处理器设置
- **utils.py**：通用工具函数，包含压缩、格式化等辅助功能
- **processors.py**：响应处理器，负责处理 Anthropic 和 OpenAI 格式的响应
- **handlers.py**：HTTP 请求处理器，负责处理各种 HTTP 请求
- **router_server.py**：主入口文件，负责服务器启动和模块导入

#### 目录结构优化

创建专门的目录用于存放日志和文档：

- **logs/**：日志目录
  - `router.log`：主日志文件
  - `router_message.log`：消息日志文件
  - `router_error.log`：错误日志文件
- **docs/**：文档目录

#### 拆分原因

1. **代码复杂度**：原始 `router_server.py` 文件包含约 650+ 行代码，维护困难
2. **职责不清**：单个文件包含多个功能模块，违反单一职责原则
3. **可读性差**：文件过大导致阅读和理解困难
4. **协作困难**：多人开发时容易产生冲突

#### 拆分过程

1. **分析现有代码**：识别各个功能模块
2. **创建新文件**：根据功能职责创建独立文件
3. **移动代码**：将相应功能模块移动到新文件中
4. **更新导入**：修改所有文件的导入语句
5. **测试验证**：确保拆分后的代码功能正常

#### 拆分效果

- **代码结构清晰**：每个文件职责单一，易于理解和维护
- **模块独立性**：各模块之间耦合度低，便于单独测试和修改
- **可读性提高**：单个文件代码量减少，提高了代码的可读性
- **便于协作**：多人开发时可以同时修改不同模块，减少冲突
- **可扩展性增强**：模块化设计便于添加新功能

### 配置系统

添加了 `config.json` 配置文件，支持以下配置项：

- **server**：Router 服务的主机和端口
- **target**：目标推理应用的主机和端口
- **logging**：
  - `log_all_traffic`：是否记录完整请求响应
  - `compress_log_data`：是否压缩日志数据（替换 system 和 tools 字段）
  - `router_log_max_bytes`：日志文件大小限制
  - `router_log_backup_count`：日志备份数量
- **features**：功能开关配置
  - `force_stream_false`：强制禁用流式传输（默认：true）
  - `parse_xml_tools`：解析 Qwen XML 工具调用（默认：true）
  - `remove_think_tags`：移除 think 标签（默认：true）
  - `fix_stop_reason`：修复 stop_reason（默认：true）
  - `enable_thinking`：控制 Qwen 是否生成思维链（默认：false）

### 日志系统

实现了完善的日志记录系统：

- **双输出**：同时输出到控制台和文件
- **按大小滚动**：自动管理日志文件大小
- **日志压缩**：可配置的日志数据压缩，避免重复内容

### 2026-04-08 日志系统优化

- **主日志压缩**：修改 `compress_log_data` 函数，只保留最近的两条消息，前面的消息会被省略显示
- **完整消息单独记录**：创建 `router_messages.log` 文件，只记录最新的一条完整消息
- **日志格式优化**：使用 ASCII 箭头（--> 和 <--）来区分请求和响应方向
- **日志系统稳定性**：确保日志记录的可靠性和性能
- **详细记录**：记录完整的处理过程和状态变化

### 遇到的问题与解决方案

1. **代码截断问题**：
   - **问题**：包含正则表达式的代码在写入文件时被截断
   - **解决方案**：将功能拆分为独立文件，避免大文件写入

2. **流式传输挑战**：
   - **问题**：流式传输无法保证 XML 工具调用和 think 标签的完整性处理
   - **解决方案**：采用非流式处理，强制禁用流式传输

3. **日志体积过大**：
   - **问题**：system 和 tools 字段重复出现，导致日志体积过大
   - **解决方案**：实现日志压缩功能，替换重复内容

4. **API 格式兼容**：
   - **问题**：不同 Agent 可能使用不同的 API 格式
   - **解决方案**：支持 Anthropic Messages API 和 OpenAI Chat Completions API

### 兼容标志分析（2026-04-09）

根据 [BUGS Running Qwen 3.5 in agentic setups](../BugAnalysis/Jinja/BUGS%20Running%20Qwen%203.5%20in%20agentic%20setups%20(coding%20agents,%20function%20calling%20loops).txt) 的说明，兼容标志用于告诉推理服务器如何处理请求：

| 标志 | 值 | 作用 | 当前状态 |
|------|-----|------|---------|
| thinkingFormat | "qwen" | 使用 `enable_thinking` 而非 OpenAI reasoning 格式 | CC 的 thinking/Effort 机制不明确，Qwen 有不同推理参数推荐，暂不处理 |
| maxTokensField | "max_tokens" | 使用 `max_tokens` 而非 `max_completion_tokens` | CC 默认发送 `max_tokens`，无需修改 |
| supportsDeveloperRole | false | 使用 system role 而非 developer role | CC 使用 system role，无需修改 |
| supportsStrictMode | false | 不在 tool schemas 中发送 `strict: true` | 需要研究 CC 是否发送 strict，暂不处理 |

**重要发现**：

- 兼容标志是**请求参数**，应在请求阶段修改，类似于强制设置 `stream=false`
- 正确的做法是在上行处理（Agent → Router → 推理服务器）中修改请求内容
- 之前在响应中添加这些字段是错误的做法，已移除
- 如果客户端无法配置这些参数，Router 应该拦截请求并添加必要的兼容标志

**后续研究方向**：

1. 研究 Claude Code 的 thinking 和 Effort 机制
2. 研究 Qwen 开启/关闭 thinking 时的推荐推理参数
3. 研究 CC 是否在 tool schemas 中发送 `strict: true`
4. 研究 CC 内部如何定义和使用这些兼容标志
5. 在 `handlers.py` 的上行处理中添加兼容标志修改逻辑（类似 `stream=false`）

**已移除**：移除了 `processors.py` 中对 `add_compatibility_flags` 的调用，保留 `compatibility_flags.py` 文件供未来参考。

### 代码简化（2026-04-09）

为了专注于 Claude Code 集成，删除了以下功能：

- **OpenAI 兼容模式**：移除了 `/v1/chat/completions` 路径处理
- **直接转发模式**：移除了其他路径的直接转发功能
- **OpenAI 响应处理**：移除了 `process_openai_response` 方法
- **相关导入**：移除了 OpenAI 相关的导入和依赖

当前 Router 仅支持：

- `/v1/messages` 路径的 Anthropic 格式请求
- 流式和非流式响应处理
- Qwen 特定的响应修正（XML 工具调用解析、think 标签移除、stop_reason 修复）

**架构简化**：

- 减少了代码复杂度和维护成本
- 专注于 Claude Code 与 Qwen 模型的集成
- 便于后续优化和扩展

1. **Think 标签移除**：
   - 移除 Qwen 生成的 think 标签及其内容
   - 确保返回给 Agent 的内容干净

2. **Stop Reason 修复**：
   - 当存在工具调用时，将 stop_reason 修复为 "tool_use"
   - 确保 Agent 正确识别工具调用结束

3. **非流式处理**：
   - 自动将请求中的 `stream=true` 改为 `stream=false`
   - 确保消息完整处理后再返回给 Agent

### 部署与使用

1. **配置**：修改 `config.json` 文件设置服务地址和目标地址
2. **启动**：在 `Router` 目录下运行 `python router_server.py`
3. **使用**：将 Claude Code 的 API 地址设置为 `http://localhost:25565`

### 性能与稳定性

- **轻量级**：基于 Python 标准库，无额外依赖
- **高性能**：处理速度快，内存占用低
- **可靠**：完善的错误处理和日志记录
- **可扩展**：模块化设计，易于添加新功能

## 流式处理实现（2026-04-09）

### 实现方案

采用**缓冲处理**方案：

```
LM Studio 流式数据 → 累积缓冲 → 完整响应 → 处理 → 重新生成流式数据 → CC
```

### 新增文件

- **stream_processor.py** - 流式响应处理器

### 修改文件

- **handlers.py** - 使用流式处理器，支持多线程模式
- **think_remover.py** - 修复正则表达式（移除 `\?`）

### 关键改动

#### 1. 多线程模式

```python
# router_server.py
from socketserver import ThreadingTCPServer

server = ThreadingTCPServer(...)
```

支持同时处理多个请求。

#### 2. SSE 解析

- 解析 `event:` 和 `data:` 行
- 正确处理跨 chunk 的事件

#### 3. 事件累积

```python
message_start → content_block_start → content_block_delta → message_stop
```

#### 4. 内容处理

- 与非流式模式相同的处理逻辑
- XML 工具调用解析
- Think 标签移除
- Stop reason 修复

#### 5. 重新流式化

处理完成后重新生成 SSE 事件序列发送给 CC。

### 注意事项

1. **原生 thinking block**：直接保留，不做修改
2. **Text 中的 think 标签**：通过 `strip_think_tags()` 移除
3. **流式 vs 非流式**：两种模式共用相同的内容处理逻辑
4. **调试日志**：添加了详细的 DEBUG 级别日志
5. **Connection 关闭**：流式传输结束后主动关闭连接

### 测试步骤

1. 启动 Router 服务
2. 在 CC 中发送消息
3. 观察日志：
   - `Total events received` - 收到的事件数
   - `Stream content processed` - 内容已处理
   - `Streaming response completed` - 流式完成
4. 观察 CC 显示：
   - think 标签是否被移除
   - 工具调用是否正常工作
   - stop_reason 是否正确

### 已知问题与修复

#### think_remover.py 正则错误

```python
# 修复前
r'<think\?>[\s\S]*?</think\?>'

# 修复后
r'<think>[\s\S]*?</think>'
```

#### SSE 解析跨 chunk

保留未完成的行，避免事件分割：

```python
lines = buffer.split(b'\n')
buffer = lines[-1]  # 保留最后一行（未完成）
```
