import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from nba_api.stats.endpoints import leaguedashteamstats, scoreboardv2, leaguedashplayerstats
from nba_api.stats.static import teams
from datetime import datetime, timedelta

# ------------------------
# 0 核心配置與中英對照
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

# (STAR_PLAYERS 與 PLAYER_CN 保持不變)

# ------------------------
# 1 數據引擎 (防重複、防假比分)
# ------------------------
@st.cache_data(ttl=600)
def fetch_injury_raw():
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get("https://www.cbssports.com/nba/injuries/", headers=headers, timeout=10)
        return BeautifulSoup(r.text, 'html.parser').get_text(separator=' ', strip=True).lower()
    except: return ""

@st.cache_data(ttl=3600)
def fetch_nba_master(game_date):
    team_dict = {t["id"]: t["full_name"] for t in teams.get_teams()}
    sb = scoreboardv2.ScoreboardV2(game_date=game_date)
    # 強制去重
    games = sb.get_data_frames()[0].drop_duplicates(subset=['GAME_ID'])
    line_score = sb.get_data_frames()[1]
    s_h = leaguedashteamstats.LeagueDashTeamStats(measure_type_detailed_defense="Advanced", location_nullable="Home").get_data_frames()[0]
    s_a = leaguedashteamstats.LeagueDashTeamStats(measure_type_detailed_defense="Advanced", location_nullable="Road").get_data_frames()[0]
    p_stats = leaguedashplayerstats.LeagueDashPlayerStats(measure_type_detailed_defense="Advanced").get_data_frames()[0]
    return team_dict, games, line_score, s_h, s_a, p_stats

# ------------------------
# 2 建議玩法邏輯
# ------------------------
def get_rec_play(h_s, a_s):
    diff = h_s - a_s
    total = h_s + a_s
    if abs(diff) > 8.5: return f"{'主' if diff > 0 else '客'}不讓分"
    if total > 232: return "全場大分"
    if total < 215: return "全場小分"
    return f"{'主' if diff > 0 else '客'}隊讓分"

# ------------------------
# 3 主介面
# ------------------------
st.set_page_config(page_title="NBA AI 實戰 V22.6", layout="wide")
st.sidebar.header("🗓️ 歷史回測控制")
target_date = st.sidebar.date_input("選擇日期", datetime.now() - timedelta(hours=8))
formatted_date = target_date.strftime('%Y-%m-%d')

st.title(f"🏀 NBA AI 終極分析與回測 ({formatted_date})")

with st.spinner("同步數據中..."):
    t_dict, games_df, line_df, s_h, s_a, p_stats = fetch_nba_master(formatted_date)
    raw_inj = fetch_injury_raw()

if games_df.empty:
    st.info("📅 此日期暫無賽程數據。")
else:
    match_data = []
    for _, row in games_df.iterrows():
        h_id, a_id = row["HOME_TEAM_ID"], row["VISITOR_TEAM_ID"]
        h_n, a_n = t_dict.get(h_id), t_dict.get(a_id)
        
        # 判定是否完賽 (防止抓到 13:17 的假分數)
        h_act = line_df[line_df['TEAM_ID'] == h_id]['PTS'].values[0] if not line_df.empty and h_id in line_df['TEAM_ID'].values else 0
        a_act = line_df[line_df['TEAM_ID'] == a_id]['PTS'].values[0] if not line_df.empty and a_id in line_df['TEAM_ID'].values else 0
        is_finished = (h_act + a_act > 160)

        try:
            h_d, a_d = s_h[s_h["TEAM_NAME"] == h_n].iloc[0], s_a[s_a["TEAM_NAME"] == a_n].iloc[0]
            # 簡化模型分數
            h_s = round((h_d["OFF_RATING"] * (h_d["PACE"]/100)) + 2.5, 1)
            a_s = round((a_d["OFF_RATING"] * (a_d["PACE"]/100)), 1)
            
            # 判斷命中 (AI 預測勝負 vs 實際勝負)
            hit = "待定"
            if is_finished:
                hit = "✅" if (h_s > a_s and h_act > a_act) or (h_s < a_s and h_act < a_act) else "❌"

            match_data.append({
                "組別": f"{TEAM_CN.get(a_n, a_n)} @ {TEAM_CN.get(h_n, h_n)}",
                "AI主": h_s, "AI客": a_s,
                "實際主": h_act if is_finished else "--",
                "實際客": a_act if is_finished else "--",
                "建議玩法": get_rec_play(h_s, a_s),
                "勝負命中": hit,
                "is_finished": is_finished,
                "h_n": h_n, "a_n": a_n
            })
        except: continue

    # --- 顯示命中率統計 (側邊欄) ---
    finished_games = [m for m in match_data if m["is_finished"]]
    if finished_games:
        acc = sum(1 for m in finished_games if m["勝負命中"] == "✅") / len(finished_games)
        st.sidebar.metric("🎯 本日 AI 勝負命中率", f"{acc:.1%}")
    else:
        st.sidebar.write("⌛ 比賽尚未結束，暫無命中率統計。")

    # --- 歷史回測數據表 (主畫面) ---
    st.header("📊 AI 預測 vs 實際結果回測表")
    df_main = pd.DataFrame(match_data)
    st.dataframe(df_main[["組別", "AI主", "AI客", "實際主", "實際客", "建議玩法", "勝負命中"]], use_container_width=True)

    # --- 🎯 串關推薦 ---
    st.divider()
    st.header("🎯 AI 推薦串關組合")
    if len(match_data) >= 2:
        c1, c2 = st.columns(2)
        c1.success(f"🔥 首選組合：{match_data[0]['組別']} ({match_data[0]['建議玩法']}) + {match_data[1]['組別']} ({match_data[1]['建議玩法']})")
        c2.info("💡 建議注碼：建議平注，若有主將缺陣則避開該場。")

    # --- 💰 台彩實戰輸入 ---
    st.divider()
    selected = st.selectbox("🔍 選擇單場深度解析", match_data, format_func=lambda x: x["組別"])
    
    ci1, ci2, ci3 = st.columns(3)
    with ci1: u_spread = st.number_input("台彩主隊讓分值", value=-7.5, step=0.5)
    with ci2: u_total = st.number_input("台彩大小分界限", value=220.5, step=0.5)
    
    # 判斷優勢 (Edge)
    ai_diff = selected['AI主'] - selected['AI客']
    edge = ai_diff - u_spread
    st.write(f"📊 AI 預估分差 ({ai_diff:.1f}) vs 台彩讓分 ({u_spread}) -> **優勢分：{edge:.1f}**")
    if abs(edge) > 4:
        st.success("🔥 發現高價值盤口 (Value Bet)！建議注資。")
    else:
        st.warning("⚖️ 盤口與 AI 預期接近，建議小注或觀望。")

st.caption("NBA AI V22.6 - 數據美化與功能完整回歸版")