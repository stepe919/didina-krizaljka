// Provjera: napredak koji se cuje i pomoc u stupnjevima.
const fs = require("fs");
const { JSDOM } = require("jsdom");
const CR = String.fromCharCode(13);
const html = fs.readFileSync(__dirname + "/didina-krizaljka.html", "utf8").split(CR).join("");
let pao = 0, prosao = 0;
const ok = (n, u, d) => { if (u) { prosao++; console.log("  OK   " + n); }
                          else { pao++; console.log("  PAO  " + n + (d ? "  -> " + d : "")); } };

const dom = new JSDOM(html, {
  runScripts: "dangerously", pretendToBeVisual: true, url: "https://example.org/",
  beforeParse(w) {
    w.__receno = [];
    w.SpeechSynthesisUtterance = function (t) { this.text = t; };
    w.speechSynthesis = {
      speaking: false, pending: false, paused: false, onvoiceschanged: null,
      getVoices: () => ([{ name: "Google hrvatski", lang: "hr-HR" }]),
      cancel(){}, resume(){}, pause(){},
      speak(u){ w.__receno.push(String(u.text)); },
    };
    Object.defineProperty(w, "innerWidth", { value: 390, configurable: true });
  },
});
const w = dom.window, $ = s => w.document.querySelector(s);
const klik = el => el.dispatchEvent(new w.MouseEvent("click", { bubbles: true }));
const tipka = s => [...$("#tipkovnica").children].find(b => b.textContent === s);
const sveReceno = () => w.__receno.join(" | ");

setTimeout(() => {
  for (let i = 0; i < 5; i++) klik($("#gUvodDalje"));      // preskoci namjestanje
  klik($("#gNova"));

  setTimeout(() => {
    console.log("=== 1. gumb POMOZI postoji i na svom je mjestu ===");
    ok("gumb POMOZI postoji", !!$("#gPomoc"));
    const red = [...$(".kretanje").children].map(b => b.id);
    ok("POMOZI je izmedu NAZAD i DALJE",
       JSON.stringify(red) === JSON.stringify(["gNazad", "gPomoc", "gDalje"]), JSON.stringify(red));
    ok("nije obojan (boje su zauzete znacenjima)",
       $("#gPomoc").className.includes("gumb--pomoc"));

    console.log("");
    console.log("=== 2. pomoc ide u stupnjevima ===");
    const rijec = w.eval("K.pojmovi[iPojam].rijec");
    w.eval("iSlovo = 0");

    w.__receno.length = 0; klik($("#gPomoc"));
    const prvi = sveReceno();
    ok("1. put kaze PRVO slovo", /Prvo slovo je/.test(prvi), prvi);
    ok("1. put NE oda cijelu rijec", !prvi.includes(rijec.split("").join(", ")), prvi);
    ok("1. put nista ne upise", w.eval("Object.keys(K.upisano).length") === 0);

    w.__receno.length = 0; klik($("#gPomoc"));
    const drugi = sveReceno();
    ok("2. put i dalje samo jedno slovo", /slovo je/.test(drugi), drugi);
    ok("2. put NE oda cijelu rijec", !drugi.includes(rijec.split("").join(", ")), drugi);

    w.__receno.length = 0; klik($("#gPomoc"));
    const treci = sveReceno();
    ok("3. put kaze cijelu rijec", /Rije\u010d je/.test(treci), treci);
    ok("3. put je i upise (nije slijepa ulica)",
       w.eval("K.pojmovi[iPojam]") && w.eval("rijesen(K.pojmovi[iPojam])"));
    ok("broji se koliko je puta pitao", w.eval("K.pomoci && K.pomoci[iPojam]") === 3,
       w.eval("JSON.stringify(K.pomoci)"));

    console.log("");
    console.log("=== 3. napredak se cuje, ne samo vidi ===");
    w.eval("iPojam = K.pojmovi.findIndex(q => !rijesen(q)); iSlovo = 0;");
    const p2 = w.eval("K.pojmovi[iPojam].rijec");
    w.__receno.length = 0;
    for (const zn of p2) { const t = tipka(zn); if (t) klik(t); }
    const nakon = sveReceno();
    ok("kaze 'Tocno'", /To\u010dno/.test(nakon), nakon);
    ok("kaze koliko je OSTALO, ne postotak",
       /Jo\u0161 \d+|Jo\u0161 samo jedna|Pola je gotovo/.test(nakon), nakon);
    ok("ne izgovara postotak", !/posto|%/.test(nakon), nakon);

    console.log("");
    console.log("=== 4. pomoc se nudi tek nakon drugog promasaja ===");
    w.eval("iPojam = K.pojmovi.findIndex(q => !rijesen(q)); iSlovo = 0; K.pomoci = {};");
    const tocna = w.eval("K.pojmovi[iPojam].rijec");
    // Dvije RAZLICITE greske: isti krivi upis dvaput aplikacija namjerno
    // presuti (zadnjiJavljen), da ne ponavlja istu zamjerku.
    const kriva1 = (tocna[0] === "A" ? "B" : "A") + tocna.slice(1);
    const kriva2 = tocna.slice(0, -1) + (tocna.slice(-1) === "A" ? "B" : "A");

    /* Polja treba isprazniti prije svakog pokusaja. Ako se tipka PREKO vec
       upisane rijeci, na pola puta nastane slucajno tocan sadrzaj (K,U,P,I,N
       + staro A) i aplikacija javi "Tocno" usred tipkanja. */
    const ocisti = () => w.eval(
      "celijePojma(K.pojmovi[iPojam]).forEach(([r,c]) => delete K.upisano[k(r,c)]);" +
      "iSlovo = 0; zadnjiJavljen = '';");

    ocisti(); w.__receno.length = 0;
    for (const zn of kriva1) { const t = tipka(zn); if (t) klik(t); }
    ok("1. promasaj NE spominje pomoc", !/POMOZI/.test(sveReceno()), sveReceno());

    ocisti(); w.__receno.length = 0;
    for (const zn of kriva2) { const t = tipka(zn); if (t) klik(t); }
    ok("2. promasaj ponudi pomoc", /POMOZI/.test(sveReceno()), sveReceno());
    ok("i kaze GDJE je gumb (dida ga ne vidi)",
       /srednji gumb/.test(sveReceno()), sveReceno());

    console.log("");
    console.log("---------------------------------------");
    console.log("proslo: " + prosao + " | palo: " + pao);
    process.exit(pao ? 1 : 0);
  }, 300);
}, 300);
