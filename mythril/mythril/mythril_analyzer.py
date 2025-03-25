#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import traceback
from argparse import Namespace
from typing import List, Optional

from mythril.analysis.callgraph import generate_graph
from mythril.analysis.report import Issue, Report
from mythril.analysis.security import fire_lasers, retrieve_callback_issues
from mythril.analysis.symbolic import SymExecWrapper
from mythril.analysis.traceexplore import get_serializable_statespace
from mythril.ethereum.evmcontract import EVMContract
from mythril.exceptions import DetectorNotFoundError
from mythril.laser.execution_info import ExecutionInfo
from mythril.laser.smt import SolverStatistics
from mythril.support.loader import DynLoader
from mythril.support.source_support import Source
from mythril.support.start_time import StartTime
from mythril.support.support_args import args

from .mythril_disassembler import MythrilDisassembler

log = logging.getLogger(__name__)

LARGE_TIME = 300


class MythrilAnalyzer:
    """
    封装了智能合约分析的逻辑，包括加载合约、执行符号执行、检测漏洞等

    The Mythril Analyzer class
    Responsible for the analysis of the smart contracts
    """

    def __init__(
        self,
        disassembler: MythrilDisassembler, # 反汇编器
        cmd_args: Namespace,
        strategy: str = "dfs", # 策略，默认深度优先搜索
        address: Optional[str] = None, # 合约地址
    ):
        """

        :param disassembler: The MythrilDisassembler class
        :param cmd_args: The command line args Namespace
        :param strategy: Search strategy
        :param address: Address of the contract
        """
        # 从rpc中获取eth实例
        self.eth = disassembler.eth
        # 合约
        self.contracts: List[EVMContract] = disassembler.contracts or []
        # 是否使用链上数据
        self.use_onchain_data = not cmd_args.no_onchain_data
        # 策略
        self.strategy = strategy
        # 合约地址
        self.address = address
        # 执行最大深度
        self.max_depth = cmd_args.max_depth
        # 执行超时时间
        self.execution_timeout = cmd_args.execution_timeout
        # 循环边界
        self.loop_bound = cmd_args.loop_bound
        # 创建超时时间
        self.create_timeout = cmd_args.create_timeout
        # 是否禁用依赖剪枝
        self.disable_dependency_pruning = cmd_args.disable_dependency_pruning
        # 自定义模块目录
        self.custom_modules_directory = (
            cmd_args.custom_modules_directory
            if cmd_args.custom_modules_directory
            else ""
        )
        # 剪枝因子
        args.pruning_factor = cmd_args.pruning_factor
        # 求解器超时时间
        args.solver_timeout = cmd_args.solver_timeout
        # 是否启用并行求解
        args.parallel_solving = cmd_args.parallel_solving
        # 是否启用无约束存储
        args.unconstrained_storage = cmd_args.unconstrained_storage
        # 调用深度限制
        args.call_depth_limit = cmd_args.call_depth_limit
        # 是否禁用指令分析
        args.disable_iprof = cmd_args.disable_iprof
        # 求解器日志
        args.solver_log = cmd_args.solver_log
        # 交易序列
        args.transaction_sequences = cmd_args.transaction_sequences
        # 是否禁用覆盖策略
        args.disable_coverage_strategy = cmd_args.disable_coverage_strategy
        # 是否禁用变异剪枝
        args.disable_mutation_pruner = cmd_args.disable_mutation_pruner
        # 是否启用摘要
        args.enable_summaries = cmd_args.enable_summaries
        # 是否启用状态合并
        args.enable_state_merge = cmd_args.enable_state_merging
        # 如果剪枝因子未设置，则根据执行超时时间自动设置
        if args.pruning_factor is None:
            if self.execution_timeout > LARGE_TIME:
                args.pruning_factor = 1
            else:
                args.pruning_factor = 0

    def dump_statespace(self, contract: EVMContract = None) -> str:
        """
        Returns serializable statespace of the contract
        :param contract: The Contract on which the analysis should be done
        :return: The serialized state space
        """
        sym = SymExecWrapper(
            contract or self.contracts[0],
            self.address,
            self.strategy,
            dynloader=DynLoader(self.eth, active=self.use_onchain_data),
            max_depth=self.max_depth,
            execution_timeout=self.execution_timeout,
            create_timeout=self.create_timeout,
            disable_dependency_pruning=self.disable_dependency_pruning,
            run_analysis_modules=False,
            custom_modules_directory=self.custom_modules_directory,
        )

        return get_serializable_statespace(sym)

    def graph_html(
        self,
        contract: EVMContract = None,
        enable_physics: bool = False,
        phrackify: bool = False,
        transaction_count: Optional[int] = None,
    ) -> str:
        """

        :param contract: The Contract on which the analysis should be done
        :param enable_physics: If true then enables the graph physics simulation
        :param phrackify: If true generates Phrack-style call graph
        :param transaction_count: The amount of transactions to be executed
        :return: The generated graph in html format
        """

        sym = SymExecWrapper(
            contract or self.contracts[0],
            self.address,
            self.strategy,
            dynloader=DynLoader(self.eth, active=self.use_onchain_data),
            max_depth=self.max_depth,
            execution_timeout=self.execution_timeout,
            transaction_count=transaction_count,
            create_timeout=self.create_timeout,
            disable_dependency_pruning=self.disable_dependency_pruning,
            run_analysis_modules=False,
            custom_modules_directory=self.custom_modules_directory,
        )
        return generate_graph(sym, physics=enable_physics, phrackify=phrackify)

    def fire_lasers(
        self,
        modules: Optional[List[str]] = None,
        transaction_count: Optional[int] = None,
    ) -> Report:
        """
        :param modules: The analysis modules which should be executed
        :param transaction_count: The amount of transactions to be executed
        :return: The Report class which contains the all the issues/vulnerabilities
        """
        all_issues: List[Issue] = []
        SolverStatistics().enabled = True
        exceptions = []
        execution_info: Optional[List[ExecutionInfo]] = None
        for contract in self.contracts:
            StartTime()  # Reinitialize start time for new contracts
            try:
                sym = SymExecWrapper(
                    contract,
                    self.address,
                    self.strategy,
                    dynloader=DynLoader(self.eth, active=self.use_onchain_data),
                    max_depth=self.max_depth,
                    execution_timeout=self.execution_timeout,
                    loop_bound=self.loop_bound,
                    create_timeout=self.create_timeout,
                    transaction_count=transaction_count,
                    modules=modules,
                    compulsory_statespace=False,
                    disable_dependency_pruning=self.disable_dependency_pruning,
                    custom_modules_directory=self.custom_modules_directory,
                )
                issues = fire_lasers(sym, modules)
                execution_info = sym.execution_info
            except DetectorNotFoundError as e:
                # Bubble up
                raise e
            except KeyboardInterrupt:
                log.critical("Keyboard Interrupt")
                issues = retrieve_callback_issues(modules)
            except Exception:
                log.critical(
                    "Exception occurred, aborting analysis. Please report this issue to the Mythril GitHub page.\n"
                    + traceback.format_exc()
                )
                issues = retrieve_callback_issues(modules)
                exceptions.append(traceback.format_exc())
            for issue in issues:
                issue.add_code_info(contract)

            all_issues += issues
            log.info("Solver statistics: \n{}".format(str(SolverStatistics())))

        source_data = Source()
        source_data.get_source_from_contracts_list(self.contracts)

        # Finally, output the results
        report = Report(
            contracts=self.contracts,
            exceptions=exceptions,
            execution_info=execution_info,
        )
        for issue in all_issues:
            report.append_issue(issue)

        return report
