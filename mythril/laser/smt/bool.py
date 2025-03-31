"""This module provides classes for an SMT abstraction of boolean
expressions."""

from typing import Set, Union, cast

import z3

from mythril.laser.smt.expression import Expression

# fmt: off


class Bool(Expression[z3.BoolRef]):
    """
    一个 Bool 类，是对 Z3 的布尔表达式的封装

    This is a Bool expression.
    """

    @property
    def is_false(self) -> bool:
        """
        检查布尔表达式是否可以简化为 False

        Specifies whether this variable can be simplified to false.

        :return:
        """
        self.simplify()
        return z3.is_false(self.raw)

    @property
    def is_true(self) -> bool:
        """
        检查布尔表达式是否可以简化为 True

        Specifies whether this variable can be simplified to true.

        :return:
        """
        self.simplify()
        return z3.is_true(self.raw)

    @property
    def value(self) -> Union[bool, None]:
        """
        返回布尔表达式的具体值

        Returns the concrete value of this bool if concrete, otherwise None.

        :return: Concrete value or None
        """
        self.simplify()
        if self.is_true:
            return True
        elif self.is_false:
            return False
        else:
            return None

    # MYPY: complains about overloading __eq__ # noqa
    def __eq__(self, other: object) -> "Bool":  # type: ignore
        """
        重载 == 操作符，用于比较两个布尔表达式
        
        :param other:
        :return:
        """
        if isinstance(other, Expression):
            return Bool(cast(z3.BoolRef, self.raw == other.raw),
                        self.annotations.union(other.annotations))
        return Bool(cast(z3.BoolRef, self.raw == other), self.annotations)

    # MYPY: complains about overloading __ne__ # noqa
    def __ne__(self, other: object) -> "Bool":  # type: ignore
        """
        重载 != 操作符，用于比较两个布尔表达式

        :param other:
        :return:
        """
        if isinstance(other, Expression):
            return Bool(cast(z3.BoolRef, self.raw != other.raw),
                        self.annotations.union(other.annotations))
        return Bool(cast(z3.BoolRef, self.raw != other), self.annotations)

    def __bool__(self) -> bool:
        """
        重载布尔上下文中的行为，返回布尔表达式的值

        :return:
        """
        if self.value is not None:
            return self.value
        else:
            return False

    def substitute(self, original_expression, new_expression):
        """
        替换布尔表达式中的子表达式

        :param original_expression:
        :param new_expression:
        """
        if self.raw is None:
            return
        original_z3 = original_expression.raw
        new_z3 = new_expression.raw
        self.raw = z3.substitute(self.raw, (original_z3, new_z3))

    def __hash__(self) -> int:
        """
        返回布尔表达式的哈希值
        """
        return self.raw.__hash__()


def And(*args: Union[Bool, bool]) -> Bool:
    """
    创建一个逻辑与(AND)表达式

    And(a, b, c) --> a AND b AND c

    Create an And expression.
    """
    annotations: Set = set()
    # 将所有参数转换为 Bool 对象
    args_list = [arg if isinstance(arg, Bool) else Bool(arg) for arg in args]
    # 合并所有参数的注解
    for arg in args_list:
        annotations = annotations.union(arg.annotations)
    # 创建逻辑与表达式
    return Bool(z3.And([a.raw for a in args_list]), annotations)


def Xor(a: Bool, b: Bool) -> Bool:
    """
    创建一个逻辑异或(XOR)表达式

    Create an And expression.
    """
    # 合并两个参数的注解
    union = a.annotations.union(b.annotations)
    # 创建一个逻辑异或表达式
    return Bool(z3.Xor(a.raw, b.raw), union)


def Or(*args: Union[Bool, bool]) -> Bool:
    """
    创建一个逻辑或(OR)表达式

    Create an or expression.

    :param a:
    :param b:
    :return:
    """
    args_list = [arg if isinstance(arg, Bool) else Bool(arg) for arg in args]
    annotations: Set = set()
    for arg in args_list:
        annotations = annotations.union(arg.annotations)
    return Bool(z3.Or([a.raw for a in args_list]), annotations=annotations)


def Not(a: Bool) -> Bool:
    """
    创建一个逻辑非(NOT)表达式

    Create a Not expression.

    :param a:
    :return:
    """
    return Bool(z3.Not(a.raw), a.annotations)


def is_false(a: Bool) -> bool:
    """
    检查布尔表达式是否可以简化为 False
    
    Returns whether the provided bool can be simplified to false.

    :param a:
    :return:
    """
    return z3.is_false(a.raw)


def is_true(a: Bool) -> bool:
    """
    检查布尔表达式是否可以简化为 True
    
    Returns whether the provided bool can be simplified to true.

    :param a:
    :return:
    """
    return z3.is_true(a.raw)
