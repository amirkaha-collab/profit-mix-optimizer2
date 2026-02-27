import streamlit as st
import pandas as pd
import numpy as np
import itertools
from pathlib import Path

# =========================
# Page + RTL "product" CSS
# =========================
st.set_page_config(page_title="Profit Mix Optimizer", layout="wide")

st.markdown(
    """
<style>
/* RTL + typography */
html, body, [class*="css"] { direction: rtl; text-align: right; }
h1, h2, h3, h4, p, label, div { text-align: right; }
table { direction: rtl; width: 100%; border-collapse: collapse; }
thead th { text-align: right !important; background:#f7f7f9; padding: 10px; border-bottom: 1px solid #e6e6ef; }
tbody td { text-align: right !important; padding: 10px; border-bottom: 1px solid #f0f0f5; }

/* Cards */
.kpi-card{
  border:1px solid #e9e9f2;
  border-radius:16px;
  padding:14px 14px 10px 14px;
  background:#ffffff;
  box-shadow:0 1px 10px rgba(0,0,0,0.03);
}
.kpi-title{ font-size: 14px; color:#555; margin-bottom:6px; }
.kpi-big{ font-size: 24px; font-weight: 700; margin:0; }
.kpi-sub{ font-size: 12px; color:#777; margin-top:6px; }

/* Pills */
.pill{ display:inline-block; padding:4px 10px; border-radius:999px; font-size:12px; border:1px solid #e9e9f2; background:#fafafe; margin-left:6px; }

/* Alerts */
.bad{ background:#ffe9ea !important; }
.warn{ background:#fff2d8 !important; }
.good{ background:#e9f8ee !important; }
/* Ensure readable text on light backgrounds */
.bad, .warn, .good { color:#111 !important; }

/* Sliders: keep LTR so tooltip/ticks don't get pushed off-screen in RTL (esp. mobile) */
div[data-baseweb="slider"], div[data-baseweb="slider"] * { direction:ltr !important; }
/* Keep slider labels RTL */
label, .stSlider label { direction: rtl !important; text-align: right !important; }
/* Small horizontal padding for narrow screens */
div[data-baseweb="slider"] { padding-left: 12px; padding-right: 12px; }


/* Buttons spacing */
div.stButton > button { border-radius: 12px; padding: 0.5rem 0.9rem; }

/* Hide Streamlit footer */
footer {visibility: hidden;}
</style>
""",
    unsafe_allow_html=True
)

# =========================
# Header
# =========================
st.markdown(
    """
<div style="padding: 6px 0 6px 0;">
  <div style="font-size:30px; font-weight:800; line-height:1.2;">Profit Mix Optimizer</div>
  <div style="margin-top:6px; color:#555; font-size:14px;">
    כלי שמציע <b>3 חלופות</b> לשילוב בין <b>2 קרנות השתלמות</b> מתוך קובץ החשיפות — לפי היעדים והכללים שתגדיר.
    <span class="pill">Single Source of Truth</span>
    <span class="pill">RTL</span>
    <span class="pill">3 חלופות</span>
  </div>
  <div style="margin-top:6px; color:#666; font-size:13px;">
    מה צריך להזין? יעד לחו״ל (או יעד לישראל), יעד למניות, אופציונלית יעד למט״ח / לא־סחיר, ומגבלת לא־סחיר (Hard).
  </div>
</div>
""",
    unsafe_allow_html=True
)

# =========================
# Data loading (Single Source of Truth)
# =========================
PARAM_MAP = {
    "סך חשיפה למניות מתוך כלל נכסי הקופה": "stocks",
    'סך חשיפה לנכסים המושקעים בחו"ל מתוך כלל נכסי הקופה': "foreign",
    "מדד שארפ": "sharpe",
    "נכסים לא סחירים": "illiquid",
    "חשיפה למט\"ח": "fx",
}

def _parse_number(x):
    if pd.isna(x):
        return np.nan
    if isinstance(x, (int, float, np.number)):
        return float(x)
    s = str(x).strip().replace("\u200f", "").replace("\u200e", "")
    if s.endswith("%"):
        s = s[:-1]
    s = s.replace(",", "")
    try:
        return float(s)
    except Exception:
        return np.nan

@st.cache_data(show_spinner=False)
def load_xlsx(path: str) -> pd.DataFrame:
    xls = pd.ExcelFile(path)
    rows = []
    for sheet in xls.sheet_names:
        df = pd.read_excel(path, sheet_name=sheet)
        if "פרמטר" not in df.columns:
            continue
        df = df.dropna(subset=["פרמטר"])
        pcol = df["פרמטר"].astype(str)
        funds = [c for c in df.columns if c != "פרמטר"]
        for fund in funds:
            rec = {"sheet": sheet, "fund": str(fund).strip()}
            for heb, key in PARAM_MAP.items():
                m = pcol == heb
                if m.any():
                    rec[key] = _parse_number(df.loc[m, fund].iloc[0])
            rows.append(rec)

    out = pd.DataFrame(rows)
    out["israel"] = 100.0 - out["foreign"]  # כלל ישראל
    out["fund_key"] = out["sheet"].astype(str) + " | " + out["fund"].astype(str)
    return out

DEFAULT_FILE = Path(__file__).with_name("קרנות_השתלמות_חשיפות.xlsx")
if not DEFAULT_FILE.exists():
    st.error("לא נמצא קובץ האקסל ליד app.py. ודא שהקובץ 'קרנות_השתלמות_חשיפות.xlsx' נמצא באותה תיקייה ב־GitHub.")
    st.stop()

data = load_xlsx(str(DEFAULT_FILE))

# =========================
# Helpers: provider + service scores (user-defined)
# =========================
def provider_from_fund_name(fund_name: str) -> str:
    tokens = fund_name.replace("-", " ").replace("_", " ").split()
    return tokens[0] if tokens else fund_name

providers = sorted({provider_from_fund_name(x) for x in data["fund"].astype(str).tolist()})

def get_service_scores_from_ui(selected_providers):
    # בסיס: הסליידרים
    scores = {}
    for p in selected_providers:
        key = f"svc_{p}"
        scores[p] = float(st.session_state.get(key, 5.0))
    # אם הועלה CSV — הוא גובר על הסליידרים
    override = st.session_state.get("service_scores_override")
    if isinstance(override, dict):
        for p, v in override.items():
            try:
                scores[str(p).strip()] = float(v)
            except Exception:
                continue
    return scores

def service_score_for_fund(fund_name: str, service_scores: dict) -> float:
    p = provider_from_fund_name(fund_name)
    return float(service_scores.get(p, 5.0))

# =========================
# Session state defaults
# =========================
def ensure_defaults():
    defaults = {
        "target_mode": "יעד חו\"ל",
        "target_foreign": 30.0,
        "target_israel": 70.0,
        "target_stocks": 40.0,
        "include_fx": False,
        "target_fx": 25.0,
        "include_illiquid_target": False,
        "target_illiquid": 20.0,
        "illiquid_cap": 20.0,
        "illiquid_pref_close_to_cap": False,
        "allow_same_provider": True,
        "objective": "דיוק ביעדים",
        "weight_step": 1,
        "max_funds": min(120, len(data)),
        "distance_warn": 2.0,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    if "service_scores_override" not in st.session_state:
        st.session_state["service_scores_override"] = None

    # Default service sliders
    for p in providers:
        k = f"svc_{p}"
        if k not in st.session_state:
            st.session_state[k] = 5.0

ensure_defaults()

def reset_settings():
    # keep service defaults at 5 unless user wants otherwise
    st.session_state.pop("service_scores_override", None)
    st.session_state.pop("service_csv", None)
    keys_to_reset = [
        "target_mode","target_foreign","target_israel","target_stocks","include_fx","target_fx",
        "include_illiquid_target","target_illiquid","illiquid_cap","illiquid_pref_close_to_cap",
        "allow_same_provider","objective","weight_step","max_funds","distance_warn"
    ]
    for k in keys_to_reset:
        st.session_state.pop(k, None)
    ensure_defaults()
    st.session_state["results"] = None

# =========================
# Presets
# =========================
def preset_global_60_40():
    st.session_state["target_mode"] = 'יעד חו"ל'
    st.session_state["target_foreign"] = 60.0
    st.session_state["target_stocks"] = 40.0
    st.session_state["include_fx"] = False
    st.session_state["include_illiquid_target"] = False
    st.session_state["illiquid_cap"] = 60.0
    st.session_state["objective"] = "דיוק ביעדים"

def preset_max_fx():
    st.session_state["target_mode"] = 'יעד חו"ל'
    st.session_state["include_fx"] = True
    st.session_state["target_fx"] = 80.0
    st.session_state["objective"] = 'מקסום חשיפה למט"ח'

def preset_illiquid_to_20():
    st.session_state["target_mode"] = 'יעד חו"ל'
    st.session_state["illiquid_cap"] = 20.0
    st.session_state["illiquid_pref_close_to_cap"] = True
    st.session_state["objective"] = 'קרוב לתקרת לא-סחיר'

# =========================
# Tabs
# =========================
tab1, tab2, tab3 = st.tabs(["הגדרות יעד", "תוצאות (3 חלופות)", "פירוט חישוב / שקיפות"])

# =========================
# TAB 1 - Settings
# =========================
with tab1:
    c1, c2 = st.columns([3, 2])

    with c1:
        st.subheader("הגדרות יעד וכללים")
        st.caption("הגדר את היעדים והחוקים. בסוף לחץ **חשב** ותוצגנה 3 חלופות מדורגות.")

        # Presets row
        p1, p2, p3, p4 = st.columns([1.2,1.2,1.2,1.2])
        with p1:
            st.button("Preset: תיק גלובלי 60/40", on_click=preset_global_60_40, use_container_width=True)
        with p2:
            st.button("Preset: מקסימום מט״ח", on_click=preset_max_fx, use_container_width=True)
        with p3:
            st.button("Preset: כמה שיותר לא־סחיר עד 20%", on_click=preset_illiquid_to_20, use_container_width=True)
        with p4:
            st.button("איפוס הגדרות", on_click=reset_settings, type="secondary", use_container_width=True)

        st.divider()

        st.radio("איך המשתמש מגדיר יעד מדינה", ["יעד חו\"ל", "יעד נכסים בישראל (יתורגם אוטומטית)"],
                 key="target_mode", horizontal=True)

        if st.session_state["target_mode"] == 'יעד חו"ל':
            st.slider('יעד חשיפה לחו"ל (%)', 0.0, 120.0, key="target_foreign", step=0.1)
        else:
            st.slider('יעד נכסים בישראל (%)', 0.0, 120.0, key="target_israel", step=0.1)
            st.session_state["target_foreign"] = 100.0 - float(st.session_state["target_israel"])
            st.info(f"תרגום אוטומטי: יעד חו״ל = {st.session_state['target_foreign']:.1f}% (כלל ישראל: ישראל = 100 − חו״ל)")

        st.slider("יעד חשיפה למניות (%)", 0.0, 120.0, key="target_stocks", step=0.1)

        fx_col, ill_col = st.columns(2)
        with fx_col:
            st.checkbox('להוסיף יעד למט״ח', key="include_fx")
            if st.session_state["include_fx"]:
                st.slider('יעד חשיפה למט"ח (%)', 0.0, 150.0, key="target_fx", step=0.1)
        with ill_col:
            st.checkbox('להוסיף יעד ללא־סחיר', key="include_illiquid_target")
            if st.session_state["include_illiquid_target"]:
                st.slider('יעד לא־סחיר (%)', -10.0, 60.0, key="target_illiquid", step=0.1)

        st.divider()
        st.subheader("מגבלות ודירוג")

        st.slider("מקסימום לא־סחיר (Hard Constraint) (%)", -10.0, 60.0, key="illiquid_cap", step=0.1)
        st.checkbox("להעדיף להיות קרוב לתקרה (כל עוד לא עוברים אותה)", key="illiquid_pref_close_to_cap")

        st.selectbox(
            "דירוג עיקרי (מקום #1)",
            ["דיוק ביעדים", 'מקסום מדד שארפ', 'מקסום חשיפה למט"ח', 'נזילות מקסימלית (מינימום לא־סחיר)', 'קרוב לתקרת לא־סחיר'],
            key="objective"
        )

        st.checkbox("לאפשר שתי קרנות מאותו גוף", key="allow_same_provider")

        st.divider()
        st.subheader("בקרות מהירות / יציבות")

        st.select_slider("דיוק חלוקה בין הקרנות (צעד באחוזים)", options=[1,2,5,10], key="weight_step",
                         help="1% הכי מדויק אך יותר חישובים. 5%-10% מהיר יותר.")
        st.slider("מגבלת כמות קרנות לחישוב (למהירות)", 20, min(200, len(data)), key="max_funds")
        st.slider("סף 'סטייה גבוהה' לצביעה כתומה (Score)", 0.0, 20.0, key="distance_warn", step=0.1)

        run = st.button("חשב", type="primary", use_container_width=True)

    with c2:
        st.subheader("שירות (הגדרת משתמש)")
        st.caption("כאן המשתמש מגדיר ציון שירות לכל גוף. זה ישפיע בעיקר על חלופה #3.")

        with st.expander("הגדרת ציוני שירות", expanded=True):
            st.markdown("**אפשרות מומלצת:** העלאת CSV עם ציוני שירות (קל לתחזוקה, בלי לגעת בקוד).")
            template_df = pd.DataFrame({"provider": providers, "score": [5.0]*len(providers)})
            st.download_button(
                label="הורד תבנית CSV לציוני שירות",
                data=template_df.to_csv(index=False).encode("utf-8"),
                file_name="service_scores_template.csv",
                mime="text/csv",
                use_container_width=True,
            )
            uploaded = st.file_uploader("העלה CSV (עמודות: provider, score)", type=["csv"], key="service_csv")
            if uploaded is not None:
                try:
                    df_svc = pd.read_csv(uploaded)
                    df_svc.columns = [c.strip().lower() for c in df_svc.columns]
                    if ("provider" not in df_svc.columns) or ("score" not in df_svc.columns):
                        st.error("ה־CSV חייב לכלול עמודות בשם provider ו־score")
                    else:
                        df_svc = df_svc[["provider","score"]].dropna()
                        df_svc["provider"] = df_svc["provider"].astype(str).str.strip()
                        df_svc["score"] = pd.to_numeric(df_svc["score"], errors="coerce")
                        df_svc = df_svc.dropna(subset=["score"]).copy()
                        # clamp to 0..10
                        df_svc["score"] = df_svc["score"].clip(0, 10)
                        st.session_state["service_scores_override"] = dict(zip(df_svc["provider"], df_svc["score"]))
                        st.success(f"נטענו ציוני שירות עבור {len(st.session_state['service_scores_override'])} גופים")
                        st.dataframe(df_svc, use_container_width=True)
                        if st.button("החל ציוני CSV על הסליידרים", use_container_width=True):
                            for prov, sc in st.session_state["service_scores_override"].items():
                                k = f"svc_{prov}"
                                if k in st.session_state:
                                    st.session_state[k] = float(sc)
                            st.success("הסליידרים עודכנו לפי ה־CSV")
                except Exception as e:
                    st.error(f"שגיאה בקריאת ה־CSV: {e}")
            st.divider()

            st.caption("ברירת מחדל: 5 לכל גוף. אפשר לשנות לפי תפיסת שירות/דיגיטל/זמינות/תמיכה וכו׳.")
            # Show only common providers first
            show_n = min(12, len(providers))
            st.info("טיפ: אפשר להתחיל עם 8–12 גופים נפוצים, ואחר כך לפרט.")

            for p in providers[:show_n]:
                st.slider(f"{p}", 0.0, 10.0, key=f"svc_{p}", step=0.1)

            if len(providers) > show_n:
                with st.expander("עוד גופים"):
                    for p in providers[show_n:]:
                        st.slider(f"{p}", 0.0, 10.0, key=f"svc_{p}", step=0.1)

# =========================
# Core optimization functions
# =========================
def combo_metrics(a, b, w, svc_scores):
    out = {}
    for k in ["foreign","stocks","fx","illiquid","sharpe","israel"]:
        va = a.get(k, np.nan)
        vb = b.get(k, np.nan)
        if pd.isna(va) and pd.isna(vb):
            out[k] = np.nan
        elif pd.isna(va):
            out[k] = float(vb)
        elif pd.isna(vb):
            out[k] = float(va)
        else:
            out[k] = float(w*va + (1-w)*vb)

    # service is weighted by user-defined provider scores
    sa = service_score_for_fund(a["fund"], svc_scores)
    sb = service_score_for_fund(b["fund"], svc_scores)
    out["service"] = float(w*sa + (1-w)*sb)
    return out

def build_targets():
    targets = {
        "foreign": float(st.session_state["target_foreign"]),
        "stocks": float(st.session_state["target_stocks"]),
    }
    if st.session_state["include_fx"]:
        targets["fx"] = float(st.session_state["target_fx"])
    if st.session_state["include_illiquid_target"]:
        targets["illiquid"] = float(st.session_state["target_illiquid"])
    return targets

def distance_to_targets(m, targets):
    d = 0.0
    for k, t in targets.items():
        v = m.get(k, np.nan)
        if pd.isna(v):
            d += 10.0
        else:
            d += abs(v - t)
    if st.session_state["illiquid_pref_close_to_cap"]:
        ill = m.get("illiquid", np.nan)
        if not pd.isna(ill):
            d += abs(float(st.session_state["illiquid_cap"]) - ill) * 0.2
    return d

def primary_score(m, targets):
    obj = st.session_state["objective"]
    if obj == "דיוק ביעדים":
        return -distance_to_targets(m, targets)
    if obj == "מקסום מדד שארפ":
        return m.get("sharpe", np.nan)
    if obj == 'מקסום חשיפה למט"ח':
        return m.get("fx", np.nan)
    if obj == 'נזילות מקסימלית (מינימום לא־סחיר)':
        ill = m.get("illiquid", np.nan)
        return -ill if not pd.isna(ill) else np.nan
    if obj == 'קרוב לתקרת לא־סחיר':
        ill = m.get("illiquid", np.nan)
        cap = float(st.session_state["illiquid_cap"])
        return -abs(cap - ill) if not pd.isna(ill) else np.nan
    return -distance_to_targets(m, targets)

def passes_constraints(m):
    ill = m.get("illiquid", np.nan)
    if pd.isna(ill):
        return False
    return ill <= float(st.session_state["illiquid_cap"]) + 1e-9

def tie_breaker(m, targets):
    sh = m.get("sharpe", -999.0)
    fxv = m.get("fx", -999.0)
    return (sh, fxv, -distance_to_targets(m, targets))

def best_three_options(results_df: pd.DataFrame) -> pd.DataFrame:
    # Option 1: by primary
    opt1 = results_df.sort_values(["primary","tb1","tb2","tb3"], ascending=False).head(1)

    # Option 2: Sharpe alternative (near opt1 if objective=accuracy)
    if st.session_state["objective"] == "דיוק ביעדים":
        best_dist = float(opt1["distance"].iloc[0])
        pool = results_df[results_df["distance"] <= best_dist + 1.0].copy()
        if len(pool) == 0:
            pool = results_df.copy()
    else:
        pool = results_df.copy()
    opt2 = pool.sort_values(["sharpe","primary","tb1","tb2","tb3"], ascending=False).head(1)

    # Option 3: Service alternative (near opt1 if objective=accuracy)
    if st.session_state["objective"] == "דיוק ביעדים":
        pool3 = results_df[results_df["distance"] <= float(opt1["distance"].iloc[0]) + 2.0].copy()
        if len(pool3) == 0:
            pool3 = results_df.copy()
    else:
        pool3 = results_df.copy()
    opt3 = pool3.sort_values(["service","primary","tb1","tb2","tb3"], ascending=False).head(1)

    out = pd.concat([opt1, opt2, opt3], ignore_index=True)
    out["Rank"] = ["#1", "#2", "#3"]
    return out

def advantage_text(row, opt1_row):
    # Row-specific punchy explanation
    dist = float(row["distance"])
    if row["Rank"] == "#1":
        return f"הכי מדויק ליעד/דירוג שנבחר — סטייה כוללת {dist:.2f}."
    if row["Rank"] == "#2":
        s1 = float(opt1_row.get("sharpe", np.nan))
        s2 = float(row.get("sharpe", np.nan))
        if np.isnan(s1) or np.isnan(s2):
            return f"שארפ משוקלל גבוה יותר (או קרוב ביותר) — סטייה {dist:.2f}."
        delta = s2 - s1
        sign = "גבוה" if delta >= 0 else "נמוך"
        return f"שארפ משוקלל {sign} ב־{abs(delta):.2f} לעומת חלופה #1, תוך סטייה {dist:.2f}."
    # #3
    svc1 = float(opt1_row.get("service", np.nan))
    svc3 = float(row.get("service", np.nan))
    if np.isnan(svc1) or np.isnan(svc3):
        return f"ציון שירות משוקלל הגבוה ביותר (לפי הגדרת המשתמש), תחת המגבלות."
    delta = svc3 - svc1
    return f"ציון שירות משוקלל הגבוה ביותר — גבוה ב־{delta:.2f} לעומת חלופה #1."

def kpi_card(title, big, sub=""):
    st.markdown(
        f"""
<div class="kpi-card">
  <div class="kpi-title">{title}</div>
  <div class="kpi-big">{big}</div>
  <div class="kpi-sub">{sub}</div>
</div>
""",
        unsafe_allow_html=True
    )

def colorize_table(df, illiquid_cap, distance_warn):
    # Returns HTML table with cell-level coloring
    def cls_ill(v):
        try:
            return "bad" if float(v) > illiquid_cap + 1e-9 else ""
        except Exception:
            return ""
    def cls_dist(v):
        try:
            return "warn" if float(v) >= distance_warn else ""
        except Exception:
            return ""
    html = "<table><thead><tr>"
    for col in df.columns:
        html += f"<th>{col}</th>"
    html += "</tr></thead><tbody>"

    for idx, row in df.iterrows():
        row_cls = "good" if row.get("Rank","") == "#1" else ""
        html += f"<tr class='{row_cls}'>"
        for col in df.columns:
            cell = row[col]
            extra = ""
            if col == "לא סחיר (%)":
                extra = cls_ill(cell)
            if col == "סטייה כוללת (Score)":
                extra = (extra + " " + cls_dist(cell)).strip()
            html += f"<td class='{extra}'>{cell}</td>"
        html += "</tr>"
    html += "</tbody></table>"
    return html

# =========================
# Run computation (only after pressing 'חשב')
# =========================
if "results" not in st.session_state:
    st.session_state["results"] = None

def compute():
    # Prepare work table
    work = data.copy()
    work = work.dropna(subset=["foreign","stocks","illiquid"]).reset_index(drop=True)

    # Prefer rows with fx/sharpe present for better secondary rankings
    work["_completeness"] = (~work["fx"].isna()).astype(int) + (~work["sharpe"].isna()).astype(int)
    work = work.sort_values(["_completeness"], ascending=False).head(int(st.session_state["max_funds"])).reset_index(drop=True)

    # service scores from UI
    svc_scores = get_service_scores_from_ui(providers)

    targets = build_targets()

    step = int(st.session_state["weight_step"])
    weights = [w/100.0 for w in range(0, 101, step)]
    pairs = list(itertools.combinations(range(len(work)), 2))

    records = []
    total = len(pairs) * len(weights)
    prog = st.progress(0, text="מריץ חישוב…")
    done = 0

    for i, j in pairs:
        a = work.loc[i].to_dict()
        b = work.loc[j].to_dict()

        if (not st.session_state["allow_same_provider"]) and (provider_from_fund_name(a["fund"]) == provider_from_fund_name(b["fund"])):
            done += len(weights)
            continue

        for w in weights:
            m = combo_metrics(a, b, w, svc_scores)
            if not passes_constraints(m):
                done += 1
                continue

            dist = distance_to_targets(m, targets)
            prim = primary_score(m, targets)
            tb = tie_breaker(m, targets)

            records.append({
                "fund_A": a["fund_key"],
                "fund_B": b["fund_key"],
                "w_A_%": round(w*100, 0),
                "w_B_%": round((1-w)*100, 0),
                "foreign_%": m.get("foreign", np.nan),
                "israel_%": m.get("israel", np.nan),
                "stocks_%": m.get("stocks", np.nan),
                "fx_%": m.get("fx", np.nan),
                "illiquid_%": m.get("illiquid", np.nan),
                "sharpe": m.get("sharpe", np.nan),
                "service": m.get("service", np.nan),
                "distance": dist,
                "primary": prim,
                "tb1": tb[0],
                "tb2": tb[1],
                "tb3": tb[2],
            })
            done += 1

        if done % max(1, total // 200) == 0:
            prog.progress(min(1.0, done / total), text="מריץ חישוב…")

    prog.progress(1.0, text="החישוב הושלם")

    if len(records) == 0:
        return None, work, targets

    res = pd.DataFrame(records)
    top = best_three_options(res)

    # Build explanations
    opt1 = top[top["Rank"] == "#1"].iloc[0].to_dict()
    top["יתרון"] = top.apply(lambda r: advantage_text(r, opt1), axis=1)

    # Round numeric columns
    for c in ["foreign_%","israel_%","stocks_%","fx_%","illiquid_%","distance","service","sharpe"]:
        if c in top.columns:
            top[c] = pd.to_numeric(top[c], errors="coerce").round(2)

    return top, work, targets

# =========================
# TAB 2 - Results
# =========================
with tab2:
    st.subheader("תוצאות — 3 חלופות מדורגות")
    st.caption("קודם מגדירים ב־Tab 1 ולוחצים 'חשב'. כאן תראה כרטיסי KPI + טבלה מלאה + צבעי חריגה.")

    if st.session_state["results"] is None:
        st.info("אין תוצאות עדיין. עבור ל־Tab 1, הגדר יעד וכללים, ואז לחץ **חשב**.")
    else:
        top = st.session_state["results"]["top"]
        ill_cap = float(st.session_state["illiquid_cap"])
        distance_warn = float(st.session_state["distance_warn"])

        # KPI cards per option
        for rank in ["#1", "#2", "#3"]:
            r = top[top["Rank"] == rank].iloc[0]

            st.markdown(f"<h3 style='margin-top: 10px;'>חלופה {rank}</h3>", unsafe_allow_html=True)

            k1, k2, k3, k4 = st.columns(4)

            with k1:
                kpi_card("סטייה כוללת (Score)", f"{float(r['distance']):.2f}", "נמוך יותר = קרוב יותר ליעד")
            with k2:
                kpi_card("חו״ל / מניות", f"{float(r['foreign_%']):.2f}% / {float(r['stocks_%']):.2f}%", "תמהיל חשיפה משוקלל")
            with k3:
                fx_txt = "N/A" if pd.isna(r["fx_%"]) else f"{float(r['fx_%']):.2f}%"
                ill_txt = "N/A" if pd.isna(r["illiquid_%"]) else f"{float(r['illiquid_%']):.2f}%"
                kpi_card("מט״ח / לא־סחיר", f"{fx_txt} / {ill_txt}", f"תקרת לא־סחיר: {ill_cap:.1f}%")
            with k4:
                sh_txt = "N/A" if pd.isna(r["sharpe"]) else f"{float(r['sharpe']):.2f}"
                svc_txt = f"{float(r['service']):.2f}"
                kpi_card("שארפ / שירות", f"{sh_txt} / {svc_txt}", "שירות לפי הגדרת המשתמש")

            st.markdown(f"<div style='margin-top:8px; color:#444; font-size:13px;'><b>יתרון:</b> {r['יתרון']}</div>", unsafe_allow_html=True)
            st.divider()

        # Full table
        st.subheader("טבלה מלאה (3 חלופות)")

        display = top.copy()
        display = display.rename(columns={
            "fund_A": "קרן א׳",
            "w_A_%": "משקל א׳ (%)",
            "fund_B": "קרן ב׳",
            "w_B_%": "משקל ב׳ (%)",
            "foreign_%": "חו״ל (%)",
            "israel_%": "ישראל (%) (חישוב)",
            "stocks_%": "מניות (%)",
            "fx_%": "מט״ח (%)",
            "illiquid_%": "לא סחיר (%)",
            "sharpe": "שארפ",
            "service": "שירות",
            "distance": "סטייה כוללת (Score)",
        })

        ordered = ["Rank","יתרון","קרן א׳","משקל א׳ (%)","קרן ב׳","משקל ב׳ (%)",
                   "חו״ל (%)","ישראל (%) (חישוב)","מניות (%)","מט״ח (%)","לא סחיר (%)",
                   "שארפ","שירות","סטייה כוללת (Score)"]
        ordered = [c for c in ordered if c in display.columns]

        html = colorize_table(display[ordered], illiquid_cap=ill_cap, distance_warn=distance_warn)
        st.markdown(html, unsafe_allow_html=True)

# =========================
# TAB 3 - Transparency
# =========================
with tab3:
    st.subheader("שקיפות / פירוט חישוב")
    st.caption("כדי לא להעמיס, הפירוט בתוך Expander. כולל: יעדים, מגבלות, וכללי הדירוג, וגם נתוני מקור מסוננים.")

    if st.session_state["results"] is None:
        st.info("אין תוצאות עדיין. הרץ חישוב ב־Tab 1.")
    else:
        top = st.session_state["results"]["top"]
        work = st.session_state["results"]["work"]
        targets = st.session_state["results"]["targets"]

        with st.expander("מה בדיוק חושב — נוסחה ומשמעות", expanded=True):
            st.markdown(
                """
**איך מחושב תמהיל משוקלל?**  
לכל פרמטר (חו״ל/מניות/מט״ח/לא־סחיר/שארפ/שירות) מתבצע ממוצע משוקלל:

- ערך משוקלל = (משקל קרן א׳ × ערך א׳) + (משקל קרן ב׳ × ערך ב׳)

**Hard Constraint**  
כל שילוב שבו *לא־סחיר* גדול מ־תקרת לא־סחיר → נפסל.

**Score (סטייה כוללת)**  
סכום סטיות מוחלטות מהיעדים שהוגדרו (L1):  
- |חו״ל − יעד חו״ל| + |מניות − יעד מניות| + (אופציונלית: מט״ח/לא־סחיר אם הוגדרו כיעדים)

**כלל ישראל**  
ישראל = 100 − חו״ל (לא משתמשים בעמודת "נכסים בארץ" בקובץ).
"""
            )

        with st.expander("יעדים/מגבלות שנכנסו לריצה הזו"):
            st.write({
                "targets": targets,
                "illiquid_cap": float(st.session_state["illiquid_cap"]),
                "objective": st.session_state["objective"],
                "weight_step": int(st.session_state["weight_step"]),
                "allow_same_provider": bool(st.session_state["allow_same_provider"]),
            })

        with st.expander("הצגת נתוני מקור ששימשו בפועל (אחרי סינון למהירות)"):
            st.dataframe(work.drop(columns=["_completeness"]).reset_index(drop=True), use_container_width=True)

# =========================
# Hook: if user pressed 'חשב' in tab1, run compute and save
# =========================
# We place it at the end so that UI is fully built and we can render progress properly.
if 'run' in locals() and run:
    top, work, targets = compute()
    if top is None:
        st.session_state["results"] = None
        st.error("לא נמצאו שילובים שעומדים במגבלות (למשל: תקרת לא־סחיר). נסה להגדיל תקרה או לשנות יעדים.")
    else:
        st.session_state["results"] = {"top": top, "work": work, "targets": targets}
        st.success("התוצאות עודכנו. עבור ל־Tab 2 לראות את 3 החלופות.")
