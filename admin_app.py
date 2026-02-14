import streamlit as st
import sqlite3
import pandas as pd
import datetime
import calendar
import random
import time

st.set_page_config(layout="wide", page_title="5A Admin Dashboard")
hide_github_icon = """
    <style>
    .css-1jc7ptx, .e1ewe7hr3, .viewerBadge_container__1QSob, .styles_viewerBadge__1yB5_, .viewerBadge_link__1S137, .viewerBadge_text__1JaDK { display: none; } 
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
    """
st.markdown(hide_github_icon, unsafe_allow_html=True)
# [시스템 무결성] 라이브러리 체크
try:
    import plotly.graph_objects as go
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False

# -----------------------------------------------------------------------------
# 1. 시스템 설정 및 상수
# -----------------------------------------------------------------------------
DB_NAME = "5a_planner_v5_fix.db"
COLOR_PRIMARY = "#007AFF"
COLOR_BG = "#F5F5F7"
COLOR_MY_MSG = "#007AFF"
COLOR_OTHER_MSG = "#E5E5EA"

# -----------------------------------------------------------------------------
# 2. 헬퍼 함수 (UI/UX, DB, AI)
# -----------------------------------------------------------------------------
def inject_custom_css():
    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap');
    
    /* [기본 스타일] */
    html, body, [class*="css"] {{ font-family: 'Noto Sans KR', sans-serif; background-color: {COLOR_BG}; }}
    
    div.stButton > button {{ 
        width: 100%; border-radius: 8px; font-weight: 600; border: 1px solid #e5e5ea; 
        background-color: white; color: #333; height: 60px; 
    }}
    div.stButton > button:hover {{ border-color: {COLOR_PRIMARY}; color: {COLOR_PRIMARY}; }}
    
    .chat-container {{ display: flex; flex-direction: column; gap: 10px; margin-bottom: 20px; max-height: 400px; overflow-y: auto; }}
    .msg-bubble {{ padding: 12px 16px; border-radius: 12px; max-width: 80%; font-size: 14px; line-height: 1.5; }}
    .msg-me {{ align_self: flex-end; background-color: {COLOR_MY_MSG}; color: white; }}
    .msg-other {{ align_self: flex-start; background-color: {COLOR_OTHER_MSG}; color: black; }}
    div[data-testid="stVerticalBlockBorderWrapper"] {{ background: white; border-radius: 16px; padding: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); border: 1px solid rgba(0,0,0,0.05); }}

    /* 🖨️ [인쇄 모드 전용 스타일] (Ctrl+P 솔루션) */
    @media print {{
        /* 1. 용지 설정 (A4 세로, 여백 최소화) */
        @page {{ size: A4 portrait; margin: 10mm; }}

        /* 2. 화면 정리 (사이드바, 버튼, 헤더/푸터 숨김) */
        [data-testid="stSidebar"], header, footer, .stButton, button {{ display: none !important; }}
        
        /* 3. 자동 축소 마법 (핵심: 내용을 75%로 줄여서 A4 폭에 맞춤) */
        .block-container {{
            width: 100% !important;
            max-width: 100% !important;
            padding: 0 !important;
            zoom: 0.75; /* 이 부분이 화면 짤림을 방지합니다 */
        }}
        
        /* 4. 박스 짤림 방지 (분석 리포트가 페이지 중간에서 잘리지 않게) */
        div[data-testid="stVerticalBlockBorderWrapper"], .stMarkdown {{
            break-inside: avoid;
            page-break-inside: avoid;
            margin-bottom: 20px;
        }}
        
        /* 5. 잉크 절약 및 가독성 (배경 흰색, 글자 검정) */
        body, [class*="css"] {{ background-color: white !important; -webkit-print-color-adjust: exact; }}
        * {{ color: black !important; }}
    }}
    </style>
    """, unsafe_allow_html=True)

def get_db_connection(): 
    return sqlite3.connect(DB_NAME, check_same_thread=False)

def render_chat(user_id, other_id):
    with get_db_connection() as conn:
        try:
            msgs = pd.read_sql("SELECT * FROM messages WHERE (from_id=? AND to_id=?) OR (from_id=? AND to_id=?) ORDER BY created_at ASC", conn, params=(user_id, other_id, other_id, user_id))
        except:
            st.info("메시지 테이블이 없습니다.")
            return

    if msgs.empty: st.info("메시지 내역 없음")
    else:
        chat_html = '<div class="chat-container">'
        for _, row in msgs.iterrows():
            cls = "msg-me" if row['from_id'] == user_id else "msg-other"
            chat_html += f'<div class="msg-bubble {cls}">{row["message"]}</div>'
        chat_html += '</div>'
        st.markdown(chat_html, unsafe_allow_html=True)

def render_native_calendar(df, year, month):
    cal = calendar.monthcalendar(year, month)
    month_name = f"{year}년 {month}월"
    
    col_prev, col_title, col_next = st.columns([1, 5, 1])
    with col_title:
        st.markdown(f"<h3 style='text-align: center; margin:0;'>{month_name}</h3>", unsafe_allow_html=True)
    
    cols = st.columns(7)
    days = ['월', '화', '수', '목', '금', '토', '일']
    for i, day in enumerate(days):
        cols[i].markdown(f"<div class='cal-header'>{day}</div>", unsafe_allow_html=True)
    
    if 'selected_date' not in st.session_state: st.session_state['selected_date'] = None

    for week in cal:
        cols = st.columns(7)
        for i, day in enumerate(week):
            if day == 0:
                cols[i].write("") 
            else:
                this_date = datetime.date(year, month, day)
                has_plan = False
                if not df.empty:
                    if not df[df['plan_date'] == this_date].empty:
                        has_plan = True
                
                label = f"{day}"
                if has_plan: label += " 🔵"
                
                if cols[i].button(label, key=f"btn_{year}_{month}_{day}", use_container_width=True):
                    st.session_state['selected_date'] = this_date

# -----------------------------------------------------------------------------
# 3. 메인 로직 (show_admin)
# -----------------------------------------------------------------------------
def show_admin():
    inject_custom_css()
    
    # [안전장치] 로그인 정보가 없으면 경고만 띄우고 종료하지 않음 (화면 확인용)
    if 'user' not in st.session_state:
        st.warning("⚠️ 로그인 정보가 없습니다. (단독 실행 모드로 전환됩니다)")
        st.session_state['user'] = {'id': 1, 'role': 'admin', 'real_name': '테스트관리자'}

    user = st.session_state['user']
    
    with st.sidebar:
        st.title("5A Admin")
        st.markdown(f"관리자: **{user['real_name']}**님")
        if st.button("로그아웃"): 
            st.session_state.clear()
            st.rerun()
        st.markdown("---")
        
        search_query = st.text_input("🔍 학생 검색", placeholder="이름 입력")
        
        # DB 연결 및 학생 목록 가져오기
        with get_db_connection() as conn: 
            try:
                # 테이블 존재 여부 확인 (에러 방지)
                conn.execute("SELECT * FROM users LIMIT 1")
                students = pd.read_sql("SELECT id, real_name, group_color FROM users WHERE role='student' ORDER BY real_name", conn)
            except:
                st.error("DB가 초기화되지 않았거나 'users' 테이블이 없습니다.")
                return

            seven_days_ago = datetime.date.today() - datetime.timedelta(days=7)
            try:
                stats = pd.read_sql(f"SELECT user_id, AVG(achievement) as avg_score FROM daily_plans WHERE plan_date >= '{seven_days_ago}' GROUP BY user_id", conn)
            except: stats = pd.DataFrame()
        
        if not stats.empty and not students.empty:
            students = pd.merge(students, stats, left_on='id', right_on='user_id', how='left')
            students['avg_score'] = students['avg_score'].fillna(0)
        else:
            if not students.empty: students['avg_score'] = 0

        if search_query and not students.empty: 
            students = students[students['real_name'].str.contains(search_query)]

        student_labels = {}
        if not students.empty:
            for _, row in students.iterrows():
                score = row.get('avg_score', 0)
                if score >= 80: signal = "🟢"
                elif score >= 50: signal = "🟡"
                else: signal = "🔴"
                student_labels[row['id']] = f"{signal} {row['real_name']}"

        with st.container(height=300, border=True):
            if students.empty: st.write("학생 없음"); sid = None
            else: sid = st.radio("학생 명단", students['id'], format_func=lambda x: student_labels.get(x, f"⚪ {x}"), label_visibility="collapsed")
        
        # [NEW] 테스트용 데이터 생성 도구 (학생 선택 후에만 보이게)
        if sid:
            st.markdown("---")
            with st.expander("🔧 개발자 도구 (Test Data)"):
                if st.button("🎲 테스트용 일지 생성 (3일치)", use_container_width=True):
                    with get_db_connection() as conn:
                        try:
                            # 1. 긍정
                            conn.execute("INSERT INTO daily_logs (user_id, log_date, resolution, review) VALUES (?, DATE('now', '-1 day'), ?, ?)", 
                                         (sid, "파이팅!", "계획 달성 완료. 뿌듯하다."))
                            # 2. 부정
                            conn.execute("INSERT INTO daily_logs (user_id, log_date, resolution, review) VALUES (?, DATE('now', '-2 days'), ?, ?)", 
                                         (sid, "졸리다", "너무 힘들고 포기하고 싶다."))
                            # 3. 부정
                            conn.execute("INSERT INTO daily_logs (user_id, log_date, resolution, review) VALUES (?, DATE('now', '-3 days'), ?, ?)", 
                                         (sid, "힘내자", "숙제가 많아서 짜증난다."))
                            conn.commit()
                            st.success("샘플 일지 생성 완료!")
                            time.sleep(0.5)
                            st.rerun()
                        except Exception as e:
                            st.error(f"오류: {e}")

        st.markdown("---")
        d_range = st.date_input("조회 기간", [datetime.date.today() - datetime.timedelta(days=30), datetime.date.today()])
        if len(d_range) == 2: start_d, end_d = d_range
        else: start_d = end_d = d_range[0]

    # 메인 화면
    if not sid: 
        st.info("👈 왼쪽 사이드바에서 학생을 선택해주세요.")
        return

    # 선택된 학생 정보 가져오기
    try:
        sname = students[students['id']==sid].iloc[0]['real_name']
    except:
        sname = "알 수 없음"
    
    st.markdown(f"## 📊 {sname} 학생 통합 관리")
    tab_analysis, tab_calendar, tab_manage = st.tabs(["📊 정밀 분석 (Analysis)", "📅 월간 계획표 (Calendar)", "🛡️ 멤버 관리 (Management)"])

    # === TAB 1: 정밀 분석 ===
    with tab_analysis:
        if not sid:
            st.info("👈 왼쪽 사이드바에서 분석할 학생을 선택해주세요.")
            c1, c2 = st.columns(2)
            with c1: st.markdown("### 📈 과목별 성적 추이"); st.caption("학생 선택 시 표시됩니다.")
            with c2: st.markdown("### 🕸️ 과목별 밸런스"); st.caption("학생 선택 시 표시됩니다.")
        else:
            # 실제 데이터 로딩
            with get_db_connection() as conn:
                try: df = pd.read_sql("SELECT * FROM daily_plans WHERE user_id=? AND plan_date BETWEEN ? AND ?", conn, params=(sid, start_d, end_d))
                except: df = pd.DataFrame()
            
            if not df.empty: df['plan_date'] = pd.to_datetime(df['plan_date']).dt.date
            
            if df.empty:
                st.info("📭 선택한 기간에 데이터가 없습니다.")
            else:
                # [그래프 & 차트 섹션 - 기존 코드 유지]
                c_left, c_right = st.columns([1, 1])

                # 1. (왼쪽) 성적 추이 그래프
                with c_left:
                    st.markdown("### 📈 과목별 성적 정밀 추이")
                    if HAS_PLOTLY:
                        fig = go.Figure()
                        color_map = {'국어': '#FF3B30', '영어': '#34C759', '수학': '#007AFF', '탐구': '#FF9500'}
                        
                        subjects = df['subject'].unique()
                        for subj in subjects:
                            subj_data = df[df['subject'] == subj].sort_values('plan_date')
                            fig.add_trace(go.Scatter(
                                x=subj_data['plan_date'], y=subj_data['achievement'],
                                mode='lines+markers', name=subj,
                                line=dict(shape='spline', width=3, color=color_map.get(subj, '#888')),
                                marker=dict(size=8, symbol='circle'), connectgaps=True
                            ))
                        fig.update_layout(hovermode="x unified", xaxis=dict(showgrid=False), yaxis=dict(range=[0, 105]), template="plotly_white", height=400, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.line_chart(df.pivot_table(index='plan_date', columns='subject', values='achievement', aggfunc='mean').interpolate())

                # 2. (오른쪽) 밸런스 차트
                with c_right:
                    st.markdown("### 🕸️ 과목별 밸런스")
                    radar_df = df.groupby('subject')['achievement'].mean().reset_index()
                    if not radar_df.empty:
                        if HAS_PLOTLY:
                            categories = radar_df['subject'].tolist()
                            values = radar_df['achievement'].tolist()
                            categories.append(categories[0]); values.append(values[0]) # 도형 닫기
                            fig = go.Figure(data=go.Scatterpolar(r=values, theta=categories, fill='toself', name='성취도', line_color='#007AFF'))
                            fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])), showlegend=False, margin=dict(l=40, r=40, t=20, b=20), height=400)
                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.bar_chart(radar_df.set_index('subject'))

            st.markdown("---")

            # ----------------------------------------------------------------
            # [NEW] 2. 학습 일지 뷰어 및 엑셀 다운로드 (새로 추가됨)
            # ----------------------------------------------------------------
            with get_db_connection() as conn:
                try:
                    logs_df = pd.read_sql("""
                        SELECT log_date, resolution, review 
                        FROM daily_logs 
                        WHERE user_id=? AND log_date BETWEEN ? AND ? 
                        ORDER BY log_date DESC
                    """, conn, params=(sid, start_d, end_d))
                except: logs_df = pd.DataFrame()

            c_log_view, c_log_action = st.columns([2, 1])
            with c_log_view:
                st.markdown("### 📝 학습 일지 (Mindset)")
                if logs_df.empty:
                    st.info("📭 해당 기간에 작성된 일지가 없습니다.")
                else:
                    st.dataframe(logs_df, use_container_width=True, hide_index=True)

            with c_log_action:
                st.markdown("### 💾 데이터 관리")
                if not logs_df.empty:
                    # CSV 변환 (한글 깨짐 방지: utf-8-sig)
                    csv = logs_df.to_csv(index=False).encode('utf-8-sig')
                    file_name = f"{sname}_학습일지_{start_d.strftime('%Y%m%d')}_{end_d.strftime('%Y%m%d')}.csv"
                    st.download_button(
                        label="📥 엑셀(CSV) 다운로드",
                        data=csv,
                        file_name=file_name,
                        mime='text/csv',
                        use_container_width=True
                    )
                else:
                    st.caption("다운로드할 데이터가 없습니다.")

            st.markdown("---")

            # ----------------------------------------------------------------
            # [FINAL] 3. 5A 딥 인사이트 & 솔루션 (Deep Analysis + Solution)
            # ----------------------------------------------------------------
            st.markdown("### 🧠 5A 딥 인사이트 (Deep Analysis & Solution)")
            st.caption(f"과목별 스탯 분석(Evidence)을 바탕으로, 즉시 실행 가능한 솔루션(Action)까지 원스톱으로 제공합니다.")

            if st.button("✨ 종합 컨설팅 리포트 생성", type="primary", use_container_width=True):
                if df.empty:
                    st.error("분석할 학습 데이터(Plan)가 부족합니다.")
                else:
                    with st.spinner("데이터 정밀 분석 및 솔루션 매칭 중..."):
                        time.sleep(1.2)

                        # ====================================================
                        # [PART 1] 데이터 정밀 분석 (통계 산출)
                        # ====================================================
                        df['achievement'] = pd.to_numeric(df['achievement'], errors='coerce').fillna(0)
                        
                        # 과목별 통계: 평균, 최고, 최저, 기복(Gap)
                        subj_stats = df.groupby('subject')['achievement'].agg(['mean', 'max', 'min'])
                        subj_stats['gap'] = subj_stats['max'] - subj_stats['min']
                        
                        # 핵심 지표
                        total_avg = df['achievement'].mean()
                        best_subj = subj_stats['mean'].idxmax()
                        worst_subj = subj_stats['mean'].idxmin()
                        volatile_subj = subj_stats['gap'].idxmax()
                        
                        best_score = subj_stats.loc[best_subj, 'mean']
                        worst_score = subj_stats.loc[worst_subj, 'mean']
                        max_gap = subj_stats.loc[volatile_subj, 'gap']

                        # --- 관리자 브리핑 포인트 생성 ---
                        briefing_points = []
                        
                        # 1. 전체 퍼포먼스
                        if total_avg >= 80:
                            briefing_points.append(f"🚀 **전체 퍼포먼스**: 평균 이행률 **{total_avg:.1f}%**로 '자기주도 완성형' 단계입니다.")
                        elif total_avg >= 50:
                            briefing_points.append(f"⚠️ **전체 퍼포먼스**: 평균 이행률 **{total_avg:.1f}%**로 중위권입니다. 실행의 기복을 잡는 것이 급선무입니다.")
                        else:
                            briefing_points.append(f"🚨 **전체 퍼포먼스**: 평균 이행률 **{total_avg:.1f}%**로 학습 습관 형성이 시급합니다.")

                        # 2. 강점/약점
                        briefing_points.append(f"👍 **전략 과목**: **'{best_subj}'**은 평균 **{best_score:.1f}%**로 학습을 주도하고 있습니다.")
                        if worst_score < 40:
                            briefing_points.append(f"🚧 **학습 병목**: **'{worst_subj}'** 이행률이 **{worst_score:.1f}%**에 머물러 전체 평균을 깎아먹고 있습니다.")
                        
                        # 3. 불안정성
                        if max_gap >= 40:
                            briefing_points.append(f"📉 **불안정성 감지**: **'{volatile_subj}'** 과목은 기복이 **{max_gap:.0f}%** 포인트나 됩니다. 기분파 학습을 경계해야 합니다.")

                        # ====================================================
                        # [PART 2] 솔루션 매칭 (진단 및 처방)
                        # ====================================================
                        diagnosis_title = ""
                        solution_steps = []
                        teacher_script = ""
                        alert_type = "info"

                        # A. 롤러코스터형 (기복 심함)
                        if max_gap >= 40:
                            diagnosis_title = "📉 진단: 감정 기복형 (Rollercoaster)"
                            alert_type = "warning"
                            solution_steps = [
                                "**최소 습관(Min-Habit)**: 컨디션 최악인 날에도 무조건 해야 하는 '최소 분량' 설정",
                                "**시작 루틴**: 공부 시작 전 책상 정리 등 뇌 스위치를 켜는 의식 만들기"
                            ]
                            teacher_script = f"'{sname}아, {volatile_subj} 점수를 보니까 잘할 땐 완벽한데, 안 될 땐 너무 놔버리는 것 같아. 기복을 줄이는 게 이번 달 목표야.'"

                        # B. 편식형 (과목 격차 심함)
                        elif (best_score - worst_score) >= 30:
                            diagnosis_title = "⚖️ 진단: 과목 편식형 (Imbalance)"
                            alert_type = "error"
                            solution_steps = [
                                "**샌드위치 학습법**: [선호 과목] ➔ [비선호 과목(30분)] ➔ [선호 과목] 배치",
                                "**허들 낮추기**: {worst_subj}는 당분간 쉬운 문제 위주로 성공 경험 쌓기"
                            ]
                            teacher_script = f"'{sname}아, {best_subj}는 정말 잘하는데 {worst_subj}가 조금 아쉽네. 맛있는 거 먹기 전에 야채 한 입만 먹는다고 생각하고 {worst_subj}부터 해볼까?'"

                        # C. 기초 부족형 (전체 저조)
                        elif total_avg < 40:
                            diagnosis_title = "🌧️ 진단: 기초 부족형 (Struggling)"
                            alert_type = "secondary"
                            solution_steps = [
                                "**타임 박싱(Time Boxing)**: 20분 공부 + 5분 휴식 사이클 도입",
                                "**플래너 간소화**: 하루 핵심 과제 3개만 적고 100% 달성하기"
                            ]
                            teacher_script = f"'{sname}아, 욕심내지 말고 천천히 가자. 오늘 플래너에 적힌 거 딱 하나만이라도 제대로 끝내면 선생님은 만족해.'"

                        # D. 마스터형 (안정적)
                        else:
                            diagnosis_title = "🚀 진단: 자기주도 완성형 (Mastery)"
                            alert_type = "success"
                            solution_steps = [
                                "**백지 복습**: 공부한 내용을 보지 않고 구조도 그리기",
                                "**티칭 학습**: 친구나 선생님에게 오늘 배운 내용 설명하기"
                            ]
                            teacher_script = f"'{sname}아, 지금 폼 정말 좋다! 꾸준함이 무기라는 걸 네가 증명하고 있어. 이대로만 가자!'"


                        # ====================================================
                        # [PART 3] 최종 리포트 출력 (UI 구성)
                        # ====================================================
                        st.success("✅ 종합 분석 리포트 생성 완료")
                        
                        # --- 1. 상단: 데이터 분석 (Evidence) ---
                        with st.container(border=True):
                            c1, c2 = st.columns([1.2, 2])
                            
                            with c1:
                                st.markdown("#### 📊 과목별 스탯 (Stats)")
                                display_df = subj_stats[['mean', 'max', 'min', 'gap']].copy()
                                display_df.columns = ['평균', '최고', '최저', '기복']
                                st.dataframe(display_df.style.format("{:.1f}"), use_container_width=True)
                                
                            with c2:
                                st.markdown("#### 📢 관리자 브리핑 (Briefing)")
                                for point in briefing_points:
                                    st.info(point, icon="📌")
                        
                        st.markdown("---")
                        
                        # --- 2. 하단: 솔루션 가이드 (Prescription) ---
                        st.markdown(f"#### {diagnosis_title}")
                        
                        col_sol, col_script = st.columns([1, 1])
                        
                        with col_sol:
                            st.markdown("**💊 처방 솔루션 (Action Plan)**")
                            for step in solution_steps:
                                if alert_type == "success": st.success(step)
                                elif alert_type == "warning": st.warning(step)
                                elif alert_type == "error": st.error(step)
                                else: st.info(step)
                                
                        with col_script:
                            st.markdown("**🗣️ 상담 스크립트 (Teacher's Guide)**")
                            st.code(teacher_script, language="text")
                            
                            with st.expander("💡 상담 Tip"):
                                st.caption("학생의 자존감을 위해 '지적'보다는 '관찰한 사실'을 먼저 이야기해주세요.")                
            # [기존 메신저 기능 연결]
            c_msg_input, c_msg_view = st.columns([1, 1])
            with c_msg_input:
                st.markdown("### 📨 메시지 보내기")
                with st.form("admin_msg_form", clear_on_submit=True):
                    admin_msg = st.text_area("보낼 메시지", height=100)
                    if st.form_submit_button("전송"):
                        if admin_msg.strip():
                            with get_db_connection() as conn:
                                conn.execute("INSERT INTO messages (from_id, to_id, message) VALUES (?,?,?)", (user['id'], sid, admin_msg))
                                conn.commit()
                            st.success("전송되었습니다!")
                            st.rerun()
                        else:
                            st.warning("내용을 입력해주세요.")

            with c_msg_view:
                st.markdown("### 📬 메신저 내역")
                render_chat(user['id'], sid)

    # === TAB 2: 월간 계획표 (Calendar) ===
    with tab_calendar:
        c_y, c_m, c_blank = st.columns([1, 1, 4])
        with c_y: cal_year = st.selectbox("년도", [2025, 2026], index=1)
        with c_m: cal_month = st.selectbox("월", list(range(1, 13)), index=datetime.date.today().month-1)
        
        start_cal = datetime.date(cal_year, cal_month, 1)
        _, last_day = calendar.monthrange(cal_year, cal_month)
        end_cal = datetime.date(cal_year, cal_month, last_day)
        
        with get_db_connection() as conn:
            try:
                cal_df = pd.read_sql("SELECT * FROM daily_plans WHERE user_id=? AND plan_date BETWEEN ? AND ?", conn, params=(sid, start_cal, end_cal))
            except: cal_df = pd.DataFrame()
        
        if not cal_df.empty:
            cal_df['plan_date'] = pd.to_datetime(cal_df['plan_date']).dt.date

        render_native_calendar(cal_df, cal_year, cal_month)

        st.markdown("---")
        if st.session_state['selected_date']:
            sel_d = st.session_state['selected_date']
            st.markdown(f"### 📌 {sel_d.strftime('%Y년 %m월 %d일')} 학습 상세")
            day_data = cal_df[cal_df['plan_date'] == sel_d] if not cal_df.empty else pd.DataFrame()
            
            if day_data.empty: st.info("📭 일정 없음")
            else:
                for _, row in day_data.iterrows():
                    st.success(f"{row['subject']} : {row['content']} ({row['achievement']}%)")
        else:
            st.info("👆 달력 날짜를 클릭하세요.")

    # === TAB 3: 멤버 관리 (Management) ===
    with tab_manage:
        st.markdown("### 👥 전체 회원 리스트 및 관리")
        
        with get_db_connection() as conn:
            all_users = pd.read_sql("SELECT id, username, real_name, role FROM users ORDER BY id DESC", conn)

        # 1. 신규 가입 대기자
        pending_users = all_users[all_users['role'] == 'pending']
        if not pending_users.empty:
            st.warning(f"⚠️ 승인 대기 중인 회원이 {len(pending_users)}명 있습니다!")
            for _, row in pending_users.iterrows():
                c1, c2, c3 = st.columns([3, 1, 1])
                c1.write(f"**{row['real_name']}** ({row['username']})")
                
                if c2.button("✅ 승인", key=f"app_{row['id']}"):
                    with get_db_connection() as conn:
                        conn.execute("UPDATE users SET role='student' WHERE id=?", (row['id'],))
                        conn.commit()
                    st.success(f"{row['real_name']}님 승인 완료!")
                    st.rerun()
                    
                if c3.button("❌ 거절", key=f"rej_{row['id']}"):
                    with get_db_connection() as conn:
                        conn.execute("DELETE FROM users WHERE id=?", (row['id'],))
                        conn.commit()
                    st.error("삭제 완료")
                    st.rerun()
            st.markdown("---")

        # 2. 전체 회원 목록
        st.dataframe(all_users, use_container_width=True)
        
        st.markdown("### 🗑️ 회원 삭제 (주의)")
        st.caption("삭제 시 해당 학생의 학습 기록, 메시지 등 모든 데이터가 영구적으로 지워집니다.")

        # [수정] 기존 st.selectbox(단일 선택) -> st.multiselect(다중 선택)으로 변경
        # 학생 이름 리스트 생성 (ID와 이름 매핑)
        student_dict = {row['real_name']: row['id'] for _, row in students.iterrows()}
        
        # 다중 선택 위젯
        selected_names = st.multiselect(
            "삭제할 회원을 선택하세요 (복수 선택 가능)",
            options=list(student_dict.keys()),
            placeholder="이름을 검색하거나 선택하세요"
        )

        # 삭제 버튼 (선택된 사람이 있을 때만 활성화)
        if selected_names:
            st.error(f"선택한 {len(selected_names)}명의 회원을 정말로 삭제하시겠습니까?")
            # 실수 방지용 체크박스
            if st.checkbox("네, 영구 삭제에 동의합니다.", key="del_agree"):
                if st.button("선택한 회원 일괄 삭제 실행", type="primary"):
                    
                    # 선택된 이름들을 ID 리스트로 변환
                    target_ids = [student_dict[name] for name in selected_names]
                    
                    with get_db_connection() as conn:
                        cur = conn.cursor()
                        # SQL 구문 생성을 위한 플레이스홀더 (?,?,? 형태) 만들기
                        placeholders = ','.join('?' * len(target_ids))
                        
                        # 1. 사용자 테이블에서 삭제
                        cur.execute(f"DELETE FROM users WHERE id IN ({placeholders})", target_ids)
                        # 2. 관련 학습 기록 삭제 (daily_plans)
                        cur.execute(f"DELETE FROM daily_plans WHERE user_id IN ({placeholders})", target_ids)
                        # 3. 관련 메시지 삭제 (messages)
                        cur.execute(f"DELETE FROM messages WHERE from_id IN ({placeholders}) OR to_id IN ({placeholders})", target_ids * 2)
                        
                        conn.commit()
                    
                    st.success(f"✅ {len(selected_names)}명의 회원이 정상적으로 삭제되었습니다.")
                    time.sleep(1.5)
                    st.rerun() # 화면 새로고침하여 리스트 갱신

# -----------------------------------------------------------------------------
# 4. [핵심] 단독 실행 보장 코드
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    st.session_state['user'] = {'id': 1, 'role': 'admin', 'real_name': '관리자(단독실행)'}
    show_admin()