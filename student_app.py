import streamlit as st
import sqlite3
import pandas as pd
import datetime
import calendar

# -----------------------------------------------------------------------------
# 1. 시스템 설정
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="5A PLANNER",
    page_icon="📘",
    layout="centered",
    initial_sidebar_state="collapsed"
)

DB_NAME = "5a_planner_v3_test.db"
COLOR_PRIMARY = "#007AFF"
COLOR_BG = "#F5F5F7"
COLOR_MY_MSG = "#007AFF"
COLOR_OTHER_MSG = "#E5E5EA"

# -----------------------------------------------------------------------------
# 2. UI/UX (태블릿 최적화 스타일)
# -----------------------------------------------------------------------------
def inject_custom_css():
    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap');
    html, body, [class*="css"] {{ font-family: 'Noto Sans KR', sans-serif; background-color: {COLOR_BG}; }}
    
    /* 버튼 및 탭 크기 확대 (터치 최적화) */
    div.stButton > button {{ 
        width: 100%; min-height: 55px; border-radius: 12px; 
        font-weight: 600; border: none; background-color: {COLOR_PRIMARY}; color: white; 
        font-size: 16px; box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }}
    .stTabs [data-baseweb="tab-list"] {{ gap: 8px; }}
    .stTabs [data-baseweb="tab"] {{ 
        height: 55px; border-radius: 10px; background-color: white; 
        flex: 1; font-size: 16px;
    }}
    
    /* 채팅창 스타일 */
    .chat-container {{ display: flex; flex-direction: column; gap: 10px; margin-bottom: 20px; max-height: 400px; overflow-y: auto; }}
    .msg-bubble {{ padding: 12px 16px; border-radius: 12px; max-width: 80%; font-size: 14px; line-height: 1.5; }}
    .msg-me {{ align_self: flex-end; background-color: {COLOR_MY_MSG}; color: white; }}
    .msg-other {{ align_self: flex-start; background-color: {COLOR_OTHER_MSG}; color: black; }}
    </style>
    """, unsafe_allow_html=True)

def get_db_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

# [방어 코드] 테이블이 없으면 생성
def init_db():
    with get_db_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE, password TEXT, role TEXT, real_name TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER, plan_date DATE, subject TEXT, content TEXT, 
                achievement INTEGER DEFAULT 0, linked_monthly_id INTEGER
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS monthly_goals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER, year_month TEXT, subject TEXT, content TEXT, 
                total_amount INTEGER, week_days TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_id INTEGER, to_id INTEGER, message TEXT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

# -----------------------------------------------------------------------------
# 3. 핵심 로직 함수 (N분배 & 범위 지정)
# -----------------------------------------------------------------------------
def distribute_monthly_plan(user_id, year, month, subject, content, start_page, end_page, selected_days):
    _, last_day = calendar.monthrange(year, month)
    target_dates = []
    
    # 1. 날짜 필터링
    for day in range(1, last_day + 1):
        date_obj = datetime.date(year, month, day)
        if date_obj >= datetime.date.today() and date_obj.weekday() in selected_days:
            target_dates.append(date_obj)
    
    if not target_dates: return False, "선택한 요일이 남은 기간에 없습니다."
    
    # 2. 페이지 분배 계산
    total_amount = end_page - start_page + 1
    if total_amount <= 0: return False, "종료 페이지가 시작 페이지보다 커야 합니다."

    daily_amount = total_amount // len(target_dates)
    remainder = total_amount % len(target_dates)
    
    with get_db_connection() as conn:
        cur = conn.cursor()
        days_str = ",".join(map(str, selected_days))
        
        # 월간 목표 등록
        cur.execute("INSERT INTO monthly_goals (user_id, year_month, subject, content, total_amount, week_days) VALUES (?,?,?,?,?,?)", 
                   (user_id, f"{year}-{month:02d}", subject, content, total_amount, days_str))
        monthly_id = cur.lastrowid
        
        # 일간 계획 생성
        current_page = start_page
        for i, p_date in enumerate(target_dates):
            amount = daily_amount + (1 if i < remainder else 0)
            range_start = current_page
            range_end = current_page + amount - 1
            current_page += amount
            
            plan_text = f"{content} (p.{range_start}~p.{range_end})"
            cur.execute("INSERT INTO daily_plans (user_id, plan_date, subject, content, linked_monthly_id) VALUES (?,?,?,?,?)", 
                       (user_id, p_date, subject, plan_text, monthly_id))
        conn.commit()
    return True, f"총 {len(target_dates)}일 동안 p.{start_page}부터 p.{end_page}까지 분배 완료!"

def render_chat(user_id, other_id):
    with get_db_connection() as conn:
        msgs = pd.read_sql("SELECT * FROM messages WHERE (from_id=? AND to_id=?) OR (from_id=? AND to_id=?) ORDER BY created_at ASC", conn, params=(user_id, other_id, other_id, user_id))
    if msgs.empty: st.info("메시지 내역 없음")
    else:
        chat_html = '<div class="chat-container">'
        for _, row in msgs.iterrows():
            cls = "msg-me" if row['from_id'] == user_id else "msg-other"
            chat_html += f'<div class="msg-bubble {cls}">{row["message"]}</div>'
        chat_html += '</div>'
        st.markdown(chat_html, unsafe_allow_html=True)
# [이 함수를 student_dashboard 함수보다 위쪽에 붙여넣으세요]

def distribute_period_plan(user_id, subject, content, start_page, end_page, start_date, end_date, selected_days):
    # 1. 기간 내 유효 날짜 추출
    target_dates = []
    current_date = start_date
    
    # 시작일부터 종료일까지 하루씩 넘기며 요일 체크
    while current_date <= end_date:
        if current_date.weekday() in selected_days:
            target_dates.append(current_date)
        current_date += datetime.timedelta(days=1)
    
    if not target_dates: return False, "설정하신 기간 내에 선택한 요일이 없습니다."
    
    # 2. 페이지 분배 계산
    total_amount = end_page - start_page + 1
    if total_amount <= 0: return False, "종료 페이지가 시작 페이지보다 커야 합니다."

    daily_amount = total_amount // len(target_dates)
    remainder = total_amount % len(target_dates)
    
    with get_db_connection() as conn:
        cur = conn.cursor()
        days_str = ",".join(map(str, selected_days))
        period_str = f"{start_date}~{end_date}"
        
        # 목표 등록
        cur.execute("INSERT INTO monthly_goals (user_id, year_month, subject, content, total_amount, week_days) VALUES (?,?,?,?,?,?)", 
                   (user_id, period_str, subject, content, total_amount, days_str))
        monthly_id = cur.lastrowid
        
        # 일간 계획 생성 (N분배)
        current_page = start_page
        for i, p_date in enumerate(target_dates):
            amount = daily_amount + (1 if i < remainder else 0)
            range_end = current_page + amount - 1
            
            plan_text = f"{content} (p.{current_page}~p.{range_end})"
            cur.execute("INSERT INTO daily_plans (user_id, plan_date, subject, content, linked_monthly_id) VALUES (?,?,?,?,?)", 
                       (user_id, p_date, subject, plan_text, monthly_id))
            
            current_page += amount # 다음 페이지 갱신
            
        conn.commit()
    return True, f"총 {len(target_dates)}일 동안 p.{start_page}~p.{end_page} 계획 생성 완료!"
# -----------------------------------------------------------------------------
# 4. 학생 대시보드 화면 (3단 탭 구성)
# -----------------------------------------------------------------------------
def student_dashboard():
    user = st.session_state['user']
    st.markdown(f"### 👋 {user['real_name']} 학생")
    
    if st.button("로그아웃"):
        del st.session_state['user']; st.rerun()
        
  # [수정됨] 탭 확장: 계획 세우기 / 오늘 할 일 / 월간 전체보기
    tab1, tab2, tab3 = st.tabs(["📅 계획 세우기", "✅ 오늘 할 일", "🗓️ 월간 전체보기"])
    
    # --- [TAB 1] 스마트 계획 수립 (기간 설정 적용) ---
    with tab1:
        st.info("교재, 범위, 기간을 설정하면 AI가 요일에 맞춰 자동으로 계획을 짜줍니다.")
        with st.container(border=True):
            with st.form("smart_plan_form"):
                subject = st.selectbox("과목", ["수학", "국어", "영어", "탐구", "기타"])
                content = st.text_input("교재명", placeholder="예: 수능완성")
                
                # 1. 페이지 범위
                col_p1, col_p2 = st.columns(2)
                with col_p1: start_p = st.number_input("시작 페이지", min_value=1, value=1)
                with col_p2: end_p = st.number_input("종료 페이지", min_value=1, value=100)
                
                # 2. [신규 기능] 기간 설정
                st.write("📅 **학습 기간 설정**")
                col_d1, col_d2 = st.columns(2)
                with col_d1: 
                    start_date = st.date_input("시작일", datetime.date.today())
                with col_d2: 
                    # 기본값: 오늘로부터 30일 뒤
                    default_end = datetime.date.today() + datetime.timedelta(days=30)
                    end_date = st.date_input("종료일", default_end)

                # 3. 요일 선택
                days_kor = ["월", "화", "수", "목", "금", "토", "일"]
                selected_days = st.multiselect("학습 요일 선택", days_kor, default=["월", "수", "금"])
                
                submitted = st.form_submit_button("🚀 AI 자동 배분 실행")

                if submitted:
                    if not selected_days: 
                        st.error("최소 하루 이상의 요일을 선택해주세요.")
                    elif start_p > end_p: 
                        st.error("종료 페이지가 시작 페이지보다 작을 수 없습니다.")
                    elif start_date > end_date:
                        st.error("종료일이 시작일보다 빠를 수 없습니다.")
                    else:
                        # 요일 인덱스 변환
                        indices = [days_kor.index(d) for d in selected_days]
                        
                        # [함수 호출] 새로 만든 기간 배분 함수 사용
                        success, msg = distribute_period_plan(
                            user['id'], subject, content, 
                            start_p, end_p, start_date, end_date, indices
                        )
                        
                        if success: 
                            st.success(msg)
                            st.balloons()
                            # 2초 뒤 리로드는 사용자가 메시지를 못 볼 수 있으니 생략하거나 st.rerun()을 버튼 밖에서 처리
                        else: 
                            st.error(msg)

    # --- [TAB 2] 오늘의 할 일 체크 & 수정 (통합 버전) ---
    with tab2:
        # 1. 상단 컨트롤러 (날짜 선택 + 수정 모드 토글)
        c_date, c_mode = st.columns([2, 1])
        with c_date:
            target_date = st.date_input("📅 날짜 선택", datetime.date.today())
        with c_mode:
            # [핵심] 수정 모드 스위치
            is_edit_mode = st.toggle("🔧 수정 모드")

        # 2. 헤더 및 데이터 조회
        today = datetime.date.today()
        day_str = ["(월)", "(화)", "(수)", "(목)", "(금)", "(토)", "(일)"][target_date.weekday()]
        is_future = target_date > today

        if target_date == today:
            st.markdown(f"### 🔥 **{target_date} {day_str} 오늘**")
        elif is_future:
            st.markdown(f"### 🔭 **{target_date} {day_str} 예습**")
        else:
            st.markdown(f"### ⏪ **{target_date} {day_str} 복습**")

        with get_db_connection() as conn:
            plans = pd.read_sql("SELECT * FROM daily_plans WHERE user_id=? AND plan_date=?", conn, params=(user['id'], target_date))
        
        if plans.empty: 
            st.info("등록된 일정이 없습니다.")
        else:
            # 프로그레스 바 (평소에만 보임)
            if not is_edit_mode and not is_future:
                done_cnt = len(plans[plans['achievement']==100])
                progress = done_cnt / len(plans) if len(plans) > 0 else 0
                st.progress(progress, text=f"달성률: {int(progress*100)}%")

            # 3. 리스트 출력 (수정 모드에 따라 UI가 변신)
            for _, r in plans.iterrows():
                with st.container(border=True):
                    if is_edit_mode:
                        # [수정 모드 ON] : 입력창과 삭제 버튼 등장
                        col_input, col_btn = st.columns([8, 2])
                        with col_input:
                            new_subject = st.selectbox("과목", ["국어", "수학", "영어", "탐구", "기타"], index=["국어", "수학", "영어", "탐구", "기타"].index(r['subject']) if r['subject'] in ["국어", "수학", "영어", "탐구", "기타"] else 0, key=f"subj_{r['id']}")
                            new_content = st.text_input("내용", value=r['content'], key=f"cont_{r['id']}")
                        
                        with col_btn:
                            st.write("") # 줄맞춤용
                            st.write("")
                            if st.button("🗑️", key=f"del_{r['id']}", help="이 계획 삭제"):
                                with get_db_connection() as conn:
                                    conn.execute("DELETE FROM daily_plans WHERE id=?", (r['id'],))
                                    conn.commit()
                                st.rerun()

                        # 변경사항 자동 감지 및 업데이트
                        if new_subject != r['subject'] or new_content != r['content']:
                            with get_db_connection() as conn:
                                conn.execute("UPDATE daily_plans SET subject=?, content=? WHERE id=?", (new_subject, new_content, r['id']))
                                conn.commit()
                            # 즉시 리런하지 않고, 사용자가 입력을 마칠 때 자연스럽게 반영되도록 둠 (또는 버튼 추가 가능)
                            
                    else:
                        # [수정 모드 OFF] : 깔끔한 보기 모드 (기존 유지)
                        c_txt, c_val = st.columns([7,3])
                        with c_txt: 
                            st.markdown(f"**[{r['subject']}]** {r['content']}")
                        with c_val:
                            val = st.slider("성취도", 0, 100, r['achievement'], step=25, key=f"s_{r['id']}", label_visibility="collapsed", disabled=is_future)
                            if val != r['achievement'] and not is_future:
                                with get_db_connection() as conn:
                                    conn.execute("UPDATE daily_plans SET achievement=? WHERE id=?", (val, r['id']))
                                    conn.commit()
                                st.rerun()
# --- [TAB 3] 월간 전체보기 (하이브리드: 캘린더 + 상세 카드) ---
    with tab3:
        # =========================================================
        # [SECTION A] 월간 히트맵 (전체 흐름 파악)
        # =========================================================
        st.markdown("### 🗓️ 이번 달 학습 흐름")
        st.caption("🔵 계획 있음 / 🟢 완료함 / ⚪ 휴식")
        
        today = datetime.date.today()
        year = today.year
        month = today.month
        
        with get_db_connection() as conn:
            start_date = f"{year}-{month:02d}-01"
            if month == 12: end_date = f"{year+1}-01-01"
            else: end_date = f"{year}-{month+1:02d}-01"
            
            monthly_plans = pd.read_sql(f"SELECT plan_date, achievement FROM daily_plans WHERE user_id=? AND plan_date >= '{start_date}' AND plan_date < '{end_date}'", conn, params=(user['id'],))
        
        status_map = {}
        for _, r in monthly_plans.iterrows():
            d_str = str(r['plan_date'])
            if status_map.get(d_str) == "full": continue
            status_map[d_str] = "full" if r['achievement'] == 100 else "plan"

        cal = calendar.monthcalendar(year, month)
        cols = st.columns(7)
        days = ["월", "화", "수", "목", "금", "토", "일"]
        for i, d in enumerate(days):
            cols[i].markdown(f"<div style='text-align:center; color:gray; font-size:12px;'>{d}</div>", unsafe_allow_html=True)
        
        st.markdown("---")
        
        for week in cal:
            cols = st.columns(7)
            for i, day in enumerate(week):
                if day != 0:
                    d_str = f"{year}-{month:02d}-{day:02d}"
                    status = status_map.get(d_str, "none")
                    mark = "🟢" if status == "full" else ("🔵" if status == "plan" else "⚪")
                    day_disp = f"**{day}**" if day == today.day else f"{day}"
                    
                    cols[i].markdown(f"""
                        <div style='text-align:center; line-height:1.2; margin-bottom:5px;'>
                            <div style='font-size:14px;'>{day_disp}</div>
                            <div style='font-size:12px;'>{mark}</div>
                        </div>
                    """, unsafe_allow_html=True)

        st.markdown("---")

        # =========================================================
        # [SECTION B] 일별 상세 카드 (스크린샷 스타일 적용)
        # =========================================================
        st.subheader("📌 학습 상세 미리보기")
        
        # 1. 날짜 선택기 (기본값: 오늘)
        c_sel, c_empty = st.columns([1, 2])
        with c_sel:
            view_date = st.date_input("확인하고 싶은 날짜를 선택하세요", today, key="view_date")
        
        # 2. 선택한 날짜 데이터 조회
        with get_db_connection() as conn:
            daily_view = pd.read_sql("SELECT subject, content, achievement FROM daily_plans WHERE user_id=? AND plan_date=?", conn, params=(user['id'], view_date))
        
        # 3. 카드 렌더링
        if daily_view.empty:
            st.info(f"{view_date}에는 등록된 계획이 없습니다. 푹 쉬세요! 🍵")
        else:
            days_kor = ["(월)", "(화)", "(수)", "(목)", "(금)", "(토)", "(일)"]
            day_label = days_kor[view_date.weekday()]
            st.markdown(f"##### **{view_date} {day_label} 계획 목록**")
            
            for _, row in daily_view.iterrows():
                # [디자인] 왼쪽 컬러바가 있는 카드 스타일 구현 (Markdown + CSS)
                # 성취도에 따라 색상 변경 (100%면 초록, 아니면 노랑/파랑)
                border_color = "#28a745" if row['achievement'] == 100 else "#ffc107" 
                
                st.markdown(f"""
                <div style="
                    border-left: 5px solid {border_color}; 
                    background-color: rgba(128, 128, 128, 0.1); 
                    padding: 15px; 
                    border-radius: 5px; 
                    margin-bottom: 10px;">
                    <div style="font-weight: bold; font-size: 16px; margin-bottom: 5px;">
                        {row['subject']}
                    </div>
                    <div style="font-size: 14px; margin-bottom: 8px;">
                        {row['content']}
                    </div>
                    <div style="font-size: 12px; color: gray;">
                        성취도: {row['achievement']}%
                    </div>
                </div>
                """, unsafe_allow_html=True)
        
        st.markdown("---")
        st.caption("🔵 계획 있음 / 🟢 완료함 / ⚪ 휴식")
    st.markdown("---")
    with st.container(border=True):
        st.markdown("##### 📬 선생님 메시지")
        render_chat(user['id'], 1)

# -----------------------------------------------------------------------------
# 5. 메인 실행
# -----------------------------------------------------------------------------
def main():
    inject_custom_css()
    init_db() # DB 초기화 확인
    
    if 'user' not in st.session_state:
        st.markdown("<br>", unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown(f"<h2 style='text-align:center; color:{COLOR_PRIMARY};'>학생용 로그인</h2>", unsafe_allow_html=True)
            uid = st.text_input("아이디")
            upw = st.text_input("비밀번호", type="password")
            if st.button("로그인"):
                with get_db_connection() as conn:
                    # role='student' 확인
                    user = conn.execute("SELECT id, role, real_name FROM users WHERE username=? AND password=?", (uid, upw)).fetchone()
                if user and user[1] == 'student':
                    st.session_state['user'] = {'id':user[0], 'role':user[1], 'real_name':user[2]}
                    st.rerun()
                else: st.error("학생 계정이 아니거나 정보가 틀렸습니다.")
    else:
        student_dashboard()

if __name__ == "__main__":
    main()