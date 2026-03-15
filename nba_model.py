import streamlit as st
import pandas as pd
import time
import requests
from bs4 import BeautifulSoup
from nba_api.stats.endpoints import leaguedashteamstats, scoreboardv2
from nba_api.stats.static import teams

st.set_page_config(page_title="NBA 全能操盤手 V8.3", page_icon="🏀", layout="wide")

st.title("🏀 NBA 全能操盤分析系統 V8.3 (雙語睡前完全體)")
st.markdown("---")

# 🌟 新增：NBA 繁體中文隊名對照表
tw_teams = {
    'Atlanta Hawks': '亞特蘭大老鷹', 'Boston Celtics': '波士頓塞爾提克',
    'Brooklyn Nets': '布魯克林籃網', 'Charlotte Hornets': '夏洛特黃蜂',
    'Chicago Bulls': '芝加哥公牛', 'Cleveland Cavaliers': '克里夫蘭騎士',
    'Dallas Mavericks': '達拉斯獨行俠', 'Denver Nuggets': '丹佛金塊',
    'Detroit Pistons': '底特律活塞', 'Golden State Warriors': '金州勇士',
    'Houston Rockets': '休士頓火箭', 'Indiana Pacers': '印第安納溜馬',
    'LA Clippers': '洛杉磯快艇', 'Los Angeles Clippers': '洛杉磯快艇',
    'Los Angeles Lakers': '洛杉磯湖人', 'Memphis Grizzlies': '曼菲斯灰熊',
    'Miami Heat': '邁阿密熱火', 'Milwaukee Bucks': '密爾瓦基公鹿',
    'Minnesota Timberwolves': '明尼蘇達灰狼', 'New Orleans Pelicans': '紐奧良鵜鶘',
    'New York Knicks': '紐約尼克', 'Oklahoma City Thunder': '奧克拉荷馬雷霆',
    'Orlando Magic': '奧蘭多魔術', 'Philadelphia 76ers': '費城76人',
    'Phoenix Suns': '鳳凰城太陽', 'Portland Trail Blazers': '波特蘭拓荒者',
    'Sacramento Kings': '沙加緬度國王', 'San Antonio Spurs': '聖安東尼奧馬刺',
    'Toronto Raptors': '多倫多暴龍', 'Utah Jazz': '猶他爵士',
    'Washington Wizards': '華盛頓巫師'
}

def get_tw_name(eng_name):
    # 將英文轉換為 "英文 (中文)" 的格式
    return f"{eng_name} ({tw_teams.get(eng_name, '未知')})"

# --- 1. 核心函數庫 ---
@st.cache_data(ttl=3600)
def fetch_nba_data():
    team_dict = {team['id']: team['full_name'] for team in teams.get_teams()}
    board = scoreboardv2.ScoreboardV2()
    games = board.get_data_frames()[0]
    stats = leaguedashteamstats.LeagueDashTeamStats(measure_type_detailed_defense='Advanced').get_data_frames()[0]
    stats_l10 = leaguedashteamstats.LeagueDashTeamStats(measure_type_detailed_defense='Advanced', last_n_games=10).get_data_frames()[0]
    return team_dict, games, stats, stats_l10

def get_team_metrics(team_name, stats, stats_l10):
    try:
        mascot = team_name.split()[-1]
        row = stats[stats['TEAM_NAME'].str.contains(mascot)].iloc[0]
        row_l10 = stats_l10[stats_l10['TEAM_NAME'].str.contains(mascot)].iloc[0]
        return {
            'off_rtg': (row['OFF_RATING'] * 0.6) + (row_l10['OFF_RATING'] * 0.4),
            'def_rtg': (row['DEF_RATING'] * 0.6) + (row_l10['DEF_RATING'] * 0.4),
            'pace': (row['PACE'] * 0.6) + (row_l10['PACE'] * 0.4),
            'net_rtg': (row['NET_RATING'] * 0.6) + (row_l10['NET_RATING'] * 0.4)
        }
    except: return None

# 🌟 智能傷兵解析引擎
star_players = {
    'Clippers': ['Kawhi Leonard', 'James Harden'],
    '76ers': ['Joel Embiid', 'Tyrese Maxey', 'Paul George'],
    'Hawks': ['Trae Young', 'Jalen Johnson'],
    'Lakers': ['LeBron James', 'Anthony Davis'],
    'Spurs': ['Victor Wembanyama'],
    'Heat': ['Tyler Herro', 'Terry Rozier', 'Jimmy Butler'],
    'Celtics': ['Jayson Tatum', 'Jaylen Brown'],
    'Nuggets': ['Nikola Jokic', 'Jamal Murray']
}

@st.cache_data(ttl=600)
def get_injury_report():
    try:
        url = "https://www.cbssports.com/nba/injuries/"
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10) 
        soup = BeautifulSoup(res.text, 'html.parser')
        return soup.get_text()
    except: return ""

def parse_injury_status(team_mascot, injury_text):
    report = []
    penalty_points = 0
    if team_mascot in star_players:
        for player in star_players[team_mascot]:
            if player in injury_text:
                idx = injury_text.find(player)
                context = injury_text[idx:idx+100].lower()
                if "out" in context:
                    report.append(f"{player} (確定缺陣)")
                    penalty_points += 8
                elif "probable" in context:
                    report.append(f"{player} (大概率打)")
                    penalty_points += 0
                else:
                    report.append(f"{player} (出戰成疑)")
                    penalty_points += 4
    return report, penalty_points

def calculate_win_prob(h_m, a_m, h_penalty, a_penalty):
    adj_h_net = h_m['net_rtg'] - h_penalty
    adj_a_net = a_m['net_rtg'] - a_penalty
    net_diff = (adj_h_net + 3.0) - adj_a_net
    prob = max(0.05, min(0.95, 0.50 + (net_diff * 0.03)))
    return prob

def predict_score(home_metrics, away_metrics):
    match_pace = (home_metrics['pace'] + away_metrics['pace']) / 2
    h_score = ((home_metrics['off_rtg'] + away_metrics['def_rtg']) / 2 * (match_pace / 100)) + 1.5
    a_score = ((away_metrics['off_rtg'] + home_metrics['def_rtg']) / 2 * (match_pace / 100)) - 1.5
    return h_score, a_score

# --- 2. 啟動數據獲取 ---
try:
    with st.spinner('🔄 正在連線 NBA 資料庫與傷兵情報網...'):
        team_dict, games, stats, stats_l10 = fetch_nba_data()
        injury_text = get_injury_report()
except Exception as e:
    st.error(f"❌ 資料連線失敗: {e}")
    st.stop()

if games.empty:
    st.info("📅 今日暫無 NBA 賽程")
    st.stop()

# --- 3. 🏆 系統自動全局掃描 (嚴選睡前串關) ---
safe_picks = []
game_list = []

for _, row in games.iterrows():
    h_en = team_dict.get(row['HOME_TEAM_ID'])
    a_en = team_dict.get(row['VISITOR_TEAM_ID'])
    
    # 將雙語隊名加入選單
    game_list.append(f"{get_tw_name(h_en)} vs {get_tw_name(a_en)}")
    
    h_m = get_team_metrics(h_en, stats, stats_l10)
    a_m = get_team_metrics(a_en, stats, stats_l10)
    
    if h_m and a_m:
        h_rep, h_pen = parse_injury_status(h_en.split()[-1], injury_text)
        a_rep, a_pen = parse_injury_status(a_en.split()[-1], injury_text)
        
        prob = calculate_win_prob(h_m, a_m, h_pen, a_pen)
        
        h_unsafe = any("出戰成疑" in r or "確定缺陣" in r for r in h_rep)
        a_unsafe = any("出戰成疑" in r or "確定缺陣" in r for r in a_rep)
        
        if prob >= 0.65 and not h_unsafe:
            safe_picks.append({'team': get_tw_name(h_en),