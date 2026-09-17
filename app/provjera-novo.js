// Provjera novih dijelova: link, potvrda naglas, boje gumba, izbor glasa.
const fs = require("fs");
const { JSDOM } = require("jsdom");

// Windows zapisuje CRLF; mičemo CR da dijeljenje po novom redu radi
const CR = String.fromCharCode(13);
const html = fs.readFileSync(__dirname + "/didina-krizaljka.html", "utf8").split(CR).join("");

let pao = 0;
const ok = (n, u, d) => { if (!u) pao++; console.log((u ? "  OK   " : "  PAO  ") + n + (!u && d ? " -> " + d : "")); };

function napravi(hash) {
  const dom = new JSDOM(html, {
    runScripts: "dangerously", pretendToBeVisual: true,
    url: "https://example.org/" + (hash || ""),
  });
  Object.defineProperty(dom.window, "innerWidth", { value: 390, configurable: true });
  return dom;
}

// ---- 1. učitavanje preko linka ----
const link = fs.readFileSync(__dirname + "/../linkovi.txt", "utf8")
  .split("\n").find(r => r.includes("#k="));
const hash = "#k=" + link.split("#k=")[1].trim();

console.log("=== 1. križaljka poslana linkom ===");
const d1 = napravi(hash);
setTimeout(() => {
  const w = d1.window, $ = s => w.document.querySelector(s);
  ok("link otvara odmah zaslon rješavanja", !$("#zRjesavanje").hidden);
  const st = w.eval("({n:K.pojmovi.length, r:K.redovi, s:K.stupci, rijec:K.pojmovi[0].rijec, opis:K.pojmovi[0].opis})");
  ok("pojmovi su rekonstruirani iz linka", st.n >= 10, st.n + " pojmova");
  ok("opis je stigao linkom", st.opis.length > 5, JSON.stringify(st.opis).slice(0, 40));
  ok("rješenje je stiglo linkom (zna provjeriti)", w.eval("new Map(K.rjesenje).size") > 20);
  ok("hash je očišćen iz adrese", !w.location.hash);
  console.log("     (iz linka: " + st.n + " pojmova, mreža " + st.r + "x" + st.s + ", prva " + st.rijec + ")");

  // ---- 2. potvrda naglas ----
  console.log("\n=== 2. kaže li točno/netočno ===");
  const klik = el => el.dispatchEvent(new w.MouseEvent("click", { bubbles: true }));
  const tipka = s => [...$("#tipkovnica").children].find(b => b.textContent === s);

  const tocna = st.rijec;
  const kriva = (tocna[0] === "A" ? "B" : "A") + tocna.slice(1);
  for (const s of kriva) { const t = tipka(s); if (t) klik(t); }
  ok("na krivo rješenje javlja da nije točno",
     /nije to[čc]no/i.test($("#cuo").textContent), JSON.stringify($("#cuo").textContent));

  // ovo je bio bug: ispravak krivog odgovora prolazio je u tišini
  w.eval("iSlovo = 0");
  for (const s of tocna) { const t = tipka(s); if (t) klik(t); }
  const pt = $("#cuo").textContent;
  ok("ispravak krivog u točno se JAVI (bug koji smo popravili)",
     /to[čc]no/i.test(pt) && !/nije/i.test(pt), JSON.stringify(pt));
  ok("riječ je označena zeleno", $("#polja").classList.contains("tocno"));
  ok("postotak je porastao", $("#postotak").textContent !== "0%", $("#postotak").textContent);

  // ---- 3. boje gumba ----
  console.log("\n=== 3. boje: zeleno = ti pričaš, crveno = aplikacija priča ===");
  ok("'Čuj pojam' je crveni (cuj--sluh)", $("#gCuj").classList.contains("cuj--sluh"));
  ok("'Reci rješenje' je zeleni (cuj--mik)", $("#gReci").classList.contains("cuj--mik"));
  const css = html.slice(html.indexOf("<style>"), html.indexOf("</style>"));
  ok("crveno je vezano na --sluh", css.includes(".cuj--sluh{background:var(--sluh)"));
  ok("zeleno je vezano na --govor", css.includes(".cuj--mik{background:var(--govor)"));
  ok("obje boje definirane i za tamnu temu",
     (css.match(/--govor:/g) || []).length >= 3 && (css.match(/--sluh:/g) || []).length >= 3);

  // ---- 4. izbor glasa ----
  console.log("\n=== 4. glas ===");
  const js = html.split("<script>").pop();
  ok("postoji izbornik glasa", !!$("#izborGlasa"));
  ok("bez govora u pregledniku red je skriven", $("#redGlas").hidden);
  ok("glasovi se rangiraju po mekoći", js.includes("neural|enhanced|premium|natural|wavenet"));
  ok("stari oštri sintetizatori se kažnjavaju", js.includes("compact|espeak|pico"));
  ok("strani jezici se odbijaju", js.includes("return -1"));
  ok("odabir glasa se pamti", js.includes("localStorage.setItem(KLJUC_GLAS"));
  ok("osnovna brzina je spuštena na 0.7", js.includes("brzinaGovora = 0.7"));
  ok("brzina se može mijenjati i pamti se", js.includes("KLJUC_BRZINA"));
  ok("glas je mekši (viša visina)", js.includes("1.06"));

  console.log("\n---------------------------------------");
  console.log(pao ? ("PALO: " + pao) : "sve prošlo");
  process.exit(pao ? 1 : 0);
}, 500);
