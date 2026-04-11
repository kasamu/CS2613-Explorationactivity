"""
utils.py - Cryptographic and validation utilities for the blockchain network.

Provides key generation, signing, verification, and hashing helpers.
"""
import hashlib
import json
import time
from typing import Any


def sha256(data: str) -> str:
    """Return the SHA-256 hex digest of the given string."""
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def hash_dict(d: dict) -> str:
    """Return a deterministic SHA-256 hash of a dictionary."""
    serialized = json.dumps(d, sort_keys=True)
    return sha256(serialized)


def current_timestamp() -> float:
    """Return the current Unix timestamp."""
    return time.time()


def generate_node_id(host: str, port: int) -> str:
    """Generate a deterministic node ID from host and port."""
    return sha256(f"{host}:{port}")[:16]


# ---------------------------------------------------------------------------
# Simple deterministic signature using SHA-256.
# The scheme uses sign_data(payload, key) = SHA-256(json(payload) + ":" + key).
# This is an educational simulator; a production blockchain would use
# asymmetric keys (e.g. ECDSA / secp256k1).
# ---------------------------------------------------------------------------

def sign_data(data: dict, private_key: str) -> str:
    """
    Create a simple signature: HMAC-SHA256(sorted_json(data), private_key).
    """
    payload = json.dumps(data, sort_keys=True)
    return hashlib.sha256(f"{payload}:{private_key}".encode("utf-8")).hexdigest()


def verify_signature(data: dict, signature: str, public_key: str) -> bool:
    """
    Verify a signature produced by sign_data.

    For this simulator the public_key == private_key (symmetric scheme).
    In a real blockchain you would use asymmetric key verification.
    """
    expected = sign_data(data, public_key)
    return expected == signature


def generate_keypair(seed: str) -> tuple[str, str]:
    """
    Generate a (private_key, public_key) pair deterministically from a seed.

    Both keys are SHA-256 digests so they are always 64 hex characters.
    public_key is derived from private_key so the relationship is verifiable.
    """
    private_key = sha256(f"private:{seed}")
    public_key = sha256(f"public:{private_key}")
    return private_key, public_key


def is_valid_address(address: str) -> bool:
    """Check that an address looks like a valid 64-char hex string."""
    if not isinstance(address, str):
        return False
    if len(address) != 64:
        return False
    try:
        int(address, 16)
        return True
    except ValueError:
        return False


def calculate_merkle_root(transactions: list) -> str:
    """
    Compute a simple Merkle root from a list of transaction dicts or strings.
    Returns the hash of all concatenated transaction IDs.
    """
    if not transactions:
        return sha256("empty")

    tx_hashes: list[str] = []
    for tx in transactions:
        if isinstance(tx, dict):
            tx_hashes.append(hash_dict(tx))
        else:
            tx_hashes.append(sha256(str(tx)))

    while len(tx_hashes) > 1:
        if len(tx_hashes) % 2 != 0:
            tx_hashes.append(tx_hashes[-1])  # duplicate last if odd
        next_level = []
        for i in range(0, len(tx_hashes), 2):
            combined = sha256(tx_hashes[i] + tx_hashes[i + 1])
            next_level.append(combined)
        tx_hashes = next_level

    return tx_hashes[0]


def format_amount(amount: float) -> str:
    """Format a token amount as a readable string."""
    return f"{amount:.6f}"


def validate_transaction_fields(tx_data: dict) -> tuple[bool, str]:
    """
    Validate that a raw transaction dictionary has all required fields.
    Returns (is_valid, error_message).
    """
    required = {"tx_id", "sender", "recipient", "amount", "timestamp", "signature"}
    missing = required - set(tx_data.keys())
    if missing:
        return False, f"Missing fields: {missing}"

    if not isinstance(tx_data["amount"], (int, float)):
        return False, "Amount must be a number"
    if tx_data["amount"] <= 0:
        return False, "Amount must be positive"
    if not isinstance(tx_data["sender"], str) or not tx_data["sender"]:
        return False, "Invalid sender"
    if not isinstance(tx_data["recipient"], str) or not tx_data["recipient"]:
        return False, "Invalid recipient"

    return True, ""
