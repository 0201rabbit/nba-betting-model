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

STAR_PLAYERS = {
    "Lakers": ["LeBron James", "Anthony Davis", "D'Angelo Russell", "Austin Reaves"], 
    "Nuggets": ["Nikola Jokic", "Jamal Murray", "Aaron Gordon", "Michael Porter Jr."],
    "Celtics": ["Jayson Tatum", "Jaylen Brown", "Kristaps Porzingis", "Derrick White", "Jrue Holiday"], 
    "Mavericks": ["Luka Doncic", "Kyrie Irving", "Dereck Lively"],
    "Thunder": ["Shai Gilgeous-Alexander", "Chet Holmgren", "Jalen Williams"], 
    "Timberwolves": ["Anthony Edwards", "Rudy Gobert", "Karl-Anthony Towns"],
    "Bucks": ["Giannis Antetokounmpo", "Damian Lillard", "Khris Middleton"], 
    "Warriors": ["Stephen Curry", "Draymond Green", "Jonathan Kuminga", "Andrew Wiggins"]
}

PLAYER_CN = {
    "LeBron James": "詹姆斯", "Anthony Davis": "戴維斯", "D'Angelo Russell": "羅素", "Austin Reaves": "里夫斯",
    "Nikola Jokic": "約基奇", "Jamal Murray": "莫瑞", "Aaron Gordon": "高登", "Michael Porter Jr.": "小波特",
    "Jayson Tatum": "塔圖姆", "Jaylen Brown": "布朗", "Kristaps Porzingis": "波辛吉斯", "Derrick White": "懷特", "Jrue Holiday": "哈勒戴",
    "Luka Doncic": "唐西奇", "Kyrie Irving": "厄文", "Dereck Lively": "萊夫利",
    "Shai Gilgeous-Alexander": "亞歷山大", "Chet Holmgren": "霍姆格倫", "Jalen Williams": "威廉斯",
    "Anthony Edwards": "愛德華茲", "Rudy Gobert": "戈貝爾", "Karl-Anthony Towns": "唐斯",
    "Giannis Antetokounmpo": "字母哥", "Damian Lillard": "里拉德", "Khris Middleton": "米德爾頓",
    "Stephen Curry": "柯瑞", "Draymond Green": "格林", "Jonathan Kuminga": "庫明加", "Andrew Wiggins": "威金斯"
}

# ------------------------
# 1 數據抓取優化 (防重複、防假比分)
# ------------------------
@st.cache_data(ttl=600)
def fetch_injury_raw():
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get("https://www.cbssports.com/nba/injuries/", headers=headers, timeout=10)
        return BeautifulSoup(r.text, 'html.parser').get_text(separator=' ', strip=True).lower()
    except: return ""

def get_injury_impact(team_name, raw_text):
    mascot = team_name.split()[-1]
    penalty, reports, has_gtd = 0, [], False
    search_key = "76ers" if mascot == "76ers" else mascot
    if search_key in STAR_PLAYERS:
        for player in STAR_PLAYERS[search_key]:
            last_name = player.split()[-1].lower()
            if last_name in raw_text:
                idx = raw_text.find(last_name)
                chunk = raw_text[idx:idx+150]
                p_cn = PLAYER_CN.get(player, "球員")
                if "out" in chunk:
                    penalty += 8.0
                    reports.append(f"🚨 {player}({p_cn}) - 確定缺陣")
                elif any(word in chunk for word in ["questionable", "gtd", "decision"]):
                    penalty += 4.0
                    reports.append(f"⚠️ {player}({p_cn}) - 出戰成疑")
                    has_gtd = True
    return penalty, reports, has_gtd

@st.cache_data(ttl=3600)
def fetch_nba_master(game_date):
    team_dict = {t["id"]: t["full_name"] for t in teams.get_teams()}
    sb = scoreboardv2.ScoreboardV2(game_date=game_date)
    # 修正重點 1: 強制去重
    games = sb.get_data_frames()[0].drop_duplicates(subset=['GAME_ID'])
    line_score = sb.get_data_frames()[1]
    s_h = leaguedashteamstats.LeagueDashTeamStats(measure_type_detailed_defense="Advanced", location_nullable="Home").get_data_frames()[0]
    s_a = leaguedashteamstats.LeagueDashTeamStats(measure_type_detailed_defense="Advanced", location_nullable="Road").get_data_frames()[0]
    p_stats = leaguedashplayerstats.LeagueDashPlayerStats(measure_type_detailed_defense="Advanced").get_data_frames()[0]
    return team_dict, games, line_score, s_h, s_a, p_stats

# ------------------------
# 2 主介面與實戰建議邏輯
# ------------------------
st.set_page_config(page_title="NBA AI 終極實戰 V22.5", layout="wide")
st.sidebar.header("🗓️ 歷史回測與實戰")
target_date = st.sidebar.date_input("選擇日期", datetime.now() - timedelta(hours=8))
formatted_date = target_date.strftime('%Y-%m-%d')

st.title(f"🏀 NBA AI 終極實戰 V22.5 ({formatted_date})")

with st.spinner("同步 NBA 數據庫..."):
    t_dict, games_df, line_df, s_h, s_a, p_stats = fetch_nba_master(formatted_date)
    raw_inj = fetch_injury_raw()

if games_df.empty:
    st.info("📅 今日暫無賽程。")
else:
    match_data = []
    for _, row in games_df.iterrows():
        h_id, a_id = row["HOME_TEAM_ID"], row["VISITOR_TEAM_ID"]
        h_n, a_n = t_dict.get(h_id), t_dict.get(a_id)
        
        # 修正重點 2: 判定是否完賽，防止 13:17 這種笑話分數
        h_act = line_df[line_df['TEAM_ID'] == h_id]['PTS'].values[0] if not line_df.empty and h_id in line_df['TEAM_ID'].values else 0
        a_act = line_df[line_df['TEAM_ID'] == a_id]['PTS'].values[0] if not line_df.empty and a_id in line_df['TEAM_ID'].values else 0
        is_finished = (h_act + a_act > 160) # NBA 全場總分通常大於 160

        h_pen, h_rep, h_gtd = get_injury_impact(h_n, raw_inj)
        a_pen, a_rep, a_gtd = get_injury_impact(a_n, raw_inj)
        
        try:
            h_d, a_d = s_h[s_h["TEAM_NAME"] == h_n].iloc[0], s_a[s_a["TEAM_NAME"] == a_n].iloc[0]
            h_abb = "".join([i[0] for i in h_n.split() if i[0].isupper()])
            h_pie = p_stats[p_stats["TEAM_ABBREVIATION"] == h_abb]["PIE"].max()
            h_edge = (h_pie - 12) * 0.5 if h_pie > 12 else 0
            
            # 簡化預測模型邏輯
            h_s = (h_d["OFF_RATING"] * (h_d["PACE"]/100)) + 2.5 - h_pen + h_edge
            a_s = (a_d["OFF_RATING"] * (a_d["PACE"]/100)) - a_pen
            
            match_data.append({
                "label": f"{TEAM_CN.get(a_n, a_n)} @ {TEAM_CN.get(h_n, h_n)}",
                "h_n": h_n, "a_n": a_n, "h_s": h_s, "a_s": a_s,
                "h_act": h_act if is_finished else None, "a_act": a_act if is_finished else None,
                "reports": h_rep + a_rep, "gtd": h_gtd or a_gtd,
                "is_finished": is_finished
            })
        except: continue

    # --- 🎯 串關看板 (對應截圖 3) ---
    st.header("🎯 AI 智能串關攻略看板")
    safe_list = [m for m in match_data if not m["gtd"]]
    if len(safe_list) >= 2:
        c1, c2, c3 = st.columns(3)
        with c1:
            st.success("🔥 【首選 2 串 1】(最穩組合)")
            st.write(f"1. {safe_list[0]['label']} -> **主勝**")
            st.write(f"2. {safe_list[1]['label']} -> **主勝**")
        with c2:
            st.info("🚀 【高賠 3 串 1】")
            if len(safe_list) >= 3: st.write(f"3. {safe_list[2]['label']} -> **客受讓**")
        with c3:
            st.warning("🛡️ 【鎖盤備案】")
            st.write("若盤口變動，優先替換為大分場次。")

    # --- 💰 台彩實戰輸入 (對應截圖 2) ---
    st.divider()
    selected = st.selectbox("🔍 選擇分析場次", match_data, format_func=lambda x: x["label"])
    
    col1, col2, col3 = st.columns(3)
    col1.metric(f"🏠 {selected['h_n']}", f"{selected['h_s']:.1f}")
    col2.markdown(f"<h3 style='text-align:center;'>預測分差: {selected['h_s']-selected['a_s']:.1f}<br>預測總分: {selected['h_s']+selected['a_s']:.1f}</h3>", unsafe_allow_html=True)
    col3.metric(f"✈️ {selected['a_n']}", f"{selected['a_s']:.1f}")

    st.subheader("📝 台彩盤口輸入與實戰建議")
    ci1, ci2, ci3 = st.columns(3)
    with ci1: u_ml = st.number_input("【不讓分】主隊賠率", value=1.18, step=0.01)
    with ci2: u_spread = st.number_input("【讓分】主隊讓分值 (如 -7.5)", value=-7.5, step=0.5)
    with ci3: u_total = st.number_input("【大小分】分界點", value=225.5, step=0.5)

    st.subheader("💡 系統判定結果")
    edge = (selected['h_s'] - selected['a_s'])
    if u_ml >= 1.15 and edge > abs(u_spread):
        st.success(f"🔥 [不讓分] 這是 Value Bet！台彩賠率 ({u_ml}) 值得單壓或串關！")
    else:
        st.info("⚖️ 盤口精準，建議觀望。")

    st.subheader("🛌 睡前下注資金建議")
    if not selected["gtd"]:
        st.success("🛡️ 陣容穩定：目前無重大傷病疑慮。適合安心下注，當作串關主力。")
    else:
        st.error("⚠️ 變數極高：主將 GTD，建議注碼減半或等開賽名單。")

    # --- 📊 歷史回測數據表 (對應截圖 1) ---
    st.divider()
    st.header("📊 歷史回測數據表")
    backtest_list = []
    for m in match_data:
        hit = "待定"
        if m["is_finished"]:
            ai_win = m["h_s"] > m["a_s"]
            act_win = m["h_act"] > m["a_act"]
            hit = "✅" if ai_win == act_win else "❌"
        
        backtest_list.append({
            "label": m["label"],
            "AI預估(主)": round(m["h_s"], 1),
            "AI預估(客)": round(m["a_s"], 1),
            "實際(主)": m["h_act"],
            "實際(客)": m["a_act"],
            "勝負命中": hit
        })
    st.table(pd.DataFrame(backtest_list))

st.caption("NBA AI V22.5 - 核心功能完全回歸版")