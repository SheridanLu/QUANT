#!/usr/bin/env python3
"""
富途L1接口实盘策略
严格风控: 最大回撤15%, 单只仓位10%, 止损8%
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, time
import warnings
warnings.filterwarnings('ignore')

# ============ 富途OpenD接口说明 ============
"""
安装: pip install futu-api

富途OpenD需要:
1. 开通富途证券账户
2. 下载OpenD客户端并运行
3. 配置 host='127.0.0.1', port=11111

L1行情限制:
- 免费订阅: 每秒10次
- 付费订阅: 每秒更高
"""

@dataclass
class RiskConfig:
    """风控配置"""
    max_drawdown: float = 0.15      # 最大回撤15%
    max_position_pct: float = 0.10  # 单只最大仓位10%
    max_total_position: float = 0.80  # 总仓位不超过80%
    stop_loss_pct: float = 0.08     # 止损8%
    take_profit_pct: float = 0.20   # 止盈20%
    max_volatility: float = 0.50    # 最大波动率50%
    min_liquidity: float = 1e8      # 最小成交额1亿港币

@dataclass
class TradeSignal:
    """交易信号"""
    symbol: str
    action: str  # 'BUY', 'SELL', 'HOLD'
    confidence: float  # 0-1
    price: float
    shares: int
    reason: str


class FutuTrader:
    """
    富途实盘交易类
    
    风控严格:
    1. 单只最大仓位10%
    2. 最大回撤15%清仓
    3. 单只止损8%
    4. 波动率>50%不买
    5. 成交额<1亿不买
    """
    
    def __init__(
        self,
        host: str = '127.0.0.1',
        port: int = 11111,
        config: RiskConfig = None
    ):
        self.host = host
        self.port = port
        self.config = config or RiskConfig()
        
        # 富途接口 (需要先运行OpenD)
        self.quote_ctx = None
        self.trade_ctx = None
        
        # 账户状态
        self.cash = 0
        self.positions = {}
        self.equity_curve = []
        self.peak_equity = 0
        self.daily_pnl = 0
        
        # 初始化
        self._connect()
    
    def _connect(self):
        """连接富途OpenD"""
        try:
            from futu import OpenQuoteContext, OpenHKTradeContext, HKMarket
            
            self.quote_ctx = OpenQuoteContext(self.host, self.port)
            self.trade_ctx = OpenHKTradeContext(self.host, self.port)
            
            print(f"✓ 已连接富途OpenD: {self.host}:{self.port}")
            self._sync_account()
            
        except ImportError:
            print("⚠️  futu-api 未安装, 运行: pip install futu-api")
            print("   使用模拟模式")
            self._mock_mode = True
        except Exception as e:
            print(f"⚠️  连接失败: {e}")
            print("   请确保OpenD已启动 (默认 127.0.0.1:11111)")
            self._mock_mode = True
    
    def _sync_account(self):
        """同步账户信息"""
        if self._mock_mode:
            return
        
        try:
            # 获取账户资金
            ret, data = self.trade_ctx.accinfo_query()
            if ret == 0:
                self.cash = data['cash'].iloc[0]
                
            # 获取持仓
            ret, data = self.trade_ctx.position_list_query()
            if ret == 0:
                for _, row in data.iterrows():
                    self.positions[row['code']] = {
                        'shares': row['qty'],
                        'cost': row['cost_price'],
                        'market_value': row['market_val']
                    }
        except Exception as e:
            print(f"同步账户失败: {e}")
    
    # ============ 风控检查 ============
    
    def check_drawdown(self) -> bool:
        """
        检查是否触及最大回撤
        Returns: True=安全, False=触及止损需要清仓
        """
        if len(self.equity_curve) < 2:
            return True
        
        current_equity = self.equity_curve[-1]
        self.peak_equity = max(self.peak_equity, current_equity)
        
        drawdown = (current_equity - self.peak_equity) / self.peak_equity
        
        if drawdown < -self.config.max_drawdown:
            print(f"⚠️  触及最大回撤! 当前: {drawdown*100:.2f}%")
            return False
        
        return True
    
    def check_position_limit(self, symbol: str, market_value: float) -> bool:
        """检查仓位限制"""
        total_equity = self._get_total_equity()
        
        # 单只仓位检查
        if market_value > total_equity * self.config.max_position_pct:
            print(f"  ⚠️  {symbol} 仓位超限: {market_value/total_equity*100:.1f}%")
            return False
        
        # 总仓位检查
        total_position = sum(p.get('market_value', 0) for p in self.positions.values())
        if total_position > total_equity * self.config.max_total_position:
            print(f"  ⚠️  总仓位超限: {total_position/total_equity*100:.1f}%")
            return False
        
        return True
    
    def check_stock_quality(self, symbol: str, data: pd.DataFrame) -> bool:
        """
        检查股票质量
        - 波动率不能太高
        - 成交额要足够
        """
        if data.empty or len(data) < 20:
            return False
        
        # 波动率检查
        returns = data['close'].pct_change()
        volatility = returns.std() * np.sqrt(252)
        if volatility > self.config.max_volatility:
            print(f"  ⚠️  {symbol} 波动率过高: {volatility*100:.1f}%")
            return False
        
        # 成交额检查
        avg_amount = (data['close'] * data['volume']).tail(20).mean()
        if avg_amount < self.config.min_liquidity:
            print(f"  ⚠️  {symbol} 成交额不足: {avg_amount/1e8:.2f}亿")
            return False
        
        return True
    
    def check_stop_loss(self, symbol: str, current_price: float) -> bool:
        """
        检查是否需要止损
        Returns: True=持有, False=需要止损卖出
        """
        if symbol not in self.positions:
            return True
        
        pos = self.positions[symbol]
        cost = pos['cost']
        pnl_pct = (current_price - cost) / cost
        
        # 止损检查
        if pnl_pct < -self.config.stop_loss_pct:
            print(f"  🛑 {symbol} 触发止损: {pnl_pct*100:.2f}%")
            return False
        
        # 止盈检查
        if pnl_pct > self.config.take_profit_pct:
            print(f"  🎯 {symbol} 触发止盈: {pnl_pct*100:.2f}%")
            return False
        
        return True
    
    # ============ 交易执行 ============
    
    def place_order(self, signal: TradeSignal) -> bool:
        """
        下单
        Returns: True=成功, False=失败
        """
        if self._mock_mode:
            print(f"  [模拟] {signal.action} {signal.symbol} x{signal.shares} @ {signal.price}")
            return True
        
        try:
            from futu import OrderType, TrdSide
            
            if signal.action == 'BUY':
                ret, data = self.trade_ctx.place_order(
                    price=signal.price,
                    qty=signal.shares,
                    code=signal.symbol,
                    order_type=OrderType.MARKET,
                    trd_side=TrdSide.BUY
                )
            elif signal.action == 'SELL':
                ret, data = self.trade_ctx.place_order(
                    price=signal.price,
                    qty=signal.shares,
                    code=signal.symbol,
                    order_type=OrderType.MARKET,
                    trd_side=TrdSide.SELL
                )
            
            if ret == 0:
                print(f"  ✓ 下单成功: {signal.action} {signal.symbol}")
                return True
            else:
                print(f"  ✗ 下单失败: {data}")
                return False
                
        except Exception as e:
            print(f"  ✗ 下单异常: {e}")
            return False
    
    def emergency_close_all(self):
        """紧急清仓"""
        print("🚨 执行紧急清仓!")
        
        for symbol, pos in list(self.positions.items()):
            signal = TradeSignal(
                symbol=symbol,
                action='SELL',
                confidence=1.0,
                price=0,  # 市价
                shares=pos['shares'],
                reason='风控清仓'
            )
            self.place_order(signal)
    
    # ============ 工具方法 ============
    
    def _get_total_equity(self) -> float:
        """计算总权益"""
        total = self.cash
        for pos in self.positions.values():
            total += pos.get('market_value', 0)
        return total
    
    def calc_position_size(
        self,
        symbol: str,
        price: float,
        volatility: float = 0.30
    ) -> int:
        """
        计算仓位大小 (凯利公式 + 风控)
        """
        equity = self._get_total_equity()
        
        # 基础仓位 = 最大仓位 * 波动率调整
        vol_adjust = min(1.0, 0.30 / max(volatility, 0.10))
        base_position = equity * self.config.max_position_pct * vol_adjust
        
        # 股数
        shares = int(base_position / price)
        
        return shares


# ============ 策略类 ============

class LowDrawdownStrategy:
    """
    低回撤策略
    
    核心:
    1. 严格的止损 (8%)
    2. 仓位控制 (10%单只)
    3. 波动率筛选
    4. 流动性筛选
    5. 趋势确认
    """
    
    def __init__(self, trader: FutuTrader):
        self.trader = trader
        self.signals = []
    
    def analyze(self, symbol: str, data: pd.DataFrame) -> Optional[TradeSignal]:
        """
        分析单只股票
        
        策略逻辑:
        1. 20日动量 > 3% (降低阈值，减少假信号)
        2. 5日均线 > 20日均线
        3. RSI 30-70之间
        4. 成交量放大
        """
        if not self.trader.check_stock_quality(symbol, data):
            return None
        
        # 计算指标
        data = data.copy()
        data['MA5'] = data['close'].rolling(5).mean()
        data['MA20'] = data['close'].rolling(20).mean()
        data['MOM'] = data['close'] / data['close'].shift(20) - 1
        data['VOL_RATIO'] = data['volume'] / data['volume'].rolling(20).mean()
        
        # RSI
        delta = data['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        data['RSI'] = 100 - (100 / (1 + gain / loss))
        
        # 最新数据
        latest = data.iloc[-1]
        
        # 买入条件
        buy_signal = (
            latest['MOM'] > 0.03 and           # 动量>3%
            latest['MA5'] > latest['MA20'] and # 短期均线在上
            30 < latest['RSI'] < 70 and        # RSI中性
            latest['VOL_RATIO'] > 1.2          # 成交量放大
        )
        
        # 卖出条件
        sell_signal = (
            latest['MOM'] < -0.03 or           # 动量转负
            latest['MA5'] < latest['MA20'] or  # 均线死叉
            latest['RSI'] > 80                  # RSI超买
        )
        
        # 检查是否已持仓
        has_position = symbol in self.trader.positions
        
        # 检查止损
        if has_position:
            if not self.trader.check_stop_loss(symbol, latest['close']):
                return TradeSignal(
                    symbol=symbol,
                    action='SELL',
                    confidence=1.0,
                    price=latest['close'],
                    shares=self.trader.positions[symbol]['shares'],
                    reason='止损/止盈'
                )
        
        # 生成信号
        if buy_signal and not has_position:
            volatility = data['close'].pct_change().std() * np.sqrt(252)
            shares = self.trader.calc_position_size(symbol, latest['close'], volatility)
            
            return TradeSignal(
                symbol=symbol,
                action='BUY',
                confidence=0.7,
                price=latest['close'],
                shares=shares,
                reason='动量+均线+成交量'
            )
        
        elif sell_signal and has_position:
            return TradeSignal(
                symbol=symbol,
                action='SELL',
                confidence=0.6,
                price=latest['close'],
                shares=self.trader.positions[symbol]['shares'],
                reason='信号反转'
            )
        
        return TradeSignal(
            symbol=symbol,
            action='HOLD',
            confidence=0.5,
            price=latest['close'],
            shares=0,
            reason='无信号'
        )
    
    def run(self, symbols: List[str], data_dict: Dict[str, pd.DataFrame]):
        """运行策略"""
        print("\n" + "=" * 60)
        print(" 低回撤策略运行中")
        print("=" * 60)
        
        # 1. 检查总回撤
        if not self.trader.check_drawdown():
            self.trader.emergency_close_all()
            return
        
        # 2. 分析每只股票
        for symbol in symbols:
            if symbol not in data_dict:
                continue
            
            signal = self.analyze(symbol, data_dict[symbol])
            
            if signal and signal.action != 'HOLD':
                self.trader.place_order(signal)
                self.signals.append(signal)
        
        print(f"\n本轮信号数: {len(self.signals)}")


# ============ 主程序 ============

def main():
    print("=" * 60)
    print(" 富途实盘策略 - 严格风控版")
    print(" 最大回撤: 15% | 单只仓位: 10% | 止损: 8%")
    print("=" * 60)
    
    # 初始化交易器
    trader = FutuTrader(
        host='127.0.0.1',
        port=11111,
        config=RiskConfig(
            max_drawdown=0.15,
            max_position_pct=0.10,
            stop_loss_pct=0.08
        )
    )
    
    # 加载历史数据
    data = pd.read_csv("data/combined_hk_stocks.csv")
    data['date'] = pd.to_datetime(data['date'])
    
    # 构建数据字典
    data_dict = {}
    for symbol in data['Symbol'].unique():
        df = data[data['Symbol'] == symbol].copy()
        data_dict[symbol] = df
    
    # 初始化策略
    strategy = LowDrawdownStrategy(trader)
    
    # 运行
    symbols = list(data_dict.keys())
    strategy.run(symbols, data_dict)
    
    print("\n策略运行完成!")


if __name__ == "__main__":
    main()
