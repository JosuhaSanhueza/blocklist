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
TIMEOUT_SECONDS = 4

VALID_TLDS = (
    ".com", ".net", ".org", ".io", ".games", ".online", ".fun", ".site",
    ".app", ".xyz", ".top", ".me", ".play", ".gg", ".game", ".cc", ".club",
    ".es", ".co", ".uk", ".de", ".fr", ".ru", ".br", ".us"
)

# Huellas dactilares de motores de juegos JS / SDKs / Canvas en código cliente
JS_GAME_FOOTPRINTS = [
    r"unitywebgl", r"phaser", r"pixi\.js", r"godot", r"construct[23]?",
    r"turbowarp", r"createjs", r"poki-sdk", r"crazygames-sdk", r"gamedistribution",
    r"playcanvas", r"cocos2d", r"game-container", r"gameframe", r"game_frame",
    r"game-iframe", r"game_canvas", r"canvas-container"
]

GAME_TEXT_INDICATORS = [
    "juego", "juegos", "game", "games", "play online", "unblocked", "free online",
    "juegos gratis", "juegos online", "juego gratis", "html5 games", "browser game"
]

WHITELIST = {
    "google.com", "youtube.com", "wikipedia.org", "github.com", "microsoft.com",
    "apple.com", "amazon.com", "facebook.com", "twitter.com", "instagram.com",
    "reddit.com", "linkedin.com", "store.steampowered.com", "twitch.tv",
    "discord.com", "fandom.com", "steamcommunity.com", "epicgames.com",
    "duckduckgo.com", "bing.com", "yahoo.com", "cloudflare.com", "startpage.com"
}

ADMIN_SUBDOMAIN_PREFIXES = (
    "mail.", "webmail.", "cpanel.", "cpcalendars.", "cpcontacts.", "jira.",
    "auth.", "authorize.", "billing.", "careers.", "blog.", "docs.", "status.",
    "autodiscover.", "admin.", "mx0.", "smtp.", "relay."
)

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

# --- MÓDULO 1: DuckDuckGo Organic Search ---
def search_duckduckgo_organic(keyword):
    found = set()
    queries = [
        f"{keyword} juegos online",
        f"{keyword} unblocked games",
        f"play {keyword} free online",
        f"site:.io {keyword}",
        f"site:.games {keyword}"
    ]
    headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0"}

    for query_str in queries:
        query = urllib.parse.quote(query_str)
        url = f"https://html.duckduckgo.com/html/?q={query}"
        req = urllib.request.Request(url, headers=headers)
        try:
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS, context=context) as response:
                html = response.read().decode('utf-8', errors='ignore')
                raw_urls = re.findall(r'uddg=([^&\"]+)', html)
                for u in raw_urls:
                    decoded = urllib.parse.unquote(u)
                    if decoded.startswith('http'):
                        parsed = urllib.parse.urlparse(decoded)
                        dom = clean_domain(parsed.netloc)
                        if dom and dom not in WHITELIST and not any(dom.endswith("." + w) for w in WHITELIST):
                            if any(dom.endswith(tld) for tld in VALID_TLDS):
                                found.add(dom)
        except Exception:
            pass

    return found

# --- MÓDULO 2: Startpage Privacy Search Engine ---
def search_startpage_organic(keyword):
    """Extrae resultados adicionales sin rastreo a través de Startpage POST search"""
    found = set()
    url = "https://www.startpage.com/sp/search"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    queries = [
        f"{keyword} juegos gratis",
        f"unblocked {keyword} games"
    ]
    
    for query_str in queries:
        data = urllib.parse.urlencode({"query": query_str, "cat": "web"}).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers=headers)
        try:
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS, context=context) as response:
                html = response.read().decode('utf-8', errors='ignore')
                # Enlaces de Startpage result-link
                links = re.findall(r'href=\"(https?://[^\"]+)\"\s+class=\"[^\"]*result-link', html)
                for href in links:
                    parsed = urllib.parse.urlparse(href)
                    dom = clean_domain(parsed.netloc)
                    if dom and dom not in WHITELIST and not any(dom.endswith("." + w) for w in WHITELIST):
                        if any(dom.endswith(tld) for tld in VALID_TLDS):
                            found.add(dom)
        except Exception:
            pass
            
    return found

# --- MÓDULO 3: DNS HostSearch Subdomain Discovery ---
def search_subdomains_dns(keyword):
    found = set()
    dns_url = f"https://api.hackertarget.com/hostsearch/?q={urllib.parse.quote(keyword)}.com"
    try:
        req = urllib.request.Request(dns_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            text = resp.read().decode('utf-8', errors='ignore')
            for line in text.split('\n'):
                if ',' in line:
                    host = line.split(',')[0].strip()
                    dom = clean_domain(host)
                    if dom and dom not in WHITELIST and any(dom.endswith(tld) for tld in VALID_TLDS):
                        found.add(dom)
    except Exception:
        pass
    return found

def discover_all_candidates(keyword):
    candidates = set()
    # Ejecutar los 3 módulos complementarios
    candidates.update(search_duckduckgo_organic(keyword))
    candidates.update(search_startpage_organic(keyword))
    candidates.update(search_subdomains_dns(keyword))
    return candidates

def is_game_website(domain):
    if domain in WHITELIST or any(domain.endswith("." + w) for w in WHITELIST):
        return False

    if any(non_game in domain for non_game in ["clinical", "medical", "appliance", "hospital", "pharma"]):
        return False

    if any(domain.startswith(prefix) for prefix in ADMIN_SUBDOMAIN_PREFIXES):
        return False

    known_game_bases = ["poki.com", "crazygames.com", "minijuegos.com", "y8.com", "friv.com", "poki-cdn.com", "poki-gdn.com", "haxball.com", "stumbleguys.com"]
    for base in known_game_bases:
        if domain.endswith("." + base) or domain == base:
            if any(game_sub in domain for game_sub in ["game", "play", "assets", "cdn", "v.", "builds", "dev", "static"]):
                return True

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    for scheme in ["https://", "http://"]:
        url = f"{scheme}{domain}"
        try:
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS, context=context) as resp:
                content_type = resp.headers.get('Content-Type', '')
                if 'text/html' not in content_type:
                    return False
                
                html = resp.read(40000).decode('utf-8', errors='ignore')
                parser = MetaTitleParser()
                parser.feed(html)
                
                combined_metadata = f"{parser.title.lower()} {parser.meta_text.lower()}"
                html_lower = html.lower()

                has_js_footprint = any(re.search(fp, html_lower) for fp in JS_GAME_FOOTPRINTS)
                has_canvas_or_iframe = "<canvas" in html_lower or ("<iframe" in html_lower and "game" in html_lower)
                text_matches = sum(1 for indicator in GAME_TEXT_INDICATORS if indicator in combined_metadata or indicator in html_lower[:3000])

                if (has_js_footprint or has_canvas_or_iframe) and text_matches >= 1:
                    return True
                elif text_matches >= 2:
                    return True

                return False
        except Exception:
            continue
            
    return False

def main():
    print("[*] Cargando dominios existentes y palabras clave...")
    existing_domains = load_existing_domains()
    keywords = load_keywords()
    
    print(f"[*] Total dominios existentes: {len(existing_domains)}")
    print(f"[*] Palabras clave a procesar: {len(keywords)}")
    
    candidate_domains = set()
    for kw in keywords:
        print(f"[*] Rastrenado con Módulos (DuckDuckGo + Startpage + Subdominios DNS) para: '{kw}'...")
        results = discover_all_candidates(kw)
        candidate_domains.update(results)
    
    print(f"[*] Candidatos únicos totales encontrados: {len(candidate_domains)}")
    
    new_domains = []
    for domain in candidate_domains:
        if len(new_domains) >= MAX_NEW_DOMAINS:
            print(f"[*] Se alcanzó el límite diario de {MAX_NEW_DOMAINS} dominios nuevos.")
            break
            
        if domain in existing_domains:
            continue
            
        print(f"[*] Inspeccionando: '{domain}'...")
        if is_game_website(domain):
            print(f"  [+] Confirmado sitio o subdominio de juegos: {domain}")
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
