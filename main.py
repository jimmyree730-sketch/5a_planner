import streamlit as st
import sqlite3
import pandas as pd
import time
import random       # [추가] 랜덤 데이터 생성용
import datetime     # [추가] 날짜 계산용

# [중요] 다른 파일들을 가져옵니다.
import admin_app
import student_dashboard

# -----------------------------------------------------------------------------
# 1. 시스템 설정
# -----------------------------------------------------------------------------
st.set_page_config(page_title="5A PLANNER", layout="wide")

DB_NAME = "5a_planner_v5_fix.db"
COLOR_PRIMARY = "#007AFF"
COLOR_BG = "#F5F5F7"

# -----------------------------------------------------------------------------
# 2. 헬퍼 함수
# -----------------------------------------------------------------------------
def inject_custom_css():
    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap');
    html, body, [class*="css"] {{ font-family: 'Noto Sans KR', sans-serif; background-color: {COLOR_BG}; }}
    div.stButton > button {{ width: 100%; border-radius: 8px; font-weight: bold; height: 50px; }}
    div.stButton > button:hover {{ border-color: {COLOR_PRIMARY}; color: {COLOR_PRIMARY}; }}
    </style>
    """, unsafe_allow_html=True)

def get_db_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

def init_db():
    """시스템 필수 테이블 및 [더미 데이터] 자동 생성"""
    with get_db_connection() as conn:
        c = conn.cursor()
        
        # 1. 테이블 생성
        c.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT, role TEXT, real_name TEXT, group_color TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        c.execute('''CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, from_id INTEGER, to_id INTEGER, message TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        c.execute('''CREATE TABLE IF NOT EXISTS daily_plans (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, plan_date DATE, subject TEXT, content TEXT, achievement INTEGER DEFAULT 0)''')
        conn.commit()
        
        # 2. 관리자 계정 생성
        admin = c.execute("SELECT * FROM users WHERE role='admin'").fetchone()
        if not admin:
            c.execute("INSERT INTO users (username, password, role, real_name) VALUES (?,?,?,?)", ("admin", "1234", "admin", "총괄 관리자"))
            
        # 3. [핵심] 학생 데이터가 없으면 30명 자동 생성!
        student_count = c.execute("SELECT count(*) FROM users WHERE role='student'").fetchone()[0]
        if student_count == 0:
            colors = ["BLUE"] * 10 + ["YELLOW"] * 10 + ["RED"] * 10
            subjects = ["국어", "영어", "수학", "탐구"]
            today = datetime.date.today()
            
            for i in range(30):
                # 학생 계정 생성 (s01 ~ s30)
                uid = f"s{i+1:02d}"
                name = f"학생{i+1}"
                c.execute("INSERT INTO users (username, password, role, real_name, group_color) VALUES (?, '1234', 'student', ?, ?)", (uid, name, colors[i]))
                user_id = c.lastrowid
                
                # 가짜 성적 데이터 생성 (최근 45일치)
                base_score = random.randint(40, 95)
                for day_offset in range(45):
                    past_date = today - datetime.timedelta(days=45-day_offset)
                    # 주말은 랜덤하게 스킵
                    if past_date.weekday() >= 5 and random.random() < 0.5: continue
                    
                    # 하루에 2~3과목 공부
                    daily_subjs = random.sample(subjects, random.randint(2, 3))
                    for subj in daily_subjs:
                        score = max(0, min(100, base_score + random.randint(-15, 15)))
                        content = f"{subj} 필수 학습 ({random.randint(10,50)}p)"
                        c.execute("INSERT INTO daily_plans (user_id, plan_date, subject, content, achievement) VALUES (?,?,?,?,?)", 
                                  (user_id, past_date, subj, content, score))
            conn.commit()

# -----------------------------------------------------------------------------
# 3. 메인 실행 함수
# -----------------------------------------------------------------------------
def main():
    inject_custom_css()
    init_db() # 여기서 데이터가 없으면 자동으로 채워넣음!
    
    if 'user' not in st.session_state:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown(f"<h1 style='text-align:center; color:{COLOR_PRIMARY};'>5A PLANNER</h1>", unsafe_allow_html=True)
            
            tab_login, tab_signup = st.tabs(["🔑 로그인", "📝 회원가입 (신규)"])
            
            with tab_login:
                with st.container(border=True):
                    uid = st.text_input("아이디", key="login_id")
                    upw = st.text_input("비밀번호", type="password", key="login_pw")
                    if st.button("로그인", use_container_width=True):
                        with get_db_connection() as conn:
                            user = conn.execute("SELECT id, role, real_name FROM users WHERE username=? AND password=?", (uid, upw)).fetchone()
                        if user:
                            if user[1] == 'pending':
                                st.warning(f"⏳ '{user[2]}'님은 가입 승인 대기 중입니다.")
                            else:
                                st.session_state['user'] = {'id':user[0], 'role':user[1], 'real_name':user[2]}
                                st.success(f"{user[2]}님 환영합니다!")
                                st.rerun()
                        else:
                            st.error("아이디 또는 비밀번호가 일치하지 않습니다.")

            with tab_signup:
                with st.container(border=True):
                    st.markdown("### 신규 회원가입 신청")
                    new_id = st.text_input("희망 아이디", key="new_id")
                    new_pw = st.text_input("희망 비밀번호", type="password", key="new_pw")
                    new_name = st.text_input("실명 (이름)", key="new_name")
                    if st.button("가입 신청하기", use_container_width=True):
                        if new_id and new_pw and new_name:
                            with get_db_connection() as conn:
                                try:
                                    exist = conn.execute("SELECT count(*) FROM users WHERE username=?", (new_id,)).fetchone()[0]
                                    if exist > 0: st.error("이미 존재하는 아이디입니다.")
                                    else:
                                        conn.execute("INSERT INTO users (username, password, real_name, role) VALUES (?, ?, ?, 'pending')", (new_id, new_pw, new_name))
                                        conn.commit()
                                        st.success(f"✅ '{new_name}'님 가입 신청 완료!")
                                except Exception as e: st.error(f"오류: {e}")
                        else: st.warning("정보를 입력하세요.")

    else:
        if st.session_state['user']['role'] == 'admin':
            admin_app.show_admin()
        else:
            student_dashboard.show_student()

if __name__ == "__main__":
    main()