"""
blockchain.py - Block, Transaction, and Chain classes.

Defines the core data structures used across the network.
"""
from __future__ import annotations

import json
import time
from typing import Any

from utils import (
    calculate_merkle_root,
    current_timestamp,
    hash_dict,
    sha256,
    sign_data,
    validate_transaction_fields,
    verify_signature,
)
from config import GENESIS_SENDER


# ---------------------------------------------------------------------------
# Transaction
# ---------------------------------------------------------------------------

class Transaction:
    """Represents a single transfer of value between two addresses."""

    def __init__(
        self,
        sender: str,
        recipient: str,
        amount: float,
        private_key: str,
        timestamp: float | None = None,
    ) -> None:
        self.sender = sender
        self.recipient = recipient
        self.amount = amount
        self.timestamp = current_timestamp() if timestamp is None else timestamp
        self.tx_id = self._compute_id()
        self.signature = sign_data(self._signable(), private_key)

    # ------------------------------------------------------------------
    def _signable(self) -> dict:
        """Return the subset of fields that are included in the signature."""
        return {
            "sender": self.sender,
            "recipient": self.recipient,
            "amount": self.amount,
            "timestamp": self.timestamp,
        }

    def _compute_id(self) -> str:
        return sha256(
            f"{self.sender}{self.recipient}{self.amount}{self.timestamp}"
        )

    # ------------------------------------------------------------------
    def is_valid(self, public_key: str) -> bool:
        """Verify the transaction signature using the sender's public key."""
        if self.sender == GENESIS_SENDER:
            return True  # genesis transactions are always valid
        return verify_signature(self._signable(), self.signature, public_key)

    # ------------------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "tx_id": self.tx_id,
            "sender": self.sender,
            "recipient": self.recipient,
            "amount": self.amount,
            "timestamp": self.timestamp,
            "signature": self.signature,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Transaction":
        """Re-create a Transaction from a dictionary (no signing needed)."""
        tx = cls.__new__(cls)
        tx.tx_id = data["tx_id"]
        tx.sender = data["sender"]
        tx.recipient = data["recipient"]
        tx.amount = float(data["amount"])
        tx.timestamp = float(data["timestamp"])
        tx.signature = data["signature"]
        return tx

    def __repr__(self) -> str:
        return (
            f"Transaction(id={self.tx_id[:8]}, "
            f"{self.sender[:8]}→{self.recipient[:8]}, "
            f"amount={self.amount})"
        )


# ---------------------------------------------------------------------------
# Block
# ---------------------------------------------------------------------------

class Block:
    """A single block in the blockchain."""

    def __init__(
        self,
        index: int,
        transactions: list[Transaction],
        previous_hash: str,
        validator: str,
        timestamp: float | None = None,
    ) -> None:
        self.index = index
        self.transactions = transactions
        self.previous_hash = previous_hash
        self.validator = validator
        self.timestamp = current_timestamp() if timestamp is None else timestamp
        self.merkle_root = calculate_merkle_root(
            [tx.to_dict() for tx in transactions]
        )
        self.hash = self._compute_hash()

    # ------------------------------------------------------------------
    def _hashable(self) -> dict:
        """Return the dict that is hashed to produce block.hash."""
        return {
            "index": self.index,
            "previous_hash": self.previous_hash,
            "validator": self.validator,
            "timestamp": self.timestamp,
            "merkle_root": self.merkle_root,
        }

    def _compute_hash(self) -> str:
        return hash_dict(self._hashable())

    # ------------------------------------------------------------------
    def is_valid(self, previous_block: "Block | None") -> tuple[bool, str]:
        """
        Validate this block's structural integrity.
        Returns (is_valid, reason).
        """
        if self.hash != self._compute_hash():
            return False, "Block hash mismatch"
        if previous_block is not None:
            if self.index != previous_block.index + 1:
                return False, "Non-consecutive block index"
            if self.previous_hash != previous_block.hash:
                return False, "Previous hash mismatch"
        return True, "OK"

    # ------------------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "transactions": [tx.to_dict() for tx in self.transactions],
            "previous_hash": self.previous_hash,
            "validator": self.validator,
            "merkle_root": self.merkle_root,
            "hash": self.hash,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Block":
        """Re-create a Block from a dictionary."""
        block = cls.__new__(cls)
        block.index = int(data["index"])
        block.timestamp = float(data["timestamp"])
        block.previous_hash = data["previous_hash"]
        block.validator = data["validator"]
        block.merkle_root = data["merkle_root"]
        block.hash = data["hash"]
        block.transactions = [
            Transaction.from_dict(tx) for tx in data["transactions"]
        ]
        return block

    def __repr__(self) -> str:
        return (
            f"Block(index={self.index}, hash={self.hash[:8]}, "
            f"txs={len(self.transactions)}, validator={self.validator[:8]})"
        )


# ---------------------------------------------------------------------------
# Blockchain
# ---------------------------------------------------------------------------

class Blockchain:
    """
    Manages the full chain, mempool, balances, and PoS stake tracking.
    """

    INITIAL_BALANCE = 1000.0     # starting balance for every address
    INITIAL_STAKE = 100          # starting stake for every node

    def __init__(self) -> None:
        self.chain: list[Block] = []
        self.mempool: list[Transaction] = []
        self._balances: dict[str, float] = {}
        self._stakes: dict[str, int] = {}
        self._create_genesis_block()

    # ------------------------------------------------------------------
    # Genesis
    # ------------------------------------------------------------------
    def _create_genesis_block(self) -> None:
        genesis = Block(
            index=0,
            transactions=[],
            previous_hash="0" * 64,
            validator=GENESIS_SENDER,
            timestamp=0.0,
        )
        self.chain.append(genesis)

    # ------------------------------------------------------------------
    # Chain properties
    # ------------------------------------------------------------------
    @property
    def last_block(self) -> Block:
        return self.chain[-1]

    @property
    def height(self) -> int:
        return len(self.chain) - 1  # genesis is height 0

    # ------------------------------------------------------------------
    # Balance / stake helpers
    # ------------------------------------------------------------------
    def get_balance(self, address: str) -> float:
        return self._balances.get(address, self.INITIAL_BALANCE)

    def get_stake(self, node_id: str) -> int:
        return self._stakes.get(node_id, self.INITIAL_STAKE)

    def set_stake(self, node_id: str, stake: int) -> None:
        self._stakes[node_id] = stake

    def _apply_transaction(self, tx: Transaction) -> None:
        """Update in-memory balances for a confirmed transaction."""
        if tx.sender != GENESIS_SENDER:
            self._balances[tx.sender] = self.get_balance(tx.sender) - tx.amount
        self._balances[tx.recipient] = self.get_balance(tx.recipient) + tx.amount

    def _apply_block(self, block: Block) -> None:
        for tx in block.transactions:
            self._apply_transaction(tx)

    # ------------------------------------------------------------------
    # Mempool
    # ------------------------------------------------------------------
    def add_to_mempool(self, tx: Transaction) -> tuple[bool, str]:
        """Validate and add a transaction to the mempool."""
        is_valid, err = validate_transaction_fields(tx.to_dict())
        if not is_valid:
            return False, err
        # Reject duplicate
        existing_ids = {t.tx_id for t in self.mempool}
        if tx.tx_id in existing_ids:
            return False, "Duplicate transaction"
        # Check it isn't already in the chain
        if self._tx_in_chain(tx.tx_id):
            return False, "Transaction already confirmed"
        # Basic balance check (not double-spend proof without full UTXO set)
        if tx.sender != GENESIS_SENDER:
            if self.get_balance(tx.sender) < tx.amount:
                return False, "Insufficient balance"
        self.mempool.append(tx)
        return True, "Transaction added to mempool"

    def _tx_in_chain(self, tx_id: str) -> bool:
        for block in self.chain:
            for tx in block.transactions:
                if tx.tx_id == tx_id:
                    return True
        return False

    def get_mempool_dicts(self) -> list[dict]:
        return [tx.to_dict() for tx in self.mempool]

    # ------------------------------------------------------------------
    # Block creation
    # ------------------------------------------------------------------
    def create_block(
        self, validator: str, max_tx: int | None = None
    ) -> Block:
        """
        Pop transactions from the mempool and forge a new block.
        """
        txs = self.mempool[:max_tx] if max_tx else self.mempool[:]
        block = Block(
            index=self.last_block.index + 1,
            transactions=txs,
            previous_hash=self.last_block.hash,
            validator=validator,
        )
        return block

    def add_block(self, block: Block) -> tuple[bool, str]:
        """Validate and append a block to the chain."""
        is_valid, reason = block.is_valid(self.last_block)
        if not is_valid:
            return False, reason
        # Remove confirmed transactions from mempool
        confirmed_ids = {tx.tx_id for tx in block.transactions}
        self.mempool = [
            tx for tx in self.mempool if tx.tx_id not in confirmed_ids
        ]
        self.chain.append(block)
        self._apply_block(block)
        return True, "Block added"

    # ------------------------------------------------------------------
    # Full chain validation
    # ------------------------------------------------------------------
    def is_chain_valid(self) -> tuple[bool, str]:
        for i in range(1, len(self.chain)):
            ok, reason = self.chain[i].is_valid(self.chain[i - 1])
            if not ok:
                return False, f"Block {i}: {reason}"
        return True, "Chain is valid"

    # ------------------------------------------------------------------
    # Replace chain (longest chain rule)
    # ------------------------------------------------------------------
    def replace_chain(self, new_chain_dicts: list[dict]) -> tuple[bool, str]:
        """
        Replace the local chain with a longer valid chain from a peer.
        """
        if len(new_chain_dicts) <= len(self.chain):
            return False, "Incoming chain is not longer"

        # Reconstruct candidate chain
        candidate: list[Block] = []
        try:
            for block_data in new_chain_dicts:
                candidate.append(Block.from_dict(block_data))
        except (KeyError, ValueError) as exc:
            return False, f"Malformed chain data: {exc}"

        # Validate genesis
        genesis = candidate[0]
        if genesis.hash != self.chain[0].hash:
            return False, "Genesis block mismatch"

        # Validate each block
        for i in range(1, len(candidate)):
            ok, reason = candidate[i].is_valid(candidate[i - 1])
            if not ok:
                return False, f"Invalid block {i}: {reason}"

        # Accept the new chain
        self.chain = candidate
        # Rebuild balances from scratch
        self._balances = {}
        for block in self.chain[1:]:
            self._apply_block(block)

        return True, "Chain replaced"

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "chain": [block.to_dict() for block in self.chain],
            "length": len(self.chain),
        }

    def get_chain_dicts(self) -> list[dict]:
        return [block.to_dict() for block in self.chain]

    @classmethod
    def from_dict(cls, data: dict) -> "Blockchain":
        bc = cls.__new__(cls)
        bc.mempool = []
        bc._balances = {}
        bc._stakes = {}
        bc.chain = [Block.from_dict(b) for b in data["chain"]]
        # Rebuild balances
        for block in bc.chain[1:]:
            bc._apply_block(block)
        return bc

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------
    def save(self, filepath: str) -> None:
        with open(filepath, "w") as fh:
            json.dump(self.to_dict(), fh, indent=2)

    @classmethod
    def load(cls, filepath: str) -> "Blockchain":
        with open(filepath) as fh:
            data = json.load(fh)
        return cls.from_dict(data)
