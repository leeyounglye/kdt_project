# ============================================================
# 1. 라이브러리 import
# ============================================================
import os
import base64
from datetime import date
from typing import TypedDict

import requests
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, START, END


# ============================================================
# 2. 환경 변수 로드
# ============================================================
load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")


# ============================================================
# 3. 월별 카테고리 예산
# ============================================================
MONTHLY_BUDGET = {
    "식비": 400000,
    "교통비": 150000,
    "생활비": 300000,
    "쇼핑": 200000,
    "IT구독": 100000,
    "기타": 100000
}


# ============================================================
# 4. LangGraph State
# ============================================================
class ExpenseState(TypedDict):

    # --------------------------------------------------------
    # 입력 정보
    # --------------------------------------------------------
    input_type: str
    user_input: str
    image_path: str

    # --------------------------------------------------------
    # 분석된 지출 정보
    # --------------------------------------------------------
    merchant: str
    expense_date: str
    amount: int
    category: str
    payment_method: str

    # --------------------------------------------------------
    # Notion 기존 지출
    # --------------------------------------------------------
    monthly_spent: int

    # --------------------------------------------------------
    # 예산 정보
    # --------------------------------------------------------
    budget: int
    remaining_budget: int

    # --------------------------------------------------------
    # AI 평가
    # --------------------------------------------------------
    feedback: str

    # --------------------------------------------------------
    # 중복 확인
    # --------------------------------------------------------
    is_duplicate: bool
    duplicate_message: str

    # --------------------------------------------------------
    # 예산 계산용 총 지출
    # --------------------------------------------------------
    total_spent: int

    # --------------------------------------------------------
    # Notion 저장 결과
    # --------------------------------------------------------
    notion_saved: bool


# ============================================================
# 5. Structured Output 정의
# ============================================================
class ExpenseInfo(BaseModel):

    merchant: str = Field(
        description="상호명"
    )

    amount: int = Field(
        description="결제 금액. 숫자만 반환"
    )

    category: str = Field(
        description="식비, 교통비, 생활비, 쇼핑, IT구독, 기타 중 하나"
    )

    payment_method: str = Field(
        description="신용카드, 체크카드, 현금 중 하나"
    )


class ReceiptInfo(BaseModel):

    merchant: str = Field(
        description="영수증의 상호명 또는 매장명"
    )

    expense_date: str = Field(
        description="결제 날짜. YYYY-MM-DD 형식"
    )

    amount: int = Field(
        description="최종 결제 금액. 숫자만 반환"
    )

    category: str = Field(
        description="식비, 교통비, 생활비, 쇼핑, IT구독, 기타 중 하나"
    )

    payment_method: str = Field(
        description="신용카드, 체크카드, 현금 중 하나"
    )


# ============================================================
# 6. LLM 생성
# ============================================================
llm = ChatOpenAI(
    model="gpt-4o",
    temperature=0
)


# 텍스트 분석용 Structured Output
expense_llm = llm.with_structured_output(
    ExpenseInfo
)


# 영수증 분석용 Structured Output
receipt_llm = llm.with_structured_output(
    ReceiptInfo
)


# ============================================================
# 7-1. Routing : 입력 종류 판단
# ============================================================
def route_input(state: ExpenseState) -> str:

    if state["input_type"] == "image":
        return "image"

    return "text"


# ============================================================
# 7-2. Node : 텍스트 지출 분석
# ============================================================
def extract_expense(state: ExpenseState) -> ExpenseState:

    prompt = f"""
다음 사용자의 지출 문장을 분석하세요.

사용자 입력:
{state["user_input"]}

다음 정보를 추출하세요.

1. 상호명
2. 결제 금액
3. 카테고리
4. 결제수단

카테고리는 반드시 다음 중 하나입니다.

식비
교통비
생활비
쇼핑
IT구독
기타

결제수단은 반드시 다음 중 하나입니다.

신용카드
체크카드
현금
"""

    data = expense_llm.invoke([
        HumanMessage(content=prompt)
    ])

    return {
        **state,

        "merchant": data.merchant,
        "expense_date": date.today().isoformat(),
        "amount": data.amount,
        "category": data.category,
        "payment_method": data.payment_method
    }


# ============================================================
# 7-3. 이미지 → Base64
# ============================================================
def encode_image(image_path):

    with open(image_path, "rb") as image_file:

        return base64.b64encode(
            image_file.read()
        ).decode("utf-8")


# ============================================================
# 7-4. Node : 영수증 이미지 분석
# ============================================================
def analyze_receipt(state: ExpenseState) -> ExpenseState:

    image_path = state["image_path"]

    base64_image = encode_image(image_path)

    message = [
        {
            "role": "user",

            "content": [

                {
                    "type": "text",

                    "text": """
이 영수증 이미지를 분석하세요.

다음 정보를 추출하세요.

1. 상호명 또는 매장명
2. 결제 날짜
3. 최종 결제 금액
4. 카테고리
5. 결제수단

카테고리는 반드시 다음 중 하나입니다.

식비
교통비
생활비
쇼핑
IT구독
기타

결제수단은 반드시 다음 중 하나입니다.

신용카드
체크카드
현금
"""
                },

                {
                    "type": "image_url",

                    "image_url": {
                        "url":
                        f"data:image/jpeg;base64,{base64_image}"
                    }
                }
            ]
        }
    ]

    data = receipt_llm.invoke(message)

    return {
        **state,

        "merchant": data.merchant,
        "expense_date": data.expense_date,
        "amount": data.amount,
        "category": data.category,
        "payment_method": data.payment_method
    }


# ============================================================
# 7-5. Node : Notion 중복 지출 확인
# ============================================================
def check_duplicate(state: ExpenseState) -> ExpenseState:

    url = (
        f"https://api.notion.com/v1/databases/"
        f"{NOTION_DATABASE_ID}/query"
    )

    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

    # 날짜 + 상호명 + 금액 + 카테고리 + 결제수단이 모두 같으면
    # 같은 지출로 판단합니다.
    payload = {
        "page_size": 1,
        "filter": {
            "and": [
                {
                    "property": "날짜",
                    "date": {
                        "equals": state["expense_date"]
                    }
                },
                {
                    "property": "상호명",
                    "title": {
                        "equals": state["merchant"]
                    }
                },
                {
                    "property": "금액",
                    "number": {
                        "equals": state["amount"]
                    }
                },
                {
                    "property": "카테고리",
                    "multi_select": {
                        "contains": state["category"]
                    }
                },
                {
                    "property": "결제수단",
                    "select": {
                        "equals": state["payment_method"]
                    }
                }
            ]
        }
    }

    response = requests.post(
        url,
        headers=headers,
        json=payload
    )

    if response.status_code != 200:
        print()
        print("Notion 중복 조회 실패")
        print(response.text)

        # 중복 조회 자체가 실패한 경우에는 안전하게 저장을 막습니다.
        # 같은 지출이 여러 번 저장되는 것보다 사용자가 확인하도록 하는 편이 안전합니다.
        return {
            **state,
            "is_duplicate": True,
            "duplicate_message":
                "Notion 중복 조회에 실패하여 자동 저장을 중단했습니다."
        }

    data = response.json()
    is_duplicate = len(data.get("results", [])) > 0

    if is_duplicate:
        message = (
            "동일한 날짜, 상호명, 금액, 카테고리, 결제수단의 "
            "지출이 이미 Notion에 등록되어 있습니다."
        )
    else:
        message = "중복 지출이 아닙니다."

    return {
        **state,
        "is_duplicate": is_duplicate,
        "duplicate_message": message
    }


# ============================================================
# 7-6. Node : Notion 기존 월 지출 조회
# ============================================================
def get_monthly_spent(state: ExpenseState) -> ExpenseState:

    category = state["category"]

    # --------------------------------------------------------
    # 지출 날짜를 기준으로 해당 월 계산
    #
    # 예:
    # 2026-04-09
    #      ↓
    # 2026-04-01 ~ 2026-05-01
    # --------------------------------------------------------
    year = int(state["expense_date"][0:4])
    month = int(state["expense_date"][5:7])

    start_date = f"{year:04d}-{month:02d}-01"

    if month == 12:
        next_year = year + 1
        next_month = 1
    else:
        next_year = year
        next_month = month + 1

    next_month_date = (
        f"{next_year:04d}-{next_month:02d}-01"
    )


    url = (
        f"https://api.notion.com/v1/databases/"
        f"{NOTION_DATABASE_ID}/query"
    )

    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }


    payload = {
        "filter": {
            "and": [

                {
                    "property": "날짜",
                    "date": {
                        "on_or_after": start_date
                    }
                },

                {
                    "property": "날짜",
                    "date": {
                        "before": next_month_date
                    }
                },

                {
                    "property": "카테고리",
                    "multi_select": {
                        "contains": category
                    }
                }
            ]
        }
    }


    response = requests.post(
        url,
        headers=headers,
        json=payload
    )


    if response.status_code != 200:

        print()
        print("Notion 조회 실패")
        print(response.text)

        return {
            **state,
            "monthly_spent": 0
        }


    data = response.json()

    monthly_spent = 0


    for page in data["results"]:

        amount = (
            page["properties"]["금액"]["number"]
        )

        if amount is not None:
            monthly_spent += amount


    return {
        **state,
        "monthly_spent": monthly_spent
    }


# ============================================================
# 7-7. Node : 예산 계산
# ============================================================
def calculate_budget(state: ExpenseState) -> ExpenseState:

    category = state["category"]

    budget = MONTHLY_BUDGET[category]

    # 이미 Notion에 등록된 중복 지출이라면 monthly_spent 안에
    # 해당 금액이 이미 포함되어 있으므로 다시 더하지 않습니다.
    if state["is_duplicate"]:
        total_spent = state["monthly_spent"]
    else:
        total_spent = (
            state["monthly_spent"]
            + state["amount"]
        )

    remaining_budget = (
        budget - total_spent
    )

    return {
        **state,
        "budget": budget,
        "total_spent": total_spent,
        "remaining_budget": remaining_budget
    }


# ============================================================
# 7-8. Routing : 예산 초과 판단
# ============================================================
def route_budget(state: ExpenseState) -> str:

    if state["remaining_budget"] < 0:
        return "overspending"

    return "normal"


# ============================================================
# 7-9. Node : 정상 지출 피드백
# ============================================================
def normal_feedback(state: ExpenseState) -> ExpenseState:

    feedback = (
        f"{state['category']} 예산 범위 내의 지출입니다. "
        f"현재 남은 예산은 "
        f"{state['remaining_budget']:,}원입니다."
    )

    return {
        **state,
        "feedback": feedback
    }


# ============================================================
# 7-10. Node : 과소비 AI 피드백
# ============================================================
def overspending_feedback(state: ExpenseState) -> ExpenseState:

    exceeded_amount = abs(
        state["remaining_budget"]
    )

    prompt = f"""
사용자가 월 예산을 초과했습니다.

카테고리:
{state["category"]}

월 예산:
{state["budget"]}원

기존 월 지출:
{state["monthly_spent"]}원

이번 지출:
{state["amount"]}원

초과 금액:
{exceeded_amount}원

사용자가 실천할 수 있는
간단한 절약 방법을 2~3문장으로 알려주세요.
"""

    response = llm.invoke([
        HumanMessage(content=prompt)
    ])

    return {
        **state,
        "feedback": response.content
    }


# ============================================================
# 7-11. Routing : 중복이면 저장하지 않음
# ============================================================
def route_save(state: ExpenseState) -> str:

    if state["is_duplicate"]:
        return "duplicate"

    return "save"


# ============================================================
# 7-12. Node : Notion 저장
# ============================================================
def save_to_notion(state: ExpenseState) -> ExpenseState:

    url = "https://api.notion.com/v1/pages"

    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }


    payload = {

        "parent": {
            "database_id": NOTION_DATABASE_ID
        },

        "properties": {

            "상호명": {
                "title": [
                    {
                        "text": {
                            "content":
                            state["merchant"]
                        }
                    }
                ]
            },

            "날짜": {
                "date": {
                    "start":
                    state["expense_date"]
                }
            },

            "금액": {
                "number":
                state["amount"]
            },

            "카테고리": {
                "multi_select": [
                    {
                        "name":
                        state["category"]
                    }
                ]
            },

            "결제수단": {
                "select": {
                    "name":
                    state["payment_method"]
                }
            }
        }
    }


    response = requests.post(
        url,
        headers=headers,
        json=payload
    )


    if response.status_code == 200:

        return {
            **state,
            "notion_saved": True
        }


    print()
    print("Notion 저장 실패")
    print("상태 코드:", response.status_code)
    print("응답:", response.text)


    return {
        **state,
        "notion_saved": False
    }


# ============================================================
# 7-13. Streamlit 대시보드용 월별 지출 조회
# ============================================================
def get_monthly_expense_records(year: int, month: int) -> list[dict]:
    """Notion에서 지정한 월의 모든 지출 내역을 조회합니다.

    Notion API는 한 번에 가져올 수 있는 결과 수가 제한되어 있으므로
    has_more / next_cursor를 사용해 페이지네이션합니다.
    """

    start_date = f"{year:04d}-{month:02d}-01"

    if month == 12:
        next_year = year + 1
        next_month = 1
    else:
        next_year = year
        next_month = month + 1

    next_month_date = f"{next_year:04d}-{next_month:02d}-01"

    url = (
        f"https://api.notion.com/v1/databases/"
        f"{NOTION_DATABASE_ID}/query"
    )

    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

    records = []
    next_cursor = None

    while True:
        payload = {
            "page_size": 100,
            "filter": {
                "and": [
                    {
                        "property": "날짜",
                        "date": {
                            "on_or_after": start_date
                        }
                    },
                    {
                        "property": "날짜",
                        "date": {
                            "before": next_month_date
                        }
                    }
                ]
            },
            "sorts": [
                {
                    "property": "날짜",
                    "direction": "ascending"
                }
            ]
        }

        if next_cursor:
            payload["start_cursor"] = next_cursor

        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=30
        )

        if response.status_code != 200:
            raise RuntimeError(
                "Notion 월별 지출 조회 실패: "
                f"{response.status_code} - {response.text}"
            )

        data = response.json()

        for page in data.get("results", []):
            props = page.get("properties", {})

            title_items = props.get("상호명", {}).get("title", [])
            merchant = ""
            if title_items:
                merchant = title_items[0].get("plain_text", "")

            date_value = (
                props.get("날짜", {})
                .get("date")
            )
            expense_date = date_value.get("start", "") if date_value else ""

            amount = props.get("금액", {}).get("number") or 0

            category_items = (
                props.get("카테고리", {})
                .get("multi_select", [])
            )
            category = (
                category_items[0].get("name", "기타")
                if category_items else "기타"
            )

            payment_value = (
                props.get("결제수단", {})
                .get("select")
            )
            payment_method = (
                payment_value.get("name", "")
                if payment_value else ""
            )

            records.append({
                "날짜": expense_date,
                "상호명": merchant,
                "금액": int(amount),
                "카테고리": category,
                "결제수단": payment_method,
            })

        if not data.get("has_more"):
            break

        next_cursor = data.get("next_cursor")
        if not next_cursor:
            break

    return records


# ============================================================
# 8. LangGraph 구성
# ============================================================
graph = StateGraph(ExpenseState)


# ------------------------------------------------------------
# Node 등록
# ------------------------------------------------------------
graph.add_node(
    "extract_expense",
    extract_expense
)

graph.add_node(
    "analyze_receipt",
    analyze_receipt
)

graph.add_node(
    "check_duplicate",
    check_duplicate
)

graph.add_node(
    "get_monthly_spent",
    get_monthly_spent
)

graph.add_node(
    "calculate_budget",
    calculate_budget
)

graph.add_node(
    "normal_feedback",
    normal_feedback
)

graph.add_node(
    "overspending_feedback",
    overspending_feedback
)

graph.add_node(
    "save_to_notion",
    save_to_notion
)


# ============================================================
# 9. 입력 종류에 따른 첫 번째 Routing
# ============================================================
graph.add_conditional_edges(

    START,

    route_input,

    {
        "text": "extract_expense",
        "image": "analyze_receipt"
    }
)


# ============================================================
# 10. 두 경로를 다시 하나로 합치기
# ============================================================
graph.add_edge(
    "extract_expense",
    "check_duplicate"
)

graph.add_edge(
    "analyze_receipt",
    "check_duplicate"
)

graph.add_edge(
    "check_duplicate",
    "get_monthly_spent"
)


# ============================================================
# 11. 예산 계산
# ============================================================
graph.add_edge(
    "get_monthly_spent",
    "calculate_budget"
)


# ============================================================
# 12. 예산에 따른 두 번째 Routing
# ============================================================
graph.add_conditional_edges(

    "calculate_budget",

    route_budget,

    {
        "normal":
            "normal_feedback",

        "overspending":
            "overspending_feedback"
    }
)


# ============================================================
# 13. 중복 여부에 따른 저장 Routing
# ============================================================
graph.add_conditional_edges(
    "normal_feedback",
    route_save,
    {
        "duplicate": END,
        "save": "save_to_notion"
    }
)

graph.add_conditional_edges(
    "overspending_feedback",
    route_save,
    {
        "duplicate": END,
        "save": "save_to_notion"
    }
)


# ============================================================
# 14. 종료
# ============================================================
graph.add_edge(
    "save_to_notion",
    END
)


# 그래프 컴파일
app = graph.compile()


# ============================================================
# 15. 프로그램 실행
# ============================================================
if __name__ == "__main__":

    # ========================================================
    # ★ 테스트 종류 선택
    #
    # "text"  → 텍스트 지출 테스트
    # "image" → 영수증 테스트
    # ========================================================
    TEST_TYPE = "image"


    # ========================================================
    # 텍스트 테스트
    # ========================================================
    if TEST_TYPE == "text":

        inputs = {

            "input_type": "text",

            "user_input":
                "스타벅스에서 5500원 신용카드로 결제했어요",

            "image_path": "",

            "merchant": "",
            "expense_date": "",
            "amount": 0,
            "category": "",
            "payment_method": "",

            "monthly_spent": 0,

            "budget": 0,
            "remaining_budget": 0,

            "feedback": "",

            "is_duplicate": False,
            "duplicate_message": "",
            "total_spent": 0,

            "notion_saved": False
        }


    # ========================================================
    # 영수증 이미지 테스트
    # ========================================================
    else:

        inputs = {

            "input_type": "image",

            "user_input": "",

            "image_path":
                "receipt.jpg",

            "merchant": "",
            "expense_date": "",
            "amount": 0,
            "category": "",
            "payment_method": "",

            "monthly_spent": 0,

            "budget": 0,
            "remaining_budget": 0,

            "feedback": "",

            "is_duplicate": False,
            "duplicate_message": "",
            "total_spent": 0,

            "notion_saved": False
        }


    # ========================================================
    # LangGraph 실행
    # ========================================================
    result = app.invoke(inputs)


    # ========================================================
    # 결과 출력
    # ========================================================
    print()
    print("========== 스마트 지출 분석 ==========")

    print("입력 종류      :", result["input_type"])
    print("상호명         :", result["merchant"])
    print("날짜           :", result["expense_date"])
    print("금액           :", result["amount"])
    print("카테고리       :", result["category"])
    print("결제수단       :", result["payment_method"])

    print("--------------------------------------")

    print("기존 월 지출   :", result["monthly_spent"])
    print("이번 지출      :", result["amount"])

    print(
        "총 지출        :",
        result["total_spent"]
    )

    print("--------------------------------------")

    print("월 예산        :", result["budget"])
    print("남은 예산      :", result["remaining_budget"])

    print("--------------------------------------")

    print("AI 평가        :", result["feedback"])

    print("--------------------------------------")

    if result["is_duplicate"]:
        print("중복 여부      : 중복")
        print("중복 안내      :", result["duplicate_message"])
        print("Notion 저장    : 중복으로 저장 생략")
    elif result["notion_saved"]:
        print("중복 여부      : 신규")
        print("Notion 저장    : 성공")
    else:
        print("중복 여부      : 신규")
        print("Notion 저장    : 실패")

    print("======================================")