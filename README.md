# energy-storage-ai-research
A AI research product for electrochemical energy storage industry chain, support company credibility rating, China-overseas benchmark comparison, external shock transmission simulation, all conclusions traceable with evidence_id. Demo with mock MCP data, not investment advice.
⚠️全部为Mock模拟数据，**不构成任何投资建议**

## 📁仓库目录
energy-storage-ai-research/
├── README.md                     # 仓库总说明、部署、演示脚本
├── PROJECT_SPEC.md               # 任务一：完整项目设计大纲
├── 测试用例说明.md                # 测试：主链路/异常/合规边界
├── AI_使用与验证记录.md           # AI校验记录
├── main.py                       # FastAPI后端入口
├── schemas.py                    # Pydantic Schema + 枚举
├── mcp_mock.py                   # Mock扶摇、iFinD MCP工具调用
├── llm_wrapper.py                # LLM封装 + jsonl分片审计日志
├── web.py                        # Streamlit Web前端（可操作产品页面）
├── review_helper.py              # 审计日志人工复核辅助脚本
├── .env.example                  # 环境变量模板
├── .gitignore                    # git忽略配置
└── ai_records/                   # 自动生成：按日期分片审计日志
    └── ai_records_20261108.jsonl

