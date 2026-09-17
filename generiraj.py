# -*- coding: utf-8 -*-
"""
generiraj.py - slaze jednu klasicnu krizaljku iz rjecnik.json i ispisuje PDF.

Pokretanje:
    python generiraj.py --n 16 --izlaz krizaljka.pdf
"""

import argparse
import json
import math
import os
import random
import sys

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.lib.utils import simpleSplit

# --- postavke ---------------------------------------------------------------

MAKS_POKUSAJA = 100       # koliko puta pokusavamo dobiti JEDINSTVENU krizaljku
MAKS_CVOROVA = 60000      # granica backtrackinga po pokusaju
MAKS_POZICIJA = 40        # koliko kandidat-pozicija po rijeci gledamo

# PDF - veliko za stariju osobu slabijeg vida
MAKS_CELIJA = 13 * mm
MIN_CELIJA = 7 * mm
FONT_OPIS = 13
FONT_NASLOV = 20
FONT_ZAGLAVLJE = 15
MARGINA = 15 * mm


# --- font s hrvatskim dijakriticima -----------------------------------------

def registriraj_font():
    """Standardni PDF fontovi nemaju č, ć, đ - mora se ugraditi TTF."""
    kandidati = [
        (r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\arialbd.ttf"),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ("/Library/Fonts/Arial.ttf", "/Library/Fonts/Arial Bold.ttf"),
    ]
    for obican, podebljan in kandidati:
        if os.path.exists(obican) and os.path.exists(podebljan):
            pdfmetrics.registerFont(TTFont("HR", obican))
            pdfmetrics.registerFont(TTFont("HR-Bold", podebljan))
            return "HR", "HR-Bold"
    print("UPOZORENJE: nije nadjen TTF font - č/ć/đ se mozda nece ispisati.")
    return "Helvetica", "Helvetica-Bold"


# --- slaganje mreze (backtracking) ------------------------------------------

def _moze_staviti(mreza, rijec, r, c, smjer):
    """Vraca broj krizanja ako je polozaj legalan, inace None.

    Pravila klasicne krizaljke:
      - polje prije pocetka i poslije kraja mora biti prazno (rijeci se ne spajaju),
      - na krizanju se slova moraju poklapati,
      - na nekrizanim poljima okomiti susjedi moraju biti prazni
        (paralelne rijeci se ne smiju dodirivati).
    """
    n = len(rijec)
    if smjer == "H":
        celije = [(r, c + i) for i in range(n)]
        prije, poslije = (r, c - 1), (r, c + n)
    else:
        celije = [(r + i, c) for i in range(n)]
        prije, poslije = (r - 1, c), (r + n, c)

    if prije in mreza or poslije in mreza:
        return None

    krizanja = 0
    for i, pos in enumerate(celije):
        if pos in mreza:
            if mreza[pos] != rijec[i]:
                return None
            krizanja += 1
        else:
            if smjer == "H":
                susjedi = [(pos[0] - 1, pos[1]), (pos[0] + 1, pos[1])]
            else:
                susjedi = [(pos[0], pos[1] - 1), (pos[0], pos[1] + 1)]
            if any(s in mreza for s in susjedi):
                return None
    return krizanja


def _pozicije(mreza, rijec):
    """Svi legalni polozaji gdje se rijec kriza s necim sto je vec na mrezi."""
    nadjene = []
    for (r, c), slovo in list(mreza.items()):
        for i, znak in enumerate(rijec):
            if znak != slovo:
                continue
            if _moze_staviti(mreza, rijec, r, c - i, "H") is not None:
                nadjene.append((r, c - i, "H"))
            if _moze_staviti(mreza, rijec, r - i, c, "V") is not None:
                nadjene.append((r - i, c, "V"))
    return list(dict.fromkeys(nadjene))


def _postavi(mreza, rijec, r, c, smjer):
    nova = []
    for i, znak in enumerate(rijec):
        pos = (r, c + i) if smjer == "H" else (r + i, c)
        if pos not in mreza:
            mreza[pos] = znak
            nova.append(pos)
    return nova


def _vrati(mreza, nova):
    for pos in nova:
        del mreza[pos]


def _backtrack(mreza, postavljene, preostale, rnd, stanje):
    if len(postavljene) > len(stanje["najbolje"]):
        stanje["najbolje"] = list(postavljene)
    if not preostale:
        return True
    if stanje["cvorovi"] >= stanje["maks_cvorova"]:
        return False
    stanje["cvorovi"] += 1

    for idx in range(len(preostale)):
        rijec = preostale[idx]
        ostatak = preostale[:idx] + preostale[idx + 1:]
        poz = _pozicije(mreza, rijec)
        rnd.shuffle(poz)
        for (r, c, smjer) in poz[:MAKS_POZICIJA]:
            nova = _postavi(mreza, rijec, r, c, smjer)
            postavljene.append((rijec, r, c, smjer))
            if _backtrack(mreza, postavljene, ostatak, rnd, stanje):
                return True
            postavljene.pop()
            _vrati(mreza, nova)
    return False


def velicina_celije(redovi, stupci):
    """Koliko bi polje bilo na A4 za mrezu ovih dimenzija. Mjerimo bas to,
    jer je citljivost na papiru ono do cega nam je stalo."""
    sirina, visina = A4
    dostupna_sirina = sirina - 2 * MARGINA
    dostupna_visina = visina - 2 * MARGINA - 12 * mm - 55 * mm
    return min(MAKS_CELIJA, dostupna_sirina / stupci, dostupna_visina / redovi)


def najkompaktnija(rijeci, rnd, pokusaja=12):
    """Slaganje je nasumicno, pa isti skup rijeci da razlicito razvucene mreze.
    Probamo nekoliko puta i uzmemo onu koja na papiru da NAJVECA polja.
    Skup rijeci ostaje isti, pa se potpis (jedinstvenost) ne mijenja."""
    najbolje, najbolja_ocjena = None, None
    for _ in range(pokusaja):
        postavljene = slozi_krizaljku(rijeci, rnd)
        if len(postavljene) < 2:
            continue
        _, _, redovi, stupci = obrezi(postavljene)
        # prvo sto vise ugradenih rijeci, pa sto vece polje na ispisu
        ocjena = (len(rijeci) - len(postavljene), -velicina_celije(redovi, stupci))
        if najbolja_ocjena is None or ocjena < najbolja_ocjena:
            najbolje, najbolja_ocjena = postavljene, ocjena
    return najbolje or []


def slozi_krizaljku(rijeci, rnd):
    """Prva rijec ide u sredinu vodoravno, ostale se krizaju backtrackingom.
    Vraca popis (rijec, red, stupac, smjer) - najbolje sto je uspjelo."""
    if not rijeci:
        return []
    rijeci = list(rijeci)
    rnd.shuffle(rijeci)
    prva = rijeci[0]

    mreza = {}
    _postavi(mreza, prva, 0, 0, "H")
    postavljene = [(prva, 0, 0, "H")]
    stanje = {"cvorovi": 0, "maks_cvorova": MAKS_CVOROVA, "najbolje": list(postavljene)}

    _backtrack(mreza, postavljene, rijeci[1:], rnd, stanje)
    return stanje["najbolje"]


# --- bounding box, numeriranje, popisi --------------------------------------

def obrezi(postavljene):
    """Pomice sve na (0,0) - obrezivanje na bounding box."""
    celije = {}
    for rijec, r, c, smjer in postavljene:
        for i, znak in enumerate(rijec):
            pos = (r, c + i) if smjer == "H" else (r + i, c)
            celije[pos] = znak
    min_r = min(p[0] for p in celije)
    min_c = min(p[1] for p in celije)
    pomaknute = [(rj, r - min_r, c - min_c, s) for rj, r, c, s in postavljene]
    mreza = {(r - min_r, c - min_c): z for (r, c), z in celije.items()}
    redovi = max(p[0] for p in mreza) + 1
    stupci = max(p[1] for p in mreza) + 1
    return pomaknute, mreza, redovi, stupci


def numeriraj(mreza, redovi, stupci):
    """Klasicno numeriranje: citanje lijevo-desno, gore-dolje.
    Polje dobiva broj ako zapocinje vodoravni ili okomiti unos duljine >= 2."""
    brojevi = {}
    vodoravno_start, okomito_start = [], []
    broj = 0
    for r in range(redovi):
        for c in range(stupci):
            if (r, c) not in mreza:
                continue
            pocinje_v = (r, c - 1) not in mreza and (r, c + 1) in mreza
            pocinje_o = (r - 1, c) not in mreza and (r + 1, c) in mreza
            if pocinje_v or pocinje_o:
                broj += 1
                brojevi[(r, c)] = broj
                if pocinje_v:
                    vodoravno_start.append((broj, r, c))
                if pocinje_o:
                    okomito_start.append((broj, r, c))
    return brojevi, vodoravno_start, okomito_start


def procitaj(mreza, r, c, smjer):
    slova = []
    while (r, c) in mreza:
        slova.append(mreza[(r, c)])
        if smjer == "H":
            c += 1
        else:
            r += 1
    return "".join(slova)


def napravi_popise(mreza, vodoravno_start, okomito_start, opisi):
    vodoravno, okomito = [], []
    for broj, r, c in vodoravno_start:
        rijec = procitaj(mreza, r, c, "H")
        vodoravno.append((broj, rijec, opisi.get(rijec, "")))
    for broj, r, c in okomito_start:
        rijec = procitaj(mreza, r, c, "V")
        okomito.append((broj, rijec, opisi.get(rijec, "")))
    return vodoravno, okomito


# --- jedinstvenost ----------------------------------------------------------

def spremi_json(put, mreza, brojevi, redovi, stupci, v_start, o_start, opisi):
    """Zapisuje krizaljku u oblik koji cita mobilna aplikacija
    (gumb 'Ucitaj s racunala'). Kljucevi polja su "red,stupac"."""
    pojmovi = []
    for smjer, starti in (("H", v_start), ("V", o_start)):
        for broj, r, c in starti:
            rijec = procitaj(mreza, r, c, smjer)
            pojmovi.append({
                "broj": broj, "r": r, "c": c, "smjer": smjer,
                "rijec": rijec, "opis": opisi.get(rijec, ""),
            })
    pojmovi.sort(key=lambda p: (p["broj"], p["smjer"]))

    podaci = {
        "redovi": redovi,
        "stupci": stupci,
        "brojevi": [[str(r) + "," + str(c), n] for (r, c), n in sorted(brojevi.items())],
        "rjesenje": [[str(r) + "," + str(c), z] for (r, c), z in sorted(mreza.items())],
        "pojmovi": pojmovi,
        "upisano": {},
    }
    with open(put, "w", encoding="utf-8") as f:
        json.dump(podaci, f, ensure_ascii=False)
    return put


def uzorak_razlicitih_opisa(sve_rijeci, opisi, n, rnd):
    """Bira n rijeci od kojih svaka ima drukciji opis.

    Bez ovoga u istoj krizaljci znaju zavrsiti KLANJEC i SKRADIN, oba s opisom
    'Grad u Hrvatskoj' - a tada se iz opisa ne moze znati koji ide gdje.
    """
    kandidati = list(sve_rijeci)
    rnd.shuffle(kandidati)
    izabrani, vidjeni = [], set()
    for rijec in kandidati:
        opis = opisi.get(rijec, "")
        if opis in vidjeni:
            continue
        izabrani.append(rijec)
        vidjeni.add(opis)
        if len(izabrani) == n:
            return izabrani
    return None


def potpis(rijeci):
    """Potpis krizaljke = abecedno sortiran popis rijeci u rjesenju."""
    return "|".join(sorted(rijeci))


def ucitaj_povijest(put):
    if not os.path.exists(put):
        return []
    with open(put, encoding="utf-8") as f:
        try:
            podaci = json.load(f)
        except json.JSONDecodeError:
            return []
    return podaci if isinstance(podaci, list) else []


def spremi_povijest(put, potpisi):
    with open(put, "w", encoding="utf-8") as f:
        json.dump(potpisi, f, ensure_ascii=False, indent=2)


# --- PDF --------------------------------------------------------------------

def _crtaj_mrezu(c, mreza, brojevi, redovi, stupci, x0, y0, celija, font, s_rjesenjem):
    c.setLineWidth(1.2)
    for r in range(redovi):
        for st in range(stupci):
            if (r, st) not in mreza:
                continue
            x = x0 + st * celija
            y = y0 - (r + 1) * celija
            c.setFillGray(1.0)
            c.rect(x, y, celija, celija, stroke=1, fill=1)
            c.setFillGray(0.0)
            if (r, st) in brojevi:
                c.setFont(font, max(6, celija * 0.22))
                c.drawString(x + 1.2 * mm, y + celija - celija * 0.28, str(brojevi[(r, st)]))
            if s_rjesenjem:
                c.setFont(font, celija * 0.5)
                c.drawCentredString(x + celija / 2.0, y + celija * 0.3, mreza[(r, st)])


def _nova_stranica(c, sirina, visina, font_b, naslov):
    c.showPage()
    c.setFont(font_b, FONT_ZAGLAVLJE)
    c.setFillGray(0.0)
    c.drawString(MARGINA, visina - MARGINA, naslov)
    return visina - MARGINA - 10 * mm


def _pisi_popis(c, y, naslov, stavke, sirina, visina, font, font_b, s_rjesenjem):
    maks_sirina = sirina - 2 * MARGINA
    if y < MARGINA + 30 * mm:
        y = _nova_stranica(c, sirina, visina, font_b, "(nastavak)")
    c.setFont(font_b, FONT_ZAGLAVLJE)
    c.drawString(MARGINA, y, naslov)
    y -= 8 * mm

    c.setFont(font, FONT_OPIS)
    for broj, rijec, opis in stavke:
        if s_rjesenjem:
            red = str(broj) + ". " + rijec + " - " + opis
        else:
            red = str(broj) + ". " + opis + " (" + str(len(rijec)) + ")"
        linije = simpleSplit(red, font, FONT_OPIS, maks_sirina)
        for linija in linije:
            if y < MARGINA:
                y = _nova_stranica(c, sirina, visina, font_b, "(nastavak)")
                c.setFont(font, FONT_OPIS)
            c.drawString(MARGINA, y, linija)
            y -= FONT_OPIS + 4
        y -= 2
    return y - 4 * mm


def ispisi_pdf(put, mreza, brojevi, redovi, stupci, vodoravno, okomito):
    font, font_b = registriraj_font()
    sirina, visina = A4
    c = pdfcanvas.Canvas(put, pagesize=A4)
    c.setTitle("Krizaljka")

    # --- stranica 1: prazna mreza + opisi ---
    c.setFont(font_b, FONT_NASLOV)
    c.drawCentredString(sirina / 2.0, visina - MARGINA, "KRIŽALJKA")
    y = visina - MARGINA - 12 * mm

    # Polje mora stati UNUTAR margina - i po sirini i po visini. Nikad ga ne
    # povecavamo preko toga, jer bi mreza izletjela iz podrucja koje pisac
    # uopce ispisuje.
    dostupna_sirina = sirina - 2 * MARGINA
    dostupna_visina = y - MARGINA - 55 * mm      # ostavi mjesta za opise
    celija = min(MAKS_CELIJA, dostupna_sirina / stupci, dostupna_visina / redovi)
    if celija < MIN_CELIJA:
        print("  napomena: mreza " + str(redovi) + "x" + str(stupci) +
              " je velika, polja su " + str(round(celija / mm, 1)) +
              " mm (manje od zeljenih " + str(round(MIN_CELIJA / mm)) + " mm).")
    x0 = (sirina - stupci * celija) / 2.0
    _crtaj_mrezu(c, mreza, brojevi, redovi, stupci, x0, y, celija, font, False)
    y = y - redovi * celija - 12 * mm

    y = _pisi_popis(c, y, "VODORAVNO", vodoravno, sirina, visina, font, font_b, False)
    y = _pisi_popis(c, y, "OKOMITO", okomito, sirina, visina, font, font_b, False)

    # --- zadnja stranica: rjesenje ---
    c.showPage()
    c.setFont(font_b, FONT_NASLOV)
    c.drawCentredString(sirina / 2.0, visina - MARGINA, "RJEŠENJE")
    y = visina - MARGINA - 12 * mm
    _crtaj_mrezu(c, mreza, brojevi, redovi, stupci, x0, y, celija, font, True)
    y = y - redovi * celija - 12 * mm
    y = _pisi_popis(c, y, "VODORAVNO", vodoravno, sirina, visina, font, font_b, True)
    y = _pisi_popis(c, y, "OKOMITO", okomito, sirina, visina, font, font_b, True)

    c.save()


# --- glavni tok -------------------------------------------------------------

def generiraj(put_rjecnika="rjecnik.json", put_povijesti="povijest.json",
              put_pdf="krizaljka.pdf", n=16, sjeme=None, min_posjeti=0, json_izlaz=None):
    if not os.path.exists(put_rjecnika):
        print("Nema " + put_rjecnika + " - prvo pokreni skrepaj.py.")
        return None

    with open(put_rjecnika, encoding="utf-8") as f:
        rjecnik = json.load(f)
    if len(rjecnik) < n:
        print("U rjecniku je samo " + str(len(rjecnik)) + " rijeci, a trazis " + str(n) + ".")
        print("Skrepaj jos kategorija ili smanji --n.")
        return None

    # izbaci premalo poznate pojmove (AACHENOSAURUS i slicno)
    if min_posjeti:
        prije_filtra = len(rjecnik)
        rjecnik = [u for u in rjecnik if u.get("posjeti", 0) >= min_posjeti]
        print("Prag poznatosti " + str(min_posjeti) + " pregleda: ostalo " +
              str(len(rjecnik)) + " od " + str(prije_filtra) + " rijeci.")
        if len(rjecnik) < n:
            print("Premalo rijeci iznad praga - smanji --min-posjeti ili --n.")
            return None

    opisi = {u["rijec"]: u["opis"] for u in rjecnik}
    sve_rijeci = sorted(opisi.keys())
    povijest = set(ucitaj_povijest(put_povijesti))
    rnd = random.Random(sjeme)

    razliciti_opisi = len(set(opisi.values()))
    if razliciti_opisi < n:
        print("U rjecniku ima samo " + str(razliciti_opisi) + " razlicitih opisa, "
              "a treba ih " + str(n) + " - skrepaj jos kategorija.")
        return None

    # ako su sve kombinacije potrosene, nema smisla ni pokusavati
    try:
        ukupno_kombinacija = math.comb(len(sve_rijeci), n)
    except ValueError:
        ukupno_kombinacija = 0
    if ukupno_kombinacija and len(povijest) >= ukupno_kombinacija:
        print("Sve moguce kombinacije od " + str(n) + " rijeci su vec iskoristene.")
        print("Skrepaj jos rijeci (skrepaj.py) da bi krizaljke i dalje bile jedinstvene.")
        return None

    for pokusaj in range(1, MAKS_POKUSAJA + 1):
        izbor = uzorak_razlicitih_opisa(sve_rijeci, opisi, n, rnd)
        if izbor is None:
            print("Ne mogu naci " + str(n) + " rijeci s razlicitim opisima.")
            return None
        postavljene = najkompaktnija(izbor, rnd)
        if len(postavljene) < 2:
            continue

        pomaknute, mreza, redovi, stupci = obrezi(postavljene)
        rijeci_u_rjesenju = [rj for rj, _, _, _ in pomaknute]
        p = potpis(rijeci_u_rjesenju)
        if p in povijest:
            continue                       # vec smo radili bas ovu - probaj opet

        brojevi, v_start, o_start = numeriraj(mreza, redovi, stupci)
        vodoravno, okomito = napravi_popise(mreza, v_start, o_start, opisi)

        ispisi_pdf(put_pdf, mreza, brojevi, redovi, stupci, vodoravno, okomito)
        if json_izlaz:
            spremi_json(json_izlaz, mreza, brojevi, redovi, stupci,
                        v_start, o_start, opisi)

        povijest.add(p)
        spremi_povijest(put_povijesti, sorted(povijest))

        print("Krizaljka gotova iz " + str(pokusaj) + ". pokusaja.")
        print("Rijeci u rjesenju: " + str(len(rijeci_u_rjesenju)) + " od " + str(n) + " trazenih")
        print("Mreza: " + str(redovi) + " x " + str(stupci))
        print("PDF: " + put_pdf)
        if json_izlaz:
            print("JSON za mobitel: " + json_izlaz)
        print("Povijest: " + str(len(povijest)) + " krizaljki u " + put_povijesti)
        return p

    print("Nakon " + str(MAKS_POKUSAJA) + " pokusaja nema nove jedinstvene krizaljke.")
    print("Skrepaj jos rijeci (skrepaj.py) pa probaj ponovno.")
    return None


def _ime_s_brojem(put, i):
    """krizaljka.pdf -> krizaljka_3.pdf"""
    korijen, nastavak = os.path.splitext(put)
    return korijen + "_" + str(i) + nastavak


def generiraj_vise(put_rjecnika, put_povijesti, put_pdf, n, sjeme, broj,
                   min_posjeti=0, json_izlaz=False):
    """Radi 'broj' uzastopnih krizaljki. Svaka se upisuje u povijest cim je
    gotova, pa sljedeca automatski izbjegava isti potpis."""
    if broj == 1:
        jz = os.path.splitext(put_pdf)[0] + ".json" if json_izlaz else None
        jedna = generiraj(put_rjecnika, put_povijesti, put_pdf, n, sjeme, min_posjeti, jz)
        return [put_pdf] if jedna else []

    napravljeni = []
    for i in range(1, broj + 1):
        izlaz = _ime_s_brojem(put_pdf, i)
        print("\n=== krizaljka " + str(i) + " od " + str(broj) + " ===")
        # razliciti seed po krizaljci, ali i dalje ponovljivo ako je --sjeme zadan
        s = None if sjeme is None else sjeme + i
        jz = os.path.splitext(izlaz)[0] + ".json" if json_izlaz else None
        if generiraj(put_rjecnika, put_povijesti, izlaz, n, s, min_posjeti, jz):
            napravljeni.append(izlaz)
        else:
            print("Stajem na " + str(i - 1) + " napravljenih krizaljki.")
            break

    print("\nGotovo: " + str(len(napravljeni)) + " krizaljki")
    for f in napravljeni:
        print("  " + f)
    return napravljeni


def main():
    p = argparse.ArgumentParser(description="Slaze klasicne krizaljke i ispisuje PDF-ove")
    p.add_argument("--rjecnik", default="rjecnik.json")
    p.add_argument("--povijest", default="povijest.json")
    p.add_argument("--izlaz", default="krizaljka.pdf")
    p.add_argument("--n", type=int, default=16, help="koliko rijeci pokusati ugraditi")
    p.add_argument("--broj", type=int, default=1, help="koliko krizaljki napraviti odjednom")
    p.add_argument("--sjeme", type=int, default=None, help="seed za ponovljiv rezultat")
    p.add_argument("--min-posjeti", type=int, default=0,
                   help="uzmi samo pojmove s barem toliko pregleda u 60 dana "
                        "(izbacuje pojmove koje nitko ne zna)")
    p.add_argument("--json", action="store_true",
                   help="uz PDF zapisi i .json za mobilnu aplikaciju")
    a = p.parse_args()
    generiraj_vise(a.rjecnik, a.povijest, a.izlaz, a.n, a.sjeme, a.broj,
                   a.min_posjeti, a.json)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
