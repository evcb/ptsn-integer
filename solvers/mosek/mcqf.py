from math import prod
from bin.constants import OUTPUT_FOLDER_NAME
from solvers.classes import TrafficType
from solvers.mosek.csqf import Csqf
from bin.io.io import (
    write_solution
)

from mosek.fusion import (
    Domain,
    Expr
)


class MultiCqf(Csqf):
    """A base class for a Multi-CQF Mosek problem instance.
    A switch configuration file must be passed.
    """
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        # Queue priority groups
        self._qp_groups = self.network.switch_conf.priority_groups
        # A direct mapping between queues and their cycle coefficient Q.a
        self._q_cf = {q: pg.cycle_coefficient for pg in self._qp_groups for q in pg.members}
        # A direct mapping between queues and their bandwidth fraction Q.b
        self._q_bf = {q: pg.bandwidth_fraction for pg in self._qp_groups for q in pg.members}
        # A direct mapping between queues and their priority
        self._q_pr = {q: pg.priority for pg in self._qp_groups for q in pg.members}

    def _calc_arrival_pattern(self, cycle, flow):
        """Overriding CSQF's original A(c)
        """
        return flow.size if (cycle * self._base_cycle % flow.period) == 0 else 0

    def _cons_priority_groups(self):
        """Constrains flows according to their priority groups
        Constrains flows by assigning them to queues with the same priority
        group.
        """

        for m in self._flows:
            _fp = m.priority

            for _q in self._queue_iter:
                _qp = self._q_pr[_q]
                # Flow priority != queue priority = blocked from transmission in that queue
                if _qp != _fp:
                    self._model.constraint(
                        f"Flow {m.uid} blocked in Queue {_q}",
                        Expr.sum(
                            self._r_vars.slice(
                                [m.uid, _q, 0, 0],
                                [m.uid + 1, _q + 1, self._device_count, self._device_count]
                        )),
                        Domain.equalsTo(0.0)
                    )

    def _cons_deadline(self):
        """Constrains deadline
        """

        for m in self._flow_iter:
            _qs_vars = []
            for q in self._queue_iter:
                # queue coefficient delay
                # from cycle domain to time domain
                _qf = self._q_cf[q] * self._base_cycle
                for d in self._dev_iter:
                    _qs_vars.append(
                        Expr.mul(
                            _qf,
                            self._r_vars.slice(
                                [m, q, d, 0],
                                [m + 1, q + 1, d + 1, self._device_count]
                            )
                        )
                    )

            self._model.constraint(
                f"Flow {m} deadline",
                Expr.sum(Expr.vstack(_qs_vars)),
                Domain.lessThan(self._flow_dls[m])
            )

    def _gen_constraints(self):
        """Overriding, adding further constraints for MCQF
        """
        super()._gen_constraints()

        # MCQF exclusive constraints
        self._cons_priority_groups()

    def _cons_bandwidth(self):
        """Link bandwidth utilization
        """

        for d in self._dev_iter:
            for e in self._dev_iter:
                for pgroup in self._qp_groups:
                    pty = pgroup.priority
                    bw_f = pgroup.bandwidth_fraction
                    cycle_coef = pgroup.cycle_coefficient
                    queues = pgroup.members

                    for c in self._cycle_iter:
                        _realc = c + 1
                        # flows in device e(d, e)
                        _pgs_vars = []
                        # Queues in this priority group
                        for q in queues:
                            _realq = q + 1
                            t_rs = _realq * cycle_coef

                            for f in self._flows:
                                # Arrival pattern (A(c - T(rs)))
                                _s_a = self._calc_arrival_pattern(_realc - t_rs, f)
                                _s_var = self._r_vars.index([f.uid, q, d, e])
                                _pgs_vars.append(Expr.mul(_s_a, _s_var))

                        # Link utilization constraint
                        # BUijkc <= Qk.B
                        # Not greater than priority group's bandwidth allowance
                        self._model.constraint(
                            f"Link capacity edge {d}<->{e} cycle {_realc} - Piority {pty}",
                            Expr.sum(Expr.vstack(_pgs_vars)),
                            Domain.lessThan(bw_f * self._link_speed)
                        )

    def _obj_mean_e2e_delay(self):
        """Objective function minimizing E2E delay.

        Given by: 
            sum(rls.q x rls.Q.a), for i,j in |D| and s in |S|
        """
        e2e = []
        for q in self._queue_iter:
            _realq = q + 1
            _qf = self._q_cf[q]

            e2e.append(
                Expr.mul(
                    _realq * _qf * self._base_cycle,
                    self._r_vars.slice(
                        [0, q, 0, 0],
                        [self._flow_count, q + 1, self._device_count, self._device_count]
                ))
            )

        # 1/|S| * sum(E2E(rij))
        return Expr.mul(
            1/self._flow_count,
            Expr.sum(Expr.vstack(e2e))
        )

    def _obj_bandwidth_util(self):
        """Objective function minimizing bandwidth utilization.

        Given by: 
            sum(Bijc) / |E|, for e,j in |D| and c in |C|
        """
        obj_mband = []
        for d in self._dev_iter:
            for e in self._dev_iter:
                _bmax_vars = self._b_vars.slice(
                    [d, e],
                    [d + 1, e + 1]
                )
                # Max(Bijc) / e.S
                obj_mband.append(
                    Expr.mul(
                        1/self._link_speed,
                        Expr.sum(_bmax_vars)
                    )
                )

        # Omega = sum(BUij) / |Epsilon|
        return Expr.mul(1/self._edge_count, Expr.sum(Expr.vstack(obj_mband)))

    def _build_obj_func(self, *args):
        """Build multi-objective function
        
        Returns:
            List: Multiple objective functions
        """
        return "Mean End-to-End delay", self._obj_mean_e2e_delay()

    def _fmt_solution(self, write_out=False):
        """Adding group statistics to output
        """
        solution = super()._fmt_solution(write_out)

        # REPORT.csv

        # TCFileName,TrafficShaper,Algorithm,Runtime(s),MeanE2E(us), 
        # 7-E2E, 6-E2E, 5-E2E, 4-E2E, 
        # MeanLU (%),MaxLU (%), MeanBWC(%), MaxBWC(%), 
        # 7-MaxBWC, 6-MaxBWC, 5-MaxBWC, 4-MaxBWC,
        # 7-MeanBWC, 6-MeanBWC, 5-MeanBWC, 4-MeanBWC, 
        # NoofmissedDeadlines, 
        # 7-missed, 6-missed, 5-missed, 4-missed 

        # Report vars
        # Stats for each priority group, in format (Mean E2E, MaxBW, MeanBW, Missed)
        _dgroups = {pg.priority: [0, 0, 0, 0] for pg in sorted(self._qp_groups, key=lambda x: x.priority)}
        
        # Amount of flows in each PG
        _fgroups = {pg: 0 for pg in _dgroups}
        for f in self._flows:
            _fgroups[f.priority] += 1

        # Dynamically building headers
        _pg_mean_delay = ",".join(["{}-E2E".format(pg) for pg in _dgroups])
        _pg_maxbwc = ",".join(["{}-MaxBWC".format(pg) for pg in _dgroups])
        _pg_meanbwc = ",".join(["{}-MeanBWC".format(pg) for pg in _dgroups])
        _pg_missed = ",".join(["{}-missed".format(pg) for pg in _dgroups])
        mean_delay = 0
        missed_dl = 0
        # BW
        mean_lu = 0
        max_lu = 0
        mean_bwc = 0
        max_bwc = 0

        # File header
        # TCFileame-TrafficShaper-Algorithm-Topo.csv
        _report_f_name = f"{self._output_name}_report.csv"
        _repor_out = f"\nTCFileName, TrafficShaper, Algorithm, Runtime(s), MeanE2E(us), {_pg_mean_delay}, MeanLU (%), MaxLU (%), MeanBWC(%), MaxBWC(%), {_pg_maxbwc}, {_pg_meanbwc}, NoofmissedDeadlines, {_pg_missed}\n"

        for flow in self._flows:
            f_path = solution.flows[flow.name][3]
            # MCQF != CSQF, as α = r.q x r.Q.α
            # Recalculating delay
            delay = sum([self._q_cf[p[3]] * p[3] * self._base_cycle for p in f_path])
            mean_delay += delay
            _dgroups[flow.priority][0] += delay / _fgroups[flow.priority]  # Mean E2E
            _dgroups[flow.priority][1] += 0                                # MeanBWC
            _dgroups[flow.priority][2] += 0                                # MaxBWC
            m_dl = 1 if delay > flow.deadline else 0
            missed_dl += m_dl                                              # NoofmissedDeadlines
            _dgroups[flow.priority][3] += m_dl                             # Missed Deadline

        _repor_out += f"{self.name}, {self._traffic_type}, IP, {self.runtime[0]}, {mean_delay / self._flow_count}"

        # MeanE2E
        for _, data in _dgroups.items():
            _repor_out += f", {data[0]}"

        # LINKS
        for _, data in solution.edges.items():
            # edge data: (max_bw, mean_bw, mean_util)
            
            # MeanLU %
            mean_lu += data[2] / self._edge_count
            # MaxLU % - transforming from kbps to mbps
            max_lu += data[0] / 1000 / self._edge_count / 100

        _repor_out += f", {mean_lu}, {max_lu}, {mean_bwc}, {max_bwc}"

        # MaxBWC per group
        for _, data in _dgroups.items():
            _repor_out += f", {data[2]}"

        # MeanBWC per group
        for _, data in _dgroups.items():
            _repor_out += f", {data[1]}"
        
        # Noofmisseddeadlines
        _repor_out += f", {missed_dl}"

        # Missed deadlines per group
        for _, data in _dgroups.items():
            _repor_out += f", {data[3]}"

        # Result to stdout
        print(_repor_out)

        if write_out:
            write_solution(_report_f_name, _repor_out, append=True)

        return solution
