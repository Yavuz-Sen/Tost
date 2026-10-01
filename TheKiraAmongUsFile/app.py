import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import random
from streamlit_autorun import autorun

# 1. Firebase Bağlantısı
if not firebase_admin._apps:
    key_dict = dict(st.secrets["textkey"])
    cred = credentials.Certificate(key_dict)
    firebase_admin.initialize_app(cred)

db = firestore.client()

st.set_page_config(page_title="Vampir Köylü", page_icon="🧛‍♂️")

# Canlı senkronizasyon (3 saniyede bir ekranı yeniler)
autorun(interval=3000, key="auto_refresh")

if "player_name" not in st.session_state:
    st.session_state.player_name = ""
if "room_code" not in st.session_state:
    st.session_state.room_code = ""

st.title("🧛‍♂️ Vampir Köylü")

# Lobi / Katılım
if not st.session_state.room_code:
    player_name = st.text_input("Oyuncu Adınız:")
    room_code = st.text_input("Oda Kodu:")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Oda Oluştur"):
            if player_name and room_code:
                db.collection("rooms").document(room_code).set({
                    "status": "LOBBY",
                    "host": player_name,
                    "players": {player_name: {"role": None, "is_alive": True}}
                })
                st.session_state.room_code = room_code
                st.session_state.player_name = player_name
                st.rerun()

    with col2:
        if st.button("Odaya Katıl"):
            if player_name and room_code:
                ref = db.collection("rooms").document(room_code)
                if ref.get().exists:
                    ref.update({f"players.{player_name}": {"role": None, "is_alive": True}})
                    st.session_state.room_code = room_code
                    st.session_state.player_name = player_name
                    st.rerun()

else:
    room_doc = db.collection("rooms").document(st.session_state.room_code).get()
    if room_doc.exists:
        data = room_doc.to_dict()
        st.write(f"**Oda Kodu:** {st.session_state.room_code}")
        st.write(f"**Oyuncu:** {st.session_state.player_name}")
        st.write("---")
        st.write("### Odadaki Oyuncular:")
        for p in data.get("players", {}):
            st.write(f"- {p}")
