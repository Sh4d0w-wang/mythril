"""This module contains various helper classes and functions to deal with EVM
code disassembly."""

import re

try:
    from collections.abc import Generator
except ImportError:
    from collections import Generator

from functools import lru_cache

from mythril.ethereum import util
from mythril.support.opcodes import ADDRESS, ADDRESS_OPCODE_MAPPING, OPCODES

regex_PUSH = re.compile(r"^PUSH(\d*)$")


class EvmInstruction:
    """
    EVM指令信息模块;

    Model to hold the information of the disassembly.
    """

    def __init__(self, address, op_code, argument=None):
        # 表示一个 EVM 指令，包含指令的地址、操作码和参数
        self.address = address
        self.op_code = op_code
        self.argument = argument

    def to_dict(self) -> dict:
        """
        指令信息转换为字典格式;

        :return:
        """
        result = {"address": self.address, "opcode": self.op_code}
        if self.argument:
            result["argument"] = self.argument
        return result


def instruction_list_to_easm(instruction_list: list) -> str:
    """
    指令列表转换为 EASM格式的字符串 --> "0 PUSH1 0x1";

    Convert a list of instructions into an easm op code string.
    :param instruction_list:
    :return:
    """
    result = ""
    # {"address": 0, "opcode": "PUSH1", "argument": "0x1"},
    # 0 PUSH1 0x1
    for instruction in instruction_list:
        result += "{} {}".format(instruction["address"], instruction["opcode"])
        if "argument" in instruction:
            result += " " + instruction["argument"]
        result += "\n"

    return result


def get_opcode_from_name(operation_name: str) -> int:
    """
    按照指令名字返回其字节码 --> "PUSH1" --> "0x60";

    Get an op code based on its name.
    :param operation_name:
    :return:
    """
    if operation_name in OPCODES:
        return OPCODES[operation_name][ADDRESS]
    raise RuntimeError("Unknown opcode")


def find_op_code_sequence(pattern: list, instruction_list: list) -> Generator:
    """
    查找指令列表中符合特定模式的指令序列;

    Returns all indices in instruction_list that point to instruction
    sequences following a pattern.

    :param pattern: The pattern to look for, e.g. [["PUSH1", "PUSH2"], ["EQ"]] where ["PUSH1", "EQ"] satisfies pattern
    :param instruction_list: List of instructions to look in
    :return: Indices to the instruction sequences
    """
    for i in range(0, len(instruction_list) - len(pattern) + 1):
        if is_sequence_match(pattern, instruction_list, i):
            yield i


def is_sequence_match(pattern: list, instruction_list: list, index: int) -> bool:
    """
    从指定索引开始的指令序列是否符合特定模式;

    Checks if the instructions starting at index follow a pattern.

    :param pattern: List of lists describing a pattern, e.g. [["PUSH1", "PUSH2"], ["EQ"]] where ["PUSH1", "EQ"] satisfies pattern
    :param instruction_list: List of instructions
    :param index: Index to check for
    :return: Pattern matched
    """
    for index, pattern_slot in enumerate(pattern, start=index):
        try:
            if not instruction_list[index]["opcode"] in pattern_slot:
                return False
        except IndexError:
            return False
    return True


lru_cache(maxsize=2**10)


def disassemble(bytecode) -> list:
    """
    反汇编字节码,返回指令列表;

    Disassembles evm bytecode and returns a list of instructions.

    :param bytecode:
    :return:
    """
    instruction_list = []
    address = 0
    length = len(bytecode)

    # 将字节码转为bytes
    # 提取最后43个字节，用于后续检查是否包含Swarm哈希
    if isinstance(bytecode, str):
        bytecode = util.safe_decode(bytecode)
        length = len(bytecode)
        part_code = bytecode[-43:]
    else:
        try:
            part_code = bytes(bytecode[-43:])
        except TypeError:
            part_code = ""
    try:
        # 忽略Swarm 哈希
        if "bzzr" in str(part_code):
            # ignore swarm hash
            length -= 43
    except ValueError:
        pass
    
    # 反汇编
    while address < length:
        try:
            # 查找当前指令字节码
            op_code = ADDRESS_OPCODE_MAPPING[bytecode[address]]
        except KeyError:
            # 不在指令表中将其标记为"INVALID"后往下处理下一个字节
            instruction_list.append(EvmInstruction(address, "INVALID"))
            address += 1
            continue
        
        # 当前指令对象
        current_instruction = EvmInstruction(address, op_code)

        # 处理PUSH指令
        match = re.search(regex_PUSH, op_code)
        if match:
            # 提取参数
            # [address + 1 : address + 1 + n]
            argument_bytes = bytecode[address + 1 : address + 1 + int(match.group(1))]
            if isinstance(argument_bytes, bytes):
                current_instruction.argument = "0x" + argument_bytes.hex()
            else:
                current_instruction.argument = argument_bytes
            address += int(match.group(1))

        instruction_list.append(current_instruction)
        address += 1

    # We use a to_dict() here for compatibility reasons
    return [element.to_dict() for element in instruction_list]
