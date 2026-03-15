import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from nba_api.stats.endpoints import leaguedashteamstats, scoreboardv2, leaguedashplayerstats
from nba_api.stats.static import teams
from datetime import datetime, timedelta
import re

# ------------------------
# 0 隊名與 2026 核心球員庫
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

# 補強後的核心監控名單
STAR_PLAYERS = {
    "Lakers": ["LeBron James", "Anthony Davis"],
    "Nuggets": ["Nikola Jokic", "Jamal Murray"],
    "Celtics": ["Jayson Tatum", "Jaylen Brown"],
    "Mavericks": ["Luka Doncic", "Kyrie Irving"],
    "Thunder": ["Shai Gilgeous-Alexander", "Chet Holmgren"],
    "Timberwolves": ["Anthony Edwards", "Rudy Gobert"],
    "Bucks": ["Giannis Antetokounmpo", "Damian Lillard"],
    "Suns": ["Kevin Durant", "Devin Booker"],
    "Warriors": ["Stephen Curry"],
    "Spurs": ["Victor Wembanyama"],
    "Sixers": ["Joel Embiid", "Tyrese Maxey"],
    "Cavaliers": ["Donovan Mitchell"]
}

# ------------------------
# 1 強化版傷兵爬蟲 (Scraper 升級)
# ------------------------
@st.cache_data(ttl=600)
def fetch_injury_raw():
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
    urls = [
        "https://www.cbssports.com/nba/injuries/",
        "https://www.espn.com/nba/injuries"
    ]
    all_text = ""
    for url in urls:
        try:
            r = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(r.text, 'html.parser')
            # 抓取包含球員表格的區塊
            all_text += soup.get_text(separator=' ', strip=True).lower()
        except: continue
    return all_text

def get_injury_impact(team_name, raw_text):
    mascot = team_name.split()[-1]
    penalty, reports, has_gtd = 0, [], False
    
    # 特殊處理 76人 (API 與網頁簡稱可能不同)
    search_key = "76ers" if mascot == "76ers" else mascot
    
    if search_key in STAR_PLAYERS:
        for player in STAR_PLAYERS[search_key]:
            # 搜尋姓氏以提高命中率
            last_name = player.split()[-1].lower()
            if last_name in raw_text:
                # 擷取名字後方 150 字元進行狀態判定
                idx = raw_text.find(last_name)
                chunk = raw_text[idx:idx+150]
                
                if "out" in chunk or "expected to be out" in chunk:
                    penalty += 8.0
                    reports.append(f"🚨 {player} [確定缺陣 Out]")
                elif any(word in chunk for word in ["questionable", "gtd", "day-to-day", "decision"]):
                    penalty += 4.0
                    reports.append(f"⚠️ {player} [出戰成疑 Questionable]")
                    has_gtd = True
                elif "probable" in chunk:
                    reports.append(f"✅ {player} [大概率出戰 Probable]")
    return penalty, reports, has_gtd

# ------------------------
# 2 數據引擎
# ------------------------
@st.cache_data(ttl=3600)
def fetch_nba_master():
    team_dict = {t["id"]: t["full_name"] for t in teams.get_teams()}
    games = scoreboardv2.ScoreboardV2().get_data_frames()[0]
    s_h = leaguedashteamstats.LeagueDashTeamStats(measure_type_detailed_defense="Advanced", location_nullable="Home").get_data_frames()[0]
    s_a = leaguedashteamstats.LeagueDashTeamStats(measure_type_detailed_defense="Advanced", location_nullable="Road").get_data_frames()[0]
    return team_dict, games, s_h, s_a

# ------------------------
# 3 主 UI 流程
# ------------------------
st.set_page_config(page_title="NBA AI 實戰 V20.1", page_icon="🏀", layout="wide")
st.title("🏀 NBA AI 終極實戰 V20.1 (傷兵偵測修正版)")

with st.spinner("正在掃描各大體育台傷兵報告..."):
    t_dict, games_df, s_h, s_a = fetch_nba_master()
    raw_inj = fetch_injury_raw()

# 診斷模式：顯示抓取的文字片段 (確認爬蟲有沒有活著)
with st.expander("🛠️ 傷兵爬蟲診斷數據 (點開確認)"):
    if len(raw_inj) > 100:
        st.write("✅ 成功抓取傷兵報告文字。")
        st.text(raw_inj[:500] + "...")
    else:
        st.error("❌ 爬蟲未抓到文字，請檢查網路。")

if games_df.empty:
    st.info("今日暫無賽程。")
else:
    match_list = []
    for _, row in games_df.iterrows():
        h_n = t_dict.get(row["HOME_TEAM_ID"])
        a_n = t_dict.get(row["VISITOR_TEAM_ID"])
        
        # 抓取雙方數據與傷兵
        h_pen, h_rep, h_gtd = get_injury_impact(h_n, raw_inj)
        a_pen, a_rep, a_gtd = get_injury_impact(a_n, raw_inj)
        
        # 簡單模型 (主客分離)
        h_data = s_h[s_h["TEAM_NAME"] == h_n].iloc[0]
        a_data = s_a[s_a["TEAM_NAME"] == a_n].iloc[0]
        h_score = (h_data["OFF_RATING"] * (h_data["PACE"]/100)) + 2.5 - h_pen
        a_score = (a_data["OFF_RATING"] * (a_data["PACE"]/100)) - a_pen
        
        match_list.append({
            "label": f"{a_n} ({TEAM_CN.get(a_n)}) @ {h_n} ({TEAM_CN.get(h_n)})",
            "h_n": h_n, "a_n": a_n, "h_s": h_score, "a_s": a_score,
            "reports": h_rep + a_rep, "gtd": h_gtd or a_gtd
        })

    selected = st.selectbox("選擇比賽深度分析", match_list, format_func=lambda x: x["label"])

    # 儀表板
    c1, c2, c3 = st.columns(3)
    with c1: st.metric(f"🏠 {selected['h_n']}", f"{selected['h_s']:.1f}")
    with c2: st.markdown(f"<h3 style='text-align:center;'>預測讓分: {selected['h_s']-selected['a_s']:.1f}</h3>", unsafe_allow_html=True)
    with c3: st.metric(f"✈️ {selected['a_n']}", f"{selected['a_s']:.1f}")

    # 顯示分析結果
    st.divider()
    if selected["reports"]:
        st.subheader("📋 傷兵影響分析")
        for r in selected["reports"]:
            if "🚨" in r: st.error(r)
            else: st.warning(r)
        if selected["gtd"]:
            st.info("💡 提醒：有核心處於成疑狀態，建議明天開賽前再確認盤口。")
    else:
        st.success("✅ 目前該場次核心主力均無傷兵紀錄 (或尚未更新)。")