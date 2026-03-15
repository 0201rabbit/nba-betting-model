import streamlit as st
import pandas as pd
import requests
from nba_api.stats.endpoints import leaguedashteamstats, scoreboardv2
from nba_api.stats.static import teams
from datetime import datetime, timedelta
import re
import sqlite3

# 嘗試導入 plotly，若無則提示安裝
try:
    import plotly.express as px
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

# ------------------------
# 0 系統配置與資料庫整合
# ------------------------
st.set_page_config(page_title="NBA AI 操盤系統 V12.2", page_icon="🏀", layout="wide")

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
# 1 自動結算功能
# ------------------------
def auto_settle_results():
    conn = sqlite3.connect('nba_master.db')
    pending_df = pd.read_sql_query("SELECT * FROM history WHERE settled = 0", conn)
    
    if not pending_df.empty:
        unique_dates = pending_df['date'].unique()
        for d_str in unique_dates:
            try:
                sb = scoreboardv2.ScoreboardV2(game_date=d_str)
                linescore = sb.get_data_frames()[1]
                
                for index, row in pending_df[pending_df['date'] == d_str].iterrows():
                    try:
                        away_n, home_n = row['game'].split(' @ ')
                        h_id = [t['id'] for t in teams.get_teams() if t['full_name'] == home_n][0]
                        a_id = [t['id'] for t in teams.get_teams() if t['full_name'] == away_n][0]
                        
                        h_score = linescore[linescore['TEAM_ID'] == h_id]['PTS'].values[0]
                        a_score = linescore[linescore['TEAM_ID'] == a_id]['PTS'].values[0]
                        
                        actual_diff = h_score - a_score
                        # 贏盤判定邏輯
                        is_win_spread = (row['pred_spread'] > row['user_spread'] and actual_diff > row['user_spread']) or \
                                        (row['pred_spread'] < row['user_spread'] and actual_diff < row['user_spread'])
                        res_spread = "Win" if is_win_spread else "Loss"
                        
                        actual_total = h_score + a_score
                        is_win_total = (row['pred_total'] > row['user_total'] and actual_total > row['user_total']) or \
                                       (row['pred_total'] < row['user_total'] and actual_total < row['user_total'])
                        res_total = "Win" if is_win_total else "Loss"

                        conn.execute("""UPDATE history SET actual_home_score=?, actual_away_score=?, 
                                        settled=1, result_spread=?, result_total=? WHERE id=?""",
                                     (int(h_score), int(a_score), res_spread, res_total, row['id']))
                    except: continue
            except: continue
        conn.commit()
    conn.close()

# ------------------------
# 2 核心數據引擎 (V12 邏輯)
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

# ------------------------
# 3 主程式 UI
# ------------------------
auto_settle_results() # 開啟即結算

with st.spinner("NBA 數據同步中..."):
    team_dict, games, stats_s, stats_l, avg_off, b2b = fetch_nba_data()
    try:
        r = requests.get("https://www.cbssports.com/nba/injuries/", timeout=10)
        inj_text = r.text.lower()
    except: inj_text = ""

if not games.empty:
    game_list = []
    for _, row in games.iterrows():
        h, a = team_dict.get(row["HOME_TEAM_ID"]), team_dict.get(row["VISITOR_TEAM_ID"])
        if h and a:
            game_list.append({"label": f"{a} @ {h}", "h_id": row["HOME_TEAM_ID"], "a_id": row["VISITOR_TEAM_ID"], "h_n": h, "a_n": a})
    
    sel = st.selectbox("選擇賽事進行分析", game_list, format_func=lambda x: x["label"])
    
    # 這裡放入你 V12 的權重計算邏輯
    h_s = stats_s[stats_s["TEAM_ID"] == sel["h_id"]].iloc[0]
    a_s = stats_s[stats_s["TEAM_ID"] == sel["a_id"]].iloc[0]
    
    # 預測分值計算 (基礎模型)
    h_pred = (h_s["OFF_RATING"] / 100) * h_s["PACE"] + (3.0 if sel["h_id"] not in b2b else 0.5)
    a_pred = (a_s["OFF_RATING"] / 100) * a_s["PACE"]
    
    spread, total = h_pred - a_pred, h_pred + a_pred

    st.write(f"### 🤖 AI 預測結果")
    c1, c2 = st.columns(2)
    c1.metric(f"{sel['h_n']} 讓分", f"{spread:.1f}")
    c2.metric("預測總分", f"{total:.1f}")
    
    u_s = st.number_input("請輸入當前盤口讓分 (主隊為準)", value=0.0, step=0.5)
    u_t = st.number_input("請輸入當前盤口總分", value=220.0, step=0.5)
    
    if st.button("📥 儲存今日預測 (用於回測)"):
        conn = sqlite3.connect('nba_master.db')
        conn.execute("INSERT INTO history (date, game, pred_spread, user_spread, pred_total, user_total) VALUES (?,?,?,?,?,?)",
                  (datetime.now().strftime("%Y-%m-%d"), sel["label"], spread, u_s, total, u_t))
        conn.commit(); conn.close()
        st.success("紀錄成功！明天重新開啟 App 時將自動對帳。")

# ------------------------
# 4 歷史戰績看板
# ------------------------
st.divider()
st.header("📊 操盤歷史回測")

conn = sqlite3.connect('nba_master.db')
hist_df = pd.read_sql_query("SELECT * FROM history WHERE settled = 1", conn)
conn.close()

if not hist_df.empty:
    if PLOTLY_AVAILABLE:
        fig = px.pie(hist_df, names='result_spread', title='讓分盤勝率分佈', color_discrete_sequence=['#2ecc71', '#e74c3c'])
        st.plotly_chart(fig)
    else:
        st.warning("請安裝 plotly 以顯示圖表 (pip install plotly)")
    
    st.write("### 歷史結算清單")
    st.dataframe(hist_df[['date', 'game', 'result_spread', 'result_total', 'actual_home_score', 'actual_away_score']].tail(10))
else:
    st.info("目前尚無結算紀錄，請先儲存預測並等待比賽結果。")