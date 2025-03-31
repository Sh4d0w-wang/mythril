from time import time
from typing import Callable

from mythril.support.support_utils import Singleton


def stat_smt_query(func: Callable):
    """
    装饰器,用于测量和记录 SMT 查询的统计信息
    
    Measures statistics for annotated smt query check function
    """
    # 获取统计存储对象
    stat_store = SolverStatistics()

    def function_wrapper(*args, **kwargs):
        # 检查是否启用统计
        if not stat_store.enabled:
            return func(*args, **kwargs)
        # 记录查询次数
        stat_store.query_count += 1
        begin = time()
        # 调用原函数
        result = func(*args, **kwargs)

        end = time()
        stat_store.solver_time += end - begin

        return result

    return function_wrapper


class SolverStatistics(object, metaclass=Singleton):
    """
    用于存储和管理 SMT 查询的统计信息

    Solver Statistics Class

    Keeps track of the important statistics around smt queries
    """

    def __init__(self):
        """
        初始化统计信息
        """
        self.enabled = False
        self.query_count = 0
        self.solver_time = 0

    def __repr__(self):
        """
        返回类的字符串表示，方便打印和调试
        """
        return "Query count: {} \nSolver time: {}".format(
            self.query_count, self.solver_time
        )
