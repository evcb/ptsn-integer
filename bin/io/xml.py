from xml.dom import minidom

from bin.classes import (
    Edge,
    Flow,
    EndSystem,
    Switch
)


def parse_app(file_path: str):
    xmldoc = minidom.parse(file_path)
    raw_messages = xmldoc.getElementsByTagName('Message')
    messages = set()
    control_id = 0

    for m in raw_messages:
        flow = Flow(
            c_id=control_id,
            name=m.attributes['Name'].value,
            source=m.attributes['Source'].value,
            destination=m.attributes['Destination'].value,
            size=int(m.attributes['Size'].value),
            period=int(m.attributes['Period'].value),
            deadline=int(m.attributes['Deadline'].value),
        )
        messages.add(flow)
        control_id += 1

    return messages


def parse_conf(file_path: str):
    xmldoc = minidom.parse(file_path)
    raw_vertexes = xmldoc.getElementsByTagName('Vertex')  # ESs and SWs
    raw_edges = xmldoc.getElementsByTagName('Edge')  # Links
    _devices = {}
    control_id = 0

    end_systems = set()
    switches = set()

    for v in raw_vertexes:
        _name = v.attributes['Name'].value

        if not _name.startswith("SW"):
            device = EndSystem(name=v.attributes['Name'].value,
                               c_id=control_id)
        else:
            device = Switch(name=v.attributes['Name'].value, c_id=control_id)
        _devices[device.name] = device
        control_id += 1

    for e in raw_edges:
        _scr = _devices[e.attributes['Source'].value]
        _dest = _devices[e.attributes['Destination'].value]

        edge = Edge(id=int(e.attributes['Id'].value),
                    propDelay=e.attributes['PropDelay'].value,
                    bandwidth=e.attributes['BW'].value,
                    source=_scr,
                    destination=_dest)

        # Link between devices
        _scr.add_edge(edge)
        _dest.add_edge(edge)

        # Adding src list of all devices
        if isinstance(_scr, EndSystem):
            end_systems.add(_scr)
        else:
            switches.add(_scr)

        # Adding destt to list of all devices
        if isinstance(_dest, EndSystem):
            end_systems.add(_dest)
        else:
            switches.add(_dest)

    return {'switches': switches, 'end_systems': end_systems}