import streamlit as st
import pandas as pd
import math

# --- App Configuration ---
st.set_page_config(page_title="MatchPlay Tracker", layout="centered")

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
    st.session_state["allowances"] = {
        "Singles": 100,
        "Fourball": 90,
        "Foursomes": 50
    }

if "extra_holes" not in st.session_state:
    st.session_state["extra_holes"] = 0

if "match_scores" not in st.session_state:
    st.session_state["match_scores"] = {}

# --- Helper Functions ---
def calculate_course_handicap(hi, slope, rating, par):
    return round((hi * (slope / 113.0)) + (rating - par))

def allocate_strokes(shots_received, hole_index):
    strokes = 0
    if shots_received > 0:
        strokes = shots_received // 18
        remainder = shots_received % 18
        if hole_index <= remainder:
            strokes += 1
    return "*" * strokes

# --- App Layout & Tabs ---
st.title("⛳ MatchPlay Tracker")

tab_setup, tab_scoring, tab_admin = st.tabs([
    "Match Setup & Handicaps", "Scorecard", "Admin"
])

# ==========================================
# TAB 1: MATCH SETUP & HANDICAPS
# ==========================================
with tab_setup:
    st.header("1. Configure Match")
    
    selected_course = st.selectbox("Select Course", list(st.session_state["courses"].keys()))
    course_data = st.session_state["courses"][selected_course]
    
    selected_tee = st.selectbox("Select Tees", list(course_data["tees"].keys()))
    tee_data = course_data["tees"][selected_tee]
    
    match_type = st.selectbox("Match Type", ["Singles", "Fourball", "Foursomes"])
    
    st.divider()
    st.header("2. Player Handicaps")
    
    players = {}
    col1, col2 = st.columns(2)
    
    if match_type == "Singles":
        with col1: players["Player 1"] = st.number_input("Player 1 HI", min_value=-5.0, max_value=54.0, value=10.0, step=0.1, format="%.1f")
        with col2: players["Player 2"] = st.number_input("Player 2 HI", min_value=-5.0, max_value=54.0, value=15.0, step=0.1, format="%.1f")
    elif match_type == "Fourball":
        with col1:
            st.subheader("Team A")
            players["Team A - P1"] = st.number_input("Player 1 HI", min_value=-5.0, max_value=54.0, value=10.0, step=0.1, format="%.1f", key="fa1")
            players["Team A - P2"] = st.number_input("Player 2 HI", min_value=-5.0, max_value=54.0, value=12.0, step=0.1, format="%.1f", key="fa2")
        with col2:
            st.subheader("Team B")
            players["Team B - P1"] = st.number_input("Player 1 HI", min_value=-5.0, max_value=54.0, value=14.0, step=0.1, format="%.1f", key="fb1")
            players["Team B - P2"] = st.number_input("Player 2 HI", min_value=-5.0, max_value=54.0, value=18.0, step=0.1, format="%.1f", key="fb2")
    elif match_type == "Foursomes":
        with col1:
            st.subheader("Team A")
            players["Team A - P1"] = st.number_input("Player 1 HI", min_value=-5.0, max_value=54.0, value=10.0, step=0.1, format="%.1f", key="fsa1")
            players["Team A - P2"] = st.number_input("Player 2 HI", min_value=-5.0, max_value=54.0, value=12.0, step=0.1, format="%.1f", key="fsa2")
        with col2:
            st.subheader("Team B")
            players["Team B - P1"] = st.number_input("Player 1 HI", min_value=-5.0, max_value=54.0, value=15.0, step=0.1, format="%.1f", key="fsb1")
            players["Team B - P2"] = st.number_input("Player 2 HI", min_value=-5.0, max_value=54.0, value=15.0, step=0.1, format="%.1f", key="fsb2")

    if st.button("Initialize & Calculate", type="primary", use_container_width=True):
        st.session_state["match_setup"] = {
            "course": selected_course,
            "tee": selected_tee,
            "tee_data": tee_data,
            "match_type": match_type,
            "players": players
        }
        st.session_state["extra_holes"] = 0
        st.session_state["match_scores"] = {}
        st.success("Match Initialized! Check the handicap breakdown below, then head to the Scorecard tab.")

    if "match_setup" in st.session_state and st.session_state["match_setup"]["match_type"] == match_type:
        st.divider()
        st.header("3. Handicap Breakdown")
        setup = st.session_state["match_setup"]
        allowance_pct = st.session_state["allowances"][match_type]
        allowance_decimal = allowance_pct / 100.0
        
        calc_data = []
        if match_type in ["Singles", "Fourball"]:
            ch_dict = {}
            for p, hi in players.items():
                ch = calculate_course_handicap(hi, tee_data["slope"], tee_data["rating"], tee_data["par"])
                ch_dict[p] = ch
            
            lowest_ch = min(ch_dict.values())
            for p, ch in ch_dict.items():
                shots_diff = ch - lowest_ch
                shots_received = round(shots_diff * allowance_decimal)
                calc_data.append({
                    "Player": p, "HI": hi, "Course Handicap": ch, 
                    f"Difference x {allowance_pct}%": shots_received
                })
        
        elif match_type == "Foursomes":
            team_a_ch = calculate_course_handicap(players["Team A - P1"], tee_data["slope"], tee_data["rating"], tee_data["par"]) + \
                        calculate_course_handicap(players["Team A - P2"], tee_data["slope"], tee_data["rating"], tee_data["par"])
            team_b_ch = calculate_course_handicap(players["Team B - P1"], tee_data["slope"], tee_data["rating"], tee_data["par"]) + \
                        calculate_course_handicap(players["Team B - P2"], tee_data["slope"], tee_data["rating"], tee_data["par"])
            
            diff = abs(team_a_ch - team_b_ch)
            shots = round(diff * allowance_decimal)
            
            calc_data.append({"Team": "Team A", "Combined CH": team_a_ch, "Shots Received": 0 if team_a_ch <= team_b_ch else shots})
            calc_data.append({"Team": "Team B", "Combined CH": team_b_ch, "Shots Received": 0 if team_b_ch <= team_a_ch else shots})

        st.dataframe(pd.DataFrame(calc_data), use_container_width=True)

# ==========================================
# TAB 2: SCORECARD
# ==========================================
with tab_scoring:
    if "match_setup" not in st.session_state:
        st.info("Please initialize the match in the Setup tab first.")
    else:
        setup = st.session_state["match_setup"]
        course_holes = st.session_state["courses"][setup["course"]]["holes"]
        allowance_decimal = st.session_state["allowances"][setup["match_type"]] / 100.0
        
        shots_received = {}
        if setup["match_type"] in ["Singles", "Fourball"]:
            ch_dict = {p: calculate_course_handicap(hi, setup["tee_data"]["slope"], setup["tee_data"]["rating"], setup["tee_data"]["par"]) for p, hi in setup["players"].items()}
            lowest_ch = min(ch_dict.values())
            for p, ch in ch_dict.items():
                shots_received[p] = round((ch - lowest_ch) * allowance_decimal)
        else: 
            team_a_ch = calculate_course_handicap(setup["players"]["Team A - P1"], setup["tee_data"]["slope"], setup["tee_data"]["rating"], setup["tee_data"]["par"]) + \
                        calculate_course_handicap(setup["players"]["Team A - P2"], setup["tee_data"]["slope"], setup["tee_data"]["rating"], setup["tee_data"]["par"])
            team_b_ch = calculate_course_handicap(setup["players"]["Team B - P1"], setup["tee_data"]["slope"], setup["tee_data"]["rating"], setup["tee_data"]["par"]) + \
                        calculate_course_handicap(setup["players"]["Team B - P2"], setup["tee_data"]["slope"], setup["tee_data"]["rating"], setup["tee_data"]["par"])
            diff = round(abs(team_a_ch - team_b_ch) * allowance_decimal)
            shots_received["Team A"] = 0 if team_a_ch <= team_b_ch else diff
            shots_received["Team B"] = 0 if team_b_ch <= team_a_ch else diff

        player_entities = list(shots_received.keys())
        total_holes = 18 + st.session_state["extra_holes"]
        score_options = ["-"] + list(range(1, 16))

        current_match_score = 0
        holes_played = 0

        for idx in range(total_holes):
            hole_key = f"hole_{idx}"
            if hole_key in st.session_state["match_scores"]:
                scores = st.session_state["match_scores"][hole_key]
                net_scores = {}
                
                for p in player_entities:
                    s = scores.get(p, "-")
                    if s != "-":
                        hole_index = course_holes[idx % 18]["index"]
                        stars = len(allocate_strokes(shots_received[p], hole_index))
                        net_scores[p] = s - stars

                if setup["match_type"] == "Fourball":
                    team_a_nets = [net_scores[p] for p in player_entities[:2] if p in net_scores]
                    team_b_nets = [net_scores[p] for p in player_entities[2:] if p in net_scores]
                    
                    if team_a_nets and team_b_nets: 
                        best_a = min(team_a_nets)
                        best_b = min(team_b_nets)
                        if best_a < best_b: current_match_score += 1
                        elif best_b < best_a: current_match_score -= 1
                        holes_played += 1
                else: 
                    if len(net_scores) == 2:
                        p1, p2 = player_entities[0], player_entities[1]
                        if net_scores[p1] < net_scores[p2]: current_match_score += 1
                        elif net_scores[p2] < net_scores[p1]: current_match_score -= 1
                        holes_played += 1

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

        st.write("**Enter Gross Scores Below**")
        for idx in range(total_holes):
            real_hole_idx = idx % 18
            hole_data = course_holes[real_hole_idx]
            hole_key = f"hole_{idx}"
            
            if hole_key not in st.session_state["match_scores"]:
                st.session_state["match_scores"][hole_key] = {p: "-" for p in player_entities}

            is_scored = any(st.session_state["match_scores"][hole_key][p] != "-" for p in player_entities)
            expander_title = f"⛳ Hole {idx + 1}  |  Par {hole_data['par']}  |  Index {hole_data['index']}"
            if is_scored: expander_title += "  ✅"

            with st.expander(expander_title, expanded=(not is_scored and idx == holes_played)):
                cols = st.columns(len(player_entities))
                for i, p in enumerate(player_entities):
                    with cols[i]:
                        asterisks = allocate_strokes(shots_received[p], hole_data["index"])
                        display_name = p.replace("Team A - ", "").replace("Team B - ", "")
                        
                        current_val = st.session_state["match_scores"][hole_key][p]
                        idx_val = score_options.index(current_val) if current_val in score_options else 0
                        
                        selected_score = st.selectbox(
                            f"{display_name} {asterisks}",
                            options=score_options,
                            index=idx_val,
                            key=f"sel_{idx}_{p}"
                        )
                        st.session_state["match_scores"][hole_key][p] = selected_score
                        
                        if selected_score != "-":
                            net = selected_score - len(asterisks)
                            st.caption(f"Net: **{net}**")

        if st.button("➕ Add Extra Hole", use_container_width=True):
            st.session_state["extra_holes"] += 1
            st.rerun()

# ==========================================
# TAB 3: ADMIN & ALLOWANCES
# ==========================================
with tab_admin:
    st.header("Admin Settings")
    st.write("Set global handicap allowances for match formats. Integers only.")
    
    c1, c2, c3 = st.columns(3)
    with c1: 
        st.session_state["allowances"]["Singles"] = int(st.number_input("Singles (%)", value=int(st.session_state["allowances"]["Singles"]), step=1))
    with c2: 
        st.session_state["allowances"]["Fourball"] = int(st.number_input("Fourball (%)", value=int(st.session_state["allowances"]["Fourball"]), step=1))
    with c3: 
        st.session_state["allowances"]["Foursomes"] = int(st.number_input("Foursomes (%)", value=int(st.session_state["allowances"]["Foursomes"]), step=1))
    
    st.divider()
    st.subheader("Course Database")
    st.write("Loaded Courses (Read-only view):")
    for course_name, data in st.session_state["courses"].items():
        with st.expander(course_name):
            st.json(data)
