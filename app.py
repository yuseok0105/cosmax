import json
import time
from difflib import SequenceMatcher
from pathlib import Path

import streamlit as st

# ------------------------------------------------------------------
# 기본 설정
# ------------------------------------------------------------------
st.set_page_config(
    page_title="PickBrief | 픽브리프",
    page_icon="💄",
    layout="wide",
)

BASE_DIR = Path(__file__).parent
DATA_PATH = BASE_DIR / "data" / "pickbrief_mock_data.json"
LOGO_PATH = BASE_DIR / "assets" / "cosmax_logo.jpg"

ACCENT = "#D96C8C"       # 로즈핑크 포인트
ACCENT_DARK = "#B24E6C"
BG = "#FBF7F4"           # 화이트/베이지 톤
CARD_BG = "#FFFFFF"

# ------------------------------------------------------------------
# 스타일
# ------------------------------------------------------------------
st.markdown(
    f"""
    <style>
    .stApp {{
        background-color: {BG};
    }}
    .pb-hero {{
        padding: 1.2rem 0 0.4rem 0;
    }}
    .pb-title {{
        font-size: 2.1rem;
        font-weight: 800;
        color: #2B2B2B;
        margin-bottom: 0.1rem;
    }}
    .pb-subtitle {{
        font-size: 1.02rem;
        color: #6B6B6B;
        margin-bottom: 0.6rem;
    }}
    .pb-badge {{
        display:inline-block;
        background:{ACCENT};
        color:white;
        padding:2px 10px;
        border-radius:999px;
        font-size:0.75rem;
        font-weight:600;
        letter-spacing:0.02em;
        margin-bottom:0.6rem;
    }}
    .pb-card {{
        background:{CARD_BG};
        border-radius:16px;
        padding:1.3rem 1.4rem;
        box-shadow: 0 2px 10px rgba(0,0,0,0.06);
        border: 1px solid #F0E7E2;
        margin-bottom: 1rem;
        height: 100%;
    }}
    .pb-score {{
        font-size:2.0rem;
        font-weight:800;
        color:{ACCENT_DARK};
    }}
    .pb-rank {{
        display:inline-block;
        background:{BG};
        border:1px solid {ACCENT};
        color:{ACCENT_DARK};
        font-weight:700;
        font-size:0.8rem;
        padding:2px 10px;
        border-radius:999px;
        margin-bottom:0.5rem;
    }}
    .pb-chip {{
        display:inline-block;
        background:#F6ECEF;
        color:{ACCENT_DARK};
        font-size:0.78rem;
        padding:3px 10px;
        border-radius:999px;
        margin:2px 4px 2px 0;
    }}
    .pb-evidence {{
        background:{BG};
        border-radius:10px;
        padding:0.6rem 0.8rem;
        font-size:0.86rem;
        color:#4B4B4B;
        margin-top:0.5rem;
    }}
    .pb-footer-note {{
        color:#9A9A9A;
        font-size:0.78rem;
        margin-top:2rem;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)


# ------------------------------------------------------------------
# 데이터 로드
# ------------------------------------------------------------------
@st.cache_data
def load_data():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@st.cache_data
def all_keywords(data):
    kws = set()
    for p in data:
        kws.update(p.get("keyword_sentiment", {}).keys())
    return sorted(kws)


@st.cache_data
def all_categories(data):
    return sorted(set(p["category"] for p in data))


# ------------------------------------------------------------------
# 매칭 / 스코어링 로직 (베타: 규칙 기반, AI API 미사용)
# ------------------------------------------------------------------
def score_product(product, benchmark_name, keywords, category):
    """제품 하나에 대한 매칭 스코어(0~100)와 근거를 계산한다."""
    score = 0.0
    matched = []

    # 1) 카테고리 일치 가중치
    if category and category != "전체":
        if product["category"] != category:
            return None  # 카테고리 필터에서 제외
        score += 10

    # 2) 벤치마크 제품명 텍스트 유사도 (브랜드/제품명 기준)
    if benchmark_name.strip():
        target_texts = [product["name"], product["brand"]]
        best_ratio = max(
            SequenceMatcher(None, benchmark_name.strip(), t).ratio()
            for t in target_texts
        )
        score += best_ratio * 25

    # 3) 감성 키워드 매칭 (언급량 + 긍정 비율 반영)
    ks = product.get("keyword_sentiment", {})
    keyword_points = 0.0
    for kw in keywords:
        if kw in ks:
            info = ks[kw]
            volume_factor = min(info["mentioned_count"] / 1500, 1.0)
            keyword_points += (info["positive_pct"] / 100) * (0.5 + 0.5 * volume_factor)
            matched.append((kw, info))
    if keywords:
        keyword_points = keyword_points / len(keywords)  # 평균화
    score += keyword_points * 45

    # 4) 제품 자체 신뢰도(평점 + 후기량) 보정
    score += (product["avg_rating"] / 5) * 12
    score += min(product["review_count"] / 8000, 1.0) * 8

    return {
        "product": product,
        "score": min(round(score, 1), 100),
        "matched_keywords": matched,
    }


def get_recommendations(data, benchmark_name, keywords, category, top_n=3):
    scored = []
    for p in data:
        result = score_product(p, benchmark_name, keywords, category)
        if result is not None:
            scored.append(result)
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_n]


def build_brief(result):
    """추천 이유(미니 브리프) 텍스트 생성"""
    product = result["product"]
    matched = sorted(result["matched_keywords"], key=lambda x: x[1]["mentioned_count"], reverse=True)

    lines = []
    if matched:
        top_kw, top_info = matched[0]
        lines.append(
            f"'{top_kw}' 관련 후기 {top_info['mentioned_count']:,}건 중 "
            f"{top_info['positive_pct']}% 긍정 언급"
        )
        if len(matched) > 1:
            kw2, info2 = matched[1]
            lines.append(
                f"'{kw2}' 관련 후기 {info2['mentioned_count']:,}건 중 "
                f"{info2['positive_pct']}% 긍정 언급"
            )
    else:
        lines.append("선택한 감성 키워드에 대한 직접 언급 데이터는 적지만, 카테고리·평점 기준 상위 제품입니다.")

    ingredient_line = "핵심 원료: " + ", ".join(product["key_ingredients"])
    source_line = f"출처: {product['channel']} · 리뷰 {product['review_count']:,}건 · 평점 {product['avg_rating']}"

    return lines, ingredient_line, source_line


# ------------------------------------------------------------------
# 세션 상태 초기화
# ------------------------------------------------------------------
if "stage" not in st.session_state:
    st.session_state.stage = "input"
if "form" not in st.session_state:
    st.session_state.form = {}
if "results" not in st.session_state:
    st.session_state.results = []


def go_to_input():
    st.session_state.stage = "input"


def submit_form(benchmark_name, keywords, category):
    st.session_state.form = {
        "benchmark_name": benchmark_name,
        "keywords": keywords,
        "category": category,
    }
    st.session_state.stage = "loading"


def run_analysis(data):
    form = st.session_state.form
    st.session_state.results = get_recommendations(
        data,
        form.get("benchmark_name", ""),
        form.get("keywords", []),
        form.get("category", "전체"),
    )
    st.session_state.stage = "result"


# ------------------------------------------------------------------
# 헤더 (공통)
# ------------------------------------------------------------------
def render_header():
    col_logo, col_text = st.columns([1, 5])
    with col_logo:
        if LOGO_PATH.exists():
            st.image(str(LOGO_PATH), use_container_width=True)
    with col_text:
        st.markdown('<div class="pb-badge">BETA</div>', unsafe_allow_html=True)
        st.markdown('<div class="pb-title">픽브리프 PickBrief</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="pb-subtitle">벤치마크 제품이나 감성 키워드만 입력하면, '
            '후기 데이터 기반으로 매칭된 대표 아이템 3개와 기획 브리프를 즉시 뽑아드립니다.</div>',
            unsafe_allow_html=True,
        )
    st.divider()


# ------------------------------------------------------------------
# 화면 1: 입력
# ------------------------------------------------------------------
def render_input_screen(data):
    render_header()

    st.markdown("##### 추천 조건 입력")
    categories = ["전체"] + all_categories(data)
    keywords_options = all_keywords(data)

    with st.form("pickbrief_input_form"):
        col1, col2 = st.columns([3, 2])
        with col1:
            benchmark_name = st.text_input(
                "벤치마크 제품명",
                placeholder="예: 설화수 톤업 선크림, 입생로랑 쿠션 ...",
                help="비교하고 싶은 벤치마크 제품명을 입력하세요. (자사/시중 제품 모두 가능)",
            )
        with col2:
            category = st.selectbox("카테고리", categories, index=0)

        keywords = st.multiselect(
            "원하는 느낌 / 감성 키워드",
            options=keywords_options,
            default=[],
            help="후기 데이터에서 자주 언급되는 감성 키워드 중 원하는 방향을 선택하세요.",
        )

        submitted = st.form_submit_button("🔍 대표 아이템 3개 분석하기", use_container_width=True, type="primary")

        if submitted:
            if not benchmark_name.strip() and not keywords:
                st.warning("벤치마크 제품명 또는 감성 키워드를 최소 1개 이상 입력해주세요.")
            else:
                submit_form(benchmark_name, keywords, category)
                st.rerun()

    st.markdown(
        '<div class="pb-footer-note">※ 본 베타는 목업(mock) 데이터를 기반으로 동작하며, '
        '실제 후기 크롤링/AI API 연동 없이 규칙 기반 로직으로 매칭 결과를 생성합니다.</div>',
        unsafe_allow_html=True,
    )


# ------------------------------------------------------------------
# 화면 2: 분석 중
# ------------------------------------------------------------------
def render_loading_screen(data):
    render_header()

    placeholder = st.empty()
    progress = st.progress(0)

    steps = [
        ("후기 데이터 수집 중...", 25),
        ("감성 키워드 매칭 분석 중...", 55),
        ("유사 제품 유사도 스코어링 중...", 80),
        ("대표 아이템 3개 선별 및 브리프 생성 중...", 100),
    ]

    for label, pct in steps:
        placeholder.markdown(f"##### {label}")
        progress.progress(pct)
        time.sleep(0.6)

    run_analysis(data)
    st.rerun()


# ------------------------------------------------------------------
# 화면 3: 결과
# ------------------------------------------------------------------
def render_result_screen(data):
    render_header()

    form = st.session_state.form
    summary_bits = []
    if form.get("benchmark_name"):
        summary_bits.append(f"벤치마크 **{form['benchmark_name']}**")
    if form.get("keywords"):
        summary_bits.append("키워드 " + ", ".join(f"`{k}`" for k in form["keywords"]))
    if form.get("category") and form["category"] != "전체":
        summary_bits.append(f"카테고리 **{form['category']}**")

    if summary_bits:
        st.markdown("조건: " + " · ".join(summary_bits))

    results = st.session_state.results

    if not results:
        st.info("조건에 맞는 추천 결과가 없습니다. 카테고리를 '전체'로 바꿔보세요.")
    else:
        cols = st.columns(len(results))
        for rank, (col, result) in enumerate(zip(cols, results), start=1):
            product = result["product"]
            lines, ingredient_line, source_line = build_brief(result)

            with col:
                st.markdown('<div class="pb-card">', unsafe_allow_html=True)
                st.markdown(f'<div class="pb-rank">추천 {rank}순위</div>', unsafe_allow_html=True)
                st.markdown(f"**{product['name']}**")
                st.caption(f"{product['brand']} · {product['subtype']}")
                st.markdown(f'<div class="pb-score">{result["score"]}%</div>', unsafe_allow_html=True)
                st.caption("매칭 스코어")

                st.markdown(
                    "".join(f'<span class="pb-chip">{ing}</span>' for ing in product["key_ingredients"]),
                    unsafe_allow_html=True,
                )

                evidence_html = "".join(f"<div>• {line}</div>" for line in lines)
                st.markdown(
                    f'<div class="pb-evidence">{evidence_html}'
                    f'<div style="margin-top:6px;">{ingredient_line}</div>'
                    f'<div>{source_line}</div></div>',
                    unsafe_allow_html=True,
                )

                st.markdown(f"가격대: 약 {product['price_krw']:,}원")
                st.markdown('</div>', unsafe_allow_html=True)

    st.write("")
    if st.button("↩︎ 새 조건으로 다시 분석하기", use_container_width=True):
        go_to_input()
        st.rerun()


# ------------------------------------------------------------------
# 메인 라우팅
# ------------------------------------------------------------------
def main():
    data = load_data()

    if st.session_state.stage == "input":
        render_input_screen(data)
    elif st.session_state.stage == "loading":
        render_loading_screen(data)
    elif st.session_state.stage == "result":
        render_result_screen(data)


if __name__ == "__main__":
    main()
