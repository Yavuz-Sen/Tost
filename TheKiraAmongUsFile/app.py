import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import random
import time

# --- 1. FIREBASE BAĞLANTISI ---
if not firebase_admin._apps:
    key_dict = dict(st.secrets["textkey"])
    cred = credentials.Certificate(key_dict)
    firebase_admin.initialize_app(cred)

db = firestore.client()

st.set_page_config(page_title="Vampir Köylü", page_icon="🧛‍♂️", layout="centered")

# --- 2. SESSION STATE KONTROLLERİ ---
if "player_name" not in st.session_state:
    st.session_state.player_name = ""
if "room_code" not in st.session_state:
    st.session_state.room_code = ""

st.title("🧛‍♂️ Vampir Köylü")

# --- YARDIMCI FONKSİYON: KAZANMA KONTROLÜ ---
def check_game_over(players):
    alive_vampires = 0
    alive_others = 0
    
    for p_data in players.values():
        if p_data.get("is_alive"):
            if p_data.get("role") == "Vampir":
                alive_vampires += 1
            else:
                alive_others += 1

    if alive_vampires == 0:
        return True, "🎉 KÖYLÜLER KAZANDI! Tüm vampirler temizlendi."
    elif alive_vampires >= alive_others:
        return True, "🧛‍♂️ VAMPİRLER KAZANDI! Kasabadaki kontrolü tamamen ele geçirdiler."
    
    return False, ""

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
                    "bot_count": 0,
                    "players": {
                        player_name: {"role": None, "is_alive": True, "voted_against": None, "is_bot": False}
                    },
                    "night_actions": {"vampire_target": None, "doctor_target": None, "seer_target": None},
                    "seer_result": None,
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
                        f"players.{player_name}": {"role": None, "is_alive": True, "voted_against": None, "is_bot": False}
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

    if st.sidebar.button("Ekranı Yenile 🔄"):
        st.rerun()

    # --- DURUM 1: LOBİ ---
    if status == "LOBBY":
        st.subheader("Oda Lobisi")
        st.write("### Katılan Oyuncular:")
        for p_name, p_data in players.items():
            bot_tag = " 🤖 (Bot)" if p_data.get("is_bot") else ""
            host_tag = " (Oda Kurucusu)" if p_name == room_data['host'] else ""
            st.write(f"- {p_name}{bot_tag}{host_tag}")

        if is_host:
            st.markdown("---")
            col_bot1, col_bot2 = st.columns(2)
            with col_bot1:
                if st.button("🤖 Bot Ekle"):
                    bot_count = room_data.get("bot_count", 0) + 1
                    bot_name = f"Bot_{bot_count}"
                    room_ref.update({
                        f"players.{bot_name}": {"role": None, "is_alive": True, "voted_against": None, "is_bot": True},
                        "bot_count": bot_count
                    })
                    st.rerun()
            
            with col_bot2:
                if len(players) < 3:
                    st.warning("Oyunu başlatabilmek için en az 3 oyuncu gereklidir.")
                elif st.button("Oyunu Başlat (Rolleri Dağıt)", type="primary"):
                    player_list = list(players.keys())
                    random.shuffle(player_list)
                    
                    roles_assignment = {}
                    roles_assignment[player_list[0]] = "Vampir"
                    roles_assignment[player_list[1]] = "Doktor"
                    if len(player_list) >= 4:
                        roles_assignment[player_list[2]] = "Gözcü"
                        for p in player_list[3:]:
                            roles_assignment[p] = "Köylü"
                    else:
                        for p in player_list[2:]:
                            roles_assignment[p] = "Köylü"

                    updates = {"status": "NIGHT", "logs": ["Oyun başladı! İlk gece daldı..."]}
                    for p, r in roles_assignment.items():
                        updates[f"players.{p}.role"] = r
                    
                    room_ref.update(updates)
                    st.rerun()

    # --- DURUM 2: GECE FAZI ---
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

            elif role == "Gözcü":
                st.write("### 🔮 Gözcü Hamlesi")
                target = st.radio("Rolünü öğrenmek istediğiniz kişiyi seçiniz:", alive_players, key="seer_choice")
                if st.button("Görü Al"):
                    target_role = players.get(target, {}).get("role", "Bilinmiyor")
                    room_ref.update({"seer_result": f"🔮 {target} kişisinin rolü: **{target_role}**"})
                    st.success("Görü alındı!")
                
                seer_res = room_data.get("seer_result")
                if seer_res:
                    st.info(seer_res)

            elif role == "Köylü":
                st.info("Siz köylüsünüz. Gece vakti yapmanız gereken bir aksiyon bulunmuyor.")

        if is_host:
            st.markdown("---")
            if st.button("Sabahı Başlat"):
                actions = room_data.get("night_actions", {})
                v_target = actions.get("vampire_target")
                d_target = actions.get("doctor_target")

                all_alive = [p for p, data in players.items() if data["is_alive"]]

                # Bot Gece Hamleleri
                for p_name, p_data in players.items():
                    if p_data["is_alive"] and p_data.get("is_bot"):
                        bot_role = p_data.get("role")
                        if bot_role == "Vampir" and not v_target:
                            targets = [p for p in all_alive if p != p_name]
                            if targets:
                                v_target = random.choice(targets)
                        elif bot_role == "Doktor" and not d_target:
                            d_target = random.choice(all_alive)

                killed_player = None
                log_msg = "Sabah oldu. "

                if v_target and v_target != d_target:
                    killed_player = v_target
                    log_msg += f"Gece **{killed_player}** saldırıya uğradı ve öldü!"
                else:
                    log_msg += "Gece sakin geçti, kimse ölmedi!"

                updates = {
                    "status": "DAY",
                    "night_actions": {"vampire_target": None, "doctor_target": None, "seer_target": None},
                    "seer_result": None
                }
                
                if killed_player:
                    updates[f"players.{killed_player}.is_alive"] = False

                # Güncellenmiş oyuncu listesi üzerinden oyun sonu kontrolü
                temp_players = dict(players)
                if killed_player:
                    temp_players[killed_player]["is_alive"] = False

                is_over, result_msg = check_game_over(temp_players)
                if is_over:
                    updates["status"] = "GAME_OVER"
                    log_msg += f" {result_msg}"

                room_ref.update(updates)
                room_ref.update({"logs": firestore.ArrayUnion([log_msg])})
                st.rerun()

    # --- DURUM 3: GÜNDÜZ FAZI ---
    elif status == "DAY":
        st.subheader("☀️ Gündüz Oldu")
        
        logs = room_data.get("logs", [])
        if logs:
            st.info(logs[-1])

        st.write("### Oyuncu Durumları:")
        for p, data in players.items():
            status_text = "🟢 Hayatta" if data["is_alive"] else "💀 Ölü"
            bot_tag = " 🤖" if data.get("is_bot") else ""
            st.write(f"- **{p}**{bot_tag}: {status_text}")

        if my_info.get("is_alive"):
            st.write("### Oylama")
            candidates = [p for p, data in players.items() if data["is_alive"] and p != my_name]
            vote_target = st.selectbox("Elenmesini istediğiniz kişi:", candidates)
            
            if st.button("Oy Kullan"):
                room_ref.update({f"players.{my_name}.voted_against": vote_target})
                st.success("Oyunuz kaydedildi.")

        if is_host:
            st.markdown("---")
            if st.button("Oylamayı Bitir ve Geceye Geç"):
                all_alive = [p for p, data in players.items() if data["is_alive"]]
                for p_name, p_data in players.items():
                    if p_data["is_alive"] and p_data.get("is_bot"):
                        targets = [p for p in all_alive if p != p_name]
                        if targets:
                            bot_vote = random.choice(targets)
                            room_ref.update({f"players.{p_name}.voted_against": bot_vote})

                updated_room = room_ref.get().to_dict()
                updated_players = updated_room.get("players", {})

                votes = {}
                for p, data in updated_players.items():
                    target = data.get("voted_against")
                    if target and updated_players.get(p, {}).get("is_alive"):
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

                for p in updated_players.keys():
                    updates[f"players.{p}.voted_against"] = None

                # Oyun sonu kontrolü
                is_over, result_msg = check_game_over(updated_players)
                if is_over:
                    updates["status"] = "GAME_OVER"
                    log_msg += f" {result_msg}"

                room_ref.update(updates)
                room_ref.update({"logs": firestore.ArrayUnion([log_msg])})
                st.rerun()

    # --- DURUM 4: OYUN BİTTİ ---
    elif status == "GAME_OVER":
        st.subheader("🏆 Oyun Bitti!")
        logs = room_data.get("logs", [])
        if logs:
            st.success(logs[-1])

        st.write("### Tüm Oyuncular ve Rolleri:")
        for p, data in players.items():
            st.write(f"- **{p}**: {data.get('role', 'Bilinmiyor')}")

        if is_host:
            st.markdown("---")
            if st.button("Lobiye Dön"):
                room_ref.update({
                    "status": "LOBBY",
                    "logs": ["Yeni oyun için lobiye dönüldü."]
                })
                st.rerun()

    # Otomatik sayfa yenileme
    time.sleep(4)
    st.rerun()
