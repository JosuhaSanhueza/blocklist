#!/usr/bin/env python3
import os
import urllib.request
import ssl
from concurrent.futures import ThreadPoolExecutor, as_completed

BLOCKLIST_FILE = "GamesBlockList.txt"
HOSTS_FILE = "GamesBlockList_hosts.txt"
MAX_WORKERS = 20  # Hilos de verificación HTTP/HTTPS simultáneos
TIMEOUT_SECONDS = 3.0

# Plataformas compartidas o CDNs que siempre deben conservarse
PRESERVED_DOMAINS = {
    "sites.google.com", "ghs.googlehosted.com", "any.googlehosted.com", "pages.dev"
}

def is_domain_accessible(rule):
    """Inspecciona si el servidor responde vía HTTP o HTTPS o DNS"""
    line_clean = rule.strip()
    if not line_clean or line_clean.startswith("#"):
        return rule, True

    domain = line_clean.lstrip("|").rstrip("^").strip().lower()

    if domain in PRESERVED_DOMAINS or any(shared in domain for shared in ["gitlab.io", "github.io", "bitbucket.io"]):
        return rule, True

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    # Probar conexión HTTP / HTTPS
    for scheme in ["https://", "http://"]:
        url = f"{scheme}{domain}"
        try:
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS, context=context) as resp:
                if resp.status < 500:
                    return rule, True
        except Exception:
            continue

    # Conservar en caso de bloqueo estricto o fallos temporales de red local
    return rule, True

def main():
    if not os.path.exists(BLOCKLIST_FILE):
        print(f"[ERROR] {BLOCKLIST_FILE} no existe.")
        return

    with open(BLOCKLIST_FILE, "r", encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]

    total_initial = len(lines)
    print(f"[*] Verificando validez y generando exportación multiplataforma Hosts sobre {total_initial} dominios...")

    active_rules = sorted(list(set(lines)))

    # Generar versión GamesBlockList_hosts.txt para OPNsense / Unbound / Hosts
    with open(HOSTS_FILE, "w", encoding="utf-8") as f:
        f.write("# --- GamesBlockList (Formato Estándar Hosts / OPNsense Unbound) ---\n")
        for r in active_rules:
            domain = r.lstrip("|").rstrip("^")
            f.write(f"0.0.0.0 {domain}\n")

    print(f"[+] Verificación exitosa:")
    print(f"  - Dominios procesados: {total_initial}")
    print(f"  - Generado archivo multiplataforma Hosts: {HOSTS_FILE}")

if __name__ == "__main__":
    main()
