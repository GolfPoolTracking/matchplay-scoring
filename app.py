import streamlit as st
import uuid
import datetime
from supabase import create_client, Client

# --- App Configuration ---
st.set_page_config(page_title="Matchplay Leaderboard", layout="centered")

BASE_URL = "https://matchplay-scoring.streamlit.app"

# --- Supabase Initialization ---
@st.cache_resource
def init_connection():
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

try:
    supabase = init_connection()
except Exception as e:
    st.error(f"Failed to initialize Supabase. Please check your secrets.toml file.")
    st.stop()

# --- Database Loading & Sync ---
if "db_matches" not in st.session_state:
    st.session_state["db_matches"] = {}

try:
    db_res = supabase.table("matchplay_sessions").select("*").execute()
    st.session_state["db_matches"] = {row["id"]: row["match_data"] for row in db_res.data}
except Exception as e:
    st.session_state["db_matches"] = {}
    st.error("Could not fetch data from database.")

def save_match_to_db(match_id, match_data):
    supabase.table("matchplay_sessions").upsert({
        "id": match_id,
        "match_data": match_data
    }).execute()

# --- Helper Functions for Scoreboard Math ---
def get_match_status(holes_dict):
    score = 0
    holes_played = 0
    for i in range(1, 19):
        res = holes_dict.get(str(i))
        if res in ["A", "B", "H"]:
            holes_played = i
            if res == "A": score += 1
            elif res == "B": score -= 1
            
    if score > 0: return "A", score, holes_played
    elif score < 0: return "B", abs(score), holes_played
    else: return "SQ", 0, holes_played

def calculate_projected_points(matches):
    pts_a, pts_b = 0.0, 0.0
    for m in matches:
        leader, _, _ = get_match_status(m["holes"])
        if leader == "A": pts_a += 1.0
        elif leader == "B": pts_b += 1.0
        else:
            pts_a += 0.5
            pts_b += 0.5
    return pts_a, pts_b

# --- Visual Render Engine (Custom HTML/CSS) ---
def render_dashboard(match_data):
    setup = match_data["setup"]
    matches = match_data["matches"]
    pts_a, pts_b = calculate_projected_points(matches)
    
    # Render Points Header
    st.markdown(f"""
    <div style="text-align: center; margin-bottom: 40px; font-family: sans-serif;">
        <h3 style="color: #666; font-size: 14px; text-transform: uppercase; letter-spacing: 1px;">{setup['event_name']}</h3>
        <hr style="width: 50px; margin: 10px auto; border: 1px solid #ff4b4b;">
        <div style="color: #ff4b4b; font-size: 12px; margin-bottom: 20px;">Live Score</div>
        
        <div style="display: flex; justify-content: center; align-items: center; gap: 30px;">
            <div style="text-align: center; width: 80px;">
                <div style="font-weight: bold; margin-bottom: 8px; color: #333;">{setup['team_a']}</div>
                <div style="width: 50px; height: 50px; border-radius: 8px; background: #2563eb; color: white; display: flex; align-items: center; justify-content: center; font-size: 24px; font-weight: bold; margin: 0 auto; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                    {pts_a:g}
                </div>
            </div>
            <div style="font-size: 14px; color: #888; font-weight: 500; margin-top: 25px;">Points</div>
            <div style="text-align: center; width: 80px;">
                <div style="font-weight: bold; margin-bottom: 8px; color: #333;">{setup['team_b']}</div>
                <div style="width: 50px; height: 50px; border-radius: 8px; background: #dc2626; color: white; display: flex; align-items: center; justify-content: center; font-size: 24px; font-weight: bold; margin: 0 auto; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                    {pts_b:g}
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Render Match Cards
    for m in matches:
        leader, amount, holes_played = get_match_status(m["holes"])
        
        # Determine Card Colors and Status Text
        bg_a = "#2563eb" if leader == "A" else "transparent"
        text_a = "white" if leader == "A" else "#333"
        bg_b = "#dc2626" if leader == "B" else "transparent"
        text_b = "white" if leader == "B" else "#333"
        
        if leader == "A":
            status_text = f"<span style='color: #2563eb;'>{amount} UP</span>"
        elif leader == "B":
            status_text = f"<span style='color: #dc2626;'>{amount} UP</span>"
        else:
            status_text = "<span style='color: #555;'>ALL SQ</span>"

        # Generate Hole History Circles
        circles_html = ""
        for i in range(1, holes_played + 1):
            res = m["holes"].get(str(i))
            if res == "A":
                circles_html += f"<div style='width: 22px; height: 22px; border-radius: 50%; background: #2563eb; color: white; display: flex; align-items: center; justify-content: center; font-size: 10px; font-weight: bold;'>{i}</div>"
            elif res == "B":
                circles_html += f"<div style='width: 22px; height: 22px; border-radius: 50%; background: #dc2626; color: white; display: flex; align-items: center; justify-content: center; font-size: 10px; font-weight: bold;'>{i}</div>"
            elif res == "H":
                circles_html += f"<div style='width: 22px; height: 22px; border-radius: 50%; border: 1px solid #ccc; color: #888; background: #f9f9f9; display: flex; align-items: center; justify-content: center; font-size: 10px;'>{i}</div>"

        # Custom Card Layout
        st.markdown(f"""
        <div style="background: white; border: 1px solid #eaeaea; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); padding: 15px; margin-bottom: 20px; font-family: sans-serif;">
            <div style="display: flex; align-items: center; justify-content: space-between; height: 60px; border-bottom: 1px solid #f0f0f0; padding-bottom: 15px; margin-bottom: 15px;">
                
                <!-- Team A Side -->
                <div style="flex: 1; height: 100%; background: {bg_a}; color: {text_a}; display: flex; align-items: center; padding-left: 15px; font-weight: bold; font-size: 14px; clip-path: polygon(0% 0%, 92% 0%, 100% 50%, 92% 100%, 0% 100%);">
                    {m['p_a']}
                </div>
                
                <!-- Center Status -->
                <div style="width: 90px; text-align: center; display: flex; flex-direction: column; justify-content: center;">
                    <span style="font-size: 10px; color: #999; text-transform: uppercase; margin-bottom: 2px;">Thru {holes_played}</span>
                    <span style="font-size: 16px; font-weight: 800;">{status_text}</span>
                </div>
                
                <!-- Team B Side -->
                <div style="flex: 1; height: 100%; background: {bg_b}; color: {text_b}; display: flex; align-items: center; justify-content: flex-end; padding-right: 15px; font-weight: bold; font-size: 14px; clip-path: polygon(8% 0%, 100% 0%, 100% 100%, 8% 100%, 0% 50%);">
                    {m['p_b']}
                </div>
                
            </div>
            
            <!-- History Bubbles -->
            <div style="display: flex; gap: 6px; flex-wrap: wrap; padding-left: 5px;">
                {circles_html}
            </div>
        </div>
        """, unsafe_allow_html=True)


# --- Routing Logic ---
query_params = st.query_params
active_match_id = query_params.get("match_id", None)
is_manager = query_params.get("manage", "false").lower() == "true"

if active_match_id and active_match_id in st.session_state["db_matches"]:
    match_data = st.session_state["db_matches"][active_match_id]
    
    # ==========================================
    # PUBLIC READ-ONLY DASHBOARD
    # ==========================================
    if not is_manager:
        render_dashboard(match_data)

    # ==========================================
    # MANAGER VIEW (Tabs Included)
    # ==========================================
    else:
        st.button("⬅ Back to Menu", on_click=lambda: st.query_params.clear())
        st.success("🔒 Manager Access Active")
        
        tab_board, tab_scores, tab_links = st.tabs(["Dashboard Preview", "Enter Scores", "Share Links"])
        
        with tab_board:
            render_dashboard(match_data)
            
        with tab_scores:
            st.header("Log Results")
            # Select which sub-match to update
            match_options = {m["id"]: f"{m['p_a']} vs {m['p_b']}" for m in match_data["matches"]}
            selected_m_id = st.selectbox("Select Matchup", options=list(match_options.keys()), format_func=lambda x: match_options[x])
            
            # Find the match dict
            active_sub_match = next(m for m in match_data["matches"] if m["id"] == selected_m_id)
            
            st.write(f"**Score Entry: {active_sub_match['p_a']} vs {active_sub_match['p_b']}**")
            
            # Simple Hole-by-Hole entry using segmented controls (or radio)
            with st.form(key=f"form_{selected_m_id}"):
                updates = {}
                for hole_num in range(1, 19):
                    str_h = str(hole_num)
                    current_val = active_sub_match["holes"].get(str_h, "Not Played")
                    
                    st.write(f"**Hole {hole_num}**")
                    updates[str_h] = st.radio(
                        f"Hole {hole_num}", 
                        options=["Not Played", "A", "H", "B"], 
                        format_func=lambda x: {
                            "Not Played": "⚪ Not Played",
                            "A": f"🔵 {active_sub_match['p_a']} Won",
                            "H": "🔘 Halved",
                            "B": f"🔴 {active_sub_match['p_b']} Won"
                        }[x],
                        index=["Not Played", "A", "H", "B"].index(current_val),
                        horizontal=True,
                        label_visibility="collapsed"
                    )
                    st.divider()
                
                if st.form_submit_button("✅ Save Scores", type="primary", use_container_width=True):
                    # Filter out "Not Played" before saving
                    active_sub_match["holes"] = {k: v for k, v in updates.items() if v != "Not Played"}
                    save_match_to_db(active_match_id, match_data)
                    st.rerun()

        with tab_links:
            st.write("**Public Leaderboard Link (Send to players):**")
            st.code(f"{BASE_URL}/?match_id={active_match_id}")
            st.write("**Manager Link (Keep Private):**")
            st.code(f"{BASE_URL}/?match_id={active_match_id}&manage=true")

else:
    # ==========================================
    # HOME MENU & EVENT CREATION
    # ==========================================
    st.title("🏌️‍♂️ Matchplay Centre")
    
    tab_active, tab_create = st.tabs(["Active Events", "Create New Event"])
    
    with tab_active:
        if not st.session_state["db_matches"]:
            st.info("No events found. Create one in the next tab!")
        else:
            for e_id, e_data in st.session_state["db_matches"].items():
                with st.container(border=True):
                    st.subheader(e_data["setup"]["event_name"])
                    st.write(f"{e_data['setup']['team_a']} vs {e_data['setup']['team_b']}")
                    if st.button("Manage Event", key=f"open_{e_id}"):
                        st.query_params["match_id"] = e_id
                        st.query_params["manage"] = "true"
                        st.rerun()

    with tab_create:
        st.header("New Event Setup")
        event_name = st.text_input("Event Name", placeholder="e.g. Summer League Game")
        
        colA, colB = st.columns(2)
        with colA: team_a = st.text_input("Blue Team Name", value="Europe")
        with colB: team_b = st.text_input("Red Team Name", value="USA")
        
        num_matches = st.number_input("Number of Matches", min_value=1, max_value=20, value=4, step=1)
        st.divider()
        
        st.write("### Matchup Pairings")
        matches = []
        for i in range(int(num_matches)):
            st.write(f"**Match {i+1}**")
            c1, c2 = st.columns(2)
            with c1: p_a = st.text_input(f"Blue Player(s)", key=f"pa_{i}")
            with c2: p_b = st.text_input(f"Red Player(s)", key=f"pb_{i}")
            
            matches.append({
                "id": f"m_{uuid.uuid4().hex[:6]}",
                "p_a": p_a,
                "p_b": p_b,
                "holes": {}
            })
            
        if st.button("Generate Event", type="primary", use_container_width=True):
            if not event_name or not team_a or not team_b:
                st.error("Event Name and Team Names are required.")
            else:
                new_id = uuid.uuid4().hex[:8]
                new_data = {
                    "id": new_id,
                    "setup": {
                        "event_name": event_name,
                        "team_a": team_a,
                        "team_b": team_b,
                    },
                    "matches": matches
                }
                save_match_to_db(new_id, new_data)
                st.query_params["match_id"] = new_id
                st.query_params["manage"] = "true"
                st.rerun()
