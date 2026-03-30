"""
node.py - Flask REST API server for a blockchain node.

Run one instance per phone / terminal:
    python node.py --port 5001 --node-id node1 --peers http://192.168.1.5:5002

API endpoints:
    POST   /api/transaction   Receive / broadcast a transaction
    POST   /api/block         Receive / validate a block from a peer
    POST   /api/peer          Register a peer node
    GET    /api/chain         Return the full blockchain ledger
    GET    /api/mempool       View pending transactions
    GET    /api/peers         List connected peers
    GET    /api/node-info     Node identity and stake info
    GET    /                  Serve the web dashboard (web_ui.html)
"""
from __future__ import annotations

import argparse
import logging
import os
import threading
import time

from flask import Flask, jsonify, request, send_from_directory

from config import (
    DEBUG,
    DEFAULT_HOST,
    DEFAULT_PORT,
    NODE_PEERS,
    SYNC_INTERVAL_SECONDS,
    THREADED,
)
from node_core import NodeCore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
node: NodeCore | None = None  # set in main()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _node() -> NodeCore:
    """Return the global node instance (guaranteed non-None after startup)."""
    assert node is not None, "NodeCore not initialised"
    return node


def _json_error(message: str, status: int = 400):
    return jsonify({"success": False, "message": message}), status


# ---------------------------------------------------------------------------
# API Routes
# ---------------------------------------------------------------------------

@app.route("/api/transaction", methods=["POST"])
def api_transaction():
    """
    Accept a transaction in two forms:

    1. **Peer-forwarded** – full signed transaction dict (contains 'tx_id',
       'sender', 'signature', etc.).  Validated and added to the mempool.

    2. **Client shorthand** – just ``{"recipient": "<addr>", "amount": <n>}``.
       The node creates and signs the transaction from its own wallet.
    """
    data = request.get_json(silent=True)
    if not data:
        return _json_error("No JSON body provided")

    # Client shorthand: node creates and signs the transaction
    if "tx_id" not in data:
        recipient = data.get("recipient", "")
        try:
            amount = float(data.get("amount", 0))
        except (TypeError, ValueError):
            return _json_error("Invalid amount")
        if not recipient:
            return _json_error("Missing 'recipient' field")
        if amount <= 0:
            return _json_error("Amount must be positive")
        result = _node().create_transaction(recipient=recipient, amount=amount)
        status = 201 if result.get("success") else 400
        return jsonify(result), status

    # Peer-forwarded full transaction
    ok, msg = _node().receive_transaction(data)
    status = 201 if ok else 400
    return jsonify({"success": ok, "message": msg}), status


@app.route("/api/block", methods=["POST"])
def api_block():
    """Receive a mined block from a peer validator."""
    data = request.get_json(silent=True)
    if not data:
        return _json_error("No JSON body provided")

    ok, msg = _node().receive_block(data)
    status = 201 if ok else 400
    return jsonify({"success": ok, "message": msg}), status


@app.route("/api/peer", methods=["POST"])
def api_add_peer():
    """Register a new peer node."""
    data = request.get_json(silent=True)
    if not data or "url" not in data:
        return _json_error("Missing 'url' field")

    ok, msg = _node().add_peer(data["url"])
    status = 201 if ok else 200
    return jsonify({"success": ok, "message": msg}), status


@app.route("/api/chain", methods=["GET"])
def api_chain():
    """Return the node's full blockchain."""
    return jsonify(_node().blockchain.to_dict()), 200


@app.route("/api/mempool", methods=["GET"])
def api_mempool():
    """Return pending (unconfirmed) transactions."""
    return jsonify({"transactions": _node().blockchain.get_mempool_dicts()}), 200


@app.route("/api/peers", methods=["GET"])
def api_peers():
    """Return the list of known peers."""
    return jsonify({"peers": _node().get_peers()}), 200


@app.route("/api/node-info", methods=["GET"])
def api_node_info():
    """Return this node's identity and state."""
    return jsonify(_node().node_info()), 200


# ---------------------------------------------------------------------------
# Web dashboard
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    """Serve the web dashboard."""
    html_path = os.path.join(os.path.dirname(__file__), "web_ui.html")
    if os.path.exists(html_path):
        return send_from_directory(os.path.dirname(html_path), "web_ui.html")
    return "<h1>Blockchain Node Running</h1><p>web_ui.html not found.</p>", 200


# ---------------------------------------------------------------------------
# Background sync thread
# ---------------------------------------------------------------------------

def _background_sync(n: NodeCore, interval: int) -> None:
    """Periodically synchronise chain with peers."""
    while True:
        time.sleep(interval)
        try:
            n.sync_chain()
        except Exception as exc:
            logger.debug("Background sync error: %s", exc)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    global node

    parser = argparse.ArgumentParser(description="Blockchain Node Server")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--node-id", dest="node_id", default=None,
                        help="Human-readable node identifier")
    parser.add_argument(
        "--peers",
        nargs="*",
        default=NODE_PEERS,
        help="Seed peer URLs, e.g. http://192.168.1.5:5002",
    )
    args = parser.parse_args()

    node = NodeCore(host=args.host, port=args.port, node_id=args.node_id)

    # Connect to seed peers and sync chain
    if args.peers:
        logger.info("Connecting to seed peers: %s", args.peers)
        node.sync_peers_on_startup(args.peers)

    # Start background chain-sync thread
    sync_thread = threading.Thread(
        target=_background_sync,
        args=(node, SYNC_INTERVAL_SECONDS),
        daemon=True,
    )
    sync_thread.start()

    logger.info(
        "Starting node %s on http://%s:%d",
        node.node_id,
        args.host,
        args.port,
    )
    app.run(host=args.host, port=args.port, debug=DEBUG, threaded=THREADED)


if __name__ == "__main__":
    main()
