#!/usr/bin/env python3
"""
Markdown 格式化器 - 添加空格与规范化标点

根据用户需求执行格式化：
1. 中英文之间添加空格
2. 中文标点符号规范化
3. 引号统一为中文引号
4. 数字与中文之间添加空格
"""

import re
from typing import List, Tuple


class MarkdownFormatter:
    """Markdown 格式化器：添加空格、规范化标点"""

    # 受保护区域的正则模式
    PROTECTED_PATTERNS = {
        'code_block': r'```[\s\S]*?```',           # 代码块
        'bold': r'\*\*[^*]+\*\*',                    # 加粗 **text**
        'table': r'(?:(?:^\|.*?\|$\n?)+)',          # Markdown 表格（多行）
        'inline_code': r'(?<!`)`(?!`)[^`]+?(?<!`)`(?!`)',  # 行内代码
        'link': r'\[[^\]]*\]\([^)]*\)',             # 链接 [text](url)
        'image': r'!\[[^\]]*\]\([^)]*\)',           # 图片 ![alt](url)
        'formula': r'\$[^$]+\$',                    # 公式 $...$
    }

    def __init__(self, text: str):
        self.text = text
        self.protected_ranges: List[Tuple[int, int]] = []
        self.placeholders: dict[str, str] = {}
        self.placeholder_counter = 0

    def _is_chinese(self, char: str) -> bool:
        """判断是否为中文字符"""
        return '\u4e00' <= char <= '\u9fff'

    def _create_placeholder(self) -> str:
        """创建唯一的占位符"""
        self.placeholder_counter += 1
        return f'__PROTECTED_{self.placeholder_counter}__'

    def mark_protected(self) -> None:
        """标记所有受保护区域，用占位符替换"""
        patterns = [
            ('code_block', self.PROTECTED_PATTERNS['code_block']),
            ('bold', self.PROTECTED_PATTERNS['bold']),
            ('table', self.PROTECTED_PATTERNS['table']),
            ('formula', self.PROTECTED_PATTERNS['formula']),
            ('image', self.PROTECTED_PATTERNS['image']),
            ('link', self.PROTECTED_PATTERNS['link']),
            ('inline_code', self.PROTECTED_PATTERNS['inline_code']),
        ]

        for name, pattern in patterns:
            for match in re.finditer(pattern, self.text):
                start, end = match.span()
                if any(s <= start < e or s < end <= e for s, e in self.protected_ranges):
                    continue

                placeholder = self._create_placeholder()
                original = match.group(0)
                self.placeholders[placeholder] = original
                self.protected_ranges.append((start, end))

        self.protected_ranges.sort(reverse=True)
        for start, end in self.protected_ranges:
            original = self.text[start:end]
            for placeholder, value in self.placeholders.items():
                if value == original:
                    self.text = self.text[:start] + placeholder + self.text[end:]
                    break

    def restore(self) -> None:
        """还原所有受保护区域"""
        for placeholder, original in self.placeholders.items():
            self.text = self.text.replace(placeholder, original)

    def format(self) -> str:
        """执行格式化"""
        # 1. 标记并保护受保护区
        self.mark_protected()

        # 2. 执行格式化规则
        self._add_spacing()
        self._fix_punctuation()
        self._fix_quotes()
        self._fix_blank_lines()

        # 3. 还原受保护区
        self.restore()

        return self.text

    def _add_spacing(self) -> None:
        """在中英文/数字之间添加空格
        
        规则：
        - 中文字符 + 英文/数字 → 中文 + 空格 + 英文/数字
        - 英文/数字 + 中文字符 → 英文/数字 + 空格 + 中文
        """
        # 中文 + 英文/数字 → 添加空格
        self.text = re.sub(r'([\u4e00-\u9fff])([a-zA-Z0-9])', r'\1 \2', self.text)
        # 英文/数字 + 中文 → 添加空格
        self.text = re.sub(r'([a-zA-Z0-9])([\u4e00-\u9fff])', r'\1 \2', self.text)

    def _fix_punctuation(self) -> None:
        """标点中文化"""
        punct_map = {
            ',': '，',
            '.': '。',
            '!': '！',
            '?': '？',
            ';': '；',
            '(': '（',
            ')': '）',
        }

        for eng, chn in punct_map.items():
            # 如果标点前有中文字符，转换
            self.text = re.sub(f'([\u4e00-\u9fff])\s*{re.escape(eng)}', f'\1{chn}', self.text)
            # 如果标点后有中文字符，也转换
            self.text = re.sub(f'{re.escape(eng)}\s*([\u4e00-\u9fff])', f'{chn}\1', self.text)

    def _fix_quotes(self) -> None:
        """引号统一为中文引号"""
        # 直引号 "..." → 「...」
        def replace_quotes(match):
            content = match.group(1)
            return f'「{content}」'
        
        self.text = re.sub(r'"([^"]*)"', replace_quotes, self.text)
        
        # 单引号 '...' → 『...』
        def replace_single_quotes(match):
            content = match.group(1)
            return f'『{content}』'
        
        self.text = re.sub(r"'([^']*)'", replace_single_quotes, self.text)

    def _fix_blank_lines(self) -> None:
        """空行规范化"""
        self.text = re.sub(r'\n\s*\n+', '\n\n', self.text)
        self.text = self.text.strip()
        if not self.text.endswith('\n'):
            self.text += '\n'


def main():
    """命令行入口"""
    import sys

    if len(sys.argv) < 3:
        print("Usage: python formatter.py <input_file> <output_file>")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    with open(input_file, 'r', encoding='utf-8') as f:
        text = f.read()

    formatter = MarkdownFormatter(text)
    result = formatter.format()

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(result)

    print(f"Formatted: {input_file} -> {output_file}")


if __name__ == '__main__':
    main()
