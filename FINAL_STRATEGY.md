# 港股实盘策略 - 最终方案

## 回测结论

经过多轮参数优化，**无法在港股市场找到同时满足以下条件的策略**：
- 年化收益 > 10%
- 最大回撤 < 15%

**原因**：
- 港股蓝筹股年化波动率 30-50%，控制15%回撤需要极低仓位
- 低仓位导致收益无法达标
- 港股近10年震荡市，趋势策略效果差

---

## 实用方案

### 方案A：高股息策略（推荐）

**目标**：年化 8-10%，回撤 10-15%

**持仓**：
```
30% 汇丰控股 0005.HK (股息率 6-7%)
25% 中国移动 0941.HK (股息率 6-7%)  
25% 中国海洋石油 0883.HK (股息率 8-10%)
20% 恒生银行 0011.HK (股息率 5-6%)
```

**操作**：
- 分批买入，长期持有
- 收股息为主，不频繁交易
- 股价跌10%加仓

---

### 方案B：趋势策略（接受更大回撤）

**目标**：年化 12-15%，回撤 20-25%

**参数**：
- 动量阈值：4%
- 单只仓位：10%
- 止损：6%
- 止盈：12%

**规则**：
1. 20日动量 > 4% 买入
2. MA5 > MA20 确认趋势
3. RSI 在 35-65 区间
4. 亏损 6% 止损
5. 盈利 12% 止盈

---

### 方案C：纯指数定投

**目标**：年化 6-8%，回撤 30-40%（长期）

**操作**：
- 每月定投恒指 ETF (2800.HK)
- 长期持有（5年以上）
- 不择时，坚持定投

---

## 富途L1实盘代码

```python
from futu import *
import time

class HKDividendStrategy:
    """高股息策略实盘版"""
    
    # 目标持仓
    TARGETS = {
        '00005': {'name': '汇丰', 'pct': 0.30},
        '00941': {'name': '中移动', 'pct': 0.25},
        '00883': {'name': '中海油', 'pct': 0.25},
        '00011': {'name': '恒生', 'pct': 0.20},
    }
    
    def __init__(self):
        self.quote_ctx = OpenQuoteContext('127.0.0.1', 11111)
        self.hk_trade_ctx = OpenHKTradeContext('127.0.0.1', 11111)
    
    def get_cash(self):
        """获取可用资金"""
        ret, data = self.hk_trade_ctx.accinfo_query()
        if ret == RET_OK:
            return data['cash'].iloc[0]
        return 0
    
    def get_position(self, code):
        """获取持仓"""
        ret, data = self.hk_trade_ctx.position_list_query(code=code)
        if ret == RET_OK and len(data) > 0:
            return data['qty'].iloc[0]
        return 0
    
    def check_and_buy(self):
        """检查并买入"""
        cash = self.get_cash()
        
        for code, info in self.TARGETS.items():
            target_value = cash * info['pct']
            
            # 获取当前价格
            ret, data = self.quote_ctx.get_market_snapshot([code])
            if ret != RET_OK:
                continue
            
            price = data['last_price'].iloc[0]
            target_shares = int(target_value / price / 100) * 100  # 港股每手100股
            
            # 检查当前持仓
            current_shares = self.get_position(code)
            
            if target_shares > current_shares:
                # 买入
                buy_shares = target_shares - current_shares
                ret, data = self.hk_trade_ctx.place_order(
                    price=price,
                    qty=buy_shares,
                    code=code,
                    order_type=OrderType.MARKET,
                    trd_side=TrdSide.BUY
                )
                
                if ret == RET_OK:
                    print(f"✓ 买入 {info['name']} {buy_shares}股")
                else:
                    print(f"✗ 买入失败: {data}")
    
    def run(self):
        """定期运行"""
        while True:
            try:
                self.check_and_buy()
                time.sleep(3600)  # 每小时检查一次
            except Exception as e:
                print(f"错误: {e}")
                time.sleep(60)

if __name__ == "__main__":
    print("="*60)
    print(" 港股高股息策略")
    print(" 富途L1实盘版")
    print("="*60)
    
    strategy = HKDividendStrategy()
    
    print("\n请确保:")
    print("1. 富途OpenD已启动 (127.0.0.1:11111)")
    print("2. 账户有足够资金")
    print("3. 已开通港股交易权限")
    
    input("\n按回车开始运行...")
    strategy.run()
```

---

## 风险提示

1. **港股风险高**：波动大，回撤可能超预期
2. **不要加杠杆**：港股无涨跌幅限制，杠杆会爆仓
3. **分散持仓**：至少5只股票
4. **保留现金**：至少20%仓位应对风险
5. **长期持有**：不要频繁交易

---

## 我的建议

如果你坚持用富途L1做港股：

1. **首选高股息策略** - 稳定、风险低
2. **接受20-25%回撤** - 才能获得10%+收益
3. **不要追求高收益** - 港股市场效率高
4. **长期持有** - 1年以上视角

**核心原则**：收股息 > 搏差价

---

最后更新：2026-03-03
