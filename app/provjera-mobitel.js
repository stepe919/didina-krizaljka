// Provjera onoga sto je popravljeno za mobitel: velicina na iPhoneu i govor.
// Pokretanje:  node provjera-mobitel.js
const fs = require("fs");
const { JSDOM } = require("jsdom");

const html = fs.readFileSync(__dirname + "/didina-krizaljka.html", "utf8");
let pao = 0, prosao = 0;
function provjeri(naziv, uvjet, detalj) {
  if (uvjet) { prosao++; console.log("  OK   " + naziv); }
  else { pao++; console.log("  PAO  " + naziv + (detalj ? "  -> " + detalj : "")); }
}

console.log("\n=== 1. iPhone crta stranicu u pravoj sirini ===");
// Bez ovoga iOS Safari slozi stranicu na 980px pa je smanji na trecinu -
// to je bio glavni razlog zasto je sve izgledalo sitno.
const vp = html.match(/<meta name="viewport" content="([^"]+)">/);
provjeri("viewport meta postoji", !!vp);
provjeri("viewport je width=device-width", !!vp && /width=device-width/.test(vp[1]), vp && vp[1]);
provjeri("viewport pokriva notch (viewport-fit=cover)",
  !!vp && /viewport-fit=cover/.test(vp[1]), vp && vp[1]);
provjeri("stvarna visina na iOS-u (100dvh)", /height:100dvh/.test(html));
provjeri("zarez oko ruba ekrana sa strane", /safe-area-inset-left/.test(html));
provjeri("dvostruki dodir ne zumira", /touch-action:manipulation/.test(html));

console.log("");
console.log("=== 2. tipkovnica ===");
// Ono sto je smetalo nije bila velicina tipke nego slovo u njoj:
// 20px u tipki od 58px, tipka je bila skoro prazna.
const tipkaCss = html.match(/\.tipka\{[^}]+\}/);
provjeri("slovo na tipki raste sa sirinom ekrana",
  !!tipkaCss && /font-size:clamp\(1\.6rem, 7\.4vw/.test(tipkaCss[0]), tipkaCss && tipkaCss[0]);
provjeri("tipka je visa na visem ekranu",
  !!tipkaCss && /min-height:clamp\(56px/.test(tipkaCss[0]));
provjeri("slovo je centrirano u tipki",
  !!tipkaCss && /place-items:center/.test(tipkaCss[0]));
provjeri("DZ, LJ i NJ i dalje imaju manji font da stanu",
  /\.tipka--digraf\{font-size:clamp\(1\.15rem/.test(html));

console.log("\n=== 3. mreza se moze pomicati umjesto da se stisne ===");
provjeri("mreza je inline-grid (pomicanje u oba smjera)", /\.mreza\{display:inline-grid/.test(html));
provjeri("celija ne pada ispod 30px", /Math\.max\(30, stane\)/.test(html));

const dom = new JSDOM(html, { runScripts: "dangerously", pretendToBeVisual: true, url: "https://example.org/" });
const { window } = dom;
Object.defineProperty(window, "innerWidth", { value: 390, configurable: true });

setTimeout(() => {
  console.log("\n=== 4. dugi opis se lomi na komade ===");
  const nakomadaj = window.nakomadaj || window.eval("nakomadaj");
  const dug = "Grad u Hrvatskoj koji se nalazi sedamdesetak kilometara sjeveroistocno od Zagreba, " +
              "a poznat je po svojoj bogatoj povijesti, sajmovima i starim gradskim zidinama koje " +
              "i danas stoje uz rijeku.";
  const komadi = nakomadaj(dug, 140);
  provjeri("dugi opis je razlomljen", komadi.length > 1, komadi.length + " komada");
  provjeri("nijedan komad nije preko 140 znakova",
    komadi.every(k => k.length <= 140), JSON.stringify(komadi.map(k => k.length)));
  provjeri("nijedna rijec nije prepolovljena",
    komadi.join(" ").replace(/\s+/g, " ") === dug.replace(/\s+/g, " "));
  const kratak = "Tocno.";
  provjeri("kratka poruka ostaje u jednom komadu", nakomadaj(kratak, 140).length === 1);

  console.log("\n=== 5. glas: iPhone nema hrvatski, mora uzeti najblizi ===");
  const ocjena = window.eval("ocjenaGlasa");
  const hr = ocjena({ lang: "hr-HR", name: "Croatian" });
  const pl = ocjena({ lang: "pl-PL", name: "Zosia" });
  const cs = ocjena({ lang: "cs-CZ", name: "Zuzana" });
  const en = ocjena({ lang: "en-US", name: "Samantha" });
  provjeri("hrvatski je i dalje prvi izbor", hr > pl && hr > cs, `hr=${hr} pl=${pl} cs=${cs}`);
  provjeri("poljski se prihvaca (iPhone ga ima)", pl > 0, "pl=" + pl);
  provjeri("ceski se prihvaca (iPhone ga ima)", cs > 0, "cs=" + cs);
  provjeri("engleski se i dalje odbija", en < 0, "en=" + en);

  console.log("\n=== 6. glas: c i d s kvacicom za strani glas ===");
  const zaGlas = window.eval("zaGlas");
  window.eval('glasHR = { lang:"pl-PL", name:"Zosia" }');
  const pol = zaGlas("Kopriv\u0144ica \u0107up \u0111on \u010dokolada \u0161e\u0107er");
  provjeri("poljskom glasu se c s kvacicom pise kao cz", /cz/.test(pol), pol);
  provjeri("poljskom glasu se s s kvacicom pise kao sz", /sz/.test(pol), pol);
  window.eval('glasHR = { lang:"cs-CZ", name:"Zuzana" }');
  const ces = zaGlas("\u0107up \u0111on");
  provjeri("ceskom glasu c-s-crticom postaje c-s-kvacicom", /\u010dup/.test(ces), ces);
  provjeri("ceskom glasu d-s-crticom postaje dz", /d\u017e/.test(ces), ces);
  window.eval('glasHR = { lang:"hr-HR", name:"Croatian" }');
  const hrv = "\u0107up \u0111on \u010dokolada";
  provjeri("hrvatskom glasu se tekst NE dira", zaGlas(hrv) === hrv, zaGlas(hrv));

  console.log("\n=== 7. govor ne pada i ne zapinje ===");
  const izgovoreno = [];
  let otkazano = 0;
  window.eval(`
    window.__izg = [];
    SpeechSynthesisUtterance = function(t){ this.text = t; };
    speechSynthesis = {
      speaking:false, pending:false, paused:false,
      cancel(){ window.__otk = (window.__otk||0)+1; },
      resume(){}, pause(){}, getVoices(){ return []; },
      speak(u){ window.__izg.push(u.text); setTimeout(()=>u.onend&&u.onend(),0); }
    };
  `);
  window.eval('izgovori("Prva recenica. Druga recenica koja je osjetno duza od prve pa bi trebala zavrsiti u drugom komadu zajedno s jos malo teksta da prijedemo granicu.")');
  setTimeout(() => {
    const izg = window.eval("window.__izg");
    provjeri("govor je krenuo", izg.length > 0, izg.length + " komada");
    provjeri("dugi tekst je pusten u vise komada", izg.length > 1, JSON.stringify(izg));
    provjeri("prethodni govor se otkazuje prije novog", window.eval("window.__otk") > 0);

    console.log("\n---------------------------------------");
    console.log(`proslo: ${prosao} | palo: ${pao}`);
    process.exit(pao ? 1 : 0);
  }, 400);
}, 300);
