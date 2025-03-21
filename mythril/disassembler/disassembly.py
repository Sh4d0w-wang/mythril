"""This module contains the class used to represent disassembly code."""

from typing import Dict, List, Tuple

from mythril.disassembler import asm
from mythril.ethereum import util
from mythril.support.signatures import SignatureDB


class Disassembly(object):
    """
    表示 EVM 字节码的反汇编代码的类;

    Disassembly class.

    Stores bytecode, and its disassembly.
    Additionally it will gather the following information on the existing functions in the disassembled code:
    - function hashes
    - function name to entry point mapping
    - function entry point to function name mapping
    """

    def __init__(self, code: str) -> None:
        """

        :param code:
        """
        # 字节码
        self.bytecode = code
        # 指令
        if isinstance(code, str):
            self.instruction_list = asm.disassemble(util.safe_decode(code))
        else:
            self.instruction_list = asm.disassemble(code)
        # 函数哈希
        self.func_hashes: List[str] = []
        # 函数名称到入口点地址的映射
        self.function_name_to_address: Dict[str, int] = {}
        # 入口点到函数名称的映射
        self.address_to_function_name: Dict[int, str] = {}
        # 进一步分析字节码
        self.assign_bytecode(bytecode=code)

    def assign_bytecode(self, bytecode):
        """
        从字节码中提取函数哈希、入口点和函数名称
        """
        self.bytecode = bytecode

        # open from default locations
        # control if you want to have online signature hash lookups
        # 创建一个 SignatureDB 对象，用于将函数哈希映射到函数名称
        signatures = SignatureDB()

        # 反汇编字节码
        self.instruction_list = asm.disassemble(bytecode)

        # Need to take from PUSH1 to PUSH4 because solc seems to remove excess 0s at the beginning for optimizing
        # 查找函数跳转表的入口
        # 函数跳转表通常由 PUSH 指令和 EQ 指令组成，用于跳转到不同的函数入口点
        # PUSH1 到 PUSH4 是因为 Solidity 编译器可能会优化掉前导的零字节，因此需要考虑不同长度的 PUSH 指令
        jump_table_indices = asm.find_op_code_sequence(
            [("PUSH1", "PUSH2", "PUSH3", "PUSH4"), ("EQ",)], self.instruction_list
        )

        # 提取函数信息
        for index in jump_table_indices:
            function_hash, jump_target, function_name = get_function_info(
                index, self.instruction_list, signatures
            )
            self.func_hashes.append(function_hash)
            if jump_target is not None and function_name is not None:
                self.function_name_to_address[function_name] = jump_target
                self.address_to_function_name[jump_target] = function_name

    def get_easm(self):
        """
        返回汇编指令列表字符串;
        :return:
        """
        return asm.instruction_list_to_easm(self.instruction_list)


def get_function_info(
    index: int, instruction_list: list, signature_database: SignatureDB
) -> Tuple[str, int, str]:
    """
    提取函数信息

    Finds the function information for a call table entry Solidity uses the
    first 4 bytes of the calldata to indicate which function the message call
    should execute The generated code that directs execution to the correct
    function looks like this:

    - PUSH function_hash
    - EQ
    - PUSH entry_point
    - JUMPI

    This function takes an index that points to the first instruction, and from that finds out the function hash,
    function entry and the function name.

    :param index: Start of the entry pattern
    :param instruction_list: Instruction list for the contract that is being analyzed
    :param signature_database: Database used to map function hashes to their respective function names
    :return: function hash, function entry point, function name
    """

    # Append with missing 0s at the beginning
    # 1. 提取函数哈希
    if isinstance(instruction_list[index]["argument"], tuple):
        try:
            # 转成字节序列并提取hex，前4字节
            function_hash = "0x" + bytes(
                instruction_list[index]["argument"]
            ).hex().rjust(8, "0")
        except AttributeError:
            raise ValueError(
                "Mythril currently does not support symbolic function signatures"
            )
    else:
        function_hash = "0x" + instruction_list[index]["argument"][2:].rjust(8, "0")

    # 2. 查找函数名称
    function_names = signature_database.get(function_hash)

    # 若有多个名称
    if len(function_names) > 0:
        function_name = " or ".join(set(function_names))
    else:
        # 未找到名称，则_function_<function_hash>
        function_name = "_function_" + function_hash

    # 3. 提取函数入口点
    try:
        # 提取 PUSH 指令后的 JUMPI 指令的目标地址
        offset = instruction_list[index + 2]["argument"]
        if isinstance(offset, tuple):
            offset = bytes(offset).hex()
        # 将十六进制字符串转换为整数
        entry_point = int(offset, 16)
    except (KeyError, IndexError):
        return function_hash, None, None

    return function_hash, entry_point, function_name
