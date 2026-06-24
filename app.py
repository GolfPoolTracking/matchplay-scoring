import streamlit as st
import pandas as pd
import math
import uuid
import datetime
import streamlit.components.v1 as components
from supabase import create_client, Client

#Ping to keep app and DB alive
if st.query_params.get("view") == "ping":
    st.write("Server is awake and ready! 🟢")
    st.stop()

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
    team_display = {"A": "", "B": ""}
    
    if "team_a" in setup and "team_b" in setup:
        p_A = setup["team_a"]
        p_B = setup["team_b"]
    else:
        p_keys = list(setup["players"].keys())
        if setup["match_type"] == "Singles":
            p_A = [p_keys[0]] if len(p_keys) > 0 else ["P1"]
            p_B = [p_keys[1]] if len(p_keys) > 1 else ["P2"]
        else:
            p_A = [p_keys[0], p_keys[1]] if len(p_keys) > 1 else ["P1", "P2"]
            p_B = [p_keys[2], p_keys[3]] if len(p_keys) > 3 else ["P3", "P4"]
            
    if setup["match_type"] == "Singles":
        team_names["A"], team_names["B"] = p_A[0], p_B[0]
        
        if not setup.get("use_handicaps", True):
            team_display["A"], team_display["B"] = team_names["A"], team_names["B"]
            return {team_names["A"]: 0, team_names["B"]: 0}, team_names, team_display

        ch_dict = {p: calculate_course_handicap(data["hi"], tee_data["slope"], tee_data["rating"], tee_data["par"]) for p, data in setup["players"].items()}
        lowest_ch = min(ch_dict.values())
        for p, ch in ch_dict.items():
            shots_received[p] = whs_round((ch - lowest_ch) * allowance_decimal)
            
        sh_a = shots_received.get(team_names["A"], 0)
        sh_b = shots_received.get(team_names["B"], 0)
        team_display["A"] = f"{team_names['A']} ({sh_a} Shots)" if sh_a > 0 else team_names["A"]
        team_display["B"] = f"{team_names['B']} ({sh_b} Shots)" if sh_b > 0 else team_names["B"]

    elif setup["match_type"] == "Fourball":
        team_names["A"] = f"{p_A[0]} & {p_A[1]}"
        team_names["B"] = f"{p_B[0]} & {p_B[1]}"
        
        if not setup.get("use_handicaps", True):
            shots_received = {p: 0 for p in p_A + p_B}
            team_display["A"], team_display["B"] = team_names["A"], team_names["B"]
            return shots_received, team_names, team_display

        ch_dict = {p: calculate_course_handicap(setup["players"][p]["hi"], tee_data["slope"], tee_data["rating"], tee_data["par"]) for p in p_A + p_B if p in setup["players"]}
        if not ch_dict:
            return {}, team_names, team_names
            
        lowest_ch = min(ch_dict.values())
        for p, ch in ch_dict.items():
            shots_received[p] = whs_round((ch - lowest_ch) * allowance_decimal)
            
        disp_a1 = f"{p_A[0]} ({shots_received.get(p_A[0],0)})" if shots_received.get(p_A[0],0) > 0 else p_A[0]
        disp_a2 = f"{p_A[1]} ({shots_received.get(p_A[1],0)})" if shots_received.get(p_A[1],0) > 0 else p_A[1]
        team_display["A"] = f"{disp_a1} & {disp_a2}"
        
        disp_b1 = f"{p_B[0]} ({shots_received.get(p_B[0],0)})" if shots_received.get(p_B[0],0) > 0 else p_B[0]
        disp_b2 = f"{p_B[1]} ({shots_received.get(p_B[1],0)})" if shots_received.get(p_B[1],0) > 0 else p_B[1]
        team_display["B"] = f"{disp_b1} & {disp_b2}"

    else: # Foursomes
        team_names["A"] = f"{p_A[0]} & {p_A[1]}"
        team_names["B"] = f"{p_B[0]} & {p_B[1]}"
        
        if not setup.get("use_handicaps", True):
            team_display["A"], team_display["B"] = team_names["A"], team_names["B"]
            return {team_names["A"]: 0, team_names["B"]: 0}, team_names, team_display

        if p_A[0] not in setup["players"]: return {}, team_names, team_names
        
        ch_A = calculate_course_handicap(setup["players"][p_A[0]]["hi"], tee_data["slope"], tee_data["rating"], tee_data["par"]) + \
               calculate_course_handicap(setup["players"][p_A[1]]["hi"], tee_data["slope"], tee_data["rating"], tee_data["par"])
        ch_B = calculate_course_handicap(setup["players"][p_B[0]]["hi"], tee_data["slope"], tee_data["rating"], tee_data["par"]) + \
               calculate_course_handicap(setup["players"][p_B[1]]["hi"], tee_data["slope"], tee_data["rating"], tee_data["par"])
        
        diff = whs_round(abs(ch_A - ch_B) * allowance_decimal)
        shots_received[team_names["A"]] = 0 if ch_A <= ch_B else diff
        shots_received[team_names["B"]] = 0 if ch_B <= ch_A else diff
        
        sh_a = shots_received[team_names["A"]]
        sh_b = shots_received[team_names["B"]]
        team_display["A"] = f"{team_names['A']} ({sh_a} Shots)" if sh_a > 0 else team_names["A"]
        team_display["B"] = f"{team_names['B']} ({sh_b} Shots)" if sh_b > 0 else team_names["B"]

    return shots_received, team_names, team_display

def get_match_status(outcomes, total_holes):
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
COLOR_A = "#10b981" 
COLOR_B = "#6366f1" 
COLOR_H = "#9ca3af"

def render_auto_refresh():
    st.markdown(f"""
    <div style="text-align: center; color: {COLOR_A}; font-size: 14px; font-weight: bold; margin-bottom: 25px; margin-top: 10px; background-color: {COLOR_A}22; padding: 8px; border-radius: 8px;">
        🔴 LIVE: Auto-refreshing in <span id="timer-span">120</span>s
    </div>
    """, unsafe_allow_html=True)

    components.html(
        """
        <script>
        if (window.parent && window.parent.document) {
            if (window.parent.liveRefreshInterval) {
                clearInterval(window.parent.liveRefreshInterval);
            }
            let time = 120;
            window.parent.liveRefreshInterval = setInterval(function() {
                time--;
                let span = window.parent.document.getElementById('timer-span');
                if (span) {
                    span.innerText = time;
                }
                if (time <= 0) {
                    clearInterval(window.parent.liveRefreshInterval);
                    window.parent.location.reload();
                }
            }, 1000);
        }
        </script>
        """,
        height=0,
        width=0
    )

def render_live_card(match_data, team_display, total_holes):
    setup = match_data["setup"]
    outcomes = match_data.get("outcomes", {})
    
    leader, amount, holes_played, match_over, final_str = get_match_status(outcomes, total_holes)
    
    # Adapts to Light/Dark Mode automatically
    bg_a, text_a = "transparent", "var(--text-color)"
    bg_b, text_b = "transparent", "var(--text-color)"
    shape_a = "none"
    shape_b = "none"
    border_a = "none"
    border_b = "none"
    
    name_a_html = f"<span style='display:inline-block; width:10px; height:10px; border-radius:50%; background-color:{COLOR_A}; margin-right:8px;'></span>{team_display['A']}"
    name_b_html = f"{team_display['B']}<span style='display:inline-block; width:10px; height:10px; border-radius:50%; background-color:{COLOR_B}; margin-left:8px;'></span>"
    
    if leader == "A":
        bg_a, text_a = COLOR_A, "white"
        shape_a = "polygon(0% 0%, 92% 0%, 100% 50%, 92% 100%, 0% 100%)"
        border_a = f"1px solid {COLOR_A}"
        status_text = f"<span style='color: {COLOR_A};'>{final_str}</span>"
        name_a_html = team_display['A'] 
    elif leader == "B":
        bg_b, text_b = COLOR_B, "white"
        shape_b = "polygon(8% 0%, 100% 0%, 100% 100%, 8% 100%, 0% 50%)"
        border_b = f"1px solid {COLOR_B}"
        status_text = f"<span style='color: {COLOR_B};'>{final_str}</span>"
        name_b_html = team_display['B'] 
    else:
        status_text = "<span style='opacity: 0.8;'>ALL SQ</span>"

    circles_html = ""
    for i in range(1, holes_played + 1):
        res = outcomes.get(str(i))
        if res == "A":
            circles_html += f"<div style='width: 24px; height: 24px; border-radius: 50%; background: {COLOR_A}; color: white; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: bold;'>{i}</div>"
        elif res == "B":
            circles_html += f"<div style='width: 24px; height: 24px; border-radius: 50%; background: {COLOR_B}; color: white; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: bold;'>{i}</div>"
        elif res == "H":
            circles_html += f"<div style='width: 24px; height: 24px; border-radius: 50%; background: {COLOR_H}; color: white; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: bold;'>{i}</div>"

    if match_over:
        subtext = "FINAL"
    elif holes_played == 0:
        subtext = "NOT STARTED"
    else:
        subtext = f"THRU {holes_played}"

    html_string = f"""
    <div style="background: var(--background-color); border: 1px solid var(--secondary-background-color); border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); padding: 20px; margin-bottom: 20px; font-family: sans-serif;">
        <div style="display: flex; align-items: stretch; justify-content: space-between; min-height: 65px; border-bottom: 1px solid var(--secondary-background-color); padding-bottom: 15px; margin-bottom: 15px;">
            <div style="flex: 1; background: {bg_a}; color: {text_a}; display: flex; align-items: center; justify-content: flex-start; padding: 10px 15px; border-radius: 6px 0 0 6px; clip-path: {shape_a}; border: {border_a};">
                <div style="font-weight: bold; font-size: 13px; line-height: 1.4;">{name_a_html}</div>
            </div>
            <div style="width: 90px; text-align: center; display: flex; flex-direction: column; justify-content: center; flex-shrink: 0; padding: 0 5px;">
                <span style="font-size: 11px; opacity: 0.6; text-transform: uppercase; margin-bottom: 2px; font-weight: bold;">{subtext}</span>
                <span style="font-size: 18px; font-weight: 800;">{status_text}</span>
            </div>
            <div style="flex: 1; background: {bg_b}; color: {text_b}; display: flex; align-items: center; justify-content: flex-end; padding: 10px 15px; border-radius: 0 6px 6px 0; clip-path: {shape_b}; border: {border_b}; text-align: right;">
                <div style="font-weight: bold; font-size: 13px; line-height: 1.4;">{name_b_html}</div>
            </div>
        </div>
        <div style="display: flex; gap: 8px; flex-wrap: wrap; justify-content: center;">
            {circles_html}
        </div>
    </div>
    """
    st.html(html_string.replace('\n', ''))

def render_compact_grid(outcomes, total_holes, active_match_id, current_hole, holes_format):
    def get_color(hole_val):
        if hole_val == "A": return COLOR_A, "white", "none"
        if hole_val == "B": return COLOR_B, "white", "none"
        if hole_val == "H": return COLOR_H, "white", "none"
        return "transparent", "var(--text-color)", "1px solid var(--secondary-background-color)"

    html = """
    <style>
    .hole-box { transition: transform 0.1s, opacity 0.1s; cursor: pointer; }
    .hole-box:hover { transform: scale(1.1); opacity: 0.8; }
    </style>
    <div style='overflow-x: auto; padding-bottom: 10px; margin-bottom: 20px;'>
    <div style='display: flex; flex-direction: column; gap: 8px; width: max-content; font-family: sans-serif; margin: 0 auto;'>
    """
    
    def make_row(start, end):
        if start > total_holes: return ""
        actual_end = min(end, total_holes)
        row_html = "<div style='display: flex; gap: 6px;'>"
        for i in range(start, actual_end + 1):
            val = outcomes.get(str(i), "Not Played")
            bg, txt, border = get_color(val)
            
            # Subtle highlight ring for active hole
            ring = "box-shadow: 0 0 0 2px var(--primary-color);" if i == current_hole else ""
            opacity = "0.5" if val == "Not Played" and i != current_hole else "1"
            
            row_html += f"<a href='?match_id={active_match_id}&manage=true&hole={i}&tab_jump=Score%20Entry' target='_self' style='text-decoration: none;'>"
            row_html += f"<div class='hole-box' style='width: 32px; height: 32px; border-radius: 6px; background: {bg}; color: {txt}; display: flex; align-items: center; justify-content: center; font-size: 13px; font-weight: bold; border: {border}; opacity: {opacity}; {ring}'>{i}</div>"
            row_html += "</a>"
        row_html += "</div>"
        return row_html

    if holes_format == 36:
        html += make_row(1, 18)
        html += make_row(19, 36)
        if total_holes > 36:
            html += make_row(37, total_holes)
    else:
        html += make_row(1, 9)
        html += make_row(10, 18)
        if total_holes > 18:
            html += make_row(19, total_holes)

    html += "</div></div>"
    return html


# --- Routing Logic ---
query_params = st.query_params
active_match_id = query_params.get("match_id", None)
is_manager = query_params.get("manage", "false").lower() == "true"

if active_match_id and active_match_id in st.session_state["db_matches"]:
    match_data = st.session_state["db_matches"][active_match_id]
    setup = match_data["setup"]
    course_holes = st.session_state["courses"][setup["course"]]["holes"]
    holes_format = setup.get("holes_format", 18)
    total_holes = holes_format + match_data.get("extra_holes", 0)
    
    shots_received, team_names, team_display = generate_shots_data(match_data)
    
    if not is_manager:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("🔄 Refresh Scoreboard", use_container_width=True):
                st.rerun()
                
        st.markdown(f"<h3 style='text-align: center; margin-top: 10px; margin-bottom: 0;'>{setup['match_name']}</h3>", unsafe_allow_html=True)
        st.markdown(f"<p style='text-align: center; opacity: 0.7; margin-bottom: 20px;'>{setup['course']} • {setup['match_type']}</p>", unsafe_allow_html=True)
        
        render_auto_refresh()
        render_live_card(match_data, team_display, total_holes)

    else:
        st.button("⬅ Back to Menu", on_click=lambda: st.query_params.clear())
        
        st.markdown(f"<h3 style='text-align: center; margin-top: 5px; margin-bottom: 0px;'>⚙️ {setup['match_name']}</h3>", unsafe_allow_html=True)
        st.markdown(f"<p style='text-align: center; opacity: 0.7; margin-bottom: 20px; font-size: 14px;'>{setup['course']} | {setup['match_type']}</p>", unsafe_allow_html=True)
        
        tab_options = ["Scoreboard", "Score Entry", "Shots Allocation", "Edit Match", "Share Links"]
        
        if "manager_active_tab" not in st.session_state:
            st.session_state.manager_active_tab = "Score Entry"
            
        if "tab_jump" in st.query_params:
            st.session_state.manager_active_tab = st.query_params["tab_jump"]
            if "tab_jump" in st.query_params:
                del st.query_params["tab_jump"]

        active_tab = st.radio(
            "Manager Navigation", 
            tab_options, 
            index=tab_options.index(st.session_state.manager_active_tab) if st.session_state.manager_active_tab in tab_options else 1,
            horizontal=True, 
            label_visibility="collapsed"
        )
        st.session_state.manager_active_tab = active_tab
        st.divider()

        if active_tab == "Scoreboard":
            render_auto_refresh()
            render_live_card(match_data, team_display, total_holes)
            
        elif active_tab == "Score Entry":
            leader, amount, holes_played, match_over, final_str = get_match_status(match_data.get("outcomes", {}), total_holes)
            state_key = f"entry_hole_{active_match_id}"

            if "hole" in st.query_params:
                try:
                    jump_hole = int(st.query_params["hole"])
                    if 1 <= jump_hole <= total_holes:
                        st.session_state[state_key] = jump_hole
                except ValueError:
                    pass
                if "hole" in st.query_params:
                    del st.query_params["hole"]

            if state_key not in st.session_state:
                if match_over:
                    st.session_state[state_key] = holes_played
                else:
                    st.session_state[state_key] = min(holes_played + 1, total_holes)

            curr_hole = st.session_state[state_key]

            if match_over:
                winner = team_names[leader] if leader in team_names else "Match"
                st.success(f"🎉 **Match Finished!** {winner} wins {final_str}")
            
            st.html(render_compact_grid(match_data.get("outcomes", {}), total_holes, active_match_id, curr_hole, holes_format))

            st.divider()
            c1, c2, c3 = st.columns([1, 2, 1])
            with c1:
                if st.button("⬅ Prev", disabled=(curr_hole <= 1), use_container_width=True):
                    st.session_state[state_key] -= 1
                    st.rerun()
            with c2:
                st.markdown(f"<h4 style='text-align:center; margin-top:5px;'>Hole {curr_hole}</h4>", unsafe_allow_html=True)
            with c3:
                disable_next = (curr_hole >= total_holes) or (match_over and curr_hole >= holes_played)
                if st.button("Next ➡", disabled=disable_next, use_container_width=True):
                    st.session_state[state_key] += 1
                    st.rerun()

            h_idx = curr_hole - 1
            real_hole_idx = h_idx % 18
            h_data = course_holes[real_hole_idx]
            str_h = str(curr_hole)
            
            current_val = match_data["outcomes"].get(str_h, "Not Played")

            with st.container(border=True):
                st.markdown(f"<div style='text-align:center; opacity:0.6; font-size:14px; margin-bottom:15px;'>Par {h_data['par']} &nbsp;|&nbsp; Index {h_data['index']}</div>", unsafe_allow_html=True)
                
                status_map = {
                    "Not Played": "⚪ Not Played",
                    "A": f"🟢 {team_names['A']} Won",
                    "H": "🔘 Halved",
                    "B": f"🟣 {team_names['B']} Won"
                }
                
                bg_color = {"Not Played": "transparent", "A": f"{COLOR_A}22", "H": "var(--secondary-background-color)", "B": f"{COLOR_B}22"}.get(current_val, "transparent")
                border_color = {"Not Played": "var(--secondary-background-color)", "A": COLOR_A, "H": "var(--secondary-background-color)", "B": COLOR_B}.get(current_val, "var(--secondary-background-color)")
                text_color = {"Not Played": "var(--text-color)", "A": COLOR_A, "H": "var(--text-color)", "B": COLOR_B}.get(current_val, "var(--text-color)")
                
                st.markdown(f"<div style='text-align:center; font-size:16px; font-weight:bold; margin-bottom:20px; padding:12px; background-color:{bg_color}; border: 1px solid {border_color}; color:{text_color}; border-radius:8px;'>Current: {status_map[current_val]}</div>", unsafe_allow_html=True)

                def update_and_advance(val):
                    if val == "Not Played":
                        match_data["outcomes"].pop(str_h, None)
                    else:
                        match_data["outcomes"][str_h] = val
                        
                    save_match_to_db(active_match_id, match_data)
                    l, a, hp, mo, fs = get_match_status(match_data["outcomes"], total_holes)
                    
                    if val != "Not Played" and not mo and curr_hole < total_holes:
                        st.session_state[state_key] = curr_hole + 1

                colA, colH, colB = st.columns(3)
                with colA:
                    if st.button(f"🟢 {team_names['A']} Win", use_container_width=True):
                        update_and_advance("A")
                        st.rerun()
                with colH:
                    if st.button("🔘 Halved", use_container_width=True):
                        update_and_advance("H")
                        st.rerun()
                with colB:
                    if st.button(f"🟣 {team_names['B']} Win", use_container_width=True):
                        update_and_advance("B")
                        st.rerun()
                
                st.write("")
                if st.button("⚪ Clear Result", use_container_width=True):
                    update_and_advance("Not Played")
                    st.rerun()

            if not match_over and st.button("➕ Add Extra Hole", use_container_width=True):
                match_data["extra_holes"] = match_data.get("extra_holes", 0) + 1
                save_match_to_db(active_match_id, match_data)
                st.rerun()

        elif active_tab == "Shots Allocation":
            st.header("Handicap Allocation")
            st.write(f"**Format:** {setup['match_type']} ({st.session_state['allowances'][setup['match_type']]}% Allowance)")
            
            grid_data = []
            for idx in range(total_holes):
                real_idx = idx % 18
                h_data = course_holes[real_idx]
                row = {"Hole": idx + 1, "Par": h_data['par'], "Index": h_data['index']}
                
                for p_name, total_shots in shots_received.items():
                    strokes_on_this_hole = allocate_strokes(total_shots, h_data['index'])
                    row[p_name] = strokes_on_this_hole if strokes_on_this_hole > 0 else "-"
                    
                grid_data.append(row)
                
            st.dataframe(pd.DataFrame(grid_data).set_index("Hole"), use_container_width=True)
            
            st.write("**Player Data Used:**")
            raw_data = []
            for p, data in setup["players"].items():
                raw_data.append({"Player": p, "HI": f"{float(data['hi']):.1f}"})
            st.dataframe(pd.DataFrame(raw_data), hide_index=True)

        elif active_tab == "Edit Match":
            st.header("Edit Match Parameters")
            st.warning("Note: Changing the course or handicap details will automatically recalculate shots for all holes.")
            
            with st.form("edit_match_form"):
                new_name = st.text_input("Match Name", value=setup["match_name"])
                
                c1, c2, c3 = st.columns([2, 1, 1])
                c_list = list(st.session_state["courses"].keys())
                c_idx = c_list.index(setup["course"]) if setup["course"] in c_list else 0
                with c1: 
                    new_course = st.selectbox("Course", c_list, index=c_idx)
                
                t_list = list(st.session_state["courses"][new_course]["tees"].keys())
                t_idx = t_list.index(setup["tee"]) if setup["tee"] in t_list else 0
                with c2: 
                    new_tee = st.selectbox("Tees", t_list, index=t_idx)
                with c3:
                    new_format = st.selectbox("Format", [18, 36], format_func=lambda x: f"{x} Holes", index=[18, 36].index(holes_format))
                    
                new_uh = st.checkbox("Use Handicaps", value=setup.get("use_handicaps", True))
                
                st.divider()
                
                new_players = {}
                if setup["match_type"] == "Singles":
                    p_A = setup.get("team_a", [list(setup["players"].keys())[0]])
                    p_B = setup.get("team_b", [list(setup["players"].keys())[1]])
                    
                    st.write("**Player Setup**")
                    col1, col2 = st.columns(2)
                    with col1: 
                        e_a1 = st.text_input("Player 1 Name", value=p_A[0])
                        e_hi_a1 = st.number_input("Player 1 HI", value=float(setup["players"][p_A[0]]["hi"]), format="%.1f", step=0.1)
                    with col2: 
                        e_b1 = st.text_input("Player 2 Name", value=p_B[0])
                        e_hi_b1 = st.number_input("Player 2 HI", value=float(setup["players"][p_B[0]]["hi"]), format="%.1f", step=0.1)
                        
                    if st.form_submit_button("💾 Save Changes", type="primary", use_container_width=True):
                        new_players = {e_a1: {"hi": round(e_hi_a1, 1)}, e_b1: {"hi": round(e_hi_b1, 1)}}
                        match_data["setup"]["match_name"] = new_name
                        match_data["setup"]["course"] = new_course
                        match_data["setup"]["tee"] = new_tee
                        match_data["setup"]["holes_format"] = new_format
                        match_data["setup"]["use_handicaps"] = new_uh
                        match_data["setup"]["players"] = new_players
                        match_data["setup"]["team_a"] = [e_a1]
                        match_data["setup"]["team_b"] = [e_b1]
                        
                        save_match_to_db(active_match_id, match_data)
                        st.success("Match updated successfully!")
                        st.rerun()
                else:
                    p_A = setup.get("team_a", list(setup["players"].keys())[0:2])
                    p_B = setup.get("team_b", list(setup["players"].keys())[2:4])
                    
                    st.write("**Team A**")
                    colA1, colA2 = st.columns(2)
                    with colA1:
                        e_a1 = st.text_input("P1 Name", value=p_A[0])
                        e_hi_a1 = st.number_input("P1 HI", value=float(setup["players"][p_A[0]]["hi"]), format="%.1f", step=0.1)
                    with colA2:
                        e_a2 = st.text_input("P2 Name", value=p_A[1])
                        e_hi_a2 = st.number_input("P2 HI", value=float(setup["players"][p_A[1]]["hi"]), format="%.1f", step=0.1)
                        
                    st.write("**Team B**")
                    colB1, colB2 = st.columns(2)
                    with colB1:
                        e_b1 = st.text_input("P3 Name", value=p_B[0])
                        e_hi_b1 = st.number_input("P3 HI", value=float(setup["players"][p_B[0]]["hi"]), format="%.1f", step=0.1)
                    with colB2:
                        e_b2 = st.text_input("P4 Name", value=p_B[1])
                        e_hi_b2 = st.number_input("P4 HI", value=float(setup["players"][p_B[1]]["hi"]), format="%.1f", step=0.1)
                        
                    if st.form_submit_button("💾 Save Changes", type="primary", use_container_width=True):
                        new_players = {
                            e_a1: {"hi": round(e_hi_a1, 1)}, e_a2: {"hi": round(e_hi_a2, 1)},
                            e_b1: {"hi": round(e_hi_b1, 1)}, e_b2: {"hi": round(e_hi_b2, 1)}
                        }
                        match_data["setup"]["match_name"] = new_name
                        match_data["setup"]["course"] = new_course
                        match_data["setup"]["tee"] = new_tee
                        match_data["setup"]["holes_format"] = new_format
                        match_data["setup"]["use_handicaps"] = new_uh
                        match_data["setup"]["players"] = new_players
                        match_data["setup"]["team_a"] = [e_a1, e_a2]
                        match_data["setup"]["team_b"] = [e_b1, e_b2]
                        
                        save_match_to_db(active_match_id, match_data)
                        st.success("Match updated successfully!")
                        st.rerun()

            st.write("<br><br>", unsafe_allow_html=True)
            st.divider()
            st.subheader("Danger Zone")
            st.error("Deleting a match is permanent and cannot be undone.")
            confirm_del = st.checkbox("I confirm I want to permanently delete this match.")
            if st.button("🗑️ Delete Match", disabled=not confirm_del, use_container_width=True):
                try:
                    supabase.table("matchplay_sessions").delete().eq("id", active_match_id).execute()
                    del st.session_state["db_matches"][active_match_id]
                except Exception as e:
                    pass
                st.query_params.clear()
                st.rerun()

        elif active_tab == "Share Links":
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
            show_archived = st.toggle("📂 Show Archived (Completed) Matches", value=False)
            st.divider()
            
            displayed_count = 0
            for m_id, m_data in st.session_state["db_matches"].items():
                # Dynamically calculate if match is over
                fmt_holes = m_data["setup"].get("holes_format", 18)
                tot_holes = fmt_holes + m_data.get("extra_holes", 0)
                _, _, _, match_over, _ = get_match_status(m_data.get("outcomes", {}), tot_holes)
                
                # Check filter condition
                if (show_archived and match_over) or (not show_archived and not match_over):
                    displayed_count += 1
                    with st.container(border=True):
                        st.subheader(m_data["setup"]["match_name"])
                        st.write(f"{m_data['setup']['date']} | {m_data['setup']['course']} ({fmt_holes} Holes) | {m_data['setup']['match_type']}")
                        if st.button("Manage Match", key=f"open_{m_id}"):
                            st.query_params["match_id"] = m_id
                            st.query_params["manage"] = "true"
                            st.rerun()
            
            if displayed_count == 0:
                if show_archived:
                    st.info("No archived matches found.")
                else:
                    st.info("No active matches found. Enjoy your round or create a new one in the next tab!")

    with tab_create:
        st.header("New Match Setup")
        match_name = st.text_input("Match Name", placeholder="e.g. Sunday Final")
        match_date = st.date_input("Date", value=datetime.date.today())
        
        c1, c2, c3 = st.columns([2, 1, 1])
        with c1: selected_course = st.selectbox("Select Course", list(st.session_state["courses"].keys()))
        with c2: selected_tee = st.selectbox("Select Tees", list(st.session_state["courses"][selected_course]["tees"].keys()))
        with c3: holes_format = st.selectbox("Format", [18, 36], format_func=lambda x: f"{x} Holes")
        
        c4, c5 = st.columns(2)
        with c4: match_type = st.selectbox("Match Type", ["Singles", "Fourball", "Foursomes"])
        with c5: use_handicaps = st.checkbox("Use Handicaps", value=True)
        
        st.divider()
        st.subheader("Players & Handicaps")
        players = {}
        
        if match_type == "Singles":
            col1, col2 = st.columns(2)
            with col1: 
                p1 = st.text_input("Player 1 Name", key="s_p1_n")
                if use_handicaps: players[p1] = {"hi": round(st.number_input("Player 1 HI", value=10.0, format="%.1f", step=0.1, key="s_p1_h"), 1)}
                else: players[p1] = {"hi": 0.0}
            with col2: 
                p2 = st.text_input("Player 2 Name", key="s_p2_n")
                if use_handicaps: players[p2] = {"hi": round(st.number_input("Player 2 HI", value=10.0, format="%.1f", step=0.1, key="s_p2_h"), 1)}
                else: players[p2] = {"hi": 0.0}
                
            if st.button("Generate Match & Link", type="primary", use_container_width=True):
                if not match_name or not p1.strip() or not p2.strip():
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
                            "holes_format": holes_format,
                            "match_type": match_type,
                            "use_handicaps": use_handicaps,
                            "players": players,
                            "team_a": [p1],
                            "team_b": [p2]
                        },
                        "outcomes": {},
                        "extra_holes": 0
                    }
                    save_match_to_db(new_id, new_data)
                    st.query_params["match_id"] = new_id
                    st.query_params["manage"] = "true"
                    st.rerun()
                
        elif match_type in ["Fourball", "Foursomes"]:
            st.write("**Team A**")
            colA1, colA2 = st.columns(2)
            with colA1:
                a1 = st.text_input("P1 Name", key="t_a1_n")
                if use_handicaps: players[a1] = {"hi": round(st.number_input("P1 HI", value=10.0, format="%.1f", step=0.1, key="t_a1_h"), 1)}
                else: players[a1] = {"hi": 0.0}
            with colA2:
                a2 = st.text_input("P2 Name", key="t_a2_n")
                if use_handicaps: players[a2] = {"hi": round(st.number_input("P2 HI", value=10.0, format="%.1f", step=0.1, key="t_a2_h"), 1)}
                else: players[a2] = {"hi": 0.0}
                
            st.write("**Team B**")
            colB1, colB2 = st.columns(2)
            with colB1:
                b1 = st.text_input("P3 Name", key="t_b1_n")
                if use_handicaps: players[b1] = {"hi": round(st.number_input("P3 HI", value=10.0, format="%.1f", step=0.1, key="t_b1_h"), 1)}
                else: players[b1] = {"hi": 0.0}
            with colB2:
                b2 = st.text_input("P4 Name", key="t_b2_n")
                if use_handicaps: players[b2] = {"hi": round(st.number_input("P4 HI", value=10.0, format="%.1f", step=0.1, key="t_b2_h"), 1)}
                else: players[b2] = {"hi": 0.0}

            if st.button("Generate Match & Link", type="primary", use_container_width=True):
                if not match_name or any(not p.strip() for p in [a1, a2, b1, b2]):
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
                            "holes_format": holes_format,
                            "match_type": match_type,
                            "use_handicaps": use_handicaps,
                            "players": players,
                            "team_a": [a1, a2],
                            "team_b": [b1, b2]
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
