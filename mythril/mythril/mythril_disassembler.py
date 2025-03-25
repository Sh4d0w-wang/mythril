import json
import logging
import os
import re
import shutil
import subprocess
import warnings
from pathlib import Path
from typing import List, Optional, Tuple

import solc
from eth_utils import int_to_big_endian
from semantic_version import NpmSpec, Version

from mythril.ethereum import util
from mythril.ethereum.evmcontract import EVMContract
from mythril.ethereum.interface.rpc.client import EthJsonRpc
from mythril.ethereum.interface.rpc.exceptions import ConnectionError
from mythril.exceptions import CompilerError, CriticalError, NoContractFoundError
from mythril.solidity.soliditycontract import (
    SolidityContract,
    get_contracts_from_file,
    get_contracts_from_foundry,
)
from mythril.support import signatures
from mythril.support.support_args import args
from mythril.support.support_utils import rzpad, sha3, zpad


def format_warning(message, category, filename, lineno, line=""):
    return "{}: {}\n\n".format(str(filename), str(message))


warnings.formatwarning = format_warning


log = logging.getLogger(__name__)


class MythrilDisassembler:
    """
    生成反汇编代码,编译solidity代码,提供访问链上存储数据功能;

    The Mythril Disassembler class
    Responsible for generating disassembly of smart contracts:
        - Compiles solc code from file/onchain
        - Can also be used to access onchain storage data
    """

    def __init__(
        self,
        # 一个 EthJsonRpc 对象，用于与以太坊节点进行交互
        eth: Optional[EthJsonRpc] = None,
        # Solidity 编译器版本
        solc_version: str = None,
        # Solidity 编译器的设置
        solc_settings_json: str = None,
        # Solidity 编译器的其他参数
        solc_args=None,
    ) -> None:
        args.solc_args = solc_args
        self.solc_version = solc_version
        # 初始化 Solidity 编译器的二进制路径
        self.solc_binary = self._init_solc_binary(solc_version)
        self.solc_settings_json = solc_settings_json
        # EthJsonRpc
        self.eth = eth
        # 创建一个 SignatureDB 对象，用于管理函数签名
        self.sigs = signatures.SignatureDB()
        # 初始化 contracts 属性，表示一个空的智能合约列表
        self.contracts: List[EVMContract] = []

    @staticmethod
    def _init_solc_binary(version: str) -> Optional[str]:
        """
        初始化sloidity编译器二进制文件

        Only proper versions are supported. No nightlies, commits etc (such as available in remix).
        This functions extracts
        :param version: Version of the solc binary required
        :return: AThe solc binary of the corresponding version
        """
        if not version:
            return None

        # tried converting input to semver, seemed not necessary so just slicing for now
        try:
            # 获取已安装的 Solidity 编译器版本
            main_version = solc.get_solc_version_string()
        except:
            main_version = ""  # allow missing solc will download instead
        main_version_number = re.search(r"\d+.\d+.\d+", main_version)
        # 如果版本字符串以 v 开头，去掉前缀 v
        if version.startswith("v"):
            version = version[1:]
        # 如果指定的版本与已安装的版本匹配，使用环境变量 SOLC 或默认值 "solc"
        if version == main_version_number:
            log.info("Given version matches installed version")
            solc_binary = os.environ.get("SOLC") or "solc"
        else:
            # 如果版本不匹配，尝试查找指定版本的 Solidity 编译器
            solc_binary = util.solc_exists(version)
            if solc_binary is None:
                raise CriticalError(
                    "The version of solc that is needed cannot be installed automatically"
                )
            else:
                log.info("Setting the compiler to %s", solc_binary)

        return solc_binary

    def load_from_bytecode(
        self, code: str, bin_runtime: bool = False, address: Optional[str] = None
    ) -> Tuple[str, EVMContract]:
        """
        从字节码中返回合约的地址和合约对象(包含反汇编)

        Returns the address and the contract class for the given bytecode
        :param code: Bytecode
        :param bin_runtime: Whether the code is runtime code or creation code
        :param address: address of contract
        :return: tuple(address, Contract class)
        """
        # 地址未提供，则生成全0地址
        if address is None:
            address = util.get_indexed_address(0)

        # 运行时字节码 True
        if bin_runtime:
            self.contracts.append(
                EVMContract(
                    code=code,
                    name="MAIN",
                )
            )
        # 创建时字节码 False
        else:
            self.contracts.append(
                EVMContract(
                    creation_code=code,
                    name="MAIN",
                )
            )
        return address, self.contracts[-1]  # return address and contract object

    def load_from_address(self, address: str) -> Tuple[str, EVMContract]:
        """
        从地址中加载合约,并返回合约的地址和合约对象(包含反汇编)

        Returns the contract given it's on chain address
        :param address: The on chain address of a contract
        :return: tuple(address, contract)
        """
        if not re.match(r"0x[a-fA-F0-9]{40}", address):
            raise CriticalError("Invalid contract address. Expected format is '0x...'.")

        # 检查RPC是否配置正确
        if self.eth is None:
            raise CriticalError(
                "Please check whether the Infura key is set or use a different RPC method."
            )

        try:
            # 获取字节码
            code = self.eth.eth_getCode(address)
        except FileNotFoundError as e:
            raise CriticalError("IPC error: " + str(e))
        except ConnectionError:
            raise CriticalError(
                "Could not connect to RPC server. Make sure that your node is running and that RPC parameters are set correctly."
            )
        except Exception as e:
            raise CriticalError("IPC / RPC error: " + str(e))

        # 合约地址无效或节点未正确连接到目标链
        if code == "0x" or code == "0x0":
            raise CriticalError(
                "Received an empty response from eth_getCode. Check the contract address and verify that you are on the correct chain."
            )
        else:
            self.contracts.append(EVMContract(code, name=address))
        # 返回地址和合约对象
        return address, self.contracts[-1]  # return address and contract object

    def load_from_foundry(self):
        """
        从 Foundry 中加载合约
        """
        project_root = os.getcwd()
        # 编译合约，生成编译信息
        cmd = ["forge", "build", "--build-info", "--force"]
        # 
        with subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=project_root,
            executable=shutil.which(cmd[0]),
        ) as p:
            stdout, stderr = p.communicate()
            stdout, stderr = (stdout.decode(), stderr.decode())
            if stderr:
                log.error(stderr)

            build_dir = Path(project_root, "artifacts", "contracts", "build-info")
        # 确定生成目录
        build_dir = os.path.join(project_root, "artifacts", "contracts", "build-info")
        # 生成全0地址
        address = util.get_indexed_address(0)
        # 列出生成目录中的文件
        files = sorted(
            os.listdir(build_dir), key=lambda x: os.path.getmtime(Path(build_dir, x))
        )
        # 找到.json文件
        files = [str(f) for f in files if str(f).endswith(".json")]
        if not files:
            txt = f"`compile` failed. Can you run it?\n{build_dir} is empty"
            raise Exception(txt)
        contracts = []
        for file in files:
            build_info = Path(build_dir, file)
            # 打开文件
            with open(build_info, encoding="utf8") as file_desc:
                loaded_json = json.load(file_desc)
                # 提取output和input部分
                targets_json = loaded_json["output"]
                input_json = loaded_json["input"]

                compiler = "solc" if input_json["language"] == "Solidity" else "vyper"

                if compiler == "vyper":
                    raise NotImplementedError("Support for Vyper is not implemented.")
                
                # 提取contracts
                if "contracts" in targets_json:
                    for original_filename, contracts_info in targets_json[
                        "contracts"
                    ].items():
                        for contract in get_contracts_from_foundry(
                            original_filename, targets_json
                        ):
                            self.contracts.append(contract)
                            contracts.append(contract)
                            self.sigs.add_sigs(original_filename, targets_json)
        return address, contracts

    def check_run_integer_module(self, source_file):
        """
        检查是否需要运行检测整数溢出的模块
        """
        # 检查文件内容是否包含"unchecked"
        with open(source_file, "r") as f:
            for line in f:
                if "unchecked" in line:
                    return True
        
        # 大于0.8.0的版本，编译器会自动为算术运算添加溢出检查
        if self.solc_version is None:
            # Runs the version installed in the system (likely 0.8.0+)
            # Post 0.8.0 versions automatically add assertions to sanity check arithmetic
            return False
        # Strip leading 'v' from version if it's there
        normalized_version = self.solc_version.lstrip("v")
        # Check if solc_version is not provided or doesn't match the required version
        # As post 0.8.0 solc versions automatically add assertions to sanity check arithmetic
        # 版本为空或者不符合^0.8.0 的要求则要运行检测模块
        if not self.solc_version or not NpmSpec("^0.8.0").match(
            Version(normalized_version)
        ):
            return True

        return False

    def load_from_solidity(
        self, solidity_files: List[str]
    ) -> Tuple[str, List[SolidityContract]]:
        """
        从 Solidity 源代码文件中加载合约,创建合约对象,其中包含源码文件索引、json数据、文件路径、ast特征、源码映射及其中的反汇编等信息

        :param solidity_files: List of solidity_files
        :return: tuple of address, contract class list
        """
        address = util.get_indexed_address(0)
        contracts = []
        for file in solidity_files:
            # 如果文件路径包含合约名称（格式为 "file.sol:ContractName"），则提取文件路径和合约名称
            if ":" in file:
                file, contract_name = file.split(":")
            else:
                contract_name = None
            
            # 获取编译器路径、版本
            file = os.path.expanduser(file)
            solc_binary = self.solc_binary
            if solc_binary is None:
                solc_binary, self.solc_version = util.extract_binary(file)
            # 检查是否需要运行检测溢出的模块
            if self.check_run_integer_module(file) is False:
                args.use_integer_module = False
            try:
                # import signatures from solidity source
                # 导入签名
                self.sigs.import_solidity_file(
                    file,
                    solc_binary=solc_binary,
                    solc_settings_json=self.solc_settings_json,
                )
                # 创建合约对象
                if contract_name is not None:
                    contract = SolidityContract(
                        input_file=file,
                        name=contract_name,
                        solc_settings_json=self.solc_settings_json,
                        solc_binary=solc_binary,
                    )
                    self.contracts.append(contract)
                    contracts.append(contract)
                else:
                    for contract in get_contracts_from_file(
                        input_file=file,
                        solc_settings_json=self.solc_settings_json,
                        solc_binary=solc_binary,
                    ):
                        self.contracts.append(contract)
                        contracts.append(contract)

            except FileNotFoundError as e:
                raise CriticalError(f"Input file not found {e}")
            except CompilerError as e:
                error_msg = str(e)
                # Check if error is related to solidity version mismatch
                if (
                    "Error: Source file requires different compiler version"
                    in error_msg
                ):
                    # Grab relevant line "pragma solidity <solv>...", excluding any comments
                    solv_pragma_line = error_msg.split("\n")[-3].split("//")[0]
                    # Grab solidity version from relevant line
                    solv_match = re.findall(r"[0-9]+\.[0-9]+\.[0-9]+", solv_pragma_line)
                    error_suggestion = (
                        "<version_number>" if len(solv_match) != 1 else solv_match[0]
                    )
                    error_msg = (
                        error_msg
                        + '\nSolidityVersionMismatch: Try adding the option "--solv '
                        + error_suggestion
                        + '"\n'
                    )

                raise CriticalError(error_msg)
            except NoContractFoundError:
                log.error(
                    "The file " + file + " does not contain a compilable contract."
                )

        return address, contracts

    @staticmethod
    def hash_for_function_signature(func: str) -> str:
        """
        返回函数选择器

        Return function nadmes corresponding signature hash
        :param func: function name
        :return: Its hash signature
        """
        return "0x%s" % sha3(func)[:4].hex()

    def get_state_variable_from_storage(
        self, address: str, params: Optional[List[str]] = None
    ) -> str:
        """
        从slot中获取状态变量的值,参数可以是:

        [position, length]：表示从指定位置开始的连续存储槽。

        ["mapping", position, key1, key2, ...]：表示映射类型的存储槽。
        
        [position, length, array]：表示数组类型的存储槽。

        Get variables from the storage
        :param address: The contract address
        :param params: The list of parameters param types: [position, length] or ["mapping", position, key1, key2, ...  ]
                       or [position, length, array]
        :return: The corresponding storage slot and its value
        """
        params = params or []
        # 存储槽的起始位置，默认为 0
        # 查询的存储槽数量，默认为 1
        # 用于存储映射类型的存储槽位置
        (position, length, mappings) = (0, 1, [])

        # 1.获取存储开始的位置
        try:
            # ["mapping", position, key1, key2, ...]：表示映射类型的存储槽。
            # 处理该类型
            if params[0] == "mapping":
                if len(params) < 3:
                    raise CriticalError("Invalid number of parameters.")
                # 获取位置p
                position = int(params[1])
                position_formatted = zpad(int_to_big_endian(position), 32)
                # 获取key
                for i in range(2, len(params)):
                    key = bytes(params[i], "utf8")
                    key_formatted = rzpad(key, 32)
                    # 计算位置
                    # slot p处存储全0，代表映射的开始
                    # slot( keccak256( key1 + p ) ) --> key1.value
                    # slot( keccak256( key2 + p ) ) --> key2.value
                    mappings.append(
                        int.from_bytes(
                            sha3(key_formatted + position_formatted), byteorder="big"
                        )
                    )

                length = len(mappings)
                if length == 1:
                    position = mappings[0]

            else:
                if len(params) >= 4:
                    raise CriticalError("Invalid number of parameters.")
                # 处理普通类型
                # [position, length]：表示从指定位置开始的连续存储槽。
                if len(params) >= 1:
                    position = int(params[0])
                if len(params) >= 2:
                    length = int(params[1])
                # 处理数组类型
                # [position, length, array]：表示数组类型的存储槽。
                if len(params) == 3 and params[2] == "array":
                    # 转成大端数字，并扩展成32位
                    position_formatted = zpad(int_to_big_endian(position), 32)
                    # 长度存在slot p
                    # array[0]的位置 --> slot( keccak256( p ) )
                    # array[1]的位置 --> slot( keccak256( p ) + 1 )
                    # ...
                    position = int.from_bytes(sha3(position_formatted), byteorder="big")

        except ValueError:
            raise CriticalError(
                "Invalid storage index. Please provide a numeric value."
            )

        outtxt = []

        # 2.查询并存储值，调用web3.eth.getStorageAt()
        try:
            # 单个slot查询
            if length == 1:
                outtxt.append(
                    "{}: {}".format(
                        position, self.eth.eth_getStorageAt(address, position)
                    )
                )
            else:
                # mapping查询
                if len(mappings) > 0:
                    for i in range(0, len(mappings)):
                        position = mappings[i]
                        outtxt.append(
                            "{}: {}".format(
                                hex(position),
                                self.eth.eth_getStorageAt(address, position),
                            )
                        )
                # 数组和普通类型的查询
                else:
                    for i in range(position, position + length):
                        outtxt.append(
                            "{}: {}".format(
                                hex(i), self.eth.eth_getStorageAt(address, i)
                            )
                        )
        except FileNotFoundError as e:
            raise CriticalError("IPC error: " + str(e))
        except ConnectionError:
            raise CriticalError(
                "Could not connect to RPC server. "
                "Make sure that your node is running and that RPC parameters are set correctly."
            )
        return "\n".join(outtxt)
