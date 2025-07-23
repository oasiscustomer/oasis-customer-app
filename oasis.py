# -*- coding: utf-8 -*-
"""oasis.py - 최종 완성본 (모바일 UI/UX 개선 + 마지막 방문일자 표시 추가)"""

import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import pytz
import time

# --- 기본 설정 및 데이터 로딩 ---
st.set_page_config(layout="centered")

now = datetime.now(pytz.timezone("Asia/Seoul"))
today = now.strftime("%Y-%m-%d")
now_str = now.strftime("%Y-%m-%d %H:%M")

@st.cache_resource
def get_gspread_client():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    credentials = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    return gspread.authorize(credentials)

@st.cache_data(ttl=60)
def load_data(_client):
    with st.spinner("🔄 데이터를 새로 보내오는 중..."):
        worksheet = _client.open("Oasis Customer Management").sheet1
        return worksheet.get_all_records()

client = get_gspread_client()
worksheet = client.open("Oasis Customer Management").sheet1
all_records = load_data(client)

특정정안제옵션 = ["기본(정안제)", "중급(정안제)", "고급(정안제)"]
회수제옵션 = ["일반 5회권", "중급 5회권", "고급 5회권", "일반 10회권", "중급 10회권", "고급 10회권", "고급 1회권"]

def get_customer(plate, records):
    customer = next((r for r in records if r.get("차량번호") == plate), None)
    row_idx = next((i + 2 for i, r in enumerate(records) if r.get("차량번호") == plate), None)
    return customer, row_idx

def clear_all_cache():
    st.cache_data.clear()
    st.cache_resource.clear()

# --- 세션 상태 초기화 ---
for key in ["registration_success", "registering", "reset_form", "matched_plate"]:
    if key not in st.session_state:
        st.session_state[key] = False

# --- UI 시작 ---
st.markdown("<h3 style='text-align: center; font-weight:bold;'>🚘 오아시스 고객 관리</h3>", unsafe_allow_html=True)

with st.form("search_form"):
    search_input = st.text_input("🔍 차량 번호 (전체 또는 끝 4자리)", key="search_input")
    submitted = st.form_submit_button("검색")

if submitted and search_input.strip():
    matched = [r for r in all_records if search_input.strip() in str(r.get("차량번호", ""))]
    if not matched:
        st.info("🚫 등록되지 않은 차량입니다.")
    else:
        options = {}
        for r in matched:
            plate = r.get("차량번호")
            jung = r.get("상품 옵션(정액제)", "없음") or "없음"
            hue = r.get("상품 옵션(회수제)", "없음") or "없음"
            label = f"{plate} → 정안제: {jung} / 회수제: {hue}"
            options[label] = plate
        st.session_state.matched_options = options
        st.session_state.matched_plate = list(options.values())[0]

if st.session_state.get("matched_plate"):
    plate = st.session_state["matched_plate"]
    label_options = list(st.session_state.matched_options.keys())
    value_options = list(st.session_state.matched_options.values())
    selected = st.selectbox("📋 검색된 고객 선택", label_options, index=value_options.index(plate))
    st.session_state.matched_plate = st.session_state.matched_options[selected]

    customer, row_idx = get_customer(st.session_state.matched_plate, all_records)

    if customer and row_idx:
        st.markdown("---")
        st.markdown(f"#### 🚘 **선택된 차량:** {plate}")

        is_blacklist = str(customer.get("블랙리스트", "")).strip().upper() == "Y"
        if is_blacklist:
            st.error("🚨 **블랙리스트 회원**")

        # ✅ 마지막 방문일자 표시
        last_visit = customer.get("최종 방문일", "")
        if last_visit:
            st.info(f"📅 마지막 방문일: `{last_visit}`")

        # --- 변수 정리 ---
        상품정액 = customer.get("상품 옵션(정액제)", "")
        상품회수 = customer.get("상품 옵션(회수제)", "")
        방문기록 = customer.get("방문기록", "")
        만료일 = customer.get("회원 만료일", "")
        남은횟수 = int(customer.get("남은 이용 횟수", 0)) if str(customer.get("남은 이용 횟수")).isdigit() else 0
        
        days_left = -999
        if 상품정액 and 만료일 not in [None, "", "None", "none"]:
            try:
                expire_date = datetime.strptime(만료일, "%Y-%m-%d").date()
                days_left = (expire_date - now.date()).days
                if str(customer.get("남은 이용 일수")) != str(max(0, days_left)):
                    worksheet.update_cell(row_idx, 7, str(max(0, days_left)))
            except: pass

        # --- ✨ UI 개선: st.metric과 st.columns로 정보 카드 디자인 ---
        col1, col2 = st.columns(2)
        with col1:
            if 상품정액:
                value = f"{days_left}일" if days_left >= 0 else "만료"
                st.metric(label="정액제 상태", value=value, delta=f"만료일: {만료일}", delta_color="off")
            else:
                st.metric(label="정액제 상태", value="없음")
        with col2:
            if 상품회수:
                st.metric(label="회수권 잔여", value=f"{남은횟수}회")
            else:
                st.metric(label="회수권 상태", value="없음")

        st.markdown("---")
        
        # --- ✨ UI 개선: 핵심 기능과 부가 기능 분리 ---
        st.subheader("✅ 방문 기록 추가")
        
        visit_options = []
        if 상품정액 and days_left >= 0: visit_options.append("정액제")
        if 상품회수 and 남은횟수 > 0: visit_options.append("회수제")

        if visit_options:
            사용옵션 = st.radio("사용할 이용권을 선택하세요.", visit_options, horizontal=True)
            if st.button(f"**{사용옵션}**으로 오늘 방문 기록하기"):
                log_type = 사용옵션
                if log_type == "회수제":
                    worksheet.update_cell(row_idx, 9, str(남은횟수 - 1))
                
                count = int(customer.get("총 방문 횟수", 0)) + 1
                new_log = f"{방문기록}, {now_str} ({log_type})" if 방문기록 else f"{now_str} ({log_type})"
                worksheet.update_cell(row_idx, 4, today)
                worksheet.update_cell(row_idx, 5, str(count))
                worksheet.update_cell(row_idx, 12, new_log)
                st.success(f"✅ {log_type} 방문 기록 완료")
                clear_all_cache()
                time.sleep(1)
                st.rerun()
        else:
            st.warning("사용 가능한 이용권이 없습니다.")

        # ✨ UI 개선: 부가 기능을 접이식 Expander로 정리
        with st.expander("갱신 및 충전 (만료/소진 시)"):
            if 상품정액 and days_left < 0:
                st.warning("⛔ 정액제가 만료되었습니다.")
                sel = st.selectbox("정액제 재등록", 정액제옵션, key="재정액")
                if st.button("📅 정액제 갱신하기"):
                    expire = now + timedelta(days=30)
                    worksheet.update_cell(row_idx, 6, sel)
                    worksheet.update_cell(row_idx, 7, "30")
                    worksheet.update_cell(row_idx, 10, expire.strftime("%Y-%m-%d"))
                    st.success("✅ 재등록 완료")
                    clear_all_cache()
                    st.rerun()
            
            if 상품회수 and 남은횟수 <= 0:
                st.warning("⛔ 회수권이 모두 소진되었습니다.")
                sel = st.selectbox("회수권 충전", 회수제옵션, key="재회수")
                if st.button("🔁 회수권 충전하기"):
                    cnt = 1 if "1회" in sel else (5 if "5회" in sel else 10)
                    worksheet.update_cell(row_idx, 9, str(cnt))
                    worksheet.update_cell(row_idx, 8, sel)
                    st.success("✅ 회수권 충전 완료")
                    clear_all_cache()
                    st.rerun()

        with st.expander("기존 고객에게 새 상품 추가"):
            with st.form("add_product_form"):
                add_jung = st.selectbox("정액제 추가 등록", ["선택 안함"] + 정액제옵션)
                add_hue = st.selectbox("회수제 추가 등록", ["선택 안함"] + 회수제옵션)
                sub = st.form_submit_button("등록")
                if sub:
                    updated = False
                    if add_jung != "선택 안함":
                        expire = now + timedelta(days=30)
                        worksheet.update_cell(row_idx, 6, add_jung)
                        worksheet.update_cell(row_idx, 7, "30")
                        worksheet.update_cell(row_idx, 10, expire.strftime("%Y-%m-%d"))
                        st.success("✅ 정액제 추가 등록 완료")
                        updated = True
                    if add_hue != "선택 안함":
                        cnt = 1 if "1회" in add_hue else (5 if "5회" in add_hue else 10)
                        worksheet.update_cell(row_idx, 9, str(cnt))
                        worksheet.update_cell(row_idx, 8, add_hue)
                        st.success("✅ 회수제 추가 등록 완료")
                        updated = True
                    if updated:
                        clear_all_cache()
                        st.rerun()

# --- 신규 등록 섹션 ---
st.markdown("---")
st.subheader("🆕 신규 고객 등록")

with st.form("register_form"):
    np = st.text_input("🚘 차량번호")
    ph = st.text_input("📞 전화번호")
    pj = st.selectbox("정액제 상품", ["선택 안함"] + 정액제옵션)
    phs = st.selectbox("회수제 상품", ["선택 안함"] + 회수제옵션)

    reg = st.form_submit_button("신규 고객으로 등록하기")

    if reg and np and ph:
        exists = any(r.get("차량번호") == np for r in all_records)
        if exists:
            st.warning("🚨 이미 등록된 고객입니다.")
        else:
            phone = ph.replace("-", "").strip()
            jung_day = "30" if pj != "선택 안함" else ""
            expire = (now + timedelta(days=30)).strftime("%Y-%m-%d") if pj != "선택 안함" else ""
            cnt = ""
            if phs != "선택 안함":
                cnt = 1 if "1회" in phs else (5 if "5회" in phs else 10)
            
            new_row = [np, phone, today, today, 1, pj if pj != "선택 안함" else "", jung_day, phs if phs != "선택 안함" else "", cnt, expire, "", f"{now_str} (신규등록)"]
            
            worksheet.append_row(new_row)
            st.success("✅ 등록이 완료되었습니다! 2초 후 앱이 새로고침 됩니다.")
            clear_all_cache()
            time.sleep(2)
            st.rerun()
