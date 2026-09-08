import numpy as np
from data.collector import MarketDataCollector
from edge_research.experiment_runner import HypothesisExperimentRunner
from validation.walk_forward_runner import WalkForwardRunner

# 1. Deterministischen Datensatz generieren (1500 Kerzen)
collector = MarketDataCollector()
btc_candles = collector.generate_deterministic_dataset("XBTEUR", n_candles=1500, start_price=65000.0, seed=101)
eth_candles = collector.generate_deterministic_dataset("ETHEUR", n_candles=1500, start_price=2600.0, seed=102)

hash_btc = collector.save_dataset_csv(btc_candles, "btc_eur_5m_audit.csv")
hash_eth = collector.save_dataset_csv(eth_candles, "eth_eur_5m_audit.csv")

btc_prices = [c["close"] for c in btc_candles]
btc_volumes = [c["volume"] for c in btc_candles]
eth_prices = [c["close"] for c in eth_candles]
eth_volumes = [c["volume"] for c in eth_candles]
synthetic_obis = [float(np.clip(np.random.normal(0, 0.25), -0.8, 0.8)) for _ in range(1500)]

runner = HypothesisExperimentRunner(initial_capital_eur=1000.0)

# 2. Out-of-Sample Test H1 bis H4
h1_res = runner.run_h1_trend_quality(btc_prices, btc_volumes)
h2_res = runner.run_h2_mean_reversion(btc_prices, btc_volumes)
h3_res = runner.run_h3_lead_lag(btc_prices, eth_prices, eth_volumes)
h4_res = runner.run_h4_microstructure(btc_prices, btc_volumes, synthetic_obis)

print("=== OUT-OF-SAMPLE TESTERGEBNISSE NACH KOSTEN ===")
print("H1 Trend-Quality:      PnL: {:+.2f} EUR ({:+.2f}%), Trades: {}, MaxDD: {:.2f}%".format(
    h1_res["net_pnl_eur"], h1_res["net_ret_pct"], h1_res["trade_count"], h1_res["max_drawdown_pct"]
))
print("H2 Mean-Reversion:     PnL: {:+.2f} EUR ({:+.2f}%), Trades: {}, MaxDD: {:.2f}%".format(
    h2_res["net_pnl_eur"], h2_res["net_ret_pct"], h2_res["trade_count"], h2_res["max_drawdown_pct"]
))
print("H3 Lead-Lag (Altcoin): PnL: {:+.2f} EUR ({:+.2f}%), Trades: {}, MaxDD: {:.2f}%".format(
    h3_res["net_pnl_eur"], h3_res["net_ret_pct"], h3_res["trade_count"], h3_res["max_drawdown_pct"]
))
print("H4 Mikrostruktur(OBI): PnL: {:+.2f} EUR ({:+.2f}%), Trades: {}, MaxDD: {:.2f}%".format(
    h4_res["net_pnl_eur"], h4_res["net_ret_pct"], h4_res["trade_count"], h4_res["max_drawdown_pct"]
))
print("SHA256 BTC Data: {}".format(hash_btc))
print("SHA256 ETH Data: {}".format(hash_eth))
