import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import random
import string
import time

# ==============================================================================
# 1. STREAMLIT SAYFA AYARLARI VE ÖZEL CSS
# ==============================================================================
st.set_page_config(
    page_title="Death Note: Kasabadaki Defter (Online)",
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

def generate_room_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

# Firebase Veritabanı Yardımcıları
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

# ==============================================================================
# 4. SESSION STATE İLKLENDİRME
# ==============================================================================
if 'player_id' not in st.session_state:
    st.session_state.player_id = f"usr_{int(time.time())}_{random.randint(100,999)}"
if 'player_name' not in st.session_state:
    st.session_state.player_name = ""
if 'room_code' not in st.session_state:
    st.session_state.room_code = None

# ==============================================================================
# 5. EKRAN 1: LOBİ - ODA KUR / KATIL
# ==============================================================================
st.markdown("<h1 class='death-title'>📖 DEATH NOTE: ONLINE KASABA</h1>", unsafe_allow_html=True)

if not db:
    st.error("🚨 Firebase bağlantısı kurulamadı! Lütfen `.streamlit/secrets.toml` dosyanızı kontrol edin.")
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
                
                # Yeni Oda Yapısı (Firestore)
                initial_room = {
                    "code": code,
                    "host_id": st.session_state.player_id,
                    "status": "LOBBY",  # LOBBY, NIGHT, DAY, GAME_OVER
                    "night_number": 1,
                    "players": {
                        st.session_state.player_id: {
                            "id": st.session_state.player_id,
                            "name": st.session_state.player_name,
                            "is_host": True,
                            "role": None,
                            "is_alive": True,
                            "action_submitted": False
                        }
                    },
                    "night_actions": {},
                    "votes": {},
                    "logs": ["Oda oluşturuldu. Oyuncular bekleniyor..."]
                }
                db.collection("rooms").document(code).set(initial_room)
                st.session_state.room_code = code
                st.rerun()
            else:
                st.warning("Lütfen bir kullanıcı adı girin.")

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
                    # Oyuncuyu odaya ekle
                    room["players"][st.session_state.player_id] = {
                        "id": st.session_state.player_id,
                        "name": st.session_state.player_name,
                        "is_host": False,
                        "role": None,
                        "is_alive": True,
                        "action_submitted": False
                    }
                    update_room_data(input_code, {"players": room["players"]})
                    add_room_log(input_code, f"{st.session_state.player_name} odaya katıldı.")
                    st.session_state.room_code = input_code
                    st.rerun()
            else:
                st.warning("Eksik bilgi girdiniz.")

# ==============================================================================
# 6. EKRAN 2: CANLI OYUN DÖNGÜSÜ
# ==============================================================================
else:
    room_code = st.session_state.room_code
    room = get_room_data(room_code)

    # Ayrılma / Bulunamama Durumu
    if not room:
        st.session_state.room_code = None
        st.rerun()

    # Otomatik Sayfa Yenileme / Senkronizasyon Butonu
    c_head1, c_head2, c_head3 = st.columns([2, 1, 1])
    with c_head1:
        st.markdown(f"<div class='room-code-box'>ODA KODU: {room_code}</div>", unsafe_allow_html=True)
    with c_head2:
        st.info(f"Durum: **{room['status']}**")
    with c_head3:
        if st.button("🔄 Verileri Yenile"):
            st.rerun()

    players = room["players"]
    my_p = players.get(st.session_state.player_id)

    # --- BEKLEME LOBİSİ ---
    if room["status"] == "LOBBY":
        st.markdown("### 👥 Oyuncular Lobi Odasında")
        
        for pid, p in players.items():
            st.write(f"- **{p['name']}** {'👑 (Oda Kurucu)' if p['is_host'] else ''}")

        if my_p and my_p["is_host"]:
            st.divider()
            if len(players) < 6:
                st.warning(f"Oyunu başlatmak için en az 6 oyuncu gerekiyor! (Şu an: {len(players)})")
            else:
                if st.button("🚀 OYUNU BAŞLAT (Rolleri Dağıt)", use_container_width=True):
                    # Rolleri Dağıt
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

    # --- OYUN ALANI (GECE / GÜNDÜZ / BİTİŞ) ---
    else:
        main_col, log_col = st.columns([2, 1])

        with main_col:
            # Oyuncu Durum Kartları
            st.markdown("#### Oyuncular")
            p_cols = st.columns(4)
            for idx, (pid, p) in enumerate(players.items()):
                with p_cols[idx % 4]:
                    c_class = "player-card-alive" if p['is_alive'] else "player-card-dead"
                    st.markdown(f"""
                    <div class="{c_class}">
                        <b>{p['name']}</b><br/>
                        <small>{'🟢 CANLI' if p['is_alive'] else '💀 ÖLÜ'}</small>
                    </div>
                    """, unsafe_allow_html=True)

            st.divider()

            # --- OYUNCUNUN ÖZEL ROL PANELSİ ---
            if my_p:
                role = my_p['role']
                st.markdown(f"### Rolünüz: {role['name']} {role['icon']}")
                st.caption(f"**Yetenek:** {role['ability']}")

                # --- GECE HAMLELERİ ---
                if room['status'] == 'NIGHT':
                    if not my_p['is_alive']:
                        st.warning("Ölü durumdasınız. Diğer oyuncuların gece hamlelerini bitirmesi bekleniyor.")
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

                    # KONTROL: Tüm Canlı Oyuncular Hamle Yaptı mı? (Sadece Host Günceller)
                    if my_p['is_host']:
                        alive_players = [p for p in players.values() if p['is_alive']]
                        all_submitted = all(p['action_submitted'] for p in alive_players)

                        if all_submitted and st.button("🌙 Geceyi Bitir ve Gündüze Geç"):
                            # Gece Sonuçlarını Hesapla
                            actions = room['night_actions']
                            kira_id = next((pid for pid, p in players.items() if p['role']['team'] == 'KIRA'), None)
                            watari_id = next((pid for pid, p in players.items() if p['role']['name'] == 'Watari (Koruyucu)'), None)

                            kira_target = actions.get(kira_id)
                            watari_target = actions.get(watari_id)

                            # Aksiyonları Sıfırla
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
                        
                        if st.button("⚖️ Oy Ver"):
                            room['votes'][my_p['id']] = vote_id
                            players[my_p['id']]['action_submitted'] = True
                            update_room_data(room_code, {
                                "votes": room['votes'],
                                "players": players
                            })
                            st.rerun()

                    # Oyları Hesaplama (Oda Kurucusu Yetkisinde)
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

                            # Aksiyon Sıfırlama ve Geceye Geçiş
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
