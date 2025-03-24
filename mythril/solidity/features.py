TRANSFER_METHODS = ["transfer", "send"]


class SolidityFeatureExtractor:
    """
    从 Solidity 合约的抽象语法树AST中提取合约的特征
    """
    def __init__(self, ast):
        """
        从 Solidity 合约的抽象语法树AST中提取合约的特征
        """
        self.ast = ast

    def extract_features(self):
        """
        提取ast特征,包含变量,操作,地址,修饰符
        """
        function_features = {}
        function_nodes = self.find_function_nodes(self.ast)
        modifier_vars = {}
        # 遍历所有修饰符节点，提取每个修饰符中在 require 和 if 语句中使用的变量
        for modifier_node in self.find_modifier_nodes(self.ast):
            modifier_vars[modifier_node["name"]] = self.find_variables_in_require(
                modifier_node
            )
            modifier_vars[modifier_node["name"]].update(
                self.find_variables_in_if(modifier_node)
            )

        for node in function_nodes:
            function_name = self.get_function_name(node)
            # 检查函数是否包含 selfdestruct、call、delegatecall、callcode 和 staticcall 等关键操作
            contains_selfdestruct = self.contains_selfdestruct(node)
            contains_call = self.contains_call(node)
            contains_delegatecall = self.contains_delegatecall(node)
            contains_callcode = self.contains_callcode(node)
            contains_staticcall = self.contains_staticcall(node)
            # 提取函数中在 require 语句中使用的变量
            all_require_vars = self.find_variables_in_require(node)
            # 提取转账相关地址
            ether_vars = self.extract_address_variable(node)

            # 遍历函数的修饰符，将修饰符中使用的变量合并到 all_require_vars 中
            for potential_modifier in node.get("modifiers", []):
                # Issues with AST, sometimes, non-modifiers pop up here
                if potential_modifier["modifierName"]["name"] in modifier_vars:
                    all_require_vars.update(
                        modifier_vars[potential_modifier["modifierName"]["name"]]
                    )
            # 检查函数是否为 payable
            is_payable = self.is_function_payable(node)
            # 检查函数是否包含 isOwner 或 onlyOwner 修饰符
            has_isowner_modifier = self.has_isowner_modifier(node)
            # 检查函数是否包含 assert 操作
            contains_assert = self.contains_assert(node)
            function_features[function_name] = {
                "contains_selfdestruct": contains_selfdestruct,
                "contains_call": contains_call,
                "is_payable": is_payable,
                "has_owner_modifier": has_isowner_modifier,
                "contains_assert": contains_assert,
                "contains_callcode": contains_callcode,
                "contains_delegatecall": contains_delegatecall,
                "contains_staticcall": contains_staticcall,
                "all_require_vars": all_require_vars,
                "transfer_vars": ether_vars,
            }

        return function_features

    def find_function_nodes(self, node):
        """
        递归查找 AST 中的所有函数定义节点
        """
        # 若当前节点是函数定义节点，则返回该节点
        if node["nodeType"] == "FunctionDefinition":
            yield node
        # 若当前节点包含子节点，则递归查找
        if "nodes" in node:
            for child_node in node["nodes"]:
                yield from self.find_function_nodes(child_node)

    def find_modifier_nodes(self, node):
        """
        递归查找 AST 中的所有修饰符定义节点
        """
        if node["nodeType"] == "ModifierDefinition":
            yield node

        if "nodes" in node:
            for child_node in node["nodes"]:
                yield from self.find_modifier_nodes(child_node)

    def get_function_name(self, node):
        """
        获取函数节点的名称
        """
        return node["name"]

    def contains_command(self, node, command):
        """
        递归检查 AST 节点中是否包含特定命令
        """
        if isinstance(node, dict):
            # 查找command是否在节点中
            if command in node.values():
                return True
            # 递归查找
            for value in node.values():
                if isinstance(value, (dict, list)):
                    if self.contains_command(value, command):
                        return True

        elif isinstance(node, list):
            for item in node:
                if self.contains_command(item, command):
                    return True

        return False

    def contains_call(self, node):
        """
        检查 AST 节点中是否包含 call 操作
        """
        return self.contains_command(node, "call")

    def is_function_payable(self, node):
        """
        检查函数是否为 payable
        """
        return node.get("stateMutability") == "payable"

    def has_isowner_modifier(self, node):
        """
        检查函数是否包含 isOwner 或 onlyOwner 修饰符
        """
        if "modifiers" in node:
            for modifier in node["modifiers"]:
                if modifier["modifierName"]["name"].lower() in ("isowner", "onlyowner"):
                    return True
        return False

    def contains_assert(self, node):
        """
        检查 AST 节点中是否包含 assert 操作
        """
        return self.contains_command(node, "assert")

    def contains_selfdestruct(self, node):
        """
        检查 AST 节点中是否包含 selfdestruct 操作
        """
        return self.contains_command(node, "selfdestruct")

    def contains_delegatecall(self, node):
        """
        检查 AST 节点中是否包含 delegatecall 操作
        """
        return self.contains_command(node, "delegatecall")

    def contains_callcode(self, node):
        """
        检查 AST 节点中是否包含 callcode 操作
        """
        return self.contains_command(node, "callcode")

    def contains_staticcall(self, node):
        """
        检查 AST 节点中是否包含 staticcall 操作
        """
        return self.contains_command(node, "staticcall")

    def contains_require(self, node):
        """
        检查 AST 节点中是否包含 require 操作
        """
        return self.contains_command(node, "require")

    def extract_nodes(self, node, command, parent=None):
        """
        递归提取 AST 节点中包含特定命令的所有节点
        """
        node_list = []
        if isinstance(node, dict):
            # 检查command是否在节点中，在的话将该节点及其父节点添加到结果列表中
            if command in node.values():
                node_list.append((parent, node))
            # 递归查找
            for key, value in node.items():
                if isinstance(value, (dict, list)):
                    node_list.extend(self.extract_nodes(value, command, parent=node))
        elif isinstance(node, list):
            for item in node:
                node_list.extend(self.extract_nodes(item, command, parent=node))
        return node_list

    def find_all_variables(self, node):
        """
        递归查找 AST 节点中所有变量的名称
        """
        variables = set()
        # 用于递归遍历 AST 节点
        def traverse(node):
            if isinstance(node, dict):
                for key, value in node.items():
                    # 检查是否是变量声明
                    if key == "nodeType" and value == "Identifier":
                        if "name" in node:
                            variables.add(node["name"])
                    elif isinstance(value, (dict, list)):
                        traverse(value)
            elif isinstance(node, list):
                for item in node:
                    traverse(item)

        traverse(node)
        return variables

    def find_variables_in_require(self, node):
        """
        提取 require 语句中使用的变量
        """
        nodes = self.extract_nodes(node, "require")
        variables = set()
        for parent, _ in nodes:
            if "arguments" in parent:
                arguments = parent["arguments"]
                for argument in arguments:
                    variables.update(self.find_all_variables(argument))
        return variables

    def find_variables_in_if(self, node):
        """
        提取 if 语句中使用的变量
        """
        variables = []

        def traverse(node):
            # 是否时条件判断语句
            if "condition" in node:
                condition = node["condition"]
                # 检查左右表达式是否是变量声明
                if (
                    "leftExpression" in condition
                    and condition["leftExpression"]["nodeType"] == "Identifier"
                ):
                    variables.append(condition["leftExpression"]["name"])
                if (
                    "rightExpression" in condition
                    and condition["rightExpression"]["nodeType"] == "Identifier"
                ):
                    variables.append(condition["rightExpression"]["name"])

                traverse(condition)
            # 若if包含falseBody或trueBody，递归处理
            if "falseBody" in node and node["falseBody"]:
                traverse(node["falseBody"])

            if "trueBody" in node and node["trueBody"]:
                # 如果 trueBody 是一个"Block"，则递归处理块中的所有语句
                if (
                    "nodeType" in node["trueBody"]
                    and node["trueBody"]["nodeType"] == "Block"
                ):
                    statements = node["trueBody"].get("statements", [])
                    for statement in statements:
                        traverse(statement)
                else:
                    traverse(node["trueBody"])
            
            # 如果当前节点包含 "body" 属性，说明它是一个语句块
            if "body" in node and node["body"]:
                if "nodeType" in node["body"] and node["body"]["nodeType"] == "Block":
                    statements = node["body"].get("statements", [])
                    for statement in statements:
                        traverse(statement)
                else:
                    traverse(node["body"])

        traverse(node)

        return variables

    def extract_address_variable(self, node):
        """
        提取与转账相关的地址
        """
        if node is None or isinstance(node, (int, str)):
            return set([])
        transfer_vars = set([])
        if (
            # 当前节点是否是一个表达式语句
            node.get("nodeType", "") == "ExpressionStatement"
            # 检查其表达式是否是一个函数调用
            and node.get("expression", {}).get("nodeType") == "FunctionCall"
        ):
            expression = node["expression"].get("expression", None)
            # 检查该调用是否是转账方法
            if expression is not None and (
                expression["nodeType"] == "MemberAccess"
                and expression["memberName"] in TRANSFER_METHODS
            ):
                # 提取调用者的名称,address
                address_variable = expression["expression"].get("name")
                if address_variable:
                    transfer_vars.update(set([address_variable]))

        # 递归处理子节点
        for key, value in node.items():
            if isinstance(value, dict):
                transfer_vars.update(self.extract_address_variable(value))

            elif isinstance(value, list):
                for item in value:
                    transfer_vars.update(self.extract_address_variable(item))

        return transfer_vars
