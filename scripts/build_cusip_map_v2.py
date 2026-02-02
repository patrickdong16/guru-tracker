#!/usr/bin/env python3
"""
CUSIP→Ticker 全量映射脚本 v2
使用 OpenFIGI API 批量查询 CUSIP 对应的 ticker
"""

import json
import os
import glob
import time
import sys
from typing import Dict, Set, List
from datetime import datetime

def extract_all_cusips(data_dir: str = "data/parsed") -> Set[str]:
    """从所有解析的 JSON 文件中提取唯一的 CUSIP"""
    print("=== 阶段1: 提取所有 CUSIP ===")
    cusips = set()
    json_files = glob.glob(f"{data_dir}/*/*.json")
    
    print(f"找到 {len(json_files)} 个 JSON 文件")
    
    for i, file_path in enumerate(json_files, 1):
        try:
            if i % 10 == 0 or i == len(json_files):
                print(f"  进度: {i}/{len(json_files)}, CUSIP总数: {len(cusips)}")
                
            with open(file_path, 'r') as f:
                data = json.load(f)
                
            if 'holdings' in data and isinstance(data['holdings'], list):
                for holding in data['holdings']:
                    if 'cusip' in holding and holding['cusip']:
                        cusip = holding['cusip'].strip()
                        if len(cusip) == 9:  # CUSIP 标准长度
                            cusips.add(cusip)
                            
        except Exception as e:
            print(f"处理文件 {file_path} 时出错: {e}")
    
    print(f"扫描完成！提取到 {len(cusips)} 个唯一 CUSIP")
    return cusips

def load_existing_mapping(config_path: str = "config/cusip_tickers.json") -> Dict[str, str]:
    """加载现有的 CUSIP→Ticker 映射"""
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            return json.load(f)
    return {}

def query_openfigi_batch(cusips: List[str]) -> Dict[str, str]:
    """批量查询 OpenFIGI API"""
    try:
        import requests
    except ImportError:
        print("错误: 需要安装 requests 库")
        return {}
        
    url = "https://api.openfigi.com/v3/mapping"
    
    # 构建请求体
    request_data = [{"idType": "ID_CUSIP", "idValue": cusip} for cusip in cusips]
    
    try:
        response = requests.post(url, json=request_data, timeout=30)
        response.raise_for_status()
        
        result = {}
        response_data = response.json()
        
        for i, cusip in enumerate(cusips):
            if i < len(response_data) and response_data[i]:
                if 'data' in response_data[i] and response_data[i]['data']:
                    figi_data = response_data[i]['data'][0]
                    if 'ticker' in figi_data:
                        result[cusip] = figi_data['ticker']
        
        return result
        
    except Exception as e:
        print(f"查询 OpenFIGI 时出错: {e}")
        return {}

def main():
    """主函数"""
    print("=== CUSIP→Ticker 全量映射开始 ===")
    start_time = datetime.now()
    
    os.chdir("/Users/dq/.openclaw/workspace/guru-tracker")
    print(f"工作目录: {os.getcwd()}")
    
    # 1. 提取所有唯一 CUSIP
    all_cusips = extract_all_cusips()
    if not all_cusips:
        print("错误: 没有提取到任何 CUSIP")
        return
    
    print(f"\n=== 阶段2: 分析现有映射 ===")
    # 2. 加载现有映射
    existing_mapping = load_existing_mapping()
    print(f"现有映射: {len(existing_mapping)} 条")
    
    # 3. 找出需要查询的 CUSIP
    missing_cusips = list(all_cusips - set(existing_mapping.keys()))
    print(f"需要查询的 CUSIP: {len(missing_cusips)} 个")
    
    if not missing_cusips:
        print("所有 CUSIP 都已有映射，无需查询")
        return
    
    print(f"\n=== 阶段3: API 查询 ===")
    # 4. 分批查询
    batch_size = 100
    delay_seconds = 12
    new_mappings = 0
    total_batches = (len(missing_cusips) + batch_size - 1) // batch_size
    
    print(f"将分 {total_batches} 批次查询，预计耗时约 {total_batches * delay_seconds / 60:.1f} 分钟")
    
    for i in range(0, len(missing_cusips), batch_size):
        batch = missing_cusips[i:i+batch_size]
        batch_num = i // batch_size + 1
        
        print(f"\n批次 {batch_num}/{total_batches} ({len(batch)} 个 CUSIP)...")
        
        # 查询这一批
        batch_result = query_openfigi_batch(batch)
        
        # 更新映射
        existing_mapping.update(batch_result)
        new_mappings += len(batch_result)
        
        print(f"  ✓ 本批次成功映射: {len(batch_result)} 个")
        print(f"  累计新增: {new_mappings} 个")
        
        # 限速：除了最后一批，都要等待
        if batch_num < total_batches:
            print(f"  ⏳ 等待 {delay_seconds} 秒...")
            time.sleep(delay_seconds)
    
    print(f"\n=== 阶段4: 保存结果 ===")
    # 5. 保存更新后的映射
    config_path = "config/cusip_tickers.json"
    with open(config_path, 'w') as f:
        json.dump(existing_mapping, f, indent=2, sort_keys=True)
    
    print(f"✓ 映射已保存到: {config_path}")
    
    # 6. 统计报告
    end_time = datetime.now()
    elapsed = end_time - start_time
    
    total_cusips = len(all_cusips)
    mapped_cusips = len([c for c in all_cusips if c in existing_mapping])
    coverage_rate = (mapped_cusips / total_cusips) * 100 if total_cusips > 0 else 0
    
    print(f"\n=== 🎉 映射完成报告 ===")
    print(f"总耗时: {elapsed}")
    print(f"全部唯一 CUSIP: {total_cusips:,} 个")
    print(f"成功映射 CUSIP: {mapped_cusips:,} 个")
    print(f"本次新增映射: {new_mappings:,} 个")
    print(f"映射覆盖率: {coverage_rate:.1f}%")
    
    return {
        "total_cusips": total_cusips,
        "mapped_cusips": mapped_cusips,
        "new_mappings": new_mappings,
        "coverage_rate": coverage_rate,
        "elapsed_time": str(elapsed)
    }

if __name__ == "__main__":
    try:
        result = main()
        if result:
            print(f"\n✅ 任务完成！映射覆盖率达到 {result['coverage_rate']:.1f}%")
    except KeyboardInterrupt:
        print("\n⚠️  用户中断")
    except Exception as e:
        print(f"\n❌ 脚本执行错误: {e}")
        import traceback
        traceback.print_exc()
