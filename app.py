import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime, timedelta, date, time
from github import Github
import io

# --- KONFIGURACJA ---
DATA_STARTU_WYJAZDU = date(2026, 7, 24)
DLUGOSC_WYJAZDU_DNI = 14
DNI_W_WIDOKU = 5
NAZWA_PLIKU_BAZY = "data.csv" # Musi być taki sam jak utworzyłeś na GitHubie

st.set_page_config(page_title="Planer Wycieczki 2026", layout="wide")

# --- CSS ---
st.markdown(
    """
    <div style='background-color: #F0F2F6; padding: 1.5rem; border-radius: 10px; text-align: center; margin-bottom: 2rem;'>
        <h1 style='color: #0E1117; margin:0; font-size: 3rem;'>🚗 Zwariowana Przygoda 2026</h1>
        <p style='margin-top: 0.5rem; font-size: 1.2rem; color: #555;'>🐒Wyjazd Czarnuchow🐒</p>
    </div>
    """,
    unsafe_allow_html=True
)

# --- ŁĄCZENIE Z GITHUBEM ---
def init_github():
    try:
        # Pobieramy token z sekretów
        token = st.secrets["github"]["token"]
        repo_name = st.secrets["github"]["repo_name"]
        g = Github(token)
        repo = g.get_repo(repo_name)
        return repo
    except Exception as e:
        st.error(f"Błąd połączenia z GitHub: {e}")
        return None

# Funkcja pobierająca dane
def get_data(repo):
    try:
        # Pobieramy zawartość pliku
        contents = repo.get_contents(NAZWA_PLIKU_BAZY)
        # Dekodujemy zawartość (GitHub trzyma to jako base64)
        csv_content = contents.decoded_content.decode("utf-8")
        
        if not csv_content:
             return pd.DataFrame(columns=['Tytuł', 'Kategoria', 'Czas (h)', 'Start', 'Koniec', 'Zaplanowane'])

        df = pd.read_csv(io.StringIO(csv_content))
        
        # Konwersja dat
        if 'Start' in df.columns:
            df['Start'] = pd.to_datetime(df['Start'], errors='coerce')
        if 'Koniec' in df.columns:
            df['Koniec'] = pd.to_datetime(df['Koniec'], errors='coerce')
            
        return df.fillna("")
    except Exception as e:
        # Jeśli plik nie istnieje lub jest pusty
        return pd.DataFrame(columns=['Tytuł', 'Kategoria', 'Czas (h)', 'Start', 'Koniec', 'Zaplanowane'])

# Funkcja zapisująca dane
def update_data(repo, df):
    try:
        # Pobieramy obecny plik, żeby mieć jego "sha" (wymagane do nadpisania)
        contents = repo.get_contents(NAZWA_PLIKU_BAZY)
        
        # Zamieniamy DataFrame z powrotem na CSV
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        new_content = csv_buffer.getvalue()
        
        # Wysyłamy update na GitHuba
        repo.update_file(contents.path, "Aktualizacja planu przez Aplikację", new_content, contents.sha)
        return True
    except Exception as e:
        st.error(f"Błąd zapisu: {e}")
        return False

# Inicjalizacja połączenia
repo = init_github()
if repo:
    if 'db' not in st.session_state:
        st.session_state.db = get_data(repo)
    # Odświeżamy dane przy każdym przeładowaniu, żeby widzieć zmiany innych
    # (Opcjonalnie można to wyłączyć dla szybkości, ale lepiej zostawić dla synchronizacji)
    st.session_state.db = get_data(repo)
else:
    st.stop() # Zatrzymujemy apkę jeśli nie ma połączenia

# --- FUNKCJE POMOCNICZE (SIATKA) ---
def przygotuj_dane_do_siatki(df):
    grid_data = []
    # Konwersja kolumny na string dla bezpieczeństwa
    zaplanowane = df[df['Zaplanowane'].astype(str).str.upper() == 'TRUE']
    
    for _, row in zaplanowane.iterrows():
        if pd.isna(row['Start']) or row['Start'] == "": continue
        
        start = row['Start']
        # Czasami pandas wczyta to jako string, upewniamy się że to liczba
        czas_h = int(float(row['Czas (h)']))
        zakres_godzin = pd.date_range(start=start, periods=czas_h, freq='h')
        
        for i, godzina_bloku in enumerate(zakres_godzin):
            label = row['Tytuł'] if i == 0 else "" 
            grid_data.append({
                'DataFull': godzina_bloku.date(),
                'Dzień': godzina_bloku.strftime('%d.%m'),
                'Godzina': godzina_bloku.hour,
                'Tytuł_Display': label,
                'Tytuł_Full': row['Tytuł'],
                'Kategoria': row['Kategoria']
            })
    return pd.DataFrame(grid_data)

def generuj_tlo_widoku(start_date, num_days):
    tlo_data = []
    for d in range(num_days):
        current_day = start_date + timedelta(days=d)
        for h in range(24):
            tlo_data.append({
                'Dzień': current_day.strftime('%d.%m'),
                'Godzina': h,
                'Tytuł_Display': '',
                'Kategoria': 'Tło'
            })
    return pd.DataFrame(tlo_data)

# --- INTERFEJS ---
tab_edytor, tab_kalendarz = st.tabs(["📝 Edytor", "📅 Kalendarz Wyjazdu"])

# ==========================================
# ZAKŁADKA 1: EDYTOR
# ==========================================
with tab_edytor:
    col_a, col_b = st.columns([1, 2])
    with col_a:
        st.subheader("Dodaj nowy element")
        with st.form("dodawanie_form", clear_on_submit=True):
            tytul = st.text_input("Tytuł")
            kat = st.selectbox("Kategoria", ["Atrakcja", "Trasa", "Odpoczynek"]) 
            czas = st.number_input("Czas (h)", min_value=1.0, step=1.0, value=1.0) 
            submit = st.form_submit_button("Zapisz", type="primary")

        if submit and tytul:
            with st.spinner("Wysyłam na serwer..."):
                nowy = pd.DataFrame([{
                    'Tytuł': tytul, 'Kategoria': kat, 'Czas (h)': float(czas), 
                    'Start': None, 'Koniec': None, 'Zaplanowane': False
                }])
                updated_df = pd.concat([st.session_state.db, nowy], ignore_index=True)
                if update_data(repo, updated_df):
                    st.success(f"Dodano '{tytul}'!")
                    st.rerun()

    with col_b:
        st.subheader("📦 Giełda pomysłów")
        
        # Filtrujemy
        niezaplanowane_mask = st.session_state.db['Zaplanowane'].astype(str).str.upper() != 'TRUE'
        do_pokazania = st.session_state.db[niezaplanowane_mask]
        
        if not do_pokazania.empty:
            event = st.dataframe(
                do_pokazania[['Tytuł', 'Kategoria', 'Czas (h)']], 
                use_container_width=True, 
                on_select="rerun", 
                selection_mode="multi-row",
                hide_index=True
            )
            
            if event.selection.rows:
                if st.button("🗑️ Usuń zaznaczone trwale", type="primary"):
                    with st.spinner("Usuwam..."):
                        indeksy_do_usuniecia = do_pokazania.iloc[event.selection.rows].index
                        updated_df = st.session_state.db.drop(indeksy_do_usuniecia).reset_index(drop=True)
                        if update_data(repo, updated_df):
                            st.rerun()
        else:
            st.info("Baza pomysłów jest pusta.")

# ==========================================
# ZAKŁADKA 2: KALENDARZ
# ==========================================
with tab_kalendarz:
    col_wykres, col_narzedzia = st.columns([3, 1])

    with col_wykres:
        offset_dni = st.slider(
            "Przewiń dni wyjazdu:", 
            min_value=0, max_value=DLUGOSC_WYJAZDU_DNI - DNI_W_WIDOKU, value=0,
            format="Dzień +%d"
        )
        data_poczatek = DATA_STARTU_WYJAZDU + timedelta(days=offset_dni)
        data_koniec = data_poczatek + timedelta(days=DNI_W_WIDOKU)

    with col_narzedzia:
        st.markdown("### 📌 Przybornik")
        niezaplanowane_mask = st.session_state.db['Zaplanowane'].astype(str).str.upper() != 'TRUE'
        niezaplanowane = st.session_state.db[niezaplanowane_mask]
        
        if not niezaplanowane.empty:
            opcje = niezaplanowane['Tytuł'].tolist()
            wybrany = st.selectbox("Wybierz klocek:", opcje)
            info = niezaplanowane[niezaplanowane['Tytuł'] == wybrany].iloc[0]
            
            st.info(f"⏳ **{int(float(info['Czas (h)']))}h** | {info['Kategoria']}")
            
            wybrana_data = st.date_input("Dzień:", value=data_poczatek, 
                                         min_value=DATA_STARTU_WYJAZDU, 
                                         max_value=DATA_STARTU_WYJAZDU + timedelta(days=DLUGOSC_WYJAZDU_DNI))
            wybrana_godzina = st.selectbox("Start:", list(range(24)), format_func=lambda x: f"{x:02d}:00", index=10)
            
            if st.button("⬅️ ZAPISZ PLAN", type="primary", use_container_width=True):
                with st.spinner("Aktualizuję plan..."):
                    start_dt = datetime.combine(wybrana_data, time(wybrana_godzina, 0))
                    end_dt = start_dt + timedelta(hours=float(info['Czas (h)']))
                    
                    idx = st.session_state.db[st.session_state.db['Tytuł'] == wybrany].index[0]
                    st.session_state.db.at[idx, 'Start'] = start_dt
                    st.session_state.db.at[idx, 'Koniec'] = end_dt
                    st.session_state.db.at[idx, 'Zaplanowane'] = True
                    
                    if update_data(repo, st.session_state.db):
                        st.success("Zapisano!")
                        st.rerun()
        else:
            st.success("Wszystko zaplanowane!")
            
        st.divider()
        zaplanowane_mask = st.session_state.db['Zaplanowane'].astype(str).str.upper() == 'TRUE'
        zaplanowane = st.session_state.db[zaplanowane_mask]
        
        if not zaplanowane.empty:
            do_zdjecia = st.selectbox("Edytuj plan:", zaplanowane['Tytuł'].tolist())
            if st.button("↩️ Zdejmij z kalendarza", use_container_width=True):
                with st.spinner("Zdejmuję..."):
                    idx = st.session_state.db[st.session_state.db['Tytuł'] == do_zdjecia].index[0]
                    st.session_state.db.at[idx, 'Zaplanowane'] = False
                    st.session_state.db.at[idx, 'Start'] = None
                    if update_data(repo, st.session_state.db):
                        st.rerun()

    with col_wykres:
        full_df = przygotuj_dane_do_siatki(st.session_state.db)
        if not full_df.empty:
            mask = (full_df['DataFull'] >= data_poczatek) & (full_df['DataFull'] < data_koniec)
            view_df = full_df.loc[mask].copy()
        else:
            view_df = pd.DataFrame()

        background_df = generuj_tlo_widoku(data_poczatek, DNI_W_WIDOKU)
        domain = ["Atrakcja", "Trasa", "Odpoczynek", "Tło"]
        range_colors = ["#66BB6A", "#42A5F5", "#FFEE58", "#FFFFFF"] 

        base = alt.Chart(background_df).encode(
            x=alt.X('Dzień:O', axis=alt.Axis(labelAngle=0, title=None, labelFontSize=12)),
            y=alt.Y('Godzina:O', scale=alt.Scale(domain=list(range(24))), axis=alt.Axis(title=None))
        )
        layer_bg = base.mark_rect(stroke='lightgray', strokeWidth=1).encode(color=alt.value('white'))

        if not view_df.empty:
            chart_data = alt.Chart(view_df).encode(
                x=alt.X('Dzień:O'),
                y=alt.Y('Godzina:O'),
                tooltip=['Tytuł_Full', 'Kategoria', 'Godzina']
            )
            layer_rects = chart_data.mark_rect(stroke='white', strokeWidth=0.5).encode(
                color=alt.Color('Kategoria', scale=alt.Scale(domain=domain, range=range_colors), legend=None)
            )
            layer_text = chart_data.mark_text(dx=5, align='left', baseline='middle', fontSize=11, fontWeight='bold').encode(
                text=alt.Text('Tytuł_Display'), color=alt.value('#333333')
            )
            final_chart = (layer_bg + layer_rects + layer_text).properties(height=700)
        else:
            final_chart = layer_bg.properties(height=700)

        st.altair_chart(final_chart, use_container_width=True)
