import re
import json
import uuid

def parse_qwen_xml_tools(text):
    """解析Qwen XML工具调用"""
    try:
        results = []
        # 只匹配function标签
        func_re = re.compile(r'<function=([\w.-]+)>([\s\S]*?)</function>')
        for m in func_re.finditer(text):
            func_name = m.group(1).strip()
            params_text = m.group(2)
            args = {}
            param_re = re.compile(r'<parameter=([\w.-]+)>([\s\S]*?)</parameter>')
            for p in param_re.finditer(params_text):
                k = p.group(1).strip()
                v = p.group(2).strip()
                try:
                    v = json.loads(v)
                except Exception:
                    pass
                args[k] = v
            results.append({
                "id": f"call_{uuid.uuid4().hex[:24]}",
                "type": "function",
                "function": {
                    "name": func_name,
                    "arguments": json.dumps(args)
                }
            })
        return results
    except Exception:
        return []

def parse_qwen_xml_tools_ClaudeCode(text):
    """解析Qwen XML工具调用为Claude Code格式"""
    
    ## Thinking 里面发现的.
    ## <tool_call>
    # \n<function=Bash>\n
    # <parameter=command>\n
    # cat \"d:/happy/BugAnalysis/BUGS Running Qwen 3.5 in agentic setups (coding agents, function calling loops).txt\"\n
    # </parameter>\n
    # <parameter=description>\n
    # Read BUGS text file\n
    # </parameter>\n
    # </function>
    # \n</tool_call>    
    
    ## 需要生成为列表.
    # {
    #   "type": "tool_use",
    #   "id": "139567541",
    #   "name": "Read",
    #   "input": {
    #     "file_path": "/d/happy/Router/test_client.py"
    #     }
    # },
    # {
    #   "type": "tool_use",
    #   "id": "545826013",
    #   "name": "Glob",
    #   "input": {
    #     "path": "/d/happy/BugAnalysis",
    #     "pattern": "**/*"
    #     }
    # }
    try:
        results = []
        # 匹配包含tool_call标签的function
        func_re = re.compile(r'<tool_call>\s*<function=([\w.-]+)>([\s\S]*?)</function>\s*</tool_call>')
        for m in func_re.finditer(text):
            func_name = m.group(1).strip()
            params_text = m.group(2)
            input_args = {}
            param_re = re.compile(r'<parameter=([\w.-]+)>([\s\S]*?)</parameter>')
            for p in param_re.finditer(params_text):
                k = p.group(1).strip()
                v = p.group(2).strip()
                try:
                    v = json.loads(v)
                except Exception:
                    pass
                input_args[k] = v
            # 生成符合Claude Code格式的工具调用
            results.append({
                "type": "tool_use",
                "id": str(uuid.uuid4().int % 10**9),  # 生成9位数字ID
                "name": func_name,
                "input": input_args
            })
        return results
    except Exception:
        return []