from typing import List, Union

import z3


class Model:
    """
    封装多个 Z3 模型
    
    The model class wraps a z3 model

    This implementation allows for multiple internal models, this is required for the use of an independence solver
    which has models for multiple queries which need an uniform output.
    """

    def __init__(self, models: List[z3.ModelRef] = None):
        """
        初始化一个模型

        Initialize a model object
        :param models: the internal z3 models that this model should use
        """
        self.raw = models or []

    def decls(self) -> List[z3.ExprRef]:
        """
        获取所有内部模型的声明
        
        Get the declarations for this model
        """
        result: List[z3.ExprRef] = []
        for internal_model in self.raw:
            result.extend(internal_model.decls())
        return result

    def __getitem__(self, item) -> Union[None, z3.ExprRef]:
        """
        根据传入的 item 获取声明或解释
        
        Get declaration from model
        If item is an int, then the declaration at offset item is returned
        If item is a declaration, then the interpretation is returned
        """
        for internal_model in self.raw:
            is_last_model = self.raw.index(internal_model) == len(self.raw) - 1

            try:
                result = internal_model[item]
                if result is not None:
                    return result
            except IndexError:
                if is_last_model:
                    raise
                continue
        return None

    def eval(
        self, expression: z3.ExprRef, model_completion: bool = False
    ) -> Union[None, z3.ExprRef]:
        """
        使用模型评估给定的表达式

        :param expression: 需要评估的 Z3 表达式
        :param model_completion: 如果模型中没有对表达式的解释，是否使用默认值
        :return: The evaluated expression
        """
        for internal_model in self.raw:
            is_last_model = self.raw.index(internal_model) == len(self.raw) - 1
            # 检查当前模型是否包含表达式的声明
            # expression.decl() 是否在当前模型的声明中
            is_relevant_model = expression.decl() in list(internal_model.decls())
            # 如果当前模型包含表达式的声明，或者当前模型是最后一个模型，则使用 internal_model.eval 方法评估表达式
            if is_relevant_model or is_last_model:
                # 接收一个 Z3 表达式（z3.ExprRef），并返回该表达式在当前模型中的具体值
                return internal_model.eval(expression, model_completion)
        return None
