# 投资大师持仓追踪 — 测试策略文档

> **项目代号：** Guru Tracker  
> **最后更新：** 2025-07-20  
> **文档版本：** v1.1  
> **作者：** Pepper for DQ

---

## 0. 规范遵从与验证铁律

本文档遵守以下上位规范：

- **全局宪法：** `GEMINI.md` — 测试必须在编码前完成
- **编码标准：** `coding-standards` skill — 所有代码规范也适用于测试代码
- **调试流程：** `systematic-debugging` skill — 测试失败时的诊断流程
- **完成验证：** `verification-before-completion` skill — 验收门禁

### 验证铁律（来自 `verification-before-completion` skill）

```
NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE
```

**任何阶段声称「完成」之前，必须：**
1. **IDENTIFY** — 什么命令能证明这个声明？
2. **RUN** — 执行完整的验证命令（新鲜运行，不是上次的结果）
3. **READ** — 读完整输出，检查 exit code，数清楚失败数
4. **VERIFY** — 输出是否确认了声明？
5. **THEN** — 带着证据做出声明

**禁止的措辞：** 「应该没问题了」「看起来通过了」「我很有信心」—— 这些不是证据。

---

## 1. 测试哲学

这个项目的核心价值是**数据准确性**。如果巴菲特买了 Apple 你显示成 Amazon，那网站就毫无意义。所以测试优先级：

1. 🔴 **数据正确性** — 最高优先级，必须 100% 覆盖
2. 🟡 **管道可靠性** — 网络中断、API 变动不能崩溃
3. 🟢 **前端展示** — 基本可用即可，不需要像素级测试

---

## 2. 测试层级

```
┌─────────────────────────────────────┐
│         E2E 测试 (端到端)           │  验证全流程跑通
├─────────────────────────────────────┤
│      集成测试 (Integration)         │  模块间配合
├─────────────────┬───────────────────┤
│  单元测试       │  数据质量测试      │  最底层
│  (Unit)        │  (Data Quality)   │
└─────────────────┴───────────────────┘
```

---

## 3. 单元测试

### 3.1 XML 解析测试 (`tests/test_parse.py`)

**这是最关键的测试模块。**

```python
"""
test_parse.py — 13F Information Table XML 解析测试

测试策略：
1. 用真实的 SEC filing XML 作为 fixture（从 SEC 下载并保存）
2. 覆盖不同 schema 版本（X0201 旧版 vs X0202 新版）
3. 覆盖各种边界条件
"""

import pytest
import os
import json

from scripts.parse_13f import parse_infotable, aggregate_by_cusip


# --- Fixtures ---

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture
def berkshire_xml():
    """真实的 Berkshire Hathaway 13F XML（从 SEC 下载的 fixture）"""
    return os.path.join(FIXTURE_DIR, "berkshire_2025q2_infotable.xml")


@pytest.fixture
def small_fund_xml():
    """一个只有几个持仓的小基金 XML"""
    return os.path.join(FIXTURE_DIR, "small_fund_infotable.xml")


@pytest.fixture
def empty_xml():
    """空的信息表（合法但无持仓）"""
    return os.path.join(FIXTURE_DIR, "empty_infotable.xml")


# --- 基础解析测试 ---

class TestBasicParsing:
    
    def test_parse_returns_list(self, berkshire_xml):
        """解析结果应该是列表"""
        result = parse_infotable(berkshire_xml)
        assert isinstance(result, list)
        assert len(result) > 0
    
    def test_holding_has_required_fields(self, berkshire_xml):
        """每个持仓条目必须包含所有必填字段"""
        result = parse_infotable(berkshire_xml)
        required_fields = ["issuer", "title", "cusip", "value", "shares", "share_type", "weight"]
        for holding in result:
            for field in required_fields:
                assert field in holding, f"Missing field: {field}"
    
    def test_cusip_format(self, berkshire_xml):
        """CUSIP 应该是 9 位字母数字"""
        result = parse_infotable(berkshire_xml)
        for h in result:
            assert len(h["cusip"]) == 9, f"Invalid CUSIP length: {h['cusip']}"
    
    def test_value_is_positive(self, berkshire_xml):
        """持仓市值应该是正数"""
        result = parse_infotable(berkshire_xml)
        for h in result:
            assert h["value"] > 0, f"Zero or negative value for {h['issuer']}"
    
    def test_shares_is_positive(self, berkshire_xml):
        """持股数量应该是正数"""
        result = parse_infotable(berkshire_xml)
        for h in result:
            assert h["shares"] > 0, f"Zero or negative shares for {h['issuer']}"
    
    def test_weight_sums_to_100(self, berkshire_xml):
        """所有持仓的权重之和应该约等于 100%"""
        result = parse_infotable(berkshire_xml)
        total_weight = sum(h["weight"] for h in result)
        assert abs(total_weight - 100.0) < 1.0, f"Weights sum to {total_weight}, expected ~100"
    
    def test_sorted_by_value_desc(self, berkshire_xml):
        """结果应该按市值降序排列"""
        result = parse_infotable(berkshire_xml)
        for i in range(len(result) - 1):
            assert result[i]["value"] >= result[i+1]["value"]


# --- Value 单位测试（关键！） ---

class TestValueUnits:
    """
    ⚠️ 最重要的测试之一！
    
    旧版 schema (X0201): value 单位是千美元
    新版 schema (X0202): value 单位是美元
    
    搞错单位 = 市值差 1000 倍 = 灾难
    """
    
    def test_berkshire_apple_value_sanity(self, berkshire_xml):
        """
        Berkshire 持有的 Apple 市值应该在合理范围
        
        2025 年 Apple 市值约 3-4 万亿，Berkshire 持有约 2-3%
        所以 Berkshire 的 Apple 持仓应该在 $50B-$150B 范围
        
        如果得到 $50M-$150M → 单位错了（差了 1000 倍）
        如果得到 $50T-$150T → 单位也错了
        """
        result = parse_infotable(berkshire_xml)
        apple = next((h for h in result if "APPLE" in h["issuer"].upper()), None)
        if apple:  # Apple 可能已被减持
            assert apple["value"] > 10_000_000_000, \
                f"Apple value too low: ${apple['value']:,.0f} — 可能是千美元单位未转换"
            assert apple["value"] < 500_000_000_000, \
                f"Apple value too high: ${apple['value']:,.0f} — 可能是重复计算"
    
    def test_total_value_sanity(self, berkshire_xml):
        """
        Berkshire 总持仓应该在 $100B-$500B 范围（2025 年）
        """
        result = parse_infotable(berkshire_xml)
        total = sum(h["value"] for h in result)
        assert total > 50_000_000_000, \
            f"Total value too low: ${total:,.0f} — 可能单位有问题"
        assert total < 1_000_000_000_000, \
            f"Total value too high: ${total:,.0f} — 可能重复聚合"


# --- CUSIP 聚合测试 ---

class TestAggregation:
    
    def test_same_cusip_aggregated(self):
        """同一 CUSIP 的多个条目应该被合并"""
        holdings = [
            {"cusip": "037833100", "issuer": "APPLE INC", "value": 100, "shares": 10,
             "title": "COM", "share_type": "SH", "discretion": "SOLE",
             "sole_voting": 10, "shared_voting": 0, "no_voting": 0},
            {"cusip": "037833100", "issuer": "APPLE INC", "value": 200, "shares": 20,
             "title": "COM", "share_type": "SH", "discretion": "DFND",
             "sole_voting": 20, "shared_voting": 0, "no_voting": 0},
        ]
        result = aggregate_by_cusip(holdings)
        assert len(result) == 1
        assert result[0]["value"] == 300
        assert result[0]["shares"] == 30
    
    def test_different_cusip_not_aggregated(self):
        """不同 CUSIP 不应该被合并"""
        holdings = [
            {"cusip": "037833100", "issuer": "APPLE INC", "value": 100, "shares": 10,
             "title": "COM", "share_type": "SH", "discretion": "SOLE",
             "sole_voting": 10, "shared_voting": 0, "no_voting": 0},
            {"cusip": "594918104", "issuer": "MSFT", "value": 200, "shares": 20,
             "title": "COM", "share_type": "SH", "discretion": "SOLE",
             "sole_voting": 20, "shared_voting": 0, "no_voting": 0},
        ]
        result = aggregate_by_cusip(holdings)
        assert len(result) == 2


# --- 边界条件测试 ---

class TestEdgeCases:
    
    def test_empty_xml(self, empty_xml):
        """空的信息表应该返回空列表，不应崩溃"""
        result = parse_infotable(empty_xml)
        assert result == []
    
    def test_nonexistent_file(self):
        """不存在的文件应该返回空列表，不应崩溃"""
        result = parse_infotable("/nonexistent/path.xml")
        assert result == []
    
    def test_malformed_xml(self, tmp_path):
        """格式错误的 XML 应该优雅处理"""
        bad_xml = tmp_path / "bad.xml"
        bad_xml.write_text("<this is not valid xml><<>")
        result = parse_infotable(str(bad_xml))
        assert result == []
    
    def test_missing_optional_fields(self, tmp_path):
        """缺少可选字段（如 votingAuthority）不应崩溃"""
        xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
        <informationTable xmlns="http://www.sec.gov/edgar/document/thirteenf/informationtable">
          <infoTable>
            <nameOfIssuer>TEST INC</nameOfIssuer>
            <titleOfClass>COM</titleOfClass>
            <cusip>123456789</cusip>
            <value>1000000</value>
            <shrsOrPrnAmt>
              <sshPrnamt>10000</sshPrnamt>
              <sshPrnamtType>SH</sshPrnamtType>
            </shrsOrPrnAmt>
            <investmentDiscretion>SOLE</investmentDiscretion>
          </infoTable>
        </informationTable>'''
        test_xml = tmp_path / "test.xml"
        test_xml.write_text(xml_content)
        result = parse_infotable(str(test_xml))
        assert len(result) == 1
        assert result[0]["issuer"] == "TEST INC"
```

### 3.2 季度对比测试 (`tests/test_compare.py`)

```python
"""
test_compare.py — 季度对比逻辑测试
"""

from scripts.compare_quarters import compare_quarters


class TestCompareQuarters:
    
    def test_new_position(self):
        """新出现的持仓应该标记为 NEW"""
        current = [{"cusip": "AAA", "issuer": "NEW CO", "value": 100, "shares": 10, "weight": 100}]
        previous = []
        result = compare_quarters(current, previous)
        assert len(result["new"]) == 1
        assert result["new"][0]["issuer"] == "NEW CO"
    
    def test_sold_position(self):
        """消失的持仓应该标记为 SOLD"""
        current = []
        previous = [{"cusip": "AAA", "issuer": "OLD CO", "value": 100, "shares": 10, "weight": 100}]
        result = compare_quarters(current, previous)
        assert len(result["sold"]) == 1
        assert result["sold"][0]["issuer"] == "OLD CO"
    
    def test_increased_position(self):
        """数量增加应该标记为 INCREASED"""
        current = [{"cusip": "AAA", "issuer": "GROW CO", "value": 200, "shares": 20, "weight": 100}]
        previous = [{"cusip": "AAA", "issuer": "GROW CO", "value": 100, "shares": 10, "weight": 100}]
        result = compare_quarters(current, previous)
        assert len(result["increased"]) == 1
        assert result["increased"][0]["share_change"] == 10
        assert result["increased"][0]["share_change_pct"] == 100.0
    
    def test_decreased_position(self):
        """数量减少应该标记为 DECREASED"""
        current = [{"cusip": "AAA", "issuer": "SHRINK CO", "value": 50, "shares": 5, "weight": 100}]
        previous = [{"cusip": "AAA", "issuer": "SHRINK CO", "value": 100, "shares": 10, "weight": 100}]
        result = compare_quarters(current, previous)
        assert len(result["decreased"]) == 1
        assert result["decreased"][0]["share_change"] == -5
    
    def test_unchanged_position(self):
        """数量不变应该标记为 UNCHANGED"""
        current = [{"cusip": "AAA", "issuer": "STABLE CO", "value": 120, "shares": 10, "weight": 100}]
        previous = [{"cusip": "AAA", "issuer": "STABLE CO", "value": 100, "shares": 10, "weight": 100}]
        result = compare_quarters(current, previous)
        assert len(result["unchanged"]) == 1
    
    def test_summary_counts(self):
        """summary 统计应该正确"""
        current = [
            {"cusip": "AAA", "issuer": "NEW", "value": 100, "shares": 10, "weight": 33},
            {"cusip": "BBB", "issuer": "UP", "value": 200, "shares": 20, "weight": 67},
        ]
        previous = [
            {"cusip": "BBB", "issuer": "UP", "value": 100, "shares": 10, "weight": 50},
            {"cusip": "CCC", "issuer": "SOLD", "value": 100, "shares": 10, "weight": 50},
        ]
        result = compare_quarters(current, previous)
        assert result["summary"]["total_new"] == 1
        assert result["summary"]["total_increased"] == 1
        assert result["summary"]["total_sold"] == 1
    
    def test_both_empty(self):
        """两个季度都为空不应崩溃"""
        result = compare_quarters([], [])
        assert result["summary"]["total_new"] == 0
        assert result["summary"]["total_sold"] == 0
    
    def test_change_pct_calculation(self):
        """变动百分比计算正确"""
        current = [{"cusip": "AAA", "issuer": "X", "value": 300, "shares": 30, "weight": 100}]
        previous = [{"cusip": "AAA", "issuer": "X", "value": 200, "shares": 20, "weight": 100}]
        result = compare_quarters(current, previous)
        # 30 vs 20 = +50%
        assert result["increased"][0]["share_change_pct"] == 50.0
```

### 3.3 网络请求测试 (`tests/test_fetch.py`)

```python
"""
test_fetch.py — 数据抓取模块测试

使用 mock 模拟 SEC API 响应，避免在测试中真的调用 SEC。
"""

import pytest
from unittest.mock import patch, MagicMock
from scripts.fetch_13f import fetch_with_retry, get_latest_13f, find_infotable_url


class TestFetchWithRetry:
    
    @patch("scripts.fetch_13f.requests.get")
    def test_success_on_first_try(self, mock_get):
        """第一次就成功的请求"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        result = fetch_with_retry("https://example.com")
        assert result is not None
        assert mock_get.call_count == 1
    
    @patch("scripts.fetch_13f.requests.get")
    def test_retry_on_failure(self, mock_get):
        """失败后重试"""
        import requests
        mock_get.side_effect = [
            requests.exceptions.Timeout(),
            requests.exceptions.Timeout(),
            MagicMock(status_code=200),
        ]
        
        result = fetch_with_retry("https://example.com")
        assert result is not None
        assert mock_get.call_count == 3
    
    @patch("scripts.fetch_13f.requests.get")
    def test_all_retries_fail(self, mock_get):
        """所有重试都失败应该抛出异常"""
        import requests
        mock_get.side_effect = requests.exceptions.Timeout()
        
        with pytest.raises(requests.exceptions.Timeout):
            fetch_with_retry("https://example.com")
        assert mock_get.call_count == 3  # MAX_RETRIES
    
    @patch("scripts.fetch_13f.requests.get")
    def test_404_raises(self, mock_get):
        """404 应该抛出异常"""
        import requests
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError()
        mock_get.return_value = mock_response
        
        with pytest.raises(requests.exceptions.HTTPError):
            fetch_with_retry("https://example.com")


class TestGetLatest13F:
    
    @patch("scripts.fetch_13f.fetch_with_retry")
    def test_finds_13f_hr(self, mock_fetch):
        """能正确找到最新的 13F-HR"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "filings": {
                "recent": {
                    "form": ["10-Q", "13F-HR", "8-K"],
                    "filingDate": ["2025-08-01", "2025-08-14", "2025-07-01"],
                    "accessionNumber": ["xxx", "0000950123-25-008343", "yyy"],
                    "primaryDocument": ["a.htm", "primary_doc.xml", "b.htm"],
                    "reportDate": [None, "2025-06-30", None],
                }
            }
        }
        mock_fetch.return_value = mock_response
        
        result = get_latest_13f("0001067983")
        assert result is not None
        assert result["accession_number"] == "0000950123-25-008343"
    
    @patch("scripts.fetch_13f.fetch_with_retry")
    def test_no_13f_found(self, mock_fetch):
        """没有 13F filing 时返回 None"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "filings": {
                "recent": {
                    "form": ["10-Q", "8-K"],
                    "filingDate": ["2025-08-01", "2025-07-01"],
                    "accessionNumber": ["xxx", "yyy"],
                    "primaryDocument": ["a.htm", "b.htm"],
                    "reportDate": [None, None],
                }
            }
        }
        mock_fetch.return_value = mock_response
        
        result = get_latest_13f("0001265354")  # Duan Yongping — no 13F
        assert result is None
```

### 3.4 工具函数测试 (`tests/test_utils.py`)

```python
"""test_utils.py — 公共工具函数测试"""

from scripts.utils import (
    format_value,
    format_change_pct,
    determine_schema_version,
)


class TestFormatValue:
    
    def test_billions(self):
        assert format_value(150_000_000_000) == "$150.0B"
    
    def test_millions(self):
        assert format_value(250_000_000) == "$250.0M"
    
    def test_thousands(self):
        assert format_value(500_000) == "$500.0K"
    
    def test_zero(self):
        assert format_value(0) == "$0"


class TestFormatChangePct:
    
    def test_positive(self):
        assert format_change_pct(15.3) == "+15.3%"
    
    def test_negative(self):
        assert format_change_pct(-8.7) == "-8.7%"
    
    def test_zero(self):
        assert format_change_pct(0) == "0.0%"
```

---

## 4. 集成测试

### 4.1 数据管道集成测试

```python
"""
test_pipeline_integration.py — 完整数据管道测试

用真实的 SEC filing fixture 跑完整流程：
fetch (mock) → parse → compare → output JSON
"""

import pytest
import json
import os

from scripts.parse_13f import parse_infotable
from scripts.compare_quarters import compare_quarters


class TestFullPipeline:
    """从 XML 解析到季度对比的完整流程"""
    
    @pytest.fixture
    def parsed_q2(self):
        """Q2 已解析数据 fixture"""
        path = os.path.join("tests", "fixtures", "berkshire_2025q2_infotable.xml")
        if os.path.exists(path):
            return parse_infotable(path)
        pytest.skip("Fixture not available")
    
    @pytest.fixture
    def parsed_q1(self):
        """Q1 已解析数据 fixture"""
        path = os.path.join("tests", "fixtures", "berkshire_2025q1_infotable.xml")
        if os.path.exists(path):
            return parse_infotable(path)
        pytest.skip("Fixture not available")
    
    def test_full_compare(self, parsed_q2, parsed_q1):
        """Q2 vs Q1 对比应该成功"""
        result = compare_quarters(parsed_q2, parsed_q1)
        
        # 应该有 summary
        assert "summary" in result
        
        # 各类变动的数量之和应该等于当前+清仓的总数
        total_current = (
            result["summary"]["total_new"]
            + result["summary"]["total_increased"]
            + result["summary"]["total_decreased"]
            + result["summary"]["total_unchanged"]
        )
        assert total_current == len(parsed_q2)
    
    def test_output_json_valid(self, parsed_q2, parsed_q1):
        """输出的 JSON 应该可序列化"""
        result = compare_quarters(parsed_q2, parsed_q1)
        json_str = json.dumps(result)
        assert len(json_str) > 0
        # 能反序列化回来
        parsed_back = json.loads(json_str)
        assert parsed_back["summary"]["total_new"] == result["summary"]["total_new"]
```

### 4.2 配置文件验证测试

```python
"""
test_config.py — 配置文件完整性验证

确保 gurus.json 的每个条目都合法。
"""

import pytest
import json
import os


@pytest.fixture
def gurus_config():
    """加载 gurus.json"""
    config_path = os.path.join("config", "gurus.json")
    with open(config_path, "r") as f:
        return json.load(f)


class TestGurusConfig:
    
    def test_has_gurus(self, gurus_config):
        """配置中应该有投资人列表"""
        assert "gurus" in gurus_config
        assert len(gurus_config["gurus"]) >= 29
    
    def test_required_fields(self, gurus_config):
        """每个 guru 必须有必填字段"""
        required = ["id", "name", "cik", "style", "display_name", "filing_type"]
        for guru in gurus_config["gurus"]:
            for field in required:
                assert field in guru, \
                    f"Guru '{guru.get('id', '?')}' missing field '{field}'"
    
    def test_unique_ids(self, gurus_config):
        """guru id 必须唯一"""
        ids = [g["id"] for g in gurus_config["gurus"]]
        assert len(ids) == len(set(ids)), "Duplicate guru IDs found"
    
    def test_cik_format(self, gurus_config):
        """CIK 格式验证"""
        for guru in gurus_config["gurus"]:
            cik = guru["cik"]
            if cik != "TODO":
                assert cik.startswith("000"), \
                    f"CIK should be zero-padded: {guru['id']} has CIK {cik}"
                assert len(cik) == 10, \
                    f"CIK should be 10 digits: {guru['id']} has CIK {cik}"
    
    def test_valid_styles(self, gurus_config):
        """投资风格必须是预定义的值之一"""
        valid_styles = {"value", "macro", "quant", "growth", "activist"}
        for guru in gurus_config["gurus"]:
            assert guru["style"] in valid_styles, \
                f"Invalid style '{guru['style']}' for {guru['id']}"
    
    def test_valid_filing_types(self, gurus_config):
        """filing_type 必须合法"""
        valid_types = {"13F-HR", "SC13G", "SC13D"}
        for guru in gurus_config["gurus"]:
            assert guru["filing_type"] in valid_types, \
                f"Invalid filing_type '{guru['filing_type']}' for {guru['id']}"
```

---

## 5. 数据质量测试

**这是这个项目最独特也最重要的测试类别。**

### 5.1 解析后数据质量 (`tests/test_data_quality.py`)

```python
"""
test_data_quality.py — 数据质量验证

在每次数据更新后运行，确保解析出来的数据合理。
这些测试使用真实数据，不是 mock。
"""

import pytest
import json
import os
import glob


DATA_DIR = "data/parsed"


def get_all_parsed_files():
    """获取所有已解析的 JSON 文件"""
    return glob.glob(os.path.join(DATA_DIR, "**/*.json"), recursive=True)


class TestDataQuality:
    """对所有已解析数据的质量检查"""
    
    @pytest.fixture(params=get_all_parsed_files() if os.path.exists(DATA_DIR) else [])
    def parsed_data(self, request):
        with open(request.param, "r") as f:
            return json.load(f)
    
    def test_no_duplicate_cusip(self, parsed_data):
        """同一 guru 的同一期报告中不应有重复 CUSIP（聚合后）"""
        cusips = [h["cusip"] for h in parsed_data.get("holdings", [])]
        assert len(cusips) == len(set(cusips)), \
            f"Duplicate CUSIPs in {parsed_data.get('guru_id')}/{parsed_data.get('period_ending')}"
    
    def test_weights_reasonable(self, parsed_data):
        """单只股票权重不应超过 50%（除非是 Berkshire 的 Apple 这种极端情况）"""
        for h in parsed_data.get("holdings", []):
            if parsed_data.get("guru_id") == "berkshire_hathaway":
                assert h["weight"] <= 60, \
                    f"Unreasonable weight {h['weight']}% for {h['issuer']}"
            else:
                assert h["weight"] <= 50, \
                    f"Unreasonable weight {h['weight']}% for {h['issuer']}"
    
    def test_value_not_in_wrong_unit(self, parsed_data):
        """
        检测 value 是否使用了错误的单位
        
        如果总市值 < $10M，很可能是千美元单位没有转换
        （除非是非常小的基金）
        """
        total = sum(h["value"] for h in parsed_data.get("holdings", []))
        guru_id = parsed_data.get("guru_id", "")
        
        # 跳过已知的小基金
        small_funds = {"duan_yongping"}  # 段永平没有 13F
        if guru_id in small_funds:
            return
        
        assert total > 10_000_000, \
            f"Total value ${total:,.0f} suspiciously low for {guru_id} — wrong unit?"
    
    def test_no_empty_issuer_names(self, parsed_data):
        """发行人名称不应为空"""
        for h in parsed_data.get("holdings", []):
            assert h["issuer"].strip() != "", "Empty issuer name found"
    
    def test_cusip_not_all_zeros(self, parsed_data):
        """CUSIP 不应全为 0"""
        for h in parsed_data.get("holdings", []):
            assert h["cusip"] != "000000000", \
                f"All-zero CUSIP found for {h['issuer']}"


class TestCrossGuruConsistency:
    """跨 guru 的数据一致性检查"""
    
    def test_same_cusip_same_issuer(self):
        """
        同一个 CUSIP 在不同 guru 的报告中应该对应同一个发行人
        
        例如：Apple 的 CUSIP 037833100 在所有 guru 的 13F 中都应该叫 "APPLE INC"
        （允许大小写和缩写差异）
        """
        cusip_issuers = {}
        
        for path in get_all_parsed_files():
            with open(path, "r") as f:
                data = json.load(f)
            for h in data.get("holdings", []):
                cusip = h["cusip"]
                issuer = h["issuer"].upper().strip()
                if cusip in cusip_issuers:
                    # 同一 CUSIP 允许小的名称差异，但不能完全不同
                    existing = cusip_issuers[cusip]
                    # 只检查前 5 个字符是否一致（处理 "APPLE INC" vs "APPLE INC." 的情况）
                    if existing[:5] != issuer[:5]:
                        pytest.fail(
                            f"CUSIP {cusip}: '{existing}' vs '{issuer}' — 可能是数据错误"
                        )
                else:
                    cusip_issuers[cusip] = issuer
```

### 5.2 历史一致性检查

```python
class TestHistoricalConsistency:
    """
    检查同一 guru 的历史数据是否一致
    
    例如：如果 Q1 Berkshire 有 300M 股 Apple，Q2 有 280M 股，
    那 Q2 应该标记为「减仓」而不是「新建仓」。
    """
    
    def test_no_phantom_new_positions(self):
        """
        如果 Q1 和 Q2 都有某只股票，
        对比结果中它不应该出现在 'new' 列表中
        """
        compared_files = glob.glob("data/compared/**/*.json", recursive=True)
        for path in compared_files:
            with open(path, "r") as f:
                data = json.load(f)
            
            guru_id = data.get("guru_id")
            current_period = data.get("current_period")
            
            # 加载两个季度的原始数据验证
            # ... (省略加载逻辑)
            
            for change in data.get("changes", {}).get("new", []):
                # 验证这只股票确实在上季度不存在
                pass  # 实现时填充
```

---

## 6. 端到端测试 (E2E)

### 6.1 完整管道 E2E

```python
"""
test_e2e.py — 端到端测试

模拟完整的 daily scan 流程：
1. 用 fixture 替代真实 SEC API 调用
2. 运行完整管道
3. 验证产出文件

不依赖网络，可在 CI 中运行。
"""

import pytest
import subprocess
import os
import json


class TestE2EPipeline:
    
    def test_full_pipeline_with_fixtures(self, tmp_path):
        """用 fixture 数据跑完整管道"""
        # 1. 准备 fixture 环境
        # 2. 运行 parse → compare → build
        # 3. 验证输出
        
        # 跳过 fetch（mock），直接从 fixture 开始
        env = os.environ.copy()
        env["DATA_DIR"] = str(tmp_path / "data")
        env["SITE_DIR"] = str(tmp_path / "site")
        
        # 复制 fixture 到 tmp data dir
        # ... setup code ...
        
        # 运行解析
        result = subprocess.run(
            ["python", "scripts/parse_13f.py"],
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Parse failed: {result.stderr}"
        
        # 运行对比
        result = subprocess.run(
            ["python", "scripts/compare_quarters.py"],
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Compare failed: {result.stderr}"
        
        # 运行构建
        result = subprocess.run(
            ["python", "scripts/build_site.py"],
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Build failed: {result.stderr}"
        
        # 验证产出
        site_dir = tmp_path / "site"
        assert (site_dir / "index.html").exists()
        assert (site_dir / "data" / "gurus.json").exists()


class TestSiteOutput:
    """验证生成的静态站点"""
    
    def test_index_html_exists(self):
        assert os.path.exists("site/index.html")
    
    def test_guru_pages_exist(self):
        """每个 guru 都应该有对应的 HTML 页面"""
        with open("config/gurus.json") as f:
            config = json.load(f)
        
        for guru in config["gurus"]:
            if guru.get("active", True):
                page = f"site/guru/{guru['id']}.html"
                assert os.path.exists(page), f"Missing page: {page}"
    
    def test_data_json_valid(self):
        """前端 JSON 文件应该是合法 JSON"""
        for json_file in ["site/data/gurus.json", "site/data/latest.json"]:
            if os.path.exists(json_file):
                with open(json_file) as f:
                    data = json.load(f)  # 如果不是合法 JSON 会抛异常
                assert isinstance(data, (dict, list))
```

---

## 7. 测试运行方式

### 7.1 本地运行

```bash
# 安装测试依赖
pip install pytest pytest-cov

# 运行全部测试
pytest tests/ -v

# 只运行单元测试（快速）
pytest tests/test_parse.py tests/test_compare.py tests/test_utils.py -v

# 只运行数据质量测试（需要有真实数据）
pytest tests/test_data_quality.py -v

# 带覆盖率报告
pytest tests/ --cov=scripts --cov-report=html
```

### 7.2 CI 中运行（GitHub Actions）

```yaml
# 在 daily-scan.yml 中添加测试步骤
- name: Run tests
  run: pytest tests/ -v --tb=short
  # 测试失败时阻止部署
```

### 7.3 测试 Fixtures 准备

```bash
# 下载真实的 SEC filing 作为测试 fixture
mkdir -p tests/fixtures

# Berkshire Q2 2025
curl -H "User-Agent: GuruTracker research@example.com" \
  "https://www.sec.gov/Archives/edgar/data/1067983/000095012325008343/43977.xml" \
  -o tests/fixtures/berkshire_2025q2_infotable.xml

# 创建空的信息表 fixture
cat > tests/fixtures/empty_infotable.xml << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<informationTable xmlns="http://www.sec.gov/edgar/document/thirteenf/informationtable">
</informationTable>
EOF
```

---

## 8. 回归策略

### 8.1 什么时候运行测试

| 触发事件 | 运行范围 | 说明 |
|---------|---------|------|
| 提交代码 (push) | 全部单元测试 + 集成测试 | 快速反馈 |
| 每日扫描 (cron) | 数据质量测试 | 确保新数据合格 |
| 手动触发 | 全部测试 | 部署前验证 |
| 修改解析逻辑 | XML 解析测试 + 数据质量测试 | 最容易出问题的地方 |

### 8.2 回归保护的关键场景

| 场景 | 可能出错的原因 | 测试覆盖 |
|------|--------------|---------|
| Value 单位搞错 | SEC schema 版本变化 | `TestValueUnits` |
| CUSIP 聚合错误 | 同一机构多个 manager 报告 | `TestAggregation` |
| 季度对比逻辑错误 | 新建仓/清仓判断失误 | `TestCompareQuarters` |
| 网络超时 | SEC API 不稳定 | `TestFetchWithRetry` |
| 配置文件格式错误 | 手动修改 gurus.json 引入 typo | `TestGurusConfig` |
| 空 filing | 某些机构的 13F 没有持仓 | `TestEdgeCases` |

### 8.3 监控告警

当以下情况发生时，通过 Telegram 发出告警（而不是正常推送）：

```python
ALERT_CONDITIONS = {
    "guru_missing": "某 guru 连续 2 个季度没有新的 13F（可能 CIK 变了）",
    "parse_failure": "XML 解析失败（可能 SEC schema 又变了）",
    "zero_holdings": "解析后持仓数为 0（不正常）",
    "value_anomaly": "总市值较上季度变化超过 80%（可能单位问题）",
    "api_down": "SEC API 连续 3 天不可达",
}
```

---

## 9. 测试覆盖率目标

| 模块 | 目标覆盖率 | 说明 |
|------|-----------|------|
| `parse_13f.py` | **≥ 95%** | 核心模块，必须高覆盖 |
| `compare_quarters.py` | **≥ 95%** | 核心模块，必须高覆盖 |
| `fetch_13f.py` | ≥ 80% | 网络逻辑用 mock 测试 |
| `build_site.py` | ≥ 60% | 模板渲染，手动验证也 OK |
| `notify_telegram.py` | ≥ 60% | 推送逻辑相对简单 |
| `utils.py` | ≥ 90% | 纯工具函数，容易测 |

**整体目标：≥ 85% 行覆盖率**

---

## 10. 测试失败时的调试流程

> 来自 `systematic-debugging` skill，遇到测试失败时**禁止盲目猜测修复**。

### 10.1 四阶段诊断（强制）

| 阶段 | 动作 | 产出 |
|------|------|------|
| **Phase 1: 根因调查** | 读完整错误信息 → 复现 → 检查最近变更 → 追踪数据流 | 理解 WHAT 和 WHY |
| **Phase 2: 模式分析** | 找到类似的通过测试 → 对比差异 | 定位差异点 |
| **Phase 3: 假设与测试** | 提出单一假设 → 最小化修改验证 | 确认或推翻假设 |
| **Phase 4: 修复实施** | 写回归测试 → 修复 → 验证 red-green cycle | bug 关闭 |

### 10.2 三次失败铁律

连续 3 次修复尝试失败 → **立刻停止**，不要尝试第 4 次。

此时说明问题很可能是架构层面的，需要：
1. 记录已尝试的修复和结果
2. 与 DQ 讨论架构问题
3. DQ 确认方向后再继续

### 10.3 常见回归风险与诊断方向

| 症状 | 最可能的根因 | 诊断步骤 |
|------|------------|---------|
| 市值差 1000 倍 | Schema 版本单位变化 | 检查 XML namespace，打印 raw value |
| CUSIP 重复 | 聚合逻辑失效 | 打印聚合前后的 CUSIP 列表对比 |
| 新建仓误判 | 上季度数据缺失或路径错误 | 确认两个季度的文件都存在 |
| Telegram 推送失败 | Token 环境变量未设置 | `echo $TELEGRAM_BOT_TOKEN` |
| GitHub Actions 超时 | SEC API 限流 | 检查 rate limit delay 是否生效 |

---

## 11. 验收测试：需求-测试映射

> 确保每个用户故事都有对应的测试覆盖

| 用户故事 | 对应测试 | 验收标准 |
|---------|---------|---------|
| US-01 看巴菲特最新持仓 | `test_parse.py::TestBasicParsing` + `test_e2e.py::TestSiteOutput::test_guru_pages_exist` | 解析正确 + 页面可访问 |
| US-02 对比季度变化 | `test_compare.py::TestCompareQuarters` | 5 种变动类型全部正确 |
| US-03 多大师共识 | `test_consensus.py`（待补充） | 共识排行数据正确 |
| US-04 Telegram 通知 | `test_fetch.py` (mock) + 手动验证 | 新 filing 触发推送 |
| US-05 按风格筛选 | `test_config.py::TestGurusConfig::test_valid_styles` | 风格标签有效 |
| US-06 大师背景简介 | `test_config.py::TestGurusConfig::test_required_fields` | bio 字段非空 |
| US-08 响应式设计 | 手动 Lighthouse 检查 | 移动端可用性 > 90 |
| US-09 ARK 每日数据 | `test_fetch_ark.py`（待补充） | CSV 解析成功 |

**每个 Phase 完成时，必须确认对应用户故事的测试全部通过。**

---

## 12. 性能测试

### 12.1 数据管道性能

```python
"""test_performance.py — 性能基准测试"""

import pytest
import time


class TestPerformance:
    
    def test_parse_large_filing(self, citadel_xml):
        """
        大机构（如 Citadel）可能有数千条持仓。
        解析时间不应超过 5 秒。
        """
        start = time.time()
        result = parse_infotable(citadel_xml)
        elapsed = time.time() - start
        assert elapsed < 5.0, f"Parsing took {elapsed:.1f}s, too slow"
        assert len(result) > 100  # Citadel 通常有数百条持仓
    
    def test_compare_large_holdings(self):
        """
        两个大型持仓列表的对比不应超过 1 秒。
        """
        current = [{"cusip": f"C{i:08d}", "issuer": f"CO_{i}", 
                     "value": i*1000, "shares": i, "weight": 0.1} 
                    for i in range(5000)]
        previous = [{"cusip": f"C{i:08d}", "issuer": f"CO_{i}", 
                      "value": i*900, "shares": i-1 if i > 0 else 0, "weight": 0.1}
                     for i in range(4500)]
        
        start = time.time()
        result = compare_quarters(current, previous)
        elapsed = time.time() - start
        assert elapsed < 1.0, f"Comparison took {elapsed:.1f}s, too slow"
```

### 12.2 站点构建性能

| 指标 | 目标 | 验证方式 |
|------|------|---------|
| 全量构建时间 | < 60 秒 | `time python scripts/build_site.py` |
| 单页 HTML 大小 | < 200 KB | `ls -la site/guru/*.html` |
| 首页加载时间 | < 3 秒 | Lighthouse Performance Score > 90 |

---

## 13. 安全测试

### 13.1 密钥泄漏检查

```python
"""test_security.py — 安全测试"""

import pytest
import os
import glob
import re


class TestNoHardcodedSecrets:
    """确保代码中没有硬编码的密钥/token"""
    
    SUSPICIOUS_PATTERNS = [
        r'["\']sk-[a-zA-Z0-9]{20,}["\']',        # OpenAI-style API key
        r'["\'][0-9]+:[A-Za-z0-9_-]{35}["\']',    # Telegram bot token
        r'["\']ghp_[a-zA-Z0-9]{36}["\']',         # GitHub personal access token
        r'password\s*=\s*["\'][^"\']+["\']',       # Hardcoded password
        r'secret\s*=\s*["\'][^"\']+["\']',         # Hardcoded secret
    ]
    
    def _get_all_python_files(self):
        return glob.glob("scripts/**/*.py", recursive=True)
    
    def test_no_secrets_in_code(self):
        """扫描所有 Python 文件，检测可疑的硬编码密钥"""
        for filepath in self._get_all_python_files():
            with open(filepath, "r") as f:
                content = f.read()
            for pattern in self.SUSPICIOUS_PATTERNS:
                matches = re.findall(pattern, content)
                assert not matches, \
                    f"🚨 Possible hardcoded secret in {filepath}: {matches[0][:20]}..."
    
    def test_env_example_exists(self):
        """确保 .env.example 存在"""
        assert os.path.exists(".env.example"), \
            ".env.example must exist — list all required env vars"
    
    def test_gitignore_covers_secrets(self):
        """确保 .gitignore 排除敏感文件"""
        with open(".gitignore", "r") as f:
            gitignore = f.read()
        assert ".env" in gitignore, ".env must be in .gitignore"
```

### 13.2 日志安全检查

```python
class TestLogSecurity:
    """确保日志不输出敏感信息"""
    
    def test_telegram_token_not_in_logs(self, capsys):
        """Telegram token 不应出现在日志输出中"""
        # 运行通知脚本（mock 模式）
        # 检查 captured output 中没有 token 明文
        pass  # 实现时填充
```

---

## 14. 测试分类与运行策略

### 14.1 速度分类

| 分类 | 包含 | 运行时间 | 何时运行 |
|------|------|---------|---------|
| 🟢 **快速（Fast）** | 单元测试 + 工具函数测试 | < 10 秒 | 每次提交 |
| 🟡 **中速（Medium）** | 集成测试 + 配置验证 | < 30 秒 | 每次提交 |
| 🔴 **慢速（Slow）** | E2E + 性能测试 + 数据质量 | < 5 分钟 | 每日扫描 / 手动触发 |

### 14.2 pytest 标记

```python
# conftest.py
import pytest

def pytest_configure(config):
    config.addinivalue_line("markers", "fast: 快速单元测试")
    config.addinivalue_line("markers", "slow: 慢速集成/E2E 测试")
    config.addinivalue_line("markers", "security: 安全测试")
    config.addinivalue_line("markers", "data_quality: 数据质量测试（需要真实数据）")
```

```bash
# 只跑快速测试（开发时常用）
pytest -m fast -v

# 只跑安全测试
pytest -m security -v

# 全部测试（CI / 部署前）
pytest tests/ -v --cov=scripts --cov-report=html
```

---

## 15. 已知限制与注意事项

1. **13F 有 45 天延迟** — 测试数据的时效性有限，不要用太旧的 fixture
2. **SEC schema 可能变化** — 需要定期更新 fixture，schema 变化是最大的回归风险
3. **大文件测试** — Citadel 等大机构的 13F 可能有数千条持仓，需要测试大文件性能
4. **ARK 数据格式** — ARK 偶尔会改 CSV 列名，需要有专门的格式检查测试
5. **Telegram 推送** — 真实 Telegram 测试需要 bot token，CI 中使用 mock
