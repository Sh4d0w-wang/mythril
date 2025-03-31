from typing import Any, Generic, Optional, Set, TypeVar, Union

import z3

from mythril.laser.smt.array import Array, BaseArray, K
from mythril.laser.smt.bitvec import BitVec
from mythril.laser.smt.bitvec_helper import (
    UGE,
    UGT,
    ULE,
    ULT,
    BVAddNoOverflow,
    BVMulNoOverflow,
    BVSubNoUnderflow,
    Concat,
    Extract,
    If,
    LShR,
    SRem,
    Sum,
    UDiv,
    URem,
)
from mythril.laser.smt.bool import And, Not, Or, is_false, is_true
from mythril.laser.smt.bool import Bool as SMTBool
from mythril.laser.smt.expression import Expression, simplify
from mythril.laser.smt.function import Function
from mythril.laser.smt.model import Model
from mythril.laser.smt.solver import Optimize, Solver, SolverStatistics

Annotations = Optional[Set[Any]]
T = TypeVar("T", bound=Union[SMTBool, z3.BoolRef])
U = TypeVar("U", bound=Union[BitVec, z3.BitVecRef])


class SymbolFactory(Generic[T, U]):
    """
    一个符号工厂，提供了一个默认接口，用于 Mythril 的各个组件创建符号

    T --> 布尔值的类型。U --> 位向量的类型。

    A symbol factory provides a default interface for all the components of mythril to create symbols
    """

    @staticmethod
    def Bool(value: "__builtins__.bool", annotations: Annotations = None) -> T:
        """
        创建一个具有具体值的布尔对象

        Creates a Bool with concrete value
        :param value: The boolean value
        :param annotations: The annotations to initialize the bool with
        :return: The freshly created Bool()
        """
        raise NotImplementedError

    @staticmethod
    def BoolSym(name: str, annotations: Annotations = None) -> T:
        """
        创建一个布尔符号

        Creates a boolean symbol
        :param name: The name of the Bool variable
        :param annotations: The annotations to initialize the bool with
        :return: The freshly created Bool()
        """
        raise NotImplementedError

    @staticmethod
    def BitVecVal(value: int, size: int, annotations: Annotations = None) -> U:
        """
        创建一个具有具体值的位向量

        Creates a new bit vector with a concrete value.

        :param value: The concrete value to set the bit vector to
        :param size: The size of the bit vector
        :param annotations: The annotations to initialize the bit vector with
        :return: The freshly created bit vector
        """
        raise NotImplementedError()

    @staticmethod
    def BitVecSym(name: str, size: int, annotations: Annotations = None) -> U:
        """
        创建一个符号位向量

        Creates a new bit vector with a symbolic value.

        :param name: The name of the symbolic bit vector
        :param size: The size of the bit vector
        :param annotations: The annotations to initialize the bit vector with
        :return: The freshly created bit vector
        """
        raise NotImplementedError()


class _SmtSymbolFactory(SymbolFactory[SMTBool, BitVec]):
    """
    具体的 SymbolFactory 实现

    An implementation of a SymbolFactory that creates symbols using
    the classes in: mythril.laser.smt
    """

    @staticmethod
    def Bool(value: "__builtins__.bool", annotations: Annotations = None) -> SMTBool:
        """
        创建一个具有具体值的布尔对象

        Creates a Bool with concrete value
        :param value: The boolean value
        :param annotations: The annotations to initialize the bool with
        :return: The freshly created Bool()
        """
        raw = z3.BoolVal(value)
        return SMTBool(raw, annotations)

    @staticmethod
    def BoolSym(name: str, annotations: Annotations = None) -> SMTBool:
        """
        创建一个布尔符号

        Creates a boolean symbol
        :param name: The name of the Bool variable
        :param annotations: The annotations to initialize the bool with
        :return: The freshly created Bool()
        """
        raw = z3.Bool(name)
        return SMTBool(raw, annotations)

    @staticmethod
    def BitVecVal(value: int, size: int, annotations: Annotations = None) -> BitVec:
        """
        创建一个具有具体值的位向量

        Creates a new bit vector with a concrete value.
        """
        raw = z3.BitVecVal(value, size)
        return BitVec(raw, annotations)

    @staticmethod
    def BitVecSym(name: str, size: int, annotations: Annotations = None) -> BitVec:
        """
        创建一个符号位向量

        Creates a new bit vector with a symbolic value.
        """
        raw = z3.BitVec(name, size)
        return BitVec(raw, annotations)


class _Z3SymbolFactory(SymbolFactory[z3.BoolRef, z3.BitVecRef]):
    """
    具体的 SymbolFactory 实现,返回Z3符号

    An implementation of a SymbolFactory that directly returns
    z3 symbols
    """

    @staticmethod
    def Bool(value: "__builtins__.bool", annotations: Annotations = None) -> z3.BoolRef:
        """
        创建一个具有具体值的布尔对象

        Creates a new bit vector with a concrete value
        """
        return z3.BoolVal(value)

    @staticmethod
    def BitVecVal(
        value: int, size: int, annotations: Annotations = None
    ) -> z3.BitVecRef:
        """
        创建一个具有具体值的位向量

        Creates a new bit vector with a concrete value.
        """
        return z3.BitVecVal(value, size)

    @staticmethod
    def BitVecSym(
        name: str, size: int, annotations: Annotations = None
    ) -> z3.BitVecRef:
        """
        创建一个符号位向量
        
        Creates a new bit vector with a symbolic value.
        """
        return z3.BitVec(name, size)


# This is the instance that other parts of mythril should use

# Type hints are not allowed here in 3.5
# symbol_factory: SymbolFactory = _SmtSymbolFactory()
symbol_factory = _SmtSymbolFactory()
