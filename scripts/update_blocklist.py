#!/usr/bin/env python3
import os
import re
import random
import socket
import json
import urllib.parse
import urllib.request
import ssl
from concurrent.futures import ThreadPoolExecutor, as_completed
from html.parser import HTMLParser

# Configuración
BLOCKLIST_FILE = "GamesBlockList.txt"
KEYWORDS_FILE = "keywords.txt"
MAX_NEW_DOMAINS = 150
TIMEOUT_SECONDS = 3.0  # Timeout ágil por petición
MAX_WORKERS_SEARCH = 12  # Hilos simultáneos para buscar por palabras clave
MAX_WORKERS_VERIFY = 20  # Hilos simultáneos para inspeccionar candidatos por HTTP/HTTPS

VALID_TLDS = (
    ".com", ".net", ".org", ".io", ".games", ".online", ".fun", ".site",
    ".app", ".xyz", ".top", ".me", ".play", ".gg", ".game", ".cc", ".club",
    ".es", ".co", ".uk", ".de", ".fr", ".ru", ".br", ".us", ".win", ".ws", ".network", ".dev"
)

# Plataformas de hosting compartido donde NO debemos consolidar al apex domain
SHARED_HOSTING_PLATFORMS = (
    "gitlab.io", "github.io", "bitbucket.io", "firebaseapp.com",
    "cloudfront.net", "softgames.de", "googlehosted.com", "pages.dev"
)

# Huellas dactilares de motores de juegos JS / SDKs / Eaglercraft WebSockets / Opticraft / Canvas en código cliente
JS_GAME_FOOTPRINTS = [
    r"unitywebgl", r"phaser", r"pixi\.js", r"godot", r"construct[23]?",
    r"turbowarp", r"createjs", r"poki-sdk", r"crazygames-sdk", r"gamedistribution",
    r"playcanvas", r"cocos2d", r"game-container", r"gameframe", r"game_frame",
    r"game-iframe", r"game_canvas", r"canvas-container",
    r"eaglercraft", r"eagler", r"wss://", r"ws://", r"_eaglercraftX", r"eaglercraftX",
    r"opticraft", r"teavm", r"minecraftweb", r"webminecraft", r"stickman"
]

GAME_TEXT_INDICATORS = [
    "juego", "juegos", "game", "games", "play online", "unblocked", "free online",
    "juegos gratis", "juegos online", "juego gratis", "html5 games", "browser game",
    "eaglercraft", "minecraft 1.8", "minecraft 1.2", "eaglercraftx", "web minecraft", "opticraft",
    "minecraft server", "servidor minecraft", "server ip", "stickman"
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

def get_root_domain(domain):
    """Saca el dominio raíz (apex domain) respetando plataformas compartidas"""
    if any(shared in domain for shared in SHARED_HOSTING_PLATFORMS):
        return domain
        
    parts = domain.split('.')
    if len(parts) <= 2:
        return domain
        
    if len(parts) >= 3 and parts[-2] in ['co', 'com', 'org', 'net', 'edu', 'gov', 'poki-gdn', 'poki-cdn'] and len(parts[-1]) <= 3:
        return '.'.join(parts[-3:])
    return '.'.join(parts[-2:])

def load_existing_domains():
    if not os.path.exists(BLOCKLIST_FILE):
        return set()
    raw_domains = set()
    with open(BLOCKLIST_FILE, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip().lower()
            if line and not line.startswith("#"):
                clean = line.lstrip("|").rstrip("^").strip()
                if clean.startswith("www."):
                    clean = clean[4:]
                raw_domains.add(clean)
    return raw_domains

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

def generate_keyword_variations(keyword):
    variations = {keyword}
    
    if "-" in keyword:
        variations.add(keyword.replace("-", " "))
        variations.add(keyword.replace("-", ""))
    
    if "juegos" in keyword and len(keyword) > 6:
        variations.add(keyword.replace("juegos", "juegos "))
    if "games" in keyword and len(keyword) > 5:
        variations.add(keyword.replace("games", " games"))
    if "unblocked" in keyword and len(keyword) > 9:
        variations.add(keyword.replace("unblocked", "unblocked "))
        
    return [v.strip() for v in variations if v.strip()]

# --- MÓDULOS DE BÚSQUEDA ---

def search_duckduckgo_organic(keyword):
    found = set()
    kw_variations = generate_keyword_variations(keyword)
    
    # Generar Dorks avanzados y combinaciones profundas para extraer hasta 100 resultados por término
    queries = []
    for kv in kw_variations:
        queries.extend([
            f"{kv} juegos online",
            f"{kv} unblocked games",
            f"play {kv} free online",
            f"site:.io {kv}",
            f"site:.games {kv}",
            f"site:.win {kv}",
            f"inurl:unblocked {kv}",
            f"intitle:game {kv}"
        ])
    
    # Shuffle dinámico para que no traiga siempre los mismos primeros 10 resultados
    random.shuffle(queries)
    headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0"}

    for query_str in queries[:10]:
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

def search_startpage_organic(keyword):
    found = set()
    url = "https://www.startpage.com/sp/search"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    kw_variations = generate_keyword_variations(keyword)
    queries = [f"{kv} juegos gratis" for kv in kw_variations] + [f"unblocked {kv} games" for kv in kw_variations]
    random.shuffle(queries)

    for q in queries[:4]:
        data = urllib.parse.urlencode({"query": q, "cat": "web"}).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers=headers)
        try:
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS, context=context) as response:
                html = response.read().decode('utf-8', errors='ignore')
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

def search_subdomains_dns(keyword):
    found = set()
    clean_kw = keyword.replace("-", "").replace(" ", "")
    
    tlds_to_query = [".com", ".net", ".org", ".io", ".win"]
    for tld in tlds_to_query:
        dns_url = f"https://api.hackertarget.com/hostsearch/?q={urllib.parse.quote(clean_kw)}{tld}"
        try:
            req = urllib.request.Request(dns_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
                text = resp.read().decode('utf-8', errors='ignore')
                for line in text.split('\n'):
                    if ',' in line:
                        host = line.split(',')[0].strip()
                        dom = clean_domain(host)
                        if dom and dom not in WHITELIST and any(dom.endswith(vtld) for vtld in VALID_TLDS):
                            found.add(dom)
        except Exception:
            pass
    return found

# --- MÓDULO 4: Shodan InternetDB API (Sin requerir API Key) ---
def search_shodan_internetdb(domain):
    """Consulta la API pública libre de Shodan por la IP del dominio para detectar puertos de juegos (25565, 19132) o etiquetas 'videogame'"""
    try:
        ip = socket.gethostbyname(domain)
        shodan_url = f"https://internetdb.shodan.io/{ip}"
        req = urllib.request.Request(shodan_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            data = json.loads(resp.read().decode('utf-8', errors='ignore'))
            ports = data.get('ports', [])
            tags = data.get('tags', [])
            hostnames = data.get('hostnames', [])
            
            # Detectar puerto estándar de Minecraft Java (25565), Bedrock (19132) o tag videogame
            if 25565 in ports or 19132 in ports or 'videogame' in tags:
                return True, hostnames
    except Exception:
        pass
    return False, []

def process_single_keyword(kw):
    res = set()
    res.update(search_duckduckgo_organic(kw))
    res.update(search_startpage_organic(kw))
    res.update(search_subdomains_dns(kw))
    return res

def is_game_website(domain):
    if domain in WHITELIST or any(domain.endswith("." + w) for w in WHITELIST):
        return False

    if any(non_game in domain for non_game in ["clinical", "medical", "appliance", "hospital", "pharma"]):
        return False

    if any(domain.startswith(prefix) for prefix in ADMIN_SUBDOMAIN_PREFIXES):
        return False

    known_game_bases = [
        "poki.com", "crazygames.com", "minijuegos.com", "y8.com", "friv.com",
        "poki-cdn.com", "poki-gdn.com", "haxball.com", "stumbleguys.com",
        "eaglercraft.win", "eaglercraft.com", "eaglercraftx.com", "opticraft.com", "webmc.com", "minelatino.com", "stickmanhookgame.org"
    ]
    for base in known_game_bases:
        if domain.endswith("." + base) or domain == base:
            if not any(admin in domain for admin in ["jira.", "admin.", "corp.", "office."]):
                return True

    # 1. Consulta Shodan InternetDB libre por puerto 25565 (Minecraft Java) / 19132 (Bedrock)
    is_mc_shodan, shodan_hosts = search_shodan_internetdb(domain)
    if is_mc_shodan:
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
                
                html = resp.read(35000).decode('utf-8', errors='ignore')
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

def verify_single_candidate(domain, existing_domains):
    root_dom = get_root_domain(domain)
    if root_dom in existing_domains or domain in existing_domains:
        return None
    
    if is_game_website(domain):
        return (domain, root_dom)
    return None

def main():
    print("[*] Cargando dominios existentes y palabras clave...")
    existing_domains = load_existing_domains()
    keywords = load_keywords()
    
    print(f"[*] Total dominios existentes (consolidados): {len(existing_domains)}")
    print(f"[*] Palabras clave a procesar: {len(keywords)}")
    
    # Aleatorizar el orden de palabras clave en cada ejecución nocturna
    random.shuffle(keywords)
    
    candidate_domains = set()
    
    print(f"[*] Rastreando candidatos en paralelo con {MAX_WORKERS_SEARCH} hilos concurrentes...")
    with ThreadPoolExecutor(max_workers=MAX_WORKERS_SEARCH) as executor:
        future_to_kw = {executor.submit(process_single_keyword, kw): kw for kw in keywords}
        for future in as_completed(future_to_kw):
            try:
                res = future.result()
                candidate_domains.update(res)
            except Exception:
                pass
    
    print(f"[*] Candidatos únicos totales encontrados: {len(candidate_domains)}")
    
    to_verify = [
        d for d in candidate_domains 
        if get_root_domain(d) not in existing_domains and d not in existing_domains
    ]
    print(f"[*] Candidatos nuevos a inspeccionar (filtrados previos): {len(to_verify)}")
    
    new_domains = []
    
    print(f"[*] Verificando contenido HTML5/JS y Shodan InternetDB en paralelo con {MAX_WORKERS_VERIFY} hilos concurrentes...")
    with ThreadPoolExecutor(max_workers=MAX_WORKERS_VERIFY) as executor:
        future_to_dom = {executor.submit(verify_single_candidate, dom, existing_domains): dom for dom in to_verify}
        for future in as_completed(future_to_dom):
            if len(new_domains) >= MAX_NEW_DOMAINS:
                break
            try:
                res = future.result()
                if res:
                    domain, root_dom = res
                    if root_dom not in existing_domains:
                        print(f"  [+] Confirmado sitio de juegos / Shodan MC: {domain} -> Consolidando a: {root_dom}")
                        new_domains.append(root_dom)
                        existing_domains.add(root_dom)
            except Exception:
                pass

    if new_domains:
        print(f"\n[+] Agregando {len(new_domains)} dominios principales consolidados a {BLOCKLIST_FILE}...")
        all_domains = sorted(list(existing_domains))
        with open(BLOCKLIST_FILE, "w", encoding="utf-8") as f:
            for dom in all_domains:
                f.write(f"||{dom}^\n")
        print(f"[+] Archivo de lista de bloqueo actualizado exitosamente con sintaxis AdGuard Home ({len(new_domains)} añadidos).")
    else:
        print("\n[-] No se encontraron nuevos dominios para agregar hoy.")

if __name__ == "__main__":
    main()
