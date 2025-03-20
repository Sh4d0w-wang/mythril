"""This module provides a basic RPC interface client.

This code is adapted from: https://github.com/ConsenSys/ethjsonrpc
"""

from abc import abstractmethod

from .constants import BLOCK_TAG_LATEST, BLOCK_TAGS
from .utils import hex_to_dec, validate_block

GETH_DEFAULT_RPC_PORT = 8545
ETH_DEFAULT_RPC_PORT = 8545
PARITY_DEFAULT_RPC_PORT = 8545
PYETHAPP_DEFAULT_RPC_PORT = 4000
MAX_RETRIES = 3
JSON_MEDIA_TYPE = "application/json"


class BaseClient(object):
    """
    基础RPC客户端;
    The base RPC client class.
    """

    @abstractmethod
    def _call(self, method, params=None, _id=1):
        """TODO: documentation

        :param method:
        :param params:
        :param _id:
        :return:
        """

        pass

    def eth_coinbase(self):
        """TODO: documentation
        获取当前以太坊节点的默认账户地址;
        https://github.com/ethereum/wiki/wiki/JSON-RPC#eth_coinbase

        TESTED
        """
        return self._call("eth_coinbase")

    def eth_blockNumber(self):
        """TODO: documentation
        获取当前以太坊节点的最新区块编号;
        https://github.com/ethereum/wiki/wiki/JSON-RPC#eth_blocknumber

        TESTED
        """
        return hex_to_dec(self._call("eth_blockNumber"))

    def eth_getBalance(self, address=None, block=BLOCK_TAG_LATEST):
        """TODO: documentation
        获取指定地址在指定区块高度的余额;
        https://github.com/ethereum/wiki/wiki/JSON-RPC#eth_getbalance

        TESTED
        """
        address = address or self.eth_coinbase()
        block = validate_block(block)
        return hex_to_dec(self._call("eth_getBalance", [address, block]))

    def eth_getStorageAt(self, address=None, position=0, block=BLOCK_TAG_LATEST):
        """TODO: documentation
        获取指定地址在指定存储位置和区块高度的存储值;
        https://github.com/ethereum/wiki/wiki/JSON-RPC#eth_getstorageat

        TESTED
        """
        block = validate_block(block)
        return self._call("eth_getStorageAt", [address, hex(position), block])

    def eth_getCode(self, address, default_block=BLOCK_TAG_LATEST):
        """TODO: documentation
        获取指定地址在指定区块高度的合约代码;
        https://github.com/ethereum/wiki/wiki/JSON-RPC#eth_getcode

        NEEDS TESTING
        """
        if isinstance(default_block, str):
            if default_block not in BLOCK_TAGS:
                raise ValueError
        return self._call("eth_getCode", [address, default_block])

    def eth_getBlockByNumber(self, block=BLOCK_TAG_LATEST, tx_objects=True):
        """TODO: documentation
        获取指定区块编号的区块信息;
        https://github.com/ethereum/wiki/wiki/JSON-RPC#eth_getblockbynumber

        TESTED
        """
        block = validate_block(block)
        return self._call("eth_getBlockByNumber", [block, tx_objects])

    def eth_getTransactionReceipt(self, tx_hash):
        """TODO: documentation
        获取指定交易哈希的交易收据;
        https://github.com/ethereum/wiki/wiki/JSON-RPC#eth_gettransactionreceipt

        TESTED
        """
        return self._call("eth_getTransactionReceipt", [tx_hash])
