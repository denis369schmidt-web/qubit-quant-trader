"""
AUTOMATISIERTER KRAKEN RECONCILIATION WORKER
---------------------------------------------
Gleicht die lokale SQLite-Datenbank (trading_ledger.db) zyklisch
mit den offiziellen Kraken Exchange REST-Endpunkten ab:
1. /0/private/TradesHistory (Ausgeführte Trades & Gebühren)
2. /0/private/Balance (Tatsächliche Exchange-Balances)
Erkennt externe Trades, Netzwerk-Verluste und Teilausführungen.
"""

import time
import threading
import sqlite3
from typing import Dict, Any, List, Optional
from institutional_trading_core import KrakenLiveGateway, SQLiteTradeLedgerManager


class KrakenReconciliationWorker:
    """
    Überwacht die Konsistenz zwischen lokalem Trade-Ledger und echtem Kraken-Konto.
    """

    def __init__(
        self,
        db_path: str = "trading_ledger.db",
        poll_interval_sec: float = 60.0
    ):
        self.db_path = db_path
        self.ledger = SQLiteTradeLedgerManager(db_path)
        self.poll_interval = poll_interval_sec
        self.running = False
        self._thread: Optional[threading.Thread] = None
        self.last_sync_time: float = 0.0
        self.last_report: Dict[str, Any] = {}

    def fetch_exchange_trades(self, api_key: str, api_secret: str, count: int = 50) -> Dict[str, Any]:
        """Ruft die letzten ausgeführten Trades direkt von Kraken ab."""
        if not api_key or not api_secret:
            return {"status": "error", "message": "MISSING_API_KEYS"}

        res = KrakenLiveGateway.query_private(
            "/0/private/TradesHistory",
            {"type": "all"},
            api_key,
            api_secret
        )
        if res.get("error") or res.get("status") == "error":
            return {"status": "error", "message": str(res.get("error") or res.get("message"))}

        trades_data = res.get("result", {}).get("trades", {})
        return {"status": "success", "trades": trades_data}

    def fetch_exchange_balances(self, api_key: str, api_secret: str) -> Dict[str, float]:
        """Ruft echte Kontostände ab."""
        return KrakenLiveGateway.fetch_real_balances(api_key, api_secret)

    def reconcile_once(self, api_key: str, api_secret: str) -> Dict[str, Any]:
        """Führt einen einzelnen vollen Abgleich durch."""
        now = time.time()
        self.last_sync_time = now

        trades_res = self.fetch_exchange_trades(api_key, api_secret)
        if trades_res["status"] != "success":
            return {
                "success": False,
                "timestamp": now,
                "reason": trades_res.get("message", "FETCH_ERROR"),
                "imported_trades_count": 0
            }

        exchange_trades = trades_res.get("trades", {})
        balances = self.fetch_exchange_balances(api_key, api_secret)

        # Bekannte TXIDs aus lokaler DB laden
        known_txids = set()
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT txid FROM trades WHERE txid IS NOT NULL")
            for r in cursor.fetchall():
                if r[0]:
                    known_txids.add(r[0])
            conn.close()
        except Exception as e:
            return {"success": False, "reason": f"DB_READ_ERROR: {e}", "imported_trades_count": 0}

        imported_count = 0
        discrepancies = []

        for trade_id, t_info in exchange_trades.items():
            ordertxid = t_info.get("ordertxid", trade_id)
            if trade_id in known_txids or ordertxid in known_txids:
                continue  # Bereits im Ledger vorhanden

            # Trade fehlt im lokalen Ledger! Importieren & synchronisieren
            pair = t_info.get("pair", "XBTEUR")
            side = t_info.get("type", "buy").upper()
            price = float(t_info.get("price", 0.0))
            vol = float(t_info.get("vol", 0.0))
            cost = float(t_info.get("cost", price * vol))
            fee = float(t_info.get("fee", 0.0))
            trade_ts = time.strftime("%H:%M:%S", time.gmtime(float(t_info.get("time", now))))

            if side == "BUY":
                self.ledger.record_buy_trade(
                    timestamp=trade_ts,
                    pair=pair,
                    price=price,
                    volume=vol,
                    fee_eur=fee,
                    txid=trade_id,
                    status="RECONCILED_EXTERNAL_BUY"
                )
            elif side == "SELL":
                self.ledger.record_sell_trade(
                    timestamp=trade_ts,
                    pair=pair,
                    price=price,
                    volume=vol,
                    fee_eur=fee,
                    txid=trade_id,
                    status="RECONCILED_EXTERNAL_SELL"
                )

            known_txids.add(trade_id)
            imported_count += 1
            discrepancies.append({
                "trade_id": trade_id,
                "pair": pair,
                "side": side,
                "vol": vol,
                "price": price,
                "fee": fee
            })

        report = {
            "success": True,
            "timestamp": now,
            "exchange_trade_count": len(exchange_trades),
            "imported_trades_count": imported_count,
            "imported_details": discrepancies,
            "real_balances": balances
        }
        self.last_report = report
        return report

    def start_background_worker(self, api_key: str, api_secret: str):
        """Startet den zyklischen Hintergrund-Reconciliation Worker."""
        if self.running:
            return
        self.running = True

        def _loop():
            while self.running:
                try:
                    self.reconcile_once(api_key, api_secret)
                except Exception as e:
                    print(f"[RECONCILIATION ERROR] {e}")
                time.sleep(self.poll_interval)

        self._thread = threading.Thread(target=_loop, daemon=True, name="KrakenReconciliationWorker")
        self._thread.start()

    def stop(self):
        self.running = False
