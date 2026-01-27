import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime, timedelta, date, time
from github import Github, Auth
import io

# --- KONFIGURACJA POCZĄTKOWA ---
DEFAULT_START_DATE = date(2026, 7, 24)
DEFAULT_DAYS = 14
DEFAULT_PEOPLE = 12 
SZEROKOSC_KOLUMNY_DZIEN = 100 
NAZWA_PLIKU_BAZY = "data.csv"

st.set_page_config(page_title="Planer Wycieczki 2026", layout="wide")

# --- INICJALIZACJA STANU ---
if 'config_start_date' not in st.session_state:
    st.session_state.config_start_date = DEFAULT_START_DATE
if 'config_days' not in st.session_state:
    st.session_state.config_days = DEFAULT_DAYS
if 'config_people' not in st.session_state:
    st.session_state.config_people = DEFAULT_PEOPLE

# --- CSS ---
st.markdown(
    """
    <style>
    .block-container { padding-top: 2rem; }
    div[data-testid="stCheckbox"] { margin-bottom: -10px; }
    div.stButton > button:first-child { height: 3em; margin-top: 1.5em; }
    [data-testid="stMetricValue"] { font-size: 3rem; color: #FF4B4B; }
    /* Wyróżnienie sekcji kosztów wspólnych */
    .st-emotion-cache-16txtl3 { padding: 20px; border-radius: 10px; background-color: #f9f9f9; }
    </style>
    """,
    unsafe_allow_html=True
)

# --- GITHUB ---
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
        
        if not csv_content:
             return pd.DataFrame(columns=expected_columns)
        
        df = pd.read_csv(io.StringIO(csv_content))
        
        if 'Start' in df.columns:
            df['Start'] = pd.to_datetime(df['Start'], errors='coerce')
        if 'Koniec' in df.columns:
            df['Koniec'] = pd.to_datetime(df['Koniec'], errors='coerce')
            
        # Migracja
        if 'Koszt' not in df.columns:
            df['Koszt'] = 0.0
        if 'Typ_Kosztu' not in df.columns:
            df['Typ_Kosztu'] = 'Indywidualny'
            
        return df.fillna("")
    except Exception:
        return pd.DataFrame(columns=['Tytuł', 'Kategoria', 'Czas (h)', 'Start', 'Koniec', 'Zaplanowane', 'Koszt', 'Typ_Kosztu'])

def update_data(repo, df):
    try:
        contents = repo.get_contents(NAZWA_PLIKU_BAZY)
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        new_content = csv_buffer.getvalue()
        repo.update_file(contents.path, "Update z aplikacji", new_content, contents.sha)
        return True
    except Exception as e:
        st.error(f"Błąd zapisu: {e}")
        return False

repo = init_github()
if repo:
    if 'db' not in st.session_state:
        st.session_state.db = get_data(repo)
    st.session_state.db = get_data(repo)
else:
    st.stop()

# --- DIALOG USTAWIEŃ ---
@st.dialog("⚙️ Konfiguracja Wyjazdu")
def settings_dialog():
    st.write("Ustawienia globalne")
    c1, c2 = st.columns(2)
    with c1:
        new_date = st.date_input("Data początkowa:", value=st.session_state.config_start_date)
    with c2:
        new_days = st.number_input("Długość (dni):", min_value=1, max_value=60, value=st.session_state.config_days)
    
    st.divider()
    st.write("💰 Rozliczenia")
    new_people = st.number_input("Liczba uczestników (do podziału kosztów stałych):", 
                                 min_value=1, value=st.session_state.config_people)
    
    if st.button("Zapisz", type="primary"):
        st.session_state.config_start_date = new_date
        st.session_state.config_days = new_days
        st.session_state.config_people = new_people
        st.rerun()

# --- HEADER ---
col_title, col_settings = st.columns([6, 1], vertical_alignment="center")
with col_title:
    st.markdown(
        """
        <div style='background-color: #F0F2F6; padding: 1.5rem; border-radius: 10px; text-align: center;'>
            <h1 style='color: #0E1117; margin:0; font-size: 3rem;'>🚗 Zwariowana Przygoda 2026</h1>
            <p style='margin-top: 0.5rem; font-size: 1.2rem; color: #555;'>Baza danych: GitHub Repository 🐙</p>
        </div>
        """,
        unsafe_allow_html=True
    )
with col_settings:
    if st.button("⚙️ Ustawienia", use_container_width=True):
        settings_dialog()

st.divider()

# --- HELPERY ---
def przygotuj_dane_do_siatki(df):
    grid_data = []
    # Tylko Indywidualne wchodzą na siatkę kalendarza
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

# --- ZAKŁADKI (DODANO NOWĄ: KOSZTY WSPÓLNE) ---
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
            with c1:
                czas = st.number_input("Czas (h)", min_value=1.0, step=1.0, value=1.0) 
            with c2:
                koszt = st.number_input("Koszt (PLN)", min_value=0.0, step=10.0, value=0.0)

            submit = st.form_submit_button("Zapisz", type="primary")

        if submit and tytul:
            with st.spinner("Zapisuję..."):
                nowy = pd.DataFrame([{
                    'Tytuł': tytul, 'Kategoria': kat, 'Czas (h)': float(czas), 
                    'Start': None, 'Koniec': None, 'Zaplanowane': False,
                    'Koszt': float(koszt),
                    'Typ_Kosztu': 'Indywidualny' 
                }])
                updated_df = pd.concat([st.session_state.db, nowy], ignore_index=True)
                if update_data(repo, updated_df):
                    st.success(f"Dodano '{tytul}'!")
                    st.rerun()

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
                        if update_data(repo, updated_df):
                            st.rerun()
        else:
            st.info("Brak elementów.")

# ==========================================
# ZAKŁADKA 2: KALENDARZ
# ==========================================
with tab_kalendarz:
    current_start_date = st.session_state.config_start_date
    current_days = st.session_state.config_days

    # --- WYKRES ---
    background_df = generuj_tlo_widoku(current_start_date, current_days)
    full_df = przygotuj_dane_do_siatki(st.session_state.db)
    
    domain = ["Atrakcja", "Trasa", "Odpoczynek", "Tło"]
    range_colors = ["#66BB6A", "#42A5F5", "#FFEE58", "#FFFFFF"] 
    total_width = current_days * SZEROKOSC_KOLUMNY_DZIEN

    st.markdown("""<style>[data-testid="stAltairChart"] {overflow-x: auto; padding-bottom: 10px;}</style>""", unsafe_allow_html=True)

    base = alt.Chart(background_df).encode(
        x=alt.X('Dzień:O', sort=alt.EncodingSortField(field="DataFull", order="ascending"), axis=alt.Axis(labelAngle=0, title=None, labelFontSize=11)),
        y=alt.Y('Godzina:O', scale=alt.Scale(domain=list(range(24))), axis=alt.Axis(title=None))
    )
    layer_bg = base.mark_rect(stroke='lightgray', strokeWidth=1).encode(color=alt.value('white'), tooltip=['Dzień', 'Godzina'])

    if not full_df.empty:
        chart_data = alt.Chart(full_df).encode(
            x=alt.X('Dzień:O', sort=alt.EncodingSortField(field="DataFull", order="ascending")),
            y=alt.Y('Godzina:O'),
            tooltip=['Tytuł_Full', 'Kategoria', 'Godzina', 'Dzień']
        )
        layer_rects = chart_data.mark_rect(stroke='white', strokeWidth=0.5).encode(color=alt.Color('Kategoria', scale=alt.Scale(domain=domain, range=range_colors), legend=None))
        layer_text = chart_data.mark_text(dx=2, align='left', baseline='middle', fontSize=10, limit=SZEROKOSC_KOLUMNY_DZIEN-5).encode(text=alt.Text('Tytuł_Display'), color=alt.value('#333333'))
        final_chart = (layer_bg + layer_rects + layer_text).properties(height=600, width=total_width)
    else:
        final_chart = layer_bg.properties(height=600, width=total_width)

    st.altair_chart(final_chart)
    st.divider()

    # --- STEROWANIE ---
    col_tools_left, col_tools_right = st.columns([1, 1])
    with col_tools_left:
        st.subheader("📌 Przybornik")
        st.write("Filtruj listę:")
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
                with cd:
                    wybrana_data = st.date_input("Dzień:", value=current_start_date, min_value=current_start_date, max_value=current_start_date + timedelta(days=current_days))
                with ch:
                    wybrana_godzina = st.selectbox("Start:", list(range(24)), format_func=lambda x: f"{x:02d}:00", index=10)
                
                if st.button("⬅️ WRZUĆ NA PLAN", type="primary", use_container_width=True):
                    with st.spinner("Aktualizuję..."):
                        start_dt = datetime.combine(wybrana_data, time(wybrana_godzina, 0))
                        idx = st.session_state.db[st.session_state.db['Tytuł'] == wybrany].index[0]
                        st.session_state.db.at[idx, 'Start'] = start_dt
                        st.session_state.db.at[idx, 'Koniec'] = start_dt + timedelta(hours=float(info['Czas (h)']))
                        st.session_state.db.at[idx, 'Zaplanowane'] = True
                        if update_data(repo, st.session_state.db):
                            st.success("Zapisano!"); st.rerun()
            else: st.warning("Brak elementów.")
        else: st.success("Pusto!")

    with col_tools_right:
        st.subheader("🗑️ Zdejmowanie")
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
# ZAKŁADKA 3: KOSZTY WSPÓLNE (NOWA!)
# ==========================================
with tab_wspolne:
    col_fixed, col_fuel = st.columns(2)
    
    # --- LEWA: KOSZTY STAŁE ---
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
                        'Koszt': float(koszt_calosc),
                        'Typ_Kosztu': 'Wspólny' # Oznaczamy jako wspólny
                    }])
                    updated_df = pd.concat([st.session_state.db, nowy], ignore_index=True)
                    if update_data(repo, updated_df):
                        st.success(f"Dodano {nazwa}!")
                        st.rerun()
                else:
                    st.error("Wpisz nazwę i kwotę.")

    # --- PRAWA: KALKULATOR PALIWA ---
    with col_fuel:
        st.markdown("### ⛽ Kalkulator Trasy")
        with st.container(border=True):
            auto_nazwa = st.text_input("Auto (np. BMW, Bus)", value="BMW")
            dystans = st.slider("Dystans (km)", 0, 6000, 3400, step=50)
            spalanie = st.slider("Spalanie (l/100km)", 1.0, 20.0, 6.0, step=0.5)
            cena_paliwa = st.slider("Cena paliwa (PLN/l)", 3.0, 10.0, 6.0, step=0.1)
            
            # Wynik na żywo
            koszt_trasy = (dystans / 100) * spalanie * cena_paliwa
            st.markdown(f"**Szacowany koszt:** :red[{koszt_trasy:.2f} PLN]")
            
            if st.button("➕ Dodaj auto do rozliczenia"):
                tytul_auta = f"Paliwo: {auto_nazwa} ({dystans}km)"
                nowy = pd.DataFrame([{
                    'Tytuł': tytul_auta, 'Kategoria': 'Trasa', 'Czas (h)': 0, 
                    'Start': None, 'Koniec': None, 'Zaplanowane': False,
                    'Koszt': float(koszt_trasy),
                    'Typ_Kosztu': 'Paliwo' # Oznaczamy jako Paliwo (też wspólne)
                }])
                updated_df = pd.concat([st.session_state.db, nowy], ignore_index=True)
                if update_data(repo, updated_df):
                    st.success(f"Dodano {auto_nazwa}!")
                    st.rerun()

    st.divider()
    st.markdown("### 📋 Lista dodanych kosztów wspólnych")
    
    # Filtrujemy tylko Wspólne i Paliwo
    mask_wspolne = st.session_state.db['Typ_Kosztu'].isin(['Wspólny', 'Paliwo'])
    df_wspolne = st.session_state.db[mask_wspolne]
    
    if not df_wspolne.empty:
        event = st.dataframe(
            df_wspolne[['Tytuł', 'Kategoria', 'Typ_Kosztu', 'Koszt']],
            use_container_width=True, hide_index=True,
            selection_mode="multi-row", on_select="rerun",
            column_config={
                "Koszt": st.column_config.NumberColumn("Koszt Całkowity", format="%.2f zł")
            }
        )
        if event.selection.rows:
            if st.button("🗑️ Usuń wybrane koszty wspólne", type="primary"):
                 with st.spinner("Usuwam..."):
                    indeksy = df_wspolne.iloc[event.selection.rows].index
                    updated_df = st.session_state.db.drop(indeksy).reset_index(drop=True)
                    if update_data(repo, updated_df):
                        st.rerun()
    else:
        st.info("Jeszcze nie dodałeś żadnych wspólnych wydatków.")

# ==========================================
# ZAKŁADKA 4: PODSUMOWANIE (BEZ ZMIAN MATEMATYKI NA RAZIE)
# ==========================================
with tab_podsumowanie:
    st.subheader("💸 Ile to będzie kosztować?")
    
    mask_koszty = (st.session_state.db['Zaplanowane'].astype(str).str.upper() == 'TRUE') & \
                  (st.session_state.db['Typ_Kosztu'] == 'Indywidualny')
    
    df_costs = st.session_state.db[mask_koszty].copy()
    
    df_costs['Koszt'] = pd.to_numeric(df_costs['Koszt'], errors='coerce').fillna(0)
    
    if not df_costs.empty:
        col_kpi, col_chart = st.columns([1, 2])
        
        with col_kpi:
            # A. KPI
            total_cost = df_costs['Koszt'].sum()
            st.metric(label="Całkowity koszt wyjazdu", value=f"{total_cost:.2f} PLN")
            
            st.divider()
            
            # B. TABELA
            tabela = df_costs[df_costs['Koszt'] > 0][['Tytuł', 'Koszt']].sort_values(by='Koszt', ascending=False)
            
            if not tabela.empty:
                st.write("**Szczegóły wydatków:**")
                st.dataframe(
                    tabela, 
                    use_container_width=True, 
                    hide_index=True,
                    column_config={
                        "Koszt": st.column_config.NumberColumn("Koszt", format="%.2f zł")
                    }
                )
            else:
                st.info("Brak płatnych atrakcji.")
                
        with col_chart:
            st.write("**📅 Rozkład wydatków w czasie**")
            df_costs['Data_Group'] = df_costs['Start'].dt.date
            daily_costs = df_costs.groupby('Data_Group')['Koszt'].sum().reset_index()
            daily_costs['Etykieta'] = daily_costs['Data_Group'].apply(lambda x: x.strftime('%d.%m'))
            daily_costs['Sort_Key'] = daily_costs['Data_Group'].astype(str)
            
            bar_chart = alt.Chart(daily_costs).mark_bar(
                color='#FF4B4B',
                cornerRadiusTopLeft=3,
                cornerRadiusTopRight=3
            ).encode(
                x=alt.X('Etykieta:O', 
                        title='Dzień',
                        sort=alt.EncodingSortField(field="Sort_Key", order="ascending"),
                        axis=alt.Axis(labelAngle=0)), 
                y=alt.Y('Koszt:Q', title='Suma (PLN)'),
                tooltip=[
                    alt.Tooltip('Etykieta', title='Dzień'), 
                    alt.Tooltip('Koszt', format='.2f', title='Kwota')
                ]
            ).properties(height=400)
            st.altair_chart(bar_chart, use_container_width=True)
            
    else:
        st.info("Kalendarz jest pusty. Zaplanuj coś, aby zobaczyć koszty!")
