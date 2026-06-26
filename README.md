# DNS Monitor
![Docker](https://img.shields.io/badge/docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![Grafana](https://img.shields.io/badge/grafana-F46800?style=for-the-badge&logo=grafana&logoColor=white)
![Prometheus](https://img.shields.io/badge/prometheus-E6522C?style=for-the-badge&logo=prometheus&logoColor=white)
![DNS Exporter](https://img.shields.io/badge/DNS_Exporter-007BFF?style=for-the-badge)

A Prometheus exporter that monitors multiple DNS servers, tracks query performance, and detects response mismatches across resolvers.

## Features

- **Multi-DNS Monitoring** – Tracks multiple DNS servers (e.g., `shecan`, `403_1`, `403_2`).
- **Prometheus Metrics** – Exports health (`dns_server_up`), query success (`dns_query_success`), response time (`dns_response_time_seconds`), resolved IPs (`dns_resolved_ip_info`), and mismatch flags (`dns_response_mismatch`).
- **Mismatch Detection** – Alerts when different DNS servers return different IPs for the same domain.
- **Pre‑configured Stack** – Includes Prometheus alerting rules and a Grafana dashboard.
- **Dockerized** – Run everything with a single `docker-compose up` command.

## Quick Start

```bash
git clone https://github.com/younesmod/dns-monitor.git
cd dns-monitor
docker-compose up -d
```

- **DNS Exporter**: `http://localhost:9253/metrics`
- **Prometheus**: `http://localhost:9090`
- **Grafana**: `http://localhost:3000` (default: `admin/admin`)

## Configuration

Edit `DNS_SERVERS` and `TEST_DOMAINS` in [`exporter/dns_exporter.py`](exporter/dns_exporter.py):

```python
DNS_SERVERS = {
    "shecan": "5.200.200.200",
    "403_1": "217.218.127.127",
    "403_2": "217.218.155.155",
}

TEST_DOMAINS = [
    # Iranian
    "digikala.com", "aparat.com", "snapp.ir", "divar.ir", "irna.ir",
    # International
    "google.com", "github.com", "cloudflare.com", "amazon.com", "wikipedia.org",
]
```

Scrape interval, query timeout, and exporter port can be adjusted via environment variables or directly in the script.

## Local Development

```bash
cd exporter
pip install -r requirements.txt
python dns_exporter.py
```

## Cleanup

```bash
docker-compose down -v
```

## License

MIT © [Younes Modaresian](https://github.com/younesmod)
