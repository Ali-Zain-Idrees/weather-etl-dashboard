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


def delete_user_data_from_db(user_name: str, db_name="weather_history.db", csv_name="cleaned_weather.csv"):
    """Permanently delete specific user records from SQLite and CSV."""
    if os.path.exists(db_name):
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM weather_records WHERE user_name = ?", (user_name,))
        conn.commit()
        conn.close()

    if os.path.exists(csv_name):
        try:
            df_csv = pd.read_csv(csv_name)
            df_csv = df_csv[df_csv["user_name"] != user_name]
            df_csv.to_csv(csv_name, index=False)
        except Exception:
            pass


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

    if "user_avatar" not in st.session_state:
        st.session_state.user_avatar = "👤"

    if "stored_profiles" not in st.session_state:
        st.session_state.stored_profiles = {}

    if "active_view" not in st.session_state:
        st.session_state.active_view = "main"

    if "app_theme" not in st.session_state:
        st.session_state.app_theme = "Dark Cosmic Blue"

    # --- DYNAMIC THEME APPLIER ---
    if st.session_state.app_theme == "Sunny Day Blue":
        bg_style = "linear-gradient(to bottom, #1e3c72, #2a5298, #4a90e2);"
        text_color = "#ffffff"
    elif st.session_state.app_theme == "Slate Grey Professional":
        bg_style = "linear-gradient(to bottom, #111827, #1f2937, #374151);"
        text_color = "#f9fafb"
    else:  # Dark Cosmic Blue
        bg_style = "linear-gradient(to bottom, #09131d, #162436, #1d3557);"
        text_color = "#ffffff"

    st.markdown(f"""
        <style>
        .stApp {{
            background: {bg_style};
            color: {text_color};
        }}

        /* MOVING CLOUDS ANIMATION */
        .cloud-1 {{
            position: fixed;
            top: 5%;
            left: -200px;
            width: 220px;
            height: 65px;
            background: rgba(255, 255, 255, 0.12);
            border-radius: 50px;
            box-shadow: 35px 12px 0 12px rgba(255, 255, 255, 0.12);
            animation: moveClouds 30s linear infinite;
            z-index: 0;
            pointer-events: none;
        }}

        .cloud-2 {{
            position: fixed;
            top: 18%;
            left: -300px;
            width: 300px;
            height: 85px;
            background: rgba(255, 255, 255, 0.08);
            border-radius: 60px;
            box-shadow: 45px 18px 0 18px rgba(255, 255, 255, 0.08);
            animation: moveClouds 45s linear infinite 8s;
            z-index: 0;
            pointer-events: none;
        }}

        @keyframes moveClouds {{
            0% {{ left: -350px; }}
            100% {{ left: 100vw; }}
        }}

        /* SUN GLOW EFFECT */
        .sun-glow {{
            position: fixed;
            top: 40px;
            right: 120px;
            width: 100px;
            height: 100px;
            background: radial-gradient(circle, rgba(255,223,0,0.7) 0%, rgba(255,165,0,0.15) 60%, rgba(0,0,0,0) 100%);
            border-radius: 50%;
            box-shadow: 0 0 45px rgba(255,223,0,0.4);
            pointer-events: none;
            z-index: 0;
        }}
        </style>
        
        <div class="cloud-1"></div>
        <div class="cloud-2"></div>
        <div class="sun-glow"></div>
    """, unsafe_allow_html=True)

    # Raw Cities List
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
    # TOP HEADER NAVIGATION BAR (Chrome Style)
    # ==========================================
    header_col1, header_col2, header_col3, header_col4, header_col5 = st.columns([4, 1.3, 1.3, 1.1, 0.5])

    with header_col1:
        st.markdown("### 🌤️ **Weather Insights**")

    with header_col2:
        if st.button("📥 Install App", key="install_btn"):
            st.info("💡 **Windows Desktop Installation:** Click the **3 dots ⋮** at top right of Chrome -> Select **'Save and share'** -> Click **'Install Weather Insights'** to run as a native desktop app!")

    with header_col3:
        current_user_display = st.session_state.logged_user_email.split('@')[0] if st.session_state.user_logged_in else "Guest"
        account_label = f"{st.session_state.user_avatar} {current_user_display}"
        account_popover = st.popover(account_label)
        
        with account_popover:
            st.markdown("#### **Weather Insights Account**")
            
            if not st.session_state.user_logged_in:
                st.info("Sign in to sync your search history.")
                user_email_input = st.text_input("Email Address", placeholder="user@example.com")
                user_pass_input = st.text_input("Password", type="password")
                
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button("Sign In"):
                        if user_email_input:
                            st.session_state.user_logged_in = True
                            st.session_state.logged_user_email = user_email_input
                            st.session_state.stored_profiles[user_email_input] = user_pass_input
                            st.rerun()
                with col_b:
                    if st.button("Sign Up"):
                        if user_email_input:
                            st.session_state.user_logged_in = True
                            st.session_state.logged_user_email = user_email_input
                            st.session_state.stored_profiles[user_email_input] = user_pass_input
                            st.rerun()
            else:
                st.success(f"Logged in as: **{st.session_state.logged_user_email}**")
                
                with st.expander("⚙️ Manage Your Weather Insights Account"):
                    new_email = st.text_input("Update Email", value=st.session_state.logged_user_email)
                    if st.button("Save Profile Settings"):
                        st.session_state.logged_user_email = new_email
                        st.toast("Profile details saved!", icon="✅")
                        st.rerun()

                with st.expander("🎨 Customize Profile"):
                    chosen_avatar = st.selectbox("Choose Profile Avatar:", ["👤", "🌤️", "⚡", "👨‍‍💻", "🦅", "🔥"])
                    chosen_theme = st.selectbox("Select Theme:", ["Dark Cosmic Blue", "Sunny Day Blue", "Slate Grey Professional"])
                    if st.button("Apply Theme & Avatar"):
                        st.session_state.user_avatar = chosen_avatar
                        st.session_state.app_theme = chosen_theme
                        st.toast("Theme and Avatar Updated!", icon="🎨")
                        st.rerun()

                if st.button("👥 Open Guest Profile"):
                    st.session_state.user_logged_in = False
                    st.session_state.logged_user_email = "Guest_User"
                    st.toast("Switched to clean Guest Profile!", icon="👤")
                    st.rerun()

                with st.expander("🛠️ Manage Profiles (Switch / Remove)"):
                    if st.session_state.stored_profiles:
                        st.write("**Stored Accounts:**")
                        for prof_email in list(st.session_state.stored_profiles.keys()):
                            p_col1, p_col2 = st.columns([2, 1])
                            p_col1.write(prof_email)
                            if p_col2.button("Switch", key=f"switch_{prof_email}"):
                                st.session_state.logged_user_email = prof_email
                                st.session_state.user_logged_in = True
                                st.rerun()
                    else:
                        st.caption("No other accounts registered.")

                st.markdown("---")
                if st.button("🚪 Sign Out of Weather Insights"):
                    st.session_state.user_logged_in = False
                    st.session_state.logged_user_email = ""
                    st.rerun()

    with header_col4:
        # Three Dots "⋮" Menu
        menu_popover = st.popover("⋮ Menu")
        with menu_popover:
            st.markdown("#### **Browser Navigation**")
            if st.button("📜 History"):
                st.session_state.active_view = "history"
                st.rerun()
            if st.button("📥 Downloads / Export Data"):
                st.session_state.active_view = "downloads"
                st.rerun()
            if st.button("🏠 Main Dashboard"):
                st.session_state.active_view = "main"
                st.rerun()
            st.markdown("---")

            # ----------------------------------------------------
            # DUAL / TRIPLE DELETE & BACKUP OPTIONS POPUP
            # ----------------------------------------------------
            with st.expander("🗑️️ Delete & Backup Data Controls"):
                st.caption("Choose how you want to handle your data:")
                
                # OPTION 1: Temporary Remove (Default Behavior)
                if st.button("🧹 Clear Screen Data (Temporary)"):
                    st.session_state.user_searched_records = pd.DataFrame()
                    st.toast("Screen view cleared! Server data remains untouched.", icon="🧹")
                    st.rerun()

                # OPTION 2: Restore / Backup Data
                if st.button("🔄 Restore / Backup Data to Screen"):
                    df_historical = fetch_historical_db_data()
                    if not df_historical.empty:
                        curr_user = st.session_state.logged_user_email if st.session_state.user_logged_in else "Guest_User"
                        if "user_name" in df_historical.columns:
                            filtered_user_df = df_historical[df_historical["user_name"] == curr_user]
                            if not filtered_user_df.empty:
                                st.session_state.user_searched_records = filtered_user_df
                            else:
                                st.session_state.user_searched_records = df_historical
                        else:
                            st.session_state.user_searched_records = df_historical
                        st.toast("Backup data successfully restored to screen!", icon="🔄")
                        st.rerun()
                    else:
                        st.warning("No backup data available in database.")

                # OPTION 3: Permanent Delete (Admin Only Guard)
                st.markdown("---")
                st.markdown("**🔥 Permanent Database Deletion**")
                admin_del_pass = st.text_input("Enter Admin Password for Permanent Delete:", type="password", key="perm_del_pass")
                if st.button("🔥 Delete Permanently From Server"):
                    if admin_del_pass == "ali123":
                        delete_all_data_from_db()
                        st.session_state.user_searched_records = pd.DataFrame()
                        st.success("All data permanently deleted from server database!")
                        st.rerun()
                    else:
                        st.error("Incorrect Admin Password! Permanent deletion denied.")

    with header_col5:
        st.markdown("⭐")

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
        st.header("📜 Weather Insights - Search History")
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
        st.header("📥 Weather Insights - Downloads & Export")
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
        st.header("👑 Admin Panel: Database Management & Permanent Delete")
        st.warning("Admin Access Granted: Perform permanent server deletions and manage all user records.")

        df_historical = fetch_historical_db_data()

        if not df_historical.empty and "user_name" in df_historical.columns:
            all_users = list(df_historical["user_name"].unique())

            st.subheader("🗑️ Permanently Delete Specific User Data from Database")
            selected_user_to_delete = st.selectbox("Select User Profile to Delete:", options=["-- Select User --"] + all_users)

            col_del1, col_del2 = st.columns([2, 2])
            with col_del1:
                if st.button(f"🔥 Permanently Delete Data for '{selected_user_to_delete}'"):
                    if selected_user_to_delete != "-- Select User --":
                        delete_user_data_from_db(selected_user_to_delete)
                        st.success(f"Data for user '{selected_user_to_delete}' permanently purged from server database!")
                        st.rerun()
                    else:
                        st.error("Please select a valid user to delete.")

            with col_del2:
                if st.button("💥 PERMANENTLY DELETE ALL DATABASE RECORDS"):
                    delete_all_data_from_db()
                    st.success("All database records cleared permanently!")
                    st.rerun()

            st.markdown("---")
            st.subheader("📋 Stored Database Records by User Profile")
            for user in all_users:
                user_df = df_historical[user_historical["user_name"] == user] if "user_name" in df_historical.columns else df_historical
                with st.expander(f"👤 User Profile: {user} ({len(user_df)} Entries)", expanded=True):
                    st.dataframe(user_df, use_container_width=True)
        else:
            st.info("Database is currently empty.")


if __name__ == "__main__":
    main()