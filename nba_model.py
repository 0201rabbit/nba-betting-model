import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from nba_api.stats.endpoints import leaguedashteamstats, scoreboardv2, leaguedashplayerstats
from nba_api.stats.static import teams
from datetime import datetime, timedelta
import re

# ------------------------
# 0 隊名對照表 (用於標註中文)
# ------------------------
TEAM_CN = {
    "Atlanta Hawks": "老鷹", "Boston Celtics": "塞爾提克", "Brooklyn Nets": "籃網",
    "Charlotte Hornets": "黃蜂", "Chicago Bulls": "公牛", "Cleveland Cavaliers": "騎士",
    "Dallas Mavericks": "獨行俠", "Denver Nuggets": "金塊", "Detroit Pistons": "活塞",
    "Golden State Warriors": "勇士", "Houston Rockets": "火箭", "Indiana Pacers": "溜馬",
    "LA Clippers": "快艇", "Los Angeles Lakers": "湖人", "Memphis Grizzlies": "灰熊",
    "Miami Heat": "熱火", "Milwaukee Bucks": "公鹿", "Minnesota Timberwolves": "灰狼",
    "New Orleans Pelicans": "鵜鶘", "New York Knicks": "尼克", "Oklahoma City Thunder": "雷霆",
    "Orlando Magic": "魔術", "Philadelphia 76ers": "76人", "Phoenix Suns": "太陽",
    "Portland Trail Blazers": "拓荒者", "Sacramento Kings": "國王", "San Antonio Spurs": "馬刺",
    "Toronto Raptors": "暴龍", "Utah Jazz": "爵士", "Washington Wizards": "巫師"
}

# ------------------------
# 1 傷兵解析模組 (V8 邏輯回歸)
# ------------------------
STAR_PLAYERS = {
    "Lakers": ["LeBron James", "Anthony Davis"], "Nuggets": ["Nikola Jokic", "Jamal Murray"],
    "Celtics": ["Jayson Tatum", "Jaylen Brown"], "Clippers": ["Kawhi Leonard", "James Harden"],
    "76ers": ["Joel Embiid", "Tyrese Maxey"], "Spurs": ["Victor Wembanyama"],
    "Warriors": ["Stephen Curry"], "Mavericks": ["Luka Doncic", "Kyrie Irving"]
}

@st.cache_data(ttl=900)
def fetch_injury_report():
    try:
        url = "https://www.cbssports.com/nba/injuries/"
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        return res.text.lower()
    except: return ""

def analyze_injuries(team_name, injury_text):
    mascot = team_name.split()[-1]
    penalty, reports, has_gtd = 0, [], False
    if mascot in STAR_PLAYERS:
        for player in STAR_PLAYERS[mascot]:
            last_name = player.split()[-1].lower()
            if last_name in injury_text:
                idx = injury_text.find(last_name)
                context = injury_text[idx:idx+120]
                if "out" in context:
                    penalty += 8.0; reports.append(f"🚨 {player} (確定缺陣 Out)")
                elif "questionable" in context or "gtd" in context:
                    penalty += 4.0; reports.append(f"⚠️ {player} (出戰成疑 GTD)"); has_gtd = True
    return penalty, reports, has_gtd

# ------------------------
# 2 數據引擎
# ------------------------
@st.cache_data(ttl=3600)
def fetch_master_data():
    team_dict = {t["id"]: t["full_name"] for t in teams.get_teams()}
    s_h = leaguedashteamstats.LeagueDashTeamStats(measure_type_detailed_defense="Advanced", location_nullable="Home").get_data_frames()[0]
    s_a = leaguedashteamstats.LeagueDashTeamStats(measure_type_detailed_defense="Advanced", location_nullable="Road").get_data_frames()[0]
    p_stats = leaguedashplayerstats.LeagueDashPlayerStats(measure_type_detailed_defense="Advanced").get_data_frames()[0]
    games = scoreboardv2.ScoreboardV2().get_data_frames()[0]
    return team_dict, games, s_h, s_a, p_stats

# ------------------------
# 3 主程式 UI
# ------------------------
st.set_page_config(page_title="NBA AI 終極版 V20.0", page_icon="🏀", layout="wide")
st.title("🏀 NBA AI 終極實戰 V20.0 (傷兵全解析 + 賠率決策)")

with st.spinner("同步數據與解析最新傷兵情報..."):
    team_dict, games, s_h, s_a, p_stats = fetch_master_data()
    injury_raw = fetch_injury_report()

if games.empty:
    st.info("今日暫無賽程。")
else:
    matchups = []
    for _, row in games.iterrows():
        h_n, a_n = team_dict.get(row["HOME_TEAM_ID"]), team_dict.get(row["VISITOR_TEAM_ID"])
        h_d = s_h[s_h["TEAM_NAME"] == h_n].iloc[0]
        a_d = s_a[s_a["TEAM_NAME"] == a_n].iloc[0]
        
        # 傷兵修正
        h_pen, h_rep, h_gtd = analyze_injuries(h_n, injury_raw)
        a_pen, a_rep, a_gtd = analyze_injuries(a_n, injury_raw)
        
        # 預測模型 (Net Rating 加權)
        pace = (h_d["PACE"] + a_d["PACE"]) / 2
        h_s = (h_d["OFF_RATING"] * (pace/100) * (110/a_d["DEF_RATING"])) + 2.5 - h_pen
        a_s = (a_d["OFF_RATING"] * (pace/100) * (110/h_d["DEF_RATING"])) - a_pen
        
        matchups.append({
            "label": f"{a_n} ({TEAM_CN.get(a_n)}) @ {h_n} ({TEAM_CN.get(h_n)})",
            "h_n": h_n, "a_n": a_n, "h_s": h_s, "a_s": a_s, "h_rep": h_rep, "a_rep": a_rep, "gtd": h_gtd or a_gtd
        })

    selected = st.selectbox("選擇比賽深度分析", matchups, format_func=lambda x: x["label"])

    # 儀表板
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(f"🏠 {selected['h_n']} ({TEAM_CN.get(selected['h_n'])})", f"{selected['h_s']:.1f}")
        for r in selected['h_rep']: st.error(r)
    with col2:
        st.markdown(f"<h3 style='text-align:center;'>讓分: {selected['h_s']-selected['a_s']:.1f}<br>總分: {selected['h_s']+selected['a_s']:.1f}</h3>", unsafe_allow_html=True)
    with col3:
        st.metric(f"✈️ {selected['a_n']} ({TEAM_CN.get(selected['a_n'])})", f"{selected['a_s']:.1f}")
        for r in selected['a_rep']: st.error(r)

    # 避雷與提示
    if selected['gtd']:
        st.error("⚠️ 【高變異警告】此場核心主力為「出戰成疑」，明早可能不打。若要今晚下注，請務必注碼減半。")
    elif not selected['h_rep'] and not selected['a_rep']:
        st.success("🛡️ 【陣容穩定】目前無重大傷勢疑慮，適合當作串關主力。")

    # --- 💰 台彩盤口實戰輸入 ---
    st.divider()
    st.subheader("📝 運彩盤口輸入與下注建議")
    c1, c2, c3 = st.columns(3)
    with c1:
        u_ml_h = st.number_input("不讓分賠率 (主勝)", value=1.50)
        u_ml_a = st.number_input("不讓分賠率 (客勝)", value=2.20)
    with c2:
        u_spread = st.number_input("主隊讓分值 (如 -5.5)", value=-5.5, step=0.5)
    with c3:
        u_total = st.number_input("大小分分界點", value=220.5, step=0.5)
        u_odd_over = st.number_input("大分賠率", value=1.75)
        u_odd_under = st.number_input("小分賠率", value=1.75)

    # --- 🎯 決策建議 ---
    st.divider()
    edge_s = (selected['h_s'] - selected['a_s']) - u_spread
    if abs(edge_s) >= 4.5:
        st.success(f"🔥 【強推建議】AI 預測讓分與盤口誤差達 {abs(edge_s):.1f}，看好 {'主隊過盤' if edge_s > 0 else '客隊受讓'}。")
    
    # 受讓極限偵測
    if u_spread < -15 or u_spread > 15:
        st.warning(f"🛡️ 【受讓極限】盤口開出 {u_spread}。若 AI 預測分差沒這麼大，反打受讓更有獲利空間。")

    # 串關戰略提示
    if not selected['gtd'] and abs(edge_s) > 3.0:
        st.info(f"🎯 **串關戰略**：本場無 GTD 變數且 Edge 穩定，建議可串 **{'讓分' if u_ml_h > 0 else '不讓分'}** 以提升獲利。")