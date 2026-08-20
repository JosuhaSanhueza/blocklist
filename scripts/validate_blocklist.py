#!/usr/bin/env python3
import sys
import os
import re

BLOCKLIST_FILE = "GamesBlockList.txt"
# La Whitelist solo protege infraestructura esencial de internet (buscadores/redes sociales), NUNCA sitios de juegos
WHITELIST = {
    "google.com", "youtube.com", "wikipedia.org", "github.com", "microsoft.com",
    "apple.com", "amazon.com", "facebook.com", "twitter.com", "instagram.com",
    "reddit.com", "linkedin.com", "twitch.tv", "discord.com", "fandom.com",
    "duckduckgo.com", "bing.com", "yahoo.com", "cloudflare.com", "startpage.com"
}

def validate_blocklist():
    if not os.path.exists(BLOCKLIST_FILE):
        print(f"[ERROR] Archivo {BLOCKLIST_FILE} no encontrado.")
        sys.exit(1)

    errors = []
    domains_seen = set()

    with open(BLOCKLIST_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    print(f"[*] Validando sintaxis e integridad de {len(lines)} reglas en {BLOCKLIST_FILE}...")

    for line_num, line in enumerate(lines, 1):
        line_clean = line.strip()
        if not line_clean or line_clean.startswith("#"):
            continue

        # Permitir reglas de filtrado de URL / Path de AdGuard (ej: ||sites.google.com/view/totalgameinn/*$document)
        if "$document" in line_clean or "/*" in line_clean:
            if not line_clean.startswith("||"):
                errors.append(f"Línea {line_num}: Regla de Path inválida '{line_clean}'. Debe iniciar con '||'.")
            continue

        # 1. Validar sintaxis AdGuard Home ||domain^
        if not (line_clean.startswith("||") and line_clean.endswith("^")):
            errors.append(f"Línea {line_num}: Sintaxis inválida '{line_clean}'. Debe ser '||dominio^'.")
            continue

        domain = line_clean[2:-1].lower()

        # 2. Verificar duplicados
        if domain in domains_seen:
            errors.append(f"Línea {line_num}: Dominio duplicado '{domain}'.")
        domains_seen.add(domain)

        # 3. Validar presencia accidental de Whitelist (solo servicios no-juegos)
        if domain in WHITELIST or any(domain.endswith("." + w) for w in WHITELIST):
            errors.append(f"Línea {line_num}: CRÍTICO - Dominio infraestructura en Whitelist detectado '{domain}'.")

        # 4. Validar formato de caracteres de dominio
        if not re.match(r'^[a-z0-9.-]+\.[a-z]{2,10}$', domain):
            errors.append(f"Línea {line_num}: Formato de dominio no válido '{domain}'.")

    if errors:
        print("\n[!] Se encontraron los siguientes errores en la validación:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)
    else:
        print("[+] Validaciones exitosas: Sintaxis 100% correcta, sin duplicados y Whitelist respetada.")
        sys.exit(0)

if __name__ == "__main__":
    validate_blocklist()
