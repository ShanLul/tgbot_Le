"""
价格解析服务
"""
import re
import operator
from decimal import Decimal, InvalidOperation
from app.models.schemas import PriceParseResult


class PriceParser:
    """价格解析器"""

    # 支持的运算符
    OPERATORS = {
        "+": operator.add,
        "-": operator.sub,
        "*": operator.mul,
        "/": operator.truediv,
    }

    # 价格关键词
    PRICE_KEYWORDS = ["总", "合计", "总价", "总计", "金额"]

    def parse(self, text: str) -> PriceParseResult:
        """
        解析文本中的价格

        Args:
            text: 待解析的文本

        Returns:
            PriceParseResult: 解析结果
        """
        if not text:
            return PriceParseResult(success=False, error="文本为空")

        # 替换乘号 × 为 *
        text = text.replace("×", "*").replace("x", "*")

        # 尝试解析各种格式
        for keyword in self.PRICE_KEYWORDS:
            # 模式1: 关键词 + 算式 = 结果 (如: 总60*2+60+6=186 或 总 55*2+6=116)
            # 优先匹配带等号的格式，避免被简单数字匹配覆盖
            pattern1 = rf"{keyword}\s*([^=\n]+?)\s*=\s*(-?\d+(?:\.\d+)?)"
            match = re.search(pattern1, text, re.IGNORECASE)
            if match:
                expression = match.group(1).strip()
                stated_result = match.group(2)

                # 计算算式验证正确性（可选）
                calculated_result = self._evaluate_expression(expression)
                try:
                    stated_decimal = Decimal(stated_result)
                    # 不支持负数金额
                    if stated_decimal < 0:
                        continue
                    return PriceParseResult(
                        success=True,
                        amount=stated_decimal,
                        expression=expression
                    )
                except (InvalidOperation, ValueError):
                    pass

            # 模式2: 关键词 + 算式 (如: 总60*2+60+6)
            pattern2 = rf"{keyword}\s*([^=\n]+?)(?:\s*$|\s*\n)"
            match = re.search(pattern2, text, re.MULTILINE | re.IGNORECASE)
            if match:
                expression = match.group(1).strip()
                # 检查是否包含运算符（排除纯数字）
                if any(op in expression for op in ["+", "-", "*", "/"]):
                    calculated_result = self._evaluate_expression(expression)
                    if calculated_result is not None:
                        # 不支持负数金额
                        if calculated_result < 0:
                            continue
                        return PriceParseResult(
                            success=True,
                            amount=calculated_result,
                            expression=expression
                        )

            # 模式3: 关键词 + 纯数字 (如: xxx总186 或 总186)
            # 只匹配紧随关键词的数字，避免匹配到算式中的第一个数字
            pattern3 = rf"{keyword}\s*(\d+(?:\.\d+)?)"
            match = re.search(pattern3, text, re.IGNORECASE)
            if match:
                # 检查匹配的数字后面是否紧跟运算符，如果是则跳过（交给上面的算式模式处理）
                match_end = match.end()
                if match_end < len(text):
                    next_chars = text[match_end:match_end + 3].strip()
                    if next_chars and next_chars[0] in ["+", "-", "*", "/", "x", "×"]:
                        continue
                try:
                    amount = Decimal(match.group(1))
                    return PriceParseResult(success=True, amount=amount)
                except (InvalidOperation, ValueError):
                    continue

        return PriceParseResult(success=False, error="未找到价格信息")

    def _remove_prefix(self, text: str) -> str:
        """移除 a/A 前缀"""
        text = text.strip()
        if text and (text[0] in "aA") and len(text) > 1:
            return text[1:].strip()
        return text

    def _evaluate_expression(self, expression: str) -> Decimal | None:
        """
        安全计算算式

        Args:
            expression: 算式字符串 (如: "60*2+60+6")

        Returns:
            计算结果或None
        """
        try:
            # 移除所有空格
            expression = expression.replace(" ", "")

            # 验证只包含数字和运算符
            if not re.match(r"^[\d+\-*/.()]+$", expression):
                return None

            # 使用安全的计算方式
            result = self._safe_eval(expression)
            if result is not None:
                # 转换为Decimal，保留两位小数
                return Decimal(str(result)).quantize(Decimal("0.01"))
            return None
        except Exception:
            return None

    def _safe_eval(self, expression: str) -> float | None:
        """
        安全计算算式（递归下降解析，正确处理运算符优先级）

        运算符优先级：括号 > 乘除 > 加减
        结合性：从左到右
        """
        try:
            # 移除空格
            expression = expression.replace(" ", "")

            # 空表达式
            if not expression:
                return None

            # 1. 处理括号（从内到外）
            while "(" in expression:
                start = expression.rfind("(")
                end = expression.find(")", start)
                if end == -1:
                    return None  # 括号不匹配
                sub_expr = expression[start + 1:end]
                sub_result = self._safe_eval(sub_expr)
                if sub_result is None:
                    return None
                expression = expression[:start] + str(sub_result) + expression[end + 1:]

            # 2. 从右到左查找 + 或 -（优先级最低，最后计算）
            # 这样可以确保 "50*2+8" 被解析为 "(50*2)+8" 而不是 "50*(2+8)"
            for op in ["+", "-"]:
                pos = expression.rfind(op)
                # 跳过开头的负号（如 "-5+3" 中的 -）
                if pos == 0 and op == "-":
                    continue
                # 找到了不在开头的运算符
                if pos > 0:
                    left = expression[:pos]
                    right = expression[pos + 1:]
                    # 递归计算左右两边
                    left_val = self._safe_eval(left)
                    right_val = self._safe_eval(right)
                    if left_val is None or right_val is None:
                        return None
                    if op == "+":
                        return left_val + right_val
                    else:
                        return left_val - right_val

            # 3. 从右到左查找 * 或 /（优先级较高，先计算）
            for op in ["*", "/"]:
                pos = expression.rfind(op)
                if pos > 0:
                    left = expression[:pos]
                    right = expression[pos + 1:]
                    # 递归计算左右两边
                    left_val = self._safe_eval(left)
                    right_val = self._safe_eval(right)
                    if left_val is None or right_val is None:
                        return None
                    if op == "*":
                        return left_val * right_val
                    else:
                        if right_val == 0:
                            return None
                        return left_val / right_val

            # 4. 没有运算符，直接返回数字
            return float(expression)

        except Exception:
            return None


# 全局解析器实例
price_parser = PriceParser()
