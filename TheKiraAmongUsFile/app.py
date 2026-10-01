import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import random
from st_autorun import autorun

# --- 1. FIREBASE BAĞLANTISI ---
if not firebase_admin._apps:
    # Streamlit Secrets/toml üzerindeki textkey yapısından okur
    key_dict = dict(st.secrets["textkey"])
    cred = credentials.Certificate(key_dict)
    firebase_admin.initialize_app(cred)

db = firestore.client()

st.set_page_config(page_title="Vampir Köylü", page_icon="🧛‍♂️", layout="centered")

# Sayfayı 3000 ms (3 saniye) bir otomatik yeniler
autorun(run_every=3000)

# --- 2. SESSION STATE KONTROLLERİ ---
if "player_name" not in st.session_state:
    st.session_state.player_name = ""
if "room_code" not in st.session_state:
    st.session_state.room_code = ""

st.title("🧛‍♂️ Vampir Köylü")

# --- 3. LOBİ / KATILIM EKRANI ---
if not st.session_state.room_code:
    st.subheader("Giriş Yap")
    player_name = st.text_input("Oyuncu Adınız:", key="input_name")
    
    col1, col2 = st.columns(2)
    with col1:
        new_room = st.text_input("Oluşturulacak Oda Kodu:", key="input_create")
        if st.button("Oda Oluştur"):
            if player_name and new_room:
                room_ref = db.collection("rooms").document(new_room)
                room_ref.set({
                    "status": "LOBBY",
                    "host": player_name,
                    "players": {
                        player_name: {"role": None, "is_alive": True, "voted_against": None}
                    },
                    "night_actions": {"vampire_target": None, "doctor_target": None},
                    "logs": ["Oda oluşturuldu. Oyuncular bekleniyor..."]
                })
                st.session_state.room_code = new_room
                st.session_state.player_name = player_name
                st.rerun()
            else:
                st.warning("Ad ve oda kodu doldurulmalıdır.")

    with col2:
        join_room = st.text_input("Katılınacak Oda Kodu:", key="input_join")
        if st.button("Odaya Katıl"):
            if player_name and join_room:
                room_ref = db.collection("rooms").document(join_room)
                room = room_ref.get()
                if room.exists:
                    room_ref.update({
                        f"players.{player_name}": {"role": None, "is_alive": True, "voted_against": None}
                    })
                    st.session_state.room_code = join_room
                    st.session_state.player_name = player_name
                    st.rerun()
                else:
                    st.error("Oda bulunamadı!")

# --- 4. OYUN EKRANI ---
else:
    room_ref = db.collection("rooms").document(st.session_state.room_code)
    room_doc = room_ref.get()
    
    if not room_doc.exists:
        st.error("Oda bulunamadı veya kapatıldı.")
        st.session_state.room_code = ""
        st.rerun()

    room_data = room_doc.to_dict()
    players = room_data.get("players", {})
    my_name = st.session_state.player_name
    my_info = players.get(my_name, {})
    is_host = room_data.get("host") == my_name
    status = room_data.get("status")

    st.sidebar.markdown(f"**Oda Kodu:** `{st.session_state.room_code}`")
    st.sidebar.markdown(f"**Oyuncu Adı:** {my_name}")
    if my_info.get("role"):
        st.sidebar.info(f"**Rolünüz:** {my_info['role']}")

    # LOBİ AŞAMASI
    if status == "LOBBY":
        st.subheader("Oda Lobisi")
        st.write("### Katılan Oyuncular:")
        for p_name in players.keys():
            st.write(f"- {p_name} {'(Oda Kurucusu)' if p_name == room_data['host'] else ''}")

        if is_host:
            st.markdown("---")
            if len(players) < 3:
                st.warning("Oyunu başlatabilmek için en az 3 oyuncu olmalıdır.")
            elif st.button("Oyunu Başlat (Rolleri Dağıt)", type="primary"):
                player_list = list(players.keys())
                random.shuffle(player_list)
                
                roles_assignment = {}
                roles_assignment[player_list[0]] = "Vampir"
                roles_assignment[player_list[1]] = "Doktor"
                for p in player_list[2:]:
                    roles_assignment[p] = "Köylü"

                updates = {"status": "NIGHT"}
                for p, r in roles_assignment.items():
                    updates[f"players.{p}.role"] = r
                
                room_ref.update(updates)
                st.rerun()

    # GECE AŞAMASI
    elif status == "NIGHT":
        st.subheader("🌙 Gece Oldu")
        st.write("Herkes uykuya daldı...")

        if not my_info.get("is_alive"):
            st.error("Elendiniz! Şu an oyunu izliyorsunuz.")
        else:
            role = my_info.get("role")
            alive_players = [p for p, data in players.items() if data["is_alive"] and p != my_name]

            if role == "Vampir":
                st.write("### 🧛‍♂️ Vampir Hamlesi")
                target = st.radio("Hedef seçiniz:", alive_players, key="vampire_choice")
                if st.button("Hedefi Onayla"):
                    room_ref.update({"night_actions.vampire_target": target})
                    st.success(f"{target} seçildi.")

            elif role == "Doktor":
                st.write("### 🩺 Doktor Hamlesi")
                target = st.radio("Korumak istediğiniz kişiyi seçiniz:", list(players.keys()), key="doctor_choice")
                if st.button("Korumayı Onayla"):
                    room_ref.update({"night_actions.doctor_target": target})
                    st.success(f"{target} korumaya alındı.")

            elif role == "Köylü":
                st.info("Siz köylüsünüz. Gece vakti yapmanız gereken bir aksiyon bulunmuyor, sabaha kadar bekleyin.")

        if is_host:
            st.markdown("---")
            if st.button("Sabahı Başlat"):
                actions = room_data.get("night_actions", {})
                v_target = actions.get("vampire_target")
                d_target = actions.get("doctor_target")

                killed_player = None
                log_msg = "Sabah oldu. "

                if v_target and v_target != d_target:
                    killed_player = v_target
                    log_msg += f"Gece **{killed_player}** saldırıya uğradı ve öldü!"
                else:
                    log_msg += "Gece sakin geçti, kimse ölmedi!"

                updates = {
                    "status": "DAY",
                    "night_actions": {"vampire_target": None, "doctor_target": None}
                }
                
                if killed_player:
                    updates[f"players.{killed_player}.is_alive"] = False

                room_ref.update(updates)
                room_ref.update({"logs": firestore.ArrayUnion([log_msg])})
                st.rerun()

    # GÜNDÜZ AŞAMASI
    elif status == "DAY":
        st.subheader("☀️ Gündüz Oldu")
        
        logs = room_data.get("logs", [])
        if logs:
            st.info(logs[-1])

        st.write("### Oyuncu Durumları:")
        for p, data in players.items():
            status_text = "🟢 Hayatta" if data["is_alive"] else "💀 Ölü"
            st.write(f"- **{p}**: {status_text}")

        if my_info.get("is_alive"):
            st.write("### Oylama")
            candidates = [p for p, data in players.items() if data["is_alive"] and p != my_name]
            vote_target = st.selectbox("Elenmesini istediğiniz kişi:", candidates)
            
            if st.button("Oy Kullan"):
                room_ref.update({f"players.{my_name}.voted_against": vote_target})
                st.success("Oyunuz kaydedildi.")

        if is_host:
            st.markdown("---")
            if st.button("Oylamayı Bitiş Tarihine Çek ve Geceye Geç"):
                votes = {}
                for p, data in players.items():
                    target = data.get("voted_against")
                    if target and players.get(p, {}).get("is_alive"):
                        votes[target] = votes.get(target, 0) + 1

                eliminated_player = None
                if votes:
                    eliminated_player = max(votes, key=votes.get)

                updates = {"status": "NIGHT"}
                log_msg = "Oylama tamamlandı. "

                if eliminated_player:
                    updates[f"players.{eliminated_player}.is_alive"] = False
                    log_msg += f"Oylama sonucu **{eliminated_player}** elendi!"
                else:
                    log_msg += "Kimse elenmedi."

                for p in players.keys():
                    updates[f"players.{p}.voted_against"] = None

                room_ref.update(updates)
                room_ref.update({"logs": firestore.ArrayUnion([log_msg])})
                st.rerun()
