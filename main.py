import argparse, sys, os, time, platform

from bin.constants import (
    CSQF_QUEUE_COUNT,
)
from solvers.mosek.csqf import Csqf
from solvers.mosek.mcqf import MultiCqf
from bin.io.topo import (
    parse_switch_conf,
    parse_topo,
    parse_flows,
    read_file
)
from bin.classes import (
    McqfSwitchConfiguration,
    Network,
    SwitchConfiguration
)
from colorama import (
    Fore,
    Style
)


def intro():
    PRESENTATION = """
    ###############################################################
    ##                                                           ##
    ##           88888888888  .d8888b.  888b    888              ##
    ##               888     d88P  Y88b 8888b   888              ##
    ##               888     Y88b.      88888b  888              ##
    ##               888      "Y888b.   888Y88b 888              ##
    ##               888         "Y88b. 888 Y88b888              ##
    ##               888           "888 888  Y88888              ##
    ##               888     Y88b  d88P 888   Y8888              ##
    ##               888      "Y8888P"  888    Y888              ##
    ##                                                           ##
    ##                                                           ##
    ##              TECHNICAL UNIVERSITY OF DENMARK              ##
    ##     DEPT. OF APPLIED MATHEMATICS AND COMPUTER SCIENCE     ##
    ##                                                           ##
    ##                   MASTER THESIS PROJECT                   ##
    ##                                                           ##
    ##  ROUTING AND QUEUE ASSIGNMENT IN TIME-SENSITIVE NETWORKS  ##
    ##               FOR CSQF && MULTI-CQF TRAFFIC               ##
    ##                                                           ##
    ##                                                           ##
    ##          ELVIS ANTÔNIO FERREIRA CAMILO - S190395          ##
    ##                  s190395@student.dtu.dk                   ##
    ##                                                           ##
    ##                         JUNE 2022                         ##
    ###############################################################
    """
    print(Fore.RED + f"{PRESENTATION}" + Style.RESET_ALL)

def parse_args():
    """
    Parse given arguments.
    """

    parser = argparse.ArgumentParser(
        description="Mixed Integer Linear models for CSQF and MCQF traffic schedule in Time-Sensitive Network."
    )

    # Main parser arguments
    parser.add_argument(
        "path",
        metavar="cases_path",
        type=str,
        help="""Path with test case, i.e: ..cases/test/2sw.proto/.
        This folder should contain both flow_1s.txt and 1_topo.txt files."""
    )

    traffic_group = parser.add_mutually_exclusive_group(required=True)
    traffic_group.add_argument(
        "-csqf",
        action="store_true",
        help="Build Integer Linear Problem using CSQF traffic definitions and constraints."
    )
    traffic_group.add_argument(
        "-mcqf",
        action='store_true',
        help="Build Integer Linear Problem using Multi-CQF traffic definitions and constraints. Further optional arguments are available."
    )

    # MCQF
    gp_mcqf = parser.add_argument_group("Optional MCQF arguments")
    gp_mcqf.add_argument(
        "-sc",
        "--switch-config",
        type=str,
        help="Multi-CQF configuration file."
    )

    # Other arguments for the main parser
    parser.add_argument(
        "-cl",
        "--cycle-length",
        type=int,
        default=10,
        help="Base cycle length (in Microseconds). Default is 10 us."
    )
    parser.add_argument(
        "-ls",
        "--link-speed",
        type=int,
        default=1000,
        help="Link speed (in Mbps). Default is 1000 Mbps."
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Increase verbosity by outputting Solver's solution details."
    )
    parser.add_argument(
        "-wt",
        "--write-task-files",
        action="store_true",
        help="Write two task files, PTF and OPF, convenient for debugging and benchmarking. These files are stored in the <root>/output folder."
    )
    parser.add_argument(
        "-ws",
        "--write-solution",
        action="store_true",
        help="Write schedule traffic solution in .CSV files. These files is stored in the <root>/output folder."
    )

    args = parser.parse_args()

    if not args.path.endswith('/'):
        args.path += '/'

    if args.mcqf and not args.switch_config:
        parser.error("The --switch-config argument is required for Multi-CQF traffic")

    if args.csqf and args.switch_config:
        parser.error("The --switch-config argument is only valid for CSQF traffic")

    return args

def main(args):
    s_time = time.time()

    cases_path = args.path
    _dir = os.path.dirname(cases_path)
    # name for the model, based on case path
    _name = os.path.basename(_dir)

    # Extending file naming for parallel instances
    if platform.system() != "Windows":
        s_path = [s for s in cases_path.split("/") if s]
        path_l = len(s_path)

        if path_l >= 2:
            _name = "_".join(s_path[path_l - 2:path_l])

    print(f"Model name: {_name}")
    
    # MCQF
    if args.mcqf:
        parsed_conf = parse_switch_conf(read_file(args.switch_config))
        sw_config = McqfSwitchConfiguration(
            queue_count=parsed_conf['queue_count'],
            base_cycle=args.cycle_length,
            link_speed=args.link_speed,
            priority_groups=parsed_conf['groups']
        )
    # CSQF
    else:
        sw_config = SwitchConfiguration(
            queue_count=CSQF_QUEUE_COUNT,
            base_cycle=args.cycle_length,
            link_speed=args.link_speed
        )
    _tf = "CSQF" if args.csqf else "MCQF"
    _cl = args.cycle_length
    _ls = args.link_speed
    
    print(f"Traffic Shaper: {_tf}\nCycle Length: {_cl}\nLink Speed: {_ls}")

    # Parsing data
    topology = parse_topo(read_file(cases_path + "1_topo.txt"))
    flows = parse_flows(read_file(cases_path + "1_flows.txt"))
    network = Network(topology=topology, flows=flows, switch_conf=sw_config)
    solve_args = (args.verbose, args.write_task_files, args.write_solution)

    if args.csqf:
        msk = Csqf(_name, network)
    else:
        msk = MultiCqf(_name, network)

    t_out = "\nModel Build + Solution time (seconds):"
    try:
        msk.solve(*solve_args)
        print(Fore.BLUE + f"{t_out} {time.time() - s_time}" + Style.RESET_ALL)
    except Exception as e:
        print(Fore.BLUE + f"{t_out} {time.time() - s_time}" + Style.RESET_ALL)
        sys.exit(3)
    
    # Finished
    sys.exit()

if __name__ == "__main__":
    intro()
    main(parse_args())
