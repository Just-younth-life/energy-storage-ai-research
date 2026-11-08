import time
import random
from typing import List, Dict, Any
from schemas import TargetStock

STOCK_MAIN: List[Dict[str, Any]] = [
    {
        "symbol": "300274",
        "stock_name": "阳光电源",
        "main_business_layer": "SYSTEM_INTEGRATE",
        "main_business_weight": 0.72,
        "secondary_business": ["BMS_PCS"],
        "non_energy_storage_business": ["光伏组件"],
        "is_concept_stock": False,
        "caliber_source": "financial_report"
    },
    {
        "symbol": "688063",
        "stock_name": "派能科技",
        "main_business_layer": "CELL",
        "main_business_weight": 0.58,
        "secondary_business": ["SYSTEM_INTEGRATE"],
        "non_energy_storage_business": ["消费电池"],
        "is_concept_stock": False,
        "caliber_source": "financial_report"
    }
]

STOCK_CONCEPT: List[Dict[str, Any]] = [
    {
        "symbol": "002598",
        "stock_name": "山东章鼓",
        "main_business_layer": "RAW_MATERIAL",
        "main_business_weight": 0.004,
        "secondary_business": [],
        "non_energy_storage_business": ["鼓风机制造"],
        "is_concept_stock": True,
        "caliber_source": "public_notice"
    },
    {
        "symbol": "600444",
        "stock_name": "国机通用",
        "main_business_layer": "EPC",
        "main_business_weight": 0.007,
        "secondary_business": [],
        "non_energy_storage_business": ["流体机械管材"],
        "is_concept_stock": True,
        "caliber_source": "public_notice"
    }
]

STOCK_OVERSEA: List[Dict[str, Any]] = [
    {
        "symbol": "NA",
        "stock_name": "Fluence",
        "main_business_layer": "SYSTEM_INTEGRATE",
        "main_business_weight": 0.90,
        "secondary_business": ["BMS_PCS"],
        "non_energy_storage_business": [],
        "is_concept_stock": False,
        "caliber_source": "oversea_report"
    }
]

ALL_STOCK_RAW = STOCK_MAIN + STOCK_CONCEPT + STOCK_OVERSEA

MOCK_EVIDENCE_POOL: List[Dict[str, Any]] = [
    {
        "sec_code": "300274",
        "sec_name": "阳光电源",
        "evidence_id": "ev‑001",
        "source_type": "公告",
        "source_rank": "A",
        "evidence_type": "fact",
        "source_title": "2024年报",
        "publish_time": "2025‑04‑20",
        "evidence_text": "报告期内储能业务实现营业收入120亿元，多个大型储能项目完成交付。",
        "red_flag": False,
        "main_business": "光伏逆变器、储能系统集成"
    },
    {
        "sec_code": "688063",
        "sec_name": "派能科技",
        "evidence_id": "ev‑002",
        "source_type": "年报",
        "source_rank": "A",
        "evidence_type": "fact",
        "source_title": "2024年度报告",
        "publish_time": "2025‑04‑22",
        "evidence_text": "户用储能产品实现大规模海外出货，储能业务确认收入。",
        "red_flag": False,
        "main_business": "户用储能电芯及系统"
    },
    {
        "sec_code": "002598",
        "sec_name": "山东章鼓",
        "evidence_id": "ev‑011",
        "source_type": "公告",
        "source_rank": "A",
        "evidence_type": "fact",
        "source_title": "投资者互动公告",
        "publish_time": "2025‑06‑10",
        "evidence_text": "公司将积极探索储能相关业务机会，暂无落地项目。",
        "red_flag": False,
        "main_business": "鼓风机制造"
    },
    {
        "sec_code": "002598",
        "sec_name": "山东章鼓",
        "evidence_id": "ev‑013",
        "source_type": "股吧",
        "source_rank": "D",
        "evidence_type": "opinion",
        "source_title": "论坛传闻",
        "publish_time": "2025‑07‑01",
        "evidence_text": "山东章鼓拿到百亿储能大订单，即将大规模出货。",
        "red_flag": True,
        "main_business": "鼓风机制造"
    },
    {
        "sec_code": "600444",
        "sec_name": "国机通用",
        "evidence_id": "ev‑012",
        "source_type": "公告",
        "source_rank": "A",
        "evidence_type": "fact",
        "source_title": "投资者问答公告",
        "publish_time": "2025‑06‑15",
        "evidence_text": "公司关注储能赛道发展，将适时研究切入储能领域的可行性，无已签订单。",
        "red_flag": False,
        "main_business": "流体机械、管材"
    },
    {
        "sec_code": "NA",
        "sec_name": "Fluence",
        "evidence_id": "ev‑o01",
        "source_type": "海外年报",
        "source_rank": "A",
        "evidence_type": "fact",
        "source_title": "Fluence 2024 Annual Report",
        "publish_time": "2025‑03‑10",
        "evidence_text": "Fluence面向北美、欧洲提供大型储能系统集成产品，海外大储项目持续交付。",
        "red_flag": False,
        "main_business": "海外储能系统集成"
    },
    {
        "sec_code": "300274",
        "sec_name": "阳光电源",
        "evidence_id": "ev‑f01",
        "source_type": "券商研报",
        "source_rank": "B",
        "evidence_type": "forecast",
        "source_title": "储能行业2025研报",
        "publish_time": "2025‑05‑01",
        "evidence_text": "预计2027年全球储能市场需求将实现大幅增长。",
        "red_flag": False,
        "main_business": "光伏逆变器、储能系统集成"
    },
    {
        "sec_code": "002598",
        "sec_name": "山东章鼓",
        "evidence_id": "ev‑c01",
        "source_type": "公告",
        "source_rank": "A",
        "evidence_type": "fact",
        "source_title": "补充公告",
        "publish_time": "2025‑08‑01",
        "evidence_text": "公司已完成储能示范项目建设，实现小规模交付。",
        "red_flag": False,
        "main_business": "鼓风机制造"
    }
]

SHOCK_EVENT_LIB: List[Dict[str, Any]] = [
    {
        "event_id": "event‑001",
        "event_name": "碳酸锂价格大幅下行",
        "event_source_rank":"B",
        "event_source_desc":"行业大宗商品监测报告",
        "event_type": ["大宗商品价格波动"],
        "affected_chain_links": ["上游资源端", "中游电芯制造"],
        "business_impact": "锂矿企业毛利承压；电芯制造成本下降，电芯厂商盈利改善",
        "impact_direction": "混合",
        "related_fin_index": ["毛利率"],
        "transmission_confidence":"高",
        "transmission_precondition":"无特殊前置条件"
    },
    {
        "event_id": "event‑002",
        "event_name": "美国IRA储能补贴收紧",
        "event_source_rank":"A",
        "event_source_desc":"美国联邦政府法案",
        "event_type": ["地缘贸易政策"],
        "affected_chain_links": ["中游系统集成"],
        "business_impact": "国内储能系统厂商海外出货承压，海外业务盈利受损",
        "impact_direction": "负向",
        "related_fin_index": ["海外营收","毛利率"],
        "transmission_confidence":"中",
        "transmission_precondition":"企业海外储能业务收入占比达到一定规模"
    },
    {
        "event_id": "event‑003",
        "event_name": "国内大储容量电价政策落地",
        "event_source_rank":"A",
        "event_source_desc":"国内能源局官方文件",
        "event_type": ["政策调整"],
        "affected_chain_links": ["中游系统集成","下游应用端"],
        "business_impact": "大型储能电站装机需求提升，带动系统集成厂商订单增长",
        "impact_direction": "正向",
        "related_fin_index": ["订单","资本开支"],
        "transmission_confidence":"高",
        "transmission_precondition":"企业面向国内大储市场"
    }
]

def dedup_evidence(items:List[Dict])->List[Dict]:
    seen=set()
    out=[]
    for x in items:
        eid=x["evidence_id"]
        if eid not in seen:
            seen.add(eid)
            out.append(x)
    return out

def mock_mcp_fuyao(tool_id:str, symbol_list:List[str])->Dict:
    res=[]
    for item in MOCK_EVIDENCE_POOL:
        if item["sec_code"] in symbol_list or item["sec_name"] in symbol_list:
            res.append({
                **item,
                "annual_capacity_gwh":round(random.uniform(0.5,35),2),
                "undelivered_order":round(random.uniform(0,22),2),
                "gross_margin":round(random.uniform(-0.05,0.22),3),
                "source_name":"fuyao",
                "source_type":"terminal",
                "publish_ts":int(time.time())
            })
    res=dedup_evidence(res)
    return {"tool_id":tool_id,"tool_result":res,"status":"success"}

def mock_mcp_ifind(tool_id:str, symbol_list:List[str])->Dict:
    res=[]
    for item in MOCK_EVIDENCE_POOL:
        if item["sec_code"] in symbol_list or item["sec_name"] in symbol_list:
            res.append({
                **item,
                "revenue_storage":round(random.uniform(0.2,120),2),
                "broker_consensus_eps":round(random.uniform(0.1,2.5),2),
                "gross_margin":round(random.uniform(-0.07,0.20),3),
                "source_name":"ifind",
                "source_type":"terminal",
                "publish_ts":int(time.time())
            })
    res=dedup_evidence(res)
    return {"tool_id":tool_id,"tool_result":res,"status":"success"}

def mcp_dispatch(tool_id:str, source:str, symbol_list:List[str]):
    if source == "fuyao":
        return mock_mcp_fuyao(tool_id, symbol_list)
    elif source == "ifind":
        return mock_mcp_ifind(tool_id, symbol_list)
    raise Exception("unknown mcp source")

