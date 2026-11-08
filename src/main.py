import time
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, Query, HTTPException
from pydantic import BaseModel
from schemas import (
    MCPToolCallRequest, LLMInferRequest, LLMInferResponse,
    RedFlagItem
)
from mcp_mock import mcp_dispatch, MOCK_EVIDENCE_POOL, SHOCK_EVENT_LIB, dedup_evidence
from llm_wrapper import call_llm

app = FastAPI(title="电化学储能AI研究Demo")
DISCLAIMER = "【免责声明】本内容仅为产业基本面推演辅助，全部Mock模拟，不构成任何投资建议，市场有风险，投资需谨慎。"

CREDIBILITY_RULE = {
    "L4": {"label": "已落地‑有储能营收", "keywords": ["储能营业收入", "储能营收", "已交付", "在手订单", "确认收入"]},
    "L3": {"label": "试点落地‑小规模项目", "keywords": ["试点项目", "示范项目", "项目签约", "项目落地"]},
    "L2": {"label": "框架协议‑意向合作", "keywords": ["框架协议", "战略合作", "意向协议"]},
    "L1": {"label": "仅概念宣传‑无实质业务", "keywords": ["计划布局", "积极探索", "战略规划", "有望切入"]}
}

PROMPT_EXTRACT_BIZ = "基于下面公告片段，简洁抽取该公司储能相关业务特征，100字以内：{evidence_text}"

def simple_text_sim(a:str,b:str)->float:
    set_a = set(a.replace("，","").replace("。","").split())
    set_b = set(b.replace("，","").replace("。","").split())
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b)/max(len(set_a),len(set_b))

def match_chain_links(main_business:str, evidence_id:str)->tuple[List[str],List[str]]:
    links=[]
    eids=[]
    if "储能系统集成" in main_business:
        links.append("中游系统集成")
        eids.append(evidence_id)
    if "电芯" in main_business:
        links.append("中游电芯制造")
        eids.append(evidence_id)
    return links,eids

def calc_credibility(evidence_list:List[Dict])->tuple[str,str,List[str],List[str],int,RedFlagItem]:
    hit_level_set = set()
    hit_eid = []
    all_chain_evids = []
    cross_validate_count = 0
    red_flag_rule_id = []
    red_flag_desc = []
    red_action = []

    ab_evidences = [e for e in evidence_list if e["source_rank"] in ("A","B")]
    if len(ab_evidences) <=1:
        red_flag_rule_id.append("R01_single_source")
        red_flag_desc.append("仅单一来源，缺少其他独立信源印证")
        red_action.append("页面显著提示，不阻断输出")

    is_same_origin = False
    for i in range(len(ab_evidences)):
        for j in range(i+1,len(ab_evidences)):
            sim = simple_text_sim(ab_evidences[i]["evidence_text"],ab_evidences[j]["evidence_text"])
            if sim>0.75:
                is_same_origin=True
                break
    if is_same_origin:
        red_flag_rule_id.append("R02_same_origin_copy")
        red_flag_desc.append("多条证据同源搬运，不构成有效交叉印证")
        red_action.append("不计入有效交叉印证计数，页面提示同源风险")
    if not is_same_origin:
        cross_validate_count = len(ab_evidences)

    fact_has = any(("已交付" in e["evidence_text"] or "储能营收" in e["evidence_text"]) for e in ab_evidences)
    fact_no = any(("暂无落地项目" in e["evidence_text"]) for e in ab_evidences)
    if fact_has and fact_no:
        red_flag_rule_id.append("R03_high_conflict")
        red_flag_desc.append("多条A/B高可信信源业务事实互相矛盾【Demo关键词占位检测】")
        red_action.append("聚合可信度自动降一级，强制人工复核提醒")

    for ev in evidence_list:
        txt = ev["evidence_text"]
        sr = ev["source_rank"]
        eid = ev["evidence_id"]
        clinks,cevids = match_chain_links(ev["main_business"],eid)
        all_chain_evids.extend(cevids)
        temp_hit_lv = None
        for lv,cfg in CREDIBILITY_RULE.items():
            for kw in cfg["keywords"]:
                if kw in txt:
                    temp_hit_lv = lv
                    break
            if temp_hit_lv:
                break
        if temp_hit_lv:
            if sr in ("A","B","C"):
                hit_level_set.add(temp_hit_lv)
                hit_eid.append(eid)

    level_priority = ["L4","L3","L2","L1"]
    final_lv = "L1"
    for lv in level_priority:
        if lv in hit_level_set:
            final_lv = lv
            break
    if "R03_high_conflict" in red_flag_rule_id:
        idx = level_priority.index(final_lv)
        if idx+1 < len(level_priority):
            final_lv = level_priority[idx+1]

    red_flag_obj = RedFlagItem(
        red_flag_triggered=bool(red_flag_rule_id),
        red_flag_rule_id=red_flag_rule_id,
        red_flag_desc=red_flag_desc,
        red_action=red_action
    )
    return final_lv, CREDIBILITY_RULE[final_lv]["label"], list(set(hit_eid)), list(set(all_chain_evids)), cross_validate_count, red_flag_obj

@app.get("/mock/rag/retrieve")
def mock_rag_retrieve(query:str, sec_name:Optional[str]=None):
    raw = MOCK_EVIDENCE_POOL
    if sec_name:
        raw = [x for x in raw if x["sec_name"] == sec_name]
    raw = dedup_evidence(raw)
    sort_map = {"A":0,"B":1,"C":2,"D":3}
    sorted_items = sorted(raw,key=lambda x: sort_map.get(x["source_rank"],99))
    has_ab = any(i["source_rank"] in ("A","B") for i in sorted_items)
    if not has_ab:
        sorted_items = [i for i in sorted_items if i["source_rank"]!="D"]
    return {
        "query":query,
        "retrieve_size":len(sorted_items),
        "evidence_list":sorted_items,
        "note":"本RAG为内存Mock模拟，无真实向量数据库，未实现发布时间衰减重排"
    }

@app.post("/api/mcp/call")
def api_mcp_call(req:MCPToolCallRequest):
    try:
        return mcp_dispatch(req.tool_id, req.source, req.symbol_list)
    except Exception as e:
        raise HTTPException(status_code=400,detail=str(e))

@app.post("/api/llm/infer",response_model=LLMInferResponse)
def api_llm_infer(req:LLMInferRequest):
    mock_ev_ids = ["ev‑001","ev‑002"]
    mock_shock_ids = ["shk‑001"]
    prompt = f"对标的{req.symbol_list}做储能产业推演，严格遵循可信度规则、冲击传导schema、中外对比控制"
    try:
        raw_text, struct_data = call_llm(
            trace_id=req.request_trace_id,
            user_id=req.user_id,
            prompt=prompt,
            symbol_list=req.symbol_list,
            evidence_ids=mock_ev_ids,
            shock_ids=mock_shock_ids,
            temperature=req.temperature
        )
    except Exception as e:
        raise HTTPException(status_code=500,detail=f"LLM推理异常:{str(e)}")
    return LLMInferResponse(
        request_trace_id=req.request_trace_id,
        natural_report=raw_text + "\n" + DISCLAIMER,
        confidence_results=[],
        shock_list=[],
        cross_region_ctrl={
            "comparable_dim":["电芯单位Wh成本"],
            "incomparable_dim":["国内分时电价"],
            "cross_region_compare_switch":req.enable_cross_compare,
            "block_reason":None,
            "policy_effect_ts":1740000000
        },
        hit_block=False,
        disclaimer_text=DISCLAIMER
    )

@app.get("/api/industry/chain")
def api_industry_chain(industry:str=Query("电化学储能",max_length=128)):
    chain_struct = {
        "disclaimer":DISCLAIMER,
        "industry_name":industry,
        "chain_layers":["上游资源端","上游材料端","中游电芯制造","中游系统集成","下游应用端"],
        "company_list":[],
        "notice":"提示：D级低可信信源仅作线索，建议多源交叉印证"
    }
    comp_map:Dict[str,List[Dict]] = {}
    for comp in MOCK_EVIDENCE_POOL:
        sn = comp["sec_name"]
        if sn not in comp_map:
            comp_map[sn] = []
        comp_map[sn].append(comp)
    for sn, ev_list in comp_map.items():
        lv, label, eids, chain_evids, cross_cnt, redflag_obj = calc_credibility(ev_list)
        sample_ev = ev_list[0]
        links,_ = match_chain_links(sample_ev["main_business"],sample_ev["evidence_id"])
        item = {
            "sec_code": sample_ev["sec_code"],
            "sec_name": sn,
            "chain_links": links,
            "chain_link_evid_ids": chain_evids,
            "credibility_level": lv,
            "credibility_label": label,
            "evidence_ids": eids,
            "cross_validate_count": cross_cnt,
            "red_flag_detail": redflag_obj.model_dump(),
            "sample_evidence_text": sample_ev["evidence_text"],
            "sample_source_rank": sample_ev["source_rank"],
            "sample_evidence_type": sample_ev["evidence_type"]
        }
        chain_struct["company_list"].append(item)
    return chain_struct

@app.get("/api/shock/transmission")
def api_shock_transmission(event_id:str=Query(...,max_length=64)):
    item = next((x for x in SHOCK_EVENT_LIB if x["event_id"]==event_id),None)
    if not item:
        raise HTTPException(status_code=404,detail="事件ID不存在")
    out = dict(item)
    out["disclaimer"] = DISCLAIMER
    return out

@app.get("/api/health")
def health():
    return {"status":"ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app",host="0.0.0.0",port=8000)

