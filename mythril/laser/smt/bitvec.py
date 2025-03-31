"""This module provides classes for an SMT abstraction of bit vectors."""

from operator import eq, lshift, ne, rshift
from typing import Any, Callable, Optional, Set, Union, cast

import z3

from mythril.laser.smt.bool import Bool
from mythril.laser.smt.expression import Expression

Annotations = Set[Any]

# fmt: off


def _padded_operation(a: z3.BitVec, b: z3.BitVec, operator):
    if a.size() == b.size():
        return operator(a, b)
    if a.size() < b.size():
        a, b = b, a
    b = z3.Concat(z3.BitVecVal(0, a.size() - b.size()), b)
    return operator(a, b)


class BitVec(Expression[z3.BitVecRef]):
    """
    表示一个位向量符号,继承自Expression

    A bit vector symbol.
    """

    def __init__(self, raw: z3.BitVecRef, annotations: Optional[Annotations] = None):
        """
        初始化位向量符号的注解

        :param raw:
        :param annotations:
        """
        super().__init__(raw, annotations)

    def size(self) -> int:
        """
        返回位向量的大小(位宽)

        :return:
        """
        return self.raw.size()

    @property
    def symbolic(self) -> bool:
        """
        检查位向量是否是符号的(即没有具体值)
        
        Returns whether this symbol doesn't have a concrete value.

        :return:
        """
        self.simplify()
        return not isinstance(self.raw, z3.BitVecNumRef)

    @property
    def value(self) -> Optional[int]:
        """
        返回位向量的具体值，如果它是具体的(非符号的)
        
        Returns the value of this symbol if concrete, otherwise None.

        :return:
        """
        if self.symbolic:
            return None
        assert isinstance(self.raw, z3.BitVecNumRef)
        return self.raw.as_long()

    def __add__(self, other: Union[int, "BitVec"]) -> "BitVec":
        """
        创建一个加法表达式
        
        Create an addition expression.

        :param other:
        :return:
        """
        # 如果 other 是整数，直接与 self.raw 相加
        if isinstance(other, int):
            return BitVec(self.raw + other, annotations=self.annotations)
        # 如果 other 是 BitVec，合并注解并相加
        union = self.annotations.union(other.annotations)
        return BitVec(self.raw + other.raw, annotations=union)

    def __sub__(self, other: Union[int, "BitVec"]) -> "BitVec":
        """
        创建一个减法表达式
        
        Create a subtraction expression.

        :param other:
        :return:
        """
        if isinstance(other, int):
            return BitVec(self.raw - other, annotations=self.annotations)

        union = self.annotations.union(other.annotations)
        return BitVec(self.raw - other.raw, annotations=union)

    def __mul__(self, other: "BitVec") -> "BitVec":
        """
        创建一个乘法表达式
        
        Create a multiplication expression.

        :param other:
        :return:
        """
        union = self.annotations.union(other.annotations)
        return BitVec(self.raw * other.raw, annotations=union)

    def __truediv__(self, other: "BitVec") -> "BitVec":
        """
        创建一个有符号除法表达式
        
        Create a signed division expression.

        :param other:
        :return:
        """
        union = self.annotations.union(other.annotations)
        return BitVec(self.raw / other.raw, annotations=union)

    def __and__(self, other: Union[int, "BitVec"]) -> "BitVec":
        """
        创建一个按位与表达式
        
        Create an and expression.

        :param other:
        :return:
        """
        if not isinstance(other, BitVec):
            other = BitVec(z3.BitVecVal(other, self.size()))
        union = self.annotations.union(other.annotations)
        return BitVec(self.raw & other.raw, annotations=union)

    def __or__(self, other: Union[int, "BitVec"]) -> "BitVec":
        """
        创建一个按位或表达式
        
        Create an or expression.

        :param other:
        :return:
        """
        if not isinstance(other, BitVec):
            other = BitVec(z3.BitVecVal(other, self.size()))
        union = self.annotations.union(other.annotations)
        return BitVec(self.raw | other.raw, annotations=union)

    def __xor__(self, other: Union[int, "BitVec"]) -> "BitVec":
        """
        创建一个按位异或表达式
        
        Create a xor expression.

        :param other:
        :return:
        """
        if not isinstance(other, BitVec):
            other = BitVec(z3.BitVecVal(other, self.size()))
        union = self.annotations.union(other.annotations)
        return BitVec(self.raw ^ other.raw, annotations=union)

    def __lt__(self, other: Union[int, "BitVec"]) -> Bool:
        """
        创建一个有符号小于表达式
        
        Create a signed less than expression.

        :param other:
        :return:
        """
        if not isinstance(other, BitVec):
            other = BitVec(z3.BitVecVal(other, self.size()))
        union = self.annotations.union(other.annotations)
        return Bool(self.raw < other.raw, annotations=union)

    def __gt__(self, other: Union[int, "BitVec"]) -> Bool:
        """
        创建一个有符号大于表达式
        
        Create a signed greater than expression.

        :param other:
        :return:
        """
        if not isinstance(other, BitVec):
            other = BitVec(z3.BitVecVal(other, self.size()))
        union = self.annotations.union(other.annotations)
        return Bool(self.raw > other.raw, annotations=union)

    def __le__(self, other: Union[int, "BitVec"]) -> Bool:
        """
        创建一个有符号小于等于表达式
        
        Create a signed less than expression.

        :param other:
        :return:
        """
        if not isinstance(other, BitVec):
            other = BitVec(z3.BitVecVal(other, self.size()))
        union = self.annotations.union(other.annotations)
        return Bool(self.raw <= other.raw, annotations=union)

    def __ge__(self, other: Union[int, "BitVec"]) -> Bool:
        """
        创建一个有符号大于等于表达式
        
        Create a signed greater than expression.

        :param other:
        :return:
        """
        if not isinstance(other, BitVec):
            other = BitVec(z3.BitVecVal(other, self.size()))
        union = self.annotations.union(other.annotations)
        return Bool(self.raw >= other.raw, annotations=union)

    # MYPY: fix complains about overriding __eq__
    def __eq__(self, other: Union[int, "BitVec"]) -> Bool:  # type: ignore
        """
        创建一个等于表达式
        
        Create an equality expression.

        :param other:
        :return:
        """
        # 如果 other 不是 BitVec，直接与 self.raw 进行比较
        if not isinstance(other, BitVec):
            return Bool(
                cast(z3.BoolRef, self.raw == other), annotations=self.annotations
            )
        # 如果 other 是 BitVec，合并注解并进行等于比较
        union = self.annotations.union(other.annotations)
        # Some of the BitVecs can be 512 bit due to sha3()
        # 使用 _padded_operation 处理不同大小的位向量（会将较小的位向量用零扩展到较大的大小，然后进行等于比较）
        eq_check = _padded_operation(self.raw, other.raw, eq)
        # MYPY: fix complaints due to z3 overriding __eq__
        return Bool(cast(z3.BoolRef, eq_check), annotations=union)

    # MYPY: fix complains about overriding __ne__
    def __ne__(self, other: Union[int, "BitVec"]) -> Bool:  # type: ignore
        """
        创建一个不等于表达式
        
        Create an inequality expression.

        :param other:
        :return:
        """
        # 如果 other 不是 BitVec，直接与 self.raw 进行比较
        if not isinstance(other, BitVec):
            return Bool(
                cast(z3.BoolRef, self.raw != other), annotations=self.annotations
            )
        # 如果 other 是 BitVec，合并注解并进行不等于比较
        union = self.annotations.union(other.annotations)
        # Some of the BitVecs can be 512 bit due to sha3()
        neq_check = _padded_operation(self.raw, other.raw, ne)
        # MYPY: fix complaints due to z3 overriding __eq__
        return Bool(cast(z3.BoolRef, neq_check), annotations=union)

    def _handle_shift(self, other: Union[int, "BitVec"], operator: Callable) -> "BitVec":
        """
        处理移位操作

        Handles shift
        :param other: The other BitVector
        :param operator: The shift operator
        :return: the resulting output
        """
        # 如果 other 不是 BitVec，直接应用移位操作
        if not isinstance(other, BitVec):
            return BitVec(
                operator(self.raw, other), annotations=self.annotations
            )
        # 如果 other 是 BitVec，合并注解并应用移位操作
        union = self.annotations.union(other.annotations)
        return BitVec(operator(self.raw, other.raw), annotations=union)

    def __lshift__(self, other: Union[int, "BitVec"]) -> "BitVec":
        """
        创建一个左移表达式

        :param other:
        :return:
        """
        return self._handle_shift(other, lshift)

    def __rshift__(self, other: Union[int, "BitVec"]) -> "BitVec":
        """
        创建一个右移表达式

        :param other:
        :return:
        """
        return self._handle_shift(other, rshift)

    def __hash__(self) -> int:
        """
        返回位向量的哈希值

        :return:
        """
        return self.raw.__hash__()
