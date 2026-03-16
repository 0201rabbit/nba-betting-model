import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from nba_api.stats.endpoints import leaguedashteamstats, scoreboardv2, leaguedashplayerstats
from nba_api.stats.static import teams
from datetime import datetime, timedelta

# ------------------------
# 0 核心配置與中英對照庫
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
    "Warriors": ["Stephen Curry", "Draymond Green", "Jonathan Kuminga", "Andrew Wiggins"],
    "Suns": ["Kevin Durant", "Devin Booker", "Bradley Beal"],
    "76ers": ["Joel Embiid", "Tyrese Maxey", "Paul George"],
    "Clippers": ["Kawhi Leonard", "James Harden"],
    "Heat": ["Jimmy Butler", "Bam Adebayo"],
    "Kings": ["De'Aaron Fox", "Domantas Sabonis"]
}

PLAYER_CN = {
    "LeBron James": "詹姆斯", "Anthony Davis": "戴維斯", "D'Angelo Russell": "羅素", "Austin Reaves": "里夫斯",
    "Nikola Jokic": "約基奇", "Jamal Murray": "莫瑞", "Aaron Gordon": "高登", "Michael Porter Jr.": "小波特",
    "Jayson Tatum": "塔圖姆", "Jaylen Brown": "布朗", "Kristaps Porzingis": "波辛吉斯", "Derrick White": "懷特", "Jrue Holiday": "哈勒戴",
    "Luka Doncic": "唐西奇", "Kyrie Irving": "厄文", "Dereck Lively": "萊夫利",
    "Shai Gilgeous-Alexander": "亞歷山大", "Chet Holmgren": "霍姆格倫", "Jalen Williams": "威廉斯",
    "Anthony Edwards": "愛德華茲", "Rudy Gobert": "戈貝爾", "Karl-Anthony Towns": "唐斯",
    "Giannis Antetokounmpo": "字母哥", "Damian Lillard": "里拉德", "Khris Middleton": "米德爾頓",
    "Stephen Curry": "柯瑞", "Draymond Green": "格林", "Jonathan Kuminga": "庫明加", "Andrew Wiggins": "威金斯",
    "Kevin Durant": "杜蘭特", "Devin Booker": "布克", "Bradley Beal": "比爾",
    "Joel Embiid": "恩比德", "Tyrese Maxey": "馬克西", "Paul George": "喬治",
    "Kawhi Leonard": "雷納德", "James Harden": "哈登",
    "Jimmy Butler": "巴特勒", "Bam Adebayo": "阿德巴約",
    "De'Aaron Fox": "福克斯", "Domantas Sabonis": "沙波尼斯"
}

# ------------------------
# 1 傷兵與數據引擎 (極速讀取版)
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
                p_cn = PLAYER_CN.get(player, player)
                if "out" in chunk or "expected to be out" in chunk:
                    penalty += 7.0
                    reports.append(f"🚨 {p_cn} - 確定缺陣")
                elif any(word in chunk for word in ["questionable", "gtd", "decision"]):
                    penalty += 3.5
                    reports.append(f"⚠️ {p_cn} - 出戰成疑(GTD)")
                    has_gtd = True
    return penalty, reports, has_gtd

@st.cache_data(ttl=3600)
def fetch_nba_master(game_date):
    team_dict = {t["id"]: t["full_name"] for t in teams.get_teams()}
    
    # 賽程與比分依然綁定日期，確保抓到對的比賽
    sb = scoreboardv2.ScoreboardV2(game_date=game_date)
    games = sb.get_data_frames()[0].drop_duplicates(subset=['GAME_ID'])
    line_score = sb.get_data_frames()[1]
    
    # 🚨 拔除超時參數，恢復極速抓取賽季總平均
    s_h = leaguedashteamstats.LeagueDashTeamStats(measure_type_detailed_defense="Advanced", location_nullable="Home").get_data_frames()[0]
    s_a = leaguedashteamstats.LeagueDashTeamStats(measure_type_detailed_defense="Advanced", location_nullable="Road").get_data_frames()[0]
    p_stats = leaguedashplayerstats.LeagueDashPlayerStats(measure_type_detailed_defense="Advanced").get_data_frames()[0]
    
    return team_dict, games, line_score, s_h, s_a, p_stats

# ------------------------
# 2 主介面與實戰分析
# ------------------------
st.set_page_config(page_title="NBA AI 攻防大師 V24.3", layout="wide", page_icon="🏀")
st.sidebar.header("🗓️ 歷史回測與實戰控制")
target_date = st.sidebar.date_input("選擇賽事日期", datetime.now() - timedelta(hours=8))
formatted_date = target_date.strftime('%Y-%m-%d')

st.title(f"🏀 NBA AI 終極分析與回測 ({formatted_date})")

with st.spinner("極速同步 NBA 數據庫與最新傷兵名單中..."):
    t_dict, games_df, line_df, s_h, s_a, p_stats = fetch_nba_master(formatted_date)
    raw_inj = fetch_injury_raw()

if games_df.empty:
    st.info("📅 此日期暫無賽程數據，請嘗試選擇其他日期。")
else:
    match_data = []
    for _, row in games_df.iterrows():
        h_id, a_id = row["HOME_TEAM_ID"], row["VISITOR_TEAM_ID"]
        h_n_en, a_n_en = t_dict.get(h_id), t_dict.get(a_id)
        h_n, a_n = TEAM_CN.get(h_n_en, h_n_en), TEAM_CN.get(a_n_en, a_n_en)
        
        # ⚠️ 安全處理比分，防止 TypeError
        try:
            h_pts_raw = line_df.loc[line_df['TEAM_ID'] == h_id, 'PTS'].values
            a_pts_raw = line_df.loc[line_df['TEAM_ID'] == a_id, 'PTS'].values
            
            h_act = int(float(h_pts_raw[0])) if len(h_pts_raw) > 0 and pd.notna(h_pts_raw[0]) else 0
            a_act = int(float(a_pts_raw[0])) if len(a_pts_raw) > 0 and pd.notna(a_pts_raw[0]) else 0
        except:
            h_act, a_act = 0, 0
            
        is_finished = (h_act > 0 and a_act > 0 and (h_act + a_act) > 150)

        h_pen, h_rep, h_gtd = get_injury_impact(h_n_en, raw_inj)
        a_pen, a_rep, a_gtd = get_injury_impact(a_n_en, raw_inj)

        try:
            h_d = s_h[s_h["TEAM_NAME"] == h_n_en].iloc[0]
            a_d = s_a[s_a["TEAM_NAME"] == a_n_en].iloc[0]
            
            # 攻防一體演算法
            game_pace = (h_d["PACE"] + a_d["PACE"]) / 2
            h_base_rating = (h_d["OFF_RATING"] + a_d["DEF_RATING"]) / 2
            a_base_rating = (a_d["OFF_RATING"] + h_d["DEF_RATING"]) / 2
            
            # 球星加權
            h_abb = "".join([i[0] for i in h_n_en.split() if i[0].isupper()])
            a_abb = "".join([i[0] for i in a_n_en.split() if i[0].isupper()])
            h_pie = p_stats[p_stats["TEAM_ABBREVIATION"] == h_abb]["PIE"].max()
            a_pie = p_stats[p_stats["TEAM_ABBREVIATION"] == a_abb]["PIE"].max()
            h_edge = (h_pie - 12) * 0.4 if h_pie > 12 else 0
            a_edge = (a_pie - 12) * 0.4 if a_pie > 12 else 0
            
            h_s = round((h_base_rating * (game_pace/100)) + 2.5 - h_pen + h_edge)
            a_s = round((a_base_rating * (game_pace/100)) - a_pen + a_edge)
            
            ai_pick = "主勝" if h_s > a_s else "客勝"
            
            hit = "待定"
            if is_finished:
                hit = "✅" if (h_s > a_s and h_act > a_act) or (h_s < a_s and h_act < a_act) else "❌"

            match_data.append({
                "對戰組合": f"{a_n} (客) @ {h_n} (主)",
                "AI預估(客:主)": f"{a_s} : {h_s}",
                "實際比分(客:主)": f"{a_act} : {h_act}" if is_finished else "進行中/未開賽",
                "預測勝負": ai_pick,
                "勝負命中": hit,
                "h_name": h_n, "a_name": a_n,
                "h_s": h_s, "a_s": a_s, 
                "h_act": h_act, "a_act": a_act,
                "is_finished": is_finished,
                "reports": h_rep + a_rep,
                "gtd": h_gtd or a_gtd
            })
        except: continue

    # ==========================================
    # 以下功能完美保留，加上防護網確保 UI 不消失
    # ==========================================
    if match_data:
        # --- 1. 命中率統計 (側邊欄) ---
        done = [m for m in match_data if m["is_finished"]]
        if done:
            rate = sum(1 for m in done if m["勝負命中"] == "✅") / len(done)
            st.sidebar.metric("🎯 本日 AI 勝負命中率", f"{rate:.1%}")
        else:
            st.sidebar.info("⌛ 比賽尚未結束，暫無命中率可統計。")

        # --- 2. 歷史回測表 (主畫面) ---
        st.header("📊 AI 攻防預測 vs 實際結果回測表")
        st.dataframe(pd.DataFrame(match_data)[["對戰組合", "AI預估(客:主)", "實際比分(客:主)", "預測勝負", "勝負命中"]], use_container_width=True)

        # --- 3. 串關推薦 ---
        st.divider()
        st.header("🎯 AI 智能串關推薦")
        safe_games = [m for m in match_data if not m["gtd"]]
        safe_games = sorted(safe_games, key=lambda x: abs(x["h_s"] - x["a_s"]), reverse=True)
        
        if len(safe_games) >= 2:
            c1, c2 = st.columns(2)
            c1.success("🔥 【首選 2 串 1 組合】(無重大傷兵疑慮)")
            c1.write(f"1. **{safe_games[0]['對戰組合']}** ➡️ 推薦：**{safe_games[0]['預測勝負']}**")
            c1.write(f"2. **{safe_games[1]['對戰組合']}** ➡️ 推薦：**{safe_games[1]['預測勝負']}**")
            c2.info("💡 操盤提示：這兩場預測分差最大且陣容穩定，適合做為串關主軸。")
        else:
            st.warning("⚠️ 今日安全場次不足，建議單場下注觀望。")

        # --- 4. 單場深度解析與盤口輸入 ---
        st.divider()
        st.header("🔍 單場深度解析與台彩盤口比對")
        s_game = st.selectbox("請選擇要深入分析的場次：", match_data, format_func=lambda x: x["對戰組合"])
        
        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader("📝 傷兵與陣容報告")
            if s_game["reports"]:
                for r in s_game["reports"]: st.warning(r)
            else:
                st.success("✅ 本場核心主力均正常出賽。")
                
        with col_b:
            st.subheader("💰 台彩讓分盤口輸入")
            u_spread = st.number_input(f"請輸入台彩開給【{s_game['h_name']}】的讓分 (例: -4.5)", value=-4.5, step=0.5)
            
            ai_diff = s_game['h_s'] - s_game['a_s']
            edge = ai_diff - u_spread
            
            st.write(f"▶️ **AI 預估主隊淨勝分：** `{ai_diff}` 分")
            st.write(f"▶️ **台彩主隊讓分值：** `{u_spread}` 分")
            st.write(f"▶️ **盤口優勢差 (Edge)：** `{edge}` 分")
            
            if edge >= 4.0:
                st.success(f"🔥 強烈推薦：**{s_game['h_name']} (主) 過盤**！AI 認為主隊會贏得比盤口開的還要多。")
            elif edge <= -4.0:
                st.success(f"🔥 強烈推薦：**{s_game['a_name']} (客) 過盤**！AI 認為客隊極具競爭力。")
            else:
                st.warning("⚖️ 盤口開得很精準，無明顯獲利空間，建議避開讓分盤。")
    else:
        st.warning("🚨 目前抓取不到任何有效場次進行分析，這可能是因為 API 尚未更新今日賽程。")

st.caption("NBA AI V24.3 - 極速防當機完整版")