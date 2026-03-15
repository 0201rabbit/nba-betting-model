import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from nba_api.stats.endpoints import leaguedashteamstats, scoreboardv2, leaguedashplayerstats
from nba_api.stats.static import teams
from datetime import datetime, timedelta
import re

# ------------------------
# 0 隊名與 2026 核心球員庫
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

STAR_PLAYERS = {
    "Lakers": ["LeBron James", "Anthony Davis"], "Nuggets": ["Nikola Jokic", "Jamal Murray"],
    "Celtics": ["Jayson Tatum", "Jaylen Brown"], "Mavericks": ["Luka Doncic", "Kyrie Irving"],
    "Thunder": ["Shai Gilgeous-Alexander", "Chet Holmgren"], "Timberwolves": ["Anthony Edwards", "Rudy Gobert"],
    "Bucks": ["Giannis Antetokounmpo", "Damian Lillard"], "Suns": ["Kevin Durant", "Devin Booker"],
    "Warriors": ["Stephen Curry"], "Spurs": ["Victor Wembanyama"], "76ers": ["Joel Embiid", "Tyrese Maxey"],
    "Cavaliers": ["Donovan Mitchell"], "Knicks": ["Jalen Brunson"]
}

# ------------------------
# 1 數據引擎與傷兵爬蟲
# ------------------------
@st.cache_data(ttl=600)
def fetch_injury_raw():
    headers = {"User-Agent": "Mozilla/5.0"}
    url = "https://www.cbssports.com/nba/injuries/"
    try:
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        return soup.get_text(separator=' ', strip=True).lower()
    except: return ""

def get_injury_impact(team_name, raw_text):
    mascot = team_name.split()[-1]
    penalty, reports, has_gtd = 0, [], False
    if mascot in STAR_PLAYERS:
        for player in STAR_PLAYERS[mascot]:
            last_name = player.split()[-1].lower()
            if last_name in raw_text:
                idx = raw_text.find(last_name)
                chunk = raw_text[idx:idx+150]
                if "out" in chunk:
                    penalty += 8.0
                    reports.append(f"🚨 {player} [確定缺陣 Out]")
                elif any(word in chunk for word in ["questionable", "gtd", "day-to-day", "decision"]):
                    penalty += 4.0
                    reports.append(f"⚠️ {player} [出戰成疑 GTD]")
                    has_gtd = True
    return penalty, reports, has_gtd

@st.cache_data(ttl=3600)
def fetch_nba_master():
    team_dict = {t["id"]: t["full_name"] for t in teams.get_teams()}
    games = scoreboardv2.ScoreboardV2().get_data_frames()[0]
    s_h = leaguedashteamstats.LeagueDashTeamStats(measure_type_detailed_defense="Advanced", location_nullable="Home").get_data_frames()[0]
    s_a = leaguedashteamstats.LeagueDashTeamStats(measure_type_detailed_defense="Advanced", location_nullable="Road").get_data_frames()[0]
    p_stats = leaguedashplayerstats.LeagueDashPlayerStats(measure_type_detailed_defense="Advanced").get_data_frames()[0]
    return team_dict, games, s_h, s_a, p_stats

# ------------------------
# 2 主介面
# ------------------------
st.set_page_config(page_title="NBA AI 終極實戰 V21.0", page_icon="🏀", layout="wide")
st.title("🏀 NBA AI 終極實戰 V21.0")

with st.spinner("同步 NBA 數據與最新傷兵名單..."):
    t_dict, games_df, s_h, s_a, p_stats = fetch_nba_master()
    raw_inj = fetch_injury_raw()

if games_df.empty:
    st.info("📅 今日暫無賽程。")
else:
    match_list = []
    for _, row in games_df.iterrows():
        h_n = t_dict.get(row["HOME_TEAM_ID"])
        a_n = t_dict.get(row["VISITOR_TEAM_ID"])
        
        # 傷兵解析
        h_pen, h_rep, h_gtd = get_injury_impact(h_n, raw_inj)
        a_pen, a_rep, a_gtd = get_injury_impact(a_n, raw_inj)
        
        # 主客場分離模型
        try:
            h_data = s_h[s_h["TEAM_NAME"] == h_n].iloc[0]
            a_data = s_a[s_a["TEAM_NAME"] == a_n].iloc[0]
            
            # 對位統治力加成
            h_abb = "".join([i[0] for i in h_n.split() if i[0].isupper()])
            a_abb = "".join([i[0] for i in a_n.split() if i[0].isupper()])
            h_pie = p_stats[p_stats["TEAM_ABBREVIATION"] == h_abb]["PIE"].max()
            a_pie = p_stats[p_stats["TEAM_ABBREVIATION"] == a_abb]["PIE"].max()
            h_edge = (h_pie - 12) * 0.5 if h_pie > 12 else 0
            a_edge = (a_pie - 12) * 0.5 if a_pie > 12 else 0
            
            h_score = (h_data["OFF_RATING"] * (h_data["PACE"]/100)) + 2.5 - h_pen + h_edge
            a_score = (a_data["OFF_RATING"] * (a_data["PACE"]/100)) - a_pen + a_edge
            
            match_list.append({
                "label": f"{a_n} ({TEAM_CN.get(a_n, '未知')}) @ {h_n} ({TEAM_CN.get(h_n, '未知')})",
                "h_n": h_n, "a_n": a_n, "h_s": h_score, "a_s": a_score,
                "reports": h_rep + a_rep, "gtd": h_gtd or a_gtd
            })
        except: continue

    selected = st.selectbox("選擇今日比賽深度分析", match_list, format_func=lambda x: x["label"])

    # 顯示核心數據
    col1, col2, col3 = st.columns(3)
    col1.metric(f"🏠 {selected['h_n']}", f"{selected['h_s']:.1f}")
    col2.markdown(f"<h3 style='text-align:center;'>預測讓分: {selected['h_s']-selected['a_s']:.1f}<br>預測總分: {selected['h_s']+selected['a_s']:.1f}</h3>", unsafe_allow_html=True)
    col3.metric(f"✈️ {selected['a_n']}", f"{selected['a_s']:.1f}")

    # 傷兵警告區
    st.divider()
    if selected["reports"]:
        st.subheader("📋 關鍵傷兵報告")
        for r in selected["reports"]:
            if "🚨" in r: st.error(r)
            else: st.warning(r)
    else:
        st.success("✅ 目前該場次核心主力均正常出賽。")

    # --- 💰 台彩實戰輸入與建議 ---
    st.divider()
    c_in1, c_in2, c_in3 = st.columns(3)
    with c_in1:
        u_ml_h = st.number_input("不讓分賠率 (主勝)", value=1.50)
        u_ml_a = st.number_input("不讓分賠率 (客勝)", value=2.20)
    with c_in2:
        u_spread = st.number_input("主隊讓分盤口 (如 -8.5)", value=-8.5, step=0.5)
    with c_in3:
        u_total = st.number_input("大小分門檻", value=220.5, step=0.5)
        u_odd_over = st.number_input("大分賠率", value=1.75)
        u_odd_under = st.number_input("小分賠率", value=1.75)

    # 決策邏輯
    st.subheader("💡 AI 操盤指令")
    ai_spread = selected['h_s'] - selected['a_s']
    edge = ai_spread - u_spread
    
    if abs(edge) >= 4.5:
        st.success(f"🔥 【重注建議】預測分差與盤口誤差達 {abs(edge):.1f} 分，適合攻擊 **{'主隊過盤' if edge > 0 else '客隊受讓'}**。")
    elif abs(edge) >= 2.5:
        st.info(f"✅ 【小注建議】建議關注 **{'主隊' if edge > 0 else '客隊'}**。")
    else:
        st.warning("⚖️ 【建議觀望】盤口與 AI 預測接近，建議轉為串關副選。")
    
    if selected["gtd"]:
        st.error("🛌 睡前提醒：本場有核心球員成疑，串關建議注碼減半或避開。")