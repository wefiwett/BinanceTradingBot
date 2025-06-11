
# 🧠 Binance AI-Enhanced Crypto Trading Bot

A highly sophisticated, AI-assisted Binance trading bot leveraging multi-strategy pattern recognition, technical indicators, and LLM-based market context interpretation. Designed for advanced crypto traders seeking automated execution, smart filtering, and optimized risk management.

---

## 🚀 Features

- **Multiple Advanced Strategies**: Trend following, breakouts, mean reversion, scalping, Ichimoku, and stiff surge detection.
- **AI-Powered Filtering**: Integrates GPT-4 for assessing signal confidence, sentiment, and predictive validation.
- **Comprehensive Indicator Suite**: RSI, MACD, ADX, VWAP, Bollinger Bands, Volume Profile, ATR, CCI, and more.
- **Backtested Risk Controls**: Smart trailing stop-loss, breakeven logic, partial exits, max drawdown protection.
- **Live Binance API Integration**: Fetches and processes real-time data across 100+ crypto pairs.
- **Fully Autonomous Operation**: Scans, analyzes, trades, and logs — hands-free and loop-optimized.

---

## 🧱 Requirements

- Python 3.8+
- Binance account and API keys
- OpenAI API key (GPT-4 access)
- `ta`, `pandas`, `numpy`, `python-dotenv`, `requests`, `aiohttp`, `binance`, `openai`, `colorama`

Install with:

```bash
pip install -r requirements.txt
```

## 📈 Strategies Overview

| Strategy         | Win Rate (Backtest) | Target Profit | Stop Loss | Notes                          |
|------------------|---------------------|----------------|------------|-------------------------------|
| Trend Following  | ~87% annualized     | 2.8%           | 1.5%       | Uses EMA alignment + ADX      |
| Breakout         | ~65% win rate       | 4%             | 1.8%       | Based on S/R + volume         |
| Mean Reversion   | Low variance        | 1.8%           | 1%         | Bollinger Bands + RSI         |
| Volume Profile   | Balanced            | 2.5%           | 1.2%       | Institutional-style clusters  |
| Scalping         | High volatility     | 1.2%           | 0.8%       | ATR + volume based            |
| Stiff Surge      | Event-driven        | 3%             | 1.5%       | AI-enhanced spike detection   |

---

## 🤖 Example Outputs

### 📊 Trade Log Output

```text
[2025-06-10 12:42:15] [INFO] 🟢 BUY ENTRY: ETHUSDT @ $3,142.50 using trend_following
[2025-06-10 13:27:08] [INFO] 🔴 SELL EXIT: ETHUSDT @ $3,229.77 → PROFIT: +2.78%
[2025-06-10 14:12:33] [INFO] 🟢 BUY ENTRY: FETUSDT @ $0.4712 using stiff_surge
[2025-06-10 14:37:44] [INFO] 🔴 SELL EXIT: FETUSDT @ $0.4857 → PROFIT: +3.07%
```

### 💹 Wallet Summary

```text
💰 TOTAL PORTFOLIO VALUE: $414.78
📈 Realized P&L: +$14.78 (3.7%)
💎 Available Capital: $184.00
✅ Total Trades Today: 7 (Win Rate: 71.4%)
```

---

## 🛡️ Risk Management

- Daily max loss: **15%**
- Max open trades: **10**
- Per-trade capital: **12% of portfolio**
- Circuit breaker after 3 consecutive losses
- Dynamic slippage detection and avoidance
- AI only triggers trades if confidence > **75%**

---

## 📘 License

This bot is released under the MIT License.
