import pytest
from io import StringIO
from solvers.mosek.csqf import Csqf
from solvers.mosek.mcqf import MultiCqf
from tests.conftest import io_wrapper
from bin.classes import Network
from bin.io.topo import (
    parse_topo,
    parse_flows
)


class TestReport:
    def test_mcqf_link_utilization_report(self, generic_solver_args, switch_mcqf_config, topo_1sw):
        """Two flows being sent from ES0 -> ES1 150 Mbits each.
        """
        # Flow.s = 150 Megabits
        raw_flows = io_wrapper(
            StringIO(
                "FLOW,7,0,VLAN_0_Flow_0,ISOCHRONOUS_REAL_TIME,node0_0_0_0,node0_0_0_1,NO,50,MICRO_SECOND,50,MICRO_SECOND,18750000\nFLOW,7,1,VLAN_0_Flow_1,ISOCHRONOUS_REAL_TIME,node0_0_0_0,node0_0_0_1,NO,50,MICRO_SECOND,50,MICRO_SECOND,18750000"
            ))
        flows = parse_flows(raw_flows)
        topology = parse_topo(topo_1sw)
        network = Network(topology=topology, flows=flows, switch_conf=switch_mcqf_config)
        msk = MultiCqf("test_mcqf", network)
        solution = msk.solve(*generic_solver_args)

        _, edges = solution.flows, solution.edges

        assert edges['e1'] == (300000.0, 0.3, 30.0)
        assert edges['e2'] == (300000.0, 0.3, 30.0)