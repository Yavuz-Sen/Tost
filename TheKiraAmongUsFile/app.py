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
        return True, "🎉 KÖYLÜLER KAZANDI! Tüm vampirler elendi."
    elif alive_vampires >= alive_others:
        return True, "🧛‍♂️ VAMPİRLER KAZANDI! Vampirler kasaba hakimiyetini sağladı."
    
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
                    "settings": {
                        "reveal_roles": True,
                        "show_vote_counts": True,
                        "show_who_voted_whom": True,
                        "test_mode": False,
                        "host_chosen_role": "Köylü"
                    },
                    "players": {
                        player_name: {"role": None, "is_alive": True, "voted_against": None, "is_bot": False}
                    },
                    "night_actions": {"vampire_target": None, "doctor_target": None, "seer_target": None},
                    "seer_result": None,
                    "messages": [],
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
    settings = room_data.get("settings", {})
    my_name = st.session_state.player_name
    my_info = players.get(my_name, {})
    is_host = room_data.get("host") == my_name
    status = room_data.get("status")

    st.sidebar.markdown(f"**Oda Kodu:** `{st.session_state.room_code}`")
    st.sidebar.markdown(f"**Oyuncu Adı:** {my_name}")
    if settings.get("test_mode"):
        st.sidebar.warning("🧪 Test Modu Aktif")
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
            host_tag = " (Kurucu)" if p_name == room_data['host'] else ""
            st.write(f"- {p_name}{bot_tag}{host_tag}")

        if is_host:
            st.markdown("---")
            st.subheader("⚙️ Oda Ayarları (Sadece Kurucu)")
            
            reveal_roles = st.checkbox("🎭 Ölen kişinin rolü açıklansın mı?", value=settings.get("reveal_roles", True))
            show_vote_counts = st.checkbox("📊 Oy sayıları gözüksün mü?", value=settings.get("show_vote_counts", True))
            show_who_voted_whom = st.checkbox("🔍 Kimin kime oy verdiği gözüksün mü?", value=settings.get("show_who_voted_whom", True))
            
            st.markdown("---")
            test_mode = st.checkbox("🧪 Test Modunu Etkinleştir", value=settings.get("test_mode", False))
            host_chosen_role = settings.get("host_chosen_role", "Köylü")
            if test_mode:
                roles_list = ["Vampir", "Doktor", "Gözcü", "Köylü"]
                idx = roles_list.index(host_chosen_role) if host_chosen_role in roles_list else 3
                host_chosen_role = st.selectbox("Test Modu Rolünüzü Seçin:", roles_list, index=idx)

            # Ayarları Güncelle
            room_ref.update({
                "settings.reveal_roles": reveal_roles,
                "settings.show_vote_counts": show_vote_counts,
                "settings.show_who_voted_whom": show_who_voted_whom,
                "settings.test_mode": test_mode,
                "settings.host_chosen_role": host_chosen_role
            })

            st.markdown("---")
            st.write("### 🤖 Bot Ekle")
            bot_col1, bot_col2 = st.columns([2, 1])
            with bot_col1:
                custom_bot_name = st.text_input("Bot İsmi (İsteğe Bağlı):", key="bot_name_input")
            with bot_col2:
                st.write("")
                st.write("") 
                if st.button("Botu Ekle"):
                    bot_count = room_data.get("bot_count", 0) + 1
                    bot_name = custom_bot_name.strip() if custom_bot_name.strip() else f"Bot_{bot_count}"
                    if bot_name in players:
                        st.error("Bu isimde bir oyuncu zaten var!")
                    else:
                        room_ref.update({
                            f"players.{bot_name}": {"role": None, "is_alive": True, "voted_against": None, "is_bot": True},
                            "bot_count": bot_count
                        })
                        st.rerun()

            st.markdown("---")
            if len(players) < 3:
                st.warning("Oyunu başlatabilmek için en az 3 oyuncu gereklidir.")
            elif st.button("Oyunu Başlat (Rolleri Dağıt)", type="primary"):
                player_list = list(players.keys())
                roles_assignment = {}

                if settings.get("test_mode"):
                    h_role = settings.get("host_chosen_role", "Köylü")
                    roles_assignment[my_name] = h_role
                    
                    other_players = [p for p in player_list if p != my_name]
                    random.shuffle(other_players)
                    
                    pool = ["Vampir", "Doktor", "Gözcü", "Köylü", "Köylü"]
                    if h_role in pool:
                        pool.remove(h_role)
                    
                    for p in other_players:
                        if pool:
                            roles_assignment[p] = pool.pop(0)
                        else:
                            roles_assignment[p] = "Köylü"
                else:
                    random.shuffle(player_list)
                    roles_assignment[player_list[0]] = "Vampir"
                    roles_assignment[player_list[1]] = "Doktor"
                    if len(player_list) >= 4:
                        roles_assignment[player_list[2]] = "Gözcü"
                        for p in player_list[3:]:
                            roles_assignment[p] = "Köylü"
                    else:
                        for p in player_list[2:]:
                            roles_assignment[p] = "Köylü"

                updates = {"status": "NIGHT", "logs": ["Oyun başladı! Gece çöktü..."]}
                for p, r in roles_assignment.items():
                    updates[f"players.{p}.role"] = r
                
                room_ref.update(updates)
                st.rerun()

    # --- DURUM 2: GECE FAZI ---
    elif status == "NIGHT":
        st.subheader("🌙 Gece Oldu")
        
        logs = room_data.get("logs", [])
        if logs:
            st.info(logs[-1])

        if not my_info.get("is_alive"):
            st.error("Elendiniz! Şu an oyunu izliyorsunuz.")
        else:
            role = my_info.get("role")
            alive_players = [p for p, data in players.items() if data["is_alive"] and p != my_name]

            if role == "Vampir":
                st.write("### 🧛‍♂️ Vampir Hamlesi")
                target = st.radio("Saldırmak istediğiniz kişi:", alive_players, key="vampire_choice")
                if st.button("Hedefi Onayla"):
                    room_ref.update({"night_actions.vampire_target": target})
                    st.success(f"{target} hedef seçildi.")

            elif role == "Doktor":
                st.write("### 🩺 Doktor Hamlesi")
                target = st.radio("Korumak istediğiniz kişi:", list(players.keys()), key="doctor_choice")
                if st.button("Korumayı Onayla"):
                    room_ref.update({"night_actions.doctor_target": target})
                    st.success(f"{target} korumaya alındı.")

            elif role == "Gözcü":
                st.write("### 🔮 Gözcü Hamlesi")
                target = st.radio("Rolünü öğrenmek istediğiniz kişi:", alive_players, key="seer_choice")
                if st.button("Görü Al"):
                    target_role = players.get(target, {}).get("role", "Bilinmiyor")
                    room_ref.update({"seer_result": f"🔮 {target} kişisinin rolü: **{target_role}**"})
                    st.success("Görü alındı!")
                
                seer_res = room_data.get("seer_result")
                if seer_res:
                    st.info(seer_res)

            elif role == "Köylü":
                st.info("Siz köylüsünüz. Gece vakti yapmanız gereken bir aksiyon yok.")

        if is_host:
            st.markdown("---")
            if st.button("Sabahı Başlat"):
                actions = room_data.get("night_actions", {})
                v_target = actions.get("vampire_target")
                d_target = actions.get("doctor_target")

                all_alive = [p for p, data in players.items() if data["is_alive"]]

                # BOT GECE HAMLELERİ
                for p_name, p_data in players.items():
                    if p_data["is_alive"] and p_data.get("is_bot"):
                        bot_role = p_data.get("role")
                        if bot_role == "Vampir" and not v_target:
                            possible_targets = [p for p in all_alive if p != p_name]
                            if possible_targets:
                                v_target = random.choice(possible_targets)
                        elif bot_role == "Doktor" and not d_target:
                            d_target = random.choice(all_alive)

                killed_player = None
                log_msg = "☀️ **Sabah Oldu!**\n\n"

                if v_target and v_target != d_target:
                    killed_player = v_target
                    role_str = f" ({players[killed_player]['role']})" if settings.get("reveal_roles") else ""
                    log_msg += f"🩸 Gece **{killed_player}**{role_str} saldırıya uğradı ve öldü.\n"
                elif v_target and v_target == d_target:
                    log_msg += "🛡️ Doktor doğru kişiyi korudu! Kimse ölmedi.\n"
                else:
                    log_msg += "🕊️ Gece sakin geçti, kimse zarar görmedi.\n"

                updates = {
                    "status": "DAY",
                    "night_actions": {"vampire_target": None, "doctor_target": None, "seer_target": None},
                    "seer_result": None
                }
                
                temp_players = dict(players)
                if killed_player:
                    updates[f"players.{killed_player}.is_alive"] = False
                    temp_players[killed_player]["is_alive"] = False

                is_over, result_msg = check_game_over(temp_players)
                if is_over:
                    updates["status"] = "GAME_OVER"
                    log_msg += f"\n🏆 **{result_msg}**"

                room_ref.update(updates)
                room_ref.update({"logs": firestore.ArrayUnion([log_msg])})
                st.rerun()

    # --- DURUM 3: GÜNDÜZ FAZI ---
    elif status == "DAY":
        st.subheader("☀️ Gündüz Oldu")
        
        logs = room_data.get("logs", [])
        if logs:
            st.info(logs[-1])

        st.write("### 👥 Oyuncular:")
        col_a, col_d = st.columns(2)
        with col_a:
            st.markdown("**🟢 Hayattakiler:**")
            for p, data in players.items():
                if data["is_alive"]:
                    st.write(f"- {p}" + (" 🤖" if data.get("is_bot") else ""))
        with col_d:
            st.markdown("**💀 Ölenler:**")
            for p, data in players.items():
                if not data["is_alive"]:
                    role_str = f" ({data.get('role')})" if settings.get("reveal_roles") else ""
                    st.write(f"- ~{p}~{role_str}")

        st.markdown("---")
        if my_info.get("is_alive"):
            st.write("### 🗳️ Oylama")
            candidates = [p for p, data in players.items() if data["is_alive"] and p != my_name]
            vote_target = st.selectbox("Kasabadan sürülmesini istediğiniz kişi:", candidates)
            
            if st.button("Oyunuzu Verin"):
                room_ref.update({f"players.{my_name}.voted_against": vote_target})
                st.success(f"Oyunuz ({vote_target}) kaydedildi.")
        else:
            st.warning("Ölü olduğunuz için oy kullanamazsınız.")

        if is_host:
            st.markdown("---")
            if st.button("Oylamayı Bitir ve Geceye Geç", type="primary"):
                all_alive = [p for p, data in players.items() if data["is_alive"]]

                # BOT OYLARI
                for p_name, p_data in players.items():
                    if p_data["is_alive"] and p_data.get("is_bot"):
                        targets = [p for p in all_alive if p != p_name]
                        if targets:
                            bot_vote = random.choice(targets)
                            room_ref.update({f"players.{p_name}.voted_against": bot_vote})

                updated_room = room_ref.get().to_dict()
                updated_players = updated_room.get("players", {})

                # OYLARI HESAPLA VE AYARLARA GÖRE METİN OLUŞTUR
                votes_received = {}
                voter_details = []

                for p, data in updated_players.items():
                    target = data.get("voted_against")
                    if target and updated_players.get(p, {}).get("is_alive"):
                        votes_received[target] = votes_received.get(target, 0) + 1
                        voter_details.append(f"• **{p}** ➡️ **{target}**")

                eliminated_player = None
                if votes_received:
                    max_votes = max(votes_received.values())
                    top_candidates = [p for p, count in votes_received.items() if count == max_votes]
                    if len(top_candidates) == 1:
                        eliminated_player = top_candidates[0]

                # AYARLARA GÖRE ÖZET ÇIKAR
                summary_lines = ["📊 **Oylama Sonucu**"]

                if settings.get("show_who_voted_whom") and voter_details:
                    summary_lines.append("\n**Kimin Kime Oy Verdiği:**")
                    summary_lines.extend(voter_details)

                if settings.get("show_vote_counts") and votes_received:
                    summary_lines.append("\n**Oy Sayıları:**")
                    for t_p, count in votes_received.items():
                        summary_lines.append(f"• **{t_p}**: {count} oy")

                if eliminated_player:
                    role_str = f" ({updated_players[eliminated_player].get('role')})" if settings.get("reveal_roles") else ""
                    summary_lines.append(f"\n🔥 En çok oyu alan **{eliminated_player}**{role_str} kasabadan sürüldü!")
                else:
                    summary_lines.append("\n⚖️ Eşitlik nedeniyle kimse elenmedi.")

                updates = {"status": "NIGHT"}
                
                if eliminated_player:
                    updates[f"players.{eliminated_player}.is_alive"] = False
                    updated_players[eliminated_player]["is_alive"] = False

                for p in updated_players.keys():
                    updates[f"players.{p}.voted_against"] = None

                is_over, result_msg = check_game_over(updated_players)
                if is_over:
                    updates["status"] = "GAME_OVER"
                    summary_lines.append(f"\n🏆 **{result_msg}**")

                log_msg = "\n".join(summary_lines)
                room_ref.update(updates)
                room_ref.update({"logs": firestore.ArrayUnion([log_msg])})
                st.rerun()

    # --- DURUM 4: OYUN BİTTİ ---
    elif status == "GAME_OVER":
        st.subheader("🏆 Oyun Bitti!")
        logs = room_data.get("logs", [])
        if logs:
            st.success(logs[-1])

        st.write("### 📜 Tüm Oyuncular ve Rolleri:")
        for p, data in players.items():
            status_str = "🟢 Hayatta" if data.get("is_alive") else "💀 Ölü"
            st.write(f"- **{p}**: {data.get('role', 'Bilinmiyor')} ({status_str})")

        if is_host:
            st.markdown("---")
            if st.button("Lobiye Dön"):
                room_ref.update({
                    "status": "LOBBY",
                    "logs": ["Yeni oyun için lobiye dönüldü."]
                })
                st.rerun()

    # --- SOHBET / CHAT MODÜLÜ ---
    st.markdown("---")
    st.subheader("💬 Kasaba Sohbeti")
    
    messages = room_data.get("messages", [])
    chat_container = st.container()
    
    with chat_container:
        for msg in messages[-10:]:
            st.text(f"{msg['sender']}: {msg['text']}")

    col_chat1, col_chat2 = st.columns([4, 1])
    with col_chat1:
        new_msg = st.text_input("Mesajınız:", key="chat_input", label_visibility="collapsed")
    with col_chat2:
        if st.button("Gönder"):
            if new_msg.strip():
                msg_data = {"sender": my_name, "text": new_msg.strip()}
                room_ref.update({"messages": firestore.ArrayUnion([msg_data])})
                st.rerun()

    time.sleep(4)
    st.rerun()
