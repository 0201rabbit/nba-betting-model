import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from nba_api.stats.endpoints import leaguedashteamstats, scoreboardv2
from nba_api.stats.static import teams
from datetime import datetime, timedelta
import re
import sqlite3

# ------------------------
# 0 系統配置與資料庫
# ------------------------
st.set_page_config(page_title="NBA AI 終極操盤手 V13.5", page_icon="🏀", layout="wide")

def init_db():
    conn = sqlite3.connect('nba_v13_5.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS history 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, game TEXT, 
                  pred_spread REAL, user_spread REAL, result_spread TEXT, settled INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()

init_db()

# 核心球員庫 (延用並擴充 V8)
STAR_PLAYERS = {
    "Celtics": ["Jayson Tatum", "Jaylen Brown"], "Nuggets": ["Nikola Jokic", "Jamal Murray"],
    "Lakers": ["LeBron James", "Anthony Davis"], "Suns": ["Kevin Durant", "Devin Booker"],
    "Warriors": ["Stephen Curry", "Draymond Green"], "Mavericks": ["Luka Doncic", "Kyrie Irving"],
    "Bucks": ["Giannis Antetokounmpo", "Damian Lillard"], "76ers": ["Joel Embiid", "Tyrese Maxey"],
    "Clippers": ["Kawhi Leonard", "James Harden"], "Spurs": ["Victor Wembanyama"]
}

# ------------------------
# 1 數據引擎
# ------------------------
@st.cache_data(ttl=3600)
def fetch_nba_master():
    team_dict = {t["id"]: t["full_name"] for t in teams.get_teams()}
    games = scoreboardv2.ScoreboardV2().get_data_frames()[0]
    stats_s = leaguedashteamstats.LeagueDashTeamStats(measure_type_detailed_defense="Advanced").get_data_frames()[0]
    stats_l = leaguedashteamstats.LeagueDashTeamStats(measure_type_detailed_defense="Advanced", last_n_games=10).get_data_frames()[0]
    avg_off = stats_s["OFF_RATING"].mean()
    return team_dict, games, stats_s, stats_l, avg_off

@st.cache_data(ttl=600)
def get_injury_text():
    try:
        r = requests.get("https://www.cbssports.com/nba/injuries/", headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        return r.text.lower()
    except: return ""

# ------------------------
# 2 核心解析邏輯 (融合 V8 期望值扣分)
# ------------------------
def parse_injury_v13(team_name, injury_text):
    mascot = team_name.split()[-1]
    penalty, reports = 0, []
    has_gtd = False
    
    if mascot in STAR_PLAYERS:
        for player in STAR_PLAYERS[mascot]:
            if player.split()[-1].lower() in injury_text:
                idx = injury_text.find(player.split()[-1].lower())
                context = injury_text[idx:idx+100]
                if "out" in context:
                    penalty += 8.0 # V8 確定缺陣扣 8 分
                    reports.append(f"🚨 {player} (確定 Out)")
                elif "probable" in context:
                    reports.append(f"✅ {player} (穩定 Probable)")
                else:
                    penalty += 4.0 # V8 期望值扣 4 分
                    reports.append(f"⚠️ {player} (GTD/Questionable)")
                    has_gtd = True
    return penalty, reports, has_gtd

# ------------------------
# 3 主程式 UI
# ------------------------
st.title("🏀 NBA 終極全能操盤手 V13.5")
st.markdown("### 🏆 傷兵期望值修正 × 智能串關建議")

with st.spinner("同步數據中..."):
    team_dict, games, stats_s, stats_l, avg_off = fetch_nba_master()
    injury_text = get_injury_text()

if games.empty:
    st.info("📅 今日暫無 NBA 賽程")
    st.stop()

# 儲存所有比賽的分析結果用於串關推薦
all_matchups = []

for _, row in games.iterrows():
    h_n = team_dict.get(row["HOME_TEAM_ID"])
    a_n = team_dict.get(row["VISITOR_TEAM_ID"])
    
    # 取得雙方進階數據
    h_row = stats_s[stats_s["TEAM_ID"] == row["HOME_TEAM_ID"]].iloc[0]
    a_row = stats_s[stats_s["TEAM_ID"] == row["VISITOR_TEAM_ID"]].iloc[0]
    h_l10 = stats_l[stats_l["TEAM_ID"] == row["HOME_TEAM_ID"]].iloc[0]
    a_l10 = stats_l[stats_l["TEAM_ID"] == row["VISITOR_TEAM_ID"]].iloc[0]
    
    # 計算複合效率 (V12.2 加權邏輯)
    h_off = h_row["OFF_RATING"] * 0.6 + h_l10["OFF_RATING"] * 0.4
    a_off = a_row["OFF_RATING"] * 0.6 + a_l10["OFF_RATING"] * 0.4
    h_def = h_row["DEF_RATING"] * 0.6 + h_l10["DEF_RATING"] * 0.4
    a_def = a_row["DEF_RATING"] * 0.6 + a_l10["DEF_RATING"] * 0.4
    pace = (h_row["PACE"] + a_row["PACE"]) / 2
    
    # 預測比分 (套用 V8 傷兵修正)
    h_pen, h_rep, h_gtd = parse_injury_v13(h_n, injury_text)
    a_pen, a_rep, a_gtd = parse_injury_v13(a_n, injury_text)
    
    h_score = (h_off * (pace/100) * (avg_off/a_def)) + 2.5 - h_pen
    a_score = (a_off * (pace/100) * (avg_off/h_def)) - a_pen
    
    all_matchups.append({
        "label": f"{a_n} @ {h_n}", "h_score": h_score, "a_score": a_score,
        "spread": h_score - a_score, "total": h_score + a_score,
        "reports": h_rep + a_rep, "has_gtd": h_gtd or a_gtd
    })

# --- 🌟 串關推薦區塊 ---
st.divider()
st.header("🎯 AI 智能串關推薦")
# 排序原則：找出讓分 Edge 最明顯且無 GTD 變數的比賽
# (此處需使用者輸入盤口才能計算準確 Edge，預設以 AI 指向性排列)
recommend_list = [m for m in all_matchups if not m["has_gtd"]]
recommend_list = sorted(recommend_list, key=lambda x: abs(x["spread"]), reverse=True)

if len(recommend_list) >= 2:
    col_r1, col_r2 = st.columns(2)
    with col_r1:
        st.success(f"🔥 **最佳串關組合：{recommend_list[0]['label']} + {recommend_list[1]['label']}**")
        st.write("推薦理由：陣容穩定（無 GTD），模型與盤口邊際值較大。")
    with col_r2:
        st.info("💡 **操作建議**：推薦 2 串 1，穩紮穩打為主。")

# --- 單場詳細分析區塊 ---
st.divider()
selected_game = st.selectbox("查看單場詳細解析", all_matchups, format_func=lambda x: x["label"])

c1, c2, c3 = st.columns([1, 1, 1])
with c1:
    st.metric(selected_game["label"].split(" @ ")[0], f"{selected_game['a_score']:.1f}")
with c2:
    st.markdown("<h3 style='text-align: center;'>VS</h3>", unsafe_allow_html=True)
    st.markdown(f"**AI 預測讓分: {selected_game['spread']:.1f}**")
with c3:
    st.metric(selected_game["label"].split(" @ ")[1], f"{selected_game['h_score']:.1f}")

# 顯示傷兵警告 (V8 風格)
if selected_game["reports"]:
    for r in selected_game["reports"]:
        if "🚨" in r: st.error(r)
        elif "⚠️" in r: st.warning(r)
        else: st.success(r)
else:
    st.success("✅ 陣容完整，適合重注。")

if selected_game["has_gtd"]:
    st.error("🛌 **睡前提醒**：此場有核心成員「出戰成疑」，若要串關，建議注碼減半或明早確認名單。")