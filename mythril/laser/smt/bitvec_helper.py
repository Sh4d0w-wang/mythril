from typing import Any, Callable, List, Set, Union, cast, overload

import z3

from mythril.laser.smt.array import Array, BaseArray
from mythril.laser.smt.bitvec import BitVec
from mythril.laser.smt.bool import Bool, Or

Annotations = Set[Any]


def _z3_array_converter(array: Union[z3.Array, z3.K]) -> Array:
    """
    将z3生成的数组转化为Array
    """
    new_array = Array(
        "name_to_be_overwritten", array.domain().size(), array.range().size()
    )
    new_array.raw = array
    return new_array


def _comparison_helper(a: BitVec, b: BitVec, operation: Callable) -> Bool:
    """
    创建一个比较表达式
    """
    annotations = a.annotations.union(b.annotations)
    return Bool(operation(a.raw, b.raw), annotations)


def _arithmetic_helper(a: BitVec, b: BitVec, operation: Callable) -> BitVec:
    """
    创建一个算术表达式
    """
    raw = operation(a.raw, b.raw)
    union = a.annotations.union(b.annotations)
    return BitVec(raw, annotations=union)


def LShR(a: BitVec, b: BitVec):
    """
    创建一个逻辑右移表达式
    """
    return _arithmetic_helper(a, b, z3.LShR)


@overload
def If(
    a: Union[Bool, bool], b: Union[BitVec, int], c: Union[BitVec, int]
) -> BitVec: ...


@overload
def If(a: Union[Bool, bool], b: BaseArray, c: BaseArray) -> BaseArray: ...


def If(
    a: Union[Bool, bool],
    b: Union[BaseArray, BitVec, int],
    c: Union[BaseArray, BitVec, int],
) -> Union[BitVec, BaseArray]:
    """
    创建一个条件表达式
    
    a : 布尔条件;
    b 和 c : 条件为真和假时的值,可以是BitVec、bool、Array;

    Create an if-then-else expression.

    :param a:
    :param b:
    :param c:
    :return:
    """
    # 将条件转换为 Bool 对象
    if not isinstance(a, Bool):
        a = Bool(z3.BoolVal(a))

    # 处理数组类型的参数
    if isinstance(b, BaseArray) and isinstance(c, BaseArray):
        array = z3.If(a.raw, b.raw, c.raw)
        return _z3_array_converter(array)
    # 处理位向量或整数类型的参数
    default_sort_size = 256
    if isinstance(b, BitVec):
        default_sort_size = b.size()
    if isinstance(c, BitVec):
        default_sort_size = c.size()
    # 转换为 BitVec
    if not isinstance(b, BitVec):
        b = BitVec(z3.BitVecVal(b, default_sort_size))
    if not isinstance(c, BitVec):
        c = BitVec(z3.BitVecVal(c, default_sort_size))
    # 合并注解并创建条件表达式
    union = a.annotations.union(b.annotations).union(c.annotations)
    return BitVec(z3.If(a.raw, b.raw, c.raw), union)


def UGT(a: BitVec, b: BitVec) -> Bool:
    """
    创建一个无符号整数“大于”表达式
    
    Create an unsigned greater than expression.

    :param a:
    :param b:
    :return:
    """
    return _comparison_helper(a, b, z3.UGT)


def UGE(a: BitVec, b: BitVec) -> Bool:
    """
    创建一个无符号整数“大于等于”表达式
    
    Create an unsigned greater than or equal to expression.

    :param a:
    :param b:
    :return:
    """
    # OR
    # UGT(a, b)：a 无符号大于 b
    # a == b：a 等于 b
    return Or(UGT(a, b), a == b)


def ULT(a: BitVec, b: BitVec) -> Bool:
    """
    创建一个无符号整数“小于”表达式
    
    Create an unsigned less than expression.

    :param a:
    :param b:
    :return:
    """
    return _comparison_helper(a, b, z3.ULT)


def ULE(a: BitVec, b: BitVec) -> Bool:
    """
    创建一个无符号整数“小于等于”表达式
    
    Create an unsigned less than or equal to expression.

    :param a:
    :param b:
    :return:
    """
    # OR
    # ULT(a, b)：a 无符号小于 b
    # a == b：a 等于 b
    return Or(ULT(a, b), a == b)


@overload
def Concat(*args: List[BitVec]) -> BitVec: ...


@overload
def Concat(*args: BitVec) -> BitVec: ...


def Concat(*args: Union[BitVec, List[BitVec]]) -> BitVec:
    """
    创建一个位向量的拼接表达式
    
    Create a concatenation expression.

    :param args:
    :return:
    """
    # The following statement is used if a list is provided as an argument to concat
    if len(args) == 1 and isinstance(args[0], list):
        # 将列表中的所有 BitVec 提取出来
        bvs: List[BitVec] = args[0]
    else:
        # 直接将传入的 BitVec 对象作为拼接的输入
        bvs = cast(List[BitVec], args)
    # 将所有位向量拼接成一个新的位向量
    nraw = z3.Concat([a.raw for a in bvs])
    annotations: Annotations = set()

    for bv in bvs:
        annotations = annotations.union(bv.annotations)
    return BitVec(nraw, annotations)


def Extract(high: int, low: int, bv: BitVec) -> BitVec:
    """
    从一个位向量中提取指定范围的子位向量(高位索引,低位索引,源位向量)
    
    Create an extract expression.

    :param high:
    :param low:
    :param bv:
    :return:
    """
    # 从 bv 中提取从 low 到 high 的位
    raw = z3.Extract(high, low, bv.raw)
    return BitVec(raw, annotations=bv.annotations)


def URem(a: BitVec, b: BitVec) -> BitVec:
    """
    创建一个无符号整数的取余表达式
    
    Create an unsigned remainder expression.

    :param a:
    :param b:
    :return:
    """
    return _arithmetic_helper(a, b, z3.URem)


def SRem(a: BitVec, b: BitVec) -> BitVec:
    """
    创建一个有符号整数的取余表达式
    
    Create a signed remainder expression.

    :param a:
    :param b:
    :return:
    """
    return _arithmetic_helper(a, b, z3.SRem)


def UDiv(a: BitVec, b: BitVec) -> BitVec:
    """
    创建一个无符号整数的除法表达式
    
    Create an unsigned division expression.

    :param a:
    :param b:
    :return:
    """
    return _arithmetic_helper(a, b, z3.UDiv)


def Sum(*args: BitVec) -> BitVec:
    """
    创建一个位向量的求和表达式
    
    Create sum expression.

    :return:
    """
    raw = z3.Sum([a.raw for a in args])
    annotations: Annotations = set()

    for bv in args:
        annotations = annotations.union(bv.annotations)
    return BitVec(raw, annotations)


def BVAddNoOverflow(a: Union[BitVec, int], b: Union[BitVec, int], signed: bool) -> Bool:
    """
    创建一个布尔表达式，验证两个位向量相加是否会发生溢出
    
    Creates predicate that verifies that the addition doesn't overflow.

    :param a:
    :param b:
    :param signed: 是否是有符号操作
    :return:
    """
    if not isinstance(a, BitVec):
        a = BitVec(z3.BitVecVal(a, 256))
    if not isinstance(b, BitVec):
        b = BitVec(z3.BitVecVal(b, 256))
    # 检查加法是否溢出
    return Bool(z3.BVAddNoOverflow(a.raw, b.raw, signed))


def BVMulNoOverflow(a: Union[BitVec, int], b: Union[BitVec, int], signed: bool) -> Bool:
    """
    创建一个布尔表达式，验证两个位向量相乘是否会发生溢出
    
    Creates predicate that verifies that the multiplication doesn't overflow.

    :param a:
    :param b:
    :param signed:
    :return:
    """
    if not isinstance(a, BitVec):
        a = BitVec(z3.BitVecVal(a, 256))
    if not isinstance(b, BitVec):
        b = BitVec(z3.BitVecVal(b, 256))
    # 检查乘法是否溢出
    return Bool(z3.BVMulNoOverflow(a.raw, b.raw, signed))


def BVSubNoUnderflow(
    a: Union[BitVec, int], b: Union[BitVec, int], signed: bool
) -> Bool:
    """
    创建一个布尔表达式，验证两个位向量相减是否会发生下溢
    
    Creates predicate that verifies that the subtraction doesn't overflow.

    :param a:
    :param b:
    :param signed:
    :return:
    """
    if not isinstance(a, BitVec):
        a = BitVec(z3.BitVecVal(a, 256))
    if not isinstance(b, BitVec):
        b = BitVec(z3.BitVecVal(b, 256))
    # 检查减法是否下溢
    return Bool(z3.BVSubNoUnderflow(a.raw, b.raw, signed))
