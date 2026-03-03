#!/usr/bin/env python3
"""
港股技术策略 - 进阶版
组合多个技术指标，提高胜率
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
import warnings
warnings.filterwarnings('ignore')

print("="*80)
print(" 港股技术策略 - 进阶版")
print("="*80)

# 加载数据
data = pd.read_csv("data/combined_hk_stocks.csv")
data['date'] = pd.to_datetime(data['date'])
data = data.sort_values(['Symbol', 'date'])

# ============ 高级指标 ============

print("\n计算高级指标...")

# 1. MACD
def calc_macd_series(series):
    ema12 = series.ewm(span=12).mean()
    ema26 = series.ewm(span=26).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9).mean()
    hist = macd - signal
    return macd, signal, hist

data['MACD'] = data.groupby('Symbol')['close'].transform(lambda x: calc_macd_series(x)[0])
data['MACD_SIGNAL'] = data.groupby('Symbol')['close'].transform(lambda x: calc_macd_series(x)[1])
data['MACD_HIST'] = data.groupby('Symbol')['close'].transform(lambda x: calc_macd_series(x)[2])

# 2. KDJ
def calc_kdj_series(close, high, low, n=9, m1=3, m2=3):
    low_n = low.rolling(n).min()
    high_n = high.rolling(n).max()
    rsv = (close - low_n) / (high_n - low_n) * 100
    
    k = rsv.ewm(alpha=1/m1).mean()
    d = k.ewm(alpha=1/m2).mean()
    j = 3 * k - 2 * d
    
    return k, d, j

# 按 group 计算
for symbol in data['Symbol'].unique():
    mask = data['Symbol'] == symbol
    k, d, j = calc_kdj_series(
        data.loc[mask, 'close'],
        data.loc[mask, 'high'],
        data.loc[mask, 'low']
    )
    data.loc[mask, 'K'] = k
    data.loc[mask, 'D'] = d
    data.loc[mask, 'J'] = j

# 3. BOLL
data['BOLL_MID'] = data.groupby('Symbol')['close'].transform(lambda x: x.rolling(20).mean())
data['BOLL_STD'] = data.groupby('Symbol')['close'].transform(lambda x: x.rolling(20).std())
data['BOLL_UP'] = data['BOLL_MID'] + 2 * data['BOLL_STD']
data['BOLL_DOWN'] = data['BOLL_MID'] - 2 * data['BOLL_STD']

# 4. ATR
def calc_atr(df, n=14):
    tr1 = df['high'] - df['low']
    tr2 = abs(df['high'] - df['close'].shift(1))
    tr3 = abs(df['low'] - df['close'].shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(n).mean()

data['ATR'] = data.groupby('Symbol', group_keys=False).apply(calc_atr)

# 5. OBV
data['OBV'] = data.groupby('Symbol', group_keys=False).apply(
    lambda x: (np.sign(x['close'].diff()) * x['volume']).fillna(0).cumsum()
)

# 6. 威廉指标
data['WR'] = data.groupby('Symbol', group_keys=False).apply(
    lambda x: (x['high'].rolling(14).max() - x['close']) / 
              (x['high'].rolling(14).max() - x['low'].rolling(14).min()) * -100
)

# 7. 动量
for period in [5, 10, 20]:
    data[f'MOM_{period}'] = data.groupby('Symbol')['close'].transform(
        lambda x: x / x.shift(period) - 1
    )

# 8. 均线系统
for w in [5, 10, 20, 50, 120]:
    data[f'MA{w}'] = data.groupby('Symbol')['close'].transform(lambda x: x.rolling(w).mean())

# 9. RSI
def rsi(s, w=14):
    d = s.diff()
    g = d.where(d>0,0).rolling(w).mean()
    l = (-d.where(d<0,0)).rolling(w).mean()
    return 100-(100/(1+g/l))

data['RSI'] = data.groupby('Symbol')['close'].transform(rsi)

# 10. 成交量指标
data['VOL_RATIO'] = data.groupby('Symbol')['volume'].transform(
    lambda x: x / x.rolling(20).mean()
)
data['AMOUNT'] = data['close'] * data['volume']

print("完成: MACD/KDJ/BOLL/ATR/OBV/WR/动量/均线/RSI/量比")

# ============ 信号生成 ============

print("\n生成交易信号...")

def generate_signals(df):
    """
    综合信号生成
    
    买入条件（必须全部满足）：
    1. MACD金叉（MACD > SIGNAL）
    2. KDJ超卖回升（J < 20 昨天到今天 > 20）
    3. 价格触及布林下轨（close <= BOLL_DOWN）
    4. RSI < 40（不超买）
    5. MA5 > MA20（短期趋势向上）
    6. 放量（VOL_RATIO > 1.5）
    
    卖出条件（满足任一）：
    1. MACD死叉
    2. KDJ超买（J > 80）
    3. 触及布林上轨
    4. RSI > 70
    """
    signals = []
    
    for i in range(1, len(df)):
        prev = df.iloc[i-1]
        curr = df.iloc[i]
        
        # 跳过NaN
        if pd.isna(curr['MACD']) or pd.isna(curr['K']) or pd.isna(curr['RSI']):
            continue
        
        # 买入信号
        buy_score = 0
        
        # 1. MACD金叉
        if curr['MACD'] > curr['MACD_SIGNAL'] and prev['MACD'] <= prev['MACD_SIGNAL']:
            buy_score += 2
        
        # 2. KDJ超卖回升
        if curr['J'] > 20 and prev['J'] <= 20:
            buy_score += 2
        
        # 3. 布林下轨
        if curr['close'] <= curr['BOLL_DOWN'] * 1.02:
            buy_score += 1
        
        # 4. RSI不超买
        if curr['RSI'] < 40:
            buy_score += 1
        
        # 5. 均线多头
        if curr['MA5'] > curr['MA20']:
            buy_score += 1
        
        # 6. 放量
        if curr['VOL_RATIO'] > 1.5:
            buy_score += 1
        
        # 买入
        if buy_score >= 5:
            signals.append({
                'date': curr['date'],
                'symbol': curr['Symbol'],
                'action': 'BUY',
                'price': curr['close'],
                'score': buy_score
            })
        
        # 卖出信号
        sell_score = 0
        
        # 1. MACD死叉
        if curr['MACD'] < curr['MACD_SIGNAL'] and prev['MACD'] >= prev['MACD_SIGNAL']:
            sell_score += 2
        
        # 2. KDJ超买
        if curr['J'] > 80:
            sell_score += 2
        
        # 3. 布林上轨
        if curr['close'] >= curr['BOLL_UP'] * 0.98:
            sell_score += 1
        
        # 4. RSI超买
        if curr['RSI'] > 70:
            sell_score += 1
        
        # 卖出
        if sell_score >= 3:
            signals.append({
                'date': curr['date'],
                'symbol': curr['Symbol'],
                'action': 'SELL',
                'price': curr['close'],
                'score': sell_score
            })
    
    return pd.DataFrame(signals)

# 生成所有股票的信号
all_signals = []
for symbol in data['Symbol'].unique():
    df = data[data['Symbol'] == symbol].reset_index(drop=True)
    sig = generate_signals(df)
    all_signals.append(sig)

signals_df = pd.concat(all_signals, ignore_index=True)
print(f"生成信号: {len(signals_df)} 条")
print(f"  买入: {len(signals_df[signals_df['action']=='BUY'])}")
print(f"  卖出: {len(signals_df[signals_df['action']=='SELL'])}")

# ============ 回测 ============

print("\n开始回测...")

def backtest_advanced(data, signals, initial_capital=1000000, stop_loss=0.05, take_profit=0.10):
    """高级回测"""
    dates = sorted(data['date'].unique())
    
    cash = initial_capital
    positions = {}
    equity_curve = []
    trades = []
    peak = initial_capital
    max_dd = 0
    
    for date in dates:
        day_data = data[data['date'] == date]
        day_signals = signals[signals['date'] == date]
        
        # 计算权益
        equity = cash
        for s, p in positions.items():
            row = day_data[day_data['Symbol'] == s]
            if len(row) > 0:
                equity += p['shares'] * row.iloc[0]['close']
        
        equity_curve.append({'date': date, 'equity': equity})
        peak = max(peak, equity)
        max_dd = min(max_dd, (equity - peak) / peak)
        
        # 检查持仓止损止盈
        for s in list(positions.keys()):
            p = positions[s]
            row = day_data[day_data['Symbol'] == s]
            if len(row) == 0:
                continue
            
            price = row.iloc[0]['close']
            pnl = (price - p['cost']) / p['cost']
            
            # 止损
            if pnl < -stop_loss:
                cash += p['shares'] * price * 0.997
                trades.append({'action': 'SELL', 'reason': 'stop_loss', 'pnl': pnl})
                del positions[s]
                continue
            
            # 止盈
            if pnl > take_profit:
                cash += p['shares'] * price * 0.997
                trades.append({'action': 'SELL', 'reason': 'take_profit', 'pnl': pnl})
                del positions[s]
        
        # 处理信号
        for _, sig in day_signals.iterrows():
            symbol = sig['symbol']
            
            if sig['action'] == 'BUY' and symbol not in positions:
                # 买入
                position_size = equity * 0.08  # 8%仓位
                shares = int(position_size / sig['price'])
                
                if shares > 0 and shares * sig['price'] < cash:
                    cost = shares * sig['price'] * 1.003
                    cash -= cost
                    positions[symbol] = {
                        'shares': shares,
                        'cost': sig['price'] * 1.003,
                        'score': sig['score']
                    }
                    trades.append({'action': 'BUY', 'symbol': symbol, 'score': sig['score']})
            
            elif sig['action'] == 'SELL' and symbol in positions:
                # 卖出
                p = positions[symbol]
                row = day_data[day_data['Symbol'] == symbol]
                if len(row) > 0:
                    price = row.iloc[0]['close']
                    pnl = (price - p['cost']) / p['cost']
                    cash += p['shares'] * price * 0.997
                    trades.append({'action': 'SELL', 'symbol': symbol, 'reason': 'signal', 'pnl': pnl})
                    del positions[symbol]
    
    # 平仓
    final = cash
    for s, p in positions.items():
        last = data[data['Symbol'] == s].iloc[-1]['close']
        final += p['shares'] * last
    
    # 计算指标
    eq_df = pd.DataFrame(equity_curve)
    eq_df['returns'] = eq_df['equity'].pct_change()
    
    total_ret = (final / initial_capital) - 1
    days = (dates[-1] - dates[0]).days
    ann_ret = (1 + total_ret) ** (252 / days) - 1
    sharpe = np.sqrt(252) * eq_df['returns'].mean() / eq_df['returns'].std() if eq_df['returns'].std() > 0 else 0
    
    wins = sum(1 for t in trades if t.get('pnl', 0) > 0)
    losses = sum(1 for t in trades if t.get('pnl', 0) < 0)
    win_rate = wins / (wins + losses) if (wins + losses) > 0 else 0
    
    return {
        'total_return': total_ret,
        'annual_return': ann_ret,
        'max_drawdown': max_dd,
        'sharpe_ratio': sharpe,
        'win_rate': win_rate,
        'total_trades': len([t for t in trades if t['action'] == 'BUY']),
        'final_equity': final
    }

# 回测
result = backtest_advanced(data, signals_df)

print("\n" + "="*80)
print(" 高级技术策略回测结果")
print("="*80)
print(f"初始资金:     1,000,000 HKD")
print(f"最终资金:     {result['final_equity']:,.0f} HKD")
print(f"累计收益:     {result['total_return']*100:.2f}%")
print(f"年化收益:     {result['annual_return']*100:.2f}%")
print(f"最大回撤:     {result['max_drawdown']*100:.2f}%")
print(f"夏普比率:     {result['sharpe_ratio']:.3f}")
print(f"胜率:         {result['win_rate']*100:.1f}%")
print(f"交易次数:     {result['total_trades']}")
print("="*80)

# 保存信号
signals_df.to_csv('results/advanced_signals.csv', index=False)
print("\n信号已保存: results/advanced_signals.csv")

# 分析最佳信号
buy_signals = signals_df[signals_df['action'] == 'BUY'].sort_values('score', ascending=False)
print(f"\n最佳买入信号 (score >= 7): {len(buy_signals[buy_signals['score']>=7])}")
print(buy_signals.head(10).to_string(index=False))
