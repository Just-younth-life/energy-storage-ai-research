import streamlit as st
import requests

BASE_URL = "http://127.0.0.1:8000"
st.set_page_config(page_title="储能产业链AI研究Demo")
st.markdown("> **本产品为笔试Demo，全部为Mock模拟数据，不构成任何投资建议**")

tab1, tab2, tab3 = st.tabs(["产业链查询","中外公司对比","冲击传导推演"])

with tab1:
    st.header("电化学储能产业链查询（双层可信度｜证据溯源）")
    if st.button("加载产业链"):
        try:
            resp = requests.get(f"{BASE_URL}/api/industry/chain",params={"industry":"电化学储能"},timeout=8)
            data = resp.json()
            st.info(data["notice"])
            st.subheader("产业链分层")
            st.write(data["chain_layers"])
            st.subheader("标的列表")
            for comp in data["company_list"]:
                rf_obj = comp["red_flag_detail"]
                rf_text = "⚠️红旗预警："+";".join(rf_obj["red_flag_desc"])+"｜处置："+";".join(rf_obj["red_action"]) if rf_obj["red_flag_triggered"] else "无红旗预警"
                st.markdown(f"""
**{comp['sec_name']} | {comp['credibility_level']}‑{comp['credibility_label']} | 信源:{comp['sample_source_rank']}｜证据类型:{comp['sample_evidence_type']}｜{rf_text}**
有效交叉印证计数：{comp['cross_validate_count']}
产业链归属溯源ID：{comp['chain_link_evid_ids']}
业务可信度证据ID：{comp['evidence_ids']}
> 证据片段：{comp['sample_evidence_text']}
""")
        except Exception as e:
            st.error(f"接口请求异常：{str(e)}")

with tab2:
    st.header("中外公司对比（结论绑定证据ID溯源）")
    d_name = st.text_input("国内公司","阳光电源")
    o_name = st.text_input("海外公司","Fluence")
    if st.button("开始对比"):
        st.warning("提示：本Demo中外对比接口为LLMInfer演示入口，可自行扩展POST参数调用")

with tab3:
    st.header("冲击传导推演（置信度+前置生效条件）")
    eid = st.selectbox("选择冲击事件",["event‑001","event‑002","event‑003"])
    if st.button("推演传导路径"):
        try:
            resp = requests.get(f"{BASE_URL}/api/shock/transmission",params={"event_id":eid},timeout=8)
            st.json(resp.json())
        except Exception as e:
            st.error(f"请求异常：{str(e)}")

