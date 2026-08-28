import os
import tempfile
from datetime import date

import pandas as pd
import streamlit as st

from expense_graph import MONTHLY_BUDGET, app, get_monthly_expense_records


st.set_page_config(
    page_title="스마트 지출관리",
    page_icon="💳",
    layout="wide",
)

st.title("💳 스마트 지출관리")
st.caption("LangGraph + OpenAI + Notion 기반 지출 분석")


def make_initial_state(input_type: str, user_input: str = "", image_path: str = ""):
    """expense_graph.py의 ExpenseState에 맞는 초기 상태를 생성합니다."""
    return {
        "input_type": input_type,
        "user_input": user_input,
        "image_path": image_path,
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
        "notion_saved": False,
    }


def show_result(result):
    st.success("지출 분석이 완료되었습니다.")

    st.subheader("분석 결과")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("상호명", result["merchant"])
        st.metric("금액", f"{result['amount']:,}원")

    with col2:
        st.metric("카테고리", result["category"])
        st.metric("결제수단", result["payment_method"])

    with col3:
        st.metric("날짜", result["expense_date"])
        st.metric("남은 예산", f"{result['remaining_budget']:,}원")

    st.subheader("월 예산 현황")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("기존 월 지출", f"{result['monthly_spent']:,}원")
    c2.metric("이번 지출", f"{result['amount']:,}원")
    c3.metric("총 지출", f"{result['total_spent']:,}원")
    c4.metric("월 예산", f"{result['budget']:,}원")

    if result["remaining_budget"] < 0:
        st.error(f"예산을 {abs(result['remaining_budget']):,}원 초과했습니다.")
    else:
        st.info(f"남은 예산은 {result['remaining_budget']:,}원입니다.")

    st.subheader("AI 피드백")
    st.write(result["feedback"])

    if result["is_duplicate"]:
        st.warning("이미 등록된 지출입니다. Notion에 중복 저장하지 않았습니다.")
        st.caption(result["duplicate_message"])
    elif result["notion_saved"]:
        st.success("Notion 저장 성공")
    else:
        st.warning("Notion 저장 실패")


def show_dashboard(year: int, month: int):
    with st.spinner("Notion에서 월별 지출 데이터를 불러오는 중입니다..."):
        records = get_monthly_expense_records(year, month)

    st.subheader(f"{year}년 {month}월 지출 현황")

    if not records:
        st.info("선택한 월에 등록된 지출 내역이 없습니다.")
        return

    df = pd.DataFrame(records)
    df["금액"] = pd.to_numeric(df["금액"], errors="coerce").fillna(0).astype(int)

    total_spent = int(df["금액"].sum())
    transaction_count = len(df)
    average_spent = int(total_spent / transaction_count) if transaction_count else 0
    total_budget = sum(MONTHLY_BUDGET.values())
    total_remaining = total_budget - total_spent

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("월 총지출", f"{total_spent:,}원")
    c2.metric("지출 건수", f"{transaction_count}건")
    c3.metric("평균 지출", f"{average_spent:,}원")
    c4.metric("전체 예산 잔액", f"{total_remaining:,}원")

    st.divider()
    st.subheader("카테고리별 지출")

    category_spent = (
        df.groupby("카테고리", as_index=False)["금액"]
        .sum()
        .rename(columns={"금액": "지출액"})
    )

    category_rows = []
    for category, budget in MONTHLY_BUDGET.items():
        match = category_spent[category_spent["카테고리"] == category]
        spent = int(match["지출액"].iloc[0]) if not match.empty else 0
        remaining = budget - spent
        usage_rate = (spent / budget * 100) if budget else 0

        category_rows.append({
            "카테고리": category,
            "월 예산": budget,
            "지출액": spent,
            "남은 예산": remaining,
            "예산 사용률(%)": round(usage_rate, 1),
        })

    budget_df = pd.DataFrame(category_rows)

    chart_df = budget_df.set_index("카테고리")[["지출액", "월 예산"]]
    st.bar_chart(chart_df)

    display_budget_df = budget_df.copy()
    display_budget_df["월 예산"] = display_budget_df["월 예산"].map(lambda x: f"{x:,}원")
    display_budget_df["지출액"] = display_budget_df["지출액"].map(lambda x: f"{x:,}원")
    display_budget_df["남은 예산"] = display_budget_df["남은 예산"].map(lambda x: f"{x:,}원")
    display_budget_df["예산 사용률(%)"] = display_budget_df["예산 사용률(%)"].map(lambda x: f"{x:.1f}%")

    st.dataframe(
        display_budget_df,
        use_container_width=True,
        hide_index=True,
    )

    over_budget = budget_df[budget_df["남은 예산"] < 0]
    if not over_budget.empty:
        names = ", ".join(over_budget["카테고리"].tolist())
        st.error(f"예산을 초과한 카테고리: {names}")

    st.divider()
    st.subheader("일자별 지출")
    daily_df = (
        df.groupby("날짜", as_index=False)["금액"]
        .sum()
        .set_index("날짜")
    )
    st.bar_chart(daily_df)

    st.divider()
    st.subheader("상세 지출 내역")
    detail_df = df[["날짜", "상호명", "카테고리", "결제수단", "금액"]].copy()
    detail_df = detail_df.sort_values("날짜", ascending=False)
    detail_df["금액"] = detail_df["금액"].map(lambda x: f"{x:,}원")

    st.dataframe(
        detail_df,
        use_container_width=True,
        hide_index=True,
    )


tab_text, tab_image, tab_dashboard = st.tabs([
    "✍️ 텍스트 입력",
    "🧾 영수증 이미지",
    "📊 월간 대시보드",
])

with tab_text:
    st.write("예: 스타벅스에서 5,500원 신용카드로 결제했어요")

    user_input = st.text_area(
        "지출 내용을 입력하세요",
        placeholder="예: 교보문고에서 책 25,000원을 신용카드로 결제했어요",
        height=120,
    )

    if st.button("텍스트 지출 분석", type="primary", use_container_width=True):
        if not user_input.strip():
            st.warning("지출 내용을 입력해 주세요.")
        else:
            inputs = make_initial_state(
                input_type="text",
                user_input=user_input.strip(),
            )

            try:
                with st.spinner("지출을 분석하고 Notion에 저장하는 중입니다..."):
                    result = app.invoke(inputs)
                show_result(result)
            except Exception as e:
                st.error("처리 중 오류가 발생했습니다.")
                st.exception(e)


with tab_image:
    uploaded_file = st.file_uploader(
        "영수증 이미지를 업로드하세요",
        type=["jpg", "jpeg", "png"],
    )

    if uploaded_file is not None:
        st.image(uploaded_file, caption="업로드한 영수증", use_container_width=True)

    if st.button("영수증 분석", type="primary", use_container_width=True):
        if uploaded_file is None:
            st.warning("영수증 이미지를 먼저 업로드해 주세요.")
        else:
            suffix = os.path.splitext(uploaded_file.name)[1] or ".jpg"
            temp_path = None

            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp.write(uploaded_file.getbuffer())
                    temp_path = tmp.name

                inputs = make_initial_state(
                    input_type="image",
                    image_path=temp_path,
                )

                with st.spinner("영수증을 분석하고 Notion에 저장하는 중입니다..."):
                    result = app.invoke(inputs)

                show_result(result)

            except Exception as e:
                st.error("처리 중 오류가 발생했습니다.")
                st.exception(e)

            finally:
                if temp_path and os.path.exists(temp_path):
                    os.remove(temp_path)


with tab_dashboard:
    today = date.today()

    col_year, col_month = st.columns(2)

    with col_year:
        selected_year = st.number_input(
            "연도",
            min_value=2020,
            max_value=2100,
            value=today.year,
            step=1,
        )

    with col_month:
        selected_month = st.selectbox(
            "월",
            options=list(range(1, 13)),
            index=today.month - 1,
            format_func=lambda x: f"{x}월",
        )

    if st.button("월간 대시보드 조회", type="primary", use_container_width=True):
        try:
            show_dashboard(int(selected_year), int(selected_month))
        except Exception as e:
            st.error("대시보드 조회 중 오류가 발생했습니다.")
            st.exception(e)
