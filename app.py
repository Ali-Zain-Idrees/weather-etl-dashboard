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
    user_name: str = Field(default="Guest_User", description="User identifier")
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


def transform_and_validate_data(raw_data_list: list, user_name: str) -> pd.DataFrame:
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
                user_name=user_name if user_name.strip() else "Guest_User",
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

    # --- ADVANCED DYNAMIC WEATHER ANIMATIONS (Clouds, Rain, Sun) ---
    st.markdown("""
        <style>
        .stApp {
            background: linear-gradient(to bottom, #09131d, #162436, #1d3557);
            color: #ffffff;
        }

        /* 1. MOVING CLOUDS ANIMATION */
        .cloud-1 {
            position: fixed;
            top: 5%;
            left: -200px;
            width: 220px;
            height: 65px;
            background: rgba(255, 255, 255, 0.15);
            border-radius: 50px;
            box-shadow: 35px 12px 0 12px rgba(255, 255, 255, 0.15);
            animation: moveClouds 30s linear infinite;
            z-index: 0;
            pointer-events: none;
        }

        .cloud-2 {
            position: fixed;
            top: 18%;
            left: -300px;
            width: 300px;
            height: 85px;
            background: rgba(255, 255, 255, 0.10);
            border-radius: 60px;
            box-shadow: 45px 18px 0 18px rgba(255, 255, 255, 0.10);
            animation: moveClouds 45s linear infinite 8s;
            z-index: 0;
            pointer-events: none;
        }

        @keyframes moveClouds {
            0% { left: -350px; }
            100% { left: 100vw; }
        }

        /* 2. RAIN ANIMATION EFFECT */
        .rain-drop-1 {
            position: fixed;
            top: -10%;
            left: 20%;
            width: 2px;
            height: 40px;
            background: rgba(200, 225, 255, 0.4);
            animation: fallRain 2s linear infinite;
            pointer-events: none;
        }

        .rain-drop-2 {
            position: fixed;
            top: -10%;
            left: 60%;
            width: 2px;
            height: 50px;
            background: rgba(200, 225, 255, 0.35);
            animation: fallRain 2.5s linear infinite 0.7s;
            pointer-events: none;
        }

        .rain-drop-3 {
            position: fixed;
            top: -10%;
            left: 80%;
            width: 2px;
            height: 35px;
            background: rgba(200, 225, 255, 0.3);
            animation: fallRain 1.8s linear infinite 1.2s;
            pointer-events: none;
        }

        @keyframes fallRain {
            0% { top: -10%; opacity: 1; }
            100% { top: 100%; opacity: 0.2; }
        }

        /* 3. GLOWING SUN EFFECT BEHIND CLOUDS */
        .sun-glow {
            position: fixed;
            top: 40px;
            right: 120px;
            width: 110px;
            height: 110px;
            background: radial-gradient(circle, rgba(255,223,0,0.8) 0%, rgba(255,165,0,0.2) 60%, rgba(0,0,0,0) 100%);
            border-radius: 50%;
            box-shadow: 0 0 50px rgba(255,223,0,0.5);
            pointer-events: none;
            z-index: 0;
            animation: pulseSun 4s ease-in-out infinite alternate;
        }

        @keyframes pulseSun {
            0% { transform: scale(0.95); opacity: 0.7; }
            100% { transform: scale(1.08); opacity: 1; }
        }
        </style>
        
        <div class="cloud-1"></div>
        <div class="cloud-2"></div>
        <div class="rain-drop-1"></div>
        <div class="rain-drop-2"></div>
        <div class="rain-drop-3"></div>
        <div class="sun-glow"></div>
    """, unsafe_allow_html=True)

    # --- SESSION STATES ---
    if "user_searched_records" not in st.session_state:
        st.session_state.user_searched_records = pd.DataFrame()

    if "selected_cities_list" not in st.session_state:
        st.session_state.selected_cities_list = ["Islamabad", "Karachi", "Lahore", "London", "New York"]

    if "user_logged_in" not in st.session_state:
        st.session_state.user_logged_in = False

    if "logged_user_email" not in st.session_state:
        st.session_state.logged_user_email = ""

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

    sorted_cities = sorted(list(dict.fromkeys(raw_cities)))
    api_key = "96df70f062038652685b4a200ede92cc"

    # ==========================================
    # SIDEBAR: PROFESSIONAL WEBSITE MENU
    # ==========================================
    st.sidebar.title("⚙️ Portal Navigation")

    # 1. ACCOUNT MANAGEMENT (SIGN UP / SIGN IN)
    st.sidebar.subheader("👤 Account Management")
    if not st.session_state.user_logged_in:
        auth_choice = st.sidebar.radio("Account Access:", ["Sign In", "Sign Up"])
        user_email = st.sidebar.text_input("Email Address:", placeholder="user@example.com")
        user_pass = st.sidebar.text_input("Password:", type="password")

        if auth_choice == "Sign Up":
            if st.sidebar.button("Create Account"):
                if user_email and user_pass:
                    st.session_state.user_logged_in = True
                    st.session_state.logged_user_email = user_email
                    st.sidebar.success("Account created successfully!")
                    st.rerun()
                else:
                    st.sidebar.error("Please fill all credentials.")
        else:
            if st.sidebar.button("Login"):
                if user_email:
                    st.session_state.user_logged_in = True
                    st.session_state.logged_user_email = user_email
                    st.sidebar.success("Logged in successfully!")
                    st.rerun()
                else:
                    st.sidebar.error("Enter valid email.")
    else:
        st.sidebar.info(f"Logged in as:\n**{st.session_state.logged_user_email}**")
        if st.sidebar.button("Sign Out"):
            st.session_state.user_logged_in = False
            st.session_state.logged_user_email = ""
            st.rerun()

    st.sidebar.markdown("---")

    # 2. APP SETTINGS & THEMES
    st.sidebar.subheader("🎨 Customization Settings")
    selected_theme = st.sidebar.selectbox("App Color Theme:", ["Dark Blue Storm", "Midnight Dark", "Sunny Blue"])
    zoom_level = st.sidebar.select_slider("Text Zoom Level:", options=["90%", "100%", "110%", "120%"], value="100%")

    st.sidebar.markdown("---")

    # 3. ADMIN PANEL
    st.sidebar.subheader("🔒 Admin Controls")
    admin_password = st.sidebar.text_input("Enter Admin Password", type="password")


    # ==========================================
    # MAIN CENTER PAGE (CHROME STYLE LAYOUT)
    # ==========================================
    st.title("🌐 Real-Time Pakistan & Global Weather Insights")
    st.markdown("Automated **ETL Data Pipeline** with Pydantic Validation, SQLite Persistence, and EDA.")

    st.markdown("<br>", unsafe_allow_html=True)

    # CENTER SECTION 1: NAME INPUT FIELD
    default_name_val = st.session_state.logged_user_email if st.session_state.user_logged_in else ""
    user_name_input = st.text_input("👤 Enter Your Name (Optional):", value=default_name_val, placeholder="e.g. Ali Zain Idrees")
    current_display_name = user_name_input.strip() if user_name_input.strip() else ("Guest_User" if not st.session_state.logged_user_email else st.session_state.logged_user_email)

    # CENTER SECTION 2: GOOGLE CHROME STYLE SEARCH BAR
    st.subheader("🔍 Search and Select Cities")
    
    searched_city = st.selectbox(
        "Search city from A-Z list:",
        options=["-- Type or Select City --"] + sorted_cities,
        index=0
    )

    if searched_city != "-- Type or Select City --" and searched_city not in st.session_state.selected_cities_list:
        st.session_state.selected_cities_list.append(searched_city)

    # CENTER SECTION 3: CONTAINER FOR SELECTED CITIES
    selected_cities = st.multiselect(
        "📦 Selected Cities Container:",
        options=st.session_state.selected_cities_list,
        default=st.session_state.selected_cities_list
    )
    st.session_state.selected_cities_list = selected_cities

    # ACTION BUTTON
    st.markdown("<br>", unsafe_allow_html=True)
    run_pipeline_btn = st.button("Show Weather 🌤️", use_container_width=True)

    # EXECUTION
    if run_pipeline_btn:
        if not selected_cities:
            st.error("Please select at least one city in the container!")
        else:
            with st.spinner("Fetching Weather Data..."):
                raw_payloads = extract_weather_data(selected_cities, api_key)
                cleaned_df = transform_and_validate_data(raw_payloads, current_display_name)

                if not cleaned_df.empty:
                    load_data_to_storage(cleaned_df)
                    
                    if st.session_state.user_searched_records.empty:
                        st.session_state.user_searched_records = cleaned_df
                    else:
                        st.session_state.user_searched_records = pd.concat([cleaned_df, st.session_state.user_searched_records], ignore_index=True)

                    st.success(f"Weather Insights successfully fetched for {len(cleaned_df)} cities!")
                else:
                    st.error("No valid weather records were processed.")

    st.markdown("---")

    # DISPLAY RECORDS AND ANALYTICS
    st.header("📊 Exploratory Data Analysis & Personal Records")
    st.subheader(f"📋 Recent Weather Records for: {current_display_name}")
    
    if not st.session_state.user_searched_records.empty:
        st.dataframe(st.session_state.user_searched_records, use_container_width=True)
        
        if st.button("🗑️ Clear My Screen Records"):
            st.session_state.user_searched_records = pd.DataFrame()
            st.rerun()

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
        st.info("No records on your screen right now. Select cities and click 'Show Weather 🌤️' to view your results.")

    # ADMIN VIEW
    if admin_password == "ali123":
        st.markdown("---")
        st.header("👑 Admin View: User-Wise Categorized Records")
        st.warning("Admin Mode Active: Displaying records grouped by individual user profiles.")
        
        df_historical = fetch_historical_db_data()
        
        if not df_historical.empty:
            if "user_name" in df_historical.columns:
                unique_users = df_historical["user_name"].unique()
                for user in unique_users:
                    user_df = df_historical[df_historical["user_name"] == user]
                    with st.expander(f"👤 User Record: {user} ({len(user_df)} Entries)", expanded=True):
                        st.dataframe(user_df, use_container_width=True)
            else:
                st.dataframe(df_historical, use_container_width=True)
                
            st.markdown(f"**Total Records Stored Across All Users:** {len(df_historical)}")
        else:
            st.info("Database is currently empty.")


if __name__ == "__main__":
    main()