# -*- coding: utf-8 -*-
"""电化学储能AI研究｜笔试Demo —— Streamlit 投研工作台前端。

设计原则（结论优先、证据后置、术语隔离）：
    - 主业务视图只展示：一句话结论、彩色可信度 badge、风险红旗、核心指标；
    - trace_id / evidence_id / 日志路径 / 调试命令 / 原始报错 / 原始 JSON
      统一收进侧边栏「🔍评审/调试信息（普通用户无需点开）」折叠面板；
    - 全量状态仅存在 st.session_state，不新增任何本地持久化文件或数据库。

后端接口（不改动、不新增字段）：
    GET  /api/industry/chain
    POST /api/llm/infer
    GET  /api/shock/transmission
    GET  /api/health

本产品为笔试Demo，全部为Mock模拟数据。仅做页面展示与接口调用，不改动后端业务逻辑。
"""

import html
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
import streamlit as st

BASE_URL = "http://127.0.0.1:8000"
DISCLAIMER = "本工具仅为投研信息参考，不构成任何投资建议，AI 结果存在幻觉风险，请人工核验原始证据"
DEFAULT_INDUSTRY = "电化学储能"
DEFAULT_USER_ID = "test-review-001"
LLM_MODEL_NAME = "deepseek-v3"
LLM_API_MODEL = "deepseek-chat"
PROMPT_VERSION = "v1"
AUDIT_LOG_PATH = "runtime_output/ai_records/*.jsonl"
REVIEW_CMD = "python src/review_helper.py"

# 后端 event_id 使用 U+2011（非断行连字符），显式拼接避免被替换成 ASCII "-"
_EVENT_HYPHEN = "\u2011"
EVENT_OPTIONS = [f"event{_EVENT_HYPHEN}00{i}" for i in (1, 2, 3)]

LOG_DIR = Path(__file__).resolve().parents[1] / "runtime_output" / "ai_records"

NAV_CHAIN = "📊 产业链研判"
NAV_COMPARE = "🔍 中外对标分析"
NAV_SHOCK = "⚡ 冲击事件推演"
NAV_POOL = "🗂 标的汇总看板"
NAV_ITEMS = [NAV_CHAIN, NAV_COMPARE, NAV_SHOCK, NAV_POOL]

DIRTY_MSG_SHOCK = "当前存在未保存的冲击推演参数，切换研判范式会清空临时参数，是否继续？"
DIRTY_MSG_COMPARE = "当前存在未提交的对标分析输入，切换研判范式会清空临时参数，是否继续？"

# ---------------------------------------------------------------- 通用样式工具

_BADGE_BASE = (
    "display:inline-block;padding:1px 9px;border-radius:10px;"
    "font-size:12px;font-weight:600;line-height:19px;white-space:nowrap;"
)


def _badge(text: Any, fg: str, bg: str) -> str:
    """原生 HTML span 彩色 badge，不引入任何第三方前端组件。"""
    return (
        f'<span style="{_BADGE_BASE}color:{fg};background:{bg};'
        f'border:1px solid {fg}33;">{html.escape(str(text))}</span>'
    )


# 4 档可信度固定配色（L4 绿 / L3 黄 / L2 橙 / L1 红），全站唯一来源
LEVEL_META = {
    "L4": ("🟢", "#1a7f37", "#e6f4ea"),
    "L3": ("🟡", "#9a6700", "#fff8c5"),
    "L2": ("🟠", "#bc4c00", "#fff1e5"),
    "L1": ("🔴", "#cf222e", "#ffebe9"),
}
RANK_META = {
    "A": ("#1a7f37", "#e6f4ea"),
    "B": ("#0969da", "#ddf4ff"),
    "C": ("#bc4c00", "#fff1e5"),
    "D": ("#82071e", "#ffebe9"),
}
CONFIDENCE_META = {
    "高": ("#1a7f37", "#e6f4ea"),
    "中": ("#9a6700", "#fff8c5"),
    "低": ("#cf222e", "#ffebe9"),
}
DIRECTION_META = {
    "正向": ("#1a7f37", "#e6f4ea"),
    "负向": ("#cf222e", "#ffebe9"),
    "混合": ("#bc4c00", "#fff1e5"),
}
SCORE_FG = {"high": ("#1a7f37", "#e6f4ea"), "mid": ("#9a6700", "#fff8c5"), "low": ("#cf222e", "#ffebe9")}


def _credibility_badge(level: str, label: str) -> str:
    emoji, fg, bg = LEVEL_META.get(str(level), ("⚪", "#57606a", "#f6f8fa"))
    return _badge(f"{emoji} {level} · {label}", fg, bg)


def _rank_badge(rank: Any) -> str:
    key = str(rank).upper()
    fg, bg = RANK_META.get(key, ("#57606a", "#f6f8fa"))
    return _badge(f"信源 {key} 级", fg, bg)


def _confidence_badge(conf: Any) -> str:
    fg, bg = CONFIDENCE_META.get(str(conf), ("#57606a", "#f6f8fa"))
    return _badge(f"传导置信度 {conf}", fg, bg)


def _direction_badge(direction: Any) -> str:
    fg, bg = DIRECTION_META.get(str(direction), ("#57606a", "#f6f8fa"))
    return _badge(f"影响{direction}", fg, bg)


def _risk_badge(triggered: bool) -> str:
    return (
        _badge("⚠️ 存在风险红旗", "#cf222e", "#ffebe9")
        if triggered
        else _badge("✅ 无风险红旗", "#1a7f37", "#e6f4ea")
    )


def _score_badge(score: Any) -> str:
    try:
        value = int(score)
    except (TypeError, ValueError):
        return _badge("综合研判分 —", "#57606a", "#f6f8fa")
    if value >= 75:
        fg, bg = SCORE_FG["high"]
    elif value >= 55:
        fg, bg = SCORE_FG["mid"]
    else:
        fg, bg = SCORE_FG["low"]
    return _badge(f"综合研判分 {value}", fg, bg)


def _join(values: Optional[List[Any]]) -> str:
    if not values:
        return "—"
    return "、".join(str(v) for v in values)


def _fmt_ts(ts: Any) -> str:
    try:
        return datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError, OSError):
        return str(ts)


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _one_line(text: Any, limit: int = 90) -> str:
    """把长文本压成一句话摘要，避免大段原文直接占据页面首屏。"""
    compact = " ".join(str(text or "").replace("#", "").split())
    if not compact:
        return "暂无摘要"
    return compact[:limit] + ("…" if len(compact) > limit else "")


# ---------------------------------------------------------------- 接口请求（含调试信息捕获）


def _push_debug_error(path: str, status: Optional[int], detail: str) -> None:
    """原始错误只进调试面板，不暴露给普通用户。"""
    errors = st.session_state.setdefault("debug_errors", [])
    errors.insert(0, {
        "time": _now_str(),
        "path": path,
        "status": status if status is not None else "—",
        "detail": detail[:2000],
    })
    st.session_state["debug_errors"] = errors[:10]


def _api_request(
    method: str,
    path: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    json_body: Optional[Dict[str, Any]] = None,
    timeout: int = 30,
) -> Tuple[Optional[Dict[str, Any]], Optional[str], Optional[int]]:
    """统一接口请求；返回 (data, 人话错误, HTTP状态码)。异常不向页面抛栈。"""
    try:
        resp = requests.request(
            method, f"{BASE_URL}{path}", params=params, json=json_body, timeout=timeout
        )
    except requests.exceptions.ConnectionError:
        _push_debug_error(path, None, "ConnectionError: 无法连接后端服务")
        return None, "暂时无法连接分析服务，请确认后端已启动后重试。", None
    except requests.exceptions.Timeout:
        _push_debug_error(path, None, f"Timeout: 超过 {timeout}s")
        return None, "分析服务响应较慢，请稍后重试。", None
    except requests.exceptions.RequestException as exc:
        _push_debug_error(path, None, f"{type(exc).__name__}: {exc}")
        return None, "网络请求异常，请稍后重试。", None

    if resp.status_code != 200:
        detail: Any = ""
        try:
            body = resp.json()
            if isinstance(body, dict):
                detail = body.get("detail", "")
        except ValueError:
            detail = resp.text[:300]
        _push_debug_error(path, resp.status_code, str(detail) or resp.text[:500])
        return None, "分析服务返回异常，本次未能生成结果；可稍后重试或联系管理员查看调试信息。", resp.status_code

    try:
        data = resp.json()
    except ValueError:
        _push_debug_error(path, resp.status_code, resp.text[:500])
        return None, "分析结果格式异常，请稍后重试。", resp.status_code

    if not isinstance(data, dict):
        _push_debug_error(path, resp.status_code, "返回结构不是 JSON 对象")
        return None, "分析结果格式异常，请稍后重试。", resp.status_code

    st.session_state["debug_last_response"] = {"path": path, "data": data, "time": _now_str()}
    return data, None, resp.status_code


# ---------------------------------------------------------------- 会话状态与标的档案

LEVEL_SCORE = {"L4": 90, "L3": 75, "L2": 55, "L1": 35}


def _init_state() -> None:
    ss = st.session_state
    ss.setdefault("active_tab", NAV_ITEMS[0])
    ss.setdefault("nav_tab", NAV_ITEMS[0])
    ss.setdefault("pending_tab", None)
    ss.setdefault("pending_tab_msg", "")
    ss.setdefault("current_target_id", None)
    ss.setdefault("targets", {})
    ss.setdefault("pool_watch", [])
    ss.setdefault("pool_focus", [])
    ss.setdefault("history", [])
    ss.setdefault("filter_level", "全部")
    ss.setdefault("filter_red_only", False)
    ss.setdefault("scenarios", {
        "基准": {"demand": 15, "li_price": -10, "policy": 3},
        "乐观": {"demand": 30, "li_price": 5, "policy": 4},
        "悲观": {"demand": 5, "li_price": -25, "policy": 2},
    })
    ss.setdefault("scenario_name", "基准")
    ss.setdefault("dirty", {"shock": False, "compare": False})
    ss.setdefault("chain_data", None)
    ss.setdefault("chain_error", None)
    ss.setdefault("compare_domestic", "阳光电源")
    ss.setdefault("compare_overseas", "Fluence")
    ss.setdefault("compare_user_id", DEFAULT_USER_ID)
    ss.setdefault("compare_result", None)
    ss.setdefault("compare_error", None)
    ss.setdefault("compare_trace_id", str(uuid.uuid4()))
    ss.setdefault("shock_event", EVENT_OPTIONS[0])
    ss.setdefault("shock_result", None)
    ss.setdefault("shock_error", None)
    ss.setdefault("brief", None)
    ss.setdefault("brief_error", None)
    ss.setdefault("pool_view", "全部标的")
    ss.setdefault("debug_errors", [])
    ss.setdefault("debug_last_response", None)
    ss.setdefault("_audit_index", None)


def _tid(item: Dict[str, Any]) -> str:
    return str(item.get("sec_code") or item.get("sec_name") or "")


def _score_of(profile: Dict[str, Any]) -> int:
    score = LEVEL_SCORE.get(str(profile.get("credibility_level", "L1")), 35)
    if profile.get("red_flag_triggered"):
        score -= 10
    try:
        if int(profile.get("cross_validate_count") or 0) >= 2:
            score += 5
    except (TypeError, ValueError):
        pass
    shock = (profile.get("conclusions") or {}).get("shock") or {}
    if shock.get("confidence") == "高":
        score += 5
    elif shock.get("confidence") == "低":
        score -= 5
    return max(0, min(100, score))


def _ensure_target(item: Dict[str, Any]) -> str:
    """产业链结果结构化写入前端标的档案（正向透传的落点）。"""
    tid = _tid(item)
    targets = st.session_state["targets"]
    profile = targets.get(tid) or {
        "sec_code": item.get("sec_code", "—"),
        "sec_name": item.get("sec_name", "未知标的"),
        "tags": [],
        "conclusions": {},
        "updated_at": "—",
    }
    red = item.get("red_flag_detail") or {}
    profile.update({
        "sec_code": item.get("sec_code", "—"),
        "sec_name": item.get("sec_name", "未知标的"),
        "chain_links": item.get("chain_links") or [],
        "chain_link_evid_ids": item.get("chain_link_evid_ids") or [],
        "evidence_ids": item.get("evidence_ids") or [],
        "credibility_level": item.get("credibility_level", "L1"),
        "credibility_label": item.get("credibility_label", ""),
        "cross_validate_count": item.get("cross_validate_count", 0),
        "red_flag_triggered": bool(red.get("red_flag_triggered")),
        "red_flag_detail": red,
        "source_rank": item.get("sample_source_rank", "—"),
        "evidence_type": item.get("sample_evidence_type", ""),
        "sample_evidence_text": item.get("sample_evidence_text", ""),
    })
    profile["risk_tags"] = [str(x) for x in (red.get("red_flag_desc") or [])]
    profile["updated_at"] = _now_str()
    profile["conclusions"]["chain"] = {
        "summary": (
            f"{profile['credibility_level']} · {profile['credibility_label']}；"
            f"有效交叉印证 {profile['cross_validate_count']} 条；"
            f"{'存在风险红旗' if profile['red_flag_triggered'] else '暂无风险红旗'}"
        ),
        "tags": [f"环节:{_join(profile['chain_links'])}"],
        "evidence_ids": list(dict.fromkeys(
            list(profile.get("chain_link_evid_ids") or []) + list(profile.get("evidence_ids") or [])
        )),
        "source_type": _source_label(profile.get("evidence_type")),
        "trace_id": None,
        "time": profile["updated_at"],
    }
    profile["score"] = _score_of(profile)
    targets[tid] = profile
    return tid


def _source_label(evidence_type: Any) -> str:
    mapping = {
        "fact": "公告事实（扶摇 MCP 模拟）",
        "forecast": "机构预测（iFinD MCP 模拟）",
        "opinion": "市场观点（资讯 MCP 模拟）",
    }
    return mapping.get(str(evidence_type), "产业数据库（MCP 模拟）")


def _sync_chain_targets(data: Dict[str, Any]) -> None:
    ids = [_ensure_target(item) for item in (data.get("company_list") or [])]
    watch = st.session_state["pool_watch"]
    focus = st.session_state["pool_focus"]
    for tid in ids:
        if tid not in watch and tid not in focus:
            watch.append(tid)


def _current_target() -> Optional[Dict[str, Any]]:
    tid = st.session_state.get("current_target_id")
    if not tid:
        return None
    return st.session_state["targets"].get(tid)


def _set_current_target(tid: Optional[str]) -> None:
    st.session_state["current_target_id"] = tid
    # 延后同步标的池选择框，避免组件实例化后再写入状态
    st.session_state["_pending_pool_select"] = tid or ""


def _record_conclusion(tab_key: str, payload: Dict[str, Any]) -> None:
    """反向回流：结构化标签 / 摘要 / 分值写回标的档案。"""
    target = _current_target()
    if not target:
        return
    target["conclusions"][tab_key] = payload
    target["updated_at"] = payload.get("time", _now_str())
    tags = list(target.get("tags") or [])
    for tag in payload.get("tags") or []:
        if tag and tag not in tags:
            tags.append(tag)
    target["tags"] = tags
    target["score"] = _score_of(target)


def _add_history(tab_label: str, trace_id: Optional[str], title: str, summary: str) -> None:
    target = _current_target()
    st.session_state["history"] = ([{
        "time": _now_str(),
        "tab": tab_label,
        "target": target.get("sec_name") if target else "—",
        "trace_id": trace_id or "",
        "title": title,
        "summary": summary,
    }] + st.session_state["history"])[:20]
    st.session_state["_audit_index"] = None


def _status_text(status: Any) -> str:
    return {"success": "成功", "error": "失败", "blocked": "已阻断"}.get(str(status), str(status))


def _load_audit_index() -> Dict[str, Tuple[Dict[str, Any], str]]:
    cached = st.session_state.get("_audit_index")
    if cached is not None:
        return cached
    index: Dict[str, Tuple[Dict[str, Any], str]] = {}
    try:
        for path in sorted(LOG_DIR.glob("ai_records_*.jsonl"), reverse=True)[:3]:
            with path.open("r", encoding="utf-8") as handler:
                for line in handler:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except ValueError:
                        continue
                    trace = record.get("request_trace_id")
                    if trace:
                        index[trace] = (record, path.name)
    except OSError:
        pass
    st.session_state["_audit_index"] = index
    return index


# ---------------------------------------------------------------- 情景与脏状态


def _scenario_params(name: Optional[str]) -> Dict[str, int]:
    name = name or "基准"
    base = st.session_state["scenarios"].get(name, {"demand": 15, "li_price": -10, "policy": 3})
    return {
        "demand": st.session_state.get(f"sc_demand_{name}", base["demand"]),
        "li_price": st.session_state.get(f"sc_price_{name}", base["li_price"]),
        "policy": st.session_state.get(f"sc_policy_{name}", base["policy"]),
    }


def _mark_shock_dirty() -> None:
    st.session_state["dirty"] = {**st.session_state["dirty"], "shock": True}


def _mark_compare_dirty() -> None:
    st.session_state["dirty"] = {**st.session_state["dirty"], "compare": True}


def _dirty_reason() -> str:
    dirty = st.session_state["dirty"]
    if dirty.get("shock"):
        return DIRTY_MSG_SHOCK
    if dirty.get("compare"):
        return DIRTY_MSG_COMPARE
    return ""


def _apply_pending_actions() -> None:
    """在组件实例化之前应用跨次运行的待处理动作，避免写已实例化组件报错。"""
    ss = st.session_state
    pending_scenario = ss.pop("_pending_scenario", None)
    if pending_scenario:
        ss["scenario_name"] = pending_scenario
        ss["scenario_pick"] = pending_scenario

    pending_nav = ss.pop("_pending_nav", None)
    if pending_nav:
        ss["nav_tab"] = pending_nav

    pending_pool_view = ss.pop("_pending_pool_view", None)
    if pending_pool_view:
        ss["pool_view"] = pending_pool_view

    reset = ss.pop("_pending_drafts_reset", None)
    if reset:
        if reset.get("shock"):
            ss["shock_event"] = EVENT_OPTIONS[0]
            for name, params in ss["scenarios"].items():
                ss[f"sc_demand_{name}"] = params["demand"]
                ss[f"sc_price_{name}"] = params["li_price"]
                ss[f"sc_policy_{name}"] = params["policy"]
        if reset.get("compare"):
            target = _current_target()
            ss["compare_domestic"] = target.get("sec_name") if target else "阳光电源"
            ss["compare_overseas"] = "Fluence"


# ---------------------------------------------------------------- 侧边栏（上半区：业务工作台）


def _pool_label(tid: str) -> str:
    profile = st.session_state["targets"].get(tid) or {}
    icon = "⭐ 重点跟踪" if tid in st.session_state["pool_focus"] else "👀 观察"
    return f"{icon} · {profile.get('sec_name', tid)}（{tid}）"


def _on_pool_select_change() -> None:
    value = st.session_state.get("pool_select")
    mapping = st.session_state.get("_pool_display_map") or {}
    st.session_state["current_target_id"] = mapping.get(value) or None


def _render_sidebar() -> None:
    ss = st.session_state
    with st.sidebar:
        st.title("电化学储能AI研究｜笔试Demo")
        st.caption("投研辅助工作台 · 结论优先 · 证据可下钻")
        st.markdown(f"**{DISCLAIMER}**")

        st.divider()
        st.markdown("### 🗂 标的池")
        targets = ss["targets"]
        if not targets:
            st.caption("标的池为空，可在「📊 产业链研判」加载数据集。")
        else:
            focus = [t for t in ss["pool_focus"] if t in targets]
            watch = [t for t in ss["pool_watch"] if t in targets and t not in focus]
            st.caption(f"👀 观察池 {len(watch)} 个 ｜ ⭐ 重点跟踪池 {len(focus)} 个")

            # 从其它页面「设为当前标的」时，在此统一同步下拉框（组件实例化前生效）
            pending_pick = ss.pop("_pending_pool_select", None)
            force_sync = pending_pick is not None
            if pending_pick is not None:
                ss["current_target_id"] = pending_pick or None

            options = ["（未选择标的）"]
            display_map = {"（未选择标的）": ""}
            for tid in focus:
                label = f"⭐ 重点跟踪池 · {targets[tid].get('sec_name', tid)}（{tid}）"
                options.append(label)
                display_map[label] = tid
            for tid in watch:
                label = f"👀 观察池 · {targets[tid].get('sec_name', tid)}（{tid}）"
                options.append(label)
                display_map[label] = tid
            ss["_pool_display_map"] = display_map

            current = ss.get("current_target_id") or ""
            current_display = next((k for k, v in display_map.items() if v == current), "（未选择标的）")
            if force_sync or ss.get("pool_select") not in options:
                ss["pool_select"] = current_display
            st.selectbox(
                "选择标的（自动带入全部研判范式）",
                options,
                key="pool_select",
                on_change=_on_pool_select_change,
            )
            current = ss.get("current_target_id") or ""
            if current not in targets:
                current = ""
            if current:
                if current in ss["pool_focus"]:
                    if st.button("👀 移回观察池", key="side_to_watch", width="stretch"):
                        ss["pool_focus"].remove(current)
                        if current not in ss["pool_watch"]:
                            ss["pool_watch"].append(current)
                        st.rerun()
                else:
                    if st.button("⭐ 加入重点跟踪池", key="side_to_focus", width="stretch"):
                        ss["pool_focus"].append(current)
                        if current in ss["pool_watch"]:
                            ss["pool_watch"].remove(current)
                        st.rerun()

        st.markdown("### 🎯 当前标的")
        target = _current_target()
        if target:
            with st.container(border=True):
                st.markdown(
                    f"**{html.escape(str(target.get('sec_name')))}** {_score_badge(target.get('score'))}",
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f"{_credibility_badge(str(target.get('credibility_level', 'L1')), target.get('credibility_label', ''))} "
                    f"{_risk_badge(bool(target.get('red_flag_triggered')))}",
                    unsafe_allow_html=True,
                )
                st.caption(f"业务环节：{_join(target.get('chain_links'))} ｜ 更新：{target.get('updated_at', '—')}")
                if target.get("risk_tags"):
                    st.caption("风险：" + "；".join(target["risk_tags"][:2]))
        else:
            st.info("尚未选择标的，请在上方标的池中选择。")

        st.markdown("### 🎚 筛选条件")
        st.selectbox("可信度筛选", ["全部", "L4", "L3", "L2", "L1"], key="filter_level")
        st.checkbox("仅看存在风险红旗的标的", key="filter_red_only")

        st.divider()
        _render_sidebar_scenarios()
        st.divider()
        _render_sidebar_history()

        st.divider()
        if st.button("📋生成标的研判简报", type="primary", width="stretch", key="brief_btn"):
            _generate_brief()
        if ss.get("brief_error"):
            st.error(ss["brief_error"])
        elif ss.get("brief"):
            st.caption("简报已生成，见主画布「📋 标的研判简报」。")

        st.divider()
        _render_debug_panel()
        st.caption(DISCLAIMER)


def _render_sidebar_scenarios() -> None:
    ss = st.session_state
    st.markdown("### 🎛 推演情景")
    names = list(ss["scenarios"].keys())
    active = ss.get("scenario_name") if ss.get("scenario_name") in names else names[0]
    picked = st.selectbox("切换情景", names, key="scenario_pick")
    if picked != active:
        ss["scenario_name"] = picked
        active = picked
    sc = ss["scenarios"][active]
    st.slider("需求增速（%）", 0, 60, int(sc["demand"]), key=f"sc_demand_{active}", on_change=_mark_shock_dirty)
    st.slider("碳酸锂价格波动（%）", -40, 40, int(sc["li_price"]), key=f"sc_price_{active}", on_change=_mark_shock_dirty)
    st.slider("政策力度（1–5）", 1, 5, int(sc["policy"]), key=f"sc_policy_{active}", on_change=_mark_shock_dirty)
    st.caption("参数修改后在「⚡ 冲击事件推演」提交；未提交即视为草稿。")

    with st.expander("➕ 新增情景"):
        new_name = st.text_input("情景名称", key="new_scenario_name", placeholder="如：极端压力")
        if st.button("创建并切换", key="add_scenario_btn", width="stretch"):
            name = (new_name or "").strip()
            if not name:
                st.warning("请填写情景名称。")
            elif name in ss["scenarios"]:
                st.warning("该情景已存在。")
            else:
                ss["scenarios"][name] = {"demand": 15, "li_price": -10, "policy": 3}
                ss["_pending_scenario"] = name
                ss["dirty"] = {**ss["dirty"], "shock": True}
                st.rerun()


def _render_sidebar_history() -> None:
    ss = st.session_state
    st.markdown("### 🕘 本次分析记录")
    if not ss["history"]:
        st.caption("暂无分析记录。")
        return
    for record in ss["history"][:5]:
        with st.expander(f"{record['time'][11:]} ｜ {record['tab']} ｜ {record['target']}"):
            st.markdown(f"**{record['title']}**")
            st.caption(record["summary"])


def _render_debug_panel() -> None:
    """评审/调试信息：默认收起，普通用户无需点开。"""
    ss = st.session_state
    with st.expander("🔍评审/调试信息（普通用户无需点开）"):
        target = _current_target()
        st.markdown("**模型与日志**")
        st.code(
            f"model={LLM_MODEL_NAME} / api={LLM_API_MODEL}\n"
            f"prompt_version={PROMPT_VERSION}\n"
            f"log={AUDIT_LOG_PATH}\n"
            f"review={REVIEW_CMD}",
            language=None,
        )
        st.warning("⚠️ 禁止手动编辑 jsonl 文件；请统一使用复核脚本。")

        if target:
            st.markdown("**当前标的证据编号**")
            evidence = list(dict.fromkeys(
                list(target.get("chain_link_evid_ids") or []) + list(target.get("evidence_ids") or [])
            ))
            st.code("\n".join(map(str, evidence)) if evidence else "无", language=None)

        st.markdown("**最近调用 trace_id（可检索 ai_records）**")
        traces = []
        for record in ss["history"]:
            if record.get("trace_id") and record["trace_id"] not in traces:
                traces.append(record["trace_id"])
        st.code("\n".join(traces) if traces else "暂无 LLM 调用记录", language=None)
        if traces:
            audit, filename = _load_audit_index().get(traces[0], (None, None))
            if audit:
                st.caption(
                    f"最近一次审计：`{filename}` ｜ 模型 `{audit.get('llm_model')}` ｜ "
                    f"状态 `{_status_text(audit.get('status'))}` ｜ "
                    f"evidence：{_join(audit.get('input_evidence_ids'))}"
                )

        st.markdown("**原始报错（最近 10 条）**")
        if ss["debug_errors"]:
            for error in ss["debug_errors"]:
                st.code(
                    f"[{error['time']}] {error['path']} status={error['status']}\n{error['detail']}",
                    language=None,
                )
        else:
            st.caption("无异常记录。")

        st.markdown("**最近一次接口原始返回**")
        if ss.get("debug_last_response"):
            payload = ss["debug_last_response"]
            st.caption(f"{payload['time']} ｜ {payload['path']}")
            st.json(payload["data"])
        else:
            st.caption("暂无。")

        st.markdown("**已知边界**")
        st.caption(
            "Mock 扶摇 / iFinD MCP；无真实向量库；R03 仅关键词占位冲突检测。"
        )


# ---------------------------------------------------------------- 顶部导航与切换保护


def _on_nav_change() -> None:
    ss = st.session_state
    selected = ss.get("nav_tab")
    committed = ss.get("active_tab", NAV_ITEMS[0])
    if not selected or selected == committed:
        return
    reason = _dirty_reason()
    if reason:
        ss["pending_tab"] = selected
        ss["pending_tab_msg"] = reason
        ss["nav_tab"] = committed
        return
    ss["active_tab"] = selected


def _render_nav() -> None:
    st.segmented_control(
        "研判范式",
        NAV_ITEMS,
        key="nav_tab",
        on_change=_on_nav_change,
        label_visibility="collapsed",
    )


def _render_pending_confirm() -> None:
    ss = st.session_state
    if not ss.get("pending_tab"):
        return
    st.warning(ss.get("pending_tab_msg") or DIRTY_MSG_SHOCK)
    col_ok, col_cancel, _ = st.columns([1, 1, 4])
    if col_ok.button("确认切换（放弃草稿）", type="primary", key="confirm_switch"):
        ss["_pending_drafts_reset"] = dict(ss["dirty"])
        ss["_pending_nav"] = ss["pending_tab"]
        ss["dirty"] = {"shock": False, "compare": False}
        ss["active_tab"] = ss["pending_tab"]
        ss["pending_tab"] = None
        ss["pending_tab_msg"] = ""
        st.rerun()
    if col_cancel.button("取消，留在当前范式", key="cancel_switch"):
        ss["pending_tab"] = None
        ss["pending_tab_msg"] = ""
        st.rerun()


def _context_banner() -> None:
    target = _current_target()
    if target:
        st.markdown(
            f"{_badge('当前标的', '#0969da', '#ddf4ff')} "
            f"**{html.escape(str(target.get('sec_name')))}**"
            f" {_credibility_badge(str(target.get('credibility_level', 'L1')), target.get('credibility_label', ''))}"
            f" {_score_badge(target.get('score'))}",
            unsafe_allow_html=True,
        )
    else:
        st.caption("当前未选择标的：可在左侧标的池选择，或在标的卡片上直接设为当前标的。")


def _filter_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    level = st.session_state.get("filter_level", "全部")
    red_only = st.session_state.get("filter_red_only", False)
    result = []
    for item in items:
        if level != "全部" and str(item.get("credibility_level")) != level:
            continue
        if red_only and not (item.get("red_flag_detail") or {}).get("red_flag_triggered"):
            continue
        result.append(item)
    return result


# ---------------------------------------------------------------- Tab1 产业链研判


def _chain_summary(item: Dict[str, Any]) -> str:
    links = _join(item.get("chain_links"))
    red = item.get("red_flag_detail") or {}
    risk = "存在风险红旗" if red.get("red_flag_triggered") else "暂无风险红旗"
    return (
        f"{item.get('credibility_level')}级可信（{item.get('credibility_label')}），"
        f"业务归属{links}，有效交叉印证 {item.get('cross_validate_count', 0)} 条，{risk}"
    )


def _render_company_card(item: Dict[str, Any], current_id: Optional[str]) -> None:
    tid = _tid(item)
    level = str(item.get("credibility_level", "L1"))
    red = item.get("red_flag_detail") or {}
    triggered = bool(red.get("red_flag_triggered"))

    with st.container(border=True):
        # 结论优先：一句话摘要 + 可信度 / 风险 badge
        st.markdown(
            f"#### {html.escape(str(item.get('sec_name', '未知标的')))} ｜ {_one_line(_chain_summary(item), 60)}",
            unsafe_allow_html=False,
        )
        st.markdown(
            f"{_credibility_badge(level, item.get('credibility_label', ''))} "
            f"{_risk_badge(triggered)} "
            f"{_rank_badge(item.get('sample_source_rank', '—'))} "
            + (_badge("🎯 当前标的", "#0969da", "#ddf4ff") if tid == current_id else ""),
            unsafe_allow_html=True,
        )
        st.caption(f"证券代码：{item.get('sec_code', '—')} ｜ 业务环节：{_join(item.get('chain_links'))}")

        if triggered:
            st.markdown("**⚠️ 风险提示**")
            descs = red.get("red_flag_desc") or []
            actions = red.get("red_action") or []
            for idx, desc in enumerate(descs):
                action = actions[idx] if idx < len(actions) else "建议人工复核"
                st.markdown(f"- {desc}；处置建议：{action}")

        with st.expander("📄查看完整原始证据与溯源信息"):
            st.markdown(f"> {item.get('sample_evidence_text', '—')}")
            st.caption(f"信源类型：{_source_label(item.get('sample_evidence_type'))}")
            chain_ids = item.get("chain_link_evid_ids") or []
            biz_ids = item.get("evidence_ids") or []
            st.markdown("**溯源编号**")
            st.code(
                "产业链：" + ("、".join(map(str, chain_ids)) if chain_ids else "无")
                + "\n业务可信度：" + ("、".join(map(str, biz_ids)) if biz_ids else "无"),
                language=None,
            )

        if tid != current_id:
            if st.button("🎯 设为当前标的", key=f"chain_pick_{tid}"):
                _set_current_target(tid)
                st.rerun()


def _render_chain_page() -> None:
    st.subheader("📊 产业链研判")
    st.caption(
        "使用指引：① 加载产业链数据集 → ② 按业务环节展开卡片 → ③ 选择标的带入全局上下文 → ④ 需要时下钻原始证据。"
    )
    _context_banner()
    st.info("D 级低可信信源仅作为线索，建议结合 A/B 等级证据交叉印证后再采信。")

    if st.button("📥 加载/刷新产业链标的", type="primary", key="chain_load"):
        with st.spinner("正在加载产业链数据…"):
            data, err, _ = _api_request(
                "GET", "/api/industry/chain", params={"industry": DEFAULT_INDUSTRY}, timeout=8
            )
        if data:
            _sync_chain_targets(data)
        st.session_state["chain_data"] = data
        st.session_state["chain_error"] = err
        st.rerun()

    err = st.session_state.get("chain_error")
    data = st.session_state.get("chain_data")
    if err:
        st.error(err)
    if not data:
        st.caption("点击上方按钮加载产业链标的。")
        return

    companies = _filter_items(data.get("company_list") or [])
    layers = data.get("chain_layers") or []
    if layers:
        st.caption("产业链分层：" + " → ".join(str(x) for x in layers))
    st.caption(f"筛选后共 {len(companies)} 个标的")

    current_id = st.session_state.get("current_target_id")
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for item in companies:
        links = item.get("chain_links") or []
        if not links:
            groups.setdefault("未归属环节", []).append(item)
        for link in links:
            groups.setdefault(str(link), []).append(item)

    if not groups:
        st.caption("当前筛选条件下暂无标的。")
        return

    for name, items in groups.items():
        with st.expander(f"📂 {name}（{len(items)} 个标的）"):
            for item in items:
                _render_company_card(item, current_id)


# ---------------------------------------------------------------- Tab2 中外对标分析


def _render_compare_page() -> None:
    ss = st.session_state
    st.subheader("🔍 中外对标分析")
    st.caption(
        "使用指引：① 确认当前标的 → ② 填写国内 / 海外对标对象 → ③ 执行推演 → ④ 先看一句话摘要，再按需展开完整推演与证据。"
    )
    _context_banner()

    target = _current_target()
    tid = target.get("sec_code") if target else None
    if ss.get("_compare_prefill_for") != tid:
        ss["compare_domestic"] = target.get("sec_name") if target else "阳光电源"
        ss["_compare_prefill_for"] = tid

    col_dom, col_ovs = st.columns(2)
    domestic = col_dom.text_input("国内标的名称", key="compare_domestic", on_change=_mark_compare_dirty)
    overseas = col_ovs.text_input("海外标的名称", key="compare_overseas", on_change=_mark_compare_dirty)
    user_id = st.text_input("分析人（默认评审账号）", key="compare_user_id", on_change=_mark_compare_dirty)

    if st.button(f"🚀 执行对标分析（{LLM_MODEL_NAME}）", type="primary", key="compare_run"):
        if not domestic.strip() or not overseas.strip():
            st.warning("请先填写国内标的与海外标的名称。")
        else:
            trace_id = str(uuid.uuid4())
            ss["compare_trace_id"] = trace_id
            symbol_list: List[str] = []
            if target:
                symbol_list.append(f"{target.get('sec_name')}({target.get('sec_code')})")
            for name in (domestic.strip(), overseas.strip()):
                if name not in symbol_list:
                    symbol_list.append(name)
            payload = {
                "request_trace_id": trace_id,
                "user_id": user_id.strip() or DEFAULT_USER_ID,
                "symbol_list": symbol_list,
                "enable_cross_compare": True,
                "enable_shock_analysis": False,
                "prompt_version": PROMPT_VERSION,
                "temperature": 0.1,
            }
            with st.spinner("正在生成对标推演，请稍候…"):
                data, err, status = _api_request(
                    "POST", "/api/llm/infer", json_body=payload, timeout=90
                )

            if err:
                err = err + "\n\n如需排查，可在侧边栏「🔍评审/调试信息」查看原始报错。"
                _add_history("中外对标分析", trace_id, "对标分析未完成", err[:120])
            if data:
                ctrl = data.get("cross_region_ctrl") or {}
                report = str(data.get("natural_report") or "")
                evidence_ids = [
                    ev.get("source_id")
                    for conf in (data.get("confidence_results") or [])
                    for ev in (conf.get("evidence_list") or [])
                ]
                _record_conclusion("compare", {
                    "summary": _one_line(report, 140),
                    "tags": [
                        "已完成中外对标",
                        f"可比维度:{_join(ctrl.get('comparable_dim'))}",
                        f"不可比维度:{_join(ctrl.get('incomparable_dim'))}",
                    ],
                    "evidence_ids": evidence_ids,
                    "source_type": "LLM 推演结论（DeepSeek-V3）",
                    "trace_id": trace_id,
                    "time": _now_str(),
                    "hit_block": bool(data.get("hit_block")),
                })
                _add_history(
                    "中外对标分析",
                    trace_id,
                    f"{domestic.strip()} vs {overseas.strip()} 对标完成",
                    f"可比：{_join(ctrl.get('comparable_dim'))}；不可比：{_join(ctrl.get('incomparable_dim'))}",
                )
                ss["dirty"] = {**ss["dirty"], "compare": False}

            ss["compare_result"] = data
            ss["compare_error"] = err
            st.rerun()

    err = ss.get("compare_error")
    data = ss.get("compare_result")
    if err:
        st.error(err)
    if not data:
        st.caption("填写标的名称后点击按钮执行对标分析。")
        return

    ctrl = data.get("cross_region_ctrl") or {}
    report = str(data.get("natural_report") or "")
    target_level = (target or {}).get("credibility_level", "L1")
    target_label = (target or {}).get("credibility_label", "")

    st.divider()
    # 结论优先
    st.markdown(f"#### 📌 一句话结论：{_one_line(report, 80)}")
    st.markdown(
        f"{_credibility_badge(str(target_level), target_label)} "
        + (_badge("⚠️ 对标结论已阻断", "#cf222e", "#ffebe9") if data.get("hit_block") else _badge("✅ 对标结论未阻断", "#1a7f37", "#e6f4ea")),
        unsafe_allow_html=True,
    )

    st.markdown("**核心指标**")
    col_a, col_b = st.columns(2)
    col_a.markdown("**✅ 可比维度**\n" + "\n".join(f"- {d}" for d in (ctrl.get("comparable_dim") or ["无"])))
    col_b.markdown("**🚫 不可比维度**\n" + "\n".join(f"- {d}" for d in (ctrl.get("incomparable_dim") or ["无"])))
    st.caption(
        f"对比开关：{'已开启' if ctrl.get('cross_region_compare_switch') else '已关闭'} ｜ "
        f"政策生效时间：{_fmt_ts(ctrl.get('policy_effect_ts'))}"
        + (f" ｜ 阻断原因：{ctrl.get('block_reason')}" if ctrl.get("block_reason") else "")
    )

    with st.expander("📄查看完整推演原文"):
        st.text_area(
            "完整推演原文（只读）",
            value=report or "（未返回推演文本）",
            height=320,
            disabled=True,
            key=f"llm_report_{ss.get('compare_trace_id')}",
        )

    with st.expander("📄查看证据与溯源信息"):
        confidence_results = data.get("confidence_results") or []
        evidence_ids = [
            ev.get("source_id")
            for conf in confidence_results
            for ev in (conf.get("evidence_list") or [])
        ]
        st.markdown("**信源类型**：LLM 推演结论，证据来自扶摇 / iFinD MCP 模拟数据")
        st.markdown("**溯源编号**")
        if evidence_ids:
            st.code("\n".join(map(str, evidence_ids)), language=None)
        else:
            st.caption("本次结果未携带结构化溯源编号，可在侧边栏调试面板按记录检索审计日志。")


# ---------------------------------------------------------------- Tab3 冲击事件推演


def _render_shock_card(item: Dict[str, Any]) -> None:
    rank = str(item.get("event_source_rank", "—")).upper()
    conf = str(item.get("transmission_confidence", "—"))
    direction = str(item.get("impact_direction", "—"))
    precondition = str(item.get("transmission_precondition") or "—")
    event_name = str(item.get("event_name", "未知事件"))
    affected = _join(item.get("affected_chain_links"))
    summary = f"{event_name}对{affected}呈{direction}影响，传导置信度{conf}"

    with st.container(border=True):
        # 结论优先：一句话摘要
        st.markdown(f"#### 📌 {_one_line(summary, 80)}")
        st.markdown(
            f"{_rank_badge(rank)} {_confidence_badge(conf)} {_direction_badge(direction)}",
            unsafe_allow_html=True,
        )

        st.markdown(
            '<div style="background:#fff8c5;border-left:4px solid #d4a72c;'
            'padding:8px 12px;border-radius:4px;margin:8px 0 10px 0;">'
            "<b>⚠️ 传导生效前置条件</b><br>"
            f"{html.escape(precondition)}</div>",
            unsafe_allow_html=True,
        )

        st.markdown(f"**事件类型**：{_join(item.get('event_type'))}")
        st.markdown(f"**受影响业务环节**：{_join(item.get('affected_chain_links'))}")
        st.markdown(f"**业务影响**：{item.get('business_impact', '—')}")
        st.markdown(f"**关联财务指标**：{_join(item.get('related_fin_index'))}")

        with st.expander("📄查看完整原始数据与溯源信息"):
            st.caption(f"信源等级：{rank} 级 ｜ 信源说明：{item.get('event_source_desc', '—')}")
            st.caption(f"事件编号：{item.get('event_id', '—')} ｜ 数据来源：冲击事件库（MCP 模拟）")


def _render_shock_page() -> None:
    ss = st.session_state
    st.subheader("⚡ 冲击事件推演")
    st.caption(
        "使用指引：① 在侧边栏确认情景参数 → ② 选择冲击事件 → ③ 执行推演 → ④ 重点看前置条件与风险方向。"
    )
    _context_banner()

    scenario = ss.get("scenario_name", "基准")
    params = _scenario_params(scenario)
    st.markdown(
        f"**当前情景**：{_badge(scenario, '#0969da', '#ddf4ff')} ｜ "
        f"需求增速 {params['demand']}% ｜ 碳酸锂价格波动 {params['li_price']}% ｜ 政策力度 {params['policy']}",
        unsafe_allow_html=True,
    )

    event_id = st.selectbox("选择冲击事件", EVENT_OPTIONS, key="shock_event", on_change=_mark_shock_dirty)
    if st.button("⚡ 执行外部冲击传导推演", type="primary", key="shock_run"):
        with st.spinner("正在推演传导路径，请稍候…"):
            data, err, _ = _api_request(
                "GET", "/api/shock/transmission", params={"event_id": event_id}, timeout=8
            )
        if data:
            _record_conclusion("shock", {
                "summary": (
                    f"{data.get('event_name')}：{data.get('impact_direction')}影响；"
                    f"传导置信度 {data.get('transmission_confidence')}；"
                    f"前置条件 {data.get('transmission_precondition')}"
                )[:160],
                "tags": [
                    f"冲击:{data.get('event_id')}",
                    f"影响方向:{data.get('impact_direction')}",
                    f"传导置信度:{data.get('transmission_confidence')}",
                ],
                "confidence": data.get("transmission_confidence"),
                "direction": data.get("impact_direction"),
                "evidence_ids": [],
                "source_type": "冲击事件库（MCP 模拟）",
                "trace_id": None,
                "time": _now_str(),
            })
            _add_history(
                "冲击事件推演",
                None,
                f"{data.get('event_name')} 推演完成（情景：{scenario}）",
                f"{data.get('impact_direction')}；置信度 {data.get('transmission_confidence')}",
            )
            ss["dirty"] = {**ss["dirty"], "shock": False}
        ss["shock_result"] = data
        ss["shock_error"] = err
        st.rerun()

    err = ss.get("shock_error")
    data = ss.get("shock_result")
    if err:
        st.error(err)
    if not data:
        st.caption("选择事件后点击按钮执行推演。")
        return

    _render_shock_card(data)


# ---------------------------------------------------------------- Tab4 标的汇总看板


def _target_summary(profile: Dict[str, Any]) -> str:
    shock = (profile.get("conclusions") or {}).get("shock") or {}
    if shock:
        return f"最近冲击推演：{_one_line(shock.get('summary'), 60)}"
    return f"业务归属{_join(profile.get('chain_links'))}，{profile.get('credibility_level')}级可信度"


def _render_target_card(profile: Dict[str, Any]) -> None:
    tid = str(profile.get("sec_code"))
    with st.container(border=True):
        st.markdown(
            f"#### {html.escape(str(profile.get('sec_name')))} {_score_badge(profile.get('score'))}",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"{_credibility_badge(str(profile.get('credibility_level', 'L1')), profile.get('credibility_label', ''))} "
            f"{_risk_badge(bool(profile.get('red_flag_triggered')))} "
            + (_badge("⭐ 重点跟踪", "#9a6700", "#fff8c5") if tid in st.session_state["pool_focus"] else ""),
            unsafe_allow_html=True,
        )
        st.caption(_one_line(_target_summary(profile), 70))
        if profile.get("risk_tags"):
            st.caption("风险：" + "；".join(profile["risk_tags"][:2]))
        st.caption(f"更新：{profile.get('updated_at', '—')}")

        with st.expander("📄查看该标的全部研判记录与证据"):
            for key, label in (("chain", "产业链"), ("compare", "中外对标"), ("shock", "冲击推演"), ("brief", "研判简报")):
                payload = (profile.get("conclusions") or {}).get(key)
                if not payload:
                    continue
                st.markdown(f"**{label}**：{payload.get('summary', '—')}")
                if payload.get("tags"):
                    st.caption("标签：" + " ｜ ".join(map(str, payload["tags"])))
                if payload.get("evidence_ids"):
                    st.code("\n".join(map(str, payload["evidence_ids"])), language=None)

        col_pick, col_pool = st.columns(2)
        if col_pick.button("🎯 设为当前标的", key=f"pool_pick_btn_{tid}"):
            _set_current_target(tid)
            st.rerun()
        if tid in st.session_state["pool_focus"]:
            if col_pool.button("👀 移回观察池", key=f"pool_watch_btn_{tid}"):
                st.session_state["pool_focus"].remove(tid)
                if tid not in st.session_state["pool_watch"]:
                    st.session_state["pool_watch"].append(tid)
                st.rerun()
        else:
            if col_pool.button("⭐ 加入重点跟踪池", key=f"pool_focus_btn_{tid}"):
                st.session_state["pool_focus"].append(tid)
                if tid in st.session_state["pool_watch"]:
                    st.session_state["pool_watch"].remove(tid)
                st.rerun()


def _render_pool_page() -> None:
    ss = st.session_state
    st.subheader("🗂 标的汇总看板")
    st.caption(
        "使用指引：① 浏览全部跟踪标的的结论与风险 → ② 点击卡片设为当前标的 → ③ 在侧边栏生成标的研判简报。"
    )

    if st.button("🔄 同步产业链标的", key="pool_sync"):
        with st.spinner("正在同步标的池…"):
            data, err, _ = _api_request(
                "GET", "/api/industry/chain", params={"industry": DEFAULT_INDUSTRY}, timeout=8
            )
        if data:
            _sync_chain_targets(data)
            ss["chain_data"] = data
            ss["chain_error"] = None
        else:
            ss["chain_error"] = err
        st.rerun()

    targets = ss["targets"]
    if not targets:
        st.info("标的池为空。请点击「🔄 同步产业链标的」或在产业链研判页加载数据集。")
        return

    focus = [t for t in ss["pool_focus"] if t in targets]
    watch = [t for t in ss["pool_watch"] if t in targets and t not in focus]
    red_count = sum(1 for p in targets.values() if p.get("red_flag_triggered"))
    col_a, col_b, col_c, col_d = st.columns(4)
    col_a.metric("标的总数", len(targets))
    col_b.metric("观察池", len(watch))
    col_c.metric("重点跟踪池", len(focus))
    col_d.metric("风险红旗标的", red_count)

    view = st.segmented_control(
        "池分类",
        ["全部标的", "👀 观察池", "⭐ 重点跟踪池"],
        key="pool_view",
        label_visibility="collapsed",
    ) or "全部标的"

    if view == "👀 观察池":
        tids = watch
    elif view == "⭐ 重点跟踪池":
        tids = focus
    else:
        tids = focus + watch

    st.markdown(f"**{view}**（{len(tids)} 个标的）")
    if not tids:
        st.caption("该分类下暂无标的，可将标的加入重点跟踪池。")
        return

    cols = st.columns(2)
    for idx, tid in enumerate(tids):
        profile = targets.get(tid)
        if not profile:
            continue
        level = st.session_state.get("filter_level", "全部")
        if level != "全部" and str(profile.get("credibility_level")) != level:
            continue
        if st.session_state.get("filter_red_only") and not profile.get("red_flag_triggered"):
            continue
        with cols[idx % 2]:
            _render_target_card(profile)


# ---------------------------------------------------------------- 标的研判简报


def _generate_brief() -> None:
    ss = st.session_state
    target = _current_target()
    ss["brief_error"] = None
    if not target:
        ss["brief_error"] = "请先在左侧标的池选择当前标的，再生成研判简报。"
        return

    conclusions = target.get("conclusions") or {}
    context_lines: List[str] = []
    for key, label in (("chain", "产业链"), ("compare", "中外对标"), ("shock", "冲击推演")):
        payload = conclusions.get(key)
        if not payload:
            context_lines.append(f"【{label}】暂无结论")
            continue
        context_lines.append(
            f"【{label}】结论：{str(payload.get('summary', ''))[:90]}；"
            f"标签：{_join(payload.get('tags'))[:60]}"
        )

    trace_id = str(uuid.uuid4())
    symbol_list = [
        f"{target.get('sec_name')}({target.get('sec_code')})",
        f"当前可信度：{target.get('credibility_level')} · {target.get('credibility_label')}",
        f"风险标签：{_join(target.get('risk_tags'))}",
        *context_lines,
        "请汇总以上三大研判模块输出一份精简研判简报：核心结论、可信度、风险提示",
    ]
    payload = {
        "request_trace_id": trace_id,
        "user_id": DEFAULT_USER_ID,
        "symbol_list": symbol_list,
        "enable_cross_compare": True,
        "enable_shock_analysis": True,
        "prompt_version": PROMPT_VERSION,
        "temperature": 0.1,
    }
    with st.spinner("正在汇总生成研判简报…"):
        data, err, _ = _api_request("POST", "/api/llm/infer", json_body=payload, timeout=90)

    if err:
        ss["brief_error"] = err
        ss["brief"] = None
        _add_history("研判简报", trace_id, "简报生成未完成", err[:120])
        return

    report = str((data or {}).get("natural_report") or "")
    modules = []
    for key in ("chain", "compare", "shock"):
        item = conclusions.get(key)
        if item:
            modules.append({
                "module": key,
                "summary": item.get("summary", ""),
                "tags": item.get("tags") or [],
                "evidence_ids": item.get("evidence_ids") or [],
                "source_type": item.get("source_type", "—"),
            })
    _record_conclusion("brief", {
        "summary": _one_line(report, 160),
        "tags": ["三模块汇总", f"简报生成:{_now_str()}"],
        "evidence_ids": list(dict.fromkeys(
            [eid for m in modules for eid in (m.get("evidence_ids") or [])]
        )),
        "source_type": "LLM 汇总（DeepSeek-V3）",
        "trace_id": trace_id,
        "time": _now_str(),
    })
    ss["brief"] = {
        "target_id": target.get("sec_code"),
        "target_name": target.get("sec_name"),
        "credibility_level": target.get("credibility_level"),
        "credibility_label": target.get("credibility_label"),
        "score": target.get("score"),
        "report": report,
        "trace_id": trace_id,
        "modules": modules,
        "time": _now_str(),
    }
    _add_history(
        "研判简报",
        trace_id,
        f"{target.get('sec_name')} 研判简报已生成",
        f"覆盖 {len(modules)} 个模块",
    )


def _render_brief_panel() -> None:
    ss = st.session_state
    brief = ss.get("brief")
    if not brief:
        if ss.get("brief_error"):
            st.error(ss["brief_error"])
        return
    current = _current_target()
    if not current or brief.get("target_id") != current.get("sec_code"):
        return
    st.divider()
    with st.container(border=True):
        st.markdown(
            f"#### 📋 标的研判简报 ｜ {brief.get('target_name')} "
            f"{_credibility_badge(str(brief.get('credibility_level', 'L1')), brief.get('credibility_label', ''))} "
            f"{_score_badge(brief.get('score'))}",
            unsafe_allow_html=True,
        )
        st.caption(f"生成时间：{brief.get('time')}")
        st.markdown(f"**一句话摘要**：{_one_line(brief.get('report'), 100)}")
        st.caption("一键复制（点击代码块右上角复制图标）：")
        st.code(brief.get("report", ""), language=None)
        with st.expander("📄查看简报引用的模块证据"):
            for module in brief.get("modules") or []:
                st.markdown(f"**{module.get('module')}**：{module.get('summary') or '—'}")
                if module.get("tags"):
                    st.caption("标签：" + " ｜ ".join(map(str, module["tags"])))
                if module.get("evidence_ids"):
                    st.code("\n".join(map(str, module["evidence_ids"])), language=None)


# ---------------------------------------------------------------- 页面骨架


def main() -> None:
    st.set_page_config(
        page_title="电化学储能AI研究｜笔试Demo",
        page_icon="🔋",
        layout="wide",
    )
    _init_state()
    _apply_pending_actions()
    _render_sidebar()

    st.title("🔋 电化学储能AI研究｜笔试Demo")
    st.caption("结论优先 · 证据可下钻 · 全链路可审计")
    st.warning(DISCLAIMER)

    _render_nav()
    _render_pending_confirm()

    active = st.session_state["active_tab"]
    if active == NAV_CHAIN:
        _render_chain_page()
    elif active == NAV_COMPARE:
        _render_compare_page()
    elif active == NAV_SHOCK:
        _render_shock_page()
    elif active == NAV_POOL:
        _render_pool_page()

    _render_brief_panel()

    st.divider()
    st.caption(DISCLAIMER)


if __name__ == "__main__":
    main()
