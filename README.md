# CS2613 Exploration Activity — Multi-Phone Blockchain Network Simulator

A distributed blockchain network where each phone (or laptop) acts as an
independent **validator node**, communicating over WiFi to create a shared
decentralized ledger using a simplified **Proof-of-Stake (PoS)** consensus
mechanism.

---

## 📂 File Structure

| File | Purpose |
|---|---|
| `blockchain.py` | `Block`, `Transaction`, and `Blockchain` classes — core data structures |
| `utils.py` | SHA-256 hashing, key generation, signing, Merkle root |
| `config.py` | Tunable parameters (ports, stake, block size, peer URLs) |
| `node_core.py` | Node logic: mempool, PoS election, broadcasting, chain sync |
| `node.py` | Flask REST API server — one instance per phone |
| `run_network.py` | Helper script to spawn multiple nodes locally for testing |
| `web_ui.html` | Browser dashboard — real-time chain, mempool, and peers |
| `README.md` | This file |

---

## 🚀 Quick Start

### 1. Install dependencies

```bash
pip install flask requests
```

> **On Android (Termux):** `pkg install python` then `pip install flask requests`

### 2. Clone the repo on every phone

```bash
git clone https://github.com/kasamu/CS2613-Explorationactivity.git
cd CS2613-Explorationactivity
```

### 3. Find each phone's WiFi IP

```bash
# macOS / Linux
ip route get 1 | awk '{print $7}'

# Android (Termux)
ip addr show wlan0
```

### 4. Edit `config.py` (optional)

Open `config.py` and add the other phones' URLs to `NODE_PEERS`:

```python
NODE_PEERS = [
    "http://192.168.1.101:5001",
    "http://192.168.1.102:5002",
    "http://192.168.1.103:5003",
    "http://192.168.1.104:5004",
]
```

### 5. Start each node

On **Phone A** (IP 192.168.1.101):

```bash
python node.py --port 5001 --node-id node1 \
  --peers http://192.168.1.102:5002 http://192.168.1.103:5003 http://192.168.1.104:5004
```

On **Phone B** (IP 192.168.1.102):

```bash
python node.py --port 5002 --node-id node2 \
  --peers http://192.168.1.101:5001 http://192.168.1.103:5003 http://192.168.1.104:5004
```

Repeat for phones C and D (ports 5003 / 5004).

### 6. Open the dashboard

In any browser on the same WiFi:

```
http://192.168.1.101:5001      ← Phone A's dashboard
http://192.168.1.102:5002      ← Phone B's dashboard
```

---

## 💻 Local Testing (single machine)

Spawn 4 nodes automatically:

```bash
python run_network.py           # starts nodes on ports 5001–5004
python run_network.py --nodes 2 # just 2 nodes
python run_network.py --kill    # stop all nodes
```

Then open `http://127.0.0.1:5001` through `http://127.0.0.1:5004`.

---

## 📡 REST API Reference

Every node exposes these endpoints:

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/transaction` | Submit / forward a transaction |
| `POST` | `/api/block` | Receive a validated block from a peer |
| `POST` | `/api/peer` | Register a peer node URL |
| `GET` | `/api/chain` | Full blockchain ledger (JSON) |
| `GET` | `/api/mempool` | Pending (unconfirmed) transactions |
| `GET` | `/api/peers` | List of connected peers |
| `GET` | `/api/node-info` | Node identity, stake, balance |
| `GET` | `/` | Web dashboard |

### Example: submit a transaction with `curl`

```bash
# Let the node sign the transaction itself (sender = node's own address)
curl -X POST http://127.0.0.1:5001/api/transaction \
  -H "Content-Type: application/json" \
  -d '{"recipient":"<64-hex-address>","amount":10}'
```

---

## 🎯 Consensus Mechanism (Simplified PoS)

1. Every **5 transactions** accumulated in the mempool trigger a validator
   election.
2. The validator is selected **weighted-randomly** by stake (all nodes start
   with `INITIAL_STAKE = 100`).
3. The elected node forges a block and **broadcasts** it to all peers.
4. Peers validate and append the block; the validator earns a
   `BLOCK_REWARD = 10` stake increase.
5. **Fork resolution** uses the longest-chain rule: if a peer's chain is
   longer and valid, the local chain is replaced.

---

## 🔑 Cryptography

- Keys are deterministically derived with SHA-256 (educational simulator).
- Transactions are signed with an HMAC-SHA256 scheme.
- Block integrity is verified by recomputing the block hash.
- A Merkle root is stored in each block for transaction integrity.

> In a production blockchain you would use asymmetric keys (e.g. ECDSA /
> secp256k1).  The symmetric scheme here is intentional simplification for
> learning purposes.

---

## ⚙️ Configuration (`config.py`)

| Parameter | Default | Description |
|---|---|---|
| `TRANSACTIONS_PER_BLOCK` | `5` | Mempool size that triggers block creation |
| `INITIAL_STAKE` | `100` | Starting stake for every node |
| `BLOCK_REWARD` | `10` | Stake bonus for the block creator |
| `SYNC_INTERVAL_SECONDS` | `30` | How often nodes poll peers for a longer chain |
| `REQUEST_TIMEOUT_SECONDS` | `5` | HTTP timeout for peer requests |

---

## ✅ Success Criteria

- ✅ 4 phones connect over WiFi and discover each other
- ✅ Transaction created on one node broadcasts to all peers
- ✅ Block created by the elected validator validates on all nodes
- ✅ All nodes maintain identical blockchain after sync
- ✅ Consensus mechanism prevents double-spending (balance check)
- ✅ Web dashboard shows real-time chain, mempool, and peer state

---

## 📚 What You Learn

| Topic | Concept |
|---|---|
| Distributed systems | Each node is independent; consensus is needed for agreement |
| P2P networking | REST over WiFi; broadcast to all peers |
| Cryptography | Hashing, signing, Merkle trees |
| Consensus algorithms | PoS validator election, longest-chain fork resolution |
| Blockchain data structures | Linked blocks, transactions, UTXO-style balances |
