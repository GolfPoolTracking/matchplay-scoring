# --- Visual Render Engine (Custom HTML/CSS) ---
def render_live_card(match_data, team_names):
    setup = match_data["setup"]
    outcomes = match_data.get("outcomes", {})
    extra_holes = match_data.get("extra_holes", 0)
    
    leader, amount, holes_played = get_match_status(outcomes, extra_holes)
    
    # Clean defaults for ALL SQ state
    bg_a, text_a = "transparent", "#333"
    bg_b, text_b = "transparent", "#333"
    shape_a = "none"
    shape_b = "none"
    border_a = "none"
    border_b = "none"
    
    if leader == "A":
        bg_a, text_a = "#2563eb", "white"
        shape_a = "polygon(0% 0%, 92% 0%, 100% 50%, 92% 100%, 0% 100%)"
        border_a = "1px solid #2563eb"
        status_text = f"<span style='color: #2563eb;'>{amount} UP</span>"
    elif leader == "B":
        bg_b, text_b = "#dc2626", "white"
        shape_b = "polygon(8% 0%, 100% 0%, 100% 100%, 8% 100%, 0% 50%)"
        border_b = "1px solid #dc2626"
        status_text = f"<span style='color: #dc2626;'>{amount} UP</span>"
    else:
        status_text = "<span style='color: #555;'>ALL SQ</span>"

    # Generate Hole History Bubbles
    circles_html = ""
    for i in range(1, holes_played + 1):
        res = outcomes.get(str(i))
        if res == "A":
            circles_html += f"<div style='width: 24px; height: 24px; border-radius: 50%; background: #2563eb; color: white; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: bold;'>{i}</div>"
        elif res == "B":
            circles_html += f"<div style='width: 24px; height: 24px; border-radius: 50%; background: #dc2626; color: white; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: bold;'>{i}</div>"
        elif res == "H":
            circles_html += f"<div style='width: 24px; height: 24px; border-radius: 50%; border: 1px solid #ccc; color: #888; background: #f9f9f9; display: flex; align-items: center; justify-content: center; font-size: 11px;'>{i}</div>"

    # FLUSH LEFT TO PREVENT STREAMLIT FROM RENDERING AS A CODE BLOCK
    html_string = f"""
<div style="background: white; border: 1px solid #eaeaea; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); padding: 20px; margin-top: 10px; font-family: sans-serif;">
    <div style="text-align: center; color: #888; font-size: 12px; text-transform: uppercase; margin-bottom: 15px; letter-spacing: 1px;">
        {setup['match_name']} - {setup['match_type']}
    </div>
    
    <div style="display: flex; align-items: center; justify-content: space-between; height: 65px; border-bottom: 1px solid #f0f0f0; padding-bottom: 15px; margin-bottom: 15px;">
        
        <div style="flex: 1; height: 100%; background: {bg_a}; color: {text_a}; display: flex; align-items: center; padding-left: 15px; font-weight: bold; font-size: 15px; border-radius: 6px 0 0 6px; clip-path: {shape_a}; border: {border_a};">
            {team_names['A']}
        </div>
        
        <div style="width: 100px; text-align: center; display: flex; flex-direction: column; justify-content: center;">
            <span style="font-size: 11px; color: #999; text-transform: uppercase; margin-bottom: 2px;">Thru {holes_played}</span>
            <span style="font-size: 18px; font-weight: 800;">{status_text}</span>
        </div>
        
        <div style="flex: 1; height: 100%; background: {bg_b}; color: {text_b}; display: flex; align-items: center; justify-content: flex-end; padding-right: 15px; font-weight: bold; font-size: 15px; border-radius: 0 6px 6px 0; clip-path: {shape_b}; border: {border_b};">
            {team_names['B']}
        </div>
        
    </div>
    
    <div style="display: flex; gap: 8px; flex-wrap: wrap; justify-content: center;">
        {circles_html}
    </div>
</div>
"""
    st.markdown(html_string, unsafe_allow_html=True)
