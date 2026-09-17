/* Service worker: sprema aplikaciju na uređaj da radi i bez interneta.
 *
 * Cijela aplikacija je jedna HTML datoteka s ugrađenim rječnikom, pa nema
 * puno toga za spremiti. Font s Google Fontsa hvatamo posebno, jer dolazi
 * s druge adrese i mijenja se rijetko.
 *
 * Kad objaviš novu verziju, promijeni VERZIJA - time se stara predmemorija
 * briše i didin mobitel povuče novu aplikaciju.
 */
const VERZIJA = "didina-krizaljka-v2";
const NASE = [
  "./",
  "./index.html",
  "./manifest.json",
  "./ikona-192.png",
  "./ikona-512.png",
  "./ikona-maskable.png",
];

self.addEventListener("install", dogadaj => {
  dogadaj.waitUntil(
    caches.open(VERZIJA)
      .then(k => k.addAll(NASE))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", dogadaj => {
  dogadaj.waitUntil(
    caches.keys()
      .then(imena => Promise.all(
        imena.filter(i => i !== VERZIJA).map(i => caches.delete(i))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", dogadaj => {
  const zahtjev = dogadaj.request;
  if (zahtjev.method !== "GET") return;

  const url = new URL(zahtjev.url);
  const font = url.hostname.endsWith("googleapis.com") ||
               url.hostname.endsWith("gstatic.com");

  // Za stranicu: pokušaj mrežu pa padni na spremljeno (da nova verzija stigne
  // čim ima interneta). Za font i slike: spremljeno prvo, jer se ne mijenjaju.
  if (zahtjev.mode === "navigate"){
    dogadaj.respondWith(
      fetch(zahtjev)
        .then(odgovor => {
          const kopija = odgovor.clone();
          caches.open(VERZIJA).then(k => k.put("./index.html", kopija));
          return odgovor;
        })
        .catch(() => caches.match("./index.html").then(x => x || caches.match("./")))
    );
    return;
  }

  dogadaj.respondWith(
    caches.match(zahtjev).then(spremljeno => {
      if (spremljeno) return spremljeno;
      return fetch(zahtjev).then(odgovor => {
        if (odgovor.ok && (font || url.origin === location.origin)){
          const kopija = odgovor.clone();
          caches.open(VERZIJA).then(k => k.put(zahtjev, kopija));
        }
        return odgovor;
      }).catch(() => spremljeno);
    })
  );
});
