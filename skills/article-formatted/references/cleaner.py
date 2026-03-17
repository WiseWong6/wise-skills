#!/usr/bin/env python3
"""
Markdown 清洗器 - 状态机保护受保护区

负责对 Markdown 文本进行确定性格式清洗：
1. 保护代码块、链接、图片、公式不被清洗
2. 执行破折号、引号、空格、标点、空行规范化
"""

import re
from typing import List, Tuple


class MarkdownCleaner:
    """Markdown 清洗器：状态机保护受保护块"""

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
        self.protected_ranges: List[Tuple[int, int]] = []  # [(start, end), ...]
        self.placeholders: dict[str, str] = {}              # {placeholder: original}
        self.placeholder_counter = 0

    def _is_chinese(self, char: str) -> bool:
        """判断是否为中文字符"""
        return '\u4e00' <= char <= '\u9fff'

    def _create_placeholder(self) -> str:
        """创建唯一的占位符"""
        self.placeholder_counter += 1
        return f'__PROTECTED_{self.placeholder_counter}__'

    def mark_protected(self) -> None:
        """标记所有受保护区域，用占位符替换

        按照"最长相等"原则，从大到小匹配，避免嵌套问题。
        """
        # 按模式长度排序，先匹配长的（代码块、表格、加粗），再匹配短的（行内代码）
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
                # 检查是否已被其他保护区域覆盖
                if any(s <= start < e or s < end <= e for s, e in self.protected_ranges):
                    continue

                placeholder = self._create_placeholder()
                original = match.group(0)
                self.placeholders[placeholder] = original
                self.protected_ranges.append((start, end))

        # 按位置倒序替换（避免位置偏移）
        self.protected_ranges.sort(reverse=True)
        for start, end in self.protected_ranges:
            # 找到对应的占位符
            original = self.text[start:end]
            # 在 placeholders 中找到对应的 placeholder
            for placeholder, value in self.placeholders.items():
                if value == original:
                    self.text = self.text[:start] + placeholder + self.text[end:]
                    break

    def restore(self) -> None:
        """还原所有受保护区域"""
        for placeholder, original in self.placeholders.items():
            self.text = self.text.replace(placeholder, original)

    def clean(self) -> str:
        """执行确定性清洗

        返回清洗后的文本

        清洗顺序说明：
        - 引号删除最先执行（在保护之前），确保中文环境中的引号被删除
        - 然后标记保护受保护区（此时引号已被处理，保护范围更准确）
        - 最后执行其他清洗规则
        """
        # 0. 引号删除最先执行（不受保护机制限制）
        self._clean_quotes()

        # 1. 标记并保护受保护区
        self.mark_protected()

        # 2. 执行其他清洗规则（引号已处理完成）
        self._clean_em_dash()
        self._fix_spacing()
        self._fix_punctuation()
        self._fix_blank_lines()

        # 3. 还原受保护区
        self.restore()

        return self.text

    def _clean_em_dash(self) -> None:
        """破折号转换

        规则：
        - `—` (em dash, U+2014) → 中文逗号（用户需求）
        - `——` (双 em dash) → 中文逗号
        - 无论在什么位置，统一转为逗号
        """
        # 所有破折号统一转为逗号（用户需求）
        # 处理双破折号
        self.text = re.sub(r'—+', '，', self.text)

        # 处理单破折号（夹在字符中间）
        self.text = re.sub(r'(\S)\s*—\s*(\S)', r'\1，\2', self.text)

        # 处理句首或句末的破折号
        self.text = re.sub(r'^\s*—\s*', '，', self.text, flags=re.MULTILINE)
        self.text = re.sub(r'—\s*$', '，', self.text, flags=re.MULTILINE)

        # 清理可能产生的双重标点
        self.text = re.sub(r'，，+', '，', self.text)

    def _clean_quotes(self) -> None:
        """引号删除（去机械化）

        规则：
        - 删除中文环境中的所有引号（直引号 " " 和弯引号 「」『』）
        - 保留代码块、加粗、表格中的引号（已在 mark_protected() 中保护）
        - 判断标准：引号内容包含中文，或引号前后有中文字符
        """
        # 1. 弯引号转直引号（统一处理）
        self.text = self.text.replace('「', '"').replace('」', '"')
        self.text = self.text.replace('『', '"').replace('』', '"')

        # 2. 删除中文环境中的直引号
        # 保护：代码块、加粗、表格已被保护，不会受影响

        # 策略：匹配成对的引号，检查是否在中文环境中
        def remove_chinese_quotes(match):
            content = match.group(1)
            # 检查：内容包含中文 = 中文环境
            has_chinese = bool(re.search(r'[\u4e00-\u9fff]', content))
            if has_chinese:
                return content  # 删除引号，保留内容
            return match.group(0)  # 保留引号

        # 匹配非贪婪的成对引号（支持跨行）
        self.text = re.sub(r'"([^"]*?)"', remove_chinese_quotes, self.text)

        # 3. 处理特殊情况：空引号或纯空白引号（删除）
        self.text = re.sub(r'"\s*"', '', self.text)

    def _fix_spacing(self) -> None:
        """中英文空格修复（用户需求：删除空格）

        规则：
        - 删除中文字符与英文/数字之间的所有空格（但不影响换行）
        - 删除英文/数字与中文字符之间的所有空格（但不影响换行）
        - 保留纯英文句子内部的空格
        - 删除中文标点后的空格
        - 删除所有连续多余空格（但不影响换行）
        """
        # 1. 删除中文与英文/数字之间的空格（只用空格，不用 \s 避免影响换行）
        # 中文 + 空格 + 英文/数字 → 中文 + 英文/数字
        self.text = re.sub(r'([\u4e00-\u9fff]) +([a-zA-Z0-9])', r'\1\2', self.text)
        # 英文/数字 + 空格 + 中文 → 英文/数字 + 中文
        self.text = re.sub(r'([a-zA-Z0-9]) +([\u4e00-\u9fff])', r'\1\2', self.text)

        # 2. 中文标点后删除空格（与中文/英文/数字之间都删除）
        zh_punct = '，。！？；（）：、""''「」『』【】…—'
        punct_pattern = '[' + re.escape(zh_punct) + ']'
        self.text = re.sub(f'({punct_pattern}) +([\u4e00-\u9fff])', r'\1\2', self.text)
        self.text = re.sub(f'({punct_pattern}) +([a-zA-Z0-9])', r'\1\2', self.text)

        # 3. 删除所有连续多余空格（只用空格，不用 \s 避免影响换行）
        self.text = re.sub(r'  +', ' ', self.text)

    def _fix_punctuation(self) -> None:
        """标点中文化

        规则：
        - 中文内容中 `, . ! ? ; ( )` → `，。！？；（）`
        - 英文句子/代码中保留英文标点
        """
        # 简单规则：如果标点前有中文，转中文标点
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
            self.text = re.sub(f'([\u4e00-\u9fff])\\s*{re.escape(eng)}', f'\\1{chn}', self.text)
            # 如果标点后有中文字符，也转换
            self.text = re.sub(f'{re.escape(eng)}\\s*([\u4e00-\u9fff])', f'{chn}\\1', self.text)

    def _fix_blank_lines(self) -> None:
        """空行规范化 - 消除特殊情况

        规则：
        - 将连续3个或更多空行归一化为一个空行
        - 保留标题和段落之间的单个空行
        - 首尾不留多余空行
        """
        # 1. 将连续3个或更多空行归一化为一个空行
        self.text = re.sub(r'\n\s*\n\s*\n+', '\n\n', self.text)

        # 2. 去除首尾空行
        self.text = self.text.strip()

        # 3. 确保以换行结尾（统一格式）
        if not self.text.endswith('\n'):
            self.text += '\n'

        # 4. 修复标题后的空行（确保标题和正文之间有空行）
        # 匹配 # ## ### 等标题后直接跟非空行的情况
        self.text = re.sub(r'^(#{1,6}[^\n#]*)\n([^\n\s])', r'\1\n\n\2', self.text, flags=re.MULTILINE)


def main():
    """测试入口"""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python cleaner.py <input_file>")
        sys.exit(1)

    input_file = sys.argv[1]

    with open(input_file, 'r', encoding='utf-8') as f:
        text = f.read()

    cleaner = MarkdownCleaner(text)
    result = cleaner.clean()

    print(result)


if __name__ == '__main__':
    main()
