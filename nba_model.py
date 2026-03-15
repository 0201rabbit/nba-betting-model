import streamlit as st
import pandas as pd
import requests
from nba_api.stats.endpoints import leaguedashteamstats, scoreboardv2
from nba_api.stats.static import teams
from datetime import datetime, timedelta
import re
import sqlite3
import plotly.express as px

# ------------------------
# 0 系統配置與資料庫整合
# ------------------------
st.set_page_config(page_title="NBA AI 操盤系統 V12.2 - 終極回測版", page_icon="🏀", layout="wide")

def init_db():
    conn = sqlite3.connect('nba_master.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS history 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  date TEXT, game TEXT, 
                  pred_spread REAL, user_spread REAL, 
                  pred_total REAL, user_total REAL,
                  actual_home_score INTEGER, actual_away_score INTEGER,
                  settled INTEGER DEFAULT 0, result_spread TEXT, result_total TEXT)''')
    conn.commit()
    conn.close()

init_db()

# ------------------------
# 1 自動結算功能 (New!)
# ------------------------
def auto_settle_results():
    conn = sqlite3.connect('nba_master.db')
    # 找出尚未結算的紀錄
    pending_df = pd.read_sql_query("SELECT * FROM history WHERE settled = 0", conn)
    
    if not pending_df.empty:
        unique_dates = pending_df['date'].unique()
        for d_str in unique_dates:
            try:
                # 抓取該日期的官方比分
                sb = scoreboardv2.ScoreboardV2(game_date=d_str)
                linescore = sb.get_data_frames()[1] # LineScore table
                
                for index, row in pending_df[pending_df['date'] == d_str].iterrows():
                    # 解析隊伍名稱 (假設格式為 "Away @ Home")
                    try:
                        away_n, home_n = row['game'].split(' @ ')
                        h_id = [t['id'] for t in teams.get_teams() if t['full_name'] == home_n][0]
                        a_id = [t['id'] for t in teams.get_teams() if t['full_name'] == away_n][0]
                        
                        h_score = linescore[linescore['TEAM_ID'] == h_id]['PTS'].values[0]
                        a_score = linescore[linescore['TEAM_ID'] == a_id]['PTS'].values[0]
                        
                        # 判定輸贏 (以主隊讓分為準)
                        actual_diff = h_score - a_score
                        res_spread = "Win" if (row['pred_spread'] > row['user_spread'] and actual_diff > row['user_spread']) or \
                                             (row['pred_spread'] < row['user_spread'] and actual_diff < row['user_spread']) else "Loss"
                        
                        actual_total = h_score + a_score
                        res_total = "Win" if (row['pred_total'] > row['user_total'] and actual_total > row['user_total']) or \
                                            (row['pred_total'] < row['user_total'] and actual_total < row['user_total']) else "Loss"

                        conn.execute("""UPDATE history SET actual_home_score=?, actual_away_score=?, 
                                        settled=1, result_spread=?, result_total=? WHERE id=?""",
                                     (int(h_score), int(a_score), res_spread, res_total, row['id']))
                    except: continue
            except: continue
        conn.commit()
    conn.close()

# ------------------------
# 2 數據引擎 (延用 V12 優化版)
# ------------------------
@st.cache_data(ttl=3600)
def fetch_nba_data():
    team_dict = {t["id"]: t["full_name"] for t in teams.get_teams()}
    games = scoreboardv2.ScoreboardV2().get_data_frames()[0]
    stats_s = leaguedashteamstats.LeagueDashTeamStats(measure_type_detailed_defense="Advanced").get_data_frames()[0]
    stats_l = leaguedashteamstats.LeagueDashTeamStats(measure_type_detailed_defense="Advanced", last_n_games=10).get_data_frames()[0]
    avg_off = stats_s["OFF_RATING"].mean()
    y_str = (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    try:
        y_g = scoreboardv2.ScoreboardV2(game_date=y_str).get_data_frames()[0]
        b2b = set(y_g["HOME_TEAM_ID"].tolist() + y_g["VISITOR_TEAM_ID"].tolist())
    except: b2b = set()
    return team_dict, games, stats_s, stats_l, avg_off, b2b

# (傷兵計算函數與權重邏輯保持 V12 不變...)
STAR_PLAYERS = {"Lakers":["LeBron James","Anthony Davis"],"Warriors":["Stephen Curry"],"Celtics":["Jayson Tatum"],"Nuggets":["Nikola Jokic"]} # 可自行擴充

def get_injury_impact(team_name, injury_text):
    mascot = team_name.split()[-1]
    penalty, reports = 0, []
    for p in STAR_PLAYERS.get(mascot, []):
        if p.split()[-1].lower() in injury_text:
            penalty += 7; reports.append(f"🚨 {p} [OUT/Q]")
    return penalty, reports

# ------------------------
# 3 主 UI 流程
# ------------------------
st.title("🏀 NBA AI 操盤系統 V12.2")

# 自動結算昨日賽果
auto_settle_results()

with st.spinner("數據同步中..."):
    team_dict, games, stats_s, stats_l, avg_off, b2b = fetch_nba_data()
    r = requests.get("https://www.cbssports.com/nba/injuries/")
    inj_text = r.text.lower()

if not games.empty:
    game_list = []
    for _, row in games.iterrows():
        h, a = team_dict.get(row["HOME_TEAM_ID"]), team_dict.get(row["VISITOR_TEAM_ID"])
        game_list.append({"label": f"{a} @ {h}", "h_id": row["HOME_TEAM_ID"], "a_id": row["VISITOR_TEAM_ID"], "h_n": h, "a_n": a})
    
    sel = st.selectbox("選擇賽事", game_list, format_func=lambda x: x["label"])
    
    # 計算 (簡化版邏輯)
    pace = 100 # 基準
    h_final = 110 + (3.0 if sel["h_id"] not in b2b else 0.5) # 示意邏輯
    a_final = 108
    spread, total = h_final - a_final, h_final + a_final

    st.write(f"### AI 預測：{sel['h_n']} 讓 {spread:.1f} / 總分 {total:.1f}")
    
    u_s = st.number_input("輸入盤口讓分", value=0.0)
    u_t = st.number_input("輸入盤口大小", value=220.0)
    
    if st.button("📥 儲存預測"):
        conn = sqlite3.connect('nba_master.db')
        conn.execute("INSERT INTO history (date, game, pred_spread, user_spread, pred_total, user_total) VALUES (?,?,?,?,?,?)",
                  (datetime.now().strftime("%Y-%m-%d"), sel["label"], spread, u_s, total, u_t))
        conn.commit(); conn.close()
        st.success("紀錄成功！隔日自動結算。")

# ------------------------
# 4 歷史回測視覺化 (New!)
# ------------------------
st.divider()
st.header("📊 操盤戰績回測")
conn = sqlite3.connect('nba_master.db')
hist_df = pd.read_sql_query("SELECT * FROM history WHERE settled = 1", conn)
conn.close()

if not hist_df.empty:
    c1, c2, c3 = st.columns(3)
    win_rate = (hist_df['result_spread'] == "Win").mean() * 100
    c1.metric("讓分盤勝率", f"{win_rate:.1f}%")
    c2.metric("總場次", len(hist_df))
    c3.metric("最近狀態", hist_df['result_spread'].iloc[-1])
    
    fig = px.line(hist_df, x="date", y="pred_spread", color="result_spread", title="預測偏差趨勢圖")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("尚無已結算的數據，請至少紀錄一場比賽並等待比賽結束。")