"""
node.py - FastAPI REST server for a blockchain node (Proof-of-Authority).

Run one instance per phone / terminal:
    python node.py --port 5001 --node-id node1 --peers http://192.168.1.5:5002

API endpoints:
    POST   /api/transaction   Receive / broadcast a transaction
    POST   /api/block         Receive / validate a block from a peer
    POST   /api/peer          Register a peer node
    GET    /api/chain         Return the full blockchain ledger
    GET    /api/mempool       View pending transactions
    GET    /api/peers         List connected peers
    GET    /api/node-info     Node identity and PoA status
    GET    /                  Serve the web dashboard (web_ui.html)
"""
from __future__ import annotations

import argparse
import logging
import os
import threading
import time
from contextlib import asynccontextmanager
from typing import Any, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, field_validator

from config import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    NODE_PEERS,
    SYNC_INTERVAL_SECONDS,
)
from node_core import NodeCore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Global node instance — set during startup via the lifespan context.
_node: NodeCore | None = None


# ---------------------------------------------------------------------------
# Pydantic request models
# ---------------------------------------------------------------------------

class TransactionRequest(BaseModel):
    """
    Two accepted forms:
    - Client shorthand: {"recipient": "<addr>", "amount": 10}
    - Peer-forwarded:   full transaction dict with tx_id, sender, signature …
    """
    # Client shorthand fields
    recipient: Optional[str] = None
    amount: Optional[float] = None
    # Peer-forwarded fields (all optional so one model covers both forms)
    tx_id: Optional[str] = None
    sender: Optional[str] = None
    timestamp: Optional[float] = None
    signature: Optional[str] = None

    @field_validator("amount", mode="before")
    @classmethod
    def amount_positive(cls, v):
        if v is not None and float(v) <= 0:
            raise ValueError("Amount must be positive")
        return v


class BlockRequest(BaseModel):
    index: int
    timestamp: float
    transactions: list[dict]
    previous_hash: str
    validator: str
    merkle_root: str
    hash: str


class PeerRequest(BaseModel):
    url: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_node() -> NodeCore:
    if _node is None:
        raise HTTPException(status_code=503, detail="NodeCore not initialised")
    return _node


# ---------------------------------------------------------------------------
# App factory / lifespan
# ---------------------------------------------------------------------------

def create_app(node: NodeCore, seed_peers: list[str]) -> FastAPI:
    """
    Build the FastAPI application and register all routes.
    A lifespan context handles startup peer-sync and background sync thread.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        global _node
        _node = node

        # Connect to seed peers and sync chain
        if seed_peers:
            logger.info("Connecting to seed peers: %s", seed_peers)
            node.sync_peers_on_startup(seed_peers)

        # Background chain-sync thread
        def _bg_sync():
            while True:
                time.sleep(SYNC_INTERVAL_SECONDS)
                try:
                    node.sync_chain()
                except Exception as exc:
                    logger.debug("Background sync error: %s", exc)

        threading.Thread(target=_bg_sync, daemon=True).start()
        yield
        # (shutdown hook — nothing needed for this simulator)

    app = FastAPI(
        title="Blockchain Node (PoA)",
        description="Proof-of-Authority distributed blockchain node",
        version="2.0.0",
        lifespan=lifespan,
    )

    # -----------------------------------------------------------------------
    # Routes
    # -----------------------------------------------------------------------

    @app.post("/api/transaction", status_code=201)
    async def api_transaction(body: TransactionRequest):
        """
        Accept a transaction in two forms:

        **Client shorthand** — ``{"recipient": "<addr>", "amount": N}``
        The node creates and signs the transaction from its own wallet.

        **Peer-forwarded** — full signed transaction dict (contains ``tx_id``,
        ``sender``, ``signature``, etc.).
        """
        n = get_node()

        if body.tx_id is None:
            # Client shorthand
            if not body.recipient:
                raise HTTPException(status_code=400, detail="Missing 'recipient' field")
            if body.amount is None or body.amount <= 0:
                raise HTTPException(status_code=400, detail="Amount must be positive")
            result = n.create_transaction(recipient=body.recipient, amount=body.amount)
            if not result.get("success"):
                raise HTTPException(status_code=400, detail=result["message"])
            return result

        # Peer-forwarded full transaction
        tx_data = body.model_dump(exclude_none=True)
        ok, msg = n.receive_transaction(tx_data)
        if not ok:
            raise HTTPException(status_code=400, detail=msg)
        return {"success": True, "message": msg}

    @app.post("/api/block", status_code=201)
    async def api_block(body: BlockRequest):
        """Receive a forged block from a peer PoA validator."""
        n = get_node()
        ok, msg = n.receive_block(body.model_dump())
        if not ok:
            raise HTTPException(status_code=400, detail=msg)
        return {"success": True, "message": msg}

    @app.post("/api/peer", status_code=201)
    async def api_add_peer(body: PeerRequest):
        """Register a new peer node URL."""
        n = get_node()
        ok, msg = n.add_peer(body.url)
        return {"success": ok, "message": msg}

    @app.get("/api/chain")
    async def api_chain():
        """Return the node's full blockchain."""
        return get_node().blockchain.to_dict()

    @app.get("/api/mempool")
    async def api_mempool():
        """Return pending (unconfirmed) transactions."""
        return {"transactions": get_node().blockchain.get_mempool_dicts()}

    @app.get("/api/peers")
    async def api_peers():
        """Return the list of known peers."""
        return {"peers": get_node().get_peers()}

    @app.get("/api/node-info")
    async def api_node_info():
        """Return this node's identity, PoA status, and chain state."""
        return get_node().node_info()

    @app.get("/")
    async def index():
        """Serve the web dashboard."""
        html_path = os.path.join(os.path.dirname(__file__), "web_ui.html")
        if os.path.exists(html_path):
            return FileResponse(html_path, media_type="text/html")
        return JSONResponse(
            {"message": "Blockchain node running — web_ui.html not found"},
            status_code=200,
        )

    return app


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Blockchain Node Server (FastAPI/PoA)")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--node-id", dest="node_id", default=None,
        help="Human-readable node identifier (must be in AUTHORIZED_VALIDATORS to forge)",
    )
    parser.add_argument(
        "--peers",
        nargs="*",
        default=NODE_PEERS,
        help="Seed peer URLs, e.g. http://192.168.1.5:5002",
    )
    args = parser.parse_args()

    node = NodeCore(host=args.host, port=args.port, node_id=args.node_id)
    seed_peers = args.peers or []

    app = create_app(node, seed_peers)

    logger.info(
        "Starting PoA node '%s' on http://%s:%d  authorized=%s",
        node.node_id,
        args.host,
        args.port,
        node.is_authorized,
    )
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()

