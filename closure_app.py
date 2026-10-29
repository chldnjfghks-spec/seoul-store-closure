import pandas as pd
import streamlit as st
import altair as alt
import joblib
from pathlib import Path

st.set_page_config(page_title="서울시 개업·폐업 분석", page_icon="📊", layout="wide")

BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "seoul_store_district.csv"
MODEL_PATH = BASE_DIR / "model" / "closure_count_model.joblib"


@st.cache_data
def load_data():
    return pd.read_csv(DATA_PATH, encoding="cp949")


@st.cache_resource
def load_model():
    return joblib.load(MODEL_PATH)


def quarter_label(code):
    code = int(code)
    return f"{code // 10}년 {code % 10}분기"


def short_quarter_label(code):
    code = int(code)
    return f"{code // 10}년 {code % 10}분기"


def ranking_chart(data, name_column, value_column, color, unit):
    chart_data = data[[name_column, value_column]].copy()

    chart_data.columns = ["이름", "값"]

    chart_data = chart_data.sort_values("값", ascending=False).head(10)

    chart_data["표시"] = chart_data["값"].apply(
        lambda value: f"{value:,.1f}{unit}" if unit == "%" else f"{value:,.0f}{unit}"
    )

    order = chart_data["이름"].tolist()

    bars = (
        alt.Chart(chart_data)
        .mark_bar(color=color, cornerRadiusEnd=3)
        .encode(
            x=alt.X("값:Q", title=value_column, scale=alt.Scale(zero=True)),
            y=alt.Y(
                "이름:N",
                title=None,
                sort=order,
                axis=alt.Axis(labelAngle=0, labelLimit=200),
            ),
            tooltip=[
                alt.Tooltip("이름:N", title=name_column),
                alt.Tooltip("표시:N", title=value_column),
            ],
        )
    )

    return bars.properties(height=360)


df = load_data()
model = load_model()

st.title("서울시 개업·폐업 현황과 예측")

st.write(
    "어느 지역과 업종에서 가게를 많이 열고 닫았는지 살펴보고, "
    "다음 분기에 폐업할 점포 수를 예측합니다."
)

st.sidebar.header("조회 조건")

district_list = sorted(df["자치구_코드_명"].unique())

selected_district = st.sidebar.selectbox(
    "지역", district_list, index=district_list.index("마포구")
)

district_data = df.loc[df["자치구_코드_명"] == selected_district].copy()

industry_list = sorted(district_data["서비스_업종_코드_명"].unique())

industry_index = 0

if "커피-음료" in industry_list:
    industry_index = industry_list.index("커피-음료")

selected_industry = st.sidebar.selectbox("업종", industry_list, index=industry_index)

selected_data = district_data.loc[
    district_data["서비스_업종_코드_명"] == selected_industry
].copy()

selected_data = selected_data.sort_values("기준_년분기_코드")

quarter_list = sorted(selected_data["기준_년분기_코드"].unique(), reverse=True)

selected_quarter = st.sidebar.selectbox(
    "기준 시기", quarter_list, format_func=quarter_label
)

st.sidebar.caption(
    "1분기: 1~3월\n\n" "2분기: 4~6월\n\n" "3분기: 7~9월\n\n" "4분기: 10~12월"
)

st.sidebar.caption("자료 범위: 2021년 1분기~2026년 2분기")

current_data = selected_data.loc[selected_data["기준_년분기_코드"] == selected_quarter]

current_row = current_data.iloc[0]

history_data = selected_data.loc[
    selected_data["기준_년분기_코드"] <= selected_quarter
].copy()

current_year = int(selected_quarter) // 10
current_quarter = int(selected_quarter) % 10

if current_quarter == 4:
    next_year = current_year + 1
    next_quarter = 1
else:
    next_year = current_year
    next_quarter = current_quarter + 1

next_quarter_code = next_year * 10 + next_quarter

prediction_input = pd.DataFrame(
    {
        "전체_점포_수": [current_row["전체_점포_수"]],
        "개업_점포_수": [current_row["개업_점포_수"]],
        "폐업_점포_수": [current_row["폐업_점포_수"]],
        "분기": [current_quarter],
    }
)

predicted_count = float(model.predict(prediction_input)[0])

next_data = selected_data.loc[selected_data["기준_년분기_코드"] == next_quarter_code]

display_names = {
    "기준_년분기_코드": "기간",
    "자치구_코드_명": "지역",
    "서비스_업종_코드_명": "업종",
    "전체_점포_수": "전체 점포 수",
    "개업_점포_수": "개업 점포 수",
    "폐업_점포_수": "폐업 점포 수",
    "폐업_률": "폐업률(%)",
}

st.subheader(f"{selected_district} · {selected_industry}")

st.caption(f"선택한 시기: {quarter_label(selected_quarter)}")

tab1, tab2, tab3 = st.tabs(["개업·폐업 현황", "다음 분기 예측", "모델 성능"])


with tab1:
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("전체 점포 수", f"{int(current_row['전체_점포_수']):,}개")

    with col2:
        st.metric("이 기간에 개업한 점포", f"{int(current_row['개업_점포_수']):,}개")

    with col3:
        st.metric("이 기간에 폐업한 점포", f"{int(current_row['폐업_점포_수']):,}개")

    st.markdown("### 분기별 개업·폐업 추이")

    show_all = st.checkbox("전체 기간 보기", value=False)

    trend_data = history_data.copy()

    if not show_all:
        trend_data = trend_data.tail(12)

    trend_data = trend_data[["기준_년분기_코드", "개업_점포_수", "폐업_점포_수"]].copy()

    trend_data["기간"] = trend_data["기준_년분기_코드"].apply(short_quarter_label)

    period_order = trend_data["기간"].tolist()

    trend_data = trend_data.rename(
        columns={"개업_점포_수": "개업", "폐업_점포_수": "폐업"}
    )

    trend_long = trend_data.melt(
        id_vars=["기간"],
        value_vars=["개업", "폐업"],
        var_name="구분",
        value_name="점포 수",
    )

    trend_chart = (
        alt.Chart(trend_long)
        .mark_line(point=True)
        .encode(
            x=alt.X(
                "기간:N",
                title=None,
                sort=period_order,
                axis=alt.Axis(labelAngle=0, labelOverlap="greedy"),
            ),
            y=alt.Y("점포 수:Q", title="점포 수(개)", scale=alt.Scale(zero=True)),
            color=alt.Color(
                "구분:N",
                title=None,
                scale=alt.Scale(domain=["개업", "폐업"], range=["#2563EB", "#EA580C"]),
                legend=alt.Legend(orient="bottom"),
            ),
            tooltip=[
                alt.Tooltip("기간:N", title="기간"),
                alt.Tooltip("구분:N", title="구분"),
                alt.Tooltip("점포 수:Q", title="점포 수(개)", format=",.0f"),
            ],
        )
        .properties(height=350)
    )

    st.altair_chart(trend_chart, use_container_width=True)

    st.caption(
        "기본 화면은 최근 12개 분기입니다. "
        "그래프에 마우스를 올리면 해당 수치를 볼 수 있습니다."
    )

    with st.expander("기간별 숫자를 표로 보기"):
        detail_data = history_data[
            [
                "기준_년분기_코드",
                "전체_점포_수",
                "개업_점포_수",
                "폐업_점포_수",
                "폐업_률",
            ]
        ].copy()

        detail_data["기준_년분기_코드"] = detail_data["기준_년분기_코드"].apply(
            quarter_label
        )

        detail_data = detail_data.rename(columns=display_names)

        st.dataframe(detail_data, hide_index=True, use_container_width=True)

    st.divider()

    st.markdown("### 지역·업종별 비교")

    metric_options = {
        "폐업한 점포가 많은 곳": "폐업_점포_수",
        "개업한 점포가 많은 곳": "개업_점포_수",
        "폐업률이 높은 곳": "폐업_률",
    }

    selected_metric = st.selectbox("비교 항목", list(metric_options.keys()))

    metric_column = metric_options[selected_metric]
    metric_name = display_names[metric_column]

    district_compare = df.loc[
        (df["기준_년분기_코드"] == selected_quarter)
        & (df["서비스_업종_코드_명"] == selected_industry)
    ].copy()

    industry_compare = df.loc[
        (df["기준_년분기_코드"] == selected_quarter)
        & (df["자치구_코드_명"] == selected_district)
    ].copy()

    unit = "개"

    if metric_column == "폐업_률":
        unit = "%"

        district_compare = district_compare.loc[
            district_compare["전체_점포_수"] > 0
        ].copy()

        industry_compare = industry_compare.loc[
            industry_compare["전체_점포_수"] > 0
        ].copy()

    district_compare = district_compare.sort_values(metric_column, ascending=False)

    industry_compare = industry_compare.sort_values(metric_column, ascending=False)

    left, right = st.columns(2)

    with left:
        st.markdown(f"#### 지역별 {metric_name} 상위 10곳")

        st.caption(f"{quarter_label(selected_quarter)} · " f"{selected_industry}")

        district_chart_data = district_compare[["자치구_코드_명", metric_column]].copy()

        district_chart_data = district_chart_data.rename(
            columns={"자치구_코드_명": "지역", metric_column: metric_name}
        )

        chart = ranking_chart(district_chart_data, "지역", metric_name, "#2563EB", unit)

        st.altair_chart(chart, use_container_width=True)

        with st.expander("모든 지역의 숫자 보기"):
            district_table = district_compare[
                [
                    "자치구_코드_명",
                    "전체_점포_수",
                    "개업_점포_수",
                    "폐업_점포_수",
                    "폐업_률",
                ]
            ].copy()

            district_table = district_table.rename(columns=display_names)

            st.dataframe(district_table, hide_index=True, use_container_width=True)

    with right:
        st.markdown(f"#### 업종별 {metric_name} 상위 10개")

        st.caption(f"{quarter_label(selected_quarter)} · " f"{selected_district}")

        industry_chart_data = industry_compare[
            ["서비스_업종_코드_명", metric_column]
        ].copy()

        industry_chart_data = industry_chart_data.rename(
            columns={"서비스_업종_코드_명": "업종", metric_column: metric_name}
        )

        chart = ranking_chart(industry_chart_data, "업종", metric_name, "#EA580C", unit)

        st.altair_chart(chart, use_container_width=True)

        with st.expander("모든 업종의 숫자 보기"):
            industry_table = industry_compare[
                [
                    "서비스_업종_코드_명",
                    "전체_점포_수",
                    "개업_점포_수",
                    "폐업_점포_수",
                    "폐업_률",
                ]
            ].copy()

            industry_table = industry_table.rename(columns=display_names)

            st.dataframe(industry_table, hide_index=True, use_container_width=True)

    if metric_column == "폐업_률":
        st.info(
            "폐업률을 비교할 때는 전체 점포 수도 함께 보세요. "
            "점포가 적으면 몇 개의 폐업만으로도 비율이 크게 달라집니다. "
            "전체 점포 수가 0인 기록은 이 비교에서 제외했습니다."
        )
    else:
        st.caption(
            "점포가 많은 지역·업종은 개업·폐업 건수도 많을 수 있습니다. "
            "건수가 많다는 것만으로 개별 가게가 더 위험하다고 볼 수는 없습니다."
        )

    st.caption(
        "같은 기간의 개업 수와 폐업 수는 서로 다른 기록입니다. "
        "그 기간에 개업한 가게가 곧바로 폐업했다는 뜻은 아닙니다."
    )


with tab2:
    st.markdown(f"### {next_year}년 {next_quarter}분기 예상 폐업 점포 수")

    result1, result2 = st.columns(2)

    with result1:
        st.metric("선택한 분기의 폐업 수", f"{int(current_row['폐업_점포_수']):,}개")

    with result2:
        st.metric("다음 분기 예상 폐업 수", f"약 {predicted_count:,.1f}개")

    st.caption("왼쪽에서 지역·업종·시기를 바꾸면 예측도 바뀝니다.")

    recent_data = history_data.tail(8).copy()

    actual_chart_data = pd.DataFrame(
        {
            "기간": recent_data["기준_년분기_코드"].apply(short_quarter_label).tolist(),
            "점포 수": recent_data["폐업_점포_수"].tolist(),
            "구분": "기존 실제값",
        }
    )

    next_label = short_quarter_label(next_quarter_code)

    period_order = actual_chart_data["기간"].tolist()
    period_order.append(next_label)

    forecast_chart_data = pd.DataFrame(
        {
            "기간": [actual_chart_data.iloc[-1]["기간"], next_label],
            "점포 수": [float(current_row["폐업_점포_수"]), predicted_count],
            "구분": ["예측 연결", "다음 분기 예측"],
        }
    )

    chart_base = alt.Chart().encode(
        x=alt.X(
            "기간:N",
            title=None,
            sort=period_order,
            axis=alt.Axis(labelAngle=0, labelOverlap="greedy"),
        ),
        y=alt.Y("점포 수:Q", title="폐업 점포 수(개)", scale=alt.Scale(zero=True)),
        tooltip=[
            alt.Tooltip("기간:N", title="기간"),
            alt.Tooltip("구분:N", title="구분"),
            alt.Tooltip("점포 수:Q", title="폐업 점포 수(개)", format=",.1f"),
        ],
    )

    actual_line = chart_base.mark_line(point=True, color="#2563EB").properties(
        data=actual_chart_data
    )

    forecast_line = chart_base.mark_line(
        point=True, color="#0D9488", strokeDash=[6, 4]
    ).properties(data=forecast_chart_data)

    prediction_chart = actual_line + forecast_line

    if not next_data.empty:
        actual_next = float(next_data.iloc[0]["폐업_점포_수"])

        next_actual_data = pd.DataFrame(
            {
                "기간": [next_label],
                "점포 수": [actual_next],
                "구분": ["다음 분기 실제값"],
            }
        )

        actual_point = chart_base.mark_point(
            color="#EA580C", size=160, shape="cross"
        ).properties(data=next_actual_data)

        prediction_chart = prediction_chart + actual_point

    st.markdown("### 최근 폐업 수와 예측 비교")

    st.altair_chart(prediction_chart.properties(height=360), use_container_width=True)

    st.caption(
        "파랑: 기존 실제값 / 초록 점선: 예측 / "
        "주황 십자: 다음 분기 실제값이 있을 때 표시"
    )

    if not next_data.empty:
        actual_count = float(next_data.iloc[0]["폐업_점포_수"])

        difference = abs(actual_count - predicted_count)

        compare1, compare2 = st.columns(2)

        with compare1:
            st.metric("다음 분기에 실제로 폐업한 점포", f"{int(actual_count):,}개")

        with compare2:
            st.metric("실제와 예측의 차이", f"{difference:.1f}개")
    else:
        st.info(
            f"{next_year}년 {next_quarter}분기의 실제값은 "
            "현재 CSV에 없어 예측값만 표시합니다."
        )

    if next_year <= 2024:
        st.info(
            "선택한 기간은 모델이 이미 학습한 기간입니다. "
            "새로운 자료를 얼마나 잘 맞히는지 확인하는 용도로는 사용하지 않습니다."
        )
    elif next_year == 2025:
        st.caption("선택한 기간은 여러 모델을 비교할 때 사용한 기간입니다.")

    with st.expander("어떤 정보로 예측했나요?"):
        input_table = prediction_input.rename(
            columns={
                "전체_점포_수": "전체 점포 수",
                "개업_점포_수": "개업 점포 수",
                "폐업_점포_수": "폐업 점포 수",
                "분기": "분기",
            }
        )

        st.dataframe(input_table, hide_index=True, use_container_width=True)

        st.write(
            "선택한 지역·업종의 숫자 4개를 모델에 넣었습니다. "
            "지역명과 업종명 자체는 모델에 넣지 않습니다."
        )

        st.write("여러 나무의 예측을 평균해서 결과가 소수로 나올 수 있습니다.")

    st.caption(
        "이 결과는 지역·업종 전체의 폐업 건수 예측입니다. "
        "개별 가게의 폐업 여부나 창업 성공 확률은 아닙니다."
    )


with tab3:
    st.subheader("모델 성능")

    st.write(
        "과거 자료로 학습한 모델을 "
        "**2026년 1~2분기 자료 4,990건**으로 평가한 결과입니다."
    )

    result1, result2, result3, result4 = st.columns(4)

    with result1:
        st.metric(
            "평균 예측 오차",
            "2.262개",
            help="실제 폐업 수와 예측값의 차이를 평균한 값입니다. 작을수록 좋습니다."
        )

    with result2:
        st.metric(
            "기준 예측 오차",
            "2.722개",
            help="이번 분기 폐업 수가 다음 분기에도 같다고 예측했을 때의 평균 오차입니다."
        )

    with result3:
        st.metric(
            "기준 대비 오차 감소",
            "16.9%",
            help="기준 예측과 비교해 평균 예측 오차가 줄어든 비율입니다."
        )

    with result4:
        st.metric(
            "결정계수 R²",
            "0.883",
            help="1에 가까울수록 좋습니다. 정확도 88.3%라는 뜻은 아닙니다."
        )

    st.info(
        "실제 폐업 수와 예측값은 평균적으로 약 2.26개 차이가 났습니다. "
        "이번 분기 폐업 수를 그대로 사용하는 기준 예측보다 "
        "평균 오차가 16.9% 줄었습니다."
    )

    st.caption(
        "서울 전체 지역·업종의 평가 결과입니다. "
        "왼쪽 조회 조건을 바꿔도 이 수치는 바뀌지 않습니다. "
        "모든 예측의 오차가 2.26개 이내라는 뜻은 아닙니다."
    )

    st.divider()

    st.subheader("모델별 성능 비교")

    st.write(
        "같은 **2025년 검증 자료 9,972건**으로 성능을 비교하여 "
        "최종 모델을 선택했습니다."
    )

    validation_table = pd.DataFrame(
        {
            "예측 방법": [
                "이번 분기 폐업 수 그대로",
                "선형회귀",
                "의사결정나무",
                "랜덤포레스트 — 깊이 5",
                "랜덤포레스트 — 깊이 10"
            ],
            "평균 오차 MAE(개)": [
                2.625, 2.296, 2.459, 2.336, 2.173
            ],
            "RMSE(개)": [
                5.518, 5.030, 5.150, 4.772, 4.451
            ],
            "R²": [
                0.868, 0.890, 0.885, 0.901, 0.914
            ]
        }
    )

    st.dataframe(
        validation_table.style.format(
            {
                "평균 오차 MAE(개)": "{:.3f}",
                "RMSE(개)": "{:.3f}",
                "R²": "{:.3f}"
            }
        ),
        hide_index=True,
        use_container_width=True
    )

    st.caption(
        "MAE와 RMSE는 작을수록 좋고, R²는 1에 가까울수록 좋습니다."
    )

    st.success(
        "검증 자료에서 오차가 가장 작았던 "
        "랜덤포레스트 — 깊이 10을 최종 모델로 선택했습니다."
    )

    st.caption(
        "위쪽 핵심 지표는 마지막 테스트 결과이고, "
        "이 표는 모델 선택에 사용한 검증 결과이므로 수치가 다릅니다."
    )

    with st.expander("자세한 평가 숫자"):
        score_table = pd.DataFrame(
            {
                "평가 항목": [
                    "평균 절대오차(MAE)",
                    "큰 오차를 더 반영한 값(RMSE)",
                    "결정계수(R²)",
                ],
                "결과": ["2.262개", "4.865개", "0.883"],
            }
        )

        st.dataframe(score_table, hide_index=True, use_container_width=True)

        st.write(
            "MAE와 RMSE는 작을수록 좋습니다. "
            "R² 0.883은 정확도 88.3%라는 뜻은 아닙니다."
        )

    with st.expander("학습과 평가에 사용한 기간"):
        split_table = pd.DataFrame(
            {
                "용도": ["패턴 학습", "모델 비교·선택", "마지막 성능 확인"],
                "정답 기간": [
                    "2021년 2분기~2024년 4분기",
                    "2025년 1~4분기",
                    "2026년 1~2분기",
                ],
                "기록 수": [37298, 9972, 4990],
            }
        )

        st.dataframe(split_table, hide_index=True, use_container_width=True)

        st.write("이전 분기까지의 실제 정보를 이용해 " "다음 한 분기를 예측했습니다.")

        st.write("최종 모델은 나무 100개, 최대 깊이 10인 " "랜덤포레스트입니다.")

    st.markdown("### 예측할 때 많이 참고한 정보")

    importance_data = pd.DataFrame(
        {"정보": model.feature_names_in_, "참고한 정도": model.feature_importances_}
    )

    importance_data["정보"] = importance_data["정보"].replace(
        {
            "전체_점포_수": "전체 점포 수",
            "개업_점포_수": "개업 점포 수",
            "폐업_점포_수": "현재 폐업 점포 수",
            "분기": "분기",
        }
    )

    importance_order = importance_data.sort_values("참고한 정도", ascending=False)[
        "정보"
    ].tolist()

    importance_chart = (
        alt.Chart(importance_data)
        .mark_bar(color="#2563EB")
        .encode(
            x=alt.X("참고한 정도:Q", title="모델이 참고한 정도"),
            y=alt.Y(
                "정보:N", title=None, sort=importance_order, axis=alt.Axis(labelAngle=0)
            ),
            tooltip=[
                alt.Tooltip("정보:N", title="정보"),
                alt.Tooltip("참고한 정도:Q", title="참고한 정도", format=".3f"),
            ],
        )
        .properties(height=220)
    )

    st.altair_chart(importance_chart, use_container_width=True)

    st.caption(
        "모델이 학습할 때 활용한 정도입니다. " "폐업의 원인을 밝혔다는 뜻은 아닙니다."
    )


st.divider()

st.markdown(
    "자료 출처: "
    "[서울 열린데이터광장 — 점포·자치구]"
    "(https://data.seoul.go.kr/dataList/OA-22173/S/1/datasetView.do)"
)

st.caption(
    "공공누리 제1유형 · 자료 범위: 2021년 1분기~2026년 2분기. "
    "자료 공개 시점과 앞으로의 환경 변화에 따라 예측에 한계가 있습니다."
)
