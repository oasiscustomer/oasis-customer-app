# -*- coding: utf-8 -*-
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
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

# ✅ 고객 조회
def get_customer(plate):
    records = worksheet.get_all_records()
    customer = next((r for r in records if r.get("차량번호") == plate), None)
    row_idx = next((i + 2 for i, r in enumerate(records) if r.get("차량번호") == plate), None)
    return customer, row_idx, records

# ✅ 옵션 정의
이용권옵션 = ["일반 5회권", "중급 5회권", "고급 5회권", "일반 10회권", "중급 10회권", "고급 10회권", "고급 1회권"]
정액제옵션 = ["기본(정액제)", "중급(정액제)", "고급(정액제)"]

# ✅ UI 시작
st.markdown("<h1 style='text-align: center; font-size: 22px;'>🚗 오아시스 고객 관리 시스템</h1>", unsafe_allow_html=True)

# ✅ 검색 UI
with st.form("search_form"):
    search_input = st.text_input("🔎 차량 번호 (전체 또는 끝 4자리)", key="search_input")
    submitted = st.form_submit_button("🔍 확인")

matched = []
if submitted and search_input.strip():
    st.session_state["new_plate"] = ""
    st.session_state["new_phone"] = ""
    st.session_state["recharge_option"] = 이용권옵션[0]
    records = worksheet.get_all_records()
    matched = [r for r in records if search_input.strip() in str(r.get("차량번호", ""))]

    if not matched:
        st.info("🚫 등록되지 않은 차량입니다.")
    else:
        st.session_state.matched_options = {
            f"{r.get('차량번호')} -> {r.get('상품 옵션', '')}": r.get("차량번호") for r in matched if r.get("차량번호")
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
        상품옵션 = customer.get("상품 옵션", "").strip()
        만료일 = customer.get("회원 만료일", "")
        visit_log = customer.get("방문기록", "")
        st.markdown(f"### 🚘 선택된 차량번호: `{st.session_state.matched_plate}`")
        st.markdown(f"**상품 옵션:** {상품옵션}")

        if 상품옵션 in 이용권옵션:
            remaining = int(customer.get("남은 이용 횟수", 0))
            st.info(f"💡 남은 이용 횟수: {remaining}회")
            if remaining <= 0:
                st.error("⛔ 이용횟수가 0건입니다. 재충전이 필요합니다.")
                st.selectbox("🔄 충전할 이용권을 선택하세요", 이용권옵션, key="recharge_option")
                if st.button("💳 이용권 충전"):
                    recharge_count = int('1' if '1회' in st.session_state.recharge_option else ('5' if '5회' in st.session_state.recharge_option else '10'))
                    worksheet.update(f"F{row_idx}", [[st.session_state.recharge_option]])
                    worksheet.update(f"G{row_idx}", [[recharge_count]])
                    worksheet.update(f"C{row_idx}", [[today]])
                    worksheet.update(f"H{row_idx}", [["None"]])
                    st.success("✅ 이용권 충전 완료")
                    time.sleep(1)
                    st.rerun()
            else:
                if st.button("✅ 오늘 방문 기록 추가"):
                    new_count = int(customer.get("총 방문 횟수", 0)) + 1
                    remaining -= 1
                    new_log = f"{visit_log}, {now_str} (1)" if visit_log else f"{now_str} (1)"
                    worksheet.update(f"D{row_idx}", [[today]])
                    worksheet.update(f"E{row_idx}", [[new_count]])
                    worksheet.update(f"G{row_idx}", [[remaining]])
                    worksheet.update(f"I{row_idx}", [[new_log]])
                    st.success(f"✅ 방문 기록이 추가되었습니다. 남은 횟수: {remaining}회")
                    st.rerun()

        elif 상품옵션 in 정액제옵션:
            try:
                expire_date = datetime.strptime(만료일.split()[0], "%Y-%m-%d").date()
                days_left = (expire_date - now.date()).days
                label = f"{max(days_left, 0)}일"

                if days_left < 0:
                    st.error("⛔ 회원 기간이 만료되었습니다.")
                    st.markdown("### 🔁 재등록 진행")
                    new_option = st.selectbox("새 상품 옵션을 선택하세요", 이용권옵션 + 정액제옵션, key="rejoin_option")
                    if st.button("🎯 재등록 완료"):
                        if new_option in 정액제옵션:
                            expire = now + timedelta(days=30)
                            worksheet.update(f"C{row_idx}", [[today]])
                            worksheet.update(f"F{row_idx}", [[new_option]])
                            worksheet.update(f"G{row_idx}", [[31]])
                            worksheet.update(f"H{row_idx}", [[expire.strftime("%Y-%m-%d")]])
                            worksheet.update(f"E{row_idx}", [[0]])
                        else:
                            count = int('1' if '1회' in new_option else ('5' if '5회' in new_option else '10'))
                            worksheet.update(f"C{row_idx}", [[today]])
                            worksheet.update(f"F{row_idx}", [[new_option]])
                            worksheet.update(f"G{row_idx}", [[count]])
                            worksheet.update(f"H{row_idx}", [["None"]])
                            worksheet.update(f"E{row_idx}", [[0]])
                        st.success("✅ 재등록 완료")
                        time.sleep(1)
                        st.rerun()
                else:
                    st.success(f"✅ 회원 유효: {expire_date}까지 남음 ({label})")
                    if st.button("✅ 오늘 방문 기록 추가"):
                        new_count = int(customer.get("총 방문 횟수", 0)) + 1
                        new_log = f"{visit_log}, {now_str} (1)" if visit_log else f"{now_str} (1)"
                        worksheet.update(f"D{row_idx}", [[today]])
                        worksheet.update(f"E{row_idx}", [[new_count]])
                        worksheet.update(f"G{row_idx}", [[max(days_left - 1, 0)]])
                        worksheet.update(f"I{row_idx}", [[new_log]])
                        st.success(f"✅ 방문 기록이 추가되었습니다. 남은 기간: {max(days_left - 1, 0)}일")
                        st.rerun()
            except Exception as e:
                st.warning(f"⚠️ 만료일 형식 오류: {e}")

# ✅ 신규 고객 등록
st.markdown("---")
st.markdown("🆕 신규 고객 등록")
with st.form("register_form"):
    new_plate = st.text_input("🚘 차량번호", key="new_plate")
    new_phone = st.text_input("📞 전화번호", key="new_phone")
    new_product = st.selectbox("🧾 이용권", 이용권옵션 + 정액제옵션)
    reg_submit = st.form_submit_button("📥 신규 등록")
    if reg_submit and new_plate and new_phone:
        try:
            _, _, records = get_customer(new_plate)
            exists = any(r.get("차량번호") == new_plate for r in records)
            if exists:
                st.warning("🚨 이미 등록된 고객입니다.")
            else:
                formatted_phone = format_phone_number(new_phone)
                if new_product in 정액제옵션:
                    expire = now + timedelta(days=30)
                    new_row = [new_plate, formatted_phone, today, today, 1, new_product, 31, expire.strftime("%Y-%m-%d"), f"{now_str} (1)"]
                else:
                    count = int('1' if '1회' in new_product else ('5' if '5회' in new_product else '10'))
                    new_row = [new_plate, formatted_phone, today, today, 1, new_product, count, "None", f"{now_str} (1)"]
                worksheet.append_row(new_row)
                st.success("✅ 신규 고객 등록 완료")
                time.sleep(1)
                st.rerun()
        except Exception as e:
            st.error(f"❌ 등록 실패: {e}")
