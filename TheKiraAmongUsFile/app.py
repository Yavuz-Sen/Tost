import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import random
import json

# ---------------------------------------------------------
# 1. FIREBASE INITIALIZATION
# ---------------------------------------------------------
@st.cache_resource
def init_firebase():
    if not firebase_admin._apps:
        # secrets.toml dosyasından bilgileri al
        key_dict = dict(st.secrets["textkey"])
        cred = credentials.Certificate(key_dict)
        firebase_admin.initialize_app(cred)
    return firestore.client()

db = init_firebase()

st.set_page_config(page_title="Vampir Köylü", page_icon="🐺", layout="centered")

# ---------------------------------------------------------
# 2. SESSION STATE MANAGEMENT
# ---------------------------------------------------------
if "room_code" not in st.session_state:
    st.session_state.room_code = None
if "player_name" not in st.session_state:
    st.session_state.player_name = None

st.title("🐺 Vampir Köylü (Mafia)")

# ---------------------------------------------------------
# 3. LOBBY / ROOM CREATION
# ---------------------------------------------------------
if not st.session_state.room_code:
    tab1, tab2 = st.tabs(["Odaya Katıl", "Yeni Oda Oluştur"])

    with tab1:
        with st.form("join_form"):
            name_input = st.text_input("Kullanıcı Adınız")
            code_input = st.text_input("Oda Kodu (6 Haneli)").upper()
            submit_join = st.form_submit_button("Odaya Katıl")

            if submit_join and name_input and code_input:
                doc_ref = db.collection("games").document(code_input)
                doc = doc_ref.get()
                if doc.exists:
                    game_data = doc.to_dict()
                    if name_input in game_data["players"]:
                        st.error("Bu isimde bir oyuncu zaten var.")
                    elif game_data["status"] != "lobby":
                        st.error("Bu oyun zaten başladı.")
                    else:
                        # Oyuncuyu ekle
                        game_data["players"][name_input] = {"role": "Bilinmiyor", "alive": True}
                        doc_ref.update({"players": game_data["players"]})
                        st.session_state.room_code = code_input
                        st.session_state.player_name = name_input
                        st.rerun()
                else:
                    st.error("Oda bulunamadı!")

    with tab2:
        with st.form("create_form"):
            host_name = st.text_input("Kurucu Adı")
            submit_create = st.form_submit_button("Oda Oluştur")

            if submit_create and host_name:
                room_code = str(random.randint(100000, 999999))
                game_data = {
                    "host": host_name,
                    "status": "lobby",  # status: lobby, night, day
                    "players": {
                        host_name: {"role": "Bilinmiyor", "alive": True}
                    },
                    "votes": {},
                    "logs": ["Oda oluşturuldu."]
                }
                db.collection("games").document(room_code).set(game_data)
                st.session_state.room_code = room_code
                st.session_state.player_name = host_name
                st.rerun()

# ---------------------------------------------------------
# 4. GAME ENGINE & ROOM LOGIC
# ---------------------------------------------------------
else:
    room_code = st.session_state.room_code
    player_name = st.session_state.player_name
    doc_ref = db.collection("games").document(room_code)
    game_doc = doc_ref.get()

    if not game_doc.exists:
        st.error("Oda kapatıldı veya bulunamadı.")
        if st.button("Ana Sayfaya Dön"):
            st.session_state.room_code = None
            st.session_state.player_name = None
            st.rerun()
        st.stop()

    game = game_doc.to_dict()
    is_host = (game["host"] == player_name)

    # Üst Bilgi Paneli
    st.sidebar.title(f"Oda Kodu: `{room_code}`")
    st.sidebar.write(f"**Oyuncu:** {player_name}")
    if is_host:
        st.sidebar.success("👑 Oda Yöneticisisiniz")

    if st.sidebar.button("Yenile 🔄"):
        st.rerun()

    if st.sidebar.button("Oıdadan Ayrıl 🚪"):
        if player_name in game["players"]:
            del game["players"][player_name]
            doc_ref.update({"players": game["players"]})
        st.session_state.room_code = None
        st.session_state.player_name = None
        st.rerun()

    # -----------------------------------------------------
    # EKRAN 1: LOBİ (LOBBY)
    # -----------------------------------------------------
    if game["status"] == "lobby":
        st.subheader("📋 Lobi")
        st.write("Oyuncular bekleniyor...")

        players_list = list(game["players"].keys())
        st.write("**Katılan Oyuncular:**", ", ".join(players_list))

        if is_host:
            st.divider()
            st.subheader("Oyun Ayarları & Başlatma")
            num_vampires = st.number_input("Vampir Sayısı", min_value=1, max_value=max(1, len(players_list)-1), value=1)
            num_doctors = st.number_input("Doktor Sayısı", min_value=0, max_value=1, value=1 if len(players_list) > 3 else 0)

            if st.button("Oyunu Başlat 🚀", type="primary"):
                if len(players_list) < 3:
                    st.warning("Oyunu başlatmak için en az 3 oyuncu gereklidir!")
                else:
                    # Rol Dağıtımı
                    roles = ["Vampir"] * num_vampires + ["Doktor"] * num_doctors
                    roles += ["Köylü"] * (len(players_list) - len(roles))
                    random.shuffle(roles)

                    updated_players = {}
                    for i, p_name in enumerate(players_list):
                        updated_players[p_name] = {
                            "role": roles[i],
                            "alive": True
                        }

                    doc_ref.update({
                        "status": "night",
                        "players": updated_players,
                        "logs": game.get("logs", []) + ["Oyun başladı! Gece oldu... 🌙"]
                    })
                    st.rerun()

    # -----------------------------------------------------
    # EKRAN 2 & 3: GECE / GÜNDÜZ EVRELERİ
    # -----------------------------------------------------
    else:
        player_info = game["players"].get(player_name, {})
        is_alive = player_info.get("alive", False)
        role = player_info.get("role", "Bilinmiyor")

        # Rol Kartı
        st.info(f"**Gizli Rolünüz:** {role}" if is_alive else "☠️ **Elendiniz (Ölüsünüz)**")

        st.divider()

        # OYUN DURUMU: GECE
        if game["status"] == "night":
            st.header("🌙 Gece Fazı")
            st.write("Şehir uyuyor... Özel roller eylemlerini seçiyor.")

            if is_alive:
                if role == "Vampir":
                    st.subheader("🎯 Kimi avlamak istiyorsun?")
                    targets = [p for p, data in game["players"].items() if data["alive"] and data["role"] != "Vampir"]
                    target = st.radio("Hedef Seç:", targets, key="vampire_target")
                    if st.button("Saldır"):
                        votes = game.get("votes", {})
                        votes["vampire_target"] = target
                        doc_ref.update({"votes": votes})
                        st.success(f"{target} hedeflendi.")

                elif role == "Doktor":
                    st.subheader("🛡️ Kimi korumak istiyorsun?")
                    targets = [p for p, data in game["players"].items() if data["alive"]]
                    target = st.radio("Hedef Seç:", targets, key="doctor_target")
                    if st.button("Koru"):
                        votes = game.get("votes", {})
                        votes["doctor_target"] = target
                        doc_ref.update({"votes": votes})
                        st.success(f"{target} koruma altına alındı.")

                elif role == "Köylü":
                    st.write("Köylüsünüz, gece yapacak bir eyleminiz yok. Gece bitimini bekleyin.")

            # Geceyi Bitirme (Sadece Host)
            if is_host:
                st.divider()
                if st.button("Gündüze Geç ☀️"):
                    votes = game.get("votes", {})
                    vampire_target = votes.get("vampire_target")
                    doctor_target = votes.get("doctor_target")

                    log_entry = ""
                    players = game["players"]

                    if vampire_target and vampire_target != doctor_target:
                        players[vampire_target]["alive"] = False
                        log_entry = f"☀️ Sabah oldu. Dün gece {vampire_target} saldırıya uğradı ve öldü!"
                    else:
                        log_entry = "☀️ Sabah oldu. Dün gece kimse ölmedi!"

                    doc_ref.update({
                        "status": "day",
                        "players": players,
                        "votes": {},  # Oyları sıfırla
                        "logs": game.get("logs", []) + [log_entry]
                    })
                    st.rerun()

        # OYUN DURUMU: GÜNDÜZ
        elif game["status"] == "day":
            st.header("☀️ Gündüz Fazı")
            st.write("Tartışın ve şüphelendiğiniz kişiyi oylayın.")

            if is_alive:
                st.subheader("🗳️ Oylama")
                targets = [p for p, data in game["players"].items() if data["alive"] and p != player_name]
                vote_target = st.radio("Sürgün etmek istediğin kişi:", targets, key="day_vote")
                
                if st.button("Oy Ver"):
                    votes = game.get("votes", {})
                    votes[player_name] = vote_target
                    doc_ref.update({"votes": votes})
                    st.success(f"{vote_target} için oy kullandınız.")

            # Oylamayı Sonlandırma (Sadece Host)
            if is_host:
                st.divider()
                if st.button("Oylamayı Bitir ve Geceye Geç 🌙"):
                    votes = game.get("votes", {})
                    
                    if votes:
                        # En çok oy kalanı bul
                        from collections import Counter
                        vote_counts = Counter(votes.values())
                        eliminated = vote_counts.most_common(1)[0][0]

                        players = game["players"]
                        players[eliminated]["alive"] = False
                        log_entry = f"🌙 Oylama sonucunda {eliminated} köyden sürgün edildi!"
                    else:
                        log_entry = "🌙 Oylamada kimse seçilmedi."

                    doc_ref.update({
                        "status": "night",
                        "players": players,
                        "votes": {},
                        "logs": game.get("logs", []) + [log_entry]
                    })
                    st.rerun()

        # -----------------------------------------------------
        # OYUN GÜNLÜĞÜ VE YAŞAYANLAR
        # -----------------------------------------------------
        st.divider()
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("📜 Oyun Günlüğü")
            for log in reversed(game.get("logs", [])):
                st.write(f"- {log}")

        with col2:
            st.subheader("👥 Oyuncu Durumları")
            for p, data in game["players"].items():
                status_icon = "🟢 Yaşıyor" if data["alive"] else "🔴 Ölü"
                st.write(f"- **{p}**: {status_icon}")
