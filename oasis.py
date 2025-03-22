# -*- coding: utf-8 -*-
"""
oasis.py

Streamlit Cloud + Google Colab 호환 고객관리 시스템 (중복 입력 방지 및 최초 클릭 반응 개선 포함)
"""

import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import re
import json

# ✅ 인증 처리 함수
def load_credentials():
    try:
        return Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        )
    except Exception:
        st.subheader("🔑 Google Sheets API 키 업로드 (Colab 전용)")
        uploaded_key = st.file_uploader("JSON 키 파일 업로드", type=["json"])
        if uploaded_key is not None:
            try:
                info = json.load(uploaded_key)
                return Credentials.from_service_account_info(
                    info,
                    scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
                )
            except Exception as e:
                st.error(f"🚨 키 파일 오류: {e}")
                st.stop()
        else:
            st.warning("⛔ 키 파일을 업로드해야 앱이 작동합니다.")
            st.stop()
    return None

credentials = load_credentials()
if credentials is None:
    st.error("🚫 인증 실패: credentials 값이 None입니다.")
    st.stop()

# ✅ Google Sheets 연동
try:
    client = gspread.authorize(credentials)
    worksheet = client.open("Oasis Customer Management").worksheet("시트1")
except Exception as e:
    st.error(f"🚨 Google Sheets 연결 실패: {e}")
    st.stop()

st.title("🚗 세차장 고객 관리 시스템")
st.write("📋 차량 번호와 고객 정보를 입력하여 Google Sheets에 기록합니다.")

# ✅ 세션 상태 변수 초기화
if "matched_result" not in st.session_state:
    st.session_state.matched_result = []
if "search_done" not in st.session_state:
    st.session_state.search_done = False
if "selected_plate" not in st.session_state:
    st.session_state.selected_plate = None

# ✅ 고객 차량 정보 입력
st.subheader("2️⃣ 고객 차량 정보 입력")
plate_input = st.text_input("🔎 차량 번호 (전체 또는 끝 4자리)", key="plate_input")
search_button = st.button("🔍 확인", key="search_button")

if search_button and plate_input:
    records = worksheet.get_all_records()
    matched = [r for r in records if "차량번호" in r and (plate_input in r["차량번호"] or r["차량번호"].endswith(plate_input))]
    st.session_state.search_done = True
    st.session_state.matched_result = matched
    st.session_state.selected_plate = None

if st.session_state.search_done:
    matched = st.session_state.matched_result
    today_str = datetime.now().strftime("%Y-%m-%d")
    customer = None

    if matched and len(matched) == 1:
        customer = matched[0]
    elif matched and len(matched) > 1:
        st.warning("🚨 동일한 끝 4자리를 가진 차량이 여러 대입니다. 전체 차량번호를 선택하세요.")
        options = [r["차량번호"] for r in matched]
        selected = st.selectbox("차량번호 선택", options, key="select_plate")
        if selected:
            st.session_state.selected_plate = selected
            customer = next((r for r in matched if r["차량번호"] == selected), None)
    else:
        customer = None

    if customer:
        # 중복 확인
        if today_str in customer.get("방문기록", ""):
            st.warning("🚨 오늘 입력된 정보가 이미 있습니다. 추가로 입력하는 게 맞습니까?")
            confirm = st.radio("📌 계속 진행하시겠습니까?", ["N", "Y"], key="confirm_existing")
            if confirm == "N":
                st.stop()

        st.success("✅ 기존 고객 확인됨. 방문 기록을 자동으로 업데이트합니다.")
        all_records = worksheet.get_all_records()
        row_index = next((i + 2 for i, r in enumerate(all_records) if r['차량번호'] == customer['차량번호']), None)
        if row_index:
            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            date_only = now.split()[0]
            old_log = customer.get("방문기록", "")
            new_log = old_log + f", {now} (1)" if old_log else f"{now} (1)"

            worksheet.update_cell(row_index, 4, date_only)
            worksheet.update_cell(row_index, 5, int(customer.get("총 방문 횟수", 0)) + 1)
            worksheet.update_cell(row_index, 6, new_log)
            st.write("🗓 방문 정보가 성공적으로 업데이트되었습니다.")

    elif matched == []:
        st.info("🆕 등록되지 않은 차량입니다. 아래에 고객 정보를 입력해 주세요.")
        full_plate = st.text_input("🚘 전체 차량번호 (예: 160호 7421)", key="new_plate")
        raw_phone = st.text_input("📞 고객 전화번호 (예: 01042921289 또는 010-4292-1289)", key="new_phone")

        def format_phone(phone):
            digits = re.sub(r'[^0-9]', '', phone)
            if len(digits) == 11:
                return f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
            return phone

        # 중복 여부 검사
        duplicate_today = any(full_plate == r["차량번호"] and today_str in r.get("방문기록", "") for r in records)
        if duplicate_today:
            st.warning("⚠️ 오늘 동일한 차량번호로 등록된 기록이 있습니다. 추가 등록하시겠습니까?")
            confirm_new = st.radio("📌 계속 등록할까요?", ["N", "Y"], key="confirm_new")
            if confirm_new == "N":
                st.stop()

        if st.button("📥 신규 고객 등록") and full_plate and raw_phone:
            phone = format_phone(raw_phone)
            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            date_only = now.split()[0]
            new_row = [full_plate, phone, date_only, date_only, 1, f"{now} (1)"]
            worksheet.append_row(new_row)
            st.success(f"✅ 신규 고객 등록 완료: {full_plate}")
            st.session_state.search_done = False
