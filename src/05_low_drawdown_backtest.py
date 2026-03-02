#!/usr/bin/env python3
"""
低回撤策略回测验证
目标: 年化10%+ 最大回撤15%以内
"""

import pandas as pd
import numpy as np
from typing import Dict, List
import warnings
warnings.filterwarnings('ignore')


class StrictRiskBacktest:
    """严格风控回测"""
    
    def __init__(self, data_path: str = "data/combined_hk_stocks.csv"):
        self.data = pd.read_csv(data_path)
        self.data['date'] = pd.to_datetime(self.data['date'])
        self.data = self.data.sort_values(['Symbol', 'date'])
        
        # 风控参数 (更严格)
        self.MAX_DRAWDOWN = 0.10      # 最大回撤10%
        self.MAX_POSITION = 0.08      # 单只8%
        self.STOP_LOSS = 0.05         # 止损5%
        self.TAKE_PROFIT = 0.12       # 止盈12%
        self.MAX_VOLATILITY = 0.35    # 最大波动35%
        self.MIN_AMOUNT = 1e8         # 最小成交额1亿
    
    def prepare_data(self):
        """计算指标"""
        print("计算技术指标...")
        
        # 动量
        self.data['MOM'] = self.data.groupby('Symbol')['close'].transform(
            lambda x: x / x.shift(20) - 1
        )
        
        # 均线
        self.data['MA5'] = self.data.groupby('Symbol')['close'].transform(
            lambda x: x.rolling(5).mean()
        )
        self.data['MA20'] = self.data.groupby('Symbol')['close'].transform(
            lambda x: x.rolling(20).mean()
        )
        
        # RSI
        def rsi(series, window=14):
            delta = series.diff()
            gain = delta.where(delta > 0, 0).rolling(window).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window).mean()
            return 100 - (100 / (1 + gain / loss))
        
        self.data['RSI'] = self.data.groupby('Symbol')['close'].transform(rsi)
        
        # 波动率
        self.data['VOL'] = self.data.groupby('Symbol')['close'].transform(
            lambda x: x.pct_change().rolling(20).std() * np.sqrt(252)
        )
        
        # 成交额
        self.data['AMOUNT'] = self.data['close'] * self.data['volume']
        
        # 量比
        self.data['VOL_RATIO'] = self.data.groupby('Symbol')['volume'].transform(
            lambda x: x / x.rolling(20).mean()
        )
        
        print("指标计算完成!")
        return self.data
    
    def backtest(self, initial_capital: float = 1000000) -> Dict:
        """
        回测主逻辑
        """
        print("\n" + "=" * 60)
        print(" 开始严格风控回测")
        print("=" * 60)
        
        # 按日期遍历
        dates = sorted(self.data['date'].unique())
        
        capital = initial_capital
        cash = capital
        positions = {}  # {symbol: {shares, cost, date}}
        equity_curve = []
        peak_equity = capital
        trades = []
        
        for date in dates:
            day_data = self.data[self.data['date'] == date]
            
            # 计算当日权益
            equity = cash
            for symbol, pos in positions.items():
                price_row = day_data[day_data['Symbol'] == symbol]
                if not price_row.empty:
                    equity += pos['shares'] * price_row.iloc[0]['close']
            
            equity_curve.append({'date': date, 'equity': equity})
            
            # 检查总回撤
            peak_equity = max(peak_equity, equity)
            drawdown = (equity - peak_equity) / peak_equity
            
            if drawdown < -self.MAX_DRAWDOWN:
                print(f"⚠️  {date.date()} 触及最大回撤 {drawdown*100:.2f}%, 清仓")
                # 清仓
                for symbol in list(positions.keys()):
                    pos = positions[symbol]
                    price_row = day_data[day_data['Symbol'] == symbol]
                    if not price_row.empty:
                        price = price_row.iloc[0]['close']
                        cash += pos['shares'] * price * 0.997  # 手续费
                        trades.append({
                            'date': date,
                            'symbol': symbol,
                            'action': 'SELL',
                            'price': price,
                            'shares': pos['shares'],
                            'reason': '风控清仓'
                        })
                positions = {}
                peak_equity = equity
            
            # 检查持仓的止损止盈
            for symbol in list(positions.keys()):
                pos = positions[symbol]
                price_row = day_data[day_data['Symbol'] == symbol]
                if price_row.empty:
                    continue
                
                price = price_row.iloc[0]['close']
                pnl = (price - pos['cost']) / pos['cost']
                
                # 止损
                if pnl < -self.STOP_LOSS:
                    print(f"  🛑 {date.date()} {symbol} 止损: {pnl*100:.2f}%")
                    cash += pos['shares'] * price * 0.997
                    trades.append({
                        'date': date,
                        'symbol': symbol,
                        'action': 'SELL',
                        'price': price,
                        'shares': pos['shares'],
                        'reason': f'止损 {pnl*100:.2f}%'
                    })
                    del positions[symbol]
                    continue
                
                # 止盈
                if pnl > self.TAKE_PROFIT:
                    print(f"  🎯 {date.date()} {symbol} 止盈: {pnl*100:.2f}%")
                    cash += pos['shares'] * price * 0.997
                    trades.append({
                        'date': date,
                        'symbol': symbol,
                        'action': 'SELL',
                        'price': price,
                        'shares': pos['shares'],
                        'reason': f'止盈 {pnl*100:.2f}%'
                    })
                    del positions[symbol]
            
            # 生成买入信号
            for _, row in day_data.iterrows():
                symbol = row['Symbol']
                
                # 已持有则跳过
                if symbol in positions:
                    continue
                
                # 质量检查
                if pd.isna(row['VOL']) or row['VOL'] > self.MAX_VOLATILITY:
                    continue
                if pd.isna(row['AMOUNT']) or row['AMOUNT'] < self.MIN_AMOUNT:
                    continue
                
                # 买入信号 (更保守)
                buy_signal = (
                    row['MOM'] > 0.05 and              # 动量>5%
                    row['MA5'] > row['MA20'] and       # 均线多头
                    40 < row['RSI'] < 60 and           # RSI更严格
                    row['VOL_RATIO'] > 1.5             # 成交量放大更多
                )
                
                if not buy_signal:
                    continue
                
                # 计算仓位
                position_value = equity * self.MAX_POSITION
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
                    'action': 'BUY',
                    'price': row['close'],
                    'shares': shares,
                    'reason': '动量+均线'
                })
        
        # 最终平仓
        final_equity = cash
        for symbol, pos in positions.items():
            last_price = self.data[self.data['Symbol'] == symbol].iloc[-1]['close']
            final_equity += pos['shares'] * last_price
        
        # 计算指标
        equity_df = pd.DataFrame(equity_curve)
        equity_df['returns'] = equity_df['equity'].pct_change()
        equity_df['cummax'] = equity_df['equity'].cummax()
        equity_df['drawdown'] = (equity_df['equity'] - equity_df['cummax']) / equity_df['cummax']
        
        total_return = (final_equity / initial_capital) - 1
        days = (dates[-1] - dates[0]).days
        annual_return = (1 + total_return) ** (252 / max(days, 1)) - 1
        max_drawdown = equity_df['drawdown'].min()
        
        sharpe = np.sqrt(252) * equity_df['returns'].mean() / equity_df['returns'].std()
        
        # 胜率
        wins = sum(1 for t in trades if t['action'] == 'SELL' and '止盈' in t.get('reason', ''))
        losses = sum(1 for t in trades if t['action'] == 'SELL' and '止损' in t.get('reason', ''))
        total_sells = wins + losses
        win_rate = wins / total_sells if total_sells > 0 else 0
        
        return {
            'initial_capital': initial_capital,
            'final_equity': final_equity,
            'total_return': total_return,
            'annual_return': annual_return,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe,
            'win_rate': win_rate,
            'total_trades': len(trades),
            'equity_curve': equity_df,
            'trades': trades
        }
    
    def print_results(self, results: Dict):
        """打印结果"""
        print("\n" + "=" * 60)
        print(" 严格风控策略回测结果")
        print("=" * 60)
        print(f"初始资金:     {results['initial_capital']:,.0f} HKD")
        print(f"最终资金:     {results['final_equity']:,.0f} HKD")
        print(f"累计收益率:   {results['total_return']*100:.2f}%")
        print(f"年化收益率:   {results['annual_return']*100:.2f}%")
        print(f"最大回撤:     {results['max_drawdown']*100:.2f}%")
        print(f"夏普比率:     {results['sharpe_ratio']:.3f}")
        print(f"胜率:         {results['win_rate']*100:.2f}%")
        print(f"交易次数:     {results['total_trades']}")
        print("=" * 60)
        
        # 检查是否达标
        if results['max_drawdown'] > -0.15:
            print("✅ 最大回撤达标 (<15%)")
        else:
            print("❌ 最大回撤超标")
        
        if results['annual_return'] > 0.10:
            print("✅ 年化收益达标 (>10%)")
        else:
            print("❌ 年化收益不达标")


def main():
    print("=" * 60)
    print(" 低回撤策略回测验证")
    print(" 目标: 年化10%+ 最大回撤15%以内")
    print("=" * 60)
    
    backtest = StrictRiskBacktest("data/combined_hk_stocks.csv")
    backtest.prepare_data()
    
    results = backtest.backtest(initial_capital=1000000)
    backtest.print_results(results)
    
    return results


if __name__ == "__main__":
    results = main()
