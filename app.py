import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import google.generativeai as genai
import pandas as pd
from datetime import datetime

# ==========================================
# --- [0. 로그인 화면 및 보안 설정] ---
# ==========================================
def check_password():
    """비밀번호 검증 로직"""
    
    # 1. 처음 접속했을 때 로그인 상태를 'False'로 초기화
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    # 2. 로그인이 안 된 상태라면 로그인 화면을 보여줌
    if not st.session_state["password_correct"]:
        st.title("🔒 Deep Focus 시스템")
        st.write("학생 관찰 기록 시스템에 접근하려면 비밀번호를 입력하세요.")
        
        with st.form("login_form"):
            entered_pw = st.text_input("비밀번호", type="password")
            submit_button = st.form_submit_button("로그인")
            
            if submit_button:
                # 입력한 비밀번호와 secrets에 저장된 비밀번호가 같은지 확인
                if entered_pw == st.secrets["app_password"]:
                    st.session_state["password_correct"] = True
                    st.rerun() # 정답이면 화면을 새로고침해서 메인 앱으로 넘어감
                else:
                    st.error("😕 비밀번호가 일치하지 않습니다.")
        return False
    
    # 3. 로그인이 된 상태라면 True 반환
    else:
        # 로그인 성공 후, 필요하다면 우측 상단에 로그아웃 버튼을 만들 수도 있습니다.
        if st.sidebar.button("로그아웃"):
            st.session_state["password_correct"] = False
            st.rerun()
        return True

# [가장 중요!] 비밀번호를 통과하지 못하면 여기서 실행을 멈춥니다.
if not check_password():
    st.stop()


# ==========================================
# --- [1. 구글 시트 연동 설정] ---
# ==========================================
# 서비스 계정 키 파일 경로 (발급받은 JSON 파일)
SERVICE_ACCOUNT_FILE = 'credentials.json' 
# 작업할 스프레드시트 이름 또는 URL
SPREADSHEET_KEY = "1cIpQCGqqN7-wgxWCFzKRtN4vYHCLPxNN5FFnpY5T2RI"

def get_gspread_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    # 클라우드 환경(st.secrets)에 인증 정보가 있으면 그것을 사용하고, 
    # 없으면 로컬 파일(credentials.json)을 사용합니다.
    if "gcp_service_account" in st.secrets:
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    else:
        creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scopes)
        
    return gspread.authorize(creds)

client = get_gspread_client()
doc = client.open_by_key(SPREADSHEET_KEY)

# ==========================================
# --- [2. 주요 기능 함수] ---
# ==========================================
def get_student_list():
    """모든 시트 이름을 가져와 학생 명단 반환 (첫 번째 시트 제외)"""
    sheets = doc.worksheets()
    # 첫 번째 시트는 보통 안내용이므로 제외하거나 로직에 맞게 조정
    return [sheet.title for sheet in sheets if sheet.title != "안내"]

def add_student(name):
    """새로운 학생 시트 생성"""
    try:
        new_sheet = doc.add_worksheet(title=name, rows="100", cols="5")
        new_sheet.append_row(["일시", "관찰내용"]) # 헤더 추가
        return True
    except:
        return False

def delete_student(name):
    """학생 시트 삭제"""
    try:
        sheet = doc.worksheet(name)
        doc.del_worksheet(sheet)
        return True
    except:
        return False

# ==========================================
# --- [3. 스트림릿 UI 구성] ---
# ==========================================
st.set_page_config(page_title="Deep Focus", layout="wide")

st.sidebar.title("🔍 Deep Focus")
st.sidebar.subheader("AI 학생 관찰 기록 시스템")

# 메뉴 구성
menu = st.sidebar.radio("메뉴", ["학생 관리", "관찰 기록 입력", "AI 요약 및 분석"])

# --- 메뉴 1: 학생 관리 ---
if menu == "학생 관리":
    st.header("👥 학생 명단 관리")
    st.info("학생별로 독립된 시트가 구글 스프레드시트에 실시간으로 생성됩니다.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("새 학생 등록")
        new_name = st.text_input("학생 이름 입력")
        if st.button("등록하기"):
            if new_name:
                if add_student(new_name):
                    st.success(f"{new_name} 학생 시트가 생성되었습니다.")
                    st.rerun()
                else:
                    st.error("이미 존재하는 이름이거나 오류가 발생했습니다.")
                    
    with col2:
        st.subheader("학생 삭제")
        student_list = get_student_list()
        del_name = st.selectbox("삭제할 학생 선택", ["선택하세요"] + student_list)
        if st.button("시트 삭제", help="주의: 해당 학생의 모든 기록이 영구 삭제됩니다."):
            if del_name != "선택하세요":
                if delete_student(del_name):
                    st.success(f"{del_name} 학생 데이터가 삭제되었습니다.")
                    st.rerun()

# --- 메뉴 2: 관찰 기록 입력 ---
elif menu == "관찰 기록 입력":
    st.header("📝 실시간 관찰 기록")
    student_list = get_student_list()
    
    if not student_list:
        st.warning("먼저 학생을 등록해 주세요.")
    else:
        selected_student = st.selectbox("학생 선택", student_list)
        sheet = doc.worksheet(selected_student)
        
        # 입력 폼
        with st.form("record_form", clear_on_submit=True):
            content = st.text_area("관찰 및 활동 내용 기록", placeholder="예: 체육 시간에 모둠 활동을 주도적으로 이끌며 규칙을 친구들에게 잘 설명함.")
            submitted = st.form_submit_button("기록 저장")
            
            if submitted:
                if content:
                    now = datetime.now().strftime("%Y-%m-%d %H:%M")
                    sheet.append_row([now, content])
                    st.toast(f"{selected_student} 기록 완료!", icon="✅")
                else:
                    st.warning("내용을 입력하세요.")
        
        # 즉각적인 내용 확인
        st.subheader(f"📌 {selected_student} 학생의 최근 기록")
        data = sheet.get_all_records()
        if data:
            df = pd.DataFrame(data)
            st.table(df.tail(5)) # 최근 5건만 표시
        else:
            st.write("아직 기록된 내용이 없습니다.")

# --- 메뉴 3: AI 요약 및 분석 (수정 완료) ---
elif menu == "AI 요약 및 분석":
    st.header("🤖 AI 행동발달사항 요약")
    student_list = get_student_list()
    
    if not student_list:
        st.warning("학생을 등록해 주세요.")
    else:
        selected_student = st.selectbox("분석 대상 학생", student_list)
        sheet = doc.worksheet(selected_student)
        records = sheet.get_all_records()
        
        if st.button("✨ AI 분석 시작"):
            if not records:
                st.warning("분석할 기록이 없습니다.")
            else:
                # [수정] 실수로 누락되었던 데이터 가공 코드 복구
                raw_text = "\n".join([f"- {r['일시']}: {r['관찰내용']}" for r in records])

                # [수정] 들여쓰기(Indentation) 완벽 정렬
                try:
                    # API 키를 텍스트 입력창이 아닌 st.secrets에서 직접 가져옵니다.
                    genai.configure(api_key=st.secrets["gemini_api_key"])
                    model = genai.GenerativeModel('gemini-2.5-flash')
                                        
                    prompt = f"""
                    다음은 초등학생 '{selected_student}'의 관찰 기록입니다. 
                    이 내용을 바탕으로 생활기록부 '행동특성 및 종합의견'에 들어갈 문구 초안을 작성해 주세요.
                    
                    [기록 내용]
                    {raw_text}
                    
                    [지침]
                    1. 관찰된 사실을 바탕으로 긍정적인 변화와 강점을 중심으로 서술할 것.
                    2. 문장은 '~함.', '~임.' 형태의 개조식 문장으로 작성하되, 전체 문장이 연결되어야 함.
                    3. 10줄 이내로 요약할 것.
                    4. 학생의 학습적 측면 1줄 이상, 생활적 측면 1줄 이상이 반드시 서술되어야 함.
                    5. 순서는 학습적 측면, 생활적 측면, 예체능적 측면으로 구성되어야 함.
                    6. 두루뭉실한 표현보다는 정확한 표현을 사용해야함.
                    7. 예체능적 측면은 1줄만 서술되어야 함.
                    """
                                        
                    with st.spinner("AI가 데이터를 분석 중입니다..."):
                        response = model.generate_content(prompt)
                        st.success("분석 결과")
                        st.info(response.text)
                        
                except Exception as e:
                    st.error(f"오류 발생: {e}")
