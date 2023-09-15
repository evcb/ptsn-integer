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
from mosek.fusion import SolutionError


class TestCsqf:
    def test_csqf_bandwidth_constraint(self, generic_solver_args, topo_1sw, switch_csqf_config):
        raw_flows = io_wrapper(StringIO("FLOW,7,0,VLAN_0_Flow_0,ISOCHRONOUS_REAL_TIME,node0_0_0_0,node0_0_0_1,NO,20,MICRO_SECOND,20,MICRO_SECOND,138000000"))
        topology = parse_topo(topo_1sw)
        flows = parse_flows(raw_flows)
        network = Network(topology=topology, flows=flows, switch_conf=switch_csqf_config)
        msk = Csqf("test_csqf", network)

        with pytest.raises(SolutionError) as e:
            msk.solve(*generic_solver_args)

    def test_csqf_queue_assignment(self, generic_solver_args, topo_1sw, switch_csqf_config):
        """"
        In case a link is fully used, the solver should delay the next incoming frames
        """
        raw_flows = io_wrapper(StringIO("FLOW,7,0,VLAN_0_Flow_0,ISOCHRONOUS_REAL_TIME,node0_0_0_0,node0_0_0_1,NO,100,MICRO_SECOND,2000,MICRO_SECOND,125000000\nFLOW,5,1,VLAN_0_Flow_1,ISOCHRONOUS_REAL_TIME,node0_0_0_0,node0_0_0_1,NO,200,MICRO_SECOND,1000,MICRO_SECOND,100"))
        topology = parse_topo(topo_1sw)
        flows = parse_flows(raw_flows)
        network = Network(topology=topology, flows=flows, switch_conf=switch_csqf_config)
        msk = Csqf("test_csqf", network)
        solution = msk.solve(*generic_solver_args)
        f_schedule = solution.flows
        bw_usage = solution.edges

        assert f_schedule['VLAN_0_Flow_0'][2] == "node0_0_0_0|e1|1|3-sw_0_0|e2|1|3-node0_0_0_1"
        assert f_schedule['VLAN_0_Flow_1'][2] == "node0_0_0_0|e1|1|1-sw_0_0|e2|1|1-node0_0_0_1"
        assert abs(bw_usage['e1'][2] - 100.00008) < 0.6

class TestMcqf:

    def test_mcqf_deadline(self, generic_solver_args, switch_mcqf_config, topo_1sw):
        raw_flows = io_wrapper(StringIO("FLOW,7,0,VLAN_0_Flow_0,ISOCHRONOUS_REAL_TIME,node0_0_0_0,node0_0_0_1,NO,50,MICRO_SECOND,50,MICRO_SECOND,135"))
        flows = parse_flows(raw_flows)
        topology = parse_topo(topo_1sw)
        network = Network(topology=topology, flows=flows, switch_conf=switch_mcqf_config)
        msk = MultiCqf("test_mcqf", network)
        solution = msk.solve(*generic_solver_args)

        # For CSQF the objective func. is minimizing bandwidth utilization
        flows, _ = solution.flows, solution.edges

        # For this test base cycle is 12
        assert flows['VLAN_0_Flow_0'][0] == 24

    def test_mcqf_exceed_bandwidth(self, generic_solver_args, switch_mcqf_config, topo_1sw):
        """For this test, group 7 is allocated 30% of the link's bandwidth.
        The flow size in this group is greater than 30%.
        """
        raw_flows = io_wrapper(StringIO("FLOW,7,0,VLAN_0_Flow_0,ISOCHRONOUS_REAL_TIME,node0_0_0_0,node0_0_0_1,NO,10,MICRO_SECOND,10,MICRO_SECOND,32500000\nFLOW,7,1,VLAN_0_Flow_1,ISOCHRONOUS_REAL_TIME,node0_0_0_0,node0_0_0_1,NO,10,MICRO_SECOND,10,MICRO_SECOND,12500000"))
        flows = parse_flows(raw_flows)
        topology = parse_topo(topo_1sw)
        network = Network(topology=topology, flows=flows, switch_conf=switch_mcqf_config)
        msk = MultiCqf("test_mcqf", network)

        with pytest.raises(SolutionError) as e:
            msk.solve(*generic_solver_args)
        # assert e.value.code == 3

    def test_mcqf_fit_bandwidth(self, generic_solver_args, switch_mcqf_config, topo_1sw):
        """For this test, group 7 is allocated 30% of the link's bandwidth.
        The flow size in this group uses approx. 29% of the link's bw capacity.
        """
        raw_flows = io_wrapper(StringIO("FLOW,7,0,VLAN_0_Flow_0,ISOCHRONOUS_REAL_TIME,node0_0_0_0,node0_0_0_1,NO,50,MICRO_SECOND,50,MICRO_SECOND,37000000"))
        flows = parse_flows(raw_flows)
        topology = parse_topo(topo_1sw)
        network = Network(topology=topology, flows=flows, switch_conf=switch_mcqf_config)
        msk = MultiCqf("test_mcqf", network)
        solution = msk.solve(*generic_solver_args)
        edgs = solution.edges
        assert abs(edgs['e1'][2] - 29) < .6
