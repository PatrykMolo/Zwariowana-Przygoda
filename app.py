import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime, timedelta, date, time
from github import Github, Auth, GithubException
import io
import json
import base64
import uuid

# ==========================================
# 🎨 PALETA KOLORÓW (RETRO DARK)
# ==========================================
COLOR_BG = "#1e2630"        # Gunmetal (Tło)
COLOR_TEXT = "#faf9dd"      # Cream (Tekst)
COLOR_ACCENT = "#d37759"    # Terracotta (Akcent: Przyciski, Atrakcje)
COLOR_SEC = "#4a7a96"       # Muted Blue (Drugorzędny: Nagłówek, Trasa)
# Dodatkowe kolory do wykresów:
COLOR_EXTRA_1 = "#7c8c58"   # Olive Drab
COLOR_EXTRA_2 = "#8c5e7c"   # Muted Plum

# ==========================================
# ⚙️ KONFIGURACJA PLIKÓW
# ==========================================
REGISTRY_FILE = "registry.json"
DEFAULT_TRIP_ID = "default"
SZEROKOSC_KOLUMNY_DZIEN = 100

st.set_page_config(page_title="Planer Wycieczki", layout="wide")

# ==========================================
# 💅 CSS & STYLIZACJA (KIOSK MODE + FONT)
# ==========================================
st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;700&display=swap');

    /* 1. TYPOGRAFIA */
    html, body, h1, h2, h3, p, div, span {{ font-family: 'Montserrat', sans-serif; }}
    h1, h2, h3 {{ font-weight: 700 !important; }}

    /* 2. UKRYWANIE ELEMENTÓW STREAMLIT */
    header {{ visibility: hidden; }}
    footer {{ visibility: hidden; }}
    .viewerBadge_container__1QSob {{ display: none !important; }}
    [data-testid="stStatusWidget"] {{ display: none !important; }}
    #MainMenu {{ visibility: hidden; }}

    /* 3. POPRAWKI UKŁADU */
    .block-container {{ padding-top: 1rem !important; }}
    div[data-testid="stCheckbox"] {{ margin-bottom: -10px; }}
    
    /* Przyciski */
    div.stButton > button:first-child {{ 
        height: 3em; margin-top: 1.5em; 
        background-color: {COLOR_ACCENT}; color: {COLOR_TEXT}; 
        border: none; font-weight: bold; border-radius: 8px;
    }}
    div.stButton > button:first-child:hover {{
        background-color: #b06045; color: {COLOR_TEXT};
    }}
    
    /* Duże Liczby (Metrics) */
    [data-testid="stMetricValue"] {{ 
        font-size: 3rem; color: {COLOR_ACCENT}; font-weight: 700;
    }}
    
    /* Zakładki */
    .stTabs [aria-selected="true"] {{
        color: {COLOR_ACCENT} !important;
        border-bottom-color: {COLOR_ACCENT} !important;
    }}
    
    /* Ramki kontenerów - delikatne dopasowanie */
    [data-testid="stVerticalBlockBorderWrapper"] > div > div {{
        border-color: rgba(250, 249, 221, 0.2) !important; 
    }}
    </style>
    """,
    unsafe_allow_html=True
)

# ==========================================
# 🔧 GITHUB & FILE SYSTEM 2.0
# ==========================================
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

def image_to_base64(image_path):
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode('utf-8')
    except FileNotFoundError: return None

# --- OBSŁUGA REJESTRU WYPRAW ---
def get_registry(repo):
    try:
        contents = repo.get_contents(REGISTRY_FILE)
        return json.loads(contents.decoded_content.decode("utf-8"))
    except Exception:
        # MIGRACJA
        try:
            old_data = repo.get_contents("data.csv")
            repo.update_file("default_data.csv", "Migracja", old_data.decoded_content, old_data.sha)
            repo.delete_file("data.csv", "Cleanup", old_data.sha)
            try:
                old_conf = repo.get_contents("config.json")
                repo.update_file("default_config.json", "Migracja", old_conf.decoded_content, old_conf.sha)
                repo.delete_file("config.json", "Cleanup", old_conf.sha)
            except: pass
            st.toast("Dokonano migracji bazy!", icon="📦")
        except: pass

        new_registry = {"current": "default", "trips": {"default": "Moja Pierwsza Wyprawa"}}
        repo.create_file(REGISTRY_FILE, "Init Registry", json.dumps(new_registry, indent=4))
        return new_registry

def update_registry(repo, registry_data):
    try:
        contents = repo.get_contents(REGISTRY_FILE)
        repo.update_file(contents.path, "Update Registry", json.dumps(registry_data, indent=4), contents.sha)
        return True
    except Exception as e:
        st.error(f"Błąd zapisu rejestru: {e}")
        return False

# --- POBIERANIE DANYCH ---
def get_trip_files(trip_id):
    return f"{trip_id}_data.csv", f"{trip_id}_config.json"

def get_data(repo, filename):
    try:
        contents = repo.get_contents(filename)
        df = pd.read_csv(io.StringIO(contents.decoded_content.decode("utf-8")))
        if 'Start' in df.columns: df['Start'] = pd.to_datetime(df['Start'], errors='coerce')
        if 'Koniec' in df.columns: df['Koniec'] = pd.to_datetime(df['Koniec'], errors='coerce')
        if 'Koszt' not in df.columns: df['Koszt'] = 0.0
        if 'Typ_Kosztu' not in df.columns: df['Typ_Kosztu'] = 'Indywidualny'
        return df.fillna("")
    except Exception:
        return pd.DataFrame(columns=['Tytuł', 'Kategoria', 'Czas (h)', 'Start', 'Koniec', 'Zaplanowane', 'Koszt', 'Typ_Kosztu'])

def get_config(repo, filename):
    default_conf = {"trip_name": "Nowa Wyprawa", "start_date": "2026-06-01", "days": 7, "people": 1}
    try:
        contents = repo.get_contents(filename)
        config = json.loads(contents.decoded_content.decode("utf-8"))
        config['start_date'] = datetime.strptime(config['start_date'], "%Y-%m-%d").date()
        if 'trip_name' not in config: config['trip_name'] = default_conf['trip_name']
        return config
    except Exception:
        default_conf['start_date'] = datetime.strptime(default_conf['start_date'], "%Y-%m-%d").date()
        return default_conf

def update_file(repo, filename, content_str, message="Update"):
    try:
        try:
            contents = repo.get_contents(filename)
            repo.update_file(contents.path, message, content_str, contents.sha)
        except:
            repo.create_file(filename, message, content_str)
        return True
    except Exception as e:
        st.error(f"Błąd zapisu pliku {filename}: {e}")
        return False

def delete_trip_files(repo, trip_id):
    f_data, f_conf = get_trip_files(trip_id)
    try: repo.delete_file(f_data, "Delete Data", repo.get_contents(f_data).sha)
    except: pass
    try: repo.delete_file(f_conf, "Delete Config", repo.get_contents(f_conf).sha)
    except: pass

# ==========================================
# 🚀 INICJALIZACJA
# ==========================================
repo = init_github()
if repo:
    # 1. Pobierz rejestr
    registry = get_registry(repo)
    remote_current_id = registry.get("current", "default")
    
    # 2. Logika manualnego przełączenia (Flaga)
    if 'manual_switch_flag' in st.session_state and st.session_state.manual_switch_flag:
        current_id = st.session_state.current_trip_id
        del st.session_state.manual_switch_flag 
    else:
        current_id = remote_current_id

    # 3. Pobierz pliki
    data_file, config_file = get_trip_files(current_id)
    
    if 'current_trip_id' not in st.session_state or st.session_state.current_trip_id != current_id or 'db' not in st.session_state:
        st.session_state.current_trip_id = current_id
        st.session_state.db = get_data(repo, data_file)
        conf = get_config(repo, config_file)
        st.session_state.config_trip_name = conf['trip_name']
        st.session_state.config_start_date = conf['start_date']
        st.session_state.config_days = conf['days']
        st.session_state.config_people = conf['people']
else: st.stop()

# ==========================================
# 📂 DIALOG: MENADŻER ZAPISÓW
# ==========================================
@st.dialog("📂 Menadżer Zapisów")
def save_manager_dialog():
    st.caption("Tutaj możesz przełączać się między różnymi wycieczkami.")
    trips_dict = registry.get("trips", {})
    trip_names = list(trips_dict.values())
    current_name = trips_dict.get(st.session_state.current_trip_id, "Nieznana")
    
    st.info(f"Aktualnie edytujesz: **{current_name}**")
    st.divider()
    
    # 1. PRZEŁĄCZANIE
    st.markdown("#### 🔄 Przełącz wyprawę")
    try: curr_index = trip_names.index(current_name)
    except ValueError: curr_index = 0
    selected_name_switch = st.selectbox("Wybierz z listy:", trip_names, index=curr_index)
    
    if st.button("Załaduj wybraną", type="primary", use_container_width=True):
        found_id = [k for k, v in trips_dict.items() if v == selected_name_switch][0]
        if found_id != st.session_state.current_trip_id:
            with st.spinner("Przełączam bazę danych..."):
                registry['current'] = found_id
                update_registry(repo, registry)
                st.session_state.current_trip_id = found_id
                st.session_state.manual_switch_flag = True
                if 'db' in st.session_state: del st.session_state.db
                st.rerun()

    st.divider()
    # 2. TWORZENIE
    st.markdown("#### ✨ Nowa Wyprawa")
    with st.form("new_trip_form"):
        new_trip_name = st.text_input("Nazwa nowej wyprawy (np. Alpy 2027)")
        if st.form_submit_button("Utwórz pustą bazę"):
            if new_trip_name in trip_names: st.error("Taka nazwa już istnieje!")
            else:
                with st.spinner("Tworzę pliki..."):
                    new_id = str(uuid.uuid4())[:8]
                    registry['trips'][new_id] = new_trip_name
                    registry['current'] = new_id
                    update_registry(repo, registry)
                    
                    new_conf = {"trip_name": new_trip_name, "start_date": "2026-06-01", "days": 7, "people": 1}
                    new_f_data, new_f_conf = get_trip_files(new_id)
                    update_file(repo, new_f_conf, json.dumps(new_conf, indent=4), "Init Config")
                    update_file(repo, new_f_data, "Tytuł,Kategoria,Czas (h),Start,Koniec,Zaplanowane,Koszt,Typ_Kosztu\n", "Init Data")
                    
                    st.session_state.current_trip_id = new_id
                    st.session_state.manual_switch_flag = True
                    if 'db' in st.session_state: del st.session_state.db
                    st.rerun()
    # 3. USUWANIE
    if len(trips_dict) > 1:
        with st.expander("🗑️ Usuwanie"):
            to_del = st.selectbox("Wybierz do usunięcia:", [n for n in trip_names if n != current_name])
            if st.button(f"Usuń trwale: {to_del}"):
                del_id = [k for k, v in trips_dict.items() if v == to_del][0]
                del registry['trips'][del_id]
                update_registry(repo, registry)
                delete_trip_files(repo, del_id)
                st.success("Usunięto."); st.rerun()

# ==========================================
# 🗑️ DIALOG: ODPINANIE
# ==========================================
@st.dialog("🗑️ Odepnij z kalendarza")
def unpin_dialog():
    st.write("Wybierz wydarzenie, które chcesz zdjąć z planu (trafi z powrotem do Edytora).")
    
    mask_zap = (st.session_state.db['Zaplanowane'].astype(str).str.upper() == 'TRUE') & (st.session_state.db['Typ_Kosztu'] == 'Indywidualny')
    zaplanowane = st.session_state.db[mask_zap]
    
    if not zaplanowane.empty:
        zaplanowane_sorted = zaplanowane.sort_values(by='Start')
        opcje = zaplanowane_sorted.apply(lambda x: f"{x['Tytuł']} ({x['Start'].strftime('%d.%m %H:%M')})", axis=1).tolist()
        
        wybrany_op = st.selectbox("Wybierz wydarzenie:", opcje)
        
        if wybrany_op:
            orig_tytul = zaplanowane_sorted.iloc[opcje.index(wybrany_op)]['Tytuł']
            
            st.warning(f"Czy na pewno chcesz odpiąć: **{orig_tytul}**?")
            
            if st.button("Tak, odepnij", type="primary", use_container_width=True):
                with st.spinner("Aktualizuję..."):
                    idx = st.session_state.db[st.session_state.db['Tytuł'] == orig_tytul].index[0]
                    st.session_state.db.at[idx, 'Zaplanowane'] = False
                    st.session_state.db.at[idx, 'Start'] = None
                    csv_buffer = io.StringIO(); st.session_state.db.to_csv(csv_buffer, index=False)
                    update_file(repo, data_file, csv_buffer.getvalue())
                    st.rerun()
    else:
        st.info("Kalendarz jest pusty. Nie ma czego odpinać.")

# ==========================================
# ⚙️ DIALOG KONFIGURACJI
# ==========================================
@st.dialog("⚙️ Konfiguracja Wyjazdu")
def settings_dialog():
    st.write("Edytujesz: " + st.session_state.config_trip_name)
    new_name = st.text_input("Nazwa Wyprawy:", value=st.session_state.config_trip_name)
    c1, c2 = st.columns(2)
    with c1: new_date = st.date_input("Start:", value=st.session_state.config_start_date)
    with c2: new_days = st.number_input("Dni:", min_value=1, max_value=60, value=st.session_state.config_days)
    st.divider()
    new_people = st.number_input("Uczestnicy:", min_value=1, value=st.session_state.config_people)
    
    if st.button("Zapisz zmiany", type="primary"):
        with st.spinner("Zapisuję..."):
            new_conf = {"trip_name": new_name, "start_date": new_date, "days": new_days, "people": new_people}
            registry['trips'][st.session_state.current_trip_id] = new_name
            update_registry(repo, registry)
            _, f_conf = get_trip_files(st.session_state.current_trip_id)
            save_c = new_conf.copy(); save_c['start_date'] = save_c['start_date'].strftime("%Y-%m-%d")
            update_file(repo, f_conf, json.dumps(save_c, indent=4))
            st.session_state.config_trip_name = new_name
            st.session_state.config_start_date = new_date
            st.session_state.config_days = new_days
            st.session_state.config_people = new_people
            st.rerun()

# ==========================================
# 🖼️ HEADER
# ==========================================
col_title, col_settings = st.columns([6, 1]) 
with col_title:
    full_title = st.session_state.config_trip_name
    title_parts = full_title.rsplit(' ', 1)
    title_html = f"{title_parts[0]} <span style='color:{COLOR_ACCENT}'>{title_parts[1]}</span>" if len(title_parts) > 1 else full_title

    icon_github = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle; margin-bottom: 3px;"><path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"></path></svg>'
    
    logo_base64 = image_to_base64("logo.png")
    if logo_base64:
        icon_logotype = f'<img src="data:image/png;base64,{logo_base64}" width="140" style="transform: scaleX(-1);">'
    else:
        icon_logotype = f'<svg xmlns="http://www.w3.org/2000/svg" width="80" height="80" viewBox="0 0 24 24" fill="{COLOR_ACCENT}" stroke="{COLOR_TEXT}" stroke-width="0.5" stroke-linecap="round" stroke-linejoin="round"><path d="M14 16H9m10 0h3v-3.15a1 1 0 0 0-.84-.99L16 11l-2.7-3.6a1 1 0 0 0-.8-.4H5.24a2 2 0 0 0-1.8 1.1l-.8 1.63A6 6 0 0 0 2 12v4.5a.5.5 0 0 0 .5.5h1a.5.5 0 0 0 .5-.5V16a1 1 0 0 1 1-1h11a1 1 0 0 1 1 1v.5a.5.5 0 0 0 .5.5h1a.5.5 0 0 0 .5-.5V16a1 1 0 0 0-1-1h-1Z"/><circle cx="6.5" cy="16.5" r="2.5" fill="{COLOR_ACCENT}" stroke="none"/><circle cx="16.5" cy="16.5" r="2.5" fill="{COLOR_ACCENT}" stroke="none"/></svg>'

    html = ""
    html += f"<div style='background-color: {COLOR_SEC}; padding: 2rem; border-radius: 16px; box-shadow: 0 4px 10px rgba(0,0,0,0.15); display: flex; align-items: center; justify-content: space-between;'>"
    html += "<div style='flex: 1;'>"
    html += f"<h1 style='color: {COLOR_TEXT}; margin: 0; font-size: 2.8rem; line-height: 1.1; letter-spacing: -1px; text-transform: uppercase; font-weight: 700;'>{title_html}</h1>"
    html += f"<p style='margin: 5px 0 0 0; font-size: 1.1rem; color: {COLOR_TEXT}; opacity: 0.9; font-weight: 400; letter-spacing: 3px; text-transform: uppercase;'>PLANNER WYJAZDOWY</p>"
    html += f"<div style='height: 4px; width: 60px; background-color: {COLOR_ACCENT}; margin: 20px 0 15px 0; border-radius: 2px;'></div>"
    html += f"<p style='margin: 0; font-size: 0.9rem; color: {COLOR_TEXT}; opacity: 0.7; font-family: monospace; display: flex; align-items: center; gap: 8px;'>{icon_github} Baza danych: GitHub Repository</p>"
    html += "</div>"
    html += f"<div style='flex: 0 0 auto; margin-left: 20px;'>{icon_logotype}</div>"
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)

with col_settings:
    st.write("") 
    if st.button("📂", use_container_width=True, help="Menadżer Zapisów"):
        save_manager_dialog()
    if st.button("⚙️", use_container_width=True, help="Ustawienia"):
        settings_dialog()

# ==========================================
# 📊 HELPERY
# ==========================================
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
                'DataFull': godzina_bloku, 'Dzień': godzina_bloku.strftime('%d.%m'), 'Godzina': godzina_bloku.hour,
                'Tytuł_Display': label, 'Tytuł_Full': row['Tytuł'], 'Kategoria': row['Kategoria']
            })
    return pd.DataFrame(grid_data)

def generuj_tlo_widoku(start_date, num_days):
    tlo_data = []
    for d in range(num_days):
        current_day = start_date + timedelta(days=d)
        for h in range(24):
            tlo_data.append({
                'DataFull': current_day, 'Dzień': current_day.strftime('%d.%m'), 'Godzina': h, 'Tytuł_Display': '', 'Kategoria': 'Tło'
            })
    return pd.DataFrame(tlo_data)

# ==========================================
# 📑 GŁÓWNE ZAKŁADKI
# ==========================================
tab_edytor, tab_kalendarz, tab_podsumowanie = st.tabs(["📝 Edytor", "📅 Kalendarz", "💰 Podsumowanie"])

# --- TAB 1: EDYTOR (SCALONY + SUWAKI PALIWA) ---
with tab_edytor:
    # Przełącznik trybu na górze
    editor_mode = st.radio(
        "Tryb edycji:", 
        ["🏃 Aktywności (Indywidualne)", "💸 Koszty Wspólne / Paliwo"], 
        horizontal=True,
        label_visibility="collapsed"
    )
    
    st.write("") # Odstęp

    # === TRYB 1: AKTYWNOŚCI ===
    if editor_mode == "🏃 Aktywności (Indywidualne)":
        col_a, col_b = st.columns([1, 1.5]) 
        with col_a:
            with st.container(border=True):
                st.subheader("➕ Dodaj aktywność")
                with st.form("dodawanie_form", clear_on_submit=True):
                    tytul = st.text_input("Tytuł")
                    # ZMIANA: Usunięto "Trasa" z listy
                    kat = st.selectbox("Kategoria", ["Atrakcja", "Odpoczynek"]) 
                    c1, c2 = st.columns(2)
                    with c1: czas = st.number_input("Czas (h)", min_value=1.0, step=1.0, value=1.0) 
                    with c2: koszt = st.number_input("Koszt (PLN)", min_value=0.0, step=10.0, value=0.0)
                    submit = st.form_submit_button("Zapisz", type="primary", use_container_width=True)

            if submit and tytul:
                with st.spinner("Zapisuję..."):
                    nowy = pd.DataFrame([{
                        'Tytuł': tytul, 'Kategoria': kat, 'Czas (h)': float(czas), 
                        'Start': None, 'Koniec': None, 'Zaplanowane': False,
                        'Koszt': float(koszt), 'Typ_Kosztu': 'Indywidualny' 
                    }])
                    updated_df = pd.concat([st.session_state.db, nowy], ignore_index=True)
                    csv_buffer = io.StringIO()
                    updated_df.to_csv(csv_buffer, index=False)
                    update_file(repo, data_file, csv_buffer.getvalue())
                    st.session_state.db = updated_df
                    st.success(f"Dodano '{tytul}'!"); st.rerun()

        with col_b:
            with st.container(border=True):
                st.subheader("📦 Giełda pomysłów (Poczekalnia)")
                mask_niezaplanowane = (st.session_state.db['Zaplanowane'].astype(str).str.upper() != 'TRUE') & \
                                      (st.session_state.db['Typ_Kosztu'] == 'Indywidualny')
                do_pokazania = st.session_state.db[mask_niezaplanowane]
                
                if not do_pokazania.empty:
                    event = st.dataframe(
                        do_pokazania[['Tytuł', 'Kategoria', 'Czas (h)', 'Koszt']], 
                        use_container_width=True, on_select="rerun", selection_mode="multi-row", hide_index=True
                    )
                    if event.selection.rows:
                        if st.button("🗑️ Usuń zaznaczone trwale", type="primary", use_container_width=True):
                            with st.spinner("Usuwam..."):
                                indeksy = do_pokazania.iloc[event.selection.rows].index
                                updated_df = st.session_state.db.drop(indeksy).reset_index(drop=True)
                                csv_buffer = io.StringIO(); updated_df.to_csv(csv_buffer, index=False)
                                update_file(repo, data_file, csv_buffer.getvalue())
                                st.session_state.db = updated_df
                                st.rerun()
                else: st.info("Brak nieprzypisanych elementów. Dodaj coś po lewej!")

    # === TRYB 2: KOSZTY WSPÓLNE ===
    else:
        col_form, col_table = st.columns([1, 1.5])
        
        # LEWA KOLUMNA: FORMULARZ (ZINTEGROWANY)
        with col_form:
            with st.container(border=True):
                st.subheader("➕ Dodaj koszt wspólny")
                
                # Wybór pod-typu wewnątrz formularza
                typ_kosztu_input = st.selectbox("Co dodajesz?", ["Wydatek (Nocleg/Inne)", "Paliwo (Trasa)"])
                st.divider()

                # --- FORMULARZ DLA WYDATKÓW (Nocleg, Inne) ---
                if typ_kosztu_input == "Wydatek (Nocleg/Inne)":
                    with st.form("form_wspolne_general", clear_on_submit=True):
                        nazwa = st.text_input("Nazwa (np. Willa, Winiety)")
                        c_kat_w, c_koszt_w = st.columns(2)
                        with c_kat_w: kategoria_wsp = st.selectbox("Kategoria", ["Nocleg", "Wynajem Busa", "Winiety", "Inne"])
                        with c_koszt_w: koszt_calosc = st.number_input("Koszt (PLN)", min_value=0.0, step=100.0)
                        
                        submitted = st.form_submit_button("Dodaj Wydatek", type="primary", use_container_width=True)
                        if submitted and nazwa and koszt_calosc > 0:
                            nowy = pd.DataFrame([{
                                'Tytuł': nazwa, 'Kategoria': kategoria_wsp, 'Czas (h)': 0, 
                                'Start': None, 'Koniec': None, 'Zaplanowane': False, 
                                'Koszt': float(koszt_calosc), 'Typ_Kosztu': 'Wspólny'
                            }])
                            updated_df = pd.concat([st.session_state.db, nowy], ignore_index=True)
                            csv_buffer = io.StringIO(); updated_df.to_csv(csv_buffer, index=False)
                            update_file(repo, data_file, csv_buffer.getvalue())
                            st.session_state.db = updated_df
                            st.success(f"Dodano {nazwa}!"); st.rerun()

                # --- FORMULARZ DLA PALIWA (Z SUWAKAMI) ---
                else: 
                    # Zwykły kontener (bez st.form), żeby suwaki działały interaktywnie
                    auto_nazwa = st.text_input("Samochód", value="Auto 1")
                    dystans = st.number_input("Dystans (km)", min_value=0, value=100, step=10)
                    
                    spalanie = st.slider("Spalanie (l/100km)", 1.0, 20.0, 8.0, step=0.1)
                    cena_paliwa = st.slider("Cena paliwa (PLN/l)", 3.0, 10.0, 6.50, step=0.01)
                    
                    koszt_trasy = (dystans / 100) * spalanie * cena_paliwa
                    st.markdown(f"**Wyliczony koszt:** :red[{koszt_trasy:.2f} PLN]")
                    
                    if st.button("Dodaj Paliwo", type="primary", use_container_width=True):
                        tytul_auta = f"Paliwo: {auto_nazwa} ({dystans}km)"
                        nowy = pd.DataFrame([{
                            'Tytuł': tytul_auta, 'Kategoria': 'Trasa', 'Czas (h)': 0, 
                            'Start': None, 'Koniec': None, 'Zaplanowane': False, 
                            'Koszt': float(koszt_trasy), 'Typ_Kosztu': 'Paliwo'
                        }])
                        updated_df = pd.concat([st.session_state.db, nowy], ignore_index=True)
                        csv_buffer = io.StringIO(); updated_df.to_csv(csv_buffer, index=False)
                        update_file(repo, data_file, csv_buffer.getvalue())
                        st.session_state.db = updated_df
                        st.success(f"Dodano {auto_nazwa}!"); st.rerun()

        # PRAWA KOLUMNA: TABELA
        with col_table:
            with st.container(border=True):
                st.subheader("📋 Baza kosztów wspólnych")
                mask_wspolne = st.session_state.db['Typ_Kosztu'].isin(['Wspólny', 'Paliwo'])
                df_wspolne = st.session_state.db[mask_wspolne]
                
                if not df_wspolne.empty:
                    cols_to_show = ['Tytuł', 'Kategoria', 'Koszt']
                    
                    event = st.dataframe(
                        df_wspolne[cols_to_show], 
                        use_container_width=True, 
                        hide_index=True, 
                        selection_mode="multi-row", 
                        on_select="rerun", 
                        column_config={"Koszt": st.column_config.NumberColumn("Koszt Całkowity", format="%.2f zł")}
                    )
                    if event.selection.rows:
                        if st.button("🗑️ Usuń wybrane koszty", type="primary", use_container_width=True):
                             with st.spinner("Usuwam..."):
                                indeksy = df_wspolne.iloc[event.selection.rows].index
                                updated_df = st.session_state.db.drop(indeksy).reset_index(drop=True)
                                csv_buffer = io.StringIO(); updated_df.to_csv(csv_buffer, index=False)
                                update_file(repo, data_file, csv_buffer.getvalue())
                                st.session_state.db = updated_df
                                st.rerun()
                else: st.info("Brak kosztów wspólnych.")

# --- TAB 2: KALENDARZ (HYBRID) ---
with tab_kalendarz:
    # GÓRNA BELKA (TOGGLE + PRZYCISK ODPINANIA)
    col_switch, col_gap, col_btn = st.columns([2, 5, 2])
    
    with col_switch:
        mobile_mode = st.toggle("📱 Widok Mobilny", value=False)
    
    with col_btn:
        if st.button("🗑️ Odepnij", use_container_width=True):
            unpin_dialog()
            
    # LOGIKA KALENDARZA
    current_start_date = st.session_state.config_start_date
    current_days = st.session_state.config_days
    mask_zap = (st.session_state.db['Zaplanowane'].astype(str).str.upper() == 'TRUE') & (st.session_state.db['Typ_Kosztu'] == 'Indywidualny')
    df_events = st.session_state.db[mask_zap].copy()
    if not df_events.empty:
        df_events['Start'] = pd.to_datetime(df_events['Start'])
        df_events = df_events.sort_values(by='Start')
        
    # --- EKSPORT ICS ---
    def create_ics_file(df):
        ics_content = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//ZwariowanaPrzygoda//PL", "CALSCALE:GREGORIAN", "METHOD:PUBLISH"]
        mask = (df['Zaplanowane'].astype(str).str.upper() == 'TRUE') & (df['Typ_Kosztu'] == 'Indywidualny')
        events = df[mask]
        for _, row in events.iterrows():
            if pd.isna(row['Start']) or row['Start'] == "": continue
            start_dt = row['Start'].strftime('%Y%m%dT%H%M%S')
            end_dt = (row['Start'] + timedelta(hours=float(row['Czas (h)']))).strftime('%Y%m%dT%H%M%S')
            try: koszt_opis = f"Koszt: {float(row['Koszt']):.0f} PLN"
            except: koszt_opis = ""
            opis = f"{row['Kategoria']} \\n{koszt_opis}"
            ics_content.append("BEGIN:VEVENT")
            ics_content.append(f"SUMMARY:{row['Tytuł']}")
            ics_content.append(f"DTSTART:{start_dt}")
            ics_content.append(f"DTEND:{end_dt}")
            ics_content.append(f"DESCRIPTION:{opis}")
            ics_content.append(f"STATUS:CONFIRMED")
            ics_content.append("END:VEVENT")
        ics_content.append("END:VCALENDAR")
        return "\n".join(ics_content)

    if not df_events.empty:
        ics_data = create_ics_file(st.session_state.db)
        safe_name = st.session_state.config_trip_name.replace(" ", "_").lower()
        st.download_button("📅 Pobierz do Kalendarza", data=ics_data, file_name=f"{safe_name}.ics", mime="text/calendar", use_container_width=True)
        st.divider()

    if mobile_mode:
        if df_events.empty: st.info("Nic jeszcze nie zaplanowano.")
        else:
            df_events['Date_Only'] = df_events['Start'].dt.date
            for day in sorted(df_events['Date_Only'].unique()):
                day_map = {'Monday': 'Poniedziałek', 'Tuesday': 'Wtorek', 'Wednesday': 'Środa', 'Thursday': 'Czwartek', 'Friday': 'Piątek', 'Saturday': 'Sobota', 'Sunday': 'Niedziela'}
                day_name = day.strftime('%A'); day_pl = day_map.get(day_name, day_name)
                st.markdown(f"#### 🗓️ {day.strftime('%d.%m')} • {day_pl}")
                daily_items = df_events[df_events['Date_Only'] == day]
                for _, row in daily_items.iterrows():
                    start_time = row['Start'].strftime('%H:%M'); end_time = (row['Start'] + timedelta(hours=float(row['Czas (h)']))).strftime('%H:%M')
                    duration = int(row['Czas (h)']); title = row['Tytuł']; cat = row['Kategoria']
                    try: cost_val = float(row['Koszt'])
                    except: cost_val = 0.0
                    cost_badge = f"<span style='float:right; font-weight:bold; background-color:rgba(255,255,255,0.2); padding: 2px 6px; border-radius:4px;'>{cost_val:.0f} zł</span>" if cost_val > 0 else ""
                    
                    if cat == "Atrakcja": bg_color = COLOR_ACCENT; text_color = "#faf9dd"
                    elif cat == "Trasa": bg_color = COLOR_SEC; text_color = "#ffffff"
                    else: bg_color = "#444444"; text_color = "#dddddd"

                    card_html = ""
                    card_html += f"<div style='background-color: {bg_color}; color: {text_color}; padding: 15px; border-radius: 12px; margin-bottom: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.15); border-left: 6px solid rgba(0,0,0,0.2);'>"
                    card_html += f"<div style='font-size: 0.9rem; opacity: 0.9; margin-bottom: 4px; display: flow-root;'><span>⏱️ {start_time} - {end_time} ({duration}h)</span>{cost_badge}</div>"
                    card_html += f"<div style='font-size: 1.2rem; font-weight: 700; line-height: 1.2; margin-bottom: 4px;'>{title}</div>"
                    card_html += f"<div style='font-size: 0.75rem; opacity: 0.7; text-transform: uppercase; letter-spacing: 1px;'>{cat}</div>"
                    card_html += "</div>"
                    st.markdown(card_html, unsafe_allow_html=True)
                st.write("")
    else:
        background_df = generuj_tlo_widoku(current_start_date, current_days)
        full_df = przygotuj_dane_do_siatki(st.session_state.db)
        domain = ["Atrakcja", "Trasa", "Odpoczynek", "Tło"]; range_colors = [COLOR_ACCENT, COLOR_SEC, COLOR_TEXT, COLOR_BG] 
        total_width = current_days * SZEROKOSC_KOLUMNY_DZIEN
        st.markdown("""<style>[data-testid="stAltairChart"] {overflow-x: auto; padding-bottom: 10px;}</style>""", unsafe_allow_html=True)
        base = alt.Chart(background_df).encode(x=alt.X('Dzień:O', sort=alt.EncodingSortField(field="DataFull", order="ascending"), axis=alt.Axis(labelAngle=0, title=None, labelFontSize=11, labelColor=COLOR_TEXT)), y=alt.Y('Godzina:O', scale=alt.Scale(domain=list(range(24))), axis=alt.Axis(title=None, labelColor=COLOR_TEXT)))
        layer_bg = base.mark_rect(stroke='gray', strokeWidth=0.2).encode(color=alt.value(COLOR_BG), tooltip=['Dzień', 'Godzina'])
        if not full_df.empty:
            chart_data = alt.Chart(full_df).encode(x=alt.X('Dzień:O', sort=alt.EncodingSortField(field="DataFull", order="ascending")), y=alt.Y('Godzina:O'), tooltip=['Tytuł_Full', 'Kategoria', 'Godzina', 'Dzień'])
            layer_rects = chart_data.mark_rect(stroke=COLOR_BG, strokeWidth=1).encode(color=alt.Color('Kategoria', scale=alt.Scale(domain=domain, range=range_colors), legend=None))
            layer_text = chart_data.mark_text(dx=-42, align='left', baseline='middle', fontSize=11, fontWeight='bold', limit=SZEROKOSC_KOLUMNY_DZIEN-10).encode(text=alt.Text('Tytuł_Display'), color=alt.value(COLOR_BG))
            final_chart = (layer_bg + layer_rects + layer_text).properties(height=600, width=total_width)
        else: final_chart = layer_bg.properties(height=600, width=total_width)
        st.altair_chart(final_chart)
    
    st.divider()

    # --- DOLNA SEKCJA (PRZYBORNIK + NOWA SZYBKA TRASA) ---
    col_toolbox, col_route = st.columns(2)

    # 1. PRZYBORNIK (LEWO)
    with col_toolbox:
        with st.container(border=True):
            st.subheader("📌 Przybornik")
            c1, c2, c3 = st.columns(3)
            filtry = []
            if c1.checkbox("Atrakcja", value=True): filtry.append("Atrakcja")
            if c2.checkbox("Trasa", value=True): filtry.append("Trasa")
            if c3.checkbox("Odpoczynek", value=True): filtry.append("Odpoczynek")
            mask_przyb = (st.session_state.db['Zaplanowane'].astype(str).str.upper() != 'TRUE') & (st.session_state.db['Typ_Kosztu'] == 'Indywidualny')
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
                            csv_buffer = io.StringIO(); st.session_state.db.to_csv(csv_buffer, index=False)
                            update_file(repo, data_file, csv_buffer.getvalue())
                            st.success("Zapisano!"); st.rerun()
                else: st.warning("Brak elementów.")
            else: st.success("Pusto!")

    # 2. SZYBKA TRASA (PRAWO)
    with col_route:
        with st.container(border=True):
            st.subheader("🚗 Dodaj Trasę")
            
            r_tytul = st.text_input("Tytuł trasy (np. Dojazd do Włoch)")
            
            c_r_data, c_r_godz = st.columns(2)
            with c_r_data: r_data = st.date_input("Kiedy:", value=current_start_date, min_value=current_start_date, max_value=current_start_date + timedelta(days=current_days), key="route_date")
            with c_r_godz: r_godz = st.selectbox("O której:", list(range(24)), format_func=lambda x: f"{x:02d}:00", index=8, key="route_hour")
            
            r_czas = st.number_input("Czas trwania (h):", min_value=1.0, step=0.5, value=2.0)
            
            if st.button("Dodaj trasę na mapę", type="primary", use_container_width=True):
                if r_tytul:
                    with st.spinner("Dodaję trasę..."):
                        start_dt = datetime.combine(r_data, time(r_godz, 0))
                        
                        # Tworzymy nowy wpis od razu jako ZAPLANOWANY
                        nowa_trasa = pd.DataFrame([{
                            'Tytuł': r_tytul, 
                            'Kategoria': 'Trasa', 
                            'Czas (h)': float(r_czas), 
                            'Start': start_dt, 
                            'Koniec': start_dt + timedelta(hours=float(r_czas)), 
                            'Zaplanowane': True,
                            'Koszt': 0.0, 
                            'Typ_Kosztu': 'Indywidualny' 
                        }])
                        
                        updated_df = pd.concat([st.session_state.db, nowa_trasa], ignore_index=True)
                        csv_buffer = io.StringIO(); updated_df.to_csv(csv_buffer, index=False)
                        update_file(repo, data_file, csv_buffer.getvalue())
                        st.session_state.db = updated_df
                        st.success(f"Dodano trasę: {r_tytul}"); st.rerun()
                else:
                    st.error("Wpisz tytuł trasy!")

# --- TAB 4: PODSUMOWANIE ---
with tab_podsumowanie:
    with st.container(border=True):
        st.subheader("Podsumowanie Wyjazdu")
        mask_A = (st.session_state.db['Zaplanowane'].astype(str).str.upper() == 'TRUE') & (st.session_state.db['Typ_Kosztu'] == 'Indywidualny')
        df_A = st.session_state.db[mask_A].copy(); df_A['Koszt'] = pd.to_numeric(df_A['Koszt'], errors='coerce').fillna(0); sum_A = df_A['Koszt'].sum()
        mask_B = st.session_state.db['Typ_Kosztu'].isin(['Wspólny', 'Paliwo'])
        df_B = st.session_state.db[mask_B].copy(); df_B['Koszt'] = pd.to_numeric(df_B['Koszt'], errors='coerce').fillna(0); sum_B_total = df_B['Koszt'].sum()
        liczba_osob = st.session_state.config_people; sum_B_per_person = sum_B_total / liczba_osob; grand_total = sum_A + sum_B_per_person

        kpi1, kpi2, kpi3 = st.columns(3)
        with kpi1: st.metric(label="Twoje łączne koszty", value=f"{grand_total:.0f} PLN")
        with kpi2: st.metric(label="Koszty aktywności", value=f"{sum_A:.0f} PLN", delta="Indywidualne")
        with kpi3: st.metric(label="Koszty Bazowe", value=f"{sum_B_per_person:.0f} PLN", delta=f"Całość: {sum_B_total:.0f} zł", delta_color="off")
    
    st.divider()

    col_left, col_right = st.columns([1, 2])
    with col_left:
        with st.container(border=True):
            st.markdown("#### Struktura kosztów")
            pie_data = [{'Kategoria': 'Atrakcje', 'Wartość': sum_A}]
            if not df_B.empty:
                grouped_B = df_B.groupby('Kategoria')['Koszt'].sum().reset_index()
                for _, row in grouped_B.iterrows(): pie_data.append({'Kategoria': row['Kategoria'], 'Wartość': row['Koszt'] / liczba_osob})
            df_pie = pd.DataFrame(pie_data); df_pie = df_pie[df_pie['Wartość'] > 0]
            if not df_pie.empty:
                df_pie['Procent'] = df_pie['Wartość'] / df_pie['Wartość'].sum()
                
                # Paleta z nowymi kolorami
                pie_scale = alt.Scale(range=[COLOR_ACCENT, COLOR_SEC, COLOR_EXTRA_1, COLOR_EXTRA_2, COLOR_TEXT, "gray"])
                
                # Baza wykresu
                base = alt.Chart(df_pie).encode(
                    theta=alt.Theta("Wartość", stack=True)
                )
                
                # 1. Warstwa Wycinków (Donut)
                pie = base.mark_arc(innerRadius=50).encode(
                    color=alt.Color("Kategoria", scale=pie_scale, legend=alt.Legend(orient="bottom", labelColor=COLOR_TEXT)),
                    order=alt.Order("Kategoria"), # Ważne dla kolejności
                    tooltip=['Kategoria', alt.Tooltip('Wartość', format='.2f')]
                )
                
                # 2. Warstwa Tła Etykiet (Trick: Wielka kropka "●")
                labels_bg = base.mark_text(radius=120, size=60).encode(
                    text=alt.value("●"),       # Znak kropki jako tło
                    color=alt.value("#1e2630"), # Ciemne tło 
                    opacity=alt.value(0.6),    # Lekka przezroczystość
                    order=alt.Order("Kategoria")
                )
                
                # 3. Warstwa Etykiet (Właściwe procenty)
                labels_text = base.mark_text(radius=120, size=14, fontWeight="bold").encode(
                    text=alt.Text("Procent", format=".0%"),
                    order=alt.Order("Kategoria"),
                    color=alt.value(COLOR_TEXT) 
                )
                
                st.altair_chart(pie + labels_bg + labels_text, use_container_width=True)
            else: st.caption("Brak danych.")
            
        with st.container(border=True):
            st.markdown("#### 🧾 Twoje atrakcje")
            if not df_A.empty:
                tabela_atrakcji = df_A[df_A['Koszt'] > 0][['Tytuł', 'Koszt']].sort_values(by='Koszt', ascending=False)
                st.dataframe(tabela_atrakcji, use_container_width=True, hide_index=True, height=200, column_config={"Koszt": st.column_config.NumberColumn(format="%.2f zł")})
            else: 
                st.caption("Brak płatnych atrakcji.")

    with col_right:
        with st.container(border=True):
            st.markdown("#### 📅 Wykres wydatków w czasie")
            if not df_A.empty:
                df_A['Data_Group'] = df_A['Start'].dt.date
                daily_costs = df_A.groupby('Data_Group')['Koszt'].sum().reset_index()
                daily_costs['Etykieta'] = daily_costs['Data_Group'].apply(lambda x: x.strftime('%d.%m'))
                daily_costs['Sort_Key'] = daily_costs['Data_Group'].astype(str)
                base_bar = alt.Chart(daily_costs).encode(x=alt.X('Etykieta:O', title='Dzień', sort=alt.EncodingSortField(field="Sort_Key", order="ascending"), axis=alt.Axis(labelAngle=0, labelColor=COLOR_TEXT, titleColor=COLOR_TEXT)), y=alt.Y('Koszt:Q', title='Suma (PLN)', axis=alt.Axis(labelColor=COLOR_TEXT, titleColor=COLOR_TEXT)))
                bars = base_bar.mark_bar(color=COLOR_ACCENT, cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(tooltip=[alt.Tooltip('Etykieta', title='Dzień'), alt.Tooltip('Koszt', format='.2f', title='Kwota')])
                text_bar = base_bar.mark_text(align='center', baseline='bottom', dy=-5, size=12).encode(text=alt.Text('Koszt:Q', format='.0f'), color=alt.value(COLOR_TEXT))
                st.altair_chart((bars + text_bar).properties(height=550), use_container_width=True)
            else: st.info("Zaplanuj płatne atrakcje w kalendarzu, aby zobaczyć wykres czasu.")
