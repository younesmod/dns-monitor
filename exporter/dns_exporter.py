#!/usr/bin/env python3
"""
DNS Monitor Exporter
Monitors DNS servers by querying test domains and exposing Prometheus metrics.
"""

import time
import logging
import dns.resolver
import dns.exception
from prometheus_client import start_http_server, Gauge, Info
from prometheus_client.core import CollectorRegistry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# ─── Configuration ────────────────────────────────────────────────────────────

DNS_SERVERS = {
    "shecan":    "5.200.200.200",
    "403_1":     "217.218.127.127",
    "403_2":     "217.218.155.155",
}

# 5 Iranian + 5 International domains
TEST_DOMAINS = [
    # Iranian
    "digikala.com",
    "aparat.com",
    "snapp.ir",
    "divar.ir",
    "irna.ir",
    # International
    "google.com",
    "github.com",
    "cloudflare.com",
    "amazon.com",
    "wikipedia.org",
]

SCRAPE_INTERVAL = 30   # seconds
QUERY_TIMEOUT   = 5    # seconds per DNS query
EXPORTER_PORT   = 9253

# ─── Prometheus Metrics ───────────────────────────────────────────────────────

dns_up = Gauge(
    "dns_server_up",
    "DNS server reachability (1=up, 0=down)",
    ["dns_name", "dns_ip"]
)

dns_query_success = Gauge(
    "dns_query_success",
    "Whether DNS query succeeded (1=success, 0=failure)",
    ["dns_name", "dns_ip", "domain"]
)

dns_response_time_seconds = Gauge(
    "dns_response_time_seconds",
    "DNS query response time in seconds",
    ["dns_name", "dns_ip", "domain"]
)

dns_resolved_ip = Gauge(
    "dns_resolved_ip_hash",
    "Hash of the first resolved IP (used for mismatch detection)",
    ["dns_name", "dns_ip", "domain"]
)

dns_resolved_ip_info = Gauge(
    "dns_resolved_ip_info",
    "Resolved IP address stored as label (1 always)",
    ["dns_name", "dns_ip", "domain", "resolved_ip"]
)

dns_response_mismatch = Gauge(
    "dns_response_mismatch",
    "1 if DNS servers return different IPs for this domain",
    ["domain"]
)

# ─── Core Logic ───────────────────────────────────────────────────────────────

def query_dns(server_ip: str, domain: str) -> dict:
    """
    Query a specific DNS server for a domain.
    Returns dict with: success, response_time, resolved_ips
    """
    resolver = dns.resolver.Resolver(configure=False)
    resolver.nameservers = [server_ip]
    resolver.timeout   = QUERY_TIMEOUT
    resolver.lifetime  = QUERY_TIMEOUT

    start = time.monotonic()
    try:
        answer = resolver.resolve(domain, "A")
        elapsed = time.monotonic() - start
        ips = sorted([rr.address for rr in answer])
        return {
            "success":      True,
            "response_time": elapsed,
            "resolved_ips": ips,
            "first_ip":     ips[0] if ips else "",
        }
    except dns.exception.Timeout:
        elapsed = time.monotonic() - start
        logger.warning(f"Timeout querying {server_ip} for {domain}")
        return {"success": False, "response_time": elapsed, "resolved_ips": [], "first_ip": ""}
    except dns.resolver.NXDOMAIN:
        elapsed = time.monotonic() - start
        logger.warning(f"NXDOMAIN from {server_ip} for {domain}")
        return {"success": False, "response_time": elapsed, "resolved_ips": [], "first_ip": "NXDOMAIN"}
    except Exception as e:
        elapsed = time.monotonic() - start
        logger.error(f"Error querying {server_ip} for {domain}: {e}")
        return {"success": False, "response_time": elapsed, "resolved_ips": [], "first_ip": ""}


def simple_ip_hash(ip_str: str) -> float:
    """
    Convert an IP string to a simple numeric hash for Prometheus Gauge.
    e.g. '142.250.185.46' → numeric value derived from octets
    """
    if not ip_str or ip_str in ("NXDOMAIN", ""):
        return 0.0
    try:
        parts = ip_str.split(".")
        return float(
            int(parts[0]) * 16777216 +
            int(parts[1]) * 65536 +
            int(parts[2]) * 256 +
            int(parts[3])
        )
    except Exception:
        return -1.0


def collect_metrics():
    """
    Main collection loop: query all DNS servers for all domains,
    update all Prometheus metrics, detect mismatches.
    """
    logger.info("Starting metrics collection cycle...")

    # results[domain][dns_name] = first_ip
    results: dict[str, dict[str, str]] = {d: {} for d in TEST_DOMAINS}

    for dns_name, dns_ip in DNS_SERVERS.items():
        server_alive = False

        for domain in TEST_DOMAINS:
            result = query_dns(dns_ip, domain)

            # Per-query metrics
            dns_query_success.labels(dns_name=dns_name, dns_ip=dns_ip, domain=domain).set(
                1 if result["success"] else 0
            )
            dns_response_time_seconds.labels(dns_name=dns_name, dns_ip=dns_ip, domain=domain).set(
                result["response_time"]
            )

            first_ip = result["first_ip"]
            results[domain][dns_name] = first_ip

            # Clear previous ip_info labels for this combo, then set new one
            # We always set the metric with resolved_ip label so Grafana can read it
            resolved_label = first_ip if first_ip else "N/A"
            dns_resolved_ip_info.labels(
                dns_name=dns_name, dns_ip=dns_ip,
                domain=domain, resolved_ip=resolved_label
            ).set(1)

            dns_resolved_ip.labels(dns_name=dns_name, dns_ip=dns_ip, domain=domain).set(
                simple_ip_hash(first_ip)
            )

            if result["success"]:
                server_alive = True

        # Server-level up/down
        dns_up.labels(dns_name=dns_name, dns_ip=dns_ip).set(1 if server_alive else 0)
        logger.info(f"DNS {dns_name} ({dns_ip}) → {'UP' if server_alive else 'DOWN'}")

    # ── Mismatch detection ──────────────────────────────────────────────────
    for domain, server_results in results.items():
        unique_ips = set(
            ip for ip in server_results.values()
            if ip and ip not in ("", "NXDOMAIN")
        )
        # Mismatch: more than one distinct IP returned across servers
        mismatch = 1 if len(unique_ips) > 1 else 0
        dns_response_mismatch.labels(domain=domain).set(mismatch)
        if mismatch:
            logger.warning(f"MISMATCH detected for {domain}: {server_results}")

    logger.info("Collection cycle complete.")


# ─── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info(f"Starting DNS Exporter on port {EXPORTER_PORT}")
    start_http_server(EXPORTER_PORT)
    logger.info(f"Monitoring {len(DNS_SERVERS)} DNS servers × {len(TEST_DOMAINS)} domains")

    while True:
        try:
            collect_metrics()
        except Exception as e:
            logger.error(f"Collection error: {e}", exc_info=True)
        time.sleep(SCRAPE_INTERVAL)
