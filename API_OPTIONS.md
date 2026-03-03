# 港股API接口对比

## 1. 富途OpenD (推荐)

**优点**：
- 免费
- API完善
- 支持L2深度数据
- 支持实盘交易
- 文档完善

**缺点**：
- 需要本地运行OpenD
- 需要富途账户

**申请**：
- https://www.futunn.com/download/OpenD
- 开通富途证券账户

---

## 2. 老虎证券 OpenAPI

**优点**：
- 免费API
- 支持美股/港股
- 支持实盘交易

**缺点**：
- 需要老虎账户

**申请**：
- https://www.tigersecurities.com/openapi

---

## 3. Interactive Brokers (IBKR)

**优点**：
- 全球最大
- API最专业
- 支持所有市场

**缺点**：
- 佣金较高
- API复杂
- 需要海外账户

**申请**：
- https://www.interactivebrokers.com

---

## 4. 长桥证券 LongPort

**优点**：
- 新兴平台
- API友好
- 支持港股/美股

**缺点**：
- 用户较少
- 文档较少

**申请**：
- https://open.longportapp.com

---

## 5. 盈透证券

**优点**：
- 专注港股
- API简单

**申请**：
- https://www.yingtou.com

---

## 6. 纯行情API（无交易）

### Tushare Pro
- 网址：https://tushare.pro
- 费用：积分制
- 数据：A股/港股/美股

### AkShare
- 网址：https://akshare.akfamily.xyz
- 费用：免费
- 数据：A股/港股

### Yahoo Finance
- 费用：免费
- 缺点：延迟、限流

### Alpha Vantage
- 网址：https://www.alphavantage.co
- 费用：免费层 + 付费
- 数据：全球市场

---

## 对比表格

| 接口 | 交易 | 行情 | L2深度 | 费用 | 难度 |
|------|------|------|--------|------|------|
| 富途OpenD | ✅ | ✅ | ✅ | 免费 | 中 |
| 老虎OpenAPI | ✅ | ✅ | ❌ | 免费 | 中 |
| IBKR | ✅ | ✅ | ✅ | 付费 | 高 |
| 长桥 | ✅ | ✅ | ❌ | 免费 | 低 |
| Tushare | ❌ | ✅ | ❌ | 积分 | 低 |
| AkShare | ❌ | ✅ | ❌ | 免费 | 低 |

---

## 我的建议

### 如果要实盘交易：

**1. 富途OpenD** (最推荐)
- 免费、功能全、L2数据
- 你已经有富途账户吗？

**2. 老虎OpenAPI** (备选)
- 如果你更喜欢老虎

**3. 长桥** (简单)
- API最简单，适合新手

### 如果只要行情数据：

**1. AkShare** (免费)
- 我们已经在用了
- 港股数据够用

**2. Tushare Pro** (更全)
- 需要积分，但数据质量高

---

## 快速选择

**告诉我**：
1. 你有哪个券商账户？（富途/老虎/其他）
2. 需要实盘交易还是只要行情？
3. 预算是多少？（免费/付费都行）

我帮你写对应接口的代码！

---

## 代码示例

### 富途（已有）
- `src/12_futu_live.py`

### 长桥（需要开户）
```python
from longport.openapi import QuoteContext, Config

config = Config.from_env()
ctx = QuoteContext(config)

# 获取行情
quotes = ctx.quotes(['700.HK'])
```

### IBKR（需要海外账户）
```python
from ibapi.client import EClient
from ibapi.wrapper import EWrapper

class TestApp(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)

app = TestApp()
app.connect("127.0.0.1", 7497, clientId=0)
```

---

**你选哪个？我帮你配置！** 🦞
