import sys
import mosek
from mosek.fusion import (
    Model,
    Domain,
    Expr,
    ObjectiveSense,
    OptimizeError,
    SolutionError,
    AccSolutionStatus,
    ProblemStatus
)
from colorama import (
    Fore,
    Style
)
from bin.constants import OUTPUT_FOLDER_NAME
from bin.io.io import (
    write_solution,
    create_folder
)
from solvers.classes import (
    TrafficType,
    GenericSolver,
    Solution
)


class Csqf(GenericSolver):
    """A base class for a CSQF Mosek problem instance.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        # MODEL
        self._model = Model()

        # Data
        self._switches = self.network.switches
        self._endsys = self.network.end_systems
        self._flows = self.network.flows
        self._link_speed = self.network.link_speed
        self._base_cycle = self.network.base_cycle
        self._edges = self.network.edges

        # Labels & identification
        self._dev_labels = {dev.uid: dev.name for dev in set.union(self._switches, self._endsys)}
        self._dev_uids = {dev.name: dev.uid for dev in set.union(self._switches, self._endsys)}

        self._edg_gids = {(edg.source.uid, edg.destination.uid): edg.gid for edg in self._edges}
        # adding reverse order, as edges are duplex
        self._edg_gids.update({(edg.destination.uid, edg.source.uid): edg.gid for edg in self._edges})

        # Sizes
        self._queue_count = self.network.switch_conf.queue_count
        self._flow_count = len(self._flows)
        self._device_count = len(self._switches) + len(self._endsys)
        self._cycle_count = self.network.cycles
        self._edge_count = len(self._edges)

        # Iterators
        self._flow_iter = range(0, self._flow_count)
        self._queue_iter = range(0, self._queue_count)
        self._dev_iter = range(0, self._device_count)
        self._cycle_iter = range(0, self._cycle_count)

        # Extracted attributes
        self._flow_dls = {flow.uid: flow.deadline for flow in self._flows}

        # Solver variables

        # Links
        self._r_vars = self._model.variable(
            "r",
            [self._flow_count, self._queue_count, self._device_count, self._device_count],
            Domain.binary()
        )

        # Aux. var, bw util == Sum(s.ci * Bijc)
        self._b_vars = self._model.variable(
            "b",
            [self._device_count, self._device_count],
            Domain.greaterThan(0.0)
        )

    def _calc_arrival_pattern(self, cycle, flow):
        """Arrival Pattern function Alpha(c).
        """
        return flow.size if 0 <= (cycle * self._base_cycle % flow.period) <= self._base_cycle else 0

    def _cons_non_edges(self):
        """Since not all devices are connected to each other,
        constrain non-existing edges in the graph to zero.
        """

        # All edges, permutated
        # Since connections are duplex, permutate connections, where (1,0) == (0,1)
        _ea_edges = set()

        for edge in self._edges:
            edg = (edge.source.uid, edge.destination.uid)
            # Permutating, since edges are full-duplex
            _ea_edges.add((edg[0], edg[1]))
            _ea_edges.add((edg[1], edg[0]))

        # Control list
        _c_edges = set()

        for d in self._dev_iter:
            for e in self._dev_iter:
                i, o = edge = (d, e)

                # Edge does not exist and is not in control list
                if edge not in _ea_edges and edge not in _c_edges:
                    self._model.constraint(
                        f"Non-existing edge r{i}->{o}",
                        Expr.sum(
                            self._r_vars.slice(
                                [0, 0, i, o],
                                [self._flow_count, self._queue_count, i + 1, o + 1]
                        )),
                        Domain.equalsTo(0.0))

                    self._model.constraint(
                        f"Non-existing edge b{i}->{o}",
                        Expr.sum(
                            self._b_vars.slice(
                                [i, o],
                                [i + 1, o + 1]
                        )),
                        Domain.equalsTo(0.0))
                    _c_edges.add(edge)

    def _cons_src_dest(self):
        """Constrain sources and destinations
        Should a vertex not be either, the path for s_i for ESi gets constrained to zero, st.:
        r[i, *, *, *] == 0
        """

        for flow in self._flows:
            for esys in self._endsys:
                _is_src = flow.source == esys.name
                _is_dest = flow.destination == esys.name
                _src_vars = self._r_vars.slice(
                    [flow.uid, 0, esys.uid, 0],
                    [flow.uid + 1, self._queue_count, esys.uid + 1, self._device_count]
                )
                _dest_vars = self._r_vars.slice(
                    [flow.uid, 0, 0, esys.uid],
                    [flow.uid + 1, self._queue_count, self._device_count, esys.uid + 1]
                )

                # Neither src or dst
                _dest_val = 0.0
                _src_val = 0.0

                # Source vertex?
                if _is_src:
                    _src_val = 1.0

                # Dest. vertex?
                if _is_dest:
                    _dest_val = 1.0

                # Const. streams leaving node
                self._model.constraint(
                    f"Endsys. {esys.name} source for {flow.name}",
                    Expr.sum(_src_vars),
                    Domain.equalsTo(_src_val)
                )

                # Const. streams leaving node
                self._model.constraint(
                    f"Endsys. {esys.name} destination for {flow.name}",
                    Expr.sum(_dest_vars),
                    Domain.equalsTo(_dest_val)
                )

    def _cons_switch_traffic(self):
        """Constrain switch traffic, s.t sum(in_flows) == sum(out_flows)
        """
        # SWITCHES
        for switch in self._switches:
            for m in self._flow_iter:
                # Ingoing edges
                _ini_var = self._r_vars.slice(
                    [m, 0, 0, switch.uid],
                    [m + 1, self._queue_count, self._device_count, switch.uid + 1],
                )
                # Outgoing edges
                _ino_var = self._r_vars.slice(
                    [m, 0, switch.uid, 0],
                    [m + 1, self._queue_count, switch.uid + 1, self._device_count],
                )

                # Flows entering must leave
                self._model.constraint(
                    f"Switch traffic sum(*->{switch.name}) = sum({switch.name}->*) for flow {m}",
                    Expr.sub(
                        Expr.sum(_ini_var),
                        Expr.sum(_ino_var)
                    ),
                    Domain.equalsTo(0.0)
                )

    def _cons_aux_vars(self):
        """Constrain aux. variables

        B is assigned the sum (s.b * r_ij + ..)
        BUji = Sum(Rij)
        """
        for d in self._dev_iter:
            for e in self._dev_iter:
                _deb_vars = []

                for f in self._flows:
                    _b_var = self._r_vars.slice(
                        [f.uid, 0, d, e],
                        [f.uid + 1, self._queue_count, d + 1, e + 1]
                    )
                    # Bw util.
                    _deb_vars.append(Expr.mul(f.size, _b_var))

                # Aux. var. for bandwidth util. calculation
                self._model.constraint(
                    f"b{d}<->{e} = sum(s.Alpha * rs{d}<->{e} + ...)",
                    Expr.sub(
                        self._b_vars.index(d, e),
                        Expr.sum(Expr.vstack(_deb_vars))
                    ),
                    Domain.equalsTo(0.0)
                )

    def _cons_bandwidth(self):
        """Cosntrain link bandwidth utilization
        Calculate bandwidth utilization by summing flows that are being transmitted in the same cycle.
        """
        for d in self._dev_iter:
            for e in self._dev_iter:
                for c in self._cycle_iter:
                    _realc = c + 1
                    _s_vars = []

                    for q in self._queue_iter:
                        # for A(c - α)
                        alpha = q + 1

                        for f in self._flows:
                            _s_a = self._calc_arrival_pattern(_realc - alpha, f)
                            _s_var = Expr.mul(
                                _s_a, # arrival pattern
                                self._r_vars.index([f.uid, q, d, e])
                            )
                            _s_vars.append(_s_var)

                    # Link utilization constraint
                    self._model.constraint(
                        f"Link capacity edge e{d}<->e{e} cycle {_realc}",
                        Expr.sum(Expr.vstack(_s_vars)),
                        Domain.lessThan(self._link_speed)
                    )

    def _cons_deadline(self):
        """Constrain deadline
        Optional hard-constraint
        The solution domain is restricted to feasible solutions where flows meet their deadlines.
        """

        for m in self._flow_iter:
            _md_vars = []
            for q in self._queue_iter:
                # Domain transf.: for all flows, multiply the queue# by the cycle length.
                # REMEMBER: queue # start from 0

                # Note: queue coefficient delay == queue #
                _qf = (q + 1) * self._base_cycle
                for d in self._dev_iter:
                    _md_vars.append(
                        Expr.mul(
                            _qf,
                            self._r_vars.slice(
                                [m, q, d, 0],
                                [m + 1, q + 1, d + 1, self._device_count]
                            )
                        )
                    )

            self._model.constraint(
                f"Deadline constraint for flow {m}",
                Expr.sum(Expr.vstack(_md_vars)),
                Domain.lessThan(self._flow_dls[m])
            )

    def _obj_bandwidth_util(self):
        """
        Objective: Bandwidth utilization
        Given by: 
            sum(Bijc) / |E|, for e,j in |D| and c in |C|
        """
        obj_mband = []

        for d in self._dev_iter:
            for e in self._dev_iter:
                _bmax_vars = self._b_vars.index([d, e])
                # (Max(Bijc) / link capacity) * 1000
                obj_mband.append(
                    Expr.mul(
                        1000,
                        Expr.mul(
                            1/self._link_speed,
                            Expr.sum(_bmax_vars)
                        )
                    )
                )

        # |E| = Set of links
        e_count = len(self._edges)

        # sum(Bij) / |E|
        return Expr.mul(1/e_count, Expr.sum(Expr.vstack(obj_mband)))

    def _obj_mean_e2e(self):
        e2e = []
        # Queue delay coefficients
        _q_cf = [(q + 1) * self._base_cycle for q in self._queue_iter]

        for q in self._queue_iter:
            e2e.append(
                Expr.mul(
                    _q_cf[q],
                    self._r_vars.slice(
                        [0, q, 0, 0],
                        [self._flow_count, q + 1, self._device_count, self._device_count],
                    )
                )
            )

        return Expr.mul(
            1/self._flow_count,
            Expr.sum(Expr.vstack(e2e))
        )


    def _gen_constraints(self):
        """"
        Call all constraints for the model
        """
        self._cons_src_dest()
        self._cons_switch_traffic()
        self._cons_bandwidth()
        self._cons_aux_vars()
        # self._cons_deadline()
        self._cons_non_edges()

    def _build_obj_func(self, *args):
        """Build objective function.
        This can ideally be a Multi-objective function

        Returns:
            tuple: Obj. name, Obj. funct.
        """
        return "Mean End-to-End delay", self._obj_mean_e2e()

    def solve(self, verbose, write_tt, write_out):
        """Feed model to solver and generate solution

        Args:
            verbose (_type_): output solver details on console
            write_tt (_type_): write .PTF file
            write_out (_type_): write .CSV solution file
        """
        sol_args = (write_tt, write_out)

        self._gen_constraints()

        obj_name, obj_func = self._build_obj_func()

        self._model.objective(
            obj_name,
            ObjectiveSense.Minimize,
            obj_func
        )

        if verbose:
            self._model.setLogHandler(sys.stdout)

        print(Fore.YELLOW + "\nOptimizing..." + Style.RESET_ALL)
        self._model.solve()
        self._model.acceptedSolutionStatus(AccSolutionStatus.Optimal)

        return self.__get_solution(*sol_args)

    def __get_solution(self, write_tt, write_out):
        """Get the solution for the model

        Args:
            write_tt (bool): Write OPF and PTF task files
            write_out (bool): Write solution to .csv files

        Returns:
            Solution: Solution object
        """

        if write_tt:
            print(Fore.BLUE + "Writing model to task files..." + Style.RESET_ALL)
            create_folder(OUTPUT_FOLDER_NAME)

            self._model.writeTask(f"{OUTPUT_FOLDER_NAME}/{self._output_name}.ptf")
            self._model.writeTask(f"{OUTPUT_FOLDER_NAME}/{self._output_name}.opf")

        try:
            _sstatus = self._model.getProblemStatus()
            self.runtime = _stime = self._model.getSolverDoubleInfo("optimizerTime"),
            _siterations = self._model.getSolverIntInfo("intpntIter"),
            _svalue = self._model.getSolverDoubleInfo("mioObjInt")

            if _sstatus in (ProblemStatus.PrimalFeasible,
                            ProblemStatus.DualFeasible):
                print(Fore.GREEN + "Solution found!" + Style.RESET_ALL)
                print(
                    f"\nProblem status: {_sstatus}\nSolver Time: {_stime[0]}\nIterations: {_siterations[0]}\nObjective Value: {_svalue}\n"
                )

            return self._fmt_solution(write_out)

        except OptimizeError as e:
            print(Fore.RED + f"Optimization failed. Error: {e}" + Style.RESET_ALL)
            sys.exit(1)

        except SolutionError as e:
            _sstatus = self._model.getProblemStatus()

            print(Fore.RED + "Solution was not available." + Style.RESET_ALL)

            if _sstatus == ProblemStatus.DualInfeasible:
                print(Fore.RED + "Dual infeasibility certificate found." + Style.RESET_ALL)
                raise e
                
            elif _sstatus == ProblemStatus.PrimalInfeasible:
                print(Fore.RED + "Primal infeasibility certificate found." + Style.RESET_ALL)
                raise e

            elif _sstatus == ProblemStatus.Unknown:
                _optres = self._model.getSolverIntInfo("optimizeResponse")
                symname, desc = mosek.Env.getcodedesc(
                    mosek.rescode(int(_optres)))

                print(Fore.RED + "The solution status is unknown." + Style.RESET_ALL)
                print(Fore.RED + f"Termination code: {symname} {desc}" + Style.RESET_ALL)
                raise e
            else:
                print(Fore.RED + f"Another unexpected problem status {_sstatus} is obtained." + Style.RESET_ALL)
                raise e

        except Exception as e:
            print(Fore.RED + f"Unexpected error: {e}" + Style.RESET_ALL)
            raise e

    def __sort_result(self, flow, dom):
        """Sort the path solution for the given flow

        Args:
            flow (_type_): the flow
            dom (_type_): the path solution for the flow

        Returns:
            _type_: A list of tuple, representing the edge coordinates and bandwidth for every edge
        """
        n = self._dev_uids
        _src = n[flow.source]
        _dest = n[flow.destination]
        nxt = _src
        srt_path = []

        # aviod inf.
        _scr_count = 0

        while nxt != _dest:
            for r in dom:
                if nxt == r[2]:
                    nxt = r[3]
                    srt_path.append(r)
                    _scr_count = 0
                else:
                    _scr_count += 1

            if _scr_count > len(dom):
                raise Exception("Solution found, but could not construct flow's path.")

        return srt_path

    def _fmt_solution(self, write_out=False):
        """Format the solution, generating the output for both the flow route and link bandwidth utilization

        Args:
            r_sol (list): the solver's solution for flow path variables
            b_sol (list): the solver's solution for bandwidth variables
        """

        r_sol = []
        # Bandwidth utilization: e#: (bandwidth, streams transmitted count)
        b_sol = {edg: (0, 0) for _, edg in self._edg_gids.items()}
        accounted = set() # accounted edges, avoid adding the same edge value data twice
        solution = Solution()

        # Extract vars. values from solver
        for m in self._flow_iter:
            for q in self._queue_iter:
                for d in self._dev_iter:
                    for e in self._dev_iter:
                        _r_pos = [m, q, d, e]
                        _rval = self._r_vars.index(_r_pos).level()
                        _bval = self._b_vars.index(d, e).level()

                        if _rval > 1e-4:
                            r_sol.append(_r_pos)
                            # key is edge and value is bandwidth util.
                            edge = self._edg_gids[(d, e)]

                            # Avoid duplicates
                            if edge not in accounted:
                                bandwidth, t_count = b_sol[edge]
                                t_count += 1
                                bandwidth += _bval[0]
                                b_sol[edge] = (bandwidth, t_count)
                                accounted.add(edge)

        dl = self._dev_labels

        # OUTPUT

        # TCFileame-TrafficShaper-Algorithm-Flows.csv
        _flow_f_name = f"{self._output_name}-IP-Flows.csv"
        # File header
        _flow_out = "FlowName,MaxE2E(us),Deadline(us),Path(SourceName|LinkID|priorityGroup|QNumber\n"

        # Construct flow path for all flows
        for m in self._flows:
            # all values for this flow
            _r = [s for s in r_sol if s[0] == m.uid]
            r_srtd = self.__sort_result(m, _r)

            f_name = m.name
            f_deadline = m.deadline
            p_path = ""
            max_e2e = 0
            r_path = []  # path in tuples

            # Flow's traveled path
            for r in r_srtd:
                q = r[1] + 1  # queue index starts from 0
                isrc = r[2]
                idst = r[3]
                src = dl[isrc]
                dst = dl[idst]

                # Edge ID
                e_name = self._edg_gids[(isrc, idst)]
                tf = 1 if self._traffic_type == TrafficType.CSQF.name else m.priority
                max_e2e += q * self._base_cycle

                # output string
                # queue # is 1-indexed
                r_path.append((src, e_name, tf, q))
                p_path += f"{src}|{e_name}|{tf}|{q}-"

            p_path += f"{dst}"
            _flow_out += f"{m.name}, {max_e2e}, {f_deadline}, {p_path}\n"
            solution.add_flow({f_name: (max_e2e, f_deadline, p_path, r_path)})

        # TCFileame-TrafficShaper-Algorithm-Topo.csv
        _topo_f_name = f"{self._output_name}-IP-Topo.csv"
        # File Header
        _topo_out = "EdgeID,maxBW(Kbps),MeanBW(Kbps),MeanLU(%)\n"

        # BW is the aux. var. for bandwidth util.
        for edge, data in b_sol.items():
            bw_mb, t_count = data # bw, originally in megabits
            bw_kb = bw_mb * 1000

            max_bw = bw_kb
            mean_bw = bw_mb / t_count / self._link_speed if t_count else 0
            mean_util = bw_mb / t_count / self._link_speed * 100 if t_count else 0

            _topo_out += f"{edge}, {max_bw}, {mean_bw}, {mean_util}%\n"
            solution.add_edge({edge: (max_bw, mean_bw, mean_util)})

        print("\n# Solution #\n")
        print(_flow_out)
        print(_topo_out)

        if write_out:
            print(Fore.BLUE + f"Writing solution .csv files to /{OUTPUT_FOLDER_NAME}..."  + Style.RESET_ALL)
            write_solution(_flow_f_name, _flow_out)
            write_solution(_topo_f_name, _topo_out)

        return solution
