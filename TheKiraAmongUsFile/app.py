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
st.set_page_config(page_title="Death Note: Kasabadaki Defter", page_icon="📓", layout="centered")

if "player_id" not in st.session_state:
    st.session_state.player_id = f"user_{random.randint(1000, 9999)}"
if "room_code" not in st.session_state:
    st.session_state.room_code = None

BOT_NAMES = ["L", "Near", "Mello", "Ryuk", "Misa", "Rem", "Soichiro", "Matsuda", "Teru Mikami"]

ROLES_INFO = {
    "Kira": {"team": "Kira", "desc": "Her gece bir kişinin adını deftere yazarak eler.", "icon": "💀"},
    "Misa": {"team": "Kira", "desc": "Kira'yı bilir. Gece Şinigami Gözleri ile rol sorgulayabilir.", "icon": "👁️"},
    "L": {"team": "Investigation", "desc": "Her gece bir kişinin tarafını (Kira mı/Masum mu) sorgular.", "icon": "🔍"},
    "Watari": {"team": "Investigation", "desc": "Her gece bir kişiyi korur.", "icon": "🛡️"},
    "Investigator": {"team": "Investigation", "desc": "Soruşturma ekibinin sade üyesi.", "icon": "🕵️"},
    "Ryuk": {"team": "Neutral", "desc": "Tek amacı gündüz oylamasında kendisini astırmaktır!", "icon": "🍎"}
}

# ---------------------------------------------------------
# 3. VERİTABANI YARDIMCI FONKSİYONLARI
# ---------------------------------------------------------
def create_room(room_code, player_name):
    doc_ref = db.collection("rooms").document(room_code)
    doc_ref.set({
        "status": "waiting",
        "phase": "night",
        "round": 1,
        "logs": ["Karanlık çöküyor... Defter bir yerlerde açıldı."],
        "created_at": firestore.SERVER_TIMESTAMP,
        "test_mode": False,
        "night_actions": {},
        "votes": {},
        "ryuk_won": False,
        "misa_eyes_left": 2,
        "players": {
            st.session_state.player_id: {
                "name": player_name,
                "role": "Investigator",
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
                "role": "Investigator",
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
            "role": "Investigator",
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
    p_ids = list(players.keys())
    n = len(p_ids)

    if n < 3:
        st.warning("Oyunu başlatmak için en az 3 oyuncu gereklidir!")
        return

    random.shuffle(p_ids)
    
    # Rol Dağıtımı
    assigned_roles = {}
    assigned_roles[p_ids[0]] = "Kira"
    assigned_roles[p_ids[1]] = "L"
    
    if n >= 4:
        assigned_roles[p_ids[2]] = "Ryuk"
    if n >= 5:
        assigned_roles[p_ids[3]] = "Watari"
    if n >= 6:
        assigned_roles[p_ids[4]] = "Misa"
        
    for p_id in p_ids:
        if p_id not in assigned_roles:
            assigned_roles[p_id] = "Investigator"

    updates = {
        "status": "playing",
        "phase": "night",
        "round": 1,
        "logs": ["Oyun başladı! Soruşturma başladı, Kira aramızda..."],
        "night_actions": {},
        "votes": {},
        "ryuk_won": False,
        "misa_eyes_left": 2
    }
    for p_id in p_ids:
        updates[f"players.{p_id}.role"] = assigned_roles[p_id]
        updates[f"players.{p_id}.is_alive"] = True

    doc_ref.update(updates)

def reset_game(room_code):
    doc_ref = db.collection("rooms").document(room_code)
    doc_ref.update({
        "status": "waiting",
        "phase": "night",
        "round": 1,
        "logs": [],
        "night_actions": {},
        "votes": {},
        "ryuk_won": False
    })

def resolve_night_phase(room_ref, room_data):
    players = room_data.get("players", {})
    actions = room_data.get("night_actions", {})
    logs = room_data.get("logs", [])

    kira_target = actions.get("kira_kill")
    watari_target = actions.get("watari_protect")

    if kira_target:
        if kira_target == watari_target:
            logs.append("🛡️ Watari doğru kişiyi korudu! Bu gece kimse ölmedi.")
        else:
            victim_name = players.get(kira_target, {}).get("name", "Biri")
            players[kira_target]["is_alive"] = False
            logs.append(f"💀 **{victim_name}** ölü bulundu! (Ölüm nedeni: Kalp Krizi)")

    room_ref.update({
        "players": players,
        "phase": "day",
        "night_actions": {},
        "logs": logs
    })

def resolve_day_phase(room_ref, room_data):
    players = room_data.get("players", {})
    votes = room_data.get("votes", {})
    logs = room_data.get("logs", [])

    alive_pids = [p_id for p_id, p in players.items() if p.get("is_alive")]

    # Botların otomatik oy kullanması
    for p_id, p_info in players.items():
        if p_info.get("is_alive") and p_info.get("is_bot") and p_id not in votes:
            votes[p_id] = random.choice(alive_pids)

    if votes:
        vote_counts = {}
        for voted_id in votes.values():
            vote_counts[voted_id] = vote_counts.get(voted_id, 0) + 1

        eliminated_id = max(vote_counts, key=vote_counts.get)
        eliminated_player = players.get(eliminated_id, {})
        eliminated_name = eliminated_player.get("name", "Biri")
        eliminated_role = eliminated_player.get("role")

        players[eliminated_id]["is_alive"] = False
        logs.append(f"⚖️ Mahkeme kararıyla **{eliminated_name}** idam edildi.")

        if eliminated_role == "Ryuk":
            room_ref.update({
                "ryuk_won": True,
                "players": players,
                "logs": logs
            })
            return

    current_round = room_data.get("round", 1)
    logs.append(f"🌙 {current_round + 1}. gece başladı.")

    room_ref.update({
        "players": players,
        "phase": "night",
        "round": current_round + 1,
        "votes": {},
        "logs": logs
    })

# ---------------------------------------------------------
# 4. ARAYÜZ (UI) AKIŞI
# ---------------------------------------------------------
st.title("📓 Death Note: Kasabadaki Defter")

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
        st.error("Oda bulunamadı.")
        if st.button("Ana Menüye Dön"):
            st.session_state.room_code = None
            st.rerun()
        st.stop()

    room_data = room_doc.to_dict()
    players = room_data.get("players", {})
    current_player = players.get(st.session_state.player_id, {})
    is_host = current_player.get("is_host", False)

    st.sidebar.markdown(f"**Oda Kodu:** `{st.session_state.room_code}`")
    st.sidebar.markdown(f"**Oyuncu:** {current_player.get('name', 'Bilinmiyor')}")

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

        if is_host:
            st.subheader("⚙️ Oda Ayarları")
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
                st.info("🧪 Test Modu Aktif.")
            st.info("Kurucunun oyunu başlatması bekleniyor...")

    # OYUN EKRANI
    elif room_data.get("status") == "playing":
        test_active = room_data.get("test_mode", False)
        if test_active:
            st.warning("🧪 TEST MODU AKTİF")

        # KAZANMA KOŞULLARI
        alive_players = {p_id: p for p_id, p in players.items() if p.get("is_alive")}
        kira_team_alive = [p_id for p_id, p in alive_players.items() if ROLES_INFO.get(p.get("role"), {}).get("team") == "Kira"]
        invest_team_alive = [p_id for p_id, p in alive_players.items() if ROLES_INFO.get(p.get("role"), {}).get("team") == "Investigation"]

        if room_data.get("ryuk_won"):
            st.balloons()
            st.success("🍎 **RYUK KAZANDI!** Kendisini astırmayı başardı ve oyunu anında bitirdi!")
            if is_host and st.button("Lobiye Dön"):
                reset_game(st.session_state.room_code)
                st.rerun()
            st.stop()
        elif not kira_team_alive:
            st.balloons()
            st.success("🔍 **SORUŞTURMA EKİBİ KAZANDI!** Kira ve destekçileri elendi.")
            if is_host and st.button("Lobiye Dön"):
                reset_game(st.session_state.room_code)
                st.rerun()
            st.stop()
        elif len(kira_team_alive) >= len(invest_team_alive):
            st.error("💀 **KIRA TARAFI KAZANDI!** Kasaba kontrolünü tamamen ele geçirdi.")
            if is_host and st.button("Lobiye Dön"):
                reset_game(st.session_state.room_code)
                st.rerun()
            st.stop()

        # OYUNCU ROL GÖSTERİMİ
        role = current_player.get("role", "Investigator")
        is_alive = current_player.get("is_alive", True)
        role_data = ROLES_INFO.get(role, ROLES_INFO["Investigator"])

        if not is_alive:
            st.error("💀 **ÖLDÜNÜZ / ELENDİNİZ!** Oyunu izliyorsunuz.")
        else:
            st.info(f"{role_data['icon']} Rolün: **{role}** ({role_data['desc']})")

        st.divider()
        phase = room_data.get("phase", "night")
        st.markdown(f"### 📍 Aşama: **{'🌙 GECE' if phase == 'night' else '☀️ GÜNDÜZ'}** (Raund {room_data.get('round', 1)})")

        # GECE FAZI EYLEMLERİ
        if phase == "night":
            actions = room_data.get("night_actions", {})
            
            if is_alive:
                targets = {p_id: p.get("name") for p_id, p in alive_players.items() if p_id != st.session_state.player_id}

                # Kira
                if role == "Kira":
                    st.subheader("📖 Death Note")
                    selected = st.selectbox("Deftere kurbanın adını yaz:", list(targets.keys()), format_func=lambda x: targets[x])
                    if st.button("Deftere Yaz ✍️"):
                        actions["kira_kill"] = selected
                        room_ref.update({"night_actions": actions})
                        st.success("Kurban kaydedildi.")

                # L
                elif role == "L":
                    st.subheader("🔍 L Soruşturması")
                    selected = st.selectbox("Tarafını sorgulamak istediğin kişi:", list(targets.keys()), format_func=lambda x: targets[x])
                    if st.button("Sorgula"):
                        target_role = players.get(selected, {}).get("role")
                        target_team = ROLES_INFO.get(target_role, {}).get("team")
                        res = "Kira Tarafı 💀" if target_team == "Kira" else "Masum 🛡️"
                        st.warning(f"Sorgulama Sonucu: **{res}**")

                # Watari
                elif role == "Watari":
                    st.subheader("🛡️ Watari Koruması")
                    all_targets = {p_id: p.get("name") for p_id, p in alive_players.items()}
                    selected = st.selectbox("Korumak istediğin kişi:", list(all_targets.keys()), format_func=lambda x: all_targets[x])
                    if st.button("Koruma Altına Al"):
                        actions["watari_protect"] = selected
                        room_ref.update({"night_actions": actions})
                        st.success("Koruma ayarlandı.")

                # Misa
                elif role == "Misa":
                    st.subheader("👁️ Şinigami Gözleri")
                    eyes_left = room_data.get("misa_eyes_left", 2)
                    st.write(f"Kalan Göz Hakkın: **{eyes_left}**")
                    if eyes_left > 0:
                        selected = st.selectbox("Gerçek rolünü öğrenmek istediğin kişi:", list(targets.keys()), format_func=lambda x: targets[x])
                        if st.button("Gözleri Kullan"):
                            target_role = players.get(selected, {}).get("role")
                            st.warning(f"Bu kişinin gerçek rolü: **{target_role}**")
                            room_ref.update({"misa_eyes_left": eyes_left - 1})

            if is_host:
                st.divider()
                if st.button("⚡ Geceyi Bitir ve Sabahı Başlat", type="primary"):
                    resolve_night_phase(room_ref, room_data)
                    st.rerun()

        # GÜNDÜZ FAZI EYLEMLERİ
        elif phase == "day":
            st.subheader("🗳️ Oylama & Mahkeme")
            if is_alive:
                targets = {p_id: p.get("name") for p_id, p in alive_players.items()}
                voted = st.selectbox("Şüphelendiğin kişiye oy ver:", list(targets.keys()), format_func=lambda x: targets[x])
                if st.button("Oyunu Gönder 🗳️"):
                    votes = room_data.get("votes", {})
                    votes[st.session_state.player_id] = voted
                    room_ref.update({"votes": votes})
                    st.success("Oyunuz alındı.")

            if is_host:
                st.divider()
                if st.button("⚡ Oylamayı Sonlandır ve Geceye Geç", type="primary"):
                    resolve_day_phase(room_ref, room_data)
                    st.rerun()

        st.divider()
        st.write("### 📜 Kasaba Olay Günlüğü")
        for log in reversed(room_data.get("logs", [])):
            st.write(f"- {log}")

        st.divider()
        st.write("### Oyuncu Listesi:")
        for p_id, p_info in players.items():
            status_icon = "💚" if p_info.get("is_alive") else "💀"
            role_text = ""
            if test_active or p_id == st.session_state.player_id:
                p_role = p_info.get("role", "Investigator")
                role_text = f" — **[{p_role}]**"

            st.write(f"{status_icon} {p_info.get('name')}{role_text}")

        if is_host:
            st.divider()
            if st.button("🔄 Oyunu Lobiye Döndür"):
                reset_game(st.session_state.room_code)
                st.rerun()

    st.divider()
    if st.button("Odadan Ayrıl"):
        st.session_state.room_code = None
        st.rerun()
