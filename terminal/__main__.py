"""
Kommandozeile des Qubit Terminal v2.

  python -m terminal scan      --exchange binance --top 40
  python -m terminal validate  --symbol BTCUSDT --strategy trend --interval 1h --days 1095
  python -m terminal backtest  --symbol ETHUSDT --strategy breakout --interval 4h --days 1095
  python -m terminal paper     --symbols BTCUSDT,ETHUSDT --strategy trend --interval 1h
  python -m terminal analyze   --file trading_ledger.db
"""

import argparse
import sys
import time

from terminal import ledger_analysis
from terminal.backtest import buy_and_hold, run_backtest
from terminal.costs import PRESETS, get_cost_model
from terminal.market_data import EXCHANGES, INTERVAL_SECONDS, drop_unclosed, get_candles, load_csv
from terminal.paper import PaperTrader, RiskLimits
from terminal.scanner import analyze, prefilter, rank
from terminal.strategies import STRATEGIES, build
from terminal.validation import permutation_test, verdict, walk_forward

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def _fmt_metrics(m):
    return (f"Rendite {m['net_return_pct']:+.2f} %  |  Max-DD {m['max_drawdown_pct']:.2f} %  |  "
            f"Trades {m['trades']}  |  Treffer {m['win_rate_pct']:.1f} %  |  PF {m['profit_factor']:.2f}  |  "
            f"Sharpe {m['sharpe']:.2f}  |  Gebühren {m['fees_paid']:.2f}  |  Im Markt {m['exposure_pct']:.0f} %")


def _candles(args):
    if args.csv:
        return load_csv(args.csv, args.symbol, args.interval)
    return drop_unclosed(get_candles(args.exchange, args.symbol, args.interval, args.days))


def cmd_scan(args):
    costs = get_cost_model(args.costs)
    client = EXCHANGES[args.exchange]()
    snap = client.market_snapshot(args.quote)
    print(f"{len(snap)} Märkte geladen, filtere nach Liquidität und Spread...")
    pre = prefilter(snap, args.min_volume)[: args.top]
    start = int(time.time()) - 400 * INTERVAL_SECONDS[args.interval]
    results = []
    for m in pre:
        try:
            c = drop_unclosed(client.klines(m["symbol"], args.interval, start))
            if len(c) > 210:
                results.append({**analyze(c, costs, m["spread_pct"]), "quote_volume": m["quote_volume"]})
        except Exception as e:
            print(f"  {m['symbol']}: {e}")
    print(f"\n{'Symbol':12s}{'Vol 24h (M)':>12s}{'ATR %':>8s}{'Kosten %':>10s}{'Kosten/ATR':>12s}"
          f"{'Trend-Q':>9s}{'Auftrend':>10s}  Signale")
    for a in rank(results):
        active = ",".join(k for k, v in a["signals"].items() if v) or "-"
        flag = "" if a["tradeable"] else "  (Kosten zu hoch)"
        print(f"{a['symbol']:12s}{a['quote_volume'] / 1e6:12.1f}{a['atr_pct']:8.2f}{a['roundtrip_cost_pct']:10.3f}"
              f"{a['cost_ratio']:12.2f}{a['efficiency']:9.2f}{'ja' if a['uptrend'] else 'nein':>10s}  {active}{flag}")


def cmd_backtest(args):
    c = _candles(args)
    costs = get_cost_model(args.costs)
    strat = build(args.strategy)
    res = run_backtest(c, strat, costs, initial_equity=args.equity, risk_per_trade=args.risk)
    bh = buy_and_hold(c, costs, args.equity)
    print(f"{c.symbol} {c.interval}: {len(c)} Kerzen, {c.gaps()} Lücken, Kosten: {costs.name} "
          f"({costs.roundtrip * 100:.2f} % Roundtrip)")
    print(f"{strat}\n  {_fmt_metrics(res.metrics())}")
    print(f"Buy & Hold: Rendite {bh['net_return_pct']:+.2f} %  |  Max-DD {bh['max_drawdown_pct']:.2f} %")
    print("Hinweis: Ein einzelner Backtest mit Standard-Parametern ist KEIN Beweis. Nutze 'validate'.")


def cmd_validate(args):
    c = _candles(args)
    costs = get_cost_model(args.costs)
    cls = STRATEGIES[args.strategy]
    train, test = args.train_bars, args.test_bars
    print(f"{c.symbol} {c.interval}: {len(c)} Kerzen | Walk-Forward Train {train} / Test {test} | {costs.name}")
    wf = walk_forward(c, cls, costs, train, test, initial_equity=args.equity, risk_per_trade=args.risk)
    if not wf.folds:
        print("Zu wenig Daten für Walk-Forward. Mehr --days laden oder Fenster verkleinern.")
        return
    for f in wf.folds:
        print(f"  Fold ab {time.strftime('%Y-%m-%d', time.gmtime(f['start_ts']))}: {f['net_return_pct']:+7.2f} %  "
              f"(B&H {f['buy_hold_pct']:+7.2f} %)  Trades {f['trades']:3d}  Parameter {f['params']}")
    oos = wf.metrics()
    print(f"\nOUT-OF-SAMPLE gesamt: {_fmt_metrics(oos)}")
    oos_candles = c.slice(train, train + len(wf.folds) * test)
    bh = buy_and_hold(oos_candles, costs, args.equity)
    print(f"Buy & Hold (gleicher Zeitraum): {bh['net_return_pct']:+.2f} %, Max-DD {bh['max_drawdown_pct']:.2f} %")
    last_params = wf.folds[-1]["params"]
    print(f"\nPermutationstest ({args.perms} Durchläufe) mit {last_params} auf dem OOS-Zeitraum...")
    perm = permutation_test(oos_candles, cls(**last_params), costs, n_perm=args.perms,
                            initial_equity=args.equity, risk_per_trade=args.risk)
    print(f"  p-Wert: {perm['p_value']:.3f}")
    v = verdict(oos, perm["p_value"], bh)
    print("\nZULASSUNGS-HÜRDEN:")
    for name, ok in v["checks"].items():
        print(f"  [{'OK' if ok else 'X '}] {name}")
    print(f"\nERGEBNIS: {v['status']}")


def cmd_paper(args):
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    trader = PaperTrader(build(args.strategy), symbols, get_cost_model(args.costs), args.exchange,
                         args.interval, args.equity, RiskLimits(risk_per_trade=args.risk), mode=args.mode)
    if args.once:
        print(trader.step())
    else:
        trader.run_forever()


def cmd_analyze(args):
    print(ledger_analysis.report(args.file))


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m terminal", description="Qubit Terminal v2")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp, symbol=True):
        sp.add_argument("--exchange", default="binance", choices=list(EXCHANGES))
        sp.add_argument("--interval", default="1h", choices=list(INTERVAL_SECONDS))
        sp.add_argument("--costs", default="binance_spot", choices=list(PRESETS))
        sp.add_argument("--equity", type=float, default=1000.0)
        sp.add_argument("--risk", type=float, default=0.01, help="Risiko pro Trade (0.01 = 1 %%)")
        if symbol:
            sp.add_argument("--symbol", default="BTCUSDT")
            sp.add_argument("--strategy", default="trend", choices=list(STRATEGIES))
            sp.add_argument("--days", type=int, default=1095)
            sp.add_argument("--csv", help="Eigene Kerzen-CSV statt Börsen-Download (ts,open,high,low,close,volume)")

    s = sub.add_parser("scan", help="Hunderte Märkte nach Handelbarkeit ranken")
    common(s, symbol=False)
    s.add_argument("--quote", default="USDT")
    s.add_argument("--top", type=int, default=40)
    s.add_argument("--min-volume", type=float, default=5e6)
    s.set_defaults(func=cmd_scan)

    b = sub.add_parser("backtest", help="Einzelner Backtest mit Standard-Parametern")
    common(b)
    b.set_defaults(func=cmd_backtest)

    v = sub.add_parser("validate", help="Walk-Forward + Permutationstest + Zulassungs-Hürden")
    common(v)
    v.add_argument("--train-bars", type=int, default=4000)
    v.add_argument("--test-bars", type=int, default=1000)
    v.add_argument("--perms", type=int, default=100)
    v.set_defaults(func=cmd_validate)

    pp = sub.add_parser("paper", help="Paper-Trading (Standard) oder Testnet")
    common(pp, symbol=False)
    pp.add_argument("--symbols", default="BTCUSDT,ETHUSDT")
    pp.add_argument("--strategy", default="trend", choices=list(STRATEGIES))
    pp.add_argument("--mode", default="paper", choices=["paper", "testnet"])
    pp.add_argument("--once", action="store_true", help="Nur einen Durchlauf ausführen")
    pp.set_defaults(func=cmd_paper)

    a = sub.add_parser("analyze", help="Echte v1-Trades auswerten (trading_ledger.db oder Kraken-CSV)")
    a.add_argument("--file", required=True)
    a.set_defaults(func=cmd_analyze)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
