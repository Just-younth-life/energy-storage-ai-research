import json
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_FOLDER = os.path.join(BASE_DIR,"runtime_output","ai_records")

def get_log_path():
    date_str = datetime.now().strftime("%Y%m%d")
    return os.path.join(LOG_FOLDER,f"ai_records_{date_str}.jsonl")

def list_records():
    log_file = get_log_path()
    if not os.path.exists(log_file):
        print(f"日志文件不存在 {log_file},请先运行接口产生日志")
        return []
    records = []
    with open(log_file,"r",encoding="utf‑8") as f:
        for idx,line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            records.append((idx,r))
    for idx,r in records:
        print(f"[{idx}] task:{r['task_name'] if 'task_name' in r else r['request_trace_id']} | is_correct:{r['human_review']['is_correct'] if 'human_review' in r else None}")
    return records

def edit_review(record_index:int,is_correct:bool,error_type:list,error_point:str,human_fix:dict):
    log_file = get_log_path()
    all_lines = []
    with open(log_file,"r",encoding="utf‑8") as f:
        for line in f:
            line = line.strip()
            if line:
                all_lines.append(json.loads(line))
    if record_index <0 or record_index >= len(all_lines):
        print("索引越界")
        return
    rec = all_lines[record_index]
    if "human_review" not in rec:
        rec["human_review"] = {
            "is_correct":None,"auto_check_result":{},"error_type":[],"error_point":"","human_fix_result":{}
        }
    hr = rec["human_review"]
    hr["is_correct"] = is_correct
    hr["error_type"] = error_type
    hr["error_point"] = error_point
    hr["human_fix_result"] = human_fix
    with open(log_file,"w",encoding="utf‑8") as f:
        for item in all_lines:
            f.write(json.dumps(item,ensure_ascii=False)+"\n")
    print("✅已更新该条复核记录")

if __name__ == "__main__":
    recs = list_records()
    if len(recs)==0:
        exit(0)
    idx_in = input("\n输入要编辑的记录序号：")
    idx = int(idx_in)
    ic = input("is_correct(true/false):").strip().lower()=="true"
    err_t_raw = input("error_type(逗号分隔，无则回车):").strip()
    err_t_list = err_t_raw.split(",") if err_t_raw else []
    err_p = input("error_point:")
    fix_str = input("human_fix(json字符串，无则回车):").strip()
    fix_obj = json.loads(fix_str) if fix_str else {}
    edit_review(idx,ic,err_t_list,err_p,fix_obj)

