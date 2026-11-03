# Plano VP — imagem para o Hugging Face Spaces (sdk: docker). Roda o mesmo app.py.
# Banco: variável PLANO_DB_URL (Secret do Space) — ver docs/PUBLICACAO.md.
FROM python:3.12-slim

RUN useradd -m -u 1000 user
WORKDIR /app
RUN chown user:user /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=user . .
USER user

EXPOSE 7860
# XSRF/CORS desligados: o Space é servido atrás do proxy do Hugging Face e o
# upload de arquivos (tela Dados) falha com XSRF ligado.
CMD ["streamlit", "run", "app.py", "--server.port=7860", "--server.address=0.0.0.0", \
     "--server.headless=true", "--server.enableXsrfProtection=false", "--server.enableCORS=false", \
     "--server.fileWatcherType=none"]
