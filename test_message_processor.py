import json
from message_processor import strip_think_tags, fix_stop_reason, add_compatibility_flags

def test_strip_think_tags():
    """测试Think标签移除功能"""
    test_cases = [
        ("Hello <think>test</think> world", "Hello  world"),
        ("<think>思考中...</think>Hello", "Hello"),
        ("Hello world", "Hello world"),
        ("<think></think>Empty", "Empty"),
    ]
    
    print("测试Think标签移除功能...")
    all_passed = True
    
    for input_text, expected in test_cases:
        result = strip_think_tags(input_text)
        passed = result == expected
        all_passed = all_passed and passed
        status = "✓" if passed else "✗"
        print(f"{status} '{input_text}' -> '{result}'")
    
    return all_passed

def test_fix_stop_reason():
    """测试Finish Reason修复功能"""
    test_cases = [
        # 包含工具调用的情况
        ({
            "content": [{"type": "tool_call", "name": "test"}],
            "stop_reason": "stop"
        }, "tool_use"),
        ({
            "content": [{"type": "tool_call", "name": "test"}],
            "stop_reason": "error"
        }, "tool_use"),
        ({
            "content": [{"type": "tool_call", "name": "test"}],
            "stop_reason": "eos_token"
        }, "tool_use"),
        ({
            "content": [{"type": "tool_call", "name": "test"}],
            "stop_reason": ""
        }, "tool_use"),
        ({
            "content": [{"type": "tool_call", "name": "test"}],
            "stop_reason": None
        }, "tool_use"),
        # 不包含工具调用的情况
        ({
            "content": [{"type": "text", "text": "Hello"}],
            "stop_reason": "stop"
        }, "stop"),
    ]
    
    print("\n测试Finish Reason修复功能...")
    all_passed = True
    
    for input_message, expected in test_cases:
        result = fix_stop_reason(input_message.copy())
        passed = result.get("stop_reason") == expected
        all_passed = all_passed and passed
        status = "✓" if passed else "✗"
        print(f"{status} stop_reason='{input_message.get('stop_reason')}' -> '{result.get('stop_reason')}'")
    
    return all_passed

def test_add_compatibility_flags():
    """测试兼容标志设置功能"""
    test_payload = {
        "model": "test-model",
        "messages": [{"role": "user", "content": "Hello"}]
    }
    
    expected_flags = {
        "thinkingFormat": "qwen",
        "maxTokensField": "max_tokens",
        "supportsDeveloperRole": False,
        "supportsStrictMode": False
    }
    
    print("\n测试兼容标志设置功能...")
    
    result = add_compatibility_flags(test_payload.copy())
    
    all_passed = True
    for flag_name, expected_value in expected_flags.items():
        actual_value = result.get(flag_name)
        passed = actual_value == expected_value
        all_passed = all_passed and passed
        status = "✓" if passed else "✗"
        print(f"{status} {flag_name}='{actual_value}'")
    
    return all_passed

def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("运行消息处理模块测试")
    print("=" * 60)
    
    tests = [
        test_strip_think_tags,
        test_fix_stop_reason,
        test_add_compatibility_flags,
    ]
    
    passed_count = 0
    total_count = len(tests)
    
    for test in tests:
        if test():
            passed_count += 1
    
    print("\n" + "=" * 60)
    print(f"测试结果: {passed_count}/{total_count} 通过")
    print("=" * 60)
    
    return passed_count == total_count

if __name__ == "__main__":
    run_all_tests()