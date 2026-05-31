import streamlit as st
import pandas as pd
import math
import uuid
import datetime
from supabase import create_client, Client

# --- App Configuration ---
st.set_page_config(page_title="Matchplay Centre", layout="centered")

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

# --- WHS Custom Rounding ---
def whs_round(val):
    return int(math.floor(val + 0.5))

# --- Default Data Setup ---
if "courses" not in st.session_state:
    st.session_state["courses"] = {
        "Laytown & Bettystown": {
            "tees": {
                "White": {"rating": 72.0, "slope": 126, "par": 71},
                "Green": {"rating": 71.2, "slope": 125, "par": 71}
            },
            "holes": [
                {"hole": 1, "par": 4, "index": 12}, {"hole": 2, "par": 4, "index": 14},
                {"hole": 3, "par": 4, "index": 4},  {"hole": 4, "par": 5, "index": 16},
                {"hole": 5, "par": 4, "index": 6},  {"hole": 6, "par": 3, "index": 10},
                {"hole": 7, "par": 4, "index": 2},  {"hole": 8, "par": 3, "index": 8},
                {"hole": 9, "par": 4, "index": 18}, {"hole": 10, "par": 4, "index": 11},
                {"hole": 11, "par": 4, "index": 5}, {"hole": 12, "par": 3, "index": 13},
                {"hole": 13, "par": 4, "index": 3}, {"hole": 14, "par": 4, "index": 9},
                {"hole": 15, "par": 4, "index": 1}, {"hole": 16, "par": 4, "index": 7},
                {"hole": 17, "par": 4, "index": 17}, {"hole": 18, "par": 5, "index": 15}
            ]
        }
    }

if "allowances" not in st.session_state:
    st.session_state["allowances"] = {"Singles": 100, "Fourball": 90, "Foursomes": 50}

# Load matches from Supabase
if "db_matches" not in st.session_state:
    st.session_state["db_matches"] = {}

try:
    db_res = supabase.table("matchplay_sessions").select("*").execute()
    st.session_state["db_matches"] = {}
    for row in db_res.data:
        data = row.get("match_data", {})
        # Ensure we are loading records built for this outcome-based format
        if "setup" in data and "outcomes" in data:
            st.session_state["db_matches"][row["id"]] = data
except Exception as e:
    st.session_state["db_matches"] = {}
    st.error("Could not fetch data from database.")

def save_match_to_db(match_id, match_data):
    supabase.table("matchplay_sessions").upsert({
        "id": match_id,
        "match_data": match_data
    }).execute()

# --- Helper Functions ---
def calculate_course_handicap(hi, slope, rating, par):
    return whs_round((hi * (slope / 113.0)) + (rating - par))

def allocate_strokes(shots_received, hole_index):
    if shots_received <= 0: return 0
    strokes = shots_received // 18 + (1 if hole_index <= (shots_received % 18) else 0)
    return strokes

def generate_shots_data(match):
    setup = match["setup"]
    tee_data = st.session_state["courses"][setup["course"]]["tees"][setup["tee"]]
    allowance_decimal = st.session_state["allowances"][setup["match_type"]] / 100.0
    shots_received = {}
    team_names = {"A": "", "B": ""}
    
    if setup["match_type"] == "Singles":
        p_keys = list(setup["players"].keys())
        team_names["A"], team_names["B"] = p_keys[0], p_keys[1]
        
        if not setup.get("use_handicaps", True):
            return {team_names["A"]: 0, team_names["B"]: 0}, team_names

        ch_dict = {p: calculate_course_handicap(data["hi"], tee_data["slope"], tee_data["rating"], tee_data["par"]) for p, data in setup["players"].items()}
        lowest_ch = min(ch_dict.values())
        for p, ch in ch_dict.items():
            shots_received[p] = whs_round((ch - lowest_ch) * allowance_decimal)

    elif setup["match_type"] == "Fourball":
        p_keys = list(setup["players"].keys())
        team_names["A"] = f"{p_keys[0]} & {p_keys[1]}"
        team_names["B"] = f"{p_keys[2]} & {p_keys[3]}"
        
        if not setup.get("use_handicaps", True):
            shots_received = {p: 0 for p in p_keys}
            return shots_received, team_names

        ch_dict = {p: calculate_course_handicap(data["hi"], tee_data["slope"], tee_data["rating"], tee_data["par"]) for p, data in setup["players"].items()}
        lowest_ch = min(ch_dict.values())
        for p, ch in ch_dict.items():
            shots_received[p] = whs_round((ch - lowest_ch) * allowance_decimal)

    else: # Foursomes
        p_keys = list(setup["players"].keys())
        team_names["A"] = f"{p_keys[0]} & {p_keys[1]}"
        team_names["B"] = f"{p_keys[2]} & {p_keys[3]}"
        
        if not setup.get("use_handicaps", True):
            return {team_names["A"]: 0, team_names["B"]: 0}, team_names

        team_a_ch = calculate_course_handicap(setup["players"][p_keys[0]]["hi"], tee_data["slope"], tee_data["rating"], tee_data["par"]) + \
                    calculate_course_handicap(setup["players"][p_keys[1]]["hi"], tee_data["slope"], tee_data["rating"], tee_data["par"])
        team_b_ch = calculate_course_handicap(setup["players"][p_keys[2]]["hi"], tee_data["slope"], tee_data["rating"], tee_data["par"]) + \
                    calculate_course_handicap(setup["players"][p_keys[3]]["hi"], tee_data["slope"], tee_data["rating"], tee_data["par"])
        
        diff = whs_round(abs(team_a_ch - team_b_ch) * allowance_decimal)
        shots_received[team_names["A"]] = 0 if team_a_ch <= team_b_ch else diff
        shots_received[team_names["B"]] = 0 if team_b_ch <= team_a_ch else diff

    return shots_received, team_names

def get_match_status(outcomes, total_holes):
    """Calculates match score and identifies if a match is mathematically over."""
    score = 0
    holes_played = 0
    match_over = False
    final_str = "ALL SQ"
    
    for i in range(1, total_holes + 1):
        res = outcomes.get(str(i))
        if res in ["A", "B", "H"]:
            holes_played = i
            if res == "A": score += 1
            elif res == "B": score -= 1
            
            holes_remaining = total_holes - i
            
            # Mathematical early finish logic (e.g., 3 UP with 2 to play -> 3&2)
            if abs(score) > holes_remaining:
                match_over = True
                if holes_remaining > 0:
                    final_str = f"{abs(score)}&{holes_remaining}"
                else:
                    final_str = f"{abs(score)} UP"
                break 
                
    if not match_over:
        if score > 0: final_str = f"{score} UP"
        elif score < 0: final_str = f"{abs(score)} UP"
        else: final_str = "ALL SQ"
        
    leader = "A" if score > 0 else ("B" if score < 0 else "SQ")
    return leader, abs(score), holes_played, match_over, final_str

# --- Visual Render Engine (Custom HTML/CSS) ---
def render_live_card(match_data, team_names, total_holes):
    setup = match_data["setup"]
    outcomes = match_data.get("outcomes", {})
    
    leader, amount, holes_played, match_over, final_str = get_match_status(outcomes, total_holes)
    
    # Modern Golf Palette: Emerald Green & Indigo
    COLOR_A = "#10b981" # Emerald Green
    COLOR_B = "#6366f1" # Indigo
    
    # Clean transparent defaults for ALL SQ state
    bg_a, text_a = "transparent", "#333"
    bg_b, text_b = "transparent", "#333"
    shape_a = "none"
    shape_b = "none"
    border_a = "none"
    border_b = "none"
    
    if leader == "A":
        bg_a, text_a = COLOR_A, "white"
        shape_a = "polygon(0% 0%, 92% 0%, 100% 50%, 92% 100%, 0% 100%)"
        border_a = f"1px solid {COLOR_A}"
        status_text = f"<span style='color: {COLOR_A};'>{final_str}</span>"
    elif leader == "B":
        bg_b, text_b = COLOR_B, "white"
        shape_b = "polygon(8% 0%, 100% 0%, 100% 100%, 8% 100%, 0% 50%)"
        border_b = f"1px solid {COLOR_B}"
        status_text = f"<span style='color: {COLOR_B};'>{final_str}</span>"
    else:
        status_text = "<span style='color: #555;'>ALL SQ</span>"

    # Generate Hole History Bubbles
    circles_html = ""
    for i in range(1, holes_played + 1):
        res = outcomes.get(str(i))
        if res == "A":
            circles_html += f"<div style='width: 24px; height: 24px; border-radius: 50%; background: {COLOR_A}; color: white; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: bold;'>{i}</div>"
        elif res == "B":
            circles_html += f"<div style='width: 24px; height: 24px; border-radius: 50%; background: {COLOR_B}; color: white; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: bold;'>{i}</div>"
        elif res == "H":
            circles_html += f"<div style='width: 24px; height: 24px; border-radius: 50%; border: 1px solid #ccc; color: #888; background: #f9f9f9; display: flex; align-items: center; justify-content: center; font-size: 11px;'>{i}</div>"

    subtext = "FINAL" if match_over else f"Thru {holes_played}"

    # Flattened string for safe Streamlit rendering
    html_string = f"""<div style="background: white; border: 1px solid #eaeaea; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); padding: 20px; margin-top: 10px; font-family: sans-serif;"><div style="text-align: center; color: #888; font-size: 12px; text-transform: uppercase; margin-bottom: 15px; letter-spacing: 1px;">{setup['match_name']} - {setup['match_type']}</div><div style="display: flex; align-items: center; justify-content: space-between; height: 65px; border-bottom: 1px solid #f0f0f0; padding-bottom: 15px; margin-bottom: 15px;"><div style="flex: 1; height: 100%; background: {bg_a}; color: {text_a}; display: flex; align-items: center; padding-left: 15px; font-weight: bold; font-size: 15px; border-radius: 6px 0 0 6px; clip-path: {shape_a}; border: {border_a};">{team_names['A']}</div><div style="width: 100px; text-align: center; display: flex; flex-direction: column; justify-content: center;"><span style="font-size: 11px; color: #999; text-transform: uppercase; margin-bottom: 2px; font-weight: bold;">{subtext}</span><span style="font-size: 18px; font-weight: 800;">{status_text}</span></div><div style="flex: 1; height: 100%; background: {bg_b}; color: {text_b}; display: flex; align-items: center; justify-content: flex-end; padding-right: 15px; font-weight: bold; font-size: 15px; border-radius: 0 6px 6px 0; clip-path: {shape_b}; border: {border_b};">{team_names['B']}</div></div><div style="display: flex; gap: 8px; flex-wrap: wrap; justify-content: center;">{circles_html}</div></div>"""
    
    st.html(html_string)


# --- Routing Logic ---
query_params = st.query_params
active_match_id = query_params.get("match_id", None)
is_manager = query_params.get("manage", "false").lower() == "true"

if active_match_id and active_match_id in st.session_state["db_matches"]:
    match_data = st.session_state["db_matches"][active_match_id]
    setup = match_data["setup"]
    course_holes = st.session_state["courses"][setup["course"]]["holes"]
    total_holes = 18 + match_data.get("extra_holes", 0)
    
    shots_received, team_names = generate_shots_data(match_data)
    
    if not is_manager:
        # ==========================================
        # PUBLIC READ-ONLY DASHBOARD
        # ==========================================
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("🔄 Refresh Scoreboard", use_container_width=True):
                st.rerun()
                
        st.html("<h4 style='text-align: center; color: #666; margin-top: 10px; font-family: sans-serif;'>Live Matchplay Scoreboard</h4>")
        render_live_card(match_data, team_names, total_holes)

    else:
        # ==========================================
        # MANAGER VIEW
        # ==========================================
        st.button("⬅ Back to Menu", on_click=lambda: st.query_params.clear())
        
        tab_board, tab_scores, tab_shots, tab_links = st.tabs(["Scoreboard", "Log Outcomes", "Shots Allocation", "Share Links"])
        
        with tab_board:
            render_live_card(match_data, team_names, total_holes)
            
        with tab_scores:
            leader, amount, holes_played, match_over, final_str = get_match_status(match_data.get("outcomes", {}), total_holes)
            state_key = f"entry_hole_{active_match_id}"

            # Auto-calculate the next logical hole to score
            if state_key not in st.session_state:
                if match_over:
                    st.session_state[state_key] = holes_played
                else:
                    st.session_state[state_key] = min(holes_played + 1, total_holes)

            curr_hole = st.session_state[state_key]

            # Top Banner
            if match_over:
                winner = team_names[leader] if leader in team_names else "Match"
                st.success(f"🎉 **Match Finished!** {winner} wins {final_str}")
            else:
                st.write("Record the outcome below. The system will automatically detect when the match is over.")

            # Custom Navigation
            st.divider()
            c1, c2, c3 = st.columns([1, 2, 1])
            with c1:
                if st.button("⬅ Prev", disabled=(curr_hole <= 1), use_container_width=True):
                    st.session_state[state_key] -= 1
                    st.rerun()
            with c2:
                st.markdown(f"<h4 style='text-align:center; margin-top:5px;'>Hole {curr_hole}</h4>", unsafe_allow_html=True)
            with c3:
                # Disable next if match is over AND they are viewing the final hole, or if they hit the max limit
                disable_next = (curr_hole >= total_holes) or (match_over and curr_hole >= holes_played)
                if st.button("Next ➡", disabled=disable_next, use_container_width=True):
                    st.session_state[state_key] += 1
                    st.rerun()

            # Single Hole Entry UI
            h_idx = curr_hole - 1
            real_hole_idx = h_idx % 18
            h_data = course_holes[real_hole_idx]
            str_h = str(curr_hole)
            current_val = match_data["outcomes"].get(str_h, "Not Played")

            with st.container(border=True):
                st.markdown(f"<div style='text-align:center; color:gray; font-size:14px; margin-bottom:15px;'>Par {h_data['par']} &nbsp;|&nbsp; Index {h_data['index']}</div>", unsafe_allow_html=True)
                
                outcome = st.radio(
                    "Result",
                    options=["Not Played", "A", "H", "B"],
                    format_func=lambda x: {
                        "Not Played": "⚪ Not Played",
                        "A": f"🟢 {team_names['A']} Won",
                        "H": "🔘 Halved",
                        "B": f"🟣 {team_names['B']} Won"
                    }[x],
                    index=["Not Played", "A", "H", "B"].index(current_val),
                    horizontal=False,
                    label_visibility="collapsed"
                )
                
                st.write("")
                submit_label = "✅ Save & Next" if not match_over else "✅ Save Update"
                
                if st.button(submit_label, type="primary", use_container_width=True):
                    if outcome == "Not Played":
                        match_data["outcomes"].pop(str_h, None)
                    else:
                        match_data["outcomes"][str_h] = outcome
                    
                    save_match_to_db(active_match_id, match_data)
                    
                    # Recalculate status to check if saving this triggered a finish
                    l, a, hp, mo, fs = get_match_status(match_data["outcomes"], total_holes)
                    
                    # Auto-advance if match isn't over and we aren't at the end
                    if outcome != "Not Played" and not mo and curr_hole < total_holes:
                        st.session_state[state_key] += 1
                        
                    st.rerun()

            if not match_over and st.button("➕ Add Extra Hole", use_container_width=True):
                match_data["extra_holes"] = match_data.get("extra_holes", 0) + 1
                save_match_to_db(active_match_id, match_data)
                st.rerun()

        with tab_shots:
            st.header("Handicap Allocation")
            st.write(f"**Format:** {setup['match_type']} ({st.session_state['allowances'][setup['match_type']]}% Allowance)")
            
            # Generate table showing exact shots per hole
            grid_data = []
            for idx in range(18):
                h_data = course_holes[idx]
                row = {"Hole": idx + 1, "Par": h_data['par'], "Index": h_data['index']}
                
                # Show asterisks for players getting shots
                for p_name, total_shots in shots_received.items():
                    strokes_on_this_hole = allocate_strokes(total_shots, h_data['index'])
                    row[p_name] = "*" * strokes_on_this_hole if strokes_on_this_hole > 0 else "-"
                    
                grid_data.append(row)
                
            st.dataframe(pd.DataFrame(grid_data).set_index("Hole"), use_container_width=True)
            
            # Show summary of CH and HI
            st.write("**Player Data Used:**")
            raw_data = []
            for p, data in setup["players"].items():
                raw_data.append({"Player": p, "HI": data["hi"]})
            st.dataframe(pd.DataFrame(raw_data), hide_index=True)

        with tab_links:
            st.write("**Public Leaderboard Link (Send to players):**")
            st.code(f"{BASE_URL}/?match_id={active_match_id}")
            st.write("**Manager Link (Keep Private):**")
            st.code(f"{BASE_URL}/?match_id={active_match_id}&manage=true")

else:
    # ==========================================
    # HOME MENU & MATCH CREATION
    # ==========================================
    st.title("🏌️‍♂️ Matchplay Centre")
    
    tab_active, tab_create, tab_admin = st.tabs(["Active Matches", "Create New Match", "Admin"])
    
    with tab_active:
        if not st.session_state["db_matches"]:
            st.info("No matches found. Create one in the next tab!")
        else:
            for m_id, m_data in st.session_state["db_matches"].items():
                with st.container(border=True):
                    st.subheader(m_data["setup"]["match_name"])
                    st.write(f"{m_data['setup']['date']} | {m_data['setup']['course']} | {m_data['setup']['match_type']}")
                    if st.button("Manage Match", key=f"open_{m_id}"):
                        st.query_params["match_id"] = m_id
                        st.query_params["manage"] = "true"
                        st.rerun()

    with tab_create:
        st.header("New Match Setup")
        match_name = st.text_input("Match Name", placeholder="e.g. Sunday Final")
        match_date = st.date_input("Date", value=datetime.date.today())
        
        c1, c2 = st.columns(2)
        with c1: selected_course = st.selectbox("Select Course", list(st.session_state["courses"].keys()))
        with c2: selected_tee = st.selectbox("Select Tees", list(st.session_state["courses"][selected_course]["tees"].keys()))
        
        c3, c4 = st.columns(2)
        with c3: match_type = st.selectbox("Match Type", ["Singles", "Fourball", "Foursomes"])
        with c4: use_handicaps = st.checkbox("Use Handicaps", value=True)
        
        st.divider()
        st.subheader("Players & Handicaps")
        players = {}
        col1, col2 = st.columns(2)
        
        if match_type == "Singles":
            with col1: 
                p1 = st.text_input("Player 1 Name", key="s_p1_n")
                if use_handicaps: players[p1] = {"hi": st.number_input("Player 1 HI", value=10.0, format="%.1f", step=0.1, key="s_p1_h")}
                else: players[p1] = {"hi": 0.0}
            with col2: 
                p2 = st.text_input("Player 2 Name", key="s_p2_n")
                if use_handicaps: players[p2] = {"hi": st.number_input("Player 2 HI", value=10.0, format="%.1f", step=0.1, key="s_p2_h")}
                else: players[p2] = {"hi": 0.0}
                
        elif match_type in ["Fourball", "Foursomes"]:
            with col1:
                st.write("**Team A**")
                a1 = st.text_input("P1 Name", key="t_a1_n")
                if use_handicaps: players[a1] = {"hi": st.number_input("P1 HI", value=10.0, format="%.1f", step=0.1, key="t_a1_h")}
                else: players[a1] = {"hi": 0.0}
                
                a2 = st.text_input("P2 Name", key="t_a2_n")
                if use_handicaps: players[a2] = {"hi": st.number_input("P2 HI", value=10.0, format="%.1f", step=0.1, key="t_a2_h")}
                else: players[a2] = {"hi": 0.0}
            with col2:
                st.write("**Team B**")
                b1 = st.text_input("P3 Name", key="t_b1_n")
                if use_handicaps: players[b1] = {"hi": st.number_input("P3 HI", value=10.0, format="%.1f", step=0.1, key="t_b1_h")}
                else: players[b1] = {"hi": 0.0}
                
                b2 = st.text_input("P4 Name", key="t_b2_n")
                if use_handicaps: players[b2] = {"hi": st.number_input("P4 HI", value=10.0, format="%.1f", step=0.1, key="t_b2_h")}
                else: players[b2] = {"hi": 0.0}

        if st.button("Generate Match & Link", type="primary", use_container_width=True):
            if not match_name or any(not p.strip() for p in players.keys()):
                st.error("Please fill in the Match Name and all Player Names.")
            else:
                new_id = uuid.uuid4().hex[:8]
                new_data = {
                    "id": new_id,
                    "setup": {
                        "match_name": match_name,
                        "date": match_date.strftime('%d %b %Y'),
                        "course": selected_course,
                        "tee": selected_tee,
                        "match_type": match_type,
                        "use_handicaps": use_handicaps,
                        "players": players
                    },
                    "outcomes": {},
                    "extra_holes": 0
                }
                save_match_to_db(new_id, new_data)
                st.query_params["match_id"] = new_id
                st.query_params["manage"] = "true"
                st.rerun()
                
    with tab_admin:
        st.header("Global Allowances")
        c1, c2, c3 = st.columns(3)
        with c1: st.session_state["allowances"]["Singles"] = int(st.number_input("Singles (%)", value=st.session_state["allowances"]["Singles"], step=1))
        with c2: st.session_state["allowances"]["Fourball"] = int(st.number_input("Fourball (%)", value=st.session_state["allowances"]["Fourball"], step=1))
        with c3: st.session_state["allowances"]["Foursomes"] = int(st.number_input("Foursomes (%)", value=st.session_state["allowances"]["Foursomes"], step=1))
        
        st.divider()
        st.header("Course Management")
        
        with st.expander("✏️ Manage Existing Courses"):
            if st.session_state["courses"]:
                edit_course = st.selectbox("Select Course to Edit", list(st.session_state["courses"].keys()))
                course_dict = st.session_state["courses"][edit_course]
                
                edit_tee = st.selectbox("Select Tee", list(course_dict["tees"].keys()))
                tee_dict = course_dict["tees"][edit_tee]
                
                colA, colB, colC = st.columns(3)
                with colA: new_par = st.number_input("Course Par", value=int(tee_dict["par"]), step=1, key="edit_par")
                with colB: new_rating = st.number_input("Rating (CR)", value=float(tee_dict["rating"]), step=0.1, format="%.1f", key="edit_cr")
                with colC: new_slope = st.number_input("Slope", value=int(tee_dict["slope"]), step=1, key="edit_slope")
                
                st.write("**Hole Data**")
                df_existing = pd.DataFrame(course_dict["holes"]).rename(columns={"hole": "Hole", "par": "Par", "index": "Index"})
                edited_df = st.data_editor(df_existing, hide_index=True, use_container_width=True, key="edit_df")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Save Course Updates", type="primary", use_container_width=True):
                        st.session_state["courses"][edit_course]["tees"][edit_tee] = {"rating": new_rating, "slope": new_slope, "par": new_par}
                        holes_list = [{"hole": int(row["Hole"]), "par": int(row["Par"]), "index": int(row["Index"])} for _, row in edited_df.iterrows()]
                        st.session_state["courses"][edit_course]["holes"] = holes_list
                        st.success("Course updated!")
                with col2:
                    if st.button("❌ Delete Course", type="secondary", use_container_width=True):
                        del st.session_state["courses"][edit_course]
                        st.rerun()
            else:
                st.info("No courses loaded.")

        with st.expander("➕ Add New Course", expanded=False):
            new_course_name = st.text_input("New Course Name")
            new_tee_name = st.text_input("New Tee Name (e.g. White, Blue)")
            colA, colB, colC = st.columns(3)
            with colA: n_par = st.number_input("New Course Par", value=72, step=1)
            with colB: n_rating = st.number_input("New Course Rating (CR)", value=72.0, step=0.1, format="%.1f")
            with colC: n_slope = st.number_input("New Slope", value=125, step=1)
            
            st.write("Enter Hole Data (Par & Index):")
            df_holes = pd.DataFrame({"Hole": range(1, 19), "Par": [4]*18, "Index": range(1, 19)})
            new_edited_df = st.data_editor(df_holes, hide_index=True, use_container_width=True, key="new_df")
            
            if st.button("Save New Course", type="primary"):
                if new_course_name and new_tee_name:
                    if new_course_name not in st.session_state["courses"]:
                        st.session_state["courses"][new_course_name] = {"tees": {}, "holes": []}
                    st.session_state["courses"][new_course_name]["tees"][new_tee_name] = {"rating": n_rating, "slope": n_slope, "par": n_par}
                    holes_list = [{"hole": int(row["Hole"]), "par": int(row["Par"]), "index": int(row["Index"])} for _, row in new_edited_df.iterrows()]
                    st.session_state["courses"][new_course_name]["holes"] = holes_list
                    st.success(f"{new_course_name} saved successfully!")
                else:
                    st.error("Please provide both Course Name and Tee Name.")
