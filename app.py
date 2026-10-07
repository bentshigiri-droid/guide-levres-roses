#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=====================================================================
 MINI-BOUTIQUE NUMERIQUE - 100 FCFA - Airtel Money (Gabon)
 Fichier unique : Flask + SQLite + interface integree (Mode Autonome).

 Installation : pip install flask
 Lancement    : python app.py     (puis ouvrir http://IP-DU-TELEPHONE:5000)
=====================================================================
"""
import os
import re
import secrets
import sqlite3
import time

from flask import Flask, abort, jsonify, render_template_string, request, send_file

# ------------------------- CONFIGURATION -------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PRIX = 100
NUMERO_MARCHAND = os.getenv("MERCHANT_NUMBER", "077 45 41 32")
FICHIER_PDF = os.getenv("PDF_PATH", "/storage/emulated/0/Download/Levres_Roses_Naturelles_Guide.pdf")
DB_PATH = os.getenv("DB_PATH", os.path.join(BASE_DIR, "ventes.db"))
DUREE_ATTENTE = 15 * 60          # 15 minutes avant expiration de session
MAX_TELECHARGEMENTS = 3          
CONTACT_WHATSAPP = "24177885513"
AVIS = [
    {"note": 5, "texte": "J'ai reçu mon guide en 2 minutes !", "auteur": "Sarah M., Libreville"},
    {"note": 5, "texte": "Recettes super simples à appliquer, je recommande.", "auteur": "Rachèle K., Port-Gentil"}
]

app = Flask(__name__)


# ------------------------- BASE DE DONNEES -------------------------
def db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS sessions (
            session_id      TEXT PRIMARY KEY,
            cle             TEXT NOT NULL,
            paye            INTEGER DEFAULT 0,
            cree_le         REAL,
            paye_le         REAL,
            telechargements INTEGER DEFAULT 0
        )""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_cle ON sessions(cle, paye)")


def verifier_pdf():
    if not os.path.isfile(FICHIER_PDF):
        print(f"\n!! ATTENTION : PDF introuvable : {FICHIER_PDF}\n")


# ------------------------- OUTILS -------------------------
def normaliser(numero):
    chiffres = re.sub(r"\D", "", numero or "")
    if chiffres.startswith("241"):
        chiffres = chiffres[3:]
    if len(chiffres) not in (8, 9):
        return None
    return chiffres[-8:]


# ------------------------- INTERFACE -------------------------
PAGE = r"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Lèvres Roses Naturelles : le guide — {{ prix }} FCFA</title>
<meta name="theme-color" content="#7B2350">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
:root{
  --forest:#7B2350; --leaf:#D6457F; --sun:#FFB3C6; --sun-d:#B83B6B;
  --ink:#2A1420; --muted:#7A6170; --mist:#FCEEF3; --paper:#FFF9FB; --card:#fff;
  --line:#F0DCE4; --err:#B3261E;
  --shadow-lg:0 2px 4px rgba(123,35,80,.06),0 30px 60px -20px rgba(123,35,80,.28);
  --body:"Inter",system-ui,sans-serif;
}
*{box-sizing:border-box;margin:0}
body{font-family:var(--body);color:var(--ink);background:var(--paper);line-height:1.6;font-size:17px}
.wrap{width:min(1080px,100% - 2.5rem);margin-inline:auto}
.top{display:flex;justify-content:space-between;align-items:center;padding:1.1rem 0}
.brand{font-weight:800;font-size:1.25rem;color:var(--forest);display:flex;align-items:center;gap:.5rem}
.brand i{width:30px;height:30px;border-radius:9px;background:var(--forest);display:grid;place-items:center;color:var(--sun)}
.secure{display:flex;align-items:center;gap:.4rem;font-size:.85rem;color:var(--muted);font-weight:500}
.secure svg{width:1.25em;height:1.25em;stroke:currentColor;fill:none;stroke-width:2}
.hero{background:linear-gradient(180deg,var(--mist),var(--paper));padding-bottom:3rem}
.hero-grid{display:grid;gap:2rem;padding-top:1.2rem}
.hero h1{font-size:clamp(2.2rem,7vw,3.9rem);font-weight:800;color:var(--forest);max-width:14ch;line-height:1.1}
.lead{margin-top:1.1rem;color:var(--muted);font-size:1.12rem;max-width:46ch}
.chips{display:flex;flex-wrap:wrap;gap:.6rem;margin-top:1.4rem}
.chip{display:inline-flex;align-items:center;gap:.45rem;background:#fff;border:1px solid var(--line);padding:.45rem .8rem;border-radius:99px;font-size:.9vrem;font-weight:500}
.price{display:flex;align-items:baseline;gap:.5rem;margin-top:1.6rem}
.price b{font-size:3rem;color:var(--forest);font-weight:800}
.order{background:var(--card);border-radius:24px;box-shadow:var(--shadow-lg);padding:1.6rem;border:1px solid var(--line)}
.order h2{font-size:1.45rem;color:var(--forest)}
.order .sub{color:var(--muted);font-size:.95rem;margin:.3rem 0 1.2rem}
label{font-weight:600;font-size:.92rem;display:block;margin-bottom:.45rem}
.field{display:flex;align-items:center;border:2px solid var(--line);border-radius:14px;background:#fff;overflow:hidden}
.field:focus-within{border-color:var(--leaf);box-shadow:0 0 0 4px rgba(214,69,127,.18)}
.field.bad{border-color:var(--err)}
.pre{padding:0 .9rem;font-weight:600;color:var(--muted);background:var(--mist);align-self:stretch;display:flex;align-items:center;border-right:1px solid var(--line)}
.field input{flex:1;border:0;outline:0;font:600 1.25rem var(--body);padding:.95rem .9rem;background:transparent;color:var(--ink)}
.op{margin-right:.7rem;font-size:.78rem;font-weight:700;padding:.25rem .55rem;border-radius:99px;display:none}
.op.airtel{display:block;background:#FDE6E4;color:#C4161C}
.err{color:var(--err);font-size:.88rem;margin-top:.5rem;min-height:1.3em}
.btn{width:100%;border:0;border-radius:14px;padding:1.05rem 1.2rem;font:700 1.08rem var(--body);cursor:pointer;display:flex;align-items:center;justify-content:center;gap:.6rem;text-decoration:none}
.btn-pay{background:var(--sun);color:#4A0E2B;box-shadow:0 8px 20px -6px rgba(214,69,127,.45)}
.btn[disabled]{opacity:.65;cursor:wait}
.state{display:none}
.state.on{display:block}
.pay-box{background:var(--mist);border:1px dashed var(--leaf);border-radius:16px;padding:1.1rem;margin:1rem 0}
.amount{font-size:2.2rem;font-weight:800;color:var(--forest);line-height:1}
.dest{display:flex;align-items:center;justify-content:space-between;gap:.6rem;background:#fff;border-radius:12px;padding:.7rem .9rem;margin-top:.8rem;border:1px solid var(--line)}
.dest small{display:block;color:var(--muted);font-size:.78rem}
.dest strong{font-size:1.35rem;letter-spacing:.05em}
.copy{border:1px solid var(--line);background:var(--paper);border-radius:10px;padding:.5rem .8rem;font:600 .85rem var(--body);cursor:pointer;color:var(--forest)}
.steps{list-style:none;padding:0;display:grid;gap:.7rem;margin:1rem 0}
.steps li{display:flex;gap:.7rem;align-items:flex-start;font-size:.97rem}
.steps li b.n{width:26px;height:26px;border-radius:50%;background:var(--forest);color:#fff;display:grid;place-items:center;font-size:.8rem;flex:none}
.wait{display:flex;align-items:center;gap:.8rem;background:#fff;border:1px solid var(--line);border-radius:14px;padding:.9rem 1rem;font-weight:500;margin-top:1rem}
.spin{width:22px;height:22px;border-radius:50%;border:3px solid var(--mist);border-top-color:var(--leaf);animation:sp .9s linear infinite;flex:none}
@keyframes sp{to{transform:rotate(360deg)}}
.timer{margin-left:auto;font-variant-numeric:tabular-nums;color:var(--muted);font-size:.9rem}
.link{background:none;border:0;color:var(--muted);text-decoration:underline;cursor:pointer;font:500 .9rem var(--body);margin-top:.9rem;padding:0}
.ok{text-align:center;padding:.5rem 0}
.tick{width:72px;height:72px;margin:0 auto 1rem;border-radius:50%;background:var(--leaf);color:#fff;display:grid;place-items:center}
.btn-dl{background:var(--forest);color:#fff;margin-top:1.2rem}
.progress-bar-container{width:100%;background:var(--line);border-radius:8px;height:8px;overflow:hidden;margin-top:.8rem}
.progress-bar{width:0%;height:100%;background:var(--leaf);transition:width 0.4s ease}
footer{border-top:1px solid var(--line);padding:2rem 0 3rem;color:var(--muted);font-size:.88rem;text-align:center}
@media(min-width:820px){.hero-grid{grid-template-columns:1.15fr .85fr;align-items:center;gap:3.5rem}}
</style>
</head>
<body>

<header class="hero">
  <div class="wrap">
    <div class="top">
      <div class="brand"><i><svg viewBox="0 0 24 24" width="18" height="18"><path d="M13 2 4 14h7l-1 8 9-12h-7z" stroke="currentColor" fill="none" stroke-width="2"/></svg></i>Lèvres Roses</div>
      <div class="secure"><svg viewBox="0 0 24 24"><rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg>Paiement Airtel Money</div>
    </div>

    <div class="hero-grid">
      <div>
        <h1>Des lèvres saines, douces et lumineuses</h1>
        <p class="lead">8 recettes simples pensées pour les peaux foncées, avec des ingrédients faciles à trouver au Gabon.</p>
        <div class="price"><b>{{ prix }} FCFA</b><span>paiement unique, rien d'autre à payer</span></div>
      </div>

      <!-- COMMANDE -->
      <div class="order" id="commande">
        <!-- État 1 : Saisie numéro -->
        <div class="state on" id="s-form">
          <h2>Reçois ton guide en 1 minute</h2>
          <p class="sub">Entre ton numéro pour lier ton paiement, puis envoie {{ prix }} FCFA.</p>
          <form id="form" novalidate>
            <label for="num">Ton numéro Airtel Money</label>
            <div class="field" id="field">
              <span class="pre">+241</span>
              <input id="num" type="tel" inputmode="tel" placeholder="077 12 34 56" maxlength="14">
              <span class="op" id="op"></span>
            </div>
            <p class="err" id="err"></p>
            <button class="btn btn-pay" id="go" type="submit">Continuer vers le paiement</button>
          </form>
        </div>

        <!-- État 2 : Instructions & Validation autonome -->
        <div class="state" id="s-wait">
          <h2>Envoie {{ prix }} FCFA maintenant</h2>
          <div class="pay-box">
            <div class="amount">{{ prix }} FCFA</div>
            <div class="dest">
              <div><small>Numéro de transfert officiel</small><strong id="merchant">—</strong></div>
              <button class="copy" id="copy" type="button">Copier</button>
            </div>
          </div>
          <ol class="steps">
            <li><b class="n">1</b><span>Ouvre <b>Airtel Money</b>.</span></li>
            <li><b class="n">2</b><span>Envoie <b>{{ prix }} FCFA</b> vers le numéro ci-dessus.</span></li>
            <li><b class="n">3</b><span>Fais l'envoi depuis <b id="mine">ton numéro</b>.</span></li>
          </ol>
          
          <button class="btn btn-pay" id="btn-paye" type="button" style="margin-top: 1rem;">
            J'ai effectué le paiement
          </button>

          <p class="err" id="err-paye" style="text-align:center; margin-top:0.5rem;"></p>

          <div class="wait"><div class="spin"></div><span>En attente de ton paiement…</span><span class="timer" id="timer">15:00</span></div>
          
          <div id="check-loader" style="display:none; margin-top:1rem; background:#fff; border:1px solid var(--line); border-radius:14px; padding:1rem; text-align:center;">
            <p style="font-weight:600; color:var(--forest); margin-bottom:0.5rem;" id="loader-txt">Vérification de la transaction...</p>
            <div class="progress-bar-container"><div class="progress-bar" id="prog-bar"></div></div>
          </div>

          <button class="link" id="cancel" type="button">Changer de numéro</button>
        </div>

        <!-- État 3 : Payé -->
        <div class="state" id="s-ok">
          <div class="ok">
            <div class="tick"><svg viewBox="0 0 24 24" width="36" height="36"><path d="M5 12l5 5L20 7" stroke="#fff" fill="none" stroke-width="3"/></svg></div>
            <h2>Paiement reçu, merci !</h2>
            <p class="sub">Ton guide est prêt à être téléchargé.</p>
            <a class="btn btn-dl" id="dl" href="#">Télécharger mon guide (PDF)</a>
          </div>
        </div>

        <!-- État 4 : Expiré -->
        <div class="state" id="s-exp">
          <h2>Session expirée</h2>
          <p class="sub">Aucun paiement valide reçu dans le temps imparti.</p>
          <button class="btn btn-pay" id="retry" type="button">Recommencer</button>
        </div>
      </div>
    </div>
  </div>
</header>

<footer><div class="wrap">© Lèvres Roses · Contact WhatsApp : <a href="https://wa.me/{{ contact }}" style="color:var(--forest)">Écrire</a></div></footer>

<script>
(() => {
  const $ = id => document.getElementById(id);
  const S = ["form","wait","ok","exp"];
  const show = n => S.forEach(s => $("s-"+s).classList.toggle("on", s===n));
  const KEY = "pay_session";
  let tick = null, sid = null, fin = 0, pageLoadTime = Date.now();

  const store = {
    set(v){ try{ localStorage.setItem(KEY, JSON.stringify(v)); }catch(e){} },
    get(){ try{ return JSON.parse(localStorage.getItem(KEY)||"null"); }catch(e){ return null; } },
    clear(){ try{ localStorage.removeItem(KEY); }catch(e){} }
  };

  const norm = v => {
    let d = v.replace(/\D/g,"");
    if (d.startsWith("241")) d = d.slice(3);
    if (d.length === 8) d = "0"+d;
    return d;
  };
  const operateur = d => {
    const p = d.slice(0,3);
    if (["074","077"].includes(p)) return "airtel";
    return null;
  };

  $("num").addEventListener("input", e => {
    const d = norm(e.target.value), o = operateur(d), b = $("op");
    b.className = "op" + (o ? " "+o : "");
    b.textContent = o === "airtel" ? "Airtel" : "";
    $("field").classList.remove("bad"); $("err").textContent = "";
  });

  function demarrer(data, fin_){
    sid = data.session_id; fin = fin_;
    $("merchant").textContent = data.numero_marchand;
    $("mine").textContent = data.mine || "ton numéro";
    show("wait");
    clearInterval(tick);
    tick = setInterval(horloge, 1000); horloge();
  }

  function horloge(){
    const r = Math.max(0, fin - Date.now());
    $("timer").textContent = String(Math.floor(r/60000)).padStart(2,"0")+":"+String(Math.floor(r/1000)%60).padStart(2,"0");
    if (r <= 0) { stop(); store.clear(); show("exp"); }
  }
  const stop = () => { clearInterval(tick); };

  $("form").addEventListener("submit", async e => {
    e.preventDefault();
    const d = norm($("num").value);
    if (d.length !== 9 || !operateur(d)) {
      $("err").textContent = "Entre un numéro Airtel valide (ex: 077 12 34 56).";
      $("field").classList.add("bad");
      return;
    }
    const b = $("go"); b.disabled = true;
    try{
      const r = await fetch("/api/initier-paiement", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({numero_client:d})});
      const j = await r.json();
      if (!r.ok || j.status !== "ok") throw new Error();
      j.mine = d.replace(/(\d{3})(\d{2})(\d{2})(\d{2})/,"$1 $2 $3 $4");
      const f = Date.now() + 15*60*1000;
      pageLoadTime = Date.now();
      store.set({data:j, fin:f});
      demarrer(j, f);
    }catch(err){
      $("err").textContent = "Erreur de connexion. Réessaie.";
    }finally{ b.disabled = false; }
  });

  // LOGIQUE AUTONOME : FILTRE 0-15s VS 30-40s+
  $("btn-paye").addEventListener("click", async () => {
    const elapsedSeconds = (Date.now() - pageLoadTime) / 1000;
    const errPaye = $("err-paye");
    const loader = $("check-loader");
    const bar = $("prog-bar");
    const loaderTxt = $("loader-txt");
    
    errPaye.textContent = "";
    loader.style.display = "block";
    bar.style.width = "0%";
    loaderTxt.textContent = "Recherche du paiement en cours...";

    let width = 0;
    const progressInterval = setInterval(() => {
      width += 10;
      if (width > 90) width = 90;
      bar.style.width = width + "%";
    }, 200);

    if (elapsedSeconds < 15) {
      setTimeout(() => {
        clearInterval(progressInterval);
        loader.style.display = "none";
        errPaye.textContent = "Aucun paiement reçu pour le moment. Veuillez effectuer le transfert ou réessayer.";
      }, 2500);
      return;
    }

    try {
      const res = await fetch("/api/valider-session/" + sid, { method: "POST" });
      const data = await res.json();
      
      setTimeout(() => {
        clearInterval(progressInterval);
        bar.style.width = "100%";
        if (data.status === "ok") {
          stop();
          store.clear();
          $("dl").href = "/telecharger/" + sid;
          show("ok");
        } else {
          loader.style.display = "none";
          errPaye.textContent = "Paiement non confirmé. Réessayez dans quelques instants.";
        }
      }, 2000);
    } catch(e) {
      setTimeout(() => {
        clearInterval(progressInterval);
        loader.style.display = "none";
        errPaye.textContent = "Erreur de vérification. Veuillez réessayer.";
      }, 2000);
    }
  });

  $("copy").addEventListener("click", async () => {
    const t = $("merchant").textContent.replace(/\s/g,"");
    try{ await navigator.clipboard.writeText(t); }catch(e){}
    const btn = $("copy"); btn.textContent = "Copié !";
    setTimeout(() => btn.textContent = "Copier", 1800);
  });

  const reset = () => { stop(); store.clear(); $("num").value=""; show("form"); $("check-loader").style.display="none"; };
  $("cancel").addEventListener("click", reset);
  $("retry").addEventListener("click", reset);

  const saved = store.get();
  if (saved && saved.fin > Date.now()) { demarrer(saved.data, saved.fin); }
  else store.clear();
})();
</script>
</body>
</html>
"""


@app.get("/")
def accueil():
    return render_template_string(PAGE, prix=PRIX, contact=CONTACT_WHATSAPP, avis=AVIS)


@app.post("/api/initier-paiement")
def initier_paiement():
    data = request.get_json(silent=True) or request.form
    cle = normaliser(data.get("numero_client", ""))
    if not cle:
        return jsonify(status="erreur", message="Numero invalide"), 400

    maintenant = time.time()
    with db() as c:
        row = c.execute(
            "SELECT session_id FROM sessions WHERE cle=? AND paye=0 AND cree_le>? ORDER BY cree_le DESC LIMIT 1",
            (cle, maintenant - DUREE_ATTENTE),
        ).fetchone()
        if row:
            session_id = row["session_id"]
        else:
            session_id = secrets.token_urlsafe(12)
            c.execute("INSERT INTO sessions (session_id, cle, cree_le) VALUES (?,?,?)", (session_id, cle, maintenant))

    return jsonify(status="ok", session_id=session_id, numero_marchand=NUMERO_MARCHAND, montant=PRIX)


@app.post("/api/valider-session/<session_id>")
def valider_session(session_id):
    maintenant = time.time()
    with db() as c:
        row = c.execute("SELECT session_id, paye, cree_le FROM sessions WHERE session_id=?", (session_id,)).fetchone()
        if not row:
            return jsonify(status="erreur"), 404
        
        c.execute("UPDATE sessions SET paye=1, paye_le=? WHERE session_id=?", (maintenant, session_id))
    
    return jsonify(status="ok")


@app.get("/telecharger/<session_id>")
def telecharger(session_id):
    with db() as c:
        row = c.execute("SELECT paye, telechargements FROM sessions WHERE session_id=?", (session_id,)).fetchone()
        if not row or not row["paye"] or row["telechargements"] >= MAX_TELECHARGEMENTS:
            abort(403)
        c.execute("UPDATE sessions SET telechargements=telechargements+1 WHERE session_id=?", (session_id,))
    return send_file(FICHIER_PDF, as_attachment=True, download_name="Levres_Roses_Naturelles_Guide.pdf")


init_db()
verifier_pdf()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
