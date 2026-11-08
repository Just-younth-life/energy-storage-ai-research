# PROJECT_SPEC.md｜电化学储能AI研究产品项目设计大纲
## 1 业务模型定义
### 1.1 储能产业链分层口径（仅电化学储能；抽水蓄能、压缩空气、飞轮储能排除）
1. 上游资源端：锂矿、钴矿、镍矿等矿产原材料
2. 上游材料端：正极、负极、电解液、隔膜、铜箔
3. 中游电芯制造：储能专用电芯生产
4. 中游系统集成：BMS、PCS、储能系统打包集成
5. 下游应用端：大型储能电站、工商业储能、户用储能

> 约束：单家公司可归属多个环节；LLM仅抽取业务原文；环节匹配代码硬编码规则；**产业链归属结论绑定evidence_id实现可追溯**。

### 1.2 双层可信度体系
#### ①证据片段信源等级 A/B/C/D
|等级|定义|样例来源|处理规则|
|---|---|---|---|
|A|官方强可信|年报、交易所公告、政府官方文件|可直接采信|
|B|专业第三方权威|券商正式研报、行业协会报告|可采信|
|C|半可信线索|互动易、正规行业新闻|仅线索，建议交叉印证|
|D|低可信传闻|股吧、匿名自媒体|仅线索；必须至少1条A/B证据交叉印证才可参考|

证据类型枚举：
- `fact`：已发生客观事实
- `forecast`：机构未来预测
- `opinion`：主观分析观点
> Demo仅做元数据标记，未纳入可信度加权运算。

#### ②红旗预警Schema（检测+处置）
```json
{
  "red_flag_triggered":true|false,
  "red_flag_rule_id":["R01_single_source","R02_same_origin_copy","R03_high_conflict"],
  "red_flag_desc":["仅单一来源","多条证据同源搬运","多条A/B信源事实互相矛盾"],
  "red_action":["页面显著提示","不计入交叉印证计数","可信度自动降一级+人工复核提醒"]
}
```
> R03 仅关键词占位实现，非语义冲突检测。

#### ③标的业务可信度 L4‑L1
等级	标签	判定标准	匹配关键词集合
L4	已落地‑有储能营收	年报披露储能业务收入、已交付项目、在手确定订单	储能营业收入、储能营收、已交付、在手订单、确认收入
L3	试点落地‑小规模项目	存在签约试点项目，无单独披露储能板块营收	试点项目、示范项目、项目签约、项目落地
L2	框架协议‑意向合作	仅框架、战略合作，无明确落地订单时间表	框架协议、战略合作、意向协议
L1	仅概念宣传‑无实质业务	仅口头 / 公告表态布局储能，无项目无订单无收入	计划布局、积极探索、战略规划、有望切入

> **可信度等级判定执行流程（硬编码，LLM 不执行业务判定）**
> 
> 
> 1. 通过 MCP/Mock‑RAG 获取单家公司多条证据片段；
> 2. LLM 仅负责文本内容抽取，**不做可信度打分、业务推理**；
> 3. D 级信源命中关键词，仅作为线索，不能直接提升业务可信度；
> 4. 同源复制证据不计入有效交叉印证计数；
> 5. R03 高可信证据冲突触发时，聚合可信度自动降一级；
> 6. 输出结果强制绑定`evidence_id`，实现每一条业务结论证据可追溯。

#### ④字段访问权限约束

- ✅**终端用户可见字段（业务 API 对外返回）**：产业链分层、公司业务可信度、信源等级、红旗描述、证据片段、冲击事件业务信息；**全部关键结论携带对应 evidence_id 溯源；业务接口顶层携带机器可读 disclaimer 合规字段**。
- 🔒**后台审计字段（仅写入 ai_records.jsonl，禁止业务接口返回前端）**：`raw_llm_response`原始大模型输出、`human_review`完整人工复核对象。

### 1.3 中外可比 / 不可比维度

✅可比：产品形态、成本结构、技术指标、盈利模式
❌不可比：补贴政策、电网机制、供应链本土壁垒、海外合规认证

> 
> 规则：MCP‑RAG 获取国内、海外证据；LLM 抽取业务特征；**对比结论绑定 evidence_id 溯源**；Demo 固定输出全部枚举维度。

### 1.4 外部冲击‑产业链‑公司‑财务指标传导 Schema
{
  "event_id":"string",
  "event_name":"string",
  "event_source_rank":"A/B/C/D",
  "event_source_desc":"来源描述",
  "event_type":["大宗商品价格波动","政策调整","地缘贸易政策"],
  "affected_chain_links":[...],
  "business_impact":"业务影响简述",
  "impact_direction":"正向|负向|混合",
  "related_fin_index":["毛利率","营收","资本开支"],
  "transmission_confidence":"高|中|低",
  "transmission_precondition":"生效前置条件"
}
预定义事件：碳酸锂下行；美国 IRA 补贴收紧；国内大储容量电价落地；每条附带信源等级、置信度、前置条件。

### 1.5 Mock‑RAG 三级递进筛选

> 
> ⚠️边界：内存模拟，无真实向量库；重排依据 source_rank；简易 D 级证据过滤；做 evidence_id 去重；未实现时间衰减重排。
> 1. 召回层：内存 mock 输出候选证据；
> 2. 重排层：信源等级排序；过滤无 A/B 伴随的 D 级证据；去重；
> 3. 引用选择层：输出证据送入 LLM 文本抽取。

## 2 MVP 必做 / 加分 / 直接放弃

### ✅必做（满足笔试提交硬性要求）

1. Mock 扶摇 MCP、iFinD MCP；Mock‑RAG；样本包含真实头部标的、2 家蹭概念标的、海外标的；内置矛盾 / 预测 / 观点测试样本；支持模拟超时、空返回脏输入。
2. LLM 封装，强制按日期分片落盘`ai_records_*.jsonl`；携带 trace_id、prompt_version、证据元数据；必须绑定 source_evidence_id；审计与业务字段隔离。
3. FastAPI 接口：mock/rag/retrieve；mock/mcp/company；api/industry/chain；api/company/compare；api/shock/transmission；Pydantic 完整 schema；全部关键结论 evidence_id 溯源。
4. Streamlit Web 前端可操作；展示信源等级、证据类型、红旗预警、原始证据片段、溯源 ID。
5. 完整交付文档：README.md、AI_使用与验证记录.md、测试用例说明.md、.gitignore、.env.example。
6. 合规：机器可读 disclaimer；页面免责声明；不输出投资建议。

### ➕加分

1. 前端按信源、可信度筛选；Mermaid 架构图；页面展示幻觉样例。

### ❌直接放弃

1. 不接入真实扶摇 /iFinD；不部署真实向量库；不爬虫海量网页；
2. 不做用户自定义冲击事件；无登录权限；不做模型微调；
3. 不实现全部 8 条红旗；不做股价、估值、买卖建议；不做 pytest 自动化 UT。

## 3 数据源 Mock 方案

1. 两套 MCP 模拟：扶摇 MCP（订单产能视角）；iFinD MCP（财报、一致预期视角）。
2. 样本集合：头部 L4、L3 试点、L2 框架；2 家 L1 蹭概念标的；海外 Fluence；
3. 专项测试样本：A 公告 + D 股吧传闻矛盾样本；forecast 预测样本；opinion 观点样本；两条 A 等级事实冲突样本；
4. Mock 异常：simulate_timeout、simulate_empty；返回结果自动 evidence_id 去重。

## 4 LLM 调用封装 & ai_records 日志规约

1. LLM deepseek‑v3 temperature=0.1；仅文本抽取；禁止业务打分推演；prompt_version="v1"。
2. 强制约束：每次调用必须传入 source_evidence_id；禁止无证据 ID 调用。
3. 日志按日期分片：`ai_records_YYYYMMDD.jsonl`；无论成功 / 报错 / 超时强制落盘；字段包含 request_trace_id、user_id、prompt_version、evidence_meta、auto_check_result 机器校验。
4. 禁止业务接口输出 raw_llm_response、human_review。

## 5 测试用例总览

1. 正常主链路：产业链查询；中外对比；冲击推演；证据溯源校验。
2. 接口异常：MCP 超时；MCP 空返回；LLM 调用异常。
3. 信源专项：D 级证据不提升可信度；R01/R02/R03 红旗触发。
4. 合规边界：接口输出 disclaimer；无任何投资买卖建议输出。

## 6 已知系统局限
---
