"""This module contains the dynamic loader logic to get on-chain storage data
and dependencies."""

import functools
import logging
import re
from typing import Optional

from mythril.disassembler.disassembly import Disassembly
from mythril.ethereum.interface.rpc.client import EthJsonRpc

LRU_CACHE_SIZE = 4096

log = logging.getLogger(__name__)


class DynLoader:
    """
    动态加载以太坊链上的存储数据和依赖项
    
    The dynamic loader class.
    """

    def __init__(self, eth: Optional[EthJsonRpc], active=True):
        """
        初始化动态加载器

        :param eth: EthJsonRpc 对象，用于与以太坊节点交互
        :param active: 表示动态加载器是否启用
        """
        self.eth = eth
        self.active = active

    @functools.lru_cache(LRU_CACHE_SIZE)
    def read_storage(self, contract_address: str, index: int) -> str:
        """
        从链上读取存储值(合约地址,索引)

        :param contract_address: 
        :param index:
        :return:
        """
        if not self.active:
            raise ValueError("Loader is disabled")
        if not self.eth:
            raise ValueError("Cannot load from the storage when eth is None")

        value = self.eth.eth_getStorageAt(
            contract_address, position=index, block="latest"
        )
        # 如果返回值以 0x 开头，返回一个默认值
        if value.startswith("0x"):
            value = "0x0000000000000000000000000000000000000000000000000000000000000000"
        return value

    @functools.lru_cache(LRU_CACHE_SIZE)
    def read_balance(self, address: str) -> str:
        """
        读取账户余额(地址)

        :param address:
        :return:
        """
        if not self.active:
            raise ValueError("Cannot load from storage when the loader is disabled")
        if not self.eth:
            raise ValueError(
                "Cannot load from the chain when eth is None, please use rpc, or specify infura-id"
            )

        return self.eth.eth_getBalance(address)

    @functools.lru_cache(LRU_CACHE_SIZE)
    def dynld(self, dependency_address: str) -> Optional[Disassembly]:
        """
        动态加载合约代码

        :param dependency_address:
        :return:
        """
        if not self.active:
            raise ValueError("Loader is disabled")
        if not self.eth:
            raise ValueError(
                "Cannot load from the chain when eth is None, please use rpc, or specify infura-id"
            )

        log.debug("Dynld at contract %s", dependency_address)

        # Ensure that dependency_address is the correct length, with 0s prepended as needed.
        # 确保合约地址格式正确,不足用0替代
        if isinstance(dependency_address, int):
            dependency_address = "0x{:040X}".format(dependency_address)
        else:
            dependency_address = (
                "0x" + "0" * (42 - len(dependency_address)) + dependency_address[2:]
            )
        # 验证和格式化合约地址
        m = re.match(r"^(0x[0-9a-fA-F]{40})$", dependency_address)
        if m:
            dependency_address = m.group(1)
        else:
            return None

        log.debug("Dependency address: %s", dependency_address)
        # 读取合约代码
        code = self.eth.eth_getCode(dependency_address)
        # 如果返回的代码以 0x 开头，返回 None
        if code.startswith("0x"):
            return None
        else:
            # 返回反汇编
            return Disassembly(code)
