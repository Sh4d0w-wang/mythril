import z3

from mythril.laser.smt.solver.independence_solver import IndependenceSolver
from mythril.laser.smt.solver.solver import BaseSolver, Optimize, Solver
from mythril.laser.smt.solver.solver_statistics import SolverStatistics
from mythril.support.support_args import args

# 并行求解，允许求解器在多核处理器上并行执行，从而提高求解效率
if args.parallel_solving:
    z3.set_param("parallel.enable", True)
