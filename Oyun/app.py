import streamlit as st

# Sayfa başlığı ve ikonu
st.set_page_config(page_title="Web Sitem", page_icon="🚀")

# Başlık ve metin
st.title("Hoş Geldiniz!")
st.subheader("Streamlit ile oluşturulmuş basit bir web sitesi.")
st.write("Buraya dilediğiniz metni veya içeriği ekleyebilirsiniz.")

# Etkileşimli elemanlar
name = st.text_input("Adınız nedir?")
if name:
    st.success(f"Merhaba {name}, sitemize hoş geldin!")

# Buton örneği
if st.button("Tıkla"):
    st.balloons()