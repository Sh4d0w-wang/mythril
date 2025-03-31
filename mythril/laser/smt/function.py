from typing import Any, List, Set, cast

import z3

from mythril.laser.smt.bitvec import BitVec


class Function:
    """
    表示无解释函数,并在符号执行和约束求解中使用

    其行为在符号执行中没有预定义的语义，而是通过约束求解器动态确定的
    
    An uninterpreted function.
    """

    def __init__(self, name: str, domain: List[int], value_range: int):
        """
        初始化一个无解释函数

        domain:函数的定义域，是一个整数列表，每个整数表示一个位向量的大小;

        value_range:函数的值域，表示函数的输出是一个位向量的大小

        Initializes an uninterpreted function.

        :param name: Name of the Function
        :param domain: The domain for the Function (10 -> all the values that a bv of size 10 could take)
        :param value_range: The range for the values of the function (10 -> all the values that a bv of size 10 could take)
        """
        self.domain = []
        # 定义域列表转换为 Z3 的 BitVecSort 对象列表
        for element in domain:
            self.domain.append(z3.BitVecSort(element))
        # 将值域转换为 Z3 的 BitVecSort 对象
        self.range = z3.BitVecSort(value_range)
        # 创建一个无解释函数
        self.raw = z3.Function(name, *self.domain, self.range)

    def __call__(self, *items) -> BitVec:
        """
        允许以函数调用的方式使用 Function 对象
        
        Function accessor, item can be symbolic.
        """
        # 提取所有输入参数的注释（annotations），并将它们合并到一个集合中
        annotations: Set[Any] = set().union(*[item.annotations for item in items])
        # 调用 Z3 的无解释函数 self.raw，传入输入参数的 raw 属性（即 Z3 的位向量表示）
        # [item.raw for item in items]：对每个输入参数 item，提取其 raw 属性
        # self.raw(*...))调用 Z3 的无解释函数self.raw
        # 使用 cast 函数将返回的 Z3 位向量对象显式转换为 z3.BitVecRef 类型
        return BitVec(
            cast(z3.BitVecRef, self.raw(*[item.raw for item in items])),
            annotations=annotations,
        )
