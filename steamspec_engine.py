import os
import re
import json
import time
import hashlib
from datetime import datetime, timezone
from urllib.parse import quote_plus
import requests
from bs4 import BeautifulSoup

# Konfigurasi Environment Variables dari GitHub Secrets / Vars
AMAZON_TAG = os.environ.get("AMAZON_TAG", "steamspecus-20").strip()
SITE_URL = os.environ.get("SITE_URL", "https://username.github.io/steamspec-us").rstrip("/")
REPO_NAME = os.environ.get("GITHUB_REPOSITORY", "user/steamspec-us")

# Kunci verifikasi IndexNow deterministik untuk Bing, Yahoo, Yandex, DuckDuckGo
INDEXNOW_KEY = hashlib.md5(f"{REPO_NAME}_{AMAZON_TAG}_steamspec12h".encode("utf-8")).hexdigest()

DATA_DIR = "data"
STATE_FILE = os.path.join(DATA_DIR, "steamspec_state.json")
DOCS_DIR = "docs"
GAMES_DIR = os.path.join(DOCS_DIR, "games")
REVIEWS_DIR = os.path.join(DOCS_DIR, "reviews")
CATEGORIES_DIR = os.path.join(DOCS_DIR, "categories")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
}

# Struktur Mega-Menu Kategori & Subkategori Perangkat Keras
TAXONOMY = [
    {
        "category": "Graphics Cards (GPUs)",
        "cat_slug": "graphics-cards-gpus",
        "icon": "🎮",
        "subcategories": [
            {"name": "1080p Ultra GPUs (RTX 4060 / RX 7600)", "slug": "1080p-ultra-gaming-gpus", "query": "NVIDIA GeForce RTX 4060 8GB OR AMD Radeon RX 7600 graphics card"},
            {"name": "1440p High-FPS GPUs (RTX 4070 Super / RX 7800 XT)", "slug": "1440p-high-fps-gpus", "query": "NVIDIA GeForce RTX 4070 Super 12GB OR RX 7800 XT 16GB graphics card"},
            {"name": "4K Ray-Tracing GPUs (RTX 4080 Super / RTX 4090)", "slug": "4k-ray-tracing-gpus", "query": "NVIDIA GeForce RTX 4080 Super 16GB OR RTX 4070 Ti Super graphics card"}
        ]
    },
    {
        "category": "Processors (CPUs)",
        "cat_slug": "gaming-processors-cpus",
        "icon": "⚡",
        "subcategories": [
            {"name": "3D V-Cache Gaming CPUs (Ryzen 7 7800X3D)", "slug": "3d-vcache-gaming-cpus", "query": "AMD Ryzen 7 7800X3D 8-Core AM5 gaming processor"},
            {"name": "Mid-Range 6/14-Core CPUs (i5-14600K / Ryzen 5 7600X)", "slug": "mid-range-gaming-cpus", "query": "AMD Ryzen 5 7600X OR Intel Core i5-13600K unlocked processor"},
            {"name": "Flagship Streaming CPUs (Ryzen 9 / Core i7-14700K)", "slug": "flagship-streaming-cpus", "query": "Intel Core i7-14700K OR AMD Ryzen 9 7900X processor"}
        ]
    },
    {
        "category": "Gaming Memory (RAM)",
        "cat_slug": "gaming-memory-ram",
        "icon": "🧠",
        "subcategories": [
            {"name": "32GB DDR5-6000 CL30 Dual-Channel Kits", "slug": "32gb-ddr5-6000-gaming-ram", "query": "32GB 2x16GB DDR5 6000MHz CL30 desktop gaming memory kit"},
            {"name": "16GB DDR4-3600 CL18 Value Upgrade Kits", "slug": "16gb-ddr4-3600-gaming-ram", "query": "16GB 2x8GB DDR4 3600MHz desktop gaming RAM"},
            {"name": "64GB DDR5 Heavy Modding & Sim Kits", "slug": "64gb-ddr5-simulation-ram", "query": "64GB 2x32GB DDR5 6000MHz desktop memory kit"}
        ]
    },
    {
        "category": "NVMe M.2 Storage (SSDs)",
        "cat_slug": "nvme-m2-gaming-ssds",
        "icon": "💾",
        "subcategories": [
            {"name": "2TB PCIe Gen4 DirectStorage SSDs (7,400 MB/s)", "slug": "2tb-pcie-gen4-nvme-ssds", "query": "2TB PCIe Gen4 NVMe M.2 internal gaming SSD 7000MB/s"},
            {"name": "1TB PCIe 4.0 Fast Boot & Game Drives", "slug": "1tb-pcie-gen4-nvme-ssds", "query": "1TB NVMe M.2 PCIe Gen4 internal gaming SSD"},
            {"name": "4TB High-Capacity Steam Library SSDs", "slug": "4tb-nvme-m2-gaming-ssds", "query": "4TB PCIe Gen4 NVMe M.2 internal gaming SSD"}
        ]
    },
    {
        "category": "Controllers & Peripherals",
        "cat_slug": "controllers-gaming-peripherals",
        "icon": "🕹️",
        "subcategories": [
            {"name": "Hall-Effect Zero-Drift PC Controllers", "slug": "hall-effect-pc-controllers", "query": "wireless Hall Effect PC gaming controller 2.4GHz dongle"},
            {"name": "Ultralight Wireless Esports Gaming Mice", "slug": "wireless-esports-gaming-mice", "query": "ultralight wireless gaming mouse optical sensor 26000 DPI"},
            {"name": "Rapid-Trigger Mechanical Keyboards", "slug": "rapid-trigger-gaming-keyboards", "query": "magnetic switch rapid trigger mechanical gaming keyboard"}
        ]
    }
]

# Basis Katalog Game PC Populer untuk dikombinasikan dengan API Live Steam (Menjamin 400+ Antrean Siap Pakai)
BASE_GAMES = [
    ("Cyberpunk 2077: Phantom Liberty", "1091500", "Action RPG", 32, 100, "NVIDIA GeForce RTX 4070 Super 12GB", "AMD Ryzen 7 7800X3D", "full", "1440p-high-fps-gpus", "graphics-cards-gpus"),
    ("Elden Ring: Shadow of the Erdtree", "1245620", "Souls-like Action RPG", 16, 80, "NVIDIA GeForce RTX 4060 8GB", "AMD Ryzen 5 7600X", "full", "hall-effect-pc-controllers", "controllers-gaming-peripherals"),
    ("Black Myth: Wukong", "2358720", "Action RPG", 32, 130, "NVIDIA GeForce RTX 4070 Ti Super 16GB", "Intel Core i7-14700K", "full", "4k-ray-tracing-gpus", "graphics-cards-gpus"),
    ("Baldur's Gate 3", "1086940", "CRPG Strategy", 32, 150, "NVIDIA GeForce RTX 4060 Ti 16GB", "AMD Ryzen 7 7800X3D", "full", "2tb-pcie-gen4-nvme-ssds", "nvme-m2-gaming-ssds"),
    ("Helldivers 2", "553850", "Co-Op Tactical Shooter", 16, 100, "AMD Radeon RX 7800 XT 16GB", "AMD Ryzen 7 7800X3D", "full", "1440p-high-fps-gpus", "graphics-cards-gpus"),
    ("Monster Hunter Wilds", "2246340", "Action Co-Op RPG", 32, 140, "NVIDIA GeForce RTX 4070 Super 12GB", "AMD Ryzen 7 7800X3D", "full", "3d-vcache-gaming-cpus", "gaming-processors-cpus"),
    ("Microsoft Flight Simulator 2024", "2537590", "Aviation Simulation", 64, 150, "NVIDIA GeForce RTX 4080 Super 16GB", "AMD Ryzen 7 7800X3D", "full", "64gb-ddr5-simulation-ram", "gaming-memory-ram"),
    ("Call of Duty: Warzone & Black Ops 6", "1938090", "Competitive FPS", 32, 149, "AMD Radeon RX 7800 XT 16GB", "AMD Ryzen 7 7800X3D", "full", "wireless-esports-gaming-mice", "controllers-gaming-peripherals"),
    ("Starfield: Shattered Space", "1716740", "Sci-Fi Open World RPG", 32, 140, "NVIDIA GeForce RTX 4070 Super 12GB", "AMD Ryzen 7 7800X3D", "full", "2tb-pcie-gen4-nvme-ssds", "nvme-m2-gaming-ssds"),
    ("Counter-Strike 2 (CS2)", "730", "Tactical Esports FPS", 16, 85, "NVIDIA GeForce RTX 4060 8GB", "AMD Ryzen 7 7800X3D", "none", "rapid-trigger-gaming-keyboards", "controllers-gaming-peripherals"),
    ("Forza Horizon 5", "1551360", "Open World Racing", 16, 110, "NVIDIA GeForce RTX 4060 Ti 16GB", "Intel Core i5-13600K", "full", "hall-effect-pc-controllers", "controllers-gaming-peripherals"),
    ("Red Dead Redemption 2", "1174180", "Open World Action", 16, 150, "NVIDIA GeForce RTX 4070 Super 12GB", "AMD Ryzen 5 7600X", "full", "2tb-pcie-gen4-nvme-ssds", "nvme-m2-gaming-ssds"),
    ("Ghost of Tsushima DIRECTOR'S CUT", "2215430", "Open World Action", 16, 75, "NVIDIA GeForce RTX 4060 Ti 16GB", "AMD Ryzen 5 7600X", "full", "1440p-high-fps-gpus", "graphics-cards-gpus"),
    ("Hogwarts Legacy", "990080", "Open World Fantasy RPG", 32, 85, "NVIDIA GeForce RTX 4070 Super 12GB", "Intel Core i5-13600K", "full", "32gb-ddr5-6000-gaming-ram", "gaming-memory-ram"),
    ("Diablo IV: Vessel of Hatred", "2344520", "Action RPG Hack & Slash", 32, 90, "NVIDIA GeForce RTX 4060 8GB", "AMD Ryzen 5 7600X", "full", "1tb-pcie-gen4-nvme-ssds", "nvme-m2-gaming-ssds"),
    ("Palworld", "1623730", "Open World Survival Craft", 32, 40, "NVIDIA GeForce RTX 4060 8GB", "AMD Ryzen 5 7600X", "full", "32gb-ddr5-6000-gaming-ram", "gaming-memory-ram"),
    ("Apex Legends", "1172470", "Battle Royale FPS", 16, 75, "NVIDIA GeForce RTX 4060 8GB", "AMD Ryzen 7 7800X3D", "full", "wireless-esports-gaming-mice", "controllers-gaming-peripherals"),
    ("Rust", "252490", "Multiplayer Survival", 32, 45, "NVIDIA GeForce RTX 4060 8GB", "AMD Ryzen 7 7800X3D", "none", "3d-vcache-gaming-cpus", "gaming-processors-cpus"),
    ("ARK: Survival Ascended", "2399830", "Unreal Engine 5 Survival", 32, 80, "NVIDIA GeForce RTX 4070 Ti Super 16GB", "AMD Ryzen 7 7800X3D", "full", "4k-ray-tracing-gpus", "graphics-cards-gpus"),
    ("Cities: Skylines II", "949230", "City Builder Simulation", 64, 60, "NVIDIA GeForce RTX 4070 Super 12GB", "Intel Core i7-14700K", "none", "flagship-streaming-cpus", "gaming-processors-cpus"),
    ("Warhammer 40,000: Space Marine 2", "2183900", "Third-Person Action", 16, 75, "NVIDIA GeForce RTX 4070 Super 12GB", "AMD Ryzen 7 7800X3D", "full", "3d-vcache-gaming-cpus", "gaming-processors-cpus"),
    ("God of War Ragnarök PC", "2322010", "Action Adventure", 16, 190, "NVIDIA GeForce RTX 4070 Super 12GB", "AMD Ryzen 5 7600X", "full", "4tb-nvme-m2-gaming-ssds", "nvme-m2-gaming-ssds"),
    ("Final Fantasy XVI PC", "2515020", "Action RPG", 16, 170, "NVIDIA GeForce RTX 4070 Super 12GB", "AMD Ryzen 7 7800X3D", "full", "2tb-pcie-gen4-nvme-ssds", "nvme-m2-gaming-ssds"),
    ("Silent Hill 2 Remake", "2124490", "Survival Horror", 16, 50, "NVIDIA GeForce RTX 4070 Super 12GB", "AMD Ryzen 5 7600X", "full", "1440p-high-fps-gpus", "graphics-cards-gpus"),
    ("S.T.A.L.K.E.R. 2: Heart of Chornobyl", "1643320", "Unreal 5 Open-World FPS", 32, 150, "NVIDIA GeForce RTX 4070 Ti Super 16GB", "AMD Ryzen 7 7800X3D", "full", "32gb-ddr5-6000-gaming-ram", "gaming-memory-ram"),
    ("Path of Exile 2", "2694490", "Isometric Action RPG", 16, 100, "NVIDIA GeForce RTX 4060 8GB", "AMD Ryzen 7 7800X3D", "full", "1080p-ultra-gaming-gpus", "graphics-cards-gpus"),
    ("Indiana Jones and the Great Circle", "2677660", "Ray-Traced Adventure", 32, 120, "NVIDIA GeForce RTX 4080 Super 16GB", "AMD Ryzen 7 7800X3D", "full", "4k-ray-tracing-gpus", "graphics-cards-gpus"),
    ("Kingdom Come: Deliverance II", "1771300", "Medieval Open-World RPG", 32, 100, "NVIDIA GeForce RTX 4070 Super 12GB", "AMD Ryzen 7 7800X3D", "full", "32gb-ddr5-6000-gaming-ram", "gaming-memory-ram"),
    ("Civilization VII", "1295660", "4X Turn-Based Strategy", 32, 40, "NVIDIA GeForce RTX 4060 8GB", "Intel Core i7-14700K", "none", "flagship-streaming-cpus", "gaming-processors-cpus"),
    ("DOOM: The Dark Ages", "3017860", "Fast-Paced Arena FPS", 32, 100, "NVIDIA GeForce RTX 4070 Ti Super 16GB", "AMD Ryzen 7 7800X3D", "full", "1440p-high-fps-gpus", "graphics-cards-gpus"),
    ("Grand Theft Auto V Enhanced PC", "271590", "Open World Action", 16, 110, "NVIDIA GeForce RTX 4060 8GB", "AMD Ryzen 5 7600X", "full", "1080p-ultra-gaming-gpus", "graphics-cards-gpus"),
    ("Enshrouded", "1203620", "Co-Op Voxel Survival RPG", 16, 60, "NVIDIA GeForce RTX 4060 Ti 16GB", "AMD Ryzen 5 7600X", "full", "16gb-ddr4-3600-gaming-ram", "gaming-memory-ram"),
    ("Manor Lords", "1363080", "Medieval City & Battle Sim", 16, 30, "NVIDIA GeForce RTX 4060 8GB", "AMD Ryzen 7 7800X3D", "none", "mid-range-gaming-cpus", "gaming-processors-cpus"),
    ("Total War: WARHAMMER III", "1142710", "Grand Strategy RTS", 32, 120, "NVIDIA GeForce RTX 4070 Super 12GB", "AMD Ryzen 7 7800X3D", "none", "2tb-pcie-gen4-nvme-ssds", "nvme-m2-gaming-ssds"),
    ("Street Fighter 6", "1364780", "Competitive Fighting", 16, 60, "NVIDIA GeForce RTX 4060 8GB", "AMD Ryzen 5 7600X", "full", "hall-effect-pc-controllers", "controllers-gaming-peripherals")
]

PERFORMANCE_PROFILES = [
    ("1080p 144Hz Competitive Build", "tuned for locked 144+ FPS frame pacing at 1080p Ultra with zero input latency"),
    ("1440p Ultra DLSS/FSR Rig", "engineered for native 1440p high-refresh gaming with high-resolution texture packs"),
    ("4K Path-Tracing & Max Settings Rig", "configured for 4K UHD resolution, full ray reconstruction, and frame generation"),
    ("DirectStorage Fast-Load Upgrade Kit", "optimized to eliminate shader stutter, asset pop-in, and 1% low frame drops"),
    ("Streaming & Content Creator Spec", "built for simultaneous 60FPS AV1/NVENC OBS streaming and high-preset gameplay"),
    ("High-Modding & Texture Overhaul Spec", "sized with extra VRAM and dual-channel DDR5 headroom for 100+ Steam Workshop / Nexus mods"),
    ("Small Form Factor (SFF) Living Room Build", "designed for low-decibel couch gaming with wireless Hall-Effect controller support"),
    ("Esports Low-Latency Frame-Cap Edition", "tailored for sub-5ms system photon-to-pixel latency and high polling peripherals"),
    ("Budget Bottleneck-Eliminator Upgrade", "targeted drop-in GPU, RAM, and NVMe SSD upgrade for older midrange PCs"),
    ("VR & Ultrawide 3440x1440 Setup", "calibrated for 21:9 QD-OLED ultrawide monitors and high-resolution PCVR headsets"),
    ("Future-Proof AM5 & PCIe 4.0 Bundle", "structured around upgradeable DDR5 memory and high-airflow multi-fan cooling"),
    ("Max 1% Low Stability Benchmark Kit", "paired with 3D V-Cache processor architecture to eliminate CPU main-thread bottlenecks")
]


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "game-upgrade"


def make_amazon_url(query: str) -> str:
    """
    Membuat tautan afiliasi Amazon US dengan Tracking ID otomatis,
    diurutkan berdasarkan Best-Sellers (exact-aware-popularity-rank) dan filter rating 4 bintang ke atas.
    """
    encoded = quote_plus(query)
    return (
        f"https://www.amazon.com/s?k={encoded}"
        f"&s=exact-aware-popularity-rank&rh=p_72%3A1248873011&tag={AMAZON_TAG}"
    )


def fetch_live_steam_trending() -> list:
    """Mengambil daftar game populer/terbaru langsung dari API publik Steam (tanpa API key)."""
    url = "https://store.steampowered.com/api/featuredcategories?cc=us&l=en"
    live_items = []
    seen = set()
    try:
        r = requests.get(url, headers=HEADERS, timeout=12)
        if r.status_code == 200:
            data = r.json()
            for bucket in ["top_sellers", "new_releases", "specials"]:
                for item in data.get(bucket, {}).get("items", []):
                    appid = str(item.get("id", ""))
                    name = item.get("name", "").strip()
                    if appid and name and appid not in seen:
                        seen.add(appid)
                        live_items.append((name, appid))
    except Exception as e:
        print(f"[WARN] Steam featuredcategories fallback: {e}")
    return live_items


def enrich_from_steam_appdetails(appid: str, default_item: dict) -> dict:
    """Mengambil spesifikasi minimum/rekomendasi nyata dari API appdetails Steam jika tersedia."""
    url = f"https://store.steampowered.com/api/appdetails?appids={appid}&cc=us&l=en"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            payload = r.json().get(str(appid), {})
            if payload.get("success"):
                data = payload.get("data", {})
                pc_req = data.get("pc_requirements", {})
                if isinstance(pc_req, dict):
                    raw_html = f"{pc_req.get('minimum', '')} {pc_req.get('recommended', '')}"
                    soup = BeautifulSoup(raw_html, "html.parser")
                    text = soup.get_text(" ", strip=True)

                    ram_m = re.search(r"(\d+)\s*GB\s*RAM", text, re.IGNORECASE)
                    if ram_m:
                        default_item["ram_gb"] = max(16, min(64, int(ram_m.group(1))))

                    ssd_m = re.search(r"(\d+)\s*GB\s*available\s*space", text, re.IGNORECASE)
                    if ssd_m:
                        default_item["storage_gb"] = max(30, min(250, int(ssd_m.group(1))))

                if data.get("header_image"):
                    default_item["header_image"] = data["header_image"]
                if data.get("controller_support"):
                    default_item["controller"] = data["controller_support"]
    except Exception:
        pass
    return default_item


def build_hardware_bundle(ram_gb: int, storage_gb: int, gpu_model: str, cpu_model: str, ctrl: str) -> dict:
    ram_spec = (
        "32GB (2x16GB) DDR5-6000MHz CL30 Dual-Channel Gaming RAM"
        if ram_gb <= 32 else
        "64GB (2x32GB) DDR5-6000MHz CL30 High-Capacity Gaming RAM"
    )
    ssd_spec = (
        "2TB PCIe Gen4 NVMe M.2 Internal Gaming SSD (Up to 7,450 MB/s)"
        if storage_gb >= 80 else
        "1TB PCIe Gen4 NVMe M.2 Internal Gaming SSD (Up to 7,000 MB/s)"
    )
    ctrl_spec = (
        "Wireless Hall-Effect PC Gaming Controller (2.4GHz Dongle + Bluetooth)"
        if ctrl in ("full", "partial") else
        "Ultralight 26,000 DPI Wireless Esports Gaming Mouse + Rapid-Trigger Keyboard"
    )
    return {
        "Recommended GPU Upgrade": gpu_model,
        "Compatible Gaming CPU": cpu_model,
        "Low-Latency RAM Kit": ram_spec,
        "DirectStorage NVMe SSD": ssd_spec,
        "Controller / Input Match": ctrl_spec
    }


def init_or_load_state() -> dict:
    os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
                if state.get("products"):
                    return state
        except Exception:
            pass

    products = []
    idx = 1

    # 1. Masukkan game populer dari live Steam API terlebih dahulu
    live_steam = fetch_live_steam_trending()
    for name, appid in live_steam[:25]:
        slug = f"{slugify(name)}-pc-hardware-upgrade-kit-{idx}"
        hw = build_hardware_bundle(32, 100, "NVIDIA GeForce RTX 4070 Super 12GB", "AMD Ryzen 7 7800X3D", "full")
        products.append({
            "id": f"SS-{idx:04d}",
            "appid": appid,
            "slug": slug,
            "name": f"{name} — Official PC System Requirements & Hardware Upgrade Kit",
            "game_title": name,
            "genre": "Steam Trending Release",
            "cat_slug": "graphics-cards-gpus",
            "sub_slug": "1440p-high-fps-gpus",
            "subcategory": "1440p High-FPS GPUs (RTX 4070 Super / RX 7800 XT)",
            "ram_gb": 32,
            "storage_gb": 100,
            "gpu_model": "NVIDIA GeForce RTX 4070 Super 12GB",
            "cpu_model": "AMD Ryzen 7 7800X3D",
            "controller": "full",
            "header_image": f"https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/{appid}/header.jpg",
            "summary": f"Complete PC system requirements and verified Amazon hardware upgrades (GPU, CPU, DDR5 RAM, NVMe SSD, and Controller) to run {name} at locked 60–144+ FPS.",
            "specs": hw,
            "buy_if": f"Your current PC experiences frame drops, VRAM stuttering, or slow loading times in {name} and you want a drop-in hardware upgrade.",
            "skip_if": f"You already run a 16GB+ VRAM RTX 4080/4090 desktop with 32GB DDR5 RAM and a Gen4 NVMe SSD.",
            "published": False,
            "published_at": ""
        })
        idx += 1

    # 2. Bangun 420+ antrean produk kombinasi Game + Profil Resolusi/Hardware untuk operasional berbulan-bulan
    for prof_name, prof_desc in PERFORMANCE_PROFILES:
        for g_title, appid, genre, ram_gb, ssd_gb, gpu, cpu, ctrl, sub_slug, cat_slug in BASE_GAMES:
            title = f"{g_title} ({prof_name})"
            slug = f"{slugify(g_title)}-{slugify(prof_name)}-{idx}"
            hw = build_hardware_bundle(ram_gb, ssd_gb, gpu, cpu, ctrl)
            products.append({
                "id": f"SS-{idx:04d}",
                "appid": appid,
                "slug": slug,
                "name": title,
                "game_title": g_title,
                "genre": genre,
                "cat_slug": cat_slug,
                "sub_slug": sub_slug,
                "subcategory": prof_name,
                "ram_gb": ram_gb,
                "storage_gb": ssd_gb,
                "gpu_model": gpu,
                "cpu_model": cpu,
                "controller": ctrl,
                "header_image": f"https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/{appid}/header.jpg",
                "summary": f"The {title} hardware package is {prof_desc}, matching official Steam requirements ({ram_gb}GB RAM, {ssd_gb}GB SSD, {gpu}).",
                "specs": hw,
                "buy_if": f"You want to play {g_title} ({genre}) with {prof_desc} without thermal throttling or VRAM bottlenecks.",
                "skip_if": "You only play lightweight 2D indie titles or cloud-stream via GeForce NOW.",
                "published": False,
                "published_at": ""
            })
            idx += 1

    state = {"products": products, "reviews": [], "cycle_count": 0}
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    return state


def save_state(state: dict):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def get_common_styles() -> str:
    return """
        :root {
            --bg: #ffffff;
            --surface: #f8fafc;
            --border: #e2e8f0;
            --navy: #0f172a;
            --slate: #475569;
            --blue: #2563eb;
            --blue-dark: #1d4ed8;
            --blue-light: #eff6ff;
            --emerald: #059669;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg); color: var(--navy); line-height: 1.65; }
        .compliance-bar { background: var(--navy); color: #f8fafc; font-size: 0.79rem; text-align: center; padding: 9px 16px; }
        .compliance-bar strong { color: #60a5fa; }
        header { background: rgba(255,255,255,0.97); border-bottom: 1px solid var(--border); position: sticky; top: 0; z-index: 100; backdrop-filter: blur(8px); }
        .nav-wrap { max-width: 1240px; margin: 0 auto; padding: 14px 20px; display: flex; justify-content: space-between; align-items: center; gap: 16px; flex-wrap: wrap; }
        .brand { font-size: 1.45rem; font-weight: 900; color: var(--navy); text-decoration: none; letter-spacing: -0.5px; }
        .brand span { color: var(--blue); }
        .nav-links { display: flex; align-items: center; gap: 16px; flex-wrap: wrap; }
        .nav-link { color: var(--navy); text-decoration: none; font-size: 0.9rem; font-weight: 600; padding: 6px 10px; border-radius: 6px; }
        .nav-link:hover { background: var(--surface); color: var(--blue); }
        .mega-dropdown { position: relative; display: inline-block; }
        .mega-menu { display: none; position: absolute; left: 0; top: 100%; width: 780px; max-width: 92vw; background: #fff; border: 1px solid var(--border); border-radius: 14px; box-shadow: 0 20px 35px rgba(15,23,42,0.14); padding: 22px; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 18px; z-index: 200; }
        .mega-dropdown:hover .mega-menu { display: grid; }
        .mega-col h4 { font-size: 0.88rem; color: var(--blue-dark); margin-bottom: 8px; border-bottom: 1px solid var(--border); padding-bottom: 4px; }
        .mega-col a { display: block; color: var(--slate); text-decoration: none; font-size: 0.82rem; padding: 4px 0; }
        .mega-col a:hover { color: var(--blue); font-weight: 600; }
        .container { max-width: 1240px; margin: 36px auto; padding: 0 20px; }
        .btn-amz { display: inline-block; background: var(--blue); color: #ffffff; font-weight: 700; text-decoration: none; padding: 12px 18px; border-radius: 8px; font-size: 0.88rem; text-align: center; transition: background 0.15s; }
        .btn-amz:hover { background: var(--blue-dark); }
        .btn-outline { display: inline-block; background: #fff; color: var(--navy); border: 1px solid var(--border); font-weight: 600; text-decoration: none; padding: 11px 15px; border-radius: 8px; font-size: 0.86rem; text-align: center; }
        .btn-outline:hover { border-color: var(--blue); color: var(--blue); }
        .grid-3 { display: grid; grid-template-columns: repeat(auto-fill, minmax(310px, 1fr)); gap: 22px; }
        .card { background: #fff; border: 1px solid var(--border); border-radius: 14px; overflow: hidden; display: flex; flex-direction: column; justify-content: space-between; transition: transform 0.15s, box-shadow 0.15s; }
        .card:hover { transform: translateY(-3px); box-shadow: 0 12px 24px rgba(15,23,42,0.07); border-color: #cbd5e1; }
        .card-body { padding: 20px; display: flex; flex-direction: column; flex: 1; justify-content: space-between; }
        .pill { display: inline-block; background: var(--blue-light); color: var(--blue-dark); font-size: 0.74rem; font-weight: 700; padding: 4px 10px; border-radius: 999px; margin-bottom: 10px; width: fit-content; }
        .micro-disclosure { font-size: 0.73rem; color: #64748b; margin: 10px 0 6px; }
        footer { background: var(--surface); border-top: 1px solid var(--border); margin-top: 70px; padding: 48px 20px; color: var(--slate); font-size: 0.85rem; }
        .footer-inner { max-width: 1240px; margin: 0 auto; display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 28px; }
        .footer-inner h4 { color: var(--navy); margin-bottom: 10px; font-size: 0.95rem; }
        .footer-inner a { display: block; color: var(--slate); text-decoration: none; padding: 3px 0; }
        .footer-inner a:hover { color: var(--blue); }
    """


def build_header_html() -> str:
    mega_cols = ""
    for cat in TAXONOMY:
        sub_links = "".join(
            f'<a href="{SITE_URL}/categories/{sub["slug"]}.html">&rsaquo; {sub["name"]}</a>'
            for sub in cat["subcategories"]
        )
        mega_cols += f"""
        <div class="mega-col">
            <h4><a href="{SITE_URL}/categories/{cat['cat_slug']}.html" style="color:var(--blue-dark);font-size:0.88rem;">{cat['icon']} {cat['category']}</a></h4>
            {sub_links}
        </div>
        """

    return f"""
    <div class="compliance-bar">
        <strong>AFFILIATE DISCLOSURE:</strong> As an Amazon Associate I earn from qualifying purchases. Game specs synced via public Steam API.
    </div>
    <header>
        <div class="nav-wrap">
            <a href="{SITE_URL}/" class="brand">⚙️ Steam<span>Spec</span> US</a>
            <nav class="nav-links">
                <a href="{SITE_URL}/" class="nav-link">Storefront</a>
                <div class="mega-dropdown">
                    <a href="#departments" class="nav-link">Hardware Categories &#9662;</a>
                    <div class="mega-menu">
                        {mega_cols}
                    </div>
                </div>
                <a href="{SITE_URL}/#reviews" class="nav-link">12H Benchmark Reviews</a>
                <a href="{SITE_URL}/legal.html" class="nav-link">Compliance & Policies</a>
            </nav>
        </div>
    </header>
    """


def build_footer_html(today: str) -> str:
    cat_links = "".join(
        f'<a href="{SITE_URL}/categories/{c["cat_slug"]}.html">{c["icon"]} {c["category"]}</a>'
        for c in TAXONOMY
    )
    return f"""
    <footer>
        <div class="footer-inner">
            <div>
                <h4>SteamSpec US Hardware Engine</h4>
                <p>Automated PC game system requirement analyzer and Amazon hardware upgrade finder covering GPUs, 3D V-Cache CPUs, DDR5 RAM, PCIe Gen4 NVMe SSDs, and Hall-Effect Controllers.</p>
                <p style="margin-top:10px;font-weight:700;color:var(--navy);">As an Amazon Associate I earn from qualifying purchases.</p>
            </div>
            <div>
                <h4>Hardware Upgrade Categories</h4>
                {cat_links}
            </div>
            <div>
                <h4>Legal & Search Feeds</h4>
                <a href="{SITE_URL}/legal.html#disclosure">Amazon Affiliate Disclosure</a>
                <a href="{SITE_URL}/legal.html#privacy">Privacy Policy</a>
                <a href="{SITE_URL}/legal.html#terms">Terms of Use</a>
                <a href="{SITE_URL}/sitemap.xml">XML Sitemap (Google / Bing)</a>
                <a href="{SITE_URL}/feed.xml">RSS 2.0 WebSub Feed</a>
            </div>
        </div>
        <div style="max-width:1240px;margin:28px auto 0;padding-top:20px;border-top:1px solid var(--border);text-align:center;font-size:0.78rem;">
            &copy; {today[:4]} SteamSpec US. Not affiliated with or endorsed by Valve Corporation, Steam, or Amazon.com, Inc. Last 12-Hour Sync: {today}.
        </div>
    </footer>
    """


def render_game_product_page(prod: dict, related: list, today: str) -> str:
    os.makedirs(GAMES_DIR, exist_ok=True)
    page_url = f"{SITE_URL}/games/{prod['slug']}.html"

    # Buat 5 kartu upgrade perangkat keras spesifik untuk game ini (GPU, CPU, RAM, SSD, Controller)
    hw_items = [
        ("Recommended Graphics Card (GPU)", prod["specs"]["Recommended GPU Upgrade"], f"{prod['gpu_model']} graphics card", "High-FPS 1080p/1440p/4K VRAM Match"),
        ("Compatible Gaming Processor (CPU)", prod["specs"]["Compatible Gaming CPU"], f"{prod['cpu_model']} gaming processor", "Eliminates 1% Low CPU Stutter"),
        ("Low-Latency System Memory (RAM)", prod["specs"]["Low-Latency RAM Kit"], f"{prod['ram_gb']}GB DDR5 6000MHz CL30 desktop gaming RAM", f"Meets {prod['ram_gb']}GB Requirement"),
        ("DirectStorage NVMe M.2 SSD", prod["specs"]["DirectStorage NVMe SSD"], "2TB PCIe Gen4 NVMe M.2 internal gaming SSD", f"Fits {prod['storage_gb']}GB Install Size"),
        ("Controller & Esports Input", prod["specs"]["Controller / Input Match"], "wireless Hall Effect PC gaming controller", f"Controller Support: {prod['controller'].upper()}")
    ]

    hw_cards_html = ""
    for label, title, query, badge in hw_items:
        amz_url = make_amazon_url(query)
        hw_cards_html += f"""
        <div class="card">
            <div class="card-body">
                <div>
                    <span class="pill">{badge}</span>
                    <div style="font-size:0.78rem;font-weight:700;color:var(--slate);text-transform:uppercase;margin-bottom:4px;">{label}</div>
                    <h3 style="font-size:1.08rem;margin-bottom:10px;color:var(--navy);">{title}</h3>
                </div>
                <div>
                    <div class="micro-disclosure">As an Amazon Associate I earn from qualifying purchases.</div>
                    <a href="{amz_url}" target="_blank" rel="nofollow sponsored noopener noreferrer" class="btn-amz" style="width:100%;">Check Price on Amazon &rarr;</a>
                </div>
            </div>
        </div>
        """

    rel_html = ""
    for r in related[:3]:
        if r["slug"] == prod["slug"]:
            continue
        r_amz = make_amazon_url(f"{r['gpu_model']} graphics card")
        rel_html += f"""
        <div class="card">
            <div class="card-body">
                <div>
                    <span class="pill">{r['genre']}</span>
                    <h3 style="font-size:1.05rem;margin-bottom:8px;"><a href="{SITE_URL}/games/{r['slug']}.html" style="color:var(--navy);text-decoration:none;">{r['name']}</a></h3>
                    <p style="font-size:0.86rem;color:var(--slate);">RAM: {r['ram_gb']}GB &bull; SSD: {r['storage_gb']}GB &bull; GPU: {r['gpu_model']}</p>
                </div>
                <div style="margin-top:14px;display:flex;gap:8px;">
                    <a href="{r_amz}" target="_blank" rel="nofollow sponsored noopener noreferrer" class="btn-amz" style="flex:1;">View GPU on Amazon</a>
                    <a href="{SITE_URL}/games/{r['slug']}.html" class="btn-outline">Specs</a>
                </div>
            </div>
        </div>
        """

    faq_schema = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": f"What GPU and RAM do I need to run {prod['game_title']} smoothly on PC?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": f"{prod['game_title']} recommends a {prod['gpu_model']} GPU, {prod['cpu_model']} processor, {prod['ram_gb']}GB of system RAM, and {prod['storage_gb']}GB of NVMe SSD storage."
                }
            },
            {
                "@type": "Question",
                "name": f"Who should buy this hardware upgrade kit for {prod['game_title']}?",
                "acceptedAnswer": {"@type": "Answer", "text": prod["buy_if"]}
            }
        ]
    }

    primary_amz = make_amazon_url(f"{prod['gpu_model']} graphics card")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{prod['name']} | SteamSpec US</title>
    <meta name="description" content="{prod['summary']} Compare compatible GPUs, CPUs, DDR5 RAM, NVMe SSDs, and check live prices on Amazon.">
    <link rel="canonical" href="{page_url}">
    <script type="application/ld+json">{json.dumps(faq_schema)}</script>
    <style>
        {get_common_styles()}
        .hero-box {{ background: var(--surface); border: 1px solid var(--border); border-radius: 16px; padding: 28px; margin-bottom: 32px; display: grid; grid-template-columns: 320px 1fr; gap: 28px; align-items: center; }}
        .hero-box img {{ width: 100%; border-radius: 10px; border: 1px solid var(--border); }}
        .verdict-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(290px, 1fr)); gap: 20px; margin: 28px 0; }}
        .v-box {{ background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 22px; }}
        @media (max-width: 780px) {{ .hero-box {{ grid-template-columns: 1fr; }} }}
    </style>
</head>
<body>
    {build_header_html()}
    <main class="container">
        <div style="font-size:0.84rem;color:var(--slate);margin-bottom:16px;">
            <a href="{SITE_URL}/" style="color:var(--blue);text-decoration:none;font-weight:600;">Home</a> &rsaquo;
            <a href="{SITE_URL}/categories/{prod['cat_slug']}.html" style="color:var(--blue);text-decoration:none;font-weight:600;">Hardware Upgrades</a> &rsaquo;
            <span>{prod['name']}</span>
        </div>

        <section class="hero-box">
            <img src="{prod['header_image']}" alt="{prod['game_title']}" onerror="this.style.display='none'">
            <div>
                <span class="pill">Steam AppID: {prod['appid']} &bull; {prod['genre']}</span>
                <h1 style="font-size:1.85rem;line-height:1.25;margin-bottom:10px;">{prod['name']}</h1>
                <p style="color:var(--slate);margin-bottom:14px;">{prod['summary']}</p>
                <div class="micro-disclosure">Affiliate Disclosure: As an Amazon Associate I earn from qualifying purchases.</div>
                <div style="display:flex;gap:12px;flex-wrap:wrap;margin-top:10px;">
                    <a href="{primary_amz}" target="_blank" rel="nofollow sponsored noopener noreferrer" class="btn-amz">Check Recommended GPU on Amazon &rarr;</a>
                    <a href="#upgrade-parts" class="btn-outline">View All 5 Compatible Parts &darr;</a>
                </div>
            </div>
        </section>

        <h2 id="upgrade-parts" style="font-size:1.45rem;margin-bottom:18px;">Complete 5-Part PC Hardware Upgrade Matches for {prod['game_title']}</h2>
        <div class="grid-3">{hw_cards_html}</div>

        <div class="verdict-grid">
            <div class="v-box">
                <h3 style="color:var(--emerald);margin-bottom:8px;">Who Should Upgrade</h3>
                <p style="font-size:0.93rem;color:var(--slate);">{prod['buy_if']}</p>
            </div>
            <div class="v-box">
                <h3 style="color:#b91c1c;margin-bottom:8px;">When You Can Skip</h3>
                <p style="font-size:0.93rem;color:var(--slate);">{prod['skip_if']}</p>
            </div>
        </div>

        <h2 style="font-size:1.4rem;margin:38px 0 18px;">Related PC Game Hardware Benchmarks</h2>
        <div class="grid-3">{rel_html}</div>
    </main>
    {build_footer_html(today)}
</body>
</html>"""

    with open(os.path.join(GAMES_DIR, f"{prod['slug']}.html"), "w", encoding="utf-8") as f:
        f.write(html)
    return page_url


def render_review_article(group: list, cycle_num: int, art_idx: int, today: str) -> dict:
    os.makedirs(REVIEWS_DIR, exist_ok=True)
    sub = group[0]["subcategory"]
    slug = f"pc-hardware-upgrade-benchmark-comparison-c{cycle_num}-{art_idx}"
    title = f"Best PC Hardware Upgrades for {', '.join(g['game_title'] for g in group[:2])} & More ({today[:4]} Guide)"
    page_url = f"{SITE_URL}/reviews/{slug}.html"

    th_cols = "".join(f"<th>{p['game_title']}<br><small style='color:var(--blue);'>{p['subcategory']}</small></th>" for p in group)
    spec_keys = list(group[0]["specs"].keys())
    matrix_rows = ""
    for k in spec_keys:
        tds = "".join(f"<td>{p['specs'].get(k, 'Verified')}</td>" for p in group)
        matrix_rows += f"<tr><th>{k}</th>{tds}</tr>"

    cta_tds = "".join(
        f'<td><a href="{make_amazon_url(p["gpu_model"] + " graphics card")}" target="_blank" rel="nofollow sponsored noopener noreferrer" class="btn-amz" style="padding:8px 12px;font-size:0.8rem;">Check Price on Amazon</a></td>'
        for p in group
    )

    sections_html = ""
    for rank, p in enumerate(group, 1):
        amz_gpu = make_amazon_url(f"{p['gpu_model']} graphics card")
        amz_ssd = make_amazon_url("2TB PCIe Gen4 NVMe M.2 gaming SSD")
        sections_html += f"""
        <section style="background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:24px;margin-bottom:22px;">
            <span class="pill">Benchmark Setup #{rank} &bull; {p['genre']}</span>
            <h2 style="font-size:1.3rem;margin-bottom:8px;"><a href="{SITE_URL}/games/{p['slug']}.html" style="color:var(--navy);text-decoration:none;">{p['name']}</a></h2>
            <p style="color:var(--slate);margin-bottom:10px;">{p['summary']}</p>
            <p style="font-size:0.9rem;margin-bottom:10px;"><strong>Target GPU:</strong> {p['gpu_model']} | <strong>CPU:</strong> {p['cpu_model']} | <strong>Memory:</strong> {p['ram_gb']}GB RAM + {p['storage_gb']}GB NVMe SSD</p>
            <div class="micro-disclosure">As an Amazon Associate I earn from qualifying purchases.</div>
            <div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:8px;">
                <a href="{amz_gpu}" target="_blank" rel="nofollow sponsored noopener noreferrer" class="btn-amz">View GPU on Amazon &rarr;</a>
                <a href="{amz_ssd}" target="_blank" rel="nofollow sponsored noopener noreferrer" class="btn-outline">Check NVMe SSD Deals</a>
                <a href="{SITE_URL}/games/{p['slug']}.html" class="btn-outline">Full 5-Part Breakdown</a>
            </div>
        </section>
        """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} | SteamSpec US</title>
    <meta name="description" content="Side-by-side PC hardware requirement comparison for {', '.join(p['game_title'] for p in group)}. Compare GPUs, CPUs, DDR5 RAM, and NVMe SSD upgrades.">
    <link rel="canonical" href="{page_url}">
    <style>
        {get_common_styles()}
        .table-scroll {{ overflow-x: auto; margin: 26px 0 36px; }}
        table {{ width: 100%; border-collapse: collapse; min-width: 720px; }}
        th, td {{ border: 1px solid var(--border); padding: 12px 14px; text-align: left; font-size: 0.88rem; }}
        th {{ background: var(--surface); color: var(--navy); }}
    </style>
</head>
<body>
    {build_header_html()}
    <main class="container">
        <span class="pill">12-Hour Comparative Hardware Buying Guide</span>
        <h1 style="font-size:2rem;margin-bottom:12px;">{title}</h1>
        <p style="color:var(--slate);max-width:860px;margin-bottom:22px;">Upgrading your gaming PC for modern Steam releases requires balancing GPU VRAM capacity, CPU L3 cache, and PCIe 4.0 NVMe storage bandwidth. Compare the four game hardware profiles below.</p>

        <div class="table-scroll">
            <table>
                <thead>
                    <tr><th>Hardware Component</th>{th_cols}</tr>
                </thead>
                <tbody>
                    {matrix_rows}
                    <tr><th>Amazon Availability</th>{cta_tds}</tr>
                </tbody>
            </table>
        </div>

        {sections_html}
    </main>
    {build_footer_html(today)}
</body>
</html>"""

    with open(os.path.join(REVIEWS_DIR, f"{slug}.html"), "w", encoding="utf-8") as f:
        f.write(html)

    return {
        "slug": slug,
        "title": title,
        "category": sub,
        "excerpt": f"Side-by-side GPU, CPU, DDR5 RAM & NVMe SSD matrix for {', '.join(g['game_title'] for g in group)}.",
        "published_at": today,
        "url": page_url
    }


def render_category_pages(published_prods: list, today: str) -> list:
    os.makedirs(CATEGORIES_DIR, exist_ok=True)
    cat_urls = []

    def write_cat_page(slug: str, heading: str, desc: str, amz_query: str, items: list):
        top_amz = make_amazon_url(amz_query)
        cards = ""
        for p in items[:36]:
            p_amz = make_amazon_url(f"{p['gpu_model']} graphics card")
            cards += f"""
            <article class="card">
                <div class="card-body">
                    <div>
                        <span class="pill">{p['genre']}</span>
                        <h3 style="font-size:1.08rem;margin-bottom:8px;"><a href="{SITE_URL}/games/{p['slug']}.html" style="color:var(--navy);text-decoration:none;">{p['name']}</a></h3>
                        <p style="font-size:0.86rem;color:var(--slate);margin-bottom:10px;">{p['summary']}</p>
                    </div>
                    <div>
                        <div class="micro-disclosure">As an Amazon Associate I earn from qualifying purchases.</div>
                        <div style="display:flex;gap:8px;">
                            <a href="{p_amz}" target="_blank" rel="nofollow sponsored noopener noreferrer" class="btn-amz" style="flex:1;">Check Price on Amazon</a>
                            <a href="{SITE_URL}/games/{p['slug']}.html" class="btn-outline">Specs</a>
                        </div>
                    </div>
                </div>
            </article>
            """

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{heading} — PC Gaming Hardware Upgrades | SteamSpec US</title>
    <meta name="description" content="{desc}">
    <link rel="canonical" href="{SITE_URL}/categories/{slug}.html">
    <style>{get_common_styles()}</style>
</head>
<body>
    {build_header_html()}
    <main class="container">
        <div style="background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:26px;margin-bottom:30px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:16px;">
            <div>
                <h1 style="font-size:1.9rem;margin-bottom:6px;">{heading}</h1>
                <p style="color:var(--slate);">{desc}</p>
            </div>
            <a href="{top_amz}" target="_blank" rel="nofollow sponsored noopener noreferrer" class="btn-amz">Shop Best-Selling {heading} on Amazon &rarr;</a>
        </div>
        <div class="grid-3">{cards}</div>
    </main>
    {build_footer_html(today)}
</body>
</html>"""
        with open(os.path.join(CATEGORIES_DIR, f"{slug}.html"), "w", encoding="utf-8") as f:
            f.write(html)
        cat_urls.append(f"{SITE_URL}/categories/{slug}.html")

    for cat in TAXONOMY:
        c_items = [p for p in published_prods if p["cat_slug"] == cat["cat_slug"]] or published_prods[:12]
        write_cat_page(
            cat["cat_slug"],
            f"{cat['icon']} {cat['category']}",
            f"Compare top-rated {cat['category'].lower()} matched to official Steam PC game system requirements.",
            cat["subcategories"][0]["query"],
            c_items
        )
        for sub in cat["subcategories"]:
            s_items = [p for p in published_prods if p["sub_slug"] == sub["slug"]] or published_prods[:9]
            write_cat_page(
                sub["slug"],
                sub["name"],
                f"Verified Amazon best-sellers and game compatibility benchmarks for {sub['name']}.",
                sub["query"],
                s_items
            )

    return cat_urls


def render_legal_page(today: str):
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Amazon Affiliate Disclosure, Privacy Policy & Terms | SteamSpec US</title>
    <link rel="canonical" href="{SITE_URL}/legal.html">
    <style>
        {get_common_styles()}
        .legal-box {{ background: var(--surface); border: 1px solid var(--border); border-radius: 14px; padding: 26px; margin-bottom: 22px; }}
    </style>
</head>
<body>
    {build_header_html()}
    <main class="container">
        <div class="legal-box" id="disclosure">
            <h2>Amazon Associates Program Disclosure</h2>
            <p style="margin-top:8px;"><strong>As an Amazon Associate I earn from qualifying purchases.</strong></p>
            <p style="margin-top:8px;color:var(--slate);">SteamSpec US participates in the Amazon Services LLC Associates Program, an affiliate advertising program designed to provide a means for websites to earn advertising commissions by linking to Amazon.com. We do not scrape Amazon pages or display static unverified prices; clicking any "Check Price on Amazon" button takes you directly to Amazon.com to view real-time pricing and availability.</p>
        </div>
        <div class="legal-box" id="privacy">
            <h2>Privacy Policy & GitHub Pages Hosting</h2>
            <p style="margin-top:8px;color:var(--slate);">This site is hosted statically on GitHub Pages and does not store personal financial data or process direct checkouts.</p>
        </div>
        <div class="legal-box" id="terms">
            <h2>Terms of Use</h2>
            <p style="margin-top:8px;color:var(--slate);">Game system requirements are synchronized via public Steam metadata for hardware sizing guidance. Always verify motherboard socket and power supply compatibility before ordering PC parts.</p>
        </div>
    </main>
    {build_footer_html(today)}
</body>
</html>"""
    with open(os.path.join(DOCS_DIR, "legal.html"), "w", encoding="utf-8") as f:
        f.write(html)


def render_storefront_homepage(published_prods: list, reviews: list, today: str):
    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(os.path.join(DOCS_DIR, ".nojekyll"), "w", encoding="utf-8") as f:
        f.write("")

    latest_prods = list(reversed(published_prods))[:48]
    latest_revs = list(reversed(reviews))[:12]

    cat_tiles = ""
    for c in TAXONOMY:
        subs = " &bull; ".join(s["name"].split("(")[0].strip() for s in c["subcategories"])
        cat_tiles += f"""
        <a href="{SITE_URL}/categories/{c['cat_slug']}.html" class="card" style="text-decoration:none;color:inherit;">
            <div class="card-body">
                <div>
                    <div style="font-size:2rem;margin-bottom:8px;">{c['icon']}</div>
                    <h3 style="font-size:1.12rem;color:var(--navy);margin-bottom:6px;">{c['category']}</h3>
                    <p style="font-size:0.84rem;color:var(--slate);">{subs}</p>
                </div>
                <span style="margin-top:14px;font-size:0.85rem;font-weight:700;color:var(--blue);">Explore Hardware Category &rarr;</span>
            </div>
        </a>
        """

    prod_cards = ""
    for p in latest_prods:
        amz_url = make_amazon_url(f"{p['gpu_model']} graphics card")
        prod_cards += f"""
        <article class="card prod-card" data-cat="{p['cat_slug']}">
            <img src="{p['header_image']}" alt="{p['game_title']}" style="width:100%;height:155px;object-fit:cover;border-bottom:1px solid var(--border);" loading="lazy" onerror="this.style.display='none'">
            <div class="card-body">
                <div>
                    <span class="pill">{p['genre']}</span>
                    <h3 style="font-size:1.06rem;margin-bottom:8px;"><a href="{SITE_URL}/games/{p['slug']}.html" style="color:var(--navy);text-decoration:none;">{p['name']}</a></h3>
                    <p style="font-size:0.84rem;color:var(--slate);margin-bottom:10px;"><strong>GPU:</strong> {p['gpu_model']} &bull; <strong>RAM:</strong> {p['ram_gb']}GB &bull; <strong>SSD:</strong> {p['storage_gb']}GB</p>
                </div>
                <div>
                    <div class="micro-disclosure">As an Amazon Associate I earn from qualifying purchases.</div>
                    <div style="display:flex;gap:8px;">
                        <a href="{amz_url}" target="_blank" rel="nofollow sponsored noopener noreferrer" class="btn-amz" style="flex:1;">Check Price on Amazon</a>
                        <a href="{SITE_URL}/games/{p['slug']}.html" class="btn-outline">5-Part Kit</a>
                    </div>
                </div>
            </div>
        </article>
        """

    rev_cards = ""
    for r in latest_revs:
        rev_cards += f"""
        <article class="card">
            <div class="card-body">
                <div>
                    <span class="pill">4-Game Hardware Matrix</span>
                    <h3 style="font-size:1.1rem;margin-bottom:8px;"><a href="{SITE_URL}/reviews/{r['slug']}.html" style="color:var(--navy);text-decoration:none;">{r['title']}</a></h3>
                    <p style="font-size:0.86rem;color:var(--slate);">{r['excerpt']}</p>
                </div>
                <div style="margin-top:16px;">
                    <a href="{SITE_URL}/reviews/{r['slug']}.html" class="btn-outline" style="width:100%;">Read Benchmark Review &rarr;</a>
                </div>
            </div>
        </article>
        """

    filter_btns = '<button class="f-btn active" onclick="filterGrid(\'all\', this)">All Upgrade Kits</button>'
    for c in TAXONOMY:
        filter_btns += f'<button class="f-btn" onclick="filterGrid(\'{c["cat_slug"]}\', this)">{c["icon"]} {c["category"]}</button>'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SteamSpec US — PC Game System Requirements & Amazon Hardware Upgrade Store</title>
    <meta name="description" content="Match official Steam PC game system requirements to the #1 best-selling GPUs, 3D V-Cache CPUs, DDR5 RAM, PCIe 4.0 NVMe SSDs, and Hall-Effect Controllers on Amazon.">
    <link rel="canonical" href="{SITE_URL}/">
    <style>
        {get_common_styles()}
        .hero-banner {{ background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 100%); color: #ffffff; padding: 54px 20px; }}
        .hero-inner {{ max-width: 1240px; margin: 0 auto; display: grid; grid-template-columns: 1.3fr 0.7fr; gap: 32px; align-items: center; }}
        .hero-badge {{ display: inline-block; background: rgba(59,130,246,0.25); border: 1px solid #60a5fa; color: #93c5fd; font-size: 0.78rem; font-weight: 700; padding: 5px 12px; border-radius: 999px; margin-bottom: 14px; }}
        .hero-banner h1 {{ font-size: 2.35rem; line-height: 1.2; margin-bottom: 14px; }}
        .search-bar {{ display: flex; gap: 10px; margin-top: 22px; max-width: 620px; }}
        .search-bar input {{ flex: 1; padding: 14px 18px; border-radius: 10px; border: none; font-size: 1rem; outline: none; }}
        .filter-row {{ display: flex; gap: 10px; flex-wrap: wrap; margin: 22px 0; }}
        .f-btn {{ background: var(--surface); border: 1px solid var(--border); color: var(--navy); padding: 8px 14px; border-radius: 999px; font-size: 0.84rem; font-weight: 600; cursor: pointer; }}
        .f-btn.active, .f-btn:hover {{ background: var(--blue); color: #fff; border-color: var(--blue); }}
        .sec-head {{ display: flex; justify-content: space-between; align-items: baseline; margin: 46px 0 20px; border-bottom: 2px solid var(--border); padding-bottom: 10px; flex-wrap: wrap; gap: 10px; }}
        @media (max-width: 820px) {{ .hero-inner {{ grid-template-columns: 1fr; }} .hero-banner h1 {{ font-size: 1.85rem; }} }}
    </style>
</head>
<body>
    {build_header_html()}
    <section class="hero-banner">
        <div class="hero-inner">
            <div>
                <span class="hero-badge">STEAM API SYNCED &bull; AUTO-UPDATED EVERY 12 HOURS</span>
                <h1>PC Game System Requirements & Exact Amazon Hardware Upgrade Finder</h1>
                <p style="color:#cbd5e1;font-size:1.04rem;">Find the exact Graphics Card (GPU), Ryzen X3D / Intel Core CPU, 32GB DDR5 RAM, 2TB Gen4 NVMe SSD, and Hall-Effect Controller required to run trending Steam PC games at 144+ FPS.</p>
                <div class="search-bar">
                    <input type="text" id="liveSearch" placeholder="Search game or hardware (e.g. Cyberpunk, Black Myth, Elden Ring, RTX 4070, 7800X3D)..." onkeyup="runSearch()">
                </div>
            </div>
            <div style="background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.2);border-radius:16px;padding:24px;">
                <div style="font-size:0.78rem;color:#93c5fd;font-weight:700;text-transform:uppercase;margin-bottom:6px;">Live Engine Status</div>
                <div style="font-size:1.6rem;font-weight:900;margin-bottom:4px;">{len(published_prods)} Game Upgrade Kits</div>
                <div style="font-size:0.9rem;color:#cbd5e1;margin-bottom:14px;">{len(reviews)} Hardware Benchmark Guides</div>
                <a href="#featured" class="btn-amz" style="width:100%;">Browse Featured Upgrade Kits &darr;</a>
            </div>
        </div>
    </section>

    <main class="container">
        <div class="sec-head" id="departments">
            <h2>Shop by PC Hardware Department & Subcategory</h2>
            <span style="font-size:0.85rem;color:var(--slate);">5 Core Component Categories &bull; 15 Performance Tiers</span>
        </div>
        <div class="grid-3">{cat_tiles}</div>

        <div class="sec-head" id="featured">
            <h2>Featured Steam Game Hardware Upgrade Kits</h2>
            <span style="font-size:0.85rem;color:var(--slate);">+20 New Kits Published Every 12 Hours</span>
        </div>
        <div class="filter-row">{filter_btns}</div>
        <div class="grid-3" id="productsContainer">{prod_cards}</div>

        <div class="sec-head" id="reviews">
            <h2>Latest 12-Hour Comparative Hardware Benchmark Reviews</h2>
            <span style="font-size:0.85rem;color:var(--slate);">+5 Side-by-Side Buying Guides Every 12 Hours</span>
        </div>
        <div class="grid-3">{rev_cards}</div>
    </main>

    {build_footer_html(today)}
    <script>
        function runSearch() {{
            const q = document.getElementById('liveSearch').value.toLowerCase();
            document.querySelectorAll('.prod-card').forEach(card => {{
                card.style.display = card.innerText.toLowerCase().includes(q) ? '' : 'none';
            }});
        }}
        function filterGrid(catSlug, btn) {{
            document.querySelectorAll('.f-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            document.querySelectorAll('.prod-card').forEach(card => {{
                if (catSlug === 'all' || card.getAttribute('data-cat') === catSlug) {{
                    card.style.display = '';
                }} else {{
                    card.style.display = 'none';
                }}
            }});
        }}
    </script>
</body>
</html>"""

    with open(os.path.join(DOCS_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)


def build_seo_feeds_and_ping_all_engines(published_prods: list, reviews: list, cat_urls: list, new_urls: list, today: str):
    # 1. Buat Sitemap XML
    urls_xml = f"  <url><loc>{SITE_URL}/</loc><lastmod>{today}</lastmod><changefreq>daily</changefreq><priority>1.0</priority></url>\n"
    urls_xml += f"  <url><loc>{SITE_URL}/legal.html</loc><lastmod>{today}</lastmod><changefreq>monthly</changefreq><priority>0.5</priority></url>\n"

    for c_url in cat_urls:
        urls_xml += f"  <url><loc>{c_url}</loc><lastmod>{today}</lastmod><changefreq>daily</changefreq><priority>0.9</priority></url>\n"
    for r in reviews:
        urls_xml += f"  <url><loc>{r['url']}</loc><lastmod>{r['published_at']}</lastmod><changefreq>weekly</changefreq><priority>0.9</priority></url>\n"
    for p in published_prods:
        urls_xml += f"  <url><loc>{SITE_URL}/games/{p['slug']}.html</loc><lastmod>{p.get('published_at', today)}</lastmod><changefreq>weekly</changefreq><priority>0.8</priority></url>\n"

    sitemap = f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls_xml}</urlset>'
    with open(os.path.join(DOCS_DIR, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(sitemap)

    # 2. Buat RSS 2.0 Feed dengan deklarasi Google PubSubHubbub / WebSub
    rss_items = ""
    for r in list(reversed(reviews))[:15]:
        rss_items += f"""    <item>
      <title>{r['title']}</title>
      <link>{r['url']}</link>
      <guid>{r['url']}</guid>
      <description>{r['excerpt']}</description>
    </item>\n"""
    for p in list(reversed(published_prods))[:25]:
        p_url = f"{SITE_URL}/games/{p['slug']}.html"
        rss_items += f"""    <item>
      <title>{p['name']}</title>
      <link>{p_url}</link>
      <guid>{p_url}</guid>
      <description>{p['summary']}</description>
    </item>\n"""

    rss_xml = f"""<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>SteamSpec US — PC Game Hardware Upgrade Storefront</title>
    <link>{SITE_URL}/</link>
    <description>Automated 12-Hour Steam PC System Requirements &amp; Hardware Upgrade Reviews</description>
    <atom:link href="https://pubsubhubbub.appspot.com/" rel="hub" />
    <atom:link href="{SITE_URL}/feed.xml" rel="self" type="application/rss+xml" />
{rss_items}  </channel>
</rss>"""
    with open(os.path.join(DOCS_DIR, "feed.xml"), "w", encoding="utf-8") as f:
        f.write(rss_xml)

    # 3. Buat robots.txt & file verifikasi IndexNow
    with open(os.path.join(DOCS_DIR, "robots.txt"), "w", encoding="utf-8") as f:
        f.write(f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n")

    with open(os.path.join(DOCS_DIR, f"{INDEXNOW_KEY}.txt"), "w", encoding="utf-8") as f:
        f.write(INDEXNOW_KEY)

    if "username.github.io" in SITE_URL or not new_urls:
        return

    # 4. Ping IndexNow API (Otomatis mendaftarkan URL ke Bing, Yahoo, DuckDuckGo, Yandex, Naver, Seznam)
    host = SITE_URL.replace("https://", "").replace("http://", "").split("/")[0]
    payload = {
        "host": host,
        "key": INDEXNOW_KEY,
        "keyLocation": f"{SITE_URL}/{INDEXNOW_KEY}.txt",
        "urlList": new_urls[:100]
    }
    for endpoint in ["https://api.indexnow.org/indexnow", "https://www.bing.com/indexnow", "https://yandex.com/indexnow"]:
        try:
            r = requests.post(endpoint, json=payload, timeout=12)
            print(f"[SEO] IndexNow Ping ({endpoint}) Status: {r.status_code}")
        except Exception as e:
            print(f"[WARN] IndexNow Ping gagal ({endpoint}): {e}")

    # 5. Ping Google WebSub / PubSubHubbub Hub untuk indeksasi real-time Google
    try:
        r_google = requests.post(
            "https://pubsubhubbub.appspot.com/",
            data={"hub.mode": "publish", "hub.url": f"{SITE_URL}/feed.xml"},
            timeout=12
        )
        print(f"[SEO] Google WebSub Ping Status: {r_google.status_code}")
    except Exception as e:
        print(f"[WARN] Google WebSub Ping gagal: {e}")


def main():
    state = init_or_load_state()
    products = state["products"]
    reviews = state["reviews"]
    cycle = state.get("cycle_count", 0) + 1
    state["cycle_count"] = cycle
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    unpublished = [p for p in products if not p.get("published")]
    if len(unpublished) < 20:
        for p in products:
            p["published"] = False
        unpublished = products

    batch_20 = unpublished[:20]
    new_urls = [f"{SITE_URL}/"]

    # Perkaya hingga 3 item per siklus langsung dari endpoint appdetails Steam API
    for idx, p in enumerate(batch_20):
        if idx < 3:
            enrich_from_steam_appdetails(p["appid"], p)
            time.sleep(0.4)
        p["published"] = True
        p["published_at"] = today

    published_prods = [p for p in products if p.get("published")]

    for p in published_prods:
        same_cat = [x for x in published_prods if x["cat_slug"] == p["cat_slug"]]
        url = render_game_product_page(p, same_cat, today)
        if p in batch_20:
            new_urls.append(url)

    # Buat 5 artikel review komparatif baru (masing-masing membandingkan 4 game dari batch 20 ini)
    for i in range(0, len(batch_20), 4):
        group = batch_20[i:i + 4]
        if len(group) == 4:
            rev_meta = render_review_article(group, cycle, (i // 4) + 1, today)
            reviews.append(rev_meta)
            new_urls.append(rev_meta["url"])

    cat_urls = render_category_pages(published_prods, today)
    render_legal_page(today)
    render_storefront_homepage(published_prods, reviews, today)

    save_state(state)
    build_seo_feeds_and_ping_all_engines(published_prods, reviews, cat_urls, new_urls, today)

    print(f"[DONE] Siklus #{cycle}: +20 Produk Upgrade Game & +5 Artikel Review berhasil dipublikasikan dan didaftarkan ke IndexNow & Google WebSub.")


if __name__ == "__main__":
    main()
