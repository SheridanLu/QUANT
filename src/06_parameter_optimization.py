#!/usr/bin/env python3
"""
港股策略优化 - 寻找收益与回撤的平衡点
目标: 年化12%+ 最大回撤15%以内
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
import warnings
warnings.filterwarnings('ignore')


def backtest_strategy(
    data: pd.DataFrame,
    mom_threshold: float = 0.04,
    max_position: float = 0.10,
    stop_loss: float = 0.06,
    take_profit: float = 0.12,
    max_volatility: float = 0.40,
    rsi_lower: float = 35,
    rsi_upper: float = 65,
    vol_ratio_threshold: float = 1.3,
    initial_capital: float = 1000000,
    verbose: bool = False
) -> Dict:
    """
    回测策略
    
    Args:
        data: 股票数据
        mom_threshold: 动量阈值
        max_position: 最大仓位
        stop_loss: 止损比例
        take_profit: 止盈比例
        max_volatility: 最大波动率
        rsi_lower: RSI下限
        rsi_upper: RSI上限
        vol_ratio_threshold: 量比阈值
        initial_capital: 初始资金
        verbose: 是否打印详情
    """
    
    # 计算指标
    df = data.copy()
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values(['Symbol', 'date'])
    
    # 动量
    df['MOM'] = df.groupby('Symbol')['close'].transform(
        lambda x: x / x.shift(20) - 1
    )
    
    # 均线
    df['MA5'] = df.groupby('Symbol')['close'].transform(lambda x: x.rolling(5).mean())
    df['MA20'] = df.groupby('Symbol')['close'].transform(lambda x: x.rolling(20).mean())
    df['MA50'] = df.groupby('Symbol')['close'].transform(lambda x: x.rolling(50).mean())
    
    # RSI
    def rsi(series, window=14):
        delta = series.diff()
        gain = delta.where(delta > 0, 0).rolling(window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window).mean()
        return 100 - (100 / (1 + gain / loss))
    
    df['RSI'] = df.groupby('Symbol')['close'].transform(rsi)
    
    # 波动率
    df['VOL'] = df.groupby('Symbol')['close'].transform(
        lambda x: x.pct_change().rolling(20).std() * np.sqrt(252)
    )
    
    # 量比
    df['VOL_RATIO'] = df.groupby('Symbol')['volume'].transform(
        lambda x: x / x.rolling(20).mean()
    )
    
    # 成交额
    df['AMOUNT'] = df['close'] * df['volume']
    
    # 回测
    dates = sorted(df['date'].unique())
    
    cash = initial_capital
    positions = {}  # {symbol: {shares, cost, date}}
    equity_curve = []
    peak_equity = initial_capital
    trades = []
    max_dd = 0
    
    for date in dates:
        day_data = df[df['date'] == date]
        
        # 计算权益
        equity = cash
        for symbol, pos in positions.items():
            price_row = day_data[day_data['Symbol'] == symbol]
            if not price_row.empty:
                equity += pos['shares'] * price_row.iloc[0]['close']
        
        equity_curve.append({'date': date, 'equity': equity})
        
        # 更新峰值和回撤
        peak_equity = max(peak_equity, equity)
        dd = (equity - peak_equity) / peak_equity
        max_dd = min(max_dd, dd)
        
        # 检查持仓止损止盈
        for symbol in list(positions.keys()):
            pos = positions[symbol]
            price_row = day_data[day_data['Symbol'] == symbol]
            if price_row.empty:
                continue
            
            price = price_row.iloc[0]['close']
            pnl = (price - pos['cost']) / pos['cost']
            
            if pnl < -stop_loss or pnl > take_profit:
                cash += pos['shares'] * price * 0.997
                trades.append({
                    'date': date,
                    'symbol': symbol,
                    'action': 'SELL',
                    'pnl': pnl
                })
                del positions[symbol]
        
        # 买入信号
        for _, row in day_data.iterrows():
            symbol = row['Symbol']
            
            if symbol in positions:
                continue
            
            # 质量检查
            if pd.isna(row['VOL']) or row['VOL'] > max_volatility:
                continue
            if pd.isna(row['AMOUNT']) or row['AMOUNT'] < 5e7:
                continue
            
            # 买入信号
            buy_signal = (
                row['MOM'] > mom_threshold and
                row['MA5'] > row['MA20'] and
                rsi_lower < row['RSI'] < rsi_upper and
                row['VOL_RATIO'] > vol_ratio_threshold
            )
            
            if not buy_signal:
                continue
            
            # 仓位计算
            position_value = equity * max_position
            shares = int(position_value / row['close'])
            
            if shares <= 0 or shares * row['close'] > cash:
                continue
            
            # 买入
            cost = shares * row['close'] * 1.003
            cash -= cost
            positions[symbol] = {
                'shares': shares,
                'cost': row['close'] * 1.003,
                'date': date
            }
            
            trades.append({
                'date': date,
                'symbol': symbol,
                'action': 'BUY'
            })
    
    # 最终平仓
    final_equity = cash
    for symbol, pos in positions.items():
        last_price = df[df['Symbol'] == symbol].iloc[-1]['close']
        final_equity += pos['shares'] * last_price
    
    # 计算指标
    equity_df = pd.DataFrame(equity_curve)
    equity_df['returns'] = equity_df['equity'].pct_change()
    
    total_return = (final_equity / initial_capital) - 1
    days = (dates[-1] - dates[0]).days
    annual_return = (1 + total_return) ** (252 / max(days, 1)) - 1
    
    sharpe = np.sqrt(252) * equity_df['returns'].mean() / equity_df['returns'].std()
    
    # 胜率
    wins = sum(1 for t in trades if t['action'] == 'SELL' and t.get('pnl', 0) > 0)
    losses = sum(1 for t in trades if t['action'] == 'SELL' and t.get('pnl', 0) < 0)
    total_sells = wins + losses
    win_rate = wins / total_sells if total_sells > 0 else 0
    
    return {
        'annual_return': annual_return,
        'max_drawdown': max_dd,
        'sharpe_ratio': sharpe,
        'win_rate': win_rate,
        'total_trades': len(trades),
        'params': {
            'mom_threshold': mom_threshold,
            'max_position': max_position,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'max_volatility': max_volatility,
            'rsi_lower': rsi_lower,
            'rsi_upper': rsi_upper,
            'vol_ratio_threshold': vol_ratio_threshold
        }
    }


def grid_search(data: pd.DataFrame) -> List[Dict]:
    """网格搜索最优参数"""
    
    print("=" * 60)
    print(" 策略参数优化")
    print("=" * 60)
    
    results = []
    
    # 参数范围
    mom_range = [0.03, 0.04, 0.05]
    pos_range = [0.08, 0.10, 0.12]
    stop_range = [0.05, 0.06, 0.08]
    profit_range = [0.10, 0.12, 0.15]
    vol_range = [0.35, 0.40, 0.45]
    
    total = len(mom_range) * len(pos_range) * len(stop_range) * len(profit_range) * len(vol_range)
    count = 0
    
    for mom in mom_range:
        for pos in pos_range:
            for stop in stop_range:
                for profit in profit_range:
                    for vol in vol_range:
                        count += 1
                        print(f"\r优化进度: {count}/{total}", end="", flush=True)
                        
                        result = backtest_strategy(
                            data,
                            mom_threshold=mom,
                            max_position=pos,
                            stop_loss=stop,
                            take_profit=profit,
                            max_volatility=vol,
                            verbose=False
                        )
                        
                        # 筛选: 回撤<15% 且 收益>5%
                        if result['max_drawdown'] > -0.15 and result['annual_return'] > 0.05:
                            results.append(result)
    
    print(f"\n\n找到 {len(results)} 组符合条件的参数")
    
    # 按夏普排序
    results.sort(key=lambda x: x['sharpe_ratio'], reverse=True)
    
    return results[:10]  # 返回前10


def main():
    print("=" * 60)
    print(" 港股策略参数优化")
    print(" 目标: 年化10%+ 最大回撤15%以内")
    print("=" * 60)
    
    # 加载数据
    data = pd.read_csv("data/combined_hk_stocks.csv")
    
    # 参数优化
    top_results = grid_search(data)
    
    if not top_results:
        print("\n⚠️  未找到符合条件的参数组合")
        print("尝试放宽条件...")
        
        # 放宽条件: 回撤<20%
        results = []
        for mom in [0.03, 0.04, 0.05]:
            for stop in [0.06, 0.08]:
                for profit in [0.10, 0.12, 0.15]:
                    result = backtest_strategy(
                        data,
                        mom_threshold=mom,
                        stop_loss=stop,
                        take_profit=profit,
                        verbose=False
                    )
                    if result['max_drawdown'] > -0.20 and result['annual_return'] > 0.05:
                        results.append(result)
        
        if results:
            results.sort(key=lambda x: x['sharpe_ratio'], reverse=True)
            top_results = results[:5]
    
    # 输出结果
    print("\n" + "=" * 80)
    print(" 最优参数组合")
    print("=" * 80)
    
    for i, r in enumerate(top_results, 1):
        p = r['params']
        print(f"\n方案 {i}:")
        print(f"  年化收益:   {r['annual_return']*100:.2f}%")
        print(f"  最大回撤:   {r['max_drawdown']*100:.2f}%")
        print(f"  夏普比率:   {r['sharpe_ratio']:.3f}")
        print(f"  胜率:       {r['win_rate']*100:.1f}%")
        print(f"  交易次数:   {r['total_trades']}")
        print(f"  参数: 动量>{p['mom_threshold']*100:.0f}% 仓位{p['max_position']*100:.0f}% 止损{p['stop_loss']*100:.0f}% 止盈{p['take_profit']*100:.0f}%")
    
    # 找出最佳
    if top_results:
        best = top_results[0]
        print("\n" + "=" * 80)
        print(" 🏆 最佳方案")
        print("=" * 80)
        print(f"年化收益: {best['annual_return']*100:.2f}%")
        print(f"最大回撤: {best['max_drawdown']*100:.2f}%")
        print(f"夏普比率: {best['sharpe_ratio']:.3f}")
        
        if best['max_drawdown'] > -0.15:
            print("\n✅ 回撤达标 (<15%)")
        else:
            print(f"\n⚠️  回撤略超 ({best['max_drawdown']*100:.1f}%)")
        
        if best['annual_return'] > 0.10:
            print("✅ 收益达标 (>10%)")
        else:
            print(f"⚠️  收益略低 ({best['annual_return']*100:.1f}%)")
    
    return top_results


if __name__ == "__main__":
    results = main()
