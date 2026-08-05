#!/usr/bin/env python3
import os
import re
import urllib.parse
import urllib.request
import ssl
from html.parser import HTMLParser

# Configuración
BLOCKLIST_FILE = "GamesBlockList.txt"
KEYWORDS_FILE = "keywords.txt"
MAX_NEW_DOMAINS = 150
TIMEOUT_SECONDS = 5

VALID_TLDS = (
    ".com", ".net", ".org", ".io", ".games", ".online", ".fun", ".site",
    ".app", ".xyz", ".top", ".me", ".play", ".gg", ".game", ".cc", ".club",
    ".es", ".co", ".uk", ".de", ".fr", ".ru", ".br", ".us"
)

# Palabras obligatorias que identifican un portal de juegos online en HTML/Metadatos
STRICT_GAME_INDICATORS = [
    "juegos gratis", "juegos online", "free online games", "play online",
    "unblocked games", "html5 games", "browser games", "juegos de",
    "play free", "juegos html5", "game portal", "online games"
]

WHITELIST = {
    "google.com", "youtube.com", "wikipedia.org", "github.com", "microsoft.com",
    "apple.com", "amazon.com", "facebook.com", "twitter.com", "instagram.com",
    "reddit.com", "linkedin.com", "store.steampowered.com", "twitch.tv",
    "discord.com", "fandom.com", "steamcommunity.com", "epicgames.com",
    "duckduckgo.com", "bing.com", "yahoo.com", "cloudflare.com"
}

class MetaTitleParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_title = False
        self.title = ""
        self.meta_text = ""

    def handle_starttag(self, tag, attrs):
        if tag.lower() == 'title':
            self.in_title = True
        elif tag.lower() == 'meta':
            attrs_dict = {k.lower(): v.lower() for k, v in attrs if k and v}
            if attrs_dict.get('name') in ['description', 'keywords']:
                self.meta_text += " " + attrs_dict.get('content', '')

    def handle_endtag(self, tag):
        if tag.lower() == 'title':
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title += data

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
    """Genera variantes específicas asociadas a la keyword"""
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
        
    # 2. Generar patrones específicos de clones
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
    """Validación rigurosa por contenido HTML/Metadata para eliminar falsos positivos"""
    if domain in WHITELIST or any(domain.endswith("." + w) for w in WHITELIST):
        return False

    # Evitar sitios corporativos/empresariales conocidos por nombres comunes (ej: slopeclinical)
    if "clinical" in domain or "medical" in domain or "appliance" in domain or "store" in domain:
        return False

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    url = f"http://{domain}"
    try:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS, context=context) as resp:
            content_type = resp.headers.get('Content-Type', '')
            if 'text/html' not in content_type:
                return False
            
            html = resp.read(30000).decode('utf-8', errors='ignore')
            parser = MetaTitleParser()
            parser.feed(html)
            
            combined_metadata = f"{parser.title.lower()} {parser.meta_text.lower()}"
            
            # 1. Comprobación estricta de meta título/descripción
            for indicator in STRICT_GAME_INDICATORS:
                if indicator in combined_metadata:
                    return True
            
            # 2. Verificación de etiquetas típicas de portales HTML5 (canvas/game iframe/arcade)
            if "<canvas" in html.lower() or "game-container" in html.lower() or "iframe" in html.lower() and "game" in html.lower():
                if any(kw in combined_metadata or kw in html.lower() for kw in ["game", "juego", "play", "poki", "friv", "crazygames"]):
                    return True
                    
            return False
    except Exception:
        # Si el sitio no responde HTTP o da timeout, NO LO AGREGAMOS (evita sitios basura/caídos/dominios estacionados)
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
            
        print(f"[*] Verificando de forma estricta: '{domain}'...")
        if is_game_website(domain):
            print(f"  [+] Confirmado como sitio de juegos: {domain}")
            new_domains.append(domain)
            existing_domains.add(domain)
        else:
            print(f"  [-] Rechazado (No es juego o inactivo): {domain}")
            
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
