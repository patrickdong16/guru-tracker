# CLAUDE.md — Guru Tracker 项目编码规则

## 全局规范遵从

本项目遵守 `GEMINI.md` 全局宪法。所有编码标准、安全规则、生命周期管理以全局规范为准。

## 文档索引

| 文档 | 用途 |
|------|------|
| `REQUIREMENTS.md` | 产品需求 — 做什么、为什么做 |
| `TDD.md` | 技术架构 — 怎么建 |
| `TESTING.md` | 测试策略 — 怎么验证 |

## 项目结构

```
guru-tracker/
├── config/          # 投资人配置、全局设置
├── scripts/         # Python 数据管道脚本
├── data/            # JSON 数据存储（raw/parsed/compared）
├── site/            # 生成的静态站点（部署到 GitHub Pages）
├── tests/           # 测试用例 + fixtures
└── .github/         # GitHub Actions workflows
```

## 技术栈

- **后端：** Python 3.11+
- **前端：** 静态 HTML + Tailwind CSS + Chart.js
- **部署：** GitHub Pages
- **CI/CD：** GitHub Actions
- **推送：** Telegram Bot API

## 编码铁律

1. **所有网络请求：** timeout(10s) + retry(3次) + 指数退避
2. **所有函数：** try-except 错误处理，异常必须有上下文
3. **密钥管理：** 零硬编码，全部用环境变量
4. **SEC API：** User-Agent 必填，频率 ≤ 10 req/sec
5. **返回格式：** `{"success": bool, "data": ..., "error": ...}`
6. **命名：** Python snake_case，常量 UPPER_SNAKE_CASE

## 常用命令

```bash
# 运行数据管道
python main.py

# 运行测试
pytest tests/ -v

# 带覆盖率
pytest tests/ --cov=scripts --cov-report=html

# 构建静态站点
python scripts/build_site.py
```

## 环境变量

见 `.env.example`
