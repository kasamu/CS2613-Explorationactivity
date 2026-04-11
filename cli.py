"""
cli.py - Interactive terminal CLI for the blockchain node.

Usage:
    python cli.py                        # connect to http://127.0.0.1:5001
    python cli.py --url http://127.0.0.1:5002
    python cli.py --url http://192.168.1.5:5001

No third-party packages required — uses only stdlib urllib / json.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from typing import Any


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _request(method: str, url: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        body = exc.read()
        try:
            detail = json.loads(body).get("detail", body.decode())
        except Exception:
            detail = body.decode()
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from None
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Cannot reach node: {exc.reason}") from None


def get(base: str, path: str) -> dict:
    return _request("GET", base + path)


def post(base: str, path: str, payload: dict) -> dict:
    return _request("POST", base + path, payload)


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def _sep(char: str = "─", width: int = 60) -> str:
    return char * width


def _header(base: str) -> None:
    """Print a status bar fetched from /api/node-info."""
    try:
        info = get(base, "/api/node-info")
        node_id   = info.get("node_id", "?")
        height    = info.get("chain_length", "?")
        mempool   = info.get("mempool_count", "?")
        auth      = "✓ Authorized" if info.get("is_authorized") else "✗ Observer"
        nxt       = info.get("next_validator", "?")
        print(_sep("═"))
        print(f"  ⛓  Blockchain CLI  │  node: {node_id}  │  height: {height}"
              f"  │  mempool: {mempool}  │  PoA: {auth}")
        print(f"  Next validator: {nxt}")
        print(_sep("═"))
    except RuntimeError as exc:
        print(_sep("═"))
        print(f"  ⛓  Blockchain CLI  │  {exc}")
        print(_sep("═"))


def _print_json(obj: Any) -> None:
    print(json.dumps(obj, indent=2))


# ---------------------------------------------------------------------------
# Menu actions
# ---------------------------------------------------------------------------

def action_node_info(base: str) -> None:
    print("\n── Node info " + _sep("─", 47))
    try:
        _print_json(get(base, "/api/node-info"))
    except RuntimeError as exc:
        print(f"  Error: {exc}")


def action_view_chain(base: str) -> None:
    print("\n── Blockchain " + _sep("─", 46))
    try:
        chain = get(base, "/api/chain")
        blocks = chain.get("chain", chain)
        for blk in blocks:
            print(f"\n  Block #{blk.get('index')}  validator={blk.get('validator')}"
                  f"  txs={len(blk.get('transactions', []))}")
            print(f"    hash:  {blk.get('hash', '')[:20]}…")
            print(f"    prev:  {blk.get('previous_hash', '')[:20]}…")
    except RuntimeError as exc:
        print(f"  Error: {exc}")


def action_view_mempool(base: str) -> None:
    print("\n── Mempool " + _sep("─", 49))
    try:
        data = get(base, "/api/mempool")
        txs = data.get("transactions", [])
        if not txs:
            print("  (empty)")
        for tx in txs:
            print(f"  {tx.get('tx_id', '?')[:12]}…  "
                  f"{tx.get('sender', '?')[:10]} → {tx.get('recipient', '?')[:10]}"
                  f"  amount={tx.get('amount')}")
    except RuntimeError as exc:
        print(f"  Error: {exc}")


def action_send_transaction(base: str) -> None:
    print("\n── Send transaction " + _sep("─", 40))
    recipient = input("  Recipient address: ").strip()
    if not recipient:
        print("  Cancelled.")
        return
    try:
        amount = float(input("  Amount: ").strip())
    except ValueError:
        print("  Invalid amount. Cancelled.")
        return
    try:
        result = post(base, "/api/transaction", {"recipient": recipient, "amount": amount})
        print(f"\n  ✅ {result.get('message', result)}")
    except RuntimeError as exc:
        print(f"  Error: {exc}")


def action_add_peer(base: str) -> None:
    print("\n── Add peer " + _sep("─", 48))
    url = input("  Peer URL (e.g. http://127.0.0.1:5002): ").strip()
    if not url:
        print("  Cancelled.")
        return
    try:
        result = post(base, "/api/peer", {"url": url})
        ok = result.get("success", False)
        msg = result.get("message", result)
        icon = "✅" if ok else "⚠️ "
        print(f"\n  {icon} {msg}")
    except RuntimeError as exc:
        print(f"  Error: {exc}")


def action_list_peers(base: str) -> None:
    print("\n── Peers " + _sep("─", 51))
    try:
        data = get(base, "/api/peers")
        peers = data.get("peers", [])
        if not peers:
            print("  (no peers connected)")
        for p in peers:
            print(f"  • {p}")
    except RuntimeError as exc:
        print(f"  Error: {exc}")


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

MENU = [
    ("Node info",          action_node_info),
    ("View blockchain",    action_view_chain),
    ("View mempool",       action_view_mempool),
    ("Send transaction",   action_send_transaction),
    ("Add peer",           action_add_peer),
    ("List peers",         action_list_peers),
]


def run(base: str) -> None:
    print(f"\nConnecting to node at {base} …\n")
    while True:
        _header(base)
        print()
        for i, (label, _) in enumerate(MENU, start=1):
            print(f"  {i}. {label}")
        print("  0. Quit")
        print()
        try:
            choice = input("  > ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nBye!")
            sys.exit(0)

        if choice == "0":
            print("Bye!")
            sys.exit(0)

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(MENU):
                MENU[idx][1](base)
            else:
                print("  Invalid choice.")
        except ValueError:
            print("  Invalid input — enter a number.")

        print()
        input("  [Press Enter to continue]")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Interactive terminal CLI for the blockchain node."
    )
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:5001",
        help="Base URL of the node to connect to (default: http://127.0.0.1:5001)",
    )
    args = parser.parse_args()
    base = args.url.rstrip("/")
    run(base)


if __name__ == "__main__":
    main()
