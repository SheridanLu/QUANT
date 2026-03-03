#!/usr/bin/env python3
"""
港股策略 - 快速回测版
每小时汇报进度
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import warnings
warnings.filterwarnings('ignore')

print("="*80)
print(f" 港股策略回测 - 每小时汇报")
print(f" 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
print("="*80)

# 加载数据
print("\n[准备] 加载数据...")
data = pd.read_csv("data/combined_hk_stocks.csv")
data['date'] = pd.to_datetime(data['date'])
print(f"   数据量: {len(data):,}")
print(f"   股票数: {data['Symbol'].nunique()}")

# 计算指标
print("\n[准备] 计算指标...")
for symbol in data['Symbol'].unique():
    mask = data['Symbol'] == symbol
    df = data[mask].sort_values('date').copy()
    
    ma5 = df['close'].rolling(5).mean().values
    ma20 = df['close'].rolling(20).mean().values
    vol_ma = df['volume'].rolling(20).mean().values
    vol_ratio = (df['volume'].values / vol_ma)
    mom = (df['close'].values / np.roll(df['close'].values, 20) - 1)
    
    # RSI
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rsi = (100 - 100/(1+gain/loss)).values
    
    data.loc[mask, 'MA5'] = ma5
    data.loc[mask, 'MA20'] = ma20
    data.loc[mask, 'VOL_MA'] = vol_ma
    data.loc[mask, 'VOL_RATIO'] = vol_ratio
    data.loc[mask, 'MOM'] = mom
    data.loc[mask, 'RSI'] = rsi

print("   完成")

# 回测函数
def quick_backtest(df, mom=0.04, pos=0.08, stop=0.06, profit=0.10, rsi_l=35, rsi_h=65, vol_r=1.5):
    dates = sorted(df['date'].unique())
    cash = 1000000
    positions = {}
    equity = []
    peak = 1000000
    max_dd = 0
    trades = 0
    
    for date in dates:
        day = df[df['date']==date]
        
        # 权益
        eq = cash + sum(p['shares']*day[day['Symbol']==s].iloc[0]['close'] 
                       for s, p in positions.items() if len(day[day['Symbol']==s])>0)
        equity.append(eq)
        peak = max(peak, eq)
        max_dd = min(max_dd, (eq-peak)/peak)
        
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
            if pd.isna(row['MOM']) or pd.isna(row['RSI']): continue
            
            if (row['MOM']>mom and row['MA5']>row['MA20'] and 
                rsi_l<row['RSI']<rsi_h and row['VOL_RATIO']>vol_r):
                shares = int(eq*pos/row['close'])
                if shares>0 and shares*row['close']<cash:
                    cash -= shares*row['close']*1.003
                    positions[s] = {'shares': shares, 'cost': row['close']*1.003}
                    trades += 1
    
    final = cash + sum(p['shares']*df[df['Symbol']==s].iloc[-1]['close'] 
                      for s, p in positions.items())
    
    eq_df = pd.DataFrame(equity)
    eq_df['returns'] = eq_df[0].pct_change()
    
    total = (final/1000000)-1
    days = (dates[-1]-dates[0]).days
    annual = (1+total)**(252/days)-1
    sharpe = np.sqrt(252)*eq_df['returns'].mean()/eq_df['returns'].std() if eq_df['returns'].std()>0 else 0
    
    return {'annual': annual, 'max_dd': max_dd, 'sharpe': sharpe, 'trades': trades}

# 分时段测试
print("\n[回测] 开始测试...")

periods = {
    '全部': data,
    '近5年': data[data['date'] > data['date'].max() - timedelta(days=1825)],
    '近3年': data[data['date'] > data['date'].max() - timedelta(days=1095)],
    '近1年': data[data['date'] > data['date'].max() - timedelta(days=365)],
}

# 参数组合（精简版）
params = [
    {'name': '激进', 'mom': 0.03, 'pos': 0.10, 'stop': 0.08, 'profit': 0.15},
    {'name': '平衡', 'mom': 0.04, 'pos': 0.08, 'stop': 0.06, 'profit': 0.12},
    {'name': '保守', 'mom': 0.05, 'pos': 0.08, 'stop': 0.05, 'profit': 0.10},
    {'name': '短线', 'mom': 0.03, 'pos': 0.06, 'stop': 0.04, 'profit': 0.08},
    {'name': '波段', 'mom': 0.05, 'pos': 0.10, 'stop': 0.08, 'profit': 0.15},
]

start_time = datetime.now()
results = []

for period_name, period_data in periods.items():
    print(f"\n测试时期: {period_name} ({len(period_data):,}条)")
    
    for i, p in enumerate(params, 1):
        r = quick_backtest(period_data, **{k:v for k,v in p.items() if k!='name'})
        r['period'] = period_name
        r['strategy'] = p['name']
        r['params'] = {k:v for k,v in p.items() if k!='name'}
        results.append(r)
        
        # 每10秒打印一次进度
        if (datetime.now() - start_time).seconds % 60 < 10:
            elapsed = (datetime.now() - start_time).seconds
            print(f"  [{elapsed}s] {p['name']}: 年化{r['annual']*100:.1f}% 回撤{r['max_dd']*100:.1f}%")

# 找最佳
print("\n" + "="*80)
print(" 回测结果")
print("="*80)

# 按时期分组
for period in ['全部', '近5年', '近3年', '近1年']:
    period_results = [r for r in results if r['period']==period]
    period_results.sort(key=lambda x: x['sharpe'], reverse=True)
    
    print(f"\n{period}:")
    for i, r in enumerate(period_results[:3], 1):
        print(f"  {i}. {r['strategy']}: 年化{r['annual']*100:.1f}% | 回撤{r['max_dd']*100:.1f}% | 夏普{r['sharpe']:.2f}")

# 最佳策略
all_results = [r for r in results if r['period']=='全部']
best = max(all_results, key=lambda x: x['sharpe'])

print("\n" + "="*80)
print(" 🏆 最佳策略")
print("="*80)
print(f"策略: {best['strategy']}")
print(f"年化收益: {best['annual']*100:.2f}%")
print(f"最大回撤: {best['max_dd']*100:.2f}%")
print(f"夏普比率: {best['sharpe']:.3f}")
print(f"交易次数: {best['trades']}")
print(f"\n参数:")
for k, v in best['params'].items():
    print(f"  {k}: {v}")

# 保存
report = f"""# 今日回测报告

时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}

## 最佳策略

**{best['strategy']}**

- 年化收益: {best['annual']*100:.2f}%
- 最大回撤: {best['max_dd']*100:.2f}%
- 夏普比率: {best['sharpe']:.3f}
- 交易次数: {best['trades']}

参数:
```python
MOM_THRESHOLD = {best['params']['mom']}
POSITION_SIZE = {best['params']['pos']}
STOP_LOSS = {best['params']['stop']}
TAKE_PROFIT = {best['params']['profit']}
```

## 各时期表现

| 时期 | 策略 | 年化收益 | 最大回撤 | 夏普比率 |
|------|------|---------|---------|---------|
"""

for r in sorted(results, key=lambda x: (x['period'], -x['sharpe'])):
    report += f"| {r['period']} | {r['strategy']} | {r['annual']*100:.1f}% | {r['max_dd']*100:.1f}% | {r['sharpe']:.2f} |\n"

with open('TODAY_BACKTEST_REPORT.md', 'w') as f:
    f.write(report)

print("\n报告已保存: TODAY_BACKTEST_REPORT.md")
print(f"\n总耗时: {(datetime.now()-start_time).seconds}秒")
