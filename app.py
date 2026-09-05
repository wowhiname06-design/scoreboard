# -*- coding: utf-8 -*-
import streamlit as st
import time
import math
import re
import html
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# 페이지 설정 (넓은 화면 사용)
st.set_page_config(page_title="웹 점수판 실시간 추적기", page_icon="📊", layout="wide")

# 커스텀 CSS로 전반적인 디자인을 평범하고 깔끔한 웹사이트처럼 다듬기
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stButton>button { width: 100%; border-radius: 6px; font-weight: bold; height: 40px; }
    .result-card {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        border-left: 5px solid #4f46e5;
        padding: 15px 20px;
        margin-bottom: 10px;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
        font-size: 18px;
        font-weight: 600;
        color: #1f2937;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .diff-badge {
        background-color: #eef2ff;
        color: #4f46e5;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 15px;
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)

if 'last_valid_parsed_list' not in st.session_state:
    st.session_state.last_valid_parsed_list = []
if 'is_running' not in st.session_state:
    st.session_state.is_running = False
if 'driver' not in st.session_state:
    st.session_state.driver = None

def get_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1200,2000")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    return webdriver.Chrome(options=options)

def parse_all_with_scroll(driver, calc_mode, exclude_ceo):
    """표의 실제 열 구조를 기준으로 라벨, 멤버 이름, 점수를 읽는다."""
    try:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(0.1)
    except Exception:
        pass

    try:
        raw_rows_data = driver.execute_script("""
            return Array.from(document.querySelectorAll('table tbody tr')).map(row =>
                Array.from(row.querySelectorAll(':scope > td')).map(cell =>
                    (cell.innerText || '').replace(/\\s+/g, ' ').trim()
                )
            );
        """)
    except Exception:
        raw_rows_data = []

    people = []
    for cells in raw_rows_data:
        try:
            # 직급/라벨, 스트리머, 웹후원, 계좌후원, 점수, 기여도
            if len(cells) < 6:
                continue

            label = cells[0].strip()
            streamer_cell = cells[1].strip()
            if not streamer_cell or streamer_cell == "총 합":
                continue

            # 대표 행만 제외한다. 부장/인턴 같은 사무직 직급은 이름 셀에
            # 포함되어 있으므로 목록으로 추측하지 않고 마지막 토큰을 이름으로 쓴다.
            if exclude_ceo and label == "대표":
                continue

            name_tokens = streamer_cell.split()
            if not name_tokens:
                continue
            name = name_tokens[-1]

            score_index = 5 if calc_mode == "contrib" else 4
            score_text = cells[score_index].replace(",", "").strip()
            score = float(score_text)

            people.append({"name": name, "label": label, "score": score})
        except (ValueError, TypeError, IndexError):
            continue

    unique_people = []
    seen = set()
    for person in people:
        if person["name"] not in seen:
            seen.add(person["name"])
            unique_people.append(person)

    return unique_people

# 메인 UI 제목
st.title("📊 웹 점수판 실시간 추적 대시보드")
st.markdown("---")

# 상단 깔끔한 설정 영역 (접고 펼치기 가능)
with st.expander("⚙️ 설정 및 필터 옵션 (클릭해서 열기/닫기)", expanded=True):
    col_1, col_2, col_3 = st.columns(3)
    
    with col_1:
        url = st.text_input("점수판 링크 URL", value="https://scoredev.flabs.kr/5snb08fSl5-WwQ")
        calc_mode_str = st.radio("계산 기준 컬럼", ["💧 기여도 (6번째 열)", "⭐ 점수 (5번째 열)"])
        calc_mode = "contrib" if "기여도" in calc_mode_str else "score"
        
    with col_2:
        diff_limit = st.number_input("점수 차이 기준 (점 이하)", value=50, step=5)
        max_display = st.number_input("최대 표시 개수 (0은 제한 없음)", value=0, step=1)
        interval = st.number_input(
            "자동 갱신 주기 (초)",
            value=1.0,
            min_value=0.1,
            step=0.1,
            format="%.1f",
        )
        
    with col_3:
        st.write("### 예외 처리 및 표시 설정")
        exclude_ceo = st.checkbox("👑 '대표 / 사장' 항목 제외", value=True)
        show_scores = st.checkbox("🏷️ 멤버 이름 옆 점수 표시", value=True)

    st.markdown("")
    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        start_btn = st.button("▶ 추적 시작", type="primary")
    with c2:
        stop_btn = st.button("⏹ 추적 중지")

if start_btn:
    st.session_state.is_running = True
    if st.session_state.driver is None:
        try:
            st.session_state.driver = get_driver()
            st.session_state.driver.get(url)
        except Exception as e:
            st.error(f"브라우저 실행 오류: {e}")
            st.session_state.is_running = False

if stop_btn:
    st.session_state.is_running = False
    if st.session_state.driver:
        try:
            st.session_state.driver.quit()
        except:
            pass
        st.session_state.driver = None

st.markdown("### 📌 실시간 모니터링 결과")
status_area = st.empty()
result_area = st.empty()

@st.fragment(run_every=interval)
def live_tracker():
    if st.session_state.is_running and st.session_state.driver:
        try:
            parsed_list = parse_all_with_scroll(st.session_state.driver, calc_mode, exclude_ceo)

            if not parsed_list or len(parsed_list) < 12:
                if st.session_state.last_valid_parsed_list:
                    parsed_list = st.session_state.last_valid_parsed_list
            else:
                st.session_state.last_valid_parsed_list = parsed_list

            if parsed_list:
                parsed_list.sort(key=lambda x: x['score'], reverse=True)
                diff_results = []
                for i in range(len(parsed_list) - 1):
                    p1 = parsed_list[i]
                    p2 = parsed_list[i + 1]
                    diff_exact = p1['score'] - p2['score']
                    if diff_exact.is_integer():
                        diff = int(diff_exact) + 1
                    else:
                        diff = math.ceil(diff_exact)

                    if diff <= diff_limit:
                        diff_results.append({'p1': p1, 'p2': p2, 'diff': diff})

                matched_count = len(diff_results)
                total_count = len(parsed_list)
                now_str = datetime.now().strftime("%H:%M:%S")

                status_area.success(f"🟢 감시 중 (총 수집: {total_count}명 | 기준 {diff_limit}점 이하: {matched_count}건 감지됨 | 마지막 갱신: {now_str})")

                output_items = diff_results[:max_display] if max_display > 0 else diff_results

                cards_html = ""
                if output_items:
                    for item in output_items:
                        if show_scores:
                            p1_name = html.escape(item["p1"]["name"])
                            p2_name = html.escape(item["p2"]["name"])
                            p1_label = html.escape(item["p1"]["label"])
                            p2_label = html.escape(item["p2"]["label"])
                            p1_str = f"{p1_name} <span style='color: #4f46e5; font-size: 14px;'>[{p1_label}]</span> <span style='color: #6b7280; font-size: 15px;'>({item['p1']['score']:,.1f})</span>"
                            p2_str = f"{p2_name} <span style='color: #4f46e5; font-size: 14px;'>[{p2_label}]</span> <span style='color: #6b7280; font-size: 15px;'>({item['p2']['score']:,.1f})</span>"
                        else:
                            p1_str = f'{html.escape(item["p1"]["name"])} <span style="color: #4f46e5; font-size: 14px;">[{html.escape(item["p1"]["label"])}]</span>'
                            p2_str = f'{html.escape(item["p2"]["name"])} <span style="color: #4f46e5; font-size: 14px;">[{html.escape(item["p2"]["label"])}]</span>'
                            
                        cards_html += f"""
                        <div class="result-card">
                            <div>👤 {p1_str} &nbsp; ➔ &nbsp; 👤 {p2_str}</div>
                            <div class="diff-badge">⚡ {item['diff']}점 차이</div>
                        </div>
                        """
                else:
                    cards_html = """
                    <div style="padding: 20px; background-color: #ffffff; border-radius: 8px; text-align: center; color: #6b7280; border: 1px solid #e0e0e0;">
                        현재 설정된 조건에 맞는 점수 차이 구간이 없습니다.
                    </div>
                    """

                result_area.markdown(cards_html, unsafe_allow_html=True)
        except Exception as e:
            status_area.warning(f"⚠️ 데이터 갱신 중... ({e})")
    else:
        status_area.info("🔵 대기 중입니다. 상단 설정 메뉴에서 **[▶ 추적 시작]** 버튼을 눌러주세요.")

live_tracker()