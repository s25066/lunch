import calendar
from datetime import datetime, timedelta
import html
import requests
import streamlit as st

# -----------------------------------------------------------------------------
# 1. 페이지 기본 설정 및 스타일 정의
# -----------------------------------------------------------------------------
st.set_page_config(page_title="학교 급식 달력", page_icon="🍱", layout="wide")

# 카드 테두리, 배지 및 영양정보 스타일 정의 (CSS)
st.markdown(
    """
    <style>
    .meal-card {
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 12px;
        margin-bottom: 12px;
        background-color: #ffffff;
        min-height: 180px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .today-card {
        border: 2px solid #3182ce !important;
        background-color: #f7fafc !important;
    }
    .date-header {
        font-weight: bold;
        font-size: 1.1em;
        margin-bottom: 8px;
        color: #2d3748;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .today-badge {
        background-color: #3182ce;
        color: white;
        font-size: 0.7em;
        padding: 2px 6px;
        border-radius: 4px;
        font-weight: bold;
    }
    .meal-title-container {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-top: 8px;
        margin-bottom: 4px;
    }
    .meal-title {
        font-weight: bold;
        font-size: 0.9em;
    }
    .lunch { color: #2b6cb0; }    /* 중식 - 파란색 */
    .dinner { color: #c53030; }   /* 석식 - 빨간색 */
    .other { color: #2f855a; }    /* 기타 - 초록색 */

    .cal-badge {
        font-size: 0.75em;
        background-color: #edf2f7;
        color: #4a5568;
        padding: 1px 5px;
        border-radius: 4px;
        font-weight: 600;
    }
    
    .meal-content {
        font-size: 0.85em;
        color: #4a5568;
        line-height: 1.4;
        margin-left: 4px;
    }
    .no-meal {
        color: #a0aec0;
        font-size: 0.85em;
        font-style: italic;
    }

    .nutrition-details {
        margin-top: 6px;
        font-size: 0.75em;
        color: #718096;
        border-top: 1px dashed #e2e8f0;
        padding-top: 4px;
    }
    .nutrition-summary {
        cursor: pointer;
        color: #4a5568;
        font-weight: bold;
        outline: none;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# 2. 알레르기 번호 매핑 사전 (1~19번)
# -----------------------------------------------------------------------------
ALLERGY_MAP = {
    "1": "난류", "2": "우유", "3": "메밀", "4": "땅콩", "5": "대두",
    "6": "밀", "7": "게", "8": "새우", "9": "돼지고기", "10": "복숭아",
    "11": "토마토", "12": "아황산류", "13": "호두", "14": "닭고기",
    "15": "쇠고기", "16": "오징어", "17": "조개류", "18": "잣", "19": "과일류(소고기/기타)"
}

# -----------------------------------------------------------------------------
# 3. 사이드바 구성
# -----------------------------------------------------------------------------
st.sidebar.title("⚙️ 설정")

if "NEIS_KEY" not in st.secrets:
    st.error("🔑 NEIS API 키가 설정되지 않았습니다.")
    st.info("`.streamlit/secrets.toml` 파일에 `NEIS_KEY = \"발급받은키\"` 형태로 추가해 주세요.")
    st.stop()

neis_key = st.secrets["NEIS_KEY"]

atpt_code = st.sidebar.text_input("시도교육청코드", value="B10", help="예: 서울(B10), 경기(J10) 등")
sd_code = st.sidebar.text_input("표준학교코드", value="7010057", help="학교의 7자리 표준학교코드")

st.sidebar.markdown("---")
convert_allergy = st.sidebar.toggle("알레르기 식품명으로 변환", value=False)

with st.sidebar.expander("ℹ️ 알레르기 번호 표 보기"):
    allergy_text = "\n".join([f"**{k}**: {v}" for k, v in ALLERGY_MAP.items()])
    st.markdown(allergy_text)

# -----------------------------------------------------------------------------
# 4. 메뉴 텍스트 및 영양 정보 정제 함수
# -----------------------------------------------------------------------------
def format_dish_name(dish_raw, convert=False):
    clean_text = dish_raw.replace("<br/>", "\n")

    if not convert:
        return clean_text

    lines = clean_text.split("\n")
    converted_lines = []

    for line in lines:
        if "." in line:
            parts = line.split(" ")
            new_parts = []
            for part in parts:
                if part.startswith("(") and part.endswith(")"):
                    nums = part[1:-1].split(".")
                    mapped_names = [ALLERGY_MAP.get(num, num) for num in nums if num in ALLERGY_MAP]
                    if mapped_names:
                        new_parts.append(f"({','.join(mapped_names)})")
                    else:
                        new_parts.append(part)
                else:
                    new_parts.append(part)
            converted_lines.append(" ".join(new_parts))
        else:
            converted_lines.append(line)

    return "\n".join(converted_lines)

def format_nutrition_info(ntr_raw):
    if not ntr_raw:
        return "정보 없음"
    clean_ntr = ntr_raw.replace("<br/>", ", ")
    return html.escape(clean_ntr)

# -----------------------------------------------------------------------------
# 5. NEIS API 데이터 수집 함수
# -----------------------------------------------------------------------------
@st.cache_data(ttl=3600)
def fetch_meal_data(key, atpt, sd, year, month):
    _, last_day = calendar.monthrange(year, month)
    from_ymd = f"{year}{month:02d}01"
    to_ymd = f"{year}{month:02d}{last_day:02d}"

    url = "https://open.neis.go.kr/hub/mealServiceDietInfo"
    params = {
        "KEY": key,
        "Type": "json",
        "pIndex": 1,
        "pSize": 100,
        "ATPT_OFCDC_SC_CODE": atpt,
        "SD_SCHUL_CODE": sd,
        "MLSV_FROM_YMD": from_ymd,
        "MLSV_TO_YMD": to_ymd,
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if "mealServiceDietInfo" in data:
            rows = data["mealServiceDietInfo"][1]["row"]
            meal_by_date = {}
            for row in rows:
                ymd = row["MLSV_YMD"]
                meal_type = row["MMEAL_SC_NM"]
                dish_name = row["DDISH_NM"]
                cal_info = row.get("CAL_INFO", "")
                ntr_info = row.get("NTR_INFO", "")

                if ymd not in meal_by_date:
                    meal_by_date[ymd] = []
                meal_by_date[ymd].append({
                    "type": meal_type,
                    "dish": dish_name,
                    "cal": cal_info,
                    "ntr": ntr_info
                })
            return meal_by_date, None

        elif "RESULT" in data and data["RESULT"]["CODE"] == "INFO-200":
            return {}, None
        else:
            err_msg = data.get("RESULT", {}).get("MESSAGE", "알 수 없는 API 에러가 발생했습니다.")
            return None, f"API 오류: {err_msg}"

    except requests.exceptions.RequestException as e:
        return (None, f"통신 오류가 발생했습니다. 인터넷 연결이나 입력값을 확인해 주세요. ({e})")

# -----------------------------------------------------------------------------
# 6. 상단 필터 및 뷰 컨트롤 (주간/월간 뷰 전환 포함)
# -----------------------------------------------------------------------------
st.title("🍱 우리 학교 급식 달력")

now = datetime.now()

# 주간 모드 기준 날짜 세션 초기화 (월요일 기준)
if "week_anchor" not in st.session_state:
    st.session_state.week_anchor = now - timedelta(days=now.weekday())

top_col1, top_col2 = st.columns([1, 1])

with top_col1:
    view_mode = st.radio("보기 방식", ["월간 보기", "주간 보기"], horizontal=True)

with top_col2:
    meal_filter = st.radio("급식 종류", ["전체 보기", "중식만 보기", "석식만 보기"], horizontal=True)

st.markdown("---")

# -----------------------------------------------------------------------------
# 7. 뷰 선택에 따른 화면 구성
# -----------------------------------------------------------------------------
try:
    weekdays_name = ["월", "화", "수", "목", "금"]
    today_str = now.strftime("%Y%m%d")

    # 카드 HTML 생성 헬퍼 함수
    def render_meal_card(date_obj, day_meals):
        ymd_str = date_obj.strftime("%Y%m%d")
        is_today = (ymd_str == today_str)
        day_num = date_obj.day
        weekday_str = weekdays_name[date_obj.weekday()]

        card_class = "meal-card today-card" if is_today else "meal-card"
        today_badge_html = '<span class="today-badge">TODAY</span>' if is_today else ""

        inner_html = f"""<div class="date-header"><span>{day_num}일 ({weekday_str})</span>{today_badge_html}</div>"""

        if not day_meals:
            inner_html += '<div class="no-meal">급식 없음</div>'
        else:
            filtered_meals = []
            for meal in day_meals:
                if meal_filter == "전체 보기":
                    filtered_meals.append(meal)
                elif meal_filter == "중식만 보기" and meal["type"] == "중식":
                    filtered_meals.append(meal)
                elif meal_filter == "석식만 보기" and meal["type"] == "석식":
                    filtered_meals.append(meal)

            if not filtered_meals:
                inner_html += '<div class="no-meal">해당 식단 없음</div>'
            else:
                for meal in filtered_meals:
                    m_type = meal["type"]
                    color_class = "lunch" if m_type == "중식" else ("dinner" if m_type == "석식" else "other")

                    formatted_dish = format_dish_name(meal["dish"], convert_allergy)
                    safe_dish = html.escape(formatted_dish).replace("\n", "<br/>")

                    cal_badge = f'<span class="cal-badge">{html.escape(meal["cal"])}</span>' if meal.get("cal") else ""
                    safe_ntr = format_nutrition_info(meal.get("ntr", ""))

                    inner_html += f"""
                    <div class="meal-title-container">
                        <span class="meal-title {color_class}">▶ {m_type}</span>
                        {cal_badge}
                    </div>
                    <div class="meal-content">{safe_dish}</div>
                    <details class="nutrition-details">
                        <summary class="nutrition-summary">📊 영양성분 보기</summary>
                        <div style="margin-top:4px;">{safe_ntr}</div>
                    </details>
                    """

        return f"""<div class="{card_class}">{inner_html}</div>"""


    # ==================== A. 월간 보기 ====================
    if view_mode == "월간 보기":
        c1, c2 = st.columns(2)
        with c1:
            selected_year = st.selectbox("연도 선택", range(now.year - 1, now.year + 2), index=1)
        with c2:
            selected_month = st.selectbox("월 선택", range(1, 13), index=now.month - 1)

        meal_data, error = fetch_meal_data(neis_key, atpt_code, sd_code, selected_year, selected_month)
        if error:
            st.error(f"🚨 급식 정보를 가져오는데 실패했습니다: {error}")
            st.stop()

        month_cal = calendar.monthcalendar(selected_year, selected_month)

        for week in month_cal:
            workdays = week[:5]
            if any(day != 0 for day in workdays):
                cols = st.columns(5)
                for idx, day in enumerate(workdays):
                    with cols[idx]:
                        if day == 0:
                            st.write("")
                            continue

                        current_date = datetime(selected_year, selected_month, day)
                        current_ymd = current_date.strftime("%Y%m%d")
                        day_meals = meal_data.get(current_ymd, [])

                        st.html(render_meal_card(current_date, day_meals))

    # ==================== B. 주간 보기 ====================
    else:
        btn_col1, btn_col2, btn_col3, _ = st.columns([1, 1, 1, 3])
        with btn_col1:
            if st.button("◀ 이전 주"):
                st.session_state.week_anchor -= timedelta(days=7)
                st.rerun()
        with btn_col2:
            if st.button("📅 이번 주"):
                st.session_state.week_anchor = now - timedelta(days=now.weekday())
                st.rerun()
        with btn_col3:
            if st.button("다음 주 ▶"):
                st.session_state.week_anchor += timedelta(days=7)
                st.rerun()

        # 주간 날짜 범위 계산 (월~금)
        monday = st.session_state.week_anchor
        week_days = [monday + timedelta(days=i) for i in range(5)]

        st.subheader(f"🗓️ {monday.strftime('%Y년 %m월 %d일')} ~ {(monday + timedelta(days=4)).strftime('%m월 %d일')} 급식")

        # 주간 보기 시 필요한 달(Month)들의 데이터를 수집
        needed_months = set((d.year, d.month) for d in week_days)
        merged_meal_data = {}
        for y, m in needed_months:
            data, error = fetch_meal_data(neis_key, atpt_code, sd_code, y, m)
            if data:
                merged_meal_data.update(data)

        cols = st.columns(5)
        for idx, date_obj in enumerate(week_days):
            with cols[idx]:
                ymd_str = date_obj.strftime("%Y%m%d")
                day_meals = merged_meal_data.get(ymd_str, [])
                st.html(render_meal_card(date_obj, day_meals))

except Exception as ex:
    st.error(f"🎨 화면 구성 중 예외가 발생했습니다: {ex}")
