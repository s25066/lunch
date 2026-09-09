import calendar
from datetime import datetime, timedelta
import html
import requests
import streamlit as st

# -----------------------------------------------------------------------------
# 1. 페이지 기본 설정 및 스타일 정의
# -----------------------------------------------------------------------------
st.set_page_config(page_title="학교 급식 달력", page_icon="🍱", layout="wide")

# CSS 스타일 정의 (알레르기 경고 하이라이트 추가)
st.markdown(
    """
    <style>
    .meal-card {
        border: 1px solid #e0e0e0;
        border-radius: 12px;
        padding: 14px;
        margin-bottom: 12px;
        background-color: #ffffff;
        min-height: 180px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .meal-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 8px 15px rgba(0,0,0,0.1);
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

    /* 알레르기 경고 하이라이트 스타일 */
    .allergy-alert {
        background-color: #fff5f5;
        border-left: 3px solid #e53e3e;
        padding: 2px 6px;
        margin-top: 2px;
        margin-bottom: 2px;
        border-radius: 2px;
    }
    .allergy-badge {
        background-color: #e53e3e;
        color: white;
        font-size: 0.7em;
        padding: 1px 5px;
        border-radius: 3px;
        font-weight: bold;
        margin-left: 4px;
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

# ⚠️ 나의 알레르기 설정 추가
st.sidebar.subheader("⚠️ 나의 알레르기 설정")
user_allergies = st.sidebar.multiselect(
    "보유 알레르기를 선택하세요",
    options=list(ALLERGY_MAP.values()),
    help="선택한 성분이 포함된 급식 메뉴가 빨간색으로 하이라이트됩니다."
)

convert_allergy = st.sidebar.toggle("알레르기 식품명으로 변환 표시", value=True)

with st.sidebar.expander("ℹ️ 전체 알레르기 번호 표"):
    allergy_text = "\n".join([f"**{k}**: {v}" for k, v in ALLERGY_MAP.items()])
    st.markdown(allergy_text)

# -----------------------------------------------------------------------------
# 4. 메뉴 텍스트 파싱 및 알레르기 강조 처리 함수
# -----------------------------------------------------------------------------
def format_dish_with_allergy(dish_raw, convert=False, my_allergies=[]):
    """
    메뉴별 알레르기 정보를 파싱하고 사용자의 알레르기 항목 포함 시 강조태그를 적용합니다.
    """
    clean_text = dish_raw.replace("<br/>", "\n")
    lines = clean_text.split("\n")
    rendered_lines = []

    for line in lines:
        if not line.strip():
            continue

        # 알레르기 번호 추출
        contained_allergy_names = []
        if "(" in line and ")" in line:
            try:
                start_idx = line.rfind("(")
                end_idx = line.rfind(")")
                num_str = line[start_idx+1:end_idx]
                nums = num_str.split(".")
                contained_allergy_names = [ALLERGY_MAP.get(n, n) for n in nums if n in ALLERGY_MAP]
            except Exception:
                pass

        # 알레르기 번호 -> 이름 변환 적용
        display_line = line
        if convert and contained_allergy_names:
            line_prefix = line[:line.rfind("(")]
            display_line = f"{line_prefix}({','.join(contained_allergy_names)})"

        safe_line = html.escape(display_line)

        # 사용자의 알레르기와 매칭 여부 검사
        matched_user_allergies = [a for a in contained_allergy_names if a in my_allergies]

        if matched_user_allergies:
            alert_tag = f'<span class="allergy-badge">🚨 {",".join(matched_user_allergies)}</span>'
            rendered_lines.append(f'<div class="allergy-alert">{safe_line} {alert_tag}</div>')
        else:
            rendered_lines.append(f'<div>{safe_line}</div>')

    return "".join(rendered_lines)

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
# 6. 메인 화면 타이틀 및 상단 컨트롤
# -----------------------------------------------------------------------------
st.title("🍱 우리 학교 급식 달력")

now = datetime.now()

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

                    # 알레르기 강조 적용
                    dish_html = format_dish_with_allergy(meal["dish"], convert_allergy, user_allergies)

                    cal_badge = f'<span class="cal-badge">{html.escape(meal["cal"])}</span>' if meal.get("cal") else ""
                    safe_ntr = format_nutrition_info(meal.get("ntr", ""))

                    inner_html += f"""
                    <div class="meal-title-container">
                        <span class="meal-title {color_class}">▶ {m_type}</span>
                        {cal_badge}
                    </div>
                    <div class="meal-content">{dish_html}</div>
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

        monday = st.session_state.week_anchor
        week_days = [monday + timedelta(days=i) for i in range(5)]

        st.subheader(f"🗓️ {monday.strftime('%Y년 %m월 %d일')} ~ {(monday + timedelta(days=4)).strftime('%m월 %d일')} 급식")

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
