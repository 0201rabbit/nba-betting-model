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

# 🛡️ V28.0 新增：球隊地理分區 (用於計算長途飛行疲勞)
TEAM_ZONE = {
    "Atlanta Hawks": "East", "Boston Celtics": "East", "Brooklyn Nets": "East",
    "Charlotte Hornets": "East", "Chicago Bulls": "East", "Cleveland Cavaliers": "East",
    "Detroit Pistons": "East", "Indiana Pacers": "East", "Miami Heat": "East",
    "Milwaukee Bucks": "East", "New York Knicks": "East", "Orlando Magic": "East",
    "Philadelphia 76ers": "East", "Toronto Raptors": "East", "Washington Wizards": "East",
    "Dallas Mavericks": "West", "Denver Nuggets": "West", "Golden State Warriors": "West",
    "Houston Rockets": "West", "LA Clippers": "West", "Los Angeles Lakers": "West",
    "Memphis Grizzlies": "West", "Minnesota Timberwolves": "West", "New Orleans Pelicans": "West",
    "Oklahoma City Thunder": "West", "Phoenix Suns": "West", "Portland Trail Blazers": "West",
    "Sacramento Kings": "West", "San Antonio Spurs": "West", "Utah Jazz": "West"
}

# 🛡️ V28.0 新增：The Odds API 隊名對照表 (解決 API 之間命名不一致)
ODDS_API_TEAMS = {
    "Atlanta Hawks": "Atlanta Hawks", "Boston Celtics": "Boston Celtics", "Brooklyn Nets": "Brooklyn Nets",
    "Charlotte Hornets": "Charlotte Hornets", "Chicago Bulls": "Chicago Bulls", "Cleveland Cavaliers": "Cleveland Cavaliers",
    "Dallas Mavericks": "Dallas Mavericks", "Denver Nuggets": "Denver Nuggets", "Detroit Pistons": "Detroit Pistons",
    "Golden State Warriors": "Golden State Warriors", "Houston Rockets": "Houston Rockets", "Indiana Pacers": "Indiana Pacers",
    "LA Clippers": "Los Angeles Clippers", "Los Angeles Lakers": "Los Angeles Lakers", "Memphis Grizzlies": "Memphis Grizzlies",
    "Miami Heat": "Miami Heat", "Milwaukee Bucks": "Milwaukee Bucks", "Minnesota Timberwolves": "Minnesota Timberwolves",
    "New Orleans Pelicans": "New Orleans Pelicans", "New York Knicks": "New York Knicks", "Oklahoma City Thunder": "Oklahoma City Thunder",
    "Orlando Magic": "Orlando Magic", "Philadelphia 76ers": "Philadelphia 76ers", "Phoenix Suns": "Phoenix Suns",
    "Portland Trail Blazers": "Portland Trail Blazers", "Sacramento Kings": "Sacramento Kings", "San Antonio Spurs": "San Antonio Spurs",
    "Toronto Raptors": "Toronto Raptors", "Utah Jazz": "Utah Jazz", "Washington Wizards": "Washington Wizards"
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
# 1 傷兵、數據與盤口引擎 
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
    out_players = [] 
    search_key = "76ers" if mascot == "76ers" else mascot 
    t_cn = TEAM_CN.get(team_name, team_name) 
    
    if search_key in STAR_PLAYERS: 
        for player in STAR_PLAYERS[search_key]: 
            full_name = player.lower() 
            if full_name in raw_text: 
                idx = raw_text.find(full_name) 
                chunk = raw_text[idx:idx+150] 
                p_cn = PLAYER_CN.get(player, player) 
                if "out" in chunk or "expected to be out" in chunk: 
                    penalty += 5.0  
                    reports.append(f"🚨 [{t_cn}] {p_cn} - 確定缺陣") 
                    out_players.append(player) 
                elif any(word in chunk for word in ["questionable", "gtd", "decision"]): 
                    penalty += 2.5 
                    reports.append(f"⚠️ [{t_cn}] {p_cn} - 出戰成疑(GTD)") 
                    has_gtd = True 
                    out_players.append(player) 
    
    penalty = min(penalty, 8.5) 
    return penalty, reports, has_gtd, out_players 

@st.cache_data(ttl=3600) 
def fetch_nba_master(game_date_str): 
    game_date_obj = datetime.strptime(game_date_str, '%Y-%m-%d')
    date_api_format = game_date_obj.strftime('%m/%d/%Y') 
    yest_str = (game_date_obj - timedelta(days=1)).strftime('%Y-%m-%d')

    team_dict = {t["id"]: t["full_name"] for t in teams.get_teams()} 
    
    sb = scoreboardv2.ScoreboardV2(game_date=game_date_str) 
    games = sb.get_data_frames()[0].drop_duplicates(subset=['GAME_ID']) 
    line_score = sb.get_data_frames()[1] 
    
    sb_yest = scoreboardv2.ScoreboardV2(game_date=yest_str)
    yest_games = sb_yest.get_data_frames()[0]
    
    # 🛡️ V28.0 改良：不僅要知道誰昨天有打，還要知道昨天是在「主場」還是「客場」打
    b2b_data = {}
    for _, y_row in yest_games.iterrows():
        b2b_data[y_row["HOME_TEAM_ID"]] = "Home"
        b2b_data[y_row["VISITOR_TEAM_ID"]] = "Away"
    
    s_h = leaguedashteamstats.LeagueDashTeamStats(measure_type_detailed_defense="Advanced", location_nullable="Home", date_to_nullable=date_api_format).get_data_frames()[0] 
    s_a = leaguedashteamstats.LeagueDashTeamStats(measure_type_detailed_defense="Advanced", location_nullable="Road", date_to_nullable=date_api_format).get_data_frames()[0] 
    p_stats = leaguedashplayerstats.LeagueDashPlayerStats(measure_type_detailed_defense="Advanced", date_to_nullable=date_api_format).get_data_frames()[0] 
    
    try:
        s_last5 = leaguedashteamstats.LeagueDashTeamStats(measure_type_detailed_defense="Advanced", last_n_games=5, date_to_nullable=date_api_format).get_data_frames()[0]
    except:
        s_last5 = pd.DataFrame()

    return team_dict, games, line_score, s_h, s_a, p_stats, b2b_data, s_last5

# 🛡️ V28.0 新增：自動抓取即時盤口
@st.cache_data(ttl=900) # 每15分鐘更新一次盤口
def fetch_live_odds(api_key):
    if not api_key: return {}
    try:
        url = f"https://api.the-odds-api.com/v4/sports/basketball_nba/odds/?apiKey={api_key}&regions=us&markets=spreads,totals&bookmakers=pinnacle"
        r = requests.get(url, timeout=10).json()
        odds_dict = {}
        for game in r:
            home = game.get('home_team')
            bookies = game.get('bookmakers', [])
            if not bookies: continue
            markets = bookies[0].get('markets', [])
            spread_val, total_val = None, None
            
            for m in markets:
                if m['key'] == 'spreads':
                    # 抓取主隊的讓分盤口
                    for outcome in m['outcomes']:
                        if outcome['name'] == home: spread_val = outcome['point']
                elif m['key'] == 'totals':
                    total_val = m['outcomes'][0]['point']
                    
            odds_dict[home] = {"spread": spread_val, "total": total_val}
        return odds_dict
    except:
        return {}

# ------------------------ 
# 2 主介面與實戰分析 
# ------------------------ 
st.set_page_config(page_title="NBA AI 攻防大師 V28.0", layout="wide", page_icon="🏀") 
st.sidebar.header("🗓️ 歷史回測與實戰控制") 
target_date = st.sidebar.date_input("選擇賽事日期", datetime.now() - timedelta(hours=8)) 
formatted_date = target_date.strftime('%Y-%m-%d') 

# 🛡️ V28.0 新增：API Key 輸入區
st.sidebar.divider()
st.sidebar.markdown("### 🤖 自動化盤口分析")
st.sidebar.caption("前往 [The Odds API](https://the-odds-api.com/) 點擊 'Get a Free API Key' 即可每月免費掃描 500 次最新盤口。")
api_key = st.sidebar.text_input("輸入 API 金鑰 (選填)", type="password")

st.title(f"🏀 NBA AI 終極分析與回測 ({formatted_date})") 

with st.spinner("極速同步 NBA 數據庫、運算疲勞度與自動化盤口中..."): 
    t_dict, games_df, line_df, s_h, s_a, p_stats, b2b_data, s_last5 = fetch_nba_master(formatted_date) 
    raw_inj = fetch_injury_raw() 
    live_odds = fetch_live_odds(api_key) if target_date == (datetime.now() - timedelta(hours=8)).date() else {}

if games_df.empty: 
    st.info("📅 此日期暫無賽程數據，請嘗試選擇其他日期。") 
else: 
    match_data = [] 
    is_historical = target_date < (datetime.now() - timedelta(hours=8)).date() 

    for _, row in games_df.iterrows(): 
        h_id, a_id = row["HOME_TEAM_ID"], row["VISITOR_TEAM_ID"] 
        h_n_en, a_n_en = t_dict.get(h_id), t_dict.get(a_id) 
        h_n, a_n = TEAM_CN.get(h_n_en, h_n_en), TEAM_CN.get(a_n_en, a_n_en) 
        
        try: 
            h_pts_raw = line_df.loc[line_df['TEAM_ID'] == h_id, 'PTS'].values 
            a_pts_raw = line_df.loc[line_df['TEAM_ID'] == a_id, 'PTS'].values 
            h_act = int(float(h_pts_raw[0])) if len(h_pts_raw) > 0 and pd.notna(h_pts_raw[0]) else 0 
            a_act = int(float(a_pts_raw[0])) if len(a_pts_raw) > 0 and pd.notna(a_pts_raw[0]) else 0 
        except: 
            h_act, a_act = 0, 0 
            
        is_finished = (h_act > 0 and a_act > 0 and (h_act + a_act) > 150) 

        h_pen, h_rep, h_gtd, h_out_players = get_injury_impact(h_n_en, raw_inj) 
        a_pen, a_rep, a_gtd, a_out_players = get_injury_impact(a_n_en, raw_inj) 
        
        if is_historical: 
            h_pen, a_pen = h_pen * 0.5, a_pen * 0.5 

        h_is_b2b = h_id in b2b_data
        a_is_b2b = a_id in b2b_data
        has_fatigue = h_is_b2b or a_is_b2b
        
        # 🛡️ V28.0 核心升級：精準計算長途客場疲勞 (Travel Fatigue)
        if h_is_b2b:
            h_pen += 3.5  
            h_rep.append(f"🔋 [{h_n}] 主場背靠背 (體能下滑)")
        if a_is_b2b:
            # 判斷昨天是在哪打的
            yest_loc = b2b_data[a_id]
            if yest_loc == "Away":
                # 連續兩天客場奔波
                a_pen += 5.5
                a_rep.append(f"✈️ [{a_n}] 連續客場背靠背 (嚴重飛行疲勞)")
            else:
                a_pen += 4.0
                a_rep.append(f"🔋 [{a_n}] 客場背靠背 (體能下滑)")

            # 跨時區懲罰 (簡易版：東區飛西區)
            if TEAM_ZONE.get(a_n_en) != TEAM_ZONE.get(h_n_en):
                a_pen += 1.5
                a_rep.append(f"🌎 [{a_n}] 跨區時差作戰 (疲勞加劇)")

        try: 
            h_d = s_h[s_h["TEAM_ID"] == h_id].iloc[0] 
            a_d = s_a[s_a["TEAM_ID"] == a_id].iloc[0] 
            
            if not s_last5.empty:
                h_l5 = s_last5[s_last5["TEAM_ID"] == h_id]
                a_l5 = s_last5[s_last5["TEAM_ID"] == a_id]
                
                if not h_l5.empty and not a_l5.empty:
                    h_off = (h_d["OFF_RATING"] * 0.7) + (h_l5.iloc[0]["OFF_RATING"] * 0.3)
                    h_def = (h_d["DEF_RATING"] * 0.7) + (h_l5.iloc[0]["DEF_RATING"] * 0.3)
                    a_off = (a_d["OFF_RATING"] * 0.7) + (a_l5.iloc[0]["OFF_RATING"] * 0.3)
                    a_def = (a_d["DEF_RATING"] * 0.7) + (a_l5.iloc[0]["DEF_RATING"] * 0.3)
                else:
                    h_off, h_def = h_d["OFF_RATING"], h_d["DEF_RATING"]
                    a_off, a_def = a_d["OFF_RATING"], a_d["DEF_RATING"]
            else:
                h_off, h_def = h_d["OFF_RATING"], h_d["DEF_RATING"]
                a_off, a_def = a_d["OFF_RATING"], a_d["DEF_RATING"]
            
            pace_h = h_d["PACE"]
            pace_a = a_d["PACE"]
            game_pace = (2 * pace_h * pace_a) / (pace_h + pace_a)
            
            h_base_rating = (h_off * 0.65) + (a_def * 0.35) 
            a_base_rating = (a_off * 0.65) + (h_def * 0.35) 
            
            h_win_pct = h_d["W_PCT"]
            a_win_pct = a_d["W_PCT"]
            elo_edge = (h_win_pct - a_win_pct) * 4.5 
            
            h_active_stats = p_stats[(p_stats["TEAM_ID"] == h_id) & (~p_stats["PLAYER_NAME"].isin(h_out_players))]
            a_active_stats = p_stats[(p_stats["TEAM_ID"] == a_id) & (~p_stats["PLAYER_NAME"].isin(a_out_players))]
            
            h_pie = h_active_stats["PIE"].max() if not h_active_stats.empty else 0
            a_pie = a_active_stats["PIE"].max() if not a_active_stats.empty else 0
            
            h_edge = (h_pie - 12) * 0.4 if h_pie > 12 else 0 
            a_edge = (a_pie - 12) * 0.4 if a_pie > 12 else 0 
            
            h_s = round((h_base_rating * (game_pace/100)) + 2.5 - h_pen + h_edge + (elo_edge / 2), 1) 
            a_s = round((a_base_rating * (game_pace/100)) - a_pen + a_edge - (elo_edge / 2), 1) 
            
            total_est = round(h_s + a_s, 1)
            total_act = h_act + a_act
            ai_diff = round(h_s - a_s, 1)

            # 🛡️ V28.0 新增：自動配對市場盤口並計算 Edge
            api_team_name = ODDS_API_TEAMS.get(h_n_en)
            market_spread = None
            market_edge = None
            if live_odds and api_team_name in live_odds:
                market_spread = live_odds[api_team_name].get("spread")
                if market_spread is not None:
                    market_edge = round(ai_diff - market_spread, 1)

            if abs(ai_diff) <= 1.0:
                ai_pick = "⚠️五五波(避開)"
            else:
                if market_edge is not None:
                    # 如果有接 API，用 Edge 來決定強烈推薦方向
                    if market_edge >= 4.0: ai_pick = f"主勝 (Edge: +{market_edge})"
                    elif market_edge <= -4.0: ai_pick = f"客勝 (Edge: {abs(market_edge)})"
                    else: ai_pick = "無顯著優勢"
                else:
                    ai_pick = "主勝" if h_s > a_s else "客勝" 
            
            hit = "待定" 
            if is_finished: 
                if "避開" in ai_pick or "無顯著優勢" in ai_pick:
                    hit = "無"  
                else:
                    hit = "✅" if (h_s > a_s and h_act > a_act) or (h_s < a_s and h_act < a_act) else "❌" 

            match_data.append({ 
                "對戰組合": f"{'✈️' if a_is_b2b else ''}{a_n} @ {'🔋' if h_is_b2b else ''}{h_n}", 
                "AI淨勝分(客:主)": f"{a_s} : {h_s}", 
                "市場讓分(主)": market_spread if market_spread is not None else "-",
                "預測與盤口優勢": ai_pick,
                "實際比分": f"{a_act} : {h_act}" if is_finished else "-", 
                "勝負命中": hit, 
                "h_name": h_n, "a_name": a_n, 
                "h_s": h_s, "a_s": a_s,  
                "total_est": total_est,       
                "is_finished": is_finished, 
                "reports": h_rep + a_rep, 
                "gtd": h_gtd or a_gtd,
                "has_fatigue": has_fatigue
            }) 
        except Exception as e: 
            continue 

    if match_data: 
        done = [m for m in match_data if m["is_finished"]] 
        done_valid = [m for m in done if m["勝負命中"] in ["✅", "❌"]]
        
        if done_valid: 
            rate = sum(1 for m in done_valid if m["勝負命中"] == "✅") / len(done_valid) 
            st.sidebar.metric("🎯 本日 AI 勝負命中率", f"{rate:.1%}") 
        else: 
            st.sidebar.info("⌛ 尚無有效預測結果可統計。") 

        st.header("📊 AI 攻防預測 vs 市場盤口分析") 
        # 顯示重點欄位
        display_df = pd.DataFrame(match_data)[["對戰組合", "AI淨勝分(客:主)", "市場讓分(主)", "預測與盤口優勢", "實際比分", "勝負命中"]]
        st.dataframe(display_df, use_container_width=True) 

        st.divider() 
        st.header("🎯 AI 智能推薦引擎 (分級風險控管)") 
        
        strict_safe_games = []
        risky_games = []
        
        for m in match_data:
            if "避開" in m["預測與盤口優勢"] or "無顯著優勢" in m["預測與盤口優勢"]:
                continue
                
            if m["gtd"] or m["has_fatigue"]:
                risky_games.append(m)
            else:
                strict_safe_games.append(m)
                
        strict_safe_games = sorted(strict_safe_games, key=lambda x: abs(x["h_s"] - x["a_s"]), reverse=True) 
        risky_games = sorted(risky_games, key=lambda x: abs(x["h_s"] - x["a_s"]), reverse=True)
        
        c1, c2 = st.columns(2) 
        with c1: 
            st.success("🔥 【S級穩膽】首選推薦 (無傷兵、無疲勞)") 
            if len(strict_safe_games) >= 2: 
                st.write(f"1. **{strict_safe_games[0]['對戰組合']}** ➡️ **{strict_safe_games[0]['預測與盤口優勢']}**") 
                st.write(f"2. **{strict_safe_games[1]['對戰組合']}** ➡️ **{strict_safe_games[1]['預測與盤口優勢']}**") 
            elif len(strict_safe_games) == 1:
                st.write(f"1. **{strict_safe_games[0]['對戰組合']}** ➡️ **{strict_safe_games[0]['預測與盤口優勢']}**")
                st.warning("⚠️ 今日 S 級穩膽僅有一場。")
            else:
                st.warning("⚠️ 今日無 S 級穩膽。")

        with c2: 
            st.warning("⚠️ 【風險備選庫】次要推薦 (含傷病或長途飛行變數)") 
            if len(risky_games) > 0:
                show_count = min(len(risky_games), 3) 
                for i in range(show_count):
                    game = risky_games[i]
                    risk_tags = []
                    if game["has_fatigue"]: risk_tags.append("✈️體能/時差劣勢")
                    if game["gtd"]: risk_tags.append("🚨傷兵疑慮")
                    risk_label = " + ".join(risk_tags)
                    
                    st.write(f"備選 {chr(65+i)}: **{game['對戰組合']}** ➡️ **{game['預測與盤口優勢']}**")
                    st.caption(f"*(風險提示: {risk_label})*")
            else:
                st.info("今日無備選賽事。")

        st.divider() 
        st.header("🔍 單場深度解析與手動盤口比對") 
        s_game = st.selectbox("請選擇要深入分析的場次：", match_data, format_func=lambda x: x["對戰組合"]) 
        
        col_a, col_b = st.columns(2) 
        with col_a: 
            st.subheader("📝 傷兵、飛行疲勞與陣容報告") 
            if s_game["reports"]: 
                for r in s_game["reports"]: 
                    if "✈️" in r or "🌎" in r or "🔋" in r:
                        st.error(r)  
                    else:
                        st.warning(r) 
            else: 
                st.success("✅ 本場核心主力均正常出賽，無長途飛行疲勞。") 
                
        with col_b: 
            st.subheader("💰 台彩盤口輸入與優勢比對 (如未串接 API 請在此手動輸入)") 
            u_spread = st.number_input(f"請輸入開給主隊的讓分 (例: -4.5)", value=-4.5, step=0.5) 
            u_total = st.number_input(f"請輸入大小分總分盤口 (例: 225.5)", value=225.5, step=0.5) 
            
            ai_diff = round(s_game['h_s'] - s_game['a_s'], 1)
            edge = round(ai_diff - u_spread, 1)
            
            st.write(f"▶️ **AI 預估主隊淨勝分：** `{ai_diff}` 分") 
            st.write(f"▶️ **台彩主隊讓分值：** `{u_spread}` 分") 
            st.write(f"▶️ **讓分盤口優勢差 (Edge)：** `{edge}` 分") 
            
            if abs(ai_diff) <= 1.0:
                st.error("🚨 AI 判定本場實力極度接近 (差距 <= 1分)，強烈建議避開讓分盤！")
            elif edge >= 4.0: 
                st.success(f"🔥 強烈推薦：主隊 過盤！") 
            elif edge <= -4.0: 
                st.success(f"🔥 強烈推薦：客隊 過盤！") 
            else: 
                st.warning("⚖️ 讓分盤口開得很精準，建議避開。") 
                
            st.divider()
            
            total_edge = round(s_game['total_est'] - u_total, 1)
            st.write(f"▶️ **AI 預估總分：** `{s_game['total_est']}` 分")
            st.write(f"▶️ **台彩大小分盤口：** `{u_total}` 分")
            
            if total_edge >= 5.0:
                st.success(f"🔥 大分推薦：AI預估高出盤口 `{total_edge}` 分！")
            elif total_edge <= -5.0:
                st.success(f"🔥 小分推薦：AI預估低於盤口 `{abs(total_edge)}` 分！")
            else:
                st.warning("⚖️ 總分預估與盤口接近，建議避開大小分。")
                
    else: 
        st.warning("🚨 目前抓取不到有效場次進行分析。") 

st.caption("NBA AI V28.0 - 終極職業版：長途飛行疲勞演算 & 自動化盤口 API 串接")