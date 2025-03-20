#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mythril.py: Bug hunting on the Ethereum blockchain

http://www.github.com/ConsenSys/mythril
"""

import argparse
import json
import logging
import os
import sys
import traceback
from argparse import ArgumentParser, Namespace, RawTextHelpFormatter
from ast import literal_eval

import coloredlogs

from mythril.__version__ import __version__ as VERSION
from mythril.analysis.module import ModuleLoader
from mythril.analysis.report import Report
from mythril.concolic import concolic_execution
from mythril.exceptions import (
    CriticalError,
    DetectorNotFoundError,
)
from mythril.laser.ethereum.transaction.symbolic import ACTORS
from mythril.mythril import MythrilAnalyzer, MythrilConfig, MythrilDisassembler
from mythril.plugin.loader import MythrilPluginLoader

# Initialise core Mythril Component
_ = MythrilPluginLoader()

ANALYZE_LIST = ("analyze", "a")
DISASSEMBLE_LIST = ("disassemble", "d")
FOUNDRY_LIST = ("foundry", "f")

CONCOLIC_LIST = ("concolic", "c")
SAFE_FUNCTIONS_COMMAND = "safe-functions"
READ_STORAGE_COMNAND = "read-storage"
FUNCTION_TO_HASH_COMMAND = "function-to-hash"
HASH_TO_ADDRESS_COMMAND = "hash-to-address"
LIST_DETECTORS_COMMAND = "list-detectors"
VERSION_COMMAND = "version"
HELP_COMMAND = "help"

log = logging.getLogger(__name__)

COMMAND_LIST = (
    ANALYZE_LIST
    + DISASSEMBLE_LIST
    + FOUNDRY_LIST
    + CONCOLIC_LIST
    + (
        READ_STORAGE_COMNAND,
        SAFE_FUNCTIONS_COMMAND,
        FUNCTION_TO_HASH_COMMAND,
        HASH_TO_ADDRESS_COMMAND,
        LIST_DETECTORS_COMMAND,
        VERSION_COMMAND,
        HELP_COMMAND,
    )
)


def exit_with_error(format_, message):
    """
    Exits with error
    :param format_: The format of the message
    :param message: message
    """
    if format_ == "text" or format_ == "markdown":
        log.error(message)
    elif format_ == "json":
        result = {"success": False, "error": str(message), "issues": []}
        print(json.dumps(result))
    else:
        result = [
            {
                "issues": [],
                "sourceType": "",
                "sourceFormat": "",
                "sourceList": [],
                "meta": {"logs": [{"level": "error", "hidden": True, "msg": message}]},
            }
        ]
        print(json.dumps(result))
    sys.exit()


def get_runtime_input_parser() -> ArgumentParser:
    """
    Returns Parser which handles input
    :return: Parser which handles input
    """
    parser = ArgumentParser(add_help=False)
    parser.add_argument(
        "-a",
        "--address",
        help="pull contract from the blockchain",
        metavar="CONTRACT_ADDRESS",
    )
    parser.add_argument(
        "--bin-runtime",
        action="store_true",
        help="Only when -c or -f is used. Consider the input bytecode as binary runtime code, default being the contract creation bytecode.",
    )
    return parser


def get_creation_input_parser() -> ArgumentParser:
    """
    Returns Parser which handles input
    :return: Parser which handles input
    """
    parser = ArgumentParser(add_help=False)
    parser.add_argument(
        "-c",
        "--code",
        help='hex-encoded bytecode string ("6060604052...")',
        metavar="BYTECODE",
    )
    parser.add_argument(
        "-f",
        "--codefile",
        help="file containing hex-encoded bytecode string",
        metavar="BYTECODEFILE",
        type=argparse.FileType("r"),
    )
    return parser


def get_safe_functions_parser() -> ArgumentParser:
    """
    Returns Parser which handles checking for safe functions
    :return: Parser which handles checking for safe functions
    """
    parser = ArgumentParser(add_help=False)
    parser.add_argument(
        "-c",
        "--code",
        help='hex-encoded bytecode string ("6060604052...")',
        metavar="BYTECODE",
    )
    parser.add_argument(
        "-f",
        "--codefile",
        help="file containing hex-encoded bytecode string",
        metavar="BYTECODEFILE",
        type=argparse.FileType("r"),
    )
    return parser


def get_output_parser() -> ArgumentParser:
    """
    Get parser which handles output
    :return: Parser which handles output
    """
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "-o",
        "--outform",
        choices=["text", "markdown", "json", "jsonv2"],
        default="text",
        help="report output format",
        metavar="<text/markdown/json/jsonv2>",
    )
    return parser


def get_rpc_parser() -> ArgumentParser:
    """
    Get parser which handles RPC flags
    :return: Parser which handles rpc inputs
    """
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--rpc",
        help="custom RPC settings",
        metavar="HOST:PORT / ganache / infura-[network_name]",
        default="infura-mainnet",
    )
    parser.add_argument(
        "--rpctls", type=bool, default=False, help="RPC connection over TLS"
    )
    parser.add_argument("--infura-id", help="set infura id for onchain analysis")

    return parser


def get_utilities_parser() -> ArgumentParser:
    """
    Get parser which handles utilities flags
    :return: Parser which handles utility flags
    """
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--solc-json",
        help="Json for the optional 'settings' parameter of solc's standard-json input",
    )
    parser.add_argument(
        "--solc-args",
        help="""Provide solc args, example: --solc-args "--allow-paths --include-path /root_folder/node_modules --base-path /home/contracts" """,
        type=str,
    )
    parser.add_argument(
        "--solv",
        help="specify solidity compiler version. If not present, will try to install it (Experimental)",
        metavar="SOLV",
    )
    return parser


def create_concolic_parser(parser: ArgumentParser) -> ArgumentParser:
    """
    智能合约的分支翻转分析添加命令
    Get parser which handles arguments for concolic branch flipping
    """
    parser.add_argument(
        "input",
        help="The input jsonv2 file with concrete data",
    )
    # 允许用户指定需要翻转的分支地址
    parser.add_argument(
        "--branches",
        help="branch addresses to be flipped. usage: --branches 34,6f8,16a",
        required=True,
        metavar="BRANCH",
    )
    # 求解器处理查询的最大时间
    parser.add_argument(
        "--solver-timeout",
        type=int,
        default=100000,
        help="The maximum amount of time(in milli seconds) the solver spends for queries from analysis modules",
    )
    return parser


def main() -> None:
    """The main CLI interface entry point."""

    # 获取RPC参数
    rpc_parser = get_rpc_parser()
    # 获取通用工具的参数
    utilities_parser = get_utilities_parser()
    # 获取运行时参数
    runtime_input_parser = get_runtime_input_parser()
    # 获取创建时参数
    creation_input_parser = get_creation_input_parser()
    # 获取输出相关参数
    output_parser = get_output_parser()
    # 定义主解析器 parser
    parser = argparse.ArgumentParser(
        description="Security analysis of Ethereum smart contracts"
    )
    # 增加 --epic 设置True，使用下来感觉是上色...
    # 增加 -v 设置日志级别
    parser.add_argument("--epic", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument(
        "-v", type=int, help="log level (0-5)", metavar="LOG_LEVEL", default=2
    )

    # 创建子命令集
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    # 1. safe-functions
    # 使用符号执行检查完全安全的函数
    safe_function_parser = subparsers.add_parser(
        SAFE_FUNCTIONS_COMMAND,
        help="Check functions which are completely safe using symbolic execution",
        parents=[
            rpc_parser,
            utilities_parser,
            creation_input_parser,
            runtime_input_parser,
            output_parser,
        ],
        formatter_class=RawTextHelpFormatter,
    )
    # 添加参数
    create_safe_functions_parser(safe_function_parser)

    # 2. analyze
    # 分析合约,最重要的
    analyzer_parser = subparsers.add_parser(
        ANALYZE_LIST[0],
        help="Triggers the analysis of the smart contract",
        parents=[
            rpc_parser,
            utilities_parser,
            creation_input_parser,
            runtime_input_parser,
            output_parser,
        ],
        aliases=ANALYZE_LIST[1:],
        formatter_class=RawTextHelpFormatter,
    )
    # 添加参数
    create_analyzer_parser(analyzer_parser)

    # 3. disassemble
    # 反汇编合约
    disassemble_parser = subparsers.add_parser(
        DISASSEMBLE_LIST[0],
        help="Disassembles the smart contract",
        aliases=DISASSEMBLE_LIST[1:],
        parents=[
            rpc_parser,
            utilities_parser,
            creation_input_parser,
            runtime_input_parser,
        ],
        formatter_class=RawTextHelpFormatter,
    )
    # 添加参数
    create_disassemble_parser(disassemble_parser)

    # 4. concolic
    # 运行共线性执行以翻转目标分支
    concolic_parser = subparsers.add_parser(
        CONCOLIC_LIST[0],
        help="Runs concolic execution to flip the desired branches",
        aliases=CONCOLIC_LIST[1:],
        parents=[],
        formatter_class=RawTextHelpFormatter,
    )
    # 添加参数
    create_concolic_parser(concolic_parser)

    # 5. foundry
    # 分析foundry下的合约
    # 为 Foundry 相关的命令创建一个专用的解析器
    foundry_parser = subparsers.add_parser(
        FOUNDRY_LIST[0],
        help="Triggers the analysis of the smart contract",
        parents=[
            rpc_parser,
            utilities_parser,
            output_parser,
        ],
        aliases=FOUNDRY_LIST[1:],
        formatter_class=RawTextHelpFormatter,
    )
    # 添加参数
    create_foundry_parser(foundry_parser)

    # 6. list-detectors
    # 列举可用的检测
    _ = subparsers.add_parser(
        LIST_DETECTORS_COMMAND,
        parents=[output_parser],
        help="Lists available detection modules",
    )

    # 7. read-storage
    # 通过RPC获取slot
    read_storage_parser = subparsers.add_parser(
        READ_STORAGE_COMNAND,
        help="Retrieves storage slots from a given address through rpc",
        parents=[rpc_parser],
    )
    # 添加参数
    create_read_storage_parser(read_storage_parser)

    # 8. function-to-hash
    # 返回函数的签名
    contract_func_to_hash = subparsers.add_parser(
        FUNCTION_TO_HASH_COMMAND, help="Returns the hash signature of the function"
    )
    # 添加参数
    create_func_to_hash_parser(contract_func_to_hash)

    # 9. hash-to-address
    # 转换哈希为以太坊地址
    contract_hash_to_addr = subparsers.add_parser(
        HASH_TO_ADDRESS_COMMAND,
        help="converts the hashes in the blockchain to ethereum address",
    )
    # 添加参数
    create_hash_to_addr_parser(contract_hash_to_addr)

    # 10. version
    # 版本
    subparsers.add_parser(
        VERSION_COMMAND, parents=[output_parser], help="Outputs the version"
    )

    # 11. help
    subparsers.add_parser(HELP_COMMAND, add_help=False)

    # Get config values
    args = parser.parse_args()

    # 入口
    # 解析参数并执行
    parse_args_and_execute(parser=parser, args=args)


def create_disassemble_parser(parser: ArgumentParser):
    """
    添加反汇编参数
    Modify parser to handle disassembly
    :param parser:
    :return:
    """
    # Using nargs=* would the implementation below for getting code for both disassemble and analyze
    parser.add_argument(
        "solidity_files",
        nargs="*",
        help="Inputs file name and contract name. Currently supports a single contract\n"
        "usage: file1.sol:OptionalContractName",
    )


def create_read_storage_parser(read_storage_parser: ArgumentParser):
    """
    Modify parser to handle storage slots
    :param read_storage_parser:
    :return:
    """
    # 读取连续的slots
    # 0,5,array --> 从0开始读到5
    # 读取映射类型的slots
    # mapping,1,[0x12,0x34] --> 读取映射类型，索引1，键值0x12，0x34
    read_storage_parser.add_argument(
        "storage_slots",
        help="read state variables from storage index",
        metavar="INDEX,NUM_SLOTS,[array] / mapping,INDEX,[KEY1, KEY2...]",
    )
    read_storage_parser.add_argument(
        "address", help="contract address", metavar="ADDRESS"
    )


def create_func_to_hash_parser(parser: ArgumentParser):
    """
    Modify parser to handle func_to_hash command
    :param parser:
    :return:
    """
    parser.add_argument(
        "func_name", help="calculate function signature hash", metavar="SIGNATURE"
    )


def create_hash_to_addr_parser(hash_parser: ArgumentParser):
    """
    Modify parser to handle hash_to_addr command
    :param hash_parser:
    :return:
    """
    hash_parser.add_argument(
        "hash", help="Find the address from hash", metavar="FUNCTION_NAME"
    )


def add_graph_commands(parser: ArgumentParser):
    """
    添加与图形生成相关的命令,生成cfg/json
    """
    commands = parser.add_argument_group("commands")
    commands.add_argument("-g", "--graph", help="generate a control flow graph")
    commands.add_argument(
        "-j",
        "--statespace-json",
        help="dumps the statespace json",
        metavar="OUTPUT_FILE",
    )


def create_safe_functions_parser(parser: ArgumentParser):
    """
    添加文件参数
    The duplication exists between safe-functions and analyze as some of them have different default values.
    :param parser: Parser
    """
    parser.add_argument(
        "solidity_files",
        nargs="*",
        help="Inputs file name and contract name. \n"
        "usage: file1.sol:OptionalContractName file2.sol file3.sol:OptionalContractName",
    )

    options = parser.add_argument_group("options")
    add_analysis_args(options)


def add_analysis_args(options):
    """
    命令行添加分析参数
    Adds arguments for analysis

    :param options: Analysis Options
    """

    # 指定 安全分析模块 列表
    options.add_argument(
        "-m",
        "--modules",
        help="Comma-separated list of security analysis modules",
        metavar="MODULES",
    )
    # 符号执行的最大深度，默认128
    options.add_argument(
        "--max-depth",
        type=int,
        default=128,
        help="Maximum recursion depth for symbolic execution",
    )
    # 调用的最大深度，默认3
    options.add_argument(
        "--call-depth-limit",
        type=int,
        default=3,
        help="Maximum call depth limit for symbolic execution",
    )
    # 符号执行策略，默认广度优先
    # 可选：深度优先、随机策略、加权随机策略、待处理
    options.add_argument(
        "--strategy",
        choices=["dfs", "bfs", "naive-random", "weighted-random", "pending"],
        default="bfs",
        help="Symbolic execution strategy",
    )
    # 指定交易序列，用于约束符号执行路径
    # [[func_hash1, func_hash2], [func_hash2, func_hash3]]
    # 第一笔交易是func_hash1或者func_hash2，第二笔交易func_hash2或者func_hash3
    # -1 表示作为一个代理的fallback()
    # -2 表示receive()
    options.add_argument(
        "--transaction-sequences",
        type=str,
        default=None,
        help="The possible transaction sequences to be executed. "
        "Like [[func_hash1, func_hash2], [func_hash2, func_hash3]] where the first transaction is constrained "
        "with func_hash1 and func_hash2, and the second tx is constrained with func_hash2 and func_hash3. Use -1 as a proxy for fallback() function and -2 for receive() function.",
    )
    # 启用Beam Search算法的宽度
    options.add_argument(
        "--beam-search",
        type=int,
        default=None,
        help="Beam search with with",
    )
    # 限制循环的最大迭代次数
    options.add_argument(
        "-b",
        "--loop-bound",
        type=int,
        default=3,
        help="Bound loops at n iterations",
        metavar="N",
    )
    # 最大的交易数量，默认为2
    options.add_argument(
        "-t",
        "--transaction-count",
        type=int,
        default=2,
        help="Maximum number of transactions issued by laser",
    )
    # 符号执行的超时时间，默认36000
    options.add_argument(
        "--execution-timeout",
        type=int,
        default=3600,
        help="The amount of seconds to spend on symbolic execution",
    )
    # 求解器处理分析模块查询的最大时间
    options.add_argument(
        "--solver-timeout",
        type=int,
        default=25000,
        help="The maximum amount of time(in milli seconds) the solver spends for queries from analysis modules",
    )
    # 合约创建阶段的最大运行时间
    options.add_argument(
        "--create-timeout",
        type=int,
        default=30,
        help="The amount of seconds to spend on the initial contract creation",
    )
    # 启用并行求解
    options.add_argument(
        "--parallel-solving",
        action="store_true",
        help="Enable solving z3 queries in parallel",
    )
    # 求解器日志
    options.add_argument(
        "--solver-log",
        help="Path to the directory for solver log",
        metavar="SOLVER_LOG",
    )
    # 禁用链上获取数据
    options.add_argument(
        "--no-onchain-data",
        action="store_true",
        help="Don't attempt to retrieve contract code, variables and balances from the blockchain",
    )
    # 控制符号执行过程中的剪枝策略
    options.add_argument(
        "--pruning-factor",
        type=float,
        default=None,
        help="Checks for reachability at the rate of <pruning-factor> (range 0-1.0). Where 1.0 would mean checking for every execution",
    )
    # 将storage视为符号，不从链上获取真实值
    options.add_argument(
        "--unconstrained-storage",
        action="store_true",
        help="Default storage value is symbolic, turns off the on-chain storage loading",
    )
    # 启用 Phrack 风格的调用图
    options.add_argument(
        "--phrack", action="store_true", help="Phrack-style call graph"
    )
    # 启用物理模拟
    options.add_argument(
        "--enable-physics", action="store_true", help="Enable graph physics simulation"
    )
    # 查询函数签名
    options.add_argument(
        "-q",
        "--query-signature",
        action="store_true",
        help="Lookup function signatures through www.4byte.directory",
    )
    # 禁用指令分析器
    options.add_argument(
        "--disable-iprof", action="store_true", help="Disable the instruction profiler"
    )
    # 禁用基于依赖关系的剪枝，保留更多的执行路劲
    options.add_argument(
        "--disable-dependency-pruning",
        action="store_true",
        help="Deactivate dependency-based pruning",
    )
    # 禁用基于覆盖发搜索策略，选择其他搜索策略
    options.add_argument(
        "--disable-coverage-strategy",
        action="store_true",
        help="Disable coverage based search strategy",
    )
    # 禁用变异剪枝，以保留更多可能的执行路径
    options.add_argument(
        "--disable-mutation-pruner",
        action="store_true",
        help="Disable mutation pruner",
    )
    # 启用状态合并，以优化符号执行的效率
    options.add_argument(
        "--enable-state-merging",
        action="store_true",
        help="Enable State Merging",
    )
    # 启用符号摘要，以优化符号执行的效率
    options.add_argument(
        "--enable-summaries",
        action="store_true",
        help="Enable using symbolic summaries",
    )
    # 指定一个目录，用于加载自定义的分析模块
    options.add_argument(
        "--custom-modules-directory",
        help="Designates a separate directory to search for custom analysis modules",
        metavar="CUSTOM_MODULES_DIRECTORY",
    )
    # 指定一个地址，用于模拟攻击者的行为
    options.add_argument(
        "--attacker-address",
        help="Designates a specific attacker address to use during analysis",
        metavar="ATTACKER_ADDRESS",
    )
    # 指定一个地址，用于模拟合约创建者的行为
    options.add_argument(
        "--creator-address",
        help="Designates a specific creator address to use during analysis",
        metavar="CREATOR_ADDRESS",
    )


def create_analyzer_parser(analyzer_parser: ArgumentParser):
    """
    添加文件参数
    Modify parser to handle analyze command
    :param analyzer_parser:
    :return:
    """
    analyzer_parser.add_argument(
        "solidity_files",
        nargs="*",
        help="Inputs file name and contract name. \n"
        "usage: file1.sol:OptionalContractName file2.sol file3.sol:OptionalContractName",
    )
    add_graph_commands(analyzer_parser)
    options = analyzer_parser.add_argument_group("options")
    add_analysis_args(options)


def create_foundry_parser(foundry_parser: ArgumentParser):
    add_graph_commands(foundry_parser)
    options = foundry_parser.add_argument_group("options")
    add_analysis_args(options)


def validate_args(args: Namespace):
    """
    验证参数
    Validate cli args
    :param args:
    :return:
    """
    # 是否启用了-v(用于设置日志级别)
    if hasattr(args, "v"):
        if 0 <= args.v < 6:
            log_levels = [
                logging.NOTSET,
                logging.CRITICAL,
                logging.ERROR,
                logging.WARNING,
                logging.INFO,
                logging.DEBUG,
            ]
            coloredlogs.install(
                fmt="%(name)s [%(levelname)s]: %(message)s", level=log_levels[args.v]
            )
        else:
            exit_with_error(
                args.outform, "Invalid -v value, you can find valid values in usage"
            )
    # 使用了反汇编命令，但提供了多个文件，退出
    if args.command in DISASSEMBLE_LIST and len(args.solidity_files) > 1:
        exit_with_error("text", "Only a single arg is supported for using disassemble")
    
    if getattr(args, "transaction_sequences", None):
        # 指定了交易序列，但未禁用依赖剪枝，警告
        if getattr(args, "disable_dependency_pruning", False) is False:
            log.warning(
                "It is advised to disable dependency pruning (use the flag --disable-dependency-pruning) when specifying transaction sequences."
            )
        try:
            # 将交易序列从字符串解析为 Python 对象
            args.transaction_sequences = literal_eval(str(args.transaction_sequences))
        except ValueError:
            exit_with_error(
                args.outform,
                "The transaction sequence is in incorrect format, It should be "
                "[list of possible function hashes in 1st transaction, "
                "list of possible func hashes in 2nd tx, ...] "
                "If any list is empty then all possible functions are considered for that transaction."
                "Use -1 as a proxy for fallback() and -2 for receive() function.",
            )
        # 交易序列的长度与交易数量不一致，更新交易数量为交易序列的长度
        if len(args.transaction_sequences) != args.transaction_count:
            args.transaction_count = len(args.transaction_sequences)


def set_config(args: Namespace):
    """
    Set config based on args
    :param args:
    :return: modified config
    """
    config = MythrilConfig()

    # 设置 Infura ID
    if getattr(args, "infura_id", None):
        config.set_api_infura_id(args.infura_id)
    
    # 指定了分析指令，但没有指定 --no-onchain-data 参数和指定 --rpc 或 --i 参数
    if (args.command in ANALYZE_LIST and not args.no_onchain_data) and not (
        args.rpc or args.i
    ):
        # 从config.ini中加载 API 设置
        config.set_api_from_config_path()

    # 设置rpc
    if getattr(args, "rpc", None):
        # Establish RPC connection if necessary
        config.set_api_rpc(rpc=args.rpc, rpctls=args.rpctls)

    return config


def load_code(disassembler: MythrilDisassembler, args: Namespace):
    """
    Loads code into disassembly and returns address
    :param disassembler:
    :param args:
    :return: Address
    """

    address = None
    if getattr(args, "code", None):
        # Load from bytecode
        code = args.code[2:] if args.code.startswith("0x") else args.code
        address, _ = disassembler.load_from_bytecode(code, args.bin_runtime)
    elif getattr(args, "codefile", None):
        bytecode = "".join([l.strip() for l in args.codefile if len(l.strip()) > 0])
        bytecode = bytecode[2:] if bytecode.startswith("0x") else bytecode
        address, _ = disassembler.load_from_bytecode(bytecode, args.bin_runtime)
    elif getattr(args, "address", None):
        # Get bytecode from a contract address
        address, _ = disassembler.load_from_address(args.address)
    elif getattr(args, "solidity_files", None):
        # Compile Solidity source file(s)
        if args.command in ANALYZE_LIST and args.graph and len(args.solidity_files) > 1:
            exit_with_error(
                args.outform,
                "Cannot generate call graphs from multiple input files. Please do it one at a time.",
            )
        address, _ = disassembler.load_from_solidity(
            args.solidity_files
        )  # list of files
    elif args.command in FOUNDRY_LIST:
        address, _ = disassembler.load_from_foundry()

    else:
        exit_with_error(
            getattr(args, "outform", "text"),
            "No input bytecode. Please provide EVM code via -c BYTECODE, -a ADDRESS, -f BYTECODE_FILE or <SOLIDITY_FILE>",
        )
    return address


def print_function_report(myth_disassembler: MythrilDisassembler, report: Report):
    """
    Prints the function report
    :param report: Mythril's report
    :return:
    """
    contract_data = {}
    for contract in myth_disassembler.contracts:
        contract_data[contract.name] = list(
            set(contract.disassembly.address_to_function_name.values())
        )

    for issue in report.issues.values():
        if issue.function in contract_data[issue.contract]:
            contract_data[issue.contract].remove(issue.function)

    for contract, function_list in contract_data.items():
        print(f"Contract {contract}: \n")
        print(
            f"""{len(function_list)} functions are deemed safe in this contract: {", ".join(function_list)}\n\n"""
        )


def execute_command(
    disassembler: MythrilDisassembler,
    address: str,
    parser: ArgumentParser,
    args: Namespace,
):
    """
    根据参数命令执行
    Execute command
    :param disassembler:
    :param address:
    :param parser:
    :param args:
    :return:
    """
    # 是否指定了 beam_search 参数
    if getattr(args, "beam_search", None):
        strategy = f"beam-search: {args.beam_search}"
    else:
        # 默认dfs
        strategy = getattr(args, "strategy", "dfs")
    
    # 指定了读取存储槽命令
    if args.command == READ_STORAGE_COMNAND:
        storage = disassembler.get_state_variable_from_storage(
            address=address,
            params=[a.strip() for a in args.storage_slots.strip().split(",")],
        )
        print(storage)
    
    # 指定了反汇编命令,打印合约代码
    elif args.command in DISASSEMBLE_LIST:
        if disassembler.contracts[0].code:
            print("Runtime Disassembly: \n" + disassembler.contracts[0].get_easm())
        if disassembler.contracts[0].creation_code:
            print("Disassembly: \n" + disassembler.contracts[0].get_creation_easm())
    
    # 指定了安全函数（那些不会导致合约状态变更或资金损失的函数）命令，配置分析器并执行分析
    elif args.command == SAFE_FUNCTIONS_COMMAND:
        # 不从区块链上获取数据，仅使用本地数据进行分析
        # 禁用依赖剪枝，以保留更多可能的执行路径
        # 默认存储值设置为符号值，而不加载实际的链上存储数据
        args.no_onchain_data = args.disable_dependency_pruning = (
            args.unconstrained_storage
        ) = True
        # 每次执行时都进行可达性检查，以确保分析的准确性
        args.pruning_factor = 1
        # 创建一个 MythrilAnalyzer 对象，用于执行智能合约的分析
        function_analyzer = MythrilAnalyzer(
            strategy=strategy, disassembler=disassembler, address=address, cmd_args=args
        )
        try:
            # 执行分析
            report = function_analyzer.fire_lasers(
                # 指定要使用的检测模块
                modules=(
                    [m.strip() for m in args.modules.strip().split(",")]
                    if args.modules
                    else None
                ),
                # 仅分析单个交易
                transaction_count=1,
            )
            print_function_report(disassembler, report)
        except DetectorNotFoundError as e:
            exit_with_error("text", format(e))
        except CriticalError as e:
            exit_with_error("text", "Analysis error encountered: " + format(e))

    # 最主要部分，执行安全性分析
    elif args.command in ANALYZE_LIST + FOUNDRY_LIST:
        # 创建一个 MythrilAnalyzer 对象，用于执行智能合约的分析
        analyzer = MythrilAnalyzer(
            strategy=strategy, disassembler=disassembler, address=address, cmd_args=args
        )

        # 检查 disassembler.contracts 是否为空
        if not disassembler.contracts:
            exit_with_error(
                args.outform, "input files do not contain any valid contracts"
            )

        # 设置攻击者地址
        if args.attacker_address:
            try:
                ACTORS["ATTACKER"] = args.attacker_address
            except ValueError:
                exit_with_error(args.outform, "Attacker address is invalid")
        # 设置创建者地址
        if args.creator_address:
            try:
                ACTORS["CREATOR"] = args.creator_address
            except ValueError:
                exit_with_error(args.outform, "Creator address is invalid")

        # 生成控制流图
        if args.graph:
            html = analyzer.graph_html(
                contract=analyzer.contracts[0],
                enable_physics=args.enable_physics,
                phrackify=args.phrack,
                transaction_count=args.transaction_count,
            )

            try:
                with open(args.graph, "w") as f:
                    f.write(html)
            except Exception as e:
                exit_with_error(args.outform, "Error saving graph: " + str(e))

        # 生成状态空间 JSON
        elif args.statespace_json:
            if not analyzer.contracts:
                exit_with_error(
                    args.outform, "input files do not contain any valid contracts"
                )

            statespace = analyzer.dump_statespace(contract=analyzer.contracts[0])

            try:
                with open(args.statespace_json, "w") as f:
                    json.dump(statespace, f)
            except Exception as e:
                exit_with_error(args.outform, "Error saving json: " + str(e))

        else:
            try:
                report = analyzer.fire_lasers(
                    # 要使用的检测模块
                    modules=(
                        [m.strip() for m in args.modules.strip().split(",")]
                        if args.modules
                        else None
                    ),
                    # 要执行的交易数量
                    transaction_count=args.transaction_count,
                )

                outputs = {
                    "json": report.as_json(),
                    "jsonv2": report.as_swc_standard_format(),
                    "text": report.as_text(),
                    "markdown": report.as_markdown(),
                }
                print(outputs[args.outform])
                if len(report.issues) > 0:
                    exit(1)
                else:
                    exit(0)
            except DetectorNotFoundError as e:
                exit_with_error(args.outform, format(e))
            except CriticalError as e:
                exit_with_error(
                    args.outform, "Analysis error encountered: " + format(e)
                )

    else:
        parser.print_help()


def contract_hash_to_address(args: Namespace):
    """
    prints the hash from function signature
    :param args:
    :return:
    """
    print(MythrilDisassembler.hash_for_function_signature(args.func_name))
    sys.exit()


def parse_args_and_execute(parser: ArgumentParser, args: Namespace) -> None:
    """
    解析参数,并执行相应操作
    Parses the arguments
    :param parser: The parser
    :param args: The args
    """
    # 将当前命令行参数传递给epic.py
    if args.epic:
        path = os.path.dirname(os.path.realpath(__file__))
        sys.argv.remove("--epic")
        os.system(" ".join(sys.argv) + " | python3 " + path + "/epic.py")
        sys.exit()
    # 检查命令是否有效
    if args.command not in COMMAND_LIST or args.command is None:
        parser.print_help()
        sys.exit()
    # 版本
    if args.command == VERSION_COMMAND:
        if args.outform == "json":
            print(json.dumps({"version_str": VERSION}))
        else:
            print("Mythril version {}".format(VERSION))
        sys.exit()
    # list-detectors
    if args.command == LIST_DETECTORS_COMMAND:
        modules = []
        for module in ModuleLoader().get_detection_modules():
            modules.append({"classname": type(module).__name__, "title": module.name})
        if args.outform == "json":
            print(json.dumps(modules))
        else:
            for module_data in modules:
                print("{}: {}".format(module_data["classname"], module_data["title"]))
        sys.exit()
    # 帮助
    if args.command == HELP_COMMAND:
        parser.print_help()
        sys.exit()
    
    # 处理符号执行命令
    if args.command in CONCOLIC_LIST:
        _ = MythrilConfig.init_mythril_dir()
        with open(args.input) as f:
            concrete_data = json.load(f)
        # 执行
        output_list = concolic_execution(
            concrete_data, args.branches.split(","), args.solver_timeout
        )
        json.dump(output_list, sys.stdout, indent=4)
        sys.exit()

    # 处理常规命令
    # Parse cmdline args
    validate_args(args)
    try:
        # 指定了函数哈希命令
        if args.command == FUNCTION_TO_HASH_COMMAND:
            contract_hash_to_address(args)
        # 配置参数
        config = set_config(args)
        # 初始化反汇编器
        solc_json = getattr(args, "solc_json", None)
        solv = getattr(args, "solv", None)
        solc_args = getattr(args, "solc_args", None)
        # 
        disassembler = MythrilDisassembler(
            eth=config.eth,
            solc_version=solv,
            solc_settings_json=solc_json,
            solc_args=solc_args,
        )
        # 加载合约代码
        address = load_code(disassembler, args)
        # 执行命令
        execute_command(
            disassembler=disassembler, address=address, parser=parser, args=args
        )
    except CriticalError as ce:
        exit_with_error(getattr(args, "outform", "text"), str(ce))
    except Exception:
        exit_with_error(getattr(args, "outform", "text"), traceback.format_exc())


if __name__ == "__main__":
    main()
