import streamlit as st
import json
from datetime import date
from garminconnect import Garmin
from google import genai

st.set_page_config(page_title="Garmin Tréninkový Generátor", page_icon="⚡")

st.markdown("## ⚡ Garmin & AI Generátor Tréninků")

GARMIN_EMAIL = "jirkadusek1985@gmail.com"

password = st.text_input("Garmin Heslo", type="password")
mfa_code = st.text_input("MFA kód z e-mailu/SMS (vyplň jen pokud ho Garmin dnes vyžaduje)")

sport_volba = st.selectbox(
    "Zvol dnešní sport:",
    ["1: Běh", "2: Kolo", "3: Plavání", "4: Posilování / Síla", "5: Nechat rozhodnout AI"]
)

sport_map = {
    "1: Běh": ("running", "Běh"),
    "2: Kolo": ("cycling", "Kolo"),
    "3: Plavničku": ("swimming", "Plavání"),
    "4: Posilování / Síla": ("strength", "Posilování / Síla"),
    "5: Nechat rozhodnout AI": ("auto", "AI volba")
}

if st.button("🚀 Spustit generování a import do Garminu"):
    if not password:
        st.error("Nejprve zadej heslo k účtu Garmin!")
    else:
        with st.spinner("Zpracovávám požadavek..."):
            try:
                api = Garmin(GARMIN_EMAIL, password)
                
                try:
                    if mfa_code.strip():
                        api.login(mfa_code.strip())
                    else:
                        api.login()
                except Exception as mfa_err:
                    err_str = str(mfa_err).lower()
                    if "mfa" in err_str or "one-time" in err_str or "prompt_mfa" in err_str:
                        st.warning("🔒 Garmin vyžaduje ověřovací kód! Zkontroluj e-mail, zadej kód do políčka 'MFA kód' výše a klikni na tlačítko znovu.")
                        st.stop()
                    else:
                        raise mfa_err

                gemini_api_key = st.secrets["GEMINI_API_KEY"]
                client = genai.Client(api_key=gemini_api_key)
                
                sport_key, sport_nazev = sport_map[sport_volba]
                
                prompt = (
                    f"Jsi špičkový běžecký a triatlonový trenér. Vytvoř strukturovaný trénink pro sport: {sport_nazev}. "
                    "Vrať odpověď výhradně jako čistý JSON objekt (bez markdown bloků jako ```json) s klíči: "
                    "nazev (string), popis (string), steps (seznam kroků)."
                )
                
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=prompt
                )
                
                st.success(f"Tvá dnešní jednotka ({sport_nazev}) je připravena!")
                st.info(f"Odpověď AI: {response.text}")
                
            except Exception as e:
                st.error(f"Chyba při zpracování: {e}")
