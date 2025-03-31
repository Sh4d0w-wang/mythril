"""This module contains an SMT abstraction of arrays.

This includes an Array class to implement basic store and set
operations, as well as as a K-array, which can be initialized with
default values over a certain range.
"""

from typing import cast

import z3

from mythril.laser.smt.bitvec import BitVec


class BaseArray:
    """
    数组,提供了基本的存储和设置操作
    
    Base array type, which implements basic store and set operations.
    """

    def __init__(self, raw):
        """
        初始化数组
        """
        self.raw = raw

    def __getitem__(self, item: BitVec) -> BitVec:
        """
        从数组中获取一个元素

        Gets item from the array, item can be symbolic.
        """
        if isinstance(item, slice):
            raise ValueError(
                "Instance of BaseArray, does not support getitem with slices"
            )
        # 使用 z3.Select 从数组中选择元素，并返回一个 BitVec 对象
        return BitVec(cast(z3.BitVecRef, z3.Select(self.raw, item.raw)))

    def __setitem__(self, key: BitVec, value: BitVec) -> None:
        """
        在数组中设置一个元素

        Sets an item in the array, key can be symbolic.
        """
        # 使用 z3.Store 在数组中存储值
        self.raw = z3.Store(self.raw, key.raw, value.raw)

    def substitute(self, original_expression, new_expression):
        """
        替换数组中的子表达式

        :param original_expression:
        :param new_expression:
        """
        if self.raw is None:
            return
        original_z3 = original_expression.raw
        new_z3 = new_expression.raw
        self.raw = z3.substitute(self.raw, (original_z3, new_z3))


class Array(BaseArray):
    """
    表示一个基本的符号数组
    
    A basic symbolic array.
    """

    def __init__(self, name: str, domain: int, value_range: int):
        """
        初始化一个符号数组(名称,索引的位宽,值的位宽)
        
        Initializes a symbolic array.

        :param name: Name of the array
        :param domain: The domain for the array (10 -> all the values that a bv of size 10 could take)
        :param value_range: The range for the values in the array (10 -> all the values that a bv of size 10 could take)
        """
        # 使用 z3.BitVecSort 创建索引和值的类型
        self.domain = z3.BitVecSort(domain)
        self.range = z3.BitVecSort(value_range)
        # 创建一个符号数组
        super(Array, self).__init__(z3.Array(name, self.domain, self.range))


class K(BaseArray):
    """
    表示一个可以初始化默认值的符号数组
    
    A basic symbolic array, which can be initialized with a default value.
    """

    def __init__(self, domain: int, value_range: int, value: int):
        """
        初始化一个带有默认值的数组(索引的位宽,值的位宽,默认值)
        
        Initializes an array with a default value.

        :param domain: The domain for the array (10 -> all the values that a bv of size 10 could take)
        :param value_range: The range for the values in the array (10 -> all the values that a bv of size 10 could take)
        :param value: The default value to use for this array
        """
        self.domain = z3.BitVecSort(domain)
        self.value = z3.BitVecVal(value, value_range)
        self.raw = z3.K(self.domain, self.value)
