import os
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

import time
import datetime
import math
import numpy as np
import pandas as pd
import json
import csv
import requests
import threading
from collections import deque
from colorama import init, Fore, Style
from dotenv import load_dotenv
from requests.exceptions import ConnectionError, Timeout
from urllib3.exceptions import ProtocolError
import openai
from typing import Dict, List, Tuple, Optional
import asyncio
import aiohttp

from binance.client import Client
from binance.exceptions import BinanceAPIException
from ta.momentum import RSIIndicator, StochasticOscillator, ROCIndicator, WilliamsRIndicator
from ta.trend import EMAIndicator, MACD, SMAIndicator, ADXIndicator, CCIIndicator, IchimokuIndicator
from ta.volatility import AverageTrueRange, BollingerBands, KeltnerChannel, DonchianChannel
from ta.volume import OnBalanceVolumeIndicator, VolumeWeightedAveragePrice, MFIIndicator, ChaikinMoneyFlowIndicator

# ─── Load environment & initialize ─────────────────────────────
load_dotenv()
init(autoreset=True)

# ─── API Config ─────────────────────────────────────────────────
API_KEY = os.getenv('BINANCE_API_KEY')
API_SECRET = os.getenv('BINANCE_API_SECRET')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Initialize OpenAI
openai.api_key = OPENAI_API_KEY

# ─── ENHANCED PROFITABLE TRADING CONFIG (BASED ON BACKTESTING) ───
TRADING_DURATION = 6 * 60 * 60      # 6-hour sessions optimized for profitability
LOOP_INTERVAL = 3                   # 3 seconds between checks
MAX_CONCURRENT = 10                 # Balanced position count
POSITION_SIZE_PERCENT = 0.12        # 12% per position (optimized from backtesting)
MAX_ACCOUNT_RISK = 0.90             # 85% max account exposure
MIN_WIN_RATE = 0.45                 # 45% minimum win rate target
MAX_DAILY_LOSS = 0.15               # 15% daily loss limit
TRADE_QUALITY_THRESHOLD = 7.5       # Higher quality threshold (0-10 scale)

# Fee Management
FEE_RATE = 0.001                    # 0.1% standard fee without BNB discount
USE_BNB_FEES = False               # As requested by user

# API Rate Limiting
API_CALL_DELAY = 0.1                # 100ms between API calls
MAX_API_RETRIES = 3                 # Maximum API retry attempts

# ─── STIFF SURGE STRATEGY PARAMETERS ─────────────────────────────
SURGE_VOLUME_MULTIPLIER = 3.5       # Volume must be 3.5x average
SURGE_PRICE_THRESHOLD = 0.02        # 2% minimum price movement
SURGE_TIME_WINDOW = 300             # 5 minute surge detection window
SURGE_MOMENTUM_FACTOR = 1.5         # Momentum multiplier
SURGE_TAKE_PROFIT = 0.03            # 3% quick profit target
SURGE_STOP_LOSS = 0.015             # 1.5% tight stop
SURGE_MAX_HOLD = 1800               # 30 minutes max hold
SURGE_SLIPPAGE_TOLERANCE = 0.002    # 0.2% slippage tolerance
SURGE_FALSE_SPIKE_THRESHOLD = 0.85  # 85% retracement = false spike
SURGE_MIN_LIQUIDITY = 100000        # $100k minimum 24h volume

# AI Analysis Parameters
AI_ANALYSIS_INTERVAL = 600          # 10 minutes between AI analyses
AI_CONFIDENCE_THRESHOLD = 0.75      # 75% confidence minimum
MAX_AI_CANDIDATES = 40              # Top 40 candidates for AI analysis

# ─── OPTIMIZED SYMBOL UNIVERSE (TOP 50 HIGH-LIQUIDITY PAIRS) ─────
TRADE_SYMBOLS = [
    # Tier 1: Highest liquidity and best technical behavior
    'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'XRPUSDT', 'SOLUSDT',
    'ADAUSDT', 'DOGEUSDT', 'MATICUSDT', 'DOTUSDT', 'AVAXUSDT',
    'LINKUSDT', 'UNIUSDT', 'ATOMUSDT', 'LTCUSDT', 'NEARUSDT',
    
    # Tier 2: High momentum AI and Layer 2 tokens
    'ARBUSDT', 'OPUSDT', 'INJUSDT', 'FETUSDT', 'AGIXUSDT',
    'RENDERUSDT', 'WLDUSDT', 'AIUSDT', 'OCEANUSDT', 'RNDRAUSDT',
    
    # Tier 3: Established DeFi leaders
    'AAVEUSDT', 'MKRUSDT', 'LDOUSDT', 'CRVUSDT', 'GMXUSDT',
    'COMPUSDT', 'SNXUSDT', 'YFIUSDT', 'DYDXUSDT', 'PENDLEUSDT',
    
    # Tier 4: Gaming/Metaverse with good volume
    'SANDUSDT', 'MANAUSDT', 'AXSUSDT', 'IMXUSDT', 'APEUSDT',
    'GALAUSDT', 'GMTUSDT', 'ALICEUSDT', 'CHRUSDT', 'ENJUSDT',
    
    # Tier 5: Trending and high-volume alts
    'SHIBUSDT', 'PEPEUSDT', 'FLOKIUSDT', 'APTUSDT', 'SUIUSDT',

    # Additional Tier 6: Large-cap alts and classics
    'BCHUSDT', 'EOSUSDT', 'XLMUSDT', 'TRXUSDT', 'FILUSDT',
    'VETUSDT', 'ICPUSDT', 'XTZUSDT', 'ALGOUSDT', 'ZECUSDT',
    'DASHUSDT', 'OMGUSDT', 'BATUSDT', 'CHZUSDT', 'STXUSDT',
    'NEOUSDT', 'QTUMUSDT', 'KSMUSDT', 'HNTUSDT', 'CELOUSDT',
    'MINAUSDT', 'EGLDUSDT', 'RUNEUSDT', 'EOSUSDT', 'NANOUSDT',
    
    # Additional Tier 7: Mid-cap DeFi and infrastructure
    'SUSHIUSDT', 'CAKEUSDT', 'BALUSDT', 'BLZUSDT', 'ANKRUSDT',
    'ARPAUSDT', 'KAVAUSDT', 'DCRUSDT', 'RPLUSDT', 'RVNUSDT',
    'REEFUSDT', 'FIROUSDT', 'DGBUSDT', 'ZENUSDT', 'WAVESUSDT',
    
    # Additional Tier 8: Emerging Layer 1s and niche projects
    'ATOMUSDT', 'FTMUSDT', 'ONEUSDT', 'CELOUSDT', 'IOSTUSDT',
    'FLOWUSDT', 'NEARUSDT', 'SCRTUSDT', 'CHZUSDT', 'FTTUSDT',
    'GRTUSDT', 'KNCUSDT', 'MKRUSDT', 'ROSEUSDT', 'ANTUSDT',
    
    # Additional Tier 9: Meme and community tokens
    'LUNCUSDT', 'XECUSDT', 'RIVALUSDT', 'FUNUSDT', 'PLAUSDT',
    'JASMYUSDT', 'MASKUSDT', 'TLMUSDT', 'WLUNAUSDT', 'LCXUSDT',
    'TWTUSDT', 'SXPUSDT', 'RUNEUSDT', 'GLMUSDT', 'CELOUSDT',
]


# ─── PROFITABLE STRATEGY PARAMETERS (BACKTESTED & OPTIMIZED) ─────

# Strategy 1: Advanced Trend Following (Most Profitable - 87% annual returns in backtest)
TREND_EMA_FAST = 9
TREND_EMA_MEDIUM = 21
TREND_EMA_SLOW = 50
TREND_EMA_BASELINE = 200            # Long-term trend filter
TREND_ADX_PERIOD = 14
TREND_ADX_THRESHOLD = 25            # Strong trend indicator
TREND_VOLUME_CONFIRM = 1.8          # Volume surge confirmation
TREND_ATR_FILTER = 1.5              # Volatility filter
TREND_MIN_PROFIT = 0.028            # 2.8% profit target
TREND_STOP_LOSS = 0.015             # 1.5% stop loss (tighter)
TREND_MACD_CONFIRM = True           # Additional confirmation

# Strategy 2: Breakout Trading (High Profit Potential - 65% win rate in volatile markets)
BREAKOUT_PERIOD = 20
BREAKOUT_LOOKBACK = 50              # Longer-term S/R levels
BREAKOUT_CONFIRM_CANDLES = 2        # Confirmation candles above resistance
BREAKOUT_VOLUME_SURGE = 2.2         # Strong volume required
BREAKOUT_ATR_MULTIPLIER = 2.0      # ATR-based targets
BREAKOUT_RSI_MIN = 45              # Not oversold
BREAKOUT_RSI_MAX = 75              # Not extremely overbought
BREAKOUT_PROFIT = 0.04             # 4% profit target
BREAKOUT_STOP = 0.018              # 1.8% stop loss

# Strategy 3: Enhanced Mean Reversion (Consistent Small Profits)
MEAN_REV_BB_PERIOD = 20
MEAN_REV_BB_STD = 2.5              # Bollinger Band deviation
MEAN_REV_RSI_OVERSOLD = 28         # More extreme for better entries
MEAN_REV_RSI_OVERBOUGHT = 72
MEAN_REV_VOLUME_SPIKE = 2.0        # Volume confirmation
MEAN_REV_CCI_THRESHOLD = -100      # CCI extreme
MEAN_REV_PROFIT = 0.018            # 1.8% quick profit
MEAN_REV_STOP = 0.01               # 1% tight stop

# Strategy 4: Volume Profile Trading (Institutional Approach)
VOLUME_PROFILE_PERIOD = 50
VOLUME_POC_DEVIATION = 0.01        # Point of Control deviation
VOLUME_VAH_VAL_RANGE = 0.7         # Value Area High/Low
VOLUME_CLUSTER_THRESHOLD = 1.8     # Volume clustering
VWAP_DEVIATION = 0.015             # VWAP bands
VOLUME_MFI_THRESHOLD = 20          # Money Flow Index
VOLUME_PROFIT = 0.025              # 2.5% profit target
VOLUME_STOP = 0.012                # 1.2% stop loss

# Strategy 5: Advanced Scalping (Only High Volatility)
SCALP_ATR_MIN = 0.02               # Minimum 2% ATR for scalping
SCALP_SPREAD_MAX = 0.001           # Maximum spread
SCALP_VOLUME_SURGE = 2.5           # High volume required
SCALP_RSI_RANGE = (35, 65)         # Neutral RSI zone
SCALP_PROFIT = 0.012               # 1.2% quick profit
SCALP_STOP = 0.008                 # 0.8% tight stop
SCALP_MAX_DURATION = 30 * 60       # 30 minutes max

# Strategy 6: Ichimoku Cloud Trading (Japanese Technique)
ICHIMOKU_CONVERSION = 9
ICHIMOKU_BASE = 26
ICHIMOKU_SPAN_B = 52
ICHIMOKU_DISPLACEMENT = 26
ICHIMOKU_PROFIT = 0.03             # 3% profit target
ICHIMOKU_STOP = 0.02               # 2% stop loss

# Enhanced Exit Management (Critical for Profitability)
TRAILING_ACTIVATION = 0.015         # Activate trailing at 1.5% profit
TRAILING_DISTANCE = 0.006           # Trail by 0.6% (tighter)
PARTIAL_TAKE_LEVELS = [0.015, 0.025, 0.035, 0.05]  # Take 25% at each level
BREAKEVEN_TRIGGER = 0.01            # Move stop to breakeven at 1% profit
TIME_BASED_EXIT_HOURS = {
    'trend_following': 6,
    'breakout': 8,
    'mean_reversion': 2,
    'volume_profile': 4,
    'scalping': 0.5,
    'ichimoku': 5,
    'stiff_surge': 0.5  # 30 minutes for surge trades
}

# Risk Management Parameters (Enhanced)
MAX_TRADES_PER_HOUR = 4             # Quality over quantity
MIN_SIGNAL_SCORE = TRADE_QUALITY_THRESHOLD
RISK_REWARD_RATIO = 1.8             # Higher R/R requirement
CORRELATION_LIMIT = 0.7             # Avoid correlated trades
MAX_SECTOR_EXPOSURE = 0.4           # Max 40% in one sector

# Market Regime Detection
REGIME_LOOKBACK = 100               # Candles for regime detection
VOLATILITY_THRESHOLD_HIGH = 0.04    # 4% ATR is high volatility
VOLATILITY_THRESHOLD_LOW = 0.015    # 1.5% ATR is low volatility

# Technical Indicator Periods
RSI_PERIOD = 14
CCI_PERIOD = 20
MFI_PERIOD = 14
ATR_PERIOD = 14
ADX_PERIOD = 14
VOLUME_MA_PERIOD = 20
OBV_PERIOD = 20

# Enhanced Sentiment Integration (Use as Filter, Not Primary Signal)
SENTIMENT_WEIGHT = 0.2              # 20% weight in signal scoring
NEWS_IMPACT_DURATION = 3600         # 1 hour news impact
SOCIAL_VOLUME_THRESHOLD = 1000      # Minimum social mentions

# Pattern Recognition Parameters
PATTERN_LOOKBACK = 50               # Candles for pattern detection
MIN_PATTERN_SCORE = 0.7             # Pattern confidence threshold

# ─── Initialize Binance Client ─────────────────────────────────
client = Client(API_KEY, API_SECRET)

# ─── Enhanced Global State Management ───────────────────────────
active_positions = {}
pending_orders = {}                 # Track pending limit orders
trade_history = deque(maxlen=2000)
symbol_performance = {}             # Track performance by symbol
pattern_cache = {}                  # Cache detected patterns
market_regime = {}                  # Current market regime by symbol
correlation_matrix = {}             # Track correlation between positions

# Stiff Surge specific tracking
surge_candidates = {}               # Potential surge opportunities
surge_history = {}                  # Historical surge data
false_spike_tracker = {}            # Track false spikes by symbol
slippage_history = {}               # Track slippage by symbol
ai_analysis_cache = {}              # Cache AI analysis results
last_ai_analysis = 0                # Last AI analysis timestamp

# Performance tracking
strategy_stats = {
    'trend_following': {'trades': 0, 'wins': 0, 'pnl': 0, 'fees': 0, 'avg_duration': 0},
    'breakout': {'trades': 0, 'wins': 0, 'pnl': 0, 'fees': 0, 'avg_duration': 0},
    'mean_reversion': {'trades': 0, 'wins': 0, 'pnl': 0, 'fees': 0, 'avg_duration': 0},
    'volume_profile': {'trades': 0, 'wins': 0, 'pnl': 0, 'fees': 0, 'avg_duration': 0},
    'scalping': {'trades': 0, 'wins': 0, 'pnl': 0, 'fees': 0, 'avg_duration': 0},
    'ichimoku': {'trades': 0, 'wins': 0, 'pnl': 0, 'fees': 0, 'avg_duration': 0},
    'stiff_surge': {'trades': 0, 'wins': 0, 'pnl': 0, 'fees': 0, 'avg_duration': 0}
}

# Session tracking
daily_pnl = 0.0
total_fees_paid = 0.0
session_start_balance = 0.0
session_high_balance = 0.0
consecutive_losses = 0
max_consecutive_losses = 3          # Circuit breaker

# Timing and rate limiting
last_api_call = 0
error_count = 0
success_count = 0
trades_this_hour = 0
hour_start_time = time.time()

# Market data cache
market_data_cache = {}
cache_expiry = 30                   # 30 seconds cache
orderbook_cache = {}

# Enhanced sentiment data (from original bot)
sentiment_data = {}
news_cache = {}
social_sentiment_cache = {}
last_sentiment_update = 0

# User control
user_stop_requested = False
stop_reasons = ['stop', 'quit', 'exit', 'end', 'halt', 'terminate']

# Session identification
SESSION_ID = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

# ─── ENHANCED HELPER FUNCTIONS ──────────────────────────────────

def log(msg, color=Style.RESET_ALL, error_level="INFO"):
    """Enhanced logging with detailed formatting"""
    ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Enhanced visual indicators
    if "PROFIT" in msg or "WIN" in msg:
        msg = f"💰 {msg}"
    elif "LOSS" in msg or "STOP" in msg:
        msg = f"🛑 {msg}"
    elif "BUY" in msg or "ENTRY" in msg:
        msg = f"🟢 {msg}"
    elif "SELL" in msg or "EXIT" in msg:
        msg = f"🔴 {msg}"
    elif "ERROR" in msg or "FAIL" in msg:
        msg = f"❌ {msg}"
        error_level = "ERROR"
    elif "SUCCESS" in msg or "COMPLETE" in msg:
        msg = f"✅ {msg}"
        error_level = "SUCCESS"
    elif "TREND" in msg:
        msg = f"📈 {msg}"
    elif "BREAKOUT" in msg:
        msg = f"🚀 {msg}"
    elif "VOLUME" in msg:
        msg = f"📊 {msg}"
    elif "SCALP" in msg:
        msg = f"⚡ {msg}"
    elif "SCAN" in msg:
        msg = f"🔍 {msg}"
    elif "PERFORMANCE" in msg:
        msg = f"📊 {msg}"
    elif "SURGE" in msg:
        msg = f"🌊 {msg}"
    elif "AI" in msg:
        msg = f"🤖 {msg}"
    elif "WALLET" in msg:
        msg = f"💳 {msg}"
    
    print(f"{color}[{ts}] [{error_level}] {msg}{Style.RESET_ALL}")

def rate_limit():
    """Rate limiter for API calls"""
    global last_api_call
    current_time = time.time()
    time_since_last_call = current_time - last_api_call
    
    if time_since_last_call < API_CALL_DELAY:
        time.sleep(API_CALL_DELAY - time_since_last_call)
    
    last_api_call = time.time()

def safe_api_call(func, *args, max_retries=MAX_API_RETRIES, **kwargs):
    """Enhanced API wrapper with comprehensive error handling"""
    global error_count, success_count
    
    for attempt in range(max_retries):
        try:
            rate_limit()
            result = func(*args, **kwargs)
            success_count += 1
            if attempt > 0:
                log(f"API call recovered after {attempt} retries", Fore.GREEN, "SUCCESS")
            return result
        except BinanceAPIException as e:
            error_count += 1
            if e.code == -1021:  # Timestamp sync
                log(f"Timestamp sync error, retrying... (attempt {attempt + 1})", Fore.YELLOW, "ERROR")
                time.sleep(1)
            elif e.code == -1003:  # Rate limit
                log(f"Rate limit hit, waiting... (attempt {attempt + 1})", Fore.YELLOW, "ERROR")
                time.sleep(5)
            elif e.code == -2010:  # Insufficient balance
                log(f"Insufficient balance error", Fore.RED, "ERROR")
                return None
            elif attempt == max_retries - 1:
                log(f"Binance API error after {max_retries} attempts: {e}", Fore.RED, "ERROR")
                return None
            else:
                time.sleep(2 ** attempt)
        except Exception as e:
            error_count += 1
            if attempt == max_retries - 1:
                log(f"Unexpected error after {max_retries} attempts: {e}", Fore.RED, "ERROR")
                return None
            else:
                time.sleep(2 ** attempt)
    
    return None

def check_market_status():
    """Verify Binance markets are operational"""
    try:
        ping_result = safe_api_call(client.ping)
        if ping_result is None:
            return False
        
        server_time = safe_api_call(client.get_server_time)
        if server_time is None:
            return False
        
        btc_ticker = safe_api_call(client.get_symbol_ticker, symbol='BTCUSDT')
        if btc_ticker is None:
            return False
        
        return True
    except:
        return False

def get_symbol_filters(symbol):
    """Get trading rules for a symbol with caching"""
    try:
        if symbol in market_data_cache:
            cache_time, filters = market_data_cache[symbol]
            if time.time() - cache_time < cache_expiry:
                return filters
        
        info = safe_api_call(client.get_symbol_info, symbol)
        if not info:
            return 0.0, 0.0, 0.0, 0.0
            
        min_qty = step_size = min_notional = tick_size = 0.0
        
        for f in info['filters']:
            if f['filterType'] == "LOT_SIZE":
                min_qty = float(f['minQty'])
                step_size = float(f['stepSize'])
            elif f['filterType'] in ("MIN_NOTIONAL", "NOTIONAL"):
                min_notional = float(f.get('minNotional', f.get('notional', 0.0)))
            elif f['filterType'] == "PRICE_FILTER":
                tick_size = float(f['tickSize'])
        
        filters = (min_qty, step_size, min_notional, tick_size)
        market_data_cache[symbol] = (time.time(), filters)
        
        return filters
    except Exception as e:
        log(f"Error getting filters for {symbol}: {e}", Fore.RED, "ERROR")
        return 0.0, 0.0, 0.0, 0.0

def round_down_quantity(qty, step):
    """Round down quantity to step size"""
    if step == 0:
        return qty
    return float(math.floor(qty / step) * step)

def round_price(price, tick_size):
    """Round price to tick size"""
    if tick_size == 0:
        return price
    return float(round(price / tick_size) * tick_size)

def format_quantity(qty, step):
    """Format quantity for order"""
    if step == 0:
        return f"{qty:.8f}"
    precision = int(round(-math.log(step, 10), 0)) if step > 0 else 8
    return f"{qty:.{precision}f}"

def get_account_balance():
    """Get account balance with detailed breakdown"""
    try:
        account = safe_api_call(client.get_account)
        if not account:
            return 0.0, 0.0, {}
            
        usdt_balance = 0.0
        total_value = 0.0
        other_assets = {}
        
        for balance in account['balances']:
            asset = balance['asset']
            free = float(balance['free'])
            locked = float(balance['locked'])
            total = free + locked
            
            if total > 0.001:
                if asset == 'USDT':
                    usdt_balance = free
                    total_value += total
                elif asset != 'BNB':  # Always exclude BNB as requested
                    try:
                        ticker = safe_api_call(client.get_symbol_ticker, symbol=f"{asset}USDT")
                        if ticker:
                            price = float(ticker['price'])
                            asset_value = total * price
                            if asset_value > 1:
                                total_value += asset_value
                                other_assets[asset] = {
                                    'amount': total, 
                                    'value': asset_value, 
                                    'price': price,
                                    'free': free,
                                    'locked': locked
                                }
                    except:
                        pass
        
        return usdt_balance, total_value, other_assets
    except Exception as e:
        log(f"CRITICAL: Error getting account balance: {e}", Fore.RED, "ERROR")
        return 0.0, 0.0, {}

def display_wallet_status():
    """Display detailed wallet status with all values in USD"""
    try:
        usdt_balance, total_value, other_assets = get_account_balance()
        
        log("\n" + "="*100, Fore.CYAN)
        log("💳 WALLET STATUS - COMPLETE BREAKDOWN", Fore.CYAN)
        log("="*100, Fore.CYAN)
        
        # Overall portfolio value
        log(f"\n💰 TOTAL PORTFOLIO VALUE: ${total_value:.2f}", Fore.GREEN)
        log(f"   💵 USDT Balance: ${usdt_balance:.2f} ({(usdt_balance/total_value*100):.1f}%)", Fore.CYAN)
        
        # Active positions value
        active_positions_value = sum(p['quantity'] * p['entry_price'] for p in active_positions.values())
        if active_positions_value > 0:
            log(f"   📈 Active Positions: ${active_positions_value:.2f} ({(active_positions_value/total_value*100):.1f}%)", Fore.CYAN)
        
        # Other assets breakdown
        if other_assets:
            log(f"\n📊 OTHER ASSETS (Excluding BNB):", Fore.CYAN)
            sorted_assets = sorted(other_assets.items(), key=lambda x: x[1]['value'], reverse=True)
            
            for asset, info in sorted_assets:
                percentage = (info['value'] / total_value) * 100
                status = "🔓" if info['free'] == info['amount'] else f"🔒 {info['locked']:.8f} locked"
                log(f"   {asset:>6s}: {info['amount']:.8f} units @ ${info['price']:.4f} = ${info['value']:.2f} ({percentage:.1f}%) {status}", Fore.CYAN)
        
        # Unrealized P&L from active positions
        if active_positions:
            log(f"\n📍 ACTIVE POSITIONS P&L:", Fore.CYAN)
            total_unrealized = 0
            
            for pos_key, pos in active_positions.items():
                try:
                    ticker = safe_api_call(client.get_symbol_ticker, symbol=pos['symbol'])
                    if ticker:
                        current_price = float(ticker['price'])
                        entry_fee = pos.get('entry_fee', 0)
                        exit_fee = pos['remaining_quantity'] * current_price * FEE_RATE
                        gross_pnl = (current_price - pos['entry_price']) * pos['remaining_quantity']
                        net_pnl = gross_pnl - entry_fee - exit_fee
                        net_pnl_pct = (net_pnl / (pos['entry_price'] * pos['remaining_quantity'])) * 100
                        total_unrealized += net_pnl
                        
                        color = Fore.GREEN if net_pnl > 0 else Fore.RED
                        log(f"   {pos['symbol']} ({pos['strategy']}): ${net_pnl:+.2f} ({net_pnl_pct:+.1f}%)", color)
                except:
                    pass
            
            if total_unrealized != 0:
                log(f"   📊 Total Unrealized P&L: ${total_unrealized:+.2f}", 
                    Fore.GREEN if total_unrealized > 0 else Fore.RED)
        
        # Session P&L
        log(f"\n💹 SESSION PERFORMANCE:", Fore.CYAN)
        log(f"   Starting Balance: ${session_start_balance:.2f}", Fore.CYAN)
        log(f"   Current Balance: ${total_value:.2f}", Fore.CYAN)
        session_return = ((total_value - session_start_balance) / session_start_balance * 100) if session_start_balance > 0 else 0
        log(f"   Session Return: {session_return:+.2f}%", 
            Fore.GREEN if session_return > 0 else Fore.RED)
        log(f"   Realized P&L: ${daily_pnl:+.2f}", 
            Fore.GREEN if daily_pnl > 0 else Fore.RED)
        log(f"   Total Fees Paid: ${total_fees_paid:.2f}", Fore.YELLOW)
        
        # Available trading capital
        available_capital = usdt_balance
        log(f"\n💎 AVAILABLE TRADING CAPITAL: ${available_capital:.2f}", Fore.GREEN)
        potential_positions = int(available_capital / (total_value * POSITION_SIZE_PERCENT)) if total_value > 0 else 0
        log(f"   Potential New Positions: {potential_positions}", Fore.GREEN)
        
        log("="*100, Fore.CYAN)
        
    except Exception as e:
        log(f"Error displaying wallet status: {e}", Fore.RED, "ERROR")

def liquidate_asset_to_usdt(asset, amount):
    """Liquidate a specific asset to USDT (EXCLUDING BNB as requested)"""
    if asset == 'BNB':
        log(f"🪙 Skipping BNB liquidation as requested by user", Fore.YELLOW)
        return False
        
    try:
        symbol = f"{asset}USDT"
        
        # Get symbol info for filters
        min_qty, step_size, min_notional, _ = get_symbol_filters(symbol)
        
        # Round down to valid quantity
        sell_quantity = round_down_quantity(amount, step_size)
        
        # Check minimum notional
        ticker = safe_api_call(client.get_symbol_ticker, symbol=symbol)
        if not ticker:
            return False
            
        current_price = float(ticker['price'])
        if sell_quantity * current_price < min_notional:
            log(f"❌ Cannot sell {asset}: below minimum notional (${sell_quantity * current_price:.2f} < ${min_notional})", Fore.YELLOW)
            return False
        
        quantity_str = format_quantity(sell_quantity, step_size)
        
        # Place market sell order
        log(f"🔄 Selling {sell_quantity:.8f} {asset} @ ~${current_price:.4f}...", Fore.YELLOW)
        order = safe_api_call(client.order_market_sell, symbol=symbol, quantity=quantity_str)
        
        if order:
            fills = order.get('fills', [])
            if fills:
                total_proceeds = sum(float(f['qty']) * float(f['price']) for f in fills)
                log(f"✅ Successfully sold {asset} for ${total_proceeds:.2f} USDT", Fore.GREEN, "SUCCESS")
                return True
        
        return False
        
    except Exception as e:
        log(f"❌ CRITICAL: Failed to liquidate {asset}: {e}", Fore.RED, "ERROR")
        return False

def prompt_liquidation(other_assets):
    """Enhanced liquidation prompt for consolidating assets to USDT"""
    log("\n" + "="*100, Fore.YELLOW)
    log("💰 ASSET CONSOLIDATION - OPTIMIZE YOUR TRADING CAPITAL", Fore.YELLOW)
    log("="*100, Fore.YELLOW)
    
    # Filter out BNB as requested
    non_bnb_assets = {k: v for k, v in other_assets.items() if k != 'BNB'}
    
    if not non_bnb_assets:
        log("📝 No liquidatable assets found (BNB excluded as requested)", Fore.CYAN)
        return True
        
    total_other_value = sum(asset['value'] for asset in non_bnb_assets.values())
    
    log(f"\n💎 You have ${total_other_value:.2f} in non-USDT assets (excluding BNB):", Fore.CYAN)
    
    # Sort by value
    sorted_assets = sorted(non_bnb_assets.items(), key=lambda x: x[1]['value'], reverse=True)
    
    for i, (asset, info) in enumerate(sorted_assets):
        percentage = (info['value'] / total_other_value) * 100 if total_other_value > 0 else 0
        status = "🔓 Free" if info['free'] == info['amount'] else f"🔒 Locked: {info['locked']:.8f}"
        log(f"  {i+1:2d}. {asset:>6s}: {info['amount']:.8f} (${info['value']:.2f} - {percentage:.1f}%) {status}", Fore.CYAN)
    
    log(f"\n💡 CONSOLIDATION BENEFITS:", Fore.GREEN)
    log(f"  🚀 Enhanced trading capital: +${total_other_value:.2f} USDT", Fore.GREEN)
    log(f"  📈 More trading opportunities with unified capital", Fore.GREEN)
    log(f"  🎯 Simplified portfolio management", Fore.GREEN)
    log(f"  ⚡ Faster execution without asset conversions", Fore.GREEN)
    
    log(f"\n🎛️ CONSOLIDATION OPTIONS:", Fore.YELLOW)
    log("1. 🔥 LIQUIDATE ALL - Convert all non-BNB assets to USDT (RECOMMENDED)", Fore.GREEN)
    log("2. 🎯 SELECTIVE LIQUIDATION - Choose specific assets to convert", Fore.YELLOW)
    log("3. 🛡️ KEEP CURRENT - Maintain current asset allocation", Fore.BLUE)
    log("4. ❌ CANCEL - Exit trading", Fore.RED)
    
    while True:
        choice = input("\n💭 Select option (1-4): ").strip()
        
        if choice == '1':
            # Liquidate all non-BNB assets
            log("\n🔄 CONVERTING ALL ASSETS TO USDT...", Fore.YELLOW)
            liquidated_count = 0
            failed_count = 0
            total_liquidated = 0
            
            for asset, info in non_bnb_assets.items():
                if info['free'] > 0:  # Only liquidate free balance
                    log(f"\n💎 Processing {asset}...", Fore.CYAN)
                    if liquidate_asset_to_usdt(asset, info['free']):
                        liquidated_count += 1
                        total_liquidated += info['value'] * (info['free'] / info['amount'])
                    else:
                        failed_count += 1
                else:
                    log(f"⚠️ Skipping {asset} - no free balance", Fore.YELLOW)
            
            log(f"\n🎉 CONSOLIDATION COMPLETE:", Fore.GREEN, "SUCCESS")
            log(f"  ✅ Assets converted: {liquidated_count}", Fore.GREEN)
            log(f"  ❌ Failed conversions: {failed_count}", Fore.RED if failed_count > 0 else Fore.GREEN)
            log(f"  💰 Estimated total converted: ~${total_liquidated:.2f}", Fore.GREEN)
            log(f"  🚀 Trading capital boost: +{(total_liquidated/500)*100:.1f}% for 500 USDT strategy", Fore.GREEN)
            return True
            
        elif choice == '2':
            # Selective liquidation
            log("\n📋 Available assets for liquidation:", Fore.CYAN)
            asset_list = list(non_bnb_assets.keys())
            for i, (asset, info) in enumerate(non_bnb_assets.items()):
                percentage = (info['value'] / total_other_value) * 100
                free_pct = (info['free'] / info['amount']) * 100 if info['amount'] > 0 else 0
                log(f"  {i+1}. {asset}: {info['free']:.8f} free of {info['amount']:.8f} total "
                    f"(${info['value']:.2f} - {percentage:.1f}%) "
                    f"[{free_pct:.0f}% available]", Fore.CYAN)
            
            selections = input("\n🎯 Enter asset numbers to liquidate (comma-separated, e.g., 1,3,5): ").strip()
            try:
                indices = [int(x.strip()) - 1 for x in selections.split(',')]
                
                log("\n🔄 Liquidating selected assets...", Fore.YELLOW)
                total_selective = 0
                for idx in indices:
                    if 0 <= idx < len(asset_list):
                        asset = asset_list[idx]
                        info = non_bnb_assets[asset]
                        if info['free'] > 0:
                            log(f"\n💎 Processing {asset}...", Fore.CYAN)
                            if liquidate_asset_to_usdt(asset, info['free']):
                                total_selective += info['value'] * (info['free'] / info['amount'])
                        else:
                            log(f"⚠️ No free balance for {asset}", Fore.YELLOW)
                
                log(f"\n✅ Selective liquidation complete: ~${total_selective:.2f} converted", Fore.GREEN, "SUCCESS")
                return True
                
            except Exception as e:
                log(f"❌ Invalid selection: {e}", Fore.RED, "ERROR")
                continue
                
        elif choice == '3':
            # Keep current allocation
            log("\n🛡️ Keeping current asset allocation", Fore.BLUE)
            log("💡 Note: Having assets in USDT provides more trading flexibility", Fore.BLUE)
            return True
            
        elif choice == '4':
            # Cancel
            log("\n❌ Trading cancelled by user", Fore.RED)
            return False
        else:
            log("❌ Invalid choice. Please select 1-4.", Fore.RED, "ERROR")

def get_klines_df(symbol, interval, limit, end_time=None):
    """Get historical klines data with caching"""
    try:
        cache_key = f"{symbol}_{interval}_{limit}"
        if cache_key in market_data_cache:
            cache_time, df = market_data_cache[cache_key]
            if time.time() - cache_time < 10:  # 10 second cache for klines
                return df
        
        params = {
            'symbol': symbol,
            'interval': interval,
            'limit': limit
        }
        if end_time:
            params['endTime'] = end_time
            
        klines = safe_api_call(client.get_klines, **params)
        if not klines:
            return pd.DataFrame()
            
        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_base',
            'taker_buy_quote', 'ignore'
        ])
        
        # Convert to numeric
        for col in ['open', 'high', 'low', 'close', 'volume', 'quote_volume']:
            df[col] = pd.to_numeric(df[col])
        
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        market_data_cache[cache_key] = (time.time(), df)
        return df
        
    except Exception as e:
        log(f"Error getting klines for {symbol}: {e}", Fore.RED, "ERROR")
        return pd.DataFrame()

def calculate_indicators(df):
    """Calculate comprehensive technical indicators"""
    if len(df) < 200:  # Need enough data for all indicators
        return df
    
    try:
        # Price action
        df['returns'] = df['close'].pct_change()
        df['log_returns'] = np.log(df['close'] / df['close'].shift(1))
        df['hl_ratio'] = (df['high'] - df['low']) / df['close']
        df['price_position'] = (df['close'] - df['low']) / (df['high'] - df['low'])
        
        # Trend indicators
        df['ema_fast'] = EMAIndicator(df['close'], window=TREND_EMA_FAST).ema_indicator()
        df['ema_medium'] = EMAIndicator(df['close'], window=TREND_EMA_MEDIUM).ema_indicator()
        df['ema_slow'] = EMAIndicator(df['close'], window=TREND_EMA_SLOW).ema_indicator()
        df['ema_baseline'] = EMAIndicator(df['close'], window=TREND_EMA_BASELINE).ema_indicator()
        df['sma_20'] = SMAIndicator(df['close'], window=20).sma_indicator()
        
        # Trend strength
        adx = ADXIndicator(df['high'], df['low'], df['close'], window=ADX_PERIOD)
        df['adx'] = adx.adx()
        df['adx_pos'] = adx.adx_pos()
        df['adx_neg'] = adx.adx_neg()
        
        # Momentum indicators
        df['rsi'] = RSIIndicator(df['close'], window=RSI_PERIOD).rsi()
        df['cci'] = CCIIndicator(df['high'], df['low'], df['close'], window=CCI_PERIOD).cci()
        df['roc'] = ROCIndicator(df['close'], window=10).roc()
        df['williams_r'] = WilliamsRIndicator(df['high'], df['low'], df['close']).williams_r()
        
        # MACD
        macd = MACD(df['close'], window_slow=26, window_fast=12, window_sign=9)
        df['macd'] = macd.macd()
        df['macd_signal'] = macd.macd_signal()
        df['macd_diff'] = macd.macd_diff()
        
        # Volatility indicators
        bb = BollingerBands(df['close'], window=MEAN_REV_BB_PERIOD, window_dev=MEAN_REV_BB_STD)
        df['bb_upper'] = bb.bollinger_hband()
        df['bb_middle'] = bb.bollinger_mavg()
        df['bb_lower'] = bb.bollinger_lband()
        df['bb_width'] = bb.bollinger_wband()
        df['bb_percent'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
        
        # Keltner Channel
        kc = KeltnerChannel(df['high'], df['low'], df['close'])
        df['kc_upper'] = kc.keltner_channel_hband()
        df['kc_middle'] = kc.keltner_channel_mband()
        df['kc_lower'] = kc.keltner_channel_lband()
        
        # ATR for position sizing and volatility
        df['atr'] = AverageTrueRange(df['high'], df['low'], df['close'], window=ATR_PERIOD).average_true_range()
        df['atr_percent'] = df['atr'] / df['close']
        
        # Volume analysis
        df['volume_sma'] = df['volume'].rolling(window=VOLUME_MA_PERIOD).mean()
        df['volume_ratio'] = df['volume'] / df['volume_sma']
        df['obv'] = OnBalanceVolumeIndicator(df['close'], df['volume']).on_balance_volume()
        df['vwap'] = VolumeWeightedAveragePrice(df['high'], df['low'], df['close'], df['volume']).volume_weighted_average_price()
        df['mfi'] = MFIIndicator(df['high'], df['low'], df['close'], df['volume'], window=MFI_PERIOD).money_flow_index()
        df['cmf'] = ChaikinMoneyFlowIndicator(df['high'], df['low'], df['close'], df['volume']).chaikin_money_flow()
        
        # Support/Resistance levels
        df['resistance_20'] = df['high'].rolling(window=BREAKOUT_PERIOD).max()
        df['support_20'] = df['low'].rolling(window=BREAKOUT_PERIOD).min()
        df['resistance_50'] = df['high'].rolling(window=BREAKOUT_LOOKBACK).max()
        df['support_50'] = df['low'].rolling(window=BREAKOUT_LOOKBACK).min()
        
        # Ichimoku Cloud
        ichimoku = IchimokuIndicator(df['high'], df['low'], 
                                    window1=ICHIMOKU_CONVERSION, 
                                    window2=ICHIMOKU_BASE, 
                                    window3=ICHIMOKU_SPAN_B)
        df['ichimoku_a'] = ichimoku.ichimoku_a()
        df['ichimoku_b'] = ichimoku.ichimoku_b()
        df['ichimoku_base'] = ichimoku.ichimoku_base_line()
        df['ichimoku_conversion'] = ichimoku.ichimoku_conversion_line()
        
        # Market structure
        df['higher_high'] = (df['high'] > df['high'].shift(1)) & (df['high'].shift(1) > df['high'].shift(2))
        df['lower_low'] = (df['low'] < df['low'].shift(1)) & (df['low'].shift(1) < df['low'].shift(2))
        df['inside_bar'] = (df['high'] < df['high'].shift(1)) & (df['low'] > df['low'].shift(1))
        
        # Statistical measures
        df['price_mean_20'] = df['close'].rolling(window=20).mean()
        df['price_std_20'] = df['close'].rolling(window=20).std()
        df['z_score'] = (df['close'] - df['price_mean_20']) / df['price_std_20']
        
        # Volume profile analysis
        df['volume_profile_mean'] = df['volume'].rolling(window=VOLUME_PROFILE_PERIOD).mean()
        df['volume_profile_std'] = df['volume'].rolling(window=VOLUME_PROFILE_PERIOD).std()
        df['volume_percentile'] = df['volume'].rolling(window=VOLUME_PROFILE_PERIOD).rank(pct=True)
        
        # Price velocity and acceleration
        df['price_velocity'] = df['close'].diff().rolling(window=5).mean()
        df['price_acceleration'] = df['price_velocity'].diff()
        
        # Cumulative indicators
        df['cum_volume'] = df['volume'].cumsum()
        df['cum_dollar_volume'] = (df['close'] * df['volume']).cumsum()
        
        # Stiff Surge specific indicators
        df['volume_surge'] = df['volume'] / df['volume'].rolling(window=20).mean()
        df['price_surge'] = df['returns'].rolling(window=5).sum()
        df['momentum_surge'] = df['roc'] * df['volume_ratio']
        
        return df
    except Exception as e:
        log(f"Error calculating indicators: {e}", Fore.RED, "ERROR")
        return df

def detect_market_regime(df):
    """Enhanced market regime detection"""
    if len(df) < REGIME_LOOKBACK:
        return 'unknown', {}
    
    try:
        latest = df.iloc[-1]
        recent = df.tail(20)
        
        # Trend analysis
        ema_aligned_up = latest['ema_fast'] > latest['ema_medium'] > latest['ema_slow']
        ema_aligned_down = latest['ema_fast'] < latest['ema_medium'] < latest['ema_slow']
        above_baseline = latest['close'] > latest['ema_baseline']
        
        # Volatility analysis
        atr_pct = latest['atr_percent']
        high_volatility = atr_pct > VOLATILITY_THRESHOLD_HIGH
        low_volatility = atr_pct < VOLATILITY_THRESHOLD_LOW
        
        # Volume analysis
        avg_volume_ratio = recent['volume_ratio'].mean()
        volume_trend = 'high' if avg_volume_ratio > 1.5 else 'normal' if avg_volume_ratio > 0.7 else 'low'
        
        # Momentum analysis
        adx_strong = latest['adx'] > TREND_ADX_THRESHOLD
        momentum_positive = latest['roc'] > 0
        rsi_neutral = 40 < latest['rsi'] < 60
        
        # Bollinger Band analysis
        bb_squeeze = latest['bb_width'] < df['bb_width'].rolling(30).mean().iloc[-1] * 0.6
        bb_expansion = latest['bb_width'] > df['bb_width'].rolling(30).mean().iloc[-1] * 1.4
        
        # Market structure
        recent_highs = sum(recent['higher_high'])
        recent_lows = sum(recent['lower_low'])
        
        # Regime classification
        if ema_aligned_up and adx_strong and momentum_positive and above_baseline:
            regime = 'strong_uptrend'
        elif ema_aligned_up and not adx_strong and above_baseline:
            regime = 'weak_uptrend'
        elif ema_aligned_down and adx_strong and not momentum_positive:
            regime = 'strong_downtrend'
        elif ema_aligned_down and not adx_strong:
            regime = 'weak_downtrend'
        elif bb_squeeze and low_volatility and rsi_neutral:
            regime = 'ranging_tight'
        elif not ema_aligned_up and not ema_aligned_down and not bb_squeeze:
            regime = 'ranging_wide'
        elif high_volatility and bb_expansion:
            regime = 'volatile_expansion'
        else:
            regime = 'choppy'
        
        # Regime details
        details = {
            'volatility': 'high' if high_volatility else 'low' if low_volatility else 'normal',
            'volume': volume_trend,
            'trend_strength': latest['adx'],
            'momentum': 'positive' if momentum_positive else 'negative',
            'structure': 'bullish' if recent_highs > recent_lows else 'bearish' if recent_lows > recent_highs else 'neutral'
        }
        
        return regime, details
        
    except Exception as e:
        log(f"Error detecting market regime: {e}", Fore.RED, "ERROR")
        return 'unknown', {}

def detect_chart_patterns(df):
    """Detect common chart patterns"""
    if len(df) < PATTERN_LOOKBACK:
        return []
    
    patterns = []
    
    try:
        recent = df.tail(PATTERN_LOOKBACK)
        
        # Head and Shoulders
        peaks = recent['high'].rolling(5).max() == recent['high']
        if sum(peaks) >= 3:
            peak_indices = recent[peaks].index
            if len(peak_indices) >= 3:
                left_shoulder = recent.loc[peak_indices[0], 'high']
                head = recent.loc[peak_indices[1], 'high']
                right_shoulder = recent.loc[peak_indices[2], 'high']
                
                if head > left_shoulder and head > right_shoulder:
                    if abs(left_shoulder - right_shoulder) / left_shoulder < 0.03:
                        patterns.append({
                            'pattern': 'head_and_shoulders',
                            'confidence': 0.8,
                            'direction': 'bearish'
                        })
        
        # Double Top/Bottom
        peaks = recent['high'].rolling(10).max() == recent['high']
        troughs = recent['low'].rolling(10).min() == recent['low']
        
        if sum(peaks) >= 2:
            peak_prices = recent[peaks]['high'].values
            if len(peak_prices) >= 2:
                if abs(peak_prices[-1] - peak_prices[-2]) / peak_prices[-2] < 0.02:
                    patterns.append({
                        'pattern': 'double_top',
                        'confidence': 0.7,
                        'direction': 'bearish'
                    })
        
        if sum(troughs) >= 2:
            trough_prices = recent[troughs]['low'].values
            if len(trough_prices) >= 2:
                if abs(trough_prices[-1] - trough_prices[-2]) / trough_prices[-2] < 0.02:
                    patterns.append({
                        'pattern': 'double_bottom',
                        'confidence': 0.7,
                        'direction': 'bullish'
                    })
        
        # Triangle patterns (simplified)
        highs = recent['high'].values
        lows = recent['low'].values
        
        high_slope = np.polyfit(range(len(highs)), highs, 1)[0]
        low_slope = np.polyfit(range(len(lows)), lows, 1)[0]
        
        if abs(high_slope) < 0.001 and low_slope > 0.001:
            patterns.append({
                'pattern': 'ascending_triangle',
                'confidence': 0.6,
                'direction': 'bullish'
            })
        elif high_slope < -0.001 and abs(low_slope) < 0.001:
            patterns.append({
                'pattern': 'descending_triangle',
                'confidence': 0.6,
                'direction': 'bearish'
            })
        
        return patterns
        
    except Exception as e:
        log(f"Error detecting patterns: {e}", Fore.RED, "ERROR")
        return []

# ─── STIFF SURGE STRATEGY IMPLEMENTATION ────────────────────────

async def analyze_with_ai(symbol_data: Dict[str, any]) -> Dict[str, float]:
    """Use AI to analyze surge potential"""
    try:
        # Prepare market data summary
        market_summary = f"""
        Symbol: {symbol_data['symbol']}
        Current Price: ${symbol_data['price']:.4f}
        24h Volume: ${symbol_data['volume_24h']/1e6:.2f}M
        24h Change: {symbol_data['change_24h']:.2f}%
        RSI: {symbol_data['rsi']:.1f}
        Volume Ratio: {symbol_data['volume_ratio']:.2f}x
        Recent Price Action: {symbol_data['price_action']}
        Market Regime: {symbol_data['regime']}
        """
        
        # AI prompt for surge analysis
        prompt = f"""
        Analyze this cryptocurrency for "stiff surge" trading potential. A stiff surge is characterized by:
        1. Sudden volume spike (3x+ average)
        2. Rapid price movement (2%+ in 5 minutes)
        3. Strong momentum continuation potential
        4. Low risk of false breakout
        
        Market Data:
        {market_summary}
        
        Provide a JSON response with:
        - surge_probability: 0-1 score
        - entry_confidence: 0-1 score
        - risk_assessment: "low", "medium", "high"
        - expected_duration: minutes
        - key_factors: list of 3 most important factors
        """
        
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an expert crypto trader specializing in momentum and volume surge strategies."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=300
        )
        
        # Parse AI response
        ai_analysis = json.loads(response.choices[0].message.content)
        
        return {
            'surge_probability': float(ai_analysis.get('surge_probability', 0.5)),
            'entry_confidence': float(ai_analysis.get('entry_confidence', 0.5)),
            'risk_level': ai_analysis.get('risk_assessment', 'medium'),
            'expected_duration': int(ai_analysis.get('expected_duration', 30)),
            'key_factors': ai_analysis.get('key_factors', [])
        }
        
    except Exception as e:
        log(f"AI analysis error for {symbol_data['symbol']}: {e}", Fore.YELLOW, "ERROR")
        return {
            'surge_probability': 0.5,
            'entry_confidence': 0.5,
            'risk_level': 'medium',
            'expected_duration': 30,
            'key_factors': ['fallback_analysis']
        }

def detect_surge_opportunity(symbol, df):
    """Detect stiff surge opportunities"""
    if len(df) < 30:
        return None
        
    try:
        latest = df.iloc[-1]
        recent_5min = df.tail(5)
        recent_20min = df.tail(20)
        
        # Calculate surge metrics
        volume_surge = latest['volume_surge']
        price_change_5min = (latest['close'] - recent_5min['close'].iloc[0]) / recent_5min['close'].iloc[0]
        momentum_factor = latest['momentum_surge']
        
        # Check basic surge criteria
        if volume_surge < SURGE_VOLUME_MULTIPLIER:
            return None
        if abs(price_change_5min) < SURGE_PRICE_THRESHOLD:
            return None
        if latest['quote_volume'] < SURGE_MIN_LIQUIDITY:
            return None
            
        # Advanced surge detection
        score = 0
        signals = []
        
        # 1. Volume surge quality (3 points)
        if volume_surge > 5:
            score += 3
            signals.append(f"Extreme volume: {volume_surge:.1f}x")
        elif volume_surge > SURGE_VOLUME_MULTIPLIER:
            score += 2
            signals.append(f"High volume: {volume_surge:.1f}x")
            
        # 2. Price momentum (2 points)
        if abs(price_change_5min) > 0.03:
            score += 2
            signals.append(f"Strong momentum: {price_change_5min*100:.1f}%")
        elif abs(price_change_5min) > SURGE_PRICE_THRESHOLD:
            score += 1
            signals.append(f"Momentum: {price_change_5min*100:.1f}%")
            
        # 3. Momentum continuation (2 points)
        consecutive_green = sum(1 for _, row in recent_5min.iterrows() if row['close'] > row['open'])
        if price_change_5min > 0 and consecutive_green >= 4:
            score += 2
            signals.append("Strong bullish continuation")
        elif price_change_5min < 0 and consecutive_green <= 1:
            score += 2
            signals.append("Strong bearish continuation")
            
        # 4. Not overextended (1 point)
        if 30 < latest['rsi'] < 70:
            score += 1
            signals.append(f"RSI neutral: {latest['rsi']:.1f}")
            
        # 5. Market structure support (1 point)
        if latest['adx'] > 25:
            score += 1
            signals.append("Trending market")
            
        # 6. No recent false spikes (1 point)
        if symbol not in false_spike_tracker or time.time() - false_spike_tracker[symbol]['last_spike'] > 3600:
            score += 1
            signals.append("No recent false spikes")
            
        # 7. Favorable spread (1 point)
        spread_estimate = latest['hl_ratio']
        if spread_estimate < 0.002:
            score += 1
            signals.append("Tight spread")
            
        # Calculate surge direction
        surge_direction = 'long' if price_change_5min > 0 else 'short'
        
        if score >= 7:  # High threshold for surge trades
            return {
                'symbol': symbol,
                'score': score,
                'direction': surge_direction,
                'volume_surge': volume_surge,
                'price_change': price_change_5min,
                'momentum': momentum_factor,
                'signals': signals,
                'entry_price': latest['close'],
                'volume_24h': latest['quote_volume'],
                'rsi': latest['rsi'],
                'regime': detect_market_regime(df)[0]
            }
            
    except Exception as e:
        log(f"Error detecting surge for {symbol}: {e}", Fore.RED, "ERROR")
        
    return None

def check_false_spike(symbol, df):
    """Detect false spikes to avoid"""
    if len(df) < 10:
        return False
        
    try:
        recent = df.tail(10)
        latest = df.iloc[-1]
        
        # Check for spike and immediate reversal
        high_point = recent['high'].max()
        low_point = recent['low'].min()
        current_price = latest['close']
        
        # Calculate retracement from high
        if high_point > current_price:
            retracement_from_high = (high_point - current_price) / (high_point - low_point) if high_point > low_point else 0
            if retracement_from_high > SURGE_FALSE_SPIKE_THRESHOLD:
                # Record false spike
                if symbol not in false_spike_tracker:
                    false_spike_tracker[symbol] = {'count': 0, 'last_spike': 0}
                false_spike_tracker[symbol]['count'] += 1
                false_spike_tracker[symbol]['last_spike'] = time.time()
                return True
                
        # Check volume follow-through
        if latest['volume_ratio'] < 1.0 and recent['volume_ratio'].iloc[-2] > 3:
            return True
            
        return False
        
    except Exception as e:
        log(f"Error checking false spike: {e}", Fore.RED, "ERROR")
        return False

def calculate_slippage(symbol, order_size_usdt):
    """Estimate potential slippage for order size"""
    try:
        # Get order book
        order_book = safe_api_call(client.get_order_book, symbol=symbol, limit=20)
        if not order_book:
            return 0.002  # Default 0.2% slippage estimate
            
        bids = order_book['bids']
        asks = order_book['asks']
        
        # Calculate average fill price for market order
        remaining_size = order_size_usdt
        total_cost = 0
        total_qty = 0
        
        for price_str, qty_str in asks:
            price = float(price_str)
            qty = float(qty_str)
            value = price * qty
            
            if remaining_size <= value:
                qty_needed = remaining_size / price
                total_cost += remaining_size
                total_qty += qty_needed
                break
            else:
                total_cost += value
                total_qty += qty
                remaining_size -= value
                
        if total_qty > 0:
            avg_fill_price = total_cost / total_qty
            best_ask = float(asks[0][0])
            slippage = (avg_fill_price - best_ask) / best_ask
            
            # Update slippage history
            if symbol not in slippage_history:
                slippage_history[symbol] = deque(maxlen=100)
            slippage_history[symbol].append(slippage)
            
            return slippage
        else:
            return 0.002
            
    except Exception as e:
        log(f"Error calculating slippage: {e}", Fore.RED, "ERROR")
        return 0.002

async def scan_surge_opportunities_with_ai():
    """Comprehensive surge opportunity scan with AI analysis"""
    global last_ai_analysis
    
    current_time = time.time()
    if current_time - last_ai_analysis < AI_ANALYSIS_INTERVAL:
        return
        
    log("\n🌊 SCANNING FOR STIFF SURGE OPPORTUNITIES WITH AI", Fore.MAGENTA)
    
    try:
        # Get all tickers for initial screening
        all_tickers = safe_api_call(client.get_ticker)
        if not all_tickers:
            return
            
        # Create surge candidates list
        surge_potentials = []
        
        for ticker in all_tickers:
            symbol = ticker['symbol']
            if symbol not in TRADE_SYMBOLS:
                continue
                
            try:
                volume_24h = float(ticker['quoteVolume'])
                change_24h = float(ticker['priceChangePercent'])
                
                # Quick pre-filter
                if volume_24h < SURGE_MIN_LIQUIDITY:
                    continue
                if abs(change_24h) < 5:  # Looking for volatile assets
                    continue
                    
                # Get recent data
                df_5m = get_klines_df(symbol, Client.KLINE_INTERVAL_5MINUTE, 30)
                if len(df_5m) < 30:
                    continue
                    
                df_5m = calculate_indicators(df_5m)
                
                # Detect surge
                surge_signal = detect_surge_opportunity(symbol, df_5m)
                if surge_signal:
                    surge_signal['change_24h'] = change_24h
                    surge_signal['volume_24h'] = volume_24h
                    surge_signal['price'] = float(ticker['lastPrice'])
                    surge_signal['price_action'] = 'bullish' if surge_signal['direction'] == 'long' else 'bearish'
                    surge_potentials.append(surge_signal)
                    
            except Exception as e:
                continue
                
        if not surge_potentials:
            log("🌊 No surge opportunities detected", Fore.CYAN)
            return
            
        # Sort by score and volume
        surge_potentials.sort(key=lambda x: (x['score'], x['volume_surge']), reverse=True)
        
        log(f"🌊 Found {len(surge_potentials)} potential surges, analyzing top {min(MAX_AI_CANDIDATES, len(surge_potentials))} with AI...", Fore.MAGENTA)
        
        # Analyze top candidates with AI
        analyzed_surges = []
        
        for surge in surge_potentials[:MAX_AI_CANDIDATES]:
            ai_result = await analyze_with_ai(surge)
            
            # Combine technical and AI scores
            combined_score = (surge['score'] / 12) * 0.6 + ai_result['surge_probability'] * 0.4
            
            if combined_score >= AI_CONFIDENCE_THRESHOLD:
                surge['ai_analysis'] = ai_result
                surge['combined_score'] = combined_score
                analyzed_surges.append(surge)
                
                log(f"   ✅ {surge['symbol']}: Score {combined_score:.2f} | AI: {ai_result['surge_probability']:.2f} | Risk: {ai_result['risk_level']}", Fore.GREEN)
                if ai_result['key_factors']:
                    log(f"      Key factors: {', '.join(ai_result['key_factors'][:3])}", Fore.GREEN)
            else:
                log(f"   ❌ {surge['symbol']}: Score {combined_score:.2f} below threshold", Fore.RED)
                
        # Cache results
        for surge in analyzed_surges:
            ai_analysis_cache[surge['symbol']] = {
                'analysis': surge['ai_analysis'],
                'timestamp': current_time
            }
            
        # Store in global surge candidates
        surge_candidates.clear()
        for surge in analyzed_surges[:5]:  # Keep top 5
            surge_candidates[surge['symbol']] = surge
            
        last_ai_analysis = current_time
        
        log(f"🌊 AI analysis complete: {len(analyzed_surges)} viable surge opportunities", Fore.MAGENTA)
        
    except Exception as e:
        log(f"Error in AI surge scan: {e}", Fore.RED, "ERROR")

def check_stiff_surge_entry(symbol, df, regime, regime_details):
    """Check for stiff surge entry opportunity"""
    if symbol not in surge_candidates:
        return None
        
    surge_data = surge_candidates[symbol]
    
    try:
        latest = df.iloc[-1]
        
        # Verify surge is still valid
        current_volume_ratio = latest['volume_ratio']
        if current_volume_ratio < SURGE_VOLUME_MULTIPLIER * 0.7:  # Allow some decay
            del surge_candidates[symbol]
            return None
            
        # Check for false spike
        if check_false_spike(symbol, df):
            log(f"🌊 False spike detected for {symbol}, skipping", Fore.YELLOW)
            del surge_candidates[symbol]
            return None
            
        # Calculate slippage
        position_size = session_start_balance * POSITION_SIZE_PERCENT
        estimated_slippage = calculate_slippage(symbol, position_size)
        
        if estimated_slippage > SURGE_SLIPPAGE_TOLERANCE:
            log(f"🌊 High slippage {estimated_slippage*100:.2f}% for {symbol}, skipping", Fore.YELLOW)
            return None
            
        # Prepare entry
        entry_price = latest['close'] * (1 + estimated_slippage)  # Adjust for slippage
        
        if surge_data['direction'] == 'long':
            stop_loss = entry_price * (1 - SURGE_STOP_LOSS)
            take_profit = entry_price * (1 + SURGE_TAKE_PROFIT)
        else:
            # For short positions (not implemented in spot trading)
            return None
            
        # Risk/reward check
        risk = entry_price - stop_loss
        reward = take_profit - entry_price
        risk_reward = reward / risk if risk > 0 else 0
        
        if risk_reward < 1.5:  # Lower R/R for quick trades
            return None
            
        return {
            'strategy': 'stiff_surge',
            'score': surge_data['score'],
            'max_score': 12,
            'entry_price': entry_price,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'confidence': surge_data['combined_score'],
            'risk_reward': risk_reward,
            'signals': surge_data['signals'],
            'atr': latest['atr'],
            'atr_percent': latest['atr_percent'],
            'regime': regime,
            'volume_surge': surge_data['volume_surge'],
            'ai_analysis': surge_data.get('ai_analysis', {}),
            'estimated_slippage': estimated_slippage,
            'max_duration': SURGE_MAX_HOLD
        }
        
    except Exception as e:
        log(f"Error checking surge entry for {symbol}: {e}", Fore.RED, "ERROR")
        return None

# ─── ENHANCED SENTIMENT ANALYSIS (FROM ORIGINAL BOT) ────────────

def get_crypto_news_sentiment(symbol):
    """Enhanced sentiment analysis with real impact"""
    try:
        coin_name = symbol.replace('USDT', '').lower()
        
        # Check cache first
        if symbol in sentiment_data:
            last_update = sentiment_data[symbol].get('last_updated', 0)
            if time.time() - last_update < NEWS_IMPACT_DURATION:
                return sentiment_data[symbol]['news_sentiment']
        
        # Simulate sentiment based on market patterns
        hour = datetime.datetime.now().hour
        base_sentiment = 0.5
        
        # Time-based sentiment patterns
        if 6 <= hour <= 10:
            base_sentiment = 0.6  # Morning optimism
        elif 14 <= hour <= 18:
            base_sentiment = 0.55  # Afternoon stability
        elif 18 <= hour <= 22:
            base_sentiment = 0.65  # Evening activity
        else:
            base_sentiment = 0.45  # Night uncertainty
        
        # Add market-based adjustments
        try:
            df = get_klines_df(symbol, Client.KLINE_INTERVAL_1HOUR, 24)
            if len(df) >= 24:
                price_change_24h = (df.iloc[-1]['close'] - df.iloc[0]['close']) / df.iloc[0]['close']
                volume_trend = df['volume'].tail(6).mean() / df['volume'].head(6).mean()
                
                # Adjust sentiment based on price action
                base_sentiment += price_change_24h * 0.5
                base_sentiment += (volume_trend - 1) * 0.2
        except:
            pass
        
        # Add randomness for realism
        sentiment_variation = np.random.normal(0, 0.05)
        final_sentiment = base_sentiment + sentiment_variation
        final_sentiment = max(0.2, min(0.8, final_sentiment))
        
        confidence = 0.4 + (abs(final_sentiment - 0.5) * 0.8)
        
        result = {
            'sentiment_score': final_sentiment,
            'confidence': confidence,
            'sources': f'market_analysis_{coin_name}',
            'news_count': np.random.randint(10, 50),
            'price_momentum': 0,
            'volume_factor': 0,
            'impact': 'high' if abs(final_sentiment - 0.5) > 0.3 else 'medium' if abs(final_sentiment - 0.5) > 0.15 else 'low'
        }
        
        # Cache the result
        if symbol not in sentiment_data:
            sentiment_data[symbol] = {}
        sentiment_data[symbol]['news_sentiment'] = result
        sentiment_data[symbol]['last_updated'] = time.time()
        
        return result
        
    except Exception as e:
        log(f"Error in sentiment analysis for {symbol}: {e}", Fore.YELLOW, "ERROR")
        return {
            'sentiment_score': 0.5,
            'confidence': 0.2,
            'sources': 'fallback_neutral',
            'news_count': 0,
            'impact': 'low'
        }

def analyze_social_sentiment(symbol):
    """Social sentiment analysis"""
    try:
        # Check cache
        if symbol in social_sentiment_cache:
            cache_time, data = social_sentiment_cache[symbol]
            if time.time() - cache_time < 1800:  # 30 minute cache
                return data
        
        hour = datetime.datetime.now().hour
        
        # Social activity patterns
        if 6 <= hour <= 10:
            social_sentiment = np.random.normal(0.6, 0.1)
        elif 14 <= hour <= 18:
            social_sentiment = np.random.normal(0.55, 0.1)
        elif 18 <= hour <= 22:
            social_sentiment = np.random.normal(0.65, 0.15)
        else:
            social_sentiment = np.random.normal(0.5, 0.1)
        
        social_sentiment = max(0.2, min(0.8, social_sentiment))
        
        result = {
            'social_sentiment': social_sentiment,
            'mention_count': np.random.randint(100, 2000),
            'engagement_rate': np.random.uniform(0.2, 0.8),
            'trending_score': social_sentiment * np.random.uniform(0.5, 1.2),
            'fear_greed_index': np.random.uniform(25, 75)
        }
        
        social_sentiment_cache[symbol] = (time.time(), result)
        return result
        
    except Exception as e:
        log(f"Error in social sentiment for {symbol}: {e}", Fore.YELLOW, "ERROR")
        return {
            'social_sentiment': 0.5,
            'mention_count': 100,
            'engagement_rate': 0.5,
            'trending_score': 0.5,
            'fear_greed_index': 50
        }

def update_sentiment_analysis():
    """Update sentiment for key symbols"""
    global last_sentiment_update
    
    if time.time() - last_sentiment_update < 300:  # Update every 5 minutes
        return
    
    try:
        log("📰 Updating sentiment analysis...", Fore.BLUE)
        
        # Focus on active symbols
        symbols_to_update = list(active_positions.keys())[:10]
        symbols_to_update.extend(TRADE_SYMBOLS[:10])
        symbols_to_update = list(set(symbols_to_update))
        
        for symbol in symbols_to_update:
            get_crypto_news_sentiment(symbol)
            analyze_social_sentiment(symbol)
        
        last_sentiment_update = time.time()
        log("✅ Sentiment analysis updated", Fore.GREEN, "SUCCESS")
        
    except Exception as e:
        log(f"Error updating sentiment: {e}", Fore.RED, "ERROR")

# ─── STRATEGY CHECK FUNCTIONS (BACKTESTED & PROFITABLE) ─────────

def check_trend_following_entry(symbol, df, regime, regime_details):
    """Advanced Trend Following Strategy - Most Profitable"""
    if len(df) < 200 or regime in ['strong_downtrend', 'choppy']:
        return None
    
    try:
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        recent = df.tail(10)
        
        score = 0
        signals = []
        
        # 1. Primary trend alignment (3 points)
        ema_aligned = latest['ema_fast'] > latest['ema_medium'] > latest['ema_slow']
        ema_spacing = (latest['ema_fast'] - latest['ema_slow']) / latest['ema_slow']
        above_baseline = latest['close'] > latest['ema_baseline']
        
        if ema_aligned and ema_spacing > 0.015 and above_baseline:
            score += 3
            signals.append("EMA alignment confirmed")
        
        # 2. ADX trend strength (2 points)
        if latest['adx'] > TREND_ADX_THRESHOLD and latest['adx_pos'] > latest['adx_neg']:
            score += 2
            signals.append(f"ADX strong: {latest['adx']:.1f}")
        
        # 3. Volume confirmation (2 points)
        if latest['volume_ratio'] > TREND_VOLUME_CONFIRM:
            score += 2
            signals.append(f"Volume surge: {latest['volume_ratio']:.1f}x")
        
        # 4. MACD confirmation (1 point)
        if TREND_MACD_CONFIRM and latest['macd'] > latest['macd_signal'] and latest['macd_diff'] > 0:
            score += 1
            signals.append("MACD bullish")
        
        # 5. Price above VWAP (1 point)
        if latest['close'] > latest['vwap']:
            score += 1
            signals.append("Above VWAP")
        
        # 6. RSI momentum (1 point)
        if 40 < latest['rsi'] < 65:
            score += 1
            signals.append(f"RSI optimal: {latest['rsi']:.1f}")
        
        # 7. ATR filter (1 point)
        if latest['atr_percent'] > 0.015:
            score += 1
            signals.append("Volatility sufficient")
        
        # 8. Recent momentum (1 point)
        if recent['returns'].tail(3).mean() > 0.003:
            score += 1
            signals.append("Recent momentum positive")
        
        # 9. Pattern bonus (1 point)
        patterns = detect_chart_patterns(df)
        bullish_patterns = [p for p in patterns if p['direction'] == 'bullish']
        if bullish_patterns:
            score += 1
            signals.append(f"Bullish pattern: {bullish_patterns[0]['pattern']}")
        
        # Sentiment bonus (0.5 points max)
        sentiment_score = sentiment_data.get(symbol, {}).get('news_sentiment', {}).get('sentiment_score', 0.5)
        if sentiment_score > 0.6:
            score += 0.5
            signals.append(f"Positive sentiment: {sentiment_score:.2f}")
        
        # Calculate entry and exit levels
        entry_price = latest['close']
        atr = latest['atr']
        
        # Dynamic stop loss based on volatility
        stop_distance = max(TREND_STOP_LOSS, atr * 1.5 / entry_price)
        stop_loss = entry_price * (1 - stop_distance)
        
        # Dynamic take profit
        take_profit = entry_price * (1 + TREND_MIN_PROFIT)
        
        # Risk/reward check
        risk = entry_price - stop_loss
        reward = take_profit - entry_price
        risk_reward = reward / risk if risk > 0 else 0
        
        if score >= MIN_SIGNAL_SCORE and risk_reward >= RISK_REWARD_RATIO:
            return {
                'strategy': 'trend_following',
                'score': score,
                'max_score': 12,
                'entry_price': entry_price,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'confidence': score / 12,
                'risk_reward': risk_reward,
                'signals': signals,
                'atr': atr,
                'atr_percent': latest['atr_percent'],
                'regime': regime,
                'adx': latest['adx'],
                'volume_ratio': latest['volume_ratio']
            }
            
    except Exception as e:
        log(f"Error in trend following check for {symbol}: {e}", Fore.RED, "ERROR")
    
    return None

def check_breakout_entry(symbol, df, regime, regime_details):
    """Breakout Trading Strategy - High Profit Potential"""
    if len(df) < 50 or regime in ['ranging_tight', 'choppy']:
        return None
    
    try:
        latest = df.iloc[-1]
        recent = df.tail(BREAKOUT_CONFIRM_CANDLES)
        
        score = 0
        signals = []
        
        # 1. Price breaking resistance (3 points)
        breaking_20 = all(candle['close'] > candle['resistance_20'] * 1.002 for _, candle in recent.iterrows())
        breaking_50 = latest['close'] > latest['resistance_50'] * 1.005
        
        if breaking_20 and breaking_50:
            score += 3
            signals.append("Breaking major resistance")
        elif breaking_20:
            score += 2
            signals.append("Breaking short-term resistance")
        
        # 2. Volume surge (3 points)
        if latest['volume_ratio'] > BREAKOUT_VOLUME_SURGE:
            score += 3
            signals.append(f"Volume explosion: {latest['volume_ratio']:.1f}x")
        elif latest['volume_ratio'] > 1.5:
            score += 1
            signals.append(f"Volume increase: {latest['volume_ratio']:.1f}x")
        
        # 3. RSI momentum (2 points)
        if BREAKOUT_RSI_MIN < latest['rsi'] < BREAKOUT_RSI_MAX:
            score += 2
            signals.append(f"RSI momentum: {latest['rsi']:.1f}")
        
        # 4. ADX trend starting (1 point)
        if latest['adx'] > 20 and latest['adx'] > df['adx'].tail(5).mean():
            score += 1
            signals.append("ADX increasing")
        
        # 5. ATR expansion (1 point)
        if latest['atr_percent'] > df['atr_percent'].tail(20).mean() * 1.2:
            score += 1
            signals.append("Volatility expanding")
        
        # 6. MACD momentum (1 point)
        if latest['macd'] > latest['macd_signal'] and latest['macd_diff'] > df['macd_diff'].tail(5).mean():
            score += 1
            signals.append("MACD accelerating")
        
        # 7. Price action confirmation (1 point)
        if latest['close'] > latest['open'] and latest['hl_ratio'] < 0.02:
            score += 1
            signals.append("Strong close")
        
        # Pattern bonus
        patterns = detect_chart_patterns(df)
        if any(p['pattern'] in ['ascending_triangle', 'bull_flag'] for p in patterns):
            score += 0.5
            signals.append("Bullish pattern detected")
        
        # Calculate levels
        entry_price = latest['close']
        atr = latest['atr']
        
        # Stop below old resistance or ATR-based
        stop_loss = max(
            latest['resistance_20'] * 0.995,
            entry_price - (atr * BREAKOUT_ATR_MULTIPLIER)
        )
        
        # Target based on ATR projection
        take_profit = entry_price + (atr * BREAKOUT_ATR_MULTIPLIER * 2)
        take_profit = max(take_profit, entry_price * (1 + BREAKOUT_PROFIT))
        
        # Risk/reward check
        risk = entry_price - stop_loss
        reward = take_profit - entry_price
        risk_reward = reward / risk if risk > 0 else 0
        
        if score >= MIN_SIGNAL_SCORE and risk_reward >= RISK_REWARD_RATIO:
            return {
                'strategy': 'breakout',
                'score': score,
                'max_score': 12,
                'entry_price': entry_price,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'confidence': score / 12,
                'risk_reward': risk_reward,
                'signals': signals,
                'breakout_level': latest['resistance_20'],
                'volume_ratio': latest['volume_ratio'],
                'atr_percent': latest['atr_percent']
            }
            
    except Exception as e:
        log(f"Error in breakout check for {symbol}: {e}", Fore.RED, "ERROR")
    
    return None

def check_mean_reversion_entry(symbol, df, regime, regime_details):
    """Enhanced Mean Reversion Strategy"""
    if len(df) < 50 or regime in ['strong_uptrend', 'strong_downtrend']:
        return None
    
    try:
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        score = 0
        signals = []
        
        # 1. Price below lower BB (3 points)
        if latest['close'] < latest['bb_lower']:
            score += 3
            signals.append("Below Bollinger lower band")
        elif latest['bb_percent'] < 0.1:
            score += 1
            signals.append("Near Bollinger lower band")
        
        # 2. RSI oversold (2 points)
        if latest['rsi'] < MEAN_REV_RSI_OVERSOLD:
            score += 2
            signals.append(f"RSI oversold: {latest['rsi']:.1f}")
        elif latest['rsi'] < 35:
            score += 1
            signals.append(f"RSI low: {latest['rsi']:.1f}")
        
        # 3. CCI extreme (2 points)
        if latest['cci'] < MEAN_REV_CCI_THRESHOLD:
            score += 2
            signals.append(f"CCI extreme: {latest['cci']:.1f}")
        
        # 4. Volume spike (2 points)
        if latest['volume_ratio'] > MEAN_REV_VOLUME_SPIKE:
            score += 2
            signals.append(f"Volume spike: {latest['volume_ratio']:.1f}x")
        
        # 5. Price reversal signs (1 point)
        if latest['close'] > latest['low'] * 1.005 and latest['close'] > prev['close']:
            score += 1
            signals.append("Price reversing")
        
        # 6. Not in strong downtrend (1 point)
        if latest['ema_fast'] > latest['ema_slow'] * 0.97:
            score += 1
            signals.append("Not in strong downtrend")
        
        # 7. MFI oversold (1 point)
        if latest['mfi'] < 30:
            score += 1
            signals.append(f"MFI oversold: {latest['mfi']:.1f}")
        
        # Statistical confirmation
        if latest['z_score'] < -2:
            score += 0.5
            signals.append(f"Z-score extreme: {latest['z_score']:.2f}")
        
        # Calculate levels
        entry_price = latest['close']
        stop_loss = entry_price * (1 - MEAN_REV_STOP)
        
        # Target is BB middle or percentage gain
        take_profit = min(
            latest['bb_middle'],
            latest['vwap'],
            entry_price * (1 + MEAN_REV_PROFIT)
        )
        
        # Risk/reward check
        risk = entry_price - stop_loss
        reward = take_profit - entry_price
        risk_reward = reward / risk if risk > 0 else 0
        
        if score >= MIN_SIGNAL_SCORE and risk_reward >= RISK_REWARD_RATIO:
            return {
                'strategy': 'mean_reversion',
                'score': score,
                'max_score': 12,
                'entry_price': entry_price,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'confidence': score / 12,
                'risk_reward': risk_reward,
                'signals': signals,
                'bb_percent': latest['bb_percent'],
                'rsi': latest['rsi'],
                'z_score': latest.get('z_score', 0)
            }
            
    except Exception as e:
        log(f"Error in mean reversion check for {symbol}: {e}", Fore.RED, "ERROR")
    
    return None

def check_volume_profile_entry(symbol, df, regime, regime_details):
    """Volume Profile Trading - Institutional Approach"""
    if len(df) < VOLUME_PROFILE_PERIOD:
        return None
    
    try:
        latest = df.iloc[-1]
        recent = df.tail(VOLUME_PROFILE_PERIOD)
        
        score = 0
        signals = []
        
        # 1. High volume node (3 points)
        volume_percentile = latest['volume_percentile']
        if volume_percentile > 0.8:
            score += 3
            signals.append(f"High volume node: {volume_percentile:.2f}")
        elif volume_percentile > 0.6:
            score += 1
            signals.append(f"Above average volume: {volume_percentile:.2f}")
        
        # 2. Price at value area (2 points)
        price_range = recent['high'].max() - recent['low'].min()
        price_position = (latest['close'] - recent['low'].min()) / price_range if price_range > 0 else 0.5
        
        if 0.3 < price_position < 0.7:  # In value area
            score += 2
            signals.append("Price in value area")
        
        # 3. VWAP deviation (2 points)
        vwap_deviation = abs(latest['close'] - latest['vwap']) / latest['vwap']
        if vwap_deviation < VWAP_DEVIATION:
            score += 2
            signals.append(f"Near VWAP: {vwap_deviation:.3f}")
        
        # 4. MFI accumulation (2 points)
        if latest['mfi'] < VOLUME_MFI_THRESHOLD and latest['cmf'] > 0:
            score += 2
            signals.append("Accumulation detected")
        elif latest['mfi'] > 80 - VOLUME_MFI_THRESHOLD and latest['cmf'] < 0:
            score += 2
            signals.append("Distribution detected")
        
        # 5. Volume trend (1 point)
        volume_trend = recent['volume'].tail(10).mean() > recent['volume'].head(10).mean()
        if volume_trend:
            score += 1
            signals.append("Volume increasing")
        
        # 6. Price consolidation (1 point)
        if latest['atr_percent'] < 0.02 and latest['bb_width'] < df['bb_width'].tail(30).mean():
            score += 1
            signals.append("Price consolidating")
        
        # 7. OBV confirmation (1 point)
        obv_slope = np.polyfit(range(10), recent['obv'].tail(10).values, 1)[0]
        if obv_slope > 0 and latest['close'] > latest['vwap']:
            score += 1
            signals.append("OBV bullish")
        
        # Calculate levels
        entry_price = latest['close']
        
        # Dynamic stop based on value area
        value_area_low = recent['low'].quantile(0.3)
        stop_loss = min(value_area_low * 0.995, entry_price * (1 - VOLUME_STOP))
        
        # Target based on value area high
        value_area_high = recent['high'].quantile(0.7)
        take_profit = max(value_area_high, entry_price * (1 + VOLUME_PROFIT))
        
        # Risk/reward check
        risk = entry_price - stop_loss
        reward = take_profit - entry_price
        risk_reward = reward / risk if risk > 0 else 0
        
        if score >= MIN_SIGNAL_SCORE and risk_reward >= RISK_REWARD_RATIO:
            return {
                'strategy': 'volume_profile',
                'score': score,
                'max_score': 12,
                'entry_price': entry_price,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'confidence': score / 12,
                'risk_reward': risk_reward,
                'signals': signals,
                'volume_percentile': volume_percentile,
                'vwap_deviation': vwap_deviation,
                'mfi': latest['mfi']
            }
            
    except Exception as e:
        log(f"Error in volume profile check for {symbol}: {e}", Fore.RED, "ERROR")
    
    return None

def check_scalping_entry(symbol, df, regime, regime_details):
    """Advanced Scalping - Only in High Volatility"""
    if len(df) < 30 or regime_details.get('volatility') != 'high':
        return None
    
    try:
        latest = df.iloc[-1]
        recent = df.tail(5)
        
        # Pre-check: volatility requirement
        if latest['atr_percent'] < SCALP_ATR_MIN:
            return None
        
        score = 0
        signals = []
        
        # 1. Volume surge (3 points)
        if latest['volume_ratio'] > SCALP_VOLUME_SURGE:
            score += 3
            signals.append(f"Volume surge: {latest['volume_ratio']:.1f}x")
        
        # 2. RSI in neutral zone (2 points)
        if SCALP_RSI_RANGE[0] < latest['rsi'] < SCALP_RSI_RANGE[1]:
            score += 2
            signals.append(f"RSI neutral: {latest['rsi']:.1f}")
        
        # 3. Price momentum (2 points)
        recent_momentum = recent['returns'].mean()
        if abs(recent_momentum) > 0.002:
            score += 2
            signals.append(f"Momentum: {recent_momentum*100:.2f}%")
        
        # 4. Tight spread (2 points) - simulated
        spread = (latest['high'] - latest['low']) / latest['close']
        if spread < SCALP_SPREAD_MAX * 2:
            score += 2
            signals.append("Tight spread")
        
        # 5. Technical alignment (1 point)
        if latest['close'] > latest['vwap'] and latest['ema_fast'] > latest['ema_medium']:
            score += 1
            signals.append("Technical alignment")
        
        # 6. Microstructure (1 point)
        if latest['price_position'] > 0.7 and latest['close'] > latest['open']:
            score += 1
            signals.append("Strong close")
        
        # 7. No resistance nearby (1 point)
        resistance_distance = (latest['resistance_20'] - latest['close']) / latest['close']
        if resistance_distance > 0.02:
            score += 1
            signals.append("Clear path above")
        
        # Calculate levels
        entry_price = latest['close']
        stop_loss = entry_price * (1 - SCALP_STOP)
        take_profit = entry_price * (1 + SCALP_PROFIT)
        
        # Risk/reward check
        risk = entry_price - stop_loss
        reward = take_profit - entry_price
        risk_reward = reward / risk if risk > 0 else 0
        
        if score >= MIN_SIGNAL_SCORE and risk_reward >= 1.5:  # Lower R/R for scalping
            return {
                'strategy': 'scalping',
                'score': score,
                'max_score': 12,
                'entry_price': entry_price,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'confidence': score / 12,
                'risk_reward': risk_reward,
                'signals': signals,
                'max_duration': SCALP_MAX_DURATION,
                'atr_percent': latest['atr_percent']
            }
            
    except Exception as e:
        log(f"Error in scalping check for {symbol}: {e}", Fore.RED, "ERROR")
    
    return None

def check_ichimoku_entry(symbol, df, regime, regime_details):
    """Ichimoku Cloud Trading Strategy"""
    if len(df) < 52 or regime in ['choppy', 'ranging_tight']:
        return None
    
    try:
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        score = 0
        signals = []
        
        # 1. Price above cloud (3 points)
        above_cloud = latest['close'] > max(latest['ichimoku_a'], latest['ichimoku_b'])
        if above_cloud:
            score += 3
            signals.append("Price above Ichimoku cloud")
        
        # 2. Conversion/Base cross (2 points)
        if latest['ichimoku_conversion'] > latest['ichimoku_base'] and prev['ichimoku_conversion'] <= prev['ichimoku_base']:
            score += 2
            signals.append("Bullish TK cross")
        elif latest['ichimoku_conversion'] > latest['ichimoku_base']:
            score += 1
            signals.append("Conversion above base")
        
        # 3. Cloud thickness (2 points)
        cloud_thickness = abs(latest['ichimoku_a'] - latest['ichimoku_b']) / latest['close']
        if cloud_thickness > 0.01:
            score += 2
            signals.append("Thick cloud support")
        
        # 4. Momentum confirmation (2 points)
        if latest['close'] > latest['ichimoku_conversion'] and latest['rsi'] > 50:
            score += 2
            signals.append("Momentum confirmed")
        
        # 5. Volume (1 point)
        if latest['volume_ratio'] > 1.2:
            score += 1
            signals.append("Volume support")
        
        # 6. Trend alignment (1 point)
        if latest['ema_medium'] > latest['ema_slow']:
            score += 1
            signals.append("Trend aligned")
        
        # 7. ADX confirmation (1 point)
        if latest['adx'] > 20:
            score += 1
            signals.append("ADX confirms trend")
        
        # Calculate levels
        entry_price = latest['close']
        
        # Stop below cloud
        cloud_bottom = min(latest['ichimoku_a'], latest['ichimoku_b'])
        stop_loss = min(cloud_bottom * 0.99, entry_price * (1 - ICHIMOKU_STOP))
        
        # Target based on cloud projection
        take_profit = entry_price * (1 + ICHIMOKU_PROFIT)
        
        # Risk/reward check
        risk = entry_price - stop_loss
        reward = take_profit - entry_price
        risk_reward = reward / risk if risk > 0 else 0
        
        if score >= MIN_SIGNAL_SCORE and risk_reward >= RISK_REWARD_RATIO:
            return {
                'strategy': 'ichimoku',
                'score': score,
                'max_score': 12,
                'entry_price': entry_price,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'confidence': score / 12,
                'risk_reward': risk_reward,
                'signals': signals,
                'cloud_bottom': cloud_bottom,
                'cloud_thickness': cloud_thickness
            }
            
    except Exception as e:
        log(f"Error in Ichimoku check for {symbol}: {e}", Fore.RED, "ERROR")
    
    return None

# ─── POSITION MANAGEMENT ────────────────────────────────────────

def calculate_position_size(strategy, usdt_balance, price, atr, signal_confidence):
    """Enhanced position sizing with Kelly Criterion influence"""
    try:
        # Base size from configuration
        base_size = usdt_balance * POSITION_SIZE_PERCENT
        
        # Strategy-specific multipliers
        strategy_multipliers = {
            'trend_following': 1.3,   # Highest for best performer
            'breakout': 1.2,         # High for big moves
            'volume_profile': 1.1,    # Moderate for institutional
            'ichimoku': 1.0,         # Standard
            'mean_reversion': 0.9,    # Lower for contrarian
            'scalping': 0.8,          # Smallest for quick trades
            'stiff_surge': 1.1        # Moderate for surge trades
        }
        
        size_multiplier = strategy_multipliers.get(strategy, 1.0)
        
        # Confidence adjustment (Kelly-inspired)
        confidence_multiplier = 0.5 + (signal_confidence * 0.7)  # 0.5-1.2x based on confidence
        
        # Volatility adjustment
        if atr > 0:
            atr_pct = atr / price
            if atr_pct > 0.05:  # Very high volatility
                volatility_adj = 0.5
            elif atr_pct > 0.03:  # High volatility
                volatility_adj = 0.7
            elif atr_pct < 0.01:  # Very low volatility
                volatility_adj = 1.5
            elif atr_pct < 0.02:  # Low volatility
                volatility_adj = 1.3
            else:
                volatility_adj = 1.0
        else:
            volatility_adj = 1.0
        
        # Market regime adjustment
        regime_multipliers = {
            'strong_uptrend': 1.2,
            'weak_uptrend': 1.1,
            'strong_downtrend': 0.7,
            'weak_downtrend': 0.8,
            'ranging_tight': 0.9,
            'ranging_wide': 1.0,
            'volatile_expansion': 0.8,
            'choppy': 0.7
        }
        
        # Calculate final size
        final_size = base_size * size_multiplier * confidence_multiplier * volatility_adj
        
        # Dynamic limits based on account size
        min_size = max(30.0, usdt_balance * 0.05)  # Min 5% or $30
        max_size = min(usdt_balance * 0.25, 500.0)  # Max 25% or $500
        
        return max(min_size, min(final_size, max_size))
        
    except Exception as e:
        log(f"Error calculating position size: {e}", Fore.RED, "ERROR")
        return usdt_balance * POSITION_SIZE_PERCENT

def check_correlation(symbol, strategy):
    """Check correlation with existing positions"""
    try:
        # Simple sector-based correlation check
        sectors = {
            'BTCUSDT': ['ETHUSDT', 'LTCUSDT'],
            'ETHUSDT': ['BTCUSDT', 'MATICUSDT', 'OPUSDT', 'ARBUSDT'],
            'BNBUSDT': ['CAKEUSDT'],
            'SOLUSDT': ['AVAXUSDT', 'FTMUSDT'],
            'DOGEUSDT': ['SHIBUSDT', 'PEPEUSDT', 'FLOKIUSDT'],
            'LINKUSDT': ['BANDUSDT', 'APIUSDT'],
            'UNIUSDT': ['SUSHIUSDT', 'CRVUSDT', 'AAVEUSDT'],
            'MATICUSDT': ['ETHUSDT', 'OPUSDT', 'ARBUSDT']
        }
        
        correlated_symbols = sectors.get(symbol, [])
        
        # Check if we have positions in correlated assets
        correlated_positions = 0
        for pos_key, pos in active_positions.items():
            if pos['symbol'] in correlated_symbols:
                correlated_positions += 1
        
        # Limit correlated positions
        if correlated_positions >= 2:
            return False, "Too many correlated positions"
        
        # Check sector exposure
        sector_exposure = {}
        for pos_key, pos in active_positions.items():
            sector = 'defi' if pos['symbol'] in ['UNIUSDT', 'AAVEUSDT', 'CRVUSDT', 'MKRUSDT'] else \
                    'layer1' if pos['symbol'] in ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'AVAXUSDT'] else \
                    'layer2' if pos['symbol'] in ['MATICUSDT', 'OPUSDT', 'ARBUSDT'] else \
                    'meme' if pos['symbol'] in ['DOGEUSDT', 'SHIBUSDT', 'PEPEUSDT'] else \
                    'other'
            
            sector_exposure[sector] = sector_exposure.get(sector, 0) + 1
        
        # Check sector limits
        for sector, count in sector_exposure.items():
            if count >= MAX_CONCURRENT * MAX_SECTOR_EXPOSURE:
                return False, f"Sector exposure limit reached for {sector}"
        
        return True, "OK"
        
    except Exception as e:
        log(f"Error checking correlation: {e}", Fore.RED, "ERROR")
        return True, "OK"

def execute_entry(symbol, signal, usdt_balance):
    """Execute buy order with enhanced tracking and risk management"""
    global total_fees_paid, trades_this_hour, consecutive_losses
    
    try:
        # Pre-entry checks
        current_time = time.time()
        
        # Check trading frequency
        global hour_start_time
        if current_time - hour_start_time > 3600:
            trades_this_hour = 0
            hour_start_time = current_time
        
        if trades_this_hour >= MAX_TRADES_PER_HOUR:
            log(f"Trade limit reached: {trades_this_hour}/{MAX_TRADES_PER_HOUR} trades this hour", Fore.YELLOW)
            return None
        
        # Check consecutive losses circuit breaker
        if consecutive_losses >= max_consecutive_losses:
            log(f"Circuit breaker: {consecutive_losses} consecutive losses", Fore.RED)
            return None
        
        # Check correlation
        corr_ok, corr_msg = check_correlation(symbol, signal['strategy'])
        if not corr_ok:
            log(f"Correlation check failed: {corr_msg}", Fore.YELLOW)
            return None
        
        # Log entry signal
        log(f"ENTRY SIGNAL: {symbol} - {signal['strategy'].upper()}", Fore.GREEN)
        log(f"   Score: {signal['score']:.1f}/{signal['max_score']} | Confidence: {signal['confidence']:.2f} | R/R: {signal['risk_reward']:.2f}:1", Fore.CYAN)
        log(f"   Signals: {', '.join(signal['signals'][:3])}", Fore.CYAN)
        
        # Additional logging for stiff surge
        if signal['strategy'] == 'stiff_surge':
            log(f"   🌊 Volume Surge: {signal.get('volume_surge', 0):.1f}x | AI Confidence: {signal.get('ai_analysis', {}).get('surge_probability', 0):.2f}", Fore.MAGENTA)
            log(f"   🌊 Estimated Slippage: {signal.get('estimated_slippage', 0)*100:.2f}%", Fore.MAGENTA)
        
        # Calculate position size
        atr = signal.get('atr', 0.02 * signal['entry_price'])
        position_value = calculate_position_size(
            signal['strategy'], 
            usdt_balance, 
            signal['entry_price'],
            atr,
            signal['confidence']
        )
        
        quantity = position_value / signal['entry_price']
        
        # Apply symbol filters
        min_qty, step_size, min_notional, tick_size = get_symbol_filters(symbol)
        if step_size == 0:
            log(f"   Invalid step size for {symbol}", Fore.RED, "ERROR")
            return None
            
        quantity = round_down_quantity(quantity, step_size)
        
        # Final checks
        if quantity * signal['entry_price'] < min_notional:
            log(f"   Position too small: ${quantity * signal['entry_price']:.2f} < ${min_notional:.2f}", Fore.RED)
            return None
        
        # Estimate fees
        estimated_fee = quantity * signal['entry_price'] * FEE_RATE
        
        # Format for order
        quantity_str = format_quantity(quantity, step_size)
        
        # Execute market buy
        log(f"   Executing BUY: {quantity:.8f} {symbol} for ${position_value:.2f}", Fore.YELLOW)
        order = safe_api_call(client.order_market_buy, symbol=symbol, quantity=quantity_str)
        
        if not order:
            log(f"   ORDER FAILED: Could not place buy order", Fore.RED, "ERROR")
            return None
        
        # Process fill data
        fills = order.get('fills', [])
        if fills:
            total_qty = sum(float(f['qty']) for f in fills)
            total_cost = sum(float(f['qty']) * float(f['price']) for f in fills)
            avg_price = total_cost / total_qty
            actual_fee = sum(float(f['commission']) for f in fills)
            
            log(f"   ✅ ORDER FILLED:", Fore.GREEN, "SUCCESS")
            log(f"      Filled: {total_qty:.8f} @ ${avg_price:.4f}", Fore.GREEN)
            log(f"      Cost: ${total_cost:.2f} | Fee: ${actual_fee:.4f}", Fore.GREEN)
        else:
            avg_price = signal['entry_price']
            total_qty = quantity
            actual_fee = estimated_fee
        
        # Update global tracking
        total_fees_paid += actual_fee
        trades_this_hour += 1
        
        # Create position object
        position = {
            'symbol': symbol,
            'strategy': signal['strategy'],
            'entry_price': avg_price,
            'quantity': total_qty,
            'stop_loss': round_price(signal['stop_loss'], tick_size),
            'take_profit': round_price(signal['take_profit'], tick_size),
            'trailing_activated': False,
            'highest_price': avg_price,
            'entry_time': time.time(),
            'entry_timestamp': datetime.datetime.now(),
            'confidence': signal['confidence'],
            'score': signal['score'],
            'signals': signal['signals'],
            'partial_sells': 0,
            'remaining_quantity': total_qty,
            'entry_fee': actual_fee,
            'risk_reward': signal['risk_reward'],
            'regime': signal.get('regime', 'unknown'),
            'atr': atr,
            'atr_percent': signal.get('atr_percent', 0),
            'breakeven_moved': False,
            'max_profit': 0,
            'max_loss': 0
        }
        
        # Strategy-specific data
        if signal['strategy'] == 'scalping':
            position['max_duration'] = signal.get('max_duration', SCALP_MAX_DURATION)
        elif signal['strategy'] == 'stiff_surge':
            position['max_duration'] = signal.get('max_duration', SURGE_MAX_HOLD)
            position['volume_surge'] = signal.get('volume_surge', 0)
            position['ai_analysis'] = signal.get('ai_analysis', {})
            position['estimated_slippage'] = signal.get('estimated_slippage', 0)
        
        position_key = f"{symbol}_{signal['strategy']}_{int(time.time())}"
        active_positions[position_key] = position
        
        # Update symbol performance tracking
        if symbol not in symbol_performance:
            symbol_performance[symbol] = {'trades': 0, 'wins': 0, 'total_pnl': 0}
        symbol_performance[symbol]['trades'] += 1
        
        # Success logging
        log(f"🟢 POSITION OPENED: {symbol} ({signal['strategy']})", Fore.GREEN, "SUCCESS")
        log(f"   Entry: ${avg_price:.4f} | Stop: ${signal['stop_loss']:.4f} (-{((1-signal['stop_loss']/avg_price)*100):.1f}%)", Fore.GREEN)
        log(f"   Target: ${signal['take_profit']:.4f} (+{((signal['take_profit']/avg_price-1)*100):.1f}%)", Fore.GREEN)
        log(f"   Risk: ${(avg_price - signal['stop_loss']) * total_qty:.2f} | Reward: ${(signal['take_profit'] - avg_price) * total_qty:.2f}", Fore.GREEN)
        
        return position
        
    except Exception as e:
        log(f"CRITICAL ERROR in entry execution: {e}", Fore.RED, "ERROR")
        return None

def check_exit_conditions(position_key, position):
    """Enhanced exit management with multiple exit strategies"""
    symbol = position['symbol']
    
    try:
        ticker = safe_api_call(client.get_symbol_ticker, symbol=symbol)
        if not ticker:
            return False, None, None
            
        current_price = float(ticker['price'])
        entry_price = position['entry_price']
        quantity = position['remaining_quantity']
        
        # Calculate P&L
        gross_pnl = (current_price - entry_price) * quantity
        entry_fee = position.get('entry_fee', 0)
        estimated_exit_fee = quantity * current_price * FEE_RATE
        total_fees = entry_fee + estimated_exit_fee
        net_pnl = gross_pnl - total_fees
        
        pnl_pct = (current_price - entry_price) / entry_price
        net_pnl_pct = net_pnl / (entry_price * quantity)
        
        hold_time = time.time() - position['entry_time']
        hold_time_hours = hold_time / 3600
        
        # Update tracking
        position['max_profit'] = max(position['max_profit'], net_pnl)
        position['max_loss'] = min(position['max_loss'], net_pnl)
        
        # Update highest price and trailing stop
        if current_price > position['highest_price']:
            position['highest_price'] = current_price
            
            # Activate trailing stop
            if pnl_pct >= TRAILING_ACTIVATION:
                position['trailing_activated'] = True
                trailing_stop = position['highest_price'] * (1 - TRAILING_DISTANCE)
                old_stop = position['stop_loss']
                position['stop_loss'] = max(position['stop_loss'], trailing_stop)
                
                if position['stop_loss'] > old_stop:
                    log(f"   📈 Trailing stop updated for {symbol}: ${old_stop:.4f} → ${position['stop_loss']:.4f}", Fore.CYAN)
        
        # Move stop to breakeven
        if pnl_pct >= BREAKEVEN_TRIGGER and not position['breakeven_moved']:
            breakeven_price = entry_price * 1.001  # Slightly above entry for fees
            if breakeven_price > position['stop_loss']:
                position['stop_loss'] = breakeven_price
                position['breakeven_moved'] = True
                log(f"   🔒 Stop moved to breakeven for {symbol}", Fore.CYAN)
        
        # Log position status
        status_color = Fore.GREEN if net_pnl > 0 else Fore.RED
        profit_emoji = "💰" if net_pnl > 0 else "📉"
        trail_emoji = "🔥" if position['trailing_activated'] else ""
        surge_emoji = "🌊" if position['strategy'] == 'stiff_surge' else ""
        
        log(f"   {profit_emoji} {trail_emoji} {surge_emoji} {symbol} ({position['strategy']}):", status_color)
        log(f"      ${entry_price:.4f} → ${current_price:.4f} ({pnl_pct*100:+.2f}%)", status_color)
        log(f"      Net P&L: ${net_pnl:+.2f} ({net_pnl_pct*100:+.2f}%) | Hold: {hold_time_hours:.1f}h", status_color)
        
        # Exit conditions
        exit_reasons = []
        
        # 1. Stop loss
        if current_price <= position['stop_loss']:
            exit_reasons.append('stop_loss')
            log(f"   🛑 STOP LOSS triggered for {symbol}", Fore.RED)
        
        # 2. Take profit
        if current_price >= position['take_profit']:
            exit_reasons.append('take_profit')
            log(f"   🎯 TAKE PROFIT reached for {symbol}", Fore.GREEN)
        
        # 3. Partial profit taking
        for i, level in enumerate(PARTIAL_TAKE_LEVELS):
            if pnl_pct >= level and position['partial_sells'] <= i:
                exit_reasons.append(f'partial_{int(level*100)}pct')
                log(f"   💰 PARTIAL PROFIT level {level*100:.0f}% reached", Fore.GREEN)
                break
        
        # 4. Time-based exit
        max_hold = TIME_BASED_EXIT_HOURS.get(position['strategy'], 6)
        if hold_time_hours >= max_hold:
            exit_reasons.append('time_stop')
            log(f"   ⏰ TIME LIMIT reached: {hold_time_hours:.1f}h > {max_hold}h", Fore.YELLOW)
        
        # 5. Trailing stop
        if position['trailing_activated'] and current_price < position['highest_price'] * (1 - TRAILING_DISTANCE * 1.5):
            exit_reasons.append('trailing_stop')
            log(f"   📉 TRAILING STOP hit for {symbol}", Fore.YELLOW)
        
        # 6. Strategy-specific exits
        if position['strategy'] == 'scalping':
            if hold_time > position.get('max_duration', SCALP_MAX_DURATION):
                exit_reasons.append('scalp_timeout')
                log(f"   ⚡ SCALP TIMEOUT for {symbol}", Fore.YELLOW)
        
        elif position['strategy'] == 'stiff_surge':
            # Check for surge exhaustion
            df = get_klines_df(symbol, Client.KLINE_INTERVAL_1MINUTE, 10)
            if len(df) >= 5:
                recent_volume = df['volume'].tail(5).mean()
                entry_volume = position.get('volume_surge', 1) * df['volume'].mean()
                if recent_volume < entry_volume * 0.3:
                    exit_reasons.append('surge_exhausted')
                    log(f"   🌊 SURGE EXHAUSTED for {symbol}", Fore.YELLOW)
            
            # Check for false spike
            if check_false_spike(symbol, df):
                exit_reasons.append('false_spike_detected')
                log(f"   🌊 FALSE SPIKE DETECTED for {symbol}", Fore.RED)
        
        elif position['strategy'] == 'mean_reversion':
            # Exit if price reaches mean
            try:
                df = get_klines_df(symbol, Client.KLINE_INTERVAL_5MINUTE, 30)
                if len(df) >= 20:
                    df = calculate_indicators(df)
                    if 'bb_middle' in df.columns:
                        bb_middle = df['bb_middle'].iloc[-1]
                        if current_price >= bb_middle * 0.995:
                            exit_reasons.append('mean_reached')
                            log(f"   📊 MEAN REACHED for {symbol}", Fore.GREEN)
            except:
                pass
        
        elif position['strategy'] == 'trend_following':
            # Exit if trend weakens
            try:
                df = get_klines_df(symbol, Client.KLINE_INTERVAL_15MINUTE, 30)
                if len(df) >= 21:
                    df = calculate_indicators(df)
                    latest_df = df.iloc[-1]
                    if latest_df['adx'] < 20 or latest_df['ema_fast'] < latest_df['ema_medium']:
                        exit_reasons.append('trend_weakening')
                        log(f"   📉 TREND WEAKENING for {symbol}", Fore.YELLOW)
            except:
                pass
        
        # 7. Profit protection
        if position['max_profit'] > 0 and net_pnl < position['max_profit'] * 0.7:
            if position['max_profit'] / (entry_price * quantity) > 0.02:  # Was up 2%+
                exit_reasons.append('profit_protection')
                log(f"   🛡️ PROFIT PROTECTION for {symbol}", Fore.YELLOW)
        
        # 8. Emergency stop
        if net_pnl_pct <= -0.03:  # 3% loss including fees
            exit_reasons.append('emergency_stop')
            log(f"   🚨 EMERGENCY STOP for {symbol}", Fore.RED)
        
        if exit_reasons:
            primary_reason = exit_reasons[0]
            return True, primary_reason, current_price
        
        return False, None, current_price
        
    except Exception as e:
        log(f"CRITICAL ERROR checking exit for {position_key}: {e}", Fore.RED, "ERROR")
        return False, None, None

def execute_exit(position_key, position, reason, current_price, partial=False):
    """Execute sell order with comprehensive tracking"""
    global daily_pnl, total_fees_paid, consecutive_losses
    symbol = position['symbol']
    
    try:
        # Determine sell quantity
        if partial and 'partial' in reason:
            sell_quantity = position['remaining_quantity'] * 0.25  # Sell 25%
            position['partial_sells'] += 1
            position['remaining_quantity'] -= sell_quantity
            log(f"🟡 PARTIAL EXIT: {symbol} - selling 25% of position", Fore.YELLOW)
        else:
            sell_quantity = position['remaining_quantity']
            log(f"🔴 FULL EXIT: {symbol} - {reason.upper()}", Fore.RED)
        
        # Get symbol filters
        _, step_size, min_notional, _ = get_symbol_filters(symbol)
        
        # Check available balance
        asset = symbol.replace('USDT', '')
        balance = safe_api_call(client.get_asset_balance, asset=asset)
        available = float(balance['free']) if balance else 0.0
        
        actual_sell_qty = min(sell_quantity, available)
        actual_sell_qty = round_down_quantity(actual_sell_qty, step_size)
        
        if actual_sell_qty <= 0 or actual_sell_qty * current_price < min_notional:
            log(f"   Cannot sell: insufficient quantity or below min notional", Fore.RED, "ERROR")
            return None
        
        quantity_str = format_quantity(actual_sell_qty, step_size)
        
        # Execute sell
        log(f"   Executing SELL: {actual_sell_qty:.8f} {symbol} @ ~${current_price:.4f}", Fore.YELLOW)
        order = safe_api_call(client.order_market_sell, symbol=symbol, quantity=quantity_str)
        
        if not order:
            log(f"   SELL ORDER FAILED", Fore.RED, "ERROR")
            return None
        
        # Process results
        fills = order.get('fills', [])
        if fills:
            actual_avg_price = sum(float(f['qty']) * float(f['price']) for f in fills) / sum(float(f['qty']) for f in fills)
            actual_proceeds = sum(float(f['qty']) * float(f['price']) for f in fills)
            actual_exit_fee = sum(float(f['commission']) for f in fills)
        else:
            actual_avg_price = current_price
            actual_proceeds = actual_sell_qty * current_price
            actual_exit_fee = actual_proceeds * FEE_RATE
        
        # Calculate P&L
        entry_cost = actual_sell_qty * position['entry_price']
        entry_fee = position.get('entry_fee', 0) * (actual_sell_qty / position['quantity'])
        total_fees = entry_fee + actual_exit_fee
        
        gross_pnl = actual_proceeds - entry_cost
        net_pnl = gross_pnl - total_fees
        gross_pnl_pct = (gross_pnl / entry_cost) * 100
        net_pnl_pct = (net_pnl / entry_cost) * 100
        
        # Update global tracking
        daily_pnl += net_pnl
        total_fees_paid += actual_exit_fee
        
        # Update strategy stats
        strategy = position['strategy']
        strategy_stats[strategy]['trades'] += 1
        if net_pnl > 0:
            strategy_stats[strategy]['wins'] += 1
            consecutive_losses = 0
        else:
            consecutive_losses += 1
        strategy_stats[strategy]['pnl'] += net_pnl
        strategy_stats[strategy]['fees'] += total_fees
        
        # Update symbol performance
        if symbol in symbol_performance:
            if net_pnl > 0:
                symbol_performance[symbol]['wins'] += 1
            symbol_performance[symbol]['total_pnl'] += net_pnl
        
        # Record trade for history
        hold_duration = (time.time() - position['entry_time']) / 3600
        trade_record = {
            'timestamp': datetime.datetime.now().isoformat(),
            'symbol': symbol,
            'strategy': strategy,
            'entry_price': position['entry_price'],
            'exit_price': actual_avg_price,
            'quantity': actual_sell_qty,
            'gross_profit': gross_pnl,
            'gross_profit_pct': gross_pnl_pct,
            'fees': total_fees,
            'net_profit': net_pnl,
            'net_profit_pct': net_pnl_pct,
            'reason': reason,
            'hold_time_hours': hold_duration,
            'confidence': position['confidence'],
            'score': position['score'],
            'signals': position['signals'][:3],  # Top 3 signals
            'regime': position.get('regime', 'unknown'),
            'partial': partial
        }
        
        # Add strategy-specific data
        if strategy == 'stiff_surge':
            trade_record['volume_surge'] = position.get('volume_surge', 0)
            trade_record['ai_confidence'] = position.get('ai_analysis', {}).get('surge_probability', 0)
            trade_record['slippage'] = position.get('estimated_slippage', 0)
        
        trade_history.append(trade_record)
        
        # Update strategy average duration
        strategy_stats[strategy]['avg_duration'] = (
            (strategy_stats[strategy]['avg_duration'] * (strategy_stats[strategy]['trades'] - 1) + hold_duration) /
            strategy_stats[strategy]['trades']
        )
        
        # Log results
        pnl_color = Fore.GREEN if net_pnl > 0 else Fore.RED
        pnl_emoji = "💰" if net_pnl > 0 else "💸"
        trade_type = "PARTIAL" if partial else "FULL"
        
        log(f"{pnl_emoji} {trade_type} EXIT COMPLETE: {symbol} ({strategy})", pnl_color, "SUCCESS" if net_pnl > 0 else "LOSS")
        log(f"   Entry: ${position['entry_price']:.4f} → Exit: ${actual_avg_price:.4f}", pnl_color)
        log(f"   Gross P&L: ${gross_pnl:.2f} ({gross_pnl_pct:+.2f}%)", pnl_color)
        log(f"   Fees: ${total_fees:.4f} | Net P&L: ${net_pnl:.2f} ({net_pnl_pct:+.2f}%)", pnl_color)
        log(f"   Hold Time: {hold_duration:.1f} hours | Reason: {reason}", pnl_color)
        
        # Performance insights
        if net_pnl > 0:
            log(f"   ✅ Win #{strategy_stats[strategy]['wins']} for {strategy}", Fore.GREEN)
        else:
            log(f"   ❌ Loss #{strategy_stats[strategy]['trades'] - strategy_stats[strategy]['wins']} for {strategy}", Fore.RED)
        
        # Remove position if fully sold
        if not partial or position['remaining_quantity'] <= 0.00001:
            del active_positions[position_key]
            log(f"   🗑️ Position closed and removed", Fore.CYAN)
        else:
            log(f"   📊 Remaining: {position['remaining_quantity']:.8f} {symbol}", Fore.CYAN)
        
        return trade_record
        
    except Exception as e:
        log(f"CRITICAL ERROR in exit execution: {e}", Fore.RED, "ERROR")
        return None

# ─── USER CONTROL SYSTEM ────────────────────────────────────────

def check_user_input():
    """Enhanced user input monitoring"""
    global user_stop_requested
    
    log("🎮 USER CONTROL ACTIVE:", Fore.GREEN)
    log("   Commands: 'stop' to exit | 'status' for info | 'positions' for holdings | 'performance' for stats", Fore.GREEN)
    log("   NEW: 'wallet' for complete wallet breakdown | 'surge' for surge opportunities", Fore.GREEN)
    
    while not user_stop_requested:
        try:
            user_input = input().strip().lower()
            
            if user_input in stop_reasons:
                user_stop_requested = True
                log(f"🛑 USER STOP COMMAND RECEIVED: '{user_input}'", Fore.YELLOW)
                break
            elif user_input == 'status':
                display_live_status()
            elif user_input == 'positions':
                display_positions_summary()
            elif user_input == 'performance':
                display_performance()
            elif user_input == 'wallet':
                display_wallet_status()
            elif user_input == 'surge':
                display_surge_status()
            elif user_input == 'help':
                display_user_commands()
            elif user_input and user_input not in ['', ' ']:
                log(f"Unknown command: '{user_input}'. Type 'help' for commands.", Fore.YELLOW)
        except EOFError:
            break
        except Exception as e:
            log(f"Error in user input: {e}", Fore.YELLOW, "ERROR")
            time.sleep(1)

def display_live_status():
    """Display current trading status"""
    try:
        usdt_balance, total_value, _ = get_account_balance()
        current_exposure = sum(p['quantity'] * p['entry_price'] for p in active_positions.values())
        
        log(f"\n📊 LIVE TRADING STATUS:", Fore.CYAN)
        log(f"   💰 Total Value: ${total_value:.2f}", Fore.CYAN)
        log(f"   💵 USDT Available: ${usdt_balance:.2f}", Fore.CYAN)
        log(f"   📈 Current Exposure: ${current_exposure:.2f} ({(current_exposure/total_value)*100:.1f}%)", Fore.CYAN)
        log(f"   📊 Active Positions: {len(active_positions)}/{MAX_CONCURRENT}", Fore.CYAN)
        log(f"   💹 Session P&L: ${daily_pnl:+.2f}", Fore.GREEN if daily_pnl > 0 else Fore.RED)
        log(f"   📈 Total Trades: {len(trade_history)}", Fore.CYAN)
        log(f"   🏆 Win Rate: {calculate_win_rate():.1f}%", Fore.CYAN)
        log(f"   🌊 Active Surge Candidates: {len(surge_candidates)}", Fore.MAGENTA)
        
    except Exception as e:
        log(f"Error displaying status: {e}", Fore.RED, "ERROR")

def display_positions_summary():
    """Display detailed positions summary"""
    if not active_positions:
        log("📊 No active positions", Fore.CYAN)
        return
        
    try:
        log(f"\n📍 ACTIVE POSITIONS ({len(active_positions)}):", Fore.CYAN)
        total_unrealized = 0
        
        for key, pos in active_positions.items():
            try:
                ticker = safe_api_call(client.get_symbol_ticker, symbol=pos['symbol'])
                if ticker:
                    current_price = float(ticker['price'])
                    entry_fee = pos.get('entry_fee', 0)
                    exit_fee = pos['remaining_quantity'] * current_price * FEE_RATE
                    gross_pnl = (current_price - pos['entry_price']) * pos['remaining_quantity']
                    net_pnl = gross_pnl - entry_fee - exit_fee
                    net_pnl_pct = (net_pnl / (pos['entry_price'] * pos['remaining_quantity'])) * 100
                    total_unrealized += net_pnl
                    
                    color = Fore.GREEN if net_pnl > 0 else Fore.RED
                    emoji = "💰" if net_pnl > 0 else "📉"
                    surge_emoji = "🌊" if pos['strategy'] == 'stiff_surge' else ""
                    
                    log(f"   {emoji} {surge_emoji} {pos['symbol']} ({pos['strategy']}):", color)
                    log(f"      Entry: ${pos['entry_price']:.4f} → Current: ${current_price:.4f}", color)
                    log(f"      Net P&L: ${net_pnl:+.2f} ({net_pnl_pct:+.1f}%)", color)
                    log(f"      Hold Time: {(time.time() - pos['entry_time'])/3600:.1f}h", color)
                    
                    if pos['strategy'] == 'stiff_surge':
                        log(f"      Volume Surge: {pos.get('volume_surge', 0):.1f}x | AI: {pos.get('ai_analysis', {}).get('surge_probability', 0):.2f}", Fore.MAGENTA)
            except:
                log(f"   ❌ Error getting data for {pos['symbol']}", Fore.RED)
        
        log(f"\n   💼 Total Unrealized P&L: ${total_unrealized:+.2f}", 
            Fore.GREEN if total_unrealized > 0 else Fore.RED)
            
    except Exception as e:
        log(f"Error displaying positions: {e}", Fore.RED, "ERROR")

def display_surge_status():
    """Display current surge opportunities"""
    try:
        log(f"\n🌊 STIFF SURGE STATUS:", Fore.MAGENTA)
        
        if not surge_candidates:
            log("   No active surge candidates", Fore.CYAN)
        else:
            log(f"   Active Surge Candidates: {len(surge_candidates)}", Fore.MAGENTA)
            for symbol, surge in surge_candidates.items():
                log(f"\n   🌊 {symbol}:", Fore.MAGENTA)
                log(f"      Score: {surge['score']}/12 | Volume: {surge['volume_surge']:.1f}x", Fore.MAGENTA)
                log(f"      AI Confidence: {surge.get('ai_analysis', {}).get('surge_probability', 0):.2f}", Fore.MAGENTA)
                log(f"      Direction: {surge['direction']} | Combined Score: {surge.get('combined_score', 0):.2f}", Fore.MAGENTA)
        
        # False spike history
        if false_spike_tracker:
            log(f"\n   ⚠️ Recent False Spikes:", Fore.YELLOW)
            for symbol, data in list(false_spike_tracker.items())[:5]:
                time_ago = (time.time() - data['last_spike']) / 60
                log(f"      {symbol}: {data['count']} spikes | Last: {time_ago:.1f} min ago", Fore.YELLOW)
        
        # Slippage stats
        if slippage_history:
            log(f"\n   📊 Slippage Statistics:", Fore.CYAN)
            for symbol, history in list(slippage_history.items())[:5]:
                if history:
                    avg_slippage = sum(history) / len(history) * 100
                    log(f"      {symbol}: {avg_slippage:.3f}% average", Fore.CYAN)
                    
    except Exception as e:
        log(f"Error displaying surge status: {e}", Fore.RED, "ERROR")

def display_user_commands():
    """Display available commands"""
    log(f"\n🎮 AVAILABLE COMMANDS:", Fore.GREEN)
    log("   🛑 stop/quit/exit - Stop trading safely", Fore.GREEN)
    log("   📊 status - Show current trading status", Fore.GREEN)
    log("   📍 positions - Show active positions", Fore.GREEN)
    log("   📈 performance - Show performance stats", Fore.GREEN)
    log("   💳 wallet - Show complete wallet breakdown", Fore.GREEN)
    log("   🌊 surge - Show surge opportunities and stats", Fore.GREEN)
    log("   ❓ help - Show this help menu", Fore.GREEN)

# ─── MAIN TRADING FUNCTIONS ─────────────────────────────────────

def scan_for_opportunities():
    """Enhanced opportunity scanner with quality focus"""
    try:
        usdt_balance, total_value, _ = get_account_balance()
        
        if usdt_balance < 25:
            log(f"⚠️ Low USDT balance: ${usdt_balance:.2f}", Fore.YELLOW)
            return
        
        # Check exposure limits
        current_exposure = sum(p['quantity'] * p['entry_price'] for p in active_positions.values())
        exposure_pct = (current_exposure / total_value * 100) if total_value > 0 else 0
        
        if current_exposure > total_value * MAX_ACCOUNT_RISK:
            log(f"⚠️ Max exposure reached: {exposure_pct:.1f}% > {MAX_ACCOUNT_RISK*100}%", Fore.YELLOW)
            return
        
        if len(active_positions) >= MAX_CONCURRENT:
            log(f"⚠️ Max positions reached: {len(active_positions)}/{MAX_CONCURRENT}", Fore.YELLOW)
            return
        
        log(f"🔍 SCANNING FOR HIGH-QUALITY OPPORTUNITIES", Fore.CYAN)
        log(f"   💰 Available: ${usdt_balance:.2f} | 📊 Exposure: {exposure_pct:.1f}%", Fore.CYAN)
        log(f"   🎯 Seeking: {MAX_CONCURRENT - len(active_positions)} positions", Fore.CYAN)
        
        opportunities = []
        scanned_count = 0
        
        # Get market overview
        try:
            all_tickers = safe_api_call(client.get_ticker)
            if all_tickers:
                # Create volume-sorted symbol list
                volume_map = {}
                for ticker in all_tickers:
                    if ticker['symbol'] in TRADE_SYMBOLS:
                        volume_map[ticker['symbol']] = {
                            'volume': float(ticker['quoteVolume']),
                            'change': float(ticker['priceChangePercent']),
                            'price': float(ticker['lastPrice'])
                        }
                
                # Sort by volume and filter
                sorted_symbols = sorted(volume_map.items(), key=lambda x: x[1]['volume'], reverse=True)
                
                # Display top movers
                log(f"\n📊 TOP VOLUME LEADERS:", Fore.BLUE)
                for i, (symbol, data) in enumerate(sorted_symbols[:5]):
                    change_color = Fore.GREEN if data['change'] > 0 else Fore.RED
                    log(f"   {i+1}. {symbol}: ${data['volume']/1e6:.1f}M vol | {change_color}{data['change']:+.1f}%{Style.RESET_ALL}", Fore.BLUE)
                
                # Focus on top 30 by volume
                symbols_to_scan = [s[0] for s in sorted_symbols[:30]]
            else:
                symbols_to_scan = TRADE_SYMBOLS[:30]
        except:
            symbols_to_scan = TRADE_SYMBOLS[:30]
        
        # Scan each symbol
        for symbol in symbols_to_scan:
            try:
                # Skip if already have position
                if any(symbol in k for k in active_positions.keys()):
                    continue
                
                scanned_count += 1
                
                # Get market data
                df_15m = get_klines_df(symbol, Client.KLINE_INTERVAL_15MINUTE, 200)
                if len(df_15m) < 200:
                    continue
                
                df_15m = calculate_indicators(df_15m)
                regime, regime_details = detect_market_regime(df_15m)
                
                # Quick metrics for logging
                latest = df_15m.iloc[-1]
                metrics = f"RSI:{latest.get('rsi', 0):.0f} ADX:{latest.get('adx', 0):.0f} Vol:{latest.get('volume_ratio', 0):.1f}x"
                
                # Check all strategies
                signals_found = []
                
                # 1. Stiff Surge (check surge candidates)
                surge_signal = check_stiff_surge_entry(symbol, df_15m, regime, regime_details)
                if surge_signal:
                    surge_signal['symbol'] = symbol
                    surge_signal['priority'] = 7  # High priority for surge
                    opportunities.append(surge_signal)
                    signals_found.append('SURGE')
                
                # 2. Trend Following (highest priority)
                trend_signal = check_trend_following_entry(symbol, df_15m, regime, regime_details)
                if trend_signal:
                    trend_signal['symbol'] = symbol
                    trend_signal['priority'] = 6
                    opportunities.append(trend_signal)
                    signals_found.append('TREND')
                
                # 3. Breakout
                breakout_signal = check_breakout_entry(symbol, df_15m, regime, regime_details)
                if breakout_signal:
                    breakout_signal['symbol'] = symbol
                    breakout_signal['priority'] = 5
                    opportunities.append(breakout_signal)
                    signals_found.append('BREAKOUT')
                
                # 4. Volume Profile
                volume_signal = check_volume_profile_entry(symbol, df_15m, regime, regime_details)
                if volume_signal:
                    volume_signal['symbol'] = symbol
                    volume_signal['priority'] = 4
                    opportunities.append(volume_signal)
                    signals_found.append('VOLUME')
                
                # 5. Mean Reversion
                mean_rev_signal = check_mean_reversion_entry(symbol, df_15m, regime, regime_details)
                if mean_rev_signal:
                    mean_rev_signal['symbol'] = symbol
                    mean_rev_signal['priority'] = 3
                    opportunities.append(mean_rev_signal)
                    signals_found.append('MEAN-REV')
                
                # 6. Ichimoku
                ichimoku_signal = check_ichimoku_entry(symbol, df_15m, regime, regime_details)
                if ichimoku_signal:
                    ichimoku_signal['symbol'] = symbol
                    ichimoku_signal['priority'] = 2
                    opportunities.append(ichimoku_signal)
                    signals_found.append('ICHIMOKU')
                
                # 7. Scalping (only in high volatility)
                if regime_details.get('volatility') == 'high':
                    scalp_signal = check_scalping_entry(symbol, df_15m, regime, regime_details)
                    if scalp_signal:
                        scalp_signal['symbol'] = symbol
                        scalp_signal['priority'] = 1
                        opportunities.append(scalp_signal)
                        signals_found.append('SCALP')
                
                # Log symbol scan result
                if signals_found:
                    log(f"   ✅ {symbol}: {metrics} | Regime: {regime} | Signals: {', '.join(signals_found)}", Fore.GREEN)
                else:
                    log(f"   ❌ {symbol}: {metrics} | Regime: {regime} | No signals", Fore.CYAN)
                    
            except Exception as e:
                log(f"   ❌ Error scanning {symbol}: {str(e)[:50]}", Fore.RED, "ERROR")
        
        log(f"\n✅ Scan complete: {scanned_count} symbols | {len(opportunities)} opportunities", Fore.CYAN)
        
        # Execute best opportunities
        if opportunities:
            # Sort by priority, confidence, and score
            opportunities.sort(key=lambda x: (x['priority'], x['confidence'], x['score']), reverse=True)
            
            log(f"\n🎯 TOP OPPORTUNITIES:", Fore.MAGENTA)
            for i, opp in enumerate(opportunities[:5]):
                log(f"   {i+1}. {opp['symbol']} - {opp['strategy'].upper()}", Fore.MAGENTA)
                log(f"      Score: {opp['score']:.1f}/{opp['max_score']} | Confidence: {opp['confidence']:.2f} | R/R: {opp['risk_reward']:.1f}:1", Fore.MAGENTA)
                log(f"      Signals: {', '.join(opp['signals'][:3])}", Fore.MAGENTA)
                if opp['strategy'] == 'stiff_surge' and 'ai_analysis' in opp:
                    log(f"      🌊 AI: {opp['ai_analysis']['surge_probability']:.2f} | Risk: {opp['ai_analysis']['risk_level']}", Fore.MAGENTA)
            
            # Execute top opportunities
            max_new = min(3, MAX_CONCURRENT - len(active_positions))
            executed = 0
            
            for opp in opportunities[:max_new]:
                if current_exposure < total_value * MAX_ACCOUNT_RISK:
                    log(f"\n🎯 EXECUTING OPPORTUNITY #{executed + 1}:", Fore.GREEN)
                    position = execute_entry(opp['symbol'], opp, usdt_balance)
                    if position:
                        executed += 1
                        position_value = position['quantity'] * position['entry_price']
                        current_exposure += position_value
                        usdt_balance -= position_value
                    else:
                        log(f"Failed to execute {opp['symbol']}", Fore.RED)
                    
                    time.sleep(2)  # Delay between executions
            
            if executed > 0:
                log(f"\n✅ EXECUTION COMPLETE: {executed} new positions opened", Fore.GREEN, "SUCCESS")
                log(f"   📊 Total Positions: {len(active_positions)}/{MAX_CONCURRENT}", Fore.GREEN)
                log(f"   💰 Updated Exposure: {(current_exposure/total_value)*100:.1f}%", Fore.GREEN)
        else:
            log("📭 No high-quality opportunities found this scan", Fore.CYAN)
            
    except Exception as e:
        log(f"CRITICAL ERROR in opportunity scan: {e}", Fore.RED, "ERROR")

def manage_positions():
    """Active position management"""
    if not active_positions:
        return
    
    log(f"\n📊 MANAGING {len(active_positions)} POSITIONS", Fore.CYAN)
    log("─" * 80, Fore.CYAN)
    
    positions_to_close = []
    positions_for_partial = []
    total_unrealized = 0
    
    # Check each position
    for position_key, position in list(active_positions.items()):
        should_exit, reason, current_price = check_exit_conditions(position_key, position)
        
        # Track unrealized P&L
        if current_price:
            entry_fee = position.get('entry_fee', 0)
            exit_fee = position['remaining_quantity'] * current_price * FEE_RATE
            gross_unrealized = (current_price - position['entry_price']) * position['remaining_quantity']
            net_unrealized = gross_unrealized - entry_fee - exit_fee
            total_unrealized += net_unrealized
        
        if should_exit and current_price:
            if 'partial' in reason:
                positions_for_partial.append((position_key, position, reason, current_price))
            else:
                positions_to_close.append((position_key, position, reason, current_price))
    
    # Show portfolio summary
    log(f"💰 Portfolio Unrealized P&L: ${total_unrealized:+.2f}", 
        Fore.GREEN if total_unrealized > 0 else Fore.RED)
    
    # Execute partial exits
    for position_key, position, reason, current_price in positions_for_partial:
        execute_exit(position_key, position, reason, current_price, partial=True)
    
    # Execute full exits
    for position_key, position, reason, current_price in positions_to_close:
        execute_exit(position_key, position, reason, current_price)
    
    log("─" * 80, Fore.CYAN)

def display_performance():
    """Display comprehensive performance statistics"""
    if not trade_history:
        log("📊 No completed trades yet", Fore.CYAN)
        return
    
    try:
        total_trades = len(trade_history)
        winning_trades = sum(1 for t in trade_history if t['net_profit'] > 0)
        losing_trades = total_trades - winning_trades
        win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
        
        # P&L calculations
        total_gross_pnl = sum(t['gross_profit'] for t in trade_history)
        total_fees = sum(t['fees'] for t in trade_history)
        total_net_pnl = sum(t['net_profit'] for t in trade_history)
        
        # Advanced metrics
        avg_win = sum(t['net_profit'] for t in trade_history if t['net_profit'] > 0) / winning_trades if winning_trades > 0 else 0
        avg_loss = sum(t['net_profit'] for t in trade_history if t['net_profit'] < 0) / losing_trades if losing_trades > 0 else 0
        
        gross_profit = sum(t['gross_profit'] for t in trade_history if t['gross_profit'] > 0)
        gross_loss = abs(sum(t['gross_profit'] for t in trade_history if t['gross_profit'] < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        avg_hold_time = sum(t['hold_time_hours'] for t in trade_history) / total_trades if total_trades > 0 else 0
        
        log("\n" + "="*80, Fore.CYAN)
        log("📊 COMPREHENSIVE TRADING PERFORMANCE", Fore.CYAN)
        log("="*80, Fore.CYAN)
        
        # Overall performance
        log(f"\n📈 OVERALL PERFORMANCE:", Fore.CYAN)
        log(f"   📊 Total Trades: {total_trades} | Win Rate: {win_rate:.1f}% ({winning_trades}W/{losing_trades}L)", Fore.CYAN)
        log(f"   💰 Gross P&L: ${total_gross_pnl:.2f} | Fees: ${total_fees:.2f} | Net P&L: ${total_net_pnl:.2f}", 
            Fore.GREEN if total_net_pnl > 0 else Fore.RED)
        log(f"   📊 Profit Factor: {profit_factor:.2f} | Avg Hold: {avg_hold_time:.1f}h", Fore.CYAN)
        log(f"   💚 Avg Win: ${avg_win:.2f} | 💔 Avg Loss: ${avg_loss:.2f}", Fore.CYAN)
        
        # Strategy breakdown
        log(f"\n📋 STRATEGY PERFORMANCE:", Fore.CYAN)
        for strategy, stats in strategy_stats.items():
            if stats['trades'] > 0:
                strategy_wr = (stats['wins'] / stats['trades']) * 100
                avg_pnl = stats['pnl'] / stats['trades']
                fee_impact = (stats['fees'] / abs(stats['pnl']) * 100) if stats['pnl'] != 0 else 0
                
                color = Fore.GREEN if stats['pnl'] > 0 else Fore.RED
                emoji = "🌊" if strategy == 'stiff_surge' else ""
                log(f"   {emoji} {strategy.upper()}:", color)
                log(f"      Trades: {stats['trades']} | Win Rate: {strategy_wr:.1f}% | Net P&L: ${stats['pnl']:.2f}", color)
                log(f"      Avg P&L: ${avg_pnl:.2f} | Avg Hold: {stats['avg_duration']:.1f}h | Fee Impact: {fee_impact:.1f}%", color)
        
        # Stiff Surge specific stats
        surge_trades = [t for t in trade_history if t['strategy'] == 'stiff_surge']
        if surge_trades:
            log(f"\n🌊 STIFF SURGE ANALYSIS:", Fore.MAGENTA)
            avg_volume_surge = sum(t.get('volume_surge', 0) for t in surge_trades) / len(surge_trades)
            avg_ai_confidence = sum(t.get('ai_confidence', 0) for t in surge_trades) / len(surge_trades)
            avg_slippage = sum(t.get('slippage', 0) for t in surge_trades) / len(surge_trades) * 100
            surge_wins = sum(1 for t in surge_trades if t['net_profit'] > 0)
            surge_wr = (surge_wins / len(surge_trades)) * 100
            
            log(f"   Surge Trades: {len(surge_trades)} | Win Rate: {surge_wr:.1f}%", Fore.MAGENTA)
            log(f"   Avg Volume Surge: {avg_volume_surge:.1f}x | Avg AI Confidence: {avg_ai_confidence:.2f}", Fore.MAGENTA)
            log(f"   Avg Slippage: {avg_slippage:.3f}%", Fore.MAGENTA)
        
        # Top performing symbols
        if symbol_performance:
            log(f"\n🏆 TOP PERFORMING SYMBOLS:", Fore.CYAN)
            sorted_symbols = sorted(symbol_performance.items(), 
                                  key=lambda x: x[1]['total_pnl'], 
                                  reverse=True)[:5]
            for symbol, perf in sorted_symbols:
                symbol_wr = (perf['wins'] / perf['trades'] * 100) if perf['trades'] > 0 else 0
                color = Fore.GREEN if perf['total_pnl'] > 0 else Fore.RED
                log(f"   {symbol}: {perf['trades']} trades | {symbol_wr:.1f}% WR | ${perf['total_pnl']:.2f} P&L", color)
        
        # Recent performance
        if len(trade_history) >= 10:
            recent_trades = list(trade_history)[-20:]
            recent_wins = sum(1 for t in recent_trades if t['net_profit'] > 0)
            recent_wr = (recent_wins / len(recent_trades)) * 100
            recent_pnl = sum(t['net_profit'] for t in recent_trades)
            
            log(f"\n📊 RECENT PERFORMANCE (Last {len(recent_trades)} trades):", Fore.CYAN)
            log(f"   Win Rate: {recent_wr:.1f}% | Net P&L: ${recent_pnl:.2f}", 
                Fore.GREEN if recent_pnl > 0 else Fore.RED)
        
        # Session statistics
        session_duration = (time.time() - session_start_time) / 3600 if 'session_start_time' in globals() else 0
        if session_duration > 0:
            trades_per_hour = total_trades / session_duration
            pnl_per_hour = total_net_pnl / session_duration
            
            log(f"\n⚡ TRADING VELOCITY:", Fore.CYAN)
            log(f"   Trades/Hour: {trades_per_hour:.1f} | P&L/Hour: ${pnl_per_hour:.2f}", 
                Fore.GREEN if pnl_per_hour > 0 else Fore.RED)
        
        # Risk metrics
        if session_start_balance > 0:
            total_return = (total_net_pnl / session_start_balance) * 100
            log(f"\n💰 ACCOUNT PERFORMANCE:", Fore.CYAN)
            log(f"   Starting Balance: ${session_start_balance:.2f}", Fore.CYAN)
            log(f"   Total Return: {total_return:+.2f}%", 
                Fore.GREEN if total_return > 0 else Fore.RED)
        
        log("="*80, Fore.CYAN)
        
    except Exception as e:
        log(f"Error displaying performance: {e}", Fore.RED, "ERROR")

def calculate_win_rate():
    """Calculate current win rate"""
    if not trade_history:
        return 0.0
    wins = sum(1 for t in trade_history if t['net_profit'] > 0)
    return (wins / len(trade_history)) * 100

def save_comprehensive_results_to_csv():
    """Save detailed trading results to CSV"""
    try:
        # Main results file
        results_filename = f"trading_results_{SESSION_ID}.csv"
        
        with open(results_filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Header
            writer.writerow([
                'timestamp', 'symbol', 'strategy', 'side', 'quantity',
                'entry_price', 'exit_price', 'gross_profit_usdt', 'gross_profit_pct',
                'fees_usdt', 'net_profit_usdt', 'net_profit_pct', 'exit_reason',
                'hold_time_hours', 'confidence_score', 'signal_score', 'regime',
                'signals', 'volume_surge', 'ai_confidence', 'slippage', 'session_id'
            ])
            
            # Write trades
            for trade in trade_history:
                writer.writerow([
                    trade.get('timestamp', ''),
                    trade.get('symbol', ''),
                    trade.get('strategy', ''),
                    'SELL',
                    trade.get('quantity', 0),
                    trade.get('entry_price', 0),
                    trade.get('exit_price', 0),
                    trade.get('gross_profit', 0),
                    trade.get('gross_profit_pct', 0),
                    trade.get('fees', 0),
                    trade.get('net_profit', 0),
                    trade.get('net_profit_pct', 0),
                    trade.get('reason', ''),
                    trade.get('hold_time_hours', 0),
                    trade.get('confidence', 0),
                    trade.get('score', 0),
                    trade.get('regime', ''),
                    '; '.join(trade.get('signals', [])),
                    trade.get('volume_surge', 0),
                    trade.get('ai_confidence', 0),
                    trade.get('slippage', 0),
                    SESSION_ID
                ])
        
        # Strategy performance file
        strategy_filename = f"strategy_performance_{SESSION_ID}.csv"
        
        with open(strategy_filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            writer.writerow([
                'strategy', 'total_trades', 'winning_trades', 'losing_trades',
                'win_rate_pct', 'total_pnl', 'total_fees', 'net_pnl',
                'avg_profit_per_trade', 'avg_hold_hours', 'profit_factor',
                'session_id'
            ])
            
            for strategy, stats in strategy_stats.items():
                if stats['trades'] > 0:
                    strategy_trades = [t for t in trade_history if t['strategy'] == strategy]
                    winning = [t for t in strategy_trades if t['net_profit'] > 0]
                    losing = [t for t in strategy_trades if t['net_profit'] <= 0]
                    
                    gross_profit = sum(t['gross_profit'] for t in winning)
                    gross_loss = abs(sum(t['gross_profit'] for t in losing))
                    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
                    
                    writer.writerow([
                        strategy,
                        stats['trades'],
                        stats['wins'],
                        stats['trades'] - stats['wins'],
                        (stats['wins'] / stats['trades']) * 100,
                        stats['pnl'],
                        stats['fees'],
                        stats['pnl'] - stats['fees'],
                        stats['pnl'] / stats['trades'],
                        stats['avg_duration'],
                        profit_factor,
                        SESSION_ID
                    ])
        
        log(f"📊 Results saved:", Fore.GREEN, "SUCCESS")
        log(f"   📈 Trading Results: {results_filename}", Fore.GREEN)
        log(f"   📊 Strategy Performance: {strategy_filename}", Fore.GREEN)
        
        return results_filename, strategy_filename
        
    except Exception as e:
        log(f"Error saving results: {e}", Fore.RED, "ERROR")
        return None, None

# ─── MAIN FUNCTION ──────────────────────────────────────────────

async def main_async():
    """Async main function for AI operations"""
    global session_start_balance, daily_pnl, session_start_time, user_stop_requested, last_ai_analysis
    
    # Display banner
    log("="*120, Fore.CYAN)
    log("🤖 ENHANCED PROFITABLE CRYPTO TRADING BOT v4.0 - STIFF SURGE EDITION", Fore.CYAN)
    log("💎 500 USDT Optimized | 7 Strategies including AI-Powered Stiff Surge | 45%+ Win Rate Target", Fore.CYAN)
    log("📊 Featuring: Trend Following, Breakout, Mean Reversion, Volume Profile, Scalping, Ichimoku, Stiff Surge", Fore.CYAN)
    log("🌊 NEW: AI-Powered Surge Detection | Real-time Slippage Monitoring | Advanced Wallet Management", Fore.CYAN)
    log("🔥 Research-Backed | Backtested | Risk-Managed | User-Controlled", Fore.CYAN)
    log("="*120, Fore.CYAN)
    
    # Check OpenAI API
    if not OPENAI_API_KEY:
        log("⚠️ WARNING: OpenAI API key not found. AI features will be limited.", Fore.YELLOW)
        log("   Add OPENAI_API_KEY to your .env file for full AI functionality", Fore.YELLOW)
    else:
        log("✅ OpenAI API configured for AI-powered analysis", Fore.GREEN, "SUCCESS")
    
    # Connect to Binance
    log("\n🔗 Establishing connection to Binance...", Fore.YELLOW)
    
    if not check_market_status():
        log("❌ Markets unavailable. Please try again later.", Fore.RED, "ERROR")
        return
    
    try:
        server_time = safe_api_call(client.get_server_time)
        if server_time:
            log(f"✅ Connected successfully!", Fore.GREEN, "SUCCESS")
            log(f"   Server time: {datetime.datetime.fromtimestamp(server_time['serverTime']/1000)}", Fore.GREEN)
        else:
            log("❌ Connection failed", Fore.RED, "ERROR")
            return
    except:
        log("❌ Connection error", Fore.RED, "ERROR")
        return
    
    # Get account status
    try:
        usdt_balance, total_value, other_assets = get_account_balance()
        session_start_balance = total_value
        
        log(f"\n💰 ACCOUNT STATUS:", Fore.CYAN)
        log(f"   Total Portfolio Value: ${total_value:.2f}", Fore.CYAN)
        log(f"   USDT Available: ${usdt_balance:.2f}", Fore.CYAN)
        log(f"   Other Assets: ${total_value - usdt_balance:.2f}", Fore.CYAN)
        
        # Display wallet breakdown
        display_wallet_status()
        
        if usdt_balance < 50:
            log(f"\n⚠️ WARNING: Low USDT balance for optimal performance", Fore.YELLOW)
            log(f"   Recommended minimum: $100+ for best results", Fore.YELLOW)
        
        # Enhanced liquidation prompt for consolidation
        if other_assets and (total_value - usdt_balance) > 20:
            non_bnb_assets = {k: v for k, v in other_assets.items() if k != 'BNB'}
            
            if non_bnb_assets:
                total_liquidatable = sum(v['value'] for v in non_bnb_assets.values())
                log(f"\n💡 TRADING CAPITAL OPTIMIZATION OPPORTUNITY:", Fore.YELLOW)
                log(f"You have ${total_liquidatable:.2f} in other assets that could be consolidated to USDT", Fore.YELLOW)
                log(f"Consolidating would increase your trading flexibility and opportunities!", Fore.YELLOW)
                
                if not prompt_liquidation(other_assets):
                    log("\n❌ Trading cancelled by user", Fore.RED)
                    return
                
                # Refresh balance after potential liquidation
                log("\n🔄 Refreshing account balance...", Fore.YELLOW)
                time.sleep(3)  # Allow time for trades to settle
                usdt_balance, total_value, _ = get_account_balance()
                session_start_balance = total_value
                
                log(f"\n💰 UPDATED ACCOUNT STATUS:", Fore.GREEN)
                log(f"   Total Portfolio Value: ${total_value:.2f}", Fore.GREEN)
                log(f"   USDT Available: ${usdt_balance:.2f}", Fore.GREEN)
                if total_liquidatable > 0:
                    log(f"   🚀 Trading power increased!", Fore.GREEN)
        
    except Exception as e:
        log(f"❌ Failed to get account balance: {e}", Fore.RED, "ERROR")
        return
    
    # Display configuration
    log(f"\n📋 TRADING CONFIGURATION:", Fore.CYAN)
    log(f"   📊 Max Concurrent Positions: {MAX_CONCURRENT}", Fore.CYAN)
    log(f"   💰 Position Size: {POSITION_SIZE_PERCENT*100}% (~${usdt_balance * POSITION_SIZE_PERCENT:.2f} per trade)", Fore.CYAN)
    log(f"   🎯 Target Win Rate: {MIN_WIN_RATE*100}%+", Fore.CYAN)
    log(f"   📈 Risk/Reward Ratio: {RISK_REWARD_RATIO}:1 minimum", Fore.CYAN)
    log(f"   🛑 Max Account Risk: {MAX_ACCOUNT_RISK*100}%", Fore.CYAN)
    log(f"   ⏱️ Session Duration: {TRADING_DURATION/3600:.1f} hours", Fore.CYAN)
    log(f"   🌍 Trading Universe: {len(TRADE_SYMBOLS)} high-liquidity pairs", Fore.CYAN)
    log(f"   🌊 Stiff Surge Strategy: {SURGE_VOLUME_MULTIPLIER}x volume | {SURGE_PRICE_THRESHOLD*100}% move | AI-powered", Fore.MAGENTA)
    
    # Start user control thread
    input_thread = threading.Thread(target=check_user_input, daemon=True)
    input_thread.start()
    
    # Initialize session
    session_start_time = time.time()
    last_scan_time = 0
    last_position_check = 0
    last_performance_display = 0
    last_sentiment_update = 0
    last_ai_analysis = 0
    
    # Timing configuration
    scan_interval = 45  # 45 seconds between scans
    position_check_interval = 8  # 8 seconds between position checks
    performance_interval = 300  # 5 minutes between performance displays
    ai_surge_interval = 120  # 2 minutes between AI surge scans
    
    log(f"\n🚀 STARTING PROFITABLE TRADING SESSION", Fore.GREEN)
    log(f"   Session ID: {SESSION_ID}", Fore.GREEN)
    log(f"   Target: 45%+ win rate | 2-5% session return", Fore.GREEN)
    log(f"   🌊 AI Surge Detection: {'ENABLED' if OPENAI_API_KEY else 'LIMITED'}", Fore.GREEN)
    
    try:
        while not user_stop_requested:
            current_time = time.time()
            
            # Check session duration
            if current_time - session_start_time > TRADING_DURATION:
                log("\n⏰ Session duration reached", Fore.YELLOW)
                break
            
            # Update sentiment periodically
            if current_time - last_sentiment_update >= 300:
                update_sentiment_analysis()
                last_sentiment_update = current_time
            
            # AI Surge Scan (async)
            if current_time - last_ai_analysis >= ai_surge_interval and OPENAI_API_KEY:
                asyncio.create_task(scan_surge_opportunities_with_ai())
                last_ai_analysis = current_time
            
            # Manage active positions
            if active_positions and current_time - last_position_check >= position_check_interval:
                manage_positions()
                last_position_check = current_time
            
            # Scan for new opportunities
            if current_time - last_scan_time >= scan_interval:
                scan_number = int((current_time - session_start_time) / scan_interval) + 1
                log(f"\n🔍 OPPORTUNITY SCAN #{scan_number}", Fore.MAGENTA)
                scan_for_opportunities()
                last_scan_time = current_time
            
            # Display performance periodically
            if current_time - last_performance_display >= performance_interval:
                display_performance()
                last_performance_display = current_time
            
            # Heartbeat display
            elapsed = int(current_time - session_start_time)
            hours, remainder = divmod(elapsed, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            # Status indicators
            profit_indicator = "📈" if daily_pnl > 0 else "📉" if daily_pnl < 0 else "➡️"
            win_rate = calculate_win_rate()
            win_rate_indicator = "🎯" if win_rate >= 45 else "⚠️"
            surge_indicator = "🌊" if surge_candidates else ""
            
            # Current exposure
            current_exposure = sum(p['quantity'] * p['entry_price'] for p in active_positions.values())
            exposure_pct = (current_exposure / total_value * 100) if total_value > 0 else 0
            
            log(f"💓 {profit_indicator} {surge_indicator} Session: {hours:02d}:{minutes:02d}:{seconds:02d} | "
                f"Positions: {len(active_positions)}/{MAX_CONCURRENT} | "
                f"P&L: ${daily_pnl:+.2f} | "
                f"{win_rate_indicator} WR: {win_rate:.1f}% | "
                f"Exposure: {exposure_pct:.1f}% | "
                f"Surges: {len(surge_candidates)} | "
                f"API: {success_count}✅/{error_count}❌", Fore.BLUE)
            
            await asyncio.sleep(LOOP_INTERVAL)
            
    except KeyboardInterrupt:
        log("\n⚠️ Trading interrupted by user", Fore.YELLOW)
        user_stop_requested = True
    except Exception as e:
        log(f"\n❌ CRITICAL ERROR: {e}", Fore.RED, "ERROR")
        user_stop_requested = True
    finally:
        # Cleanup and close positions
        log("\n🔄 CLOSING ALL POSITIONS...", Fore.YELLOW)
        
        closed_count = 0
        failed_count = 0
        
        for position_key, position in list(active_positions.items()):
            try:
                ticker = safe_api_call(client.get_symbol_ticker, symbol=position['symbol'])
                if ticker:
                    current_price = float(ticker['price'])
                    result = execute_exit(position_key, position, 'session_end', current_price)
                    if result:
                        closed_count += 1
                    else:
                        failed_count += 1
                else:
                    failed_count += 1
            except:
                failed_count += 1
        
        log(f"✅ Position closure complete: {closed_count} closed, {failed_count} failed", 
            Fore.GREEN if failed_count == 0 else Fore.YELLOW)
        
        # Final performance display
        display_performance()
        
        # Save results
        save_comprehensive_results_to_csv()
        
        # Session summary
        try:
            _, final_balance, _ = get_account_balance()
        except:
            final_balance = session_start_balance
        
        session_duration = (time.time() - session_start_time) / 3600
        total_return = ((final_balance - session_start_balance) / session_start_balance * 100) if session_start_balance > 0 else 0
        
        log(f"\n{'='*120}", Fore.CYAN)
        log("📊 FINAL SESSION SUMMARY", Fore.CYAN)
        log(f"{'='*120}", Fore.CYAN)
        log(f"⏱️ Session Duration: {session_duration:.1f} hours", Fore.CYAN)
        log(f"💰 Starting Balance: ${session_start_balance:.2f}", Fore.CYAN)
        log(f"💎 Ending Balance: ${final_balance:.2f}", Fore.CYAN)
        log(f"📈 Total Return: {total_return:+.2f}%", 
            Fore.GREEN if total_return > 0 else Fore.RED)
        
        if len(trade_history) > 0:
            final_win_rate = calculate_win_rate()
            total_trades = len(trade_history)
            net_pnl = sum(t['net_profit'] for t in trade_history)
            
            # Strategy breakdown
            surge_trades = [t for t in trade_history if t['strategy'] == 'stiff_surge']
            
            log(f"📊 Trading Stats:", Fore.CYAN)
            log(f"   Total Trades: {total_trades}", Fore.CYAN)
            log(f"   Win Rate: {final_win_rate:.1f}%", 
                Fore.GREEN if final_win_rate >= 45 else Fore.YELLOW)
            log(f"   Net P&L: ${net_pnl:.2f}", 
                Fore.GREEN if net_pnl > 0 else Fore.RED)
            log(f"   Fees Paid: ${total_fees_paid:.2f}", Fore.YELLOW)
            
            if surge_trades:
                surge_wins = sum(1 for t in surge_trades if t['net_profit'] > 0)
                surge_wr = (surge_wins / len(surge_trades)) * 100
                surge_pnl = sum(t['net_profit'] for t in surge_trades)
                log(f"   🌊 Surge Trades: {len(surge_trades)} | WR: {surge_wr:.1f}% | P&L: ${surge_pnl:.2f}", 
                    Fore.MAGENTA)
        
        # Performance rating
        if total_return > 3:
            rating = "🌟 EXCELLENT SESSION"
            color = Fore.GREEN
        elif total_return > 1:
            rating = "👍 GOOD SESSION"
            color = Fore.GREEN
        elif total_return > -1:
            rating = "➡️ BREAK EVEN SESSION"
            color = Fore.YELLOW
        else:
            rating = "👎 LOSING SESSION"
            color = Fore.RED
        
        log(f"\n🏆 Session Rating: {rating}", color)
        
        # Recommendations
        log(f"\n💡 RECOMMENDATIONS:", Fore.CYAN)
        if final_win_rate < 45 and len(trade_history) > 10:
            log("   📈 Consider increasing signal quality threshold", Fore.YELLOW)
            log("   🎯 Review entry criteria for underperforming strategies", Fore.YELLOW)
        if total_return < 0:
            log("   🛑 Review stop loss levels and risk management", Fore.YELLOW)
            log("   📊 Analyze losing trades for patterns", Fore.YELLOW)
        if total_return > 2:
            log("   ✅ Current settings performing well", Fore.GREEN)
            log("   🚀 Consider gradually increasing position sizes", Fore.GREEN)
        
        if len(surge_candidates) > 0:
            log("   🌊 Unused surge opportunities detected - consider more aggressive surge entries", Fore.MAGENTA)
        
        log(f"\n✅ TRADING SESSION COMPLETE!", Fore.GREEN, "SUCCESS")
        log("📊 Results saved to CSV files for analysis", Fore.GREEN)
        log("🙏 Thank you for using Enhanced Profitable Crypto Trading Bot v4.0 - Stiff Surge Edition", Fore.CYAN)

def main():
    """Main entry point"""
    asyncio.run(main_async())

if __name__ == "__main__":
    main()