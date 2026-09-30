import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
from streamlit_autorefresh import st_autorefresh
import random
import string
import time

# ==============================================================================
# 1. STREAMLIT SAYFA AYARLARI VE ÖZEL CSS
# ==============================================================================
st.set_page_config(
    page_title="Death Note: Kasabadaki Defter (Online + Botlar)",
    page_icon="📖",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    .stApp { background-color: #0a0a0c; color: #e2e8f0; }
    .death-title {
        font-family: 'Cinzel', serif;
        color: #ffffff;
        text-shadow: 0 0 15px rgba(220, 38, 38, 0.6);
        text-align: center;
    }
    .player-card-alive {
        border: 1px solid #262630; background-color: #121216;
        padding: 12px; border-radius: 8px; text-align: center;
    }
    .player-card-dead {
        border: 1px solid #8b0000; background-color: #0a0a0c; opacity: 0.5;
        padding: 12px; border-radius: 8px; text-align: center;
    }
    .room-code-box {
        background-color: #1e1e24; border: 2px dashed #dc2626;
        padding: 10px; border-radius: 8px; text-align: center;
        font-size: 1.5rem; letter-spacing: 4px; font-weight: bold;
    }
    .log-box {
        background-color: #0a0a0c; border: 1px solid #262630;
        border-radius: 8px; padding: 10px; height: 380px;
        overflow-y: auto; font-size: 0.85rem;
    }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. FIREBASE BAGLANTISI
# ==============================================================================
@st.cache_resource
def init_firebase():
    if not firebase_admin._apps:
        try:
            cred_dict = dict(st.secrets["firebase"])
            if "private_key" in cred_dict:
                cred_dict["private_key"] = cred_dict["private_key"].replace("\\n", "\n")
            cred = credentials.Certificate(cred_dict)
            return firebase_admin.initialize_app(cred)
        except Exception as e:
            st.error(f"Firebase Secrets Bağlantı Hatası: {e}")
            return None
    return firebase_admin.get_app()

firebase_app = init_firebase()
db = firestore.client() if firebase_app else None

# ==============================================================================
# 3. YARDIMCI FONKSİYONLAR VE SABİTLER
# ==============================================================================
ROLES = {
    'KIRA': {'name': 'Kira (Light)', 'team': 'KIRA', 'icon': '💀', 'ability': 'Her gece birini öldürür.'},
    'MISA': {'name': 'Misa / İkinci Kira', 'team': 'KIRA', 'icon': '👁️', 'ability': 'Şinigami gözleriyle rol öğrenir.'},
    'L': {'name': 'L (Dedektif)', 'team': 'TOWN', 'icon': '🔍', 'ability': 'Şüphelilerin safını sorgular.'},
    'WATARI': {'name': 'Watari (Koruyucu)', 'team': 'TOWN', 'icon': '🛡️', 'ability': 'Her gece birini korur.'},
    'CITIZEN': {'name': 'Soruşturma Ekibi', 'team': 'TOWN', 'icon': '🕵️', 'ability': 'Gündüz oy hakkı vardır.'},
    'RYUK': {'name': 'Ryuk (Şinigami)', 'team': 'NEUTRAL', 'icon': '🍎', 'ability': 'Kendini astırırsa kazanır.'}
}

BOT_NAMES = ['Bot L', 'Bot Light', 'Bot Misa', 'Bot Near', 'Bot Mello', 'Bot Watari', 'Bot Matsuda', 'Bot Aizawa', 'Bot Mogi', 'Bot Teru']

def generate_room_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def get_room_data(room_code):
    if not db: return None
    doc = db.collection("rooms").document(room_code).get()
    return doc.to_dict() if doc.exists else None

def update_room_data(room_code, data):
    if db:
        db.collection("rooms").document(room_code).update(data)

def add_room_log(room_code, msg):
    if db:
        db.collection("rooms").document(room_code).update({
            "logs": firestore.ArrayUnion([f"🔹 {msg}"])
        })

# Bot Hamlelerini Otomatik Simüle Etme
def process_bot_actions(room, room_code):
    players = room['players']
    status = room['status']
    updated = False

    alive_players = [p for p in players.values() if p['is_alive']]

    # GECE HAMLELERİ
    if status == 'NIGHT':
        for p in alive_players:
            if p['is_bot'] and not p['action_submitted']:
                targets = [t['id'] for t in alive_players if t['id'] != p['id']]
                if targets:
                    chosen = random.choice(targets)
                    room['night_actions'][p['id']] = chosen
                players[p['id']]['action_submitted'] = True
                updated = True

    # GÜNDÜZ OYLAMA HAMLELERİ
    elif status == 'DAY':
        for p in alive_players:
            if p['is_bot'] and not p['action_submitted']:
                targets = [t['id'] for t in alive_players if t['id'] != p['id']]
                if targets:
                    chosen = random.choice(targets)
                    room['votes'][p['id']] = chosen
                players[p['id']]['action_submitted'] = True
                updated = True

    if updated:
        update_room_data(room_code, {
            "players": players,
            "night_actions": room['night_actions'],
            "votes": room['votes']
        })

# ==============================================================================
# 4. SESSION STATE & OTOMATİK YENİLEME
# ==============================================================================
if 'player_id' not in st.session_state:
    st.session_state.player_id = f"usr_{int(time.time())}_{random.randint(100,999)}"
if 'player_name' not in st.session_state:
    st.session_state.player_name = ""
if 'room_code' not in st.session_state:
    st.session_state.room_code = None

# Oda içerisindeyken her 2 saniyede bir otomatik yenile
if st.session_state.get('room_code'):
    st_autorefresh(interval=2000, limit=None, key="online_sync_counter")

# ==============================================================================
# 5. LOBİ - ODA KUR / KATIL
# ==============================================================================
st.markdown("<h1 class='death-title'>📖 DEATH NOTE: ONLINE KASABA</h1>", unsafe_allow_html=True)

if not db:
    st.error("🚨 Firebase bağlantısı kurulamadı!")
    st.stop()

if not st.session_state.room_code:
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🏠 Yeni Oda Kur")
        host_name = st.text_input("Kullanıcı Adınız", value=st.session_state.player_name, key="host_name_input")
        if st.button("Oda Oluştur", use_container_width=True):
            if host_name.strip():
                st.session_state.player_name = host_name.strip()
                code = generate_room_code()
                
                initial_room = {
                    "code": code,
                    "host_id": st.session_state.player_id,
                    "status": "LOBBY",
                    "night_number": 1,
                    "players": {
                        st.session_state.player_id: {
                            "id": st.session_state.player_id,
                            "name": st.session_state.player_name,
                            "is_host": True,
                            "is_bot": False,
                            "role": None,
                            "is_alive": True,
                            "action_submitted": False
                        }
                    },
                    "night_actions": {},
                    "votes": {},
                    "logs": ["Oda oluşturuldu. Oyuncular ve botlar bekleniyor..."]
                }
                db.collection("rooms").document(code).set(initial_room)
                st.session_state.room_code = code
                st.rerun()

    with col2:
        st.markdown("### 🔑 Odaya Katıl")
        join_name = st.text_input("Kullanıcı Adınız", value=st.session_state.player_name, key="join_name_input")
        input_code = st.text_input("Oda Kodu", max_chars=6).upper()
        
        if st.button("Odaya Bağlan", use_container_width=True):
            if join_name.strip() and input_code:
                room = get_room_data(input_code)
                if not room:
                    st.error("Oda bulunamadı!")
                elif room["status"] != "LOBBY":
                    st.error("Bu oyun zaten başladı!")
                else:
                    st.session_state.player_name = join_name.strip()
                    room["players"][st.session_state.player_id] = {
                        "id": st.session_state.player_id,
                        "name": st.session_state.player_name,
                        "is_host": False,
                        "is_bot": False,
                        "role": None,
                        "is_alive": True,
                        "action_submitted": False
                    }
                    update_room_data(input_code, {"players": room["players"]})
                    add_room_log(input_code, f"{st.session_state.player_name} odaya katıldı.")
                    st.session_state.room_code = input_code
                    st.rerun()

# ==============================================================================
# 6. CANLI OYUN VE BOT İŞLEMLERİ
# ==============================================================================
else:
    room_code = st.session_state.room_code
    room = get_room_data(room_code)

    if not room:
        st.session_state.room_code = None
        st.rerun()

    # Bot hamlelerini arka planda tetikle
    process_bot_actions(room, room_code)

    c_head1, c_head2 = st.columns([3, 1])
    with c_head1:
        st.markdown(f"<div class='room-code-box'>ODA KODU: {room_code}</div>", unsafe_allow_html=True)
    with c_head2:
        st.info(f"Durum: **{room['status']}**")

    players = room["players"]
    my_p = players.get(st.session_state.player_id)

    # --- BEKLEME LOBİSİ & BOT EKLEME ---
    if room["status"] == "LOBBY":
        st.markdown("### 👥 Oyuncular Lobi Odasında")
        
        for pid, p in players.items():
            st.write(f"- **{p['name']}** {'🤖 [BOT]' if p['is_bot'] else ''} {'👑 (Kurucu)' if p['is_host'] else ''}")

        if my_p and my_p["is_host"]:
            st.divider()
            b_col1, b_col2 = st.columns(2)
            
            with b_col1:
                if st.button("🤖 Bot Ekle", use_container_width=True):
                    bot_count = sum(1 for p in players.values() if p['is_bot'])
                    if bot_count < len(BOT_NAMES):
                        bot_id = f"bot_{int(time.time())}_{random.randint(10,99)}"
                        bot_name = BOT_NAMES[bot_count]
                        players[bot_id] = {
                            "id": bot_id,
                            "name": bot_name,
                            "is_host": False,
                            "is_bot": True,
                            "role": None,
                            "is_alive": True,
                            "action_submitted": False
                        }
                        update_room_data(room_code, {"players": players})
                        add_room_log(room_code, f"{bot_name} odaya eklendi.")
                        st.rerun()
                    else:
                        st.warning("Maksimum bot sayısına ulaştınız.")

            with b_col2:
                if st.button("❌ Son Botu Çıkar", use_container_width=True):
                    bot_pids = [pid for pid, p in players.items() if p['is_bot']]
                    if bot_pids:
                        last_bot = bot_pids[-1]
                        b_name = players[last_bot]['name']
                        del players[last_bot]
                        update_room_data(room_code, {"players": players})
                        add_room_log(room_code, f"{b_name} odadan çıkarıldı.")
                        st.rerun()

            st.divider()
            if len(players) < 6:
                st.warning(f"Oyunu başlatmak için en az 6 oyuncu gerekiyor! (Şu an: {len(players)})")
            else:
                if st.button("🚀 OYUNU BAŞLAT", use_container_width=True):
                    p_list = list(players.values())
                    deck = [ROLES['KIRA'], ROLES['L'], ROLES['WATARI'], ROLES['MISA'], ROLES['RYUK']]
                    while len(deck) < len(p_list):
                        deck.append(ROLES['CITIZEN'])
                    random.shuffle(deck)

                    for idx, p_obj in enumerate(p_list):
                        players[p_obj['id']]['role'] = deck[idx]

                    update_room_data(room_code, {
                        "players": players,
                        "status": "NIGHT",
                        "logs": ["Oyun başladı! Gece çöktü, herkes gizlice hamlesini yapıyor..."]
                    })
                    st.rerun()

    # --- OYUN ALANI ---
    else:
        main_col, log_col = st.columns([2, 1])

        with main_col:
            st.markdown("#### Oyuncular")
            p_cols = st.columns(4)
            for idx, (pid, p) in enumerate(players.items()):
                with p_cols[idx % 4]:
                    c_class = "player-card-alive" if p['is_alive'] else "player-card-dead"
                    st.markdown(f"""
                    <div class="{c_class}">
                        <b>{p['name']}</b> {'🤖' if p['is_bot'] else ''}<br/>
                        <small>{'🟢 CANLI' if p['is_alive'] else '💀 ÖLÜ'}</small>
                    </div>
                    """, unsafe_allow_html=True)

            st.divider()

            if my_p:
                role = my_p['role']
                st.markdown(f"### Rolünüz: {role['name']} {role['icon']}")
                st.caption(f"**Yetenek:** {role['ability']}")

                # --- GECE HAMLELERİ ---
                if room['status'] == 'NIGHT':
                    if not my_p['is_alive']:
                        st.warning("Ölü durumdasınız.")
                    elif my_p['action_submitted']:
                        st.success("✅ Gece hamlenizi gönderdiniz. Diğer oyuncular bekleniyor...")
                    else:
                        alive_targets = {pid: p['name'] for pid, p in players.items() if p['is_alive'] and pid != my_p['id']}
                        
                        if role['team'] == 'KIRA' or role['name'] == 'L (Dedektif)':
                            target_id = st.selectbox("Hedef Oyuncuyu Seçin:", list(alive_targets.keys()), format_func=lambda x: alive_targets[x])
                            if st.button("Hamleyi Onayla"):
                                room['night_actions'][my_p['id']] = target_id
                                players[my_p['id']]['action_submitted'] = True
                                update_room_data(room_code, {
                                    "night_actions": room['night_actions'],
                                    "players": players
                                })
                                st.rerun()
                        else:
                            if st.button("Geceyi Pas Geç / Onayla"):
                                players[my_p['id']]['action_submitted'] = True
                                update_room_data(room_code, {"players": players})
                                st.rerun()

                    # ODA KURUCUSUNUN GECEYİ BİTİRME KONTROLÜ
                    if my_p['is_host']:
                        alive_players = [p for p in players.values() if p['is_alive']]
                        all_submitted = all(p['action_submitted'] for p in alive_players)

                        if all_submitted and st.button("🌙 Geceyi Bitir ve Gündüze Geç"):
                            actions = room['night_actions']
                            kira_id = next((pid for pid, p in players.items() if p['role']['team'] == 'KIRA'), None)
                            watari_id = next((pid for pid, p in players.items() if p['role']['name'] == 'Watari (Koruyucu)'), None)

                            kira_target = actions.get(kira_id)
                            watari_target = actions.get(watari_id)

                            for pid in players:
                                players[pid]['action_submitted'] = False

                            if kira_target and kira_target != watari_target:
                                players[kira_target]['is_alive'] = False
                                add_room_log(room_code, f"{players[kira_target]['name']} gece ölü bulundu! (Kalp Krizi)")
                            else:
                                add_room_log(room_code, "Bu gece kurban verilmedi!")

                            update_room_data(room_code, {
                                "status": "DAY",
                                "players": players,
                                "night_actions": {}
                            })
                            st.rerun()

                # --- GÜNDÜZ OYLAMA FAZI ---
                elif room['status'] == 'DAY':
                    st.markdown("### ☀️ Gündüz Mahkemesi")
                    
                    if not my_p['is_alive']:
                        st.warning("Ölü oyuncular oy kullanamaz.")
                    elif my_p['action_submitted']:
                        st.success("✅ Oyunuzu kullandınız. Diğer oyuncular bekleniyor...")
                    else:
                        alive_targets = {pid: p['name'] for pid, p in players.items() if p['is_alive']}
                        vote_id = st.selectbox("İdam Edilmesini İstediğiniz Oyuncu:", list(alive_targets.keys()), format_func=lambda x: alive_targets[x])
                        
                        if st.button("⚖️️ Oy Ver"):
                            room['votes'][my_p['id']] = vote_id
                            players[my_p['id']]['action_submitted'] = True
                            update_room_data(room_code, {
                                "votes": room['votes'],
                                "players": players
                            })
                            st.rerun()

                    if my_p['is_host']:
                        alive_players = [p for p in players.values() if p['is_alive']]
                        all_voted = all(p['action_submitted'] for p in alive_players)

                        if all_voted and st.button("⚖️ Oyları Say ve Mahkeme Kararını Açıkla"):
                            votes = room['votes']
                            counts = {}
                            for target in votes.values():
                                counts[target] = counts.get(target, 0) + 1

                            if counts:
                                max_vote = max(counts.values())
                                top_targets = [pid for pid, cnt in counts.items() if cnt == max_vote]

                                if len(top_targets) == 1:
                                    lynched = players[top_targets[0]]
                                    lynched['is_alive'] = False
                                    add_room_log(room_code, f"MAHKEME KARARI: {lynched['name']} idam edildi!")
                                    add_room_log(room_code, f"{lynched['name']} oyuncusunun rolü: {lynched['role']['name']}")
                                else:
                                    add_room_log(room_code, "Oylar eşit çıktı, kimse idam edilmedi.")

                            for pid in players:
                                players[pid]['action_submitted'] = False

                            update_room_data(room_code, {
                                "status": "NIGHT",
                                "players": players,
                                "votes": {},
                                "night_number": room['night_number'] + 1
                            })
                            st.rerun()

        # --- SAĞ PANEL: CANLI LOGLAR ---
        with log_col:
            st.markdown("#### 📖 Soruşturma Günlüğü")
            log_html = "<div class='log-box'>"
            for log in reversed(room.get('logs', [])):
                log_html += f"<div style='margin-bottom:8px;'>{log}</div>"
            log_html += "</div>"
            st.markdown(log_html, unsafe_allow_html=True)
