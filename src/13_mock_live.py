#!/usr/bin/env python3
"""
模拟实盘测试
不需要真实账户，用历史数据模拟实时交易
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import random

print("="*80)
print(" 模拟实盘测试")
print(" 用历史数据模拟实时交易环境")
print("="*80)

# 加载数据
data = pd.read_csv("data/combined_hk_stocks.csv")
data['date'] = pd.to_datetime(data['date'])

# 股票池 (注意：数据中的Symbol格式)
SYMBOLS = ['00700', '00941', '00005', '00883', '01810', '03690', '00011', '00016']
NAMES = {
    '00700': '腾讯', '00941': '中移动', '00005': '汇丰', '00883': '中海油',
    '01810': '小米', '03690': '美团', '00011': '恒生', '00016': '新鸿基'
}

# 策略参数
CONFIG = {
    'ma_fast': 5,
    'ma_slow': 20,
    'vol_ratio': 1.5,
    'position_pct': 0.08,
    'max_positions': 3,
    'stop_loss': 0.06,
    'take_profit': 0.12,
}

# ============ 模拟交易类 ============

class MockLiveTrader:
    """模拟实盘交易"""
    
    def __init__(self, data, symbols, config):
        self.data = data
        self.symbols = symbols
        self.config = config
        
        # 账户
        self.cash = 1000000
        self.positions = {}
        self.trades = []
        
        # 指标
        self._calc_indicators()
    
    def _calc_indicators(self):
        """预计算指标"""
        for symbol in self.symbols:
            df = self.data[self.data['Symbol'] == symbol].copy()
            df = df.sort_values('date')
            
            df['MA_FAST'] = df['close'].rolling(self.config['ma_fast']).mean()
            df['MA_SLOW'] = df['close'].rolling(self.config['ma_slow']).mean()
            df['VOL_MA'] = df['volume'].rolling(20).mean()
            df['VOL_RATIO'] = df['volume'] / df['VOL_MA']
            
            self.data.loc[df.index, 'MA_FAST'] = df['MA_FAST']
            self.data.loc[df.index, 'MA_SLOW'] = df['MA_SLOW']
            self.data.loc[df.index, 'VOL_RATIO'] = df['VOL_RATIO']
    
    def get_equity(self, date):
        """计算权益"""
        equity = self.cash
        day = self.data[self.data['date'] == date]
        
        for symbol, pos in self.positions.items():
            row = day[day['Symbol'] == symbol]
            if len(row) > 0:
                equity += pos['shares'] * row.iloc[0]['close']
        
        return equity
    
    def check_stop_loss(self, symbol, price):
        """检查止损止盈"""
        if symbol not in self.positions:
            return False, None
        
        pos = self.positions[symbol]
        pnl = (price - pos['cost']) / pos['cost']
        
        if pnl < -self.config['stop_loss']:
            return True, f"止损 ({pnl*100:.2f}%)"
        
        if pnl > self.config['take_profit']:
            return True, f"止盈 ({pnl*100:.2f}%)"
        
        return False, None
    
    def buy(self, symbol, price, date):
        """买入"""
        equity = self.get_equity(date)
        position_value = equity * self.config['position_pct']
        shares = int(position_value / price / 100) * 100
        
        if shares <= 0 or shares * price > self.cash:
            return False
        
        cost = shares * price * 1.003  # 手续费
        self.cash -= cost
        
        self.positions[symbol] = {
            'shares': shares,
            'cost': price * 1.003,
            'date': date
        }
        
        self.trades.append({
            'date': date,
            'symbol': symbol,
            'action': 'BUY',
            'price': price,
            'shares': shares
        })
        
        return True
    
    def sell(self, symbol, price, reason=''):
        """卖出"""
        if symbol not in self.positions:
            return
        
        pos = self.positions[symbol]
        revenue = pos['shares'] * price * 0.997  # 手续费
        self.cash += revenue
        
        pnl = (price - pos['cost']) / pos['cost']
        
        self.trades.append({
            'date': self.current_date,
            'symbol': symbol,
            'action': 'SELL',
            'price': price,
            'shares': pos['shares'],
            'pnl': pnl,
            'reason': reason
        })
        
        del self.positions[symbol]
    
    def run_live_simulation(self, start_date=None, speed=1):
        """
        模拟实盘运行
        
        Args:
            start_date: 开始日期 (None=最近1年)
            speed: 模拟速度 (1=实时, 100=100倍速)
        """
        # 选择时间范围
        if start_date:
            dates = sorted(self.data[self.data['date'] >= start_date]['date'].unique())
        else:
            # 最近3年（更多交易机会）
            max_date = self.data['date'].max()
            start = max_date - timedelta(days=1095)
            dates = sorted(self.data[self.data['date'] >= start]['date'].unique())
        
        print(f"\n模拟时间: {dates[0].date()} ~ {dates[-1].date()}")
        print(f"交易天数: {len(dates)}")
        print(f"初始资金: {self.cash:,.0f} HKD\n")
        
        peak = self.cash
        max_dd = 0
        
        for date in dates:
            self.current_date = date
            day = self.data[self.data['date'] == date]
            
            # 显示日期
            print(f"[{date.strftime('%Y-%m-%d')}] ", end='')
            
            # 计算权益
            equity = self.get_equity(date)
            peak = max(peak, equity)
            dd = (equity - peak) / peak
            max_dd = min(max_dd, dd)
            
            print(f"权益: {equity:,.0f} | 回撤: {dd*100:.1f}% | 持仓: {len(self.positions)}")
            
            # 检查持仓
            for symbol in list(self.positions.keys()):
                row = day[day['Symbol'] == symbol]
                if len(row) == 0:
                    continue
                
                price = row.iloc[0]['close']
                should_sell, reason = self.check_stop_loss(symbol, price)
                
                if should_sell:
                    self.sell(symbol, price, reason)
                    print(f"  → {NAMES.get(symbol, symbol)} {reason}")
            
            # 扫描买入信号
            for symbol in self.symbols:
                if symbol in self.positions:
                    continue
                
                if len(self.positions) >= self.config['max_positions']:
                    break
                
                row = day[day['Symbol'] == symbol]
                if len(row) == 0:
                    continue
                
                row = row.iloc[0]
                
                # 检查指标
                if pd.isna(row['MA_FAST']) or pd.isna(row['VOL_RATIO']):
                    continue
                
                # 买入信号
                if (row['MA_FAST'] > row['MA_SLOW'] and 
                    row['VOL_RATIO'] > self.config['vol_ratio']):
                    
                    if self.buy(symbol, row['close'], date):
                        print(f"  → 买入 {NAMES.get(symbol, symbol)} x{self.positions[symbol]['shares']} @ {row['close']:.2f}")
            
            # 延迟
            if speed < 100:
                time.sleep(0.1 / speed)
        
        # 最终结果
        final_equity = self.get_equity(dates[-1])
        total_return = (final_equity / 1000000) - 1
        days = (dates[-1] - dates[0]).days
        annual_return = (1 + total_return) ** (252 / days) - 1
        
        # 统计
        wins = sum(1 for t in self.trades if t.get('pnl', 0) > 0)
        losses = sum(1 for t in self.trades if t.get('pnl', 0) < 0)
        win_rate = wins / (wins + losses) if (wins + losses) > 0 else 0
        
        print("\n" + "="*80)
        print(" 模拟实盘结果")
        print("="*80)
        print(f"初始资金:   1,000,000 HKD")
        print(f"最终资金:   {final_equity:,.0f} HKD")
        print(f"累计收益:   {total_return*100:.2f}%")
        print(f"年化收益:   {annual_return*100:.2f}%")
        print(f"最大回撤:   {max_dd*100:.2f}%")
        print(f"交易次数:   {len([t for t in self.trades if t['action']=='BUY'])}")
        print(f"胜率:       {win_rate*100:.1f}%")
        print("="*80)
        
        return {
            'final_equity': final_equity,
            'total_return': total_return,
            'annual_return': annual_return,
            'max_drawdown': max_dd,
            'win_rate': win_rate,
            'trades': self.trades
        }


# ============ 运行 ============

if __name__ == "__main__":
    print("\n⚠️  这是模拟测试，不是真实交易")
    print("   用于验证策略逻辑\n")
    
    trader = MockLiveTrader(data, SYMBOLS, CONFIG)
    result = trader.run_live_simulation(speed=100)  # 100倍速
    
    # 保存交易记录
    trades_df = pd.DataFrame(result['trades'])
    trades_df.to_csv('results/mock_live_trades.csv', index=False)
    print("\n交易记录: results/mock_live_trades.csv")
