
import streamlit as st


st.set_page_config(
    page_title="LexiSyncAI",
    page_icon="⚖️",
    layout="wide",
)

st.title("⚖️ LexiSyncAI")
st.subheader("Evidence-Grounded Legal Document Analyst")

st.markdown(
    """
    Welcome to LexiSyncAI.

    Upload public legal documents, ask questions about their contents,
    and receive evidence-grounded answers with document citations.

    **Development status:** PDF ingestion implemented.
    """
)

st.info(
    "The document ingestion and retrieval pipeline is currently under development."
)

st.sidebar.header("About")
st.sidebar.write("Local legal document analysis powered by AI.")
st.sidebar.caption("Deep Learning & Generative AI Project")
