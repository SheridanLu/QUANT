#!/usr/bin/env python3
"""
港股数据获取模块 v2
分批次获取，避免限流
"""

import pandas as pd
import yfinance as yf
import time
import os
import random

# 核心港股股票池 (精简到最重要的20只)
HK_STOCKS = [
    # 科技巨头
    "0700.HK",  # 腾讯
    "9988.HK",  # 阿里巴巴
    "1810.HK",  # 小米
    "3690.HK",  # 美团
    "9999.HK",  # 网易
    # 金融
    "0005.HK",  # 汇丰控股
    "1299.HK",  # 友邦保险
    "2318.HK",  # 中国平安
    "1398.HK",  # 工商银行
    "3988.HK",  # 中国银行
    # 地产
    "0016.HK",  # 新鸿基地产
    "0011.HK",  # 恒生银行
    # 其他蓝筹
    "0941.HK",  # 中国移动
    "0883.HK",  # 中国海洋石油
    "1211.HK",  # 比亚迪
    "2269.HK",  # 药明生物
    "1177.HK",  # 中国生物制药
    "2899.HK",  # 紫金矿业
    "0386.HK",  # 中国石化
    # 指数
    "^HSI",     # 恒生指数
]

def get_stock_with_retry(symbol: str, period: str = "3y", max_retries: int = 3) -> pd.DataFrame:
    """带重试的获取股票数据"""
    for attempt in range(max_retries):
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period)
            
            if df.empty:
                return None
            
            df['Symbol'] = symbol
            return df
        except Exception as e:
            if "Rate limited" in str(e) or "Too Many" in str(e):
                wait_time = (attempt + 1) * 10 + random.randint(1, 5)
                print(f"  限流，等待 {wait_time} 秒...")
                time.sleep(wait_time)
            else:
                print(f"  错误: {e}")
                return None
    return None

def main():
    print("=" * 60)
    print("港股数据获取程序 v2 (分批次，避免限流)")
    print("=" * 60)
    
    save_dir = "data/raw"
    os.makedirs(save_dir, exist_ok=True)
    
    data = {}
    batch_size = 5  # 每批5只，中间休息
    
    for i, symbol in enumerate(HK_STOCKS):
        print(f"[{i+1}/{len(HK_STOCKS)}] 获取 {symbol}...", end=" ", flush=True)
        
        df = get_stock_with_retry(symbol, period="3y")
        
        if df is not None and not df.empty:
            data[symbol] = df
            df.to_csv(f"{save_dir}/{symbol.replace('.HK', '').replace('^', 'IDX_')}.csv")
            print(f"✓ ({len(df)} 条)")
        else:
            print("✗")
        
        # 每批之后休息一下
        if (i + 1) % batch_size == 0:
            wait = random.randint(3, 8)
            print(f"  -- 批次完成，休息 {wait} 秒 --")
            time.sleep(wait)
        else:
            time.sleep(random.uniform(0.5, 1.5))  # 请求之间也有间隔
    
    # 创建合并数据集
    if data:
        all_dfs = []
        for symbol, df in data.items():
            df = df.reset_index()
            df['Symbol'] = symbol
            all_dfs.append(df)
        
        combined = pd.concat(all_dfs, ignore_index=True)
        combined.to_csv("data/combined_hk_stocks.csv", index=False)
        
        print("\n" + "=" * 60)
        print(f"完成! 成功获取 {len(data)}/{len(HK_STOCKS)} 只股票")
        print(f"数据保存至: data/combined_hk_stocks.csv")
        print(f"数据形状: {combined.shape}")
        print("=" * 60)
    else:
        print("\n未能获取任何数据!")

if __name__ == "__main__":
    main()
