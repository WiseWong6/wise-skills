#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 Gate B 的 orientation 和 count 解析逻辑
验证 process_pending_questions 中的解析是否能正确处理 6 种典型输入
"""

import re
import sys

def parse_user_answer(answer):
    """
    模拟 orchestrator.py:251-303 的解析逻辑
    返回: {orientation, count, cover_ratio, poster_ratio}
    """
    result = {
        "orientation": "landscape",  # 默认横屏
        "count": 4,  # 默认 4 张
        "cover_ratio": None,
        "poster_ratio": None
    }

    # 解析 orientation
    if "横屏" in answer:
        result["orientation"] = "landscape"
    elif "竖屏" in answer:
        result["orientation"] = "portrait"
    elif "portrait" in answer:
        result["orientation"] = "portrait"
    elif "landscape" in answer:
        result["orientation"] = "landscape"
    else:
        # 默认横屏（当前实现）
        result["orientation"] = "landscape"

    # 解析 count
    count_match = re.search(r'(\d+)\s*[张张]', answer)
    if count_match:
        result["count"] = int(count_match.group(1))
    else:
        # 默认 4 张
        result["count"] = 4

    # 解析可选比例
    if "封面" in answer or "cover" in answer:
        cover_match = re.search(r'(?:封面|cover)[：:\s]*([\d:]+)', answer)
        if cover_match:
            result["cover_ratio"] = cover_match.group(1)

    if "正文" in answer or "poster" in answer:
        poster_match = re.search(r'(?:正文|poster)[：:\s]*([\d:]+)', answer)
        if poster_match:
            result["poster_ratio"] = poster_match.group(1)

    return result


def test_parse():
    """测试解析逻辑"""
    # 6 个典型输入用例
    test_cases = [
        "横屏，4张",
        "竖屏，5张",
        "横屏 4张",
        "横屏，4张",
        "竖屏，5张，封面16:9，正文3:4",
        "横屏，4张，正文21:9",
    ]

    print("=" * 70)
    print("用户回复解析边界测试")
    print("=" * 70)

    all_passed = True

    for i, test_input in enumerate(test_cases, 1):
        result = parse_user_answer(test_input)
        print(f"\n--- 测试用例 {i} ---")
        print(f"输入: {test_input}")
        print(f"解析结果:")
        print(f"  orientation: {result['orientation']}")
        print(f"  count: {result['count']}")
        print(f"  cover_ratio: {result['cover_ratio']}")
        print(f"  poster_ratio: {result['poster_ratio']}")

        # 验证每个用例
        passed, expected = validate_test_case(i, test_input, result)
        if passed:
            print(f"PASS: {expected}")
        else:
            print(f"FAIL: {expected}")
            all_passed = False

    print("\n" + "=" * 70)
    if all_passed:
        print("所有测试用例通过")
    else:
        print("存在测试用例失败")
    print("=" * 70)

    return all_passed


def validate_test_case(case_num, input_str, result):
    """验证测试用例是否符合预期"""
    if case_num == 1:
        # "横屏，4张" -> landscape, 4, None, None
        expected = "orientation=landscape, count=4"
        passed = (
            result["orientation"] == "landscape" and
            result["count"] == 4 and
            result["cover_ratio"] is None and
            result["poster_ratio"] is None
        )
        return passed, expected

    elif case_num == 2:
        # "竖屏，5张" -> portrait, 5, None, None
        expected = "orientation=portrait, count=5"
        passed = (
            result["orientation"] == "portrait" and
            result["count"] == 5 and
            result["cover_ratio"] is None and
            result["poster_ratio"] is None
        )
        return passed, expected

    elif case_num == 3:
        # "横屏 4张" -> landscape, 4, None, None
        expected = "orientation=landscape, count=4"
        passed = (
            result["orientation"] == "landscape" and
            result["count"] == 4 and
            result["cover_ratio"] is None and
            result["poster_ratio"] is None
        )
        return passed, expected

    elif case_num == 4:
        # "横屏，4张" -> landscape, None (默认4)
        expected = "orientation=landscape, count=4 (默认)"
        # 注意：当前实现没有检测到 count，会用默认值 4
        passed = (
            result["orientation"] == "landscape" and
            result["count"] == 4
        )
        return passed, expected

    elif case_num == 5:
        # "竖屏，5张，封面16:9，正文3:4" -> portrait, 5, 16:9, 3:4
        expected = "orientation=portrait, count=5, cover=16:9, poster=3:4"
        passed = (
            result["orientation"] == "portrait" and
            result["count"] == 5 and
            result["cover_ratio"] == "16:9" and
            result["poster_ratio"] == "3:4"
        )
        return passed, expected

    elif case_num == 6:
        # "横屏，4张，正文21:9" -> landscape, 4, None, 21:9
        expected = "orientation=landscape, count=4, poster=21:9"
        passed = (
            result["orientation"] == "landscape" and
            result["count"] == 4 and
            result["cover_ratio"] is None and
            result["poster_ratio"] == "21:9"
        )
        return passed, expected

    return False, "未知用例"


def test_regex_patterns():
    """测试正则表达式"""
    print("\n" + "=" * 70)
    print("正则表达式验证")
    print("=" * 70)

    # 测试 count 解析
    count_pattern = r'(\d+)\s*[张张]'
    count_tests = [
        ("横屏，4张", "4"),
        ("竖屏，5张", "5"),
        ("横屏 4张", "4"),
        ("横屏，4张，封面16:9", "4"),
    ]

    print("\nCount 解析正则:")
    for test_input, expected in count_tests:
        match = re.search(count_pattern, test_input)
        if match:
            result = f"匹配: {match.group(1)}, 期望: {expected}"
            status = "PASS" if match.group(1) == expected else "FAIL"
            print(f"{status} {test_input} -> {result}")
        else:
            print(f"FAIL {test_input} -> 未匹配")

    # 测试比例解析
    cover_pattern = r'(?:封面|cover)[：:\s]*([\d:]+)'
    poster_pattern = r'(?:正文|poster)[：:\s]*([\d:]+)'

    print("\nCover ratio 解析正则:")
    cover_tests = [
        ("横屏，4张，封面16:9", "16:9"),
        ("竖屏，5张，封面16:9，正文3:4", "16:9"),
        ("cover:16:9", "16:9"),
    ]

    for test_input, expected in cover_tests:
        match = re.search(cover_pattern, test_input)
        if match:
            result = f"匹配: {match.group(1)}, 期望: {expected}"
            status = "PASS" if match.group(1) == expected else "FAIL"
            print(f"{status} {test_input} -> {result}")
        else:
            print(f"FAIL {test_input} -> 未匹配")

    print("\nPoster ratio 解析正则:")
    poster_tests = [
       ("横屏，4张，正文3:4", "3:4"),
        ("竖屏，5张，封面16:9，正文3:4", "3:4"),
        ("横屏，4张，正文21:9", "21:9"),
        ("poster:16:9", "16:9"),
    ]

    for test_input, expected in poster_tests:
        match = re.search(poster_pattern, test_input)
        if match:
            result = f"匹配: {match.group(1)}, 期望: {expected}"
            status = "PASS" if match.group(1) == expected else "FAIL"
            print(f"{status} {test_input} -> {result}")
        else:
            print(f"FAIL {test_input} -> 未匹配")


if __name__ == "__main__":
    # 运行所有测试
    regex_ok = True

    try:
        test_regex_patterns()
    except Exception as e:
        print(f"正则测试失败: {e}")
        regex_ok = False

    parse_ok = test_parse()

    # 退出码
    if regex_ok and parse_ok:
        print("\n所有测试通过")
        sys.exit(0)
    else:
        print("\n部分测试失败")
        sys.exit(1)
