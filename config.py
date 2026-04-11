"""
config.py - Network and node configuration for the blockchain simulator.

Edit NODE_PEERS to list all nodes in your WiFi network.
Each entry is a base URL: "http://<phone-ip>:<port>"
"""

# ---------------------------------------------------------------------------
# Node identity (overridden at runtime by CLI flags in node.py)
# ---------------------------------------------------------------------------
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 5001
NODE_ID = None  # auto-generated from host:port if not set

# ---------------------------------------------------------------------------
# Proof-of-Authority (PoA) parameters
#
# AUTHORIZED_VALIDATORS is the explicit allow-list of node IDs permitted to
# forge blocks.  Add the node_id of every trusted node here.
# The validator for each block is chosen by round-robin:
#   validator = AUTHORIZED_VALIDATORS[block_index % len(AUTHORIZED_VALIDATORS)]
# ---------------------------------------------------------------------------
TRANSACTIONS_PER_BLOCK = 5          # mempool depth that triggers block creation
GENESIS_SENDER = "GENESIS"          # special address for the genesis block

# Pre-registered validator node IDs.
# When running locally with run_network.py the default IDs are node1..node4.
# On real phones, set --node-id on each device and add that ID here.
AUTHORIZED_VALIDATORS: list[str] = [
    "node1",
    "node2",
    "node3",
    "node4",
]

# ---------------------------------------------------------------------------
# Network peers
# Populate with the actual IPs of the other phones on the same WiFi.
# Each phone should list all *other* phones here (not itself).
# ---------------------------------------------------------------------------
NODE_PEERS: list[str] = [
    # "http://192.168.1.101:5001",
    # "http://192.168.1.102:5002",
    # "http://192.168.1.103:5003",
    # "http://192.168.1.104:5004",
]

# ---------------------------------------------------------------------------
# Timing / consensus
# ---------------------------------------------------------------------------
SYNC_INTERVAL_SECONDS = 30   # how often a node checks peer chain lengths
REQUEST_TIMEOUT_SECONDS = 5  # HTTP request timeout

# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------
BLOCKCHAIN_FILE = "blockchain_data.json"  # local ledger storage path
