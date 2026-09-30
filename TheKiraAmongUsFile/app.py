import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import random
import time

# ==============================================================================
# 1. STREAMLIT SAYFA AYARLARI VE ÖZEL CSS (HTML Temasına Sadık)
# ==============================================================================
st.set_page_config(
    page_title="Death Note: Kasabadaki Defter",
    page_icon="📖",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Dark Gothic Death Note Teması
st.markdown("""
<style>
    /* Ana Arka Plan */
    .stApp {
        background-color: #0a0a0c;
        color: #e2e8f0;
    }
    
    /* Başlık Stili */
    .death-title {
        font-family: 'Cinzel', serif;
        color: #ffffff;
        text-shadow: 0 0 15px rgba(220, 38, 38, 0.6);
        text-align: center;
    }
    
    /* Kart Yapıları */
    .death-card {
        background-color: #121216;
        border: 1px solid #262630;
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 12px;
    }
    
    /* Canlı/Ölü Oyuncu Kartı */
    .player-alive {
        border: 1px solid #262630;
        background-color: #121216;
        padding: 12px;
        border-radius: 8px;
        text-align: center;
    }
    .player-dead {
        border: 1px solid #8b0000;
        background-color: #0a0a0c;
        opacity: 0.5;
        padding: 12px;
        border-radius: 8px;
        text-align: center;
    }
    
    /* Kırmızı Vurgu */
    .text-crimson {
        color: #dc2626;
        font-weight: bold;
    }
    
    /* Günlük Log Başlığı */
    .log-box {
        background-color: #0a0a0c;
        border: 1px solid #262630;
        border-radius: 8px;
        padding: 10px;
        height: 380px;
        overflow-y: auto;
        font-size: 0.85rem;
    }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. FIREBASE KURULUMU (Secrets Yöneticisi ile)
# ==============================================================================
@st.cache_resource
def init_firebase():
    if not firebase_admin._apps:
        try:
            cred_dict = dict(st.secrets["firebase"])
            # Multi-line private key formatını düzelt
            if "private_key" in cred_dict:
                cred_dict["private_key"] = cred_dict["private_key"].replace("\\n", "\n")
            cred = credentials.Certificate(cred_dict)
            return firebase_admin.initialize_app(cred)
        except Exception as e:
            st.warning(f"Firebase Secrets yüklenemedi, yerel modda çalışılıyor: {e}")
            return None
    return firebase_admin.get_app()

firebase_app = init_firebase()
db = firestore.client() if firebase_app else None

# ==============================================================================
# 3. SABİTLER VE ROL TANIMLARI
# ==============================================================================
ROLES = {
    'KIRA': {
        'id': 'KIRA',
        'name': 'Kira (Light)',
        'team': 'KIRA',
        'icon': '💀',
        'goal': 'Soruşturma ekibini tek tek eleyerek üstünlük kurmak.',
        'ability': 'Her gece Death Note\'a bir kurban ismi yazar (Kalp krizi).'
    },
    'MISA': {
        'id': 'MISA',
        'name': 'Misa / İkinci Kira',
        'team': 'KIRA',
        'icon': '👁️',
        'goal': 'Kira\'ya yardım etmek ve soruşturmacıları şaşırtmak.',
        'ability': 'Şinigami Gözleri ile oyunda en fazla 2 kez birinin TAM rolünü öğrenir.'
    },
    'L': {
        'id': 'L',
        'name': 'L (Lider Dedektif)',
        'team': 'TOWN',
        'icon': '🔍',
        'goal': 'Kira ve Misa\'yı tespit edip gündüz idam ettirmek.',
        'ability': 'Her gece bir oyuncuyu sorgular: "Kira Tarafı" mı yoksa "Masum" mu öğrenir.'
    },
    'WATARI': {
        'id': 'WATARI',
        'name': 'Watari (Koruyucu)',
        'team': 'TOWN',
        'icon': '🛡️',
        'goal': 'Masumları ve L\'i Kira\'nın defterinden korumak.',
        'ability': 'Her gece bir oyuncuyu korumaya alır. O gece yazılırsa hedef ölmez.'
    },
    'CITIZEN': {
        'id': 'CITIZEN',
        'name': 'Soruşturma Ekibi (Near/Mello)',
        'team': 'TOWN',
        'icon': '🕵️',
        'goal': 'Gündüz tartışmalarında mantık yürüterek Kira\'yı bulmak.',
        'ability': 'Özel gece gücü yoktur, oylamada yüksek analiz gücüne sahiptir.'
    },
    'RYUK': {
        'id': 'RYUK',
        'name': 'Ryuk (Şinigami)',
        'team': 'NEUTRAL',
        'icon': '🍎',
        'goal': 'Eğlenmek! Tek amacı gündüz mahkemesinde kendisini astırmaktır.',
        'ability': 'Gündüz oylamasında asılırsa oyunu anında TEK BAŞINA kazanır.'
    }
}

BOT_NAMES = ['L Lawliet', 'Light Yagami', 'Misa Amane', 'Near (N)', 'Mello (M)', 'Watari', 'Matsuda', 'Aizawa', 'Mogi', 'Ide', 'Teru Mikami']

# ==============================================================================
# 4. SESSION STATE (OYUN DURUMU) İLKLENDİRME
# ==============================================================================
if 'game_state' not in st.session_state:
    st.session_state.game_state = {
        'phase': 'SETUP',  # 'SETUP', 'NIGHT', 'DAY_DISCUSSION', 'DAY_VOTING', 'GAME_OVER'
        'mode': 'ai',
        'night_number': 1,
        'players': [],
        'logs': [],
        'misa_charges': 2,
        'night_actions': {},
        'active_pass_idx': 0,
        'game_id': None
    }

gs = st.session_state.game_state

def add_log(msg, log_type='info'):
    prefix = {"danger": "💀", "success": "🛡️", "phase": "🌙", "system": "📜"}.get(log_type, "🔹")
    entry = f"{prefix} {msg}"
    gs['logs'].append(entry)
    
    # Firebase'e senkronize et
    if db and gs['game_id']:
        try:
            db.collection("games").document(gs['game_id']).update({
                "logs": firestore.ArrayUnion([entry])
            })
        except Exception:
            pass

# ==============================================================================
# 5. OYUN KURULUM FONKSİYONLARI
# ==============================================================================
def start_new_game(mode, player_name, role_pref, total_players, pass_names_text):
    gs['mode'] = mode
    gs['night_number'] = 1
    gs['misa_charges'] = 2
    gs['logs'] = []
    gs['players'] = []
    gs['game_id'] = f"game_{int(time.time())}"

    names = []
    if mode == 'ai':
        names.append({'name': player_name or 'Kira Hunter', 'is_ai': False, 'pref': role_pref})
        shuffled = [b for b in BOT_NAMES if b != player_name]
        random.shuffle(shuffled)
        for i in range(total_players - 1):
            names.append({'name': shuffled[i] if i < len(shuffled) else f'Bot {i+1}', 'is_ai': True, 'pref': 'RANDOM'})
    else:
        lines = [l.strip() for l in pass_names_text.split('\n') if l.strip()]
        for l in lines:
            names.append({'name': l, 'is_ai': False, 'pref': 'RANDOM'})

    # Rol Dağıtımı
    deck = [ROLES['KIRA'], ROLES['L'], ROLES['WATARI'], ROLES['MISA'], ROLES['RYUK']]
    while len(deck) < len(names):
        deck.append(ROLES['CITIZEN'])
    random.shuffle(deck)

    # İnsan oyuncunun rol tercihi
    if names[0]['pref'] != 'RANDOM':
        target = names[0]['pref']
        found = next((i for i, r in enumerate(deck) if r['id'] == target), None)
        if found is not None:
            deck[0], deck[found] = deck[found], deck[0]

    for idx, n in enumerate(names):
        gs['players'].append({
            'id': f'p_{idx}',
            'name': n['name'],
            'is_ai': n['is_ai'],
            'role': deck[idx],
            'is_alive': True
        })

    # Firebase Kaydı
    if db:
        try:
            db.collection("games").document(gs['game_id']).set({
                "created_at": firestore.SERVER_TIMESTAMP,
                "mode": mode,
                "player_count": len(names)
            })
        except Exception:
            pass

    gs['phase'] = 'NIGHT'
    add_log("Oyun başladı! Kasabada şüpheli ölümler ve gerilim tırmanıyor.", "system")

# ==============================================================================
# 6. HEADER VE ÜST PANEL
# ==============================================================================
st.markdown("<h1 class='death-title'>📖 DEATH NOTE: KASABADAKI DEFTER</h1>", unsafe_allow_html=True)

# ==============================================================================
# 7. EKRAN 1: SETUP (AYARLAR VE MOD SEÇİMİ)
# ==============================================================================
if gs['phase'] == 'SETUP':
    st.markdown("### ⚙️ Oyun Kurulumu")
    
    col1, col2 = st.columns(2)
    with col1:
        mode = st.radio("Oyun Modu", ["Yapay Zeka BOTS (Tek Başına)", "Pass & Play (Aynı Cihazda Arkadaşlarınla)"])
        is_ai = "Yapay Zeka" in mode
    
    with col2:
        if is_ai:
            player_name = st.text_input("Adınız", value="Kira Hunter")
            role_pref = st.selectbox("Tercih Ettiğiniz Rol", ["RANDOM", "KIRA", "L", "MISA", "WATARI", "RYUK", "CITIZEN"])
            total_players = st.slider("Toplam Oyuncu Sayısı", min_value=6, max_value=10, value=7)
            pass_text = ""
        else:
            player_name, role_pref, total_players = "", "RANDOM", 7
            pass_text = st.text_area("Oyuncu İsimleri (Her satıra bir isim - Min 6)", value="Light\nL Lawliet\nMisa\nNear\nMello\nWatari\nMatsuda")

    if st.button("🚀 Oyunu Başlat", use_container_width=True):
        if not is_ai and len([l for l in pass_text.split('\n') if l.strip()]) < 6:
            st.error("Pass & Play modunda en az 6 oyuncu yazmalısınız!")
        else:
            start_new_game('ai' if is_ai else 'pass', player_name, role_pref, total_players, pass_text)
            st.rerun()

# ==============================================================================
# 8. EKRAN 2: GECE / GÜNDÜZ / OYLAMA / GAME OVER
# ==============================================================================
else:
    # Üst Kontrol Barı
    c1, c2, c3 = st.columns([2, 2, 1])
    with c1:
        st.subheader(f"📍 Faz: {gs['phase']} | Gece {gs['night_number']}")
    with c2:
        alive_cnt = sum(1 for p in gs['players'] if p['is_alive'])
        st.info(f"👥 Canlı Oyuncular: {alive_cnt}/{len(gs['players'])}")
    with c3:
        if st.button("🔄 Yeniden Başlat"):
            gs['phase'] = 'SETUP'
            st.rerun()

    main_col, log_col = st.columns([2, 1])

    # --------------------------------------------------------------------------
    # SOL PANEL: OYUNCU KARTLARI VE HAMLELER
    # --------------------------------------------------------------------------
    with main_col:
        
        # --- OYUNCU LİSTESİ BİLGİ KARTLARI ---
        st.markdown("#### Kasaba Sakinleri")
        p_cols = st.columns(4)
        for idx, p in enumerate(gs['players']):
            with p_cols[idx % 4]:
                card_class = "player-alive" if p['is_alive'] else "player-dead"
                status_icon = "🟢" if p['is_alive'] else "💀"
                st.markdown(f"""
                <div class="{card_class}">
                    <b>{p['name']}</b><br/>
                    <small>{status_icon} {'CANLI' if p['is_alive'] else 'ÖLÜ'}</small><br/>
                    <small style="color: #94a3b8;">{'BOT' if p['is_ai'] else 'OYUNCU'}</small>
                </div>
                """, unsafe_allow_html=True)

        st.divider()

        # --- FAZ 1: GECE EVRESİ ---
        if gs['phase'] == 'NIGHT':
            st.markdown("### 🌙 Gece Çöktü")
            
            human_player = gs['players'][0] if gs['mode'] == 'ai' else gs['players'][gs['active_pass_idx']]
            
            if not human_player['is_alive'] and gs['mode'] == 'ai':
                st.warning("Hayattasınız değilsiniz. Gece hamleleri yapılıyor...")
                if st.button("Gündüze Geç"):
                    # Bot Hamlelerini Çöz
                    alive_p = [p for p in gs['players'] if p['is_alive']]
                    kira_p = next((p for p in alive_p if p['role']['id'] == 'KIRA'), None)
                    watari_p = next((p for p in alive_p if p['role']['id'] == 'WATARI'), None)
                    
                    kt = random.choice([p for p in alive_p if p['id'] != kira_p['id']])['id'] if kira_p else None
                    wt = random.choice(alive_p)['id'] if watari_p else None
                    
                    killed = next((p for p in gs['players'] if p['id'] == kt and kt != wt), None)
                    if killed:
                        killed['is_alive'] = False
                        add_log(f"{killed['name']} yatağında ölü bulundu! (Kalp Krizi)", "danger")
                    else:
                        add_log("Bu gece kimse ölmedi!", "success")
                        
                    gs['phase'] = 'DAY_DISCUSSION'
                    st.rerun()

            else:
                st.info(f"**Sıradaki Oyuncu:** {human_player['name']} | **Rol:** {human_player['role']['name']} ({human_player['role']['icon']})")
                st.caption(f"**Yetenek:** {human_player['role']['ability']}")

                alive_targets = [p for p in gs['players'] if p['is_alive'] and p['id'] != human_player['id']]
                target_names = {p['id']: p['name'] for p in alive_targets}

                role_id = human_player['role']['id']
                selected_target_id = None

                if role_id == 'KIRA':
                    selected_target_id = st.selectbox("Death Note'a Yazılacak Kurbanı Seç:", list(target_names.keys()), format_func=lambda x: target_names[x])
                elif role_id == 'WATARI':
                    all_alive = {p['id']: p['name'] for p in gs['players'] if p['is_alive']}
                    selected_target_id = st.selectbox("Korumak İstediğin Kişiyi Seç:", list(all_alive.keys()), format_func=lambda x: all_alive[x])
                elif role_id == 'L':
                    selected_target_id = st.selectbox("Sorgulamak İstediğin Şüpheliyi Seç:", list(target_names.keys()), format_func=lambda x: target_names[x])
                elif role_id == 'MISA':
                    if gs['misa_charges'] > 0:
                        st.write(f"Kalan Şinigami Gözü Hakkı: {gs['misa_charges']}")
                        selected_target_id = st.selectbox("Rolünü Öğrenmek İstediğin Kişiyi Seç:", list(target_names.keys()), format_func=lambda x: target_names[x])
                    else:
                        st.write("Göz hakkınız kalmadı.")

                if st.button("Gece Hamlesini Onayla"):
                    # L veya Misa Bilgi Bildirimi
                    if role_id == 'L' and selected_target_id:
                        t_obj = next(p for p in gs['players'] if p['id'] == selected_target_id)
                        is_evil = t_obj['role']['team'] == 'KIRA'
                        st.toast(f"🔍 Soruşturma Sonucu: {t_obj['name']} -> {'🔴 KIRA TARAFI' if is_evil else '🟢 MASUM'}")
                        time.sleep(2)
                    elif role_id == 'MISA' and selected_target_id and gs['misa_charges'] > 0:
                        t_obj = next(p for p in gs['players'] if p['id'] == selected_target_id)
                        gs['misa_charges'] -= 1
                        st.toast(f"👁️ Şinigami Gözü Sonucu: {t_obj['name']} -> {t_obj['role']['name']}")
                        time.sleep(2)

                    # Gece Geçiçi Kayıt
                    gs['night_actions'][human_player['id']] = {
                        'role': role_id,
                        'target': selected_target_id
                    }

                    # AI Botlarının Hamlelerini Otomatik Simüle Et (AI Modundaysak)
                    if gs['mode'] == 'ai':
                        alive_p = [p for p in gs['players'] if p['is_alive']]
                        kt = selected_target_id if role_id == 'KIRA' else None
                        wt = selected_target_id if role_id == 'WATARI' else None

                        # Eğer insan Kira veya Watari değilse Botlar seçsin
                        if not kt:
                            k_bot = next((p for p in alive_p if p['is_ai'] and p['role']['id'] == 'KIRA'), None)
                            if k_bot:
                                kt = random.choice([p for p in alive_p if p['id'] != k_bot['id']])['id']
                        if not wt:
                            w_bot = next((p for p in alive_p if p['is_ai'] and p['role']['id'] == 'WATARI'), None)
                            if w_bot:
                                wt = random.choice(alive_p)['id']

                        # Sonucu Hesapla
                        killed = next((p for p in gs['players'] if p['id'] == kt and kt != wt), None)
                        if killed:
                            killed['is_alive'] = False
                            add_log(f"{killed['name']} yatağında ölü bulundu! Ölüm Sebebi: Kalp Krizi.", "danger")
                        else:
                            add_log("🛡️ Bu gece kimse ölmedi! Watari bir masumu korumuş olabilir.", "success")

                        gs['phase'] = 'DAY_DISCUSSION'
                        st.rerun()

        # --- FAZ 2: GÜNDÜZ TARTIŞMASI VE OYLAMA ---
        elif gs['phase'] in ['DAY_DISCUSSION', 'DAY_VOTING']:
            st.markdown("### ☀️ Gündüz Mahkemesi")
            st.write("Şüphelileri değerlendirin ve Kira olduğundan şüphelendiğiniz kişiyi oylayın.")

            alive_targets = [p for p in gs['players'] if p['is_alive']]
            target_names = {p['id']: p['name'] for p in alive_targets}

            vote_target = st.selectbox("İdam Edilmesini İstediğiniz Oyuncu:", list(target_names.keys()), format_func=lambda x: target_names[x])

            if st.button("⚖️ Oyu Gönder ve Mahkeme Kararını Açıkla"):
                votes = {p['id']: 0 for p in alive_targets}
                
                # İnsan Oyu
                votes[vote_target] += 1
                
                # Bot Oyları
                for p in alive_targets:
                    if p['is_ai']:
                        choices = [t['id'] for t in alive_targets if t['id'] != p['id']]
                        if choices:
                            votes[random.choice(choices)] += 1

                # En Çok Oy Alan
                max_v = max(votes.values())
                top_voters = [pid for pid, cnt in votes.items() if cnt == max_v]

                if len(top_voters) == 1:
                    lynched = next(p for p in gs['players'] if p['id'] == top_voters[0])
                    lynched['is_alive'] = False
                    add_log(f"⚖️ MAHKEME KARARI: {lynched['name']} çoğunluk oyuyla ({max_v} oy) idam edildi!", "danger")
                    add_log(f"📜 {lynched['name']} oyuncusunun gerçek rolü: {lynched['role']['name']}", "system")

                    # Ryuk Kazanma Kontrolü
                    if lynched['role']['id'] == 'RYUK':
                        gs['phase'] = 'GAME_OVER'
                        gs['winner'] = ('RYUK', 'Ryuk kendisini astırmayı başardı ve oyunu TEK BAŞINA kazandı!')
                        st.rerun()
                else:
                    add_log("⚖️ Oylar eşit çıktı, bugün kimse idam edilmedi.", "system")

                # Kazanma Koşulu Kontrolü
                alive_now = [p for p in gs['players'] if p['is_alive']]
                kira_team = [p for p in alive_now if p['role']['team'] == 'KIRA']
                town_team = [p for p in alive_now if p['role']['team'] in ['TOWN', 'NEUTRAL']]

                if len(kira_team) == 0:
                    gs['phase'] = 'GAME_OVER'
                    gs['winner'] = ('TOWN', 'Tüm Kira destekçileri etkisiz hale getirildi. Adalet sağlandı!')
                elif len(kira_team) >= len(town_team):
                    gs['phase'] = 'GAME_OVER'
                    gs['winner'] = ('KIRA', 'Kira kasabada tam kontrolü sağladı. Yeni Dünya\'nın Tanrısı doğdu!')
                else:
                    gs['night_number'] += 1
                    gs['phase'] = 'NIGHT'

                st.rerun()

        # --- FAZ 3: OYUN BİTTİ (GAME OVER MODAL/EKRAN) ---
        elif gs['phase'] == 'GAME_OVER':
            w_team, w_desc = gs.get('winner', ('NONE', ''))
            st.error(f"🏆 OYUN BİTTİ: {w_team} KAZANDI!")
            st.write(f"**Özet:** {w_desc}")

            st.markdown("#### Oyuncu Rolleri Özeti")
            for p in gs['players']:
                st.write(f"- **{p['name']}**: {p['role']['name']} ({'CANLI' if p['is_alive'] else 'ÖLÜ'})")

            if st.button("🎮 Yeni Oyun Başlat", use_container_width=True):
                gs['phase'] = 'SETUP'
                st.rerun()

    # --------------------------------------------------------------------------
    # SAĞ PANEL: SORUŞTURMA GÜNLÜĞÜ (HTML'deki Notebook Log Yapısı)
    # --------------------------------------------------------------------------
    with log_col:
        st.markdown("#### 📖 Soruşturma Günlüğü")
        log_html = "<div class='log-box'>"
        for log in reversed(gs['logs']):
            log_html += f"<div style='margin-bottom:8px;'>{log}</div>"
        log_html += "</div>"
        st.markdown(log_html, unsafe_allow_html=True)
