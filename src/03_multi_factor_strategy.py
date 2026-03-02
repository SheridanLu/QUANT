#!/usr/bin/env python3
"""
多因子组合策略 + 风险控制
基于前面回测结果，组合最优因子并加入风控
"""

import pandas as pd
import numpy as np
from typing import Dict, List
import warnings
warnings.filterwarnings('ignore')

class MultiFactorStrategy:
    """多因子组合策略"""
    
    def __init__(self, data_path: str = "data/combined_hk_stocks.csv"):
        self.raw_data = pd.read_csv(data_path)
        self.raw_data['date'] = pd.to_datetime(self.raw_data['date'])
        self.raw_data = self.raw_data.sort_values(['Symbol', 'date'])
        
    def calc_all_factors(self):
        """计算所有因子"""
        # 动量因子 (表现最好)
        self.raw_data['MOM_20'] = self.raw_data.groupby('Symbol')['close'].transform(
            lambda x: x / x.shift(20) - 1
        )
        self.raw_data['MOM_60'] = self.raw_data.groupby('Symbol')['close'].transform(
            lambda x: x / x.shift(60) - 1
        )
        
        # RSI
        def calc_rsi(series, window=14):
            delta = series.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window).mean()
            rs = gain / loss
            return 100 - (100 / (1 + rs))
        
        self.raw_data['RSI'] = self.raw_data.groupby('Symbol')['close'].transform(
            lambda x: calc_rsi(x, 14)
        )
        
        # 布林带位置
        self.raw_data['MA20'] = self.raw_data.groupby('Symbol')['close'].transform(
            lambda x: x.rolling(20).mean()
        )
        self.raw_data['STD20'] = self.raw_data.groupby('Symbol')['close'].transform(
            lambda x: x.rolling(20).std()
        )
        self.raw_data['BOLL_PCT'] = (self.raw_data['close'] - self.raw_data['MA20']) / (2 * self.raw_data['STD20'])
        
        # 波动率
        self.raw_data['VOL'] = self.raw_data.groupby('Symbol')['close'].transform(
            lambda x: x.pct_change().rolling(20).std() * np.sqrt(252)
        )
        
        # 成交量因子
        self.raw_data['VOL_RATIO'] = self.raw_data.groupby('Symbol')['volume'].transform(
            lambda x: x / x.rolling(20).mean()
        )
        
        # 均线系统
        self.raw_data['MA5'] = self.raw_data.groupby('Symbol')['close'].transform(
            lambda x: x.rolling(5).mean()
        )
        self.raw_data['MA10'] = self.raw_data.groupby('Symbol')['close'].transform(
            lambda x: x.rolling(10).mean()
        )
        self.raw_data['MA60'] = self.raw_data.groupby('Symbol')['close'].transform(
            lambda x: x.rolling(60).mean()
        )
        
        print("所有因子计算完成")
        return self.raw_data
    
    def generate_combined_signal(self):
        """
        组合信号生成
        基于回测结果，给不同因子赋权重
        """
        # 因子打分 (0-100)
        self.raw_data['SCORE'] = 0
        
        # 1. 动量因子 (权重40%) - 表现最好
        self.raw_data['MOM_SCORE'] = 0
        self.raw_data.loc[self.raw_data['MOM_20'] > 0.10, 'MOM_SCORE'] = 40
        self.raw_data.loc[self.raw_data['MOM_20'] > 0.05, 'MOM_SCORE'] = 30
        self.raw_data.loc[self.raw_data['MOM_20'] > 0, 'MOM_SCORE'] = 20
        self.raw_data.loc[self.raw_data['MOM_20'] < -0.05, 'MOM_SCORE'] = -20
        self.raw_data.loc[self.raw_data['MOM_20'] < -0.10, 'MOM_SCORE'] = -40
        
        # 2. 均线排列 (权重25%)
        self.raw_data['MA_SCORE'] = 0
        ma_bull = (
            (self.raw_data['MA5'] > self.raw_data['MA10']) & 
            (self.raw_data['MA10'] > self.raw_data['MA20']) &
            (self.raw_data['MA20'] > self.raw_data['MA60'])
        )
        ma_bear = (
            (self.raw_data['MA5'] < self.raw_data['MA10']) & 
            (self.raw_data['MA10'] < self.raw_data['MA20']) &
            (self.raw_data['MA20'] < self.raw_data['MA60'])
        )
        self.raw_data.loc[ma_bull, 'MA_SCORE'] = 25
        self.raw_data.loc[ma_bear, 'MA_SCORE'] = -25
        
        # 3. RSI因子 (权重15%)
        self.raw_data['RSI_SCORE'] = 0
        self.raw_data.loc[self.raw_data['RSI'] < 30, 'RSI_SCORE'] = 15  # 超卖
        self.raw_data.loc[self.raw_data['RSI'] < 40, 'RSI_SCORE'] = 10
        self.raw_data.loc[self.raw_data['RSI'] > 70, 'RSI_SCORE'] = -15  # 超买
        self.raw_data.loc[self.raw_data['RSI'] > 60, 'RSI_SCORE'] = -10
        
        # 4. 布林带位置 (权重10%)
        self.raw_data['BOLL_SCORE'] = 0
        self.raw_data.loc[self.raw_data['BOLL_PCT'] < -1, 'BOLL_SCORE'] = 10  # 低于下轨
        self.raw_data.loc[self.raw_data['BOLL_PCT'] < -0.5, 'BOLL_SCORE'] = 5
        self.raw_data.loc[self.raw_data['BOLL_PCT'] > 1, 'BOLL_SCORE'] = -10  # 高于上轨
        self.raw_data.loc[self.raw_data['BOLL_PCT'] > 0.5, 'BOLL_SCORE'] = -5
        
        # 5. 成交量确认 (权重10%)
        self.raw_data['VOL_SCORE'] = 0
        self.raw_data.loc[self.raw_data['VOL_RATIO'] > 2, 'VOL_SCORE'] = 10  # 放量
        self.raw_data.loc[self.raw_data['VOL_RATIO'] > 1.5, 'VOL_SCORE'] = 5
        self.raw_data.loc[self.raw_data['VOL_RATIO'] < 0.5, 'VOL_SCORE'] = -5  # 缩量
        
        # 总分
        self.raw_data['TOTAL_SCORE'] = (
            self.raw_data['MOM_SCORE'] + 
            self.raw_data['MA_SCORE'] + 
            self.raw_data['RSI_SCORE'] + 
            self.raw_data['BOLL_SCORE'] + 
            self.raw_data['VOL_SCORE']
        )
        
        # 生成信号 (用整数表示: 2=强买, 1=弱买, 0=持有, -1=弱卖, -2=强卖)
        self.raw_data['COMBO_SIGNAL'] = 0
        self.raw_data.loc[self.raw_data['TOTAL_SCORE'] >= 50, 'COMBO_SIGNAL'] = 2   # 强买入
        self.raw_data.loc[self.raw_data['TOTAL_SCORE'] >= 30, 'COMBO_SIGNAL'] = 1   # 弱买入
        self.raw_data.loc[self.raw_data['TOTAL_SCORE'] <= -50, 'COMBO_SIGNAL'] = -2  # 强卖出
        self.raw_data.loc[self.raw_data['TOTAL_SCORE'] <= -30, 'COMBO_SIGNAL'] = -1  # 弱卖出
        
        return self.raw_data


class RiskManager:
    """风险管理模块"""
    
    def __init__(self, max_drawdown: float = -0.15, max_position: float = 0.20):
        """
        Args:
            max_drawdown: 最大允许回撤
            max_position: 单只股票最大仓位
        """
        self.max_drawdown = max_drawdown
        self.max_position = max_position
    
    def check_drawdown(self, equity_curve: pd.Series) -> bool:
        """检查是否触及止损线"""
        cummax = equity_curve.cummax()
        drawdown = (equity_curve - cummax) / cummax
        current_dd = drawdown.iloc[-1]
        return current_dd < self.max_drawdown
    
    def calc_position_size(
        self, 
        capital: float, 
        price: float, 
        volatility: float,
        target_vol: float = 0.20
    ) -> int:
        """
        波动率调整仓位
        """
        if volatility <= 0:
            return int(capital * self.max_position / price)
        
        # 根据波动率调整仓位
        vol_adjusted_position = target_vol / volatility
        position_pct = min(vol_adjusted_position, self.max_position)
        
        return int(capital * position_pct / price)


def backtest_with_risk_control(
    data: pd.DataFrame,
    signal_col: str = 'COMBO_SIGNAL',
    initial_capital: float = 1000000,
    commission: float = 0.003,
    max_drawdown_stop: float = -0.20,
    max_position: float = 0.15,
) -> Dict:
    """
    带风控的回测
    """
    print(f"\n回测策略: {signal_col} (带风控)")
    print("-" * 50)
    
    risk_mgr = RiskManager(max_drawdown=max_drawdown_stop, max_position=max_position)
    
    all_results = []
    
    for symbol in data['Symbol'].unique():
        df = data[data['Symbol'] == symbol].copy().reset_index(drop=True)
        
        if signal_col not in df.columns:
            continue
        
        capital = initial_capital / len(data['Symbol'].unique())  # 分配资金
        cash = capital
        position = 0
        equity_curve = []
        stopped = False
        
        for i, row in df.iterrows():
            if stopped:
                break
            
            signal = row.get(signal_col, 0)
            price = row['close']
            vol = row.get('VOL', 0.3)
            
            # 计算当前权益
            equity = cash + position * price
            equity_curve.append(equity)
            
            # 检查是否触及止损
            if len(equity_curve) > 20:
                eq_series = pd.Series(equity_curve)
                if risk_mgr.check_drawdown(eq_series):
                    # 清仓止损
                    if position > 0:
                        cash += position * price * (1 - commission)
                        position = 0
                    stopped = True
                    continue
            
            # 交易逻辑 (signal: 2=强买, 1=弱买, 0=持有, -1=弱卖, -2=强卖)
            if signal >= 1 and position == 0:  # 买入信号
                shares = risk_mgr.calc_position_size(cash, price, vol)
                if shares > 0:
                    cost = shares * price * (1 + commission)
                    if cost <= cash:
                        position = shares
                        cash -= cost
            
            elif signal <= -1 and position > 0:  # 卖出信号
                revenue = position * price * (1 - commission)
                cash += revenue
                position = 0
        
        # 最终平仓
        if position > 0:
            last_price = df.iloc[-1]['close']
            cash += position * last_price * (1 - commission)
        
        all_results.append({
            'symbol': symbol,
            'final_equity': cash,
            'stopped': stopped
        })
    
    # 汇总
    total_equity = sum(r['final_equity'] for r in all_results)
    total_return = (total_equity / initial_capital) - 1
    
    # 计算综合指标
    days = (data['date'].max() - data['date'].min()).days
    annual_return = (1 + total_return) ** (252 / max(days, 1)) - 1
    
    stopped_count = sum(1 for r in all_results if r['stopped'])
    
    return {
        'initial_capital': initial_capital,
        'final_equity': total_equity,
        'total_return': total_return,
        'annual_return': annual_return,
        'stopped_count': stopped_count,
        'total_stocks': len(all_results),
        'results': all_results
    }


def main():
    print("=" * 60)
    print(" 多因子组合策略 + 风险控制")
    print("=" * 60)
    
    # 初始化
    strategy = MultiFactorStrategy("data/combined_hk_stocks.csv")
    
    # 计算因子
    strategy.calc_all_factors()
    
    # 生成组合信号
    strategy.generate_combined_signal()
    
    # 保存带因子的数据
    strategy.raw_data.to_csv("data/stocks_with_factors.csv", index=False)
    print("因子数据已保存: data/stocks_with_factors.csv")
    
    # 回测
    results = backtest_with_risk_control(
        strategy.raw_data,
        signal_col='COMBO_SIGNAL',
        initial_capital=1000000,
        max_drawdown_stop=-0.20,
        max_position=0.15
    )
    
    # 输出结果
    print("\n" + "=" * 60)
    print(" 多因子组合策略回测结果")
    print("=" * 60)
    print(f"初始资金:     {results['initial_capital']:,.2f} HKD")
    print(f"最终资金:     {results['final_equity']:,.2f} HKD")
    print(f"累计收益率:   {results['total_return']*100:.2f}%")
    print(f"年化收益率:   {results['annual_return']*100:.2f}%")
    print(f"触发止损股票: {results['stopped_count']}/{results['total_stocks']}")
    print("=" * 60)
    
    return strategy, results


if __name__ == "__main__":
    strategy, results = main()
