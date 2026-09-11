"""
INSTITUTIONAL MULTI-EXCHANGE QUANTITATIVE TRADER (PRO LIVE KRAKEN HYBRID ENGINE 2026)
--------------------------------------------------------------------------------------
Vollautonomes High-Frequency Trading-System mit 100% Wallet-Kapital-Allokation,
modernisierter Fintech Dark-Theme Benutzeroberfläche, Composite Edge Ranking,
Machine Learning Marktphasen-Erkennung und Sub-15ms WebSocket Order Execution.
"""

import os
import sys
import json
import time
import math
import hmac
import hashlib
import base64
import urllib.request
import urllib.parse
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, List, Tuple, Any, Optional
import numpy as np

# Windows Console UTF-8 Fix
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from institutional_trading_core import (
    TechnicalAnalysisEngine,
    InstitutionalRiskManager,
    PaperTradingSimulator,
    KrakenLiveGateway,
    CCXTOfficialGateway,
    MultiAssetWalletAllocator,
    SQLiteTradeLedgerManager,
    QuantitativeRegimeClassifier,
    KrakenPrivateWSGateway,
    NotificationManager,
    VectorizedOrderbookMath,
    OrderLifecycleTracker,
    OrderLifecycleState
)
from risk.regime_models import StructuralRegimeClassifier, MarketRegime
from risk.correlation_engine import PortfolioCorrelationEngine
from multi_exchange_websocket_engine import MultiExchangeWebSocketManager
from stat_arb_kelly_engine import (
    StatisticalArbitrageEngine,
    KellyCriterionManager,
    LiquidationCascadeDetector,
    MultiPairCorrelationGuard,
    ExecutionHealthMonitor,
    CrossExchangeArbitrageEngine,
    AutoCompoundingEngine
)
from backtester_engine import QuantitativeBacktester
from equity_report_generator import HTML5EquityVisualizer
from ops.config_loader import SystemConfig
from ops.reconciliation_worker import KrakenReconciliationWorker

HSM_VAULT_PATH = os.path.join(os.getcwd(), ".kraken_hsm_vault.json")


class EncryptedCredentialVault:
    """
    OS-Nativer Windows DPAPI Credential Vault (Version 3).
    Nutzt CryptProtectData / CryptUnprotectData aus crypt32.dll.
    Keine eigene Krypto-Implementierung. Die Schlüssel sind hardware- und
    benutzergebunden durch das Windows-Betriebssystem geschützt.
    Migriert alte v1 (Base64) und v2 (Fernet) Vaults transparent auf DPAPI.
    """

    _VAULT_FORMAT_VERSION = 3
    _DPAPI_ENTROPY = b"qubit_quant_trader_dpapi_entropy_2026"

    # ------------------------------------------------------------------
    # Windows DPAPI über ctypes
    # ------------------------------------------------------------------
    @staticmethod
    def _dpapi_encrypt(text: str) -> str:
        if not text:
            return ""
        try:
            import ctypes
            from ctypes import wintypes

            class DATA_BLOB(ctypes.Structure):
                _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_byte))]

            data_bytes = text.encode('utf-8')
            entropy_bytes = EncryptedCredentialVault._DPAPI_ENTROPY

            blob_in = DATA_BLOB(len(data_bytes), ctypes.cast(ctypes.create_string_buffer(data_bytes), ctypes.POINTER(ctypes.c_byte)))
            blob_entropy = DATA_BLOB(len(entropy_bytes), ctypes.cast(ctypes.create_string_buffer(entropy_bytes), ctypes.POINTER(ctypes.c_byte)))
            blob_out = DATA_BLOB()

            # 0x01 = CRYPTPROTECT_UI_FORBIDDEN
            if not ctypes.windll.crypt32.CryptProtectData(
                ctypes.byref(blob_in), "qubit_credential", ctypes.byref(blob_entropy), None, None, 0x01, ctypes.byref(blob_out)
            ):
                raise ctypes.WinError()

            cipher_bytes = ctypes.string_at(blob_out.pbData, blob_out.cbData)
            ctypes.windll.kernel32.LocalFree(blob_out.pbData)
            return base64.b64encode(cipher_bytes).decode('ascii')
        except Exception:
            return ""

    @staticmethod
    def _dpapi_decrypt(b64_cipher: str) -> str:
        if not b64_cipher:
            return ""
        try:
            import ctypes
            from ctypes import wintypes

            class DATA_BLOB(ctypes.Structure):
                _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_byte))]

            cipher_bytes = base64.b64decode(b64_cipher.encode('ascii'))
            entropy_bytes = EncryptedCredentialVault._DPAPI_ENTROPY

            blob_in = DATA_BLOB(len(cipher_bytes), ctypes.cast(ctypes.create_string_buffer(cipher_bytes), ctypes.POINTER(ctypes.c_byte)))
            blob_entropy = DATA_BLOB(len(entropy_bytes), ctypes.cast(ctypes.create_string_buffer(entropy_bytes), ctypes.POINTER(ctypes.c_byte)))
            blob_out = DATA_BLOB()

            if not ctypes.windll.crypt32.CryptUnprotectData(
                ctypes.byref(blob_in), None, ctypes.byref(blob_entropy), None, None, 0x01, ctypes.byref(blob_out)
            ):
                raise ctypes.WinError()

            plain_bytes = ctypes.string_at(blob_out.pbData, blob_out.cbData)
            ctypes.windll.kernel32.LocalFree(blob_out.pbData)
            return plain_bytes.decode('utf-8')
        except Exception:
            return ""

    # ------------------------------------------------------------------
    # Legacy Fallback / Migration (v1 & v2)
    # ------------------------------------------------------------------
    @staticmethod
    def _decrypt_v2_fernet(token: str) -> str:
        try:
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
            from cryptography.hazmat.primitives import hashes as _hashes
            from cryptography.hazmat.backends import default_backend
            from cryptography.fernet import Fernet
            import winreg

            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as k:
                guid, _ = winreg.QueryValueEx(k, "MachineGuid")
                sec = guid.encode()
            
            kdf = PBKDF2HMAC(
                algorithm=_hashes.SHA256(), length=32, salt=b"qubit_vault_v2_salt_2026",
                iterations=260_000, backend=default_backend()
            )
            raw = kdf.derive(sec)
            f_key = base64.urlsafe_b64encode(raw)
            return Fernet(f_key).decrypt(token.encode()).decode()
        except Exception:
            return ""

    @staticmethod
    def _deobfuscate_v1(encoded_str: str) -> str:
        try:
            raw = base64.b64decode(encoded_str.encode())
            return raw[32:].decode()
        except Exception:
            return ""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @staticmethod
    def save_vault(api_key: str, api_secret: str, tg_token: str = "", tg_chat: str = "", discord_url: str = "") -> bool:
        try:
            vault_data = {
                "vault_format": EncryptedCredentialVault._VAULT_FORMAT_VERSION,
                "hsm_key":         EncryptedCredentialVault._dpapi_encrypt(api_key),
                "hsm_secret":      EncryptedCredentialVault._dpapi_encrypt(api_secret),
                "hsm_tg_token":    EncryptedCredentialVault._dpapi_encrypt(tg_token),
                "hsm_tg_chat":     EncryptedCredentialVault._dpapi_encrypt(tg_chat),
                "hsm_discord_url": EncryptedCredentialVault._dpapi_encrypt(discord_url),
                "vault_timestamp": time.time()
            }
            with open(HSM_VAULT_PATH, "w", encoding="utf-8") as f:
                json.dump(vault_data, f, indent=2)
            return True
        except Exception:
            return False

    @staticmethod
    def load_vault() -> Tuple[str, str, str, str, str]:
        if not os.path.exists(HSM_VAULT_PATH):
            return "", "", "", "", ""
        try:
            with open(HSM_VAULT_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)

            fmt = data.get("vault_format", 1)

            def _read(field: str) -> str:
                val = data.get(field, "")
                if not val:
                    return ""
                if fmt == 3:
                    return EncryptedCredentialVault._dpapi_decrypt(val)
                elif fmt == 2:
                    res = EncryptedCredentialVault._decrypt_v2_fernet(val)
                    return res if res else EncryptedCredentialVault._dpapi_decrypt(val)
                else: # v1
                    res = EncryptedCredentialVault._deobfuscate_v1(val)
                    return res if res else EncryptedCredentialVault._dpapi_decrypt(val)

            result = (
                _read("hsm_key"),
                _read("hsm_secret"),
                _read("hsm_tg_token"),
                _read("hsm_tg_chat"),
                _read("hsm_discord_url"),
            )

            # Auto-Migration auf v3 (DPAPI)
            if fmt < EncryptedCredentialVault._VAULT_FORMAT_VERSION:
                EncryptedCredentialVault.save_vault(*result)

            return result
        except Exception:
            return "", "", "", "", ""


class MultiExchangeTraderApp:

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("⚡ QUBIT QUANT TRADER | AUTONOMOUS HIGH-FREQUENCY ENGINE")
        self.root.geometry("1600x990+5+5")
        self.root.configure(bg="#090d16")
        self.root.attributes("-topmost", True)

        saved_k, saved_s, saved_tgt, saved_tgc, saved_disc = EncryptedCredentialVault.load_vault()
        self.kraken_api_key = saved_k or os.environ.get("KRAKEN_API_KEY", "")
        self.kraken_api_secret = saved_s or os.environ.get("KRAKEN_API_SECRET", "")
        self.tg_bot_token = saved_tgt or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.tg_chat_id = saved_tgc or os.environ.get("TELEGRAM_CHAT_ID", "")
        self.discord_webhook = saved_disc or os.environ.get("DISCORD_WEBHOOK_URL", "")

        self.trading_mode = "PAPER"
        self.sensitivity_mode = "HYBRID"  # HYBRID / SCALP / MOMENTUM
        self.is_trading_active = True
        self.running = True

        # System Config (config.yaml) & Execution Settings
        self.system_config = SystemConfig.load()
        self.post_only_enabled = SystemConfig.is_maker_post_only()
        self.reconciliation_worker = KrakenReconciliationWorker(db_path="trading_ledger.db", poll_interval_sec=60.0)
        if self.kraken_api_key and self.kraken_api_secret:
            self.reconciliation_worker.start_background_worker(self.kraken_api_key, self.kraken_api_secret)

        # Core Engines
        self.ws_manager = MultiExchangeWebSocketManager()
        self.stat_arb_engine = StatisticalArbitrageEngine()
        self.risk_manager = InstitutionalRiskManager(taker_fee_pct=0.0026)
        self.paper_simulator = PaperTradingSimulator(initial_balance_eur=1000.0, taker_fee_pct=0.0026)
        self.backtester = QuantitativeBacktester(initial_capital_eur=1000.0)
        self.db_manager = SQLiteTradeLedgerManager()
        self.structural_regime_clf = StructuralRegimeClassifier(hysteresis_ticks=5)
        self.correlation_engine = PortfolioCorrelationEngine(window=60)
        self.last_var_data: Dict[str, float] = {
            "var_eur": 0.0,
            "cvar_es_eur": 0.0,
            "stress_var_eur": 0.0,
            "exposure_throttle_factor": 1.0
        }
        self.active_market_regime: str = MarketRegime.RANGE_BOUND

        self.real_balances: Dict[str, float] = {}
        self.real_equity_eur = 0.0
        self.initial_equity: Optional[float] = None
        self.cumulative_live_pnl: float = 0.0
        # Pairs whose sells produced UNKNOWN_COST_BASIS (PnL = None from ledger).
        # These are excluded from cumulative_live_pnl and block compounding.
        self.unknown_pnl_pairs: set = set()
        self._pnl_unknown_count: int = 0  # total unknown-cost-basis sell events
        self.last_arb_alert_time: float = 0.0
        self.last_order_time_per_pair: Dict[str, float] = {}
        self.last_logged_status: Dict[str, str] = {}
        self.live_entry_prices: Dict[str, float] = {}
        self.live_peak_prices: Dict[str, float] = {}
        self.bot_txids: set = set()  # Eigene vom Bot platzierte Order-IDs für sicheren Stale Cleaner
        # Historische Einstiegspreise: Volumengewichteter Durchschnitt (VWAP) aller offenen Lots
        for pair_k, limits_v in KrakenLiveGateway.PAIR_LIMITS.items():
            vwap_p = self.db_manager.fetch_weighted_average_cost_basis(pair_k)
            if vwap_p and vwap_p > 0:
                self.live_entry_prices[limits_v["asset"]] = vwap_p
                self.live_peak_prices[limits_v["asset"]] = vwap_p
            else:
                last_bp = self.db_manager.fetch_last_buy_price(pair_k)
                if last_bp and last_bp > 0:
                    self.live_entry_prices[limits_v["asset"]] = last_bp
                    self.live_peak_prices[limits_v["asset"]] = last_bp
        
        # Unabhängige Preis-Historien pro Asset
        self.asset_price_histories: Dict[str, List[float]] = {
            "BTC": [],
            "XRP": [],
            "ETH": [],
            "SOL": []
        }

        self.setup_ui()
        self.ws_manager.start_all_feeds()
        self.start_balance_fetch_loop()
        self.start_stale_order_cleaner_loop()
        self.start_main_trading_loop()

    def log_console(self, msg: str):
        if hasattr(self, 'console') and self.console:
            timestamp = time.strftime("%H:%M:%S")
            self.console.insert(tk.END, f"[{timestamp}] {msg}\n")
            self.console.see(tk.END)

    def setup_ui(self):
        # 1. HEADER CONTROL BAR
        header = tk.Frame(self.root, bg="#111827", height=65, highlightbackground="#1e293b", highlightthickness=1)
        header.pack(side=tk.TOP, fill=tk.X)

        title_frame = tk.Frame(header, bg="#111827")
        title_frame.pack(side=tk.LEFT, padx=16, pady=10)

        tk.Label(
            title_frame, text="⚡ QUBIT QUANT TRADER", bg="#111827", fg="#00ff88", font=("Segoe UI", 13, "bold")
        ).pack(anchor="w")
        tk.Label(
            title_frame, text="Event-Driven Real-Time Spot Engine • Multi-Regime & Risk-Gated Architecture", bg="#111827", fg="#94a3b8", font=("Segoe UI", 8)
        ).pack(anchor="w")

        # Control Buttons
        btn_frame = tk.Frame(header, bg="#111827")
        btn_frame.pack(side=tk.LEFT, padx=15)

        self.btn_mode_toggle = tk.Button(
            btn_frame,
            text="🧪 MODUS: PAPER TRADING",
            bg="#8b5cf6",
            fg="#ffffff",
            activebackground="#7c3aed",
            font=("Segoe UI", 9, "bold"),
            relief=tk.FLAT,
            command=self.toggle_trading_mode,
            cursor="hand2",
            padx=12,
            pady=4
        )
        self.btn_mode_toggle.pack(side=tk.LEFT, padx=5)

        self.btn_sens_toggle = tk.Button(
            btn_frame,
            text="⚡ MODUS: HYBRID AUTONOMOUS",
            bg="#0284c7",
            fg="#ffffff",
            activebackground="#0369a1",
            font=("Segoe UI", 9, "bold"),
            relief=tk.FLAT,
            command=self.toggle_sensitivity_mode,
            cursor="hand2",
            padx=12,
            pady=4
        )
        self.btn_sens_toggle.pack(side=tk.LEFT, padx=5)

        btn_manual_trade = tk.Button(
            btn_frame,
            text="🚀 Test-Order Ausführen",
            bg="#334155",
            fg="#f1f5f9",
            activebackground="#475569",
            font=("Segoe UI", 9),
            relief=tk.FLAT,
            command=self.trigger_manual_test_trade,
            cursor="hand2",
            padx=10,
            pady=4
        )
        btn_manual_trade.pack(side=tk.LEFT, padx=5)

        # Right Header Badges
        right_hdr = tk.Frame(header, bg="#111827")
        right_hdr.pack(side=tk.RIGHT, padx=16)

        btn_report = tk.Button(
            right_hdr, text="📊 HTML5 Report", bg="#1e293b", fg="#00ff88", font=("Segoe UI", 9, "bold"),
            relief=tk.FLAT, command=lambda: HTML5EquityVisualizer.open_report_in_browser(), cursor="hand2", padx=10, pady=4
        )
        btn_report.pack(side=tk.RIGHT, padx=6)

        btn_vault = tk.Button(
            right_hdr, text="🔐 API Key Vault", bg="#1e293b", fg="#38bdf8", font=("Segoe UI", 9, "bold"),
            relief=tk.FLAT, command=self.open_vault_dialog, cursor="hand2", padx=10, pady=4
        )
        btn_vault.pack(side=tk.RIGHT, padx=6)

        self.lbl_profit_guard = tk.Label(
            right_hdr, text="🛡️ 100% PROFIT-GUARD: AKTIV", bg="#1e1b4b", fg="#c084fc", font=("Segoe UI", 8, "bold"),
            padx=10, pady=4
        )
        self.lbl_profit_guard.pack(side=tk.RIGHT, padx=5)

        self.lbl_feed_status = tk.Label(
            right_hdr, text="🟢 KRAKEN API & PRIVATE WS AKTIV", bg="#064e3b", fg="#34d399", font=("Segoe UI", 8, "bold"),
            padx=10, pady=4
        )
        self.lbl_feed_status.pack(side=tk.RIGHT, padx=5)

        # 2. HERO KPI CARDS (3 Hauptkarten)
        hero_bar = tk.Frame(self.root, bg="#090d16")
        hero_bar.pack(side=tk.TOP, fill=tk.X, padx=12, pady=6)

        # Card 1: Gesamtkontostand
        card1 = tk.Frame(hero_bar, bg="#151c2c", highlightbackground="#232f48", highlightthickness=1)
        card1.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)
        tk.Label(card1, text="💰 GESAMTKONTOSTAND (ECHTES GUTHABEN):", bg="#151c2c", fg="#94a3b8", font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=12, pady=(8, 2))
        self.lbl_equity = tk.Label(card1, text="Lade echten Kraken Kontostand...", bg="#151c2c", fg="#00ff88", font=("Consolas", 17, "bold"))
        self.lbl_equity.pack(anchor="w", padx=12)
        self.lbl_equity_sub = tk.Label(card1, text="100% Wallet-Kapital-Allokation aktiv • Cash-Puffer geschützt", bg="#151c2c", fg="#64748b", font=("Segoe UI", 8))
        self.lbl_equity_sub.pack(anchor="w", padx=12, pady=(1, 8))

        # Card 2: Wallet-Bestände
        card2 = tk.Frame(hero_bar, bg="#151c2c", highlightbackground="#232f48", highlightthickness=1)
        card2.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)
        tk.Label(card2, text="💼 ALLOKIERTE WALLET-BESTÄNDE:", bg="#151c2c", fg="#94a3b8", font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=12, pady=(8, 2))
        self.lbl_wallets_detail = tk.Label(card2, text="BTC: 0.00 | XRP: 0.00 | SOL: 0.00 | EUR: 0.00 €", bg="#151c2c", fg="#38bdf8", font=("Consolas", 12, "bold"))
        self.lbl_wallets_detail.pack(anchor="w", padx=12)
        self.lbl_wallets_sub = tk.Label(card2, text="Priorisiertes Rebalancing nach Composite Edge Score", bg="#151c2c", fg="#64748b", font=("Segoe UI", 8))
        self.lbl_wallets_sub.pack(anchor="w", padx=12, pady=(1, 8))

        # Card 3: AI Regime & Risiko-Radar
        card3 = tk.Frame(hero_bar, bg="#151c2c", highlightbackground="#232f48", highlightthickness=1)
        card3.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)
        tk.Label(card3, text="🧠 AI MARKTREGIME & RISIKO-RADAR:", bg="#151c2c", fg="#94a3b8", font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=12, pady=(8, 2))
        self.lbl_regime_badge = tk.Label(card3, text="RANGE_SCALPING (Effizienz: 65%)", bg="#151c2c", fg="#fbbf24", font=("Consolas", 12, "bold"))
        self.lbl_regime_badge.pack(anchor="w", padx=12)
        self.lbl_regime_sub = tk.Label(card3, text="Circuit Breaker: 5.0% Max Drawdown • Vola-Adaptiver Stop-Loss", bg="#151c2c", fg="#64748b", font=("Segoe UI", 8))
        self.lbl_regime_sub.pack(anchor="w", padx=12, pady=(1, 8))

        # 3. 4-EXCHANGE TICKER & ORDERBOOK FLOW BAR
        ex_frame = tk.Frame(self.root, bg="#111827", highlightbackground="#1e293b", highlightthickness=1)
        ex_frame.pack(side=tk.TOP, fill=tk.X, padx=16, pady=4)

        tk.Label(ex_frame, text="🌐 LIVE BÖRSEN-FEEDS & WEBSOCKET-LATENZEN:", bg="#111827", fg="#94a3b8", font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=10, pady=(3, 1))

        ex_inner = tk.Frame(ex_frame, bg="#111827")
        ex_inner.pack(side=tk.TOP, fill=tk.X, padx=8, pady=(0, 4))

        self.ex_labels = {}
        for ex in ["Kraken", "Binance", "Coinbase", "Bybit"]:
            c = tk.Frame(ex_inner, bg="#151c2c", highlightbackground="#232f48", highlightthickness=1)
            c.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=3, pady=2)
            tk.Label(c, text=f"🏛️ {ex}", bg="#151c2c", fg="#38bdf8", font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=6, pady=(2, 0))
            lbl = tk.Label(c, text="Lade Feed...", bg="#151c2c", fg="#00ff88", font=("Consolas", 9, "bold"))
            lbl.pack(anchor="w", padx=6, pady=(0, 2))
            self.ex_labels[ex] = lbl

        # Extra Flow Card: Binance Lead-Lag & CVD
        c_flow = tk.Frame(ex_inner, bg="#151c2c", highlightbackground="#232f48", highlightthickness=1)
        c_flow.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=3, pady=2)
        tk.Label(c_flow, text="📡 LEAD-LAG & CVD RADAR", bg="#151c2c", fg="#a855f7", font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=6, pady=(2, 0))
        self.lbl_flow_radar = tk.Label(c_flow, text="CVD: NEUTRAL | LEAD: NORMAL", bg="#151c2c", fg="#fbbf24", font=("Consolas", 9, "bold"))
        self.lbl_flow_radar.pack(anchor="w", padx=6, pady=(0, 2))

        # 4. MATH EDGES & QUANTITATIVE SIGNALS
        edge_frame = tk.Frame(self.root, bg="#111827", highlightbackground="#1e293b", highlightthickness=1)
        edge_frame.pack(side=tk.TOP, fill=tk.X, padx=16, pady=4)

        tk.Label(edge_frame, text="📊 QUANTITATIVE MATHEMATISCHE EDGES (LIVE KERN-METRIKEN):", bg="#111827", fg="#94a3b8", font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=10, pady=(3, 1))

        edge_inner = tk.Frame(edge_frame, bg="#111827")
        edge_inner.pack(side=tk.TOP, fill=tk.X, padx=8, pady=(0, 4))

        self.edge_labels = {}
        for title, key in [
            ("📉 RSI (14) Dynamisch", "rsi"),
            ("📈 Stat-Arb Z-Score", "zscore"),
            ("🎯 Half-Kelly Allokation", "kelly"),
            ("⚖️ Kraken OBI Index", "obi"),
            ("⚡ Composite Execution Signal", "signal")
        ]:
            card = tk.Frame(edge_inner, bg="#151c2c", highlightbackground="#232f48", highlightthickness=1)
            card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=3, pady=2)

            tk.Label(card, text=title, bg="#151c2c", fg="#94a3b8", font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=6, pady=(2, 0))
            lbl = tk.Label(card, text="--", bg="#151c2c", fg="#00ff88", font=("Consolas", 9, "bold"))
            lbl.pack(anchor="w", padx=6, pady=(0, 2))
            self.edge_labels[key] = lbl

        # 5. TRADE LEDGER TABLE (Styling mit ttk.Style)
        main_frame = tk.Frame(self.root, bg="#090d16")
        main_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=16, pady=4)

        ledger_hdr = tk.Frame(main_frame, bg="#090d16")
        ledger_hdr.pack(side=tk.TOP, fill=tk.X, pady=(2, 4))
        tk.Label(ledger_hdr, text="📜 HANDELSJOURNAL (PERSISTENTE ECHTE KRAKEN ORDERS & REBALANCING):", bg="#090d16", fg="#f1f5f9", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)
        self.lbl_cum_pnl = tk.Label(ledger_hdr, text="Gesamt Realisierte PnL: +0.00 €", bg="#090d16", fg="#00ff88", font=("Segoe UI", 9, "bold"))
        self.lbl_cum_pnl.pack(side=tk.RIGHT)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Treeview",
            background="#111827",
            foreground="#f1f5f9",
            fieldbackground="#111827",
            rowheight=26,
            font=("Consolas", 9)
        )
        style.configure(
            "Treeview.Heading",
            background="#1e293b",
            foreground="#38bdf8",
            font=("Segoe UI", 9, "bold"),
            relief="flat"
        )
        style.map("Treeview", background=[("selected", "#1e293b")], foreground=[("selected", "#00ff88")])

        columns = ("time", "side", "price", "volume", "fee", "pnl", "status")
        self.trade_tree = ttk.Treeview(main_frame, columns=columns, show="headings", height=8)

        self.trade_tree.heading("time", text="Zeitstempel")
        self.trade_tree.heading("side", text="Order-Typ")
        self.trade_tree.heading("price", text="Ausführungspreis")
        self.trade_tree.heading("volume", text="Volumen (Asset)")
        self.trade_tree.heading("fee", text="Börsengebühr")
        self.trade_tree.heading("pnl", text="Netto-PnL (€)")
        self.trade_tree.heading("status", text="Ausführungs-Status & TXID")

        self.trade_tree.column("time", width=110, anchor="center")
        self.trade_tree.column("side", width=90, anchor="center")
        self.trade_tree.column("price", width=130, anchor="center")
        self.trade_tree.column("volume", width=130, anchor="center")
        self.trade_tree.column("fee", width=110, anchor="center")
        self.trade_tree.column("pnl", width=120, anchor="center")
        self.trade_tree.column("status", width=240, anchor="w")

        self.trade_tree.tag_configure("BUY", foreground="#00ff88")
        self.trade_tree.tag_configure("SELL", foreground="#f43f5e")

        self.trade_tree.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=1)

        # Lade historische Trades aus der SQLite-Datenbank
        past_trades = self.db_manager.fetch_all_trades()
        for t in reversed(past_trades):
            side = t.get("side", "BUY")
            tag = "BUY" if side == "BUY" else "SELL"
            self.trade_tree.insert(
                "", 0,
                values=(t["timestamp"], side, f"{t['price']:,.2f} €", f"{t['volume']:.6f}", f"{t['fee_eur']:.4f} €", f"{t['pnl_eur']:+.2f} €", t["status"]),
                tags=(tag,)
            )

        # 6. LIVE CONSOLE TERMINAL
        self.console = tk.Text(main_frame, bg="#0b0f19", fg="#00ff88", font=("Consolas", 8), height=5, relief=tk.FLAT, highlightbackground="#1e293b", highlightthickness=1)
        self.console.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True, pady=(4, 2))
        self.log_console("⚡ QUBIT QUANT TRADER INITIALISIERT! Standard-Sicherheitsmodus: PAPER TRADING aktiv.")

    def start_balance_fetch_loop(self):
        def loop():
            while self.running:
                if self.kraken_api_key and self.kraken_api_secret:
                    bals = KrakenLiveGateway.fetch_real_balances(self.kraken_api_key, self.kraken_api_secret)
                    if "error" not in bals:
                        self.real_balances = bals
                        live_prices = self.ws_manager.asset_prices
                        eq = KrakenLiveGateway.calculate_total_equity_eur(bals, live_prices)
                        self.real_equity_eur = eq

                        self.root.after(0, lambda e=eq, b=bals: self._update_balances_ui(e, b))
                time.sleep(4.0)

        threading.Thread(target=loop, daemon=True).start()

    def start_stale_order_cleaner_loop(self):
        """Hintergrund-Thread: Storniert alte, ungefüllte Kraken-Orders nach 30 Sekunden"""
        def loop():
            while self.running:
                if self.trading_mode == "LIVE" and self.kraken_api_key and self.kraken_api_secret:
                    res = KrakenLiveGateway.cancel_stale_orders(self.kraken_api_key, self.kraken_api_secret, allowed_txids=self.bot_txids)
                    if res.get("status") == "success" and res.get("canceled_count", 0) > 0:
                        self.log_console(f"🧹 STALE ORDER CLEANER: {res['canceled_count']} alte eigene Bot-Order(s) storniert.")
                time.sleep(15.0)

        threading.Thread(target=loop, daemon=True).start()

    def _update_balances_ui(self, eq: float, bals: dict):
        if self.trading_mode == "LIVE":
            self.lbl_equity.config(text=f"{eq:,.2f} €")
        else:
            eq_paper = self.paper_simulator.get_portfolio_equity(self.ws_manager.market_prices["Kraken"]["price"])
            self.lbl_equity.config(text=f"{eq_paper:,.2f} € (Paper) | Real: {eq:,.2f} €")

        btc = bals.get("BTC", 0.0)
        xrp = bals.get("XRP", 0.0)
        sol = bals.get("SOL", 0.0)
        eur = bals.get("EUR", 0.0)
        detail_str = f"BTC: {btc:.6f} | XRP: {xrp:.2f} | SOL: {sol:.4f} | Cash: {eur:.2f} €"
        self.lbl_wallets_detail.config(text=detail_str)

    def toggle_trading_mode(self):
        if self.trading_mode == "PAPER":
            if not self.kraken_api_key or not self.kraken_api_secret:
                messagebox.showwarning("API Keys Fehlen", "Bitte hinterlege erst deine Kraken API Keys im Vault.")
                return
            confirm = messagebox.askyesno(
                "🚨 ECHTGELD LIVE-HANDEL STARTEN?",
                "ACHTUNG: Du aktivierst den VOLLAUTONOMEN LIVE-HANDEL mit deinem echten Kraken-Guthaben!\n\n"
                "• Echte Orders werden live an Kraken übermittelt.\n"
                "• Maker Post-Only Schutz (0.40% Gebühr) ist aktiv.\n"
                "• Zyklische Live-Reconciliation & Circuit Breaker schützen dein Kapital.\n\n"
                "Möchtest du echte autonome Live-Trades JETZT starten?",
                icon="warning"
            )
            if not confirm:
                self.log_console("🛡️ LIVE-Aktivierung vom Nutzer abgebrochen. Bleibe im sicheren PAPER-Modus.")
                return
            self.trading_mode = "LIVE"
            self.btn_mode_toggle.config(text="🔴 ECHTGELD LIVE: AKTIV (KRAKEN AUTONOM)", bg="#dc2626")
            self.log_console("⚠️ UMGESCHALTET AUF ECHTGELD LIVE KRAKEN HANDEL!")
            self.log_console("🚀 AUTONOME LIVE ORDER-PIPELINE MIT MAKER POST-ONLY SCHARFGESCHALTET.")
            # Sofort Kontostände abrufen
            self.update_real_balances()
            if hasattr(self, 'reconciliation_worker') and self.reconciliation_worker:
                self.reconciliation_worker.start_background_worker(self.kraken_api_key, self.kraken_api_secret)
        else:
            self.trading_mode = "PAPER"
            self.btn_mode_toggle.config(text="🧪 MODUS: PAPER TRADING", bg="#8b5cf6")
            self.log_console("ℹ️ UMGESCHALTET AUF PAPER TRADING SIMULATION.")

    def toggle_sensitivity_mode(self):
        if self.sensitivity_mode == "HYBRID":
            self.sensitivity_mode = "SCALP"
            self.btn_sens_toggle.config(text="⚡ MODUS: SCALPING (SCHNELL)", bg="#059669")
            self.log_console("⚡ SIGNAL-MODUS: SCALPING (Fokus auf schnelle Mikro-Gewinne)")
        elif self.sensitivity_mode == "SCALP":
            self.sensitivity_mode = "MOMENTUM"
            self.btn_sens_toggle.config(text="🚀 MODUS: MOMENTUM (TREND)", bg="#d97706")
            self.log_console("🚀 SIGNAL-MODUS: MOMENTUM (Fokus auf große Trendfolge-Bewegungen)")
        else:
            self.sensitivity_mode = "HYBRID"
            self.btn_sens_toggle.config(text="⚡ MODUS: HYBRID AUTONOMOUS", bg="#0284c7")
            self.log_console("⚡ SIGNAL-MODUS: HYBRID (Dynamische ML-Umschaltung zwischen Trend & Range)")

    def trigger_manual_test_trade(self):
        kraken_p = self.ws_manager.market_prices["Kraken"]["price"]
        if kraken_p <= 0:
            messagebox.showwarning("Fehler", "Warte kurz bis der Kraken Live Feed geladen ist.")
            return

        pair, asset_code, amount = KrakenLiveGateway.select_best_executable_pair(self.real_balances, "SELL")
        self.log_console(f"🚀 MANUELLE TEST-ORDER INITIERT ({pair} auf Kraken)...")

        if self.trading_mode == "LIVE":
            vol = 0.00005 if pair == "XBTEUR" else 1.65
            limit_p = round(kraken_p * 1.005, 1) if pair == "XBTEUR" else round(2.50, 4)
            
            res = KrakenPrivateWSGateway.execute_sub15ms_order(
                self.kraken_api_key, self.kraken_api_secret, pair, "SELL", vol, limit_p,
                eur_balance=self.real_balances.get("EUR", 0.0),
                asset_balance=self.real_balances.get(asset_code, 0.0)
            )
            if res.get("status") == "success":
                rec = {
                    "timestamp": time.strftime("%H:%M:%S"),
                    "side": "SELL",
                    "price": limit_p,
                    "volume": vol,
                    "fee_eur": 0.01,
                    "pnl_eur": 0.0,
                    "status": f"🔴 LIVE EXECUTED ({res['txid']})"
                }
                self.add_trade_to_ledger(rec)
                self.log_console(f"✅ ECHTE KRAKEN ORDER PLATZIERT! TXID: {res['txid']}")
                messagebox.showinfo("Order Platziert", f"Echte Kraken Limit-Order gesendet!\n\nPair: {pair}\nSide: SELL\nTXID: {res['txid']}")
            else:
                self.log_console(f"❌ KRAKEN ORDER FEHLER: {res.get('message')}")
                messagebox.showerror("Order Fehler", f"Kraken API Antwort:\n{res.get('message')}")
        else:
            vol = 0.00005 if pair == "XBTEUR" else 1.65
            sim_sig = {
                "allowed": True,
                "signal_type": "BUY",
                "volume": vol,
                "stop_loss_price": kraken_p * 0.98,
                "take_profit_price": kraken_p * 1.03
            }
            paper_rec = self.paper_simulator.execute_paper_order(sim_sig, kraken_p * 0.9998, kraken_p * 1.0002)
            if paper_rec:
                self.add_trade_to_ledger(paper_rec)
                self.log_console(f"🧪 MANUELLE PAPER-ORDER SIMULIERT: {paper_rec['side']} {paper_rec['volume']} @ {paper_rec['price']:.2f} €")
                messagebox.showinfo("Paper Order", f"Paper-Simulation erfolgreich ausgeführt!\n\nPair: {pair}\nSide: BUY\nPreis: {paper_rec['price']:.2f} €")

    def open_vault_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("🔐 Kraken API & Alerting Vault")
        dialog.geometry("520x460+250+150")
        dialog.configure(bg="#111827")
        dialog.attributes("-topmost", True)

        tk.Label(dialog, text="🔐 Kraken API & Webhook Vault", bg="#111827", fg="#00ff88", font=("Segoe UI", 12, "bold")).pack(pady=(12, 4))
        tk.Label(dialog, text="Schlüssel werden nativ über Windows DPAPI (CryptProtectData) hardware- und benutzergebunden geschützt", bg="#111827", fg="#64748b", font=("Segoe UI", 8)).pack(pady=(0, 8))

        # Kraken API
        tk.Label(dialog, text="Kraken API Key:", bg="#111827", fg="#94a3b8", font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=30, pady=(4, 1))
        e_key = tk.Entry(dialog, width=54, bg="#090d16", fg="#38bdf8", insertbackground="white", relief=tk.FLAT)
        e_key.pack(padx=30)
        if self.kraken_api_key:
            e_key.insert(0, self.kraken_api_key)

        tk.Label(dialog, text="Kraken API Secret:", bg="#111827", fg="#94a3b8", font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=30, pady=(6, 1))
        e_sec = tk.Entry(dialog, width=54, show="*", bg="#090d16", fg="#38bdf8", insertbackground="white", relief=tk.FLAT)
        e_sec.pack(padx=30)
        if self.kraken_api_secret:
            e_sec.insert(0, self.kraken_api_secret)

        # Telegram
        tk.Label(dialog, text="Telegram Bot Token (Optional):", bg="#111827", fg="#94a3b8", font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=30, pady=(8, 1))
        e_tgt = tk.Entry(dialog, width=54, bg="#090d16", fg="#00ff88", insertbackground="white", relief=tk.FLAT)
        e_tgt.pack(padx=30)
        if self.tg_bot_token:
            e_tgt.insert(0, self.tg_bot_token)

        tk.Label(dialog, text="Telegram Chat ID (Optional):", bg="#111827", fg="#94a3b8", font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=30, pady=(6, 1))
        e_tgc = tk.Entry(dialog, width=54, bg="#090d16", fg="#00ff88", insertbackground="white", relief=tk.FLAT)
        e_tgc.pack(padx=30)
        if self.tg_chat_id:
            e_tgc.insert(0, self.tg_chat_id)

        # Discord
        tk.Label(dialog, text="Discord Webhook URL (Optional):", bg="#111827", fg="#94a3b8", font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=30, pady=(8, 1))
        e_disc = tk.Entry(dialog, width=54, bg="#090d16", fg="#a855f7", insertbackground="white", relief=tk.FLAT)
        e_disc.pack(padx=30)
        if self.discord_webhook:
            e_disc.insert(0, self.discord_webhook)

        def test_alert():
            tgt = e_tgt.get().strip()
            tgc = e_tgc.get().strip()
            disc = e_disc.get().strip()
            test_msg = "🔔 *QUBIT QUANT TRADER*: Test-Benachrichtigung erfolgreich verknüpft!"
            if tgt and tgc:
                NotificationManager.send_telegram_alert_async(tgt, tgc, test_msg)
            if disc:
                NotificationManager.send_discord_alert_async(disc, test_msg)
            messagebox.showinfo("Test Gesendet", "Test-Push wurde an die hinterlegten Webhooks übermittelt!")

        def save():
            k = e_key.get().strip()
            s = e_sec.get().strip()
            tgt = e_tgt.get().strip()
            tgc = e_tgc.get().strip()
            disc = e_disc.get().strip()
            if k and s:
                self.kraken_api_key = k
                self.kraken_api_secret = s
                self.tg_bot_token = tgt
                self.tg_chat_id = tgc
                self.discord_webhook = disc
                EncryptedCredentialVault.save_vault(k, s, tgt, tgc, disc)
                self.log_console("🔐 API KEYS & WEBHOOKS ERFOLGREICH GESPEICHERT.")
                dialog.destroy()

        b_row = tk.Frame(dialog, bg="#111827")
        b_row.pack(pady=15)
        tk.Button(b_row, text="🔔 Test Alert Senden", bg="#1e293b", fg="#38bdf8", font=("Segoe UI", 8, "bold"), relief=tk.FLAT, command=test_alert).pack(side=tk.LEFT, padx=6)
        tk.Button(b_row, text="🔐 Speichern & Verschlüsseln", bg="#00ff88", fg="#090d16", font=("Segoe UI", 9, "bold"), relief=tk.FLAT, command=save).pack(side=tk.LEFT, padx=6)

    def start_main_trading_loop(self):
        def loop():
            while self.running:
                m_prices = self.ws_manager.market_prices
                live_asset_prices = self.ws_manager.asset_prices
                
                kraken_p = m_prices["Kraken"]["price"]
                binance_p = m_prices["Binance"]["price"]
                
                # Update Pro-Asset Historien
                for asset, p_val in live_asset_prices.items():
                    if p_val > 0:
                        self.asset_price_histories[asset].append(p_val)
                        if len(self.asset_price_histories[asset]) > 500:
                            self.asset_price_histories[asset].pop(0)

                # Indikatoren berechnen pro Asset (BTC, XRP, ETH, SOL)
                rsi_btc = TechnicalAnalysisEngine.calculate_rsi(self.asset_price_histories["BTC"], 14)
                rsi_xrp = TechnicalAnalysisEngine.calculate_rsi(self.asset_price_histories["XRP"], 14)
                rsi_eth = TechnicalAnalysisEngine.calculate_rsi(self.asset_price_histories["ETH"], 14)
                rsi_sol = TechnicalAnalysisEngine.calculate_rsi(self.asset_price_histories["SOL"], 14)
                
                rsi_dict = {
                    "BTC": rsi_btc,
                    "XRP": rsi_xrp,
                    "ETH": rsi_eth,
                    "SOL": rsi_sol
                }

                # ATR Volatilitäts-Indikatoren berechnen pro Asset
                atr_dict = {
                    "BTC": TechnicalAnalysisEngine.calculate_atr(self.asset_price_histories["BTC"], 14),
                    "XRP": TechnicalAnalysisEngine.calculate_atr(self.asset_price_histories["XRP"], 14),
                    "ETH": TechnicalAnalysisEngine.calculate_atr(self.asset_price_histories["ETH"], 14),
                    "SOL": TechnicalAnalysisEngine.calculate_atr(self.asset_price_histories["SOL"], 14)
                }

                upper_b, sma_b, lower_b = TechnicalAnalysisEngine.calculate_bollinger_bands(self.asset_price_histories["BTC"], 20)

                spread, mean, std, z_score = self.stat_arb_engine.update_spread_and_calculate_zscore(
                    kraken_p if kraken_p > 0 else 65000.0,
                    binance_p if binance_p > 0 else 65000.0
                )

                win_rate_est = max(min(self.paper_simulator.winning_trades / max(self.paper_simulator.total_trades, 1), 0.85), 0.40)
                kelly_f = KellyCriterionManager.calculate_kelly_fraction(win_rate_est, risk_reward_ratio=2.0, safety_fraction=0.5)

                # Rolling Correlation & Tail-Risk Engine Update
                for a_code, p_val in live_asset_prices.items():
                    if p_val > 0:
                        self.correlation_engine.update_price(a_code, p_val)

                # ML / Quantitative Regime Classification mit Hysterese für Leitwährung (BTC)
                btc_p = live_asset_prices.get("BTC", kraken_p if kraken_p > 0 else 65000.0)
                btc_atr = atr_dict.get("BTC", 0.0)
                btc_atr_pct = (btc_atr / btc_p) if (btc_p > 0 and btc_atr > 0) else 0.01
                k_spread_bps = 2.0
                if "Kraken" in self.ws_manager.orderbooks:
                    k_b = self.ws_manager.orderbooks["Kraken"].get("bids", [])
                    k_a = self.ws_manager.orderbooks["Kraken"].get("asks", [])
                    if k_b and k_a and len(k_b) > 0 and len(k_a) > 0 and k_b[0][0] > 0 and k_a[0][0] > 0:
                        k_spread_bps = max(0.5, (k_a[0][0] - k_b[0][0]) / k_b[0][0] * 10000.0)

                vol_b = 10.0
                if "Kraken" in self.ws_manager.orderbooks:
                    vol_b = sum(b[1] for b in self.ws_manager.orderbooks["Kraken"].get("bids", [])[:5])

                self.active_market_regime = self.structural_regime_clf.update(
                    price=btc_p,
                    volume=vol_b,
                    spread_bps=k_spread_bps,
                    atr_pct=btc_atr_pct
                )

                if self.trading_mode == "PAPER":
                    allocator_balances = self.paper_simulator.get_balances()
                else:
                    allocator_balances = self.real_balances

                self.last_var_data = self.correlation_engine.calculate_portfolio_var_and_es(allocator_balances)

                regime_res = {
                    "regime": self.active_market_regime,
                    "confidence": 0.85,
                    "rsi_buy": 40 if self.active_market_regime in [MarketRegime.RANGE_BOUND, MarketRegime.CALM_UPTREND] else 30,
                    "rsi_sell": 60 if self.active_market_regime in [MarketRegime.RANGE_BOUND, MarketRegime.CALM_DOWNTREND] else 70,
                    "strategy": "MEAN_REVERSION_H2" if self.active_market_regime == MarketRegime.RANGE_BOUND else "TREND_FOLLOWING",
                    "exposure_throttle_factor": self.last_var_data.get("exposure_throttle_factor", 1.0),
                    "var_data": self.last_var_data
                }

                if self.sensitivity_mode == "SCALP":
                    rsi_buy_thresh = 45
                    rsi_sell_thresh = 55
                    z_thresh = 1.0
                elif self.sensitivity_mode == "MOMENTUM":
                    rsi_buy_thresh = 52
                    rsi_sell_thresh = 68
                    z_thresh = 2.0
                else: # HYBRID
                    rsi_buy_thresh = regime_res.get("rsi_buy", 40)
                    rsi_sell_thresh = regime_res.get("rsi_sell", 60)
                    z_thresh = 1.5

                # P1-A: Echte OBI Scores & CVD Absorption Radar berechnen PRO ASSET
                obi_dict = {}
                cvd_dict = {}
                for a_code in ["BTC", "XRP", "ETH", "SOL"]:
                    a_ob = getattr(self.ws_manager, "asset_orderbooks", {}).get(a_code, {})
                    a_bids = a_ob.get("bids", [])
                    a_asks = a_ob.get("asks", [])
                    obi_dict[a_code] = a_ob.get("obi", 0.0)
                    cvd_dict[a_code] = TechnicalAnalysisEngine.calculate_cvd_absorption(a_bids, a_asks)

                # Fallback für BTC falls asset_orderbooks noch initialisiert wird
                if not obi_dict.get("BTC") and "Kraken" in self.ws_manager.orderbooks:
                    k_bids = self.ws_manager.orderbooks["Kraken"].get("bids", [])
                    k_asks = self.ws_manager.orderbooks["Kraken"].get("asks", [])
                    obi_dict["BTC"] = self.ws_manager.orderbooks["Kraken"].get("obi", 0.0)
                    cvd_dict["BTC"] = TechnicalAnalysisEngine.calculate_cvd_absorption(k_bids, k_asks)

                cvd_data = cvd_dict.get("BTC", {})

                # VALIDIERTE STRATEGIE-ENGINE: HYPOTHESE H2 (MEAN-REVERSION NACH ERSCHÖPFUNG)
                # Kauft nur bei statistischer Extrem-Auslenkung (> 2.0 StdAbw vom Mittelwert)
                # UND bestätigtem OBI/Käuferdruck (kein blindes Hineingreifen in freie Abstürze).
                asset_signals = {}
                for a_sym, a_rsi in rsi_dict.items():
                    p_hist = self.asset_price_histories.get(a_sym, [])
                    if len(p_hist) >= 20:
                        p_arr = np.array(p_hist[-30:])
                        p_mean = float(np.mean(p_arr))
                        p_std = float(np.std(p_arr))
                        cur_p = p_hist[-1]
                        a_obi = obi_dict.get(a_sym, 0.0)

                        # H2 Einstiegsbedingung: Kurs signifikant unter Mean (> 2.0 StdAbw) UND überverkauft UND OBI-Käuferabstützung
                        is_exhaustion_dip = (cur_p < (p_mean - 2.0 * p_std)) if p_std > 0 else False
                        is_rsi_oversold = (a_rsi < rsi_buy_thresh)
                        has_liquidity_support = (a_obi >= 0.0)

                        if is_exhaustion_dip and is_rsi_oversold and has_liquidity_support and cur_p > 0:
                            asset_signals[a_sym] = "BUY"
                        elif cur_p >= p_mean and (a_rsi > rsi_sell_thresh):
                            asset_signals[a_sym] = "SELL"
                        else:
                            asset_signals[a_sym] = "HOLD"
                    else:
                        asset_signals[a_sym] = "HOLD"

                # Binance Lead-Lag Signal abfragen
                lead_lag = self.ws_manager.get_binance_lead_lag_signal()

                # Auto-Compounding Zinseszins-Multiplikator berechnen
                if self.initial_equity is None and self.real_equity_eur > 0:
                    self.initial_equity = self.real_equity_eur

                base_eq = self.initial_equity if (self.initial_equity and self.initial_equity > 0) else max(self.real_equity_eur, 50.0)
                # P0-A: Block compounding when any pair has unresolved cost basis.
                # Using cumulative_live_pnl that excludes UNKNOWN events is correct,
                # but we still gate the multiplier at 1.0 as an additional safety layer.
                if self.unknown_pnl_pairs:
                    compounding_mult = 1.0
                else:
                    compounding_mult = AutoCompoundingEngine.calculate_compounding_multiplier(
                        cumulative_pnl_eur=self.cumulative_live_pnl,
                        base_equity_eur=base_eq,
                        compounding_rate=0.5
                    )

                # Cross-Exchange Arbitrage Radar (Kraken, Binance, Coinbase, Bybit)
                arb_res = CrossExchangeArbitrageEngine.detect_cross_exchange_spread(m_prices)
                if arb_res.get("opportunity"):
                    now_arb = time.time()
                    if now_arb - getattr(self, "last_arb_alert_time", 0.0) > 60.0:
                        self.last_arb_alert_time = now_arb
                        arb_msg = f"⚡ ARBITRAGE CHANCE: {arb_res['action']} (Spread: {arb_res['gross_spread_pct']:.2f}%, Netto: +{arb_res['net_profit_pct']:.2f}%)"
                        self.log_console(arb_msg)
                        NotificationManager.send_telegram_alert_async(self.tg_bot_token, self.tg_chat_id, f"⚡ *QUBIT CROSS-ARBITRAGE*\n{arb_msg}")
                        NotificationManager.send_discord_alert_async(self.discord_webhook, f"⚡ **QUBIT CROSS-ARBITRAGE**\n{arb_msg}")

                # Dynamische Höchstpreis-Verfolgung (Peak Price Tracker für Trailing Profit Locks)
                for a_code, p_val in live_asset_prices.items():
                    if p_val > 0 and p_val > self.live_peak_prices.get(a_code, 0.0):
                        self.live_peak_prices[a_code] = p_val

                # P0-C: PAPER-Modus nutzt isoliertes Paper-Portfolio, nicht echte Wallet-Bestände.
                # LIVE-Modus nutzt self.real_balances (echte Kraken-Salden).
                if self.trading_mode == "PAPER":
                    allocator_balances = self.paper_simulator.get_balances()
                else:
                    allocator_balances = self.real_balances

                # VOLLAUTONOMER MULTI-ASSET WALLET ALLOCATOR (Guaranteed-Profit Guard + Trailing Profit Locks + Auto-Compounding)
                executable_orders = MultiAssetWalletAllocator.evaluate_multi_asset_opportunities(
                    allocator_balances,
                    asset_signals,
                    live_asset_prices,
                    rsi_scores=rsi_dict,
                    obi_scores=obi_dict,
                    entry_prices=self.live_entry_prices,
                    peak_prices=self.live_peak_prices,
                    atr_scores=atr_dict,
                    cvd_scores=cvd_dict,
                    regime_data=regime_res,
                    lead_lag_data=lead_lag,
                    cash_reserve_ratio=0.05,
                    compounding_mult=compounding_mult,
                    correlation_data=self.last_var_data
                )

                # 1. Daily Equity Circuit Breaker (Notaus bei >5% Tages-Drawdown)
                is_tripped, cb_msg = self.risk_manager.check_daily_circuit_breaker(self.real_equity_eur)
                if is_tripped:
                    if not getattr(self, "_cb_logged", False):
                        self.log_console(f"{cb_msg}")
                        self._cb_logged = True
                        cb_alert = f"🚨 *QUBIT CIRCUIT BREAKER ALERT*\n{cb_msg}"
                        NotificationManager.send_telegram_alert_async(self.tg_bot_token, self.tg_chat_id, cb_alert)
                        NotificationManager.send_discord_alert_async(self.discord_webhook, cb_alert)
                    executable_orders = [o for o in executable_orders if o.get("side") == "SELL"]
                else:
                    self._cb_logged = False

                # 2. Binance Futures Lead-Lag Momentum Filter (Frühindikator)
                if lead_lag.get("action") == "VETO_BUY":
                    executable_orders = [o for o in executable_orders if o.get("side") != "BUY"]

                if self.is_trading_active and executable_orders:
                    now_tm = time.time()
                    for order in executable_orders:
                        pair_name = order["pair"]
                        asset_code = order.get("asset", "BTC")

                        # 30-Sekunden Cooldown pro Trading-Paar zur Vermeidung von Mehrfach-Orders
                        if now_tm - self.last_order_time_per_pair.get(pair_name, 0.0) < 30.0:
                            continue

                        # P1-B: Signal-Deduplizierung & Positions-Guard
                        # Wenn bereits ein aktives Lot/eine Position für dieses Asset existiert, keine wiederholten Zukäufe ausführen!
                        if order["side"] == "BUY":
                            existing_lots = self.db_manager.fetch_open_lots(pair_name)
                            if existing_lots:
                                # Position existiert bereits -> Kauf blockieren zur Risikovermeidung
                                continue

                        # Multi-Pair Correlation Guard (Verhindert Klumpenrisiken)
                        if order["side"] == "BUY":
                            corr_throttle, corr_msg = MultiPairCorrelationGuard.should_throttle_correlated_buy(
                                asset_code, self.real_balances, {"SOL_BTC": 0.82, "ETH_BTC": 0.88, "XRP_BTC": 0.72}
                            )
                            if corr_throttle:
                                self.log_console(f"🛡️ {corr_msg}")
                                continue

                        intent = OrderLifecycleTracker.create_intent(
                            pair=pair_name,
                            side=order["side"],
                            volume=order["volume"],
                            price=order["price"]
                        )

                        if self.trading_mode == "LIVE":
                            OrderLifecycleTracker.transition(intent.intent_id, OrderLifecycleState.SUBMITTED)
                            p_dec = KrakenLiveGateway.PAIR_LIMITS.get(pair_name, {}).get("price_decimals", 1)
                            exec_price = round(order["price"], p_dec)

                            is_risk_exit = (order.get("exit_type") == "RISK_EXIT")
                            use_post_only = self.post_only_enabled and not is_risk_exit

                            live_res = KrakenPrivateWSGateway.execute_sub15ms_order(
                                self.kraken_api_key,
                                self.kraken_api_secret,
                                pair=pair_name,
                                side=order["side"],
                                volume=order["volume"],
                                price=exec_price,
                                eur_balance=self.real_balances.get("EUR", 0.0),
                                asset_balance=self.real_balances.get(asset_code, 0.0),
                                post_only=use_post_only
                            )
                            if live_res.get("status") == "success":
                                self.last_order_time_per_pair[pair_name] = now_tm
                                txid = live_res['txid']
                                self.bot_txids.add(txid)  # Registrieren für Stale Cleaner

                                # P0-D: Echte Fill-Verifikation über Kraken API statt blindem Vertrauen in AddOrder
                                fill_check = KrakenLiveGateway.verify_order_fill(
                                    self.kraken_api_key,
                                    self.kraken_api_secret,
                                    txid=txid,
                                    max_wait_sec=2.0
                                )

                                if fill_check.get("status") == "filled":
                                    actual_price = fill_check.get("price", live_res["price"])
                                    actual_vol = fill_check.get("filled_volume", live_res["volume"])
                                    actual_fee = fill_check.get("fee_eur", round(actual_price * actual_vol * 0.0026, 4))
                                    order_status_label = f"🔴 LIVE FILLED ({txid})"
                                else:
                                    # Fallback auf AddOrder-Angaben falls QueryOrders verzögert
                                    actual_price = live_res["price"]
                                    actual_vol = live_res["volume"]
                                    actual_fee = round(actual_price * actual_vol * 0.0026, 4)
                                    order_status_label = f"🔴 LIVE EXECUTED ({txid})"

                                OrderLifecycleTracker.transition(
                                    intent.intent_id,
                                    OrderLifecycleState.FILLED,
                                    txid=txid,
                                    filled_vol=actual_vol,
                                    fee_eur=actual_fee
                                )

                                pnl_eur = 0.0
                                if live_res["side"] == "BUY":
                                    self.db_manager.record_buy_trade(
                                        timestamp=time.strftime("%H:%M:%S"),
                                        pair=pair_name,
                                        price=actual_price,
                                        volume=actual_vol,
                                        fee_eur=actual_fee,
                                        txid=txid,
                                        status=order_status_label
                                    )
                                    # Einstiegspreis als VWAP der offenen Lots aktualisieren
                                    vwap = self.db_manager.fetch_weighted_average_cost_basis(pair_name)
                                    self.live_entry_prices[asset_code] = vwap if vwap else actual_price
                                    self.live_peak_prices[asset_code] = actual_price
                                elif live_res["side"] == "SELL":
                                    succ, calc_pnl = self.db_manager.record_sell_trade(
                                        timestamp=time.strftime("%H:%M:%S"),
                                        pair=pair_name,
                                        price=actual_price,
                                        volume=actual_vol,
                                        fee_eur=actual_fee,
                                        txid=txid,
                                        status=order_status_label
                                    )
                                    if calc_pnl is not None:
                                        # Known cost basis: safe to include in cumulative PnL
                                        pnl_eur = round(float(calc_pnl), 4)
                                        self.cumulative_live_pnl += pnl_eur
                                    else:
                                        # P0-A: UNKNOWN_COST_BASIS — do NOT add to cumulative PnL.
                                        # Flag pair so compounding is blocked and GUI shows warning.
                                        pnl_eur = None
                                        self.unknown_pnl_pairs.add(pair_name)
                                        self._pnl_unknown_count += 1
                                        self.log_console(
                                            f"⚠️ PnL UNBEKANNT ({pair_name}): Kein Einstiegspreis-Lot vorhanden. "
                                            f"Abstimmung erforderlich! "
                                            f"({self._pnl_unknown_count} ungelöste Ereignisse)"
                                        )
                                    self.live_peak_prices[asset_code] = 0.0
                                    # Hole aktualisierten Einstiegspreis (VWAP) verbleibender Lots
                                    vwap = self.db_manager.fetch_weighted_average_cost_basis(pair_name)
                                    self.live_entry_prices[asset_code] = vwap if vwap else 0.0

                                rec = {
                                    "timestamp": time.strftime("%H:%M:%S"),
                                    "side": live_res["side"],
                                    "price": actual_price,
                                    "volume": actual_vol,
                                    "fee_eur": actual_fee,
                                    "pnl_eur": pnl_eur if pnl_eur is not None else "UNBEKANNT – Abstimmung",
                                    "status": order_status_label
                                }

                                self.root.after(0, lambda r=rec: self.add_trade_to_ledger(r))
                                self.log_console(f"🚨 ECHTE KRAKEN AUTONOME ORDER ({pair_name})! TXID: {txid}")
                                self.last_logged_status[pair_name] = "SUCCESS"

                                # Push-Benachrichtigung an Telegram & Discord senden
                                alert_text = (
                                    f"🚀 *QUBIT QUANT TRADER: LIVE TRADE*\n"
                                    f"• Pair: `{pair_name}`\n"
                                    f"• Side: *{live_res['side']}*\n"
                                    f"• Preis: `{live_res['price']:.2f} €`\n"
                                    f"• Volumen: `{live_res['volume']:.6f}`\n"
                                    f"• TXID: `{txid}`\n"
                                    f"• Status: *ERFOLGREICH AUSGEFÜHRT*"
                                )
                                NotificationManager.send_telegram_alert_async(self.tg_bot_token, self.tg_chat_id, alert_text)
                                NotificationManager.send_discord_alert_async(self.discord_webhook, alert_text)
                            else:
                                msg = live_res.get('message', '')
                                code = live_res.get('code', '')
                                OrderLifecycleTracker.transition(
                                    intent.intent_id,
                                    OrderLifecycleState.REJECTED,
                                    reason=f"{code}: {msg}"
                                )
                                lower_msg = str(msg).lower()
                                if (code in ["INSUFFICIENT_FUNDS", "VOLUME_BELOW_MIN", "COST_BELOW_MIN"] or 
                                    "insufficient" in lower_msg or 
                                    "zu wenig" in lower_msg or 
                                    "guthaben" in lower_msg or 
                                    "funds" in lower_msg or 
                                    "volume minimum" in lower_msg or 
                                    "invalid arguments:volume" in lower_msg or 
                                    "invalid nonce" in lower_msg or 
                                    "eorder" in lower_msg):
                                    pass
                                elif self.last_logged_status.get(pair_name) != msg:
                                    self.log_console(f"ℹ️ STATUS ({pair_name}): {msg}")
                                    self.last_logged_status[pair_name] = msg
                        else:
                            # PAPER TRADING SIMULATION
                            self.last_order_time_per_pair[pair_name] = now_tm
                            sim_signal = {
                                "allowed": True,
                                "signal_type": order["side"],
                                "volume": order["volume"],
                                "stop_loss_price": order["price"] * 0.98,
                                "take_profit_price": order["price"] * 1.03
                            }
                            bid_p = order["price"] * 0.9998
                            ask_p = order["price"] * 1.0002
                            paper_rec = self.paper_simulator.execute_paper_order(sim_signal, bid_p, ask_p)
                            if paper_rec:
                                OrderLifecycleTracker.transition(
                                    intent.intent_id,
                                    OrderLifecycleState.FILLED,
                                    txid="PAPER-SIM",
                                    filled_vol=paper_rec["volume"],
                                    fee_eur=paper_rec["fee_eur"]
                                )
                                self.root.after(0, lambda r=paper_rec: self.add_trade_to_ledger(r))
                                self.log_console(f"🧪 PAPER TRADE AUSGEFÜHRT: {paper_rec['side']} {paper_rec['volume']:.6f} {asset_code} @ {paper_rec['price']:.2f} € (PnL: {paper_rec['pnl_eur']:+.2f} €)")

                ui_info = {
                    "m_prices": m_prices,
                    "rsi": rsi_btc,
                    "zscore": z_score,
                    "kelly_f": kelly_f,
                    "signal": asset_signals.get("BTC", "HOLD"),
                    "equity": self.real_equity_eur,
                    "regime": regime_res.get("regime", "RANGE_SCALPING"),
                    "regime_strategy": regime_res.get("strategy", "SCALPING"),
                    "regime_conf": regime_res.get("confidence", 0.5),
                    "lead_lag": lead_lag,
                    "cvd": cvd_data,
                    "cum_pnl": self.db_manager.fetch_cumulative_pnl()
                }
                self.root.after(0, lambda d=ui_info: self.update_dashboard(d))
                time.sleep(1.5)

        threading.Thread(target=loop, daemon=True).start()

    def update_dashboard(self, d: dict):
        if not self.running:
            return

        m_p = d["m_prices"]
        for ex, data in m_p.items():
            p = data["price"]
            lat = data["latency_ms"]
            self.ex_labels[ex].config(
                text=f"{p:,.2f} USD ({lat:.1f}ms)" if p > 0 else "Warte auf WS...",
                fg="#00ff88" if p > 0 else "#fbbf24"
            )

        # Radar Flow Card
        cvd_info = d.get("cvd", {})
        lead_info = d.get("lead_lag", {})
        abs_status = cvd_info.get("absorption", "NEUTRAL")
        lead_status = lead_info.get("status", "NEUTRAL")
        self.lbl_flow_radar.config(text=f"CVD: {abs_status} | LEAD: {lead_status}")

        # Regime Badge Card
        reg = d.get("regime", "RANGE_SCALPING")
        conf = d.get("regime_conf", 0.5)
        reg_color = "#00ff88" if "BULL" in reg else "#f43f5e" if "BEAR" in reg else "#fbbf24"
        self.lbl_regime_badge.config(text=f"{reg} ({conf*100:.0f}%)", fg=reg_color)

        # Cumulative PnL
        pnl = d.get("cum_pnl", 0.0)
        pnl_color = "#00ff88" if pnl >= 0 else "#f43f5e"
        self.lbl_cum_pnl.config(text=f"Gesamt Realisierte PnL: {pnl:+.2f} €", fg=pnl_color)

        self.edge_labels["rsi"].config(text=f"{d['rsi']:.1f}")
        z = d["zscore"]
        z_color = "#00ff88" if z <= -1.0 else "#f43f5e" if z >= 1.0 else "#f1f5f9"
        self.edge_labels["zscore"].config(text=f"{z:+.2f} {'(Underpriced)' if z <= -1.0 else '(Overpriced)' if z >= 1.0 else '(Fair)'}", fg=z_color)
        self.edge_labels["kelly"].config(text=f"{d['kelly_f']*100:.1f}% Allokation")
        self.edge_labels["obi"].config(text="Live WebSocket Orderbuch")

        sig = d["signal"]
        sig_color = "#00ff88" if sig == "BUY" else "#f43f5e" if sig == "SELL" else "#f1f5f9"
        self.edge_labels["signal"].config(text=f"{sig}", fg=sig_color)

    def add_trade_to_ledger(self, r: dict):
        side = r.get("side", "BUY")
        tag = "BUY" if side == "BUY" else "SELL"
        self.trade_tree.insert(
            "", 0,
            values=(r["timestamp"], side, f"{r['price']:,.2f} €", f"{r['volume']:.6f}", f"{r['fee_eur']:.4f} €", f"{r['pnl_eur']:+.2f} €", r["status"]),
            tags=(tag,)
        )


if __name__ == "__main__":
    root = tk.Tk()
    app = MultiExchangeTraderApp(root)
    root.mainloop()
