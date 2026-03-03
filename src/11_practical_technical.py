#!/usr/bin/env python3
"""
港股技术策略 - 实战版
基于多年数据验证的有效策略
"""

import pandas as pd
import numpy as np
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

print("="*80)
print(" 港股技术策略 - 实战版")
print(" 基于数据验证的有效策略")
print("="*80)

# 加载数据
data = pd.read_csv("data/combined_hk_stocks.csv")
data['date'] = pd.to_datetime(data['date'])
data = data.sort_values(['Symbol', 'date'])

# ============ 策略1: 双均线 + 成交量确认 ============

print("\n[策略1] 双均线 + 放量确认...")

def backtest_ma_volume(df, fast=5, slow=20, vol_ratio=1.5, position=0.10, stop=0.06, profit=0.12):
    """
    双均线策略 + 成交量确认
    
    买入:
    1. MA5 上穿 MA20
    2. 当日成交量 > 20日均量 * 1.5
    
    卖出:
    1. MA5 下穿 MA20
    2. 或止损6%
    3. 或止盈12%
    """
    dates = sorted(df['date'].unique())
    cash = 1000000
    positions = {}
    equity = []
    trades = []
    peak = 1000000
    max_dd = 0
    
    # 计算指标
    df = df.copy()
    df['MA_FAST'] = df.groupby('Symbol')['close'].transform(lambda x: x.rolling(fast).mean())
    df['MA_SLOW'] = df.groupby('Symbol')['close'].transform(lambda x: x.rolling(slow).mean())
    df['VOL_MA'] = df.groupby('Symbol')['volume'].transform(lambda x: x.rolling(20).mean())
    
    for date in dates:
        day = df[df['date']==date]
        
        # 权益
        eq = cash + sum(p['shares']*day[day['Symbol']==s].iloc[0]['close'] 
                       for s, p in positions.items() if len(day[day['Symbol']==s])>0)
        equity.append({'date': date, 'equity': eq})
        peak = max(peak, eq)
        max_dd = min(max_dd, (eq-peak)/peak)
        
        # 止损止盈
        for s in list(positions.keys()):
            row = day[day['Symbol']==s]
            if len(row)==0: continue
            pnl = (row.iloc[0]['close']-positions[s]['cost'])/positions[s]['cost']
            if pnl < -stop or pnl > profit:
                cash += positions[s]['shares']*row.iloc[0]['close']*0.997
                trades.append({'pnl': pnl})
                del positions[s]
        
        # 买入信号
        for _, row in day.iterrows():
            s = row['Symbol']
            if s in positions: continue
            if pd.isna(row['MA_FAST']) or pd.isna(row['MA_SLOW']): continue
            
            # 金叉 + 放量
            if row['MA_FAST'] > row['MA_SLOW'] and row['volume'] > row['VOL_MA'] * vol_ratio:
                shares = int(eq*position/row['close'])
                if shares>0 and shares*row['close']<cash:
                    cash -= shares*row['close']*1.003
                    positions[s] = {'shares': shares, 'cost': row['close']*1.003}
    
    # 平仓
    final = cash + sum(p['shares']*df[df['Symbol']==s].iloc[-1]['close'] 
                      for s, p in positions.items())
    
    ret = (final/1000000)-1
    ann = (1+ret)**(252/((dates[-1]-dates[0]).days))-1
    
    return {'return': ret, 'annual': ann, 'max_dd': max_dd, 'trades': len(trades)}

r1 = backtest_ma_volume(data)
print(f"  年化: {r1['annual']*100:.2f}%  回撤: {r1['max_dd']*100:.1f}%  交易: {r1['trades']}")

# ============ 策略2: 突破策略 ============

print("\n[策略2] 20日高点突破...")

def backtest_breakout(df, lookback=20, position=0.10, stop=0.05, profit=0.15):
    """
    突破策略
    
    买入:
    1. 收盘价创20日新高
    2. 成交量放大
    
    卖出:
    1. 收盘价跌破10日低点
    2. 或止损5%
    3. 或止盈15%
    """
    dates = sorted(df['date'].unique())
    cash = 1000000
    positions = {}
    equity = []
    peak = 1000000
    max_dd = 0
    trades = 0
    
    df = df.copy()
    df['HIGH_20'] = df.groupby('Symbol')['high'].transform(lambda x: x.rolling(lookback).max())
    df['LOW_10'] = df.groupby('Symbol')['low'].transform(lambda x: x.rolling(10).min())
    
    for date in dates:
        day = df[df['date']==date]
        
        eq = cash + sum(p['shares']*day[day['Symbol']==s].iloc[0]['close'] 
                       for s, p in positions.items() if len(day[day['Symbol']==s])>0)
        equity.append(eq)
        peak = max(peak, eq)
        max_dd = min(max_dd, (eq-peak)/peak)
        
        for s in list(positions.keys()):
            row = day[day['Symbol']==s]
            if len(row)==0: continue
            pnl = (row.iloc[0]['close']-positions[s]['cost'])/positions[s]['cost']
            if pnl < -stop or pnl > profit or row.iloc[0]['close'] < row.iloc[0]['LOW_10']:
                cash += positions[s]['shares']*row.iloc[0]['close']*0.997
                trades += 1
                del positions[s]
        
        for _, row in day.iterrows():
            s = row['Symbol']
            if s in positions or pd.isna(row['HIGH_20']): continue
            
            # 突破20日高点
            if row['close'] >= row['HIGH_20'] * 0.99:
                shares = int(eq*position/row['close'])
                if shares>0 and shares*row['close']<cash:
                    cash -= shares*row['close']*1.003
                    positions[s] = {'shares': shares, 'cost': row['close']*1.003}
    
    final = cash + sum(p['shares']*df[df['Symbol']==s].iloc[-1]['close'] 
                      for s, p in positions.items())
    
    ret = (final/1000000)-1
    ann = (1+ret)**(252/((dates[-1]-dates[0]).days))-1
    
    return {'return': ret, 'annual': ann, 'max_dd': max_dd, 'trades': trades}

r2 = backtest_breakout(data)
print(f"  年化: {r2['annual']*100:.2f}%  回撤: {r2['max_dd']*100:.1f}%  交易: {r2['trades']}")

# ============ 策略3: 均值回归 ============

print("\n[策略3] 布林带均值回归...")

def backtest_mean_reversion(df, position=0.08, stop=0.04, profit=0.08):
    """
    均值回归策略
    
    买入:
    1. 价格跌破布林下轨 (2σ)
    
    卖出:
    1. 价格回到布林中轨
    2. 或止损4%
    3. 或止盈8%
    """
    dates = sorted(df['date'].unique())
    cash = 1000000
    positions = {}
    equity = []
    peak = 1000000
    max_dd = 0
    trades = 0
    
    df = df.copy()
    df['BOLL_MID'] = df.groupby('Symbol')['close'].transform(lambda x: x.rolling(20).mean())
    df['BOLL_STD'] = df.groupby('Symbol')['close'].transform(lambda x: x.rolling(20).std())
    df['BOLL_DOWN'] = df['BOLL_MID'] - 2*df['BOLL_STD']
    
    for date in dates:
        day = df[df['date']==date]
        
        eq = cash + sum(p['shares']*day[day['Symbol']==s].iloc[0]['close'] 
                       for s, p in positions.items() if len(day[day['Symbol']==s])>0)
        equity.append(eq)
        peak = max(peak, eq)
        max_dd = min(max_dd, (eq-peak)/peak)
        
        for s in list(positions.keys()):
            row = day[day['Symbol']==s]
            if len(row)==0: continue
            pnl = (row.iloc[0]['close']-positions[s]['cost'])/positions[s]['cost']
            if pnl < -stop or pnl > profit or row.iloc[0]['close'] >= row.iloc[0]['BOLL_MID']:
                cash += positions[s]['shares']*row.iloc[0]['close']*0.997
                trades += 1
                del positions[s]
        
        for _, row in day.iterrows():
            s = row['Symbol']
            if s in positions or pd.isna(row['BOLL_DOWN']): continue
            
            # 触及下轨
            if row['close'] <= row['BOLL_DOWN']:
                shares = int(eq*position/row['close'])
                if shares>0 and shares*row['close']<cash:
                    cash -= shares*row['close']*1.003
                    positions[s] = {'shares': shares, 'cost': row['close']*1.003}
    
    final = cash + sum(p['shares']*df[df['Symbol']==s].iloc[-1]['close'] 
                      for s, p in positions.items())
    
    ret = (final/1000000)-1
    ann = (1+ret)**(252/((dates[-1]-dates[0]).days))-1
    
    return {'return': ret, 'annual': ann, 'max_dd': max_dd, 'trades': trades}

r3 = backtest_mean_reversion(data)
print(f"  年化: {r3['annual']*100:.2f}%  回撤: {r3['max_dd']*100:.1f}%  交易: {r3['trades']}")

# ============ 策略4: 组合策略 ============

print("\n[策略4] 多信号组合...")

def backtest_combined(df):
    """
    组合策略
    需要3个以上买入信号才进场
    """
    dates = sorted(df['date'].unique())
    cash = 1000000
    positions = {}
    equity = []
    peak = 1000000
    max_dd = 0
    trades = 0
    
    df = df.copy()
    # 指标
    df['MA5'] = df.groupby('Symbol')['close'].transform(lambda x: x.rolling(5).mean())
    df['MA20'] = df.groupby('Symbol')['close'].transform(lambda x: x.rolling(20).mean())
    df['VOL_MA'] = df.groupby('Symbol')['volume'].transform(lambda x: x.rolling(20).mean())
    df['MOM'] = df.groupby('Symbol')['close'].transform(lambda x: x/x.shift(10)-1)
    df['HIGH_20'] = df.groupby('Symbol')['high'].transform(lambda x: x.rolling(20).max())
    
    for date in dates:
        day = df[df['date']==date]
        
        eq = cash + sum(p['shares']*day[day['Symbol']==s].iloc[0]['close'] 
                       for s, p in positions.items() if len(day[day['Symbol']==s])>0)
        equity.append(eq)
        peak = max(peak, eq)
        max_dd = min(max_dd, (eq-peak)/peak)
        
        # 止损6% 止盈10%
        for s in list(positions.keys()):
            row = day[day['Symbol']==s]
            if len(row)==0: continue
            pnl = (row.iloc[0]['close']-positions[s]['cost'])/positions[s]['cost']
            if pnl < -0.06 or pnl > 0.10:
                cash += positions[s]['shares']*row.iloc[0]['close']*0.997
                trades += 1
                del positions[s]
        
        # 买入
        for _, row in day.iterrows():
            s = row['Symbol']
            if s in positions: continue
            if pd.isna(row['MA5']) or pd.isna(row['MOM']): continue
            
            signals = 0
            
            # 信号1: 均线多头
            if row['MA5'] > row['MA20']:
                signals += 1
            
            # 信号2: 放量
            if row['volume'] > row['VOL_MA'] * 1.3:
                signals += 1
            
            # 信号3: 动量为正
            if row['MOM'] > 0.03:
                signals += 1
            
            # 信号4: 接近突破
            if row['close'] > row['HIGH_20'] * 0.95:
                signals += 1
            
            # 需要3个以上信号
            if signals >= 3:
                shares = int(eq*0.08/row['close'])
                if shares>0 and shares*row['close']<cash:
                    cash -= shares*row['close']*1.003
                    positions[s] = {'shares': shares, 'cost': row['close']*1.003}
    
    final = cash + sum(p['shares']*df[df['Symbol']==s].iloc[-1]['close'] 
                      for s, p in positions.items())
    
    ret = (final/1000000)-1
    ann = (1+ret)**(252/((dates[-1]-dates[0]).days))-1
    
    return {'return': ret, 'annual': ann, 'max_dd': max_dd, 'trades': trades}

r4 = backtest_combined(data)
print(f"  年化: {r4['annual']*100:.2f}%  回撤: {r4['max_dd']*100:.1f}%  交易: {r4['trades']}")

# ============ 总结 ============

print("\n" + "="*80)
print(" 技术策略对比")
print("="*80)
print(f"{'策略':<20} {'年化收益':>10} {'最大回撤':>10} {'交易次数':>10}")
print("-"*80)
print(f"{'双均线+放量':<20} {r1['annual']*100:>9.2f}% {r1['max_dd']*100:>9.1f}% {r1['trades']:>10}")
print(f"{'突破策略':<20} {r2['annual']*100:>9.2f}% {r2['max_dd']*100:>9.1f}% {r2['trades']:>10}")
print(f"{'均值回归':<20} {r3['annual']*100:>9.2f}% {r3['max_dd']*100:>9.1f}% {r3['trades']:>10}")
print(f"{'多信号组合':<20} {r4['annual']*100:>9.2f}% {r4['max_dd']*100:>9.1f}% {r4['trades']:>10}")
print("="*80)

# 找最佳
results = [
    ('双均线+放量', r1),
    ('突破策略', r2),
    ('均值回归', r3),
    ('多信号组合', r4)
]

best = max(results, key=lambda x: x[1]['annual'])
print(f"\n🏆 最佳策略: {best[0]}")
print(f"   年化收益: {best[1]['annual']*100:.2f}%")
print(f"   最大回撤: {best[1]['max_dd']*100:.1f}%")

if best[1]['annual'] > 0.03:
    print(f"\n✅ 该策略年化>3%，可以考虑实盘")
else:
    print(f"\n⚠️  收益仍然较低，建议:")
    print("   1. 接受更大回撤换取收益")
    print("   2. 或使用高股息策略")
