import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime, timedelta, time, date
from github import Github, Auth
import io
import json
import base64
import uuid

# ==========================================
# ⚙️ KONFIGURACJA I STAŁE
# ==========================================
st.set_page_config(page_title="Planer Wycieczki", layout="wide")

REGISTRY_FILE = "registry.json"

# Paleta Kolorów (Globalna)
THEME = {
    "bg": "#1e2630",        # Gunmetal
    "text": "#faf9dd",      # Cream
    "accent": "#d37759",    # Terracotta
    "sec": "#4a7a96",       # Muted Blue
    "gray": "#888888",
    "grid": "#444444"
}

# Konfiguracja Kategorii (Kolory i kolejność)
CATEGORY_CONFIG = {
    "Atrakcja":        THEME["accent"],
    "Trasa":           THEME["sec"],
    "Jedzenie":        "#7c8c58", # Olive
    "Impreza":         "#8c5e7c", # Plum
    "Sport/Rekreacja": "#e0c068", # Gold
    "Nocleg":          "#e0c068", # Mapowanie dla kosztów wspólnych
    "Wynajem Busa":    "#8c5e7c",
    "Winiety":         "#7c8c58",
    "Paliwo":          THEME["sec"],
    "Inne":            THEME["gray"]
}

# ==========================================
# 💅 CSS & STYLIZACJA
# ==========================================
st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;700&display=swap');
    html, body, h1, h2, h3, p, div, span {{ font-family: 'Montserrat', sans-serif; }}
    h1, h2, h3 {{ font-weight: 700 !important; }}
    
    /* Ukrywanie elementów UI Streamlit */
    header, footer, .viewerBadge_container__1QSob, [data-testid="stStatusWidget"], #MainMenu {{ display: none !important; }}
    .block-container {{ padding-top: 1rem !important; }}
    div[data-testid="stCheckbox"] {{ margin-bottom: -10px; }}
    
    /* Przyciski */
    div.stButton > button:first-child {{ 
        height: 3em; margin-top: 1.5em; background-color: {THEME['accent']}; color: {THEME['text']}; 
        border: none; font-weight: bold; border-radius: 8px;
    }}
    div.stButton > button:first-child:hover {{ background-color: #b06045; color: {THEME['text']}; }}
    
    /* Metryki i Zakładki */
    [data-testid="stMetricValue"] {{ font-size: 3rem; color: {THEME['accent']}; font-weight: 700; }}
    .stTabs [aria-selected="true"] {{ color: {THEME['accent']} !important; border-bottom-color: {THEME['accent']} !important; }}
    
    /* Altair Scroll Fix */
    [data-testid="stAltairChart"] {{ overflow-x: auto !important; padding-bottom: 20px; }}
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 🔧 FUNKCJE POMOCNICZE (GITHUB & DATA)
# ==========================================
def init_github():
    try:
        token = st.secrets["github"]["token"]
        repo_name = st.secrets["github"]["repo_name"]
        return Github(auth=Auth.Token(token)).get_repo(repo_name)
    except Exception as e:
        st.error(f"GitHub Error: {e}")
        return None

def get_registry(repo):
    try:
        return json.loads(repo.get_contents(REGISTRY_FILE).decoded_content.decode("utf-8"))
    except:
        new_reg = {"current": "default", "trips": {"default": "Moja Pierwsza Wyprawa"}}
        repo.create_file(REGISTRY_FILE, "Init", json.dumps(new_reg, indent=4))
        return new_reg

def update_registry(repo, data):
    try:
        contents = repo.get_contents(REGISTRY_FILE)
        repo.update_file(contents.path, "Update", json.dumps(data, indent=4), contents.sha)
    except: pass

def get_trip_files(trip_id):
    return f"{trip_id}_data.csv", f"{trip_id}_config.json"

def get_data(repo, filename):
    try:
        c = repo.get_contents(filename).decoded_content.decode("utf-8")
        df = pd.read_csv(io.StringIO(c))
        for col in ['Start', 'Koniec']:
            if col in df.columns: df[col] = pd.to_datetime(df[col], errors='coerce')
        if 'Koszt' not in df.columns: df['Koszt'] = 0.0
        if 'Typ_Kosztu' not in df.columns: df['Typ_Kosztu'] = 'Indywidualny'
        return df.fillna("")
    except:
        return pd.DataFrame(columns=['Tytuł', 'Kategoria', 'Czas (h)', 'Start', 'Koniec', 'Zaplanowane', 'Koszt', 'Typ_Kosztu'])

def update_file(repo, filename, content, msg="Update"):
    try:
        contents = repo.get_contents(filename)
        repo.update_file(contents.path, msg, content, contents.sha)
    except:
        repo.create_file(filename, msg, content)

def image_to_base64(path):
    try:
        with open(path, "rb") as f: return base64.b64encode(f.read()).decode('utf-8')
    except: return None

# ==========================================
# 📊 FUNKCJE POMOCNICZE (WIZUALIZACJA)
# ==========================================
def get_category_scale():
    """Zwraca spójną skalę kolorów dla wszystkich wykresów."""
    cats = list(CATEGORY_CONFIG.keys())
    colors = list(CATEGORY_CONFIG.values())
    return alt.Scale(domain=cats, range=colors)

def prepare_calendar_data(df, y_base_date=date(1900, 1, 1)):
    """Przetwarza dane do kalendarza: cięcie przez północ + normalizacja godziny."""
    chart_rows = []
    df['Start'] = pd.to_datetime(df['Start'])
    df['Koniec'] = pd.to_datetime(df['Koniec'])
    
    for _, row in df.iterrows():
        s, e = row['Start'], row['Koniec']
        while s.date() < e.date():
            end_of_day = datetime.combine(s.date(), time(23, 59, 59))
            seg = row.copy()
            seg['Start'], seg['Koniec'] = s, end_of_day
            seg['Y_Start'] = datetime.combine(y_base_date, s.time())
            seg['Y_End'] = datetime.combine(y_base_date, time(23, 59, 59))
            chart_rows.append(seg)
            s = datetime.combine(s.date() + timedelta(days=1), time(0, 0, 0))
        
        last = row.copy()
        last['Start'], last['Koniec'] = s, e
        last['Y_Start'] = datetime.combine(y_base_date, s.time())
        last['Y_End'] = datetime.combine(y_base_date, e.time())
        chart_rows.append(last)
    
    res = pd.DataFrame(chart_rows)
    if not res.empty:
        res['Day_Label'] = res['Start'].dt.strftime('%d.%m %A')
    return res

def render_header(trip_name):
    logo = image_to_base64("logo.png")
    img_html = f'<img src="data:image/png;base64,{logo}" width="140" style="transform: scaleX(-1);">' if logo else ""
    
    st.markdown(f"""
    <div style='background-color: {THEME['sec']}; padding: 2rem; border-radius: 16px; box-shadow: 0 4px 10px rgba(0,0,0,0.15); display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px;'>
        <div style='flex: 1;'>
            <h1 style='color: {THEME['text']}; margin: 0; font-size: 2.8rem; text-transform: uppercase;'>{trip_name}</h1>
            <p style='margin: 5px 0 0 0; font-size: 1.1rem; color: {THEME['text']}; opacity: 0.9; letter-spacing: 3px;'>PLANNER WYJAZDOWY</p>
            <div style='height: 4px; width: 60px; background-color: {THEME['accent']}; margin: 20px 0 15px 0; border-radius: 2px;'></div>
        </div>
        <div style='flex: 0 0 auto; margin-left: 20px;'>{img_html}</div>
    </div>
    """, unsafe_allow_html=True)

# ==========================================
# 🚀 INICJALIZACJA APLIKACJI
# ==========================================
repo = init_github()
if not repo: st.stop()

registry = get_registry(repo)
current_id = st.session_state.get('current_trip_id', registry.get("current", "default"))
if st.session_state.get('manual_switch_flag'): del st.session_state.manual_switch_flag

data_file, config_file = get_trip_files(current_id)

# Ładowanie stanu (tylko przy zmianie ID lub starcie)
if 'db' not in st.session_state or st.session_state.get('current_trip_id') != current_id:
    st.session_state.current_trip_id = current_id
    st.session_state.db = get_data(repo, data_file)
    try:
        conf = json.loads(repo.get_contents(config_file).decoded_content.decode("utf-8"))
        st.session_state.conf = {
            'trip_name': conf.get('trip_name', "Nowa Wyprawa"),
            'start_date': datetime.strptime(conf.get('start_date', "2026-06-01"), "%Y-%m-%d").date(),
            'days': conf.get('days', 7),
            'people': conf.get('people', 1)
        }
    except:
        st.session_state.conf = {'trip_name': "Nowa Wyprawa", 'start_date': date(2026, 6, 1), 'days': 7, 'people': 1}

# ==========================================
# 🧱 INTERFEJS: DIALOGI
# ==========================================
@st.dialog("📂 Menadżer Zapisów")
def save_manager_dialog():
    trips = registry.get("trips", {})
    curr_name = trips.get(current_id, "Nieznana")
    st.info(f"Edytujesz: **{curr_name}**")
    
    sel = st.selectbox("Przełącz:", list(trips.values()), index=list(trips.values()).index(curr_name) if curr_name in trips.values() else 0)
    if st.button("Załaduj"):
        new_id = [k for k,v in trips.items() if v == sel][0]
        if new_id != current_id:
            registry['current'] = new_id
            update_registry(repo, registry)
            st.session_state.current_trip_id = new_id
            del st.session_state.db
            st.rerun()
            
    st.divider()
    with st.form("new_trip"):
        name = st.text_input("Nowa nazwa (np. Alpy 2027)")
        if st.form_submit_button("Utwórz"):
            nid = str(uuid.uuid4())[:8]
            registry['trips'][nid] = name
            registry['current'] = nid
            update_registry(repo, registry)
            update_file(repo, f"{nid}_config.json", json.dumps({"trip_name": name, "start_date": "2026-06-01"}, indent=4))
            update_file(repo, f"{nid}_data.csv", "Tytuł,Kategoria,Czas (h),Start,Koniec,Zaplanowane,Koszt,Typ_Kosztu\n")
            st.session_state.current_trip_id = nid
            del st.session_state.db
            st.rerun()

@st.dialog("⚙️ Ustawienia")
def settings_dialog():
    c = st.session_state.conf
    name = st.text_input("Nazwa:", value=c['trip_name'])
    d1, d2 = st.columns(2)
    start = d1.date_input("Start:", value=c['start_date'])
    days = d2.number_input("Dni:", value=c['days'], min_value=1)
    ppl = st.number_input("Osoby:", value=c['people'], min_value=1)
    
    if st.button("Zapisz", type="primary"):
        new_conf = {"trip_name": name, "start_date": start.strftime("%Y-%m-%d"), "days": days, "people": ppl}
        update_file(repo, config_file, json.dumps(new_conf, indent=4))
        registry['trips'][current_id] = name
        update_registry(repo, registry)
        st.session_state.conf.update({'trip_name': name, 'start_date': start, 'days': days, 'people': ppl})
        st.rerun()

@st.dialog("🗑️ Odepnij")
def unpin_dialog():
    mask = (st.session_state.db['Zaplanowane'].astype(str).str.upper() == 'TRUE') & (st.session_state.db['Typ_Kosztu'] == 'Indywidualny')
    df = st.session_state.db[mask].sort_values('Start')
    if df.empty:
        st.info("Brak zaplanowanych wydarzeń."); return
        
    opts = df.apply(lambda x: f"{x['Tytuł']} ({pd.to_datetime(x['Start']).strftime('%d.%m %H:%M')})", axis=1).tolist()
    sel = st.selectbox("Wybierz:", opts)
    
    if sel and st.button("Odepnij", type="primary"):
        orig = df.iloc[opts.index(sel)]['Tytuł']
        idx = st.session_state.db[st.session_state.db['Tytuł'] == orig].index[0]
        st.session_state.db.at[idx, 'Zaplanowane'] = False
        st.session_state.db.at[idx, 'Start'] = None
        csv_buffer = io.StringIO(); st.session_state.db.to_csv(csv_buffer, index=False)
        update_file(repo, data_file, csv_buffer.getvalue())
        st.rerun()

# ==========================================
# 🖥️ GŁÓWNY UI
# ==========================================
render_header(st.session_state.conf['trip_name'])

c_h, c_set = st.columns([6, 1])
with c_set:
    if st.button("📂", use_container_width=True): save_manager_dialog()
    if st.button("⚙️", use_container_width=True): settings_dialog()

tab1, tab2, tab3 = st.tabs(["📝 Edytor", "📅 Kalendarz", "💰 Podsumowanie"])

# --- TAB 1: EDYTOR ---
with tab1:
    mode = st.radio("Tryb:", ["🏃 Aktywności", "💸 Koszty Wspólne"], horizontal=True, label_visibility="collapsed")
    c_form, c_list = st.columns([1, 1.5])
    
    with c_form:
        with st.container(border=True):
            if mode == "🏃 Aktywności":
                st.subheader("➕ Aktywność")
                with st.form("act_form", clear_on_submit=True):
                    t = st.text_input("Tytuł")
                    k = st.selectbox("Kategoria", ["Atrakcja", "Jedzenie", "Impreza", "Sport/Rekreacja"])
                    h = st.number_input("Czas (h)", 1.0, step=0.5)
                    pln = st.number_input("Koszt (PLN)", 0.0, step=10.0)
                    if st.form_submit_button("Zapisz", type="primary"):
                        row = {'Tytuł': t, 'Kategoria': k, 'Czas (h)': h, 'Koszt': pln, 'Zaplanowane': False, 'Typ_Kosztu': 'Indywidualny'}
                        st.session_state.db = pd.concat([st.session_state.db, pd.DataFrame([row])], ignore_index=True)
                        update_file(repo, data_file, st.session_state.db.to_csv(index=False))
                        st.rerun()
            else:
                st.subheader("➕ Koszt Wspólny")
                sub_mode = st.selectbox("Typ", ["Wydatek", "Paliwo"])
                if sub_mode == "Wydatek":
                    with st.form("cost_form", clear_on_submit=True):
                        n = st.text_input("Nazwa")
                        k = st.selectbox("Kat.", ["Nocleg", "Wynajem Busa", "Winiety", "Inne"])
                        p = st.number_input("Koszt", 0.0, step=50.0)
                        if st.form_submit_button("Dodaj"):
                            row = {'Tytuł': n, 'Kategoria': k, 'Koszt': p, 'Typ_Kosztu': 'Wspólny', 'Czas (h)': 0, 'Zaplanowane': False}
                            st.session_state.db = pd.concat([st.session_state.db, pd.DataFrame([row])], ignore_index=True)
                            update_file(repo, data_file, st.session_state.db.to_csv(index=False))
                            st.rerun()
                else:
                    d = st.number_input("Dystans (km)", 100)
                    s = st.slider("Spalanie", 1.0, 20.0, 8.0)
                    c = st.slider("Cena", 3.0, 10.0, 6.50)
                    total = (d/100)*s*c
                    st.write(f"Koszt: :red[{total:.2f} PLN]")
                    if st.button("Dodaj Paliwo", type="primary"):
                        row = {'Tytuł': f"Paliwo ({d}km)", 'Kategoria': 'Trasa', 'Koszt': total, 'Typ_Kosztu': 'Paliwo', 'Czas (h)': 0, 'Zaplanowane': False}
                        st.session_state.db = pd.concat([st.session_state.db, pd.DataFrame([row])], ignore_index=True)
                        update_file(repo, data_file, st.session_state.db.to_csv(index=False))
                        st.rerun()

    with c_list:
        with st.container(border=True):
            if mode == "🏃 Aktywności":
                st.subheader("📦 Poczekalnia")
                mask = (st.session_state.db['Zaplanowane'].astype(str).str.upper() != 'TRUE') & (st.session_state.db['Typ_Kosztu'] == 'Indywidualny')
            else:
                st.subheader("📋 Lista Kosztów")
                mask = st.session_state.db['Typ_Kosztu'].isin(['Wspólny', 'Paliwo'])
            
            df_view = st.session_state.db[mask]
            evt = st.dataframe(df_view[['Tytuł', 'Kategoria', 'Koszt']], use_container_width=True, on_select="rerun", selection_mode="multi-row", hide_index=True)
            
            if evt.selection.rows and st.button("🗑️ Usuń zaznaczone", type="primary"):
                st.session_state.db = st.session_state.db.drop(df_view.iloc[evt.selection.rows].index).reset_index(drop=True)
                update_file(repo, data_file, st.session_state.db.to_csv(index=False))
                st.rerun()

# --- TAB 2: KALENDARZ ---
with tab2:
    c_mob, _, c_unpin = st.columns([2, 5, 2])
    mobile = c_mob.toggle("📱 Tryb Mobilny")
    if c_unpin.button("🗑️ Odepnij", use_container_width=True): unpin_dialog()

    # Przygotowanie danych
    mask_cal = (st.session_state.db['Zaplanowane'].astype(str).str.upper() == 'TRUE') & (st.session_state.db['Typ_Kosztu'] == 'Indywidualny')
    df_cal = st.session_state.db[mask_cal].copy()
    if not df_cal.empty:
        df_cal['Start'] = pd.to_datetime(df_cal['Start'])
        df_cal['Koniec'] = pd.to_datetime(df_cal['Start']) + pd.to_timedelta(df_cal['Czas (h)'].astype(float), unit='h')
        df_cal = df_cal.sort_values('Start')

    if mobile:
        if df_cal.empty: st.info("Pusto.")
        else:
            df_cal['Day'] = df_cal['Start'].dt.date
            for d in sorted(df_cal['Day'].unique()):
                st.markdown(f"#### {d.strftime('%d.%m %A')}")
                for _, r in df_cal[df_cal['Day'] == d].iterrows():
                    clr = CATEGORY_CONFIG.get(r['Kategoria'], "#444")
                    st.markdown(f"""
                    <div style='background:{clr}; color:#fff; padding:12px; border-radius:10px; margin-bottom:10px;'>
                        <div style='opacity:0.8; font-size:0.9em;'>{r['Start'].strftime('%H:%M')} - {r['Koniec'].strftime('%H:%M')}</div>
                        <div style='font-weight:bold; font-size:1.1em;'>{r['Tytuł']}</div>
                        <div style='font-size:0.8em; opacity:0.8;'>{r['Kategoria']}</div>
                    </div>
                    """, unsafe_allow_html=True)
    else:
        # WIDOK DESKTOPOWY (ALTAIR)
        all_dates = [st.session_state.conf['start_date'] + timedelta(days=i) for i in range(st.session_state.conf['days'])]
        labels = [d.strftime('%d.%m %A') for d in all_dates]
        
        # Tło 24h (1900-01-01 base)
        base_y_min = datetime(1900, 1, 1, 0, 0)
        base_y_max = datetime(1900, 1, 1, 23, 59, 59)
        
        # Przetwarzanie danych (funkcja pomocnicza)
        df_chart = prepare_calendar_data(df_cal, base_y_min.date()) if not df_cal.empty else pd.DataFrame()
        
        # Baza gridu
        bg_data = pd.DataFrame([{'Day_Label': l, 'Y_Start': base_y_min, 'Y_End': base_y_max} for l in labels])
        
        base = alt.Chart(bg_data).mark_rect(opacity=0).encode(
            x=alt.X('Day_Label:N', scale=alt.Scale(domain=labels, paddingInner=0.05), axis=alt.Axis(orient='top', labelColor=THEME['text'], domainColor=THEME['bg'])),
            y=alt.Y('Y_Start:T', scale=alt.Scale(reverse=True, domain=[base_y_min, base_y_max]), axis=alt.Axis(format='%H:%M', labelColor=THEME['text'], grid=True, gridColor=THEME['grid'])),
            y2='Y_End:T'
        )
        
        chart = base
        if not df_chart.empty:
            bars = alt.Chart(df_chart).mark_bar(cornerRadius=4, width=60).encode(
                x=alt.X('Day_Label:N', scale=alt.Scale(domain=labels, paddingInner=0.05)),
                y=alt.Y('Y_Start:T', scale=alt.Scale(reverse=True, domain=[base_y_min, base_y_max])),
                y2='Y_End:T',
                color=alt.Color('Kategoria', scale=get_category_scale(), legend=None),
                tooltip=['Tytuł', 'Start', 'Koszt']
            )
            txt = bars.mark_text(dy=-10, color='white', fontWeight='bold', limit=55).encode(text='Tytuł')
            time_txt = bars.mark_text(dy=5, color='white', opacity=0.8, fontSize=9).encode(text=alt.Text('Y_Start:T', format='%H:%M'))
            chart = base + bars + txt + time_txt
            
        chart = chart.properties(height=800, width=max(len(labels)*120, 600), background=THEME['bg']).configure_view(strokeWidth=0)
        st.altair_chart(chart, use_container_width=False)

    st.divider()
    c_tool, c_route = st.columns(2)
    
    with c_tool:
        with st.container(border=True):
            st.subheader("📌 Przybornik")
            # Filtry
            cols = st.columns(3)
            active_cats = []
            for i, cat in enumerate(["Atrakcja", "Trasa", "Jedzenie", "Impreza", "Sport/Rekreacja"]):
                if cols[i%3].checkbox(cat, True): active_cats.append(cat)
            
            mask_wait = (st.session_state.db['Zaplanowane'].astype(str).str.upper() != 'TRUE') & (st.session_state.db['Typ_Kosztu'] == 'Indywidualny')
            df_wait = st.session_state.db[mask_wait]
            df_wait = df_wait[df_wait['Kategoria'].isin(active_cats)]
            
            if not df_wait.empty:
                sel = st.selectbox("Element:", df_wait['Tytuł'])
                row = df_wait[df_wait['Tytuł'] == sel].iloc[0]
                d1, d2 = st.columns(2)
                day = d1.date_input("Dzień", st.session_state.conf['start_date'])
                hour = d2.selectbox("Godz", range(24), index=10, format_func=lambda x: f"{x:02d}:00")
                
                if st.button("⬅️ Wrzuć"):
                    idx = st.session_state.db[st.session_state.db['Tytuł'] == sel].index[0]
                    start = datetime.combine(day, time(hour, 0))
                    st.session_state.db.at[idx, 'Start'] = start
                    st.session_state.db.at[idx, 'Zaplanowane'] = True
                    update_file(repo, data_file, st.session_state.db.to_csv(index=False))
                    st.rerun()
            else: st.caption("Pusto w wybranych kategoriach.")

    with c_route:
        with st.container(border=True):
            st.subheader("🚗 Szybka Trasa")
            rt = st.text_input("Tytuł (np. Dojazd)")
            r1, r2 = st.columns(2)
            rd = r1.date_input("Kiedy", st.session_state.conf['start_date'], key='rd')
            rh = r2.selectbox("O której", range(24), index=8, format_func=lambda x: f"{x:02d}:00", key='rh')
            rc = st.number_input("Czas (h)", 1.0, step=0.5)
            
            if st.button("Dodaj Trasę", type="primary"):
                if rt:
                    start = datetime.combine(rd, time(rh, 0))
                    row = {'Tytuł': rt, 'Kategoria': 'Trasa', 'Czas (h)': rc, 'Start': start, 'Zaplanowane': True, 'Koszt': 0.0, 'Typ_Kosztu': 'Indywidualny'}
                    st.session_state.db = pd.concat([st.session_state.db, pd.DataFrame([row])], ignore_index=True)
                    update_file(repo, data_file, st.session_state.db.to_csv(index=False))
                    st.rerun()

# --- TAB 3: PODSUMOWANIE ---
with tab3:
    with st.container(border=True):
        st.subheader("Finanse")
        df = st.session_state.db.copy()
        df['Koszt'] = pd.to_numeric(df['Koszt'], errors='coerce').fillna(0)
        
        sum_ind = df[(df['Zaplanowane'].astype(str).str.upper() == 'TRUE') & (df['Typ_Kosztu'] == 'Indywidualny')]['Koszt'].sum()
        sum_shared = df[df['Typ_Kosztu'].isin(['Wspólny', 'Paliwo'])]['Koszt'].sum()
        per_person = sum_shared / st.session_state.conf['people']
        
        k1, k2, k3 = st.columns(3)
        k1.metric("Łącznie (Ty)", f"{sum_ind + per_person:.0f} PLN")
        k2.metric("Twoje Atrakcje", f"{sum_ind:.0f} PLN")
        k3.metric("Baza (na osobę)", f"{per_person:.0f} PLN", f"Całość: {sum_shared:.0f}")

    st.divider()
    c_pie, c_bar = st.columns([1, 2])
    
    with c_pie:
        with st.container(border=True):
            st.markdown("#### Podział")
            # Agregacja Pie Chart (Indywidualne jako "Atrakcje")
            pie_data = [{'Kategoria': 'Atrakcje', 'Wartość': sum_ind}]
            if sum_shared > 0:
                grp = df[df['Typ_Kosztu'].isin(['Wspólny', 'Paliwo'])].groupby('Kategoria')['Koszt'].sum()
                for cat, val in grp.items():
                    pie_data.append({'Kategoria': cat, 'Wartość': val / st.session_state.conf['people']})
            
            df_pie = pd.DataFrame(pie_data)
            df_pie = df_pie[df_pie['Wartość'] > 0]
            
            if not df_pie.empty:
                df_pie['Procent'] = df_pie['Wartość'] / df_pie['Wartość'].sum()
                base = alt.Chart(df_pie).encode(theta=alt.Theta("Wartość", stack=True))
                pie = base.mark_arc(innerRadius=50).encode(
                    color=alt.Color("Kategoria", scale=get_category_scale(), legend=alt.Legend(orient="bottom", columns=2, labelColor=THEME['text'])),
                    order=alt.Order("Kategoria"), tooltip=['Kategoria', 'Wartość']
                )
                text = base.mark_text(radius=120).encode(text=alt.Text("Procent", format=".0%"), color=alt.value(THEME['text']))
                st.altair_chart(pie + text, use_container_width=True)

    with c_bar:
        with st.container(border=True):
            st.markdown("#### Wydatki w czasie")
            mask_bar = (df['Zaplanowane'].astype(str).str.upper() == 'TRUE') & (df['Typ_Kosztu'] == 'Indywidualny')
            df_bar = df[mask_bar].copy()
            
            if not df_bar.empty:
                df_bar['Start'] = pd.to_datetime(df_bar['Start'])
                df_bar['Dzień'] = df_bar['Start'].dt.strftime('%d.%m')
                df_bar['Sort'] = df_bar['Start'].dt.strftime('%Y-%m-%d')
                
                base = alt.Chart(df_bar).encode(
                    x=alt.X('Dzień', sort=alt.EncodingSortField(field="Sort", op="min"), axis=alt.Axis(labelColor=THEME['text'], title=None))
                )
                bars = base.mark_bar().encode(
                    y=alt.Y('sum(Koszt)', axis=alt.Axis(labelColor=THEME['text'], title=None, gridColor=THEME['grid'])),
                    color=alt.Color('Kategoria', scale=get_category_scale(), legend=None),
                    tooltip=['Dzień', 'Kategoria', 'sum(Koszt)']
                )
                totals = df_bar.groupby(['Dzień', 'Sort'])['Koszt'].sum().reset_index()
                text = alt.Chart(totals).mark_text(dy=-5, color=THEME['text']).encode(
                    x=alt.X('Dzień', sort=alt.EncodingSortField(field="Sort", op="min")),
                    y='Koszt', text=alt.Text('Koszt', format='.0f')
                )
                st.altair_chart(bars + text, use_container_width=True)
            else: st.info("Brak danych na osi czasu.")
