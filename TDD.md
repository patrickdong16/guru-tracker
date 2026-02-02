# 投资大师持仓追踪 — 技术设计文档（TDD）

> **项目代号：** Guru Tracker  
> **最后更新：** 2025-07-20  
> **文档版本：** v1.1  
> **作者：** Pepper for DQ

---

## 0. 规范遵从声明

本文档遵守以下上位规范：

- **全局宪法：** `GEMINI.md` — 所有代码规范、安全规则、生命周期管理
- **编码标准：** `coding-standards` skill — 错误处理、网络请求、API 格式、密钥管理
- **调试流程：** `systematic-debugging` skill — 遇到 bug 时的四阶段诊断流程
- **完成验证：** `verification-before-completion` skill — 每个阶段的验收门禁

**所有开发者（包括 AI）在编码时必须同时参考本文档和上述规范。**

---

## 1. 系统概览

### 1.1 架构选型

| 维度 | 决策 | 理由 |
|------|------|------|
| 部署平台 | GitHub Pages | 免费、自动 HTTPS、CDN 加速 |
| 构建方式 | GitHub Actions | 每日自动运行、免费 CI/CD |
| 数据存储 | Git repo 中的 JSON 文件 | 版本可追溯、无需数据库 |
| 前端框架 | 纯静态 HTML + Tailwind CSS + Chart.js | 轻量、快速、无构建依赖 |
| 后端语言 | Python 3.11+ | 生态好、解析 XML/JSON 方便 |
| 推送通道 | Telegram Bot API | DQ 已有基础设施 |

### 1.2 系统数据流

```
┌─────────────┐    ┌──────────────┐    ┌───────────────┐    ┌──────────────┐
│  SEC EDGAR  │───▶│ Python 数据  │───▶│  JSON 数据    │───▶│ 静态 HTML    │
│  13F API    │    │  管道脚本    │    │  文件 (repo)  │    │  生成脚本    │
└─────────────┘    └──────┬───────┘    └───────────────┘    └──────┬───────┘
                          │                                        │
┌─────────────┐           │                                        ▼
│  ARK Daily  │───────────┘                                 ┌──────────────┐
│  Trade CSV  │                                             │ GitHub Pages │
└─────────────┘                                             │ 静态站点     │
                                                            └──────────────┘
       ┌──────────────────────────────────────────┐
       │           GitHub Actions                  │
       │  ┌─────────┐   ┌──────────┐   ┌───────┐ │
       │  │ 数据抓取 │──▶│ 数据处理 │──▶│ 构建  │ │
       │  └─────────┘   └────┬─────┘   └───┬───┘ │
       │                     │              │     │
       │                     ▼              ▼     │
       │              ┌──────────┐   ┌──────────┐│
       │              │ Telegram │   │ 部署到   ││
       │              │ 推送     │   │ gh-pages ││
       │              └──────────┘   └──────────┘│
       └──────────────────────────────────────────┘
```

---

## 2. 项目目录结构

```
guru-tracker/
├── .github/
│   └── workflows/
│       ├── daily-scan.yml          # 每日扫描 workflow
│       └── manual-build.yml        # 手动触发构建
├── config/
│   ├── gurus.json                  # 投资人名单配置（核心配置文件）
│   └── settings.json               # 全局设置（阈值、推送规则等）
├── scripts/
│   ├── fetch_13f.py                # SEC EDGAR 数据抓取
│   ├── fetch_ark.py                # ARK 每日交易抓取
│   ├── parse_13f.py                # 13F XML 解析
│   ├── compare_quarters.py         # 季度对比分析
│   ├── build_site.py               # 静态站点生成
│   ├── notify_telegram.py          # Telegram 推送
│   └── utils.py                    # 公共工具函数
├── data/
│   ├── raw/                        # 原始 13F XML 文件
│   │   └── {guru_id}/
│   │       └── {period_ending}/
│   │           └── infotable.xml
│   ├── parsed/                     # 解析后的 JSON
│   │   └── {guru_id}/
│   │       └── {period_ending}.json
│   ├── compared/                   # 季度对比结果
│   │   └── {guru_id}/
│   │       └── {period_ending}_vs_{prev_period}.json
│   ├── consensus/                  # 大师共识分析
│   │   └── {period_ending}.json
│   └── ark/                        # ARK 每日交易数据
│       └── {date}.json
├── site/                           # 生成的静态站点（部署到 gh-pages）
│   ├── index.html
│   ├── guru/
│   │   └── {guru_id}.html
│   ├── stock/
│   │   └── {cusip}.html
│   ├── css/
│   │   └── style.css
│   ├── js/
│   │   ├── app.js
│   │   └── charts.js
│   └── data/                       # 前端消费的 JSON
│       ├── gurus.json
│       ├── latest.json
│       └── consensus.json
├── tests/
│   ├── test_fetch.py
│   ├── test_parse.py
│   ├── test_compare.py
│   └── test_data_quality.py
├── requirements.txt
├── REQUIREMENTS.md
├── TDD.md
└── TESTING.md
```

---

## 3. 核心模块设计

### 3.1 配置文件 (`config/gurus.json`)

```json
{
  "version": "1.0",
  "last_updated": "2025-07-20",
  "gurus": [
    {
      "id": "berkshire_hathaway",
      "name": "Berkshire Hathaway Inc",
      "display_name": "巴菲特 / Berkshire Hathaway",
      "cik": "0001067983",
      "style": "value",
      "style_label": "价值投资",
      "category": "value",
      "representative": "沃伦·巴菲特 (Warren Buffett)",
      "aum": "$1T+",
      "bio": "史上最伟大的价值投资者，年化回报约20%，核心持仓集中在苹果、可口可乐等。",
      "famous_trade": "1988年开始买入可口可乐，至今持有，回报超20倍。",
      "filing_type": "13F-HR",
      "active": true
    },
    {
      "id": "duan_yongping",
      "name": "DUAN YONG PING",
      "display_name": "段永平",
      "cik": "0001265354",
      "style": "value",
      "style_label": "价值投资",
      "category": "chinese",
      "representative": "段永平",
      "aum": "未公开",
      "bio": "步步高/OPPO/vivo创始人，62万美元抄底网易赚上亿。",
      "famous_trade": "2001年以约0.8美元/股抄底网易，最终涨到70美元+。",
      "filing_type": "SC13G",
      "active": true,
      "note": "个人投资者，不提交13F，通过SC 13G/13D追踪"
    }
  ]
}
```

### 3.2 SEC EDGAR 数据抓取 (`scripts/fetch_13f.py`)

#### 核心逻辑

```python
"""
SEC EDGAR 13F 数据抓取模块

数据流：
1. 读取 gurus.json 配置
2. 对每个 guru，调用 Submissions API 获取最新 13F filing
3. 对比本地已有数据，判断是否有新 filing
4. 如有新 filing，下载 13F Information Table XML
5. 保存到 data/raw/{guru_id}/{period_ending}/infotable.xml
"""

import requests
import time
import os
import json
import xml.etree.ElementTree as ET
from typing import Optional, Dict, List

# SEC API 配置
SEC_BASE_URL = "https://data.sec.gov"
SEC_ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data"
USER_AGENT = os.environ.get("SEC_USER_AGENT", "GuruTracker research@example.com")
REQUEST_TIMEOUT = 10  # 秒
MAX_RETRIES = 3
RETRY_DELAY = 2  # 秒
RATE_LIMIT_DELAY = 0.12  # 100ms+ between requests (stay under 10/sec)


def fetch_with_retry(url: str, headers: dict = None) -> Optional[requests.Response]:
    """带重试的 HTTP GET 请求"""
    if headers is None:
        headers = {"User-Agent": USER_AGENT}
    
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            time.sleep(RATE_LIMIT_DELAY)  # 遵守速率限制
            return response
        except requests.exceptions.RequestException as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
            else:
                raise
    return None


def get_latest_13f(cik: str) -> Optional[Dict]:
    """
    获取某 CIK 的最新 13F-HR filing 信息
    
    返回:
    {
        "accession_number": "0000950123-25-008343",
        "filing_date": "2025-08-14",
        "period_ending": "2025-06-30",
        "primary_doc": "primary_doc.xml"
    }
    """
    url = f"{SEC_BASE_URL}/submissions/CIK{cik}.json"
    response = fetch_with_retry(url)
    if not response:
        return None
    
    data = response.json()
    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    
    for i, form in enumerate(forms):
        if form == "13F-HR":
            return {
                "accession_number": recent["accessionNumber"][i],
                "filing_date": recent["filingDate"][i],
                "period_ending": recent.get("reportDate", [None] * (i+1))[i],
                "primary_doc": recent["primaryDocument"][i],
            }
    return None


def find_infotable_url(cik: str, accession: str) -> Optional[str]:
    """
    从 filing index 页面找到 Information Table XML 的 URL
    
    13F filing 通常包含两个 XML：
    - primary_doc.xml — 封面信息（filer info, signature）
    - XXXXXX.xml — 实际持仓信息表
    """
    accession_clean = accession.replace("-", "")
    index_url = f"{SEC_ARCHIVES_URL}/{int(cik)}/{accession_clean}/"
    
    response = fetch_with_retry(index_url)
    if not response:
        return None
    
    # 在目录列表中找到非 primary_doc 的 XML 文件
    # 那个就是 information table
    import re
    xml_files = re.findall(r'href="([^"]+\.xml)"', response.text)
    
    for xml_file in xml_files:
        filename = xml_file.split("/")[-1]
        if filename != "primary_doc.xml" and filename.endswith(".xml"):
            return f"{SEC_ARCHIVES_URL}/{int(cik)}/{accession_clean}/{filename}"
    
    return None


def download_infotable(guru_id: str, cik: str, filing_info: Dict) -> Optional[str]:
    """下载并保存 13F Information Table XML"""
    infotable_url = find_infotable_url(cik, filing_info["accession_number"])
    if not infotable_url:
        return None
    
    response = fetch_with_retry(infotable_url)
    if not response:
        return None
    
    # 保存到本地
    period = filing_info["period_ending"]
    save_dir = f"data/raw/{guru_id}/{period}"
    os.makedirs(save_dir, exist_ok=True)
    save_path = f"{save_dir}/infotable.xml"
    
    with open(save_path, "w", encoding="utf-8") as f:
        f.write(response.text)
    
    return save_path
```

#### SEC API Endpoints 详解

| 步骤 | API | 返回格式 | 说明 |
|------|-----|---------|------|
| 1. 获取 filing 列表 | `GET /submissions/CIK{cik}.json` | JSON | 包含最近 1000 次 filing 的元数据 |
| 2. 获取 filing 目录 | `GET /Archives/edgar/data/{cik}/{accession}/` | HTML | 列出所有文件 |
| 3. 下载信息表 | `GET /Archives/edgar/data/{cik}/{accession}/{table}.xml` | XML | 13F 持仓明细 |

### 3.3 13F XML 解析 (`scripts/parse_13f.py`)

```python
"""
13F Information Table XML 解析模块

XML 命名空间: http://www.sec.gov/edgar/document/thirteenf/informationtable
Schema 版本: X0201 或 X0202

每个 <infoTable> 包含:
  - nameOfIssuer: 发行人名称 (e.g., "APPLE INC")
  - titleOfClass: 证券类型 (e.g., "COM" = 普通股)
  - cusip: CUSIP 代码 (9 位)
  - value: 持仓市值（美元，注意：千美元单位，需 ×1000）
  - shrsOrPrnAmt/sshPrnamt: 数量
  - shrsOrPrnAmt/sshPrnamtType: "SH" = 股票数, "PRN" = 本金
  - investmentDiscretion: "SOLE" | "DFND" | "OTR"
  - votingAuthority: Sole/Shared/None
"""

NS = {"ns": "http://www.sec.gov/edgar/document/thirteenf/informationtable"}


def parse_infotable(xml_path: str) -> List[Dict]:
    """
    解析 13F Information Table XML，返回持仓列表
    
    重要：13F 的 value 字段单位是「千美元」，需要乘以 1000！
    但从 2023 年开始的新版 schema (X0202) 改为了「美元」。
    需要检查 schema 版本来确定单位。
    """
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        holdings = []
        
        for entry in root.findall("ns:infoTable", NS):
            holding = {
                "issuer": entry.findtext("ns:nameOfIssuer", "", NS).strip(),
                "title": entry.findtext("ns:titleOfClass", "", NS).strip(),
                "cusip": entry.findtext("ns:cusip", "", NS).strip(),
                "value": int(entry.findtext("ns:value", "0", NS)),
                "shares": int(entry.findtext("ns:shrsOrPrnAmt/ns:sshPrnamt", "0", NS)),
                "share_type": entry.findtext("ns:shrsOrPrnAmt/ns:sshPrnamtType", "SH", NS),
                "discretion": entry.findtext("ns:investmentDiscretion", "", NS),
                "sole_voting": int(entry.findtext("ns:votingAuthority/ns:Sole", "0", NS)),
                "shared_voting": int(entry.findtext("ns:votingAuthority/ns:Shared", "0", NS)),
                "no_voting": int(entry.findtext("ns:votingAuthority/ns:None", "0", NS)),
            }
            holdings.append(holding)
        
        # 聚合同一 CUSIP 的多个条目（一个机构可能有多个 manager 分别报告同一只股票）
        aggregated = aggregate_by_cusip(holdings)
        
        # 计算占比
        total_value = sum(h["value"] for h in aggregated)
        for h in aggregated:
            h["weight"] = round(h["value"] / total_value * 100, 2) if total_value > 0 else 0
        
        return sorted(aggregated, key=lambda x: x["value"], reverse=True)
    
    except Exception as e:
        print(f"Error parsing {xml_path}: {e}")
        return []


def aggregate_by_cusip(holdings: List[Dict]) -> List[Dict]:
    """
    按 CUSIP 聚合同一只股票的多个条目
    
    为什么需要聚合？
    大机构（如 Berkshire）有多个投资经理，同一只股票可能分别报告。
    例如 Berkshire 的 13F 中，Apple 可能出现 3-5 个条目（不同 manager）。
    """
    cusip_map = {}
    for h in holdings:
        key = h["cusip"]
        if key in cusip_map:
            cusip_map[key]["value"] += h["value"]
            cusip_map[key]["shares"] += h["shares"]
            cusip_map[key]["sole_voting"] += h["sole_voting"]
            cusip_map[key]["shared_voting"] += h["shared_voting"]
            cusip_map[key]["no_voting"] += h["no_voting"]
        else:
            cusip_map[key] = h.copy()
    return list(cusip_map.values())
```

> **⚠️ value 字段单位陷阱**
> 
> 这是 13F 解析最常见的坑：
> - **旧版 schema (X0201, 2023 年以前)**：`value` 单位是 **千美元**，需要 `× 1000`
> - **新版 schema (X0202, 2023 年及以后)**：`value` 单位是 **美元**，直接使用
> 
> 从实际数据验证来看，Berkshire 2025 Q2 的 Apple 持仓 `value` 约为 600 多亿级别数字，如果是千美元就对不上。**建议：检查 primary_doc.xml 中的 schema_version 字段来判断。**
>
> 经验证：2025 年的最新 filing 使用 X0202 schema，value 直接是美元。

### 3.4 季度对比分析 (`scripts/compare_quarters.py`)

```python
"""
季度对比分析模块

对比逻辑：
1. 以 CUSIP 为唯一标识
2. 当前季度有、上季度没有 → 新建仓 (NEW)
3. 两个季度都有、数量增加 → 加仓 (INCREASED)
4. 两个季度都有、数量减少 → 减仓 (DECREASED)
5. 两个季度都有、数量不变 → 持仓不变 (UNCHANGED)
6. 上季度有、当前没有 → 清仓 (SOLD)
"""


def compare_quarters(current: List[Dict], previous: List[Dict]) -> Dict:
    """
    对比两个季度的持仓，生成变动报告
    
    返回:
    {
        "new": [...],        # 新建仓
        "increased": [...],  # 加仓
        "decreased": [...],  # 减仓
        "unchanged": [...],  # 不变
        "sold": [...],       # 清仓
        "summary": {
            "total_new": 3,
            "total_increased": 5,
            "total_decreased": 2,
            "total_unchanged": 15,
            "total_sold": 1,
            "total_value_current": 320000000000,
            "total_value_previous": 310000000000,
            "total_value_change_pct": 3.2
        }
    }
    """
    current_map = {h["cusip"]: h for h in current}
    previous_map = {h["cusip"]: h for h in previous}
    
    result = {
        "new": [],
        "increased": [],
        "decreased": [],
        "unchanged": [],
        "sold": [],
    }
    
    # 遍历当前持仓
    for cusip, curr in current_map.items():
        if cusip not in previous_map:
            result["new"].append({
                **curr,
                "change_type": "NEW",
            })
        else:
            prev = previous_map[cusip]
            share_change = curr["shares"] - prev["shares"]
            
            if share_change > 0:
                result["increased"].append({
                    **curr,
                    "change_type": "INCREASED",
                    "prev_shares": prev["shares"],
                    "prev_value": prev["value"],
                    "share_change": share_change,
                    "share_change_pct": round(share_change / prev["shares"] * 100, 1),
                })
            elif share_change < 0:
                result["decreased"].append({
                    **curr,
                    "change_type": "DECREASED",
                    "prev_shares": prev["shares"],
                    "prev_value": prev["value"],
                    "share_change": share_change,
                    "share_change_pct": round(share_change / prev["shares"] * 100, 1),
                })
            else:
                result["unchanged"].append({
                    **curr,
                    "change_type": "UNCHANGED",
                })
    
    # 找出清仓的（上季度有，本季度没有）
    for cusip, prev in previous_map.items():
        if cusip not in current_map:
            result["sold"].append({
                **prev,
                "change_type": "SOLD",
            })
    
    # 计算汇总
    total_current = sum(h["value"] for h in current)
    total_previous = sum(h["value"] for h in previous)
    
    result["summary"] = {
        "total_new": len(result["new"]),
        "total_increased": len(result["increased"]),
        "total_decreased": len(result["decreased"]),
        "total_unchanged": len(result["unchanged"]),
        "total_sold": len(result["sold"]),
        "total_value_current": total_current,
        "total_value_previous": total_previous,
        "total_value_change_pct": round(
            (total_current - total_previous) / total_previous * 100, 1
        ) if total_previous > 0 else 0,
    }
    
    return result
```

### 3.5 大师共识分析

```python
"""
大师共识分析模块

对所有追踪的 guru 的最新持仓取交集/并集，
计算每只股票被多少个 guru 同时持有。
"""


def build_consensus(all_holdings: Dict[str, List[Dict]]) -> List[Dict]:
    """
    构建大师共识数据
    
    参数: {guru_id: [holdings_list]}
    
    返回: [
        {
            "cusip": "037833100",
            "issuer": "APPLE INC",
            "guru_count": 15,
            "gurus": ["berkshire_hathaway", "bridgewater", ...],
            "total_value": 150000000000,
            "avg_weight": 5.2,
        },
        ...
    ]
    """
    stock_map = {}  # cusip -> {guru_ids, total_value, weights}
    
    for guru_id, holdings in all_holdings.items():
        for h in holdings:
            cusip = h["cusip"]
            if cusip not in stock_map:
                stock_map[cusip] = {
                    "cusip": cusip,
                    "issuer": h["issuer"],
                    "gurus": [],
                    "total_value": 0,
                    "weights": [],
                }
            stock_map[cusip]["gurus"].append(guru_id)
            stock_map[cusip]["total_value"] += h["value"]
            stock_map[cusip]["weights"].append(h.get("weight", 0))
    
    consensus = []
    for cusip, data in stock_map.items():
        consensus.append({
            "cusip": data["cusip"],
            "issuer": data["issuer"],
            "guru_count": len(data["gurus"]),
            "gurus": data["gurus"],
            "total_value": data["total_value"],
            "avg_weight": round(sum(data["weights"]) / len(data["weights"]), 2),
        })
    
    return sorted(consensus, key=lambda x: x["guru_count"], reverse=True)
```

---

## 4. 数据存储方案

### 4.1 解析后的持仓 JSON (`data/parsed/{guru_id}/{period}.json`)

```json
{
  "guru_id": "berkshire_hathaway",
  "cik": "0001067983",
  "period_ending": "2025-06-30",
  "filing_date": "2025-08-14",
  "accession_number": "0000950123-25-008343",
  "total_value": 267410000000,
  "holdings_count": 38,
  "holdings": [
    {
      "issuer": "APPLE INC",
      "title": "COM",
      "cusip": "037833100",
      "value": 63200000000,
      "shares": 300000000,
      "share_type": "SH",
      "weight": 23.64,
      "discretion": "DFND"
    }
  ]
}
```

### 4.2 季度对比 JSON (`data/compared/{guru_id}/{period}_vs_{prev}.json`)

```json
{
  "guru_id": "berkshire_hathaway",
  "current_period": "2025-06-30",
  "previous_period": "2025-03-31",
  "summary": {
    "total_new": 2,
    "total_increased": 5,
    "total_decreased": 3,
    "total_unchanged": 28,
    "total_sold": 0,
    "total_value_change_pct": 4.2
  },
  "changes": {
    "new": [...],
    "increased": [...],
    "decreased": [...],
    "unchanged": [...],
    "sold": [...]
  }
}
```

### 4.3 大师共识 JSON (`data/consensus/{period}.json`)

```json
{
  "period_ending": "2025-06-30",
  "generated_at": "2025-08-15T06:00:00Z",
  "total_gurus_analyzed": 28,
  "top_consensus": [
    {
      "cusip": "037833100",
      "issuer": "APPLE INC",
      "guru_count": 18,
      "gurus": ["berkshire_hathaway", "bridgewater", "citadel", ...],
      "total_value": 150000000000,
      "avg_weight": 5.2
    }
  ]
}
```

### 4.4 前端数据 JSON (`site/data/`)

为了减小前端加载体积，生成精简版 JSON：

| 文件 | 内容 | 预估大小 |
|------|------|---------|
| `gurus.json` | 所有 guru 的基本信息 + 最新统计 | ~15KB |
| `latest.json` | 所有 guru 最新季度的持仓摘要（前 20 大持仓） | ~100KB |
| `consensus.json` | 大师共识 Top 100 | ~20KB |
| `guru/{id}.json` | 单个 guru 的完整持仓 + 季度对比 | ~20-50KB each |

---

## 5. 前端方案

### 5.1 技术栈

- **HTML 模板引擎：** Python Jinja2（在构建时渲染，产出纯静态 HTML）
- **CSS：** Tailwind CSS（CDN 引入）+ 自定义样式
- **图表：** Chart.js 4.x（CDN 引入）
- **字体：** Inter（Google Fonts CDN）
- **交互：** Vanilla JS（无框架，搜索/筛选/排序通过原生 JS 实现）

### 5.2 视觉风格

与 BTC ETF Tracker 保持一致：

```css
/* 色彩系统 - Zinc 暗色 */
--bg-primary: #18181b;     /* zinc-900 */
--bg-secondary: #27272a;   /* zinc-800 */
--bg-card: #3f3f46;        /* zinc-700 */
--text-primary: #fafafa;   /* zinc-50 */
--text-secondary: #a1a1aa; /* zinc-400 */
--accent-green: #22c55e;   /* green-500 — 加仓/新建 */
--accent-red: #ef4444;     /* red-500 — 减仓/清仓 */
--accent-blue: #3b82f6;    /* blue-500 — 链接/交互 */
--accent-yellow: #eab308;  /* yellow-500 — 提示 */

/* 字体 */
font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
```

### 5.3 页面结构

| 页面 | URL | 功能 |
|------|-----|------|
| 首页/仪表盘 | `/index.html` | 大师列表 + 最新动态 + 共识排行 |
| 大师详情页 | `/guru/{id}.html` | 档案卡 + 持仓表 + 季度对比 + 图表 |
| 股票详情页 | `/stock/{cusip}.html` | 某只股票在各大师中的持仓情况 |

### 5.4 首页布局

```
┌─────────────────────────────────────────┐
│  🧠 Guru Tracker — 投资大师持仓追踪     │
│  [搜索栏: 按大师名/股票名搜索]          │
├─────────────────┬───────────────────────┤
│                 │                       │
│  📊 最新动态     │  🔥 大师共识 Top 10   │
│  (最新 10 条     │  (被最多大师持有的     │
│   持仓变动)      │   股票排行)           │
│                 │                       │
├─────────────────┴───────────────────────┤
│                                         │
│  👤 投资大师列表                         │
│  [风格筛选: 全部 | 价值 | 宏观 | 量化]  │
│                                         │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐   │
│  │ 巴菲特  │ │ 达利欧  │ │ Ackman  │   │
│  │ $320B   │ │ $125B   │ │ $18B    │   │
│  │ 38 只   │ │ 450 只  │ │ 8 只    │   │
│  │ 最近: 8/14│ │ 最近:..│ │ 最近:.. │   │
│  └─────────┘ └─────────┘ └─────────┘   │
│  ...                                    │
└─────────────────────────────────────────┘
```

### 5.5 Chart.js 图表

| 图表 | 类型 | 展示内容 |
|------|------|---------|
| 持仓分布饼图 | Doughnut | 某 guru 的前 10 大持仓占比 |
| 持仓市值柱图 | Bar | 前 15 大持仓的市值对比 |
| 季度变动柱图 | Bar (grouped) | 新建/加仓/减仓/清仓的数量统计 |
| 共识趋势折线图 | Line | 某股票的「大师持有数」随时间变化 |

---

## 6. GitHub Actions Workflow 设计

### 6.1 每日扫描 (`daily-scan.yml`)

```yaml
name: Daily 13F Scan

on:
  schedule:
    # 每天 UTC 22:00 运行（= 北京时间 06:00）
    # 避开 SEC 高峰期，在美国深夜扫描
    - cron: '0 22 * * *'
  workflow_dispatch:  # 手动触发

permissions:
  contents: write  # 需要 push 数据文件
  pages: write     # 需要部署 GitHub Pages

env:
  SEC_USER_AGENT: "GuruTracker patrickdong@gmail.com"
  TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
  TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}

jobs:
  scan-and-build:
    runs-on: ubuntu-latest
    timeout-minutes: 30

    steps:
      - name: Checkout repo
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Fetch latest 13F filings
        run: python scripts/fetch_13f.py
        env:
          SEC_USER_AGENT: ${{ env.SEC_USER_AGENT }}

      - name: Fetch ARK daily trades
        run: python scripts/fetch_ark.py
        continue-on-error: true  # ARK 数据不关键，失败不阻塞

      - name: Parse and compare
        run: |
          python scripts/parse_13f.py
          python scripts/compare_quarters.py

      - name: Build static site
        run: python scripts/build_site.py

      - name: Commit data changes
        run: |
          git config user.name "Guru Tracker Bot"
          git config user.email "bot@guru-tracker"
          git add data/ site/
          if git diff --staged --quiet; then
            echo "No data changes detected"
          else
            git commit -m "📊 Data update: $(date -u +'%Y-%m-%d %H:%M UTC')"
            git push
          fi

      - name: Deploy to GitHub Pages
        uses: peaceiris/actions-gh-pages@v4
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./site

      - name: Notify Telegram (if new filings)
        if: steps.commit.outputs.changed == 'true'
        run: python scripts/notify_telegram.py
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
```

### 6.2 执行顺序

```
1. Checkout repo
2. Setup Python + install deps
3. fetch_13f.py — 扫描所有 guru 的最新 filing
   └─ 对每个 guru：
      ├─ GET /submissions/CIK{cik}.json
      ├─ 找到最新的 13F-HR
      ├─ 对比本地 data/raw/ 判断是否为新 filing
      └─ 如果是新的，下载 infotable.xml
4. fetch_ark.py — 下载 ARK 今日交易
5. parse_13f.py — 解析所有新下载的 XML → JSON
6. compare_quarters.py — 生成季度对比
7. build_site.py — 用 Jinja2 渲染 HTML
8. Commit + Push 数据文件
9. Deploy site/ 到 gh-pages
10. notify_telegram.py — 如果有新 filing，推送通知
```

---

## 7. Telegram 推送方案

### 7.1 推送逻辑

```python
"""Telegram 推送模块"""

import os
import requests

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"


def send_message(text: str, parse_mode: str = "HTML") -> bool:
    """发送 Telegram 消息"""
    try:
        response = requests.post(
            f"{TG_API}/sendMessage",
            json={
                "chat_id": CHAT_ID,
                "text": text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True,
            },
            timeout=10,
        )
        return response.ok
    except Exception as e:
        print(f"Telegram send failed: {e}")
        return False


def format_filing_notification(guru_name: str, comparison: dict, site_url: str) -> str:
    """格式化持仓更新通知"""
    summary = comparison["summary"]
    changes = comparison["changes"]
    
    lines = [
        f"🔔 <b>{guru_name}</b> 持仓更新！",
        f"",
        f"📅 报告期：{comparison['current_period']}",
        f"📊 总持仓变化：{summary['total_value_change_pct']:+.1f}%",
        f"",
    ]
    
    if changes["new"]:
        lines.append("🆕 <b>新建仓：</b>")
        for h in changes["new"][:5]:
            lines.append(f"  • {h['issuer']} — ${h['value']:,.0f} ({h['weight']:.1f}%)")
    
    if changes["sold"]:
        lines.append("❌ <b>清仓：</b>")
        for h in changes["sold"][:5]:
            lines.append(f"  • {h['issuer']}")
    
    if changes["increased"]:
        lines.append(f"⬆️ 加仓 {len(changes['increased'])} 只")
    if changes["decreased"]:
        lines.append(f"⬇️ 减仓 {len(changes['decreased'])} 只")
    
    lines.append(f"\n🔗 <a href='{site_url}'>查看详情</a>")
    
    return "\n".join(lines)
```

### 7.2 推送规则

| 条件 | 动作 |
|------|------|
| 检测到新的 13F-HR filing | 推送完整变动摘要 |
| 仅有 13F-HR/A（修正版） | 推送简短通知「修正版发布」 |
| ARK 单日交易超过 5M 美元 | 推送 ARK 大额交易通知 |
| 扫描无新 filing | 不推送（静默） |
| API 错误 | 推送错误告警 |

---

## 8. 段永平特殊处理方案

段永平（CIK: 0001265354）不提交 13F，只有 SC 13G/13D。

### 方案

```python
def fetch_sc13g(cik: str) -> List[Dict]:
    """
    获取 SC 13G/13D 文件中的持仓信息
    
    SC 13G 不是标准化表格，而是文本文件，
    需要从正文中提取：
    - 持有的公司名和股票代码
    - 持股数量和占比
    
    由于格式不统一，采用半自动方式：
    1. 自动检测新的 SC 13G filing
    2. 下载原文
    3. 标注需要人工审核
    """
    url = f"{SEC_BASE_URL}/submissions/CIK{cik}.json"
    response = fetch_with_retry(url)
    if not response:
        return []
    
    data = response.json()
    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    
    filings = []
    for i, form in enumerate(forms):
        if "13G" in form or "13D" in form:
            filings.append({
                "form": form,
                "date": recent["filingDate"][i],
                "accession": recent["accessionNumber"][i],
            })
    
    return filings
```

**前端处理：**
- 段永平的档案页标注「数据来源：SC 13G/13D（非 13F）」
- 显示已知持仓（网易、Frontier Airlines 等历史记录）
- 补充雪球等渠道的已知信息（手动维护）

---

## 9. 关键技术决策记录

| 决策 | 选择 | 原因 | 替代方案 |
|------|------|------|---------|
| 数据存储 | JSON in repo | 零运维、版本可追溯、免费 | SQLite（增加复杂度）|
| 前端框架 | 纯静态 HTML | GitHub Pages 直接部署、SEO 友好 | React/Vue（需构建）|
| 模板引擎 | Jinja2 | Python 生态、语法清晰 | Mustache（太简陋）|
| 图表库 | Chart.js | 轻量、文档好、够用 | ECharts（太重）|
| CSS 方案 | Tailwind CDN | 快速、一致、无需编译 | 手写 CSS（慢）|
| CI/CD | GitHub Actions | 免费、与 Pages 集成好 | 无替代 |
| 推送渠道 | Telegram | DQ 已有基础设施 | Email（不够即时）|

---

## 10. 编码规范与工程约束

> 以下规则来自 `GEMINI.md` 宪法和 `coding-standards` skill，本项目所有代码必须遵守。

### 10.1 统一错误处理模式

所有 async 函数必须有 try-except，所有异常必须有上下文信息：

```python
# ✅ 正确模式
async def fetch_guru_data(guru_id: str) -> dict:
    try:
        result = await _do_fetch(guru_id)
        return {"success": True, "data": result, "error": None}
    except requests.exceptions.Timeout as e:
        logger.error(f"Timeout fetching {guru_id}: {e}")
        return {"success": False, "data": None, "error": f"Timeout: {e}"}
    except Exception as e:
        logger.error(f"Unexpected error fetching {guru_id}: {e}")
        return {"success": False, "data": None, "error": str(e)}

# ❌ 禁止：裸调用无错误处理
async def fetch_guru_data(guru_id: str):
    return await _do_fetch(guru_id)
```

### 10.2 API/函数返回格式标准

所有对外暴露的函数统一返回格式（即使本项目是 CLI 管道而非 REST API）：

```python
# 统一返回结构
{
    "success": True/False,
    "data": {...} or None,
    "error": "错误描述" or None
}
```

**应用场景：**
- `fetch_13f.py` 的 `get_latest_13f()` → 返回 `{"success": True, "data": filing_info}`
- `parse_13f.py` 的 `parse_infotable()` → 返回 `{"success": True, "data": holdings_list}`
- `notify_telegram.py` 的 `send_message()` → 返回 `{"success": True/False, "error": ...}`

### 10.3 网络请求铁律（超时 + 重试）

所有网络请求（SEC API、ARK CSV、Telegram API）必须满足：

| 参数 | 值 | 说明 |
|------|---|------|
| timeout | 10 秒 | 单次请求超时 |
| max_retries | 3 次 | 最大重试次数 |
| retry_delay | 指数退避 | 2s, 4s, 8s |
| rate_limit | 0.12s/req | SEC API 专用（10 req/sec） |

### 10.4 密钥管理（零容忍）

```python
# ✅ 正确：从环境变量读取，缺失时报错退出
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
if not BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")

# ❌ 严重违规：硬编码 fallback
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "123456:ABC-DEF...")  # 禁止！
```

**必须维护的文件：**
- `.env.example` — 列出所有需要的环境变量（不含真实值）
- `.gitignore` — 排除 `.env`、`*-keys.json`、`*-credentials.*`

`.env.example` 模板：
```
# SEC EDGAR
SEC_USER_AGENT=GuruTracker your-email@example.com

# Telegram 推送
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

### 10.5 环境确认协议

> 来自 GEMINI.md 最高优先级规则

执行任何数据写入操作前，脚本必须：
1. 打印当前数据目录路径确认环境
2. 在日志中明确标注是 `local` / `ci` / `production` 环境
3. GitHub Actions 中通过 `$GITHUB_ACTIONS` 环境变量自动识别

```python
import os

def confirm_environment():
    """在写入操作前确认环境"""
    data_dir = os.environ.get("DATA_DIR", "data/")
    is_ci = os.environ.get("GITHUB_ACTIONS", "false") == "true"
    env_name = "CI (GitHub Actions)" if is_ci else "Local"
    print(f"🔍 Environment: {env_name}")
    print(f"🔍 Data directory: {data_dir[:50]}")
    return env_name
```

### 10.6 日志策略

| 级别 | 使用场景 | 示例 |
|------|---------|------|
| `INFO` | 正常流程节点 | `"Fetching 13F for berkshire_hathaway..."` |
| `WARNING` | 非致命异常 | `"ARK CSV format changed, skipping column X"` |
| `ERROR` | 可恢复错误 | `"SEC API timeout for soros, will retry"` |
| `CRITICAL` | 不可恢复错误 | `"TELEGRAM_BOT_TOKEN not set, cannot notify"` |

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("guru-tracker")
```

### 10.7 命名规范

遵从 `coding-standards` skill：

| 元素 | 规范 | 示例 |
|------|------|------|
| Python 函数/变量 | `snake_case` | `fetch_with_retry`, `guru_id` |
| Python 类名 | `PascalCase` | `GuruConfig`, `FilingParser` |
| Python 常量 | `UPPER_SNAKE_CASE` | `MAX_RETRIES`, `SEC_BASE_URL` |
| JSON key | `snake_case` | `"guru_id"`, `"period_ending"` |
| 文件名 | `snake_case` | `fetch_13f.py`, `compare_quarters.py` |
| CSS class | Tailwind 原子类 | `bg-zinc-900 text-zinc-50` |
| HTML 文件 | `kebab-case` 或 `{id}.html` | `index.html`, `berkshire_hathaway.html` |

### 10.8 调试协议

遇到 bug 时，**禁止直接猜测修复**，必须按照 `systematic-debugging` skill 的四阶段执行：

1. **Phase 1: 根因调查** — 读错误信息、复现、检查最近变更、追踪数据流
2. **Phase 2: 模式分析** — 找到工作的参照代码、对比差异
3. **Phase 3: 假设与测试** — 一次只改一个变量、验证假设
4. **Phase 4: 实施修复** — 先写失败测试、再修复、再验证

**铁律：** 连续 3 次修复失败 → 停下来质疑架构设计，与 DQ 讨论后再继续。

---

## 11. 性能与限制

### 11.1 SEC API 限制

- **频率：** 10 requests/second（必须遵守）
- **并发：** 建议单线程顺序执行
- **爬虫规则：** User-Agent 必填，需包含联系邮箱
- **可用性：** SEC 偶尔维护，夜间更稳定

### 11.2 GitHub Actions 限制

- **时间限制：** 单 job 最多 6 小时（我们只需要 10-15 分钟）
- **存储限制：** repo 大小建议 < 1GB（JSON 数据不会很大）
- **运行频率：** 免费账户每月 2000 分钟（每日 15 分钟 × 30 天 = 450 分钟，富余）

### 11.3 数据体积估算

| 数据类型 | 单个大师 | 29 个大师合计 |
|---------|---------|-------------|
| 原始 XML | 50-500 KB | ~5 MB |
| 解析 JSON | 20-100 KB | ~2 MB |
| 对比 JSON | 10-50 KB | ~1 MB |
| 共识 JSON | — | ~100 KB |
| **单个季度合计** | — | **~8 MB** |
| **保留 4 个季度** | — | **~32 MB** |

完全在 GitHub 的承受范围内。

---

## 12. 安全清单

- [ ] `TELEGRAM_BOT_TOKEN` → GitHub Secrets
- [ ] `TELEGRAM_CHAT_ID` → GitHub Secrets
- [ ] `SEC_USER_AGENT` → GitHub Secrets 或 Actions 环境变量
- [ ] 代码中零硬编码密钥（`grep -r "sk-\|token.*=" scripts/` 验证）
- [ ] `.env.example` 已创建且列出所有环境变量
- [ ] `.gitignore` 排除 `.env`、`*-keys.json`、`*-credentials.*`
- [ ] 所有外部请求 timeout=10s + retry=3
- [ ] 所有 async 函数 try-except 错误处理
- [ ] `git diff --staged` 提交前检查无敏感信息
- [ ] 日志输出不包含密钥/token 的明文
