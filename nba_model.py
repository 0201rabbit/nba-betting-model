import streamlit as st
import pandas as pd
import time
import requests
from bs4 import BeautifulSoup
from nba_api.stats.endpoints import leaguedashteamstats, scoreboardv2
from nba_api.stats.static import teams

st.set_page_config(page_title="NBA 全能操盤手 V8.1", page_icon="🏀", layout="wide")

st.title("🏀 NBA 全能操盤分析系統 V8.1 (睡前完全體)")
st.markdown("---")

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

# 🌟 傷兵解析與勝率計算
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
    # 將傷兵扣分反映在淨勝分上，重新計算真實勝率
    adj_h_net = h_m['net_rtg'] - h_penalty
    adj_a_net = a_m['net_rtg'] - a_penalty
    net_diff = (adj_h_net + 3.0) - adj_a_net # 主場優勢 +3
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

# --- 3. 🔍 單場深度分析 ---
st.header("🔍 單場深度分析 (含不讓分與傷兵修正)")
game_list = [f"{team_dict.get(row['HOME_TEAM_ID'])} vs {team_dict.get(row['VISITOR_TEAM_ID'])}" for _, row in games.iterrows()]
selected_game = st.selectbox("請選擇要試算的比賽", game_list)

h_selected = selected_game.split(" vs ")[0]
a_selected = selected_game.split(" vs ")[1]

h_m = get_team_metrics(h_selected, stats, stats_l10)
a_m = get_team_metrics(a_selected, stats, stats_l10)

if h_m and a_m:
    h_report, h_penalty = parse_injury_status(h_selected.split()[-1], injury_text)
    a_report, a_penalty = parse_injury_status(a_selected.split()[-1], injury_text)
    
    # 計算分數與勝率
    h_score_raw, a_score_raw = predict_score(h_m, a_m)
    h_score_final = h_score_raw - h_penalty
    a_score_final = a_score_raw - a_penalty
    prob = calculate_win_prob(h_m, a_m, h_penalty, a_penalty)
    fair_ml = 1 / prob
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(label=f"🏠 {h_selected}", value=f"{h_score_final:.1f}")
        if h_report:
            for r in h_report: st.warning(f"⚠️ {r}")
        else: st.success("✅ 主力安全")
        
    with col2:
        st.write(f"📈 模型勝率: **{prob:.1%}**")
        st.write(f"📏 預測讓分: **主隊 {'+' if (h_score_final-a_score_final)<0 else '-'}{abs(h_score_final-a_score_final):.1f}**")
        st.write(f"📊 預測總分: **{h_score_final + a_score_final:.1f}**")
        
    with col3:
        st.metric(label=f"✈️ {a_selected}", value=f"{a_score_final:.1f}")
        if a_report:
            for r in a_report: st.warning(f"⚠️ {r}")
        else: st.success("✅ 主力安全")

    st.markdown("### 📝 台彩盤口輸入")
    col_in1, col_in2, col_in3 = st.columns(3)
    
    with col_in1:
        tw_ml = st.number_input("【不讓分】主隊賠率", value=0.0, step=0.05)
    with col_in2:
        tw_spread = st.number_input("【讓分】主隊讓分值 (如 -5.5)", value=0.0, step=0.5)
    with col_in3:
        tw_total = st.number_input("【大小分】分界點", value=220.0, step=0.5)

    st.markdown("#### 💡 實戰建議")
    
    # 不讓分判斷
    if tw_ml > 0:
        if tw_ml >= fair_ml: st.success(f"🔥 **[不讓分] 價值注！** 賠率 ({tw_ml}) > 底線 ({fair_ml:.2f})")
        else: st.error(f"❌ **[不讓分] 賠率太低！** 賠率 ({tw_ml}) < 底線 ({fair_ml:.2f})，無投資價值。")
        
    # 讓分判斷
    adj_spread = h_score_final - a_score_final
    if tw_spread != 0:
        if adj_spread > abs(tw_spread) + 2: st.success("✅ **[讓分]** 看好主隊過盤。")
        elif adj_spread < abs(tw_spread) - 2: st.success("✅ **[讓分]** 看好客隊受讓過盤。")
        else: st.warning("⚖️ **[讓分]** 盤口精準，建議觀望。")
        
    # 大小分判斷
    adj_total = h_score_final + a_score_final
    if tw_total > 200:
        if adj_total > tw_total + 4: st.success(f"🔥 **[大小分]** 預測 {adj_total:.1f}，建議買【大分】。")
        elif adj_total < tw_total - 4: st.success(f"❄️ **[大小分]** 預測 {adj_total:.1f}，建議買【小分】。")
        else: st.warning("⚖️ **[大小分]** 盤口精準，建議觀望。")

    # 🛌 睡前資金控管警告
    st.markdown("#### 🛌 睡前下注資金建議")
    has_questionable = any("出戰成疑" in r for r in h_report + a_report)
    if has_questionable:
        st.error("⚠️ **高變異警告**：有核心主力為「出戰成疑」，明早可能不打。若今晚必須下注，**強烈建議注碼減半**，或直接放掉這場。")
    elif h_report or a_report:
        st.warning("📉 **傷兵確認**：名單中有傷兵狀況。模型已修正勝率與比分，請對照上方底線賠率下注。")
    else:
        st.success("🛡️ **陣容穩定**：目前無重大傷勢疑慮，變數極低。適合今晚安心下注，當作串關主力。")

else:
    st.warning("⚠️ 數據不全，無法預測。")