# 富途实盘接入指南

## 第一步：准备工作

### 1.1 开通富途证券账户
- 下载「富途牛牛」App
- 开通港股交易权限
- 充值港币

### 1.2 安装OpenD
1. 下载地址：https://www.futunn.com/download/OpenD
2. 安装后运行
3. 用富途账号登录
4. 默认端口：127.0.0.1:11111

### 1.3 安装Python库
```bash
pip install futu-api
```

---

## 第二步：测试连接

创建 `test_futu.py`:

```python
from futu import *

# 连接
quote_ctx = OpenQuoteContext('127.0.0.1', 11111)

# 测试获取行情
ret, data = quote_ctx.get_market_snapshot(['HK.00700'])
if ret == RET_OK:
    print("✓ 连接成功!")
    print(data)
else:
    print("✗ 连接失败:", data)

quote_ctx.close()
```

运行：
```bash
python test_futu.py
```

---

## 第三步：实盘策略代码

我已经写好了，见：`src/12_futu_live.py`

---

## 第四步：运行

1. 确保OpenD在运行
2. 确保交易时间（港股 09:30-16:00）
3. 运行策略：
```bash
python src/12_futu_live.py
```

---

## 注意事项

1. **先用小资金测试**（比如1万港币）
2. **不要全仓**
3. **严格止损**
4. **交易时间运行**
5. **监控日志**

---

## 风险提示

- 实盘有真实亏损风险
- 策略回测不代表未来
- 先模拟盘测试
- 做好资金管理

---

我来帮你写完整代码，你只需要：
1. 确保OpenD在运行
2. 告诉我你的账户资金规模
3. 我生成配置并运行
