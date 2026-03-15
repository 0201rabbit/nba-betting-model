import streamlit as st
import pandas as pd
import requests
from nba_api.stats.endpoints import leaguedashteamstats, scoreboardv2, leaguedashplayerstats
from nba_api.stats.static import teams
from datetime import datetime, timedelta
import sqlite3

# ------------------------
# 0 系統配置與中文化
# ------------------------
st.set_page_config(page_title="NBA AI 實戰 V19.0 - 結算強化版", page_icon="🏀", layout="wide")

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
# 1 數據引擎：主客場 + 防守修正
# ------------------------
@st.cache_data(ttl=3600)
def fetch_master_data():
    team_dict = {t["id"]: t["full_name"] for t in teams.get_teams()}
    # 抓取主、客場分離進階數據
    s_h = leaguedashteamstats.LeagueDashTeamStats(measure_type_detailed_defense="Advanced", location_nullable="Home").get_data_frames()[0]
    s_a = leaguedashteamstats.LeagueDashTeamStats(measure_type_detailed_defense="Advanced", location_nullable="Road").get_data_frames()[0]
    p_stats = leaguedashplayerstats.LeagueDashPlayerStats(measure_type_detailed_defense="Advanced").get_data_frames()[0]
    games = scoreboardv2.ScoreboardV2().get_data_frames()[0]
    return team_dict, games, s_h, s_a, p_stats

def predict_v19(h_n, a_n, s_h, s_a, p_stats):
    h_data = s_h[s_h["TEAM_NAME"] == h_n].iloc[0]
    a_data = s_a[s_a["TEAM_NAME"] == a_n].iloc[0]
    
    # 基礎分差模型修正：加入防守係數
    pace = (h_data["PACE"] + a_data["PACE"]) / 2
    h_pred = (h_data["OFF_RATING"] * (pace/100) * (110 / a_data["DEF_RATING"])) + 2.5
    a_pred = (a_data["OFF_RATING"] * (pace/100) * (110 / h_data["DEF_RATING"]))
    
    # 對位優勢 (PIE 修正)
    h_star = p_stats[p_stats["TEAM_ABBREVIATION"] == "".join([i[0] for i in h_n.split() if i[0].isupper()])]["PIE"].max()
    a_star = p_stats[p_stats["TEAM_ABBREVIATION"] == "".join([i[0] for i in a_n.split() if i[0].isupper()])]["PIE"].max()
    h_edge = (h_star - 12) * 0.4 if h_star > 12 else 0
    a_edge = (a_star - 12) * 0.4 if a_star > 12 else 0
    
    return h_pred + h_edge, a_pred + a_edge

# ------------------------
# 2 主介面：全功能盤口輸入
# ------------------------
st.title("🏀 NBA AI 實戰 V19.0 (對比運彩專版)")

with st.spinner("NBA 數據分析中..."):
    team_dict, games, s_h, s_a, p_stats = fetch_master_data()

if games.empty:
    st.info("今日暫無賽程。")
else:
    match_options = []
    for _, row in games.iterrows():
        h_n = team_dict.get(row["HOME_TEAM_ID"])
        a_n = team_dict.get(row["VISITOR_TEAM_ID"])
        h_score, a_score = predict_v19(h_n, a_n, s_h, s_a, p_stats)
        match_options.append({"label": f"{TEAM_CN.get(a_n, a_n)} @ {TEAM_CN.get(h_n, h_n)}", "h_n": h_n, "a_n": a_n, "h_s": h_score, "a_s": a_score})

    selected = st.selectbox("選擇比賽進行盤口比對", match_options, format_func=lambda x: x["label"])

    # 顯示 AI 預測
    c1, c2, c3 = st.columns(3)
    c1.metric(f"🏠 {TEAM_CN.get(selected['h_n'])}", f"{selected['h_s']:.1f}")
    c2.markdown(f"<h3 style='text-align:center;'>讓分: {selected['h_s']-selected['a_s']:.1f}<br>總分: {selected['h_s']+selected['a_s']:.1f}</h3>", unsafe_allow_html=True)
    c3.metric(f"✈️ {TEAM_CN.get(selected['a_n'])}", f"{selected['a_s']:.1f}")

    # --- 💰 實戰盤口錄入 (依照截圖樣式) ---
    st.divider()
    st.subheader("📝 輸入運彩盤口進行精準分析")
    
    col_in1, col_in2, col_in3 = st.columns(3)
    with col_in1:
        st.write("**不讓分賠率**")
        tw_ml_h = st.number_input("主隊賠率", value=1.18, step=0.01)
        tw_ml_a = st.number_input("客隊賠率", value=3.10, step=0.01)
    with col_in2:
        st.write("**讓分盤數據**")
        tw_spread_val = st.number_input("主隊讓分值 (如 -8.5)", value=-8.5, step=0.5)
        tw_spread_odd = st.number_input("讓分賠率 (如 1.70)", value=1.70, step=0.01)
    with col_in3:
        st.write("**大小分數據**")
        tw_total_val = st.number_input("總分分界 (如 225.5)", value=225.5, step=0.5)
        tw_total_odd = st.number_input("大小賠率", value=1.75, step=0.01)

    # --- 🎯 決策分析 ---
    st.divider()
    st.header("💡 AI 操盤策略")
    
    pred_spread = selected['h_s'] - selected['a_s']
    edge = pred_spread - tw_spread_val
    
    # 邏輯判定
    if abs(edge) >= 5.0:
        st.success(f"🔥 【重注建議】AI 預測讓分 {pred_spread:.1f} 與盤口 {tw_spread_val} 差距達 {abs(edge):.1f} 分。信心度高！")
    elif abs(edge) >= 2.5:
        st.info(f"✅ 【小注建議】存在價值空間。建議買 **{'主隊過盤' if edge > 0 else '客隊受讓'}**。")
    else:
        st.warning("⚖️ 【觀望建議】盤口開得非常精準（誤差 < 2.5），不建議單場投注。")

    # 串關建議
    st.subheader("🎯 串關戰略提示")
    if tw_ml_h > 0 and tw_ml_a > 0:
        if (selected['h_s'] > selected['a_s']) and tw_ml_h < 1.3:
            st.write("推薦：此場主勝極穩，適合做為串關的「不讓分」穩健基石。")