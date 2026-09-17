// Provjera govora: podmećemo lažni sintetizator i gledamo ŠTO izgovori.
const fs = require("fs");
const { JSDOM } = require("jsdom");
const CR = String.fromCharCode(13);
const html = fs.readFileSync(__dirname + "/didina-krizaljka.html", "utf8").split(CR).join("");

let pao = 0;
const ok = (n, u, d) => { if (!u) pao++; console.log((u ? "  OK   " : "  PAO  ") + n + (!u && d ? " -> " + d : "")); };

const dom = new JSDOM(html, {
  runScripts: "dangerously", pretendToBeVisual: true, url: "https://example.org/",
  beforeParse(w) {
    const receno = [];
    w.__receno = receno;
    w.SpeechSynthesisUtterance = function (t) { this.text = t; };
    w.speechSynthesis = {
      onvoiceschanged: null,
      getVoices: () => ([
        { name: "Marta Compact", lang: "hr-HR" },       // stari, oštar
        { name: "Google hrvatski", lang: "hr-HR" },     // mekši
        { name: "Daniel", lang: "en-GB" },              // strani
        { name: "Srpski Enhanced", lang: "sr-RS" },
      ]),
      cancel() {},
      speak(u) { receno.push(String(u.text)); },
    };
    Object.defineProperty(w, "innerWidth", { value: 390, configurable: true });
  },
});
const w = dom.window, $ = s => w.document.querySelector(s);
const klik = el => el.dispatchEvent(new w.MouseEvent("click", { bubbles: true }));
const tipka = s => [...$("#tipkovnica").children].find(b => b.textContent === s);
const zadnje = () => w.__receno[w.__receno.length - 1] || "";

setTimeout(() => {
  console.log("=== 1. izbor glasa ===");
  ok("ponuđeni su samo naši jezici (bez engleskog)",
     [...$("#izborGlasa").options].every(o => !/Daniel/.test(o.value)),
     [...$("#izborGlasa").options].map(o => o.value).join(", "));
  ok("izabran je mekši glas, ne 'Compact'",
     w.eval("glasHR.name") === "Google hrvatski", w.eval("glasHR && glasHR.name"));
  ok("red s glasom je vidljiv kad govor postoji", !$("#redGlas").hidden);

  console.log("\n=== 2. pojam se ne ispisuje, nego sluša ===");
  ok("tekst pojma je maknut s ekrana", $("#opis").className.includes("opis-skriven"));
  ok("gumb piše SLUŠAJ", /SLUŠAJ/.test($("#gCuj").textContent), $("#gCuj").textContent.trim());
  ok("gumb piše GOVORI", /GOVORI/.test($("#gReci").textContent), $("#gReci").textContent.trim());

  klik($("#gNova"));
  setTimeout(() => {
    ok("pojam se pročita čim se križaljka otvori",
       /VODORAVNO|OKOMITO|vodoravno|okomito/.test(w.__receno.join(" ")),
       w.__receno.join(" | ").slice(0, 80));

    console.log("\n=== 3. upis je TIH po zadanome ===");
    w.__receno.length = 0;
    klik(tipka("A"));
    ok("upis slova ne govori ništa", w.__receno.length === 0, JSON.stringify(w.__receno));

    w.__receno.length = 0;
    klik([...$("#tipkovnica").children].find(b => /Briši/.test(b.textContent)));
    ok("brisanje ne govori ništa", w.__receno.length === 0, JSON.stringify(w.__receno));
    ok("prekidač za slova postoji i isključen je",
       $("#gSlova") && $("#gSlova").getAttribute("aria-pressed") === "false");

    // uključimo ga pa provjerimo da Č i Ć i dalje imaju razlikovna imena
    klik($("#gSlova"));
    w.__receno.length = 0; klik(tipka("Č")); const reklaC = zadnje();
    w.__receno.length = 0; klik(tipka("Ć")); const reklaCc = zadnje();
    ok("uključeno: Č se kaže kao 'tvrdo če'", /tvrdo/.test(reklaC), JSON.stringify(reklaC));
    ok("uključeno: Ć se kaže kao 'meko će'", /meko/.test(reklaCc), JSON.stringify(reklaCc));
    ok("Č i Ć se NE izgovaraju isto", reklaC !== reklaCc);

    w.__receno.length = 0;
    klik(tipka("Š"));
    ok("Š dobije riječ za razlikovanje", /šuma/.test(zadnje()), JSON.stringify(zadnje()));

    klik($("#gSlova"));                       // vrati na isključeno
    ok("može se opet isključiti", $("#gSlova").getAttribute("aria-pressed") === "false");

    console.log("\n=== 4. točno/netočno čim se upiše zadnje slovo ===");
    const st = w.eval("({rijec:K.pojmovi[iPojam].rijec})");
    w.eval("iSlovo = 0");
    w.__receno.length = 0;
    const kriva = (st.rijec[0] === "A" ? "B" : "A") + st.rijec.slice(1);
    for (const s of kriva) { const t = tipka(s); if (t) klik(t); }
    ok("krivo -> kaže 'Nije točno'", /Nije točno/.test(w.__receno.join(" ")),
       w.__receno.join(" | ").slice(-60));
    ok("zadnje slovo NE prekida potvrdu",
       !/^[A-ZČĆŽŠĐ]$/.test(zadnje()), JSON.stringify(zadnje()));

    w.eval("iSlovo = 0");
    w.__receno.length = 0;
    for (const s of st.rijec) { const t = tipka(s); if (t) klik(t); }
    const sve = w.__receno.join(" ");
    ok("točno -> kaže 'Točno'", /Točno/.test(sve), w.__receno.join(" | ").slice(-60));
    // slovkamo sa zarezima - zarez tjera sintetizator na pauzu između slova
    ok("točno -> slovka riječ s pauzama",
       sve.includes(st.rijec.split("").join(", ")), st.rijec);

    console.log("\n=== 5. veličina slova ===");
    // mjerimo SVE pojmove ove križaljke, ne izmišljene duljine
    const mjere = w.eval("K.pojmovi.map((p,i)=>i)").map(i => {
      w.eval("iPojam = " + i + "; iSlovo = 0; crtajPojam();");
      return {
        slova: w.eval("K.pojmovi[iPojam].rijec.length"),
        px: parseInt($("#polja").style.getPropertyValue("--polje-w"), 10),
      };
    });
    const najmanje = Math.min(...mjere.map(m => m.px));
    const najduza = mjere.reduce((a, b) => (b.slova > a.slova ? b : a));
    ok("nijedno polje nije sitnije od 54px", najmanje >= 54, najmanje + "px");
    ok("i najduža riječ ostaje krupna (prelama se)", najduza.px >= 54,
       najduza.slova + " slova -> " + najduza.px + "px");
    ok("kratke riječi koriste punu veličinu (78px)",
       mjere.some(m => m.px >= 70), "najveće: " + Math.max(...mjere.map(m => m.px)) + "px");
    const sazeto = [...new Set(mjere.map(m => m.slova + "sl=" + m.px + "px"))].join("  ");
    console.log("     (" + sazeto + ")");

    console.log("\n---------------------------------------");
    console.log(pao ? ("PALO: " + pao) : "sve prošlo");
    process.exit(pao ? 1 : 0);
  }, 300);
}, 300);
