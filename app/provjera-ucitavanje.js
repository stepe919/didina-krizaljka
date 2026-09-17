// Provjera da aplikacija stvarno ucita .json koji izveze generiraj.py
const fs = require("fs");
const { JSDOM } = require("jsdom");
const html = fs.readFileSync(__dirname + "/didina-krizaljka.html", "utf8");
const krizaljka = fs.readFileSync(__dirname + "/../krizaljka_1.json", "utf8");

const dom = new JSDOM(html, { runScripts:"dangerously", pretendToBeVisual:true, url:"https://example.org/" });
const { window } = dom;
const greske = [];
window.onerror = m => greske.push(String(m));
Object.defineProperty(window, "innerWidth", { value:390, configurable:true });
const $ = s => window.document.querySelector(s);

setTimeout(() => {
  // isti put kojim ide gumb "Ucitaj s racunala"
  window.eval(`
    (function(){
      const o = ${krizaljka};
      o.upisano = o.upisano || {};
      pokreni(o);
    })()
  `);
  const ok = (n, u, d) => console.log((u ? "  OK   " : "  PAO  ") + n + (d && !u ? " -> " + d : ""));

  ok("nema JS grešaka", greske.length === 0, greske[0]);
  ok("otvorio se zaslon rješavanja", !$("#zRjesavanje").hidden);
  ok("opis je iz datoteke, ne iz ugrađenog rječnika",
     /Solinčica|rijeka|Grad|Planina|Jezero/i.test($("#opis").textContent), $("#opis").textContent);
  const polja = $("#polja").querySelectorAll(".polje");
  ok("polja odgovaraju duljini riječi", polja.length >= 3, polja.length + " polja");

  const stanje = window.eval("({pojmova:K.pojmovi.length, r:K.redovi, s:K.stupci, rijec:K.pojmovi[0].rijec})");
  console.log("     (učitano: " + stanje.pojmova + " pojmova, mreža " +
              stanje.r + "x" + stanje.s + ", prva riječ " + stanje.rijec + ")");

  // upis prve rijeci mora oznaciti tocno
  for (const slovo of stanje.rijec){
    const t = [...$("#tipkovnica").children].find(b => b.textContent === slovo);
    if (t) t.dispatchEvent(new window.MouseEvent("click", {bubbles:true}));
  }
  ok("upis rješenja radi na učitanoj križaljci", $("#polja").classList.contains("tocno"));
  ok("postotak se osvježio", $("#postotak").textContent !== "0%", $("#postotak").textContent);
  process.exit(greske.length ? 1 : 0);
}, 400);
