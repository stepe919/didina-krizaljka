// Provjera aplikacije u pravom DOM-u (jsdom) - klikamo kroz nju kao korisnik.
const fs = require("fs");
const { JSDOM } = require("jsdom");

const html = fs.readFileSync(__dirname + "/didina-krizaljka.html", "utf8");
const greske = [];
let pao = 0, prosao = 0;

function provjeri(naziv, uvjet, detalj) {
  if (uvjet) { prosao++; console.log("  OK   " + naziv); }
  else { pao++; console.log("  PAO  " + naziv + (detalj ? "  -> " + detalj : "")); }
}

const dom = new JSDOM(html, {
  runScripts: "dangerously",
  pretendToBeVisual: true,
  url: "https://example.org/",
});
const { window } = dom;
window.addEventListener("error", e => greske.push(String(e.error || e.message)));
window.onerror = (m) => greske.push(String(m));

// jsdom ne crta, pa clientWidth je 0 - kod ima zamjenu preko innerWidth
Object.defineProperty(window, "innerWidth", { value: 390, configurable: true });

const $ = s => window.document.querySelector(s);
const klik = el => el.dispatchEvent(new window.MouseEvent("click", { bubbles: true }));

setTimeout(() => {
  console.log("\n=== 1. stranica se učitala bez greške ===");
  provjeri("nema JS grešaka pri učitavanju", greske.length === 0, greske[0]);
  provjeri("rječnik je ugrađen",
    window.document.getElementById("rjecnik").textContent.length > 1000);
  // 30 tipki = hrvatska abeceda s DŽ, LJ i NJ; plus tipka Briši
  provjeri("tipkovnica ima 30 slova + briši",
    $("#tipkovnica").children.length === 31,
    "ima " + $("#tipkovnica").children.length);
  // Na praznom uređaju aplikacija kreće od početnog namještanja, ne od
  // početnog zaslona - dida ne smije dobiti izbornik prije nego što je
  // išta namješteno.
  provjeri("prvo pokretanje otvara namještanje", !$("#zUvod").hidden);
  provjeri("početni zaslon se NE nudi prije namještanja", $("#zPocetak").hidden);
  // preskočimo namještanje da ostatak provjere ide na rješavanje
  for (let i = 0; i < 5; i++) klik($("#gUvodDalje"));

  console.log("\n=== 2. generiranje križaljke ===");
  klik($("#gNova"));

  setTimeout(() => {
    provjeri("nema grešaka pri slaganju", greske.length === 0, greske[0]);
    provjeri("prešlo je na zaslon rješavanja", !$("#zRjesavanje").hidden);

    const opis = $("#opis").textContent.trim();
    provjeri("pojam ima opis", opis.length > 5, "opis = " + JSON.stringify(opis));
    provjeri("oznaka kaže smjer",
      /VODORAVNO|OKOMITO/.test($("#oznaka").textContent), $("#oznaka").textContent);

    const polja = $("#polja").querySelectorAll(".polje");
    provjeri("nacrtana su polja za slova", polja.length >= 3, polja.length + " polja");
    provjeri("prvo polje je u fokusu",
      polja[0] && polja[0].getAttribute("aria-current") === "true");

    console.log("\n=== 3. upis slova tipkovnicom ===");
    const tipkaA = [...$("#tipkovnica").children].find(b => b.textContent === "A");
    klik(tipkaA);
    const poljaPoslije = $("#polja").querySelectorAll(".polje");
    provjeri("slovo se upisalo u prvo polje",
      poljaPoslije[0].textContent.replace(/\d/g, "") === "A",
      JSON.stringify(poljaPoslije[0].textContent));
    provjeri("fokus se pomaknuo na drugo polje",
      poljaPoslije[1] && poljaPoslije[1].getAttribute("aria-current") === "true");

    console.log("\n=== 4. brisanje ===");
    const tipkaBrisi = [...$("#tipkovnica").children].find(b => /Briši/.test(b.textContent));
    klik(tipkaBrisi);
    provjeri("brisanje vraća slovo",
      $("#polja").querySelectorAll(".polje")[0].textContent.replace(/\d/g, "") === "");

    console.log("\n=== 5. kretanje među pojmovima ===");
    const prviOpis = $("#opis").textContent;
    klik($("#gDalje"));
    provjeri("Dalje mijenja pojam", $("#opis").textContent !== prviOpis);
    klik($("#gNazad"));
    provjeri("Nazad vraća na prvi pojam", $("#opis").textContent === prviOpis);

    console.log("\n=== 6. rješavanje cijele riječi i napredak ===");
    // upišemo točno rješenje prvog pojma preko tipkovnice
    const stanje = window.eval("({ rijec: K.pojmovi[iPojam].rijec, ukupno: K.pojmovi.length })");
    for (const slovo of stanje.rijec) {
      const t = [...$("#tipkovnica").children].find(b => b.textContent === slovo);
      if (t) klik(t);
    }
    provjeri("riječ je označena kao točna", $("#polja").classList.contains("tocno"),
      "upisano: " + [...$("#polja").querySelectorAll(".polje")]
        .map(p => p.textContent.replace(/\d/g, "")).join(""));
    const pct = $("#postotak").textContent;
    provjeri("postotak je porastao s 0%", pct !== "0%", "postotak = " + pct);
    provjeri("brojač pokazuje riješene",
      /^[1-9]\d* od \d+ riječi$/.test($("#brojac").textContent), $("#brojac").textContent);

    console.log("\n=== 7. cijela mreža ===");
    klik($("#gMreza"));
    provjeri("sloj s mrežom se otvorio", !$("#sloj").hidden);
    const celije = $("#mreza").querySelectorAll(".celija");
    provjeri("mreža je nacrtana", celije.length > 20, celije.length + " ćelija");
    provjeri("neka ćelija je označena kao trenutna",
      $("#mreza").querySelectorAll(".celija.sad").length > 0);
    klik($("#gZatvoriSloj"));
    provjeri("sloj se zatvorio", $("#sloj").hidden);

    console.log("\n=== 8. spremanje napretka ===");
    const spremljeno = window.localStorage.getItem("didina-krizaljka-v1");
    provjeri("napredak je spremljen u localStorage", !!spremljeno);
    if (spremljeno) {
      const o = JSON.parse(spremljeno);
      provjeri("spremljeno sadrži pojmove i upisano",
        o.K && o.K.pojmovi && o.K.pojmovi.length === stanje.ukupno && o.K.upisano);
    }

    console.log("\n=== 9. ispravnost složene mreže ===");
    const ok = window.eval(`(function(){
      const kl=(r,c)=>r+","+c;
      const m=new Map(K.rjesenje);
      let sudari=0, bezKrizanja=0, izvan=0;
      for(const p of K.pojmovi){
        for(let i=0;i<p.rijec.length;i++){
          const r=p.smjer==="H"?p.r:p.r+i, c=p.smjer==="H"?p.c+i:p.c;
          if(!m.has(kl(r,c))) izvan++;
          else if(m.get(kl(r,c))!==p.rijec[i]) sudari++;
        }
      }
      const opisi=K.pojmovi.map(p=>p.opis);
      const duplihOpisa=opisi.length-new Set(opisi).size;
      return {sudari,izvan,duplihOpisa,pojmova:K.pojmovi.length,
              redovi:K.redovi,stupci:K.stupci};
    })()`);
    provjeri("slova se poklapaju na križanjima", ok.sudari === 0, "sudara: " + ok.sudari);
    provjeri("sve riječi su unutar mreže", ok.izvan === 0, "izvan: " + ok.izvan);
    provjeri("nema dva ista opisa", ok.duplihOpisa === 0, "duplih: " + ok.duplihOpisa);
    console.log("     (mreža " + ok.redovi + "x" + ok.stupci + ", " + ok.pojmova + " pojmova)");

    console.log("\n=== 10. glasovni dio ===");
    provjeri("bez govora u pregledniku ne puca",
      (klik($("#gCuj")), true));
    provjeri("bez mikrofona javlja poruku umjesto pada",
      (klik($("#gReci")), !$("#cuo").hidden), "poruka skrivena");

    console.log("\n---------------------------------------");
    console.log("prošlo: " + prosao + " | palo: " + pao);
    if (greske.length) {
      console.log("\nJS GREŠKE:");
      [...new Set(greske)].slice(0, 5).forEach(g => console.log("  " + g));
    }
    process.exit(pao ? 1 : 0);
  }, 400);
}, 300);
