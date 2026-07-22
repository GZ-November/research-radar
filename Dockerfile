FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Copy packaging metadata and sources first so dependency installation stays
# cached unless the library code itself changes.
COPY pyproject.toml README.md ./
COPY radar ./radar
RUN pip install --no-cache-dir .

# Entrypoint changes often; keep it in a later layer than dependencies.
COPY app.py ./
COPY .streamlit ./.streamlit

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.headless=true"]
