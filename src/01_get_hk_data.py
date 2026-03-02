#!/usr/bin/env python3
"""
港股数据获取模块
从 Yahoo Finance 获取港股日线数据
"""

import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import os

# 港股蓝筹股票池 (恒生指数成分股 + 热门港股)
HK_STOCKS = [
    # 科技
    "0700.HK",  # 腾讯
    "9988.HK",  # 阿里巴巴
    "9999.HK",  # 网易
    "1810.HK",  # 小米
    "3690.HK",  # 美团
    "9888.HK",  # 百度
    "1024.HK",  # 快手
    # 金融
    "0005.HK",  # 汇丰控股
    "1299.HK",  # 友邦保险
    "2318.HK",  # 中国平安
    "3888.HK",  # 金山软件
    "1398.HK",  # 工商银行
    "3988.HK",  # 中国银行
    "0939.HK",  # 建设银行
    "2628.HK",  # 中国人寿
    # 地产
    "0001.HK",  # 长和
    "0016.HK",  # 新鸿基地产
    "0011.HK",  # 恒生银行
    "0012.HK",  # 恒基地产
    # 消费
    "1928.HK",  # 金沙中国
    "0688.HK",  # 中国海外发展
    # 其他蓝筹
    "0002.HK",  # 中电控股
    "0003.HK",  # 香港中华煤气
    "0006.HK",  # 电能实业
    "0019.HK",  # 太古股份
    "0066.HK",  # 港铁公司
    "0083.HK",  # 信和置业
    "0175.HK",  # 吉利汽车
    "0267.HK",  # 中信股份
    "0386.HK",  # 中国石油化工
    "0883.HK",  # 中国海洋石油
    "0941.HK",  # 中国移动
    "1038.HK",  # 长江基建集团
    "1044.HK",  # 恒安国际
    "1093.HK",  # 石药集团
    "1177.HK",  # 中国生物制药
    "1211.HK",  # 比亚迪股份
    "1518.HK",  # 中国东方航空
    "1766.HK",  # 中国中车
    "2007.HK",  # 碧桂园
    "2269.HK",  # 药明生物
    "2313.HK",  # 申万宏源
    "2382.HK",  # 舜宇光学科技
    "2388.HK",  # 中银香港
    "2899.HK",  # 紫金矿业
    "3328.HK",  # 交通银行
]

# 指数
HK_INDICES = [
    "^HSI",     # 恒生指数
    "^HSCE",    # 恒生中国企业指数
]

def get_stock_data(symbol: str, period: str = "3y") -> pd.DataFrame:
    """
    获取单只股票的历史数据
    
    Args:
        symbol: 股票代码 (如 "0700.HK")
        period: 时间周期 ("1y", "2y", "3y", "5y", "10y", "max")
    
    Returns:
        DataFrame with OHLCV data
    """
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period)
        
        if df.empty:
            print(f"[WARN] {symbol} 数据为空")
            return None
        
        df['Symbol'] = symbol
        return df
    except Exception as e:
        print(f"[ERROR] 获取 {symbol} 数据失败: {e}")
        return None

def get_all_stocks_data(symbols: list, period: str = "3y", save_dir: str = "data/raw") -> dict:
    """
    批量获取股票数据
    
    Args:
        symbols: 股票代码列表
        period: 时间周期
        save_dir: 数据保存目录
    
    Returns:
        dict: {symbol: DataFrame}
    """
    os.makedirs(save_dir, exist_ok=True)
    data = {}
    
    print(f"开始获取 {len(symbols)} 只股票的数据...")
    
    for i, symbol in enumerate(symbols):
        print(f"[{i+1}/{len(symbols)}] 获取 {symbol}...", end=" ")
        
        df = get_stock_data(symbol, period)
        
        if df is not None and not df.empty:
            data[symbol] = df
            # 保存单只股票数据
            df.to_csv(f"{save_dir}/{symbol.replace('.HK', '').replace('^', 'index_')}.csv")
            print(f"✓ ({len(df)} 条记录)")
        else:
            print("✗")
    
    print(f"\n成功获取 {len(data)}/{len(symbols)} 只股票的数据")
    return data

def create_combined_dataset(data: dict, save_path: str = "data/combined_hk_stocks.csv"):
    """
    创建合并数据集
    """
    all_dfs = []
    
    for symbol, df in data.items():
        df = df.reset_index()
        df['Symbol'] = symbol
        all_dfs.append(df)
    
    if all_dfs:
        combined = pd.concat(all_dfs, ignore_index=True)
        combined.to_csv(save_path, index=False)
        print(f"合并数据集已保存至 {save_path}")
        print(f"数据形状: {combined.shape}")
        print(f"日期范围: {combined['Date'].min()} ~ {combined['Date'].max()}")
        return combined
    
    return None

def main():
    """主函数"""
    print("=" * 60)
    print("港股数据获取程序")
    print("=" * 60)
    
    # 获取所有股票数据
    all_symbols = HK_STOCKS + HK_INDICES
    data = get_all_stocks_data(all_symbols, period="3y")
    
    # 创建合并数据集
    combined = create_combined_dataset(data)
    
    # 输出统计信息
    if combined is not None:
        print("\n数据统计:")
        print(f"  股票数量: {combined['Symbol'].nunique()}")
        print(f"  日期范围: {combined['Date'].min().date()} ~ {combined['Date'].max().date()}")
        print(f"  总记录数: {len(combined)}")
    
    return data, combined

if __name__ == "__main__":
    main()
