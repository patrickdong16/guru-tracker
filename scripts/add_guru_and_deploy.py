#!/usr/bin/env python3
"""
添加新 guru 并自动部署到 GitHub Pages

用法：
  python3 scripts/add_guru_and_deploy.py

会提示输入 guru 信息，然后自动：
1. 添加到 gurus.json
2. 运行数据管线（fetch + parse + compare）
3. 生成网站
4. Git commit + push
"""

import json
import sys
import subprocess
from pathlib import Path
from datetime import datetime

# 路径
WORKSPACE = Path(__file__).parent.parent
CONFIG_FILE = WORKSPACE / "config/gurus.json"


def load_config():
    """加载现有配置"""
    with open(CONFIG_FILE) as f:
        return json.load(f)


def save_config(data):
    """保存配置"""
    data['last_updated'] = datetime.now().strftime('%Y-%m-%d')
    with open(CONFIG_FILE, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"✅ 配置已保存: {CONFIG_FILE}")


def add_guru(guru_data):
    """添加 guru 到配置"""
    config = load_config()
    
    # 检查是否已存在
    if any(g['id'] == guru_data['id'] for g in config['gurus']):
        print(f"⚠️ Guru {guru_data['id']} 已存在，跳过")
        return False
    
    # 插入到对应类别
    category = guru_data.get('category', 'value')
    inserted = False
    for i, guru in enumerate(config['gurus']):
        if guru['category'] == category and not inserted:
            config['gurus'].insert(i, guru_data)
            inserted = True
            break
    
    if not inserted:
        config['gurus'].append(guru_data)
    
    save_config(config)
    print(f"✅ 已添加: {guru_data['display_name']} (CIK: {guru_data['cik']})")
    return True


def run_pipeline():
    """运行数据管线"""
    print("\n📊 运行数据管线...")
    result = subprocess.run(
        ["python3", "main.py"],
        cwd=WORKSPACE,
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print(f"❌ 数据管线失败:\n{result.stderr}")
        return False
    
    print("✅ 数据管线完成")
    return True


def generate_site():
    """生成网站"""
    print("\n🌐 生成网站...")
    result = subprocess.run(
        ["python3", "scripts/generate_site.py"],
        cwd=WORKSPACE,
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print(f"❌ 网站生成失败:\n{result.stderr}")
        return False
    
    print("✅ 网站生成完成")
    return True


def git_deploy(message):
    """Git commit + push"""
    print("\n🚀 部署到 GitHub Pages...")
    
    # git add
    subprocess.run(["git", "add", "-A"], cwd=WORKSPACE, check=True)
    
    # git commit
    result = subprocess.run(
        ["git", "commit", "-m", message],
        cwd=WORKSPACE,
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        if "nothing to commit" in result.stdout:
            print("⚠️ 没有变更，跳过部署")
            return True
        print(f"❌ Git commit 失败:\n{result.stderr}")
        return False
    
    # git push
    result = subprocess.run(
        ["git", "push", "origin", "main"],
        cwd=WORKSPACE,
        capture_output=True,
        text=True,
        timeout=60
    )
    
    if result.returncode != 0:
        print(f"❌ Git push 失败:\n{result.stderr}")
        return False
    
    print("✅ 部署成功！")
    print("🌐 网站将在 1-2 分钟后更新")
    return True


def main():
    """主流程"""
    # 示例：从命令行参数读取 guru 数据（JSON 格式）
    # 或者从其他地方获取
    
    if len(sys.argv) < 2:
        print("用法: python3 scripts/add_guru_and_deploy.py '<guru_json>'")
        print("或者直接调用 add_guru_and_deploy(guru_data) 函数")
        sys.exit(1)
    
    try:
        guru_data = json.loads(sys.argv[1])
    except json.JSONDecodeError:
        print("❌ 无效的 JSON 格式")
        sys.exit(1)
    
    # 执行流程
    if not add_guru(guru_data):
        print("⚠️ Guru 未添加，中止部署")
        sys.exit(0)
    
    if not run_pipeline():
        print("❌ 数据管线失败，中止部署")
        sys.exit(1)
    
    if not generate_site():
        print("❌ 网站生成失败，中止部署")
        sys.exit(1)
    
    commit_msg = f"feat: add {guru_data['display_name']} (CIK {guru_data['cik']})"
    if not git_deploy(commit_msg):
        print("❌ 部署失败")
        sys.exit(1)
    
    print(f"\n🎉 完成！{guru_data['display_name']} 已添加并部署")


if __name__ == "__main__":
    main()
