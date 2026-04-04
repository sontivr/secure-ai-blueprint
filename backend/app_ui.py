import requests
import streamlit as st

try:
    API_BASE_URL = st.secrets["API_BASE_URL"]
except Exception:
    API_BASE_URL = "http://127.0.0.1:8000"

st.set_page_config(page_title="Secure AI Blueprint", page_icon="🔒", layout="wide")


def api_headers() -> dict:
    token = st.session_state.get("token")
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def login(username: str, password: str):
    resp = requests.post(
        f"{API_BASE_URL}/auth/login",
        json={"username": username, "password": password},
        timeout=30,
    )
    return resp


def ingest_text(source: str, text: str):
    resp = requests.post(
        f"{API_BASE_URL}/ingest/text",
        headers={**api_headers(), "Content-Type": "application/json"},
        json={"source": source, "text": text},
        timeout=120,
    )
    return resp


def ingest_file(uploaded_file, endpoint: str):
    files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
    resp = requests.post(
        f"{API_BASE_URL}{endpoint}",
        headers=api_headers(),
        files=files,
        timeout=240,
    )
    return resp


def query_docs(question: str, top_k: int):
    resp = requests.post(
        f"{API_BASE_URL}/query",
        headers={**api_headers(), "Content-Type": "application/json"},
        json={"question": question, "top_k": top_k},
        timeout=240,
    )
    return resp


def get_audit_summary():
    resp = requests.get(
        f"{API_BASE_URL}/audit/summary",
        headers=api_headers(),
        timeout=60,
    )
    return resp


if "token" not in st.session_state:
    st.session_state.token = None
if "role" not in st.session_state:
    st.session_state.role = None
if "username" not in st.session_state:
    st.session_state.username = None

st.title("🔒 Secure AI Blueprint")
st.caption("Local-first, regulated-ready document QA demo")

with st.sidebar:
    st.subheader("Connection")
    st.write(f"API: `{API_BASE_URL}`")

    if st.session_state.token:
        st.success(f"Logged in as {st.session_state.username} ({st.session_state.role})")
        if st.button("Log out"):
            st.session_state.token = None
            st.session_state.role = None
            st.session_state.username = None
            st.rerun()
    else:
        st.info("Not logged in")

tab_login, tab_ingest, tab_query, tab_audit = st.tabs(["Login", "Ingest", "Query", "Audit"])

with tab_login:
    st.subheader("Login")

    if st.session_state.token:
        st.success("Already authenticated.")
    else:
        with st.form("login_form"):
            username = st.text_input("Username", value="")
            password = st.text_input("Password", type="password", value="")
            submitted = st.form_submit_button("Login")

        if submitted:
            try:
                resp = login(username, password)
                if resp.ok:
                    data = resp.json()
                    st.session_state.token = data["access_token"]
                    st.session_state.role = data["role"]
                    st.session_state.username = username
                    st.success("Login successful.")
                    st.rerun()
                else:
                    st.error(f"Login failed: {resp.text}")
            except Exception as e:
                st.error(f"Login error: {e}")

with tab_ingest:
    st.subheader("Document Ingestion")

    if not st.session_state.token:
        st.warning("Please log in first.")
    elif st.session_state.role != "admin":
        st.warning("Only admin users can ingest content.")
    else:
        ingest_mode = st.radio("Choose input type", ["Text", "TXT File", "PDF File"], horizontal=True)

        if ingest_mode == "Text":
            with st.form("ingest_text_form"):
                source = st.text_input("Source label", value="policy.txt")
                text = st.text_area("Text content", height=180)
                submitted = st.form_submit_button("Ingest Text")

            if submitted:
                if not source.strip() or not text.strip():
                    st.error("Source and text are required.")
                else:
                    try:
                        resp = ingest_text(source, text)
                        if resp.ok:
                            st.success("Text ingested successfully.")
                            st.json(resp.json())
                        else:
                            st.error(f"Ingest failed: {resp.text}")
                    except Exception as e:
                        st.error(f"Ingest error: {e}")

        elif ingest_mode == "TXT File":
            uploaded_txt = st.file_uploader("Upload .txt file", type=["txt"], key="txt_uploader")
            if uploaded_txt is not None:
                if st.button("Ingest TXT File"):
                    try:
                        resp = ingest_file(uploaded_txt, "/ingest/file")
                        if resp.ok:
                            st.success("TXT file ingested successfully.")
                            st.json(resp.json())
                        else:
                            st.error(f"Ingest failed: {resp.text}")
                    except Exception as e:
                        st.error(f"Ingest error: {e}")

        elif ingest_mode == "PDF File":
            uploaded_pdf = st.file_uploader("Upload PDF file", type=["pdf"], key="pdf_uploader")
            if uploaded_pdf is not None:
                if st.button("Ingest PDF File"):
                    try:
                        resp = ingest_file(uploaded_pdf, "/ingest/pdf")
                        if resp.ok:
                            st.success("PDF ingested successfully.")
                            st.json(resp.json())
                        else:
                            st.error(f"Ingest failed: {resp.text}")
                    except Exception as e:
                        st.error(f"Ingest error: {e}")

with tab_query:
    st.subheader("Ask Questions")

    if not st.session_state.token:
        st.warning("Please log in first.")
    else:
        with st.form("query_form"):
            question = st.text_area("Question", height=120, placeholder="Ask a question about the ingested documents...")
            top_k = st.slider("Top K retrieval", min_value=1, max_value=10, value=5)
            submitted = st.form_submit_button("Run Query")

        if submitted:
            if not question.strip():
                st.error("Question is required.")
            else:
                try:
                    resp = query_docs(question, top_k)
                    if resp.ok:
                        data = resp.json()

                        st.markdown("### Answer")
                        st.markdown(data.get("answer", ""))

                        contexts = data.get("contexts", [])
                        st.markdown("### Retrieved Contexts")

                        if not contexts:
                            st.info("No relevant contexts were returned.")
                        else:
                            for i, ctx in enumerate(contexts, start=1):
                                title = f"Context {i}: {ctx.get('source', 'unknown')}"
                                if ctx.get("page") is not None:
                                    title += f" | page {ctx.get('page')}"
                                if ctx.get("chunk_index") is not None:
                                    title += f" | chunk {ctx.get('chunk_index')}"

                                with st.expander(title):
                                    st.write(f"**ID:** {ctx.get('id')}")
                                    st.write(f"**Distance:** {ctx.get('distance')}")
                                    st.write(ctx.get("text", ""))
                    else:
                        st.error(f"Query failed: {resp.text}")
                except Exception as e:
                    st.error(f"Query error: {e}")

with tab_audit:
    st.subheader("Audit Summary")

    if not st.session_state.token:
        st.warning("Please log in first.")
    elif st.session_state.role != "admin":
        st.warning("Only admin users can view audit summary.")
    else:
        if st.button("Refresh Audit Summary"):
            try:
                resp = get_audit_summary()
                if resp.ok:
                    st.json(resp.json())
                else:
                    st.error(f"Audit summary failed: {resp.text}")
            except Exception as e:
                st.error(f"Audit summary error: {e}")