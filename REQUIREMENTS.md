# 投资大师持仓追踪 — 产品需求文档（PRD）

> **项目代号：** Guru Tracker  
> **最后更新：** 2025-07-20  
> **文档版本：** v1.1  
> **作者：** Pepper for DQ

---

## 0. 文档层级与关系

```
GEMINI.md（全局规范，宪法）
  └── CLAUDE.md（项目规则，地方法规）
        ├── → REQUIREMENTS.md（本文档 — 做什么、为什么做）
        ├── → TDD.md（怎么建、技术架构）
        ├── → TESTING.md（怎么验证、测试分层）
        └── → DESIGN.md（怎么看，如需要）
```

- **全局规范遵从：** 本项目遵守 `GEMINI.md` 全局宪法，项目级 `CLAUDE.md` 为地方法规
- **Source of Truth：** REQUIREMENTS.md 和 TDD.md 是权威文档，代码与文档冲突时以文档为准
- **铁律：** 本文档（①）+ TDD.md（②）+ TESTING.md（③）必须在写第一行代码之前完成

---

## 1. 产品愿景

**一句话描述：** 一站式追踪全球顶级投资人/机构的季度持仓变化，让个人投资者和巴菲特、达利欧、Druckenmiller 看同一份数据。

**为什么做这个？**

SEC 规定，管理超过 1 亿美元的机构投资经理必须每季度提交 13F 报告，披露其持有的美股仓位。这是公开数据，但散户很少主动去读——因为原始 XML 又臭又长，对比上季度更是痛苦。

Guru Tracker 把这些大师的持仓变化做成一个可读、可搜索、自动更新的静态网站，每日扫描 SEC 是否有新披露，有则自动构建并通过 Telegram 推送通知。

**核心价值：**
- 🔍 **透明度** — 不用翻 SEC 网站，所有大师持仓一目了然
- 📊 **对比分析** — 季度变化自动高亮：新建仓、加仓、减仓、清仓
- 🔔 **及时性** — 每日扫描 + Telegram 推送，不错过任何重大变动
- 🧠 **集体智慧** — 看到一只股票被多少大师同时持有

---

## 2. 用户故事

| 编号 | 角色 | 故事 | 优先级 |
|------|------|------|--------|
| US-01 | 投资者 | 我想看巴菲特最新一季的持仓，知道他买了什么新票 | P0 |
| US-02 | 投资者 | 我想对比达利欧上季度和本季度的持仓变化 | P0 |
| US-03 | 投资者 | 我想知道哪些大师同时持有 Apple 或 TSMC | P0 |
| US-04 | 投资者 | 当某位大师提交新的 13F 时，我想收到 Telegram 通知 | P0 |
| US-05 | 投资者 | 我想按「投资风格」筛选大师（价值派/宏观派/科技派） | P1 |
| US-06 | 投资者 | 我想了解每个大师的背景简介（风格、AUM、成名战绩） | P1 |
| US-07 | 投资者 | 我想看某只股票在大师群体中的持仓集中度趋势 | P2 |
| US-08 | 投资者 | 网站在手机上也能正常使用 | P1 |
| US-09 | 投资者 | ARK Invest 的数据能每日更新（不只是季度） | P1 |

---

## 3. 追踪名单（29 个独立实体）

### 3.1 价值投资派

| # | 机构/实体名 | SEC CIK | 代表人物 | 简介 |
|---|-----------|---------|---------|------|
| 1 | **Berkshire Hathaway Inc** | 0001067983 | 沃伦·巴菲特 | 史上最伟大的价值投资者。从 1965 年执掌伯克希尔至今，年化回报约 20%，将一家纺织厂变成市值超 1 万亿美元的投资帝国。风格：买入优质企业并长期持有，核心持仓集中在苹果、可口可乐、美国运通等。 |
| 2 | **Himalaya Capital Management** | 需确认 | 李录 | 巴菲特和芒格的忠实门徒，查理·芒格曾将个人资产交给他管理。华人价值投资的代表人物，哥伦比亚大学 MBA，管理约 200 亿美元。以极度集中持仓著称，长期重仓比亚迪，回报惊人。 |
| 3 | **Daily Journal Corp** | 0000783412 | 查理·芒格（遗产持仓） | 芒格生前担任 Daily Journal 董事长，其投资组合极度集中：几乎全部押在美国银行、富国银行和比亚迪。芒格 2023 年 11 月去世，但这些仓位仍在 13F 中可追踪。 |
| 4 | **Fairholme Capital Management** | 0001056831 | Bruce Berkowitz | 2009 年被 Morningstar 评为「十年最佳基金经理」。深度价值风格，愿意在市场恐慌时重仓逆向押注。AUM 约 10 亿美元（巅峰时超 200 亿）。以重仓 Fannie Mae/Freddie Mac 著称。 |
| 5 | **Baupost Group** | 0001061768 | Seth Klarman | 《安全边际》(Margin of Safety) 的作者，该书已绝版，二手价超 1000 美元。管理约 250 亿美元，以极端耐心和高现金比例著称，经常持有 30-50% 现金等待机会。 |
| 6 | **Greenlight Capital** | 0001079114 | David Einhorn | 著名的做空大师，曾在 2008 年金融危机前做空雷曼兄弟而成名。同时也是优秀的多头价值投资者。管理约 30 亿美元，风格犀利，善于发现市场定价错误。 |
| 7 | **Pabrai Investment Funds** | 0001173334 | Mohnish Pabrai | 印裔美国人，巴菲特的忠实追随者，曾在慈善拍卖中花 65 万美元与巴菲特共进午餐。管理约 5-10 亿美元，以极度集中投资（组合不超过 10 只股票）和"0 风险"策略著称。 |

### 3.2 全球宏观 / 对冲基金

| # | 机构/实体名 | SEC CIK | 代表人物 | 简介 |
|---|-----------|---------|---------|------|
| 8 | **Soros Fund Management** | 0001029160 | 乔治·索罗斯 | 传奇投机家，1992 年做空英镑赚 10 亿美元，被称为「打败英格兰银行的人」。量子基金从 1969 年到 2000 年年化回报超 30%。现已转为家族办公室，但仍提交 13F。 |
| 9 | **Bridgewater Associates** | 0001350694 | 瑞·达利欧 | 全球最大对冲基金创始人，管理约 1250 亿美元。以「全天候」(All Weather) 策略著称，通过风险平价配置在任何宏观环境下赚钱。《原则》一书作者。 |
| 10 | **Pershing Square Capital** | 0001336528 | Bill Ackman | 激进主义投资的代表，善于买入大量股票后推动公司变革。管理约 180 亿美元。成名战役：通用增长地产 (GGP) 翻 60 倍；惨痛教训：做空康宝莱亏损 10 亿美元。 |
| 11 | **Citadel Advisors** | 0001423053 | Ken Griffin | 全球最赚钱的对冲基金之一，管理约 650 亿美元。多策略巨头，涵盖量化、固收、宏观、股票等。Griffin 白手起家，从哈佛宿舍开始交易。 |
| 12 | **Point72 Asset Management** | 0001603466 | Steve Cohen | 前 SAC Capital 创始人，华尔街交易天才。管理约 350 亿美元，以极强的短线交易直觉著称。也是纽约大都会棒球队老板。 |
| 13 | **Renaissance Technologies** | 0001037389 | Jim Simons（已故） | 数学家出身，创建了史上最赚钱的量化基金 Medallion Fund（年化 66%，扣费后 39%）。Simons 于 2024 年 5 月去世，但 RenTech 仍在运营。其 13F 反映的是外部基金持仓。 |
| 14 | **D.E. Shaw & Co.** | 0001009207 | David Shaw | 计算机科学家出身的量化投资先驱，Jeff Bezos 的前老板。管理约 600 亿美元，融合量化和基本面分析。极为低调神秘。 |
| 15 | **Two Sigma Investments** | 0001179392 | David Siegel & John Overdeck | 纯量化巨头，由两位计算机科学家创立，管理约 600 亿美元。利用机器学习、分布式计算处理海量数据找 alpha。 |
| 16 | **Millennium Management** | 0001273087 | Israel Englander | 管理超 600 亿美元的多策略平台基金，旗下有数百个独立交易团队。以严格的风控和低波动率著称，几乎每年都盈利。 |
| 17 | **Third Point** | 0001040273 | Dan Loeb | 激进主义对冲基金，善于写措辞激烈的「致管理层公开信」推动变革。管理约 150 亿美元。著名战役：Yahoo 换帅、Sony 分拆。 |

### 3.3 科技 / 成长派

| # | 机构/实体名 | SEC CIK | 代表人物 | 简介 |
|---|-----------|---------|---------|------|
| 18 | **ARK Investment Management** | 0001603466 | Cathie Wood | 「颠覆性创新」教母，重仓 AI、基因编辑、区块链、机器人等主题。2020 年 ARKK 回报 152% 一战成名。**特殊数据源：ARK 每日公开持仓变动**，比 13F 更实时。管理约 150 亿美元。 |
| 19 | **Tiger Global Management** | 0001167483 | Chase Coleman | Tiger Management（Julian Robertson 的）的「小虎」之一。曾是全球最大科技对冲基金，巅峰管理约 800 亿美元。2022 年亏损惨重后大幅缩水，但仍是重要的科技投资风向标。 |
| 20 | **Coatue Management** | 0001535392 | Philippe Laffont | 另一只「小虎」，专注科技和 TMT 投资。管理约 200 亿美元，横跨公开市场和私募。以研究深度和技术理解力著称。 |
| 21 | **Dragoneer Investment Group** | 0001684577 | Marc Stad | 专注成长期科技公司投资，管理约 120 亿美元。同时活跃在私募市场（Uber、Slack 等的早期投资者）。交叉基金模式（公开+私募）。 |
| 22 | **Altimeter Capital Management** | 0001730815 | Brad Gerstner | 科技成长型投资者，管理约 100 亿美元。善于在科技领域寻找结构性增长机会，曾在 SPAC 热潮中高调活跃。 |
| 23 | **D1 Capital Partners** | 0001799900 | Dan Sundheim | 前 Viking Global 投资组合经理，2018 年创立 D1。管理约 200 亿美元，混合公开市场和私募投资，专注科技/消费/医疗。 |

### 3.4 传奇 / 长青机构

| # | 机构/实体名 | SEC CIK | 代表人物 | 简介 |
|---|-----------|---------|---------|------|
| 24 | **Sequoia Fund** | 0000090168 | — | 由巴菲特早年推荐的基金经理 Bill Ruane 于 1970 年创立。长期集中持股风格，曾重仓 Valeant（惨痛教训）。管理约 50 亿美元，是美国历史最悠久的价值基金之一。 |
| 25 | **Appaloosa Management** | 0001656456 | David Tepper | 「最赚钱的对冲基金经理」之一，善于在危机中抄底不良资产。2009 年金融危机后抄底银行股大赚 70 亿美元。管理约 130 亿美元，也是 Carolina Panthers 橄榄球队老板。 |
| 26 | **Elliott Investment Management** | 0001048445 | Paul Singer | 全球最知名的激进投资机构，管理超 650 亿美元。风格极为强硬，曾与阿根廷政府打了 15 年官司追讨债务并获胜。擅长逼迫公司回购、分拆、换帅。 |
| 27 | **Icahn Enterprises** | 0000049588 | Carl Icahn | 企业掠夺者（corporate raider）鼻祖。1985 年强行收购 TWA 航空一战成名。风格：大量买入，然后逼董事会做出对股东有利的变革。管理约 150 亿美元。 |
| 28 | **Duquesne Family Office** | 0001536411 | Stanley Druckenmiller | 曾为索罗斯管理量子基金，亲手执行了 1992 年做空英镑的交易。自己的 Duquesne Capital 年化 30%，零亏损年。2010 年关闭基金转为家族办公室，但仍提交 13F。市场公认的当代最佳宏观投资者。 |

### 3.5 华人投资人

| # | 机构/实体名 | SEC CIK | 代表人物 | 简介 |
|---|-----------|---------|---------|------|
| 29 | **DUAN YONG PING**（个人名义） | 0001265354 | 段永平 | 步步高/OPPO/vivo 背后的创始人，2001 年以 62 万美元「抄底」网易股票赚到上亿美元的传奇投资。巴菲特午餐的第一位中国竞拍者。 |

> **⚠️ 重要说明：段永平的数据源差异**
> 
> 段永平在 SEC 的注册名为 **DUAN YONG PING**（CIK: 0001265354），但他 **不提交 13F 报告**——因为他是个人投资者，不是管理超过 1 亿美元的「机构投资经理」（13F 的申报门槛）。
> 
> 他的 SEC 披露是通过 **SC 13G/13D**（个人大股东申报），历史记录包括：网易 (NTES)、九城数码、Frontier Airlines 等。最后一次 SEC 申报是 2010 年。
> 
> **追踪方案：** 将段永平列为「特殊追踪」，数据来源为 SC 13G/13D 而非 13F。在前端标注数据来源差异。同时考虑从其社交媒体（雪球等）人工维护已知持仓。

---

## 4. 功能需求

### F-01: 投资人档案卡片

**描述：** 每个投资人/机构有独立的档案页面，包含基本信息和持仓数据。

**档案信息：**
- 机构名称 + 代表人物
- 投资风格标签（价值/宏观/量化/科技/激进主义）
- 管理资产规模 (AUM)
- 成名战绩（1-2 句话）
- SEC CIK 链接
- 最近一次 13F 提交日期

**验收标准：**
- 所有 29 个实体都有完整档案
- 档案页可直接跳转到持仓详情

### F-02: 最新持仓结构

**描述：** 展示每个机构最近一次 13F 中披露的全部持仓。

**表格字段：**
| 字段 | 说明 |
|------|------|
| 股票名称 | nameOfIssuer |
| 证券类型 | titleOfClass |
| CUSIP | 唯一标识 |
| 持仓市值 | value（美元） |
| 持股数量 | sshPrnamt |
| 持仓占比 | 该仓位市值 / 总持仓市值 |

**交互：**
- 表格支持按市值、占比、股票名排序
- 支持搜索股票名或 CUSIP

### F-03: 季度对比分析

**描述：** 自动对比本季度与上季度的持仓变化。

**变动分类：**
| 类型 | 定义 | 视觉标识 |
|------|------|----------|
| 🆕 新建仓 | 上季度没有、本季度新出现 | 绿色高亮 |
| ⬆️ 加仓 | 持股数量增加 | 浅绿 + 箭头 |
| ⬇️ 减仓 | 持股数量减少 | 浅红 + 箭头 |
| ❌ 清仓 | 上季度有、本季度消失 | 红色高亮 |
| ➡️ 不变 | 持股数量和上季度完全一样 | 灰色 |

**计算逻辑：** 以 CUSIP 作为唯一标识对比两个季度的信息表。

### F-04: 趋势分析（大师共识）

**描述：** 分析某只股票在所有追踪的大师中的「共识度」。

**功能：**
- 查看某只股票被多少个大师同时持有
- 大师持仓集中度排行（哪只股票最受追捧）
- 历史趋势：共识度的季度变化

### F-05: 搜索与筛选

**描述：** 提供多维度的搜索和筛选能力。

**筛选维度：**
- 按投资人名称
- 按投资风格（价值/宏观/量化/科技/激进主义）
- 按股票名称或 CUSIP
- 按变动类型（新建仓/加仓/减仓/清仓）
- 按持仓市值范围

### F-06: Telegram 推送通知

**描述：** 当检测到新的 13F 报告发布时，通过 Telegram 推送摘要。

**推送内容：**
```
🔔 巴菲特（Berkshire Hathaway）Q3 2025 持仓更新！

📅 报告期：2025-09-30
📊 总持仓：$3,120 亿

🆕 新建仓：
  • XYZ Corp — $5.2B（1.7%）

⬆️ 加仓：
  • Apple — +12.3%（$892M → $1.0B）
  
⬇️ 减仓：
  • Bank of America — -15.2%

❌ 清仓：
  • (无)

🔗 详情：https://xxx.github.io/guru/berkshire
```

**推送规则：**
- 每个大师的新 13F 独立推送
- 仅推送有实质变动的报告（非全部不变）
- ARK 的每日交易仅推送超过阈值的变动

### F-07: ARK Invest 每日交易追踪

**描述：** ARK 每日公开其 ETF 交易明细（买入/卖出），这比 13F 实时得多。

**数据源：** `https://ark-funds.com/wp-content/uploads/funds-etf-csv/ARK_TRADE.csv`

**功能：**
- 每日拉取 ARK 交易 CSV
- 展示最近 30 天的交易记录
- 高亮大额交易

---

## 5. 数据需求

### 5.1 主数据源：SEC EDGAR 13F API

**API 体系：**

| API | 用途 | URL 格式 | 频率限制 |
|-----|------|---------|---------|
| Submissions API | 获取某 CIK 的全部 filing 列表 | `https://data.sec.gov/submissions/CIK{padded_cik}.json` | 10 req/sec |
| Filing Index | 获取某次 filing 的文件列表 | `https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/` | 10 req/sec |
| Information Table | 获取 13F 持仓明细 XML | `https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{table_file}.xml` | 10 req/sec |
| EFTS Search | 全文搜索 SEC 文件 | `https://efts.sec.gov/LATEST/search-index?q=...` | 10 req/sec |

**13F Information Table XML 格式：**

```xml
<informationTable xmlns="http://www.sec.gov/edgar/document/thirteenf/informationtable">
  <infoTable>
    <nameOfIssuer>ALLY FINL INC</nameOfIssuer>
    <titleOfClass>COM</titleOfClass>
    <cusip>02005N100</cusip>
    <value>495431341</value>          <!-- 市值，单位：美元 -->
    <shrsOrPrnAmt>
      <sshPrnamt>12719675</sshPrnamt> <!-- 持股/合约数量 -->
      <sshPrnamtType>SH</sshPrnamtType> <!-- SH=股票, PRN=本金 -->
    </shrsOrPrnAmt>
    <investmentDiscretion>DFND</investmentDiscretion>
    <votingAuthority>
      <Sole>12719675</Sole>
      <Shared>0</Shared>
      <None>0</None>
    </votingAuthority>
  </infoTable>
  <!-- ... more entries ... -->
</informationTable>
```

**SEC API 规则（必须遵守）：**
- **User-Agent 必填：** `{项目名} {邮箱}`，否则被封
- **频率限制：** 最多 10 requests/second
- **无需 API Key：** 完全免费

### 5.2 辅助数据源：ARK Invest 每日交易

**URL：** `https://ark-funds.com/wp-content/uploads/funds-etf-csv/ARK_TRADE.csv`

**CSV 格式：**
```
FUND,Date,Direction,Ticker,CUSIP,Name,Shares,% of ETF
ARKK,07/18/2025,Buy,TSLA,88160R101,TESLA INC,150000,1.25
```

### 5.3 数据刷新策略

| 数据源 | 扫描频率 | 触发条件 |
|--------|---------|---------|
| 13F Reports | 每日 1 次（UTC 22:00 = 北京 06:00） | 发现新的 13F-HR filing |
| ARK Trade | 每日 1 次 | 每个交易日 |
| 投资人档案 | 手动维护 | 配置文件更新 |

---

## 6. 非功能需求

### NFR-01: 性能

- 首页加载时间 < 3 秒（静态站点，应该轻松达到）
- 数据构建过程 < 10 分钟（GitHub Actions 限制）

### NFR-02: 可靠性

- 网络请求超时 10 秒 + 3 次重试
- SEC API 临时不可用时不崩溃，跳过并在下次扫描重试
- 所有异常有清晰的错误日志

### NFR-03: 安全

- 零硬编码密钥，全部走 GitHub Secrets / 环境变量
- Telegram bot token 和 chat ID 均通过环境变量传入
- SEC API 无需认证，但 User-Agent 中不暴露敏感信息

### NFR-04: 可维护性

- 投资人名单通过 JSON 配置文件管理，新增/删除无需改代码
- 数据存储在 repo 的 JSON 文件中，版本可追溯
- 文档清晰，另一个人能在 30 分钟内理解系统

### NFR-05: 用户体验

- 暗色主题（zinc 色系 + Inter 字体，与 BTC ETF Tracker 一致）
- 响应式设计，手机可用
- Chart.js 图表可交互

### NFR-06: 合规

- 页面底部声明：「数据来源：SEC EDGAR。仅供研究参考，不构成投资建议。」
- 所有数据引用原始 SEC filing 链接
- 遵守 SEC EDGAR API 使用条款

---

## 7. 里程碑规划

| 阶段 | 目标 | 预估时间 |
|------|------|---------|
| **Phase 1** | 基础数据管道 — 能自动抓取并解析 29 个实体的 13F | 3-5 天 |
| **Phase 2** | 静态站点 — 持仓展示 + 季度对比 + 搜索 | 3-5 天 |
| **Phase 3** | 自动化 — GitHub Actions 每日扫描 + Telegram 推送 | 2-3 天 |
| **Phase 4** | 增强功能 — ARK 每日数据 + 趋势分析 + 大师共识 | 3-5 天 |

### 7.1 各阶段完成标准（验收门禁）

每个阶段必须通过以下验收标准才能进入下一阶段（参照 `verification-before-completion` skill）：

| 阶段 | 完成标准 | 验证方式 |
|------|---------|---------|
| **Phase 1** | ① 29 个实体的 13F 数据至少成功抓取 25 个 ② XML 解析零错误 ③ 解析后 JSON 通过数据质量测试 ④ 所有单元测试通过 | `pytest tests/ -v`，检查 exit code = 0 |
| **Phase 2** | ① 所有 guru 页面可访问 ② 季度对比数据正确（抽查 3 个大师） ③ 搜索功能正常 ④ 首页加载 < 3s ⑤ 移动端可用 | 浏览器手动验证 + Lighthouse 检查 |
| **Phase 3** | ① GitHub Actions 手动触发成功 ② 有新 filing 时 Telegram 收到通知 ③ 连续 3 天无报错运行 | Actions 日志 + Telegram 实际收到消息 |
| **Phase 4** | ① ARK 每日数据拉取成功 ② 共识排行数据正确 ③ 全部测试通过 ④ 覆盖率 ≥ 85% | `pytest --cov` + 手动抽查 |

**铁律：不允许「感觉完成了」就进入下一阶段。必须有命令输出或截图作为证据。**

### 7.2 需求-用户故事-功能映射

| Phase | 覆盖的用户故事 | 对应功能 |
|-------|--------------|---------|
| Phase 1 | — | 数据管道基础设施 |
| Phase 2 | US-01, US-02, US-05, US-06, US-08 | F-01, F-02, F-03, F-05 |
| Phase 3 | US-04 | F-06 |
| Phase 4 | US-03, US-07, US-09 | F-04, F-07 |

---

## 附录 A: 完整 CIK 对照表

> 以下 CIK 需要在开发阶段逐一验证，部分可能有变动（如 ARK 的 CIK 需确认）。

```json
{
  "berkshire_hathaway": {"name": "Berkshire Hathaway Inc", "cik": "0001067983", "style": "value"},
  "himalaya_capital": {"name": "Himalaya Capital Management", "cik": "TODO", "style": "value"},
  "daily_journal": {"name": "Daily Journal Corp", "cik": "0000783412", "style": "value"},
  "fairholme": {"name": "Fairholme Capital Management", "cik": "0001056831", "style": "value"},
  "baupost": {"name": "Baupost Group", "cik": "0001061768", "style": "value"},
  "greenlight": {"name": "Greenlight Capital", "cik": "0001079114", "style": "value"},
  "pabrai": {"name": "Pabrai Investment Funds", "cik": "0001173334", "style": "value"},
  "soros": {"name": "Soros Fund Management", "cik": "0001029160", "style": "macro"},
  "bridgewater": {"name": "Bridgewater Associates", "cik": "0001350694", "style": "macro"},
  "pershing_square": {"name": "Pershing Square Capital", "cik": "0001336528", "style": "macro"},
  "citadel": {"name": "Citadel Advisors", "cik": "0001423053", "style": "macro"},
  "point72": {"name": "Point72 Asset Management", "cik": "0001603466", "style": "macro"},
  "renaissance": {"name": "Renaissance Technologies", "cik": "0001037389", "style": "quant"},
  "de_shaw": {"name": "D.E. Shaw & Co.", "cik": "0001009207", "style": "quant"},
  "two_sigma": {"name": "Two Sigma Investments", "cik": "0001179392", "style": "quant"},
  "millennium": {"name": "Millennium Management", "cik": "0001273087", "style": "macro"},
  "third_point": {"name": "Third Point", "cik": "0001040273", "style": "activist"},
  "ark_invest": {"name": "ARK Investment Management", "cik": "TODO", "style": "growth"},
  "tiger_global": {"name": "Tiger Global Management", "cik": "0001167483", "style": "growth"},
  "coatue": {"name": "Coatue Management", "cik": "0001535392", "style": "growth"},
  "dragoneer": {"name": "Dragoneer Investment Group", "cik": "0001684577", "style": "growth"},
  "altimeter": {"name": "Altimeter Capital Management", "cik": "0001730815", "style": "growth"},
  "d1_capital": {"name": "D1 Capital Partners", "cik": "0001799900", "style": "growth"},
  "sequoia_fund": {"name": "Sequoia Fund", "cik": "0000090168", "style": "value"},
  "appaloosa": {"name": "Appaloosa Management", "cik": "0001656456", "style": "macro"},
  "elliott": {"name": "Elliott Investment Management", "cik": "0001048445", "style": "activist"},
  "icahn": {"name": "Icahn Enterprises", "cik": "0000049588", "style": "activist"},
  "duquesne": {"name": "Duquesne Family Office", "cik": "0001536411", "style": "macro"},
  "duan_yongping": {"name": "DUAN YONG PING", "cik": "0001265354", "style": "value", "filing_type": "SC13G"}
}
```

---

## 附录 B: 13F 报告时间表

SEC 13F 季度报告的提交截止日期：

| 报告期 | 提交截止日 | 通常集中提交时段 |
|--------|-----------|----------------|
| Q1 (截至 3/31) | 5 月 15 日 | 5 月 1-15 日 |
| Q2 (截至 6/30) | 8 月 14 日 | 8 月 1-14 日 |
| Q3 (截至 9/30) | 11 月 14 日 | 11 月 1-14 日 |
| Q4 (截至 12/31) | 2 月 14 日 | 2 月 1-14 日 |

> **注意：** 13F 有 45 天的滞后期。当你在 5 月 15 日看到的报告，反映的是 3 月 31 日的持仓——已经过去 45 天了。大师可能早已调整了仓位。
