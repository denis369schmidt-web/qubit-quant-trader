"""
Analyse echter Trades aus v1: trading_ledger.db (SQLite) oder Kraken-Trade-Export (CSV).

Gespeicherte PnL-Werte werden bewusst NICHT übernommen (v1 hatte Schein-Gewinne),
sondern aus Kauf/Verkauf-Zeilen per FIFO neu berechnet.
"""

import csv
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional

import numpy as np


@dataclass
class Fill:
    ts: float
    pair: str
    side: str      # BUY | SELL
    price: float
    volume: float
    fee: float     # in Quote-Währung (EUR)


@dataclass
class RoundTrip:
    pair: str
    entry_ts: float
    exit_ts: float
    volume: float
    entry_price: float
    exit_price: float
    fees: float

    @property
    def gross(self) -> float:
        return (self.exit_price - self.entry_price) * self.volume

    @property
    def net(self) -> float:
        return self.gross - self.fees

    @property
    def notional(self) -> float:
        return self.entry_price * self.volume


def parse_ts(v) -> float:
    if v is None or v == "":
        return 0.0
    try:
        return float(v)
    except (TypeError, ValueError):
        pass
    s = str(v).strip().replace("T", " ").rstrip("Z")
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%d.%m.%Y %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:26], fmt).replace(tzinfo=timezone.utc).timestamp()
        except ValueError:
            continue
    return 0.0


def normalize_pair(p: str) -> str:
    p = p.upper().replace("/", "").replace("-", "")
    for old, new in (("XXBTZ", "XBT"), ("XETHZ", "ETH"), ("XXRPZ", "XRP"), ("XBT", "BTC")):
        p = p.replace(old, new)
    return p


def load_ledger_db(path: str) -> List[Fill]:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM trades ORDER BY id ASC").fetchall()
    conn.close()
    fills = []
    for r in rows:
        side = str(r["side"]).upper()
        if side not in ("BUY", "SELL") or "REJECT" in str(r["status"]).upper():
            continue
        fills.append(Fill(parse_ts(r["timestamp"]), normalize_pair(r["pair"]), side, float(r["price"]),
                          float(r["volume"]), float(r["fee_eur"] or 0.0)))
    return fills


def load_kraken_csv(path: str) -> List[Fill]:
    fills = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            side = r.get("type", "").upper()
            if side not in ("BUY", "SELL"):
                continue
            fills.append(Fill(parse_ts(r.get("time")), normalize_pair(r.get("pair", "")), side,
                              float(r["price"]), float(r["vol"]), float(r.get("fee") or 0.0)))
    return sorted(fills, key=lambda x: x.ts)


def load(path: str) -> List[Fill]:
    return load_kraken_csv(path) if path.lower().endswith(".csv") else load_ledger_db(path)


def build_roundtrips(fills: List[Fill]):
    """FIFO-Matching. Liefert (roundtrips, unmatched_sell_volume_per_pair, open_lots_per_pair)."""
    lots: Dict[str, List[List[float]]] = defaultdict(list)  # [ts, price, vol_rem, fee_rem]
    trips: List[RoundTrip] = []
    unmatched: Dict[str, float] = defaultdict(float)
    for f in fills:
        if f.side == "BUY":
            lots[f.pair].append([f.ts, f.price, f.volume, f.fee])
            continue
        remaining = f.volume
        while remaining > 1e-12 and lots[f.pair]:
            lot = lots[f.pair][0]
            take = min(lot[2], remaining)
            buy_fee = lot[3] * take / lot[2]
            sell_fee = f.fee * take / f.volume
            trips.append(RoundTrip(f.pair, lot[0], f.ts, take, lot[1], f.price, buy_fee + sell_fee))
            lot[2] -= take
            lot[3] -= buy_fee
            remaining -= take
            if lot[2] <= 1e-12:
                lots[f.pair].pop(0)
        if remaining > 1e-12:
            unmatched[f.pair] += remaining
    open_lots = {p: sum(l[2] for l in ls) for p, ls in lots.items() if ls}
    return trips, dict(unmatched), open_lots


def summarize(trips: List[RoundTrip], alt_fee_pct: float = 0.001) -> Dict[str, object]:
    if not trips:
        return {"roundtrips": 0}
    net = np.array([t.net for t in trips])
    gross = np.array([t.gross for t in trips])
    fees = np.array([t.fees for t in trips])
    notional = np.array([t.notional for t in trips])
    hold_h = np.array([(t.exit_ts - t.entry_ts) / 3600.0 for t in trips])
    move_pct = np.array([(t.exit_price / t.entry_price - 1.0) * 100.0 for t in trips])
    wins, losses = net[net > 0], net[net <= 0]
    per_pair = {}
    for pair in sorted({t.pair for t in trips}):
        sel = np.array([t.pair == pair for t in trips])
        per_pair[pair] = {"roundtrips": int(sel.sum()), "net": float(net[sel].sum()),
                          "fees": float(fees[sel].sum()), "win_rate_pct": float((net[sel] > 0).mean() * 100)}
    alt_net = gross - notional * alt_fee_pct * 2.0
    return {
        "roundtrips": len(trips),
        "net_pnl": float(net.sum()),
        "gross_pnl_before_fees": float(gross.sum()),
        "fees_total": float(fees.sum()),
        "fees_vs_abs_gross": float(fees.sum() / max(np.abs(gross).sum(), 1e-12)),
        "win_rate_pct": float((net > 0).mean() * 100.0),
        "gross_win_rate_pct": float((gross > 0).mean() * 100.0),
        "avg_win": float(wins.mean()) if len(wins) else 0.0,
        "avg_loss": float(losses.mean()) if len(losses) else 0.0,
        "profit_factor": float(wins.sum() / -losses.sum()) if losses.sum() < 0 else float("inf"),
        "avg_notional": float(notional.mean()),
        "median_hold_hours": float(np.median(hold_h)),
        "median_move_pct": float(np.median(move_pct)),
        "avg_roundtrip_fee_pct": float((fees / notional).mean() * 100.0),
        "net_with_alt_fees": float(alt_net.sum()),
        "alt_fee_pct": alt_fee_pct * 100.0,
        "per_pair": per_pair,
    }


def report(path: str) -> str:
    fills = load(path)
    trips, unmatched, open_lots = build_roundtrips(fills)
    s = summarize(trips)
    lines = [f"Datei: {path}", f"Fills: {len(fills)}  |  Abgeschlossene Roundtrips (FIFO): {s['roundtrips']}"]
    if s["roundtrips"]:
        lines += [
            f"Netto-PnL:               {s['net_pnl']:+.4f}",
            f"Brutto vor Gebühren:     {s['gross_pnl_before_fees']:+.4f}",
            f"Gebühren gesamt:         {s['fees_total']:.4f}  ({s['fees_vs_abs_gross'] * 100:.0f} % der Brutto-Bewegung)",
            f"Ø Roundtrip-Gebühr:      {s['avg_roundtrip_fee_pct']:.3f} %  |  Ø Kursbewegung (Median): {s['median_move_pct']:+.3f} %",
            f"Trefferquote netto:      {s['win_rate_pct']:.1f} %  (brutto: {s['gross_win_rate_pct']:.1f} %)",
            f"Ø Gewinn / Ø Verlust:    {s['avg_win']:+.4f} / {s['avg_loss']:+.4f}  |  Profit-Faktor {s['profit_factor']:.2f}",
            f"Ø Positionsgröße:        {s['avg_notional']:.2f}  |  Median Haltedauer {s['median_hold_hours']:.2f} h",
            f"Mit {s['alt_fee_pct']:.2f} % Gebühr/Seite wäre Netto: {s['net_with_alt_fees']:+.4f}",
            "Pro Paar:",
        ]
        for pair, p in s["per_pair"].items():
            lines.append(f"  {pair:10s} {p['roundtrips']:4d} Trades  Netto {p['net']:+.4f}  "
                         f"Gebühren {p['fees']:.4f}  Treffer {p['win_rate_pct']:.0f} %")
    if unmatched:
        lines.append(f"Verkäufe ohne bekannten Kauf (unbekannte Einstandskosten): {unmatched}")
    if open_lots:
        lines.append(f"Noch offene Bestände: {open_lots}")
    return "\n".join(lines)
