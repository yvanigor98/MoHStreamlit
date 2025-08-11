# app.py — Malaria Insights (Fixed Version)
import json
from pathlib import Path
from typing import List, Optional

import pandas as pd
import plotly.express as px
import streamlit as st

# --------------------------------
# Config & Paths
# --------------------------------
st.set_page_config(page_title="Malaria Insights — OPD Cases", page_icon="🦟", layout="wide")
ROOT = Path(__file__).parent
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)
GEOJSON_PATH = DATA / "rwanda_adm2.geojson"

# --------------------------------
# Helpers
# --------------------------------
@st.cache_data(show_spinner=False)
def load_csv(path: Path) -> pd.DataFrame:
    if path.exists() and path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    return pd.DataFrame()

@st.cache_data(show_spinner=False)
def load_geojson(path: Path) -> Optional[dict]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None

def first_col(df: pd.DataFrame, names: List[str]) -> Optional[str]:
    for n in names:
        if n in df.columns:
            return n
    return None

MONTH_LABELS = {1:"Jan",2:"Feb",3:"Mar",4:"Apr",5:"May",6:"Jun",7:"Jul",8:"Aug",9:"Sep",10:"Oct",11:"Nov",12:"Dec"}

def month_to_num(m):
    if pd.isna(m):
        return None
    if isinstance(m, (int, float)) and not pd.isna(m):
        return int(m)
    s = str(m).strip()
    if s.isdigit():
        return int(s)
    mnames = {
        'jan':1,'january':1,'feb':2,'february':2,'mar':3,'march':3,'apr':4,'april':4,
        'may':5,'jun':6,'june':6,'jul':7,'july':7,'aug':8,'august':8,'sep':9,'sept':9,'september':9,
        'oct':10,'october':10,'nov':11,'november':11,'dec':12,'december':12
    }
    return mnames.get(s.lower())

def infer_year_month(df: pd.DataFrame):
    if df.empty:
        return [], []
    ycol = first_col(df, ["year", "Year", "YEAR"]) 
    mcol = first_col(df, ["month", "Month", "MONTH"]) 
    years, months = [], []
    if ycol:
        years = sorted(pd.to_numeric(df[ycol], errors="coerce").dropna().astype(int).unique().tolist())
    if mcol:
        months = sorted({month_to_num(v) for v in df[mcol].dropna().unique().tolist() if month_to_num(v)})
    if not years or not months:
        dcol = first_col(df, ["date", "Date", "period", "Period", "report_date", "month_date"]) 
        if dcol:
            dt = pd.to_datetime(df[dcol], errors="coerce", infer_datetime_format=True)
            if not years:
                years = sorted(dt.dt.year.dropna().astype(int).unique().tolist())
            if not months:
                months = sorted(dt.dt.month.dropna().astype(int).unique().tolist())
    return years, months

def filter_year_month(df: pd.DataFrame, year_sel, month_sel):
    if df.empty:
        return df
    res = df.copy()
    ycol = first_col(res, ["year", "Year", "YEAR"]) 
    mcol = first_col(res, ["month", "Month", "MONTH"]) 
    dcol = first_col(res, ["date", "Date", "period", "Period", "report_date", "month_date"]) 

    if year_sel not in (None, "(All)"):
        yv = int(year_sel)
        if ycol is not None:
            res = res[pd.to_numeric(res[ycol], errors="coerce").astype("Int64") == yv]
        elif dcol is not None:
            dt = pd.to_datetime(res[dcol], errors="coerce", infer_datetime_format=True)
            res = res[dt.dt.year == yv]

    if month_sel not in (None, "(All)"):
        mv = {v: k for k, v in MONTH_LABELS.items()}.get(month_sel, month_to_num(month_sel))
        if mv:
            if mcol is not None:
                res = res[res[mcol].apply(month_to_num) == int(mv)]
            elif dcol is not None:
                dt = pd.to_datetime(res[dcol], errors="coerce", infer_datetime_format=True)
                res = res[dt.dt.month == int(mv)]

    return res

# --------------------------------
# Load Data (CSV only, relative paths)
# --------------------------------
OPD_CSV      = DATA / "opd.csv"
COMM_CSV     = DATA / "community.csv"  # optional

opd = load_csv(OPD_CSV)
community = load_csv(COMM_CSV)

datasets = {k: v for k, v in {"OPD": opd, "Community": community}.items() if not v.empty}
if not datasets:
    datasets = {"(empty)": pd.DataFrame()}

# --------------------------------
# Sidebar — Filters with unique keys
# --------------------------------
st.sidebar.header("Filters")
sel_dataset = st.sidebar.selectbox("Dataset", list(datasets.keys()), key="dataset_selector")
df0 = datasets[sel_dataset].copy()

# resolve key columns
DIST_COL = first_col(df0, ["district_clean", "district", "adm2_name"])
SECT_COL = first_col(df0, ["sector", "sector_name"])
MEAS_COL = first_col(df0, ["Total", "total", "cases", "value"])

# year/month
years, months = infer_year_month(df0)
year_sel = st.sidebar.selectbox("Year", ["(All)"] + [str(y) for y in years] if years else ["(All)"], key="year_selector")
month_sel = st.sidebar.selectbox("Month", ["(All)"] + [MONTH_LABELS[m] for m in months] if months else ["(All)"], key="month_selector")

# district filter
district_opts = sorted(df0[DIST_COL].dropna().astype(str).unique()) if DIST_COL else []
sel_districts = st.sidebar.multiselect("District(s)", district_opts, key="district_selector")

# Apply filters
df = filter_year_month(df0, year_sel, month_sel)
if DIST_COL and sel_districts:
    df = df[df[DIST_COL].astype(str).isin(sel_districts)]

# --------------------------------
# KPIs
# --------------------------------
st.title("Malaria Insights — OPD Cases")

mcol = MEAS_COL
dcol = DIST_COL
scol = SECT_COL

total_cases = int(df[mcol].sum()) if (mcol and not df.empty) else 0

active_districts = 0
top_d_name, top_d_val = "—", 0
if dcol and mcol and not df.empty:
    ddf = (
        df.groupby(dcol, dropna=False)[mcol]
          .sum()
          .reset_index()
          .rename(columns={dcol: "district", mcol: "Total"})
    )
    active_districts = int((ddf["Total"] > 0).sum())
    if not ddf.empty:
        row = ddf.sort_values("Total", ascending=False).iloc[0]
        top_d_name, top_d_val = str(row["district"]), int(row["Total"])

top_s_name, top_s_val = "—", 0
if scol and mcol and not df.empty:
    sdf = (
        df.groupby(scol, dropna=False)[mcol]
          .sum()
          .reset_index()
          .rename(columns={scol: "sector", mcol: "Total"})
    )
    if not sdf.empty:
        row = sdf.sort_values("Total", ascending=False).iloc[0]
        top_s_name, top_s_val = str(row["sector"]), int(row["Total"]) 

c1, c2, c3, c4 = st.columns(4)
with c1: st.metric("Total cases", f"{total_cases:,}")
with c2: st.metric("Active districts", f"{active_districts:,}")
with c3: st.metric("Top district", top_d_name, help=(f"{top_d_val:,} cases" if top_d_val else None))
with c4: st.metric("Top sector", top_s_name, help=(f"{top_s_val:,} cases" if top_s_val else None))

st.markdown("---")

# --------------------------------
# Map
# --------------------------------
st.subheader("Rwanda District Map")
geojson = load_geojson(GEOJSON_PATH)
if dcol and mcol and geojson is not None and not df.empty:
    d_agg = (
        df.groupby(dcol, dropna=False)[mcol]
          .sum()
          .reset_index()
          .rename(columns={dcol: "district", mcol: "Total"})
    )
    fig_map = px.choropleth_mapbox(
        d_agg,
        geojson=geojson,
        locations="district",
        featureidkey="properties.shapeName",
        color="Total",
        mapbox_style="carto-positron",
        zoom=6.5,
        center={"lat": -1.94, "lon": 29.87},
        opacity=0.75,
        height=640,
    )
    fig_map.update_layout(margin=dict(l=0, r=0, t=30, b=0))
    st.plotly_chart(fig_map, use_container_width=True)
else:
    st.info("To show the map, add data/rwanda_adm2.geojson and ensure your dataset has a district and a Total column.")

# --------------------------------
# Charts: Top Districts & Top Sectors
# --------------------------------
left, right = st.columns(2)

with left:
    st.markdown("### Top Districts")
    if dcol and mcol and not df.empty:
        ddf = (
            df.groupby(dcol, dropna=False)[mcol]
              .sum()
              .reset_index()
              .rename(columns={dcol: "district", mcol: "Total"})
        )
        ddf = ddf.sort_values("Total", ascending=False).head(15)
        fig_d = px.bar(ddf.sort_values("Total"), x="Total", y="district", orientation="h", height=520)
        fig_d.update_layout(margin=dict(l=20, r=20, t=40, b=20), uniformtext_minsize=8, uniformtext_mode='hide')
        st.plotly_chart(fig_d, use_container_width=True)
    else:
        st.info("No district column found.")

with right:
    st.markdown("### Top Sectors")
    if scol and mcol and not df.empty:
        sdf = (
            df.groupby(scol, dropna=False)[mcol]
              .sum()
              .reset_index()
              .rename(columns={scol: "sector", mcol: "Total"})
        )
        sdf = sdf.sort_values("Total", ascending=False).head(30)
        fig_s = px.bar(sdf, x="sector", y="Total", height=520)
        fig_s.update_layout(margin=dict(l=20, r=20, t=40, b=80))
        st.plotly_chart(fig_s, use_container_width=True)
    else:
        st.info("No sector column found.")

# --------------------------------
# Footer
# --------------------------------
st.caption("CSV-only version. Place opd.csv/community.csv in ./data and rwanda_adm2.geojson for the map.")