"""This module contains account-related functionality.

This includes classes representing accounts and their storage.
"""

import logging
from copy import copy, deepcopy
from typing import Any, Dict, Set, Union

from mythril.disassembler.disassembly import Disassembly
from mythril.laser.smt import Array, BaseArray, BitVec, If, K, simplify, symbol_factory
from mythril.laser.smt import SMTBool as Bool
from mythril.support.support_args import args

log = logging.getLogger(__name__)


class Storage:
    """
    以太坊账户的存储类,支持符号执行和动态加载存储值

    Storage class represents the storage of an Account.
    """

    def __init__(self, concrete=False, address=None, dynamic_loader=None) -> None:
        """
        初始化一个Storage

        Constructor for Storage.

        :param concrete: bool indicating whether to interpret uninitialized storage as concrete versus symbolic
        """
        # 表示整个Storage
        # concrete：表示是否将未初始化的存储解释为具体值
        if concrete and args.unconstrained_storage is False:
            # 初始化一个具体的Storage数组，默认值为0
            self._standard_storage: BaseArray = K(256, 256, 0)
        else:
            # 初始化一个符号Storage数组，名称为 Storage{address}
            self._standard_storage = Array(f"Storage{address}", 256, 256)

        # 存储可打印的Storage值
        self.printable_storage: Dict[BitVec, BitVec] = {}
        # 动态加载器，用于从链上加载Storage值
        self.dynld = dynamic_loader
        # 存储已经从链上加载的Storage键
        self.storage_keys_loaded: Set[int] = set()
        # 账户地址
        self.address = address

        # Stores all keys set in the storage
        # 存储所有在Storage中设置的键
        self.keys_set: Set[BitVec] = set()

        # Stores all get keys in the storage
        # 存储所有从Storage中获取的键
        self.keys_get: Set[BitVec] = set()

    def __getitem__(self, item: BitVec) -> BitVec:
        """
        获取Storage中的值,优先返回已经设置的值
        """
        storage = self._standard_storage
        # 添加记录
        self.keys_get.add(item)
        if (
            self.address
            and self.address.value != 0
            and item.symbolic is False # 键是具体的值，而不是符号值
            and int(item.value) not in self.storage_keys_loaded # 键尚未从链上加载
            and (self.dynld and self.dynld.active) # 动态加载器已启用
            and args.unconstrained_storage is False # 未启用无约束存储
        ):
            try:
                # 将整数转为256为的BitVec
                value = symbol_factory.BitVecVal(
                    # 将读取的的hex转为整数
                    int(
                        # read_storage(合约地址,索引)
                        self.dynld.read_storage(
                            contract_address="0x{:040X}".format(self.address.value),
                            index=int(item.value),
                        ),
                        16,
                    ),
                    256,
                )
                # 确保优先使用已经设置的值
                # 遍历 已经设置的所有键 中的每个键 key
                for key in self.keys_set:
                    # key == item --> 检查当前键 key 是否等于要获取的键 item
                    # storage[item] --> 如果 key == item 为 True，则返回存储中对应键 item 的值
                    # value --> 如果 key == item 为 False，则返回之前加载的值 value
                    value = If(key == item, storage[item], value)

                # 更新Storage
                storage[item] = value
                # 表示该键已经从链上加载
                self.storage_keys_loaded.add(int(item.value))
                self.printable_storage[item] = storage[item]
            except ValueError as e:
                log.debug("Couldn't read storage at %s: %s", item, e)

        return simplify(storage[item])

    def __setitem__(self, key, value: Any) -> None:
        """
        设置Storage值
        """
        # bool值的话，设为1或0
        if isinstance(value, Bool):
            value = If(value, 1, 0)
        # 设置值
        self.printable_storage[key] = value
        self._standard_storage[key] = value
        # 添加记录
        self.keys_set.add(key)
        # 不是符号，则添加到 已经从链上加载的Storage键 集合中
        if key.symbolic is False:
            self.storage_keys_loaded.add(int(key.value))

    def __deepcopy__(self, memodict=dict()):
        """
        Storage 的深拷贝功能，确保所有属性被正确复制
        """
        # 是否是符号
        concrete = isinstance(self._standard_storage, K)
        # 创建一个新Storage
        storage = Storage(
            concrete=concrete, address=self.address, dynamic_loader=self.dynld
        )
        # 拷贝
        storage._standard_storage = deepcopy(self._standard_storage)
        storage.printable_storage = copy(self.printable_storage)
        storage.storage_keys_loaded = copy(self.storage_keys_loaded)
        storage.keys_set = deepcopy(self.keys_set)
        storage.keys_get = deepcopy(self.keys_get)
        return storage

    def __str__(self) -> str:
        """
        返回存储的字符串表示
        """
        # TODO: Do something better here
        return str(self.printable_storage)


class Account:
    """
    以太坊账户类

    Account class representing ethereum accounts.
    """

    def __init__(
        self,
        address: Union[BitVec, str],
        code=None,
        contract_name=None,
        balances: Array = None,
        concrete_storage=False,
        dynamic_loader=None,
        nonce=0,
    ) -> None:
        """
        初始化账户

        Constructor for account.

        :param address: Address of the account
        :param code: The contract code of the account
        :param contract_name: The name associated with the account
        :param balances: The balance for the account
        :param concrete_storage: Interpret storage as concrete
        """
        # 是否将Storage解释为具体值
        self.concrete_storage = concrete_storage
        # 账户发起的交易数量
        self.nonce = nonce
        # 合约反汇编
        self.code = code or Disassembly("")
        # 地址，转换为 BitVec
        self.address = (
            address
            if isinstance(address, BitVec)
            else symbol_factory.BitVecVal(int(address, 16), 256)
        )
        # 账户的Storage
        self.storage = Storage(
            concrete_storage, address=self.address, dynamic_loader=dynamic_loader
        )

        # Metadata
        # 账户的合约名称，如果未提供，则根据地址生成默认名称
        if contract_name is None:
            self.contract_name = (
                "{0:#0{1}x}".format(self.address.value, 42)
                if not self.address.symbolic
                else "unknown"
            )
        else:
            self.contract_name = contract_name
        
        # 账户是否被删除
        self.deleted = False
        # 内部余额数组，用于存储所有账户的余额
        self._balances = balances
        # 账户余额
        self.balance = lambda: self._balances[self.address]

    def __str__(self) -> str:
        """
        返回账户的字符串表示
        """
        return str(self.as_dict)

    def set_balance(self, balance: Union[int, BitVec]) -> None:
        """
        设置余额

        :param balance:
        """
        # 转符号
        balance = (
            symbol_factory.BitVecVal(balance, 256)
            if isinstance(balance, int)
            else balance
        )
        assert self._balances is not None
        # 设置余额
        self._balances[self.address] = balance

    def set_storage(self, storage: Dict):
        """
        设置Storage

        Sets concrete storage
        """
        # 均转符号
        for key, value in storage.items():
            concrete_key, concrete_value = int(key, 16), int(value, 16)
            self.storage[symbol_factory.BitVecVal(concrete_key, 256)] = (
                symbol_factory.BitVecVal(concrete_value, 256)
            )

    def add_balance(self, balance: Union[int, BitVec]) -> None:
        """
        增加余额

        :param balance:
        """
        # 转符号
        balance = (
            symbol_factory.BitVecVal(balance, 256)
            if isinstance(balance, int)
            else balance
        )
        # 增加余额
        self._balances[self.address] += balance

    @property
    def as_dict(self) -> Dict:
        """
        返回账户的字典表示

        :return:
        """
        return {
            "nonce": self.nonce,
            "code": self.serialised_code(),
            "balance": self.balance(),
            "storage": self.storage,
        }

    def serialised_code(self):
        """
        返回账户的序列化代码
        """
        if isinstance(self.code.bytecode, str):
            return self.code.bytecode
        new_code = "0x"
        for byte in self.code.bytecode:
            # 如果字节是整数类型，将其转换为十六进制字符串并附加到 new_code
            if isinstance(byte, int):
                new_code += hex(byte)
            # 如果字节不是整数类型，假设它是动态数据（如调用数据），附加 <call_data> 到 new_code
            else:
                new_code += "<call_data>"
        return new_code

    def __copy__(self, memodict={}):
        """
        拷贝账户
        """
        new_account = Account(
            address=self.address,
            code=self.code,
            contract_name=self.contract_name,
            balances=deepcopy(self._balances),
            concrete_storage=self.concrete_storage,
            nonce=self.nonce,
        )
        new_account.storage = deepcopy(self.storage)
        new_account.code = self.code
        return new_account
