# -*- coding: utf-8 -*-
"""
posalji.py - od krizaljke napravi LINK koji se posalje na mobitel.

Dida ne mora baratati datotekama: klikne link u Viberu/WhatsAppu i krizaljka
se otvori. Link nosi i rjesenje, pa provjera "tocno/netocno" radi i bez mreze.

Pokretanje:
    python generiraj.py --n 14 --broj 3 --min-posjeti 300 --json
    python posalji.py krizaljka_1.json krizaljka_2.json krizaljka_3.json
"""

import argparse
import base64
import json
import os
import sys

# gdje je aplikacija objavljena (promijeni ako je prebacis na GitHub Pages)
ADRESA = "https://claude.ai/code/artifact/992831e3-dc1a-4d5a-92b7-ad3545af3783"


def napravi_link(put_json, adresa=ADRESA):
    """Saljemo SAMO postavljene rijeci - mrezu, brojeve i rjesenje aplikacija
    izracuna sama. Tako je link nekoliko puta kraci."""
    with open(put_json, encoding="utf-8") as f:
        k = json.load(f)

    # iz pojmova vadimo jedinstvene rijeci s polozajem (vodoravne i okomite)
    rijeci = [[p["rijec"], p["r"], p["c"], p["smjer"], p["opis"]] for p in k["pojmovi"]]
    sitno = {"n": rijeci}

    tekst = json.dumps(sitno, ensure_ascii=False, separators=(",", ":"))
    b64 = base64.urlsafe_b64encode(tekst.encode("utf-8")).decode("ascii").rstrip("=")
    return adresa + "#k=" + b64, len(rijeci), len(tekst)


def main():
    p = argparse.ArgumentParser(description="Pretvara krizaljka_*.json u link za mobitel")
    p.add_argument("datoteke", nargs="+", help="npr. krizaljka_1.json")
    p.add_argument("--adresa", default=ADRESA, help="adresa objavljene aplikacije")
    p.add_argument("--izlaz", default="linkovi.txt")
    a = p.parse_args()

    redovi = []
    for put in a.datoteke:
        if not os.path.exists(put):
            print("  !! nema datoteke: " + put)
            continue
        link, broj_rijeci, velicina = napravi_link(put, a.adresa)
        redovi.append(os.path.basename(put) + "\n" + link + "\n")
        print("\n" + os.path.basename(put) + "  (" + str(broj_rijeci) +
              " rijeci, link " + str(len(link)) + " znakova)")
        print(link)
        if len(link) > 8000:
            print("  !! link je dug - neke poruke ga mogu prelomiti; posalji .json datoteku")

    if redovi:
        with open(a.izlaz, "w", encoding="utf-8") as f:
            f.write("\n".join(redovi))
        print("\nSve spremljeno u: " + a.izlaz)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
