FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY dns_exporter.py .

# Non-root user for security
RUN useradd -r -u 1000 exporter
USER exporter

EXPOSE 9253

CMD ["python", "-u", "dns_exporter.py"]
