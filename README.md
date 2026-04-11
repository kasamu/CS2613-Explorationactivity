# CS2613 Exploration Activity — Multi-Phone Blockchain Network Simulator

A distributed blockchain network where each phone (or laptop) acts as an
independent **validator node**, communicating over WiFi to create a shared
decentralized ledger using **Proof-of-Authority (PoA)** consensus and a
**FastAPI** REST server.

---

## 📂 File Structure

| File | Purpose |
|---|---|
| `blockchain.py` | `Block`, `Transaction`, and `Blockchain` classes — core data structures |
| `utils.py` | SHA-256 hashing, key generation, signing, Merkle root |
| `config.py` | Tunable parameters (block size, PoA validators, peer URLs) |
| `node_core.py` | Node logic: mempool, PoA round-robin election, broadcasting, chain sync |
| `node.py` | **FastAPI** REST server — one instance per phone (served by uvicorn) |
| `run_network.py` | Helper script to spawn multiple nodes locally for testing |
| `web_ui.html` | Browser dashboard — real-time chain, mempool, PoA status, and peers |
| `README.md` | This file |

---

## 🚀 Quick Start

### 1. Install dependencies

```bash
pip install fastapi uvicorn requests
```

> **On Android (Termux):** `pkg install python` then the same `pip install` command.

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

### 4. Edit `config.py`

Open `config.py` and:
- Set `AUTHORIZED_VALIDATORS` to the `--node-id` values you will use on each phone.
- Optionally pre-populate `NODE_PEERS` with the other phones' URLs.

```python
AUTHORIZED_VALIDATORS = ["node1", "node2", "node3", "node4"]

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

Repeat for phones C and D (ports 5003 / 5004, node-ids node3 / node4).

### 6. Open the dashboard

In any browser on the same WiFi:

```
http://192.168.1.101:5001      ← Phone A's dashboard
http://192.168.1.102:5002      ← Phone B's dashboard
```

The dashboard also shows the FastAPI auto-generated docs at `/docs`.

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

Every node exposes these endpoints (auto-documented at `/docs`):

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/transaction` | Submit / forward a transaction |
| `POST` | `/api/block` | Receive a forged block from a peer validator |
| `POST` | `/api/peer` | Register a peer node URL |
| `GET` | `/api/chain` | Full blockchain ledger (JSON) |
| `GET` | `/api/mempool` | Pending (unconfirmed) transactions |
| `GET` | `/api/peers` | List of connected peers |
| `GET` | `/api/node-info` | Node identity, PoA status, balance |
| `GET` | `/` | Web dashboard |
| `GET` | `/docs` | Interactive Swagger UI (FastAPI built-in) |

### Example: submit a transaction with `curl`

```bash
# The node signs the transaction from its own wallet
curl -X POST http://127.0.0.1:5001/api/transaction \
  -H "Content-Type: application/json" \
  -d '{"recipient":"<64-hex-address>","amount":10}'
```

---

## 🎯 Consensus Mechanism — Proof of Authority (PoA)

1. **`AUTHORIZED_VALIDATORS`** in `config.py` is the explicit allow-list of
   node IDs that may forge blocks.  Only these nodes are trusted.
2. When the mempool reaches **`TRANSACTIONS_PER_BLOCK`** (default 5) transactions,
   a block forging is triggered.
3. The **round-robin** turn order is fully deterministic:
   ```
   validator = AUTHORIZED_VALIDATORS[next_block_index % len(AUTHORIZED_VALIDATORS)]
   ```
   All nodes with the same chain always agree on whose turn it is — no
   randomness, no stake weighting.
4. The elected node forges a block and **broadcasts** it to all peers.
5. Peers validate the block (hash integrity + PoA authority check) and append it.
6. **Fork resolution** uses the longest-chain rule: if a peer's chain is
   longer and fully valid, the local chain is replaced.
7. Blocks from unauthorised nodes are **rejected**.

### Why PoA instead of PoS?

| | PoS | PoA |
|---|---|---|
| Who can validate? | Anyone with stake | Pre-approved list only |
| Turn order | Probabilistic (weighted random) | Deterministic (round-robin) |
| Trust model | Economic incentives | Identity / reputation |
| Good for | Public blockchains | Permissioned / private networks |

---

## 🔑 Cryptography

- Keys are deterministically derived with SHA-256 (educational simulator).
- Transactions are signed with a SHA-256 scheme.
- Block integrity is verified by recomputing the block hash.
- A Merkle root is stored in each block for transaction integrity.

> In a production blockchain you would use asymmetric keys (e.g. ECDSA /
> secp256k1).  The symmetric scheme here is intentional simplification for
> learning purposes.

---

## ⚙️ Configuration (`config.py`)

| Parameter | Default | Description |
|---|---|---|
| `AUTHORIZED_VALIDATORS` | `["node1","node2","node3","node4"]` | PoA allow-list of node IDs |
| `TRANSACTIONS_PER_BLOCK` | `5` | Mempool depth that triggers block creation |
| `SYNC_INTERVAL_SECONDS` | `30` | How often nodes poll peers for a longer chain |
| `REQUEST_TIMEOUT_SECONDS` | `5` | HTTP timeout for peer requests |

---

## ✅ Success Criteria

- ✅ 4 phones connect over WiFi and discover each other
- ✅ Transaction created on one node broadcasts to all peers
- ✅ Block forged by the PoA turn-holder validates on all nodes
- ✅ Unauthorised nodes cannot forge blocks
- ✅ All nodes maintain identical blockchain after sync
- ✅ Consensus mechanism prevents double-spending (balance check)
- ✅ Web dashboard shows real-time chain, mempool, PoA status, and peers

---

## 📚 What You Learn

| Topic | Concept |
|---|---|
| Distributed systems | Each node is independent; consensus is needed for agreement |
| P2P networking | REST over WiFi; broadcast to all peers |
| Cryptography | Hashing, signing, Merkle trees |
| Consensus algorithms | PoA round-robin, longest-chain fork resolution |
| Permissioned blockchains | Authority lists vs. open participation |
| FastAPI / uvicorn | Modern async Python web framework and ASGI server |
| Blockchain data structures | Linked blocks, transactions, balance ledger |
