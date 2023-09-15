import math


class NetworkObject:

    def __init__(self, *args, **kwargs) -> None:
        self.name = kwargs['name']
        self.uid = kwargs['uid']  # unique identifier

    def __repr__(self) -> str:
        return self.__str__()

    def __str__(self) -> str:
        return self.name


class SwitchConfiguration:
    """A class to model switch configuration.
    """

    def __init__(
        self,
        queue_count: int,
        base_cycle: int,
        link_speed: int
    ) -> None:

        """Switch configuration for CSQF and MCQF traffic.

        Args:
            queue_count (int): Amount of queues in each switch
            base_cycle (int): Base cycle length in microseconds, i.e 10, 12
            link_speed (int): Link speed in megabits per second, i.e 1000
        """
        self.queue_count = queue_count
        self.base_cycle = base_cycle
        self.link_speed = link_speed


class McqfSwitchConfiguration(SwitchConfiguration):
    """MCQF Configuration class.
    It allows instantiation of MCQF Queue configurations.
    Holds a list of McqfPriority group member.
    """

    def __init__(
            self,
            priority_groups,
            *args,
            **kwargs) -> None:

        super().__init__(*args, **kwargs)
        # This will return a List[McqfPriority]
        self.priority_groups = priority_groups


class McqfPriority:
    """A class to store information about a priorty group and its members.
    """

    def __init__(
        self,
        priority: int,
        bandwidth_fraction: float,
        cycle_coefficient: float,
        members: list(),
    ) -> None:

        self.priority = int(priority)
        self.bandwidth_fraction = float(bandwidth_fraction)
        self.cycle_coefficient = float(cycle_coefficient)
        self.members = members

    def __str__(self) -> str:
        return f"PG#{self.priority}: {self.members} - Bandwidth Factor {self.bandwidth_fraction} & Cycle Coef. {self.cycle_coefficient}"

    def __repr__(self) -> str:
        return self.__str__()

    def build_default_groups(self):
        """Build groups for unspecified priorities.
        """


class Network:

    def __init__(
        self,
        topology: dict,
        flows,
        switch_conf: SwitchConfiguration) -> None:

        self.flows = flows
        self.end_systems = topology['end_systems']
        self.switches = topology['switches']
        self.edges = topology['edges']

        self.base_cycle = switch_conf.base_cycle  # Base cycle length in Microseconds
        self.link_speed = switch_conf.link_speed  # Link speed in Megabits (Mbps) per second

        # Pre-compute
        self.hypercycle = self.__calc_hypercycle()  # In microseconds
        self.cycles = self.__calc_cycles()          # how many cycles in a hypercycle?

        # For MCQF only
        self.switch_conf = switch_conf

    def __calc_hypercycle(self):
        """
        Returns hypercycle in us.

        Returns:
            _type_: int
        """
        return math.lcm(*[f.period for f in self.flows])

    def __calc_cycles(self):
        """Returns up amount of cycles in a hypercycle.
        Value is rounded up if fraction.

        Returns:
            _type_: int
        """
        return math.ceil(self.hypercycle / self.base_cycle)


class Flow(NetworkObject):

    def __init__(self,
                 uid,
                 name,
                 source,
                 destination,
                 priority: int,
                 size: int,
                 period: int,
                 deadline: int,
                 * args,
                 **kwargs) -> None:

        self.name = name
        self.source = source
        self.destination = destination
        self.priority = priority
        self.size = int(size) * 8.0e-6  # originally in bytes; to Mb (megabits)
        self.period = period            # originally in us
        self.deadline = deadline        # originally in us

        kwargs = {'name': name, 'uid': uid}
        super().__init__(*args, **kwargs)

    def __str__(self) -> str:
        return f"Flow{self.uid} {self.source}->{self.destination}"


class Device(NetworkObject):

    def __init__(self, mac_address, *args, **kwargs) -> None:
        super(Device, self).__init__(*args, **kwargs)
        self.mac = mac_address
        self._ingress = set()
        self._egress = set()

    def add_edge(self, edges):
        """Edges will be either egress or ingress
        """

        for edge in edges:
            # The source specifies the direction for the edge
            # If the source is equals to the device itself, this edge is outgoing
            if edge.source == self:
                self._egress.add(edge)
            else:
                self._ingress.add(edge)

    def ingress_edges(self):
        """Incoming port.
        Edge() where attr. destination == self
        """
        return self._ingress

    def egress_edges(self):
        """Outgoing port.
        Edge() where attr. source == self
        """
        return self._egress


class EndSystem(Device):
    pass


class Switch(Device):
    pass


class Edge:

    def __init__(self, gid, source, destination, port) -> None:
        self.gid = gid       # given id
        self.source = source
        self.destination = destination
        self.port = port

    def __repr__(self) -> str:
        return self.__str__()

    def __str__(self) -> str:
        return f"Edge-{self.gid} ({self.source}-{self.destination})"
