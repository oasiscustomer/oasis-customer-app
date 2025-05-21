# -*- coding: utf-8 -*-
"""oasis.py - 실전 모바일 사용 최적화 + 정액제/회수제 중복관리 완성 버전"""

import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import pytz
import time

# ✅ 한국 시간대 설정
tz = pytz.timezone("Asia/Seoul")
now = datetime.now(tz)
today = now.strftime("%Y-%m-%d")
now_str = now.strftime("%Y-%m-%d %H:%M")

# ✅ 구글 인증
scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
client = gspread.authorize(credentials)
worksheet = client.open("Oasis Customer Management").sheet1

# ✅ 옵션 설정
정액제옵션 = ["기본(정액제)", "중급(정액제)", "고급(정액제)"]
회수제옵션 = ["일반 5회권", "중급 5회권", "고급 5회권", "일반 10회권", "중급 10회권", "고급 10회권", "고급 1회권"]

# ✅ 전화번호 포맷
def format_phone_number(phone: str) -> str:
    phone = phone.replace("-", "").strip()
    if len(phone) == 11 and phone.startswith("010"):
        return f"{phone[:3]}-{phone[3:7]}-{phone[7:]}"
    elif len(phone) == 10:
        return f"{phone[:3]}-{phone[3:6]}-{phone[6:]}"
    return phone

# ✅ 고객 정보 조회
def get_customer(plate):
    records = worksheet.get_all_records()
    customer = next((r for r in records if r.get("차량번호") == plate), None)
    row_idx = next((i + 2 for i, r in enumerate(records) if r.get("차량번호") == plate), None)
    return customer, row_idx, records

# ✅ UI 시작
st.markdown("<h1 style='text-align: center; font-size: 22px;'>🚘 오아시스 고객 관리 시스템</h1>", unsafe_allow_html=True)

with st.form("search_form"):
    search_input = st.text_input("🔎 차량 번호 (전체 또는 끝 4자리)", key="search_input")
    submitted = st.form_submit_button("🔍 확인")

matched = []
if submitted and search_input.strip():
    st.session_state["new_plate"] = ""
    st.session_state["new_phone"] = ""
    records = worksheet.get_all_records()
    matched = [r for r in records if search_input.strip() in str(r.get("차량번호", ""))]

    if not matched:
        st.info("🚫 등록되지 않은 차량입니다.")
    else:
        st.session_state.matched_options = {
            f"{r.get('차량번호')} -> {r.get('상품 옵션(정액제)', '')}/{r.get('상품 옵션(회수제)', '')}": r.get("차량번호") for r in matched if r.get("차량번호")
        }
        st.session_state.matched_plate = list(st.session_state.matched_options.values())[0]

if st.session_state.get("matched_plate") and st.session_state.get("matched_options"):
    current_plate = st.session_state.get("matched_plate")
    options = list(st.session_state.matched_options.keys())
    values = list(st.session_state.matched_options.values())
    selected_label = st.selectbox("📋 고객 선택", options, index=values.index(current_plate))
    st.session_state.matched_plate = st.session_state.matched_options[selected_label]

# ✅ 고객 처리
if st.session_state.get("matched_plate"):
    customer, row_idx, _ = get_customer(st.session_state.matched_plate)
    if customer and row_idx:
        st.markdown(f"### 🚘 차량번호: `{st.session_state.matched_plate}`")
        상품정액 = customer.get("상품 옵션(정액제)", "")
        상품회수 = customer.get("상품 옵션(회수제)", "")
        남은일수 = int(customer.get("남은 이용 일수", 0)) if customer.get("남은 이용 일수") else 0
        남은횟수 = int(customer.get("남은 이용 횟수", 0)) if customer.get("남은 이용 횟수") else 0
        만료일 = customer.get("회원 만료일", "")
        방문기록 = customer.get("방문기록", "")

        days_left = -999
        if 상품정액:
            try:
                if 만료일 and 만료일.lower() != "none":
                    exp_date = datetime.strptime(만료일, "%Y-%m-%d").date()
                    days_left = (exp_date - now.date()).days
            except:
                days_left = -999

        if st.button("✅ 오늘 방문 기록 추가"):
            log_type = None
            if 상품정액 and days_left >= 0:
                남은일수 -= 1
                worksheet.update_cell(row_idx, 7, str(남은일수))
                log_type = "정액제"
            elif 상품회수 and 남은횟수 > 0:
                남은횟수 -= 1
                worksheet.update_cell(row_idx, 8, str(남은횟수))
                log_type = "회수제"
            else:
                st.warning("⛔ 사용 가능한 이용권이 없습니다. 재등록해주세요.")

            if log_type:
                new_count = int(customer.get("총 방문 횟수", 0)) + 1
                new_log = f"{방문기록}, {now_str} ({log_type})" if 방문기록 else f"{now_str} ({log_type})"
                worksheet.update_cell(row_idx, 4, today)
                worksheet.update_cell(row_idx, 5, str(new_count))
                worksheet.update_cell(row_idx, 10, new_log)
                st.success(f"✅ {log_type} 방문 기록이 저장되었습니다.")
                time.sleep(1)
                st.rerun()

        # 🔁 정액제 재등록
        if 상품정액 and days_left < 0:
            st.warning("⛔ 정액제 만료되었습니다.")
            new_option = st.selectbox("정액제 재등록", 정액제옵션, key="정액재등록")
            if st.button("📅 정액제 재등록"):
                expire = now + timedelta(days=30)
                worksheet.update_cell(row_idx, 6, new_option)
                worksheet.update_cell(row_idx, 7, "30")
                worksheet.update_cell(row_idx, 9, expire.strftime("%Y-%m-%d"))
                st.success("✅ 정액제 재등록 완료")
                st.rerun()

        # 🔁 회수제 재등록
        if 상품회수 and 남은횟수 <= 0:
            st.warning("⛔ 회수제 소진되었습니다.")
            new_option = st.selectbox("회수제 충전", 회수제옵션, key="회수재등록")
            if st.button("🔁 회수제 충전"):
                count = 1 if "1회" in new_option else (5 if "5회" in new_option else 10)
                worksheet.update_cell(row_idx, 8, str(count))
                worksheet.update_cell(row_idx, 7, new_option)
                st.success("✅ 회수제 충전 완료")
                st.rerun()

# ✅ 신규 등록
st.markdown("---")
st.subheader("🆕 신규 고객 등록")
with st.form("register_form"):
    new_plate = st.text_input("🚘 차량번호", key="new_plate")
    new_phone = st.text_input("📞 전화번호", key="new_phone")
    new_jung = st.selectbox("🧾 정액제 상품 선택", ["None"] + 정액제옵션)
    new_hue = st.selectbox("🧾 회수제 상품 선택", ["None"] + 회수제옵션)
    reg_submit = st.form_submit_button("📥 등록하기")

    if reg_submit and new_plate and new_phone:
        _, _, all_records = get_customer(new_plate)
        exists = any(r.get("차량번호") == new_plate for r in all_records)
        if exists:
            st.warning("🚨 이미 등록된 고객입니다.")
        else:
            formatted_phone = format_phone_number(new_phone)
            jung_day = "30" if new_jung != "None" else ""
            expire = (now + timedelta(days=30)).strftime("%Y-%m-%d") if new_jung != "None" else "None"
            hue_count = 1 if "1회" in new_hue else (5 if "5회" in new_hue else (10 if new_hue != "None" else ""))
            new_row = [new_plate, formatted_phone, today, today, 1, new_jung if new_jung != "None" else "", new_hue if new_hue != "None" else "", hue_count, expire, f"{now_str} (신규등록)"]
            worksheet.append_row(new_row)
            st.success("✅ 신규 고객 등록 완료")
            time.sleep(1)
            st.rerun()
