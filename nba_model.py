import streamlit as st
import pandas as pd
import time
import requests
from bs4 import BeautifulSoup
from nba_api.stats.endpoints import leaguedashteamstats, scoreboardv2
from nba_api.stats.static import teams

st.set_page_config(page_title="NBA 全能操盤手 V8.2", page_icon="🏀", layout="wide")

st.title("🏀 NBA 全能操盤系統 V8.2 (台彩抗鎖盤 + 睡前決策版)")
st.markdown("---")

# --- 0. 中英文隊名對照表 ---
CHINESE_TRANSLATION = {
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

def get_display_name(eng_name):
    ch_name = CHINESE_TRANSLATION.get(eng_name, '')
    return f"{eng_name} ({ch_name})" if ch_name else eng_name

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
        if "Clippers" in team_name: mascot = "Clippers"
        else: mascot = team_name.split()[-1]
        
        row = stats[stats['TEAM_NAME'].str.contains(mascot)].iloc[0]
        row_l10 = stats_l10[stats_l10['TEAM_NAME'].str.contains(mascot)].iloc[0]
        return {
            'off_rtg': (row['OFF_RATING'] * 0.6) + (row_l10['OFF_RATING'] * 0.4),
            'def_rtg': (row['DEF_RATING'] * 0.6) + (row_l10['DEF_RATING'] * 0.4),
            'pace': (row['PACE'] * 0.6) + (row_l10['PACE'] * 0.4),
            'net_rtg': (row['NET_RATING'] * 0.6) + (row_l10['NET_RATING'] * 0.4)
        }
    except: return None

star_players = {
    'Clippers': ['Kawhi Leonard', 'James Harden'],
    '76ers': ['Joel Embiid', 'Tyrese Maxey', 'Paul George'],
    'Hawks': ['Trae Young', 'Jalen Johnson'],
    'Lakers': ['LeBron James', 'Anthony Davis'],
    'Spurs': ['Victor Wembanyama'],
    'Heat': ['Tyler Herro', 'Terry Rozier', 'Jimmy Butler'],
    'Celtics': ['Jayson Tatum', 'Jaylen Brown'],
    'Nuggets': ['Nikola Jokic', 'Jamal Murray'],
    'Knicks': ['Jalen Brunson', 'Julius Randle'],
    'Cavaliers': ['Donovan Mitchell']
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

def predict_score(home_metrics, away_metrics):
    match_pace = (home_metrics['pace'] + away_metrics['pace']) / 2
    h_score = ((home_metrics['off_rtg'] + away_metrics['def_rtg']) / 2 * (match_pace / 100)) + 1.5
    a_score = ((away_metrics['off_rtg'] + home_metrics['def_rtg']) / 2 * (match_pace / 100)) - 1.5
    return h_score, a_score

def calculate_win_prob(h_m, a_m, penalty_diff):
    net_diff = (h_m['net_rtg'] + 3.0) - a_m['net_rtg'] - penalty_diff
    prob = max(0.05, min(0.95, 0.50 + (net_diff * 0.03)))
    return prob

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

# --- 3. 🏆 系統自動全局掃描 (尋找最穩串關 + 備案) ---
safe_picks = []

for _, row in games.iterrows():
    h = team_dict.get(row['HOME_TEAM_ID'])
    a = team_dict.get(row['VISITOR_TEAM_ID'])
    h_m = get_team_metrics(h, stats, stats_l10)
    a_m = get_team_metrics(a, stats, stats_l10)
    
    if h_m and a_m:
        h_mascot = h.split()[-1] if "Clippers" not in h else "Clippers"
        a_mascot = a.split()[-1] if "Clippers" not in a else "Clippers"
        h_report, h_penalty = parse_injury_status(h_mascot, injury_text)
        a_report, a_penalty = parse_injury_status(a_mascot, injury_text)
        
        # 串關嚴選：挑選沒有重大傷兵疑慮的比賽
        if not h_report and not a_report:
            h_score_raw, a_score_raw = predict_score(h_m, a_m)
            prob = calculate_win_prob(h_m, a_m, h_penalty - a_penalty)
            
            adj_spread = h_score_raw - a_score_raw
            adj_total = h_score_raw + a_score_raw
            spread_str = f"主隊 {'+' if adj_spread<0 else '-'}{abs(adj_spread):.1f}"
            
            # 使用包含中文的隊名
            disp_h = get_display_name(h)
            disp_a = get_display_name(a)
            
            if prob >= 0.65:
                safe_picks.append({'team': disp_h, 'match': f"{h} vs {a}", 'prob': prob, 'side': '主勝', 'fair': 1/prob, 'spread': spread_str, 'total': adj_total})
            elif prob <= 0.35:
                safe_picks.append({'team': disp_a, 'match': f"{h} vs {a}", 'prob': 1-prob, 'side': '客勝', 'fair': 1/(1-prob), 'spread': spread_str, 'total': adj_total})

safe_picks = sorted(safe_picks, key=lambda x: x['prob'], reverse=True)
unique_picks = []
seen_matches = set()
for pick in safe_picks:
    if pick['match'] not in seen_matches:
        unique_picks.append(pick)
        seen_matches.add(pick['match'])

st.header("🏆 今日嚴選串關與備案推薦")
if len(unique_picks) >= 2:
    st.success("✅ 系統已掃描全聯盟，排除高風險傷兵後，以下為今日最穩健的投注標的：")
    
    st.subheader("🎯 穩健 2 串 1 推薦")
    for i in range(2):
        st.markdown(f"**{i+1}️⃣ {unique_picks[i]['team']} ({unique_picks[i]['side']})** - 勝率: {unique_picks[i]['prob']:.1%} | 模型底線: {unique_picks[i]['fair']:.2f}")
        st.caption(f"🔒 **若被鎖盤，備案請看 👉** 【模型預估讓分】：{unique_picks[i]['spread']} ｜ 【預估總分】：{unique_picks[i]['total']:.1f}")
        st.write("")
        
    if len(unique_picks) >= 3:
        st.markdown("---")
        st.subheader("🔥 高報酬 3 串 1 推薦")
        for i in range(3):
            st.markdown(f"**{i+1}️⃣ {unique_picks[i]['team']} ({unique_picks[i]['side']})** - 勝率: {unique_picks[i]['prob']:.1%}")
            st.caption(f"🔒 備案 👉 讓分: {unique_picks[i]['spread']} ｜ 總分: {unique_picks[i]['total']:.1f}")
            st.write("")
    else:
        st.info("ℹ️ 今日安全賽事不足 3 場，系統不建議勉強拼 3 串 1，請專注於 2 串 1 即可。")
else:
    st.error("🛑 系統警告：今日多數強隊遭遇傷兵或勝率不明確，**強烈建議今日 PASS 不串關**，保護本金！")

st.markdown("---")

# --- 4. 🔍 單場深度分析 (復原 V7.3 的不讓分試算) ---
st.header("🔍 單場深度分析與賠率試算 (含傷兵修正)")
game_list = [f"{get_display_name(team_dict.get(row['HOME_TEAM_ID']))} vs {get_display_name(team_dict.get(row['VISITOR_TEAM_ID']))}" for _, row in games.iterrows()]
selected_game = st.selectbox("請選擇要試算的比賽", game_list)

# 還原為純英文以利數據搜尋
h_selected = selected_game.split(" vs ")[0].split(" (")[0]
a_selected = selected_game.split(" vs ")[1].split(" (")[0]

h_m = get_team_metrics(h_selected, stats, stats_l10)
a_m = get_team_metrics(a_selected, stats, stats_l10)

if h_m and a_m:
    h_mascot = h_selected.split()[-1] if "Clippers" not in h_selected else "Clippers"
    a_mascot = a_selected.split()[-1] if "Clippers" not in a_selected else "Clippers"
    h_report, h_penalty = parse_injury_status(h_mascot, injury_text)
    a_report, a_penalty = parse_injury_status(a_mascot, injury_text)
    
    h_score_raw, a_score_raw = predict_score(h_m, a_m)
    prob = calculate_win_prob(h_m, a_m, h_penalty - a_penalty)
    fair_ml = 1 / prob
    
    h_score_final = h_score_raw - h_penalty
    a_score_final = a_score_raw - a_penalty
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(label=f"🏠 {get_display_name(h_selected)}", value=f"{h_score_final:.1f}")
        if h_report:
            for r in h_report:
                if "缺陣" in r: st.error(f"🚨 {r}")
                elif "大概率" in r: st.success(f"✅ {r}")
                else: st.warning(f"⚠️ {r}")
        else: st.success("✅ 主力安全")
        
    with col2:
        st.markdown("<h3 style='text-align: center;'>VS</h3>", unsafe_allow_html=True)
        st.write(f"📈 模型勝率: **{prob:.1%}**")
        st.write(f"📏 預測讓分: **主隊 {'+' if (h_score_final-a_score_final)<0 else '-'}{abs(h_score_final-a_score_final):.1f}**")
        st.write(f"📊 預測總分: **{h_score_final + a_score_final:.1f}**")
        
    with col3:
        st.metric(label=f"✈️ {get_display_name(a_selected)}", value=f"{a_score_final:.1f}")
        if a_report:
            for r in a_report:
                if "缺陣" in r: st.error(f"🚨 {r}")
                elif "大概率" in r: st.success(f"✅ {r}")
                else: st.warning(f"⚠️ {r}")
        else: st.success("✅ 主力安全")

    st.markdown("### 📝 台彩盤口輸入與實戰建議")
    col_in1, col_in2, col_in3 = st.columns(3)
    
    with col_in1:
        tw_ml = st.number_input(f"【不讓分】主隊賠率", value=0.0, step=0.05)
    with col_in2:
        tw_spread = st.number_input(f"【讓分】主隊讓分值 (如 -5.5)", value=0.0, step=0.5)
    with col_in3:
        tw_total = st.number_input("【大小分】分界點", value=220.0, step=0.5)
        
    st.markdown("#### 💡 系統判定結果")
    
    # 🌟 復原 V7.3 不讓分價值判定
    if tw_ml > 0:
        if tw_ml >= fair_ml:
            st.success(f"🔥 **[不讓分] 這是 Value Bet！** 台彩賠率 ({tw_ml}) > 模型底線 ({fair_ml:.2f})，值得單壓或串關！")
        else:
            st.error(f"❌ **[不讓分] 賠率太低！** 台彩賠率 ({tw_ml}) < 模型底線 ({fair_ml:.2f})，無投資價值。")
    elif tw_ml == 0 and tw_spread == 0 and tw_total == 220.0:
        st.info("ℹ️ 輸入上方盤口賠率以獲取投資建議。")

    # 讓分與大小分判定
    adj_spread = h_score_final - a_score_final
    if tw_spread != 0:
        if adj_spread > abs(tw_spread) + 2: st.success("✅ **[讓分]** 模型看好主隊強過讓分盤。")
        elif adj_spread < abs(tw_spread) - 2: st.success("✅ **[讓分]** 模型看好客隊咬住比分，建議買客受讓。")
        else: st.warning("⚖️ **[讓分]** 盤口精準，建議觀望。")
        
    adj_total = h_score_final + a_score_final
    if tw_total > 200 and tw_total != 220.0:
        if adj_total > tw_total + 4: st.success(f"🔥 **[大小分]** 預測總分 {adj_total:.1f}，建議買【大分】。")
        elif adj_total < tw_total - 4: st.success(f"❄️ **[大小分]** 預測總分 {adj_total:.1f}，建議買【小分】。")
        else: st.warning("⚖️ **[大小分]** 盤口精準，建議觀望。")

    # 🛌 保留睡前決策警告
    st.markdown("#### 🛌 睡前下注資金建議")
    has_questionable = any("出戰成疑" in r for r in h_report + a_report)
    has_out = any("缺陣" in r for r in h_report + a_report)
    
    if has_questionable:
        st.error("⚠️ **高變異警告**：有核心主力為「出戰成疑」，明早可能不打。若今晚必須下注，**強烈建議注碼減半**，或直接放掉這場。")
    elif has_out:
        st.warning("📉 **傷兵確認**：有主力確定缺陣。模型已重度扣分，只要盤口價值還在，維持正常注碼即可。")
    else:
        st.success("🛡️ **陣容穩定**：目前無重大傷勢疑慮，變數極低。適合今晚安心下注，當作串關主力。")

else:
    st.warning("⚠️ 數據不全，無法預測。")