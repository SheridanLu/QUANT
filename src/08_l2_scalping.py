#!/usr/bin/env python3
"""
富途L2短线策略 - 高频日内交易
利用L2深度数据做短线
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from datetime import datetime, time
import warnings
warnings.filterwarnings('ignore')

"""
富途L2行情特点：
1. 10档买卖盘深度
2. 经纪商队列（看谁在买卖）
3. 实时分笔成交
4. 更新频率快（毫秒级）

短线核心：
- 看大单动向
- 跟主力资金
- 秒级反应
- 快进快出
"""

class L2ScalpingStrategy:
    """L2短线策略"""
    
    def __init__(self):
        self.MIN_AMOUNT = 50_000_000  # 最小成交额5000万（流动性）
        self.MIN_VOL_RATIO = 2.0      # 量比>2（活跃）
        self.MAX_SPREAD = 0.002       # 买卖价差<0.2%（流动性好）
        self.STOP_LOSS = 0.02         # 止损2%（短线更严格）
        self.TAKE_PROFIT = 0.03       # 止盈3%（快进快出）
        
    def analyze_order_book(self, order_book: Dict) -> str:
        """
        分析L2订单簿
        
        Args:
            order_book: L2深度数据
                - bid: 买盘10档 [(price, volume), ...]
                - ask: 卖盘10档 [(price, volume), ...]
        
        Returns:
            'BUY', 'SELL', 'HOLD'
        """
        bid = order_book.get('bid', [])  # 买盘
        ask = order_book.get('ask', [])  # 卖盘
        
        if not bid or not ask:
            return 'HOLD'
        
        # 1. 买卖盘力量对比
        bid_volume = sum(v for _, v in bid[:5])  # 前5档买单量
        ask_volume = sum(v for _, v in ask[:5])  # 前5档卖单量
        
        volume_ratio = bid_volume / (bid_volume + ask_volume)
        
        # 买盘力量 > 70%
        if volume_ratio > 0.7:
            return 'BUY'
        # 卖盘力量 > 70%
        elif volume_ratio < 0.3:
            return 'SELL'
        
        return 'HOLD'
    
    def analyze_big_orders(self, trades: List[Dict]) -> str:
        """
        分析大单成交
        
        Args:
            trades: 分笔成交数据
                - price: 成交价
                - volume: 成交量
                - direction: 买/卖方向
        
        Returns:
            'BUY', 'SELL', 'HOLD'
        """
        if not trades:
            return 'HOLD'
        
        # 统计大单
        big_buy_volume = 0
        big_sell_volume = 0
        
        for trade in trades[-50:]:  # 最近50笔
            volume = trade.get('volume', 0)
            direction = trade.get('direction', '')
            
            # 大单定义：成交额>50万
            if volume * trade.get('price', 0) > 500_000:
                if direction == 'BUY':
                    big_buy_volume += volume
                else:
                    big_sell_volume += volume
        
        # 大单净买入
        net_big = big_buy_volume - big_sell_volume
        
        if net_big > 0:
            return 'BUY'
        elif net_big < 0:
            return 'SELL'
        
        return 'HOLD'
    
    def analyze_broker_queue(self, queue: Dict) -> str:
        """
        分析经纪商队列
        
        Args:
            queue: 经纪商数据
                - bid_brokers: 买盘经纪商
                - ask_brokers: 卖盘经纪商
        
        Returns:
            'BUY', 'SELL', 'HOLD'
        """
        bid_brokers = queue.get('bid_brokers', [])
        ask_brokers = queue.get('ask_brokers', [])
        
        # 识别主力经纪商（大券商）
        big_brokers = {
            '高盛', '摩根士丹利', '瑞银', '花旗', '摩根大通',
            '中金', '中信', '海通', '国泰君安', '华泰'
        }
        
        big_bid = sum(1 for b in bid_brokers if b in big_brokers)
        big_ask = sum(1 for b in ask_brokers if b in big_brokers)
        
        if big_bid > big_ask + 2:
            return 'BUY'
        elif big_ask > big_bid + 2:
            return 'SELL'
        
        return 'HOLD'
    
    def generate_signal(
        self,
        order_book: Dict,
        trades: List[Dict],
        broker_queue: Dict,
        price_data: Dict
    ) -> Tuple[str, float]:
        """
        综合信号
        
        Returns:
            (action, confidence)
        """
        # 1. 订单簿分析
        ob_signal = self.analyze_order_book(order_book)
        
        # 2. 大单分析
        big_signal = self.analyze_big_orders(trades)
        
        # 3. 经纪商分析
        broker_signal = self.analyze_broker_queue(broker_queue)
        
        # 4. 价格动量
        close = price_data.get('close', [])
        if len(close) >= 5:
            mom = (close[-1] - close[-5]) / close[-5]
        else:
            mom = 0
        
        # 投票
        buy_votes = sum([ob_signal == 'BUY', big_signal == 'BUY', broker_signal == 'BUY'])
        sell_votes = sum([ob_signal == 'SELL', big_signal == 'SELL', broker_signal == 'SELL'])
        
        # 决策
        if buy_votes >= 2 and mom > 0:
            confidence = buy_votes / 3.0
            return 'BUY', confidence
        elif sell_votes >= 2 and mom < 0:
            confidence = sell_votes / 3.0
            return 'SELL', confidence
        
        return 'HOLD', 0


class FutuL2Trader:
    """富途L2实盘交易"""
    
    def __init__(self, host='127.0.0.1', port=11111):
        self.host = host
        self.port = port
        
        # 策略
        self.strategy = L2ScalpingStrategy()
        
        # 持仓
        self.positions = {}
        self.entry_price = {}
        self.entry_time = {}
        
        # 风控
        self.MAX_HOLDING_TIME = 30 * 60  # 最长持有30分钟
        self.MAX_POSITION = 0.05         # 单只5%仓位
        self.STOP_LOSS = 0.02            # 止损2%
        self.TAKE_PROFIT = 0.03          # 止盈3%
        
        # 连接富途
        self._connect()
    
    def _connect(self):
        """连接富途OpenD"""
        try:
            from futu import OpenQuoteContext, OpenHKTradeContext
            
            self.quote_ctx = OpenQuoteContext(self.host, self.port)
            self.trade_ctx = OpenHKTradeContext(self.host, self.port)
            
            print(f"✓ 已连接富途L2: {self.host}:{self.port}")
            print("  确保已订阅L2行情")
            
        except Exception as e:
            print(f"⚠️  连接失败: {e}")
            self._mock_mode = True
    
    def subscribe_l2(self, symbols: List[str]):
        """订阅L2行情"""
        if self._mock_mode:
            return
        
        try:
            from futu import SubType
            
            for symbol in symbols:
                # 订阅K线
                self.quote_ctx.subscribe(symbol, SubType.K_1M)
                # 订阅实时数据
                self.quote_ctx.subscribe(symbol, SubType.QUOTE)
                # 订阅深度
                self.quote_ctx.subscribe(symbol, SubType.ORDER_BOOK)
                # 订阅分笔
                self.quote_ctx.subscribe(symbol, SubType.TICKER)
                
            print(f"✓ 已订阅 {len(symbols)} 只股票的L2行情")
            
        except Exception as e:
            print(f"订阅失败: {e}")
    
    def get_order_book(self, symbol: str) -> Dict:
        """获取L2订单簿"""
        if self._mock_mode:
            return {'bid': [], 'ask': []}
        
        try:
            from futu import RetDef
            
            ret, data = self.quote_ctx.get_order_book(symbol)
            if ret == RetDef.RET_OK:
                return {
                    'bid': [(r['price'], r['volume']) for _, r in data.iterrows() if r['side'] == 'BID'],
                    'ask': [(r['price'], r['volume']) for _, r in data.iterrows() if r['side'] == 'ASK']
                }
        except:
            pass
        
        return {'bid': [], 'ask': []}
    
    def get_trades(self, symbol: str) -> List[Dict]:
        """获取分笔成交"""
        if self._mock_mode:
            return []
        
        try:
            ret, data = self.quote_ctx.get_rt_ticker(symbol, 100)
            if ret == 0:
                return [
                    {
                        'price': r['price'],
                        'volume': r['volume'],
                        'direction': 'BUY' if r['ticker_direction'] == 1 else 'SELL'
                    }
                    for _, r in data.iterrows()
                ]
        except:
            pass
        
        return []
    
    def get_broker_queue(self, symbol: str) -> Dict:
        """获取经纪商队列"""
        # 富途需要特殊接口
        return {'bid_brokers': [], 'ask_brokers': []}
    
    def run_single(self, symbol: str):
        """运行单只股票"""
        import time
        
        # 获取数据
        order_book = self.get_order_book(symbol)
        trades = self.get_trades(symbol)
        broker_queue = self.get_broker_queue(symbol)
        
        # 获取价格
        price_data = {'close': []}
        try:
            ret, data = self.quote_ctx.get_market_snapshot([symbol])
            if ret == 0:
                price_data['close'] = [data['last_price'].iloc[0]]
        except:
            pass
        
        # 生成信号
        action, confidence = self.strategy.generate_signal(
            order_book, trades, broker_queue, price_data
        )
        
        # 执行交易
        if action == 'BUY' and symbol not in self.positions:
            self._buy(symbol, confidence)
        elif action == 'SELL' and symbol in self.positions:
            self._sell(symbol)
        
        # 检查止损止盈
        if symbol in self.positions:
            self._check_exit(symbol, price_data['close'][-1] if price_data['close'] else 0)
    
    def _buy(self, symbol: str, confidence: float):
        """买入"""
        # 实现买入逻辑
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 买入信号 {symbol} 置信度{confidence:.2f}")
    
    def _sell(self, symbol: str):
        """卖出"""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 卖出信号 {symbol}")
    
    def _check_exit(self, symbol: str, current_price: float):
        """检查止损止盈"""
        if symbol not in self.entry_price:
            return
        
        pnl = (current_price - self.entry_price[symbol]) / self.entry_price[symbol]
        
        # 止损
        if pnl < -self.STOP_LOSS:
            self._sell(symbol)
            print(f"  → 止损 {pnl*100:.2f}%")
        
        # 止盈
        elif pnl > self.TAKE_PROFIT:
            self._sell(symbol)
            print(f"  → 止盈 {pnl*100:.2f}%")
        
        # 超时平仓
        elif symbol in self.entry_time:
            hold_time = (datetime.now() - self.entry_time[symbol]).seconds
            if hold_time > self.MAX_HOLDING_TIME:
                self._sell(symbol)
                print(f"  → 超时平仓")


# ============ 短线股票筛选 ============

def scan_hot_stocks(data_path: str = "data/combined_hk_stocks.csv") -> List[str]:
    """扫描热门股票（适合短线）"""
    
    df = pd.read_csv(data_path)
    df['date'] = pd.to_datetime(df['date'])
    
    # 最近数据
    latest = df[df['date'] == df['date'].max()]
    
    # 筛选条件
    hot_stocks = []
    
    for _, row in latest.iterrows():
        # 1. 成交额 > 5000万
        amount = row['close'] * row['volume']
        if amount < 50_000_000:
            continue
        
        # 2. 换手率 > 2%（活跃）
        # 3. 波动率适中（10-30%）
        
        hot_stocks.append(row['Symbol'])
    
    print(f"找到 {len(hot_stocks)} 只热门股票")
    return hot_stocks


# ============ 主程序 ============

def main():
    print("="*60)
    print(" 富途L2短线策略")
    print(" 快进快出，日内交易")
    print("="*60)
    
    print("\n⚠️  风险提示:")
    print("  • 短线交易风险极高")
    print("  • 需要实时盯盘")
    print("  • 手续费会侵蚀利润")
    print("  • 需要富途L2行情订阅")
    
    print("\n策略核心:")
    print("  1. L2订单簿 - 看买卖盘力量")
    print("  2. 大单追踪 - 跟主力资金")
    print("  3. 经纪商队列 - 识别主力")
    print("  4. 快速止损 - 2%止损，3%止盈")
    print("  5. 超时平仓 - 最长持有30分钟")
    
    print("\n实盘运行:")
    print("  trader = FutuL2Trader()")
    print("  trader.subscribe_l2(['00700', '00941', ...])")
    print("  trader.run_single('00700')")

if __name__ == "__main__":
    main()
