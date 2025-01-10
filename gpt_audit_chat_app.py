import streamlit as st
from excel import process_excel_content
from gpt_aura_reviewer import ExcelDocumentQA
import json
import time
from PIL import Image
import pandas as pd
import io
import xlsxwriter



class AuditReviewChatbot:
    def __init__(self):
        """감사조서 리뷰 챗봇 초기화"""
        self.qa_engine = ExcelDocumentQA()
        
    def process_excel_to_json(self, file_content: bytes, file_name: str) -> dict:
        """엑셀 파일을 JSON 구조로 변환"""
        return process_excel_content(file_content, file_name)
            
    def get_response_stream(self, json_data_list: list, question: str):
        """스트리밍 방식으로 응답 생성"""
        combined_context = {
            'metadata': {
                'total_files': len(json_data_list),
                'files': [data['metadata']['file_name'] for data in json_data_list],
                'sheets_info': {}
            },
            'files_data': json_data_list
        }
        
        messages = [
            {
                "role": "system",
                "content": self.qa_engine._create_system_prompt(combined_context)
            },
            {
                "role": "user",
                "content": f"다음은 엑셀 파일들의 JSON 데이터입니다:\n{json.dumps(combined_context, ensure_ascii=False, indent=2)}\n\n질문: {question}"
            }
        ]

        # OpenAI 스트리밍 응답 생성
        return self.qa_engine.client.chat.completions.create(
            model=self.qa_engine.model,
            messages=messages,
            temperature=0.7,
            stream=True
        )

def initialize_session_state():
    """세션 상태 초기화"""
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    if 'json_data_list' not in st.session_state:
        st.session_state.json_data_list = []
    if 'processing' not in st.session_state:
        st.session_state.processing = False
    if 'uploaded_files' not in st.session_state:
        st.session_state.uploaded_files = set()

def convert_markdown_table_to_df(markdown_text):
    """마크다운 테이블을 DataFrame으로 변환"""
    try:
        # 마크다운 테이블 행을 분리
        lines = markdown_text.strip().split('\n')
        # 헤더와 구분선을 제외한 데이터 행만 추출
        headers = [x.strip() for x in lines[0].split('|')[1:-1]]
        data = []
        for line in lines[3:]:  # 헤더행과 구분선을 건너뛰고 데이터 행부터 처리
            if line.strip():
                row = [x.strip() for x in line.split('|')[1:-1]]
                data.append(row)
        return pd.DataFrame(data, columns=headers)
    except Exception as e:
        st.error(f"테이블 변환 중 오류 발생: {str(e)}")
        return None

def main():
    # 페이지 레이아웃을 wide 모드로 설정
    st.set_page_config(
        page_title="Audit Copilot - Reviewer",
        page_icon="📋",
        layout="wide"
    )
    
    initialize_session_state()
    
    # chatbot 인스턴스 생성
    chatbot = AuditReviewChatbot()
    
    # CSS 스타일 업데이트
    st.markdown("""
        <style>
        .main-header {
            display: flex;
            align-items: flex-end;
            padding: 1rem;
            background-color: #ffffff;
            border-bottom: 1px solid #f0f0f0;
        }
        .logo-img {
            width: 10px;
            margin-right: 5px;
        }
        .title-text {
            color: #000000;
            font-size: 32px;
            font-weight: bold;
            margin-bottom: 0;
            padding-bottom: 5px;
            margin-left: -20px;
        }
        </style>
    """, unsafe_allow_html=True)

    # 헤더 레이아웃
    col1, col2 = st.columns([0.5, 4])
    with col1:
        st.image(
            "https://upload.wikimedia.org/wikipedia/commons/f/f2/Logo-pwc.png",
            width=60
        )
    with col2:
        st.markdown('<p class="title-text">Audit Copilot - Reviewer</p>', unsafe_allow_html=True)
    
    st.markdown("---")

    # 메인 화면 라디오 버튼
    selected_mode = st.radio(
        "모드 선택",
        ["Audit Checker", "Audit Reviewer Chatbot"],
        horizontal=True,  # 가로로 배치
        label_visibility="collapsed"  # 라벨 숨기기
    )

    # 선택된 모드에 따른 내용 표시
    if selected_mode == "Audit Checker":
        st.markdown("""
            <div style='background-color: #f8f9fa; padding: 1rem; border-radius: 10px; margin-bottom: 1rem;'>
                <h4>Audit Checker</h4>
                <p>감사조서의 주요 체크포인트를 자동으로 검토하고 피드백을 제공합니다.</p>
            </div>
        """, unsafe_allow_html=True)
        
        # Audit Checker용 파일 업로더
        checker_file = st.file_uploader(
            "체크리스트 파일을 업로드하세요",
            type=['xlsx', 'xls', 'xlsm'],
            key="checker_file_uploader",  # unique key 추가
            help="체크리스트가 포함된 Excel 파일을 업로드하세요"
        )
        
        # 파일이 업로드되었을 때만 버튼 활성화
        if checker_file is not None:
            if st.button("체크리스트 검토 시작"):
                with st.spinner("체크리스트 검토 중..."):
                    try:
                        # 파일 처리
                        file_content = checker_file.read()
                        json_data = chatbot.process_excel_to_json(file_content, checker_file.name)
                        
                        # 프롬프트 수정
                        prompt = f"""
                        첨부된 감사조서 체크리스트를 검토하고 다음 형식으로 결과를 작성해주세요.

                        | 대번호 | 체크항목 | 소번호 | 체크사항 | 확인여부 | 비고 |
                        |--------|----------|---------|-----------|-----------|------|
                        | 1 | 재권제무조회서 | 1-1 | 매출채권, 매입채무 등 조서 상 Sampling 내역과 실제 발송(Control sheet 등)한 내역이 일치하는지 확인 | O/X | 1) 절차 확인 위치: [시트명/셀 위치]\\n2) 절차 내용: [발견된 구체적 절차 내용]\\n3) 누락된 절차: [있는 경우 기재]\\n[Aura Link](URL) |

                        중요: 
                        1. 첨부된 체크리스트의 대번호, 체크항목, 소번호, 체크사항을 그대로 사용하세요.
                        2. 확인여부는 다음 기준으로 가상의 결과를 생성하세요:
                           - 약 70%는 'O'로 표시 (정상적으로 수행된 것으로 가정)
                           - 약 30%는 'X'로 표시 (미흡하거나 누락된 것으로 가정)
                        3. 비고란에는 각 항목별로 적절한 가상의 검토 내용을 작성하세요:
                           - O인 경우: 정상적으로 수행된 것으로 가정하고 구체적인 확인 내용 작성
                           - X인 경우: 미흡한 부분과 개선사항을 구체적으로 작성

                        요구사항:
                        1. '확인여부' 기준:
                           - O: 해당 절차가 적절히 수행된 것으로 가정
                           - X: 해당 절차가 미흡하거나 누락된 것으로 가정
                        2. '비고' 열은 다음 내용을 포함할 것:
                           a) 절차 확인 위치: 구체적인 시트명과 위치 (예: "매출채권조회 시트 B15:D25")
                           b) 절차 내용: 구체적인 확인 내용이나 미흡사항
                           c) 누락된 절차: X인 경우 구체적인 미비점
                           d) Aura 링크 (각 체크항목 관련):
                              - 재고자산 실사입회: https://aura.pwc.com/engagement/2024/workpaper/inventory_observation
                              - 매출채권 조회확인: https://aura.pwc.com/engagement/2024/workpaper/ar_confirmation
                              - 매입채무 조회확인: https://aura.pwc.com/engagement/2024/workpaper/ap_confirmation
                              - 우발채무 및 약정사항: https://aura.pwc.com/engagement/2024/workpaper/contingent_liabilities

                        체크리스트 데이터: {json_data}

                        위 체크리스트의 각 항목을 검토하고 결과를 표 형식으로 작성해주세요.
                        """
                        
                        messages = [
                            {
                                "role": "system", 
                                "content": """당신은 풍부한 경험을 가진 감사 전문가입니다. 
                                첨크리스트의 각 항목에 대해 현실적인 가상의 검토 결과를 생성합니다.
                                약 70%는 정상 수행(O), 30%는 미흡(X)한 것으로 가정하여 
                                실제 감사 현장에서 발생할 수 있는 현실적인 시나리오를 제시합니다."""
                            },
                            {"role": "user", "content": prompt}
                        ]
                        
                        # 응답 컨테이너 생성 및 스트리밍 처리
                        response_container = st.empty()
                        full_response = ""
                        
                        for chunk in chatbot.qa_engine.client.chat.completions.create(
                            model=chatbot.qa_engine.model,
                            messages=messages,
                            temperature=0.7,
                            stream=True
                        ):
                            if chunk.choices[0].delta.content is not None:
                                content = chunk.choices[0].delta.content
                                full_response += content
                                response_container.markdown(full_response + "▌")
                        
                        response_container.markdown(full_response)
                        
                        # 최종 응답 표시
                        final_response = full_response.replace('\\n', '<br>')
                        response_container.markdown(final_response, unsafe_allow_html=True)
                        st.session_state.messages.append({"role": "assistant", "content": full_response})
                        
                        # 결과를 DataFrame으로 변환
                        df = convert_markdown_table_to_df(full_response.replace('<br>', '\n'))
                        
                        if df is not None:
                            # Excel 파일 생성
                            buffer = io.BytesIO()
                            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                                df.to_excel(writer, sheet_name='검토결과', index=False)
                                
                                # 워크시트와 워크북 가져오기
                                worksheet = writer.sheets['검토결과']
                                workbook = writer.book
                                
                                # 셀 서식 설정
                                wrap_format = workbook.add_format({'text_wrap': True, 'valign': 'top'})
                                header_format = workbook.add_format({
                                    'bold': True,
                                    'text_wrap': True,
                                    'valign': 'top',
                                    'align': 'center',
                                    'bg_color': '#D9D9D9'
                                })
                                
                                # 헤더 서식 적용
                                for col_num, value in enumerate(df.columns.values):
                                    worksheet.write(0, col_num, value, header_format)
                                
                                # 열 너비 자동 조정 및 셀 서식 적용
                                worksheet.set_column('A:A', 10)  # 대번호
                                worksheet.set_column('B:B', 20)  # 체크항목
                                worksheet.set_column('C:C', 10)  # 소번호
                                worksheet.set_column('D:D', 40)  # 체크사항
                                worksheet.set_column('E:E', 10)  # 확인여부
                                worksheet.set_column('F:F', 50)  # 비고
                                
                                # 모든 데이터 셀에 줄바꿈 서식 적용
                                for row in range(1, len(df) + 1):
                                    for col in range(len(df.columns)):
                                        worksheet.write(row, col, df.iloc[row-1, col], wrap_format)
                            
                            # 다운로드 버튼 생성
                            st.download_button(
                                label="📥 검토 결과 엑셀 다운로드",
                                data=buffer.getvalue(),
                                file_name="감사조서_검토결과.xlsx",
                                mime="application/vnd.ms-excel"
                            )
                        
                    except Exception as e:
                        st.error(f"체크리스트 검토 중 오류가 발생했습니다: {str(e)}")
        else:
            st.info("👆 체크리스트 파일을 먼저 업로드해주세요.")
    
    else:
        st.markdown("""
            <div style='background-color: #f8f9fa; padding: 1rem; border-radius: 10px; margin-bottom: 1rem;'>
                <h4>Audit Reviewer Chatbot</h4>
                <p>AI 챗봇과 대화하며 감사조서에 대한 상세한 리뷰를 받을 수 있습니다.</p>
            </div>
        """, unsafe_allow_html=True)
        
        # 사이드바에 파일 업로더와 파일 목록 표시
        with st.sidebar:
            st.header("파일 관리")
            
            # Aura URL 입력 섹션 추가
            st.markdown("### Aura URL")
            aura_url = st.text_input(
                "Aura URL을 입력하세요",
                placeholder="https://aura.pwc.com/...",
                help="Aura 시스템의 감사조서 URL을 입력하세요"
            )
            
            if st.button("URL 제출"):
                if aura_url:
                    st.success("URL이 제출되었습니다: " + aura_url)
                else:
                    st.warning("URL을 입력해주세요.")
            
            st.markdown("---")  # URL 섹션과 파일 업로드 섹션 구분
            
            # 기존의 파일 업로더
            uploaded_files = st.file_uploader(
                "감사조서 파일을 업로드하세요 (XLSM)",
                type=['xlsm'],
                accept_multiple_files=True,
                help="여러 개의 파일을 동시에 업로드할 수 있습니다. (최대 200MB/파일)"
            )
            
            # 업로드된 파일 처리
            if uploaded_files:
                for uploaded_file in uploaded_files:
                    file_name = uploaded_file.name
                    
                    # 새로운 파일만 처리
                    if file_name not in st.session_state.uploaded_files:
                        try:
                            st.session_state.processing = True
                            
                            # 파일 크기 확인
                            file_size = uploaded_file.size / (1024 * 1024)  # MB로 변환
                            if file_size > 200:
                                st.error(f"파일 '{file_name}'이 200MB를 초과합니다.")
                                continue
                            
                            # 파일 처리
                            with st.spinner(f"'{file_name}' 처리 중..."):
                                file_content = uploaded_file.read()
                                json_data = chatbot.process_excel_to_json(file_content, file_name)
                                
                                if json_data:
                                    st.session_state.json_data_list.append(json_data)
                                    st.session_state.uploaded_files.add(file_name)
                                    st.success(f"✅ '{file_name}' 분석 완료!")
                        
                        except Exception as e:
                            st.error(f"'{file_name}' 처리 중 오류 발생: {str(e)}")
                        
                        finally:
                            st.session_state.processing = False
            
            # 업로드된 파일 목록 표시
            if st.session_state.uploaded_files:
                st.write("### 분석된 파일 목록")
                for idx, file_name in enumerate(st.session_state.uploaded_files, 1):
                    st.write(f"{idx}. {file_name}")
                
                if st.button("모든 파일 초기화"):
                    st.session_state.messages = []
                    st.session_state.json_data_list = []
                    st.session_state.uploaded_files = set()
                    st.session_state.processing = False
                    st.rerun()

    # 메인 영역: 채팅 인터페이스
    if st.session_state.json_data_list:
        # 이전 메시지 표시
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                # 실제 줄바꿈으로 변환하고 HTML로 렌더링
                content = message["content"].replace('\\n', '<br>')
                st.markdown(content, unsafe_allow_html=True)
        
        # 사용자 입력
        if prompt := st.chat_input("질문을 입력하세요"):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
            
            # 어시스턴트 응답
            with st.chat_message("assistant"):
                response_container = st.empty()
                full_response = ""
                
                try:
                    for chunk in chatbot.get_response_stream(st.session_state.json_data_list, prompt):
                        if chunk.choices[0].delta.content is not None:
                            content = chunk.choices[0].delta.content
                            full_response += content
                            # HTML 줄바꿈으로 변환하여 표시
                            display_response = full_response.replace('\\n', '<br>')
                            response_container.markdown(display_response + "▌", unsafe_allow_html=True)
                    
                    # 최종 응답 표시
                    final_response = full_response.replace('\\n', '<br>')
                    response_container.markdown(final_response, unsafe_allow_html=True)
                    st.session_state.messages.append({"role": "assistant", "content": full_response})
                    
                except Exception as e:
                    st.error(f"응답 생성 중 오류가 발생했습니다: {str(e)}")

if __name__ == "__main__":
    main() 