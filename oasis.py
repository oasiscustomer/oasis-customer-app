# -*- coding: utf-8 -*-
"""oasis.py - 정액제 + 회수제 중복 등록 완전 지원 버전 (열 구조: A~J)
기능:
- 정액제 + 회수제 동시 등록, 방문 시 자동 분기 사용
- 각각의 소진 여부에 따라 재등록 UI 출력
- 모든 기록(G, H, I, J) 완전 자동화
"""

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

# ✅ 상품 옵션
정액제옵션 = ["기본(정액제)", "중급(정액제)", "고급(정액제)"]
회수제옵션 = ["일반 5회권", "중급 5회권", "고급 5회권", "일반 10회권", "중급 10회권", "고급 10회권", "고급 1회권"]

# ✅ 고객 정보 조회
def get_customer(plate):
    records = worksheet.get_all_records()
    customer = next((r for r in records if r.get("차량번호") == plate), None)
    row_idx = next((i + 2 for i, r in enumerate(records) if r.get("차량번호") == plate), None)
    return customer, row_idx, records

# ✅ 전화번호 포맷
def format_phone_number(phone: str) -> str:
    phone = phone.replace("-", "").strip()
    if len(phone) == 11 and phone.startswith("010"):
        return f"{phone[:3]}-{phone[3:7]}-{phone[7:]}"
    elif len(phone) == 10:
        return f"{phone[:3]}-{phone[3:6]}-{phone[6:]}"
    return phone

# ✅ UI 시작
st.title("🚘 오아시스 고객 관리 시스템")
search_plate = st.text_input("차량 번호 입력")

if search_plate:
    customer, row_idx, _ = get_customer(search_plate)
    if not customer:
        st.error("❌ 등록되지 않은 고객입니다.")
    else:
        st.success(f"✅ {search_plate} 고객 정보 불러오기 완료")
        상품정액 = customer.get("상품 옵션(정액제)", "")
        상품회수 = customer.get("상품 옵션(회수제)", "")
        남은일수 = int(customer.get("남은 이용 횟수", 0)) if 상품회수 else 0
        남은횟수 = int(customer.get("남은 이용 횟수", 0)) if 상품회수 else 0
        만료일 = customer.get("회원 만료일", "")
        방문기록 = customer.get("방문기록", "")

        # 만료일 계산
        days_left = -999
        if 상품정액:
            try:
                if 만료일 and 만료일.lower() != "none":
                    exp_date = datetime.strptime(만료일, "%Y-%m-%d").date()
                    days_left = (exp_date - now.date()).days
            except:
                days_left = -999

        # 📌 방문 처리
        if st.button("✅ 오늘 방문 기록 추가"):
            log_type = None
            if 상품정액 and days_left >= 0:
                worksheet.update_cell(row_idx, 7, str(days_left - 1))  # G열
                log_type = "정액제"
            elif 상품회수 and 남은횟수 > 0:
                worksheet.update_cell(row_idx, 8, str(남은횟수 - 1))  # H열
                log_type = "회수제"
            else:
                st.warning("❗ 사용 가능한 이용권이 없습니다. 재등록해주세요.")

            if log_type:
                new_count = int(customer.get("총 방문 횟수", 0)) + 1
                new_log = f"{방문기록}, {now_str} ({log_type})" if 방문기록 else f"{now_str} ({log_type})"
                worksheet.update_cell(row_idx, 4, today)  # D열
                worksheet.update_cell(row_idx, 5, new_count)  # E열
                worksheet.update_cell(row_idx, 10, new_log)  # J열
                st.success(f"✅ {log_type} 방문 기록이 추가되었습니다.")
                time.sleep(1)
                st.rerun()

        # 📌 정액제 만료 시 재등록
        if 상품정액 and days_left < 0:
            st.warning("⛔ 정액제 이용기간이 만료되었습니다.")
            new_pass = st.selectbox("정액제 재등록", 정액제옵션)
            if st.button("📅 정액제 재등록"):
                expire = now + timedelta(days=30)
                worksheet.update_cell(row_idx, 6, new_pass)  # F열
                worksheet.update_cell(row_idx, 7, "30")  # G열
                worksheet.update_cell(row_idx, 9, expire.strftime("%Y-%m-%d"))  # I열
                worksheet.update_cell(row_idx, 3, today)  # C열
                st.success("정액제 재등록 완료")
                st.rerun()

        # 📌 회수제 소진 시 충전
        if 상품회수 and 남은횟수 <= 0:
            st.warning("⛔ 회수제 이용권이 소진되었습니다.")
            new_tickets = st.selectbox("회수제 충전", 회수제옵션)
            if st.button("🔁 회수제 충전"):
                count = 1 if "1회" in new_tickets else (5 if "5회" in new_tickets else 10)
                worksheet.update_cell(row_idx, 8, str(count))  # H열
                worksheet.update_cell(row_idx, 7, new_tickets)  # G열
                worksheet.update_cell(row_idx, 3, today)
                st.success("회수제 충전 완료")
                st.rerun()

# ✅ 신규 등록
st.markdown("---")
st.subheader("🆕 신규 고객 등록")
with st.form("register_form"):
    new_plate = st.text_input("차량번호")
    new_phone = st.text_input("전화번호")
    option_jung = st.selectbox("정액제 상품", ["None"] + 정액제옵션)
    option_hue = st.selectbox("회수제 상품", ["None"] + 회수제옵션)
    submit = st.form_submit_button("📥 등록하기")

    if submit:
        _, _, all_records = get_customer(new_plate)
        exists = any(r.get("차량번호") == new_plate for r in all_records)
        if exists:
            st.warning("이미 등록된 차량번호입니다.")
        else:
            formatted_phone = format_phone_number(new_phone)
            new_row = [new_plate, formatted_phone, today, today, 1]
            # 상품 옵션
            if option_jung != "None":
                new_row += [option_jung, ""]
                new_row += ["", (now + timedelta(days=30)).strftime("%Y-%m-%d")]
            else:
                new_row += ["", ""]
                new_row += ["", "None"]
            if option_hue != "None":
                count = 1 if "1회" in option_hue else (5 if "5회" in option_hue else 10)
                new_row[6] = option_hue  # G열
                new_row[7] = str(count)  # H열
            else:
                new_row[7] = ""
            new_row += [f"{now_str} (신규등록)"]
            worksheet.append_row(new_row)
            st.success("신규 고객 등록 완료")
            time.sleep(1)
            st.rerun()
