FROM python:3.11-slim

WORKDIR /app
COPY src/nascente_brasil ./src/nascente_brasil
ENV PYTHONPATH=/app/src
RUN pip install --no-cache-dir "fastapi>=0.141,<1" "uvicorn>=0.53,<1" \
    "psycopg[binary]>=3.2,<4" "python-dotenv>=1,<2"

EXPOSE 8000
CMD ["uvicorn", "nascente_brasil.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
