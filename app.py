import streamlit as st
import sqlite3
import pandas as pd
import datetime
import calendar

# [시스템 무결성] 라이브러리 체크
try:
    import plotly.graph_objects as go
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False

# -----------------------------------------------------------------------------
# 1. 시스템 설정 (관리자 전용)
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="5A ADMIN PRO",
    page_icon="👨‍🏫",
    layout="wide",
    initial_sidebar_state="expanded"
)

DB_NAME = "5a_planner_v3_test.db" # 기존 DB 공유
COLOR_PRIMARY = "#007AFF"
COLOR_BG = "#F5F5F7"
COLOR_MY_MSG = "#007AFF"
COLOR_OTHER_MSG = "#E5E5EA"

# -----------------------------------------------------------------------------
# 2. UI/UX 및 DB
# -----------------------------------------------------------------------------
def inject_custom_css():
    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap');
    html, body, [class*="css"] {{ font-family: 'Noto Sans KR', sans-serif; background-color: {COLOR_BG}; }}
    div.stButton > button {{ width: 100%; min-height: 50px; border-radius: 12px; font-weight: 600; border: none; background-color: {COLOR_PRIMARY}; color: white; }}
    .chat-container {{ display: flex; flex-direction: column; gap: 10px; margin-bottom: 20px; max-height: 400px; overflow-y: auto; }}
    .msg-bubble {{ padding: 12px 16px; border-radius: 12px; max-width: 80%; font-size: 14px; line-height: 1.5; }}
    .msg-me {{ align_self: flex-end; background-color: {COLOR_MY_MSG}; color: white; }}
    .msg-other {{ align_self: flex-start; background-color: {COLOR_OTHER_MSG}; color: black; }}
    div[data-testid="stVerticalBlockBorderWrapper"] {{ background: white; border-radius: 16px; padding: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); border: 1px solid rgba(0,0,0,0.05); }}
    </style>
    """, unsafe_allow_html=True)

def get_db_connection(): return sqlite3.connect(DB_NAME, check_same_thread=False)

def init_db():
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT, role TEXT, real_name TEXT, group_color TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS monthly_goals (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, year_month TEXT, subject TEXT, content TEXT, total_amount INTEGER, week_days TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        c.execute('''CREATE TABLE IF NOT EXISTS daily_plans (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, plan_date DATE, subject TEXT, content TEXT, achievement INTEGER DEFAULT 0, linked_monthly_id INTEGER)''')
        c.execute('''CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, from_id INTEGER, to_id INTEGER, message TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        conn.commit()

# -----------------------------------------------------------------------------
# 3. [핵심 수정] AI 분석 로직 (경고 후 분석 진행)
# -----------------------------------------------------------------------------
def generate_analysis_report(student_name, start_date, end_date, df):
    if df.empty: return "선택한 기간에 데이터가 없습니다."
    
    # 1. 기본 통계 계산
    avg_score = df['achievement'].mean()
    subj_stats = df.groupby('subject')['achievement'].mean().sort_values(ascending=False)
    subj_count = df.groupby('subject')['achievement'].count().sort_values(ascending=False)
    best_subj = subj_stats.index[0]
    worst_subj = subj_stats.index[-1]
    gap = subj_stats.iloc[0] - subj_stats.iloc[-1]

    # 2. [Hierarchy Check] 1순위: 절대 학습량(성취도) 검증
    report = f"[ 📊 {student_name} 학습 정밀 분석 ]\n📅 기간: {start_date} ~ {end_date}\n\n"
    
    if avg_score < 50:
        # [Red Alert] 분석을 중단(return)하지 않고 경고문만 상단에 배치
        report += f"🚨 **[긴급 경고] 학습량 절대 부족 (평균 {int(avg_score)}점)**\n"
        report += "- 현재 학습 성취도가 위험 수준(🔴)입니다.\n"
        report += "- **기초 학습량 확보가 시급하며, 아래 분석 데이터는 상담 참고용입니다.**\n\n" 
    elif avg_score < 80:
        report += f"⚠️ **[주의 필요] 성취도 개선 요망 (평균 {int(avg_score)}점)**\n"
        report += "- 전반적인 학습 실행력이 다소 부족합니다 (🟡).\n\n"
    else:
        report += f"✅ **[우수] 안정적인 학습 수행 (평균 {int(avg_score)}점)**\n- 성실하게 계획을 이행하고 있습니다 (🟢).\n\n"

    # 3. [Hierarchy Check] 2순위: 밸런스 분석 (50점 미만이어도 실행됨)
    report += "1️⃣ **과목별 밸런스**\n"
    report += f"- 강점: {best_subj} ({int(subj_stats.iloc[0])}점) vs 약점: {worst_subj} ({int(subj_stats.iloc[-1])}점)\n"
    
    if gap > 20:
        report += f"- ⚠️ **불균형 경고:** 과목 간 편차가 {int(gap)}점으로 큽니다. 편식 학습을 경계하세요.\n"
    else:
        # 성취도가 낮은데 밸런스가 좋은 경우에 대한 멘트 보정
        if avg_score < 50:
            report += "- ℹ️ **참고:** 과목 간 편차는 적으나, **전체적인 학습량이 낮아 큰 의미는 없습니다.**\n"
        else:
            report += "- ⚖️ **밸런스 양호:** 전 과목을 고르게 학습하고 있습니다. 아주 좋습니다.\n"

    report += f"\n2️⃣ **학습 빈도**\n- 최다: {subj_count.index[0]} ({subj_count.iloc[0]}회)\n"
    
    return report

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

# -----------------------------------------------------------------------------
# 4. 관리자 대시보드 (Admin View)
# -----------------------------------------------------------------------------
def admin_dashboard():
    user = st.session_state['user']
    with st.sidebar:
        st.title("5A Admin")
        st.markdown(f"관리자: **{user['real_name']}**님")
        if st.button("로그아웃"): del st.session_state['user']; st.rerun()
        st.markdown("---")
        
        search_query = st.text_input("🔍 학생 검색", placeholder="이름 입력")
        
        with get_db_connection() as conn: 
            students = pd.read_sql("SELECT id, real_name, group_color FROM users WHERE role='student' ORDER BY real_name", conn)
            seven_days_ago = datetime.date.today() - datetime.timedelta(days=7)
            stats = pd.read_sql(f"SELECT user_id, AVG(achievement) as avg_score FROM daily_plans WHERE plan_date >= '{seven_days_ago}' GROUP BY user_id", conn)
        
        if not stats.empty:
            students = pd.merge(students, stats, left_on='id', right_on='user_id', how='left')
            students['avg_score'] = students['avg_score'].fillna(0)
        else: students['avg_score'] = 0

        if search_query: students = students[students['real_name'].str.contains(search_query)]

        student_labels = {}
        for _, row in students.iterrows():
            score = row['avg_score']
            if score >= 80: signal = "🟢"
            elif score >= 50: signal = "🟡"
            else: signal = "🔴"
            student_labels[row['id']] = f"{signal} {row['real_name']}"

        with st.container(height=300, border=True):
            if students.empty: st.write("결과 없음"); sid = None
            else: sid = st.radio("학생 명단", students['id'], format_func=lambda x: student_labels.get(x, f"⚪ {x}"), label_visibility="collapsed")
        
        st.markdown("---")
        d_range = st.date_input("분석 기간", [datetime.date.today() - datetime.timedelta(days=30), datetime.date.today()])
        if len(d_range) == 2: start_d, end_d = d_range
        else: start_d = end_d = d_range[0]

    if not sid: st.info("👈 왼쪽 사이드바에서 학생을 선택해주세요."); return

    sname = students[students['id']==sid].iloc[0]['real_name']
    with get_db_connection() as conn:
        query = "SELECT * FROM daily_plans WHERE user_id=? AND plan_date BETWEEN ? AND ? ORDER BY plan_date"
        df = pd.read_sql(query, conn, params=(sid, start_d, end_d))

    st.markdown(f"## 📊 {sname} 학생 정밀 분석")
    st.caption(f"분석 기준: {start_d} ~ {end_d}")

    if df.empty: st.warning("⚠️ 선택한 기간에 학습 데이터가 없습니다."); return

    c_left, c_right = st.columns([1, 1])
    with c_left:
        st.markdown("### 📊 과목별 성취도 (Avg)")
        with st.container(border=True):
            subj_avg = df.groupby('subject')['achievement'].mean()
            st.bar_chart(subj_avg, color="#007AFF")

    with c_right:
        st.markdown("### 🕸️ 과목별 밸런스 (Balance)")
        with st.container(border=True):
            radar_df = df.groupby('subject')['achievement'].mean().reset_index()
            if not radar_df.empty:
                if HAS_PLOTLY:
                    categories = radar_df['subject'].tolist()
                    values = radar_df['achievement'].tolist()
                    categories.append(categories[0])
                    values.append(values[0])
                    fig = go.Figure(data=go.Scatterpolar(r=values, theta=categories, fill='toself', name=sname, line_color='#007AFF'))
                    fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])), showlegend=False, margin=dict(l=40, r=40, t=20, b=20), height=300)
                    st.plotly_chart(fig, use_container_width=True)
                else: st.bar_chart(radar_df.set_index('subject'))

    col_ai, col_chat = st.columns([1, 1])
    with col_ai:
        st.markdown("### 🤖 AI 분석 리포트")
        with st.container(border=True):
            if st.button("📋 리포트 생성 (New Logic)"):
                rep = generate_analysis_report(sname, start_d, end_d, df)
                st.session_state['ai_rep'] = rep
            val = st.session_state.get('ai_rep', "")
            final_msg = st.text_area("분석 내용", value=val, height=300)
            if st.button("메시지로 전송"):
                with get_db_connection() as conn: conn.execute("INSERT INTO messages (from_id, to_id, message) VALUES (?,?,?)", (user['id'], sid, final_msg))
                st.success("전송 완료!"); st.rerun()

    with col_chat:
        st.markdown("### 📬 메신저 내역")
        with st.container(border=True):
            render_chat(user['id'], sid)

# -----------------------------------------------------------------------------
# 5. 메인 실행 (로그인)
# -----------------------------------------------------------------------------
def main():
    inject_custom_css()
    init_db()
    if 'user' not in st.session_state:
        _, col, _ = st.columns([1,1,1])
        with col:
            st.markdown("<br><br>", unsafe_allow_html=True)
            with st.container(border=True):
                st.markdown(f"<h2 style='text-align:center; color:{COLOR_PRIMARY};'>5A ADMIN</h2>", unsafe_allow_html=True)
                uid = st.text_input("아이디")
                upw = st.text_input("비밀번호", type="password")
                if st.button("로그인"):
                    with get_db_connection() as conn:
                        user = conn.execute("SELECT id, role, real_name FROM users WHERE username=? AND password=?", (uid, upw)).fetchone()
                    if user and user[1] == 'admin':
                        st.session_state['user'] = {'id':user[0], 'role':user[1], 'real_name':user[2]}
                        st.rerun()
                    else: st.error("관리자 계정이 아닙니다.")
    else:
        admin_dashboard()

if __name__ == "__main__":
    main()