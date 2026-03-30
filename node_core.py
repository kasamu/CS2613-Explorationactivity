"""
node_core.py - Core blockchain node logic.

Manages blockchain state, peer list, PoS validator selection,
transaction broadcasting, and block forging/propagation.
"""
from __future__ import annotations

import logging
import os
import threading
from typing import Any

import requests

from blockchain import Block, Blockchain, Transaction
from config import (
    BLOCK_REWARD,
    BLOCKCHAIN_FILE,
    INITIAL_STAKE,
    REQUEST_TIMEOUT_SECONDS,
    TRANSACTIONS_PER_BLOCK,
)
from utils import current_timestamp, generate_keypair, generate_node_id

logger = logging.getLogger(__name__)


class NodeCore:
    """
    The heart of a blockchain node.

    Responsibilities:
    - Own identity (node_id, keys, stake)
    - Maintain blockchain + mempool
    - Track peers
    - Broadcast transactions and blocks
    - PoS validator selection
    - Chain synchronisation
    """

    def __init__(self, host: str, port: int, node_id: str | None = None) -> None:
        self.host = host
        self.port = port
        self.node_id = node_id or generate_node_id(host, port)
        self.private_key, self.public_key = generate_keypair(self.node_id)
        self.address = self.public_key  # this node's wallet address

        self.blockchain = self._load_or_create_blockchain()
        self.peers: list[str] = []  # list of peer base-URLs
        self._lock = threading.Lock()

        logger.info(
            "NodeCore initialised: id=%s address=%s port=%d",
            self.node_id,
            self.address[:16],
            self.port,
        )

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _load_or_create_blockchain(self) -> Blockchain:
        path = self._data_path()
        if os.path.exists(path):
            try:
                bc = Blockchain.load(path)
                logger.info("Loaded blockchain from %s (height=%d)", path, bc.height)
                return bc
            except Exception as exc:
                logger.warning("Could not load blockchain (%s) – starting fresh", exc)
        return Blockchain()

    def _data_path(self) -> str:
        """Unique data file per node so multiple nodes can coexist locally."""
        return f"{self.node_id[:8]}_{BLOCKCHAIN_FILE}"

    def save(self) -> None:
        with self._lock:
            self.blockchain.save(self._data_path())

    # ------------------------------------------------------------------
    # Peer management
    # ------------------------------------------------------------------
    def add_peer(self, peer_url: str) -> tuple[bool, str]:
        """Add a peer URL (e.g. 'http://192.168.1.5:5002')."""
        peer_url = peer_url.rstrip("/")
        my_url = f"http://{self.host}:{self.port}"
        if peer_url == my_url:
            return False, "Cannot add self as peer"
        if peer_url in self.peers:
            return False, "Peer already registered"
        self.peers.append(peer_url)
        logger.info("Added peer: %s", peer_url)
        return True, "Peer added"

    def get_peers(self) -> list[str]:
        return list(self.peers)

    # ------------------------------------------------------------------
    # Node info
    # ------------------------------------------------------------------
    def node_info(self) -> dict:
        return {
            "node_id": self.node_id,
            "address": self.address,
            "host": self.host,
            "port": self.port,
            "chain_height": self.blockchain.height,
            "mempool_size": len(self.blockchain.mempool),
            "peers": self.peers,
            "stake": self.blockchain.get_stake(self.node_id),
            "balance": self.blockchain.get_balance(self.address),
            "timestamp": current_timestamp(),
        }

    # ------------------------------------------------------------------
    # Transaction handling
    # ------------------------------------------------------------------
    def create_transaction(self, recipient: str, amount: float) -> dict:
        """
        Create a signed transaction from this node's wallet and broadcast it.
        """
        tx = Transaction(
            sender=self.address,
            recipient=recipient,
            amount=amount,
            private_key=self.private_key,
        )
        ok, msg = self.blockchain.add_to_mempool(tx)
        if not ok:
            return {"success": False, "message": msg}

        self._broadcast_transaction(tx)
        self._maybe_forge_block()
        return {"success": True, "tx_id": tx.tx_id, "message": msg}

    def receive_transaction(self, tx_data: dict) -> tuple[bool, str]:
        """
        Accept a transaction forwarded by a peer.
        Returns (accepted, message).
        """
        try:
            tx = Transaction.from_dict(tx_data)
        except (KeyError, ValueError) as exc:
            return False, f"Malformed transaction: {exc}"

        ok, msg = self.blockchain.add_to_mempool(tx)
        if ok:
            self._maybe_forge_block()
        return ok, msg

    def _broadcast_transaction(self, tx: Transaction) -> None:
        """Send the transaction to all known peers."""
        self._broadcast_post("/api/transaction", tx.to_dict())

    # ------------------------------------------------------------------
    # Block handling
    # ------------------------------------------------------------------
    def receive_block(self, block_data: dict) -> tuple[bool, str]:
        """
        Accept a block from a peer validator.
        """
        try:
            block = Block.from_dict(block_data)
        except (KeyError, ValueError) as exc:
            return False, f"Malformed block: {exc}"

        with self._lock:
            ok, msg = self.blockchain.add_block(block)
        if ok:
            self.save()
        return ok, msg

    def _forge_block(self) -> Block | None:
        """
        Create a new block from the current mempool and broadcast it.
        Called only when this node is the elected validator.
        """
        with self._lock:
            if len(self.blockchain.mempool) < TRANSACTIONS_PER_BLOCK:
                return None
            block = self.blockchain.create_block(
                validator=self.node_id,
                max_tx=TRANSACTIONS_PER_BLOCK,
            )
            ok, msg = self.blockchain.add_block(block)

        if not ok:
            logger.warning("Failed to add self-forged block: %s", msg)
            return None

        logger.info("Forged block %d with %d txs", block.index, len(block.transactions))
        # Reward the validator
        self.blockchain.set_stake(
            self.node_id,
            self.blockchain.get_stake(self.node_id) + BLOCK_REWARD,
        )
        self.save()
        self._broadcast_block(block)
        return block

    def _broadcast_block(self, block: Block) -> None:
        self._broadcast_post("/api/block", block.to_dict())

    # ------------------------------------------------------------------
    # PoS validator selection
    # ------------------------------------------------------------------
    def _select_validator(self) -> str:
        """
        Weighted random validator selection based on stake.
        Uses the current mempool size as a deterministic seed so all
        nodes with the same state agree on the same validator.
        """
        import random

        nodes: list[str] = [self.node_id] + [
            self._url_to_node_id(p) for p in self.peers
        ]
        weights = [self.blockchain.get_stake(nid) for nid in nodes]
        total = sum(weights)
        if total == 0:
            return self.node_id

        # Deterministic seed: last block hash + mempool size
        seed = self.blockchain.last_block.hash + str(len(self.blockchain.mempool))
        rng = random.Random(seed)
        chosen = rng.choices(nodes, weights=weights, k=1)[0]
        return chosen

    def _url_to_node_id(self, peer_url: str) -> str:
        """Ask peer for its node_id; fall back to a hash of the URL."""
        try:
            resp = requests.get(
                f"{peer_url}/api/node-info",
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            if resp.ok:
                return resp.json().get("node_id", self._hash_url(peer_url))
        except Exception:
            pass
        return self._hash_url(peer_url)

    @staticmethod
    def _hash_url(url: str) -> str:
        from utils import sha256
        return sha256(url)[:16]

    # ------------------------------------------------------------------
    # Auto-forge trigger
    # ------------------------------------------------------------------
    def _maybe_forge_block(self) -> None:
        """Forge a block if the mempool is full AND this node is elected."""
        if len(self.blockchain.mempool) < TRANSACTIONS_PER_BLOCK:
            return
        validator = self._select_validator()
        if validator == self.node_id:
            threading.Thread(target=self._forge_block, daemon=True).start()

    # ------------------------------------------------------------------
    # Chain synchronisation
    # ------------------------------------------------------------------
    def sync_chain(self) -> None:
        """
        Ask all peers for their chains; replace local chain if a longer
        valid chain is found (longest-chain rule).
        """
        for peer_url in self.peers:
            try:
                resp = requests.get(
                    f"{peer_url}/api/chain",
                    timeout=REQUEST_TIMEOUT_SECONDS,
                )
                if not resp.ok:
                    continue
                data = resp.json()
                peer_chain = data.get("chain", [])
                with self._lock:
                    ok, msg = self.blockchain.replace_chain(peer_chain)
                if ok:
                    logger.info("Chain replaced from %s: %s", peer_url, msg)
                    self.save()
                    break
            except Exception as exc:
                logger.debug("Sync failed for peer %s: %s", peer_url, exc)

    def sync_peers_on_startup(self, seed_peers: list[str]) -> None:
        """
        Register with each seed peer and fetch its peer list.
        """
        for peer_url in seed_peers:
            peer_url = peer_url.rstrip("/")
            self.add_peer(peer_url)
            # Tell the peer about us
            my_url = f"http://{self.host}:{self.port}"
            try:
                requests.post(
                    f"{peer_url}/api/peer",
                    json={"url": my_url},
                    timeout=REQUEST_TIMEOUT_SECONDS,
                )
                # Fetch their peer list
                resp = requests.get(
                    f"{peer_url}/api/peers",
                    timeout=REQUEST_TIMEOUT_SECONDS,
                )
                if resp.ok:
                    for p in resp.json().get("peers", []):
                        if p != my_url:
                            self.add_peer(p)
            except Exception as exc:
                logger.debug("Startup sync failed for %s: %s", peer_url, exc)

        # Pull the best chain
        self.sync_chain()

    # ------------------------------------------------------------------
    # Generic HTTP broadcast helper
    # ------------------------------------------------------------------
    def _broadcast_post(self, endpoint: str, payload: dict) -> None:
        """POST payload to all peers at the given endpoint (fire-and-forget)."""

        def _send(url: str) -> None:
            try:
                requests.post(
                    f"{url}{endpoint}",
                    json=payload,
                    timeout=REQUEST_TIMEOUT_SECONDS,
                )
            except Exception as exc:
                logger.debug("Broadcast to %s%s failed: %s", url, endpoint, exc)

        for peer_url in self.peers:
            threading.Thread(target=_send, args=(peer_url,), daemon=True).start()
