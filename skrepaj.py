# -*- coding: utf-8 -*-
"""
skrepaj.py - skida pojmove s hrvatske Wikipedije i gradi rjecnik.json.

BEZ ikakvog AI-ja: sve ide preko MediaWiki API-ja i determinističkih
pravila (regex + rezanje stringova).

Pokretanje:
    python skrepaj.py "Kategorija:Gradovi u Hrvatskoj" "Kategorija:Rijeke u Hrvatskoj"
"""

import argparse
import json
import os
import re
import sys
import time
from urllib.parse import quote

import requests

# --- postavke ---------------------------------------------------------------

API = "https://hr.wikipedia.org/w/api.php"
REST_SAZETAK = "https://hr.wikipedia.org/api/rest_v1/page/summary/"
CLANAK_URL = "https://hr.wikipedia.org/wiki/"

# Wikipedia trazi User-Agent s imenom projekta i kontaktom.
#
# Adresa NIJE u kodu, nego u datoteci kontakt.txt (koja se ne objavljuje) ili
# u varijabli okoline KRIZALJKE_KONTAKT - inace bi u javnom repozitoriju
# zavrsila na uvid robotima za nezeljenu postu.
def _nadi_kontakt():
    iz_okoline = os.environ.get("KRIZALJKE_KONTAKT", "").strip()
    if iz_okoline:
        return iz_okoline
    put = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kontakt.txt")
    if os.path.exists(put):
        with open(put, encoding="utf-8") as f:
            adresa = f.read().strip()
            if adresa:
                return adresa
    return ""


KONTAKT = _nadi_kontakt()
if not KONTAKT:
    print("UPOZORENJE: nema kontakt adrese. Wikipedia trazi kontakt u\n"
          "            User-Agentu. Upisi svoj mail u kontakt.txt ili\n"
          "            postavi KRIZALJKE_KONTAKT prije skrepanja.")
USER_AGENT = ("KrizaljkeHR/1.0 (generator krizaljki"
              + ("; " + KONTAKT if KONTAKT else "") + ") python-requests")

PAUZA = 0.2          # sekundi izmedu zahtjeva, da ne opteretimo server
MAKS_OPIS = 90       # rezanje po mogucnosti na granici surecenice
MIN_DULJINA = 3      # rijeci krace od 3 slova su beskorisne u krizaljci

# Hrvatska abeceda (bez q, w, x, y). Digrafi dz/lj/nj se tretiraju kao
# pojedinacna slova, jer u mrezi krizaljke svako slovo ide u svoje polje.
HR_SLOVA = set("abcčćdđefghijklmnoprsštuvzž")

GLAGOLI = ("je", "su", "jest", "bio", "bila", "bilo")


# --- pravila filtriranja i ciscenja ------------------------------------------

def je_jednorjecni(naslov):
    """Prihvaca SAMO jednorjecne pojmove: bez razmaka, bez zagrada,
    bez brojeva, samo hrvatska slova."""
    if not naslov:
        return False
    if any(z.isspace() for z in naslov):
        return False
    if "(" in naslov or ")" in naslov:
        return False
    if any(z.isdigit() for z in naslov):
        return False
    # sve ostalo (crtice, apostrofi, tocke, q/w/x/y) pada na ovoj provjeri
    return all(z.lower() in HR_SLOVA for z in naslov)


def _makni_zagrade(tekst):
    """Izbacuje zagrade i njihov sadrzaj.

    Radi se PRIJE rezanja prve recenice, jer zagrade cesto sadrze kratice
    s tockama (npr. '(lat. Croatia)') koje bi inace prerano prekinule recenicu.
    """
    prosli = None
    while prosli != tekst:                 # ugnijezdene zagrade
        prosli = tekst
        tekst = re.sub(r"\([^()]*\)", " ", tekst)
    return re.sub(r"\s{2,}", " ", tekst).strip()


def _prva_recenica(tekst):
    """Prva recenica = do prve tocke/usklicnika/upitnika iza koje slijedi
    razmak pa veliko slovo (ili kraj teksta)."""
    m = re.search(r"(?<=[.!?])\s+(?=[A-ZČĆŽŠĐ])", tekst)
    prva = tekst[: m.start()] if m else tekst
    return prva.strip().rstrip(".!?").strip()


def _skrati(tekst, maks=MAKS_OPIS):
    """Skracuje na ~maks znakova.

    Najprije trazi granicu surecenice (zarez, tocka-zarez, crtica) - tako opis
    zavrsi kao zaokruzena misao umjesto da se prekine usred nje. Tek ako takve
    granice nema, reze na granici rijeci i stavlja '…'.
    """
    if len(tekst) <= maks:
        return tekst
    rez = tekst[:maks]
    for znak in (", ", "; ", " – ", " - ", ") "):
        p = rez.rfind(znak)
        if p >= max(MIN_OPIS * 2, maks * 0.3):   # ne rezi prekratko
            return rez[:p].rstrip(" ,;:-")
    if " " in rez:
        rez = rez[: rez.rfind(" ")]
    return rez.rstrip(" ,;:-") + "…"


MIN_OPIS = 12        # krace od ovoga nije upotrebljiv opis
NEKORISNI = ("može imati više značenja", "moze imati vise znacenja",
             "razdvojba", "popis članaka")


def korisan_opis(opis):
    """Odbacuje prekratke opise i stranice za razdvojbu ('Rijec X moze imati
    vise znacenja'), koje nisu opis pojma nego popis."""
    if not opis or len(opis) < MIN_OPIS:
        return False
    nizak = opis.lower()
    return not any(loše in nizak for loše in NEKORISNI)


def maskiraj_rjesenje(opis, rijec):
    """Zamjenjuje rijec (i njezine izvedenice) s '…' da opis ne oda rjesenje.

    Wikipedia cesto ponovi pojam u istoj recenici ('Divlji kupus, biljna
    vrsta...') ili ga upotrijebi u izvedenom obliku ('KIRURG' -> 'kirurgiju',
    'BERIL' -> 'berilijev'), pa hvatamo rijec plus sve sto se na nju nastavi.
    """
    if not opis or not rijec:
        return opis
    return re.sub(re.escape(rijec) + r"\w*", "…", opis, flags=re.IGNORECASE)


def ocisti_opis(extract, naslov):
    """Pretvara Wikipedijin uvod u kratak opis za krizaljku - cistim pravilima."""
    if not extract:
        return ""
    tekst = _makni_zagrade(extract)
    tekst = _prva_recenica(tekst)

    # makni sam naslov s pocetka (da rjesenje ne stoji u opisu)
    if tekst.lower().startswith(naslov.lower()):
        tekst = tekst[len(naslov):].lstrip(" ,-–—")

    # makni glagol(e) s pocetka: "je", "je bio", "su", ...
    uzorak_glagola = r"^(?:" + "|".join(GLAGOLI) + r")\b\s*"
    prosli = None
    while prosli != tekst:
        prosli = tekst
        tekst = re.sub(uzorak_glagola, "", tekst, flags=re.IGNORECASE)

    # Wikipedia cesto pise "Umag grad je na zapadu Hrvatske" - nakon micanja
    # naslova ostane "grad je na zapadu". Makni glagol koji stoji iza
    # imenice (2. ili 3. rijec), a imenicu zadrzi.
    tekst = re.sub(r"^(\S+(?:\s+\S+)?)\s+(?:%s)\b\s*" % "|".join(GLAGOLI),
                   r"\1 ", tekst, count=1, flags=re.IGNORECASE)

    tekst = tekst.lstrip(" ,-–—").strip()
    tekst = maskiraj_rjesenje(tekst, naslov)
    tekst = re.sub(r"\s{2,}", " ", tekst).strip(" ,-–—")
    tekst = _skrati(tekst)
    if tekst:
        tekst = tekst[0].upper() + tekst[1:]
    return tekst


# --- pristup Wikipediji ------------------------------------------------------

def napravi_sesiju():
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
    return s


def _jedna_kategorija(sesija, kategorija):
    """Clanovi jedne kategorije (action=query, list=categorymembers, cmlimit=500),
    uz pracenje 'continue' ako kategorija ima vise od 500 clanova.
    Vraca (stranice, podkategorije)."""
    stranice, podkategorije, nastavak = [], [], None
    while True:
        params = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": kategorija,
            "cmlimit": "500",
            "cmtype": "page|subcat",
            "format": "json",
            "formatversion": "2",
        }
        if nastavak:
            params["cmcontinue"] = nastavak
        r = sesija.get(API, params=params, timeout=30)
        r.raise_for_status()
        podaci = r.json()
        for clan in podaci.get("query", {}).get("categorymembers", []):
            naslov = clan["title"]
            if naslov.startswith("Kategorija:"):
                podkategorije.append(naslov)
            else:
                stranice.append(naslov)
        nastavak = podaci.get("continue", {}).get("cmcontinue")
        time.sleep(PAUZA)
        if not nastavak:
            return stranice, podkategorije


def dohvati_clanove(sesija, kategorija, dubina=1):
    """Stranice kategorije, uz ulazak u podkategorije do zadane dubine.

    Treba jer na hr.wikipediji vecina velikih kategorija (npr.
    'Kategorija:Gradovi u Hrvatskoj') drzi clanke u podkategorijama,
    a sama ih izravno ima tek nekoliko.  dubina=0 znaci bez rekurzije.
    """
    svi, vidjeno, red = [], set(), [(kategorija, 0)]
    while red:
        trenutna, razina = red.pop(0)
        if trenutna in vidjeno:
            continue                       # zastita od ciklusa u kategorijama
        vidjeno.add(trenutna)
        stranice, podkategorije = _jedna_kategorija(sesija, trenutna)
        svi.extend(stranice)
        if razina < dubina:
            for pod in podkategorije:
                red.append((pod, razina + 1))
    return list(dict.fromkeys(svi))


def dohvati_posjecenost(sesija, naslovi):
    """Broj pregleda clanka u zadnjih 60 dana - gruba mjera koliko je pojam poznat.

    Sluzi da se iz rjecnika izbace pojmovi tipa AACHENOSAURUS, koje nitko ne
    moze pogoditi. MediaWiki prima do 50 naslova po zahtjevu, pa je ovo
    desetak zahtjeva umjesto jednog po rijeci.
    """
    rezultat = {}
    for i in range(0, len(naslovi), 50):
        skupina = naslovi[i:i + 50]
        nastavak = {}
        while True:
            params = {
                "action": "query",
                "prop": "pageviews",
                "titles": "|".join(skupina),
                "pvipdays": "60",
                "format": "json",
                "formatversion": "2",
            }
            params.update(nastavak)
            try:
                r = sesija.get(API, params=params, timeout=30)
                r.raise_for_status()
                podaci = r.json()
            except (requests.RequestException, ValueError):
                break                       # bez brojke radimo dalje, samo je 0
            for stranica in podaci.get("query", {}).get("pages", []):
                pregledi = stranica.get("pageviews") or {}
                zbroj = sum(v for v in pregledi.values() if v)
                if zbroj or stranica["title"] not in rezultat:
                    rezultat[stranica["title"]] = zbroj
            time.sleep(PAUZA)
            # MediaWiki obraduje samo dio naslova po zahtjevu i ostatak nudi
            # kroz 'continue'; bez ovoga vecina rijeci tiho ostane na 0.
            nastavak = podaci.get("continue")
            if not nastavak:
                break
    return rezultat


def dohvati_sazetak(sesija, naslov):
    """Polje 'extract' iz REST sazetka clanka."""
    url = REST_SAZETAK + quote(naslov.replace(" ", "_"), safe="")
    try:
        r = sesija.get(url, timeout=30)
        if r.status_code != 200:
            return ""
        return r.json().get("extract", "") or ""
    except (requests.RequestException, ValueError):
        return ""


# --- rjecnik -----------------------------------------------------------------

def ucitaj_rjecnik(put):
    if not os.path.exists(put):
        return []
    with open(put, encoding="utf-8") as f:
        try:
            podaci = json.load(f)
        except json.JSONDecodeError:
            return []
    return podaci if isinstance(podaci, list) else []


def spremi_rjecnik(put, unosi):
    with open(put, "w", encoding="utf-8") as f:
        json.dump(unosi, f, ensure_ascii=False, indent=2)


def skrepaj(kategorije, put_rjecnika="rjecnik.json", maks_po_kategoriji=None, dubina=1):
    sesija = napravi_sesiju()
    postojeci = ucitaj_rjecnik(put_rjecnika)
    vec_imamo = {u["rijec"].lower() for u in postojeci}
    prije = len(postojeci)
    novi = 0

    for kategorija in kategorije:
        print("\n[kategorija] " + kategorija)
        try:
            naslovi = dohvati_clanove(sesija, kategorija, dubina)
        except requests.RequestException as e:
            print("  !! greska pri dohvatu kategorije: " + str(e))
            continue
        print("  clanova ukupno: " + str(len(naslovi)))

        kandidati = [n for n in naslovi if je_jednorjecni(n) and len(n) >= MIN_DULJINA]
        if maks_po_kategoriji:
            kandidati = kandidati[:maks_po_kategoriji]
        print("  jednorjecnih kandidata: " + str(len(kandidati)))

        iz_kategorije = []
        for naslov in kandidati:
            if naslov.lower() in vec_imamo:
                continue
            extract = dohvati_sazetak(sesija, naslov)
            time.sleep(PAUZA)
            opis = ocisti_opis(extract, naslov)
            if not korisan_opis(opis):
                continue
            iz_kategorije.append({
                "rijec": naslov.upper(),
                "opis": opis,
                "kategorija": kategorija,
                "izvor_url": CLANAK_URL + quote(naslov.replace(" ", "_"), safe=""),
                # cuvamo i sirovi uvod: ako kasnije promijenimo pravila ciscenja,
                # opise mozemo preraditi bez ponovnog skidanja s Wikipedije
                "sazetak": extract,
                "naslov": naslov,
            })
            vec_imamo.add(naslov.lower())
            print("  + " + naslov + ": " + opis)

        if iz_kategorije:
            pregledi = dohvati_posjecenost(sesija, [u["naslov"] for u in iz_kategorije])
            for u in iz_kategorije:
                u["posjeti"] = pregledi.get(u["naslov"], 0)
            print("  posjecenost dohvacena za " + str(len(iz_kategorije)) + " pojmova")

        postojeci.extend(iz_kategorije)
        novi += len(iz_kategorije)

    spremi_rjecnik(put_rjecnika, postojeci)
    print("\nNovih rijeci: " + str(novi))
    print("Ukupno u rjecniku: " + str(len(postojeci)) + " (prije: " + str(prije) + ")")
    print("Spremljeno u: " + put_rjecnika)
    return novi, len(postojeci)


def main():
    p = argparse.ArgumentParser(
        description="Skida pojmove s hrvatske Wikipedije u rjecnik.json")
    p.add_argument("kategorije", nargs="+", help='npr. "Kategorija:Gradovi u Hrvatskoj"')
    p.add_argument("--izlaz", default="rjecnik.json")
    p.add_argument("--dubina", type=int, default=1,
                   help="koliko razina podkategorija obici (0 = samo zadana kategorija)")
    p.add_argument("--maks-po-kategoriji", type=int, default=None,
                   help="ogranici broj obradenih pojmova po kategoriji (za brzo testiranje)")
    a = p.parse_args()
    skrepaj(a.kategorije, a.izlaz, a.maks_po_kategoriji, a.dubina)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
