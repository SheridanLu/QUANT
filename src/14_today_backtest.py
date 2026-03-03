#!/usr/bin/env python3
"""
港股策略 - 今日完整回测
时间: 2026-03-03 09:20
目标: 找到最优策略参数
"""

import pandas as pd
import numpy as np
from datetime import datetime
import json
import warnings
warnings.filterwarnings('ignore')

print("="*80)
print(f" 港股策略回测 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
print("="*80)

# ============ 数据准备 ============

print("\n[1/6] 加载数据...")
data = pd.read_csv("data/combined_hk_stocks.csv")
data['date'] = pd.to_datetime(data['date'])
print(f"   数据: {len(data):,} 条")
print(f"   股票: {data['Symbol'].nunique()} 只")
print(f"   时间: {data['date'].min().date()} ~ {data['date'].max().date()}")

# ============ 计算指标 ============

print("\n[2/6] 计算技术指标...")

def calc_all_indicators(df):
    """计算所有技术指标"""
    df = df.sort_values(['Symbol', 'date'])
    
    # 动量
    for p in [5, 10, 20]:
        df[f'MOM_{p}'] = df.groupby('Symbol')['close'].transform(
            lambda x: x/x.shift(p)-1
        )
    
    # 均线
    for w in [5, 10, 20, 50]:
        df[f'MA{w}'] = df.groupby('Symbol')['close'].transform(
            lambda x: x.rolling(w).mean()
        )
    
    # RSI
    def rsi(s, w=14):
        d = s.diff()
        g = d.where(d>0,0).rolling(w).mean()
        l = (-d.where(d<0,0)).rolling(w).mean()
        return 100-(100/(1+g/l))
    df['RSI'] = df.groupby('Symbol')['close'].transform(rsi)
    
    # 波动率
    df['VOL'] = df.groupby('Symbol')['close'].transform(
        lambda x: x.pct_change().rolling(20).std()*np.sqrt(252)
    )
    
    # 量比
    df['VOL_RATIO'] = df.groupby('Symbol')['volume'].transform(
        lambda x: x/x.rolling(20).mean()
    )
    
    # 成交额
    df['AMOUNT'] = df['close'] * df['volume']
    
    return df

data = calc_all_indicators(data)
print("   完成: MOM/MA/RSI/VOL/量比")

# ============ 回测函数 ============

def backtest(df, params):
    """通用回测"""
    dates = sorted(df['date'].unique())
    cash = 1000000
    positions = {}
    equity_curve = []
    trades = []
    peak = 1000000
    max_dd = 0
    
    for date in dates:
        day = df[df['date']==date]
        
        # 权益
        equity = cash
        for s, p in positions.items():
            row = day[day['Symbol']==s]
            if len(row) > 0:
                equity += p['shares'] * row.iloc[0]['close']
        
        equity_curve.append({'date': date, 'equity': equity})
        peak = max(peak, equity)
        max_dd = min(max_dd, (equity-peak)/peak)
        
        # 止损止盈
        for s in list(positions.keys()):
            row = day[day['Symbol']==s]
            if len(row) == 0:
                continue
            
            pnl = (row.iloc[0]['close']-positions[s]['cost'])/positions[s]['cost']
            
            if pnl < -params['stop_loss'] or pnl > params['take_profit']:
                cash += positions[s]['shares'] * row.iloc[0]['close'] * 0.997
                trades.append({'pnl': pnl})
                del positions[s]
        
        # 买入信号
        for _, row in day.iterrows():
            s = row['Symbol']
            if s in positions:
                continue
            
            if pd.isna(row['MOM_20']) or pd.isna(row['RSI']):
                continue
            if row['VOL'] > params['max_vol']:
                continue
            if row['AMOUNT'] < 5e7:
                continue
            
            # 买入条件
            buy = (
                row['MOM_20'] > params['mom'] and
                row['MA5'] > row['MA20'] and
                params['rsi_low'] < row['RSI'] < params['rsi_high'] and
                row['VOL_RATIO'] > params['vol_ratio']
            )
            
            if not buy:
                continue
            
            shares = int(equity * params['position'] / row['close'])
            if shares <= 0 or shares * row['close'] > cash:
                continue
            
            cash -= shares * row['close'] * 1.003
            positions[s] = {
                'shares': shares,
                'cost': row['close'] * 1.003,
                'date': date
            }
            trades.append({'action': 'BUY'})
    
    # 平仓
    final = cash
    for s, p in positions.items():
        last = df[df['Symbol']==s].iloc[-1]['close']
        final += p['shares'] * last
    
    # 指标
    eq_df = pd.DataFrame(equity_curve)
    eq_df['returns'] = eq_df['equity'].pct_change()
    
    total = (final/1000000)-1
    days = (dates[-1]-dates[0]).days
    annual = (1+total)**(252/days)-1
    sharpe = np.sqrt(252)*eq_df['returns'].mean()/eq_df['returns'].std() if eq_df['returns'].std()>0 else 0
    
    return {
        'total': total,
        'annual': annual,
        'max_dd': max_dd,
        'sharpe': sharpe,
        'trades': len([t for t in trades if t.get('action')=='BUY'])
    }

# ============ 策略测试 ============

print("\n[3/6] 策略参数网格搜索...")

results = []

# 参数组合
param_grid = []

# 动量阈值
for mom in [0.03, 0.04, 0.05, 0.06]:
    # 仓位
    for pos in [0.08, 0.10, 0.12]:
        # 止损
        for stop in [0.05, 0.06, 0.08]:
            # 止盈
            for profit in [0.08, 0.10, 0.12, 0.15]:
                # RSI
                for rsi_l, rsi_h in [(30, 70), (35, 65), (40, 60)]:
                    # 量比
                    for vol_r in [1.2, 1.5, 2.0]:
                        param_grid.append({
                            'mom': mom,
                            'position': pos,
                            'stop_loss': stop,
                            'take_profit': profit,
                            'rsi_low': rsi_l,
                            'rsi_high': rsi_h,
                            'vol_ratio': vol_r,
                            'max_vol': 0.45
                        })

print(f"   测试 {len(param_grid)} 组参数...")

for i, p in enumerate(param_grid[:100], 1):  # 限制100组
    if i % 10 == 0:
        print(f"   进度: {i}/{min(len(param_grid), 100)}", end='\r')
    
    r = backtest(data, p)
    r['params'] = p
    results.append(r)

print(f"\n   完成: {len(results)} 组")

# ============ 筛选最优 ============

print("\n[4/6] 筛选最优策略...")

# 分类筛选
categories = {
    '高收益': lambda r: r['annual'],
    '低回撤': lambda r: -r['max_dd'],
    '高夏普': lambda r: r['sharpe'],
    '平衡': lambda r: r['sharpe'] - abs(r['max_dd'])*2,
}

best_by_cat = {}
for cat, key_func in categories.items():
    sorted_results = sorted(results, key=key_func, reverse=True)
    if sorted_results:
        best_by_cat[cat] = sorted_results[0]

for cat, r in best_by_cat.items():
    p = r['params']
    print(f"\n   {cat}:")
    print(f"     年化: {r['annual']*100:.2f}%  回撤: {r['max_dd']*100:.1f}%  夏普: {r['sharpe']:.2f}")
    print(f"     动量>{p['mom']*100:.0f}%  仓位{p['position']*100:.0f}%  止损{p['stop_loss']*100:.0f}%  止盈{p['take_profit']*100:.0f}%")

# ============ 时间段分析 ============

print("\n[5/6] 不同时间段表现...")

# 分3个时期
total_days = (data['date'].max() - data['date'].min()).days
split1 = data['date'].min() + pd.Timedelta(days=total_days//3)
split2 = data['date'].min() + pd.Timedelta(days=total_days*2//3)

periods = {
    '早期': data[data['date'] < split1],
    '中期': data[(data['date'] >= split1) & (data['date'] < split2)],
    '晚期': data[data['date'] >= split2]
}

# 用最佳参数测试不同时期
best_params = best_by_cat['高夏普']['params']

for name, period_data in periods.items():
    r = backtest(period_data, best_params)
    print(f"   {name} ({period_data['date'].min().year}-{period_data['date'].max().year}): 年化{r['annual']*100:.1f}% 回撤{r['max_dd']*100:.1f}%")

# ============ 生成报告 ============

print("\n[6/6] 生成报告...")

report = f"""# 港股策略回测报告

生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}

## 数据概况

- 数据量: {len(data):,} 条
- 股票数: {data['Symbol'].nunique()}
- 时间范围: {data['date'].min().date()} ~ {data['date'].max().date()}
- 测试参数: {len(results)} 组

## 最优策略

### 按夏普比率

"""

# Top 10 by Sharpe
top_sharpe = sorted(results, key=lambda x: x['sharpe'], reverse=True)[:10]
report += "| 排名 | 年化收益 | 最大回撤 | 夏普比率 | 动量 | 仓位 | 止损 | 止盈 |\n"
report += "|------|---------|---------|---------|------|------|------|------|\n"
for i, r in enumerate(top_sharpe, 1):
    p = r['params']
    report += f"| {i} | {r['annual']*100:.1f}% | {r['max_dd']*100:.1f}% | {r['sharpe']:.2f} | {p['mom']*100:.0f}% | {p['position']*100:.0f}% | {p['stop_loss']*100:.0f}% | {p['take_profit']*100:.0f}% |\n"

report += f"""

### 按分类最优

"""

for cat, r in best_by_cat.items():
    p = r['params']
    report += f"""
**{cat}**:
- 年化收益: {r['annual']*100:.2f}%
- 最大回撤: {r['max_dd']*100:.2f}%
- 夏普比率: {r['sharpe']:.3f}

参数配置:
```
动量阈值: {p['mom']*100:.0f}%
仓位大小: {p['position']*100:.0f}%
止损: {p['stop_loss']*100:.0f}%
止盈: {p['take_profit']*100:.0f}%
RSI区间: {p['rsi_low']}-{p['rsi_high']}
量比要求: {p['vol_ratio']:.1f}
```
"""

report += f"""

## 不同时期表现

使用最佳策略（夏普最高）在不同时期的表现:

| 时期 | 年化收益 | 最大回撤 | 夏普比率 |
|------|---------|---------|---------|
"""

for name, period_data in periods.items():
    r = backtest(period_data, best_params)
    report += f"| {name} | {r['annual']*100:.1f}% | {r['max_dd']*100:.1f}% | {r['sharpe']:.2f} |\n"

report += f"""

## 实盘建议

### 策略选择

"""

# 找出回撤<20%中夏普最高的
low_dd_strategies = [r for r in results if r['max_dd'] > -0.20]
if low_dd_strategies:
    best_safe = sorted(low_dd_strategies, key=lambda x: x['sharpe'], reverse=True)[0]
    p = best_safe['params']
    report += f"""
**推荐策略** (回撤<20%):

```python
# 策略参数
MOM_THRESHOLD = {p['mom']}      # 动量阈值
POSITION_SIZE = {p['position']}   # 仓位
STOP_LOSS = {p['stop_loss']}       # 止损
TAKE_PROFIT = {p['take_profit']}   # 止盈
RSI_RANGE = ({p['rsi_low']}, {p['rsi_high']})  # RSI区间
VOL_RATIO = {p['vol_ratio']}       # 量比

# 买入条件
买入 = (
    20日动量 > {p['mom']*100:.0f}% and
    MA5 > MA20 and
    {p['rsi_low']} < RSI < {p['rsi_high']} and
    量比 > {p['vol_ratio']}
)

# 预期
年化收益: ~{best_safe['annual']*100:.1f}%
最大回撤: ~{best_safe['max_dd']*100:.1f}%
夏普比率: ~{best_safe['sharpe']:.2f}
```
"""

report += """

### 风险提示

1. 过去表现不代表未来
2. 策略可能过拟合
3. 实盘有滑点和手续费
4. 市场环境会变化
5. 建议小资金测试

### 执行步骤

1. 用推荐参数配置富途策略
2. 初始资金建议5-10万港币
3. 观察1个月实际表现
4. 根据实盘调整参数
5. 逐步增加资金

---

_报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_
"""

# 保存
with open('TODAY_BACKTEST_REPORT.md', 'w', encoding='utf-8') as f:
    f.write(report)

# 保存详细数据
with open('results/today_backtest.json', 'w', encoding='utf-8') as f:
    json.dump({
        'timestamp': datetime.now().isoformat(),
        'results': results[:50],  # Top 50
        'best_by_category': {k: {
            'annual': v['annual'],
            'max_dd': v['max_dd'],
            'sharpe': v['sharpe'],
            'params': v['params']
        } for k, v in best_by_cat.items()}
    }, f, indent=2, default=str)

print("   报告: TODAY_BACKTEST_REPORT.md")
print("   数据: results/today_backtest.json")

# ============ 总结 ============

print("\n" + "="*80)
print(" 今日回测完成")
print("="*80)

best = best_by_cat['高夏普']
print(f"\n🏆 最佳策略:")
print(f"   年化收益: {best['annual']*100:.2f}%")
print(f"   最大回撤: {best['max_dd']*100:.2f}%")
print(f"   夏普比率: {best['sharpe']:.3f}")

p = best['params']
print(f"\n   参数:")
print(f"   动量>{p['mom']*100:.0f}% | 仓位{p['position']*100:.0f}% | 止损{p['stop_loss']*100:.0f}% | 止盈{p['take_profit']*100:.0f}%")

if best['max_dd'] > -0.20:
    print(f"\n✅ 回撤<20%，可以实盘")
else:
    print(f"\n⚠️  回撤>{abs(best['max_dd'])*100:.0f}%，需要谨慎")

print("\n" + "="*80)
