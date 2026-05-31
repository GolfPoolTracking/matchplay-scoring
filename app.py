import streamlit as st
import pandas as pd
import math
import uuid
import datetime

from supabase import create_client, Client

@st.cache_resource
def init_connection():
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

supabase = init_connection()

# --- App Configuration ---
st.set_page_config(page_title="Matchplay Centre", layout="centered")

BASE_URL = "https://matchplay-scoring.streamlit.app"

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

if "db_matches" not in st.session_state:
    st.session_state["db_matches"] = {} # PLACEHOLDER FOR SUPABASE

# --- Helper Functions ---
def calculate_course_handicap(hi, slope, rating, par):
    return whs_round((hi * (slope / 113.0)) + (rating - par))

def allocate_strokes(shots_received, hole_index):
    if shots_received <= 0: return ""
    strokes = shots_received // 18 + (1 if hole_index <= (shots_received % 18) else 0)
    return "*" * strokes

def calculate_shots_received(match):
    setup = match["setup"]
    tee_data = st.session_state["courses"][setup["course"]]["tees"][setup["tee"]]
    allowance_decimal = st.session_state["allowances"][setup["match_type"]] / 100.0
    shots_received = {}
    
    if not setup.get("use_handicaps", True):
        for p in setup["players"]: shots_received[p] = 0
        return shots_received

    if setup["match_type"] in ["Singles", "Fourball"]:
        ch_dict = {p: calculate_course_handicap(data["hi"], tee_data["slope"], tee_data["rating"], tee_data["par"]) for p, data in setup["players"].items()}
        lowest_ch = min(ch_dict.values())
        for p, ch in ch_dict.items():
            shots_received[p] = whs_round((ch - lowest_ch) * allowance_decimal)
    else: # Foursomes
        p_keys = list(setup["players"].keys())
        team_a_ch = calculate_course_handicap(setup["players"][p_keys[0]]["hi"], tee_data["slope"], tee_data["rating"], tee_data["par"]) + \
                    calculate_course_handicap(setup["players"][p_keys[1]]["hi"], tee_data["slope"], tee_data["rating"], tee_data["par"])
        team_b_ch = calculate_course_handicap(setup["players"][p_keys[2]]["hi"], tee_data["slope"], tee_data["rating"], tee_data["par"]) + \
                    calculate_course_handicap(setup["players"][p_keys[3]]["hi"], tee_data["slope"], tee_data["rating"], tee_data["par"])
        
        diff = whs_round(abs(team_a_ch - team_b_ch) * allowance_decimal)
        team_a_name = f"{p_keys[0]} & {p_keys[1]}"
        team_b_name = f"{p_keys[2]} & {p_keys[3]}"
        shots_received[team_a_name] = 0 if team_a_ch <= team_b_ch else diff
        shots_received[team_b_name] = 0 if team_b_ch <= team_a_ch else diff

    return shots_received

# --- Routing Logic ---
query_params = st.query_params
active_match_id = query_params.get("match_id", None)
is_manager = query_params.get("manage", "false").lower() == "true"

if active_match_id and active_match_id in st.session_state["db_matches"]:
    # ==========================================
    # ACTIVE MATCH VIEW (SCORECARD)
    # ==========================================
    match = st.session_state["db_matches"][active_match_id]
    setup = match["setup"]
    course_holes = st.session_state["courses"][setup["course"]]["holes"]
    shots_received = calculate_shots_received(match)
    player_entities = list(shots_received.keys())
    total_holes = 18 + match.get("extra_holes", 0)
    
    if st.button("⬅ Back to Dashboard"):
        st.query_params.clear()
        st.rerun()
    
    st.title(f"⛳ {setup['match_name']}")
    st.caption(f"{setup['date'].strftime('%d %b %Y')} | {setup['course']} | {setup['match_type']}")
    if not is_manager:
        st.info("👁️ **Read-Only Mode:** You are viewing the live public scorecard.")
    
    tab_scorecard, tab_breakdown, tab_manager = st.tabs(["Scorecard", "Handicaps", "Manager Links"])
    
    with tab_scorecard:
        current_match_score = 0
        holes_played = match.get("current_hole", 0)

        # Calculate Overall Status
        for idx in range(total_holes):
            if idx in match["scores"] and idx < holes_played:
                scores = match["scores"][idx]
                net_scores = {}
                for p in player_entities:
                    s = scores.get(p, "NR")
                    if s != "NR":
                        hole_index = course_holes[idx % 18]["index"]
                        stars = len(allocate_strokes(shots_received[p], hole_index))
                        net_scores[p] = s - stars

                if setup["match_type"] == "Fourball":
                    team_a_nets = [net_scores[p] for p in player_entities[:2] if p in net_scores]
                    team_b_nets = [net_scores[p] for p in player_entities[2:] if p in net_scores]
                    if team_a_nets and team_b_nets: 
                        best_a, best_b = min(team_a_nets), min(team_b_nets)
                        if best_a < best_b: current_match_score += 1
                        elif best_b < best_a: current_match_score -= 1
                else: 
                    if len(net_scores) == 2:
                        p1, p2 = player_entities[0], player_entities[1]
                        if net_scores[p1] < net_scores[p2]: current_match_score += 1
                        elif net_scores[p2] < net_scores[p1]: current_match_score -= 1

        # Display Top Status Bar
        st.markdown("---")
        if current_match_score > 0:
            leader = "Team A" if setup["match_type"] != "Singles" else player_entities[0]
            st.markdown(f"<h2 style='text-align: center; color: #2e7d32;'>🏆 {leader} {abs(current_match_score)} Up </h2>", unsafe_allow_html=True)
        elif current_match_score < 0:
            leader = "Team B" if setup["match_type"] != "Singles" else player_entities[1]
            st.markdown(f"<h2 style='text-align: center; color: #1565c0;'>🏆 {leader} {abs(current_match_score)} Up </h2>", unsafe_allow_html=True)
        else:
            st.markdown("<h2 style='text-align: center; color: #ff8f00;'>⚖️ All Square </h2>", unsafe_allow_html=True)
        st.caption(f"<div style='text-align: center;'>Thru {holes_played} holes</div>", unsafe_allow_html=True)
        st.markdown("---")

        # Score Entry UI
        view_all = st.checkbox("View Full Scorecard", value=not is_manager)

        for idx in range(total_holes):
            # Only show completed holes if view_all is checked.
            # If manager, always show the *current* active hole.
            if not view_all and idx != holes_played:
                continue
                
            real_hole_idx = idx % 18
            hole_data = course_holes[real_hole_idx]
            par = hole_data['par']
            
            if idx not in match["scores"]:
                match["scores"][idx] = {p: par for p in player_entities}
            
            is_active_hole = (idx == holes_played)
            expander_title = f"⛳ Hole {idx + 1} | Par {par} | Index {hole_data['index']}"
            if idx < holes_played: expander_title += " ✅"

            with st.expander(expander_title, expanded=(is_active_hole or not view_all)):
                for p in player_entities:
                    asterisks = allocate_strokes(shots_received[p], hole_data["index"])
                    st.markdown(f"**{p}** {asterisks}")
                    
                    c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
                    current_val = match["scores"][idx][p]
                    
                    if is_manager and (is_active_hole or view_all):
                        with c1:
                            if st.button("➖", key=f"dec_{idx}_{p}", use_container_width=True):
                                if isinstance(current_val, int) and current_val > 1:
                                    match["scores"][idx][p] -= 1
                                    st.rerun()
                        with c2:
                            st.markdown(f"<h3 style='text-align:center; margin:0;'>{current_val}</h3>", unsafe_allow_html=True)
                        with c3:
                            if st.button("➕", key=f"inc_{idx}_{p}", use_container_width=True):
                                if current_val == "NR": match["scores"][idx][p] = par
                                else: match["scores"][idx][p] += 1
                                st.rerun()
                        with c4:
                            if st.button("NR", key=f"nr_{idx}_{p}", use_container_width=True):
                                match["scores"][idx][p] = "NR"
                                st.rerun()
                    else:
                        st.markdown(f"<h3 style='text-align:center;'>{current_val}</h3>", unsafe_allow_html=True)
                    
                    if current_val != "NR":
                        net = current_val - len(asterisks)
                        st.caption(f"Net: {net}")
                    st.divider()
                
                # Confirm Button for Manager
                if is_manager and is_active_hole:
                    if st.button(f"✅ Confirm Hole {idx + 1} Scores", type="primary", use_container_width=True):
                        match["current_hole"] = idx + 1
                        # UPDATE SUPABASE HERE in the future
                        st.rerun()

        if is_manager and st.button("➕ Add Extra Hole", use_container_width=True):
            match["extra_holes"] = match.get("extra_holes", 0) + 1
            st.rerun()

    with tab_breakdown:
        st.subheader("Match Parameters")
        st.write(f"**Handicaps Used:** {'Yes' if setup.get('use_handicaps', True) else 'No (Scratch)'}")
        st.write(f"**Allowance:** {st.session_state['allowances'][setup['match_type']]}%")
        
        calc_data = []
        for p, data in setup["players"].items():
            if setup.get("use_handicaps", True):
                calc_data.append({"Player": p, "HI": data["hi"], "Shots Received": shots_received.get(p, 0)})
            else:
                calc_data.append({"Player": p, "HI": "N/A", "Shots Received": 0})
        st.dataframe(pd.DataFrame(calc_data), use_container_width=True)

    with tab_manager:
        if is_manager:
            st.success("You are the Manager of this match.")
            st.write("**Public Link (Read-Only - Send to Group):**")
            st.code(f"{BASE_URL}/?match_id={active_match_id}")
            
            st.write("**Manager Link (Keep Private):**")
            st.code(f"{BASE_URL}/?match_id={active_match_id}&manage=true")
        else:
            st.error("You are in Read-Only mode. Ask the match creator for the manager link to enter scores.")

else:
    # ==========================================
    # HOME DASHBOARD & MATCH CREATION
    # ==========================================
    st.title("🏌️‍♂️ Match Dashboard")
    
    tab_list, tab_create, tab_admin = st.tabs(["Active Matches", "Create New Match", "Admin & Courses"])
    
    with tab_list:
        if not st.session_state["db_matches"]:
            st.info("No matches found in your current browser session. Create one in the next tab!")
        else:
            for m_id, m_data in st.session_state["db_matches"].items():
                with st.container(border=True):
                    st.subheader(m_data["setup"]["match_name"])
                    st.write(f"{m_data['setup']['date'].strftime('%d %b %Y')} | {m_data['setup']['course']} | {m_data['setup']['match_type']}")
                    if st.button("Open as Manager", key=f"open_{m_id}"):
                        st.query_params["match_id"] = m_id
                        st.query_params["manage"] = "true"
                        st.rerun()
                        
    with tab_create:
        st.header("New Match Setup")
        match_name = st.text_input("Match Name", value="")
        match_date = st.date_input("Date", value=datetime.date.today())
        
        c1, c2 = st.columns(2)
        with c1: selected_course = st.selectbox("Select Course", list(st.session_state["courses"].keys()))
        with c2: selected_tee = st.selectbox("Select Tees", list(st.session_state["courses"][selected_course]["tees"].keys()))
        
        c3, c4 = st.columns(2)
        with c3: match_type = st.selectbox("Match Type", ["Singles", "Fourball", "Foursomes"])
        with c4: use_handicaps = st.checkbox("Use Handicaps", value=True)
        
        st.divider()
        st.subheader("Players")
        players = {}
        col1, col2 = st.columns(2)
        
        if match_type == "Singles":
            with col1: 
                p1 = st.text_input("Player 1 Name", value="", key="s_p1_n")
                if use_handicaps: players[p1] = {"hi": st.number_input("Player 1 HI", value=10.0, format="%.1f", step=0.1, key="s_p1_h")}
                else: players[p1] = {"hi": 0.0}
            with col2: 
                p2 = st.text_input("Player 2 Name", value="", key="s_p2_n")
                if use_handicaps: players[p2] = {"hi": st.number_input("Player 2 HI", value=10.0, format="%.1f", step=0.1, key="s_p2_h")}
                else: players[p2] = {"hi": 0.0}
                
        elif match_type in ["Fourball", "Foursomes"]:
            with col1:
                st.write("**Team A**")
                a1 = st.text_input("P1 Name", value="", key="t_a1_n")
                if use_handicaps: players[a1] = {"hi": st.number_input("P1 HI", value=10.0, format="%.1f", step=0.1, key="t_a1_h")}
                else: players[a1] = {"hi": 0.0}
                
                a2 = st.text_input("P2 Name", value="", key="t_a2_n")
                if use_handicaps: players[a2] = {"hi": st.number_input("P2 HI", value=10.0, format="%.1f", step=0.1, key="t_a2_h")}
                else: players[a2] = {"hi": 0.0}
            with col2:
                st.write("**Team B**")
                b1 = st.text_input("P3 Name", value="", key="t_b1_n")
                if use_handicaps: players[b1] = {"hi": st.number_input("P3 HI", value=10.0, format="%.1f", step=0.1, key="t_b1_h")}
                else: players[b1] = {"hi": 0.0}
                
                b2 = st.text_input("P4 Name", value="", key="t_b2_n")
                if use_handicaps: players[b2] = {"hi": st.number_input("P4 HI", value=10.0, format="%.1f", step=0.1, key="t_b2_h")}
                else: players[b2] = {"hi": 0.0}

        if st.button("Generate Match & Link", type="primary", use_container_width=True):
            # Form validation
            if not match_name or any(not p.strip() for p in players.keys()):
                st.error("Please fill in the Match Name and all Player Names.")
            else:
                new_id = uuid.uuid4().hex[:8]
                st.session_state["db_matches"][new_id] = {
                    "id": new_id,
                    "setup": {
                        "match_name": match_name, "date": match_date, "course": selected_course,
                        "tee": selected_tee, "match_type": match_type, "use_handicaps": use_handicaps,
                        "players": players
                    },
                    "scores": {}, "current_hole": 0, "extra_holes": 0
                }
                # PUSH TO SUPABASE HERE in the future
                st.query_params["match_id"] = new_id
                st.query_params["manage"] = "true"
                st.rerun()

    with tab_admin:
        st.header("Global Allowances")
        c1, c2, c3 = st.columns(3)
        with c1: st.session_state["allowances"]["Singles"] = int(st.number_input("Singles (%)", value=st.session_state["allowances"]["Singles"], step=1))
        with c2: st.session_state["allowances"]["Fourball"] = int(st.number_input("Fourball (%)", value=st.session_state["allowances"]["Fourball"], step=1))
        with c3: st.session_state["allowances"]["Foursomes"] = int(st.number_input("Foursomes (%)", value=st.session_state["allowances"]["Foursomes"], step=1))
