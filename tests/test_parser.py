from main import main
from bin.io.topo import (
    parse_flows,
    parse_switch_conf,
    parse_topo
)


class TestParser:

    def test_switch_conf_init(self, sw_config):
        assert parse_switch_conf(sw_config)

    def test_topo_parser_init(self, topo_4sw):
        assert parse_topo(topo_4sw)

    def test_flow_parser_init(self, flow_1):
        assert parse_flows(flow_1)
