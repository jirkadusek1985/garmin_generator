import streamlit as st
import json
from datetime import date
from garminconnect import Garmin
import garth
from google import genai

# Nastavení vzhledu pro mobil
st.set_page_config(page_title="Garmin Tréninkový Generátor", page_icon="⚡")
st.markdown("## ⚡ Garmin & AI Generátor Tréninků")

# Tvůj e-mail zapsaný natvrdo
GARMIN_EMAIL = "jirkadusek1985@gmail.com"

# Vstupy v rozhraní
password = st.text_input("Garmin Heslo", type="password")
mfa_code = st.text_input("MFA kód z e-mailu/SMS (vyplň jen pokud ho Garmin dnes vyžaduje)", type="default")

sport_volba = st.selectbox(
    "Zvol dnešní sport:",
    ["1: Běh", "2: Kolo", "3: Plavání", "4: Posilování / Síla", "5: Nechat rozhodnout AI"]
)

sport_map = {
    "1: Běh": ("running", "Běh"),
    "2: Kolo": ("cycling", "Kolo"),
    "3: Plavání": ("swimming", "Plavání"),
    "4: Posilování / Síla": ("strength_training", "Posilování"),
    "5: Nechat rozhodnout AI": (None, "Autonomní volba AI")
}
zvoleny_sport_key, zvoleny_sport_nazev = sport_map[sport_volba]

PROFIL_SPORTOVCE = """
Jsem triatlonista (41 let, 190 cm).
- Hmotnost: Aktuálně 98 kg, dlouhodobý cíl je stabilně 94 kg.
- Hlavní cíle: Maximalizace VO2 max, zvýšení FTP na kole.
- Objem: Trénovat můžu 4-5x týdně (preference: 1x bazén, 2x kolo, 2x běh + doplňková síla).
- KOLO: Silniční kolo, FTP 290 Wattů. Z2 vytrvalost a intervaly se musí odvíjet od tohoto FTP.
- BĚH: Prahová hodnota (tepový práh) 170 tepů. Lehký klus Z2 a intervaly stavět s ohledem na tento práh a tempo.
- PLAVÁNÍ: Bazén / open water, technické a vytrvalostní bloky.
- PESTROST TRÉNINKŮ: Vyžaduji maximální pestrost a strukturovanost! Vyhýbej se nudným blokům. Využívej pyramidy, střídání intenzit, over-unders.
- SILOVÝ TRÉNINK: Zaměřený primárně na core, stabilizaci a kompenzaci. Nikdy nedávej sílu v den těžkých intervalů.
"""

if st.button("🚀 Spustit generování a import do Garminu", type="primary"):
    if not password:
        st.error("Zadej prosím heslo do Garminu.")
    else:
        with st.spinner("Připojuji se ke Garminu, stahuji data a volám Gemini..."):
            try:
                # 1. Přihlášení
                if mfa_code:
                    garmin = Garmin(GARMIN_EMAIL, password, prompt_mfa=lambda: mfa_code)
                else:
                    garmin = Garmin(GARMIN_EMAIL, password)
                garmin.login()
                
                # 2. Stažení dat
                dnes = date.today().isoformat()
                hrv = garmin.get_hrv_data(dnes)
                readiness = garmin.get_training_readiness(dnes)
                spanek = garmin.get_sleep_data(dnes)
                aktivity = garmin.get_activities(0, 30)
                
                historie_aktivit = [
                    {
                        "datum": a.get("startTimeLocal"),
                        "typ": a.get("activityType", {}).get("typeKey"),
                        "nazev": a.get("activityName"),
                        "delka_min": round(a.get("duration", 0) / 60),
                        "vzdalenost_km": round(a.get("distance", 0) / 1000, 1),
                        "prumerny_tep": a.get("averageHR")
                    }
                    for a in aktivity
                ]

                kompletni_data = {
                    "dnesni_datum": dnes,
                    "uzivatelem_zvoleny_sport": zvoleny_sport_nazev,
                    "hrv_stav": hrv.get("hrvSummary", {}).get("status") if hrv else "neznámý",
                    "training_readiness_skore": readiness[0].get("score") if readiness else "neznámé",
                    "spanek_skore": spanek.get("dailySleepDTO", {}).get("sleepScores", {}).get("overall", {}).get("value") if spanek else "neznámé",
                    "historie_30_aktivit": historie_aktivit
                }

                # 3. Gemini klíč ze zabezpečených tajemství Streamlitu
                api_key = st.secrets["GEMINI_API_KEY"]
                client = genai.Client(api_key=api_key)

                pokyn_sportu = f"UŽIVATEL SI VÝSLOVNĚ VYBRAL TENTO SPORT NA DNES: {zvoleny_sport_nazev} (klíč je '{zvoleny_sport_key}')." if zvoleny_sport_key else "Zvol sport autonomně podle únavy."

                prompt = f"""
                Jsi elitní triatlonový trenér. Na základě ranních dat, 30denní historie a profilu vytvoř jeden strukturovaný trénink na dnešní den.
                {PROFIL_SPORTOVCE}
                {pokyn_sportu}
                Vrať VÝHRADNĚ validní JSON objekt (bez markdown bloků jako ```json) v přesné struktuře pro Garmin Connect API.
                Zde jsou data z Garminu: {json.dumps(kompletni_data, ensure_ascii=False, default=str)}
                """

                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt
                )

                raw_text = response.text.strip()
                if raw_text.startswith("```"):
                    raw_text = raw_text.split("```")[1]
                    if raw_text.startswith("json"):
                        raw_text = raw_text[4:].strip()

                trenink = json.loads(raw_text)

                # 4. Nahrání do Garminu
                odpoved = garmin.upload_workout(trenink)
                workout_id = odpoved.get("workoutId")

                if workout_id:
                    garmin.client.post("connectapi", f"workout-service/schedule/{workout_id}", json={"date": dnes})
                    st.success(f"✅ Tvůj dnešní trénink („{trenink['workoutName']}“) je připraven a importován v Garminu!")
                    st.info(f"**Zdůvodnění trenéra:** {trenink['description']}")
                else:
                    st.error("Chyba: Trénink se nepodařilo naplánovat.")

            except Exception as e:
                st.error(f"Chyba při zpracování: {str(e)}")
