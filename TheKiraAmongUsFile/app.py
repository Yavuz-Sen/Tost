import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import json
import random

# ---------------------------------------------------------
# 1. FIREBASE BAĞLANTISI
# ---------------------------------------------------------
if not firebase_admin._apps:
    try:
        if "textkey" in st.secrets:
            key_dict = json.loads(st.secrets["textkey"])
            cred = credentials.Certificate(key_dict)
        else:
            cred = credentials.Certificate("firebase_key.json")
        firebase_admin.initialize_app(cred)
    except Exception as e:
        st.error(f"Firebase bağlantısı kurulamadı: {e}")
        st.stop()

db = firestore.client()

# ---------------------------------------------------------
# 2. SAYFA YAPILANDIRMASI VE OTURUM DURUMU
# ---------------------------------------------------------
st.set_page_config(page_title="The Kira: Among Us", page_icon="🗡️", layout="centered")

if "player_id" not in st.session_state:
    st.session_state.player_id = f"user_{random.randint(1000, 9999)}"
if "room_code" not in st.session_state:
    st.session_state.room_code = None

BOT_NAMES = ["L", "Near", "Mello", "Ryuk", "Misa", "Rem", "Soichiro", "Matsuda"]

# ---------------------------------------------------------
# 3. VERİTABANI YARDIMCI FONKSİYONLARI
# ---------------------------------------------------------
def create_room(room_code, player_name):
    doc_ref = db.collection("rooms").document(room_code)
    doc_ref.set({
        "status": "waiting",
        "created_at": firestore.SERVER_TIMESTAMP,
        "test_mode": False,
        "players": {
            st.session_state.player_id: {
                "name": player_name,
                "role": "Villager",
                "is_alive": True,
                "is_host": True,
                "is_bot": False
            }
        }
    })

def join_room(room_code, player_name):
    doc_ref = db.collection("rooms").document(room_code)
    doc = doc_ref.get()
    if doc.exists:
        doc_ref.update({
            f"players.{st.session_state.player_id}": {
                "name": player_name,
                "role": "Villager",
                "is_alive": True,
                "is_host": False,
                "is_bot": False
            }
        })
        return True
    return False

def add_bot(room_code):
    doc_ref = db.collection("rooms").document(room_code)
    doc = doc_ref.get()
    if not doc.exists:
        return
    data = doc.to_dict()
    players = data.get("players", {})
    
    bot_id = f"bot_{random.randint(1000, 9999)}"
    used_names = [p.get("name") for p in players.values()]
    available_names = [n for n in BOT_NAMES if n not in used_names]
    bot_name = random.choice(available_names) if available_names else f"Bot_{random.randint(1, 99)}"

    doc_ref.update({
        f"players.{bot_id}": {
            "name": f"🤖 {bot_name}",
            "role": "Villager",
            "is_alive": True,
            "is_host": False,
            "is_bot": True
        }
    })

def clear_bots(room_code):
    doc_ref = db.collection("rooms").document(room_code)
    doc = doc_ref.get()
    if not doc.exists:
        return
    data = doc.to_dict()
    players = data.get("players", {})
    
    updates = {}
    for p_id, p_info in players.items():
        if p_info.get("is_bot"):
            updates[f"players.{p_id}"] = firestore.DELETE_FIELD

    if updates:
        doc_ref.update(updates)

def start_game(room_code):
    doc_ref = db.collection("rooms").document(room_code)
    doc = doc_ref.get()
    if not doc.exists:
        return
    
    data = doc.to_dict()
    players = data.get("players", {})
    player_ids = list(players.keys())
    
    if len(player_ids) < 3:
        st.warning("Oyunu başlatmak için en az 3 oyuncu (veya bot) gereklidir!")
        return

    # Rastgele bir Vampir/Kira seç
    vampire_id = random.choice(player_ids)
    
    updates = {"status": "playing"}
    for p_id in player_ids:
        role = "Vampire" if p_id == vampire_id else "Villager"
        updates[f"players.{p_id}.role"] = role

    doc_ref.update(updates)

def reset_game(room_code):
    doc_ref = db.collection("rooms").document(room_code)
    doc_ref.update({"status": "waiting"})

# ---------------------------------------------------------
# 4. ARAYÜZ (UI) AKIŞI
# ---------------------------------------------------------
st.title("🗡️ The Kira: Among Us")

# ODA OLUŞTURMA / KATILMA EKRANI
if not st.session_state.room_code:
    st.subheader("Giriş Yap")
    player_name = st.text_input("Oyuncu Adınız:", value="Oyuncu")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Yeni Oda Oluştur", use_container_width=True):
            if player_name.strip():
                new_code = str(random.randint(1000, 9999))
                create_room(new_code, player_name)
                st.session_state.room_code = new_code
                st.rerun()
            else:
                st.error("Lütfen geçerli bir isim girin.")

    with col2:
        input_code = st.text_input("Oda Kodu:")
        if st.button("Odaya Katıl", use_container_width=True):
            if input_code.strip() and player_name.strip():
                if join_room(input_code.strip(), player_name):
                    st.session_state.room_code = input_code.strip()
                    st.rerun()
                else:
                    st.error("Oda bulunamadı!")
            else:
                st.error("Lütfen adınızı ve oda kodunu girin.")

# ODA İÇİ EKRANI
else:
    room_ref = db.collection("rooms").document(st.session_state.room_code)
    room_doc = room_ref.get()

    if not room_doc.exists:
        st.error("Oda kapatıldı veya bulunamıyor.")
        if st.button("Ana Menüye Dön"):
            st.session_state.room_code = None
            st.rerun()
        st.stop()

    room_data = room_doc.to_dict()
    players = room_data.get("players", {})
    current_player = players.get(st.session_state.player_id, {})
    is_host = current_player.get("is_host", False)

    st.sidebar.markdown(f"**Oda Kodu:** `{st.session_state.room_code}`")
    st.sidebar.markdown(f"**Oyuncu Adı:** {current_player.get('name', 'Bilinmiyor')}")

    if st.sidebar.button("🔄 Durumu Yenile"):
        st.rerun()

    # OYUN LOBİSİ (Bekleme Durumu)
    if room_data.get("status") == "waiting":
        st.subheader("Lobi - Oyuncular Bekleniyor")
        
        st.write(f"### Katılan Oyuncular ({len(players)}):")
        for p_id, p_info in players.items():
            host_label = " 👑 (Kurucu)" if p_info.get("is_host") else ""
            st.write(f"- {p_info.get('name')}{host_label}")

        st.divider()

        # KURUCU KONTROLLERİ (BOT VE TEST MODU)
        if is_host:
            st.subheader("⚙️ Oda & Test Ayarları")
            
            # Test Modu Anahtarı
            test_mode = st.toggle("🧪 Test Modu (Rolleri Herkese Açık Göster)", value=room_data.get("test_mode", False))
            if test_mode != room_data.get("test_mode"):
                room_ref.update({"test_mode": test_mode})
                st.rerun()

            col_b1, col_b2 = st.columns(2)
            with col_b1:
                if st.button("🤖 Bot Ekle"):
                    add_bot(st.session_state.room_code)
                    st.rerun()
            with col_b2:
                if st.button("🗑️ Botları Temizle"):
                    clear_bots(st.session_state.room_code)
                    st.rerun()

            st.divider()
            if st.button("🚀 Oyunu Başlat", type="primary", use_container_width=True):
                start_game(st.session_state.room_code)
                st.rerun()
        else:
            if room_data.get("test_mode"):
                st.info("🧪 Bu oda Test Modunda açıldı.")
            st.info("Kurucunun oyunu başlatması bekleniyor...")

    # OYUN EKRANI (Devam Eden Oyun)
    elif room_data.get("status") == "playing":
        st.subheader("🎮 Oyun Başladı!")
        
        test_active = room_data.get("test_mode", False)
        if test_active:
            st.warning("🧪 TEST MODU AKTİF - Tüm oyuncuların rolleri görünür durumda.")

        # Kendi Rol Gösterimi
        role = current_player.get("role", "Villager")
        if role == "Vampire":
            st.error("🔥 Rolün: **KIRA / VAMPİR** (Köylüleri elenmeden avla!)")
        else:
            st.success("🛡️ Rolün: **KÖYLÜ** (Aramızdaki Kira'yı tespit et!)")

        st.divider()
        st.write("### Oyuncu Listesi:")
        
        for p_id, p_info in players.items():
            status_icon = "💚" if p_info.get("is_alive") else "💀"
            role_text = ""
            
            # Test Modunda veya Oyuncunun Kendi Rolünde Bilgi Gösterimi
            if test_active or p_id == st.session_state.player_id:
                p_role = "Kira/Vampir" if p_info.get("role") == "Vampire" else "Köylü"
                role_text = f" — **[{p_role}]**"

            st.write(f"{status_icon} {p_info.get('name')}{role_text}")

        if is_host:
            st.divider()
            if st.button("🔄 Oyunu Lobiye Döndür (Yeniden Başlat)"):
                reset_game(st.session_state.room_code)
                st.rerun()

    st.divider()
    if st.button("Odadan Ayrıl"):
        st.session_state.room_code = None
        st.rerun()
