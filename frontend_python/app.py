import streamlit as st
import requests
import json
import os
from typing import Optional

# Configuration
BACKEND_URL = os.getenv("BACKEND_URL", "http://python_backend:8000")

# Initialize session state
if "token" not in st.session_state:
    st.session_state.token = None
if "username" not in st.session_state:
    st.session_state.username = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []


def get_headers():
    """Get authorization headers"""
    if st.session_state.token:
        return {"Authorization": f"Bearer {st.session_state.token}"}
    return {}


def login(username: str, password: str) -> bool:
    """Login user"""
    try:
        response = requests.post(
            f"{BACKEND_URL}/login",
            data={"username": username, "password": password},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            st.session_state.token = data["access_token"]
            st.session_state.username = username
            return True
    except Exception as e:
        st.error(f"Login failed: {str(e)}")
    return False


def register(username: str, password: str) -> bool:
    """Register new user"""
    try:
        response = requests.post(
            f"{BACKEND_URL}/register",
            json={"username": username, "password": password},
            timeout=10
        )
        if response.status_code == 201:
            return True
        else:
            st.error(response.json().get("detail", "Registration failed"))
    except Exception as e:
        st.error(f"Registration failed: {str(e)}")
    return False


def logout():
    """Logout user"""
    st.session_state.token = None
    st.session_state.username = None
    st.session_state.chat_history = []


def get_cards(name: Optional[str] = None, category: Optional[str] = None):
    """Get person cards"""
    try:
        params = {}
        if name:
            params["name"] = name
        if category:
            params["category"] = category

        response = requests.get(
            f"{BACKEND_URL}/cards",
            headers=get_headers(),
            params=params,
            timeout=10
        )
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        st.error(f"Failed to fetch cards: {str(e)}")
    return []


def create_card(name: str, category: str, description: str, lat: Optional[float], lon: Optional[float]):
    """Create new person card"""
    try:
        data = {
            "name": name,
            "category": category,
            "description": description,
            "lat": lat,
            "lon": lon
        }
        response = requests.post(
            f"{BACKEND_URL}/cards",
            headers=get_headers(),
            json=data,
            timeout=10
        )
        if response.status_code == 201:
            st.success("Card created successfully!")
            return True
        else:
            st.error(response.json().get("detail", "Failed to create card"))
    except Exception as e:
        st.error(f"Failed to create card: {str(e)}")
    return False


def upload_document(file, person_id: int):
    """Upload document for a person card"""
    try:
        files = {"file": file}
        data = {"person_id": person_id}
        response = requests.post(
            f"{BACKEND_URL}/upload_document",
            headers=get_headers(),
            files=files,
            data=data,
            timeout=60
        )
        if response.status_code == 200:
            result = response.json()
            st.success(f"Document uploaded! {result['chunks_created']} chunks created.")
            return True
        else:
            st.error(response.json().get("detail", "Upload failed"))
    except Exception as e:
        st.error(f"Upload failed: {str(e)}")
    return False


def get_alphabetical_index():
    """Fetch persons grouped by first letter."""
    try:
        response = requests.get(
            f"{BACKEND_URL}/api/persons/alphabetical",
            headers=get_headers(),
            timeout=10
        )
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        st.error(f"Ошибка загрузки: {str(e)}")
    return {}


def chat(query: str):
    """Send chat message"""
    try:
        response = requests.post(
            f"{BACKEND_URL}/chat",
            headers=get_headers(),
            json={"query": query},
            timeout=30
        )
        if response.status_code == 200:
            return response.json()
        else:
            st.error(response.json().get("detail", "Chat failed"))
    except Exception as e:
        st.error(f"Chat failed: {str(e)}")
    return None


# Main UI
st.set_page_config(page_title="Archive Search", page_icon="📚", layout="wide")

st.title("📚 Archive Search - RAG System")

# Sidebar for auth
with st.sidebar:
    st.header("Authentication")

    if st.session_state.token:
        st.success(f"Logged in as: {st.session_state.username}")
        if st.button("Logout"):
            logout()
            st.rerun()
    else:
        tab1, tab2 = st.tabs(["Login", "Register"])

        with tab1:
            login_username = st.text_input("Username", key="login_user")
            login_password = st.text_input("Password", type="password", key="login_pass")
            if st.button("Login"):
                if login(login_username, login_password):
                    st.success("Login successful!")
                    st.rerun()

        with tab2:
            reg_username = st.text_input("Username", key="reg_user")
            reg_password = st.text_input("Password", type="password", key="reg_pass")
            if st.button("Register"):
                if register(reg_username, reg_password):
                    st.success("Registration successful! Please login.")

# Main content
if st.session_state.token:
    tab1, tab2, tab3, tab4 = st.tabs(["💬 Chat", "📁 Documents", "👤 Person Cards", "🔤 А–Я"])

    # Chat Tab
    with tab1:
        st.header("Chat with Archives")

        # Display chat history
        for msg in st.session_state.chat_history:
            with st.chat_message("user"):
                st.write(msg["query"])
            with st.chat_message("assistant"):
                st.write(msg["answer"])
                if msg.get("sources"):
                    st.caption(f"Sources: Person IDs {msg['sources']}")

        # Chat input
        user_query = st.chat_input("Ask a question about the archives...")
        if user_query:
            with st.chat_message("user"):
                st.write(user_query)

            with st.spinner("Thinking..."):
                response = chat(user_query)

            if response:
                with st.chat_message("assistant"):
                    st.write(response["answer"])
                    if response.get("sources"):
                        st.caption(f"Sources: Person IDs {response['sources']}")

                st.session_state.chat_history.append({
                    "query": user_query,
                    "answer": response["answer"],
                    "sources": response.get("sources", [])
                })

    # Documents Tab
    with tab2:
        st.header("Upload Documents")

        cards = get_cards()
        if cards:
            card_options = {f"{card['name']} ({card['category']})": card['id'] for card in cards}
            selected_card = st.selectbox("Select Person Card", options=list(card_options.keys()))

            uploaded_file = st.file_uploader("Choose a text or markdown file", type=["txt", "md"])

            if st.button("Upload Document"):
                if uploaded_file and selected_card:
                    person_id = card_options[selected_card]
                    upload_document(uploaded_file, person_id)
        else:
            st.info("No person cards available. Create one first!")

    # Person Cards Tab
    with tab3:
        st.header("Person Cards")

        # Create new card
        with st.expander("Create New Card"):
            col1, col2 = st.columns(2)
            with col1:
                new_name = st.text_input("Name")
                new_category = st.text_input("Category")
            with col2:
                new_lat = st.number_input("Latitude", value=None, format="%.6f")
                new_lon = st.number_input("Longitude", value=None, format="%.6f")

            new_description = st.text_area("Description")

            if st.button("Create Card"):
                if new_name and new_category:
                    create_card(new_name, new_category, new_description, new_lat, new_lon)
                    st.rerun()
                else:
                    st.error("Name and category are required")

        # Filter and display cards
        st.subheader("Existing Cards")
        col1, col2 = st.columns(2)
        with col1:
            filter_name = st.text_input("Filter by name", key="filter_name")
        with col2:
            filter_category = st.text_input("Filter by category", key="filter_category")

        cards = get_cards(name=filter_name or None, category=filter_category or None)

        if cards:
            for card in cards:
                with st.container():
                    st.markdown(f"**{card['name']}** - _{card['category']}_")
                    if card['description']:
                        st.write(card['description'])
                    if card['lat'] and card['lon']:
                        st.caption(f"📍 Location: {card['lat']}, {card['lon']}")
                    st.divider()
        else:
            st.info("No cards found")

    # Alphabetical Index Tab
    with tab4:
        st.header("Алфавитный указатель репрессированных")

        index = get_alphabetical_index()

        if not index:
            st.info("Данные не загружены. Импортируйте seed.json через /api/persons/import")
        else:
            letters = list(index.keys())
            total = sum(len(v) for v in index.values())
            st.caption(f"Всего записей: {total} · Букв: {len(letters)}")

            # ── Letter navigation bar ──────────────────────────────────────
            letter_cols = st.columns(min(len(letters), 10))
            for i, letter in enumerate(letters):
                col = letter_cols[i % 10]
                col.markdown(
                    f"<a href='#{letter.lower()}' style='text-decoration:none;'>"
                    f"<button style='width:100%;padding:4px;border-radius:6px;"
                    f"background:#1f4e79;color:white;border:none;cursor:pointer;"
                    f"font-weight:bold;font-size:16px'>{letter}</button></a>",
                    unsafe_allow_html=True,
                )

            st.divider()

            # ── Filter ─────────────────────────────────────────────────────
            search_q = st.text_input("🔍 Поиск по имени или профессии", placeholder="Байтемиров...")

            # ── Cards per letter ───────────────────────────────────────────
            for letter, persons in index.items():
                # Apply search filter
                if search_q:
                    persons = [
                        p for p in persons
                        if search_q.lower() in p["full_name"].lower()
                           or search_q.lower() in (p.get("occupation") or "").lower()
                    ]
                if not persons:
                    continue

                st.markdown(
                    f"<h3 id='{letter.lower()}' style='color:#1f4e79;border-bottom:2px solid #1f4e79;"
                    f"padding-bottom:4px;margin-top:24px'>{letter} <span style='font-size:14px;"
                    f"color:#888;font-weight:normal'>({len(persons)})</span></h3>",
                    unsafe_allow_html=True,
                )

                for p in persons:
                    years = f"{p['birth_year'] or '?'} – {p['death_year'] or 'неизв.'}"
                    rehab = p.get("rehabilitation_date") or "—"
                    sentence = p.get("sentence") or "—"

                    with st.expander(f"**{p['full_name']}** &nbsp;·&nbsp; {p.get('occupation', '—')} &nbsp;·&nbsp; {years}"):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown(f"**Регион:** {p.get('region', '—')}")
                            st.markdown(f"**Приговор:** {sentence}")
                        with col2:
                            st.markdown(f"**Реабилитирован:** {rehab}")
                            st.markdown(f"**ID:** {p['id']}")

else:
    st.info("👈 Please login or register to use the system")