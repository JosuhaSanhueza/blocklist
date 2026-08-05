#!/usr/bin/env python3
import os
import re
import urllib.parse
import urllib.request
import ssl

# Configuración
BLOCKLIST_FILE = "GamesBlockList.txt"
KEYWORDS_FILE = "keywords.txt"
MAX_NEW_DOMAINS = 150
TIMEOUT_SECONDS = 4

VALID_TLDS = (
    ".com", ".net", ".org", ".io", ".games", ".online", ".fun", ".site",
    ".app", ".xyz", ".top", ".me", ".play", ".gg", ".game", ".cc", ".club",
    ".es", ".co", ".uk", ".de", ".fr", ".ru", ".br", ".us"
)

GAME_INDICATORS = [
    "juego", "juegos", "game", "games", "play", "online", "free", "gratis",
    "arcade", "unblocked", "html5", "flash", "poki", "y8", "friv", "crazygames",
    "minijuegos", "roblox", "minecraft", "haxball"
]

WHITELIST = {
    "google.com", "youtube.com", "wikipedia.org", "github.com", "microsoft.com",
    "apple.com", "amazon.com", "facebook.com", "twitter.com", "instagram.com",
    "reddit.com", "linkedin.com", "store.steampowered.com", "twitch.tv",
    "discord.com", "fandom.com", "steamcommunity.com", "epicgames.com",
    "duckduckgo.com", "bing.com", "yahoo.com", "cloudflare.com"
}

def load_existing_domains():
    if not os.path.exists(BLOCKLIST_FILE):
        return set()
    with open(BLOCKLIST_FILE, "r", encoding="utf-8", errors="ignore") as f:
        return {line.strip().lower() for line in f if line.strip() and not line.startswith("#")}

def load_keywords():
    if not os.path.exists(KEYWORDS_FILE):
        return []
    with open(KEYWORDS_FILE, "r", encoding="utf-8", errors="ignore") as f:
        return [line.strip().lower() for line in f if line.strip() and not line.startswith("#")]

def clean_domain(domain):
    domain = domain.lower().strip()
    domain = re.sub(r"^https?://", "", domain)
    domain = re.sub(r"^www\.", "", domain)
    domain = domain.split("/")[0].split(":")[0]
    return domain

def discover_subdomains_and_variants(keyword):
    """Descubre subdominios y dominios usando servicios de DNS hostsearch públicos de alta velocidad"""
    found = set()
    
    # 1. API pública de resolución DNS HostSearch
    url = f"https://api.hackertarget.com/hostsearch/?q={urllib.parse.quote(keyword)}.com"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            text = resp.read().decode('utf-8', errors='ignore')
            for line in text.split('\n'):
                if ',' in line:
                    host = line.split(',')[0].strip()
                    dom = clean_domain(host)
                    if dom and any(dom.endswith(tld) for tld in VALID_TLDS):
                        found.add(dom)
    except Exception:
        pass
        
    # 2. Generar patrones directos de subdominios y espejos comunes (ej: friv2, friv3, unblocked-friv)
    for i in range(1, 10):
        found.add(f"{keyword}{i}.com")
        found.add(f"unblocked-{keyword}.com")
        found.add(f"play-{keyword}.com")
        found.add(f"{keyword}-games.com")
        found.add(f"{keyword}.io")
        found.add(f"{keyword}.games")
        found.add(f"{keyword}.online")

    return found

def is_game_website(domain):
    if domain in WHITELIST or any(domain.endswith("." + w) for w in WHITELIST):
        return False

    # Si el propio nombre de dominio contiene palabras clave de juegos conocidas
    for kw in ["friv", "geometrydash", "minijuegos", "eaglecraft", "stumbleguys", "haxball", "poki", "y8", "crazygames", "unblocked"]:
        if kw in domain:
            return True

    # Verificación por HTTP
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    url = f"http://{domain}"
    try:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS, context=context) as resp:
            html = resp.read(20000).decode('utf-8', errors='ignore').lower()
            matches = sum(1 for indicator in GAME_INDICATORS if indicator in html)
            return matches >= 1
    except Exception:
        return False

def main():
    print("[*] Cargando dominios existentes y palabras clave...")
    existing_domains = load_existing_domains()
    keywords = load_keywords()
    
    print(f"[*] Total dominios existentes: {len(existing_domains)}")
    print(f"[*] Palabras clave a procesar: {len(keywords)}")
    
    candidate_domains = set()
    for kw in keywords:
        print(f"[*] Buscando candidatos para: '{kw}'...")
        results = discover_subdomains_and_variants(kw)
        candidate_domains.update(results)
    
    print(f"[*] Candidatos únicos generados: {len(candidate_domains)}")
    
    new_domains = []
    for domain in candidate_domains:
        if len(new_domains) >= MAX_NEW_DOMAINS:
            print(f"[*] Se alcanzó el límite diario de {MAX_NEW_DOMAINS} dominios nuevos.")
            break
            
        if domain in existing_domains:
            continue
            
        print(f"[*] Verificando: '{domain}'...")
        if is_game_website(domain):
            print(f"  [+] Confirmado como sitio de juegos: {domain}")
            new_domains.append(domain)
            existing_domains.add(domain)
        else:
            print(f"  [-] Rechazado: {domain}")
            
    if new_domains:
        print(f"\n[+] Agregando {len(new_domains)} dominios nuevos a {BLOCKLIST_FILE}...")
        all_domains = sorted(list(existing_domains))
        with open(BLOCKLIST_FILE, "w", encoding="utf-8") as f:
            for dom in all_domains:
                f.write(dom + "\n")
        print(f"[+] Archivo de lista de bloqueo actualizado exitosamente ({len(new_domains)} añadidos).")
    else:
        print("\n[-] No se encontraron nuevos dominios para agregar.")

if __name__ == "__main__":
    main()
