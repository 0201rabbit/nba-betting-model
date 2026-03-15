import streamlit as st
import pandas as pd
import time
import requests
from bs4 import BeautifulSoup
from nba_api.stats.endpoints import leaguedashteamstats, scoreboardv2
from nba_api.stats.static import teams

st.set_page_config(page_title="NBA 全能操盤手 V7.3", page_icon="🏀", layout="wide")

st.title("🏀 NBA 全能操盤分析系統 V7.3")
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

def normalize_name(name):
    if "Clippers" in name: return "LA Clippers"
    return name

def get_team_metrics(team_name, stats, stats_l10):
    try:
        mascot = team_name.split()[-1]
        row = stats[stats['TEAM_NAME'].str.contains(mascot)].iloc[0]
        row_l10 = stats_l10[stats_l10['TEAM_NAME'].str.contains(mascot)].iloc[0]
        return {
            'off_rtg': (row['OFF_RATING'] * 0.6) + (row_l10['OFF_RATING'] * 0.4),
            'def_rtg': (row['DEF_RATING'] * 0.6) + (row_l10['DEF_RATING'] * 0.4),
            'pace': (row['PACE'] * 0.6) + (row_l10['PACE'] * 0.4),
            'net_rtg': (row['NET_RATING'] * 0.6) + (row_l10['NET_RATING'] * 0.4) # 新增淨勝分計算不讓分
        }
    except: return None

def calculate_win_prob(h_m, a_m, injured_stars=False):
    net_diff = (h_m['net_rtg'] + 3.0) - a_m['net_rtg']
    prob = max(0.05, min(0.95, 0.50 + (net_diff * 0.03)))
    return prob * 0.8 if injured_stars else prob

def predict_score(home_metrics, away_metrics):
    match_pace = (home_metrics['pace'] + away_metrics['pace']) / 2
    h_score = ((home_metrics['off_rtg'] + away_metrics['def_rtg']) / 2 * (match_pace / 100)) + 1.5
    a_score = ((away_metrics['off_rtg'] + home_metrics['def_rtg']) / 2 * (match_pace / 100)) - 1.5
    return h_score, a_score

@st.cache_data(ttl=600)
def get_injury_report():
    try:
        url = "https://www.cbssports.com/nba/injuries/"
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10) 
        soup = BeautifulSoup(res.text, 'html.parser')
        return soup.get_text()
    except: return ""

star_players = {
    'Clippers': ['Kawhi Leonard', 'James Harden'],
    '76ers': ['Joel Embiid', 'Tyrese Maxey', 'Paul George'],
    'Hawks': ['Trae Young', 'Jalen Johnson'],
    'Lakers': ['LeBron James', 'Anthony Davis'],
    'Spurs': ['Victor Wembanyama'],
    'Heat': ['Tyler Herro', 'Terry Rozier', 'Jimmy Butler'],
    'Celtics': ['Jayson Tatum', 'Jaylen Brown']
}

# --- 2. 啟動數據獲取 ---
try:
    with st.spinner('🔄 正在連線 NBA 資料庫，並掃描今日傷兵...'):
        team_dict, games, stats, stats_l10 = fetch_nba_data()
        injury_text = get_injury_report()
except Exception as e:
    st.error(f"❌ 資料連線失敗: {e}")
    st.stop()

if games.empty:
    st.info("📅 今日暫無 NBA 賽程")
    st.stop()

# --- 3. 🏆 系統自動全局掃描 (尋找最穩串關) ---
safe_picks = []
game_list = []

for _, row in games.iterrows():
    h = team_dict.get(row['HOME_TEAM_ID'])
    a = team_dict.get(row['VISITOR_TEAM_ID'])
    game_list.append(f"{h} vs {a}")
    
    h_m = get_team_metrics(h, stats, stats_l10)
    a_m = get_team_metrics(a, stats, stats_l10)
    
    if h_m and a_m:
        h_mascot = h.split()[-1]
        injured_stars = [p for p in star_players.get(h_mascot, []) if p in injury_text]
        
        # 只挑選沒有主力受傷的球隊
        if not injured_stars:
            prob = calculate_win_prob(h_m, a_m, False)
            if prob >= 0.65: # 主隊高勝率
                safe_picks.append({'team': h, 'match': f"{h} vs {a}", 'prob': prob, 'fair': 1/prob, 'side': '主勝'})
            elif prob <= 0.35: # 客隊高勝率
                safe_picks.append({'team': a, 'match': f"{h} vs {a}", 'prob': 1-prob, 'fair': 1/(1-prob), 'side': '客勝'})

# 排序選出最穩的球隊
safe_picks = sorted(safe_picks, key=lambda x: x['prob'], reverse=True)

st.header("🏆 今日嚴選串關推薦")
if len(safe_picks) >= 2:
    st.success("✅ 系統已為您掃描全聯盟，排除地雷後，以下是今日最穩健的投注標的：")
    col_p1, col_p2 = st.columns(2)
    
    with col_p1:
        st.subheader("🎯 穩健 2 串 1 推薦")
        st.write(f"1️⃣ **{safe_picks[0]['team']}** ({safe_picks[0]['side']}) - 勝率: {safe_picks[0]['prob']:.1%} | 底線賠率: {safe_picks[0]['fair']:.2f}")
        st.write(f"2️⃣ **{safe_picks[1]['team']}** ({safe_picks[1]['side']}) - 勝率: {safe_picks[1]['prob']:.1%} | 底線賠率: {safe_picks[1]['fair']:.2f}")
        st.info("💡 建議：若台彩這兩場賠率皆大於底線，可直接重注串關。")
        
    with col_p2:
        if len(safe_picks) >= 3:
            st.subheader("🔥 高報酬 3 串 1 推薦")
            st.write(f"1️⃣ **{safe_picks[0]['team']}** ({safe_picks[0]['side']})")
            st.write(f"2️⃣ **{safe_picks[1]['team']}** ({safe_picks[1]['side']})")
            st.write(f"3️⃣ **{safe_picks[2]['team']}** ({safe_picks[2]['side']}) - 勝率: {safe_picks[2]['prob']:.1%}")
            st.warning("💡 建議：3 串 1 風險較高，請用小額本金（例如半凱利）娛樂測試。")
else:
    st.error("🛑 系統警告：今日多數強隊遭遇傷兵或勝率不明確，**強烈建議今日 PASS 不串關**，保護本金！")

st.markdown("---")

# --- 4. 🔍 單場深度分析與賠率試算 ---
st.header("🔍 單場深度分析")
selected_game = st.selectbox("請選擇要試算的比賽", game_list)

h_selected = selected_game.split(" vs ")[0]
a_selected = selected_game.split(" vs ")[1]

h_m = get_team_metrics(h_selected, stats, stats_l10)
a_m = get_team_metrics(a_selected, stats, stats_l10)

if h_m and a_m:
    h_mascot = h_selected.split()[-1]
    injured_stars = [p for p in star_players.get(h_mascot, []) if p in injury_text]
    
    # 計算分數與不讓分勝率
    h_score_raw, a_score_raw = predict_score(h_m, a_m)
    prob = calculate_win_prob(h_m, a_m, bool(injured_stars))
    fair_ml = 1 / prob
    
    h_score_final = h_score_raw - (8 if injured_stars else 0)
    a_score_final = a_score_raw
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(label=f"🏠 {h_selected}", value=f"{h_score_final:.1f}")
        if injured_stars: st.error(f"🚨 傷兵: {', '.join(injured_stars)}")
        else: st.success("✅ 主力安全")
    with col2:
        st.write(f"📈 模型勝率: **{prob:.1%}**")
        st.write(f"📏 預測讓分: **主隊 {'+' if (h_score_final-a_score_final)<0 else '-'}{abs(h_score_final-a_score_final):.1f}**")
        st.write(f"📊 預測總分: **{h_score_final + a_score_final:.1f}**")
    with col3:
        st.metric(label=f"✈️ {a_selected}", value=f"{a_score_final:.1f}")

    st.markdown("### 📝 台彩賠率試算")
    col_in1, col_in2, col_in3 = st.columns(3)
    
    with col_in1:
        tw_ml = st.number_input(f"【不讓分】主隊賠率", value=0.0, step=0.05)
    with col_in2:
        tw_spread = st.number_input(f"【讓分】主隊讓分值 (如 -5.5)", value=0.0, step=0.5)
    with col_in3:
        tw_total = st.number_input("【大小分】分界點", value=220.0, step=0.5)
        
    st.markdown("### 💡 系統判定結果")
    
    # 判斷不讓分
    if tw_ml > 0:
        if tw_ml >= fair_ml:
            st.success(f"🔥 **[不讓分] 這是 Value Bet！** 台彩賠率 ({tw_ml}) > 模型底線 ({fair_ml:.2f})，值得單壓或串關！")
        else:
            st.error(f"❌ **[不讓分] 賠率太低！** 台彩賠率 ({tw_ml}) < 模型底線 ({fair_ml:.2f})，無投資價值。")
    else:
        st.info("ℹ️ 輸入不讓分賠率以獲取建議。")
        
    # 判斷讓分
    adj_spread = h_score_final - a_score_final
    if tw_spread != 0:
        if adj_spread > abs(tw_spread) + 2: st.success("✅ **[讓分]** 看好主隊過盤。")
        elif adj_spread < abs(tw_spread) - 2: st.success("✅ **[讓分]** 看好客隊受讓過盤。")
        else: st.warning("⚖️ **[讓分]** 盤口精準，建議觀望。")
        
    # 判斷大小分
    adj_total = h_score_final + a_score_final
    if tw_total > 200:
        if adj_total > tw_total + 4: st.success(f"🔥 **[大小分]** 預測 {adj_total:.1f}，建議買【大分】。")
        elif adj_total < tw_total - 4: st.success(f"❄️ **[大小分]** 預測 {adj_total:.1f}，建議買【小分】。")
        else: st.warning("⚖️ **[大小分]** 盤口精準，建議觀望。")

else:
    st.warning("⚠️ 數據不全，無法預測。")
