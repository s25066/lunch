import calendar
from datetime import datetime
import html
import requests
import streamlit as st

# -----------------------------------------------------------------------------
# 1. 페이지 기본 설정 및 스타일 정의
# -----------------------------------------------------------------------------
st.set_page_config(page_title="학교 급식 달력", page_icon="🍱", layout="wide")

# 카드 테두리 및 배지 스타일 정의 (CSS)
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
    .meal-title {
        font-weight: bold;
        margin-top: 6px;
        margin-bottom: 4px;
        font-size: 0.9em;
    }
    .lunch { color: #2b6cb0; }    /* 중식 - 파란색 */
    .dinner { color: #c53030; }   /* 석식 - 빨간색 */
    .other { color: #2f855a; }    /* 기타 - 초록색 */
    
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
    </style>
""",
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# 2. 알레르기 번호 매핑 사전 (1~19번)
# -----------------------------------------------------------------------------
ALLERGY_MAP = {
    "1": "난류",
    "2": "우유",
    "3": "메밀",
    "4": "땅콩",
    "5": "대두",
    "6": "밀",
    "7": "게",
    "8": "새우",
    "9": "돼지고기",
    "10": "복숭아",
    "11": "토마토",
    "12": "아황산류",
    "13": "호두",
    "14": "닭고기",
    "15": "쇠고기",
    "16": "오징어",
    "17": "조개류",
    "18": "잣",
    "19": "과일류(소고기/기타)",
}

# -----------------------------------------------------------------------------
# 3. 사이드바 구성
# -----------------------------------------------------------------------------
st.sidebar.title("⚙️ 설정")

if "NEIS_KEY" not in st.secrets:
    st.error("🔑 NEIS API 키가 설정되지 않았습니다.")
    st.info(
        "`.streamlit/secrets.toml` 파일에 `NEIS_KEY = \"발급받은키\"` 형태로 추가해 주세요."
    )
    st.stop()

neis_key = st.secrets["NEIS_KEY"]

atpt_code = st.sidebar.text_input(
    "시도교육청코드", value="B10", help="예: 서울(B10), 경기(J10) 등"
)
sd_code = st.sidebar.text_input(
    "표준학교코드", value="7010057", help="학교의 7자리 표준학교코드"
)

st.sidebar.markdown("---")
convert_allergy = st.sidebar.toggle("알레르기 식품명으로 변환", value=False)

with st.sidebar.expander("ℹ️ 알레르기 번호 표 보기"):
    allergy_text = "\n".join(
        [f"**{k}**: {v}" for k, v in ALLERGY_MAP.items()]
    )
    st.markdown(allergy_text)


# -----------------------------------------------------------------------------
# 4. 메뉴 텍스트 변환 함수
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
                    mapped_names = [
                        ALLERGY_MAP.get(num, num)
                        for num in nums
                        if num in ALLERGY_MAP
                    ]
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

                if ymd not in meal_by_date:
                    meal_by_date[ymd] = []
                meal_by_date[ymd].append(
                    {"type": meal_type, "dish": dish_name}
                )
            return meal_by_date, None

        elif "RESULT" in data and data["RESULT"]["CODE"] == "INFO-200":
            return {}, None
        else:
            err_msg = data.get("RESULT", {}).get(
                "MESSAGE", "알 수 없는 API 에러가 발생했습니다."
            )
            return None, f"API 오류: {err_msg}"

    except requests.exceptions.RequestException as e:
        return (
            None,
            f"통신 오류가 발생했습니다. 인터넷 연결이나 입력값을 확인해 주세요. ({e})",
        )


# -----------------------------------------------------------------------------
# 6. 상단 필터 컨트롤
# -----------------------------------------------------------------------------
st.title("🍱 우리 학교 월간 급식 달력")

now = datetime.now()
col1, col2, col3 = st.columns([1, 1, 2])

with col1:
    selected_year = st.selectbox(
        "연도 선택", range(now.year - 1, now.year + 2), index=1
    )

with col2:
    selected_month = st.selectbox("월 선택", range(1, 13), index=now.month - 1)

with col3:
    meal_filter = st.radio(
        "급식 종류",
        ["전체 보기", "중식만 보기", "석식만 보기"],
        horizontal=True,
    )

st.markdown("---")

# -----------------------------------------------------------------------------
# 7. 데이터 불러오기 및 예외 처리
# -----------------------------------------------------------------------------
meal_data, error = fetch_meal_data(
    neis_key, atpt_code, sd_code, selected_year, selected_month
)

if error:
    st.error(f"🚨 급식 정보를 가져오는데 실패했습니다: {error}")
    st.stop()

# -----------------------------------------------------------------------------
# 8. 한 달 달력 생성 및 메인 화면 구성
# -----------------------------------------------------------------------------
try:
    month_cal = calendar.monthcalendar(selected_year, selected_month)
    weekdays_name = ["월", "화", "수", "목", "금"]
    today_str = now.strftime("%Y%m%d")

    for week in month_cal:
        workdays = week[:5]

        if any(day != 0 for day in workdays):
            cols = st.columns(5)

            for idx, day in enumerate(workdays):
                with cols[idx]:
                    if day == 0:
                        st.write("")
                        continue

                    current_ymd = (
                        f"{selected_year}{selected_month:02d}{day:02d}"
                    )
                    is_today = current_ymd == today_str

                    card_class = (
                        "meal-card today-card" if is_today else "meal-card"
                    )
                    today_badge_html = (
                        '<span class="today-badge">TODAY</span>'
                        if is_today
                        else ""
                    )

                    inner_html = f"""<div class="date-header"><span>{day}일 ({weekdays_name[idx]})</span>{today_badge_html}</div>"""

                    day_meals = meal_data.get(current_ymd, [])

                    if not day_meals:
                        inner_html += '<div class="no-meal">급식 없음</div>'
                    else:
                        filtered_meals = []
                        for meal in day_meals:
                            if meal_filter == "전체 보기":
                                filtered_meals.append(meal)
                            elif (
                                meal_filter == "중식만 보기"
                                and meal["type"] == "중식"
                            ):
                                filtered_meals.append(meal)
                            elif (
                                meal_filter == "석식만 보기"
                                and meal["type"] == "석식"
                            ):
                                filtered_meals.append(meal)

                        if not filtered_meals:
                            inner_html += '<div class="no-meal">해당 식단 없음</div>'
                        else:
                            for meal in filtered_meals:
                                m_type = meal["type"]
                                color_class = (
                                    "lunch"
                                    if m_type == "중식"
                                    else ("dinner" if m_type == "석식" else "other")
                                )

                                formatted_dish = format_dish_name(
                                    meal["dish"], convert_allergy
                                )
                                # 메뉴 이름 부분만 안전하게 텍스트만 치환
                                safe_dish = html.escape(formatted_dish).replace(
                                    "\n", "<br/>"
                                )

                                inner_html += f"""<div class="meal-title {color_class}">▶ {m_type}</div><div class="meal-content">{safe_dish}</div>"""

                    # st.markdown 대신 st.html을 써서 Pure HTML로 통째로 렌더링
                    full_card = f"""<div class="{card_class}">{inner_html}</div>"""
                    st.html(full_card)

except Exception as ex:
    st.error(f"🎨 화면 구성 중 예외가 발생했습니다: {ex}")
