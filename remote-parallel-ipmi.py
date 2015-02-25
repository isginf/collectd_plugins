#!/usr/bin/python
#
# Spawn a few threads to collect IPMI data from a cluster
#
# Programmed by <bastian.ballmann@inf.ethz.ch>
#

###[ Loading modules ]###

import sys
import commands
from random import randint
from time import sleep, time
from multiprocessing import Process, Queue


###[ Configuration ]###

interval = 10                                   # polling interval in seconds
nr_of_threads = 10                              # nr of threads to spawn
sensor_cmd = "ipmi-sensors -u admin -a NONE"    # cmd to exec without -h host
interessting_data = [                           # List of names we are interessted in
    "CPU1",
    "CPU2"
]


###[ Subroutines ]###

def get_sensor_data(work_queue, result_queue):
    """
    Collect IPMI data, parse it and return it in Collectd input format
    """
    while 1:
        while work_queue.qsize():
            host = work_queue.get()
            output = commands.getoutput(sensor_cmd + " -h " + host)
            result = ""
            results = []

            for data in output.split("\n"):
                try:
                    # 5968: CPU2 DIMM7 (Temperature): 30.50 C (NA/87.00): [OK]
                    sensor = data.split(":")[1] \
                                 .split("(")[0] \
                                 .rstrip(" ") \
                                 .strip(" ") \
                                 .replace(" ", "_")

                    if sensor not in interessting_data:
                        continue

                    value = data.split(":")[2] \
                                .split(" ")[1]

                    try:
                        float(value)
                    except ValueError:
                        value="U"

                    result = "PUTVAL \"" + host + "/remote_ipmi/" + sensor + "\" interval=10 N:" + value
                except IndexError:
                    pass

                results.append(result)
                result_queue.put([host,results])
        sleep(randint(1, interval/2))


###[ MAIN PART ]###

hosts = sys.argv[1:]
work_queue = Queue()
result_queue = Queue()

# Spawn threads
if nr_of_threads > len(hosts):
    nr_of_threads = len(hosts)

for i in range(nr_of_threads):
    worker = Process(target=get_sensor_data, args=(work_queue,result_queue))
    worker.start()

while 1:
    start_time = time()
    results = {}

    # Push all hosts in work queue
    for host in hosts:
        work_queue.put(host)

    # wait until we got a result for all hosts
    while len(results.keys()) < len(hosts):
        data = result_queue.get()
        results[data[0]] = data[1]

    # feed collectd
    for host, data in results.items():
        for result in data:
            if result:
                print result

    # Calc exeeded time and wait if we have some time to loose
    time_exceeded = time() - start_time

    if time_exceeded < interval:
        sleep(interval-time_exceeded)
