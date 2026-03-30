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
# Proof-of-Stake parameters
# ---------------------------------------------------------------------------
TRANSACTIONS_PER_BLOCK = 5          # validator elected every N transactions
INITIAL_STAKE = 100                 # starting stake for every node
BLOCK_REWARD = 10                   # tokens awarded to the block creator
GENESIS_SENDER = "GENESIS"          # special address for genesis block

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

# ---------------------------------------------------------------------------
# Flask server settings
# ---------------------------------------------------------------------------
DEBUG = False
THREADED = True
