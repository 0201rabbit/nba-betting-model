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
# 1 傷兵與數據引擎 
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
    t_cn = TEAM_CN.get(team_name, team_name) 
    
    if search_key in STAR_PLAYERS: 
        for player in STAR_PLAYERS[search_key]: 
            last_name = player.split()[-1].lower() 
            if last_name in raw_text: 
                idx = raw_text.find(last_name) 
                chunk = raw_text[idx:idx+150] 
                p_cn = PLAYER_CN.get(player, player) 
                if "out" in chunk or "expected to be out" in chunk: 
                    penalty += 5.0  
                    reports.append(f"🚨 [{t_cn}] {p_cn} - 確定缺陣") 
                elif any(word in chunk for word in ["questionable", "gtd", "decision"]): 
                    penalty += 2.5 
                    reports.append(f"⚠️ [{t_cn}] {p_cn} - 出戰成疑(GTD)") 
                    has_gtd = True 
    
    penalty = min(penalty, 8.5) 
    return penalty, reports, has_gtd 

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
    b2b_teams = list(yest_games["HOME_TEAM_ID"]) + list(yest_games["VISITOR_TEAM_ID"])
    
    s_h = leaguedashteamstats.LeagueDashTeamStats(measure_type_detailed_defense="Advanced", location_nullable="Home", date_to_nullable=date_api_format).get_data_frames()[0] 
    s_a = leaguedashteamstats.LeagueDashTeamStats(measure_type_detailed_defense="Advanced", location_nullable="Road", date_to_nullable=date_api_format).get_data_frames()[0] 
    p_stats = leaguedashplayerstats.LeagueDashPlayerStats(measure_type_detailed_defense="Advanced", date_to_nullable=date_api_format).get_data_frames()[0] 
    
    try:
        s_last5 = leaguedashteamstats.LeagueDashTeamStats(measure_type_detailed_defense="Advanced", last_n_games=5, date_to_nullable=date_api_format).get_data_frames()[0]
    except:
        s_last5 = pd.DataFrame()

    return team_dict, games, line_score, s_h, s_a, p_stats, b2b_teams, s_last5

# ------------------------ 
# 2 主介面與實戰分析 
# ------------------------ 
st.set_page_config(page_title="NBA AI 攻防大師 V25.4", layout="wide", page_icon="🏀") 
st.sidebar.header("🗓️ 歷史回測與實戰控制") 
target_date = st.sidebar.date_input("選擇賽事日期", datetime.now() - timedelta(hours=8)) 
formatted_date = target_date.strftime('%Y-%m-%d') 

st.title(f"🏀 NBA AI 終極分析與回測 ({formatted_date})") 

with st.spinner("極速同步 NBA 數據庫、掃描 B2B 賽程與近期狀態中..."): 
    t_dict, games_df, line_df, s_h, s_a, p_stats, b2b_teams, s_last5 = fetch_nba_master(formatted_date) 
    raw_inj = fetch_injury_raw() 

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

        h_pen, h_rep, h_gtd = get_injury_impact(h_n_en, raw_inj) 
        a_pen, a_rep, a_gtd = get_injury_impact(a_n_en, raw_inj) 
        
        if is_historical: 
            h_pen, a_pen = h_pen * 0.5, a_pen * 0.5 

        h_is_b2b = h_id in b2b_teams
        a_is_b2b = a_id in b2b_teams
        
        if h_is_b2b:
            h_pen += 3.5  
            h_rep.append(f"🔋 [{h_n}] 主場背靠背 (體力衰退)")
        if a_is_b2b:
            a_pen += 4.5  
            a_rep.append(f"🔋 [{a_n}] 客場背靠背 (極度疲勞)")

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
            
            game_pace = (h_d["PACE"] + a_d["PACE"]) / 2 
            
            h_base_rating = (h_off * 0.65) + (a_def * 0.35) 
            a_base_rating = (a_off * 0.65) + (h_def * 0.35) 
            
            h_pie_series = p_stats[p_stats["TEAM_ID"] == h_id]["PIE"]
            a_pie_series = p_stats[p_stats["TEAM_ID"] == a_id]["PIE"]
            h_pie = h_pie_series.max() if not h_pie_series.empty else 0
            a_pie = a_pie_series.max() if not a_pie_series.empty else 0
            
            h_edge = (h_pie - 12) * 0.4 if h_pie > 12 else 0 
            a_edge = (a_pie - 12) * 0.4 if a_pie > 12 else 0 
            
            # 🎯 V25.4 更新：保留小數點第一位，增加預測顆粒度
            h_s = round((h_base_rating * (game_pace/100)) + 2.5 - h_pen + h_edge, 1) 
            a_s = round((a_base_rating * (game_pace/100)) - a_pen + a_edge, 1) 
            
            total_est = round(h_s + a_s, 1)
            total_act = h_act + a_act
            
            # 🎯 V25.4 更新：五五波迴避機制 (差距 <= 1.0 分直接避開)
            if abs(h_s - a_s) <= 1.0:
                ai_pick = "⚠️五五波(避開)"
            else:
                ai_pick = "主勝" if h_s > a_s else "客勝" 
            
            hit = "待定" 
            if is_finished: 
                if "五五波" in ai_pick:
                    hit = "無"  # 不計入勝率統計
                else:
                    hit = "✅" if (h_s > a_s and h_act > a_act) or (h_s < a_s and h_act < a_act) else "❌" 

            match_data.append({ 
                "對戰組合": f"{'🔋' if a_is_b2b else ''}{a_n} (客) @ {'🔋' if h_is_b2b else ''}{h_n} (主)", 
                "AI預估(客:主)": f"{a_s} : {h_s}", 
                "實際比分(客:主)": f"{a_act} : {h_act}" if is_finished else "未完賽", 
                "AI預估總分": total_est,         
                "實際總分": total_act if is_finished else "未完賽", 
                "預測勝負": ai_pick, 
                "勝負命中": hit, 
                "h_name": h_n, "a_name": a_n, 
                "h_s": h_s, "a_s": a_s,  
                "total_est": total_est,       
                "h_act": h_act, "a_act": a_act, 
                "is_finished": is_finished, 
                "reports": h_rep + a_rep, 
                "gtd": h_gtd or a_gtd,
                "has_b2b": h_is_b2b or a_is_b2b
            }) 
        except Exception as e: 
            continue 

    if match_data: 
        done = [m for m in match_data if m["is_finished"]] 
        # 計算命中率時，排除掉五五波的場次
        done_valid = [m for m in done if m["勝負命中"] in ["✅", "❌"]]
        
        if done_valid: 
            rate = sum(1 for m in done_valid if m["勝負命中"] == "✅") / len(done_valid) 
            st.sidebar.metric("🎯 本日 AI 勝負命中率", f"{rate:.1%}") 
        else: 
            st.sidebar.info("⌛ 尚無有效預測結果可統計。") 

        st.header("📊 AI 攻防預測 vs 實際結果回測表 (🔋代表背靠背)") 
        st.dataframe(pd.DataFrame(match_data)[["對戰組合", "AI預估(客:主)", "實際比分(客:主)", "AI預估總分", "實際總分", "預測勝負", "勝負命中"]], use_container_width=True) 

        st.divider() 
        st.header("🎯 AI 智能推薦引擎 (分級風險控管)") 
        
        strict_safe_games = []
        risky_games = []
        
        for m in match_data:
            # 🎯 絕對不把五五波的比賽放入任何推薦名單！
            if "五五波" in m["預測勝負"]:
                continue
                
            if m["gtd"] or m["has_b2b"]:
                risky_games.append(m)
            else:
                strict_safe_games.append(m)
                
        strict_safe_games = sorted(strict_safe_games, key=lambda x: abs(x["h_s"] - x["a_s"]), reverse=True) 
        risky_games = sorted(risky_games, key=lambda x: abs(x["h_s"] - x["a_s"]), reverse=True)
        
        c1, c2 = st.columns(2) 
        with c1: 
            st.success("🔥 【S級穩膽】首選推薦 (無傷兵、無背靠背)") 
            if len(strict_safe_games) >= 2: 
                st.write(f"1. **{strict_safe_games[0]['對戰組合']}** ➡️ 推薦：**{strict_safe_games[0]['預測勝負']}** (預估分差: {abs(strict_safe_games[0]['h_s'] - strict_safe_games[0]['a_s']):.1f}分)") 
                st.write(f"2. **{strict_safe_games[1]['對戰組合']}** ➡️ 推薦：**{strict_safe_games[1]['預測勝負']}** (預估分差: {abs(strict_safe_games[1]['h_s'] - strict_safe_games[1]['a_s']):.1f}分)") 
            elif len(strict_safe_games) == 1:
                st.write(f"1. **{strict_safe_games[0]['對戰組合']}** ➡️ 推薦：**{strict_safe_games[0]['預測勝負']}**")
                st.warning("⚠️ 今日 S 級穩膽僅有一場，無法湊滿穩健的 2 串 1。")
            else:
                st.warning("⚠️ 今日無 S 級穩膽 (所有比賽皆有風險或為五五波)。")

        with c2: 
            st.warning("⚠️ 【風險備選庫】次要推薦 (含體力或傷兵變數)") 
            if len(risky_games) > 0:
                show_count = min(len(risky_games), 3) 
                for i in range(show_count):
                    game = risky_games[i]
                    risk_tags = []
                    if game["has_b2b"]: risk_tags.append("🔋背靠背")
                    if game["gtd"]: risk_tags.append("🚨傷兵疑慮")
                    risk_label = " + ".join(risk_tags)
                    
                    st.write(f"備選 {chr(65+i)}: **{game['對戰組合']}** ➡️ 推薦：**{game['預測勝負']}** (預估分差: {abs(game['h_s'] - game['a_s']):.1f}分)")
                    st.caption(f"*(風險提示: {risk_label})*")
            else:
                st.info("今日無備選賽事。")

        st.divider() 
        st.header("🔍 單場深度解析與台彩盤口比對") 
        s_game = st.selectbox("請選擇要深入分析的場次：", match_data, format_func=lambda x: x["對戰組合"]) 
        
        col_a, col_b = st.columns(2) 
        with col_a: 
            st.subheader("📝 傷兵、體力與陣容報告") 
            if s_game["reports"]: 
                for r in s_game["reports"]: 
                    if "🔋" in r:
                        st.error(r)  
                    else:
                        st.warning(r) 
            else: 
                st.success("✅ 本場核心主力均正常出賽，且體力充沛。") 
                
        with col_b: 
            st.subheader("💰 台彩盤口輸入與優勢比對") 
            u_spread = st.number_input(f"請輸入開給【{s_game['h_name']}】的讓分 (例: -4.5)", value=-4.5, step=0.5) 
            u_total = st.number_input(f"請輸入大小分總分盤口 (例: 225.5)", value=225.5, step=0.5) 
            
            ai_diff = round(s_game['h_s'] - s_game['a_s'], 1)
            edge = round(ai_diff - u_spread, 1)
            
            st.write(f"▶️ **AI 預估主隊淨勝分：** `{ai_diff}` 分") 
            st.write(f"▶️ **台彩主隊讓分值：** `{u_spread}` 分") 
            st.write(f"▶️ **讓分盤口優勢差 (Edge)：** `{edge}` 分") 
            
            if "五五波" in s_game["預測勝負"]:
                st.error("🚨 AI 判定本場實力極度接近 (差距 <= 1分)，強烈建議避開讓分盤！")
            elif edge >= 4.0: 
                st.success(f"🔥 強烈推薦：**{s_game['h_name']} (主) 過盤**！") 
            elif edge <= -4.0: 
                st.success(f"🔥 強烈推薦：**{s_game['a_name']} (客) 過盤**！") 
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

st.caption("NBA AI V25.4 - 小數點精準預測 & 五五波避險機制")