from typing import Dict, List, Set, Tuple, cast

import z3

from mythril.laser.smt.bool import Bool
from mythril.laser.smt.model import Model
from mythril.laser.smt.solver.solver_statistics import stat_smt_query


def _get_expr_variables(expression: z3.ExprRef) -> List[z3.ExprRef]:
    """
    提取 Z3 表达式中的所有变量
    
    Gets the variables that make up the current expression
    :param expression:
    :return:
    """
    result = []
    if not expression.children() and not isinstance(expression, z3.BitVecNumRef):
        result.append(expression)
    for child in expression.children():
        c_children = _get_expr_variables(child)
        result.extend(c_children)
    return result


class DependenceBucket:
    """
    存储一组相互依赖的条件和变量
    
    Bucket object to contain a set of conditions that are dependent on each other
    """

    def __init__(self, variables=None, conditions=None):
        """
        初始化一组相互依赖的条件和变量
        Initializes a DependenceBucket object
        :param variables: Variables contained in the conditions
        :param conditions: The conditions that are dependent on each other
        """
        self.variables: List[z3.ExprRef] = variables or []
        self.conditions: List[z3.ExprRef] = conditions or []


class DependenceMap:
    """
    管理多个 DependenceBucket,并根据条件的依赖关系将它们分组
    
    DependenceMap object that maintains a set of dependence buckets, used to separate independent smt queries"""

    def __init__(self):
        """
        初始化一个DependenceMap
        
        Initializes a DependenceMap object
        """
        self.buckets: List[DependenceBucket] = []
        # 将变量映射到它们所属的 DependenceBucket
        self.variable_map: Dict[str, DependenceBucket] = {}

    def add_condition(self, condition: z3.BoolRef) -> None:
        """
        添加条件到DependenceMap中


        Add condition to the dependence map
        :param condition: The condition that is to be added to the dependence map
        """
        # 提取条件中的变量
        variables = set(_get_expr_variables(condition))
        relevant_buckets = set()
        for variable in variables:
            try:
                # 查找与这些变量相关的 DependenceBucket
                bucket = self.variable_map[str(variable)]
                relevant_buckets.add(bucket)
            except KeyError:
                continue
        # 创建一个新的 DependenceBucket，并将条件加入其中
        new_bucket = DependenceBucket(variables, [condition])
        self.buckets.append(new_bucket)
        # 如果存在相关的 DependenceBucket，则将它们合并
        if relevant_buckets:
            # Merge buckets, and rewrite variable map accordingly
            relevant_buckets.add(new_bucket)
            new_bucket = self._merge_buckets(relevant_buckets)

        for variable in new_bucket.variables:
            self.variable_map[str(variable)] = new_bucket

    def _merge_buckets(self, bucket_list: Set[DependenceBucket]) -> DependenceBucket:
        """
        合并一组 DependenceBucket
        
        Merges the buckets in bucket list"""
        variables: List[str] = []
        conditions: List[z3.BoolRef] = []
        for bucket in bucket_list:
            self.buckets.remove(bucket)
            variables += bucket.variables
            conditions += bucket.conditions

        new_bucket = DependenceBucket(variables, conditions)
        self.buckets.append(new_bucket)

        return new_bucket


class IndependenceSolver:
    """
    一个优化的 SMT 求解器,利用独立性优化(independence optimization)来提高求解效率
    
    An SMT solver object that uses independence optimization"""

    def __init__(self):
        """
        初始化一个求解器
        """
        self.raw = z3.Solver()
        self.constraints = []
        self.models = []

    def set_timeout(self, timeout: int) -> None:
        """
        设置求解器的超时时间

        Sets the timeout that will be used by this solver, timeout is in milliseconds.

        :param timeout:
        """
        self.raw.set(timeout=timeout)

    def add(self, *constraints: Bool) -> None:
        """
        将一个或多个约束(Bool 类型)添加到求解器中
        
        Adds the constraints to this solver.

        :param constraints: constraints to add
        """
        # 包含所有转换后的 Z3 约束
        raw_constraints: List[z3.BoolRef] = [
            c.raw for c in cast(Tuple[Bool], constraints)
        ]
        self.constraints.extend(raw_constraints)

    def append(self, *constraints: Tuple[Bool]) -> None:
        """
        将一个或多个约束(Bool 类型)添加到求解器中
        
        Adds the constraints to this solver.

        :param constraints: constraints to add
        """
        # 包含所有转换后的 Z3 约束
        raw_constraints: List[z3.BoolRef] = [
            c.raw for c in cast(Tuple[Bool], constraints)
        ]
        self.constraints.extend(raw_constraints)

    @stat_smt_query
    def check(self) -> z3.CheckSatResult:
        """
        使用独立性优化来检查约束的可满足性

        Returns z3 smt check result.
        """
        # 创建一个 DependenceMap，将约束分组到独立的 DependenceBucket 中
        dependence_map = DependenceMap()
        # 对每个 DependenceBucket，重置 Z3 求解器，添加相关条件，并检查可满足性
        for constraint in self.constraints:
            dependence_map.add_condition(constraint)

        self.models = []
        # 如果所有 DependenceBucket 都可满足，则将所有模型存储到 models 中，并返回 z3.sat
        for bucket in dependence_map.buckets:
            # 重置求解器，清空所有约束
            self.raw.reset()
            self.raw.append(*bucket.conditions)
            check_result = self.raw.check()
            if check_result == z3.sat:
                self.models.append(self.raw.model())
            else:
                # 如果某个 DependenceBucket 不可满足，则返回 z3.unsat
                return check_result

        return z3.sat

    def model(self) -> Model:
        """
        返回一个 Model 对象，封装了所有满足约束的模型
        
        Returns z3 model for a solution.
        """
        return Model(self.models)

    def reset(self) -> None:
        """
        重置求解器，清空所有约束
        
        Reset this solver.
        """
        self.constraints = []

    def pop(self, num) -> None:
        """
        从约束列表中移除指定数量的约束
        
        Pop num constraints from this solver.
        """
        self.constraints.pop(num)
