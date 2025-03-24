"""This module contains the class representing EVM contracts, aka Smart
Contracts."""

import logging
import re

import persistent

from mythril.disassembler.disassembly import Disassembly
from mythril.support.support_utils import get_code_hash, sha3

log = logging.getLogger(__name__)


class EVMContract(persistent.Persistent):
    """
    表示一个智能合约，包含合约的代码、创建代码、名称以及反汇编信息;
    继承自 persistent.Persistent,这使得合约对象可以被持久化存储;
    This class represents an address with associated code (Smart
    Contract).
    """

    def __init__(self, code="", creation_code="", name="Unknown"):
        """
        创建一个合约对象,包含合约的代码、创建代码、名称以及反汇编信息

        Create a new contract.

        Workaround: We currently do not support compile-time linking.
        Dynamic contract addresses of the format __[contract-name]_____________ are replaced with a generic address
        Apply this for creation_code & code

        :param code:
        :param creation_code:
        :param name:
        """
        # creation_code = "0x...__MyContractAddress__..."
        # code = "0x...__MyContractAddress__..."
        # -->
        # creation_code = "0x...aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa..."
        # code = "0x...aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa..."
        # 将动态地址换成通用地址
        creation_code = re.sub(r"(_{2}.{38})", "aa" * 20, creation_code)
        code = re.sub(r"(_{2}.{38})", "aa" * 20, code)
        # 创建字节码
        self.creation_code = creation_code
        self.name = name
        # 运行时字节码
        self.code = code
        # 运行时字节码反汇编
        self.disassembly = Disassembly(code)
        # 创建时字节码反汇编
        self.creation_disassembly = Disassembly(creation_code)

    @property
    def bytecode_hash(self):
        """
        属性,运行时字节码哈希;
        :return: runtime bytecode hash
        """
        return get_code_hash(self.code)

    @property
    def creation_bytecode_hash(self):
        """
        属性,创建时字节码哈希;
        :return: Creation bytecode hash
        """
        return get_code_hash(self.creation_code)

    def as_dict(self):
        """
        将合约对象转为字典格式;
        :return:
        """
        return {
            "name": self.name,
            "code": self.code,
            "creation_code": self.creation_code,
            "disassembly": self.disassembly,
        }

    def get_easm(self):
        """
        返回运行时字节码反汇编;
        :return:
        """
        return self.disassembly.get_easm()

    def get_creation_easm(self):
        """
        返回创建时字节码反汇编;
        :return:
        """
        return self.creation_disassembly.get_easm()

    def matches_expression(self, expression):
        """
        正则匹配代码中的表达式;
        :param expression:
        :return:
        """
        # 最终的匹配字符串
        str_eval = ""
        easm_code = None
        # contract.matches_expression("code#PUSH1# or code#PUSH1#"),
        # contract.matches_expression("func#abcdef#"),
        tokens = re.split(r"\s+(and|or|not)\s+", expression, re.IGNORECASE)

        for token in tokens:
            # 构建匹配字符串
            if token in ("and", "or", "not"):
                str_eval += " " + token + " "
                continue
            # 使用正则表达式匹配 code#[EASM_CODE]# 模式
            m = re.match(r"^code#([a-zA-Z0-9\s,\[\]]+)#", token)

            if m:
                if easm_code is None:
                    easm_code = self.get_easm()

                code = m.group(1).replace(",", "\\n")
                str_eval += '"' + code + '" in easm_code'
                continue
            # 使用正则表达式匹配 func#[FUNCTION_SIGNATURE]# 模式
            m = re.match(r"^func#([a-zA-Z0-9\s_,(\\)\[\]]+)#$", token)

            if m:
                sign_hash = "0x" + sha3(m.group(1))[:4].hex()
                str_eval += '"' + sign_hash + '" in self.disassembly.func_hashes'

        return eval(str_eval.strip())
