# Stock-market-

# DecodeLabs IPODecisionEngine

A compact, self-contained Python implementation of the DecodeLabs systematic trading engine framework. The IPODecisionEngine processes streaming OHLCV candle data to compute microstructure metrics, smooth trend indicators, and enforce mechanical risk circuit breakers — enabling fully-mechanical decisioning for systematic strategies.

## Project overview

This repository contains a minimal implementation intended as a testbed and starting point for research-grade mechanical trading engines. The engine demonstrates core building blocks used in production strategies:

- Candle microstructure mechanics
  - Wick-to-body ratio calculation for price rejection detection (Rwb)
- Trend smoothing and structural filters
  - Exponential Moving Averages (EMA 50 and EMA 200)
  - EMA structural regime alignment (golden cross / death cross detection)
- Momentum filtering
  - Wilder's RSI implementation with smoothing
- Interaction gate model (IPO Model)
  - Gate A: Support/Resistance proximity checks
  - Gate B: EMA structural alignment
  - Gate C: RSI momentum confirmation
- Risk management circuit-breakers
  - Pre-set session hard lock and intraday drawdown hard stops
  - Half-size position sizing after consecutive losses
- Simple runtime testbed demonstrating warm-up and example decisions

## Files

- ipodecision_engine.py — Core engine implementation and a lightweight runtime demonstration.

## Quickstart

1. Clone the repository:

   git clone https://github.com/musmanshafique45/Stock-market-.git
   cd Stock-market-

2. Run the demo script (Python 3.8+ recommended):

   python ipodecision_engine.py

The script warms up indicator arrays with sample candles, prints per-candle decisions, and demonstrates the half-size rule after simulated losses.

## Next steps and suggestions

- Add a proper examples/ folder with larger simulated streams and parameter sweeps.
- Add unit tests for the indicator functions (RSI, EMA warm-up, wick-to-body).
- Integrate with a backtesting framework or paper trading connector once behaviour is validated.
- Add logging and configuration via YAML/JSON to avoid hard-coded parameters.

## License

This repository is provided as-is for research and learning. Add your preferred open-source license if you intend to share or publish the project.
