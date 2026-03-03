# 富途L2短线策略

## L2行情优势

| 功能 | L1 | L2 |
|------|----|----|
| 买卖档位 | 1档 | **10档** |
| 更新频率 | 3秒 | **毫秒级** |
| 经纪商队列 | ❌ | **✅** |
| 分笔成交 | 简单 | **详细** |

## 短线核心

### 1. 看订单簿（买盘 vs 卖盘）
```
买盘10档总量 > 卖盘10档总量 × 2 → 买入信号
买盘10档总量 < 卖盘10档总量 ÷ 2 → 卖出信号
```

### 2. 跟大单（主力资金）
```
最近50笔大单（>50万）净买入 → 跟买
最近50笔大单（>50万）净卖出 → 跟卖
```

### 3. 看经纪商（谁在买卖）
```
大券商（高盛/摩根/中金/中信）集中买 → 主力进场
大券商集中卖 → 主力撤退
```

## 策略参数

```python
# 仓位控制
单只仓位: 5%    # 短线小仓位
最大持仓: 3只   # 不超过3只

# 止损止盈
止损: 2%        # 快速止损
止盈: 3%        # 见好就收
超时: 30分钟    # 最长持有30分钟

# 筛选条件
成交额: >5000万  # 流动性
量比: >2         # 活跃
价差: <0.2%      # 好成交
```

## 实盘代码

```python
from futu import *

class ScalpingTrader:
    def __init__(self):
        self.quote = OpenQuoteContext('127.0.0.1', 11111)
        self.trade = OpenHKTradeContext('127.0.0.1', 11111)
    
    def get_signal(self, code):
        # 1. 订单簿
        ret, orderbook = self.quote.get_order_book(code)
        bid_vol = sum(v for p, v in orderbook['Bid'][:5])
        ask_vol = sum(v for p, v in orderbook['Ask'][:5])
        
        if bid_vol > ask_vol * 2:
            return 'BUY'
        elif ask_vol > bid_vol * 2:
            return 'SELL'
        
        # 2. 大单
        ret, ticks = self.quote.get_rt_ticker(code, 100)
        big_buy = sum(v for _, r in ticks.iterrows() 
                     if r['volume']*r['price']>500000 and r['ticker_direction']==1)
        big_sell = sum(v for _, r in ticks.iterrows() 
                      if r['volume']*r['price']>500000 and r['ticker_direction']==0)
        
        if big_buy > big_sell * 1.5:
            return 'BUY'
        elif big_sell > big_buy * 1.5:
            return 'SELL'
        
        return 'HOLD'
    
    def run(self, codes):
        while True:
            for code in codes:
                signal = self.get_signal(code)
                
                if signal == 'BUY':
                    self.trade.place_order(
                        price=0,  # 市价
                        qty=100,
                        code=code,
                        order_type=OrderType.MARKET,
                        trd_side=TrdSide.BUY
                    )
                    print(f"买入 {code}")
                
                elif signal == 'SELL':
                    self.trade.place_order(
                        price=0,
                        qty=100,
                        code=code,
                        order_type=OrderType.MARKET,
                        trd_side=TrdSide.SELL
                    )
                    print(f"卖出 {code}")
            
            time.sleep(1)  # 每秒检查

# 运行
trader = ScalpingTrader()
trader.run(['00700', '00941', '00005'])
```

## 风险警告

### ⚠️ 极高风险

1. **手续费**：短线频繁交易，手续费可能吃掉所有利润
2. **滑点**：快进快出，买卖价差是成本
3. **盯盘**：需要全神贯注，不能离开
4. **情绪**：追涨杀跌，容易失控

### 建议

- ❌ 不建议新手做短线
- ❌ 不建议全职做短线
- ❌ 不要用全部资金
- ✅ 先用小资金练手
- ✅ 严格止损
- ✅ 控制交易频率

## 更实际的方案

如果你想要"快速发展"：

### 方案A：L2 + 波段（推荐）

- 用L2找买点（大单进场时买入）
- 持有1-5天（不是30分钟）
- 止盈5-10%（不是3%）

```python
# L2找买点
def find_entry_with_l2(code):
    # 大单净买入
    if big_buy - big_sell > threshold:
        # 买盘力量强
        if bid_vol > ask_vol * 1.5:
            return 'BUY'  # 进场
```

### 方案B：L2 + 突破

- 用L2确认突破有效性
- 放量突破 + 大单跟风
- 持有到趋势结束

### 方案C：价差套利

- 两个相关股票对冲
- 比如腾讯 vs 阿里
- 赚价差回归

## 总结

**短线（日内）**：
- 回撤控制：好（2%止损）
- 收益潜力：低（手续费吃利润）
- 难度：极高
- 时间成本：全职盯盘

**波段（1-5天）**：
- 回撤控制：中（5%止损）
- 收益潜力：中高（5-10%）
- 难度：中等
- 时间成本：下班后看一眼

**我的建议**：
用L2找买点，做波段，不做日内。收益更高，压力更小。

---

代码已保存: `src/08_l2_scalping.py`
