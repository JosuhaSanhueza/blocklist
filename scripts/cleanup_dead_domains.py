#!/usr/bin/env python3
import os
import socket
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

    if "$document" in line_clean or "/*" in line_clean:
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
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS, context=context) as resp:
                if resp.status < 500:
                    return rule, True
        except Exception:
            continue

    # Última chance: resolución DNS. Si el dominio ni siquiera resuelve, se considera muerto.
    try:
        socket.gethostbyname(domain)
        return rule, True
    except Exception:
        pass

    return rule, False

def main():
    if not os.path.exists(BLOCKLIST_FILE):
        print(f"[ERROR] {BLOCKLIST_FILE} no existe.")
        return

    with open(BLOCKLIST_FILE, "r", encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]

    total_initial = len(lines)
    print(f"[*] Verificando accesibilidad de {total_initial} reglas (HTTP/HTTPS/DNS)...")

    rules = sorted(set(lines))
    active_rules = []
    dead_rules = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_rule = {executor.submit(is_domain_accessible, r): r for r in rules}
        for future in as_completed(future_to_rule):
            rule, alive = future.result()
            if alive:
                active_rules.append(rule)
            else:
                dead_rules.append(rule)

    active_rules = sorted(active_rules)

    if dead_rules:
        print(f"[-] Eliminando {len(dead_rules)} dominios muertos (sin respuesta HTTP/HTTPS ni DNS):")
        for r in sorted(dead_rules):
            print(f"    - {r}")
        with open(BLOCKLIST_FILE, "w", encoding="utf-8") as f:
            for r in active_rules:
                f.write(f"{r}\n")
    else:
        print("[+] No se encontraron dominios muertos.")

    # Generar versión GamesBlockList_hosts.txt para OPNsense / Unbound / Hosts (solo dominios puros)
    with open(HOSTS_FILE, "w", encoding="utf-8") as f:
        f.write("# --- GamesBlockList (Formato Estándar Hosts / OPNsense Unbound) ---\n")
        for r in active_rules:
            if not ("$document" in r or "/*" in r):
                domain = r.lstrip("|").rstrip("^")
                f.write(f"0.0.0.0 {domain}\n")

    print(f"[+] Verificación exitosa:")
    print(f"  - Dominios procesados: {total_initial}")
    print(f"  - Dominios activos restantes: {len(active_rules)}")
    print(f"  - Generado archivo multiplataforma Hosts: {HOSTS_FILE}")

if __name__ == "__main__":
    main()
