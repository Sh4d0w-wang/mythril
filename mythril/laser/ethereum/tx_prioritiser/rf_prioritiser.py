import logging
import pickle

import numpy as np

log = logging.getLogger(__name__)


class RfTxPrioritiser:
    def __init__(self, contract, depth=3, model_path=None):
        """
        用于事务优先级排序的工具,基于随机森林(Random Forest)模型来预测下一个最有可能执行的事务

        初始化事务优先级排序器的状态
        """
        # 随机森林模型的路径
        self.rf_path = None
        self.contract = contract
        self.depth = depth

        # 从文件中反序列化对象
        with open(model_path, "rb") as file:
            self.model = pickle.load(file)
        # 如果没有特征数据，事务优先级排序将被禁用
        if self.contract.features is None:
            log.info(
                "There are no available features. Rf based Tx Prioritisation turned off."
            )
            return None
        # 将合约的特征数据预处理为模型所需的格式
        self.preprocessed_features = self.preprocess_features(self.contract.features)
        # 存储最近的预测结果
        self.recent_predictions = []

    def preprocess_features(self, features_dict):
        """
        将合约的特征字典转换为一个扁平化的特征数组，以便与随机森林模型的输入格式兼容
        """
        flat_features = []
        for function_name, function_features in features_dict.items():
            function_features_values = list(function_features.values())
            flat_features.extend(function_features_values)
        # 1：第一个的维度大小为1
        # -1：自动计算第二个维度的大小，以保持数组中总元素数量不变
        # 返回的是一个(1, n)的二维数组
        return np.array(flat_features).reshape(1, -1)

    def __next__(self, address):
        """
        预测下一个最有可能执行的事务序列
        """
        predictions_sequence = []
        # 预处理的特征(1, n)和最近的预测结果(1, m)拼接起来 --> (1, n + m)
        current_features = np.concatenate(
            [
                self.preprocessed_features,
                np.array(self.recent_predictions).reshape(1, -1),
            ],
            axis=1,
        )

        for i in range(self.depth):
            # 预测每个事务的概率
            predictions = self.model.predict_proba(current_features)
            # 选择概率最高的事务
            most_likely_next_tx = np.argmax(predictions, axis=1)[0]
            predictions_sequence.append(most_likely_next_tx)
            # 更新特征
            current_features = np.concatenate(
                [
                    self.preprocessed_features,
                    np.array(
                        self.recent_predictions + predictions_sequence[: i + 1]
                    ).reshape(1, -1),
                ],
                axis=1,
            )

        self.recent_predictions.extend(predictions_sequence)
        while len(self.recent_predictions) > self.depth:
            self.recent_predictions.pop(0)
        return predictions_sequence
