# Yield Predictor web app (v0.2.0). Build:  docker build -t yield-predictor .
# The server reads data/processed/ (the same files the Streamlit app reads) and answers the front page; it needs pandas,
# pyarrow and FastAPI, not Streamlit, geopandas or scikit-learn: a small image for Render's free plan. The data science
# runs on your PC (the scripts) and its results come in through Git.
FROM python:3.12-slim

# Don't write .pyc files; print logs straight away. PYTHONPATH: the code runs from src/ as it is, so appdata.py finds
# data/processed/ beside it (/srv/data/processed), as on your PC.
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/srv/src YIELD_PREDICTOR_HOSTED=1

WORKDIR /srv
COPY requirements-web.txt ./
RUN pip install --no-cache-dir -r requirements-web.txt
COPY src ./src
# Only the files the web app reads: yields, the model's ranges, and this season's weather
COPY data/processed/*_yield_county.parquet data/processed/ranges.parquet data/processed/ranges_soy.parquet \
     data/processed/ranges_ia.parquet data/processed/ranges_ia_soy.parquet data/processed/season_ne.parquet ./data/processed/

# Run as an ordinary user, not root.
RUN useradd --create-home yields
USER yields

# Hosts say which port to listen on through $PORT (Render uses 10000); 8000 when they don't.
ENV PORT=8000
EXPOSE 8000
HEALTHCHECK CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/health')"
CMD ["sh", "-c", "exec uvicorn yieldpred.web.app:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips=*"]
