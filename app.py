import streamlit as st
import pandas as pd
import geopandas as gpd
import plotly.express as px

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
        # Standardize date columns
        df_raw['date'] = pd.to_datetime(df_raw['year'].astype(str) + '-' + df_raw['month'], format='%Y-%B')
        df_raw['source'] = source_name
        return df_raw

    # --- Load Datasets ---
    try:
        df_opd = preprocess_df(pd.read_csv('malaria_cases_opd_final(in).csv'), 'OPD')
        df_chw = preprocess_df(pd.read_csv('malaria_community_final.csv'), 'CHWs')
        df_fever = preprocess_df(pd.read_csv('fever_cases_opd_final.csv'), 'Fever Cases')
    except FileNotFoundError as e:
        st.error(f"Error: A data file could not be found. Please check file names. Missing file: {e.filename}")
        return None, None

    # --- Load Geographic Data ---
    try:
        gdf_districts = gpd.read_file('geoBoundaries-RWA-ADM2.geojson')
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
    st.stop() # Stop execution if data loading failed


# =======================
# Sidebar and Filters
# =======================
st.sidebar.title("Dashboard Controls")

# --- Dataset Selector ---
selected_dataset_name = st.sidebar.selectbox(
    "Select a Dataset to View",
    options=list(datasets.keys())
)

# --- Get the selected dataframe ---
df = datasets[selected_dataset_name].copy()

st.sidebar.markdown("---")
st.sidebar.header("Data Filters")

# --- Dynamic Filters based on selected dataset ---
# -- District Filter --
district_list = ['All Districts'] + sorted(df['district_clean'].unique())
selected_district = st.sidebar.selectbox("Select District", options=district_list)

# -- Year Filter --
year_list = ['All Years'] + sorted(df['year'].unique(), reverse=True)
selected_year = st.sidebar.selectbox("Select Year", options=year_list)

# -- Dynamic Month Filter --
month_order = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
if selected_year and selected_year != 'All Years':
    months_in_year = sorted(df[df['year'] == selected_year]['month'].unique(), key=lambda m: month_order.index(m))
    available_months = ['All Months'] + months_in_year
else:
    # Use all unique months present in the data, sorted chronologically
    all_months_in_data = sorted(df['month'].unique(), key=lambda m: month_order.index(m))
    available_months = ['All Months'] + all_months_in_data
selected_month = st.sidebar.selectbox("Select Month", options=available_months)


# =======================
# Main Page Layout
# =======================
st.title(f"{selected_dataset_name} Analysis")
st.markdown("Use the filters on the left to analyze the data for a specific area or time period.")
st.markdown("---")

# --- IMPORTANT: Define column names ---
# Adjust these if your column names differ between datasets
VALUE_COL = 'Total'
AGE_COL = 'age_category_new'
GENDER_COL = 'gender'

# --- Filter Data based on selections ---
if selected_district != 'All Districts':
    df = df[df['district_clean'] == selected_district]
if selected_year != 'All Years':
    df = df[df['year'] == selected_year]
if selected_month != 'All Months':
    df = df[df['month'] == selected_month]

# Check if the main value column exists
if VALUE_COL not in df.columns:
    st.error(f"The selected dataset does not contain the required value column: '{VALUE_COL}'. Please check the data or column name definitions in the script.")
    st.stop()
    
# =======================
# Display KPI Section
# =======================
# Calculate KPIs
total_cases = df[VALUE_COL].sum()
active_districts = df[df[VALUE_COL] > 0]['district_clean'].nunique()

# Top district
top_district_row = (
    df.groupby('district_clean')[VALUE_COL]
    .sum()
    .reset_index()
    .sort_values(VALUE_COL, ascending=False)
    .head(1)
)
top_district = top_district_row['district_clean'].iloc[0] if not top_district_row.empty else "N/A"

# Top sector
if 'sector' in df.columns:
    top_sector_row = (
        df.groupby('sector')[VALUE_COL]
        .sum()
        .reset_index()
        .sort_values(VALUE_COL, ascending=False)
        .head(1)
    )
    top_sector = top_sector_row['sector'].iloc[0] if not top_sector_row.empty else "N/A"
else:
    top_sector = "N/A"

# Display KPIs in columns
kpi1, kpi2, kpi3, kpi4 = st.columns(4)
kpi1.metric(label="Total cases", value=f"{total_cases:,.0f}")
kpi2.metric(label="Active districts", value=active_districts)
kpi3.metric(label="Top district", value=top_district)
kpi4.metric(label="Top sector", value=top_sector)

st.markdown("---")


# --- Layout for Charts ---
col1, col2 = st.columns(2)

with col1:
    # --- MAP CHART (CHOROPLETH) ---
    st.subheader("Total Cases by District")
    district_cases = df.groupby('district_clean')[VALUE_COL].sum().reset_index()
    merged_gdf = gdf_districts.merge(district_cases, left_on='shapeName', right_on='district_clean', how='left').fillna(0)
    map_fig = px.choropleth_mapbox(merged_gdf, geojson=merged_gdf.geometry, locations=merged_gdf.index, color=VALUE_COL,
                                 hover_name="shapeName", hover_data={VALUE_COL: ":,.0f"}, color_continuous_scale="Blues",
                                 mapbox_style="carto-positron", zoom=7.3, center={"lat": -1.94, "lon": 29.87}, opacity=0.7,
                                 labels={VALUE_COL: 'Total Cases'})
    map_fig.update_layout(margin={"r":0, "t":0, "l":0, "b":0})
    st.plotly_chart(map_fig, use_container_width=True)

with col2:
    # --- LINE CHART (Monthly Trend) ---
    st.subheader("Monthly Cases Trend")
    line_df = df.groupby('date')[VALUE_COL].sum().reset_index().sort_values('date')
    line_fig = px.line(line_df, x='date', y=VALUE_COL, title="Monthly Trend", markers=True)
    line_fig.update_layout(xaxis_title='Month-Year', yaxis_title='Total Cases')
    st.plotly_chart(line_fig, use_container_width=True)

# =======================
# Top Sectors Chart
# =======================
if 'sector' in df.columns:
    st.subheader("Top Sectors by Cases")
    top_sectors_df = (
        df.groupby('sector')[VALUE_COL]
        .sum()
        .reset_index()
        .sort_values(VALUE_COL, ascending=False)
        .head(10)  # Top 10 sectors
    )
    top_sector_fig = px.bar(
        top_sectors_df,
        x='sector',
        y=VALUE_COL,
        title="Top Sectors by Total Cases",
        labels={'sector': 'Sector', VALUE_COL: 'Total Cases'},
    )
    st.plotly_chart(top_sector_fig, use_container_width=True)


# --- Second row of charts (conditionally displayed) ---
st.markdown("---")
st.subheader("Demographic Breakdown")
col3, col4 = st.columns(2)

with col3:
    # --- BAR CHART (Age) ---
    if AGE_COL in df.columns:
        bar_df = df.groupby(AGE_COL)[VALUE_COL].sum().reset_index()
        bar_fig = px.bar(bar_df, x=AGE_COL, y=VALUE_COL, title="Cases by Age Group", labels={AGE_COL: 'Age Group', VALUE_COL: 'Total Cases'})
        st.plotly_chart(bar_fig, use_container_width=True)
    else:
        st.info(f"Age breakdown analysis is not available for the '{selected_dataset_name}' dataset.")

with col4:
    # --- PIE CHART (Gender) ---
    if GENDER_COL in df.columns:
        pie_df = df.groupby(GENDER_COL)[VALUE_COL].sum().reset_index()
        pie_fig = px.pie(pie_df, names=GENDER_COL, values=VALUE_COL, title="Cases by Gender", hole=0.3)
        st.plotly_chart(pie_fig, use_container_width=True)
    else:
        st.info(f"Gender breakdown analysis is not available for the '{selected_dataset_name}' dataset.")
