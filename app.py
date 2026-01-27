import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime, timedelta, date, time
from github import Github, Auth
import io
import json
import base64

# --- TWOJA NOWA PALETA (RETRO DARK) ---
COLOR_BG = "#1e2630"        # Gunmetal (Ciemne Tło)
COLOR_TEXT = "#faf9dd"      # Cream (Jasny Tekst)
COLOR_ACCENT = "#d37759"    # Terracotta (Główny Akcent - Atrakcje/Przyciski)
COLOR_SEC = "#4a7a96"       # Muted Blue (Drugorzędny - Trasa/Nagłówek) - dodany dla kontrastu

# --- KONFIGURACJA DOMYŚLNA ---
DEFAULT_CONFIG = {
    "start_date": "2026-07-24",
    "days": 14,
    "people": 12
}

SZEROKOSC_KOLUMNY_DZIEN = 100 
NAZWA_PLIKU_BAZY = "data.csv"
NAZWA_PLIKU_CONFIG = "config.json"

st.set_page_config(page_title="Planer Wycieczki 2026", layout="wide")

# --- FUNKCJA POMOCNICZA DO OBRAZKÓW BASE64 ---
def image_to_base64(image_path):
    """Wczytuje obrazek i konwertuje go na ciąg base64."""
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode('utf-8')
    except FileNotFoundError:
        return None # Zwróć None, jeśli plik nie istnieje
        
# --- CSS (CLEAN APP MODE - BEZ PASKÓW STREAMLIT) ---
st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;700&display=swap');

    /* 1. TYPOGRAFIA */
    html, body {{
        font-family: 'Montserrat', sans-serif;
    }}
    h1, h2, h3, p, div, span {{
        font-family: 'Montserrat', sans-serif;
    }}
    h1, h2, h3 {{
        font-weight: 700 !important;
    }}

    /* 2. UKRYWANIE ELEMENTÓW INTERFEJSU STREAMLIT (KIOSK MODE) */
    
    /* Ukrywa górny pasek (Hamburger menu, Deploy button, kolorowy pasek) */
    header {{
        visibility: hidden;
    }}
    
    /* Ukrywa stopkę "Made with Streamlit" */
    footer {{
        visibility: hidden;
    }}
    
    /* Ukrywa Twój awatar i ikonę "Viewer" na dole po prawej */
    .viewerBadge_container__1QSob {{
        display: none !important;
    }}
    [data-testid="stStatusWidget"] {{
        display: none !important;
    }}
    
    /* Ukrywa menu z trzema kropkami (jeśli header nie wystarczy) */
    #MainMenu {{
        visibility: hidden;
    }}

    /* 3. POPRAWKI UKŁADU */
    
    /* Zmniejszamy odstęp na górze, skoro nie ma paska narzędzi */
    .block-container {{
        padding-top: 1rem !important;
    }}

    /* Checkboxy */
    div[data-testid="stCheckbox"] {{ margin-bottom: -10px; }}
    
    /* Przyciski - Ceglasty Akcent */
    div.stButton > button:first-child {{ 
        height: 3em; 
        margin-top: 1.5em; 
        background-color: {COLOR_ACCENT}; 
        color: {COLOR_TEXT}; 
        border: none;
        font-weight: bold;
        border-radius: 8px;
    }}
    div.stButton > button:first-child:hover {{
        background-color: #b06045; 
        color: {COLOR_TEXT};
    }}
    
    /* Duże Liczby (Metrics) */
    [data-testid="stMetricValue"] {{ 
        font-size: 3rem; 
        color: {COLOR_ACCENT}; 
        font-weight: 700;
    }}
    
    /* Zakładki */
    .stTabs [aria-selected="true"] {{
        color: {COLOR_ACCENT} !important;
        border-bottom-color: {COLOR_ACCENT} !important;
    }}
    </style>
    """,
    unsafe_allow_html=True
)

# --- GITHUB & OBSŁUGA DANYCH ---
def init_github():
    try:
        token = st.secrets["github"]["token"]
        repo_name = st.secrets["github"]["repo_name"]
        auth = Auth.Token(token)
        g = Github(auth=auth) 
        repo = g.get_repo(repo_name)
        return repo
    except Exception as e:
        st.error(f"Błąd połączenia z GitHub: {e}")
        return None

def get_data(repo):
    try:
        contents = repo.get_contents(NAZWA_PLIKU_BAZY)
        csv_content = contents.decoded_content.decode("utf-8")
        expected_columns = ['Tytuł', 'Kategoria', 'Czas (h)', 'Start', 'Koniec', 'Zaplanowane', 'Koszt', 'Typ_Kosztu']
        
        if not csv_content: return pd.DataFrame(columns=expected_columns)
        
        df = pd.read_csv(io.StringIO(csv_content))
        if 'Start' in df.columns: df['Start'] = pd.to_datetime(df['Start'], errors='coerce')
        if 'Koniec' in df.columns: df['Koniec'] = pd.to_datetime(df['Koniec'], errors='coerce')
        if 'Koszt' not in df.columns: df['Koszt'] = 0.0
        if 'Typ_Kosztu' not in df.columns: df['Typ_Kosztu'] = 'Indywidualny'
            
        return df.fillna("")
    except Exception:
        return pd.DataFrame(columns=['Tytuł', 'Kategoria', 'Czas (h)', 'Start', 'Koniec', 'Zaplanowane', 'Koszt', 'Typ_Kosztu'])

def get_config(repo):
    try:
        contents = repo.get_contents(NAZWA_PLIKU_CONFIG)
        json_content = contents.decoded_content.decode("utf-8")
        config = json.loads(json_content)
        config['start_date'] = datetime.strptime(config['start_date'], "%Y-%m-%d").date()
        return config
    except Exception:
        defaults = DEFAULT_CONFIG.copy()
        defaults['start_date'] = datetime.strptime(defaults['start_date'], "%Y-%m-%d").date()
        return defaults

def update_data(repo, df):
    try:
        contents = repo.get_contents(NAZWA_PLIKU_BAZY)
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        new_content = csv_buffer.getvalue()
        repo.update_file(contents.path, "Update z aplikacji", new_content, contents.sha)
        return True
    except Exception as e:
        st.error(f"Błąd zapisu danych: {e}")
        return False

def update_config(repo, new_config):
    try:
        save_config = new_config.copy()
        save_config['start_date'] = save_config['start_date'].strftime("%Y-%m-%d")
        json_str = json.dumps(save_config, indent=4)
        try:
            contents = repo.get_contents(NAZWA_PLIKU_CONFIG)
            repo.update_file(contents.path, "Update ustawień", json_str, contents.sha)
        except Exception:
            repo.create_file(NAZWA_PLIKU_CONFIG, "Init config", json_str)
        return True
    except Exception as e:
        st.error(f"Błąd zapisu ustawień: {e}")
        return False

# --- INICJALIZACJA ---
repo = init_github()
if repo:
    if 'db' not in st.session_state: st.session_state.db = get_data(repo)
    st.session_state.db = get_data(repo)
    global_config = get_config(repo)
    st.session_state.config_start_date = global_config['start_date']
    st.session_state.config_days = global_config['days']
    st.session_state.config_people = global_config['people']
else: st.stop()

# --- DIALOG USTAWIEŃ ---
@st.dialog("⚙️ Konfiguracja Wyjazdu")
def settings_dialog():
    st.write("Ustawienia globalne")
    c1, c2 = st.columns(2)
    with c1: new_date = st.date_input("Data początkowa:", value=st.session_state.config_start_date)
    with c2: new_days = st.number_input("Długość (dni):", min_value=1, max_value=60, value=st.session_state.config_days)
    st.divider()
    st.write("💰 Rozliczenia")
    new_people = st.number_input("Liczba uczestników:", min_value=1, value=st.session_state.config_people)
    
    if st.button("Zapisz w chmurze", type="primary"):
        with st.spinner("Aktualizuję konfigurację..."):
            new_conf_dict = {"start_date": new_date, "days": new_days, "people": new_people}
            if update_config(repo, new_conf_dict):
                st.session_state.config_start_date = new_date
                st.session_state.config_days = new_days
                st.session_state.config_people = new_people
                st.success("Zapisano!")
                st.rerun()

# --- HEADER (NOWY LOGOTYP BASE64) ---
col_title, col_settings = st.columns([6, 1], vertical_alignment="center")

with col_title:
    # 1. Definicje ikon
    # Ikona GitHub (bez zmian)
    icon_github = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" '
        'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
        'style="vertical-align: middle; margin-bottom: 3px;">'
        '<path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"></path>'
        '</svg>'
    )

    # NOWOŚĆ: Wczytanie Twojego logotypu jako Base64
    logo_base64 = image_to_base64("logo.png")
    
    if logo_base64:
        # Jeśli plik logo.png istnieje, stwórz tag <img>
        # Ustawiamy szerokość na 140px i zachowujemy odbicie lustrzane dla efektu pędu w prawo
        icon_logotype = f'<img src="data:image/png;base64,{logo_base64}" width="140" style="transform: scaleX(-1);">'
    else:
        # Fallback (zapas): jeśli plik nie istnieje, wyświetl stary SVG auta
        icon_logotype = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="80" height="80" viewBox="0 0 24 24" '
            f'fill="{COLOR_ACCENT}" stroke="{COLOR_TEXT}" stroke-width="0.5" stroke-linecap="round" stroke-linejoin="round">'
            '<path d="M14 16H9m10 0h3v-3.15a1 1 0 0 0-.84-.99L16 11l-2.7-3.6a1 1 0 0 0-.8-.4H5.24a2 2 0 0 0-1.8 1.1l-.8 1.63A6 6 0 0 0 2 12v4.5a.5.5 0 0 0 .5.5h1a.5.5 0 0 0 .5-.5V16a1 1 0 0 1 1-1h11a1 1 0 0 1 1 1v.5a.5.5 0 0 0 .5.5h1a.5.5 0 0 0 .5-.5V16a1 1 0 0 0-1-1h-1Z"/>'
            f'<circle cx="6.5" cy="16.5" r="2.5" fill="{COLOR_ACCENT}" stroke="none"/>'
            f'<circle cx="16.5" cy="16.5" r="2.5" fill="{COLOR_ACCENT}" stroke="none"/>'
            '</svg>'
        )

    # 2. Budowa HTML
    header_html = (
        f'<div style="background-color: {COLOR_SEC}; padding: 2rem; border-radius: 16px; '
        'box-shadow: 0 4px 10px rgba(0,0,0,0.15); display: flex; align-items: center; justify-content: space-between;">'
        
        # LEWA STRONA (TEKST)
        '<div style="flex: 1;">'
        f'<h1 style="color: {COLOR_TEXT}; margin: 0; font-size: 2.8rem; line-height: 1.1; letter-spacing: -1px; text-transform: uppercase; font-weight: 700;">'
        f'ZWARIOWANA<br>PRZYGODA <span style="color:{COLOR_ACCENT}">2026</span>'
        '</h1>'
        f'<p style="margin: 5px 0 0 0; font-size: 1.1rem; color: {COLOR_TEXT}; opacity: 0.9; font-weight: 400; letter-spacing: 3px; text-transform: uppercase;">PLANNER WYJAZDOWY</p>'
        f'<div style="height: 4px; width: 60px; background-color: {COLOR_ACCENT}; margin: 20px 0 15px 0; border-radius: 2px;"></div>'
        f'<p style="margin: 0; font-size: 0.9rem; color: {COLOR_TEXT}; opacity: 0.7; font-family: monospace; display: flex; align-items: center; gap: 8px;">{icon_github} Baza danych: GitHub Repository</p>'
        '</div>'
        
        # PRAWA STRONA (LOGOTYP)
        # Usuwamy dodatkowy div z margin-left i transform, bo są już w samym tagu <img>
        f'<div style="flex: 0 0 auto; margin-left: 20px;">{icon_logotype}</div>'
        
        '</div>'
    )

    st.markdown(header_html, unsafe_allow_html=True)

with col_settings:
    st.write("") # Pusty odstęp dla wyrównania
    if st.button("⚙️", use_container_width=True):
        settings_dialog()
        
st.divider()

# --- HELPERY ---
def przygotuj_dane_do_siatki(df):
    grid_data = []
    mask = (df['Zaplanowane'].astype(str).str.upper() == 'TRUE') & (df['Typ_Kosztu'] == 'Indywidualny')
    zaplanowane = df[mask]
    for _, row in zaplanowane.iterrows():
        if pd.isna(row['Start']) or row['Start'] == "": continue
        start = row['Start']
        czas_h = int(float(row['Czas (h)']))
        zakres_godzin = pd.date_range(start=start, periods=czas_h, freq='h')
        for i, godzina_bloku in enumerate(zakres_godzin):
            label = row['Tytuł'] if i == 0 else "" 
            grid_data.append({
                'DataFull': godzina_bloku,
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
                'DataFull': current_day,
                'Dzień': current_day.strftime('%d.%m'),
                'Godzina': h,
                'Tytuł_Display': '',
                'Kategoria': 'Tło'
            })
    return pd.DataFrame(tlo_data)

# --- ZAKŁADKI ---
tab_edytor, tab_kalendarz, tab_wspolne, tab_podsumowanie = st.tabs([
    "📝 Edytor i Giełda", 
    "📅 Kalendarz", 
    "💸 Koszty Wspólne", 
    "💰 Podsumowanie"
])

# ==========================================
# ZAKŁADKA 1: EDYTOR
# ==========================================
with tab_edytor:
    col_a, col_b = st.columns([1, 2])
    with col_a:
        st.subheader("Dodaj atrakcję (Indywidualne)")
        with st.form("dodawanie_form", clear_on_submit=True):
            tytul = st.text_input("Tytuł")
            kat = st.selectbox("Kategoria", ["Atrakcja", "Trasa", "Odpoczynek"]) 
            c1, c2 = st.columns(2)
            with c1: czas = st.number_input("Czas (h)", min_value=1.0, step=1.0, value=1.0) 
            with c2: koszt = st.number_input("Koszt (PLN)", min_value=0.0, step=10.0, value=0.0)
            submit = st.form_submit_button("Zapisz", type="primary")

        if submit and tytul:
            with st.spinner("Zapisuję..."):
                nowy = pd.DataFrame([{
                    'Tytuł': tytul, 'Kategoria': kat, 'Czas (h)': float(czas), 
                    'Start': None, 'Koniec': None, 'Zaplanowane': False,
                    'Koszt': float(koszt), 'Typ_Kosztu': 'Indywidualny' 
                }])
                updated_df = pd.concat([st.session_state.db, nowy], ignore_index=True)
                if update_data(repo, updated_df): st.success(f"Dodano '{tytul}'!"); st.rerun()

    with col_b:
        st.subheader("📦 Giełda pomysłów")
        mask_niezaplanowane = (st.session_state.db['Zaplanowane'].astype(str).str.upper() != 'TRUE') & \
                              (st.session_state.db['Typ_Kosztu'] == 'Indywidualny')
        do_pokazania = st.session_state.db[mask_niezaplanowane]
        if not do_pokazania.empty:
            event = st.dataframe(
                do_pokazania[['Tytuł', 'Kategoria', 'Czas (h)', 'Koszt']], 
                use_container_width=True, on_select="rerun", selection_mode="multi-row", hide_index=True
            )
            if event.selection.rows:
                if st.button("🗑️ Usuń zaznaczone trwale", type="primary"):
                    with st.spinner("Usuwam..."):
                        indeksy = do_pokazania.iloc[event.selection.rows].index
                        updated_df = st.session_state.db.drop(indeksy).reset_index(drop=True)
                        if update_data(repo, updated_df): st.rerun()
        else: st.info("Brak elementów.")

# ==========================================
# ZAKŁADKA 2: KALENDARZ (HYBRYDOWY: DESKTOP & MOBILE)
# ==========================================
with tab_kalendarz:
    # 1. Przełącznik Widoku
    col_switch, _ = st.columns([1, 4])
    with col_switch:
        mobile_mode = st.toggle("📱 Widok Mobilny (Lista)", value=False)

    # 2. Logika Danych
    current_start_date = st.session_state.config_start_date
    current_days = st.session_state.config_days
    
    # Pobieramy tylko zaplanowane i posortowane chronologicznie
    mask_zap = (st.session_state.db['Zaplanowane'].astype(str).str.upper() == 'TRUE') & \
               (st.session_state.db['Typ_Kosztu'] == 'Indywidualny')
    df_events = st.session_state.db[mask_zap].copy()
    
    if not df_events.empty:
        df_events['Start'] = pd.to_datetime(df_events['Start'])
        df_events = df_events.sort_values(by='Start')

    # --- WIDOK MOBILNY (AGENDA) ---
    if mobile_mode:
        if df_events.empty:
            st.info("Nic jeszcze nie zaplanowano.")
        else:
            # Grupujemy wydarzenia po dniach
            df_events['Date_Only'] = df_events['Start'].dt.date
            unique_dates = sorted(df_events['Date_Only'].unique())

            for day in unique_dates:
                # Nagłówek Dnia
                day_str = day.strftime('%d.%m (%A)')
                # Tłumaczenie dni tygodnia (opcjonalne)
                day_map = {'Monday': 'Poniedziałek', 'Tuesday': 'Wtorek', 'Wednesday': 'Środa', 'Thursday': 'Czwartek', 'Friday': 'Piątek', 'Saturday': 'Sobota', 'Sunday': 'Niedziela'}
                day_name = day.strftime('%A')
                day_display = f"{day.strftime('%d.%m')} • {day_map.get(day_name, day_name)}"
                
                st.markdown(f"#### 🗓️ {day_display}")
                
                daily_items = df_events[df_events['Date_Only'] == day]
                
                for _, row in daily_items.iterrows():
                    # Przygotowanie danych do karty
                    start_time = row['Start'].strftime('%H:%M')
                    end_time = (row['Start'] + timedelta(hours=float(row['Czas (h)']))).strftime('%H:%M')
                    title = row['Tytuł']
                    cat = row['Kategoria']
                    cost = row['Koszt'] if row['Koszt'] > 0 else ""
                    cost_badge = f"<span style='float:right; font-weight:bold;'>{cost:.0f} zł</span>" if cost else ""
                    
                    # Kolorowanie kart w zależności od kategorii
                    if cat == "Atrakcja":
                        bg_color = COLOR_ACCENT # Ceglasty
                        text_color = COLOR_BG   # Ciemny tekst
                    elif cat == "Trasa":
                        bg_color = COLOR_SEC    # Morski
                        text_color = COLOR_TEXT # Jasny tekst
                    else:
                        bg_color = "#444"       # Szary dla reszty
                        text_color = "#fff"

                    # HTML Karty (Mobile Friendly)
                    card_html = f"""
                    <div style="
                        background-color: {bg_color};
                        color: {text_color};
                        padding: 12px 16px;
                        border-radius: 10px;
                        margin-bottom: 8px;
                        box-shadow: 0 2px 4px rgba(0,0,0,0.2);
                        border-left: 5px solid rgba(0,0,0,0.2);
                    ">
                        <div style="font-size: 0.85rem; opacity: 0.8; display: flex; justify-content: space-between;">
                            <span>⏱️ {start_time} - {end_time} ({int(row['Czas (h)'])}h)</span>
                            {cost_badge}
                        </div>
                        <div style="font-size: 1.1rem; font-weight: 700; margin-top: 4px;">
                            {title}
                        </div>
                        <div style="font-size: 0.8rem; opacity: 0.7; margin-top: 2px; text-transform: uppercase; letter-spacing: 1px;">
                            {cat}
                        </div>
                    </div>
                    """
                    st.markdown(card_html, unsafe_allow_html=True)
                
                st.write("") # Odstęp między dniami

    # --- WIDOK DESKTOP (ALTAIR) ---
    else:
        background_df = generuj_tlo_widoku(current_start_date, current_days)
        full_df = przygotuj_dane_do_siatki(st.session_state.db)
        
        domain = ["Atrakcja", "Trasa", "Odpoczynek", "Tło"]
        range_colors = [COLOR_ACCENT, COLOR_SEC, COLOR_TEXT, COLOR_BG] 
        
        total_width = current_days * SZEROKOSC_KOLUMNY_DZIEN

        st.markdown("""<style>[data-testid="stAltairChart"] {overflow-x: auto; padding-bottom: 10px;}</style>""", unsafe_allow_html=True)
        
        base = alt.Chart(background_df).encode(
            x=alt.X('Dzień:O', sort=alt.EncodingSortField(field="DataFull", order="ascending"), 
                    axis=alt.Axis(labelAngle=0, title=None, labelFontSize=11, labelColor=COLOR_TEXT)),
            y=alt.Y('Godzina:O', scale=alt.Scale(domain=list(range(24))), axis=alt.Axis(title=None, labelColor=COLOR_TEXT))
        )
        layer_bg = base.mark_rect(stroke='gray', strokeWidth=0.2).encode(color=alt.value(COLOR_BG), tooltip=['Dzień', 'Godzina'])

        if not full_df.empty:
            chart_data = alt.Chart(full_df).encode(
                x=alt.X('Dzień:O', sort=alt.EncodingSortField(field="DataFull", order="ascending")),
                y=alt.Y('Godzina:O'),
                tooltip=['Tytuł_Full', 'Kategoria', 'Godzina', 'Dzień']
            )
            layer_rects = chart_data.mark_rect(stroke=COLOR_BG, strokeWidth=1).encode(
                color=alt.Color('Kategoria', scale=alt.Scale(domain=domain, range=range_colors), legend=None)
            )
            
            # POPRAWIONE ETYKIETY (BOLD + LEFT ALIGN)
            layer_text = chart_data.mark_text(
                dx=-42,                 
                align='left',           
                baseline='middle',
                fontSize=11,            
                fontWeight='bold',      
                limit=SZEROKOSC_KOLUMNY_DZIEN-10
            ).encode(
                text=alt.Text('Tytuł_Display'),
                color=alt.value(COLOR_BG) 
            )
            final_chart = (layer_bg + layer_rects + layer_text).properties(height=600, width=total_width)
        else:
            final_chart = layer_bg.properties(height=600, width=total_width)

        st.altair_chart(final_chart)
        
    st.divider()

    # --- PRZYBORNIK (WSPÓLNY DLA OBU WIDOKÓW) ---
    col_tools_left, col_tools_right = st.columns([1, 1])
    with col_tools_left:
        st.subheader("📌 Przybornik")
        # (Reszta kodu przybornika bez zmian...)
        c1, c2, c3 = st.columns(3)
        filtry = []
        if c1.checkbox("Atrakcja", value=True): filtry.append("Atrakcja")
        if c2.checkbox("Trasa", value=True): filtry.append("Trasa")
        if c3.checkbox("Odpoczynek", value=True): filtry.append("Odpoczynek")

        mask_przyb = (st.session_state.db['Zaplanowane'].astype(str).str.upper() != 'TRUE') & \
                     (st.session_state.db['Typ_Kosztu'] == 'Indywidualny')
        niezaplanowane = st.session_state.db[mask_przyb]
        if not niezaplanowane.empty:
            filtrowane_df = niezaplanowane[niezaplanowane['Kategoria'].isin(filtry)]
            if not filtrowane_df.empty:
                opcje = filtrowane_df['Tytuł'].tolist()
                wybrany = st.selectbox("Wybierz element:", opcje)
                info = filtrowane_df[filtrowane_df['Tytuł'] == wybrany].iloc[0]
                st.caption(f"Czas: **{int(float(info['Czas (h)']))}h** | Koszt: **{info.get('Koszt', 0)} PLN**")
                cd, ch = st.columns(2)
                with cd: wybrana_data = st.date_input("Dzień:", value=current_start_date, min_value=current_start_date, max_value=current_start_date + timedelta(days=current_days))
                with ch: wybrana_godzina = st.selectbox("Start:", list(range(24)), format_func=lambda x: f"{x:02d}:00", index=10)
                if st.button("⬅️ WRZUĆ NA PLAN", type="primary", use_container_width=True):
                    with st.spinner("Aktualizuję..."):
                        start_dt = datetime.combine(wybrana_data, time(wybrana_godzina, 0))
                        idx = st.session_state.db[st.session_state.db['Tytuł'] == wybrany].index[0]
                        st.session_state.db.at[idx, 'Start'] = start_dt
                        st.session_state.db.at[idx, 'Koniec'] = start_dt + timedelta(hours=float(info['Czas (h)']))
                        st.session_state.db.at[idx, 'Zaplanowane'] = True
                        if update_data(repo, st.session_state.db): st.success("Zapisano!"); st.rerun()
            else: st.warning("Brak elementów.")
        else: st.success("Pusto!")

    with col_tools_right:
        st.subheader("🗑️ Zdejmowanie")
        # (Reszta kodu zdejmowania bez zmian...)
        mask_zap = (st.session_state.db['Zaplanowane'].astype(str).str.upper() == 'TRUE') & \
                   (st.session_state.db['Typ_Kosztu'] == 'Indywidualny')
        zaplanowane = st.session_state.db[mask_zap]
        if not zaplanowane.empty:
            zaplanowane_sorted = zaplanowane.sort_values(by='Start')
            opcje = zaplanowane_sorted.apply(lambda x: f"{x['Tytuł']} ({x['Start'].strftime('%d.%m %H:%M')})", axis=1).tolist()
            wybrany_op = st.selectbox("Element:", opcje)
            if wybrany_op:
                orig_tytul = zaplanowane_sorted.iloc[opcje.index(wybrany_op)]['Tytuł']
                if st.button("↩️ Wróć do poczekalni", use_container_width=True):
                    with st.spinner("Zdejmuję..."):
                        idx = st.session_state.db[st.session_state.db['Tytuł'] == orig_tytul].index[0]
                        st.session_state.db.at[idx, 'Zaplanowane'] = False
                        st.session_state.db.at[idx, 'Start'] = None
                        if update_data(repo, st.session_state.db): st.rerun()
        else: st.info("Kalendarz pusty.")

# ==========================================
# ZAKŁADKA 3: KOSZTY WSPÓLNE
# ==========================================
with tab_wspolne:
    col_fixed, col_fuel = st.columns(2)
    with col_fixed:
        st.markdown("### 🏨 Noclegi i Opłaty")
        with st.form("form_wspolne", clear_on_submit=True):
            nazwa = st.text_input("Nazwa (np. Oli House, Winiety)")
            kategoria_wsp = st.selectbox("Rodzaj", ["Nocleg", "Wynajem Busa", "Winiety", "Inne"])
            koszt_calosc = st.number_input("Łączny koszt (PLN)", min_value=0.0, step=100.0)
            if st.form_submit_button("Dodaj do wspólnych"):
                if nazwa and koszt_calosc > 0:
                    nowy = pd.DataFrame([{
                        'Tytuł': nazwa, 'Kategoria': kategoria_wsp, 'Czas (h)': 0, 
                        'Start': None, 'Koniec': None, 'Zaplanowane': False,
                        'Koszt': float(koszt_calosc), 'Typ_Kosztu': 'Wspólny'
                    }])
                    updated_df = pd.concat([st.session_state.db, nowy], ignore_index=True)
                    if update_data(repo, updated_df): st.success(f"Dodano {nazwa}!"); st.rerun()

    with col_fuel:
        st.markdown("### ⛽ Kalkulator Trasy")
        with st.container(border=True):
            auto_nazwa = st.text_input("Auto (np. BMW, Bus)", value="BMW")
            dystans = st.number_input("Dystans (km)", min_value=0, value=3400, step=10)
            spalanie = st.slider("Spalanie (l/100km)", 1.0, 20.0, 6.0, step=0.1)
            cena_paliwa = st.slider("Cena paliwa (PLN/l)", 3.0, 10.0, 6.0, step=0.01)
            koszt_trasy = (dystans / 100) * spalanie * cena_paliwa
            st.markdown(f"**Szacowany koszt:** :red[{koszt_trasy:.2f} PLN]")
            if st.button("➕ Dodaj auto do rozliczenia"):
                tytul_auta = f"Paliwo: {auto_nazwa} ({dystans}km)"
                nowy = pd.DataFrame([{
                    'Tytuł': tytul_auta, 'Kategoria': 'Trasa', 'Czas (h)': 0, 
                    'Start': None, 'Koniec': None, 'Zaplanowane': False,
                    'Koszt': float(koszt_trasy), 'Typ_Kosztu': 'Paliwo'
                }])
                updated_df = pd.concat([st.session_state.db, nowy], ignore_index=True)
                if update_data(repo, updated_df): st.success(f"Dodano {auto_nazwa}!"); st.rerun()

    st.divider()
    st.markdown("### 📋 Lista dodanych kosztów wspólnych")
    mask_wspolne = st.session_state.db['Typ_Kosztu'].isin(['Wspólny', 'Paliwo'])
    df_wspolne = st.session_state.db[mask_wspolne]
    if not df_wspolne.empty:
        event = st.dataframe(
            df_wspolne[['Tytuł', 'Kategoria', 'Typ_Kosztu', 'Koszt']],
            use_container_width=True, hide_index=True,
            selection_mode="multi-row", on_select="rerun",
            column_config={"Koszt": st.column_config.NumberColumn("Koszt Całkowity", format="%.2f zł")}
        )
        if event.selection.rows:
            if st.button("🗑️ Usuń wybrane koszty wspólne", type="primary"):
                 with st.spinner("Usuwam..."):
                    indeksy = df_wspolne.iloc[event.selection.rows].index
                    updated_df = st.session_state.db.drop(indeksy).reset_index(drop=True)
                    if update_data(repo, updated_df): st.rerun()
    else: st.info("Jeszcze nie dodałeś żadnych wspólnych wydatków.")

# ==========================================
# ZAKŁADKA 4: PODSUMOWANIE (NOWE KOLORY)
# ==========================================
with tab_podsumowanie:
    st.subheader("💰 Wielkie Podsumowanie Wyjazdu")
    
    mask_A = (st.session_state.db['Zaplanowane'].astype(str).str.upper() == 'TRUE') & \
             (st.session_state.db['Typ_Kosztu'] == 'Indywidualny')
    df_A = st.session_state.db[mask_A].copy()
    df_A['Koszt'] = pd.to_numeric(df_A['Koszt'], errors='coerce').fillna(0)
    sum_A = df_A['Koszt'].sum()

    mask_B = st.session_state.db['Typ_Kosztu'].isin(['Wspólny', 'Paliwo'])
    df_B = st.session_state.db[mask_B].copy()
    df_B['Koszt'] = pd.to_numeric(df_B['Koszt'], errors='coerce').fillna(0)
    sum_B_total = df_B['Koszt'].sum()

    liczba_osob = st.session_state.config_people
    sum_B_per_person = sum_B_total / liczba_osob
    grand_total = sum_A + sum_B_per_person

    kpi1, kpi2, kpi3 = st.columns(3)
    with kpi1: st.metric(label="Twoje łączne koszty", value=f"{grand_total:.2f} PLN")
    with kpi2: st.metric(label="Tylko atrakcje (Kalendarz)", value=f"{sum_A:.2f} PLN", delta="Indywidualne")
    with kpi3: st.metric(label="Zrzutka (Noclegi/Paliwo)", value=f"{sum_B_per_person:.2f} PLN", 
                         delta=f"Całość: {sum_B_total:.0f} zł / {liczba_osob} os.", delta_color="off")
    st.divider()

    col_left, col_right = st.columns([1, 2])
    with col_left:
        st.markdown("##### 🍰 Struktura kosztów (Twoja działka)")
        pie_data = [{'Kategoria': 'Atrakcje', 'Wartość': sum_A}]
        if not df_B.empty:
            grouped_B = df_B.groupby('Kategoria')['Koszt'].sum().reset_index()
            for _, row in grouped_B.iterrows():
                pie_data.append({'Kategoria': row['Kategoria'], 'Wartość': row['Koszt'] / liczba_osob})
        
        df_pie = pd.DataFrame(pie_data)
        df_pie = df_pie[df_pie['Wartość'] > 0]

        if not df_pie.empty:
            total_pie = df_pie['Wartość'].sum()
            df_pie['Procent'] = df_pie['Wartość'] / total_pie
            
            # Paleta: Cegła, Zgaszony Morski, Krem, Szary
            pie_scale = alt.Scale(range=[COLOR_ACCENT, COLOR_SEC, COLOR_TEXT, "gray"])
            
            base_pie = alt.Chart(df_pie).encode(theta=alt.Theta(field="Wartość", type="quantitative", stack=True))
            pie = base_pie.mark_arc(innerRadius=50).encode(
                color=alt.Color(field="Kategoria", type="nominal", scale=pie_scale, legend=alt.Legend(orient="bottom", labelColor=COLOR_TEXT)),
                tooltip=['Kategoria', alt.Tooltip('Wartość', format='.2f'), alt.Tooltip('Procent', format='.1%')]
            )
            # Białe etykiety dla czytelności na ciemnym tle
            text = base_pie.mark_text(radius=120, size=14).encode(
                text=alt.Text("Procent", format=".0%"), order=alt.Order("Kategoria"),
                color=alt.value(COLOR_TEXT) 
            )
            st.altair_chart(pie + text, use_container_width=True)
        else: st.caption("Brak danych.")

        st.markdown("##### 🧾 Twoje atrakcje")
        if not df_A.empty:
            tabela = df_A[df_A['Koszt'] > 0][['Tytuł', 'Koszt']].sort_values(by='Koszt', ascending=False)
            st.dataframe(tabela, use_container_width=True, hide_index=True, height=200, 
                         column_config={"Koszt": st.column_config.NumberColumn(format="%.2f zł")})
        else: st.info("Brak płatnych atrakcji.")

    with col_right:
        st.markdown("##### 📅 Kiedy portfel zaboli najbardziej?")
        if not df_A.empty:
            df_A['Data_Group'] = df_A['Start'].dt.date
            daily_costs = df_A.groupby('Data_Group')['Koszt'].sum().reset_index()
            daily_costs['Etykieta'] = daily_costs['Data_Group'].apply(lambda x: x.strftime('%d.%m'))
            daily_costs['Sort_Key'] = daily_costs['Data_Group'].astype(str)
            
            base_bar = alt.Chart(daily_costs).encode(
                x=alt.X('Etykieta:O', title='Dzień', sort=alt.EncodingSortField(field="Sort_Key", order="ascending"), 
                        axis=alt.Axis(labelAngle=0, labelColor=COLOR_TEXT, titleColor=COLOR_TEXT)),
                y=alt.Y('Koszt:Q', title='Suma (PLN)', axis=alt.Axis(labelColor=COLOR_TEXT, titleColor=COLOR_TEXT))
            )
            # Słupki w kolorze Ceglastym
            bars = base_bar.mark_bar(color=COLOR_ACCENT, cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
                tooltip=[alt.Tooltip('Etykieta', title='Dzień'), alt.Tooltip('Koszt', format='.2f', title='Kwota')]
            )
            text_bar = base_bar.mark_text(align='center', baseline='bottom', dy=-5, size=12).encode(
                text=alt.Text('Koszt:Q', format='.0f'),
                color=alt.value(COLOR_TEXT)
            )
            st.altair_chart((bars + text_bar).properties(height=550), use_container_width=True)
        else: st.info("Zaplanuj płatne atrakcje w kalendarzu, aby zobaczyć wykres czasu.")

