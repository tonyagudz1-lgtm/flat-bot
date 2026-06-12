import requests
import json
import os
import time
from datetime import datetime

# ============================================================
# НАСТРОЙКИ
# ============================================================
TELEGRAM_TOKEN = "8644931013:AAH0oKek7cwgxCGUnbS_1GhOB4Oh_uIoJX4"
CHAT_ID = "1708244669"
SEEN_FILE = "seen_listings.json"
MAX_PRICE = 30000

# ============================================================
# TELEGRAM
# ============================================================
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    try:
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")

# ============================================================
# БАЗА ВИДЕННЫХ ОБЪЯВЛЕНИЙ
# ============================================================
def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)

# ============================================================
# SREALITY.CZ
# ============================================================
def fetch_sreality():
    results = []
    # Praha 6 locality_district_id = 5006
    # category_sub_cb: 2 = 2+kk, 3 = 2+1, 4 = 3+kk, 5 = 3+1
    room_codes = [2, 3, 4, 5]
    for room in room_codes:
        url = (
            "https://www.sreality.cz/api/cs/v2/estates"
            "?category_main_cb=1"
            "&category_type_cb=2"
            f"&category_sub_cb={room}"
            "&locality_district_id=5006"
            f"&czk_price_summary_order2_to={MAX_PRICE}"
            "&per_page=60"
            "&sort=0"
        )
        try:
            headers = {"User-Agent": "Mozilla/5.0 (compatible; FlatBot/1.0)"}
            r = requests.get(url, headers=headers, timeout=15)
            data = r.json()
            estates = data.get("_embedded", {}).get("estates", [])
            for e in estates:
                eid = str(e.get("hash_id", ""))
                name = e.get("name", "")
                price = e.get("price_czk", {}).get("value_raw", 0)
                locality = e.get("locality", "")
                link = f"https://www.sreality.cz/detail/pronajem/byt/{eid}"
                results.append({
                    "id": f"sreality_{eid}",
                    "source": "Sreality",
                    "name": name,
                    "price": price,
                    "locality": locality,
                    "link": link
                })
        except Exception as ex:
            print(f"Sreality error (room {room}): {ex}")
        time.sleep(1)
    return results

# ============================================================
# BEZREALITKY.CZ
# ============================================================
def fetch_bezrealitky():
    results = []
    # disposition: 2kk=4, 2+1=5, 3kk=6, 3+1=7
    dispositions = [4, 5, 6, 7]
    for disp in dispositions:
        url = (
            "https://www.bezrealitky.cz/api/record/markers"
            "?offerType=pronajem"
            "&estateType=byt"
            f"&disposition[]={disp}"
            "&regionOsmIds[]=R435541"  # Praha 6
            f"&priceMax={MAX_PRICE}"
            "&currency=czk"
        )
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; FlatBot/1.0)",
                "Accept": "application/json"
            }
            r = requests.get(url, headers=headers, timeout=15)
            data = r.json()
            listings = data if isinstance(data, list) else data.get("records", [])
            for item in listings:
                eid = str(item.get("id", ""))
                price = item.get("price", 0)
                street = item.get("street", "")
                city_part = item.get("cityPart", "")
                link = f"https://www.bezrealitky.cz/nemovitosti-byty-domy/{eid}"
                results.append({
                    "id": f"bezrealitky_{eid}",
                    "source": "Bezrealitky",
                    "name": f"Byt {street}, {city_part}",
                    "price": price,
                    "locality": f"{city_part}, Praha",
                    "link": link
                })
        except Exception as ex:
            print(f"Bezrealitky error (disp {disp}): {ex}")
        time.sleep(1)
    return results

# ============================================================
# ULOVDOMOV.CZ
# ============================================================
def fetch_ulovdomov():
    results = []
    url = (
        "https://www.ulovdomov.cz/api/v1/offer/list"
        "?offer_type_id=1"
        "&page=1"
        "&per_page=60"
        "&city_id=1"  # Praha
        "&district_id=6"  # Praha 6
        f"&max_price={MAX_PRICE}"
        "&disposition[]=2kk&disposition[]=21&disposition[]=3kk&disposition[]=31"
    )
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; FlatBot/1.0)",
            "Accept": "application/json"
        }
        r = requests.get(url, headers=headers, timeout=15)
        data = r.json()
        offers = data.get("offers", data.get("data", []))
        for item in offers:
            eid = str(item.get("id", ""))
            price = item.get("price", 0)
            title = item.get("title", "Byt k pronájmu")
            address = item.get("address", "")
            link = f"https://www.ulovdomov.cz/nabidka/{eid}"
            results.append({
                "id": f"ulovdomov_{eid}",
                "source": "UlovDomov",
                "name": title,
                "price": price,
                "locality": address,
                "link": link
            })
    except Exception as ex:
        print(f"UlovDomov error: {ex}")
    return results

# ============================================================
# REALITY.CZ
# ============================================================
def fetch_reality_cz():
    results = []
    # Praha 6 scraping via their search
    url = (
        "https://www.reality.cz/byty/pronajem/Praha-6/"
        "?disposition[]=2kk&disposition[]=2_1&disposition[]=3kk&disposition[]=3_1"
        f"&price_to={MAX_PRICE}"
    )
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; FlatBot/1.0)"}
        r = requests.get(url, headers=headers, timeout=15)
        from html.parser import HTMLParser

        class RealityParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.listings = []
                self.current = {}
                self.in_title = False
                self.in_price = False

            def handle_starttag(self, tag, attrs):
                attrs_dict = dict(attrs)
                if tag == "a" and "href" in attrs_dict:
                    href = attrs_dict["href"]
                    if "/detail/" in href and href not in [l.get("link") for l in self.listings]:
                        self.current = {"link": "https://www.reality.cz" + href if href.startswith("/") else href}

            def handle_data(self, data):
                pass

        # Simple regex approach for reality.cz
        import re
        pattern = r'href="(/detail/[^"]+)"[^>]*>.*?<[^>]+class="[^"]*title[^"]*"[^>]*>([^<]+)'
        matches = re.findall(pattern, r.text, re.DOTALL)
        seen_links = set()
        for href, title in matches[:20]:
            link = "https://www.reality.cz" + href
            if link not in seen_links:
                seen_links.add(link)
                eid = href.replace("/", "_").strip("_")
                results.append({
                    "id": f"reality_cz_{eid}",
                    "source": "Reality.cz",
                    "name": title.strip(),
                    "price": 0,
                    "locality": "Praha 6",
                    "link": link
                })
    except Exception as ex:
        print(f"Reality.cz error: {ex}")
    return results

# ============================================================
# IDNES REALITY
# ============================================================
def fetch_idnes():
    results = []
    url = (
        "https://reality.idnes.cz/s/pronajem/byty/praha-6/"
        "?s-qc[estateSubtype][0]=flat2&s-qc[estateSubtype][1]=flat3"
        f"&s-qc[priceMax]={MAX_PRICE}"
    )
    try:
        import re
        headers = {"User-Agent": "Mozilla/5.0 (compatible; FlatBot/1.0)"}
        r = requests.get(url, headers=headers, timeout=15)
        pattern = r'href="(https://reality\.idnes\.cz/detail/[^"]+)"'
        links = list(set(re.findall(pattern, r.text)))[:20]
        title_pattern = r'<h2[^>]*class="[^"]*title[^"]*"[^>]*>([^<]+)'
        titles = re.findall(title_pattern, r.text)
        for i, link in enumerate(links):
            eid = link.split("/")[-2] if link.endswith("/") else link.split("/")[-1]
            title = titles[i].strip() if i < len(titles) else "Byt k pronájmu"
            results.append({
                "id": f"idnes_{eid}",
                "source": "iDnes Reality",
                "name": title,
                "price": 0,
                "locality": "Praha 6",
                "link": link
            })
    except Exception as ex:
        print(f"iDnes error: {ex}")
    return results

# ============================================================
# ФОРМАТИРОВАНИЕ СООБЩЕНИЯ
# ============================================================
def format_message(listing):
    price_str = f"{listing['price']:,} CZK".replace(",", " ") if listing['price'] > 0 else "cena neuvedena"
    return (
        f"🏠 <b>{listing['source']}</b>\n"
        f"📍 {listing['locality']}\n"
        f"🏷 {listing['name']}\n"
        f"💰 {price_str}\n"
        f"🔗 <a href='{listing['link']}'>Zobrazit inzerát</a>"
    )

# ============================================================
# ГЛАВНЫЙ ЗАПУСК
# ============================================================
def main():
    print(f"[{datetime.now()}] Spouštím kontrolu bytů...")
    seen = load_seen()
    new_count = 0

    all_listings = []
    all_listings += fetch_sreality()
    all_listings += fetch_bezrealitky()
    all_listings += fetch_ulovdomov()
    all_listings += fetch_reality_cz()
    all_listings += fetch_idnes()

    print(f"Celkem nalezeno: {len(all_listings)} inzerátů")

    for listing in all_listings:
        lid = listing["id"]
        if lid not in seen:
            seen.add(lid)
            msg = format_message(listing)
            send_telegram(msg)
            new_count += 1
            time.sleep(0.5)

    save_seen(seen)

    if new_count == 0:
        print("Žádné nové inzeráty.")
    else:
        summary = f"✅ Kontrola dokončena: {new_count} nových inzerátů odesláno do Telegramu."
        send_telegram(summary)
        print(summary)

if __name__ == "__main__":
    main()
