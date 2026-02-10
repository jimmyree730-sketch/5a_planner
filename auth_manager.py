import streamlit as st
import sqlite3
import pandas as pd
import datetime

# -----------------------------------------------------------------------------
# 1. DB 설정 및 연결 함수 (이 부분이 사라져서 에러가 났던 겁니다!)
# -----------------------------------------------------------------------------
DB_NAME = "5a_live.db"

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db_connection() as conn:
        # 학습 계획 테이블
        conn.execute('''
            CREATE TABLE IF NOT EXISTS daily_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                plan_date DATE,
                subject TEXT,
                content TEXT,
                achievement INTEGER DEFAULT 0
            )
        ''')
        # 사용자 테이블 (승인 대기 기능 포함)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                password TEXT NOT NULL,
                real_name TEXT NOT NULL,
                role TEXT DEFAULT 'student',
                approved INTEGER DEFAULT 0,
                joined_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()

# -----------------------------------------------------------------------------
# 2. 로그인 페이지 (모바일/태블릿 반응형 적용 완료)
# -----------------------------------------------------------------------------
def login_page():
    # 반응형 레이아웃 (좌우 여백을 주어 태블릿/PC에서 중앙 집중)
    c_left, c_center, c_right = st.columns([1, 2, 1])
    
    with c_center:
        st.title("📅 5A 월간플래너") 
        st.caption("목표 달성을 위한 스마트한 시작")
        
        with st.container(border=True):
            tab1, tab2 = st.tabs(["🔑 로그인", "📝 회원가입 신청"])
            
            # [TAB 1] 로그인
            with tab1:
                with st.form("login_form"):
                    st.markdown("##### 👋 학생 로그인")
                    login_id = st.text_input("아이디", placeholder="예: 5678김철수")
                    login_pw = st.text_input("비밀번호", type="password")
                    
                    # 모바일 터치 최적화 (버튼 꽉 채우기)
                    submit = st.form_submit_button("로그인", use_container_width=True)
                    
                    # [auth_manager.py -> login_page 함수 내부]

                    # 버튼 클릭 여부 확인
                    if submit:
                        # 1. 관리자 마스터 키 (줄 맞춤 주의: if와 with가 같은 라인에 있어야 함)
                        if login_id == "admin1234" and login_pw == "admin1234":
                            return {'id': 'admin1234', 'real_name': '관리자', 'role': 'admin', 'approved': 1}
                        
                        # 2. 학생 DB 조회
                        with get_db_connection() as conn:
                            user = pd.read_sql("SELECT * FROM users WHERE id=? AND password=?", 
                                            conn, params=(login_id, login_pw))
                        
                        # 3. 결과 처리
                        if not user.empty:
                            user_data = user.iloc[0]
                            if user_data['approved'] == 1:
                                return user_data.to_dict() 
                            else:
                                st.warning("⏳ 선생님 승인 대기 중입니다.")
                        else:
                            st.error("아이디 또는 비밀번호가 일치하지 않습니다.")
            
            # [TAB 2] 회원가입
            with tab2:
                st.info("학원생 인증을 위해 정보를 입력해주세요.")
                with st.form("signup_form"):
                    new_name = st.text_input("이름 (실명)", placeholder="홍길동")
                    new_id = st.text_input("아이디 (폰번호뒤4+이름)", placeholder="예: 5678홍길동")
                    new_pw = st.text_input("비밀번호 설정", type="password")
                    new_pw_chk = st.text_input("비밀번호 확인", type="password")
                    
                    if st.form_submit_button("가입 신청하기", use_container_width=True):
                        if new_pw != new_pw_chk:
                            st.error("비밀번호가 일치하지 않습니다.")
                        elif new_name and new_id and new_pw:
                            try:
                                with get_db_connection() as conn:
                                    conn.execute("INSERT INTO users (id, password, real_name, approved) VALUES (?, ?, ?, 0)",
                                                (new_id, new_pw, new_name))
                                    conn.commit()
                                st.success("✅ 신청 완료! 승인 대기 중입니다.")
                            except:
                                st.error("이미 존재하는 아이디입니다.")
    return None

# -----------------------------------------------------------------------------
# 3. 관리자 페이지
# -----------------------------------------------------------------------------
# [auth_manager.py] 파일의 기존 admin_page 함수를 이걸로 통째로 교체하세요!

# [auth_manager.py] 파일의 admin_page 함수 전체 교체

def admin_page():
    # 1. 상단 헤더 & 로그아웃
    c1, c2 = st.columns([8, 2])
    with c1: st.title("👨‍🏫 관리자 대시보드")
    with c2:
        if st.button("로그아웃", use_container_width=True):
            del st.session_state['user']
            st.rerun()

    # 2. 관리자 인증
    st.markdown("---")
    with st.expander("🔐 관리자 인증", expanded=True):
        pwd = st.text_input("관리자 비밀번호", type="password")
    
    if pwd != "admin1234":
        st.info("비밀번호를 입력하세요.")
        return

    # 3. 기능 분리 (탭 구조 도입)
    tab1, tab2 = st.tabs(["🆕 가입 승인 (대기중)", "👥 전체 학생 관리"])

    with get_db_connection() as conn:
        
        # --- [Tab 1] 가입 승인 ---
        with tab1:
            pending_users = pd.read_sql("SELECT id, real_name, joined_at FROM users WHERE approved=0", conn)
            
            if pending_users.empty:
                st.success("🎉 현재 승인 대기 중인 학생이 없습니다.")
            else:
                st.info(f"총 {len(pending_users)}명이 승인을 기다립니다.")
                if st.button("🚀 전원 승인하기", use_container_width=True):
                    conn.execute("UPDATE users SET approved=1 WHERE approved=0")
                    conn.commit()
                    st.rerun()
                
                for _, row in pending_users.iterrows():
                    with st.container(border=True):
                        c_a, c_b, c_c = st.columns([2, 2, 2])
                        c_a.write(f"**{row['real_name']}** ({row['id']})")
                        c_b.caption(str(row['joined_at'])[:16])
                        if c_c.button("승인", key=f"ok_{row['id']}", use_container_width=True):
                            conn.execute("UPDATE users SET approved=1 WHERE id=?", (row['id'],))
                            conn.commit()
                            st.rerun()

        # --- [Tab 2] 전체 학생 관리 (여기가 새로 추가된 부분!) ---
        with tab2:
            # 승인된(approved=1) 학생만 가져오기 (관리자 제외)
            active_users = pd.read_sql("SELECT id, real_name, joined_at FROM users WHERE approved=1 AND role='student'", conn)
            
            st.write(f"📚 현재 총 **{len(active_users)}명**의 학생이 학습 중입니다.")
            
            # 보기 좋게 표(DataFrame)로 보여주기
            if not active_users.empty:
                st.dataframe(active_users, use_container_width=True)
                
                st.markdown("---")
                st.subheader("🗑️ 학생 계정 삭제")
                col_del, col_btn = st.columns([3, 1])
                target_id = col_del.text_input("삭제할 학생 아이디 입력")
                if col_btn.button("삭제 실행", type="primary"):
                    conn.execute("DELETE FROM users WHERE id=?", (target_id,))
                    conn.commit()
                    st.warning(f"{target_id} 계정이 삭제되었습니다.")
                    st.rerun()