from enum import Enum
from abc import abstractmethod
from colorama import (
    Fore,
    Style
)
from bin.classes import McqfSwitchConfiguration


class TrafficType(Enum):
    CSQF = 1
    MCQF = 2


class Solution:
    def __init__(self) -> None:
        self.flows = {}
        self.edges = {}

    def add_flow(self, flow: dict):
        self.flows.update(flow)

    def add_edge(self, edge: dict):
        self.edges.update(edge)

    def __str__(self) -> str:
        return f"{self.flows} & {self.edges}"


class GenericSolver:
    def __init__(self, name, network, *args, **kwargs) -> None:
        print(
            Fore.MAGENTA + "\nInitializing..." + Style.RESET_ALL +
            "\nBuilding model and solving. This could take some time..."
        )

        self.name = name
        self.network = network
        self.runtime = None
        self._traffic_type = TrafficType.CSQF.name

        if isinstance(network.switch_conf, McqfSwitchConfiguration):
            self._traffic_type = TrafficType.MCQF.name

        # Output files
        self._output_name = f"{name}-{self._traffic_type}"

    @abstractmethod
    def solve(self, *args):
        raise NotImplementedError()

    @abstractmethod
    def __get_solution(self, *args):
        raise NotImplementedError()

    @abstractmethod
    def _gen_constraints(self):
        """"
        Call all constraints for the model
        """
        raise NotImplementedError()

    @abstractmethod
    def _build_obj_func(self, *args):
        """Builds the multi-objective function

        Raises:
            NotImplementedError: _description_
        """
        raise NotImplementedError()
