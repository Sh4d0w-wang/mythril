"""This module contains an abstract SMT representation of an SMT solver."""

import logging
import os
import sys
from typing import Generic, List, Sequence, TypeVar, Union, cast

import z3

from mythril.laser.smt.bool import Bool
from mythril.laser.smt.expression import Expression
from mythril.laser.smt.model import Model
from mythril.laser.smt.solver.solver_statistics import stat_smt_query

T = TypeVar("T", bound=Union[z3.Solver, z3.Optimize])

log = logging.getLogger(__name__)


class BaseSolver(Generic[T]):
    """
    供了 SMT 求解器的基本功能
    """
    def __init__(self, raw: T) -> None:
        """
        初始化求解器
        """
        self.raw = raw

    def set_timeout(self, timeout: int) -> None:
        """
        设置求解器的超时时间
        
        Sets the timeout that will be used by this solver, timeout is in
        milliseconds.

        :param timeout:
        """
        self.raw.set(timeout=timeout)

    def set_unsat_core(self) -> None:
        """
        启用生成不可满足核心(unsat core)的功能,这有助于诊断和调试不可满足的约束条件

        不可满足核心是指导致约束集合不可满足的最小约束子集

        启用这个功能后，当求解器发现约束集合不可满足时，可以提取出这些关键的约束，从而帮助诊断和调试问题

        Enables the generation of unsatisfiable cores in the solver. This option must be activated
        if you intend to identify and extract the minimal set of conflicting constraints that make
        a problem unsolvable. Useful for diagnosing and debugging unsatisfiable conditions within
        constraint sets.
        """
        # 发现不可满足时，生成并保留不可满足核心
        self.raw.set(unsat_core=True)

    def add(self, *constraints: Bool) -> None:
        """
        向求解器添加约束
        
        Adds the constraints to this solver.

        :param constraints:
        :return:
        """
        z3_constraints: Sequence[z3.BoolRef] = [
            c.raw for c in cast(List[Bool], constraints)
        ]
        self.raw.add(z3_constraints)

    def assert_and_track(self, constraints: Bool, name: str) -> None:
        """
        添加一个可跟踪的约束，用于提取不可满足核心

        Adds a constraint to the solver with an associated name, allowing the constraint to be tracked.
        This is particularly useful for identifying specific constraints contributing to an unsat.

        :param constraints: The constraints.
        :param name: A unique identifier for the constraint, used for tracking purposes in unsat core extraction.
        :return: None
        """
        # 不仅添加了约束，还为约束分配了一个唯一的名称，使得在后续的不可满足核心提取中可以识别该约束
        # 通过为约束分配唯一名称，可以更方便地识别哪些约束导致了不可满足
        self.raw.assert_and_track(constraints.raw, name)

    def append(self, *constraints: Bool) -> None:
        """
        向求解器添加约束

        Adds the constraints to this solver.

        :param constraints:
        :return:
        """
        self.add(*constraints)

    @stat_smt_query
    def check(self, *args) -> z3.CheckSatResult:
        """
        检查约束的可满足性，并抑制 Z3 的标准输出以避免不必要的输出

        Returns z3 smt check result.
        Also suppresses the stdout when running z3 library's check() to avoid unnecessary output
        :return: The evaluated result which is either of sat, unsat or unknown
        """
        old_stdout = sys.stdout
        # 临时将标准输出重定向到 /dev/null
        with open(os.devnull, "w") as dev_null_fd:
            sys.stdout = dev_null_fd
            try:
                # 检查当前约束集合是否可满足
                evaluate = self.raw.check(args)
            except z3.z3types.Z3Exception as e:
                # Some requests crash the solver
                evaluate = z3.unknown
                log.info(f"Encountered Z3 exception when checking the constraints: {e}")
        sys.stdout = old_stdout
        return evaluate

    def model(self) -> Model:
        """
        获取满足约束的模型

        Returns z3 model for a solution.

        :return:
        """
        try:
            return Model([self.raw.model()])
        except z3.z3types.Z3Exception as e:
            log.info(f"Encountered a Z3 exception while querying for the model: {e}")
            return Model()

    def sexpr(self):
        """
        返回求解器的 SMT 表达式
        """
        return self.raw.sexpr()


class Solver(BaseSolver[z3.Solver]):
    """
    具体的 SMT 求解器类,继承于BaseSolver
    
    An SMT solver object.
    """

    def __init__(self) -> None:
        """
        初始化一个具体的求解器
        """
        super().__init__(z3.Solver())

    def reset(self) -> None:
        """
        重置求解器，清除所有约束
        
        Reset this solver.
        """
        self.raw.reset()

    def pop(self, num: int) -> None:
        """
        从求解器中移除指定数量的约束
        
        Pop num constraints from this solver.

        :param num:
        """
        self.raw.pop(num)


class Optimize(BaseSolver[z3.Optimize]):
    """
    优化求解器类
    
    An optimizing smt solver.
    """

    def __init__(self) -> None:
        """
        初始化一个优化求解器
        
        Create a new optimizing solver instance.
        """
        super().__init__(z3.Optimize())

    def minimize(self, element: Expression[z3.ExprRef]) -> None:
        """
        在求解过程中尝试最小化某个表达式

        In solving this solver will try to minimize the passed expression.

        :param element:
        """
        self.raw.minimize(element.raw)

    def maximize(self, element: Expression[z3.ExprRef]) -> None:
        """
        在求解过程中尝试最大化某个表达式
        
        In solving this solver will try to maximize the passed expression.

        :param element:
        """
        self.raw.maximize(element.raw)
