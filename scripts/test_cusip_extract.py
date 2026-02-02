#!/usr/bin/env python3
"""测试 CUSIP 提取功能"""

import json
import os
import glob
import sys

def test_extract():
    print("=== 测试 CUSIP 提取 ===")
    
    os.chdir("/Users/dq/.openclaw/workspace/guru-tracker")
    print(f"当前目录: {os.getcwd()}")
    
    # 检查 data/parsed 目录
    if not os.path.exists("data/parsed"):
        print("错误: data/parsed 目录不存在")
        return
    
    json_files = glob.glob("data/parsed/*/*.json")
    print(f"找到 {len(json_files)} 个 JSON 文件")
    
    if not json_files:
        print("错误: 没有找到 JSON 文件")
        return
    
    # 测试读取第一个文件
    first_file = json_files[0]
    print(f"测试文件: {first_file}")
    
    try:
        with open(first_file, 'r') as f:
            data = json.load(f)
        
        print(f"文件结构键: {list(data.keys())}")
        
        if 'holdings' in data:
            print(f"holdings 数量: {len(data['holdings'])}")
            if data['holdings']:
                first_holding = data['holdings'][0]
                print(f"第一个持仓: {first_holding}")
                
                if 'cusip' in first_holding:
                    print(f"CUSIP 示例: {first_holding['cusip']}")
    
    except Exception as e:
        print(f"读取文件错误: {e}")
    
    # 提取几个 CUSIP 作为测试
    cusips = set()
    for i, file_path in enumerate(json_files[:5]):  # 只测试前5个文件
        print(f"处理文件 {i+1}: {file_path}")
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                
            if 'holdings' in data and isinstance(data['holdings'], list):
                for holding in data['holdings']:
                    if 'cusip' in holding and holding['cusip']:
                        cusip = holding['cusip'].strip()
                        if len(cusip) == 9:
                            cusips.add(cusip)
                            
        except Exception as e:
            print(f"处理文件错误: {e}")
    
    print(f"测试提取到 {len(cusips)} 个唯一 CUSIP")
    print("前 10 个 CUSIP:")
    for i, cusip in enumerate(list(cusips)[:10]):
        print(f"  {i+1}: {cusip}")

if __name__ == "__main__":
    test_extract()