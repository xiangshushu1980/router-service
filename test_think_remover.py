#!/usr/bin/env python3
"""测试 think_remover.py 的功能"""

from think_remover import strip_think_tags

def test_strip_think_tags():
    """测试移除 think 标签的功能"""
    test_cases = [
        # 测试用例 1: 完整的 <think>...</think> 标签对
        {
            "input": "<think>这是思考内容</think> 这是实际内容",
            "expected": "这是实际内容",
            "description": "完整的 <think>...</think> 标签对"
        },
        # 测试用例 2: 单独的 </think> 标签
        {
            "input": "</think> 这是实际内容",
            "expected": "这是实际内容",
            "description": "单独的 </think> 标签"
        },
        # 测试用例 3: 标签后的空白内容
        {
            "input": "<think>思考内容</think>   \n  实际内容   \n",
            "expected": "实际内容",
            "description": "标签后的空白内容"
        },
        # 测试用例 4: 没有 think 标签的内容
        {
            "input": "没有 think 标签的内容",
            "expected": "没有 think 标签的内容",
            "description": "没有 think 标签的内容"
        },
        # 测试用例 5: 空字符串
        {
            "input": "",
            "expected": "",
            "description": "空字符串"
        },
        # 测试用例 6: 只有空白字符
        {
            "input": "   \n  \t  ",
            "expected": "",
            "description": "只有空白字符"
        },
        # 测试用例 7: 只有 think 标签
        {
            "input": "<think>只有思考内容</think>",
            "expected": "",
            "description": "只有 think 标签"
        },
        # 测试用例 8: 只有单独的 </think> 标签
        {
            "input": "</think>",
            "expected": "",
            "description": "只有单独的 </think> 标签"
        },
        # 测试用例 9: 单独的 <think> 标签
        {
            "input": "<think> 这是实际内容",
            "expected": "这是实际内容",
            "description": "单独的 <think> 标签"
        },
        # 测试用例 10: 只有单独的 <think> 标签
        {
            "input": "<think>",
            "expected": "",
            "description": "只有单独的 <think> 标签"
        }
    ]
    
    passed = 0
    failed = 0
    
    for i, test_case in enumerate(test_cases, 1):
        input_text = test_case["input"]
        expected = test_case["expected"]
        description = test_case["description"]
        
        result = strip_think_tags(input_text)
        
        if result == expected:
            print(f"✓ 测试用例 {i}: {description}")
            print(f"  输入: '{input_text}'")
            print(f"  输出: '{result}'")
            print(f"  预期: '{expected}'")
            print()
            passed += 1
        else:
            print(f"✗ 测试用例 {i}: {description}")
            print(f"  输入: '{input_text}'")
            print(f"  输出: '{result}'")
            print(f"  预期: '{expected}'")
            print()
            failed += 1
    
    print(f"测试结果: {passed} 个通过, {failed} 个失败")
    
    if failed == 0:
        print("所有测试用例都通过了！")
    else:
        print(f"有 {failed} 个测试用例失败，需要修复。")

if __name__ == "__main__":
    test_strip_think_tags()
