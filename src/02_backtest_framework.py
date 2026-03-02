#!/usr/bin/env python3
"""
港股回测框架
支持因子计算、策略回测、绩效分析
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional
import warnings
warnings.filterwarnings('ignore')


class HKBacktestEngine:
    """港股回测引擎"""
    
    def __init__(self, data_path: str = "data/combined_hk_stocks.csv"):
        """
        初始化回测引擎
        
        Args:
            data_path: 数据文件路径
        """
        self.raw_data = pd.read_csv(data_path)
        self.raw_data['date'] = pd.to_datetime(self.raw_data['date'])
        self.raw_data = self.raw_data.sort_values(['Symbol', 'date'])
        
        # 数据清洗
        self.raw_data['volume'] = self.raw_data['volume'].fillna(0)
        self.raw_data = self.raw_data.dropna(subset=['open', 'high', 'low', 'close'])
        
        # 存储计算结果
        self.factor_data = {}
        self.signals = {}
        self.positions = {}
        self.portfolio_returns = None
        
    # ==================== 技术指标计算 ====================
    
    def calc_ma(self, window: int = 20) -> pd.DataFrame:
        """计算移动平均线"""
        self.raw_data[f'MA{window}'] = self.raw_data.groupby('Symbol')['close'].transform(
            lambda x: x.rolling(window).mean()
        )
        return self.raw_data
    
    def calc_rsi(self, window: int = 14) -> pd.DataFrame:
        """计算 RSI"""
        def _rsi(series, window):
            delta = series.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window).mean()
            rs = gain / loss
            return 100 - (100 / (1 + rs))
        
        self.raw_data['RSI'] = self.raw_data.groupby('Symbol')['close'].transform(
            lambda x: _rsi(x, window)
        )
        return self.raw_data
    
    def calc_macd(self, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
        """计算 MACD"""
        def _macd(group):
            ema_fast = group['close'].ewm(span=fast).mean()
            ema_slow = group['close'].ewm(span=slow).mean()
            macd = ema_fast - ema_slow
            signal_line = macd.ewm(span=signal).mean()
            hist = macd - signal_line
            return pd.DataFrame({
                'MACD': macd,
                'MACD_SIGNAL': signal_line,
                'MACD_HIST': hist
            })
        
        macd_df = self.raw_data.groupby('Symbol').apply(_macd).reset_index(drop=True)
        self.raw_data = pd.concat([self.raw_data.reset_index(drop=True), macd_df], axis=1)
        return self.raw_data
    
    def calc_bollinger(self, window: int = 20, num_std: float = 2.0) -> pd.DataFrame:
        """计算布林带"""
        def _bollinger(group):
            mid = group['close'].rolling(window).mean()
            std = group['close'].rolling(window).std()
            return pd.DataFrame({
                'BOLL_MID': mid,
                'BOLL_UP': mid + num_std * std,
                'BOLL_DOWN': mid - num_std * std
            })
        
        boll_df = self.raw_data.groupby('Symbol').apply(_bollinger).reset_index(drop=True)
        self.raw_data = pd.concat([self.raw_data.reset_index(drop=True), boll_df], axis=1)
        return self.raw_data
    
    def calc_atr(self, window: int = 14) -> pd.DataFrame:
        """计算 ATR (Average True Range)"""
        def _atr(group):
            high = group['high']
            low = group['low']
            close = group['close'].shift(1)
            
            tr1 = high - low
            tr2 = abs(high - close)
            tr3 = abs(low - close)
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(window).mean()
            return atr
        
        self.raw_data['ATR'] = self.raw_data.groupby('Symbol', group_keys=False).apply(_atr)
        return self.raw_data
    
    def calc_momentum(self, window: int = 20) -> pd.DataFrame:
        """计算动量因子"""
        self.raw_data['MOMENTUM'] = self.raw_data.groupby('Symbol')['close'].transform(
            lambda x: x / x.shift(window) - 1
        )
        return self.raw_data
    
    def calc_volatility(self, window: int = 20) -> pd.DataFrame:
        """计算波动率"""
        self.raw_data['VOLATILITY'] = self.raw_data.groupby('Symbol')['close'].transform(
            lambda x: x.pct_change().rolling(window).std() * np.sqrt(252)
        )
        return self.raw_data
    
    def calc_volume_ratio(self, window: int = 20) -> pd.DataFrame:
        """计算量比"""
        self.raw_data['VOL_RATIO'] = self.raw_data.groupby('Symbol')['volume'].transform(
            lambda x: x / x.rolling(window).mean()
        )
        return self.raw_data
    
    def calc_all_indicators(self):
        """计算所有技术指标"""
        print("计算技术指标...")
        self.calc_ma(5)
        self.calc_ma(10)
        self.calc_ma(20)
        self.calc_ma(60)
        self.calc_rsi(14)
        self.calc_macd()
        self.calc_bollinger()
        self.calc_atr()
        self.calc_momentum(20)
        self.calc_volatility(20)
        self.calc_volume_ratio(20)
        print("技术指标计算完成!")
        return self.raw_data
    
    # ==================== 信号生成 ====================
    
    def generate_signal_ma_cross(self, fast: int = 5, slow: int = 20) -> pd.DataFrame:
        """
        均线交叉策略
        快线上穿慢线 -> 买入 (1)
        快线下穿慢线 -> 卖出 (-1)
        """
        fast_col = f'MA{fast}'
        slow_col = f'MA{slow}'
        
        if fast_col not in self.raw_data.columns:
            self.calc_ma(fast)
        if slow_col not in self.raw_data.columns:
            self.calc_ma(slow)
        
        # 信号
        self.raw_data['MA_CROSS_SIGNAL'] = 0
        self.raw_data.loc[
            self.raw_data[fast_col] > self.raw_data[slow_col], 'MA_CROSS_SIGNAL'
        ] = 1
        self.raw_data.loc[
            self.raw_data[fast_col] < self.raw_data[slow_col], 'MA_CROSS_SIGNAL'
        ] = -1
        
        return self.raw_data
    
    def generate_signal_rsi(self, oversold: float = 30, overbought: float = 70) -> pd.DataFrame:
        """
        RSI 策略
        RSI < 30 -> 超卖 -> 买入 (1)
        RSI > 70 -> 超买 -> 卖出 (-1)
        """
        if 'RSI' not in self.raw_data.columns:
            self.calc_rsi()
        
        self.raw_data['RSI_SIGNAL'] = 0
        self.raw_data.loc[self.raw_data['RSI'] < oversold, 'RSI_SIGNAL'] = 1
        self.raw_data.loc[self.raw_data['RSI'] > overbought, 'RSI_SIGNAL'] = -1
        
        return self.raw_data
    
    def generate_signal_macd(self) -> pd.DataFrame:
        """
        MACD 策略
        MACD 上穿信号线 -> 买入 (1)
        MACD 下穿信号线 -> 卖出 (-1)
        """
        if 'MACD' not in self.raw_data.columns:
            self.calc_macd()
        
        self.raw_data['MACD_SIGNAL_GEN'] = 0
        # MACD > Signal -> 看多
        self.raw_data.loc[
            self.raw_data['MACD'] > self.raw_data['MACD_SIGNAL'], 'MACD_SIGNAL_GEN'
        ] = 1
        self.raw_data.loc[
            self.raw_data['MACD'] < self.raw_data['MACD_SIGNAL'], 'MACD_SIGNAL_GEN'
        ] = -1
        
        return self.raw_data
    
    def generate_signal_bollinger(self) -> pd.DataFrame:
        """
        布林带策略
        价格触及下轨 -> 买入 (1)
        价格触及上轨 -> 卖出 (-1)
        """
        if 'BOLL_DOWN' not in self.raw_data.columns:
            self.calc_bollinger()
        
        self.raw_data['BOLL_SIGNAL'] = 0
        self.raw_data.loc[
            self.raw_data['close'] <= self.raw_data['BOLL_DOWN'], 'BOLL_SIGNAL'
        ] = 1
        self.raw_data.loc[
            self.raw_data['close'] >= self.raw_data['BOLL_UP'], 'BOLL_SIGNAL'
        ] = -1
        
        return self.raw_data
    
    def generate_signal_momentum(self, threshold: float = 0.05) -> pd.DataFrame:
        """
        动量策略
        动量 > threshold -> 买入 (1)
        动量 < -threshold -> 卖出 (-1)
        """
        if 'MOMENTUM' not in self.raw_data.columns:
            self.calc_momentum()
        
        self.raw_data['MOM_SIGNAL'] = 0
        self.raw_data.loc[self.raw_data['MOMENTUM'] > threshold, 'MOM_SIGNAL'] = 1
        self.raw_data.loc[self.raw_data['MOMENTUM'] < -threshold, 'MOM_SIGNAL'] = -1
        
        return self.raw_data
    
    # ==================== 回测核心 ====================
    
    def backtest_single_strategy(
        self, 
        signal_col: str,
        initial_capital: float = 1000000,
        commission_rate: float = 0.003,
        slippage: float = 0.001,
        position_size: float = 0.95,  # 仓位比例
    ) -> Dict:
        """
        回测单个策略
        
        Args:
            signal_col: 信号列名
            initial_capital: 初始资金
            commission_rate: 佣金率
            slippage: 滑点
            position_size: 仓位比例
        
        Returns:
            回测结果字典
        """
        print(f"\n开始回测策略: {signal_col}")
        print("-" * 50)
        
        # 按股票分组回测
        all_results = []
        
        for symbol in self.raw_data['Symbol'].unique():
            df = self.raw_data[self.raw_data['Symbol'] == symbol].copy()
            df = df.sort_values('date').reset_index(drop=True)
            
            if signal_col not in df.columns:
                continue
            
            # 模拟交易
            capital = initial_capital
            position = 0  # 持仓股数
            cash = capital
            trades = []
            equity_curve = []
            
            for i, row in df.iterrows():
                signal = row[signal_col]
                price = row['close']
                date = row['date']
                
                # 买入
                if signal == 1 and position == 0 and not np.isnan(price):
                    shares = int(cash * position_size / price)
                    if shares > 0:
                        cost = shares * price * (1 + commission_rate + slippage)
                        if cost <= cash:
                            position = shares
                            cash -= cost
                            trades.append({
                                'date': date,
                                'type': 'BUY',
                                'price': price,
                                'shares': shares,
                                'value': cost
                            })
                
                # 卖出
                elif signal == -1 and position > 0 and not np.isnan(price):
                    revenue = position * price * (1 - commission_rate - slippage)
                    cash += revenue
                    trades.append({
                        'date': date,
                        'type': 'SELL',
                        'price': price,
                        'shares': position,
                        'value': revenue
                    })
                    position = 0
                
                # 记录权益
                equity = cash + position * price
                equity_curve.append({
                    'date': date,
                    'equity': equity,
                    'Symbol': symbol
                })
            
            # 最终平仓
            if position > 0:
                last_price = df.iloc[-1]['close']
                revenue = position * last_price * (1 - commission_rate)
                cash += revenue
                position = 0
            
            final_equity = cash
            
            if equity_curve:
                equity_df = pd.DataFrame(equity_curve)
                all_results.append({
                    'symbol': symbol,
                    'final_equity': final_equity,
                    'equity_curve': equity_df,
                    'trades': trades
                })
        
        # 合并所有股票的结果
        if all_results:
            return self._calculate_metrics(all_results, initial_capital)
        else:
            return {'error': '无有效回测结果'}
    
    def _calculate_metrics(self, results: List[Dict], initial_capital: float) -> Dict:
        """计算绩效指标"""
        
        # 合并权益曲线
        all_equity = pd.concat([r['equity_curve'] for r in results])
        all_equity = all_equity.groupby('date')['equity'].sum().reset_index()
        all_equity = all_equity.sort_values('date')
        
        # 计算收益率
        all_equity['returns'] = all_equity['equity'].pct_change()
        
        # 基本指标
        final_equity = all_equity['equity'].iloc[-1]
        total_return = (final_equity / initial_capital) - 1
        days = (all_equity['date'].iloc[-1] - all_equity['date'].iloc[0]).days
        annual_return = (1 + total_return) ** (252 / max(days, 1)) - 1 if days > 0 else 0
        
        # 最大回撤
        all_equity['cummax'] = all_equity['equity'].cummax()
        all_equity['drawdown'] = (all_equity['equity'] - all_equity['cummax']) / all_equity['cummax']
        max_drawdown = all_equity['drawdown'].min()
        
        # 夏普比率
        risk_free_rate = 0.02  # 无风险利率
        excess_returns = all_equity['returns'].dropna() - risk_free_rate / 252
        sharpe_ratio = np.sqrt(252) * excess_returns.mean() / excess_returns.std() if excess_returns.std() > 0 else 0
        
        # Calmar 比率
        calmar_ratio = annual_return / abs(max_drawdown) if max_drawdown != 0 else 0
        
        # 胜率
        all_trades = []
        for r in results:
            all_trades.extend(r['trades'])
        
        winning_trades = 0
        total_trades = 0
        for i in range(0, len(all_trades) - 1, 2):
            if i + 1 < len(all_trades):
                buy = all_trades[i]
                sell = all_trades[i + 1]
                if buy['type'] == 'BUY' and sell['type'] == 'SELL':
                    total_trades += 1
                    if sell['value'] > buy['value']:
                        winning_trades += 1
        
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        
        return {
            'initial_capital': initial_capital,
            'final_equity': final_equity,
            'total_return': total_return,
            'annual_return': annual_return,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'calmar_ratio': calmar_ratio,
            'win_rate': win_rate,
            'total_trades': total_trades,
            'equity_curve': all_equity,
            'results_by_symbol': results
        }
    
    def print_metrics(self, metrics: Dict, strategy_name: str = "Strategy"):
        """打印回测结果"""
        print("\n" + "=" * 60)
        print(f" {strategy_name} 回测结果")
        print("=" * 60)
        print(f"初始资金:     {metrics['initial_capital']:,.2f} HKD")
        print(f"最终资金:     {metrics['final_equity']:,.2f} HKD")
        print(f"累计收益率:   {metrics['total_return']*100:.2f}%")
        print(f"年化收益率:   {metrics['annual_return']*100:.2f}%")
        print(f"最大回撤:     {metrics['max_drawdown']*100:.2f}%")
        print(f"夏普比率:     {metrics['sharpe_ratio']:.3f}")
        print(f"Calmar比率:   {metrics['calmar_ratio']:.3f}")
        print(f"胜率:         {metrics['win_rate']*100:.2f}%")
        print(f"交易次数:     {metrics['total_trades']}")
        print("=" * 60)


# ==================== 主程序 ====================

def main():
    print("=" * 60)
    print(" 港股量化回测系统")
    print(" 时间:", pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 60)
    
    # 初始化引擎
    engine = HKBacktestEngine("data/combined_hk_stocks.csv")
    
    # 计算所有指标
    engine.calc_all_indicators()
    
    # 生成各种策略信号
    print("\n生成交易信号...")
    engine.generate_signal_ma_cross(5, 20)
    engine.generate_signal_ma_cross(10, 60)
    engine.generate_signal_rsi(30, 70)
    engine.generate_signal_macd()
    engine.generate_signal_bollinger()
    engine.generate_signal_momentum(0.05)
    
    # 回测各策略
    strategies = [
        ('MA_CROSS_SIGNAL', 'MA5/20 均线交叉'),
        ('RSI_SIGNAL', 'RSI 超买超卖'),
        ('MACD_SIGNAL_GEN', 'MACD 策略'),
        ('BOLL_SIGNAL', '布林带策略'),
        ('MOM_SIGNAL', '动量策略'),
    ]
    
    all_results = {}
    
    for signal_col, name in strategies:
        if signal_col in engine.raw_data.columns:
            metrics = engine.backtest_single_strategy(signal_col)
            engine.print_metrics(metrics, name)
            all_results[name] = metrics
    
    # 找出最佳策略
    print("\n" + "=" * 60)
    print(" 策略对比")
    print("=" * 60)
    
    comparison = []
    for name, metrics in all_results.items():
        if 'error' not in metrics:
            comparison.append({
                '策略': name,
                '年化收益率': f"{metrics['annual_return']*100:.2f}%",
                '夏普比率': f"{metrics['sharpe_ratio']:.3f}",
                '最大回撤': f"{metrics['max_drawdown']*100:.2f}%",
                '胜率': f"{metrics['win_rate']*100:.2f}%",
            })
    
    if comparison:
        df_compare = pd.DataFrame(comparison)
        print(df_compare.to_string(index=False))
    
    print("\n回测完成!")
    return engine, all_results


if __name__ == "__main__":
    engine, results = main()
