# -----------------------------------------------------------------------------
# 8. 한 달 달력 생성 및 메인 화면 구성
# -----------------------------------------------------------------------------
try:
    # 해당 월의 주차별 달력 배열 생성 (월요일 시작=0)
    month_cal = calendar.monthcalendar(selected_year, selected_month)
    weekdays_name = ["월", "화", "수", "목", "금"]

    # 오늘 날짜 확인
    today_str = now.strftime("%Y%m%d")

    # 주 단위 레이아웃 반복
    for week in month_cal:
        # 월~금(0~4) 데이터만 필터링 (주말 토·일 제외)
        workdays = week[:5]
        
        # 날짜가 하루라도 존재하는 주차만 화면에 출력
        if any(day != 0 for day in workdays):
            cols = st.columns(5)
            
            for idx, day in enumerate(workdays):
                with cols[idx]:
                    if day == 0:
                        st.write("")
                        continue

                    # 날짜 키 생성 (YYYYMMDD)
                    current_ymd = f"{selected_year}{selected_month:02d}{day:02d}"
                    is_today = (current_ymd == today_str)

                    card_class = "meal-card today-card" if is_today else "meal-card"
                    today_badge_html = '<span class="today-badge">TODAY</span>' if is_today else ""
                    
                    # 카드 헤더 HTML
                    inner_html = f"""
                    <div class="date-header">
                        <span>{day}일 ({weekdays_name[idx]})</span>
                        {today_badge_html}
                    </div>
                    """

                    # 해당 날짜 급식 정보 파싱
                    day_meals = meal_data.get(current_ymd, [])

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
                                dish_html = formatted_dish.replace("\n", "<br/>")

                                inner_html += f"""
                                <div class="meal-title {color_class}">▶ {m_type}</div>
                                <div class="meal-content">{dish_html}</div>
                                """

                    # 단일 div 카드 태그로 감싸서 안전하게 출력
                    full_card_html = f'<div class="{card_class}">{inner_html}</div>'
                    st.markdown(full_card_html, unsafe_allow_html=True)

except Exception as e:
    st.error(f"🎨 화면 구성 중 예외가 발생했습니다: {e}")
