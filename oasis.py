# -*- coding: utf-8 -*-
"""oasis.py - 완전 안정화본: 이용권 충전 UI 오류 및 rerun 동기화 문제 해결"""

import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
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

# ✅ 전화번호 포맷 함수
def format_phone_number(phone: str) -> str:
    phone = phone.replace("-", "").strip()
    if len(phone) == 11 and phone.startswith("010"):
        return f"{phone[:3]}-{phone[3:7]}-{phone[7:]}"
    elif len(phone) == 10:
        return f"{phone[:3]}-{phone[3:6]}-{phone[6:]}"
    return phone

# ✅ 고객 정보 재조회 함수
def get_customer(plate):
    records = worksheet.get_all_records()
    customer = next((r for r in records if r.get("차량번호") == plate), None)
    row_idx = next((i + 2 for i, r in enumerate(records) if r.get("차량번호") == plate), None)
    return customer, row_idx, records

# ✅ UI 제목
st.markdown("<h1 style='text-align: center; font-size: 22px;'>🚗 오아시스 고객 관리 시스템</h1>", unsafe_allow_html=True)

# ✅ 차량번호 검색 (Form 기반)
with st.form("search_form"):
    search_input = st.text_input("🔎 차량 번호 (전체 또는 끝 4자리)", key="search_input")
    submitted = st.form_submit_button("🔍 확인")

matched = []
if submitted and search_input.strip():
    records = worksheet.get_all_records()
    matched = [r for r in records if search_input.strip() in str(r.get("차량번호", ""))]

    if not matched:
        st.info("🚫 등록되지 않은 차량입니다.")
    else:
        def format_option_label(r):
            옵션 = r.get('상품 옵션', '')
            if 옵션 in ['5회', '10회', '20회']:
                return f"{r.get('차량번호')}"
            return f"{r.get('차량번호')} -> {옵션}"

        st.session_state.matched_options = {
            format_option_label(r): r.get("차량번호")
            for r in matched if r.get("차량번호")
        }
        st.session_state.matched_plate = list(st.session_state.matched_options.values())[0] if st.session_state.matched_options else None

# ✅ 고객 선택 유지 및 표시
if st.session_state.get("matched_plate") and st.session_state.get("matched_options"):
    current_plate = st.session_state.get("matched_plate")
    options = list(st.session_state.matched_options.keys())
    values = list(st.session_state.matched_options.values())
    try:
        selected_label = st.selectbox("📋 고객 선택", options, index=values.index(current_plate))
        st.session_state.matched_plate = st.session_state.matched_options[selected_label]
    except:
        st.session_state.matched_plate = values[0]

# ✅ 고객 처리
if st.session_state.get("matched_plate"):
    customer, row_idx, _ = get_customer(st.session_state.matched_plate)
    if customer and row_idx:
        상품옵션 = customer.get("상품 옵션", "").strip()
        상품명 = customer.get("상품명", "")
        만료일 = customer.get("회원 만료일", "")
        visit_log = customer.get("방문기록", "")

        st.markdown(f"### 🚘 선택된 차량번호: `{st.session_state.matched_plate}`")
        st.markdown(f"**상품 옵션:** {상품옵션} | **상품명:** {상품명}")

        if 상품옵션 in ["5회", "10회", "20회"]:
            try:
                remaining = int(customer.get("남은 이용 횟수", 0))
            except:
                remaining = 0

            st.info(f"💡 남은 이용 횟수: {remaining}회")

            if remaining <= 0:
                st.error("⛔ 이용횟수가 0건입니다. 재충전이 필요합니다.")
                if "recharge_option" not in st.session_state:
                    st.session_state.recharge_option = "5회"
                st.selectbox("🔄 충전할 이용권을 선택하세요", ["5회", "10회", "20회"], key="recharge_option")
                if st.button("💳 이용권 충전"):
                    recharge_count = int(st.session_state.recharge_option.replace("회", ""))
                    worksheet.update(f"F{row_idx}", [[st.session_state.recharge_option]])
                    worksheet.update(f"G{row_idx}", [[recharge_count]])
                    worksheet.update(f"C{row_idx}", [[today]])
                    st.success(f"✅ {st.session_state.recharge_option}로 충전이 완료되었습니다.")
                    time.sleep(1)
                    st.rerun()
                    st.stop()
            else:
                if st.button("✅ 오늘 방문 기록 추가"):
                    try:
                        new_remaining = remaining - 1
                        new_count = int(customer.get("총 방문 횟수", 0)) + 1
                        new_log = f"{visit_log}, {now_str} (1)" if visit_log else f"{now_str} (1)"

                        worksheet.update(f"D{row_idx}", [[today]])
                        worksheet.update(f"E{row_idx}", [[new_count]])
                        worksheet.update(f"G{row_idx}", [[new_remaining]])
                        worksheet.update(f"I{row_idx}", [[new_log]])

                        st.success(f"✅ 방문 기록이 추가되었습니다. 남은 이용 횟수: {new_remaining}회.")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Google Sheet 업데이트 실패: {e}")

        elif 상품옵션 in ["기본", "프리미엄", "스페셜"]:
            st.info(f"📄 정액제 회원입니다. (상품 옵션: {상품옵션})")
            if 만료일:
                try:
                    expire_date = datetime.strptime(만료일.split()[0], "%Y-%m-%d").date()
                    days_left = (expire_date - now.date()).days
                    if days_left < 0:
                        st.error("⛔ 회원 기간이 만료되었습니다.")
                        choice = st.radio("⏳ 회원이 만료되었습니다. 재등록 하시겠습니까?", ["예", "아니오"])
                        if choice == "예":
                            new_option = st.selectbox("새 상품 옵션을 선택하세요", ["5회", "10회", "20회"])
                            confirm = st.button("🎯 재등록 완료")
                            if confirm:
                                count = int(new_option.replace("회", ""))
                                worksheet.update(f"C{row_idx}", [[today]])
                                worksheet.update(f"F{row_idx}", [[new_option]])
                                worksheet.update(f"G{row_idx}", [[count]])
                                worksheet.update(f"H{row_idx}", [["None"]])
                                worksheet.update(f"E{row_idx}", [[0]])
                                st.success("✅ 재등록이 완료되었습니다.")
                                time.sleep(1)
                                st.rerun()
                                st.stop()
                    else:
                        st.success(f"✅ 회원 유효: {expire_date}까지 남음 ({days_left}일)")
                except Exception as e:
                    st.warning(f"⚠️ 만료일 형식 오류입니다: {e}")
            else:
                st.warning("⚠️ 회원 만료일 정보가 없습니다.")
        else:
            st.warning("⚠️ 알 수 없는 상품 옵션입니다. 관리자에게 문의하세요.")

# ✅ 신규 고객 등록
st.markdown("---")
st.markdown("🆕 신규 고객 등록")

with st.form("register_form"):
    new_plate = st.text_input("🚘 차량번호")
    new_phone = st.text_input("📞 전화번호")
    new_product = st.selectbox("🧾 이용권", ["5회", "10회", "20회"])
    reg_submit = st.form_submit_button("📥 신규 등록")

    if reg_submit and new_plate and new_phone:
        try:
            _, _, records = get_customer(new_plate)
            exists = any(r.get("차량번호") == new_plate for r in records)
            if exists:
                st.warning("🚨 이미 등록된 고객입니다.")
            else:
                formatted_phone = format_phone_number(new_phone)
                count = int(new_product.replace("회", ""))
                new_row = [new_plate, formatted_phone, today, today, 1, new_product, count, "None", f"{now_str} (1)"]
                worksheet.append_row(new_row)
                st.success("✅ 신규 고객 등록 완료")
                time.sleep(1)
                st.rerun()
        except Exception as e:
            st.error(f"❌ 등록 실패: {e}")
