# -*- coding: utf-8 -*-
"""oasis.ipynb - 실시간 동기화 기반 시스템 (신규 회원은 차감/충전, 기존 회원은 만료일 안내)"""

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
    customer = next((r for r in records if r["차량번호"] == plate), None)
    row_idx = next((i + 2 for i, r in enumerate(records) if r["차량번호"] == plate), None)
    return customer, row_idx, records

# ✅ UI 제목
st.markdown("<h1 style='text-align: center; font-size: 22px;'>🚗 오아시스 고객 관리 시스템</h1>", unsafe_allow_html=True)

# ✅ 차량번호 검색
with st.form("search_form"):
    search_input = st.text_input("🔎 차량 번호 (전체 또는 끝 4자리)")
    submitted = st.form_submit_button("🔍 확인")

if submitted and search_input.strip():
    plate_input = search_input.strip()
    records = worksheet.get_all_records()
    matched = [r for r in records if plate_input in r["차량번호"]]

    if not matched:
        st.info("🆕 등록되지 않은 차량입니다. 아래에서 신규 고객을 등록하세요.")
    else:
        customer_options = {
            f"{r.get('차량번호', '')} → {r.get('상품 옵션', '')} / 남은 {r.get('남은 이용 횟수', '0')}회": r["차량번호"]
            for r in matched
        }
        selected_label = st.selectbox("📋 고객 선택", list(customer_options.keys()))
        selected_plate = customer_options[selected_label]
        customer, row_idx, _ = get_customer(selected_plate)

        상품옵션 = customer.get("상품 옵션", "")
        만료일 = customer.get("회원 만료일", "")

        if 상품옵션 in ["5회", "10회", "20회"]:
            try:
                remaining = int(customer.get("남은 이용 횟수", 0))
            except:
                remaining = 0

            visit_log = customer.get("방문기록", "")
            today_logged = any(today in log.strip() for log in visit_log.split(",")) if visit_log else False

            if remaining <= 0:
                st.warning("⛔ 이용횟수가 0건입니다.")
                if st.radio("재충전 하시겠습니까?", ["예", "아니오"], key="recharge") == "예":
                    recharge_option = st.selectbox("🧾 이용권 재선택", ["5회", "10회", "20회"])
                    count = int(recharge_option.replace("회", ""))
                    if st.button("✅ 충전 완료"):
                        worksheet.update(f"F{row_idx}", [[recharge_option]])
                        worksheet.update(f"G{row_idx}", [[count]])
                        st.success("충전 완료! 새로고침 해주세요.")
                        st.stop()
            else:
                if today_logged:
                    if st.radio("오늘 이미 방문 기록이 있습니다. 추가로 입력할까요?", ["Y", "N"], key="repeat") == "Y":
                        if st.button("📌 추가 방문 기록 입력"):
                            count = int(customer.get("총 방문 횟수", 0)) + 1
                            remaining -= 1
                            new_log = f"{visit_log}, {now_str} (1)"
                            worksheet.update(f"D{row_idx}", [[today]])
                            worksheet.update(f"E{row_idx}", [[count]])
                            worksheet.update(f"G{row_idx}", [[remaining]])
                            worksheet.update(f"I{row_idx}", [[new_log]])
                            st.success(f"✅ 방문 기록이 추가되었습니다. 남은 이용 횟수: {remaining}회.")
                else:
                    if st.button("✅ 오늘 방문 기록 추가"):
                        count = int(customer.get("총 방문 횟수", 0)) + 1
                        remaining -= 1
                        new_log = f"{visit_log}, {now_str} (1)" if visit_log else f"{now_str} (1)"
                        worksheet.update(f"D{row_idx}", [[today]])
                        worksheet.update(f"E{row_idx}", [[count]])
                        worksheet.update(f"G{row_idx}", [[remaining]])
                        worksheet.update(f"I{row_idx}", [[new_log]])
                        st.success(f"✅ 방문 기록이 추가되었습니다. 남은 이용 횟수: {remaining}회.")
        else:
            st.info(f"📄 이 고객은 정액제 회원입니다. (상품 옵션: {상품옵션})")
            if 만료일:
                try:
                    expire_date = datetime.strptime(만료일, "%Y-%m-%d").date()
                    days_left = (expire_date - now.date()).days
                    if days_left < 0:
                        st.error("⛔ 회원 기간이 만료되었습니다.")
                    else:
                        st.success(f"✅ 회원 유효: {expire_date}까지 남음 ({days_left}일)")
                except Exception as e:
                    st.warning(f"⚠️ 만료일 형식 오류: {e}")
            else:
                st.warning("⚠️ 회원 만료일 정보가 없습니다.")

# ✅ 신규 고객 등록
st.markdown("---")
st.markdown("🆕 신규 고객 등록")

with st.form("register_form"):
    new_plate = st.text_input("🚘 차량번호")
    new_phone = st.text_input("📞 전화번호")
    new_product = st.selectbox("🧾 이용권", ["5회", "10회", "20회"])
    reg_submit = st.form_submit_button("📥 신규 등록")

    if reg_submit and new_plate and new_phone:
        _, _, records = get_customer(new_plate)
        exists = any(r["차량번호"] == new_plate for r in records)
        if exists:
            st.warning("🚨 이미 등록된 고객입니다.")
        else:
            try:
                formatted_phone = format_phone_number(new_phone)
                count = int(new_product.replace("회", ""))
                new_row = [new_plate, formatted_phone, today, today, 1, new_product, count, "", f"{now_str} (1)"]
                worksheet.append_row(new_row)
                st.success("✅ 신규 고객 등록 완료")
                time.sleep(1)
                st.experimental_rerun()
            except Exception as e:
                st.error(f"❌ 등록 실패: {e}")
