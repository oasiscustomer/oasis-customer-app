# -*- coding: utf-8 -*-
"""oasis.ipynb"""

import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import pytz
import time

# ✅ 한국 시간대
tz = pytz.timezone("Asia/Seoul")
now = datetime.now(tz)
today = now.strftime("%Y-%m-%d")
now_str = now.strftime("%Y-%m-%d %H:%M")

# ✅ Google 인증
scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
client = gspread.authorize(credentials)
worksheet = client.open("Oasis Customer Management").sheet1

# ✅ 전화번호 포맷
def format_phone_number(phone: str) -> str:
    phone = phone.replace("-", "").strip()
    if len(phone) == 11 and phone.startswith("010"):
        return f"{phone[:3]}-{phone[3:7]}-{phone[7:]}"
    elif len(phone) == 10:
        return f"{phone[:3]}-{phone[3:6]}-{phone[6:]}"
    return phone

# ✅ 옵션 → 개월 수 매핑
def get_expire_date(join_date: datetime.date, option: str) -> str:
    option_map = {"1개월": 1, "3개월": 3, "6개월": 6, "12개월": 12}
    months = option_map.get(option, 1)
    expire_date = join_date + relativedelta(months=months) - timedelta(days=1)
    return expire_date.strftime("%Y-%m-%d")

# ✅ 세션 초기화
if "search_input" not in st.session_state:
    st.session_state.search_input = ""
if "matched_customers" not in st.session_state:
    st.session_state.matched_customers = []
if "selected_plate" not in st.session_state:
    st.session_state.selected_plate = ""
if "clear_fields" not in st.session_state:
    st.session_state.clear_fields = False

# ✅ UI
st.markdown("<h1 style='text-align: center; font-size: 22px;'>🚗 오아시스 고객 관리 시스템</h1>", unsafe_allow_html=True)
st.markdown("### 2️⃣ 고객 차량 정보 입력")

# ✅ 차량번호 검색
with st.form("search_form"):
    search_input = st.text_input("🔎 차량 번호 (전체 또는 끝 4자리)", value=st.session_state.search_input)
    search_submit = st.form_submit_button("🔍 확인")

records = worksheet.get_all_records()

if search_submit and search_input.strip():
    st.session_state.search_input = search_input.strip()
    st.session_state.matched_customers = [
        r for r in records
        if isinstance(r, dict)
        and "차량번호" in r
        and isinstance(r["차량번호"], str)
        and st.session_state.search_input in r["차량번호"]
    ]
    st.session_state.selected_plate = ""

# ✅ 기존 고객 처리
if st.session_state.matched_customers:
    st.session_state.selected_plate = st.selectbox(
        "📋 전체 차량번호 중에서 선택하세요",
        [r["차량번호"] for r in st.session_state.matched_customers],
        index=0 if st.session_state.selected_plate == "" else
        [r["차량번호"] for r in st.session_state.matched_customers].index(st.session_state.selected_plate)
    )

    selected_customer = next((r for r in records if r["차량번호"] == st.session_state.selected_plate), None)
    row_idx = next((i + 2 for i, r in enumerate(records) if r["차량번호"] == st.session_state.selected_plate), None)

    if not selected_customer or not row_idx:
        st.error("❌ 선택한 고객 정보를 찾을 수 없습니다. 다시 검색해 주세요.")
        st.stop()

    expired = False
    product = selected_customer.get("상품명", "").strip()
    join_date_str = selected_customer.get("가입날짜", "").strip()

    try:
        join_date = datetime.strptime(join_date_str, "%Y-%m-%d").date()
        days_since_join = (now.date() - join_date).days
        if days_since_join >= 30 or product == "비회원":
            expired = True
    except ValueError:
        st.warning("⚠️ 가입날짜가 올바르지 않아 만료 여부를 확인할 수 없습니다.")

    if expired:
        st.warning("📢 이 고객은 회원 기간이 만료되었거나 비회원입니다.")
        renew_choice = st.radio("재등록 하시겠습니까?", ["예", "아니오"], key="renew_choice")

        if renew_choice == "예":
            new_product = st.selectbox("🧾 새 상품 등급을 선택하세요", ["기본", "프리미엄", "스페셜"], key="product_renew")
            option = st.selectbox("🗓 회원권 기간을 선택하세요", ["1개월", "3개월", "6개월", "12개월"], key="option_renew")
            if st.button("✅ 재등록 확정"):
                try:
                    expire_date = get_expire_date(now.date(), option)
                    worksheet.update(f"C{row_idx}", [[today]])
                    worksheet.update(f"F{row_idx}", [[new_product]])
                    worksheet.update(f"G{row_idx}", [[option]])
                    worksheet.update(f"H{row_idx}", [[expire_date]])
                    st.success("✅ 재등록이 완료되었습니다.")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ 재등록 실패: {e}")
                st.stop()
        else:
            try:
                worksheet.update(f"F{row_idx}", [["비회원"]])
                st.info("ℹ️ 비회원으로 처리되었습니다.")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"❌ 비회원 처리 실패: {e}")
            st.stop()

    visit_log = selected_customer.get("방문기록", "")

    if today in visit_log:
        with st.form("existing_repeat_form"):
            st.info("📌 오늘 이미 방문 기록이 있습니다. 추가로 입력할까요?")
            repeat_choice = st.radio("입력 확인", ["Y", "N"], key="repeat_choice")
            repeat_submit = st.form_submit_button("✅ 기존 고객 확인")
            if repeat_submit:
                if repeat_choice == "Y":
                    try:
                        count = int(selected_customer.get("총 방문 횟수", 0)) + 1
                        new_log = f"{visit_log}, {now_str} (1)"
                        worksheet.update(f"D{row_idx}", [[today]])
                        worksheet.update(f"E{row_idx}", [[count]])
                        worksheet.update(f"I{row_idx}", [[new_log]])
                        st.success("✅ 방문 기록이 추가되었습니다.")
                        time.sleep(2)
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ 업데이트 실패: {e}")
                else:
                    st.stop()
    else:
        with st.form("new_visit_form"):
            confirm = st.form_submit_button("✅ 오늘 방문 기록 추가")
            if confirm:
                try:
                    count = int(selected_customer.get("총 방문 횟수", 0)) + 1
                    new_log = f"{visit_log}, {now_str} (1)" if visit_log else f"{now_str} (1)"
                    worksheet.update(f"D{row_idx}", [[today]])
                    worksheet.update(f"E{row_idx}", [[count]])
                    worksheet.update(f"I{row_idx}", [[new_log]])
                    st.success("✅ 방문 기록이 추가되었습니다.")
                    time.sleep(2)
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ 업데이트 실패: {e}")

# ✅ 신규 고객 등록
st.markdown("---")
st.markdown("🆕 신규 고객 차량 정보 입력")

new_plate_value = "" if st.session_state.clear_fields else None
new_phone_value = "" if st.session_state.clear_fields else None

with st.form("register_form"):
    new_plate = st.text_input("🚘 전체 차량번호", value=new_plate_value)
    new_phone = st.text_input("📞 고객 전화번호", value=new_phone_value)
    product_options = ["기본", "프리미엄", "스페셜"]
    selected_product = st.selectbox("🧾 상품명 선택", product_options)
    selected_option = st.selectbox("🗓 회원권 기간을 선택하세요", ["1개월", "3개월", "6개월", "12개월"])
    register_submit = st.form_submit_button("📥 신규 고객 등록")

    if register_submit and new_plate and new_phone:
        exists = any(r["차량번호"] == new_plate for r in records)
        if exists:
            st.warning("🚨 이미 등록된 차량입니다.")
        else:
            try:
                formatted_phone = format_phone_number(new_phone)
                expire_date = get_expire_date(now.date(), selected_option)
                new_row = [new_plate, formatted_phone, today, today, 1, selected_product, selected_option, expire_date, f"{now_str} (1)"]
                worksheet.append_row(new_row)
                st.success("✅ 신규 고객 등록 완료")
                st.session_state.clear_fields = True
                time.sleep(2)
                st.rerun()
            except Exception as e:
                st.error(f"❌ 등록 실패: {e}")

if st.session_state.clear_fields:
    st.session_state.clear_fields = False
