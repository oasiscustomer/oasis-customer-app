# -*- coding: utf-8 -*-
"""oasis.py - 최종 완성본 (HTML 직접 생성으로 모든 문제 해결)"""

import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import pytz
import time

# --- 1. 기본 설정 및 데이터 로딩 (로직 변경 없음) ---
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
    with st.spinner("🔄 데이터를 새로 불러오는 중..."):
        worksheet = _client.open("Oasis Customer Management").sheet1
        return worksheet.get_all_records()

client = get_gspread_client()
worksheet = client.open("Oasis Customer Management").sheet1
all_records = load_data(client)

정액제옵션 = ["기본(정액제)", "중급(정액제)", "고급(정액제)"]
회수제옵션 = ["일반 5회권", "중급 5회권", "고급 5회권", "일반 10회권", "중급 10회권", "고급 10회권", "고급 1회권"]

def get_customer(plate, records):
    customer = next((r for r in records if r.get("차량번호") == plate), None)
    row_idx = next((i + 2 for i, r in enumerate(records) if r.get("차량번호") == plate), None)
    return customer, row_idx

def clear_all_cache():
    st.cache_data.clear()
    st.cache_resource.clear()

for key in ["registration_success", "registering", "reset_form", "matched_plate"]:
    if key not in st.session_state:
        st.session_state[key] = False

# --- 2. UI 구조 개선 ---

st.markdown("<h3 style='text-align: center; font-weight:bold;'>🚘 오아시스 고객 관리</h3>", unsafe_allow_html=True)

tab1, tab2 = st.tabs(["**기존 고객 관리**", "**신규 고객 등록**"])

with tab1:
    # ✨ --- [UI 개선점] st.form 대신 HTML form을 직접 생성 --- ✨
    # 이 방법은 디자인을 100% 제어하고 환경에 따른 오류가 없습니다.
    search_form_html = """
    <style>
        .custom-search-form {{
            margin-bottom: 1rem;
        }}
        .custom-search-form label {{
            font-size: 1.1rem !important;
            font-weight: 600 !important;
            display: block;
            margin-bottom: 0.5rem;
        }}
        .custom-search-form input[type="text"] {{
            font-size: 1.25rem !important;
            height: 50px !important;
            width: 100%;
            padding: 0.5rem;
            border: 1px solid #ccc;
            border-radius: 0.5rem;
            box-sizing: border-box;
        }}
        .custom-search-form input[type="submit"] {{
            width: 100%;
            height: 42px;
            margin-top: 0.75rem;
            border-radius: 0.5rem;
            border: none;
            background-color: #f63366;
            color: white;
            font-size: 1rem;
            font-weight: 600;
        }}
    </style>
    <form action="" method="get" class="custom-search-form">
        <label for="search_plate">🔍 차량 번호 (전체 또는 끝 4자리)</label>
        <input type="text" id="search_plate" name="search_plate" placeholder="예: 1234">
        <input type="submit" value="검색">
    </form>
    """
    st.markdown(search_form_html, unsafe_allow_html=True)
    
    # URL 쿼리 파라미터에서 검색어 가져오기
    query_params = st.experimental_get_query_params()
    search_input = query_params.get("search_plate", [None])[0]

    # 검색어가 있을 때만 로직 실행
    if search_input and search_input.strip():
        # 이전에 검색된 결과가 현재 검색어와 다를 경우, 세션 초기화
        if st.session_state.get("last_search") != search_input:
            st.session_state.matched_plate = None

        st.session_state.last_search = search_input
        matched = [r for r in all_records if search_input.strip() in str(r.get("차량번호", ""))]
        
        if not matched:
            st.info("🚫 등록되지 않은 차량입니다. '신규 고객 등록' 탭을 이용해 주세요.")
            st.session_state.matched_plate = None
        else:
            # 검색 결과가 있으면, 첫 번째 결과를 기본 선택으로 설정
            options = {}
            for r in matched:
                plate = r.get("차량번호")
                jung = r.get("상품 옵션(정액제)", "없음") or "없음"
                hue = r.get("상품 옵션(회수제)", "없음") or "없음"
                label = f"{plate} → 정액제: {jung} / 회수제: {hue}"
                options[label] = plate
            st.session_state.matched_options = options
            # 현재 선택된 차량이 없거나, 현재 선택된 차량이 새 검색결과에 없을 때만 업데이트
            if not st.session_state.get("matched_plate") or st.session_state.get("matched_plate") not in options.values():
                st.session_state.matched_plate = list(options.values())[0]

    if st.session_state.get("matched_plate"):
        plate = st.session_state["matched_plate"]
        label_options = list(st.session_state.matched_options.keys())
        value_options = list(st.session_state.matched_options.values())
        
        try:
            current_index = value_options.index(plate)
        except ValueError:
            current_index = 0

        selected_label = st.selectbox("👇 검색된 고객 선택", label_options, index=current_index, key="customer_select")
        
        # selectbox에서 다른 고객을 선택하면 바로 반영
        if st.session_state.matched_plate != st.session_state.matched_options[selected_label]:
            st.session_state.matched_plate = st.session_state.matched_options[selected_label]
            st.rerun()

        customer, row_idx = get_customer(st.session_state.matched_plate, all_records)

        if customer and row_idx:
            with st.container(border=True):
                st.markdown(f"#### **{st.session_state.matched_plate}** 님 정보")

                is_blacklist = str(customer.get("블랙리스트", "")).strip().upper() == "Y"
                if is_blacklist:
                    st.error("🚨 **블랙리스트 회원**")

                # (로직 변경 없음)
                상품정액 = customer.get("상품 옵션(정액제)", "")
                상품회수 = customer.get("상품 옵션(회수제)", "")
                방문기록 = customer.get("방문기록", "")
                만료일 = customer.get("회원 만료일", "")
                남은횟수 = int(customer.get("남은 이용 횟수", 0)) if str(customer.get("남은 이용 횟수")).isdigit() else 0
                최근방문일 = "기록 없음"
                if 방문기록:
                    try:
                        last_log = 방문기록.split(',')[-1].strip()
                        최근방문일 = last_log.split(' ')[0]
                    except IndexError:
                        최근방문일 = "확인 불가"
                방문횟수_기간내 = 0
                if 상품정액 and 만료일 not in [None, "", "None", "none"]:
                    try:
                        expire_date = datetime.strptime(만료일, "%Y-%m-%d").date()
                        start_date = expire_date - timedelta(days=30)
                        if 방문기록:
                            visit_logs = 방문기록.split(',')
                            for log in visit_logs:
                                log_date_str = log.strip().split(' ')[0]
                                log_date = datetime.strptime(log_date_str, "%Y-%m-%d").date()
                                if start_date <= log_date <= expire_date:
                                    방문횟수_기간내 += 1
                    except: pass
                days_left = -999
                if 상품정액 and 만료일 not in [None, "", "None", "none"]:
                    try:
                        expire_date = datetime.strptime(만료일, "%Y-%m-%d").date()
                        days_left = (expire_date - now.date()).days
                        if str(customer.get("남은 이용 일수")) != str(max(0, days_left)):
                            worksheet.update_cell(row_idx, 7, str(max(0, days_left)))
                    except: pass
                
                # HTML 테이블로 정보 표시
                val1 = f"{days_left}일" if 상품정액 and days_left >= 0 else ("만료" if 상품정액 else "없음")
                delta1 = f"~{만료일}" if 상품정액 else ""
                val2 = f"{남은횟수}회" if 상품회수 else "없음"
                val3 = 최근방문일
                val4 = f"{방문횟수_기간내}회" if 상품정액 else ""
                
                html_table = f"""
                <style>
                    .metric-table {{ width: 100%; border-collapse: collapse; margin-top: 1rem; }}
                    .metric-table td {{ width: 50%; padding: 8px; text-align: center; vertical-align: top; }}
                    .metric-label {{ font-size: 0.95rem; color: #555; margin-bottom: 0.25rem; }}
                    .metric-value {{ font-size: 1.75rem; font-weight: 600; line-height: 1.2; }}
                    .metric-delta {{ font-size: 0.8rem; color: #888; }}
                </style>
                <table class="metric-table">
                    <tr>
                        <td>
                            <div class="metric-label">정액제</div>
                            <div class="metric-value">{val1}</div>
                            <div class="metric-delta">{delta1}</div>
                        </td>
                        <td>
                            <div class="metric-label">회수권(남은횟수)</div>
                            <div class="metric-value">{val2}</div>
                            <div class="metric-delta">&nbsp;</div>
                        </td>
                    </tr>
                    <tr>
                        <td>
                            <div class="metric-label">최근 방문</div>
                            <div class="metric-value">{val3}</div>
                            <div class="metric-delta">&nbsp;</div>
                        </td>
                        <td>
                            <div class="metric-label">기간 내 이용</div>
                            <div class="metric-value">{val4}</div>
                            <div class="metric-delta">&nbsp;</div>
                        </td>
                    </tr>
                </table>
                """
                
                st.markdown(html_table, unsafe_allow_html=True)
            
            # 이하 로직은 변경 없음
            with st.container(border=True):
                st.subheader("✅ 방문 기록 추가")
                visit_options = []
                if 상품정액 and days_left >= 0: visit_options.append("정액제")
                if 상품회수 and 남은횟수 > 0: visit_options.append("회수제")

                if visit_options:
                    사용옵션 = st.radio("사용할 이용권 선택:", visit_options, horizontal=True)
                    if st.button(f"**{사용옵션}으로 방문 기록하기**", use_container_width=True, type="primary"):
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
            
            with st.expander("🔄 상품 추가 / 갱신 / 충전"):
                if (상품정액 and days_left < 0) or (상품회수 and 남은횟수 <= 0):
                    st.info("만료/소진된 상품을 갱신 또는 충전합니다.")
                    if 상품정액 and days_left < 0:
                        sel = st.selectbox("정액제 갱신", 정액제옵션, key="재정액")
                        if st.button("📅 정액제 갱신하기", use_container_width=True):
                            expire = now + timedelta(days=30)
                            worksheet.update_cell(row_idx, 6, sel)
                            worksheet.update_cell(row_idx, 7, "30")
                            worksheet.update_cell(row_idx, 10, expire.strftime("%Y-%m-%d"))
                            st.success("✅ 재등록 완료"); clear_all_cache(); st.rerun()
                    if 상품회수 and 남은횟수 <= 0:
                        sel = st.selectbox("회수권 충전", 회수제옵션, key="재회수")
                        if st.button("🔁 회수권 충전하기", use_container_width=True):
                            cnt = 1 if "1회" in sel else (5 if "5회" in sel else 10)
                            worksheet.update_cell(row_idx, 9, str(cnt))
                            worksheet.update_cell(row_idx, 8, sel)
                            st.success("✅ 회수권 충전 완료"); clear_all_cache(); st.rerun()
                
                st.info("기존 고객에게 새로운 종류의 상품을 추가합니다.")
                with st.form("add_product_form"):
                    add_jung = st.selectbox("정액제 추가 등록", ["선택 안함"] + 정액제옵션)
                    add_hue = st.selectbox("회수제 추가 등록", ["선택 안함"] + 회수제옵션)
                    if st.form_submit_button("새 상품 추가하기", use_container_width=True):
                        updated = False
                        if add_jung != "선택 안함":
                            expire = now + timedelta(days=30)
                            worksheet.update_cell(row_idx, 6, add_jung); worksheet.update_cell(row_idx, 7, "30"); worksheet.update_cell(row_idx, 10, expire.strftime("%Y-%m-%d"))
                            st.success("✅ 정액제 추가 등록 완료"); updated = True
                        if add_hue != "선택 안함":
                            cnt = 1 if "1회" in add_hue else (5 if "5회" in add_hue else 10)
                            worksheet.update_cell(row_idx, 9, str(cnt)); worksheet.update_cell(row_idx, 8, add_hue)
                            st.success("✅ 회수제 추가 등록 완료"); updated = True
                        if updated:
                            clear_all_cache(); st.rerun()

with tab2:
    st.subheader("🆕 신규 고객 정보 입력")
    with st.form("register_form"):
        np = st.text_input("🚘 차량번호", placeholder="12가 1234")
        ph = st.text_input("📞 전화번호", placeholder="010-1234-5678")
        st.markdown("---")
        pj = st.selectbox("정액제 상품 (선택)", ["선택 안함"] + 정액제옵션)
        phs = st.selectbox("회수제 상품 (선택)", ["선택 안함"] + 회수제옵션)

        if st.form_submit_button("신규 고객으로 등록하기", use_container_width=True, type="primary"):
            if np and ph:
                exists = any(r.get("차량번호") == np for r in all_records)
                if exists:
                    st.warning("🚨 이미 등록된 차량번호입니다. '기존 고객 관리' 탭에서 검색해 보세요.")
                else:
                    phone = ph.replace("-", "").strip()
                    jung_day = "30" if pj != "선택 안함" else ""
                    expire = (now + timedelta(days=30)).strftime("%Y-%m-%d") if pj != "선택 안함" else ""
                    cnt = ""
                    if phs != "선택 안함":
                        cnt = 1 if "1회" in phs else (5 if "5회" in phs else 10)
                    new_row = [np, phone, today, today, 1, pj if pj != "선택 안함" else "", jung_day, phs if phs != "선택 안함" else "", cnt, expire, "", f"{now_str} (신규등록)"]
                    worksheet.append_row(new_row)
                    st.success("✅ 등록이 완료되었습니다! 앱이 새로고침 됩니다.")
                    clear_all_cache()
                    time.sleep(2)
                    st.rerun()
            else:
                st.error("차량번호와 전화번호는 필수 입력 항목입니다.")
