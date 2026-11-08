from pydantic import BaseModel, Field, ConfigDict
from enum import Enum
from typing import List, Optional, Dict, Any

class BusinessLayerEnum(str, Enum):
    RAW_MATERIAL = "RAW_MATERIAL"
    CELL = "CELL"
    BMS_PCS = "BMS_PCS"
    SYSTEM_INTEGRATE = "SYSTEM_INTEGRATE"
    EPC = "EPC"
    STATION_OPERATE = "STATION_OPERATE"
    SERVICE = "SERVICE"

class ConfidenceLevelEnum(str, Enum):
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    L4 = "L4"

class TransferTypeEnum(str, Enum):
    DIRECT = "direct"
    INDIRECT = "indirect"

class EvidenceItem(BaseModel):
    source_id: str
    source_type: str
    quote_segment: Optional[str] = None
    publish_ts: int = Field(gt=0)
    model_config = ConfigDict(extra="forbid")

class ConfidenceConclusion(BaseModel):
    conclusion_id: str
    target_symbol: str
    confidence_level: ConfidenceLevelEnum
    evidence_list: List[EvidenceItem]
    confidence_downgrade_reason: Optional[str] = None
    rule_version: str
    model_config = ConfigDict(extra="forbid")

class RedFlagItem(BaseModel):
    red_flag_triggered: bool
    red_flag_rule_id: List[str]
    red_flag_desc: List[str]
    red_action: List[str]
    model_config = ConfigDict(extra="forbid")

class ShockTransferSchema(BaseModel):
    event_id: str
    event_name: str
    event_source_rank: str
    event_source_desc: str
    event_type: List[str]
    affected_chain_links: List[str]
    business_impact: str
    impact_direction: str
    related_fin_index: List[str]
    transmission_confidence: str
    transmission_precondition: str
    model_config = ConfigDict(extra="forbid")

class CrossRegionCompareSchema(BaseModel):
    comparable_dim: List[str]
    incomparable_dim: List[str]
    cross_region_compare_switch: bool
    block_reason: Optional[str] = None
    policy_effect_ts: int
    model_config = ConfigDict(extra="forbid")

class TargetStock(BaseModel):
    symbol: str
    stock_name: str
    main_business_layer: BusinessLayerEnum
    main_business_weight: float = Field(ge=0, le=1)
    secondary_business: List[BusinessLayerEnum]
    non_energy_storage_business: List[str]
    is_concept_stock: bool = False
    caliber_source: str
    model_config = ConfigDict(extra="forbid")

class MCPToolCallRequest(BaseModel):
    tool_id: str
    session_id: str
    symbol_list: List[str]
    source: str = Field(pattern="^(fuyao|ifind)$")
    model_config = ConfigDict(extra="forbid")

class LLMInferRequest(BaseModel):
    request_trace_id: str
    user_id: str
    symbol_list: List[str]
    enable_cross_compare: bool = True
    enable_shock_analysis: bool = True
    prompt_version: str = "v1"
    temperature: float = Field(ge=0, le=1, default=0.2)
    model_config = ConfigDict(extra="forbid")

class LLMInferResponse(BaseModel):
    request_trace_id: str
    natural_report: str
    confidence_results: List[ConfidenceConclusion]
    shock_list: List[ShockTransferSchema]
    cross_region_ctrl: CrossRegionCompareSchema
    hit_block: bool
    disclaimer_text: str
    model_config = ConfigDict(extra="forbid")

class AILogRecord(BaseModel):
    request_trace_id: str
    user_id: str
    create_ts: int
    llm_model: str
    prompt_version: str
    temperature: float
    top_p: float
    input_symbol_list: List[str]
    input_evidence_ids: List[str]
    shock_ids: List[str]
    conclusion_ids: List[str]
    hit_incomparable_dim: bool
    confidence_list: List[Dict[str, str]]
    status: str
    error_msg: Optional[str]
    prompt: str
    llm_raw_response: Optional[str]
    structured_result: Optional[Dict[str, Any]]
    cost_tokens: Dict[str, int]
    rule_version: Dict[str, str]
    model_config = ConfigDict(extra="forbid")

