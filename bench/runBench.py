# Arguments in order: protocol, #replicas, #threads per client, #client machines
# EX: python ./bench/runBench.py unreplicated 5 1 1
# To run with batching, use protocol "batch"
import sys, string
import subprocess
import os
import threading
import time

project = "nopaxos-204404"
zone="us-west1-a"

def generateCmdStr(machine, remoteCmd):
    return ("gcloud compute --project \"%s\" ssh --zone \"%s\" \"%s\" --command \"%s\"") % (project, zone, machine, remoteCmd)

def timeout(p):
    print "timeout"
    if p.poll() is None:
        print "killing"
        p.terminate()

def runTest(protocol, numReplicas, numThreadsPerClient, numClientMachines):
    configMap = {3: "config", 5: "config-5", 7: "config-7", 9: "config-9"} # TODO: add others
    replicas = ["nopaxos-1", "nopaxos-2", "nopaxos-3", "nopaxos-04", "nopaxos-05", "nopaxos-06", "nopaxos-07", "nopaxos-08", "nopaxos-09"]
    clients = ["client", "client-2", "client-3"]
    config = configMap[numReplicas]
    sequencer = "sequencer"
    processes = []
    devNull = open(os.devnull, 'w')

    # Start sequencer for nopaxos
    if protocol == "nopaxos":
        sequencerCmd = ("sudo lsof -t -i udp:8000 | sudo xargs kill; cd /home/emmadauterman/NOPaxos; sudo ./sequencer/sequencer -C %s -c sequencer_config") % config
        process = subprocess.Popen(generateCmdStr(sequencer, sequencerCmd),
            shell=True) 
        processes.append(process)
        time.sleep(0.5)

    # Start replicas
    for i in range(0, numReplicas):
        protocolStr = protocol
        if protocol == "batch":
            protocolStr = "vr -b 100"
        replicaCmd = ("sudo lsof -t -i udp:8000 | sudo xargs kill; cd /home/emmadauterman/NOPaxos; ./bench/replica -c %s -i %d -m %s") % (config, i, protocolStr)
        process = subprocess.Popen(generateCmdStr(replicas[i], replicaCmd),
            shell=True)
        processes.append(process)
        time.sleep(0.5)

    # Start clients
    protocolStr = protocol
    if protocol == "batch":
        protocolStr = "vr"
    clientCmd = ("cd /home/emmadauterman/NOPaxos; rm output.txt; ./bench/client -t %d -c %s -m %s &> output.txt; python ./bench/combineThreadOutputs.py") % (numThreadsPerClient, config, protocolStr)
    clientProcesses = []
    timers = []
    totThroughput = 0.0
    totLatency = 0.0
    for i in reversed(range(0, numClientMachines)):
        process = subprocess.Popen(generateCmdStr(clients[i], clientCmd),
            shell=True, stdout=subprocess.PIPE)
        t = threading.Timer(300, timeout, [process])
        t.start()
        timers.append(t)
        clientProcesses.append(process)

    try:
        for i in reversed(range(0, numClientMachines)):
            output = clientProcesses[i].stdout.read()
            outputLines = output.splitlines()
            elems = outputLines[0].split(":")
            totThroughput += float(elems[1])
            elems = outputLines[1].split(":")
            totLatency += float(elems[1])
        avgLatency = totLatency / numClientMachines
    except Exception:
        totThroughput = -1
        avgLatency = -1

    # Kill replicas and sequencer.
    for process in processes :
        process.terminate()

    for t in timers:
        t.cancel()

    print ""
    print "******************************************************************"
    print ("Finished running %s with %d replicas with %d client machines each running %d threads") % (protocol, numReplicas, numClientMachines, numThreadsPerClient)
    print ("Total throughput (requests/sec): %d") % (totThroughput)
    print ("Average latency (us): %d") % (avgLatency)
    return totThroughput, avgLatency