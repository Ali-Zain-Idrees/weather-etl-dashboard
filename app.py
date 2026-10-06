import os
import random
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
    if os.path.exists(db_name):
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM weather_records")
        conn.commit()
        conn.close()

    if os.path.exists(csv_name):
        pd.DataFrame().to_csv(csv_name, index=False)


# ==========================================
# 3. WELCOME MODAL DIALOG
# ==========================================
@st.dialog("👋 Welcome to Weather Insights")
def welcome_auth_modal():
    st.markdown("Please **Sign In**, **Sign Up**, or continue as a guest to proceed.")
    tab_signin, tab_signup = st.tabs(["🔑 Sign In", "📝 Sign Up"])

    with tab_signin:
        if st.session_state.stored_profiles:
            st.caption("Select from previously saved accounts:")
            selected_email = st.selectbox("Saved Accounts:", options=list(st.session_state.stored_profiles.keys()), key="modal_saved_email")
            
            if st.button("Sign In with Selected Account", use_container_width=True):
                user_info = st.session_state.stored_profiles.get(selected_email, {})
                st.session_state.user_logged_in = True
                st.session_state.logged_user_email = selected_email
                st.session_state.user_nickname = user_info.get("nickname", selected_email.split('@')[0])
                st.session_state.auth_modal_shown = True
                
                if selected_email.lower() in ["ali123@gmail.com", "admin@gmail.com"]:
                    st.session_state.is_admin = True
                else:
                    st.session_state.is_admin = False
                    
                st.rerun()
        else:
            st.info("No saved accounts found. Please Sign Up or Continue as Guest.")
            login_email = st.text_input("Email Address", placeholder="user@example.com", key="modal_login_email")
            login_pass = st.text_input("Password", type="password", key="modal_login_pass")
            if st.button("Sign In", use_container_width=True):
                if login_email:
                    st.session_state.user_logged_in = True
                    st.session_state.logged_user_email = login_email
                    st.session_state.user_nickname = login_email.split('@')[0]
                    st.session_state.stored_profiles[login_email] = {"password": login_pass, "nickname": st.session_state.user_nickname}
                    st.session_state.auth_modal_shown = True
                    
                    if login_email.lower() in ["ali123@gmail.com", "admin@gmail.com"]:
                        st.session_state.is_admin = True
                    else:
                        st.session_state.is_admin = False
                        
                    st.rerun()

    with tab_signup:
        signup_email = st.text_input("Enter Email", placeholder="newuser@example.com", key="modal_signup_email")
        signup_nickname = st.text_input("Enter Nickname / Username (Optional)", placeholder="e.g. Ali Zain", key="modal_signup_nickname")
        signup_pass = st.text_input("Create Password", type="password", key="modal_signup_pass")
        
        if st.button("Create Account & Continue", use_container_width=True):
            if signup_email and signup_pass:
                nick = signup_nickname.strip() if signup_nickname.strip() else signup_email.split('@')[0]
                st.session_state.stored_profiles[signup_email] = {"password": signup_pass, "nickname": nick}
                st.session_state.user_logged_in = True
                st.session_state.logged_user_email = signup_email
                st.session_state.user_nickname = nick
                st.session_state.auth_modal_shown = True
                
                if signup_email.lower() in ["ali123@gmail.com", "admin@gmail.com"]:
                    st.session_state.is_admin = True
                else:
                    st.session_state.is_admin = False
                    
                st.rerun()
            else:
                st.error("Please provide both email and password.")

    st.markdown("---")
    if st.button("🌐 Continue as Guest", use_container_width=True):
        st.session_state.auth_modal_shown = True
        st.session_state.user_logged_in = False
        st.session_state.user_nickname = "Guest_User"
        st.session_state.is_admin = False
        st.rerun()


# ==========================================
# 4. STREAMLIT WEB DASHBOARD
# ==========================================
def main():
    st.set_page_config(page_title="Weather Insights", layout="wide", initial_sidebar_state="collapsed")

    # --- SESSION STATES INITIALIZATION ---
    if "user_searched_records" not in st.session_state:
        st.session_state.user_searched_records = pd.DataFrame()

    if "last_deleted_backup" not in st.session_state:
        st.session_state.last_deleted_backup = pd.DataFrame()

    if "selected_cities_list" not in st.session_state:
        st.session_state.selected_cities_list = ["Islamabad", "Karachi", "Lahore", "London", "New York"]

    if "user_logged_in" not in st.session_state:
        st.session_state.user_logged_in = False

    if "logged_user_email" not in st.session_state:
        st.session_state.logged_user_email = ""

    if "user_nickname" not in st.session_state:
        st.session_state.user_nickname = "Guest_User"

    if "is_admin" not in st.session_state:
        st.session_state.is_admin = False

    if "user_profile_pic" not in st.session_state:
        st.session_state.user_profile_pic = None

    if "stored_profiles" not in st.session_state:
        st.session_state.stored_profiles = {}

    if "active_view" not in st.session_state:
        st.session_state.active_view = "main"

    if "app_theme" not in st.session_state:
        st.session_state.app_theme = "Dark Cosmic Blue"

    if "avatar_bg_color" not in st.session_state:
        st.session_state.avatar_bg_color = "#e53935"

    if "auth_modal_shown" not in st.session_state:
        st.session_state.auth_modal_shown = False

    # SHOW WELCOME MODAL ON INITIAL LOAD
    if not st.session_state.auth_modal_shown:
        welcome_auth_modal()

    def get_random_color():
        colors = [
            "#e53935", "#d81b60", "#8e24aa", "#5e35b1", 
            "#3949ab", "#1e88e5", "#039be5", "#00acc1", 
            "#00897b", "#43a047", "#7cb342", "#f4511e", "#fb8c00"
        ]
        return random.choice(colors)

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

    # --- STRICT ADMIN SIDEBAR VISIBILITY CONTROL ---
    sidebar_css = "" if st.session_state.is_admin else """
        section[data-testid="stSidebar"] {
            display: none !important;
        }
    """

    st.markdown(f"""
        <style>
        .stApp {{
            background: {bg_style};
            color: {text_color};
            position: relative;
            overflow-x: hidden;
        }}

        {sidebar_css}

        /* MANAGE ACCOUNT & THREE DOTS GAP FIX (EXACTLY 15PX) */
        .right-header-container {{
            display: flex;
            align-items: center;
            justify-content: flex-end;
            gap: 15px !important;
        }}

        /* WEATHER ICON COLOR STYLING */
        .weather-sun-icon {{
            color: #FFD700;
            filter: drop-shadow(0 0 3px #FF8C00);
            font-size: 24px;
            margin-right: 6px;
        }}
        </style>
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
    # HEADER ROW
    # ==========================================
    header_col1, header_col2 = st.columns([6.2, 3.8])

    with header_col1:
        st.markdown('### <span class="weather-sun-icon">☀️</span>☁ **Weather Insights**', unsafe_allow_html=True)

    with header_col2:
        if st.session_state.user_logged_in and st.session_state.logged_user_email:
            avatar_letter = st.session_state.user_nickname[0].upper()
        else:
            avatar_letter = "G"

        btn_col1, btn_col2 = st.columns([3, 1])

        with btn_col1:
            popover_label = f"{avatar_letter}  Manage Account"
            account_popover = st.popover(popover_label)
            
            with account_popover:
                st.markdown("#### **Account & Settings Menu**")
                
                if not st.session_state.user_logged_in:
                    tab_signin, tab_signup = st.tabs(["🔑 Sign In", "📝 Sign Up"])

                    with tab_signin:
                        if st.session_state.stored_profiles:
                            st.caption("Select saved account:")
                            selected_saved_email = st.selectbox("Saved Accounts:", options=list(st.session_state.stored_profiles.keys()), key="hdr_saved_email_select")
                            if st.button("Sign In with Selected Account"):
                                user_info = st.session_state.stored_profiles.get(selected_saved_email, {})
                                st.session_state.user_logged_in = True
                                st.session_state.logged_user_email = selected_saved_email
                                st.session_state.user_nickname = user_info.get("nickname", selected_saved_email.split('@')[0])
                                st.session_state.avatar_bg_color = get_random_color()
                                
                                if selected_saved_email.lower() in ["ali123@gmail.com", "admin@gmail.com"]:
                                    st.session_state.is_admin = True
                                else:
                                    st.session_state.is_admin = False
                                    
                                st.toast(f"Welcome back, {st.session_state.user_nickname}!", icon="✅")
                                st.rerun()
                        else:
                            st.info("No saved accounts found. Please Sign Up first.")
                            user_email_input = st.text_input("Email Address", placeholder="user@example.com", key="hdr_login_email")
                            user_pass_input = st.text_input("Password", type="password", key="hdr_login_pass")
                            if st.button("Sign In"):
                                if user_email_input:
                                    st.session_state.user_logged_in = True
                                    st.session_state.logged_user_email = user_email_input
                                    st.session_state.user_nickname = user_email_input.split('@')[0]
                                    st.session_state.stored_profiles[user_email_input] = {"password": user_pass_input, "nickname": st.session_state.user_nickname}
                                    st.session_state.avatar_bg_color = get_random_color()
                                    
                                    if user_email_input.lower() in ["ali123@gmail.com", "admin@gmail.com"]:
                                        st.session_state.is_admin = True
                                    else:
                                        st.session_state.is_admin = False
                                    st.rerun()

                    with tab_signup:
                        new_user_email = st.text_input("Enter Email", placeholder="newuser@example.com", key="hdr_signup_email")
                        new_user_nickname = st.text_input("Enter Nickname (Optional)", placeholder="e.g. Ali Zain", key="hdr_signup_nickname")
                        new_user_pass = st.text_input("Create Password", type="password", key="hdr_signup_pass")
                        if st.button("Create Account & Sign In"):
                            if new_user_email and new_user_pass:
                                nick = new_user_nickname.strip() if new_user_nickname.strip() else new_user_email.split('@')[0]
                                st.session_state.stored_profiles[new_user_email] = {"password": new_user_pass, "nickname": nick}
                                st.session_state.user_logged_in = True
                                st.session_state.logged_user_email = new_user_email
                                st.session_state.user_nickname = nick
                                st.session_state.avatar_bg_color = get_random_color()
                                
                                if new_user_email.lower() in ["ali123@gmail.com", "admin@gmail.com"]:
                                    st.session_state.is_admin = True
                                else:
                                    st.session_state.is_admin = False
                                    
                                st.success("Account registered successfully!")
                                st.rerun()
                            else:
                                st.error("Please enter email and password.")

                else:
                    st.success(f"Logged in as: **{st.session_state.user_nickname}** ({st.session_state.logged_user_email})")
                    
                    with st.expander("⚙ Profile & Photo Settings"):
                        updated_nick = st.text_input("Update Nickname", value=st.session_state.user_nickname)
                        pic_url = st.text_input("Profile Picture URL (Optional):", value=st.session_state.user_profile_pic or "", placeholder="https://example.com/photo.jpg")
                        
                        if st.button("Save Profile"):
                            st.session_state.user_nickname = updated_nick.strip()
                            st.session_state.user_profile_pic = pic_url.strip() if pic_url.strip() else None
                            st.session_state.avatar_bg_color = get_random_color()
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
                        st.session_state.user_nickname = "Guest_User"
                        st.session_state.user_profile_pic = None
                        st.session_state.is_admin = False
                        st.session_state.avatar_bg_color = get_random_color()
                        st.rerun()

        with btn_col2:
            menu_popover = st.popover("⋮")
            with menu_popover:
                st.markdown("#### **Menu**")
                
                if st.button("📥 Install App"):
                    st.info("📲 App installation active! On desktop browser, click 3 dots on top-right -> 'Save and share' -> 'Install Weather Insights'.")
                    
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
                    st.session_state.active_view = "delete_data_view"
                    st.rerun()

    st.markdown("---")

    # ==========================================
    # SIDEBAR: ADMIN PANEL (VISIBLE EXCLUSIVELY TO ADMIN)
    # ==========================================
    if st.session_state.is_admin:
        st.sidebar.title("🔒 Security & Admin Panel")
        st.sidebar.success("👑 Logged in as Super Admin")
        admin_password = st.sidebar.text_input("Enter Admin Password", type="password")
        if admin_password == "ali123":
            st.sidebar.info("Admin Full Unlocked")

    # ==========================================
    # VIEW ROUTING SYSTEM
    # ==========================================

    if st.session_state.active_view == "history":
        st.header("📜 Search History Analytics")
        df_historical = fetch_historical_db_data()
        
        if st.session_state.is_admin:
            st.success("👑 **Admin Access View**: Displaying all user histories")
            if not df_historical.empty:
                current_admin_name = st.session_state.user_nickname
                admin_records = df_historical[df_historical['user_name'] == current_admin_name]
                other_records = df_historical[df_historical['user_name'] != current_admin_name]

                st.subheader(f"🏷️ Your Admin Activity ({current_admin_name})")
                if not admin_records.empty:
                    st.dataframe(admin_records, use_container_width=True)
                else:
                    st.info("No admin searches recorded yet.")

                st.subheader("👥 All User & Guest Search Histories")
                if not other_records.empty:
                    st.dataframe(other_records, use_container_width=True)
                else:
                    st.info("No guest or other user searches logged.")
            else:
                st.info("No historical search data present in database.")
        else:
            st.info("👤 **User View**: Your Recent Searches")
            current_user_name = st.session_state.user_nickname
            if not df_historical.empty:
                user_df = df_historical[df_historical['user_name'] == current_user_name]
                if not user_df.empty:
                    st.dataframe(user_df, use_container_width=True)
                else:
                    st.info("No history records found for your account.")
            else:
                st.info("No history records available.")
            
        if st.button("⬅️ Back to Main Dashboard"):
            st.session_state.active_view = "main"
            st.rerun()

    elif st.session_state.active_view == "downloads":
        st.header("📥 Downloads & Data Export Center")
        df_historical = fetch_historical_db_data()
        
        if st.session_state.is_admin:
            st.success("👑 **Admin Export Access**: All user records ready for export")
            if not df_historical.empty:
                csv_data_all = df_historical.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Export Complete Server Database (CSV)",
                    data=csv_data_all,
                    file_name=f"all_users_weather_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
                st.dataframe(df_historical, use_container_width=True)
            else:
                st.info("No server data available for download.")
        else:
            current_user_name = st.session_state.user_nickname
            if not st.session_state.user_searched_records.empty:
                csv_data = st.session_state.user_searched_records.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label=f"📥 Download ({current_user_name}) Active Session CSV",
                    data=csv_data,
                    file_name=f"my_weather_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
                st.dataframe(st.session_state.user_searched_records, use_container_width=True)
            else:
                st.info("No active session records on screen to export.")
            
        if st.button("⬅️ Back to Main Dashboard"):
            st.session_state.active_view = "main"
            st.rerun()

    elif st.session_state.active_view == "delete_data_view":
        st.header("🗑 Delete Browsing Data & System Backups")
        
        if st.session_state.is_admin:
            st.subheader("👑 Admin Control Options")
            opt = st.radio("Choose Action:", [
                "1. Temporary Screen Clear (Current View Only)",
                "2. Permanent Server Data Wipe (Requires Password)",
                "3. Restore Data from Backups"
            ])

            if "1." in opt:
                if st.button("Clear Screen View"):
                    st.session_state.last_deleted_backup = st.session_state.user_searched_records.copy()
                    st.session_state.user_searched_records = pd.DataFrame()
                    st.toast("Temporary screen data cleared!", icon="🧹")

            elif "2." in opt:
                del_pass = st.text_input("Enter Admin Password for Permanent Purge:", type="password")
                if st.button("🔥 Permanently Delete All Server Data"):
                    if del_pass == "ali123":
                        delete_all_data_from_db()
                        st.session_state.user_searched_records = pd.DataFrame()
                        st.session_state.last_deleted_backup = pd.DataFrame()
                        st.success("All server database and CSV records permanently erased!")
                    else:
                        st.error("Invalid password!")

            elif "3." in opt:
                st.markdown("#### **Backup Restoration Options**")
                col_b1, col_b2 = st.columns(2)
                with col_b1:
                    if st.button("🔄 Restore Last Session Deleted Batch"):
                        if not st.session_state.last_deleted_backup.empty:
                            st.session_state.user_searched_records = pd.concat([st.session_state.user_searched_records, st.session_state.last_deleted_backup], ignore_index=True)
                            st.success("Last deleted batch successfully restored!")
                        else:
                            st.warning("No recent session backup found.")
                with col_b2:
                    if st.button("📦 Restore All Complete Database Records"):
                        all_db = fetch_historical_db_data()
                        if not all_db.empty:
                            st.session_state.user_searched_records = all_db
                            st.success("All-time database history restored to screen!")
                        else:
                            st.warning("Database is empty.")
        else:
            st.subheader("👤 Clear Browsing Session")
            st.caption("Clears temporary records currently shown on your browser screen.")
            if st.button("🧹 Clear My Screen Data"):
                st.session_state.user_searched_records = pd.DataFrame()
                st.toast("Screen session cleared successfully!", icon="✅")

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("⬅️ Back to Main Dashboard"):
            st.session_state.active_view = "main"
            st.rerun()

    else: # MAIN DASHBOARD
        st.title("🌐 Real-Time Pakistan & Global Weather Insights")
        st.markdown("Automated **ETL Data Pipeline** with Pydantic Validation, SQLite Persistence, and EDA.")

        st.markdown("<br>", unsafe_allow_html=True)

        current_display_name = st.session_state.user_nickname if st.session_state.user_logged_in else "Guest_User"

        st.subheader("🔍 Search and Select Cities")
        searched_city = st.selectbox(
            "Search city from A-Z list:",
            options=["-- Type or Select City --"] + sorted_cities,
            index=0
        )

        if searched_city != "-- Type or Select City --" and searched_city not in st.session_state.selected_cities_list:
            st.session_state.selected_cities_list.append(searched_city)

        selected_cities = st.multiselect(
            "📦 Selected Cities Container:",
            options=st.session_state.selected_cities_list,
            default=st.session_state.selected_cities_list
        )
        st.session_state.selected_cities_list = selected_cities

        st.markdown("<br>", unsafe_allow_html=True)
        run_pipeline_btn = st.button("Show Weather 🌤", use_container_width=True)

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
            st.info("No records on your screen right now. Select cities and click 'Show Weather 🌤' to view your results.")


if __name__ == "__main__":
    main()