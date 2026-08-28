# 💳 스마트 지출관리

LangGraph + OpenAI + Notion + Streamlit을 활용한 스마트 지출관리 프로젝트입니다.

사용자는 텍스트로 지출 내역을 입력하거나 영수증 이미지를 업로드할 수 있으며,
OpenAI가 지출 정보를 분석하고 LangGraph가 처리 흐름을 제어합니다.
분석된 결과는 Notion 데이터베이스에 저장되고, Streamlit에서 월간 지출 현황을 확인할 수 있습니다.

---

## 주요 기능

- 텍스트 기반 지출 입력
- 영수증 이미지 분석
- 상호명, 날짜, 금액, 카테고리, 결제수단 자동 추출
- Notion 기존 월 지출 조회
- 카테고리별 월 예산 계산
- 정상 지출 / 예산 초과 Routing
- AI 기반 소비 피드백
- 동일 지출 중복 저장 방지
- Notion 자동 저장
- Streamlit 웹 UI
- 월간 지출 대시보드

---

## 프로젝트 처리 흐름

```text
텍스트 입력 / 영수증 이미지
        ↓
OpenAI 지출 정보 분석
        ↓
Notion 기존 월 지출 조회
        ↓
월 예산 계산
        ↓
LangGraph Routing
   ├─ 정상 지출
   └─ 예산 초과
        ↓
AI 피드백
        ↓
중복 지출 확인
        ↓
Notion 자동 저장
        ↓
Streamlit 결과 및 월간 대시보드 표시
```

---

## 사용 기술

- Python
- LangGraph
- LangChain
- OpenAI API
- Notion API
- Streamlit
- Pandas
- Requests
- python-dotenv
- Git / GitHub
- Streamlit Community Cloud

---

## 프로젝트 파일

```text
kdt_project/
├─ expense_graph.py
├─ streamlit_app.py
├─ requirements.txt
├─ .gitignore
└─ README.md
```

### `expense_graph.py`

LangGraph의 핵심 로직을 담당합니다.

- 텍스트 지출 분석
- 영수증 이미지 분석
- Notion 데이터 조회
- 예산 계산
- Routing
- AI 피드백
- 중복 지출 확인
- Notion 저장
- 월간 지출 데이터 조회

### `streamlit_app.py`

사용자 웹 화면을 담당합니다.

- 텍스트 입력
- 영수증 이미지 업로드
- 지출 분석 결과 표시
- 월간 대시보드 표시

---

## 환경 변수

프로젝트 실행에는 다음 환경 변수가 필요합니다.

```env
OPENAI_API_KEY=your_openai_api_key
NOTION_TOKEN=your_notion_token
NOTION_DATABASE_ID=your_notion_database_id
```

실제 키가 들어 있는 `.env` 파일은 GitHub에 업로드하지 않습니다.

`.gitignore`에 다음 항목이 포함되어 있어야 합니다.

```gitignore
.env
.env.*
```

Streamlit Community Cloud에서는 `.env` 대신 **Secrets**에 다음 형식으로 등록합니다.

```toml
OPENAI_API_KEY = "your_openai_api_key"
NOTION_TOKEN = "your_notion_token"
NOTION_DATABASE_ID = "your_notion_database_id"
```

---

## 설치

프로젝트 폴더에서 필요한 패키지를 설치합니다.

```bash
pip install -r requirements.txt
```

---

## 로컬 실행

```bash
python -m streamlit run streamlit_app.py
```

실행 후 브라우저에서 일반적으로 다음 주소로 접속합니다.

```text
http://localhost:8501
```

---

## GitHub 업로드 기본 순서

```bash
git status
git add 파일명
git commit -m "수정 내용"
git push origin main
```

GitHub의 최신 내용을 로컬로 가져올 때는 다음 명령을 사용합니다.

```bash
git pull origin main
```

---

## Streamlit Community Cloud 배포

배포 시 다음 항목을 지정합니다.

```text
Repository     : leeyounglye/kdt_project
Branch         : main
Main file path : streamlit_app.py
```

그리고 Advanced settings의 Secrets에 OpenAI / Notion 환경 변수를 등록합니다.

---

## 주의사항

- `.env` 파일을 GitHub에 올리지 않습니다.
- OpenAI API Key와 Notion Token을 코드에 직접 작성하지 않습니다.
- 실제 영수증 이미지에 개인정보나 결제정보가 포함되어 있다면 공개 저장소에 업로드하지 않는 것을 권장합니다.
- 테스트용 중간 파일은 필요할 때만 Git에 추가합니다.

---

## 현재 구현 상태

현재 다음 기능까지 구현 및 테스트가 완료되었습니다.

- 텍스트 지출 분석
- 영수증 이미지 분석
- LangGraph 통합 처리
- Notion 조회 및 자동 저장
- 예산 초과 Routing
- AI 피드백
- 중복 저장 방지
- Streamlit 웹 UI
- 월간 대시보드
- GitHub 연동
- Streamlit Community Cloud 배포
