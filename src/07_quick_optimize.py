#!/usr/bin/env python3
"""
快速参数优化 - 只测几组关键参数
"""

import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')


def quick_backtest(data, mom, pos, stop, profit):
    """快速回测"""
    df = data.copy()
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values(['Symbol', 'date'])
    
    # 指标
    df['MOM'] = df.groupby('Symbol')['close'].transform(lambda x: x/x.shift(20)-1)
    df['MA5'] = df.groupby('Symbol')['close'].transform(lambda x: x.rolling(5).mean())
    df['MA20'] = df.groupby('Symbol')['close'].transform(lambda x: x.rolling(20).mean())
    
    def rsi(s):
        d = s.diff()
        g = d.where(d>0,0).rolling(14).mean()
        l = (-d.where(d<0,0)).rolling(14).mean()
        return 100-(100/(1+g/l))
    df['RSI'] = df.groupby('Symbol')['close'].transform(rsi)
    
    # 回测
    dates = sorted(df['date'].unique())
    cash, equity = 1000000, 1000000
    positions = {}
    peak = 1000000
    max_dd = 0
    
    for date in dates:
        day = df[df['date']==date]
        
        # 权益
        equity = cash + sum(p['shares']*day[day['Symbol']==s].iloc[0]['close'] 
                          for s, p in positions.items() if len(day[day['Symbol']==s])>0)
        peak = max(peak, equity)
        max_dd = min(max_dd, (equity-peak)/peak)
        
        # 止损止盈
        for s in list(positions.keys()):
            row = day[day['Symbol']==s]
            if len(row)==0: continue
            pnl = (row.iloc[0]['close']-positions[s]['cost'])/positions[s]['cost']
            if pnl < -stop or pnl > profit:
                cash += positions[s]['shares']*row.iloc[0]['close']*0.997
                del positions[s]
        
        # 买入
        for _, row in day.iterrows():
            s = row['Symbol']
            if s in positions: continue
            if pd.isna(row['MOM']): continue
            
            if row['MOM']>mom and row['MA5']>row['MA20'] and 35<row['RSI']<65:
                shares = int(equity*pos/row['close'])
                if shares>0 and shares*row['close']<cash:
                    cash -= shares*row['close']*1.003
                    positions[s] = {'shares': shares, 'cost': row['close']*1.003}
    
    # 平仓
    for s, p in positions.items():
        last = df[df['Symbol']==s].iloc[-1]['close']
        cash += p['shares']*last
    
    ret = (cash/1000000)-1
    ann = (1+ret)**(252/((dates[-1]-dates[0]).days))-1
    
    return ann, max_dd


# 加载数据
print("加载数据...")
data = pd.read_csv("data/combined_hk_stocks.csv")

print("\n" + "="*60)
print(" 港股策略参数优化 (快速版)")
print("="*60)

# 测试几组参数
results = []

params = [
    # (动量, 仓位, 止损, 止盈)
    (0.03, 0.08, 0.05, 0.10),
    (0.03, 0.10, 0.06, 0.12),
    (0.04, 0.08, 0.05, 0.10),
    (0.04, 0.10, 0.06, 0.12),
    (0.04, 0.12, 0.08, 0.15),
    (0.05, 0.08, 0.05, 0.12),
    (0.05, 0.10, 0.06, 0.15),
    (0.05, 0.12, 0.08, 0.18),
    (0.06, 0.10, 0.06, 0.12),
    (0.06, 0.12, 0.08, 0.15),
]

for i, (mom, pos, stop, profit) in enumerate(params, 1):
    print(f"[{i}/10] 测试: 动量>{mom*100:.0f}% 仓位{pos*100:.0f}% 止损{stop*100:.0f}% 止盈{profit*100:.0f}%...")
    ann, max_dd = quick_backtest(data, mom, pos, stop, profit)
    
    results.append({
        'params': (mom, pos, stop, profit),
        'annual_return': ann,
        'max_drawdown': max_dd,
        'valid': max_dd > -0.15 and ann > 0.05
    })
    
    print(f"       年化: {ann*100:.2f}% 回撤: {max_dd*100:.2f}% {'✅' if max_dd>-0.15 and ann>0.05 else ''}")

# 筛选符合条件
valid = [r for r in results if r['valid']]
valid.sort(key=lambda x: x['annual_return'], reverse=True)

print("\n" + "="*80)
print(" 符合条件的参数组合 (回撤<15%, 年化>5%)")
print("="*80)

if valid:
    for i, r in enumerate(valid, 1):
        mom, pos, stop, profit = r['params']
        print(f"\n方案 {i}:")
        print(f"  年化收益: {r['annual_return']*100:.2f}%")
        print(f"  最大回撤: {r['max_drawdown']*100:.2f}%")
        print(f"  参数: 动量>{mom*100:.0f}% | 仓位{pos*100:.0f}% | 止损{stop*100:.0f}% | 止盈{profit*100:.0f}%")
else:
    print("\n未找到完全符合的参数，放宽条件重新筛选...")
    
    # 放宽到回撤<20%
    valid = [r for r in results if r['max_drawdown'] > -0.20 and r['annual_return'] > 0.05]
    valid.sort(key=lambda x: x['annual_return'], reverse=True)
    
    if valid:
        print("\n" + "="*80)
        print(" 放宽条件后的结果 (回撤<20%, 年化>5%)")
        print("="*80)
        
        for i, r in enumerate(valid[:5], 1):
            mom, pos, stop, profit = r['params']
            print(f"\n方案 {i}:")
            print(f"  年化收益: {r['annual_return']*100:.2f}%")
            print(f"  最大回撤: {r['max_drawdown']*100:.2f}%")
            print(f"  参数: 动量>{mom*100:.0f}% | 仓位{pos*100:.0f}% | 止损{stop*100:.0f}% | 止盈{profit*100:.0f}%")

# 最佳推荐
print("\n" + "="*80)
print(" 🏆 最终推荐")
print("="*80)

if valid:
    best = valid[0]
    mom, pos, stop, profit = best['params']
    print(f"\n年化收益: {best['annual_return']*100:.2f}%")
    print(f"最大回撤: {best['max_drawdown']*100:.2f}%")
    print(f"\n参数配置:")
    print(f"  • 动量阈值: {mom*100:.0f}%")
    print(f"  • 最大仓位: {pos*100:.0f}%")
    print(f"  • 止损线: {stop*100:.0f}%")
    print(f"  • 止盈线: {profit*100:.0f}%")
    print(f"\n交易规则:")
    print(f"  • 买入: 20日动量 > {mom*100:.0f}% 且 MA5 > MA20 且 RSI在35-65")
    print(f"  • 止损: 亏损 {stop*100:.0f}% 卖出")
    print(f"  • 止盈: 盈利 {profit*100:.0f}% 卖出")
    print(f"  • 仓位: 单只股票最多 {pos*100:.0f}% 资金")
else:
    print("\n❌ 无法找到合适的参数组合")
    print("建议:")
    print("  1. 放弃动量策略，改用高股息策略")
    print("  2. 或者接受更大的回撤 (20-25%)")
