import streamlit as st
import pandas as pd
import numpy as np
import math

st.set_page_config(page_title="MatchPlay Scoring App", layout="wide")

# --- 1. INITIALIZE SESSION STATE & DEFAULT DATA ---
if 'courses' not in st.session_state:
    # Pre-loading Laytown & Bettystown
    st.session_state.courses = {
        "Laytown & Bettystown": {
            "holes": {
                #[cite: 1] for all pars and indexes below
                1: {"par": 4, "index": 12}, 2: {"par": 4, "index": 14},
                3: {"par": 4, "index": 4},  4: {"par": 5, "index": 16},
                5: {"par": 4, "index": 6},  6: {"par": 3, "index": 10},
                7: {"par": 4, "index": 2},  8: {"par": 3, "index": 8},
                9: {"par": 4, "index": 18}, 10: {"par": 4, "index": 11},
                11: {"par": 4, "index": 5}, 12: {"par": 3, "index": 13},
                13: {"par": 4, "index": 3}, 14: {"par": 4, "index": 9},
                15: {"par": 4, "index": 1}, 16: {"par": 4, "index": 7},
                17: {"par": 4, "index": 17},18: {"par": 5, "index": 15}
            },
            "tees": {
                "White": {"rating": 72.0, "slope": 126, "par": 71},
                "Green": {"rating": 71.2, "slope": 125, "par": 71}
            }
        }
    }

if 'allowances' not in st.session_state:
    st.session_state.allowances = {
        "Singles": 1.00,
        "Fourball": 0.90,
        "Foursomes": 0.50
    }

if 'extra_holes' not in st.session_state:
    st.session_state.extra_holes = 0

# --- 2. HANDICAP HELPER FUNCTIONS ---
def calculate_course_handicap(hi, slope, rating, par):
    """Calculates standard WHS Course Handicap"""
    return (hi * (slope / 113)) + (rating - par)

def allocate_strokes(shots_received, hole_index):
    """Returns a string of asterisks based on shots received vs hole index"""
    if shots_received <= 0:
        return ""
    strokes = 0
    temp_shots = shots_received
    while temp_shots >= hole_index:
        strokes += 1
        temp_shots -= 18
    return "*" * strokes

# --- 3. APP UI ---
st.title("⛳ Golf Matchplay Scoring & Handicap Engine")

# Top Level Tabs
tab_setup, tab_scorecard, tab_hcap_calc, tab_admin = st.tabs([
    "⚙️ Match Setup", "🏌️ Scorecard", "🧮 Handicap Breakdown", "🔒 Admin"
])

# --- TAB 1: MATCH SETUP ---
with tab_setup:
    st.header("Match Setup")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        selected_course = st.selectbox("Select Course", list(st.session_state.courses.keys()))
        course_data = st.session_state.courses[selected_course]
        
    with col2:
        selected_tee = st.selectbox("Select Tee", list(course_data["tees"].keys()))
        tee_data = course_data["tees"][selected_tee]
        
    with col3:
        match_type = st.selectbox("Match Type", ["Singles", "Fourball", "Foursomes"])

    st.subheader("Player Information")
    players = {}
    
    if match_type == "Singles":
        c1, c2 = st.columns(2)
        with c1:
            p1_name = st.text_input("Player 1 Name", "Player A")
            p1_hi = st.number_input("Player 1 Handicap Index", min_value=-5.0, max_value=54.0, value=3.6, step=0.1)
            players["Player 1"] = {"name": p1_name, "hi": p1_hi}
        with c2:
            p2_name = st.text_input("Player 2 Name", "Player B")
            p2_hi = st.number_input("Player 2 Handicap Index", min_value=-5.0, max_value=54.0, value=12.4, step=0.1)
            players["Player 2"] = {"name": p2_name, "hi": p2_hi}
            
    elif match_type in ["Fourball", "Foursomes"]:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Team 1**")
            t1p1_name = st.text_input("T1 Player 1 Name", "Eddie")
            t1p1_hi = st.number_input("T1 P1 Index", value=2.5, step=0.1)
            t1p2_name = st.text_input("T1 Player 2 Name", "Player B")
            t1p2_hi = st.number_input("T1 P2 Index", value=10.0, step=0.1)
            players["T1_P1"] = {"name": t1p1_name, "hi": t1p1_hi, "team": 1}
            players["T1_P2"] = {"name": t1p2_name, "hi": t1p2_hi, "team": 1}
        with c2:
            st.markdown("**Team 2**")
            t2p1_name = st.text_input("T2 Player 1 Name", "Player C")
            t2p1_hi = st.number_input("T2 P1 Index", value=8.0, step=0.1)
            t2p2_name = st.text_input("T2 Player 2 Name", "Player D")
            t2p2_hi = st.number_input("T2 P2 Index", value=14.2, step=0.1)
            players["T2_P1"] = {"name": t2p1_name, "hi": t2p1_hi, "team": 2}
            players["T2_P2"] = {"name": t2p2_name, "hi": t2p2_hi, "team": 2}

    st.info(f"Course: **{selected_course}** | Tee: **{selected_tee}** (Rating: {tee_data['rating']}, Slope: {tee_data['slope']}, Par: {tee_data['par']})")

# --- BACKGROUND CALCULATIONS ---
calc_details = []
playing_handicaps = {}

if match_type == "Singles":
    for p_key, p_data in players.items():
        ch = calculate_course_handicap(p_data['hi'], tee_data['slope'], tee_data['rating'], tee_data['par'])
        ph = round(ch * st.session_state.allowances["Singles"])
        playing_handicaps[p_key] = ph
        calc_details.append({"Name": p_data['name'], "HI": p_data['hi'], "CH (Unrounded)": ch, "Allowance": "100%", "Playing Handicap": ph})
        
elif match_type == "Fourball":
    for p_key, p_data in players.items():
        ch = calculate_course_handicap(p_data['hi'], tee_data['slope'], tee_data['rating'], tee_data['par'])
        ph = round(ch * st.session_state.allowances["Fourball"])
        playing_handicaps[p_key] = ph
        calc_details.append({"Name": p_data['name'], "Team": p_data['team'], "HI": p_data['hi'], "CH (Unrounded)": ch, "Allowance": "90%", "Playing Handicap": ph})

elif match_type == "Foursomes":
    # Foursomes combines CH first, then takes 50%
    team1_ch = calculate_course_handicap(players["T1_P1"]['hi'], tee_data['slope'], tee_data['rating'], tee_data['par']) + \
               calculate_course_handicap(players["T1_P2"]['hi'], tee_data['slope'], tee_data['rating'], tee_data['par'])
    team2_ch = calculate_course_handicap(players["T2_P1"]['hi'], tee_data['slope'], tee_data['rating'], tee_data['par']) + \
               calculate_course_handicap(players["T2_P2"]['hi'], tee_data['slope'], tee_data['rating'], tee_data['par'])
    
    t1_ph = round(team1_ch * st.session_state.allowances["Foursomes"])
    t2_ph = round(team2_ch * st.session_state.allowances["Foursomes"])
    
    playing_handicaps["Team 1"] = t1_ph
    playing_handicaps["Team 2"] = t2_ph
    calc_details.append({"Name": "Team 1 Combined", "Combined CH": team1_ch, "Allowance": "50%", "Playing Handicap": t1_ph})
    calc_details.append({"Name": "Team 2 Combined", "Combined CH": team2_ch, "Allowance": "50%", "Playing Handicap": t2_ph})

# Calculate relative shots
lowest_ph = min(playing_handicaps.values())
shots_received = {k: v - lowest_ph for k, v in playing_handicaps.items()}

# --- TAB 2: SCORECARD ---
with tab_scorecard:
    st.header("Active Scorecard")
    
    # Extra holes controller
    if st.button("➕ Add Extra Hole"):
        st.session_state.extra_holes += 1
    
    total_holes = 18 + st.session_state.extra_holes
    scorecard_data = []
    
    for i in range(1, total_holes + 1):
        # Map extra holes back to 1-18 for pars and indexes
        mapped_hole = i if i <= 18 else ((i - 1) % 18) + 1
        h_data = course_data["holes"][mapped_hole]
        
        row = {
            "Hole": i,
            "Par": h_data["par"],
            "Index": h_data["index"]
        }
        
        # Allocate strokes (asterisks)
        if match_type == "Singles":
            for p_key, p_data in players.items():
                asterisks = allocate_strokes(shots_received[p_key], h_data["index"])
                row[p_data['name']] = asterisks
        elif match_type == "Fourball":
            for p_key, p_data in players.items():
                asterisks = allocate_strokes(shots_received[p_key], h_data["index"])
                row[p_data['name']] = asterisks
        elif match_type == "Foursomes":
            row["Team 1 Shots"] = allocate_strokes(shots_received["Team 1"], h_data["index"])
            row["Team 2 Shots"] = allocate_strokes(shots_received["Team 2"], h_data["index"])
            
        scorecard_data.append(row)

    df_scorecard = pd.DataFrame(scorecard_data)
    st.dataframe(df_scorecard, use_container_width=True, hide_index=True)

# --- TAB 3: HANDICAP BREAKDOWN ---
with tab_hcap_calc:
    st.header("Handicap Math Breakdown")
    st.markdown("Detailed step-by-step calculation based on current Golf Ireland WHS guidelines.")
    
    df_calc = pd.DataFrame(calc_details)
    st.table(df_calc)
    
    st.subheader("Shots Received (Relative to Lowest)")
    for k, v in shots_received.items():
        name_label = players[k]['name'] if k in players else k
        st.write(f"**{name_label}:** Receives {v} shots")

# --- TAB 4: ADMIN PANEL ---
with tab_admin:
    st.header("Administration Panel")
    
    st.subheader("Matchplay Allowances")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.session_state.allowances["Singles"] = st.number_input("Singles %", value=st.session_state.allowances["Singles"], step=0.05)
    with c2:
        st.session_state.allowances["Fourball"] = st.number_input("Fourball %", value=st.session_state.allowances["Fourball"], step=0.05)
    with c3:
        st.session_state.allowances["Foursomes"] = st.number_input("Foursomes %", value=st.session_state.allowances["Foursomes"], step=0.05)
        
    st.divider()
    st.subheader("Course Management (Preview)")
    st.info("In a full production build linked to a database (like Supabase), this is where you would upload new courses, set tee ratings/slopes, and configure 9-hole loops.")
    st.json(st.session_state.courses)
