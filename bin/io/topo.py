from decimal import Decimal
import queue
from re import L
from bin import constants
from bin.classes import (
    Edge,
    Flow,
    EndSystem,
    Switch,
    McqfPriority
)

def read_file(file_path: str):
    with open(file_path, 'r') as f:
        raw_data = f.read().splitlines()
    
    # Remove comments
    return [d for d in raw_data if not d.startswith("#")]

def parse_topo(raw_data: str):
    """Parse topology configuration file.
    """
    _devices = {}
    _end_systems = set()
    _edges = set()
    _switches = set()
    # To help control array indexes when building the model
    ctrl_uid = 0

    # Vertexes
    for r_line in raw_data:
        p_line = tuple(r_line.split(","))
        v_id = p_line[0].lower()

        if v_id == 'vertex':
            _, dtype, name, _, mac, _, _ = p_line

            if dtype.lower() == "plc":
                device = EndSystem(
                    name=name,
                    uid=ctrl_uid,
                    mac_address=mac
                )
            elif dtype.lower() == "switch":
                device = Switch(
                    name=name,
                    uid=ctrl_uid,
                    mac_address=mac
                )

            _devices[device.name] = device
            ctrl_uid += 1

    # Edges
    for r_line in raw_data:
        p_line = tuple(r_line.split(","))
        e_id = p_line[0].lower()

        if e_id == 'edge':
            _, dtype, src, dest, _, g_id = p_line

            # Checking port
            if "." in src:
                src, port = src.split(".")
                port = int(port.replace("P", ""))
            else:
                src, port = dest, 0

            if "." in dest:
                dest, port = dest.split(".")
                port = int(port.replace("P", ""))
            else:
                dest, port = dest, 0

            _scr = _devices[src]
            _dest = _devices[dest]

            _in_edge = Edge(
                gid=g_id,
                source=_scr,
                destination=_dest,
                port=port
            )

            _out_edge = Edge(
                gid=g_id,
                source=_dest,
                destination=_scr,
                port=port
            )

            # Link between devices
            _scr.add_edge([_in_edge, _out_edge])
            _dest.add_edge([_in_edge, _out_edge])

            # Adding src list of all devices
            if isinstance(_scr, EndSystem):
                _end_systems.add(_scr)
            else:
                _switches.add(_scr)

            # Adding destt to list of all devices
            if isinstance(_dest, EndSystem):
                _end_systems.add(_dest)
            else:
                _switches.add(_dest)

            _edges.add(_in_edge)

    return {
        'switches': _switches,
        'end_systems': _end_systems,
        'edges': _edges
    }


def parse_flows(raw_data: str):
    """Parse flow file.
    """

    _flows = set()

    for line in raw_data:
        raw_flow = tuple(line.split(","))
        # flow, priority, id, flowname, type(ISOCHRONOUS_REAL_TIME=TT, AVB_HIGH=AVBA, AVB_LOW=AVBB), source, sink, unused, period, period_unit, deadline, deadline_unit, size(bytes)
        _, priority, gid, fname, _, src, dest, _, period, _, dline, _, size = raw_flow
        _flow = Flow(
            uid=int(gid),
            name=fname,
            source=src,
            destination=dest,
            priority=int(priority), # starts from 1
            size=int(size),         # bytes
            period=int(period),     # microseconds
            deadline=int(dline)     # microseconds
        )
        _flows.add(_flow)
    return _flows


def parse_switch_conf(raw_data: str):
    """Parse switch configuration file, used for MCQF traffic.

    USER INPUT IS TRUSTED:
        Bandwidth is a fraction of 1

    If the amount of queue members does not corespond to constants.MCQF_QUEUE_COUNT (8), the remaining
    queues will be added to the next group.
    """
    config = {}

    # Attributes for non-specific groups
    # Counter to keep track of generated queue #s
    q_count = 0
    # Accumulated bandwidth cycle
    # acc_bw_f = 0
    # # Greatest cycle factor among groups
    # gt_cl_f = 0

    for line in raw_data:
        raw_conf = tuple(line.split(","))
        # Priority group,#queues,bandwidth,factor
        priority, mb_count, bw_fract, cl_factor = raw_conf
        priority = int(priority)
        mb_count = int(mb_count)
        bw_fract = float(bw_fract)
        cl_factor = int(cl_factor)
        members = [q for q in range(q_count, q_count + mb_count)]
        # Increase member count to next group
        q_count += len(members)

        # In case queues are missing from the given groups
        # acc_bw_f += bw_fract
        # if gt_cl_f < cl_factor:
        #     gt_cl_f = cl_factor

        config[(priority, bw_fract, cl_factor)] = members

    # Create another priority group with remaining queues
    # if genq_count != constants.MCQF_QUEUE_COUNT:
    #     priority = 0 # lowest priority
    #     bw_fract = 1 - acc_bw_f
    #     cl_factor = cl_factor * 2
    #     members = [q for q in range(genq_count, constants.MCQF_QUEUE_COUNT)]

    #     config[(priority, bw_fract, cl_factor)] = members

    mcqf_prios = set()

    for k, memb in config.items():
        p, bf, cf = k

        mcqf_prios.add(
            McqfPriority(
                priority=p,
                bandwidth_fraction=bf,
                cycle_coefficient=cf,
                members=memb
            )
        )

    return {
        'groups': mcqf_prios,
        'queue_count': q_count
    }
