"""This module includes classes used for annotating trace information.

This includes the base StateAnnotation class, as well as an adaption,
which will not be copied on every new state.
"""

from abc import abstractmethod


class StateAnnotation:
    """
    基类，用于在符号执行中持久化信息,允许模块在不需要遍历状态空间的情况下对状态进行推理

    The StateAnnotation class is used to persist information over traces.

    This allows modules to reason about traces without the need to
    traverse the state space themselves.
    """

    # TODO: Remove this? It seems to be used only in the MutationPruner, and
    # we could simply use world state annotations if we want them to be persisted.
    @property
    def persist_to_world_state(self) -> bool:
        """
        是否将注释持久化到世界状态

        如果希望注释在不同的用户发起的消息调用事务中持久化，则应启用此功能
        
        If this function returns true then laser will also annotate the
        world state.

        If you want annotations to persist through different user initiated message call transactions
        then this should be enabled.

        The default is set to False
        """
        return False

    @property
    def persist_over_calls(self) -> bool:
        """
        是否在调用之间传播注释

        如果希望注释在不同的调用之间传播，则应启用此功能

        If this function returns true then laser will propagate the annotation between calls

        The default is set to False
        """
        return False

    @property
    def search_importance(self) -> int:
        """
        表示注释的搜索重要性

        用于估计带有相应注释的状态的优先级

        Used in estimating the priority of a state annotated with the corresponding annotation.
        Default is 1
        """
        return 1


class MergeableStateAnnotation(StateAnnotation):
    """
    抽象类，用于定义可以合并的注释

    This class allows a base annotation class for annotations that
    can be merged.
    """

    @abstractmethod
    def check_merge_annotation(self, annotation) -> bool:
        """
        检查是否可以将当前注释与另一个注释合并
        """
        pass

    @abstractmethod
    def merge_annotation(self, annotation):
        """
        将当前注释与另一个注释合并
        """
        pass


class NoCopyAnnotation(StateAnnotation):
    """
    基类，创建新状态时不会被复制，而是直接传播同一个对象
    
    This class provides a base annotation class for annotations that
    shouldn't be copied on every new state.

    Rather the same object should be propagated. This is very useful if
    you are looking to analyze a property over multiple substates
    """

    def __copy__(self):
        """
        返回当前对象的引用，而不是创建一个副本
        """
        return self

    def __deepcopy__(self, _):
        """
        返回当前对象的引用，而不是创建一个深副本
        """
        return self
