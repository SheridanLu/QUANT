#!/usr/bin/env python3
"""
富途实盘策略 - 双均线+放量
基于回测验证的有效策略

运行前确保:
1. OpenD 已启动 (127.0.0.1:11111)
2. 在交易时间 (09:30-16:00)
3. 账户有足够资金
4. 已开通港股交易权限
"""

import time
import json
from datetime import datetime, time as dt_time
from typing import Dict, List
import pandas as pd
import numpy as np

print("="*80)
print(" 富途实盘策略 - 双均线+放量")
print("="*80)

# ============ 配置 ============

CONFIG = {
    # 交易股票池
    'symbols': [
        'HK.00700',  # 腾讯
        'HK.00941',  # 中移动
        'HK.00005',  # 汇丰
        'HK.00883',  # 中海油
        'HK.01810',  # 小米
        'HK.03690',  # 美团
        'HK.00011',  # 恒生
        'HK.00016',  # 新鸿基
    ],
    
    # 策略参数
    'ma_fast': 5,
    'ma_slow': 20,
    'vol_ratio': 1.5,
    
    # 仓位控制
    'position_pct': 0.08,  # 单只8%仓位
    'max_positions': 3,     # 最多持有3只
    
    # 止损止盈
    'stop_loss': 0.06,      # 止损6%
    'take_profit': 0.12,    # 止盈12%
    
    # 交易设置
    'host': '127.0.0.1',
    'port': 11111,
}

# ============ 富途API ============

try:
    from futu import (
        OpenQuoteContext, OpenHKTradeContext, 
        RET_OK, OrderType, TrdSide, SubType
    )
    FUTU_AVAILABLE = True
    print("✓ futu-api 已安装")
except ImportError:
    FUTU_AVAILABLE = False
    print("⚠️  futu-api 未安装")
    print("   运行: pip install futu-api")

# ============ 策略类 ============

class FutuLiveTrader:
    """富途实盘交易"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.quote_ctx = None
        self.trade_ctx = None
        
        # 持仓
        self.positions = {}  # {symbol: {shares, cost}}
        self.cash = 0
        self.total_equity = 0
        
        # 历史数据缓存
        self.history = {}  # {symbol: DataFrame}
        
        # 连接
        self._connect()
    
    def _connect(self):
        """连接富途OpenD"""
        if not FUTU_AVAILABLE:
            print("⚠️  模拟模式")
            return
        
        try:
            self.quote_ctx = OpenQuoteContext(
                self.config['host'], 
                self.config['port']
            )
            self.trade_ctx = OpenHKTradeContext(
                self.config['host'],
                self.config['port']
            )
            print(f"✓ 已连接 OpenD: {self.config['host']}:{self.config['port']}")
            
            # 订阅行情
            self._subscribe()
            
            # 获取账户信息
            self._sync_account()
            
        except Exception as e:
            print(f"✗ 连接失败: {e}")
            print("   请确保 OpenD 已启动")
    
    def _subscribe(self):
        """订阅行情"""
        if not self.quote_ctx:
            return
        
        for symbol in self.config['symbols']:
            ret = self.quote_ctx.subscribe(symbol, SubType.K_DAY)
            if ret == RET_OK:
                print(f"  订阅 {symbol} ✓")
    
    def _sync_account(self):
        """同步账户信息"""
        if not self.trade_ctx:
            return
        
        # 获取资金
        ret, data = self.trade_ctx.accinfo_query()
        if ret == RET_OK:
            self.cash = data['cash'].iloc[0]
            self.total_equity = data['total_assets'].iloc[0]
            print(f"✓ 账户资金: {self.cash:,.0f} HKD")
            print(f"  总资产: {self.total_equity:,.0f} HKD")
        
        # 获取持仓
        ret, data = self.trade_ctx.position_list_query()
        if ret == RET_OK:
            for _, row in data.iterrows():
                self.positions[row['code']] = {
                    'shares': row['qty'],
                    'cost': row['cost_price'],
                    'market_value': row['market_val']
                }
            print(f"✓ 持仓: {len(self.positions)} 只")
    
    def get_history(self, symbol: str, days: int = 60) -> pd.DataFrame:
        """获取历史数据"""
        if not self.quote_ctx:
            return pd.DataFrame()
        
        ret, data = self.quote_ctx.get_history_kline(
            symbol, 
            ktype=KLType.K_DAY,
            max_count=days
        )
        
        if ret == RET_OK:
            df = data.rename(columns={
                'time_key': 'date',
                'open': 'open',
                'close': 'close',
                'high': 'high',
                'low': 'low',
                'volume': 'volume'
            })
            self.history[symbol] = df
            return df
        
        return pd.DataFrame()
    
    def calc_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算指标"""
        df = df.copy()
        
        # 均线
        df['MA_FAST'] = df['close'].rolling(self.config['ma_fast']).mean()
        df['MA_SLOW'] = df['close'].rolling(self.config['ma_slow']).mean()
        
        # 量比
        df['VOL_MA'] = df['volume'].rolling(20).mean()
        df['VOL_RATIO'] = df['volume'] / df['VOL_MA']
        
        return df
    
    def generate_signal(self, symbol: str) -> str:
        """
        生成信号
        
        Returns:
            'BUY', 'SELL', 'HOLD'
        """
        # 获取历史数据
        df = self.get_history(symbol)
        if df.empty or len(df) < 30:
            return 'HOLD'
        
        # 计算指标
        df = self.calc_indicators(df)
        
        # 最新数据
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        # 买入信号
        # 1. MA5 > MA20
        # 2. 放量 (量比 > 1.5)
        if (latest['MA_FAST'] > latest['MA_SLOW'] and 
            latest['VOL_RATIO'] > self.config['vol_ratio']):
            return 'BUY'
        
        # 卖出信号
        # 1. MA5 < MA20
        if latest['MA_FAST'] < latest['MA_SLOW']:
            return 'SELL'
        
        return 'HOLD'
    
    def check_stop_loss(self, symbol: str, current_price: float) -> bool:
        """检查止损止盈"""
        if symbol not in self.positions:
            return False
        
        pos = self.positions[symbol]
        pnl = (current_price - pos['cost']) / pos['cost']
        
        # 止损
        if pnl < -self.config['stop_loss']:
            print(f"  🛑 {symbol} 止损: {pnl*100:.2f}%")
            return True
        
        # 止盈
        if pnl > self.config['take_profit']:
            print(f"  🎯 {symbol} 止盈: {pnl*100:.2f}%")
            return True
        
        return False
    
    def buy(self, symbol: str, price: float):
        """买入"""
        if not self.trade_ctx:
            print(f"[模拟] 买入 {symbol} @ {price}")
            return
        
        # 计算仓位
        position_value = self.total_equity * self.config['position_pct']
        shares = int(position_value / price / 100) * 100  # 港股每手100股
        
        if shares <= 0:
            print(f"  资金不足，无法买入 {symbol}")
            return
        
        # 下单
        ret, data = self.trade_ctx.place_order(
            price=price,
            qty=shares,
            code=symbol,
            order_type=OrderType.MARKET,
            trd_side=TrdSide.BUY
        )
        
        if ret == RET_OK:
            print(f"✓ 买入成功: {symbol} x{shares}")
            self.positions[symbol] = {
                'shares': shares,
                'cost': price
            }
        else:
            print(f"✗ 买入失败: {data}")
    
    def sell(self, symbol: str, price: float):
        """卖出"""
        if symbol not in self.positions:
            return
        
        if not self.trade_ctx:
            print(f"[模拟] 卖出 {symbol} @ {price}")
            del self.positions[symbol]
            return
        
        shares = self.positions[symbol]['shares']
        
        ret, data = self.trade_ctx.place_order(
            price=price,
            qty=shares,
            code=symbol,
            order_type=OrderType.MARKET,
            trd_side=TrdSide.SELL
        )
        
        if ret == RET_OK:
            print(f"✓ 卖出成功: {symbol} x{shares}")
            del self.positions[symbol]
        else:
            print(f"✗ 卖出失败: {data}")
    
    def run_once(self):
        """运行一轮扫描"""
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 扫描...")
        
        for symbol in self.config['symbols']:
            # 获取当前价格
            if not self.quote_ctx:
                continue
            
            ret, data = self.quote_ctx.get_market_snapshot([symbol])
            if ret != RET_OK:
                continue
            
            current_price = data['last_price'].iloc[0]
            
            # 检查持仓止损止盈
            if symbol in self.positions:
                if self.check_stop_loss(symbol, current_price):
                    self.sell(symbol, current_price)
                    continue
            
            # 生成信号
            signal = self.generate_signal(symbol)
            
            # 执行交易
            if signal == 'BUY' and symbol not in self.positions:
                if len(self.positions) < self.config['max_positions']:
                    print(f"  📈 {symbol} 买入信号")
                    self.buy(symbol, current_price)
            
            elif signal == 'SELL' and symbol in self.positions:
                print(f"  📉 {symbol} 卖出信号")
                self.sell(symbol, current_price)
    
    def run(self, interval: int = 60):
        """
        运行主循环
        
        Args:
            interval: 扫描间隔(秒)
        """
        print("\n" + "="*80)
        print(" 开始运行")
        print(f" 股票池: {len(self.config['symbols'])} 只")
        print(f" 扫描间隔: {interval}秒")
        print("="*80)
        
        while True:
            now = datetime.now().time()
            
            # 检查是否在交易时间
            if dt_time(9, 30) <= now <= dt_time(16, 0):
                try:
                    self.run_once()
                except Exception as e:
                    print(f"错误: {e}")
            else:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 非交易时间")
            
            time.sleep(interval)


# ============ 主程序 ============

if __name__ == "__main__":
    print("\n⚠️  风险提示:")
    print("  • 这是实盘交易，有真实亏损风险")
    print("  • 建议先用小资金测试")
    print("  • 确保OpenD已运行")
    print("  • 确保在交易时间")
    
    input("\n按回车继续...")
    
    # 创建交易器
    trader = FutuLiveTrader(CONFIG)
    
    # 运行
    try:
        trader.run(interval=60)  # 每60秒扫描一次
    except KeyboardInterrupt:
        print("\n\n已停止")
