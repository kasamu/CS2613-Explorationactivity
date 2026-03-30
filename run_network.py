"""
run_network.py - Launch multiple blockchain nodes on the local machine.

Useful for local testing before deploying to real phones.
By default spawns 4 nodes on ports 5001-5004.

Usage:
    python run_network.py              # spawn 4 nodes
    python run_network.py --nodes 2   # spawn 2 nodes
    python run_network.py --kill      # kill all spawned nodes
"""
from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import tempfile
import time

BASE_PORT = 5001
DEFAULT_NODE_COUNT = 4
PID_FILE = os.path.join(tempfile.gettempdir(), "blockchain_nodes.pids")


def get_peer_urls(count: int, base_port: int = BASE_PORT) -> list[str]:
    return [f"http://127.0.0.1:{base_port + i}" for i in range(count)]


def spawn_nodes(count: int) -> list[subprocess.Popen]:
    all_urls = get_peer_urls(count)
    processes: list[subprocess.Popen] = []
    pids: list[int] = []

    python = sys.executable
    node_script = os.path.join(os.path.dirname(__file__), "node.py")

    for i in range(count):
        port = BASE_PORT + i
        node_id = f"node{i + 1}"
        # Each node gets all *other* nodes as peers
        peers = [url for j, url in enumerate(all_urls) if j != i]

        cmd = [
            python, node_script,
            "--host", "127.0.0.1",
            "--port", str(port),
            "--node-id", node_id,
            "--peers", *peers,
        ]

        log_file = open(
            os.path.join(tempfile.gettempdir(), f"node_{node_id}.log"), "w"
        )
        proc = subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=log_file,
        )
        processes.append(proc)
        pids.append(proc.pid)
        print(f"  ✅ Started {node_id} on port {port}  (PID {proc.pid})")
        time.sleep(0.5)  # small stagger so ports don't race

    # Save PIDs for later cleanup
    with open(PID_FILE, "w") as f:
        f.write("\n".join(str(p) for p in pids))

    return processes


def kill_nodes() -> None:
    if not os.path.exists(PID_FILE):
        print("No PID file found. Are any nodes running?")
        return
    with open(PID_FILE) as f:
        pids = [int(line.strip()) for line in f if line.strip()]
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
            print(f"  🛑 Killed PID {pid}")
        except ProcessLookupError:
            print(f"  ⚠️  PID {pid} not found (already exited?)")
    os.remove(PID_FILE)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run multiple blockchain nodes locally")
    parser.add_argument("--nodes", type=int, default=DEFAULT_NODE_COUNT,
                        help="Number of nodes to spawn")
    parser.add_argument("--kill", action="store_true",
                        help="Kill all previously spawned nodes")
    args = parser.parse_args()

    if args.kill:
        print("Stopping all blockchain nodes …")
        kill_nodes()
        return

    print(f"\n🚀 Starting {args.nodes} blockchain nodes (ports {BASE_PORT}–{BASE_PORT + args.nodes - 1})\n")
    processes = spawn_nodes(args.nodes)

    print(f"\n📡 Network running! Access dashboards at:")
    for i in range(args.nodes):
        print(f"   Node {i + 1}: http://127.0.0.1:{BASE_PORT + i}")

    print("\nPress Ctrl+C to stop all nodes.\n")

    try:
        while True:
            # Check that processes are still alive
            for proc in processes:
                if proc.poll() is not None:
                    print(f"  ⚠️  Process {proc.pid} exited with code {proc.returncode}")
            time.sleep(5)
    except KeyboardInterrupt:
        print("\nShutting down …")
        for proc in processes:
            proc.terminate()
        print("All nodes stopped.")


if __name__ == "__main__":
    main()
