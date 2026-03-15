import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from nba_api.stats.endpoints import leaguedashteamstats, scoreboardv2, leaguedashplayerstats
from nba_api.stats.static import teams
from datetime import datetime, timedelta

# ------------------------
# 0 隊名與核心球員中文對照庫
# ------------------------
TEAM_CN = {
    "Atlanta Hawks": "老鷹", "Boston Celtics": "塞爾提克", "Brooklyn Nets": "籃網",
    "Charlotte Hornets": "黃蜂", "Chicago Bulls": "公牛", "Cleveland Cavaliers": "騎士",
    "Dallas Mavericks": "獨行俠", "Denver Nuggets": "金塊", "Detroit Pistons": "活塞",
    "Golden State Warriors": "勇勇", "Houston Rockets": "火箭", "Indiana Pacers": "溜馬",
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
    "Suns": ["Kevin Durant", "Devin Booker", "Bradley Beal"],
    "Warriors": ["Stephen Curry", "Draymond Green", "Jonathan Kuminga", "Andrew Wiggins"], 
    "Spurs": ["Victor Wembanyama", "Devin Vassell"], 
    "76ers": ["Joel Embiid", "Tyrese Maxey", "Paul George", "Kelly Oubre"], 
    "Cavaliers": ["Donovan Mitchell", "Darius Garland", "Evan Mobley", "Jarrett Allen"], 
    "Knicks": ["Jalen Brunson", "Karl-Anthony Towns", "OG Anunoby", "Mikal Bridges"],
    "Heat": ["Jimmy Butler", "Bam Adebayo", "Tyler Herro"],
    "Clippers": ["Kawhi Leonard", "James Harden", "Norman Powell"],
    "Kings": ["De'Aaron Fox", "Domantas Sabonis", "DeMar DeRozan"]
}

PLAYER_CN = {
    "LeBron James": "詹姆斯", "Anthony Davis": "戴維斯", "D'Angelo Russell": "羅素", "Austin Reaves": "里夫斯",
    "Nikola Jokic": "約基奇", "Jamal Murray": "莫瑞", "Aaron Gordon": "高登", "Michael Porter Jr.": "小波特",
    "Jayson Tatum": "塔圖姆", "Jaylen Brown": "布朗", "Kristaps Porzingis": "波辛吉斯", "Derrick White": "懷特", "Jrue Holiday": "哈勒戴",
    "Luka Doncic": "唐西奇", "Kyrie Irving": "厄文", "Dereck Lively": "萊夫利",
    "Shai Gilgeous-Alexander": "亞歷山大", "Chet Holmgren": "霍姆格倫", "Jalen Williams": "威廉斯",
    "Anthony Edwards": "愛德華茲", "Rudy Gobert": "戈貝爾", "Karl-Anthony Towns": "唐斯",
    "Giannis Antetokounmpo": "字母哥", "Damian Lillard": "里拉德", "Khris Middleton": "米德爾頓",
    "Kevin Durant": "杜蘭特", "Devin Booker": "布克", "Bradley Beal": "比爾",
    "Stephen Curry": "柯瑞", "Draymond Green": "格林", "Jonathan Kuminga": "庫明加", "Andrew Wiggins": "威金斯",
    "Victor Wembanyama": "文班亞馬", "Devin Vassell": "瓦賽爾",
    "Joel Embiid": "恩比德", "Tyrese Maxey": "馬克西", "Paul George": "喬治", "Kelly Oubre": "烏布瑞",
    "Donovan Mitchell": "米契爾", "Darius Garland": "葛蘭", "Evan Mobley": "莫布里", "Jarrett Allen": "艾倫",
    "Jalen Brunson": "布朗森", "OG Anunoby": "阿努諾比", "Mikal Bridges": "布里吉斯",
    "Jimmy Butler": "巴特勒", "Bam Adebayo": "阿德巴約", "Tyler Herro": "赫洛",
    "Kawhi Leonard": "雷納德", "James Harden": "哈登", "Norman Powell": "鮑威爾",
    "De'Aaron Fox": "福克斯", "Domantas Sabonis": "沙波尼斯", "DeMar DeRozan": "德羅展"
}

# ------------------------
# 1 數據引擎與傷兵爬蟲
# ------------------------
@st.cache_data(ttl=600)
def fetch_injury_raw():
    headers = {"User-Agent": "Mozilla/5.0"}
    url = "https://www.cbssports.com/nba/injuries/"
    try:
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        return soup.get_text(separator=' ', strip=True).lower()
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
                p_cn = PLAYER_CN.get(player, "未知")
                t_cn = TEAM_CN.get(team_name, mascot)
                if "out" in chunk or "expected to be out" in chunk:
                    penalty += 8.0
                    reports.append(f"🚨 {player} ({p_cn}) - {t_cn} [確定缺陣 Out]")
                elif any(word in chunk for word in ["questionable", "gtd", "day-to-day", "decision"]):
                    penalty += 4.0
                    reports.append(f"⚠️ {player} ({p_cn}) - {t_cn} [出戰成疑 GTD]")
                    has_gtd = True
    return penalty, reports, has_gtd

@st.cache_data(ttl=3600)
def fetch_nba_master(game_date):
    team_dict = {t["id"]: t["full_name"] for t in teams.get_teams()}
    sb = scoreboardv2.ScoreboardV2(game_date=game_date)
    games = sb.get_data_frames()[0]
    line_score = sb.get_data_frames()[1]
    
    s_h = leaguedashteamstats.LeagueDashTeamStats(measure_type_detailed_defense="Advanced", location_nullable="Home").get_data_frames()[0]
    s_a = leaguedashteamstats.LeagueDashTeamStats(measure_type_detailed_defense="Advanced", location_nullable="Road").get_data_frames()[0]
    p_stats = leaguedashplayerstats.LeagueDashPlayerStats(measure_type_detailed_defense="Advanced").get_data_frames()[0]
    return team_dict, games, line_score, s_h, s_a, p_stats

# ------------------------
# 2 智能玩法推薦器
# ------------------------
def get_bet_recommendation(h_score, a_score):
    spread = h_score - a_score
    total = h_score + a_score
    if abs(spread) > 9.0: return f"[不讓分] {'主勝' if spread > 0 else '客勝'}"
    elif total > 233.0: return "[大小分] 大分"
    elif total < 212.0: return "[大小分] 小分"
    else: return f"[讓分] {'主隊' if spread > 0 else '客隊'}"

# ------------------------
# 3 主介面
# ------------------------
st.set_page_config(page_title="NBA AI 終極回測 V22.1", page_icon="🏀", layout="wide")

# 側邊欄控制台
st.sidebar.header("📅 回測控制台")
target_date = st.sidebar.date_input("選擇賽事日期", datetime.now() - timedelta(hours=8))
formatted_date = target_date.strftime('%Y-%m-%d')

st.title(f"🏀 NBA AI 終極實戰分析 (日期: {formatted_date})")

with st.spinner("正在同步 NBA 官方數據庫與即時傷兵名單..."):
    t_dict, games_df, line_df, s_h, s_a, p_stats = fetch_nba_master(formatted_date)
    raw_inj = fetch_injury_raw()

if games_df.empty:
    st.info(f"📅 {formatted_date} 暫無賽程數據，請嘗試選擇其他日期。")
else:
    match_list = []
    for _, row in games_df.iterrows():
        h_id, a_id = row["HOME_TEAM_ID"], row["VISITOR_TEAM_ID"]
        h_n, a_n = t_dict.get(h_id), t_dict.get(a_id)
        
        # 抓取實際比分
        h_actual = line_df[line_df['TEAM_ID'] == h_id]['PTS'].values[0] if not line_df.empty and h_id in line_df['TEAM_ID'].values else None
        a_actual = line_df[line_df['TEAM_ID'] == a_id]['PTS'].values[0] if not line_df.empty and a_id in line_df['TEAM_ID'].values else None

        h_pen, h_rep, h_gtd = get_injury_impact(h_n, raw_inj)
        a_pen, a_rep, a_gtd = get_injury_impact(a_n, raw_inj)
        
        try:
            h_data = s_h[s_h["TEAM_NAME"] == h_n].iloc[0]
            a_data = s_a[s_a["TEAM_NAME"] == a_n].iloc[0]
            
            h_abb = "".join([i[0] for i in h_n.split() if i[0].isupper()])
            a_abb = "".join([i[0] for i in a_n.split() if i[0].isupper()])
            h_pie = p_stats[p_stats["TEAM_ABBREVIATION"] == h_abb]["PIE"].max()
            a_pie = p_stats[p_stats["TEAM_ABBREVIATION"] == a_abb]["PIE"].max()
            h_edge = (h_pie - 12) * 0.5 if h_pie > 12 else 0
            a_edge = (a_pie - 12) * 0.5 if a_pie > 12 else 0
            
            # 預測公式
            h_score = (h_data["OFF_RATING"] * (h_data["PACE"]/100)) + 2.5 - h_pen + h_edge
            a_score = (a_data["OFF_RATING"] * (a_data["PACE"]/100)) - a_pen + a_edge
            
            match_list.append({
                "組別": f"{TEAM_CN.get(a_n, a_n)} @ {TEAM_CN.get(h_n, h_n)}",
                "h_n": h_n, "a_n": a_n,
                "AI預估(主)": round(h_score, 1),
                "AI預估(客)": round(a_score, 1),
                "實際(主)": h_actual,
                "實際(客)": a_actual,
                "勝負命中": "✅" if h_actual is not None and ((h_score > a_score and h_actual > a_actual) or (h_score < a_score and h_actual < a_actual)) else "❌",
                "傷兵": "有" if h_rep or a_rep else "無",
                "建議": get_bet_recommendation(h_score, a_score),
                "reports": h_rep + a_rep,
                "gtd": h_gtd or a_gtd
            })
        except Exception as e:
            continue

    # --- 數據展示看板 ---
    st.header("📊 AI 預測 vs 實際結果對照")
    if match_list:
        df_display = pd.DataFrame(match_list)
        st.dataframe(df_display[["組別", "AI預估(主)", "AI預估(客)", "實際(主)", "實際(客)", "勝負命中", "傷兵", "建議"]], use_container_width=True)
        
        # 側邊欄勝率統計
        if any(m["實際(主)"] is not None for m in match_list):
            valid_games = [m for m in match_list if m["實際(主)"] is not None]
            hit_rate = sum(1 for m in valid_games if m["勝負命中"] == "✅") / len(valid_games)
            st.sidebar.metric("本日 AI 勝負命中率", f"{hit_rate:.1%}")
    
    # --- 詳細解析 (修正 TypeError 處) ---
    st.divider()
    if match_list:
        selected_game = st.selectbox("🔍 選擇場次查看深度分析與傷兵報告", match_list, format_func=lambda x: x["組別"])
        
        col1, col2, col3 = st.columns(3)
        col1.metric(f"🏠 {TEAM_CN.get(selected_game['h_n'], selected_game['h_n'])}", f"{selected_game['AI預估(主)']} 分")
        col2.markdown(f"<h3 style='text-align:center;'>預測讓分: {selected_game['AI預估(主)']-selected_game['AI預估(客)']:.1f}<br>預測總分: {selected_game['AI預估(主)']+selected_game['AI預估(客)']:.1f}</h3>", unsafe_allow_html=True)
        col3.metric(f"✈️ {TEAM_CN.get(selected_game['a_n'], selected_game['a_n'])}", f"{selected_game['AI預估(客)']} 分")

        st.subheader("📋 關鍵傷兵報告")
        if selected_game["reports"]:
            for r in selected_game["reports"]:
                if "🚨" in r: st.error(r)
                else: st.warning(r)
        else:
            st.success("✅ 該場次核心主力目前均正常出賽。")
            
        if selected_game["gtd"]:
            st.warning("🛌 提醒：此場次有球員出戰成疑 (GTD)，建議等到賽前 30 分鐘確認名單。")
    else:
        st.warning("暫無比賽細節可顯示。")

st.divider()
st.caption("數據來源: NBA API & CBS Sports. 本工具僅供數據分析參考，不構成投注建議。")