"""This module contains the SMT abstraction for a basic symbol expression."""

from typing import Any, Generic, Optional, Set, TypeVar, cast

import z3

Annotations = Set[Any]
T = TypeVar("T", bound=z3.ExprRef)


class Expression(Generic[T]):
    """
    符号表达式的基类,提供了简化和注解的功能
    
    This is the base symbol class and maintains functionality for simplification and annotations.
    """

    def __init__(self, raw: T, annotations: Optional[Annotations] = None):
        """
        初始化注解

        :param raw:
        :param annotations:
        """
        self.raw = raw

        # 如果提供了注解集合，确保其类型为 set
        if annotations:
            assert isinstance(annotations, set)
        # 初始化 _annotations 属性，存储注解集合
        self._annotations = annotations or set()

    @property
    def annotations(self) -> Annotations:
        """
        获取表达式的注解集合
        
        Gets the annotations for this expression.

        :return:
        """

        return self._annotations

    def annotate(self, annotation: Any) -> None:
        """
        为表达式添加注解
        
        Annotates this expression with the given annotation.

        :param annotation:
        """

        self._annotations.add(annotation)

    def simplify(self) -> None:
        """
        简化表达式
        
        Simplify this expression.
        """
        self.raw = cast(T, z3.simplify(self.raw))

    def __repr__(self) -> str:
        """
        返回表达式的字符串表示
        """
        return repr(self.raw)

    def size(self):
        """
        返回表达式的大小
        """
        return self.raw.size()

    def __hash__(self) -> int:
        """
        返回表达式的哈希值
        """
        return self.raw.__hash__()

    def get_annotations(self, annotation: Any):
        """
        获取特定类型的注解
        """
        return list(filter(lambda x: isinstance(x, annotation), self.annotations))


G = TypeVar("G", bound=Expression)


def simplify(expression: G) -> G:
    """
    简化表达式
    
    Simplify the expression .

    :param expression:
    :return:
    """
    expression.simplify()
    return expression
