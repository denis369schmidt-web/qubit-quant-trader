"""
PRE-TRADE COMPLIANCE & PRICE COLLAR GUARD (SEC 15c3-5 & MIFID II STYLE)
------------------------------------------------------------------------
Portiert und adaptiert aus Chimera (Agent Justitia & Cerberus):
1. Fat-Finger Price Collar Check:
   Verhindert Order-Erteilung, wenn der Preis um mehr als +/- 1.5%
   vom aktuellen Mid-Market/Arrival Price abweicht.
2. Max Notional Cap pro Einzel-Order.
3. Krypto-Merkle-Hash Audit Trail für jeden ausgeführten Trade.
"""

import time
import hashlib
import json
from typing import Dict, Any, Tuple, Optional


class PreTradeComplianceGuard:
    """Schützt vor Fat-Finger Fehlern, Kursspitzen und erzeugt kryptografische Audit-Hashes."""

    def __init__(
        self,
        max_notional_per_order_eur: float = 2500.0,
        max_price_collar_pct: float = 0.015  # Max 1.5% Preisabweichung
    ):
        self.max_notional = max_notional_per_order_eur
        self.max_collar_pct = max_price_collar_pct
        self.audit_log = []

    def validate_order(
        self,
        pair: str,
        side: str,
        volume: float,
        price: float,
        prevailing_market_price: float
    ) -> Tuple[bool, str]:
        """Prüft Order gegen Notional Cap und Price Collar."""
        if volume <= 0 or price <= 0:
            return False, "INVALID_ORDER_PARAMETERS"

        notional_eur = volume * price
        if notional_eur > self.max_notional:
            return False, f"NOTIONAL_LIMIT_EXCEEDED ({notional_eur:.2f} € > Max {self.max_notional:.2f} €)"

        if prevailing_market_price > 0:
            price_dev_pct = abs(price - prevailing_market_price) / prevailing_market_price
            if price_dev_pct > self.max_collar_pct:
                return False, f"PRICE_COLLAR_VIOLATION (Abweichung {price_dev_pct*100:.2f}% > Limit {self.max_collar_pct*100:.2f}%)"

        return True, "COMPLIANCE_APPROVED"

    @staticmethod
    def generate_merkle_trade_hash(
        txid: str,
        pair: str,
        side: str,
        volume: float,
        price: float,
        fee_eur: float,
        timestamp: str
    ) -> str:
        """
        Erzeugt einen unmanipulierbaren kryptografischen SHA-256 Audit-Hash
        für jeden Trade-Eintrag (nach Vorbild Chimera Cerberus Enclave).
        """
        payload = f"{txid}|{pair}|{side}|{volume:.6f}|{price:.2f}|{fee_eur:.4f}|{timestamp}"
        return hashlib.sha256(payload.encode('utf-8')).hexdigest()
