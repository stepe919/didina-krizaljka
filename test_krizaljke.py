# -*- coding: utf-8 -*-
"""Kratki testovi. Pokretanje:  python -m unittest -v test_krizaljke.py"""

import json
import os
import shutil
import tempfile
import unittest

import skrepaj
import generiraj


class TestJednorjecni(unittest.TestCase):
    """skrepaj smije uzeti SAMO jednorjecne pojmove."""

    def test_prihvaca_jednu_rijec(self):
        for naslov in ["Zagreb", "Sava", "Učka", "Đakovo", "Šibenik", "Čazma"]:
            self.assertTrue(skrepaj.je_jednorjecni(naslov), naslov)

    def test_odbija_razmak(self):
        for naslov in ["Slavonski Brod", "Velika Gorica", "Nova Gradiška"]:
            self.assertFalse(skrepaj.je_jednorjecni(naslov), naslov)

    def test_odbija_zagrade_brojeve_i_strana_slova(self):
        for naslov in ["Sava (rijeka)", "Zagreb2", "1991", "New York",
                       "Split-Dalmacija", "Quebec", "Wien", "Xanten", "York"]:
            self.assertFalse(skrepaj.je_jednorjecni(naslov), naslov)

    def test_odbija_prazno(self):
        self.assertFalse(skrepaj.je_jednorjecni(""))


class TestCiscenjeOpisa(unittest.TestCase):
    """Ciscenje mora uzeti PRVU recenicu i maknuti naslov + glagol."""

    def test_reze_na_prvoj_recenici(self):
        extract = ("Zagreb je glavni grad Hrvatske. Nalazi se na sjeverozapadu zemlje. "
                   "Ima oko 800.000 stanovnika.")
        opis = skrepaj.ocisti_opis(extract, "Zagreb")
        self.assertNotIn("Nalazi", opis)
        self.assertNotIn("stanovnika", opis)

    def test_mice_naslov_i_glagol_s_pocetka(self):
        opis = skrepaj.ocisti_opis("Sava je rijeka u Hrvatskoj.", "Sava")
        self.assertTrue(opis.lower().startswith("rijeka"), opis)
        self.assertNotIn("Sava", opis)

    def test_mice_i_slozeni_glagol(self):
        opis = skrepaj.ocisti_opis("Dioklecijan je bio rimski car.", "Dioklecijan")
        self.assertTrue(opis.lower().startswith("rimski"), opis)

    def test_izbacuje_zagrade(self):
        opis = skrepaj.ocisti_opis("Učka je planina (najviši vrh Vojak) u Istri.", "Učka")
        self.assertNotIn("(", opis)
        self.assertNotIn("Vojak", opis)

    def test_zagrada_s_tockom_ne_prekida_recenicu(self):
        # '(lat. Croatia)' ne smije biti shvacen kao kraj recenice
        opis = skrepaj.ocisti_opis("Hrvatska (lat. Croatia) je država u Europi.", "Hrvatska")
        self.assertIn("država", opis.lower())   # prvo slovo opisa ide u veliko
        self.assertIn("Europi", opis)

    def test_skracuje_na_granici_rijeci(self):
        dug = "Zagreb je " + "vrlo " * 40 + "velik grad."
        opis = skrepaj.ocisti_opis(dug, "Zagreb")
        self.assertLessEqual(len(opis), skrepaj.MAKS_OPIS + 1)   # +1 za "…"
        self.assertFalse(opis.endswith("vrl"))                    # nije rezano usred rijeci

    def test_mice_glagol_iza_imenice(self):
        # hrvatska konstrukcija "Umag grad je na zapadu..."
        opis = skrepaj.ocisti_opis("Umag grad je na zapadu Hrvatske, u Istri.", "Umag")
        self.assertNotIn(" je ", opis)
        self.assertTrue(opis.lower().startswith("grad na zapadu"), opis)

    def test_ne_dira_je_dublje_u_recenici(self):
        opis = skrepaj.ocisti_opis("Sava je rijeka u Hrvatskoj koja je duga.", "Sava")
        self.assertIn("koja je duga", opis)

    def test_ne_oda_rjesenje_doslovno(self):
        opis = skrepaj.ocisti_opis("Kupus je divlji kupus, biljna vrsta.", "Kupus")
        self.assertNotIn("kupus", opis.lower())

    def test_ne_oda_rjesenje_kroz_izvedenicu(self):
        # KIRURG ne smije procuriti kao "kirurgiju", BERIL kao "berilijev"
        o1 = skrepaj.ocisti_opis("Kirurg je specijalist za kirurgiju.", "Kirurg")
        self.assertNotIn("kirurg", o1.lower())
        o2 = skrepaj.ocisti_opis("Beril je mineral, berilijev alumosilikat.", "Beril")
        self.assertNotIn("beril", o2.lower())

    def test_maskiranje_ne_dira_druge_rijeci(self):
        opis = skrepaj.ocisti_opis("Sava je rijeka u Hrvatskoj.", "Sava")
        self.assertIn("rijeka", opis.lower())

    def test_odbacuje_stranice_za_razdvojbu(self):
        self.assertFalse(skrepaj.korisan_opis("Riječ referent može imati više značenja"))
        self.assertFalse(skrepaj.korisan_opis("Grad"))           # prekratko
        self.assertTrue(skrepaj.korisan_opis("Rijeka u Splitsko-dalmatinskoj županiji"))

    def test_reze_na_granici_surecenice(self):
        # ne smije prekinuti usred misli ako postoji zarez
        dug = ("Osorščica je planina koja se proteže duž otoka, a najviši "
               "joj je vrh Televrina visok 588 metara nadmorske visine.")
        opis = skrepaj.ocisti_opis(dug, "Osorščica")
        self.assertFalse(opis.endswith("…"), opis)
        self.assertTrue(opis.endswith("otoka"), opis)

    def test_prazan_extract(self):
        self.assertEqual(skrepaj.ocisti_opis("", "Zagreb"), "")


RIJECI = ["ZAGREB", "SAVA", "DRAVA", "OSIJEK", "SPLIT", "RIJEKA", "ZADAR",
          "PULA", "SISAK", "KARLOVAC", "VARAZDIN", "TROGIR", "OMIS", "KNIN",
          "SENJ", "VINKOVCI", "POREC", "ROVINJ", "MAKARSKA", "DUBROVNIK",
          "NIN", "PAG", "HVAR", "KRK", "RAB", "VIS", "BRAC", "SOLIN"]


def napravi_rjecnik(put):
    unosi = [{"rijec": r, "opis": "opis za " + r, "kategorija": "test",
              "izvor_url": "https://hr.wikipedia.org/wiki/" + r} for r in RIJECI]
    with open(put, "w", encoding="utf-8") as f:
        json.dump(unosi, f, ensure_ascii=False)


class TestJedinstvenost(unittest.TestCase):
    """Dva uzastopna poziva generiraj() ne smiju dati isti potpis."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.rjecnik = os.path.join(self.dir, "rjecnik.json")
        self.povijest = os.path.join(self.dir, "povijest.json")
        self.pdf = os.path.join(self.dir, "k.pdf")
        napravi_rjecnik(self.rjecnik)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_dva_poziva_razliciti_potpisi(self):
        p1 = generiraj.generiraj(self.rjecnik, self.povijest, self.pdf, n=6, sjeme=1)
        p2 = generiraj.generiraj(self.rjecnik, self.povijest, self.pdf, n=6, sjeme=2)
        self.assertIsNotNone(p1)
        self.assertIsNotNone(p2)
        self.assertNotEqual(p1, p2)

    def test_potpis_se_sprema_u_povijest(self):
        p1 = generiraj.generiraj(self.rjecnik, self.povijest, self.pdf, n=6, sjeme=1)
        self.assertIn(p1, generiraj.ucitaj_povijest(self.povijest))

    def test_potpis_ne_ovisi_o_redoslijedu(self):
        self.assertEqual(generiraj.potpis(["SAVA", "PULA"]),
                         generiraj.potpis(["PULA", "SAVA"]))

    def test_pdf_je_stvarno_nastao(self):
        generiraj.generiraj(self.rjecnik, self.povijest, self.pdf, n=6, sjeme=7)
        self.assertTrue(os.path.exists(self.pdf))
        self.assertGreater(os.path.getsize(self.pdf), 1000)


class TestRazlicitiOpisi(unittest.TestCase):
    """U istoj krizaljci ne smiju biti dvije rijeci s istim opisom."""

    def test_bira_samo_razlicite_opise(self):
        import random
        opisi = {"KLANJEC": "Grad u Hrvatskoj", "SKRADIN": "Grad u Hrvatskoj",
                 "OZALJ": "Grad u Hrvatskoj", "SAVA": "Rijeka", "UČKA": "Planina",
                 "KRKA": "Rijeka u Dalmaciji", "PAG": "Otok"}
        izbor = generiraj.uzorak_razlicitih_opisa(
            sorted(opisi), opisi, 5, random.Random(1))
        self.assertIsNotNone(izbor)
        self.assertEqual(len(izbor), 5)
        self.assertEqual(len({opisi[r] for r in izbor}), 5)

    def test_vraca_none_kad_nema_dovoljno(self):
        import random
        opisi = {"A": "isti", "B": "isti", "C": "isti"}
        self.assertIsNone(generiraj.uzorak_razlicitih_opisa(
            sorted(opisi), opisi, 2, random.Random(1)))

    def test_gotova_krizaljka_nema_dva_ista_opisa(self):
        import random, collections
        opisi = {r: ("isti opis" if i % 3 == 0 else "opis " + r)
                 for i, r in enumerate(RIJECI)}
        izbor = generiraj.uzorak_razlicitih_opisa(
            sorted(opisi), opisi, 8, random.Random(5))
        c = collections.Counter(opisi[r] for r in izbor)
        self.assertEqual(max(c.values()), 1)


class TestPravilaMreze(unittest.TestCase):
    """Slozena mreza mora postivati pravila klasicne krizaljke."""

    def test_rijeci_se_krizaju_i_ne_dodiruju(self):
        import random
        postavljene = generiraj.slozi_krizaljku(RIJECI[:8], random.Random(3))
        self.assertGreaterEqual(len(postavljene), 2)
        pomaknute, mreza, redovi, stupci = generiraj.obrezi(postavljene)

        # svaki maksimalni niz duljine >= 2 mora biti tocno jedna postavljena rijec
        postavljeni_skup = set(rj for rj, _, _, _ in pomaknute)
        brojevi, v_start, o_start = generiraj.numeriraj(mreza, redovi, stupci)
        for broj, r, c in v_start:
            self.assertIn(generiraj.procitaj(mreza, r, c, "H"), postavljeni_skup)
        for broj, r, c in o_start:
            self.assertIn(generiraj.procitaj(mreza, r, c, "V"), postavljeni_skup)


if __name__ == "__main__":
    unittest.main(verbosity=2)
