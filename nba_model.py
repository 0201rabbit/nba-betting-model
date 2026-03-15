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
# 0 系統配置與資料庫 (自動結算邏輯)
# ------------------------
st.set_page_config(page_title="NBA AI 終極操盤手 V14.1", page_icon="🏀", layout="wide")

def init_db():
    conn = sqlite3.connect('nba_v14_master.db')
    c = conn.cursor()
    # 確保資料庫包含結算欄位
    c.execute('''CREATE TABLE IF NOT EXISTS history 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, game TEXT, 
                  pred_spread REAL, user_spread REAL, pred_total REAL, user_total REAL,
                  actual_home_score INTEGER, actual_away_score INTEGER,
                  settled INTEGER DEFAULT 0, result_spread TEXT, result_total TEXT)''')
    conn.commit()
    conn.close()

init_db()

# --- [自動結算引擎] ---
def auto_settle_results():
    conn = sqlite3.connect('nba_v14_master.db')
    pending_df = pd.read_sql_query("SELECT * FROM history WHERE settled = 0", conn)
    
    if not pending_df.empty:
        unique_dates = pending_df['date'].unique()
        for d_str in unique_dates:
            try:
                # 抓取該日比分 (使用 scoreboardv2)
                sb = scoreboardv2.ScoreboardV2(game_date=d_str)
                # 取得 LineScore 表 (包含各隊總分)
                linescore = sb.get_data_frames()[1] 
                
                for _, row in pending_df[pending_df['date'] == d_str].iterrows():
                    try:
                        # 解析 "客隊 @ 主隊"
                        away_n, home_n = row['game'].split(' @ ')
                        h_id = [t['id'] for t in teams.get_teams() if t['full_name'] == home_n][0]
                        a_id = [t['id'] for t in teams.get_teams() if t['full_name'] == away_n][0]
                        
                        # 取得實際得分
                        h_score = int(linescore[linescore['TEAM_ID'] == h_id]['PTS'].values[0])
                        a_score = int(linescore[linescore['TEAM_ID'] == a_id]['PTS'].values[0])
                        
                        # 結算判斷 (與 V8/V12 邏輯一致)
                        actual_diff = h_score - a_score
                        # 讓分判定：若 AI 預測大於盤口且實際也大於盤口 -> Win
                        res_spread = "Win" if (row['pred_spread'] > row['user_spread'] and actual_diff > row['user_spread']) or \
                                             (row['pred_spread'] < row['user_spread'] and actual_diff < row['user_spread']) else "Loss"
                        
                        actual_total = h_score + a_score
                        res_total = "Win" if (row['pred_total'] > row['user_total'] and actual_total > row['user_total']) or \
                                            (row['pred_total'] < row['user_total'] and actual_total < row['user_total']) else "Loss"

                        conn.execute("""UPDATE history SET actual_home_score=?, actual_away_score=?, 
                                        settled=1, result_spread=?, result_total=? WHERE id=?""",
                                     (h_score, a_score, res_spread, res_total, row['id']))
                    except: continue
            except: continue
        conn.commit()
    conn.close()

# ------------------------
# 1 數據引擎與傷兵解析 (V12 + V13)
# ------------------------
STAR_PLAYERS = {
    "Celtics": ["Jayson Tatum", "Jaylen Brown"], "Nuggets": ["Nikola Jokic", "Jamal Murray"],
    "Lakers": ["LeBron James", "Anthony Davis"], "Suns": ["Kevin Durant", "Devin Booker"],
    "Warriors": ["Stephen Curry", "Draymond Green"], "Mavericks": ["Luka Doncic", "Kyrie Irving"],
    "Bucks": ["Giannis Antetokounmpo", "Damian Lillard"], "76ers": ["Joel Embiid", "Tyrese Maxey"],
    "Clippers": ["Kawhi Leonard", "James Harden"], "Spurs": ["Victor Wembanyama"]
}

@st.cache_data(ttl=3600)
def fetch_data_v14():
    team_dict = {t["id"]: t["full_name"] for t in teams.get_teams()}
    games = scoreboardv2.ScoreboardV2().get_data_frames()[0]
    stats_s = leaguedashteamstats.LeagueDashTeamStats(measure_type_detailed_defense="Advanced").get_data_frames()[0]
    stats_l = leaguedashteamstats.LeagueDashTeamStats(measure_type_detailed_defense="Advanced", last_n_games=10).get_data_frames()[0]
    avg_off = stats_s["OFF_RATING"].mean()
    return team_dict, games, stats_s, stats_l, avg_off

@st.cache_data(ttl=900)
def fetch_injuries():
    try:
        r = requests.get("https://www.cbssports.com/nba/injuries/", headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        return r.text.lower()
    except: return ""

def parse_injury_v14(team_name, inj_text):
    mascot = team_name.split()[-1]
    penalty, reports, has_gtd = 0, [], False
    if mascot in STAR_PLAYERS:
        for p in STAR_PLAYERS[mascot]:
            last = p.split()[-1].lower()
            if last in inj_text:
                idx = inj_text.find(last)
                context = inj_text[idx:idx+100]
                if "out" in context:
                    penalty += 8.0; reports.append(f"🚨 {p} (確定缺陣)")
                elif "probable" in context:
                    reports.append(f"✅ {p} (穩定出戰)")
                else:
                    penalty += 4.0; reports.append(f"⚠️ {p} (出戰成疑)"); has_gtd = True
    return penalty, reports, has_gtd

# ------------------------
# 2 主程式執行流程
# ------------------------
st.title("🏀 NBA AI 終極全能操盤系統 V14.1")

# 第一步：執行自動結算 (每次啟動時自動跑)
auto_settle_results()

with st.spinner("同步數據與對帳中..."):
    team_dict, games, stats_s, stats_l, avg_off = fetch_data_v14()
    inj_text = fetch_injuries()

if games.empty:
    st.info("📅 今日暫無賽程。")
else:
    # --- 單場深度解析與推薦 (與 V14 同) ---
    all_res = []
    for _, row in games.iterrows():
        h_n, a_n = team_dict.get(row["HOME_TEAM_ID"]), team_dict.get(row["VISITOR_TEAM_ID"])
        h_s = stats_s[stats_s["TEAM_ID"] == row["HOME_TEAM_ID"]].iloc[0]
        a_s = stats_s[stats_s["TEAM_ID"] == row["VISITOR_TEAM_ID"]].iloc[0]
        h_l = stats_l[stats_l["TEAM_ID"] == row["HOME_TEAM_ID"]].iloc[0]
        a_l = stats_l[stats_l["TEAM_ID"] == row["VISITOR_TEAM_ID"]].iloc[0]
        
        h_off = h_s["OFF_RATING"] * 0.6 + h_l["OFF_RATING"] * 0.4
        a_off = a_s["OFF_RATING"] * 0.6 + a_l["OFF_RATING"] * 0.4
        h_def = h_s["DEF_RATING"] * 0.6 + h_l["DEF_RATING"] * 0.4
        a_def = a_s["DEF_RATING"] * 0.6 + a_l["DEF_RATING"] * 0.4
        pace = (h_s["PACE"] + a_s["PACE"]) / 2
        
        h_pen, h_rep, h_gtd = parse_injury_v14(h_n, inj_text)
        a_pen, a_rep, a_gtd = parse_injury_v14(a_n, inj_text)
        
        h_score = (h_off * (pace/100) * (avg_off/a_def)) + 2.8 - h_pen
        a_score = (a_off * (pace/100) * (avg_off/h_def)) - a_pen
        
        all_res.append({
            "label": f"{a_n} @ {h_n}", "h_n": h_n, "a_n": a_n,
            "h_score": h_score, "a_score": a_score, "spread": h_score - a_score, "total": h_score + a_score,
            "reports": h_rep + a_rep, "has_gtd": h_gtd or a_gtd
        })

    # 串關推薦 UI
    st.divider()
    st.subheader("🎯 今日串關推薦")
    safe = [g for g in all_res if not g["has_gtd"]]
    if len(safe) >= 2:
        best = sorted(safe, key=lambda x: abs(x["spread"]), reverse=True)[:2]
        st.success(f"🔥 最佳串關組合：{best[0]['label']} + {best[1]['label']}")

    # 分析與儲存 UI
    selected = st.selectbox("分析比賽", all_res, format_func=lambda x: x["label"])
    c1, c2, c3 = st.columns(3)
    with c1: st.metric(selected["a_n"], f"{selected['a_score']:.1f}")
    with c2: st.markdown(f"<p style='text-align:center;'>預測讓分: {selected['spread']:.1f}<br>預測總分: {selected['total']:.1f}</p>", unsafe_allow_html=True)
    with c3: st.metric(selected["h_n"], f"{selected['h_score']:.1f}")

    u_spread = st.number_input("輸入讓分盤口", value=0.0, step=0.5)
    u_total = st.number_input("輸入大小分盤口", value=220.0, step=0.5)

    if st.button("📥 儲存預測並開啟明日結算"):
        conn = sqlite3.connect('nba_v14_master.db')
        conn.execute("INSERT INTO history (date, game, pred_spread, user_spread, pred_total, user_total) VALUES (?,?,?,?,?,?)",
                  (datetime.now().strftime("%Y-%m-%d"), selected["label"], selected["spread"], u_spread, selected["total"], u_total))
        conn.commit(); conn.close()
        st.success("已紀錄！明天開啟 App 時會自動抓取比分對帳。")

# ------------------------
# 3 績效看盤室 (回測數據)
# ------------------------
st.divider()
st.header("📊 歷史戰績對帳看板")

conn = sqlite3.connect('nba_v14_master.db')
df = pd.read_sql_query("SELECT * FROM history WHERE settled = 1", conn)
conn.close()

if not df.empty:
    m1, m2, m3 = st.columns(3)
    s_win = (df['result_spread'] == "Win").mean() * 100
    m1.metric("讓分盤勝率", f"{s_win:.1f}%")
    m2.metric("總結算場次", len(df))
    m3.metric("最近狀態", df['result_spread'].iloc[-1])
    
    st.write("### 歷史結算明細 (Win/Loss)")
    st.dataframe(df[['date', 'game', 'result_spread', 'actual_home_score', 'actual_away_score']].tail(10))
else:
    st.info("尚無結算紀錄。請儲存預測，系統會在隔日自動對帳。")