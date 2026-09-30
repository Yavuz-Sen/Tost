import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import json
import random
import time

# ---------------------------------------------------------
# 1. FIREBASE BAĞLANTISI (GÜVENLİ VE HATA YÖNETİMLİ)
# ---------------------------------------------------------
if not firebase_admin._apps:
    try:
        # Streamlit Cloud üzerinde Secrets kontrolü
        if "textkey" in st.secrets:
            key_dict = json.loads(st.secrets["textkey"])
            cred = credentials.Certificate(key_dict)
        else:
            # Yerel bilgisayarda test için dosya kontrolü
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

# ---------------------------------------------------------
# 3. VERİTABANI YARDIMCI FONKSİYONLARI
# ---------------------------------------------------------
def create_room(room_code, player_name):
    doc_ref = db.collection("rooms").document(room_code)
    doc_ref.set({
        "status": "waiting",
        "created_at": firestore.SERVER_TIMESTAMP,
        "players": {
            st.session_state.player_id: {
                "name": player_name,
                "role": "Villager",
                "is_alive": True,
                "is_host": True
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
                "is_host": False
            }
        })
        return True
    return False

def start_game(room_code):
    doc_ref = db.collection("rooms").document(room_code)
    doc = doc_ref.get()
    if not doc.exists:
        return
    
    data = doc.to_dict()
    players = data.get("players", {})
    player_ids = list(players.keys())
    
    if len(player_ids) < 3:
        st.warning("Oyunu başlatmak için en az 3 oyuncu gereklidir!")
        return

    # Rastgele bir Vampir/Kira seç
    vampire_id = random.choice(player_ids)
    
    updates = {"status": "playing"}
    for p_id in player_ids:
        role = "Vampire" if p_id == vampire_id else "Villager"
        updates[f"players.{p_id}.role"] = role

    doc_ref.update(updates)

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

    # Otomatik yenileme yerine manuel yenileme butonu
    if st.sidebar.button("🔄 Durumu Yenile"):
        st.rerun()

    # OYUN LOBİSİ (Bekleme Durumu)
    if room_data.get("status") == "waiting":
        st.subheader("Lobi - Oyuncular Bekleniyor")
        
        st.write("### Katılan Oyuncular:")
        for p_id, p_info in players.items():
            host_label = " 👑 (Kurucu)" if p_info.get("is_host") else ""
            st.write(f"- {p_info.get('name')}{host_label}")

        if is_host:
            st.divider()
            if st.button("Oyun Başlat", type="primary"):
                start_game(st.session_state.room_code)
                st.rerun()
        else:
            st.info("Kurucunun oyunu başlatması bekleniyor...")

    # OYUN EKRANI (Devam Eden Oyun)
    elif room_data.get("status") == "playing":
        st.subheader("🎮 Oyun Başladı!")
        
        # Rol Gösterimi
        role = current_player.get("role", "Villager")
        if role == "Vampire":
            st.error("🔥 Rolün: **KIRA / VAMPİR** (Köylüleri elenmeden avla!)")
        else:
            st.success("🛡️ Rolün: **KÖYLÜ** (Aramızdaki Kira'yı tespit et!)")

        st.divider()
        st.write("### Hayattaki Oyuncular:")
        for p_id, p_info in players.items():
            status_icon = "💚" if p_info.get("is_alive") else "💀"
            st.write(f"{status_icon} {p_info.get('name')}")

    st.divider()
    if st.button("Odadan Ayrıl"):
        st.session_state.room_code = None
        st.rerun()
