import os
import requests
import pandas as pd
import sqlite3
from datetime import datetime
from pydantic import BaseModel, Field, ValidationError
import matplotlib.pyplot as plt
import seaborn as sns
import streamlit as st

# ==========================================
# 1. DATA VALIDATION ENGINE (Pydantic Model)
# ==========================================
class WeatherDataModel(BaseModel):
    city: str = Field(..., description="City name")
    temperature_celsius: float = Field(..., description="Temperature in Celsius")
    humidity: int = Field(..., ge=0, le=100, description="Humidity percentage")
    pressure: int = Field(..., ge=0, description="Atmospheric pressure in hPa")
    wind_speed: float = Field(..., ge=0.0, description="Wind speed in m/s")
    weather_description: str = Field(..., description="General weather status")
    timestamp: str = Field(..., description="ISO formatted extraction timestamp")


# ==========================================
# 2. ETL PIPELINE FUNCTIONS
# ==========================================
def extract_weather_data(cities: list, api_key: str) -> list:
    """Fetch raw weather JSON payloads from OpenWeatherMap API."""
    raw_data_list = []
    for city in cities:
        url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                raw_data_list.append(response.json())
            else:
                st.warning(f"Failed to fetch data for city: {city} (Status: {response.status_code})")
        except Exception as e:
            st.error(f"Error connecting to API for city {city}: {e}")
    return raw_data_list


def transform_and_validate_data(raw_data_list: list) -> pd.DataFrame:
    """Validate JSON payload using Pydantic and transform Kelvin to Celsius."""
    validated_records = []
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for raw_item in raw_data_list:
        try:
            city_name = raw_item.get("name", "Unknown")
            temp_kelvin = raw_item["main"]["temp"]
            temp_celsius = round(temp_kelvin - 273.15, 2)
            humidity_val = raw_item["main"]["humidity"]
            pressure_val = raw_item["main"]["pressure"]
            wind_spd = raw_item["wind"]["speed"]
            desc = raw_item["weather"][0]["description"].title()

            record_obj = WeatherDataModel(
                city=city_name,
                temperature_celsius=temp_celsius,
                humidity=humidity_val,
                pressure=pressure_val,
                wind_speed=wind_spd,
                weather_description=desc,
                timestamp=current_time
            )

            validated_records.append(record_obj.model_dump())

        except (ValidationError, KeyError) as err:
            st.warning(f"Data Validation error encountered for city record: {err}")
            continue

    df = pd.DataFrame(validated_records)
    return df


def load_data_to_storage(df: pd.DataFrame, db_name="weather_history.db", csv_name="cleaned_weather.csv"):
    """Persist cleaned records to SQLite Database and CSV file."""
    if df.empty:
        return

    conn = sqlite3.connect(db_name)
    df.to_sql("weather_records", conn, if_exists="append", index=False)
    conn.close()

    if not os.path.exists(csv_name):
        df.to_csv(csv_name, index=False)
    else:
        df.to_csv(csv_name, mode='a', header=False, index=False)


def fetch_historical_db_data(db_name="weather_history.db") -> pd.DataFrame:
    """Fetch stored historical records from SQLite Database."""
    if not os.path.exists(db_name):
        return pd.DataFrame()
    conn = sqlite3.connect(db_name)
    df_hist = pd.read_sql_query("SELECT * FROM weather_records", conn)
    conn.close()
    return df_hist


# ==========================================
# 3. STREAMLIT WEB DASHBOARD
# ==========================================
def main():
    st.set_page_config(page_title="Pakistan & Global Weather Pipeline", layout="wide")
    st.title("🌐 Real-Time Pakistan & Global Weather Insights Dashboard")
    st.markdown("Automated **ETL Data Pipeline** with Pydantic Validation, SQLite Persistence, and EDA.")

    # --- SESSION STATE FOR USER SPECIFIC PRIVACY ---
    if "user_searched_records" not in st.session_state:
        st.session_state.user_searched_records = pd.DataFrame()

    # Comprehensive Raw Cities List
    raw_cities = [
        # --- PAKISTAN (Districts & Major Cities) ---
        "Islamabad", "Lahore", "Karachi", "Peshawar", "Quetta", "Muzaffarabad", "Gilgit",
        "Faisalabad", "Rawalpindi", "Multan", "Gujranwala", "Sargodha", "Sialkot", "Bahawalpur",
        "Jhang", "Sheikhupura", "Gujrat", "Sahiwal", "Kasur", "Rahim Yar Khan", "Okara",
        "Wah Cantonment", "Dera Ghazi Khan", "Mirpur Khas", "Chiniot", "Hafizabad", "Mandi Bahauddin",
        "Attock", "Khanewal", "Jhelum", "Muzaffargarh", "Bahawalnagar", "Murree", "Chakwal",
        "Hyderabad", "Sukkur", "Larkana", "Nawabshah", "Kotri", "Shikarpur", "Jacobabad",
        "Khairpur", "Dadu", "Badin", "Thatta", "Ghotki", "Tando Adam", "Umerkot",
        "Mardan", "Mingora", "Kohat", "Abbottabad", "Dera Ismail Khan", "Nowshera", "Swabi",
        "Charsadda", "Mansehra", "Bannu", "Chitral", "Swat", "Dir",
        "Turbat", "Khuzdar", "Hub", "Chaman", "Gwadar", "Dera Murad Jamali", "Sibi", "Zhob",
        "Loralai", "Kalat", "Mirpur", "Rawalakot", "Kotli", "Bhimber", "Bagh", "Skardu", "Hunza",

        # --- INTERNATIONAL CITIES ---
        "New Delhi", "Mumbai", "Bangalore", "Kolkata", "Chennai", "Hyderabad", "Ahmedabad", "Jaipur", "Chandigarh", "Lucknow",
        "Riyadh", "Makkah", "Madinah", "Jeddah", "Dammam", "Dubai", "Abu Dhabi", "Sharjah",
        "New York", "Washington", "Los Angeles", "Chicago", "Houston", "Miami", "Toronto", "Vancouver", "Montreal",
        "London", "Manchester", "Birmingham", "Paris", "Berlin", "Rome", "Madrid", "Amsterdam", "Moscow", "Istanbul",
        "Beijing", "Shanghai", "Tokyo", "Osaka", "Seoul", "Bangkok", "Kuala Lumpur", "Singapore",
        "Sydney", "Melbourne", "Brisbane", "Cairo", "Cape Town", "Tehran", "Kabul"
    ]

    # Remove duplicates and SORT ALPHABETICALLY (A -> Z)
    sorted_cities = sorted(list(dict.fromkeys(raw_cities)))

    # Sidebar Configurations
    st.sidebar.header("Pipeline Configurations")
    api_key = "96df70f062038652685b4a200ede92cc"

    st.sidebar.markdown("🔍 **Search or Select Cities Below:**")
    selected_cities = st.sidebar.multiselect(
        "Type city name to search (Sorted A to Z):",
        options=sorted_cities,
        default=["Islamabad", "Karachi", "Lahore", "London", "New York"]
    )

    run_pipeline_btn = st.sidebar.button("Run ETL Pipeline 🚀")

    # Execution Trigger
    if run_pipeline_btn:
        if not api_key:
            st.sidebar.error("Please enter a valid OpenWeatherMap API Key!")
        elif not selected_cities:
            st.sidebar.error("Please select at least one city!")
        else:
            with st.spinner("Extracting, Validating, and Storing Data..."):
                raw_payloads = extract_weather_data(selected_cities, api_key)
                cleaned_df = transform_and_validate_data(raw_payloads)

                if not cleaned_df.empty:
                    # 1. Back-end SQLite Database mein record save karna (Master History)
                    load_data_to_storage(cleaned_df)
                    
                    # 2. User ki apni private screen session state ko update karna
                    if st.session_state.user_searched_records.empty:
                        st.session_state.user_searched_records = cleaned_df
                    else:
                        st.session_state.user_searched_records = pd.concat([cleaned_df, st.session_state.user_searched_records], ignore_index=True)

                    st.success(f"ETL Pipeline successfully processed and saved {len(cleaned_df)} city records!")
                else:
                    st.error("No valid weather records were processed.")

    st.markdown("---")
    st.header("📊 Exploratory Data Analysis & Personal Records")

    # --- 1. USER PERSONAL RECORD VIEW ---
    st.subheader("📋 Your Recent Searches (Private View)")
    
    if not st.session_state.user_searched_records.empty:
        st.dataframe(st.session_state.user_searched_records, use_container_width=True)
        
        # Clear Record Button for the User
        if st.button("🗑️️ Clear My Screen Records"):
            st.session_state.user_searched_records = pd.DataFrame()
            st.rerun()

        # Visualizations (EDA) for current user searches
        st.subheader("Visual Climate Analytics (Your Searched Data)")
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### Temperature Distribution by City (°C)")
            fig1, ax1 = plt.subplots(figsize=(10, 5))
            sns.barplot(data=st.session_state.user_searched_records.head(20), x="city", y="temperature_celsius", ax=ax1, palette="mako")
            plt.xticks(rotation=45, ha='right')
            plt.ylabel("Temperature (°C)")
            st.pyplot(fig1)

        with col2:
            st.markdown("#### Humidity Levels Across Target Cities (%)")
            fig2, ax2 = plt.subplots(figsize=(10, 5))
            sns.scatterplot(data=st.session_state.user_searched_records.head(20), x="temperature_celsius", y="humidity", hue="city", s=150, ax=ax2)
            plt.xlabel("Temperature (°C)")
            plt.ylabel("Humidity (%)")
            plt.xticks(rotation=45, ha='right')
            st.pyplot(fig2)

    else:
        st.info("No records on your screen right now. Select cities and click 'Run ETL Pipeline' to view your results.")


    # --- 2. ADMIN ACCESS PANEL (SIDEBAR & MAIN VIEW) ---
    st.sidebar.markdown("---")
    st.sidebar.header("🔒 Admin Panel")
    admin_password = st.sidebar.text_input("Enter Admin Password", type="password")

    # Aap apna password yahan change kar sakte hain (default rakha hai: 'ali123')
    if admin_password == "ali123":
        st.markdown("---")
        st.header("👑 Admin View: Master SQLite Database Records")
        st.warning("Admin Mode Active: Showing complete stored historical records across all user sessions.")
        
        df_historical = fetch_historical_db_data()
        
        if not df_historical.empty:
            st.dataframe(df_historical, use_container_width=True)
            st.markdown(f"**Total Records Stored in Master DB:** {len(df_historical)}")
        else:
            st.info("Database is currently empty.")


if __name__ == "__main__":
    main()