"""
PORTFOLIO- UND RISIKOMANAGEMENT-ENGINE
--------------------------------------
1. Positionsgröße strikt aus Verlustbudget / Stop-Distanz.
2. Max Exposure-Limits pro Asset und Gesamtkonto.
3. Mehrstufige Stops:
   - Technischer Stop
   - Volatilitäts-Stop (ATR-basiert)
   - Time-Stop
4. RISK_EXIT hat unbedingten Vorrang vor PROFIT_EXIT.
5. Tages- & Wochenverlustlimits mit automatischer Sperre.
"""

from typing import Dict, Any, Tuple, Optional
from risk.regime_models import MarketRegime

class PortfolioRiskEngine:
    """
    Zentrale Risikosteuerung. Gewährleistet mathematischen Kapitalschutz
    unabhängig von Marktphasen oder Signalgebern.
    """

    def __init__(
        self,
        max_risk_per_trade_pct: float = 0.010,  # Max 1.0% Kapitalrisiko pro Trade
        max_total_exposure_pct: float = 0.50,   # Max 50% Gesamtportfolio in Krypto investiert
        daily_loss_limit_pct: float = 0.030,    # Max 3.0% Tagesverlust -> Handelspause
        weekly_loss_limit_pct: float = 0.060    # Max 6.0% Wochenverlust -> Notstopp
    ):
        self.max_risk_per_trade_pct = max_risk_per_trade_pct
        self.max_total_exposure_pct = max_total_exposure_pct
        self.daily_loss_limit_pct = daily_loss_limit_pct
        self.weekly_loss_limit_pct = weekly_loss_limit_pct
        
        self.daily_start_equity = None
        self.weekly_start_equity = None
        self.trading_halted = False
        self.halt_reason = ""

    def check_circuit_breakers(self, current_equity_eur: float) -> Tuple[bool, str]:
        """Prüft Tages- und Wochen-Drawdown-Limits."""
        if current_equity_eur <= 0:
            return True, "ZERO_OR_NEGATIVE_EQUITY"

        if self.daily_start_equity is None:
            self.daily_start_equity = current_equity_eur
        if self.weekly_start_equity is None:
            self.weekly_start_equity = current_equity_eur

        # Tages-Verlust prüfen
        daily_dd = (self.daily_start_equity - current_equity_eur) / self.daily_start_equity
        if daily_dd >= self.daily_loss_limit_pct:
            self.trading_halted = True
            self.halt_reason = f"DAILY_LOSS_LIMIT_REACHED (-{daily_dd*100:.2f}%)"
            return True, self.halt_reason

        # Wochen-Verlust prüfen
        weekly_dd = (self.weekly_start_equity - current_equity_eur) / self.weekly_start_equity
        if weekly_dd >= self.weekly_loss_limit_pct:
            self.trading_halted = True
            self.halt_reason = f"WEEKLY_LOSS_LIMIT_REACHED (-{weekly_dd*100:.2f}%)"
            return True, self.halt_reason

        return False, "OK"

    def calculate_position_size(
        self,
        current_equity_eur: float,
        current_cash_eur: float,
        asset_price: float,
        stop_loss_price: float,
        current_asset_exposure_eur: float,
        current_total_exposure_eur: float,
        current_regime: str = MarketRegime.RANGE_BOUND,
        pending_buy_exposure_eur: float = 0.0,
        min_order_cost_eur: float = 0.45,
        min_order_volume: float = 0.00005
    ) -> Dict[str, Any]:
        """
        Berechnet die exakte Positionsgröße basierend auf Stop-Distanz und Verlustbudget.
        Berücksichtigt offene BUY-Verpflichtungen und verwirft Orders unter Mindestgröße
        strikt mit SKIP_MINIMUM_ORDER (kein gefährliches Aufrunden!).
        """
        if self.trading_halted:
            return {"allowed": False, "volume": 0.0, "reason": f"HALTED: {self.halt_reason}"}

        # 1. Regime-Gating: Keine Neukäufe bei Schock oder Stress
        if current_regime in [MarketRegime.LIQUIDITY_STRESS, MarketRegime.VOLATILITY_SHOCK, MarketRegime.CALM_DOWNTREND]:
            return {"allowed": False, "volume": 0.0, "reason": f"REGIME_PROHIBITED ({current_regime})"}

        # 2. Stop-Distanz validieren
        if stop_loss_price >= asset_price or stop_loss_price <= 0:
            return {"allowed": False, "volume": 0.0, "reason": "INVALID_STOP_PRICE"}

        risk_per_unit = asset_price - stop_loss_price
        risk_pct = risk_per_unit / asset_price

        # Mindestabstand zum Stop gegen Rauschen (mindestens 1.0%)
        if risk_pct < 0.010:
            risk_per_unit = asset_price * 0.010
            risk_pct = 0.010

        # 3. Maximales Verlustbudget in EUR (strikt 1.0% der Gesamt-Equity)
        max_loss_budget_eur = current_equity_eur * self.max_risk_per_trade_pct

        # Zielvolumen aus Verlustbudget
        target_volume = max_loss_budget_eur / risk_per_unit
        target_cost_eur = target_volume * asset_price

        # 4. Exposure-Limits prüfen (Pre-Trade Commitment: Offene BUYs zählen bereits voll!)
        projected_exposure = current_total_exposure_eur + pending_buy_exposure_eur
        max_allowed_total = current_equity_eur * self.max_total_exposure_pct
        remaining_exposure = max(0.0, max_allowed_total - projected_exposure)
        
        # Begrenzung auf verfügbares Cash (nach Abzug offener Kaufverpflichtungen)
        usable_cash = max(0.0, current_cash_eur - pending_buy_exposure_eur)
        allocatable_eur = min(target_cost_eur, usable_cash * 0.90, remaining_exposure)
        
        # Kleinkapital-Schutz & Mindestgrößen (SKIP_MINIMUM_ORDER: Niemals aufrunden!)
        final_volume = allocatable_eur / asset_price if asset_price > 0 else 0.0

        if allocatable_eur < min_order_cost_eur or final_volume < min_order_volume:
            return {
                "allowed": False,
                "volume": 0.0,
                "reason": f"SKIP_MINIMUM_ORDER (Allokation {allocatable_eur:.2f} € < Min {min_order_cost_eur:.2f} € oder Vol {final_volume:.6f} < Min {min_order_volume:.6f})"
            }

        return {
            "allowed": True,
            "volume": final_volume,
            "invest_eur": allocatable_eur,
            "max_risk_eur": allocatable_eur * risk_pct,
            "risk_pct_of_trade": risk_pct,
            "reason": "APPROVED_BY_RISK_ENGINE"
        }

    def evaluate_exit(
        self,
        current_price: float,
        entry_price: float,
        holding_time_seconds: float,
        atr_value: float,
        max_holding_seconds: float = 7200.0 # 2 Stunden Time-Stop
    ) -> Dict[str, Any]:
        """
        Prüft mehrstufige Ausstiege. RISK_EXIT hat bedingungslose Priorität!
        """
        if entry_price <= 0 or current_price <= 0:
            return {"exit": False}

        gross_ret = (current_price - entry_price) / entry_price

        # 1. Volatilitäts-Stop (z. B. 2.0 * ATR unter Entry)
        vol_stop_dist = max(0.015, (2.0 * atr_value) / entry_price if atr_value > 0 else 0.020)
        if gross_ret <= -vol_stop_dist:
            return {
                "exit": True,
                "exit_type": "RISK_EXIT",
                "reason": f"VOLATILITY_STOP (-{vol_stop_dist*100:.2f}%)"
            }

        # 2. Fester Notfall-Stop (-3.5%)
        if gross_ret <= -0.035:
            return {
                "exit": True,
                "exit_type": "RISK_EXIT",
                "reason": "HARD_RISK_STOP (-3.50%)"
            }

        # 3. Time-Stop (Verhindert gebundenes Kapital bei Seitwärtsmarkt ohne Edge)
        if holding_time_seconds >= max_holding_seconds:
            return {
                "exit": True,
                "exit_type": "RISK_EXIT" if gross_ret < 0 else "PROFIT_EXIT",
                "reason": f"TIME_STOP ({holding_time_seconds/60:.0f} min)"
            }

        return {"exit": False}
