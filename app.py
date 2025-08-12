import streamlit as st
import pandas as pd
import geopandas as gpd
import plotly.express as px
from pathlib import Path


ROOT = Path(__file__).parent
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)

# --- Page Configuration ---
st.set_page_config(
    page_title="Rwanda Malaria Dashboard",
    page_icon="🇷🇼",
    layout="wide",
)

# --- Data Loading ---
@st.cache_data
def load_all_data():
    """Loads, preprocesses, and merges all datasets."""
    # --- Helper Function for Preprocessing ---
    def preprocess_df(df_raw, source_name):
        df_raw['date'] = pd.to_datetime(df_raw['year'].astype(str) + '-' + df_raw['month'], format='%Y-%B')
        df_raw['source'] = source_name
        return df_raw

    # --- Load Datasets ---
    try:
        df_opd = preprocess_df(pd.read_csv(DATA / 'malaria_cases_opd_final(in).csv'), 'OPD')
        df_chw = preprocess_df(pd.read_csv(DATA / 'malaria_community_final.csv'), 'CHWs')
        df_fever = preprocess_df(pd.read_csv(DATA / 'fever_cases_opd_final.csv'), 'Fever Cases')
    except FileNotFoundError as e:
        st.error(f"Error: A data file could not be found. Please check file names. Missing file: {e.filename}")
        return None, None

    # --- Load Geographic Data ---
    try:
        gdf_districts = gpd.read_file(DATA / 'geoBoundaries-RWA-ADM2.geojson')
    except Exception as e:
        st.error(f"Error loading GeoJSON file: {e}")
        return None, None
        
    datasets = {
        "OPD Cases": df_opd,
        "CHW Cases": df_chw,
        "Fever Cases": df_fever,
    }
    
    return datasets, gdf_districts

# --- Load all data ---
datasets, gdf_districts = load_all_data()

if not datasets or gdf_districts is None:
    st.stop()


# =======================
# Sidebar Controls
# =======================
st.sidebar.title("Dashboard Controls")

# --- Dataset Selector ---
selected_dataset_name = st.sidebar.selectbox(
    "Select a Dataset to View",
    options=list(datasets.keys())
)

# --- Get the selected dataframe for initial filter options ---
# We use df_master here to get unique filter options before any filtering occurs.
df_master = datasets[selected_dataset_name].copy()

st.sidebar.markdown("---")
st.sidebar.header("Chart Options")

# --- Trend Aggregation Filter (remains in sidebar) ---
aggregation_period = st.sidebar.radio(
    "Select Trend Aggregation",
    ["Yearly", "Quarterly", "Monthly"],
    help="Select the time period to aggregate the trend chart."
)


# =======================
# Main Page Layout
# =======================
st.title(f"{selected_dataset_name} Analysis")

# --- Main Page Filters (District, Year, Month) ---
# Moved directly under the title
filter_col1, filter_col2, filter_col3 = st.columns(3)

with filter_col1:
    # -- District Filter --
    district_list = ['All Districts'] + sorted(df_master['district_clean'].unique())
    selected_district = st.selectbox("Select District", options=district_list)

with filter_col2:
    # -- Year Filter --
    year_list = ['All Years'] + sorted(df_master['year'].unique(), reverse=True)
    selected_year = st.selectbox("Select Year", options=year_list)

with filter_col3:
    # -- Dynamic Month Filter --
    # Month list depends on selected_year, so it must be defined AFTER selected_year
    month_order = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
    if selected_year and selected_year != 'All Years':
        months_in_year = sorted(df_master[df_master['year'] == selected_year]['month'].unique(), key=lambda m: month_order.index(m))
        available_months = ['All Months'] + months_in_year
    else:
        all_months_in_data = sorted(df_master['month'].unique(), key=lambda m: month_order.index(m))
        available_months = ['All Months'] + all_months_in_data
    selected_month = st.selectbox("Select Month", options=available_months)

st.markdown("---")


# --- IMPORTANT: Define column names ---
VALUE_COL = 'Total'
AGE_COL = 'age_category_new'
GENDER_COL = 'gender'

# --- Filter Data based on selections ---
df = df_master.copy() # Work with a copy for filtering

# Removed the 'exclude_2020' checkbox and its logic.
# Users can now filter 2020 using the 'Year' dropdown if they wish.

if selected_district != 'All Districts':
    df = df[df['district_clean'] == selected_district]
if selected_year != 'All Years':
    df = df[df['year'] == selected_year]
if selected_month != 'All Months':
    df = df[df['month'] == selected_month]

# Check if the dataframe is empty after filtering
if df.empty:
    st.warning("No data available for the current filter selection. Please adjust the filters.")
    st.stop()
    
# =======================
# Display KPI Section
# =======================
# Calculate KPIs
total_cases = df[VALUE_COL].sum()
active_districts = df[df[VALUE_COL] > 0]['district_clean'].nunique()

# Top district
top_district_row = df.groupby('district_clean')[VALUE_COL].sum().nlargest(1).index
top_district = top_district_row[0] if not top_district_row.empty else "N/A"

# Top sector
top_sector = "N/A"
if 'sector' in df.columns:
    top_sector_row = df.groupby('sector')[VALUE_COL].sum().nlargest(1).index
    top_sector = top_sector_row[0] if not top_sector_row.empty else "N/A"

# --- Peak Period KPI ---
# Aggregate data by the chosen period to find the peak
resample_rule = {'Yearly': 'Y', 'Quarterly': 'Q', 'Monthly': 'M', }[aggregation_period]
period_df = df.set_index('date').resample(resample_rule)[VALUE_COL].sum()
peak_value = 0
peak_period_str = "N/A"
if not period_df.empty:
    peak_value = period_df.max()
    peak_period_ts = period_df.idxmax()
    if aggregation_period == "Yearly": peak_period_str = str(peak_period_ts.year)
    elif aggregation_period == "Quarterly": peak_period_str = f"Q{peak_period_ts.quarter} {peak_period_ts.year}"
    elif aggregation_period == "Monthly": peak_period_str = peak_period_ts.strftime('%B %Y')

# Display KPIs in columns
kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
kpi1.metric(label="Total cases", value=f"{total_cases:,.0f}")
kpi2.metric(label="Districts", value=active_districts)
kpi3.metric(label="District with Most Cases", value=top_district)
kpi4.metric(label="Sector with Most Cases", value=top_sector)
kpi5.metric(label=f"Peak {aggregation_period[:-2]}", value=peak_period_str, delta=f"{peak_value:,.0f} cases", delta_color="off")

st.markdown("---")


# --- Layout for Charts ---
col1, col2 = st.columns(2)

with col1:
    # --- MAP CHART (CHOROPLETH) ---
    st.subheader("Total Cases by District")
    district_cases = df.groupby('district_clean')[VALUE_COL].sum().reset_index()
    merged_gdf = gdf_districts.merge(district_cases, left_on='shapeName', right_on='district_clean', how='left').fillna(0)
    
    map_fig = px.choropleth_mapbox(
        merged_gdf, geojson=merged_gdf.geometry, locations=merged_gdf.index, color=VALUE_COL,
        hover_data=['shapeName', VALUE_COL], color_continuous_scale="Blues",
        mapbox_style="carto-positron", zoom=7.3, center={"lat": -1.94, "lon": 29.87}, opacity=0.7,
        labels={VALUE_COL: 'Total Cases'}
    )
    map_fig.update_traces(hovertemplate=("<b>%{customdata[0]}</b><br>" + "Total Cases: %{customdata[1]:,.0f}" + "<extra></extra>"))
    map_fig.update_layout(margin={"r":0, "t":0, "l":0, "b":0})
    st.plotly_chart(map_fig, use_container_width=True)

with col2:
    # --- DYNAMIC TIME SERIES CHART (Trend) ---
    st.subheader(f"{aggregation_period} Cases Trend")
    trend_df = period_df.reset_index()
    trend_df.columns = ['period', 'Total Cases']

    if aggregation_period in ["Yearly", "Quarterly"]:
        if aggregation_period == "Yearly": trend_df['period_str'] = trend_df['period'].dt.year.astype(str)
        else: trend_df['period_str'] = trend_df['period'].dt.to_period('Q').astype(str)
        trend_fig = px.bar(trend_df, x='period_str', y='Total Cases', title=f"{aggregation_period} Trend")
        trend_fig.update_layout(xaxis_title='Period', yaxis_title='Total Cases')
    else: # Monthly
        trend_fig = px.line(trend_df, x='period', y='Total Cases', title="Monthly Trend", markers=True)
        trend_fig.update_layout(xaxis_title='Month-Year', yaxis_title='Total Cases')
    st.plotly_chart(trend_fig, use_container_width=True)

# Top Districts & Sectors Charts
col3, col4 = st.columns(2)
with col3:
    if 'district_clean' in df.columns:
        st.subheader('Top 15 Districts by Cases Volume')
        top_15_districts_df = df.groupby('district_clean')[VALUE_COL].sum().nlargest(15).sort_values(ascending=False)
        top_15_districts_fig = px.bar(
            top_15_districts_df, x=top_15_districts_df.index, y=top_15_districts_df.values,
            labels={'district_clean':'District', VALUE_COL: 'Total Cases'}
        )
        st.plotly_chart(top_15_districts_fig, use_container_width=True)
with col4:
    if 'sector' in df.columns:
        st.subheader("Top Sectors by Cases Volume")
        top_sectors_df = df.groupby('sector')[VALUE_COL].sum().nlargest(15).sort_values(ascending=False)
        top_sector_fig = px.bar(
            top_sectors_df, x=top_sectors_df.index, y=top_sectors_df.values,
            labels={'sector': 'Sector', VALUE_COL: 'Total Cases'},
            
        )
        st.plotly_chart(top_sector_fig, use_container_width=True)

# Demographic Breakdown
st.subheader("Demographic Breakdown")
has_age = AGE_COL in df.columns and df[AGE_COL].notna().any()
has_gender = GENDER_COL in df.columns and df[GENDER_COL].notna().any()
if has_age and has_gender:
    demographics_df = df.groupby([AGE_COL, GENDER_COL])[VALUE_COL].sum().reset_index()
    demographics_fig = px.bar(
        demographics_df, x=AGE_COL, y=VALUE_COL, color=GENDER_COL, barmode='group', 
        title="Cases by Age Group and Gender",
        labels={AGE_COL: 'Age Group', VALUE_COL: 'Total Cases', GENDER_COL: 'Gender'}
    )
    st.plotly_chart(demographics_fig, use_container_width=True)
elif has_age:
    st.info(f"Gender breakdown is not available for the '{selected_dataset_name}' dataset.")
    age_df = df.groupby(AGE_COL)[VALUE_COL].sum().reset_index()
    age_fig = px.bar(
        age_df, x=AGE_COL, y=VALUE_COL, title="Cases by Age Group", 
        labels={AGE_COL: 'Age Group', VALUE_COL: 'Total Cases'}
    )
    st.plotly_chart(age_fig, use_container_width=True)
else:
    st.info(f"Demographic (age and gender) analysis is not available for the {selected_dataset_name} dataset.")

st.markdown("---")