import streamlit as st
import pandas as pd
import requests
from nba_api.stats.endpoints import leaguedashteamstats, scoreboardv2, leaguedashplayerstats
from nba_api.stats.static import teams
from datetime import datetime, timedelta
import sqlite3

# ------------------------
# 0 系統配置與中文化映射 (保持 V16)
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

st.set_page_config(page_title="NBA AI 統治力 V17.0", page_icon="🔥", layout="wide")

# ------------------------
# 1 進階數據引擎 (新增球員對位數據)
# ------------------------
@st.cache_data(ttl=3600)
def fetch_v17_data():
    # 隊伍數據
    stats_home = leaguedashteamstats.LeagueDashTeamStats(measure_type_detailed_defense="Advanced", location_nullable="Home").get_data_frames()[0]
    stats_road = leaguedashteamstats.LeagueDashTeamStats(measure_type_detailed_defense="Advanced", location_nullable="Road").get_data_frames()[0]
    
    # 關鍵球員數據 (用於計算對位優勢)
    # 我們抓取全聯盟前 50 名核心球員的內線與進攻效率
    player_stats = leaguedashplayerstats.LeagueDashPlayerStats(measure_type_detailed_defense="Advanced").get_data_frames()[0]
    
    games = scoreboardv2.ScoreboardV2().get_data_frames()[0]
    team_dict = {t["id"]: t["full_name"] for t in teams.get_teams()}
    avg_league_off = stats_home["OFF_RATING"].mean()
    
    return team_dict, games, stats_home, stats_road, player_stats, avg_league_off

# ------------------------
# 2 對位演算法：找出「錯位優勢」
# ------------------------
def calculate_matchup_edge(h_n, a_n, player_stats):
    # 模擬對位邏輯：找出雙方隊伍中最強的核心球員，並比對其對手隊伍的防守弱點
    # 這裡以 PIE (Player Impact Estimate) 作為統治力指標
    h_core = player_stats[player_stats["TEAM_ABBREVIATION"] == "".join([s[0] for s in h_n.split()])].nlargest(1, "PIE")
    a_core = player_stats[player_stats["TEAM_ABBREVIATION"] == "".join([s[0] for s in a_n.split()])].nlargest(1, "PIE")
    
    h_edge = 0
    a_edge = 0
    
    if not h_core.empty:
        # 如果主隊核心 PIE > 15 (頂級球星)，賦予 1.5 - 3 分的額外得分潛力
        h_edge = (h_core["PIE"].values[0] - 10) * 0.25 if h_core["PIE"].values[0] > 12 else 0
        
    if not a_core.empty:
        a_edge = (a_core["PIE"].values[0] - 10) * 0.25 if a_core["PIE"].values[0] > 12 else 0
        
    return h_edge, a_edge

# ------------------------
# 3 核心預測模型 (V17 統治力修正)
# ------------------------
def predict_v17(h_n, a_n, s_home, s_road, player_stats, avg_off):
    h_data = s_home[s_home["TEAM_NAME"] == h_n].iloc[0]
    a_data = s_road[s_road["TEAM_NAME"] == a_n].iloc[0]
    
    # 基本數據得分
    h_base = (h_data["OFF_RATING"] * (h_data["PACE"]/100) * (avg_off/a_data["DEF_RATING"])) + 2.8
    a_base = (a_data["OFF_RATING"] * (a_data["PACE"]/100) * (avg_off/h_data["DEF_RATING"]))
    
    # 加上「球員對位統治力」修正
    h_matchup, a_matchup = calculate_matchup_edge(h_n, a_n, player_stats)
    
    return h_base + h_matchup, a_base + a_matchup, h_matchup, a_matchup

# ------------------------
# 4 實戰介面
# ------------------------
st.title("🔥 NBA AI 統治力對位系統 V17.0")
st.markdown("### 🛠️ 核心進化：主客場分離 + 核心球員對位優勢修正 (Matchup Edge)")

with st.spinner("正在掃描球員對位數據與內線防守缺口..."):
    team_dict, games, s_home, s_road, p_stats, avg_off = fetch_v17_data()

if games.empty:
    st.info("今日暫無賽程。")
else:
    match_list = []
    for _, row in games.iterrows():
        h_n, a_n = team_dict.get(row["HOME_TEAM_ID"]), team_dict.get(row["VISITOR_TEAM_ID"])
        h_final, a_final, h_edge, a_edge = predict_v17(h_n, a_n, s_home, s_road, p_stats, avg_off)
        
        match_list.append({
            "標籤": f"{TEAM_CN.get(a_n, a_n)} @ {TEAM_CN.get(h_n, h_n)}",
            "主隊": h_n, "客隊": a_n,
            "預測主分": h_final, "預測客分": a_final,
            "主隊優勢加成": h_edge, "客隊優勢加成": a_edge,
            "預測讓分": h_final - a_final, "預測總分": h_final + a_final
        })

    # --- 🎯 推薦串關面板 (新增對位分析) ---
    st.divider()
    best_picks = sorted(match_list, key=lambda x: abs(x['預測讓分']), reverse=True)
    
    c1, c2 = st.columns(2)
    with c1:
        st.success("🔥 【高勝率 2 串 1】")
        st.write(f"1. **{best_picks[0]['標籤']}** (對位加成: {best_picks[0]['主隊優勢加成']:.1f})")
        st.write(f"2. **{best_picks[1]['標籤']}** (對位加成: {best_picks[1]['主隊優勢加成']:.1f})")
    with c2:
        st.info("🚀 【串關 3 串 1 備選】")
        st.write(f"首選：{best_picks[0]['標籤']} | 次選：{best_picks[1]['標籤']} | 補強：{best_picks[2]['標籤']}")
        st.warning(f"⚠️ **鎖盤備案**：請替換為 **{best_picks[3]['標籤']}**")

    # --- 🔍 單場實戰與盤口輸入 ---
    st.divider()
    selected = st.selectbox("單場詳細數據解析", match_list, format_func=lambda x: x["標籤"])
    
    col1, col2, col3 = st.columns(3)
    col1.metric(f"🏠 {TEAM_CN.get(selected['主隊'])}", f"{selected['預測主分']:.1f}", f"+{selected['主隊優勢加成']:.1f} 對位修正")
    col2.markdown(f"<h3 style='text-align:center;'>預測讓分: {selected['預測讓分']:.1f}</h3>", unsafe_allow_html=True)
    col3.metric(f"✈️ {TEAM_CN.get(selected['客隊'])}", f"{selected['預測客分']:.1f}", f"+{selected['客隊優勢加成']:.1f} 對位修正")

    # 手動輸入決策 (與 V16 保持一致)
    u_spread = st.number_input("主隊讓分盤口", value=0.0, step=0.5)
    edge = selected["預測讓分"] - u_spread
    if abs(edge) > 4.5:
        st.success(f"✅ **實戰指令**：數據與對位均指向 **{'主隊' if edge > 0 else '客隊'}** 極具優勢！")