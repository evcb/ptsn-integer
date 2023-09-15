import pytest
from io import StringIO
from bin.constants import (
    CSQF_BASE_CYCLE,
    CSQF_DEFAULT_LINK_SPEED,
    CSQF_QUEUE_COUNT
)
from bin.classes import (
    SwitchConfiguration,
    McqfSwitchConfiguration
)
from bin.io.topo import parse_switch_conf


class Args:
    """A mock class for ArgParser
    """
    def __init__(
        self,
        path,
        mcqf,
        csqf,
        cycle_length=10,
        link_speed=1000,
        switch_config="",
        verbose=False,
        write_task_files=False,
        write_solution=False
    ) -> None:
        self.path = path
        self.mcqf = mcqf
        self.csqf = csqf
        self.verbose=verbose
        self.switch_config=switch_config
        self.cycle_length = cycle_length
        self.link_speed = link_speed
        self.write_task_files=write_task_files
        self.write_solution=write_solution

    def to_dict(self):
        return self.__dict__

def io_wrapper(stream):
    return stream.read().splitlines()

@pytest.fixture
def sw_config():
    """This SW configuration has the following settings:
    Priority Group 7: 1 queue   | bandwidth allocation 30% of link capacity
    Priority Group 6: 2 queues  | bandwidth allocation 25% of link capacity
    Priority Group 5: 3 queues  | bandwidth allocation 25% of link capacity
    Priority Group 4: 1 queues  | bandwidth allocation 20% of link capacity

    Returns:
        str: Switch configuration
    """
    _tp = StringIO("7,1,0.3,1\n6,2,0.25,4\n5,3,0.25,8\n4,1,0.2,8")
    return io_wrapper(_tp)

@pytest.fixture
def flow_1():
    _tp = StringIO(
        "FLOW,7,0,VLAN_0_Flow_0,ISOCHRONOUS_REAL_TIME,node0_0_0_0,node0_0_0_1,NO,50,MICRO_SECOND,50,MICRO_SECOND,300\nFLOW,7,1,VLAN_0_Flow_1,ISOCHRONOUS_REAL_TIME,node0_0_0_0,node0_0_0_1,NO,100,MICRO_SECOND,100,MICRO_SECOND,187\nFLOW,7,2,VLAN_0_Flow_2,ISOCHRONOUS_REAL_TIME,node0_0_0_0,node0_0_0_2,NO,50,MICRO_SECOND,50,MICRO_SECOND,300"
    )
    return io_wrapper(_tp)

@pytest.fixture
def topo_4sw():
    _fl = StringIO(
        "vertex,PLC,node0_0_0_0,mac,00:00:00:00:00:08,PortNumber,1\nvertex,PLC,node0_0_0_1,mac,00:00:00:00:00:09,PortNumber,1\nvertex,PLC,node0_0_0_2,mac,00:00:00:00:00:08,PortNumber,1\nvertex,SWITCH,sw_0_0,mac,00:00:00:00:00:00,PortNumber,8\nvertex,SWITCH,sw_0_1,mac,00:00:00:00:00:00,PortNumber,8\nvertex,SWITCH,sw_0_2,mac,00:00:00:00:00:00,PortNumber,8\nvertex,SWITCH,sw_0_3,mac,00:00:00:00:00:00,PortNumber,8\nedge,WIRE,sw_0_0.P0,node0_0_0_0,undirect,e1\nedge,WIRE,sw_0_1.P0,node0_0_0_1,undirect,e2\nedge,WIRE,sw_0_2.P0,sw_0_1.P0,undirect,e3\nedge,WIRE,sw_0_2.P1,sw_0_0.P0,undirect,e4\nedge,WIRE,sw_0_3.P0,node0_0_0_0,undirect,e5\nedge,WIRE,sw_0_3.P1,node0_0_0_1,undirect,e6\nedge,WIRE,sw_0_2.P2,node0_0_0_2,undirect,e7"
    )
    return io_wrapper(_fl)

@pytest.fixture
def topo_1sw():
    _tp = StringIO("vertex,PLC,node0_0_0_0,mac,00:00:00:00:00:08,PortNumber,1\nvertex,PLC,node0_0_0_1,mac,00:00:00:00:00:09,PortNumber,1\nvertex,SWITCH,sw_0_0,mac,00:00:00:00:00:00,PortNumber,8\nedge,WIRE,sw_0_0.P0,node0_0_0_0,undirect,e1\nedge,WIRE,sw_0_0.P1,node0_0_0_1,undirect,e2")
    return io_wrapper(_tp)

@pytest.fixture
def generic_solver_args():
    return (False, False, False)


@pytest.fixture
def switch_csqf_config():
    return SwitchConfiguration(
        queue_count=CSQF_QUEUE_COUNT,
        base_cycle=CSQF_BASE_CYCLE,
        link_speed=CSQF_DEFAULT_LINK_SPEED
    )

@pytest.fixture
def switch_mcqf_config(sw_config):
    parsed_conf = parse_switch_conf(sw_config)
    return McqfSwitchConfiguration(
        queue_count=parsed_conf['queue_count'],
        base_cycle=CSQF_BASE_CYCLE,
        link_speed=CSQF_DEFAULT_LINK_SPEED,
        priority_groups=parsed_conf['groups']
    )

@pytest.fixture
def csqf_main_args():
    return Args(
        path = "cases/test/1sw.proto/",
        csqf = True,
        mcqf = False
    )

@pytest.fixture
def mcqf_main_args():
    return Args(
        path = "cases/test/1sw.proto/",
        csqf = False,
        mcqf = True,
        switch_config = "cases/test/1sw.proto/config.csv"
    )