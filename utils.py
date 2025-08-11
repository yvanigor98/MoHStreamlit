import streamlit as st
import pandas as pd
import geopandas as gpd

def process_dataframe(df):
    """A helper function to process dates, handling potential errors."""
    # Convert year and month to a datetime object for proper sorting and plotting
    try:
        df['date'] = pd.to_datetime(df['year'].astype(str) + '-' + df['month'], format='%Y-%B')
    except Exception as e:
        st.error(f"Could not process the date columns. Please check your data. Error: {e}")
        df['date'] = pd.NaT # Set to Not a Time if conversion fails
    return df

@st.cache_data
def load_opd_data():
    """Loads and preprocesses the Malaria OPD data."""
    try:
        df = pd.read_csv('malaria_cases_opd_final.csv')
        df = process_dataframe(df)
        return df
    except FileNotFoundError:
        st.error("The data file 'malaria_cases_opd_final.csv' was not found.")
        return None

@st.cache_data
def load_chw_data():
    """Loads and preprocesses the Malaria Community Health Worker (CHW) data."""
    try:
        df = pd.read_csv('malaria_community_final.csv')
        df = process_dataframe(df)
        # Assuming the CHW data also has a 'Total' column, rename if different
        # For example: if the column is 'cases', use df.rename(columns={'cases': 'Total'}, inplace=True)
        return df
    except FileNotFoundError:
        st.error("The data file 'malaria_community_final.csv' was not found.")
        return None

@st.cache_data
def load_fever_data():
    """Loads and preprocesses the Fever Case data."""
    try:
        df = pd.read_csv('fever_cases_opd_final.csv')
        df = process_dataframe(df)
        return df
    except FileNotFoundError:
        st.error("The data file 'fever_cases_opd_final.csv' was not found.")
        return None
        
@st.cache_data
def load_geo_data():
    """Loads the geographic data for maps."""
    try:
        gdf = gpd.read_file('geoBoundaries-RWA-ADM2.geojson')
        return gdf
    except Exception as e:
        st.error(f"Error loading GeoJSON file: {e}")
        return None