## Integer TSN

This is the **public** version of a project, part of a Computer Science and Engineering Master's Thesis at the Technical University of Denmark. In the given context, the author models an Integer Linear Problem to schedule stream assignments in latency-bounded networks. The program model implements two traffic shapers from IEEE 802.1 TSN, CSQF and Multi-CQF.

In this version of the repository, this project lacks the test cases. They are copywrited and cannot be distributed. The user will need to create them manually.

## Abstract

## Routing and Queue Assignment in Time-Sensitive Networks For CSQF & Multi-CQF Traffic

In recent years, advancements in network technology allowed companies and products to improve at scale paces never seen before. From cutting-edge advanced production lines to LIDAR-based autonomous vehicles, these industries have pushed the demand for network protocols that can provide real Quality-of-Service guarantees. Although traditional Internet Protocol (IP) services provide some solutions, performance is still statistical. Furthermore, existing scalable solutions are proprietary and expensive.

For this reason, the IEEE Time-Sensitive Network task group (IEEE 802.1 WG) has worked on a set real-time and safety-critical protocols to meet the traffic demand some industries have created. Its objective is propose a set of standards for network traffic in latency-bounded networks. Furthermore, these standards can objectively simplify network hardware and become the de-facto protocol in latency-sensitive networks with tight QoS guarantees.

# Interface & Libraries

## Requirements

A MOSEK® license is required to run this program. Therefore, before continuing, you must obain an Academic or Trial License at https://www.mosek.com/. In the email you will receive, you will find the instructions for the license installation.

Navigate to the root folder of the project and install the required libraries for this project with `pipenv sync`. This will install the files and load the environment. In the future, to activate the environment for this project, simply run `pipenv shell` in the root folder. 

Alternatively, you can also use pip to install from `requirements.txt`.

## Commandline Interface

Listing all options:

```
python main.py --help
```

Adding solver verbosity to output:

```
python main.py <ARGS> --verbose
```

*Base cycle length* and *link speed* are optinal arguments, having default values `10` and `1000`, respectively:

```
python main.py <ARGS> --cycle-length 20 --link-speed 1000
```

MCQF model:

```
python main.py cases/test/4sw.proto/ -mcqf --switch-config cases/test/4sw.proto/config.csv
```

CSQF model:

```
python main.py cases/test/4sw.proto/ -csqf --cycle-length 20 --link-speed 1000
```

`-wt` or `--write-task-files` outputs the model to `output/<case_name>.ptf` and `output/<case_name>.opf` files. These task files are useful for benchmarking and debugging.

```
python main.py cases/test/4sw.proto/ -csqf --write-task-file
```

`-ws` or `--write-solution` will write the solution to `output/<case_name>_*.csv`. Omitting this argument will output the results to `stdout`.

```
python main.py cases/test/4sw.proto/ -csqf --write-solution
```

#

Author: Elvis Antônio Ferreira Camilo (s190395 at student.dtu.dk)

Supervisor: Paul Pop (paupo at dtu.dk)
