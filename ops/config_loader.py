"""
ZENTRALER KONFIGURATIONS-LOADER FÜR QUBIT SYSTEMATIC TRADER
------------------------------------------------------------
Lädt und validiert alle strategischen Parameter aus config.yaml.
Unterstützt Umgebungsvariablen als Overrides.
"""

import os
import yaml
from typing import Dict, Any, List

DEFAULT_CONFIG: Dict[str, Any] = {
    "trading": {
        "default_mode": "PAPER",
        "timeframe_seconds": 300,
        "resample_timeframe_seconds": 900,
        "universe": ["XBTEUR", "ETHEUR", "SOLEUR", "XRPEUR"]
    },
    "risk_management": {
        "max_risk_per_trade_pct": 0.010,
        "max_total_exposure_pct": 0.50,
        "max_asset_allocation_pct": 0.35,
        "daily_loss_limit_pct": 0.030,
        "weekly_loss_limit_pct": 0.060,
        "min_stop_distance_pct": 0.010
    },
    "execution": {
        "execution_style": "MAKER_POST_ONLY",
        "post_only": True,
        "stale_order_timeout_sec": 30.0,
        "min_order_cost_eur": 0.45,
        "verify_expectancy_before_entry": True
    },
    "reconciliation": {
        "enabled": True,
        "interval_seconds": 60.0,
        "auto_sync_external_trades": True
    },
    "regimes": {
        "blocked_entry_regimes": ["LIQUIDITY_STRESS", "VOLATILITY_SHOCK", "CALM_DOWNTREND"]
    }
}


class SystemConfig:
    """Singleton/Klassen-Wrapper für typsichere Konfigurationsabfragen."""

    _cached_config = None

    @classmethod
    def load(cls, config_path: str = "config.yaml") -> Dict[str, Any]:
        if cls._cached_config is not None:
            return cls._cached_config

        config = dict(DEFAULT_CONFIG)
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    user_conf = yaml.safe_load(f)
                    if isinstance(user_conf, dict):
                        for section, values in user_conf.items():
                            if section in config and isinstance(values, dict):
                                config[section].update(values)
                            else:
                                config[section] = values
            except Exception as e:
                print(f"[CONFIG WARNING] Konnte {config_path} nicht parsen ({e}), nutze Defaults.")

        # Environment Variable Overrides
        if "QUBIT_TRADING_MODE" in os.environ:
            config["trading"]["default_mode"] = os.environ["QUBIT_TRADING_MODE"]

        cls._cached_config = config
        return config

    @classmethod
    def get_trading_universe(cls) -> List[str]:
        return cls.load()["trading"]["universe"]

    @classmethod
    def get_risk_limits(cls) -> Dict[str, float]:
        return cls.load()["risk_management"]

    @classmethod
    def get_execution_settings(cls) -> Dict[str, Any]:
        return cls.load()["execution"]

    @classmethod
    def is_maker_post_only(cls) -> bool:
        return cls.get_execution_settings().get("post_only", True)
