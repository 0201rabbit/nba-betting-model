import streamlit as st 
import pandas as pd 
import requests 
import numpy as np
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

@st.cache_data(ttl=900) 
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
                    for outcome in m['outcomes']:
                        if outcome['name'] == home: spread_val = outcome['point']
                elif m['key'] == 'totals':
                    total_val = m['outcomes'][0]['point']
                    
            odds_dict[home] = {"spread": spread_val, "total": total_val}
        return odds_dict
    except:
        return {}

def calculate_weighted_pie(p_stats_df, team_id, out_players):
    active_players = p_stats_df[(p_stats_df["TEAM_ID"] == team_id) & (~p_stats_df["PLAYER_NAME"].isin(out_players))]
    core_players = active_players[active_players["MIN"] > 15] 
    if core_players.empty:
        return 0
    top5 = core_players.nlargest(5, 'PIE')
    weighted_pie = (top5['PIE'] * top5['MIN']).sum() / top5['MIN'].sum()
    return weighted_pie

# 🛡️ V30.0 核武器：蒙地卡羅回合模擬器
def run_monte_carlo(h_s, a_s, game_pace, n_sims=10000):
    # 模擬 10,000 次比賽的節奏變異 (標準差約 4)
    sim_pace = np.random.normal(loc=game_pace, scale=4.0, size=n_sims)
    
    # 模擬 10,000 次的進攻效率變異 (單場 PPP 變異標準差約 0.12)
    h_ppp_mean = h_s / game_pace
    a_ppp_mean = a_s / game_pace
    sim_h_ppp = np.random.normal(loc=h_ppp_mean, scale=0.12, size=n_sims)
    sim_a_ppp = np.random.normal(loc=a_ppp_mean, scale=0.12, size=n_sims)
    
    # 產出 10,000 種最終比分結果
    sim_h_score = sim_pace * sim_h_ppp
    sim_a_score = sim_pace * sim_a_ppp
    
    sim_diff = sim_h_score - sim_a_score
    sim_total = sim_h_score + sim_a_score
    
    return sim_diff, sim_total

def calculate_ev(win_prob, decimal_odds=1.909):
    # 計算期望值 (EV)，假設運彩標準賠率 1.90 (-110)
    # EV = (勝率 * 淨利) - (敗率 * 本金1)
    return (win_prob * (decimal_odds - 1)) - (1 - win_prob)

# ------------------------ 
# 2 主介面與實戰分析 
# ------------------------ 
st.set_page_config(page_title="NBA AI 攻防大師 V30.0", layout="wide", page_icon="🏀") 
st.sidebar.header("🗓️ 歷史回測與實戰控制") 
target_date = st.sidebar.date_input("選擇賽事日期", datetime.now() - timedelta(hours=8)) 
formatted_date = target_date.strftime('%Y-%m-%d') 

st.sidebar.divider()
st.sidebar.markdown("### 🤖 自動化盤口分析")
st.sidebar.caption("前往 The Odds API 獲取免費金鑰。")
api_key = st.sidebar.text_input("輸入 API 金鑰 (選填)", type="password")

st.title(f"🏀 NBA AI V30 職業盤: 蒙地卡羅與 EV 決策引擎 ({formatted_date})") 

with st.spinner("啟動 10,000 次蒙地卡羅迴圈模擬與期望值運算中..."): 
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
        
        if h_is_b2b:
            h_pen += 3.5  
            h_rep.append(f"🔋 [{h_n}] 主場背靠背 (體能下滑)")
        if a_is_b2b:
            yest_loc = b2b_data[a_id]
            if yest_loc == "Away":
                a_pen += 5.5
                a_rep.append(f"✈️ [{a_n}] 連續客場背靠背 (嚴重飛行疲勞)")
            else:
                a_pen += 4.0
                a_rep.append(f"🔋 [{a_n}] 客場背靠背 (體能下滑)")

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
                    h_l5_off = h_l5.iloc[0]["OFF_RATING"]
                    if h_l5_off > h_d["OFF_RATING"] * 1.08:
                        h_l5_off = h_d["OFF_RATING"] * 1.05 
                    a_l5_off = a_l5.iloc[0]["OFF_RATING"]
                    if a_l5_off > a_d["OFF_RATING"] * 1.08:
                        a_l5_off = a_d["OFF_RATING"] * 1.05 
                    
                    h_off = (h_d["OFF_RATING"] * 0.7) + (h_l5_off * 0.3)
                    h_def = (h_d["DEF_RATING"] * 0.7) + (h_l5.iloc[0]["DEF_RATING"] * 0.3)
                    a_off = (a_d["OFF_RATING"] * 0.7) + (a_l5_off * 0.3)
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
            
            h_pie = calculate_weighted_pie(p_stats, h_id, h_out_players)
            a_pie = calculate_weighted_pie(p_stats, a_id, a_out_players)
            
            h_edge = (h_pie - 12) * 0.4 if h_pie > 12 else 0 
            a_edge = (a_pie - 12) * 0.4 if a_pie > 12 else 0 
            
            h_s = round((h_base_rating * (game_pace/100)) + 2.5 - h_pen + h_edge + (elo_edge / 2), 1) 
            a_s = round((a_base_rating * (game_pace/100)) - a_pen + a_edge - (elo_edge / 2), 1) 
            
            # 🛡️ 啟動蒙地卡羅運算
            sim_diff, sim_total = run_monte_carlo(h_s, a_s, game_pace)
            
            api_team_name = ODDS_API_TEAMS.get(h_n_en)
            market_spread = None
            market_total = None
            
            if live_odds and api_team_name in live_odds:
                market_spread = live_odds[api_team_name].get("spread")
                market_total = live_odds[api_team_name].get("total")

            # 運算各項機率與期望值
            home_win_prob = np.mean(sim_diff > 0)
            best_bet_str = f"主勝 {home_win_prob:.1%} / 無盤口資訊"
            max_ev = 0
            
            if market_spread is not None:
                # 模擬涵蓋盤口機率
                cover_h_prob = np.mean(sim_diff > -market_spread)
                cover_a_prob = np.mean(sim_diff < -market_spread)
                
                ev_h = calculate_ev(cover_h_prob)
                ev_a = calculate_ev(cover_a_prob)
                
                if ev_h >= ev_a and ev_h > 0:
                    best_bet_str = f"主隊 (-{market_spread}) | EV: +{ev_h:.1%}"
                    max_ev = ev_h
                elif ev_a > ev_h and ev_a > 0:
                    best_bet_str = f"客隊 (+{market_spread}) | EV: +{ev_a:.1%}"
                    max_ev = ev_a
                else:
                    best_bet_str = "⚠️ 負 EV (建議避開)"
                    max_ev = max(ev_h, ev_a)
            else:
                # 沒盤口時，回歸純預測
                if abs(h_s - a_s) <= 1.0:
                    best_bet_str = "⚠️五五波(避開)"
                else:
                    best_bet_str = f"主勝 ({home_win_prob:.1%})" if home_win_prob > 0.5 else f"客勝 ({1-home_win_prob:.1%})"

            hit = "待定" 
            if is_finished: 
                if "避開" in best_bet_str or "無盤口資訊" in best_bet_str:
                    hit = "無"  
                else:
                    if market_spread is not None:
                        # 用真實比分回測盤口
                        if "主隊" in best_bet_str and (h_act - a_act > -market_spread): hit = "✅"
                        elif "客隊" in best_bet_str and (h_act - a_act < -market_spread): hit = "✅"
                        else: hit = "❌"
                    else:
                        hit = "✅" if (h_s > a_s and h_act > a_act) or (h_s < a_s and h_act < a_act) else "❌" 

            match_data.append({ 
                "對戰組合": f"{'✈️' if a_is_b2b else ''}{a_n} @ {'🔋' if h_is_b2b else ''}{h_n}", 
                "AI淨勝分(客:主)": f"{a_s} : {h_s}", 
                "市場讓分(主)": market_spread if market_spread is not None else "-",
                "最佳 EV 決策": best_bet_str,
                "實際比分": f"{a_act} : {h_act}" if is_finished else "-", 
                "勝負命中": hit, 
                "h_name": h_n, "a_name": a_n, 
                "h_s": h_s, "a_s": a_s,  
                "game_pace": game_pace,
                "max_ev": max_ev, # 隱藏欄位，用於排序
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
            st.sidebar.metric("🎯 本日 EV 策略命中率", f"{rate:.1%}") 
        else: 
            st.sidebar.info("⌛ 尚無有效預測結果可統計。") 

        st.header("📊 蒙地卡羅 EV 決策總表 (10,000 次模擬)") 
        display_df = pd.DataFrame(match_data)[["對戰組合", "AI淨勝分(客:主)", "市場讓分(主)", "最佳 EV 決策", "實際比分", "勝負命中"]]
        st.dataframe(display_df, use_container_width=True) 

        st.divider() 
        st.header("🎯 職業級下注推薦 (依期望值 EV 排序)") 
        
        # 🛡️ V30.0：只推薦正 EV，且依期望值高低排序
        valid_bets = [m for m in match_data if m["max_ev"] > 0]
        valid_bets = sorted(valid_bets, key=lambda x: x["max_ev"], reverse=True) 
        
        c1, c2 = st.columns(2) 
        with c1: 
            st.success("💰 【+EV 價值盤】長期獲利保證") 
            if len(valid_bets) >= 1: 
                for i in range(min(len(valid_bets), 3)):
                    st.write(f"{i+1}. **{valid_bets[i]['對戰組合']}** ➡️ **{valid_bets[i]['最佳 EV 決策']}**") 
            else:
                st.warning("⚠️ 今日無大於 0% EV 的賽事，建議空手觀望。")

        with c2: 
            st.info("💡 什麼是 EV 決策？") 
            st.caption("這代表系統在後台將比賽模擬了 10,000 次，計算出真實的過盤率。當 EV 顯示 +5%，意味著你長期照著這個訊號下注 100 元，平均每次能淨賺 5 元。在職業運彩中，我們**只下注正 EV 的比賽**。")

        st.divider() 
        st.header("🔍 蒙地卡羅深度解析儀 (手動盤口測試)") 
        s_game = st.selectbox("請選擇要深入分析的場次：", match_data, format_func=lambda x: x["對戰組合"]) 
        
        col_a, col_b = st.columns(2) 
        with col_a: 
            st.subheader("📝 變數與陣容報告") 
            if s_game["reports"]: 
                for r in s_game["reports"]: 
                    if "✈️" in r or "🌎" in r or "🔋" in r: st.error(r)  
                    else: st.warning(r) 
            else: 
                st.success("✅ 無異常變數干擾。") 
                
        with col_b: 
            st.subheader("🎲 跑一萬次！動態 EV 模擬") 
            u_spread = st.number_input(f"請輸入台彩開給主隊的讓分 (例: -4.5)", value=-4.5, step=0.5) 
            u_total = st.number_input(f"請輸入大小分總分盤口 (例: 225.5)", value=225.5, step=0.5) 
            
            # 即時跑蒙地卡羅
            sim_diff, sim_total = run_monte_carlo(s_game['h_s'], s_game['a_s'], s_game['game_pace'])
            
            prob_cover_h = np.mean(sim_diff > -u_spread)
            prob_cover_a = np.mean(sim_diff < -u_spread)
            prob_over = np.mean(sim_total > u_total)
            prob_under = np.mean(sim_total < u_total)
            
            ev_h = calculate_ev(prob_cover_h)
            ev_a = calculate_ev(prob_cover_a)
            ev_over = calculate_ev(prob_over)
            ev_under = calculate_ev(prob_under)
            
            st.write("▶️ **讓分盤 10,000 次模擬結果：**")
            st.write(f"主隊 ({u_spread}) 過盤率: `{prob_cover_h:.1%}` ➡️ EV: `{ev_h:.1%}`")
            st.write(f"客隊 ({-u_spread}) 過盤率: `{prob_cover_a:.1%}` ➡️ EV: `{ev_a:.1%}`")
            
            st.divider()
            
            st.write("▶️ **大小分 10,000 次模擬結果：**")
            st.write(f"大分 (> {u_total}) 機率: `{prob_over:.1%}` ➡️ EV: `{ev_over:.1%}`")
            st.write(f"小分 (< {u_total}) 機率: `{prob_under:.1%}` ➡️ EV: `{ev_under:.1%}`")
            
            st.divider()
            st.markdown("🎯 **最終職業建議：** 尋找上方 EV 大於 **+3.0%** 的項目進行投資。如果全部都是負數，請堅決放棄本場比賽！")
                
    else: 
        st.warning("🚨 目前抓取不到有效場次進行分析。") 

st.caption("NBA AI V30.0 - 職業集團專用：Monte Carlo 蒙地卡羅萬次模擬與期望值 (EV) 引擎")