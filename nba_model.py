import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from nba_api.stats.endpoints import leaguedashteamstats, scoreboardv2, leaguedashplayerstats
from nba_api.stats.static import teams
from datetime import datetime, timedelta

# ------------------------
# 0 核心配置與中英庫
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
# 1 數據引擎
# ------------------------
@st.cache_data(ttl=3600)
def fetch_nba_master(game_date):
    team_dict = {t["id"]: t["full_name"] for t in teams.get_teams()}
    sb = scoreboardv2.ScoreboardV2(game_date=game_date)
    games = sb.get_data_frames()[0].drop_duplicates(subset=['GAME_ID'])
    line_score = sb.get_data_frames()[1]
    s_h = leaguedashteamstats.LeagueDashTeamStats(measure_type_detailed_defense="Advanced", location_nullable="Home").get_data_frames()[0]
    s_a = leaguedashteamstats.LeagueDashTeamStats(measure_type_detailed_defense="Advanced", location_nullable="Road").get_data_frames()[0]
    p_stats = leaguedashplayerstats.LeagueDashPlayerStats(measure_type_detailed_defense="Advanced").get_data_frames()[0]
    return team_dict, games, line_score, s_h, s_a, p_stats

# ------------------------
# 2 主介面
# ------------------------
st.set_page_config(page_title="NBA AI 實戰 V23.0", layout="wide")
st.sidebar.header("🗓️ 歷史回測控制")
target_date = st.sidebar.date_input("選擇日期", datetime(2026, 3, 15))
formatted_date = target_date.strftime('%Y-%m-%d')

st.title(f"🏀 NBA AI 終極分析與回測 ({formatted_date})")

with st.spinner("同步數據中..."):
    t_dict, games_df, line_df, s_h, s_a, p_stats = fetch_nba_master(formatted_date)

if games_df.empty:
    st.info("📅 此日期暫無賽程數據。")
else:
    match_data = []
    for _, row in games_df.iterrows():
        h_id, a_id = row["HOME_TEAM_ID"], row["VISITOR_TEAM_ID"]
        h_n_en, a_n_en = t_dict.get(h_id), t_dict.get(a_id)
        h_n, a_n = TEAM_CN.get(h_n_en, h_n_en), TEAM_CN.get(a_n_en, a_n_en)
        
        h_act = line_df[line_df['TEAM_ID'] == h_id]['PTS'].values[0] if not line_df.empty and h_id in line_df['TEAM_ID'].values else 0
        a_act = line_df[line_df['TEAM_ID'] == a_id]['PTS'].values[0] if not line_df.empty and a_id in line_df['TEAM_ID'].values else 0
        is_finished = (h_act + a_act > 160)

        try:
            h_d = s_h[s_h["TEAM_NAME"] == h_n_en].iloc[0]
            a_d = s_a[s_a["TEAM_NAME"] == a_n_en].iloc[0]
            
            # 修正版預測公式 (四捨五入到整數比較直覺)
            h_s = round((h_d["OFF_RATING"] * (h_d["PACE"]/100)) + 2.5)
            a_s = round((a_d["OFF_RATING"] * (a_d["PACE"]/100)))
            
            # 勝負判定邏輯
            hit = "待定"
            if is_finished:
                hit = "✅" if (h_s > a_s and h_act > a_act) or (h_s < a_s and h_act < a_act) else "❌"

            match_data.append({
                "對戰": f"{a_n} (客) @ {h_n} (主)",
                "AI預估": f"{a_s} : {h_s}",
                "實際比分": f"{a_act} : {h_act}" if is_finished else "進行中",
                "建議玩法": "主勝" if h_s > a_s else "客勝",
                "勝負命中": hit,
                "is_finished": is_finished,
                "h_name": h_n, "a_name": a_n,
                "h_s": h_s, "a_s": a_s, "h_act": h_act, "a_act": a_act
            })
        except: continue

    # --- 1. 命中率統計 ---
    done = [m for m in match_data if m["is_finished"]]
    if done:
        rate = sum(1 for m in done if m["勝負命中"] == "✅") / len(done)
        st.sidebar.metric("🎯 本日 AI 勝負命中率", f"{rate:.1%}")

    # --- 2. 顯示回測表 ---
    st.header("📊 AI 預測結果回測表")
    st.table(pd.DataFrame(match_data)[["對戰", "AI預估", "實際比分", "建議玩法", "勝負命中"]])

    # --- 3. 串關建議 ---
    st.divider()
    st.header("🎯 AI 推薦串關組合")
    if len(match_data) >= 2:
        st.success(f"🔥 首選組合：{match_data[0]['對戰']} ({match_data[0]['建議玩法']}) + {match_data[1]['對戰']} ({match_data[1]['建議玩法']})")

    # --- 4. 盤口輸入器 ---
    st.divider()
    s_game = st.selectbox("🔍 選擇單場深度解析", match_data, format_func=lambda x: x["對戰"])
    c1, c2 = st.columns(2)
    with c1:
        u_spread = st.number_input(f"台彩給 {s_game['h_name']} 的讓分 (如 -5.5)", value=-5.5, step=0.5)
    with c2:
        ai_diff = s_game['h_s'] - s_game['a_s']
        st.write(f"📊 AI 預估分差：{ai_diff} | 台彩分差：{u_spread}")
        if (ai_diff - u_spread) > 3: st.success("🔥 推薦主隊過盤")
        elif (ai_diff - u_spread) < -3: st.success("🔥 推薦客隊過盤")
        else: st.warning("⚖️ 盤口精準，建議觀望")