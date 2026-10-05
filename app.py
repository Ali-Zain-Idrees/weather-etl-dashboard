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
# 2. ETL PIPELINE & DATABASE FUNCTIONS
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

    return pd.DataFrame(validated_records)


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
    try:
        df_hist = pd.read_sql_query("SELECT * FROM weather_records", conn)
    except Exception:
        df_hist = pd.DataFrame()
    conn.close()
    return df_hist


def delete_all_data_from_db(db_name="weather_history.db", csv_name="cleaned_weather.csv"):
    """Permanently clear all database records from server."""
    if os.path.exists(db_name):
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM weather_records")
        conn.commit()
        conn.close()

    if os.path.exists(csv_name):
        pd.DataFrame().to_csv(csv_name, index=False)


# ==========================================
# 3. STREAMLIT WEB DASHBOARD
# ==========================================
def main():
    st.set_page_config(page_title="Weather Insights", layout="wide", initial_sidebar_state="collapsed")

    # --- SESSION STATES ---
    if "user_searched_records" not in st.session_state:
        st.session_state.user_searched_records = pd.DataFrame()

    if "selected_cities_list" not in st.session_state:
        st.session_state.selected_cities_list = ["Islamabad", "Karachi", "Lahore", "London", "New York"]

    if "user_logged_in" not in st.session_state:
        st.session_state.user_logged_in = False

    if "logged_user_email" not in st.session_state:
        st.session_state.logged_user_email = ""

    if "stored_profiles" not in st.session_state:
        st.session_state.stored_profiles = {}

    if "active_view" not in st.session_state:
        st.session_state.active_view = "main"

    if "app_theme" not in st.session_state:
        st.session_state.app_theme = "Dark Cosmic Blue"

    # --- THEME STYLING ---
    if st.session_state.app_theme == "Sunny Day Blue":
        bg_style = "linear-gradient(to bottom, #1e3c72, #2a5298, #4a90e2);"
        text_color = "#ffffff"
    elif st.session_state.app_theme == "Slate Grey Professional":
        bg_style = "linear-gradient(to bottom, #111827, #1f2937, #374151);"
        text_color = "#f9fafb"
    else:  # Dark Cosmic Blue
        bg_style = "linear-gradient(to bottom, #09131d, #162436, #1d3557);"
        text_color = "#ffffff"

    # --- ORIGINAL STYLING WITH ONLY 5PX RIGHT ALIGNMENT FOR BUTTONS ---
    st.markdown(f"""
        <style>
        .stApp {{
            background: {bg_style};
            color: {text_color};
        }}

        /* MOVE ONLY THE ACCOUNT & THREE DOTS BUTTONS CONTAINER TO 5PX FROM RIGHT */
        div[data-testid="stHorizontalBlock"]:has(div[data-testid="stPopover"]) {{
            position: absolute !important;
            right: 5px !important;
            top: 0px !important;
            z-index: 999999 !important;
        }}

        /* SUN GLOW EFFECT */
        .sun-glow {{
            position: fixed;
            top: 40px;
            right: 35%;
            width: 100px;
            height: 100px;
            background: radial-gradient(circle, rgba(255,223,0,0.6) 0%, rgba(255,165,0,0.1) 60%, rgba(0,0,0,0) 100%);
            border-radius: 50%;
            box-shadow: 0 0 45px rgba(255,223,0,0.3);
            pointer-events: none;
            z-index: 0;
        }}
        </style>
        
        <div class="sun-glow"></div>
    """, unsafe_allow_html=True)

    raw_cities = [
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
        "New Delhi", "Mumbai", "Bangalore", "Dubai", "Abu Dhabi", "New York", "London", "Paris", "Tokyo", "Sydney"
    ]

    sorted_cities = sorted(list(dict.fromkeys(raw_cities)))
    api_key = "96df70f062038652685b4a200ede92cc"

    # ==========================================
    # HEADER CONTROLS (Avatar + Three Dots)
    # ==========================================
    h_col_left, h_col_avatar, h_col_menu = st.columns([10, 0.5, 0.5])

    with h_col_left:
        st.markdown("### 🌤️ **Weather Insights**")

    # ICON 1: ACCOUNT AVATAR ICON
    with h_col_avatar:
        if st.session_state.user_logged_in and st.session_state.logged_user_email:
            avatar_letter = st.session_state.logged_user_email[0].upper()
        else:
            avatar_letter = "G"

        account_popover = st.popover(avatar_letter)
        
        with account_popover:
            st.markdown("#### **Account Settings**")
            
            if not st.session_state.user_logged_in:
                tab_signin, tab_signup = st.tabs(["🔑 Sign In", "📝 Sign Up"])

                with tab_signin:
                    if st.session_state.stored_profiles:
                        st.caption("Select from previously registered emails:")
                        selected_saved_email = st.selectbox("Saved Email Accounts:", options=list(st.session_state.stored_profiles.keys()))
                        saved_pass_input = st.text_input("Password", type="password", key="saved_pass")
                        if st.button("Sign In with Saved Account"):
                            if saved_pass_input == st.session_state.stored_profiles.get(selected_saved_email):
                                st.session_state.user_logged_in = True
                                st.session_state.logged_user_email = selected_saved_email
                                st.toast(f"Welcome back, {selected_saved_email}!", icon="✅")
                                st.rerun()
                            else:
                                st.error("Incorrect password!")
                    else:
                        st.info("No saved accounts found. Please Sign Up first.")
                        user_email_input = st.text_input("Email Address", placeholder="user@example.com", key="login_email")
                        user_pass_input = st.text_input("Password", type="password", key="login_pass")
                        if st.button("Sign In"):
                            if user_email_input:
                                st.session_state.user_logged_in = True
                                st.session_state.logged_user_email = user_email_input
                                st.session_state.stored_profiles[user_email_input] = user_pass_input
                                st.rerun()

                with tab_signup:
                    new_user_email = st.text_input("Enter Email for New Account", placeholder="newuser@example.com", key="signup_email")
                    new_user_pass = st.text_input("Create Password", type="password", key="signup_pass")
                    if st.button("Create Account & Sign In"):
                        if new_user_email and new_user_pass:
                            st.session_state.stored_profiles[new_user_email] = new_user_pass
                            st.session_state.user_logged_in = True
                            st.session_state.logged_user_email = new_user_email
                            st.success("Account registered and signed in successfully!")
                            st.rerun()
                        else:
                            st.error("Please enter email and password.")

            else:
                st.success(f"Logged in as: **{st.session_state.logged_user_email}**")
                
                with st.expander("⚙️ Profile Settings"):
                    new_email = st.text_input("Update Email", value=st.session_state.logged_user_email)
                    if st.button("Save Profile"):
                        st.session_state.logged_user_email = new_email
                        st.toast("Profile updated!", icon="✅")
                        st.rerun()

                with st.expander("🎨 App Theme"):
                    chosen_theme = st.selectbox("Select Theme:", ["Dark Cosmic Blue", "Sunny Day Blue", "Slate Grey Professional"])
                    if st.button("Apply Theme"):
                        st.session_state.app_theme = chosen_theme
                        st.toast("Theme updated!", icon="🎨")
                        st.rerun()

                st.markdown("---")
                if st.button("🚪 Sign Out"):
                    st.session_state.user_logged_in = False
                    st.session_state.logged_user_email = ""
                    st.rerun()

    # ICON 2: THREE DOTS MENU (⋮)
    with h_col_menu:
        menu_popover = st.popover("⋮")
        with menu_popover:
            st.markdown("#### **Menu**")
            
            if st.button("📥 Install App"):
                st.info("💡 Click 3 dots ⋮ on your browser -> 'Save and share' -> 'Install Weather Insights'.")
                
            st.markdown("---")
            if st.button("🏠 Main Dashboard"):
                st.session_state.active_view = "main"
                st.rerun()
            if st.button("📜 History"):
                st.session_state.active_view = "history"
                st.rerun()
            if st.button("📥 Downloads"):
                st.session_state.active_view = "downloads"
                st.rerun()
            
            st.markdown("---")

            if st.button("🗑 Delete Browsing Data"):
                st.session_state.user_searched_records = pd.DataFrame()
                st.toast("Browsing data cleared from screen!", icon="🧹")
                st.rerun()

    st.markdown("---")

    # ==========================================
    # SIDEBAR: ADMIN PANEL
    # ==========================================
    st.sidebar.title("🔒 Security & Admin Panel")
    admin_password = st.sidebar.text_input("Enter Admin Password", type="password")

    # ==========================================
    # VIEW ROUTING
    # ==========================================

    # --- VIEW 1: HISTORY TAB ---
    if st.session_state.active_view == "history":
        st.header("📜 Search History")
        st.caption("All historical weather queries logged across sessions.")
        
        df_historical = fetch_historical_db_data()
        if not df_historical.empty:
            st.dataframe(df_historical, use_container_width=True)
        else:
            st.info("No historical searches found in database.")
            
        if st.button("⬅️ Back to Main Dashboard"):
            st.session_state.active_view = "main"
            st.rerun()

    # --- VIEW 2: DOWNLOADS TAB ---
    elif st.session_state.active_view == "downloads":
        st.header("📥 Downloads & Data Export")
        st.caption("Export search records into clean CSV format.")
        
        if not st.session_state.user_searched_records.empty:
            csv_data = st.session_state.user_searched_records.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Current Session CSV",
                data=csv_data,
                file_name=f"weather_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
            st.dataframe(st.session_state.user_searched_records, use_container_width=True)
        else:
            st.info("No active records available on screen to download.")
            
        if st.button("⬅️ Back to Main Dashboard"):
            st.session_state.active_view = "main"
            st.rerun()

    # --- VIEW 3: MAIN DASHBOARD VIEW ---
    else:
        st.title("🌐 Real-Time Pakistan & Global Weather Insights")
        st.markdown("Automated **ETL Data Pipeline** with Pydantic Validation, SQLite Persistence, and EDA.")

        st.markdown("<br>", unsafe_allow_html=True)

        # CENTER SECTION 1: USER NAME
        default_name_val = st.session_state.logged_user_email if st.session_state.user_logged_in else ""
        user_name_input = st.text_input("👤 Enter Your Name (Optional):", value=default_name_val, placeholder="e.g. Ali Zain Idrees")
        current_display_name = user_name_input.strip() if user_name_input.strip() else ("Guest_User" if not st.session_state.logged_user_email else st.session_state.logged_user_email)

        # CENTER SECTION 2: SEARCH BAR
        st.subheader("🔍 Search and Select Cities")
        searched_city = st.selectbox(
            "Search city from A-Z list:",
            options=["-- Type or Select City --"] + sorted_cities,
            index=0
        )

        if searched_city != "-- Type or Select City --" and searched_city not in st.session_state.selected_cities_list:
            st.session_state.selected_cities_list.append(searched_city)

        # CENTER SECTION 3: SELECTED CONTAINER
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

        # DISPLAY EDA & DATA
        st.header("📊 Exploratory Data Analysis & Personal Records")
        st.subheader(f"📋 Recent Weather Records for: {current_display_name}")
        
        if not st.session_state.user_searched_records.empty:
            st.dataframe(st.session_state.user_searched_records, use_container_width=True)
            
            if st.button("🗑 Clear My Screen Records"):
                st.session_state.user_searched_records = pd.DataFrame()
                st.rerun()

            st.subheader("Visual Climate Analytics")
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

    # ==========================================
    # ADMIN PANEL VIEW
    # ==========================================
    if admin_password == "ali123":
        st.markdown("---")
        st.header("👑 Admin Panel: Database & Backup Management")
        st.warning("Admin Access Granted")

        col_adm1, col_adm2 = st.columns(2)
        
        with col_adm1:
            if st.button("🔄 Restore All Database Backup to Screen"):
                df_historical = fetch_historical_db_data()
                if not df_historical.empty:
                    st.session_state.user_searched_records = df_historical
                    st.success("All historical database records restored to screen!")
                    st.rerun()
                else:
                    st.warning("No records in database to restore.")

        with col_adm2:
            if st.button("🔥 Permanently Purge All Server Data"):
                delete_all_data_from_db()
                st.session_state.user_searched_records = pd.DataFrame()
                st.success("Server database and CSV records permanently deleted!")
                st.rerun()


if __name__ == "__main__":
    main()