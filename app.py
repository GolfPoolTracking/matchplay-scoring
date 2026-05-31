import streamlit as st
import pandas as pd
import math
import uuid
import datetime

# --- App Configuration ---
st.set_page_config(page_title="SLIM MatchPlay Tracker", layout="centered")

# --- WHS Custom Rounding ---
def whs_round(val):
    """WHS dictates that .5 always rounds UP. Python's default round() rounds to nearest even."""
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
    st.session_state["db_matches"] = {} # Simulating a Supabase table

# --- Helper Functions ---
def calculate_course_handicap(hi, slope, rating, par):
    return whs_round((hi * (slope / 113.0)) + (rating - par))

def allocate_strokes(shots_received, hole_index):
    strokes = 0
    if shots_received > 0:
        strokes = shots_received // 18
        remainder = shots_received % 18
        if hole_index <= remainder:
            strokes += 1
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
    st.caption(f"{setup['date'].strftime('%d %b %Y')} | {setup['course']} ({setup['tee']}) | {setup['match_type']}")
    
    tab_scorecard, tab_breakdown, tab_edit = st.tabs(["Scorecard", "Handicap Breakdown", "Edit Match"])
    
    with tab_scorecard:
        current_match_score = 0
        holes_played = 0

        # Calculate Overall Status
        for idx in range(total_holes):
            if idx in match["scores"]:
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
                        holes_played += 1
                else: 
                    if len(net_scores) == 2:
                        p1, p2 = player_entities[0], player_entities[1]
                        if net_scores[p1] < net_scores[p2]: current_match_score += 1
                        elif net_scores[p2] < net_scores[p1]: current_match_score -= 1
                        holes_played += 1

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
        for idx in range(total_holes):
            real_hole_idx = idx % 18
            hole_data = course_holes[real_hole_idx]
            par = hole_data['par']
            
            # Initialize scores with Par by default
            if idx not in match["scores"]:
                match["scores"][idx] = {p: par for p in player_entities}
            
            is_scored = any(match["scores"][idx][p] != par for p in player_entities)
            expander_title = f"⛳ Hole {idx + 1} | Par {par} | Index {hole_data['index']}"
            if is_scored: expander_title += " ✅"

            with st.expander(expander_title, expanded=(idx == holes_played)):
                for p in player_entities:
                    asterisks = allocate_strokes(shots_received[p], hole_data["index"])
                    st.markdown(f"**{p}** {asterisks}")
                    
                    c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
                    current_val = match["scores"][idx][p]
                    
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
                    
                    if current_val != "NR":
                        net = current_val - len(asterisks)
                        st.caption(f"Net: {net}")
                    st.divider()

        if st.button("➕ Add Extra Hole", use_container_width=True):
            match["extra_holes"] = match.get("extra_holes", 0) + 1
            st.rerun()

    with tab_breakdown:
        st.subheader("Match Parameters")
        st.write(f"**Handicaps Used:** {'Yes' if setup.get('use_handicaps', True) else 'No (Scratch)'}")
        st.write(f"**Allowance:** {st.session_state['allowances'][setup['match_type']]}%")
        
        calc_data = []
        for p, data in setup["players"].items():
            calc_data.append({"Player": p, "HI": data["hi"], "Shots Received": shots_received.get(p, 0)})
        st.dataframe(pd.DataFrame(calc_data), use_container_width=True)
        
        st.subheader("Public Share Link")
        st.code(f"https://your-app-url.streamlit.app/?match_id={active_match_id}")

    with tab_edit:
        st.warning("Make changes to the setup here. Note: Changing match type or removing players may reset scorecard data.")
        new_name = st.text_input("Match Name", value=setup["match_name"])
        new_use_hc = st.checkbox("Use Handicaps", value=setup.get("use_handicaps", True), key="edit_hc")
        
        if st.button("Save Changes", type="primary"):
            st.session_state["db_matches"][active_match_id]["setup"]["match_name"] = new_name
            st.session_state["db_matches"][active_match_id]["setup"]["use_handicaps"] = new_use_hc
            st.success("Updated!")
            st.rerun()

else:
    # ==========================================
    # HOME DASHBOARD & MATCH CREATION
    # ==========================================
    st.title("🏌️‍♂️ Match Dashboard")
    
    tab_list, tab_create, tab_admin = st.tabs(["Active Matches", "Create New Match", "Admin & Courses"])
    
    with tab_list:
        if not st.session_state["db_matches"]:
            st.info("No matches found. Create one in the next tab!")
        else:
            for m_id, m_data in st.session_state["db_matches"].items():
                with st.container(border=True):
                    st.subheader(m_data["setup"]["match_name"])
                    st.write(f"{m_data['setup']['date'].strftime('%d %b %Y')} | {m_data['setup']['course']} | {m_data['setup']['match_type']}")
                    if st.button("Open Match Scorecard", key=f"open_{m_id}"):
                        st.query_params["match_id"] = m_id
                        st.rerun()
                        
    with tab_create:
        st.header("New Match Setup")
        match_name = st.text_input("Match Name", value="SLIM Golf Trip Match")
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
        
        # Default placeholder names mapped for convenience
        if match_type == "Singles":
            with col1: players[st.text_input("P1 Name", value="Eddie")] = {"hi": st.number_input("P1 HI", value=5.3, format="%.1f", step=0.1)}
            with col2: players[st.text_input("P2 Name", value="Ben")] = {"hi": st.number_input("P2 HI", value=12.0, format="%.1f", step=0.1)}
        elif match_type in ["Fourball", "Foursomes"]:
            with col1:
                st.write("**Team A**")
                players[st.text_input("A1 Name", value="Eddie", key="a1n")] = {"hi": st.number_input("A1 HI", value=5.3, format="%.1f", step=0.1, key="a1h")}
                players[st.text_input("A2 Name", value="Player 2", key="a2n")] = {"hi": st.number_input("A2 HI", value=10.0, format="%.1f", step=0.1, key="a2h")}
            with col2:
                st.write("**Team B**")
                players[st.text_input("B1 Name", value="Ben", key="b1n")] = {"hi": st.number_input("B1 HI", value=12.0, format="%.1f", step=0.1, key="b1h")}
                players[st.text_input("B2 Name", value="Player 4", key="b2n")] = {"hi": st.number_input("B2 HI", value=15.0, format="%.1f", step=0.1, key="b2h")}

        if st.button("Generate Match & Link", type="primary", use_container_width=True):
            new_id = uuid.uuid4().hex[:8]
            st.session_state["db_matches"][new_id] = {
                "id": new_id,
                "setup": {
                    "match_name": match_name, "date": match_date, "course": selected_course,
                    "tee": selected_tee, "match_type": match_type, "use_handicaps": use_handicaps,
                    "players": players
                },
                "scores": {}, "extra_holes": 0
            }
            st.query_params["match_id"] = new_id
            st.rerun()

    with tab_admin:
        st.header("Global Allowances")
        c1, c2, c3 = st.columns(3)
        with c1: st.session_state["allowances"]["Singles"] = int(st.number_input("Singles (%)", value=st.session_state["allowances"]["Singles"], step=1))
        with c2: st.session_state["allowances"]["Fourball"] = int(st.number_input("Fourball (%)", value=st.session_state["allowances"]["Fourball"], step=1))
        with c3: st.session_state["allowances"]["Foursomes"] = int(st.number_input("Foursomes (%)", value=st.session_state["allowances"]["Foursomes"], step=1))
        
        st.divider()
        st.header("Add New Course")
        with st.expander("➕ Add Course Data", expanded=False):
            new_course_name = st.text_input("Course Name")
            new_tee_name = st.text_input("Tee Name (e.g. White, Blue)")
            colA, colB, colC = st.columns(3)
            with colA: new_par = st.number_input("Course Par", value=72, step=1)
            with colB: new_rating = st.number_input("Course Rating (CR)", value=72.0, step=0.1, format="%.1f")
            with colC: new_slope = st.number_input("Slope", value=125, step=1)
            
            st.write("Enter Hole Data (Par & Index):")
            # Create a default dataframe for 18 holes
            df_holes = pd.DataFrame({"Hole": range(1, 19), "Par": [4]*18, "Index": range(1, 19)})
            edited_df = st.data_editor(df_holes, hide_index=True, use_container_width=True)
            
            if st.button("Save Course", type="primary"):
                if new_course_name and new_tee_name:
                    if new_course_name not in st.session_state["courses"]:
                        st.session_state["courses"][new_course_name] = {"tees": {}, "holes": []}
                    
                    st.session_state["courses"][new_course_name]["tees"][new_tee_name] = {
                        "rating": new_rating, "slope": new_slope, "par": new_par
                    }
                    
                    # Convert dataframe back to dictionary list
                    holes_list = [{"hole": int(row["Hole"]), "par": int(row["Par"]), "index": int(row["Index"])} for _, row in edited_df.iterrows()]
                    st.session_state["courses"][new_course_name]["holes"] = holes_list
                    st.success(f"{new_course_name} saved successfully!")
                else:
                    st.error("Please provide both Course Name and Tee Name.")
