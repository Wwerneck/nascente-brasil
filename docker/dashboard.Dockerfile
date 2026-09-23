FROM python:3.11-slim

WORKDIR /app
RUN pip install --no-cache-dir "streamlit>=1.64,<2" "plotly>=6.9,<7" "pandas>=2.1" "requests>=2.32,<3"
COPY dashboard ./dashboard

EXPOSE 8501
CMD ["streamlit", "run", "dashboard/app.py", "--server.address", "0.0.0.0", "--server.port", "8501", "--server.headless", "true"]
