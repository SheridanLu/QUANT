#!/usr/bin/env python3
"""
使用 akshare 获取港股日线数据
akshare 是国内开源的金融数据接口，不限流
"""

import akshare as ak
import pandas as pd
import os
import time
from datetime import datetime, timedelta

def get_hk_stock_daily(symbol: str, adjust: str = "qfq") -> pd.DataFrame:
    """
    获取港股日线数据
    
    Args:
        symbol: 港股代码 (如 "00700" 代表腾讯)
        adjust: 复权类型 ("qfq"-前复权, "hfq"-后复权, ""-不复权)
    
    Returns:
        DataFrame with OHLCV data
    """
    try:
        df = ak.stock_hk_daily(symbol=symbol, adjust=adjust)
        if df.empty:
            return None
        return df
    except Exception as e:
        print(f"  错误: {e}")
        return None

def get_hk_index_daily(symbol: str = "HSI") -> pd.DataFrame:
    """
    获取港股指数数据
    
    Args:
        symbol: 指数代码 (HSI=恒生指数)
    """
    try:
        if symbol == "HSI":
            df = ak.index_hk_daily(symbol="HSI")
            return df
    except Exception as e:
        print(f"  获取指数错误: {e}")
        return None

# 港股核心股票池 (akshare 用5位数字代码)
HK_STOCKS = {
    # 科技
    "00700": "腾讯控股",
    "09988": "阿里巴巴",
    "01810": "小米集团",
    "03690": "美团",
    "09999": "网易",
    # 金融
    "00005": "汇丰控股",
    "01299": "友邦保险",
    "02318": "中国平安",
    "01398": "工商银行",
    "03988": "中国银行",
    # 地产
    "00016": "新鸿基地产",
    "00011": "恒生银行",
    # 其他蓝筹
    "00941": "中国移动",
    "00883": "中国海洋石油",
    "01211": "比亚迪股份",
    "02269": "药明生物",
    "01177": "中国生物制药",
    "02899": "紫金矿业",
    "00386": "中国石化",
}

def main():
    print("=" * 60)
    print("港股数据获取程序 (akshare 版)")
    print("时间:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 60)
    
    save_dir = "data/raw"
    os.makedirs(save_dir, exist_ok=True)
    
    all_data = {}
    
    # 1. 获取恒生指数
    print("\n[0] 获取恒生指数...")
    try:
        hsi = ak.index_hk_daily(symbol="HSI")
        if not hsi.empty:
            hsi['Symbol'] = '^HSI'
            hsi.to_csv(f"{save_dir}/HSI_index.csv")
            all_data['^HSI'] = hsi
            print(f"  ✓ 恒生指数: {len(hsi)} 条")
    except Exception as e:
        print(f"  ✗ 恒生指数获取失败: {e}")
    
    # 2. 获取个股数据
    success_count = 0
    for i, (code, name) in enumerate(HK_STOCKS.items()):
        print(f"[{i+1}/{len(HK_STOCKS)}] {name} ({code})...", end=" ", flush=True)
        
        df = get_hk_stock_daily(code)
        
        if df is not None and not df.empty:
            df['Symbol'] = code
            df['Name'] = name
            df.to_csv(f"{save_dir}/{code}.csv")
            all_data[code] = df
            success_count += 1
            print(f"✓ ({len(df)} 条)")
        else:
            print("✗")
        
        time.sleep(0.5)  # 稍微等待
    
    # 3. 合并所有数据
    if all_data:
        combined_list = []
        for symbol, df in all_data.items():
            df_copy = df.copy()
            df_copy['Symbol'] = symbol
            combined_list.append(df_copy)
        
        combined = pd.concat(combined_list, ignore_index=True)
        
        # 标准化列名
        column_map = {
            '日期': 'Date',
            '开盘': 'Open', 
            '收盘': 'Close',
            '最高': 'High',
            '最低': 'Low',
            '成交量': 'Volume',
            '成交额': 'Amount',
            '振幅': 'Amplitude',
            '涨跌幅': 'PctChange',
            '涨跌额': 'Change',
            '换手率': 'Turnover'
        }
        combined.rename(columns=column_map, inplace=True)
        
        combined.to_csv("data/combined_hk_stocks.csv", index=False)
        
        print("\n" + "=" * 60)
        print(f"完成! 成功: {success_count}/{len(HK_STOCKS)} 只股票 + 恒生指数")
        print(f"数据保存至: data/combined_hk_stocks.csv")
        print(f"数据形状: {combined.shape}")
        print("=" * 60)
        
        # 显示数据概览
        print("\n数据概览:")
        print(combined.head())
        print("\n列名:", list(combined.columns))
        print("\n股票列表:")
        if 'Symbol' in combined.columns:
            print(combined['Symbol'].unique())
    else:
        print("\n未能获取任何数据!")

if __name__ == "__main__":
    main()
