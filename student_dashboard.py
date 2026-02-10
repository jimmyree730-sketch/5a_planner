import streamlit as st
import pandas as pd
import datetime
import calendar
import sqlite3

# -----------------------------------------------------------------------------
# 1. 시스템 설정 (DB 연결 준비)
# -----------------------------------------------------------------------------
DB_NAME = "5a_planner_v5_fix.db"

def get_db_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

# -----------------------------------------------------------------------------
# 2. 메인 실행 함수 (이름을 show_student로 맞춰야 main.py와 연결됩니다!)
# -----------------------------------------------------------------------------
def show_student():
    # 로그인 정보 확인
    if 'user' not in st.session_state:
        st.error("로그인 정보가 없습니다.")
        return
        
    user = st.session_state['user']
    
    # 상단 헤더
    c1, c2 = st.columns([8, 2])
    with c1: st.markdown(f"### 👋 반가워요, **{user['real_name']}** 학생!")
    with c2: 
        if st.button("로그아웃"):
            st.session_state.clear()
            st.rerun()

    # 3단 탭 구조 (대표님 원래 로직 유지)
    tab1, tab2, tab3 = st.tabs(["📅 계획 세우기", "✅ 오늘 할 일", "🗓️ 월간 전체보기"])
    
    # [Tab 1] 계획 수립
    with tab1:
        st.info("💡 학습할 기간과 내용을 입력하세요.")
        with st.form("plan_form"):
            c_d1, c_d2 = st.columns(2)
            start_d = c_d1.date_input("시작일", datetime.date.today())
            end_d = c_d2.date_input("종료일", datetime.date.today())
            subject = st.text_input("과목", "수학")
            content = st.text_input("내용", "p.10 ~ p.20")
            
            days = ["월", "화", "수", "목", "금", "토", "일"]
            selected_days = st.multiselect("요일 선택", days, default=days[:5])
            
            if st.form_submit_button("계획 저장"):
                week_map = {d: i for i, d in enumerate(days)}
                target_idx = [week_map[d] for d in selected_days]
                curr = start_d
                cnt = 0
                with get_db_connection() as conn:
                    while curr <= end_d:
                        if curr.weekday() in target_idx:
                            conn.execute("INSERT INTO daily_plans (user_id, plan_date, subject, content) VALUES (?,?,?,?)",
                                         (user['id'], curr, subject, content))
                            cnt += 1
                        curr += datetime.timedelta(days=1)
                    conn.commit()
                st.success(f"{cnt}일치 저장 완료!")

    # [Tab 2] 오늘 할 일 (각오 - 학습 - 평가 시스템)
    with tab2:
        # 1. [DB 무결성 확보] 일일 기록장 테이블이 없으면 자동 생성 (Defensive Coding)
        with get_db_connection() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS daily_logs 
                           (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                            user_id INTEGER, 
                            log_date DATE, 
                            resolution TEXT, 
                            review TEXT, 
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
            conn.commit()

        # 2. 날짜 선택 및 데이터 로딩
        col_date, col_head = st.columns([1, 2])
        target_date = col_date.date_input("날짜 확인", datetime.date.today())
        
        # 해당 날짜의 각오/평가 데이터 가져오기
        log_data = {'resolution': "", 'review': ""}
        with get_db_connection() as conn:
            log_row = conn.execute("SELECT resolution, review FROM daily_logs WHERE user_id=? AND log_date=?", (user['id'], target_date)).fetchone()
            if log_row:
                log_data['resolution'] = log_row[0] if log_row[0] else ""
                log_data['review'] = log_row[1] if log_row[1] else ""

        # --- [SECTION 1] 상단: 오늘의 각오 ---
        st.markdown("### 🌅 오늘의 각오")
        with st.form("resolution_form"):
            resolution_input = st.text_area("시작이 반이다! 오늘의 마음가짐을 단단히 하세요.", 
                                          value=log_data['resolution'], 
                                          height=80, 
                                          placeholder="예: 오늘은 수학 문제를 풀 때 절대 답지를 보지 않겠다!")
            
            # (UI 깔끔하게) 각오만 저장하는 버튼
            if st.form_submit_button("🔥 각오 다지기"):
                with get_db_connection() as conn:
                    # 데이터가 있는지 확인 후 UPDATE 혹은 INSERT (UPSERT 로직)
                    exist = conn.execute("SELECT id FROM daily_logs WHERE user_id=? AND log_date=?", (user['id'], target_date)).fetchone()
                    if exist:
                        conn.execute("UPDATE daily_logs SET resolution=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (resolution_input, exist[0]))
                    else:
                        conn.execute("INSERT INTO daily_logs (user_id, log_date, resolution) VALUES (?,?,?)", (user['id'], target_date, resolution_input))
                    conn.commit()
                st.success("각오가 저장되었습니다! 오늘도 파이팅!")
                st.rerun()

        st.markdown("---")

        # --- [SECTION 2] 중단: 학습 계획 및 수행 체크 ---
        st.markdown(f"### 📝 {target_date.strftime('%m월 %d일')} 학습 리스트")
        
        with get_db_connection() as conn:
            plans = pd.read_sql("SELECT * FROM daily_plans WHERE user_id=? AND plan_date=?", conn, params=(user['id'], target_date))
        
        if plans.empty:
            st.info("📅 등록된 일정이 없습니다. '계획 세우기' 탭에서 계획을 추가해주세요.")
        else:
            for _, r in plans.iterrows():
                with st.container(border=True):
                    c_txt, c_val = st.columns([7,3])
                    c_txt.markdown(f"**[{r['subject']}]** {r['content']}")
                    val = c_val.slider("성취도", 0, 100, r['achievement'], key=f"s_{r['id']}")
                    if val != r['achievement']:
                        with get_db_connection() as conn:
                            conn.execute("UPDATE daily_plans SET achievement=? WHERE id=?", (val, r['id']))
                            conn.commit()
                        st.rerun()

        st.markdown("---")

        # --- [SECTION 3] 하단: 하루 마무리 평가 ---
        st.markdown("### 🌙 하루 평가 (메타인지)")
        with st.form("review_form"):
            review_input = st.text_area("오늘 하루를 되돌아보며 부족했던 점과 잘한 점을 기록하세요.", 
                                      value=log_data['review'], 
                                      height=150, 
                                      placeholder="자기평가를 통해 메타인지를 끌어올리세요") # 요청하신 워터마크 적용
            
            if st.form_submit_button("💾 평가 제출하기"):
                with get_db_connection() as conn:
                    exist = conn.execute("SELECT id FROM daily_logs WHERE user_id=? AND log_date=?", (user['id'], target_date)).fetchone()
                    if exist:
                        conn.execute("UPDATE daily_logs SET review=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (review_input, exist[0]))
                    else:
                        # 각오 없이 평가만 먼저 쓰는 경우 대비
                        conn.execute("INSERT INTO daily_logs (user_id, log_date, review) VALUES (?,?,?)", (user['id'], target_date, review_input))
                    conn.commit()
                st.success("오늘 하루도 정말 고생 많으셨습니다! 👏")
                st.rerun()

    # [Tab 3] 월간 캘린더 (하이브리드 뷰)
    with tab3:
        st.markdown("### 🗓️ 이번 달 학습 흐름")
        today = datetime.date.today()
        year, month = today.year, today.month
        
        with get_db_connection() as conn:
            # SQL 쿼리 최적화 (날짜 포맷 맞춤)
            start = f"{year}-{month:02d}-01"
            if month == 12:
                end = f"{year+1}-01-01"
            else:
                end = f"{year}-{month+1:02d}-01"
                
            plans = pd.read_sql(f"SELECT plan_date, achievement FROM daily_plans WHERE user_id=? AND plan_date >= '{start}' AND plan_date < '{end}'", conn, params=(user['id'],))
        
        # 캘린더 표시 로직
        status_map = {}
        for _, r in plans.iterrows():
            d_str = str(r['plan_date'])
            # 기존 로직 유지 (100점이면 full, 아니면 plan)
            if d_str not in status_map or status_map[d_str] != "full":
                status_map[d_str] = "full" if r['achievement'] == 100 else "plan"

        cal = calendar.monthcalendar(year, month)
        cols = st.columns(7)
        for i, d in enumerate(["월","화","수","목","금","토","일"]): 
            cols[i].markdown(f"<div style='text-align:center; font-weight:bold'>{d}</div>", unsafe_allow_html=True)
        
        for week in cal:
            cols = st.columns(7)
            for i, day in enumerate(week):
                if day != 0:
                    d_str = f"{year}-{month:02d}-{day:02d}"
                    status = status_map.get(d_str, "none")
                    mark = "🟢" if status == "full" else ("🔵" if status == "plan" else "⚪")
                    cols[i].markdown(f"<div style='text-align:center; padding:10px; border-radius:10px; background-color:white; margin:2px;'>{day}<br>{mark}</div>", unsafe_allow_html=True)