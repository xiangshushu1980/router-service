# Router 配置文件说明

配置文件 `config.json` 用于控制 Router 服务的所有行为。

## 配置结构

```json
{
    "server": { ... },
    "target": { ... },
    "logging": { ... },
    "features": { ... }
}
```

---

## server - 服务配置

Router 服务自身的网络配置。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `host` | string | `"localhost"` | Router 监听地址 |
| `port` | int | `25566` | Router 监听端口 |

**示例：**
```json
{
    "server": {
        "host": "localhost",
        "port": 25566
    }
}
```

---

## target - 目标服务配置

本地推理后端（如 LM Studio、Ollama）的连接配置。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `host` | string | `"localhost"` | 目标服务地址 |
| `port` | int | `1234` | 目标服务端口 |

**示例：**
```json
{
    "target": {
        "host": "localhost",
        "port": 1234
    }
}
```

---

## logging - 日志配置

日志记录相关配置。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `log_all_traffic` | bool | `true` | 是否记录所有请求响应 |
| `compress_log_data` | bool | `true` | 是否压缩日志数据 |
| `router_log_max_bytes` | int | `1048576` | 日志文件最大字节数（1MB） |
| `router_log_backup_count` | int | `5` | 日志备份数量 |
| `debug` | bool | `false` | 是否启用 DEBUG 级别日志 |

### compress_log_data 详细说明

当设置为 `true` 时，日志会进行智能压缩：

| 字段 | 处理方式 |
|------|----------|
| `system` | 替换为 `"... (truncated) ..."` |
| `tools` | 替换为 `"... (truncated) ..."` |
| `messages` | 只保留最近 2 条消息 |

**目的：** API 请求中 system prompt 和 tools 定义通常很长且重复，压缩后可大幅减少日志体积。

**注意：** 完整消息会单独记录到 `logs/router_message.log`，不受此配置影响。

**示例：**
```json
{
    "logging": {
        "log_all_traffic": true,
        "compress_log_data": true,
        "router_log_max_bytes": 1048576,
        "router_log_backup_count": 5,
        "debug": true
    }
}
```

---

## features - 功能开关

控制 Router 的核心处理功能。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `force_stream_false` | bool | `false` | 强制禁用流式传输 |
| `parse_xml_tools` | bool | `true` | 解析 XML 格式工具调用 |
| `remove_think_tags` | bool | `true` | 移除 think 标签 |
| `fix_stop_reason` | bool | `true` | 修复 stop_reason |
| `enable_thinking` | bool/null | `null` | 启用 Qwen 思维链模式 |
| `smart_streaming` | bool | `true` | 启用智能流式处理 |

### 功能详解

#### force_stream_false
强制将流式请求转为非流式请求。适用于不支持流式传输的推理后端。

#### parse_xml_tools
解析本地模型生成的 XML 格式工具调用，转换为 Claude Code 期望的 JSON 格式。

**支持的 XML 格式：**
```xml
<tool_call)>
{"name": "tool_name", "arguments": {...}}
</tool_call)>
```

#### remove_think_tags
移除响应中的 `<think...</think)>` 标签及其内容。本地模型常在响应中包含思维链内容，此功能可清理这些标签。

#### fix_stop_reason
当响应包含工具调用时，自动将 `stop_reason` 修正为 `"tool_use"`，确保 Claude Code 正确识别工具调用。

#### enable_thinking
控制 Qwen 模型是否生成思维链：
- `true`: 启用思维链生成
- `false`: 禁用思维链生成
- `null`: 不修改请求，使用模型默认行为

#### smart_streaming
启用智能流式处理模式，在流式传输过程中实时处理内容，减少延迟。

**示例：**
```json
{
    "features": {
        "force_stream_false": false,
        "parse_xml_tools": true,
        "remove_think_tags": true,
        "fix_stop_reason": true,
        "enable_thinking": null,
        "smart_streaming": true
    }
}
```

---

## 完整配置示例

```json
{
    "server": {
        "host": "localhost",
        "port": 25566
    },
    "target": {
        "host": "localhost",
        "port": 1234
    },
    "logging": {
        "log_all_traffic": true,
        "compress_log_data": true,
        "router_log_max_bytes": 1048576,
        "router_log_backup_count": 5,
        "debug": true
    },
    "features": {
        "force_stream_false": false,
        "parse_xml_tools": true,
        "remove_think_tags": true,
        "fix_stop_reason": true,
        "enable_thinking": null,
        "smart_streaming": true
    }
}
```

---

## 常见配置场景

### 场景 1：调试模式

启用详细日志，便于排查问题：

```json
{
    "logging": {
        "log_all_traffic": true,
        "compress_log_data": false,
        "debug": true
    }
}
```

### 场景 2：生产环境

减少日志体积，禁用调试：

```json
{
    "logging": {
        "log_all_traffic": false,
        "compress_log_data": true,
        "debug": false
    }
}
```

### 场景 3：禁用所有处理

直接转发请求，不做任何处理：

```json
{
    "features": {
        "force_stream_false": false,
        "parse_xml_tools": false,
        "remove_think_tags": false,
        "fix_stop_reason": false,
        "enable_thinking": null,
        "smart_streaming": false
    }
}
```
