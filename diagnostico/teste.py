# Diagnóstico de infraestrutura do Streamlit Cloud (nov/2026): app mínimo, sem
# banco e sem as dependências do Plano VP. Serve só para comparar a estabilidade
# do servidor. Pode ser apagado depois do teste (docs/PUBLICACAO.md).
import streamlit as st

st.write("ok — app de diagnóstico")
