import json
import os
from datetime import datetime
from typing import List, Dict, Any, Tuple
from tenacity import retry, stop_after_attempt, wait_exponential
from dotenv import load_dotenv
from openai import OpenAI
from schemas import AILogRecord

load_dotenv()
MODEL_NAME = "deepseek-v3"
PROMPT_VERSION = "v1"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_FOLDER = os.path.join(BASE_DIR,"runtime_output","ai_records")
os.makedirs(LOG_FOLDER, exist_ok=True)

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

def get_log_file_path()->str:
    date_str = datetime.now().strftime("%Y%m%d")
    return os.path.join(LOG_FOLDER, f"ai_records_{date_str}.jsonl")

def write_ai_record(record:AILogRecord):
    path = get_log_file_path()
    with open(path,"a",encoding="utf-8") as f:
        f.write(json.dumps(record.model_dump(), ensure_ascii=False)+"\n")

@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=3))
def call_llm(
    trace_id:str,
    user_id:str,
    prompt:str,
    symbol_list:List[str],
    evidence_ids:List[str],
    shock_ids:List[str],
    temperature:float=0.1,
    top_p:float=0.9
)->Tuple[str, Dict[str,Any]]:
    status = "success"
    err_msg:Optional[str] = None
    raw_resp:Optional[str] = None
    structured:Dict[str,Any] = {}
    token_cost = {"input":len(prompt)//3,"output":0}
    try:
        resp = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role":"user","content":prompt}],
            temperature=temperature,
            top_p=top_p
        )
        raw_resp = resp.choices[0].message.content
        if resp.usage:
            token_cost["input"] = resp.usage.prompt_tokens
            token_cost["output"] = resp.usage.completion_tokens
        structured = {"mock_struct":True}
    except Exception as e:
        status = "error"
        err_msg = str(e)
    log_rec = AILogRecord(
        request_trace_id=trace_id,
        user_id=user_id,
        create_ts=int(datetime.now().timestamp()),
        llm_model=MODEL_NAME,
        prompt_version=PROMPT_VERSION,
        temperature=temperature,
        top_p=top_p,
        input_symbol_list=symbol_list,
        input_evidence_ids=evidence_ids,
        shock_ids=shock_ids,
        conclusion_ids=[],
        hit_incomparable_dim=False,
        confidence_list=[],
        status=status,
        error_msg=err_msg,
        prompt=prompt,
        llm_raw_response=raw_resp,
        structured_result=structured,
        cost_tokens=token_cost,
        rule_version={"confidence":"conf‑v1.0","shock":"shock‑v1.0"}
    )
    write_ai_record(log_rec)
    if status=="error":
        raise Exception(err_msg)
    return raw_resp, structured

