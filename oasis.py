# -*- coding: utf-8 -*-
"""oasis.py - 속도 최적화 및 안정성 강화 최종 버전"""

import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import pytz
import time

# ✅ 시간 및 인증 설정
now = datetime.now(pytz.timezone("Asia/Seoul"))
today = now.strftime("%Y-%m-%d")
now_str = now.strftime("%Y-%m-%d %H:%M")
scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
client = gspread.authorize(credentials)
worksheet = client.open("Oasis Customer Management").sheet1

# --- ✨ 속도 최적화: 앱 실행 시 데이터를 한번만 불러오기 ---
@st.cache_data(ttl=60) # 60초 동안 데이터 캐싱하여 불필요한 API 호출 방지
def load_data():
    return worksheet.get_all_records()

all_records = load_data()
# ----------------------------------------------------

정액제옵션 = ["기본(정액제)", "중급(정액제)", "고급(정액제)"]
회수제옵션 = ["일반 5회권", "중급 5회권", "고급 5회권", "일반 10회권", "중급 10회권", "고급 10회권", "고급 1회권"]

def format_phone_number(phone: str) -> str:
    phone = phone.replace("-", "").strip()
    if len(phone) == 11 and phone.startswith("010"):
        return f"{phone[:3]}-{phone[3:7]}-{phone[7:]}"
    elif len(phone) == 10:
        return f"{phone[:3]}-{phone[3:6]}-{phone[6:]}"
    return phone

# --- ✨ 속도 최적화: 불러온 데이터를 인자로 받아 사용 ---
def get_customer(plate, records):
    customer = next((r for r in records if r.get("차량번호") == plate), None)
    row_idx = next((i + 2 for i, r in enumerate(records) if r.get("차량번호") == plate), None)
    return customer, row_idx
# --------------------------------------------------

# ✅ 세션 상태 초기화
for key in ["registration_success", "registering", "reset_form", "matched_plate"]:
    if key not in st.session_state:
        st.session_state[key] = False

# ✅ UI 시작
st.markdown("<h1 style='text-align: center;'>🚘 오아시스 고객 관리 시스템</h1>", unsafe_allow_html=True)

with st.form("search_form"):
    search_input = st.text_input("🔍 차량 번호 (전체 또는 끝 4자리)", key="search_input")
    submitted = st.form_submit_button("검색")

if submitted and search_input.strip():
    # --- ✨ 속도 최적화: 미리 불러온 all_records 사용 ---
    matched = [r for r in all_records if search_input.strip() in str(r.get("차량번호", ""))]
    # ------------------------------------------------
    if not matched:
        st.info("🚫 등록되지 않은 차량입니다.")
    else:
        options = {}
        for r in matched:
            plate = r.get("차량번호")
            jung = r.get("상품 옵션(정액제)", "")
            hue = r.get("상품 옵션(회수제)", "")
            jung_remain = r.get("남은 이용 일수", "")
            hue_remain = r.get("남은 이용 횟수", "")
            
            is_blacklist = str(r.get("블랙리스트", "")).upper() == "Y"
            blacklist_label = "블랙리스트 회원" if is_blacklist else ""
            
            label = f"{plate} → {jung} {jung_remain}일 / {hue} {hue_remain}회 {blacklist_label}"
            options[label] = plate
            
        st.session_state.matched_options = options
        st.session_state.matched_plate = list(options.values())[0]

if st.session_state.get("matched_plate"):
    plate = st.session_state["matched_plate"]
    label_options = list(st.session_state.matched_options.keys())
    value_options = list(st.session_state.matched_options.values())
    selected = st.selectbox("📋 고객 선택", label_options, index=value_options.index(plate))
    st.session_state.matched_plate = st.session_state.matched_options[selected]

    # --- ✨ 속도 최적화: 미리 불러온 all_records 사용 ---
    customer, row_idx = get_customer(st.session_state.matched_plate, all_records)
    # ------------------------------------------------
    
    if customer and row_idx:
        st.markdown(f"### 🚘 선택된 차량: {plate}")
        
        상품정액 = customer.get("상품 옵션(정액제)", "")
        상품회수 = customer.get("상품 옵션(회수제)", "")
        방문기록 = customer.get("방문기록", "")
        만료일 = customer.get("회원 만료일", "")

        if 상품정액 and 만료일 not in [None, "", "None", "none"]:
            try:
                expire_date = datetime.strptime(만료일, "%Y-%m-%d").date()
                remain = max((expire_date - now.date()).days, 0)
                if str(customer.get("남은 이용 일수")) != str(remain):
                    worksheet.update_cell(row_idx, 7, str(remain))
            except:
                st.warning("⚠️ 남은 이용 일수 자동 계산 실패")

        try:
            남은일수 = int(customer.get("남은 이용 일수", 0))
        except:
            남은일수 = 0
        try:
            남은횟수 = int(customer.get("남은 이용 횟수", 0))
        except:
            남은횟수 = 0

        days_left = -999
        if 상품정액:
            try:
                if 만료일 and 만료일.lower() != "none":
                    exp = datetime.strptime(만료일, "%Y-%m-%d").date()
                    days_left = (exp - now.date()).days
            except:
                pass

        사용옵션 = st.radio("사용할 이용권을 선택하세요", ["정액제", "회수제"])

        if st.button("✅ 오늘 방문 기록 추가"):
            log_type = None
            if 사용옵션 == "정액제" and 상품정액 and days_left > 0:
                log_type = "정액제"
            elif 사용옵션 == "회수제" and 상품회수 and 남은횟수 > 0:
                남은횟수 -= 1
                worksheet.update_cell(row_idx, 9, str(남은횟수))
                log_type = "회수제"
            else:
                st.warning("⛔ 선택한 이용권을 사용할 수 없습니다.")

            if log_type:
                count = int(customer.get("총 방문 횟수", 0)) + 1
                new_log = f"{방문기록}, {now_str} ({log_type})" if 방문기록 else f"{now_str} ({log_type})"
                worksheet.update_cell(row_idx, 4, today)
                worksheet.update_cell(row_idx, 5, str(count))
                worksheet.update_cell(row_idx, 12, new_log)
                st.success(f"✅ {log_type} 방문 기록 완료")
                time.sleep(1)
                st.rerun()

        # ... (이하 나머지 코드는 이전과 동일)
        if 상품정액 and days_left < 0:
            st.warning("⛔ 정액제 만료되었습니다.")
            sel = st.selectbox("정액제 재등록", 정액제옵션, key="재정액")
            if st.button("📅 정액제 재등록"):
                expire = now + timedelta(days=30)
                worksheet.update_cell(row_idx, 6, sel)
                worksheet.update_cell(row_idx, 7, "30")
                worksheet.update_cell(row_idx, 10, expire.strftime("%Y-%m-%d"))
                st.success("✅ 재등록 완료")
                st.rerun()

        if 상품회수 and 남은횟수 <= 0:
            st.warning("⛔ 회수제 소진됨. 충전 필요.")
            sel = st.selectbox("회수제 충전", 회수제옵션, key="재회수")
            if st.button("🔁 회수제 충전"):
                cnt = 1 if "1회" in sel else (5 if "5회" in sel else 10)
                worksheet.update_cell(row_idx, 9, str(cnt))
                worksheet.update_cell(row_idx, 8, sel)
                st.success("✅ 회수제 충전 완료")
                st.rerun()

        with st.form("add_product_form"):
            st.markdown("---")
            st.subheader("➕ 기존 고객 추가 상품 등록")
            add_jung = st.selectbox("정액제 추가 등록", ["None"] + 정액제옵션)
            add_hue = st.selectbox("회수제 추가 등록", ["None"] + 회수제옵션)
            sub = st.form_submit_button("등록")
            if sub:
                if add_jung != "None":
                    expire = now + timedelta(days=30)
                    worksheet.update_cell(row_idx, 6, add_jung)
                    worksheet.update_cell(row_idx, 7, "30")
                    worksheet.update_cell(row_idx, 10, expire.strftime("%Y-%m-%d"))
                    st.success("✅ 정액제 추가 등록 완료")
                if add_hue != "None":
                    cnt = 1 if "1회" in add_hue else (5 if "5회" in add_hue else 10)
                    worksheet.update_cell(row_idx, 9, str(cnt))
                    worksheet.update_cell(row_idx, 8, add_hue)
                    st.success("✅ 회수제 추가 등록 완료")
                st.rerun()

# ✅ 신규 등록
st.markdown("---")
st.subheader("🆕 신규 고객 등록")

np_value = "" if st.session_state.reset_form else None
ph_value = "" if st.session_state.reset_form else None

with st.form("register_form"):
    np = st.text_input("🚘 차량번호", value=np_value, key="new_plate")
    ph = st.text_input("📞 전화번호", value=ph_value, key="new_phone")
    pj = st.selectbox("정액제 상품", ["None"] + 정액제옵션, key="new_jung")
    phs = st.selectbox("회수제 상품", ["None"] + 회수제옵션, key="new_hue")

    reg = st.form_submit_button("등록", disabled=st.session_state.registering)

    if reg and np and ph:
        st.session_state.registering = True
        # --- ✨ 속도 최적화: 미리 불러온 all_records 사용 ---
        exists = any(r.get("차량번호") == np for r in all_records)
        # ------------------------------------------------
        if exists:
            st.warning("🚨 이미 등록된 고객입니다.")
            st.session_state.registering = False
        else:
            phone = format_phone_number(ph)
            jung_day = "30" if pj != "None" else ""
            expire = (now + timedelta(days=30)).strftime("%Y-%m-%d") if pj != "None" else "None"
            cnt = 1 if "1회" in phs else (5 if "5회" in phs else (10 if phs != "None" else ""))
            
            new_row = [np, phone, today, today, 1, pj if pj != "None" else "", jung_day, phs if phs != "None" else "", cnt, expire, "", f"{now_str} (신규등록)"]
            
            worksheet.append_row(new_row)
            st.success("✅ 등록이 완료되었습니다! 2초 후 앱이 새로고침 됩니다.")
            st.session_state.registration_success = True
            st.session_state.reset_form = True
            time.sleep(2)
            st.rerun()

if st.session_state.registration_success:
    st.session_state.registration_success = False
    st.session_state.registering = False
    st.session_state.reset_form = False
