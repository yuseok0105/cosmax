import json
import time
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

BRAND_NONE = "브랜드 무관 (전체 비교)"

# ------------------------------------------------------------------
# 스타일 (팔레트는 PickBrief 프로토타입 톤을 그대로 사용)
# ------------------------------------------------------------------
st.markdown(
    """
    <style>
    :root{
        --pb-bg:#F8F6F4;
        --pb-primary:#A69B94;
        --pb-primary-dark:#857A73;
        --pb-primary-soft:#EFEAE7;
        --pb-secondary:#2F4A3C;
        --pb-secondary-dark:#23372C;
        --pb-secondary-soft:#E4EBE6;
        --pb-accent:#C9583F;
        --pb-border:#E3DDD8;
        --pb-beige-dark:#DDD6D1;
        --pb-text-light:#8F8580;
    }
    .stApp{ background-color: var(--pb-bg); }

    .pb-badge{
        display:inline-block; background:var(--pb-secondary-soft); color:var(--pb-secondary);
        padding:3px 12px; border-radius:100px; font-size:0.75rem; font-weight:700; margin-bottom:0.5rem;
    }
    .pb-title{ font-size:1.9rem; font-weight:800; margin:0 0 0.1rem; letter-spacing:-0.3px; }
    .pb-subtitle{ font-size:0.98rem; color:var(--pb-text-light); margin-bottom:0.4rem; }

    .pb-cardtop{
        border-radius:12px; height:64px; display:flex; align-items:center; justify-content:center;
        font-size:28px; position:relative; margin-bottom:8px;
    }
    .pb-rankflag{
        position:absolute; top:8px; left:8px; background:rgba(255,255,255,0.9);
        color:var(--pb-primary-dark); font-size:11px; font-weight:800; padding:3px 9px; border-radius:100px;
    }
    .pb-ratingbadge{
        padding:6px 12px; border-radius:100px; background:var(--pb-secondary-soft);
        color:var(--pb-secondary); font-size:13px; font-weight:800; text-align:center; white-space:nowrap;
    }

    .score-ring{
        --score:0; width:52px; height:52px; border-radius:50%; margin-left:auto;
        background:conic-gradient(var(--pb-accent) calc(var(--score)*1%), var(--pb-beige-dark) 0);
        display:flex; align-items:center; justify-content:center;
    }
    .score-ring-inner{
        width:42px; height:42px; border-radius:50%; background:#fff;
        display:flex; align-items:center; justify-content:center;
        font-size:12px; font-weight:800; color:var(--pb-accent);
    }

    .pb-chip{
        display:inline-block; background:var(--pb-primary-soft); color:var(--pb-primary-dark);
        font-size:0.78rem; font-weight:700; padding:4px 11px; border-radius:100px; margin:2px 4px 2px 0;
    }
    .pb-reasonbox{
        background:var(--pb-secondary-soft); border-radius:10px; padding:0.7rem 0.9rem;
        font-size:0.9rem; line-height:1.6; color:#242424; margin:0.3rem 0 0.8rem;
    }
    .pb-modalicon{
        width:54px; height:54px; border-radius:12px; display:flex; align-items:center;
        justify-content:center; font-size:26px;
    }
    .pb-footer-note{ color:var(--pb-text-light); font-size:0.78rem; margin-top:1.5rem; }

    div[data-testid="stSelectbox"] div[data-baseweb="select"],
    div[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
    div[data-testid="stSelectbox"] div[data-baseweb="select"] > div > div{
        border: 1px solid rgba(49, 51, 63, 0.4) !important;
        border-radius: 0.5rem !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ------------------------------------------------------------------
# 데이터 로드 및 인덱싱
# ------------------------------------------------------------------
@st.cache_data
def load_data():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@st.cache_data
def build_indexes(data):
    categories = []
    products_by_category = {}
    brands_by_category = {}
    keywords_by_category = {}

    for p in data:
        if p["category"] not in categories:
            categories.append(p["category"])
        products_by_category.setdefault(p["category"], []).append(p)

        brands = brands_by_category.setdefault(p["category"], [])
        if p["brand"] not in brands:
            brands.append(p["brand"])

        kws = keywords_by_category.setdefault(p["category"], [])
        for k in p.get("keyword_sentiment", {}):
            if k not in kws:
                kws.append(k)

    for c in categories:
        brands_by_category[c].sort()
        keywords_by_category[c].sort()

    return categories, products_by_category, brands_by_category, keywords_by_category


def get_category_meta(category):
    if category and "선크림" in category:
        return {"icon": "☀️", "grad": "linear-gradient(135deg,#E4EBE6,#CFE0D5)"}
    if category and "색조" in category:
        return {"icon": "💄", "grad": "linear-gradient(135deg,#F6E4E8,#EFD2D9)"}
    if category and "기초" in category:
        return {"icon": "🧴", "grad": "linear-gradient(135deg,#EAF1F7,#D3E3EE)"}
    return {"icon": "✨", "grad": "linear-gradient(135deg,#F1E9DF,#E7DCCC)"}


# ------------------------------------------------------------------
# 매칭 / 스코어링 로직 (베타: 규칙 기반, AI API 미사용)
# ------------------------------------------------------------------
def calculate_score(product, selected_keywords, selected_brand):
    stats = product.get("keyword_sentiment", {})
    basis = selected_keywords if selected_keywords else list(stats.keys())

    total = 0.0
    for kw in basis:
        stat = stats.get(kw)
        if not stat:
            continue
        relevance = min(stat["mentioned_count"] / product["review_count"], 1.0)
        positivity = stat["positive_pct"] / 100
        total += relevance * 0.4 + positivity * 0.6

    base = (total / len(basis)) * 100 if basis else 0.0
    bonus = 8 if (selected_brand and product["brand"] == selected_brand) else 0
    return max(28, min(99, round(base + bonus)))


def rank_products(products_by_category, category, selected_keywords, selected_brand, top_n=3):
    products = products_by_category.get(category, [])
    scored = [(p, calculate_score(p, selected_keywords, selected_brand)) for p in products]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_n]


def top_keywords_for_product(product, selected_keywords):
    stats = product.get("keyword_sentiment", {})
    pool = [k for k in selected_keywords if stats.get(k, {}).get("mentioned_count", 0) > 0]
    if not pool:
        pool = sorted(stats.keys(), key=lambda k: stats[k]["mentioned_count"], reverse=True)
    return pool[:4]


def build_reason(product, score, selected_keywords, selected_brand, top_keywords):
    stats = product.get("keyword_sentiment", {})
    parts = []

    primary_kw = top_keywords[0] if top_keywords else None
    primary_stat = stats.get(primary_kw) if primary_kw else None
    is_recommendation = score is not None

    if primary_stat and is_recommendation:
        parts.append(
            f"'{primary_kw}' 관련 후기 {primary_stat['mentioned_count']:,}건 중 "
            f"{primary_stat['positive_pct']}%가 긍정 반응을 보여, 요청하신 감성 조건과 가장 잘 맞는 제품입니다."
        )
    elif primary_stat:
        parts.append(
            f"'{primary_kw}' 관련 후기 {primary_stat['mentioned_count']:,}건 중 "
            f"{primary_stat['positive_pct']}%가 긍정 반응을 보였습니다."
        )

    if is_recommendation and selected_brand and product["brand"] == selected_brand:
        parts.append(f"선택하신 벤치마크 브랜드({selected_brand})와 동일한 브랜드 라인입니다.")

    parts.append(
        f"총 {product['review_count']:,}건의 후기가 {product['channel']} 채널에서 수집되어 "
        f"근거 데이터의 신뢰도가 높습니다."
    )
    return " ".join(parts)


# ------------------------------------------------------------------
# 세션 상태 초기화
# ------------------------------------------------------------------
if "stage" not in st.session_state:
    st.session_state.stage = "input"
if "form" not in st.session_state:
    st.session_state.form = {"category": None, "brand": "", "keywords": []}
if "results" not in st.session_state:
    st.session_state.results = []


def submit_form(category, brand, keywords):
    st.session_state.form = {"category": category, "brand": brand, "keywords": keywords}
    st.session_state.stage = "loading"


def run_analysis(products_by_category):
    form = st.session_state.form
    st.session_state.results = rank_products(
        products_by_category, form["category"], form["keywords"], form["brand"]
    )
    st.session_state.stage = "results"


# ------------------------------------------------------------------
# 상세 정보 모달
# ------------------------------------------------------------------
@st.dialog("제품 상세 정보", width="large")
def show_detail_dialog(product, score, selected_keywords, selected_brand):
    meta = get_category_meta(product["category"])
    top_kws = top_keywords_for_product(product, selected_keywords or [])
    reason = build_reason(product, score, selected_keywords or [], selected_brand, top_kws)

    col_icon, col_title = st.columns([1, 5])
    with col_icon:
        st.markdown(
            f'<div class="pb-modalicon" style="background:{meta["grad"]}">{meta["icon"]}</div>',
            unsafe_allow_html=True,
        )
    with col_title:
        st.markdown(f"### {product['name']}")
        st.caption(f"{product['brand']} · {product['subtype']}")

    st.markdown("##### 추천 이유")
    st.markdown(f'<div class="pb-reasonbox">{reason}</div>', unsafe_allow_html=True)

    st.markdown("##### 핵심 성분")
    st.markdown(
        "".join(f'<span class="pb-chip">{ing}</span>' for ing in product["key_ingredients"]),
        unsafe_allow_html=True,
    )

    st.markdown("##### 키워드별 언급 현황")
    for kw in top_kws:
        stat = product["keyword_sentiment"].get(kw)
        if stat:
            st.markdown(f"- **{kw}** — 관련 후기 {stat['mentioned_count']:,}건 중 **{stat['positive_pct']}% 긍정**")

    col_a, col_b = st.columns(2)
    with col_a:
        st.metric("총 후기 건수", f"{product['review_count']:,}건")
    with col_b:
        if score is not None:
            st.metric("매칭 스코어", f"{score}%")
        else:
            st.metric("평균 평점", f"{product['avg_rating']:.1f} / 5.0")

    st.markdown("##### 판매 채널")
    st.markdown(f'<span class="pb-chip">{product["channel"]}</span>', unsafe_allow_html=True)
    st.caption(f"약 {product['price_krw']:,}원")


# ------------------------------------------------------------------
# 공통 컴포넌트
# ------------------------------------------------------------------
def render_header():
    col_logo, col_text = st.columns([1, 6])
    with col_logo:
        if LOGO_PATH.exists():
            st.image(str(LOGO_PATH), use_container_width=True)
    with col_text:
        st.markdown('<div class="pb-badge">BETA</div>', unsafe_allow_html=True)
        st.markdown('<div class="pb-title">픽브리프 PickBrief</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="pb-subtitle">카테고리와 벤치마크 브랜드, 원하는 감성 키워드만 알려주시면 '
            '후기 데이터 기반으로 매칭된 대표 아이템 3개와 추천 근거를 즉시 뽑아드립니다.</div>',
            unsafe_allow_html=True,
        )
    st.divider()


def render_product_card(product, meta, key_prefix, rank_label=None, score=None,
                         selected_keywords=None, selected_brand=None):
    with st.container(border=True):
        flag_html = f'<span class="pb-rankflag">{rank_label}</span>' if rank_label else ""
        st.markdown(
            f'<div class="pb-cardtop" style="background:{meta["grad"]}">{flag_html}<span>{meta["icon"]}</span></div>',
            unsafe_allow_html=True,
        )

        col_name, col_score = st.columns([3, 1])
        with col_name:
            st.markdown(f"**{product['name']}**")
            st.caption(f"{product['brand']} · {product['subtype']}")
        with col_score:
            if score is not None:
                st.markdown(
                    f'<div class="score-ring" style="--score:{score}">'
                    f'<div class="score-ring-inner">{score}%</div></div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(f'<div class="pb-ratingbadge">⭐ {product["avg_rating"]:.1f}</div>', unsafe_allow_html=True)

        if st.button("자세히 보기 →", key=f"{key_prefix}_{product['id']}", use_container_width=True):
            show_detail_dialog(product, score, selected_keywords, selected_brand)


# ------------------------------------------------------------------
# 화면 1: 입력
# ------------------------------------------------------------------
def render_input_screen(categories, brands_by_category, keywords_by_category):
    render_header()

    st.markdown("##### 추천 조건 입력")
    category = st.selectbox(
        "카테고리 선택", options=categories, index=None, placeholder="카테고리를 선택하세요",
        key="input_category",
    )

    brand = BRAND_NONE
    selected_keywords = []

    if category:
        brand_options = [BRAND_NONE] + brands_by_category.get(category, [])
        brand = st.selectbox(
            "벤치마크 브랜드 (선택, 검색 가능)",
            options=brand_options,
            index=0,
            key=f"input_brand__{category}",
        )

        st.markdown("**원하는 느낌 / 감성 키워드** (1개 이상 선택)")
        selected_keywords = st.pills(
            "keyword_pills",
            options=keywords_by_category.get(category, []),
            selection_mode="multi",
            label_visibility="collapsed",
            key=f"input_keywords__{category}",
        ) or []
    else:
        st.caption("카테고리를 먼저 선택하세요")

    ready = bool(category) and bool(selected_keywords)
    if st.button("🔍 대표 아이템 3개 분석하기", type="primary", use_container_width=True, disabled=not ready):
        real_brand = "" if brand == BRAND_NONE else brand
        submit_form(category, real_brand, selected_keywords)
        st.rerun()
    if not ready:
        st.caption("카테고리를 선택하고 감성 키워드를 1개 이상 골라주세요")

    st.markdown(
        '<div class="pb-footer-note">※ 본 베타는 목업(mock) 데이터를 기반으로 동작하며, '
        '실제 후기 크롤링/AI API 연동 없이 규칙 기반 로직으로 매칭 결과를 생성합니다.</div>',
        unsafe_allow_html=True,
    )

    st.divider()
    if st.button("전체 상품 둘러보기 →", use_container_width=True):
        st.session_state.stage = "browse"
        st.rerun()


# ------------------------------------------------------------------
# 화면 2: 분석 중
# ------------------------------------------------------------------
def render_loading_screen(products_by_category):
    render_header()

    placeholder = st.empty()
    progress = st.progress(0)

    steps = [
        ("후기 데이터를 수집하고 있어요...", 25),
        ("감성 키워드를 분석하고 있어요...", 55),
        ("유사 제품을 매칭하고 있어요...", 80),
        ("추천 브리프를 생성하고 있어요...", 100),
    ]
    for label, pct in steps:
        placeholder.markdown(f"##### {label}")
        progress.progress(pct)
        time.sleep(0.5)

    run_analysis(products_by_category)
    st.rerun()


# ------------------------------------------------------------------
# 화면 3: 결과
# ------------------------------------------------------------------
def render_results_screen():
    render_header()

    form = st.session_state.form
    brand_label = form["brand"] or "브랜드 무관"
    st.markdown(
        f"조건: 카테고리 **{form['category']}** · 벤치마크 브랜드 **{brand_label}** · "
        f"키워드 **{', '.join(form['keywords'])}**"
    )
    if st.button("↩︎ 새 조건으로 다시 검색하기"):
        st.session_state.stage = "input"
        st.rerun()

    st.markdown("#### 후기 데이터 기반 매칭 결과 TOP 3")
    results = st.session_state.results
    if not results:
        st.info("조건에 맞는 추천 결과가 없습니다.")
        return

    meta = get_category_meta(form["category"])
    cols = st.columns(len(results))
    for idx, (col, (product, score)) in enumerate(zip(cols, results)):
        with col:
            render_product_card(
                product, meta, key_prefix="result", rank_label=f"TOP {idx + 1}", score=score,
                selected_keywords=form["keywords"], selected_brand=form["brand"],
            )


# ------------------------------------------------------------------
# 화면 4: 전체 상품 둘러보기
# ------------------------------------------------------------------
def render_browse_screen(data, categories, products_by_category):
    render_header()

    if st.button("← 처음으로"):
        st.session_state.stage = "input"
        st.rerun()

    st.markdown("#### 전체 상품 둘러보기")
    filter_category = st.selectbox("카테고리 필터", options=["전체"] + categories, index=0, key="browse_category")
    products = data if filter_category == "전체" else products_by_category.get(filter_category, [])
    st.caption(f"{filter_category} · {len(products)}개 제품")

    for i in range(0, len(products), 3):
        row = products[i:i + 3]
        cols = st.columns(3)
        for col, product in zip(cols, row):
            with col:
                render_product_card(product, get_category_meta(product["category"]), key_prefix="browse")


# ------------------------------------------------------------------
# 메인 라우팅
# ------------------------------------------------------------------
def main():
    data = load_data()
    categories, products_by_category, brands_by_category, keywords_by_category = build_indexes(data)

    if st.session_state.stage == "input":
        render_input_screen(categories, brands_by_category, keywords_by_category)
    elif st.session_state.stage == "loading":
        render_loading_screen(products_by_category)
    elif st.session_state.stage == "results":
        render_results_screen()
    elif st.session_state.stage == "browse":
        render_browse_screen(data, categories, products_by_category)


if __name__ == "__main__":
    main()
