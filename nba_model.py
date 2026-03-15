import streamlit as st
import pandas as pd
from nba_api.stats.endpoints import leaguedashteamstats, scoreboardv2, leaguedashplayerstats
from nba_api.stats.static import teams

# ------------------------
# 0 系統配置與中文化
# ------------------------
st.set_page_config(page_title="NBA AI 實戰 V19.3", page_icon="🎯", layout="wide")

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
# 1 核心數據引擎 (引進 Net Rating 與 進階防守)
# ------------------------
@st.cache_data(ttl=3600)
def fetch_master_data():
    team_dict = {t["id"]: t["full_name"] for t in teams.get_teams()}
    # 抓取進階數據 (包含 Net Rating)
    stats_all = leaguedashteamstats.LeagueDashTeamStats(measure_type_detailed_defense="Advanced").get_data_frames()[0]
    # 主客分離數據
    stats_h = leaguedashteamstats.LeagueDashTeamStats(measure_type_detailed_defense="Advanced", location_nullable="Home").get_data_frames()[0]
    stats_a = leaguedashteamstats.LeagueDashTeamStats(measure_type_detailed_defense="Advanced", location_nullable="Road").get_data_frames()[0]
    # 球員數據 (核心偵測)
    player_stats = leaguedashplayerstats.LeagueDashPlayerStats(measure_type_detailed_defense="Advanced").get_data_frames()[0]
    games = scoreboardv2.ScoreboardV2().get_data_frames()[0]
    return team_dict, games, stats_all, stats_h, stats_a, player_stats

def predict_v19_3(h_n, a_n, s_all, s_h, s_a, p_stats):
    h_data = s_h[s_h["TEAM_NAME"] == h_n].iloc[0]
    a_data = s_a[s_a["TEAM_NAME"] == a_n].iloc[0]
    
    # 核心優化：使用 Net Rating 評估統治力 (找出騎士、老鷹這種大勝體質)
    h_net = h_data["NET_RATING"]
    a_net = a_data["NET_RATING"]
    
    # 基本得分預測 (考慮 Pace 與 攻防效率)
    pace = (h_data["PACE"] + a_data["PACE"]) / 2
    h_pred = (h_data["OFF_RATING"] * (pace/100) * (110/a_data["DEF_RATING"])) + 2.5
    a_pred = (a_data["OFF_RATING"] * (pace/100) * (110/h_data["DEF_RATING"]))
    
    # 偵測核心受傷風險 (若核心球員 PIE 消失，標記地雷)
    h_abb = "".join([i[0] for i in h_n.split() if i[0].isupper()])
    a_abb = "".join([i[0] for i in a_n.split() if i[0].isupper()])
    h_top_players = p_stats[p_stats["TEAM_ABBREVIATION"] == h_abb]
    a_top_players = p_stats[p_stats["TEAM_ABBREVIATION"] == a_abb]
    
    # 避地雷邏輯：如果前二大核心 PIE 總合過低，標記為風險場次
    risk_score = 0
    if h_top_players["PIE"].max() < 12: risk_score += 1
    if a_top_players["PIE"].max() < 12: risk_score += 1

    return h_pred, a_pred, h_net - a_net, risk_score

# ------------------------
# 2 主介面
# ------------------------
st.title("🏀 NBA AI 終極實戰 V19.3")

with st.spinner("正在解析 Net Rating 與 核心對位..."):
    team_dict, games, s_all, s_h, s_a, p_stats = fetch_master_data()

if games.empty:
    st.info("今日暫無賽程。")
else:
    match_options = []
    for _, row in games.iterrows():
        h_n, a_n = team_dict.get(row["HOME_TEAM_ID"]), team_dict.get(row["VISITOR_TEAM_ID"])
        h_s, a_s, net_diff, risk = predict_v19_3(h_n, a_n, s_all, s_h, s_a, p_stats)
        match_options.append({"label": f"{TEAM_CN.get(a_n, a_n)} @ {TEAM_CN.get(h_n, h_n)}", "h_n": h_n, "a_n": a_n, "h_s": h_s, "a_s": a_s, "net": net_diff, "risk": risk})

    selected = st.selectbox("選擇比賽進行深度分析", match_options, format_func=lambda x: x["label"])

    # 數據儀表板
    col1, col2, col3 = st.columns(3)
    col1.metric(f"🏠 {TEAM_CN.get(selected['h_n'])}", f"{selected['h_s']:.1f}")
    col2.markdown(f"<h3 style='text-align:center;'>AI 讓分: {selected['h_s']-selected['a_s']:.1f}<br>體質分 (NetDiff): {selected['net']:.1f}</h3>", unsafe_allow_html=True)
    col3.metric(f"✈️ {TEAM_CN.get(selected['a_n'])}", f"{selected['a_s']:.1f}")

    # 避雷提醒
    if selected['risk'] >= 1:
        st.error("⚠️ 【避雷建議】該場次核心球員數據異常或有傷兵疑慮，建議空手觀望，不宜重注。")

    # --- 💰 台彩盤口實戰輸入 ---
    st.divider()
    c_in1, c_in2, c_in3 = st.columns(3)
    with c_in1:
        st.write("**不讓分賠率**")
        tw_ml_h = st.number_input("主勝賠率", value=1.50)
        tw_ml_a = st.number_input("客勝賠率", value=2.20)
    with c_in2:
        st.write("**讓分盤**")
        tw_spread_val = st.number_input("台彩讓分值 (主隊)", value=-4.5, step=0.5)
    with c_in3:
        st.write("**大小分 (賠率不對稱)**")
        tw_total_val = st.number_input("大小分界線", value=220.5)
        tw_odd_over = st.number_input("【大】賠率", value=1.75)
        tw_odd_under = st.number_input("【小】賠率", value=1.75)

    # --- 💡 終極決策邏輯 ---
    st.divider()
    st.header("💡 AI 操盤分析建議")
    
    ai_spread = selected['h_s'] - selected['a_s']
    edge = ai_spread - tw_spread_val
    
    # 1. 抓大勝邏輯
    if selected['net'] > 8 and ai_spread > 10:
        st.success(f"🔥 【強隊統治】{TEAM_CN.get(selected['h_n'])} 具備大勝體質 (NetDiff > 8)，且 AI 預測大勝，建議強攻讓分主勝。")
    
    # 2. 抓受讓極限邏輯
    if tw_spread_val < -15 or tw_spread_val > 15:
        st.warning(f"🛡️ 【受讓極限】台彩開出 {tw_spread_val} 的極端盤口。若 AI 預測分差小於盤口，強烈建議反打受讓方。")

    # 3. 串關戰略提示 (只有條件觸發才會顯示)
    st.subheader("🎯 串關戰略提示")
    strat_found = False
    if tw_ml_h < 1.35 and ai_spread > 5:
        st.write("✅ **低風險頭**：主隊不讓分極穩，適合當作 2 串 1 或 3 串 1 的穩健「頭」。")
        strat_found = True
    if abs(edge) > 6.0:
        st.write(f"✅ **高價值串關**：本場預測與盤口誤差達 {abs(edge):.1f} 分，適合加入串關增加賠率。")
        strat_found = True
    if not strat_found:
        st.write("⚪ 目前數據邊際不足，不建議強行串關，建議單場小注或觀望。")