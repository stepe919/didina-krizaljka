# -*- coding: utf-8 -*-
"""
napravi.py - gradi mobilnu aplikaciju iz rjecnika i predloska.

Jedini korak koji treba pamtiti pri odrzavanju:

    python skrepaj.py "Kategorija:Nesto"    # dopuni bazu (rjecnik.json)
    python napravi.py                       # sagradi aplikaciju
    # pa objaviti app/didina-krizaljka.html

Sto radi:
  1. cita rjecnik.json (baza)
  2. pise app/rjecnik_app.json (sazeti oblik za mobitel)
  3. ubacuje ga u app/predlozak.html -> app/didina-krizaljka.html
  4. javi sto se promijenilo od proslog puta
"""

import argparse
import io
import json
import os
import subprocess
import sys

KORIJEN = os.path.dirname(os.path.abspath(__file__))
BAZA = os.path.join(KORIJEN, "rjecnik.json")
PREDLOZAK = os.path.join(KORIJEN, "app", "predlozak.html")
IZLAZ = os.path.join(KORIJEN, "app", "didina-krizaljka.html")
SAZETI = os.path.join(KORIJEN, "rjecnik_app.json")
OZNAKA = "/*__RJECNIK__*/"

MIN_POSJETI_ZADANO = 0     # u aplikaciju idu sve rijeci; prag se bira u njoj


def ucitaj_bazu():
    if not os.path.exists(BAZA):
        sys.exit("Nema " + BAZA + " - prvo pokreni skrepaj.py.")
    with io.open(BAZA, encoding="utf-8") as f:
        return json.load(f)


def sazmi(rjecnik, min_posjeti=MIN_POSJETI_ZADANO):
    """Iz baze vadimo samo ono sto aplikaciji treba: rijec, opis, kategorija,
    posjecenost. Sirovi sazetci i URL-ovi ostaju na laptopu - inace bi
    objavljena datoteka bila peterostruko veca."""
    odabir = [u for u in rjecnik if u.get("posjeti", 0) >= min_posjeti]
    odabir.sort(key=lambda u: -u.get("posjeti", 0))
    return [{"r": u["rijec"],
             "o": u["opis"],
             "k": u["kategorija"].replace("Kategorija:", ""),
             "p": u.get("posjeti", 0)} for u in odabir]


def provjeri_zdravlje(rjecnik):
    """Kratka kontrola prije objave - bolje uhvatiti ovdje nego na mobitelu."""
    problemi = []
    curi = [u for u in rjecnik if u["rijec"].lower() in u["opis"].lower()]
    if curi:
        problemi.append(str(len(curi)) + " opisa odaje vlastito rjesenje "
                        "(npr. " + curi[0]["rijec"] + ")")
    kratke = [u for u in rjecnik if len(u["rijec"]) < 3]
    if kratke:
        problemi.append(str(len(kratke)) + " rijeci krace od 3 slova")
    prazni = [u for u in rjecnik if not u["opis"].strip()]
    if prazni:
        problemi.append(str(len(prazni)) + " praznih opisa")
    bez_posjeta = [u for u in rjecnik if "posjeti" not in u]
    if bez_posjeta:
        problemi.append(str(len(bez_posjeta)) + " rijeci bez podatka o "
                        "posjecenosti (pokreni skrepaj.py da ga dohvati)")
    return problemi


def main():
    p = argparse.ArgumentParser(description="Gradi mobilnu aplikaciju iz rjecnika")
    p.add_argument("--min-posjeti", type=int, default=MIN_POSJETI_ZADANO,
                   help="ne ugraduj rijeci ispod ovog broja pregleda")
    p.add_argument("--testovi", action="store_true",
                   help="pokreni i sve provjere nakon gradnje")
    a = p.parse_args()

    rjecnik = ucitaj_bazu()
    print("baza:      " + str(len(rjecnik)) + " rijeci, " +
          str(len({u["kategorija"] for u in rjecnik})) + " kategorija")

    problemi = provjeri_zdravlje(rjecnik)
    if problemi:
        print("\nUPOZORENJA:")
        for x in problemi:
            print("  ! " + x)
        print()

    sazeto = sazmi(rjecnik, a.min_posjeti)
    io.open(SAZETI, "w", encoding="utf-8").write(
        json.dumps(sazeto, ensure_ascii=False))

    # koliko je rijeci bilo u proslo objavljenoj verziji
    prije = None
    if os.path.exists(IZLAZ):
        staro = io.open(IZLAZ, encoding="utf-8").read()
        poc = staro.find('id="rjecnik" type="application/json">')
        if poc > 0:
            kraj = staro.find("</script>", poc)
            try:
                prije = len(json.loads(staro[staro.index(">", poc) + 1:kraj]))
            except (ValueError, json.JSONDecodeError):
                prije = None

    predlozak = io.open(PREDLOZAK, encoding="utf-8").read()
    if OZNAKA not in predlozak:
        sys.exit("U predlosku nema oznake " + OZNAKA)
    io.open(IZLAZ, "w", encoding="utf-8").write(
        predlozak.replace(OZNAKA, json.dumps(sazeto, ensure_ascii=False)))

    # GitHub Pages sluzi samo iz korijena ili iz docs/, pa sve sto se
    # objavljuje kopiramo tamo. app/ ostaje razvojna mapa.
    docs = os.path.join(KORIJEN, "docs")
    if os.path.isdir(docs):
        import shutil
        shutil.copyfile(IZLAZ, os.path.join(docs, "index.html"))
        for pomocna in ("manifest.json", "sw.js", "ikona-192.png",
                        "ikona-512.png", "ikona-maskable.png"):
            izvor = os.path.join(KORIJEN, "app", pomocna)
            if os.path.exists(izvor):
                shutil.copyfile(izvor, os.path.join(docs, pomocna))
        print("objava:    docs/ osvjezen")

    vel = os.path.getsize(IZLAZ) / 1024
    print("ugradeno:  " + str(len(sazeto)) + " rijeci")
    if prije is not None and prije != len(sazeto):
        razlika = len(sazeto) - prije
        print("promjena:  " + ("+" if razlika > 0 else "") + str(razlika) +
              " u odnosu na proslu gradnju (" + str(prije) + ")")
    print("gotovo:    app/didina-krizaljka.html  (" + str(round(vel)) + " KB)")

    if a.testovi:
        print("\n--- provjere ---")
        app = os.path.join(KORIJEN, "app")
        for skripta in ("provjera.js", "provjera-novo.js", "provjera-glas.js"):
            if not os.path.exists(os.path.join(app, skripta)):
                continue
            r = subprocess.run(["node", skripta], cwd=app,
                               capture_output=True, text=True, encoding="utf-8")
            zadnji = [x for x in (r.stdout or "").strip().splitlines() if x.strip()]
            print("  %-20s %s" % (skripta, zadnji[-1] if zadnji else "bez izlaza"))
        r = subprocess.run([sys.executable, "-m", "unittest", "test_krizaljke"],
                           cwd=KORIJEN, capture_output=True, text=True)
        print("  %-20s %s" % ("test_krizaljke.py",
              "OK" if r.returncode == 0 else "PAO"))

    print("\nSljedeci korak: objavi app/didina-krizaljka.html")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
