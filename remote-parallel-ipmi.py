#!/usr/bin/python3
#
# Spawn a few processes to collect IPMI data from a cluster
#
# Copyright 2017 ETH Zurich, ISGINF, Bastian Ballmann
# E-Mail: bastian.ballmann@inf.ethz.ch
# Web: http://www.isg.inf.ethz.ch
#
# This is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# It is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License.
# If not, see <http://www.gnu.org/licenses/>.

###[ Loading modules ]###

import sys
import subprocess
from random import randint
from time import sleep, time
from signal import signal, SIGINT
from multiprocessing import Process, Queue


###[ Configuration ]###

interval = 10                                   # polling interval in seconds
nr_of_threads = 10                              # nr of threads to spawn
sensor_cmd = "ipmi-sensors -u admin -a NONE"    # cmd to exec without -h host
interessting_data = [                           # List of names we are interessted in
    "CPU1",
    "CPU2"
]
processes = []


#
# SIGNAL HANDLERS
#

def clean_shutdown(signal, frame):
    for process in processes:
        process.terminate()

signal(SIGINT, clean_shutdown)


###[ Subroutines ]###

def get_sensor_data(work_queue, result_queue):
    """
    Collect IPMI data, parse it and return it in Collectd input format
    """
    while 1:
        while not work_queue.empty():
            host = work_queue.get()
            output = subprocess.getoutput(sensor_cmd + " -h " + host)
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
    processes.append(worker)
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
                print(result)

    # Calc exeeded time and wait if we have some time to loose
    time_exceeded = time() - start_time

    if time_exceeded < interval:
        sleep(interval-time_exceeded)
