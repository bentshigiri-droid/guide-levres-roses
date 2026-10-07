import os
import re
import secrets
import sqlite3
import time
from datetime import datetime

from flask import (Flask, abort, redirect, render_template_string, request,
                   send_file, url_for)

# ---------------------------------------------------------------------------
# Configuration (uniquement des chemins relatifs au dossier de l'application)
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "ventes.db")
PDF_NAME = "Levres_Roses_Naturelles_Guide.pdf"
PDF_PATH = os.path.join(BASE_DIR, PDF_NAME)


def trouver_pdf():
    """Cherche le PDF (racine du projet, dossier courant, static/), sans tenir
    compte des majuscules, et accepte une variante '.pdf.pdf'."""
    voulus = {PDF_NAME.lower(), PDF_NAME.lower() + ".pdf"}
    for dossier in (BASE_DIR, os.getcwd(), os.path.join(BASE_DIR, "static")):
        if not os.path.isdir(dossier):
            continue
        for nom in os.listdir(dossier):
            chemin = os.path.join(dossier, nom)
            if nom.lower() in voulus and os.path.isfile(chemin):
                return chemin
    return None

PRIX = "100 FCFA"

# Numéros Airtel Money du marchand affichés aux clients.
NUMERO_AIRTEL_1 = "077 45 41 32"
NUMERO_AIRTEL_2 = ""  # Ex : "076 12 34 56" (laisser vide pour ne pas l'afficher)
NUMEROS_MARCHAND = [n for n in (NUMERO_AIRTEL_1, NUMERO_AIRTEL_2) if n]

# Préfixes Airtel acceptés pour le numéro du client (format local 0XX XXXXXX).
PREFIXES_AIRTEL = ("074", "076", "077")

# Minuteur anti-bot (vérifié côté SERVEUR, le JavaScript n'est qu'un affichage)
DELAI_BOT = 15      # < 15 s après l'ouverture de la page : rejet (robot probable)
DELAI_ATTENTE = 35  # >= 35 s : validation autorisée

# "1" : téléchargement dès que le minuteur est écoulé.
# "0" : vous validez chaque paiement dans /admin avant le téléchargement.
AUTO_VALIDATE = os.environ.get("AUTO_VALIDATE", "1") == "1"
# À définir dans les variables d'environnement de Render pour activer /admin.
ADMIN_KEY = os.environ.get("ADMIN_KEY", "")

app = Flask(__name__)


# ---------------------------------------------------------------------------
# Base de données
# ---------------------------------------------------------------------------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS ventes (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   telephone TEXT NOT NULL,
                   reference TEXT,
                   token TEXT NOT NULL UNIQUE,
                   statut TEXT NOT NULL DEFAULT 'cree',
                   date_achat TEXT NOT NULL,
                   ouvert_le REAL
               )"""
        )
        # Migration douce si une ancienne version de la table existe déjà.
        colonnes = [c["name"] for c in conn.execute("PRAGMA table_info(ventes)")]
        if "ouvert_le" not in colonnes:
            conn.execute("ALTER TABLE ventes ADD COLUMN ouvert_le REAL")


init_db()


def normaliser_numero(brut):
    """Retourne le numéro au format local 0XXXXXXXX, ou None s'il est invalide."""
    chiffres = re.sub(r"\D", "", brut or "")
    if chiffres.startswith("241"):
        chiffres = chiffres[3:]
    if len(chiffres) == 8:
        chiffres = "0" + chiffres
    if re.fullmatch(r"\d{9}", chiffres) and chiffres[:3] in PREFIXES_AIRTEL:
        return chiffres
    return None


# ---------------------------------------------------------------------------
# Gabarits
# ---------------------------------------------------------------------------
STYLE = """
:root{--rose:#e8799b;--rose-clair:#fde8ef;--rose-pale:#fff6f9;
--vert:#3f8f6b;--vert-clair:#e3f3ea;--texte:#2c3a33}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',system-ui,-apple-system,sans-serif;color:var(--texte);
background:linear-gradient(180deg,var(--rose-pale),#fff 40%,var(--vert-clair));
line-height:1.6;min-height:100vh}
.wrap{max-width:520px;margin:0 auto;padding:20px 16px 40px}
header{text-align:center;padding:28px 8px 12px}
.badge{display:inline-block;background:var(--vert-clair);color:var(--vert);
font-size:.8rem;font-weight:600;padding:5px 12px;border-radius:20px}
h1{font-size:1.7rem;line-height:1.25;margin:14px 0 8px;color:var(--rose)}
.sub{color:#5d6b64}
.card{background:#fff;border-radius:18px;padding:20px;margin-top:18px;
box-shadow:0 6px 22px rgba(232,121,155,.14)}
h2{font-size:1.15rem;margin-bottom:12px;color:var(--vert)}
ul.liste{list-style:none}
ul.liste li{padding:7px 0 7px 28px;position:relative}
ul.liste li:before{content:"\\273F";position:absolute;left:0;color:var(--rose)}
.prix{text-align:center}
.prix strong{font-size:2.4rem;color:var(--rose);display:block}
ol.etapes{counter-reset:e;list-style:none}
ol.etapes li{counter-increment:e;position:relative;padding:8px 0 8px 40px}
ol.etapes li:before{content:counter(e);position:absolute;left:0;top:8px;width:28px;
height:28px;border-radius:50%;background:var(--vert);color:#fff;font-weight:700;
text-align:center;line-height:28px;font-size:.9rem}
.num{display:inline-block;background:var(--rose-clair);color:var(--rose);font-weight:700;
padding:2px 10px;border-radius:8px;margin:2px 2px;white-space:nowrap}
label{display:block;font-weight:600;margin:12px 0 6px}
input[type=text],input[type=tel]{width:100%;padding:14px;border:2px solid var(--rose-clair);
border-radius:12px;font-size:1rem;outline:none}
input:focus{border-color:var(--rose)}
.btn{display:block;width:100%;margin-top:18px;padding:15px;border:0;border-radius:14px;
background:linear-gradient(135deg,var(--rose),#f08fae);color:#fff;font-size:1.05rem;
font-weight:700;text-align:center;text-decoration:none;cursor:pointer}
.btn.vert{background:linear-gradient(135deg,var(--vert),#58ad87)}
.btn:disabled{background:#cfd8d3;cursor:not-allowed}
.err{background:#fdecea;color:#b3261e;font-weight:600;padding:12px;border-radius:10px;margin-top:12px;border:1px solid #f3b8b3}
.petit{font-size:.8rem;color:#7a8780;text-align:center;margin-top:18px}
.barre{height:8px;background:var(--rose-clair);border-radius:8px;overflow:hidden;margin-top:14px}
.barre div{height:100%;width:0;background:linear-gradient(90deg,var(--rose),var(--vert))}
#compteur{text-align:center;font-weight:600;color:var(--vert);margin-top:10px;min-height:1.6em}
.hp{position:absolute;left:-9999px;height:0;overflow:hidden}
table{width:100%;border-collapse:collapse;font-size:.9rem}
td,th{padding:8px 4px;border-bottom:1px solid var(--rose-clair);text-align:left}
"""

HEAD = """<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#e8799b">
<title>{{ titre }}</title><style>{{ style|safe }}</style>
{% if refresh %}<meta http-equiv="refresh" content="{{ refresh }}">{% endif %}
</head><body><div class="wrap">"""

FOOT = """<p class="petit">&copy; Lèvres Roses Naturelles &middot; Gabon</p>
</div></body></html>"""

NUMEROS_HTML = """{% for n in numeros %}<span class="num">{{ n }}</span>{% endfor %}"""

LANDING = HEAD + """
<header>
  <span class="badge">🌿 100 % naturel · Guide PDF</span>
  <h1>Lèvres Roses Naturelles</h1>
  <p class="sub">Le guide simple pour retrouver des lèvres douces, hydratées et
  naturellement roses, avec des ingrédients accessibles.</p>
</header>

<div class="card">
  <h2>Ce que vous allez découvrir</h2>
  <ul class="liste">
    <li>Des recettes naturelles faciles à préparer chez vous</li>
    <li>Les bons gestes pour hydrater et exfolier en douceur</li>
    <li>Les habitudes à éviter pour ne pas foncer les lèvres</li>
    <li>Un guide clair, lisible sur téléphone</li>
  </ul>
</div>

<div class="card prix">
  <h2>Prix</h2>
  <strong>{{ prix }}</strong>
  <span class="sub">Paiement unique par Airtel Money</span>
</div>

<div class="card">
  <h2>Comment obtenir le guide ?</h2>
  <ol class="etapes">
    <li>Envoyez <b>{{ prix }}</b> par <b>Airtel Money</b> à l'un de ces numéros :
        """ + NUMEROS_HTML + """</li>
    <li>Saisissez ci-dessous le numéro avec lequel vous allez payer</li>
    <li>Effectuez le paiement, puis appuyez sur « J'ai envoyé » pour télécharger le PDF</li>
  </ol>
</div>

<div class="card">
  <h2>Je veux payer</h2>
  <form method="post" action="{{ url_for('commander') }}" autocomplete="on">
    <label for="tel">Numéro Airtel Money avec lequel vous payez</label>
    <input id="tel" name="telephone" type="tel" inputmode="tel"
           placeholder="Ex : 077 00 00 00" required autocomplete="tel">
    <div class="hp" aria-hidden="true">
      <label for="site">Ne pas remplir</label>
      <input id="site" name="site" type="text" tabindex="-1" autocomplete="off">
    </div>
    {% if erreur %}<div class="err">{{ erreur }}</div>{% endif %}
    <button class="btn" type="submit">Aller au paiement</button>
  </form>
</div>
""" + FOOT

PAIEMENT = HEAD + """
<header>
  <span class="badge">Étape 2 sur 2</span>
  <h1>Paiement 🌸</h1>
  <p class="sub">Numéro enregistré : <b>{{ telephone }}</b></p>
</header>

<div class="card">
  <h2>Effectuez votre paiement</h2>
  <p>Envoyez <b>{{ prix }}</b> par Airtel Money à : """ + NUMEROS_HTML + """</p>
  <p class="sub" style="margin-top:8px">Envoyez l'argent depuis votre téléphone,
  puis revenez ici et appuyez sur « J'ai envoyé le paiement ».</p>

  <form method="post" action="{{ url_for('valider', token=token) }}">
    <div class="hp" aria-hidden="true">
      <label for="site">Ne pas remplir</label>
      <input id="site" name="site" type="text" tabindex="-1" autocomplete="off">
    </div>
    {% if erreur %}<div class="err">{{ erreur }}</div>{% endif %}
    <button class="btn vert" type="submit">J'ai envoyé le paiement</button>
  </form>
</div>

""" + FOOT

ATTENTE = HEAD + """
<header><h1>Vérification en cours ⏳</h1>
<p class="sub">Votre paiement est en cours de vérification manuelle. Cette page
s'actualise automatiquement.</p></header>
<div class="card">
  <p>Pas encore payé ? Envoyez {{ prix }} à : """ + NUMEROS_HTML + """</p>
  <a class="btn" href="">Actualiser</a>
</div>
""" + FOOT

PRET = HEAD + """
<header><span class="badge">✔ Merci pour votre achat</span>
<h1>Votre guide est prêt 🌸</h1>
<p class="sub">Appuyez sur le bouton pour télécharger le PDF.</p></header>
<div class="card">
  <a class="btn vert" href="{{ lien }}">Télécharger le guide (PDF)</a>
  <p class="petit">Conservez cette page pour retélécharger le guide plus tard.</p>
</div>
""" + FOOT

ADMIN = HEAD + """
<header><h1>Ventes</h1></header>
<div class="card" style="overflow-x:auto"><table>
<tr><th>Tél.</th><th>Date</th><th>Statut</th><th></th></tr>
{% for v in ventes %}<tr><td>{{ v.telephone }}</td><td>{{ v.date_achat }}</td>
<td>{{ v.statut }}</td><td>{% if v.statut != 'valide' %}
<form method="post" action="{{ url_for('admin_valider', vente_id=v.id) }}">
<input type="hidden" name="cle" value="{{ cle }}">
<button class="btn vert" style="margin:0;padding:6px 10px;font-size:.8rem">Valider</button>
</form>{% endif %}</td></tr>{% endfor %}</table></div>
""" + FOOT


def rendre(gabarit, titre="Lèvres Roses Naturelles", **ctx):
    return render_template_string(
        gabarit, style=STYLE, titre=titre, prix=PRIX,
        numeros=NUMEROS_MARCHAND, **ctx)


# ---------------------------------------------------------------------------
# Utilitaires
# ---------------------------------------------------------------------------
def charger_vente(token):
    with get_db() as conn:
        vente = conn.execute("SELECT * FROM ventes WHERE token = ?", (token,)).fetchone()
    if vente is None:
        abort(404)
    return vente


def afficher_paiement(vente, erreur=None, code=200):
    page = rendre(PAIEMENT, refresh=None, token=vente["token"],
                  telephone=vente["telephone"], erreur=erreur)
    return page, code


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def accueil():
    return rendre(LANDING)


@app.route("/commander", methods=["POST"])
def commander():
    # Honeypot : un humain ne remplit jamais ce champ caché.
    if request.form.get("site"):
        abort(400)

    telephone = normaliser_numero(request.form.get("telephone"))
    if not telephone:
        return rendre(LANDING, erreur="Numéro Airtel invalide (ex : 077 00 00 00)."), 400

    token = secrets.token_urlsafe(24)

    with get_db() as conn:
        conn.execute(
            "INSERT INTO ventes (telephone, reference, token, statut, date_achat, ouvert_le) "
            "VALUES (?, ?, ?, 'cree', ?, ?)",
            (telephone, "", token,
             datetime.now().isoformat(timespec="seconds"), time.time()),
        )
    return redirect(url_for("paiement", token=token))


@app.route("/paiement/<token>")
def paiement(token):
    vente = charger_vente(token)
    if vente["statut"] != "cree":
        return redirect(url_for("telecharger", token=token))
    return afficher_paiement(vente)


@app.route("/valider/<token>", methods=["POST"])
def valider(token):
    vente = charger_vente(token)

    if vente["statut"] != "cree":
        return redirect(url_for("telecharger", token=token))

    if request.form.get("site"):  # honeypot rempli : robot
        abort(400)

    ecoule = time.time() - (vente["ouvert_le"] or 0)

    # Minuteur invisible : trop tôt = paiement impossible à avoir été effectué.
    if ecoule < DELAI_BOT:
        return afficher_paiement(vente, "Paiement non terminé : envoyez d'abord les 100 FCFA, puis appuyez de nouveau sur le bouton.", 429)

    if ecoule < DELAI_ATTENTE:
        return afficher_paiement(vente, "Paiement non terminé : envoyez d'abord les 100 FCFA, puis appuyez de nouveau sur le bouton.", 425)

    nouveau_statut = "valide" if AUTO_VALIDATE else "en_attente"
    with get_db() as conn:
        conn.execute("UPDATE ventes SET statut = ? WHERE id = ?",
                     (nouveau_statut, vente["id"]))
    return redirect(url_for("telecharger", token=token))


@app.route("/telecharger/<token>")
def telecharger(token):
    vente = charger_vente(token)

    if vente["statut"] == "cree":
        return redirect(url_for("paiement", token=token))

    if vente["statut"] != "valide":
        return rendre(ATTENTE, refresh=20)

    if request.args.get("dl") == "1":
        chemin_pdf = trouver_pdf()
        if chemin_pdf is None:
            app.logger.error("PDF introuvable dans %s (contenu : %s)",
                             BASE_DIR, os.listdir(BASE_DIR))
            return "Le guide est momentanément indisponible. Contactez-nous.", 503
        return send_file(chemin_pdf, as_attachment=True,
                         download_name=PDF_NAME, mimetype="application/pdf")

    return rendre(PRET, lien=url_for("telecharger", token=token, dl=1))


# --- Administration minimale : validation manuelle des paiements -----------
def cle_valide(cle):
    return bool(ADMIN_KEY) and secrets.compare_digest(cle or "", ADMIN_KEY)


@app.route("/admin")
def admin():
    cle = request.args.get("cle", "")
    if not cle_valide(cle):
        abort(404)
    with get_db() as conn:
        ventes = conn.execute(
            "SELECT * FROM ventes ORDER BY id DESC LIMIT 200").fetchall()
    return rendre(ADMIN, ventes=ventes, cle=cle)


@app.route("/admin/valider/<int:vente_id>", methods=["POST"])
def admin_valider(vente_id):
    cle = request.form.get("cle", "")
    if not cle_valide(cle):
        abort(404)
    with get_db() as conn:
        conn.execute("UPDATE ventes SET statut = 'valide' WHERE id = ?", (vente_id,))
    return redirect(url_for("admin", cle=cle))


@app.route("/diagnostic")
def diagnostic():
    """Aide au dépannage : /diagnostic?cle=VOTRE_ADMIN_KEY"""
    if not cle_valide(request.args.get("cle", "")):
        abort(404)
    trouve = trouver_pdf()
    fichiers = "\n".join(sorted(os.listdir(BASE_DIR)))
    texte = (f"Dossier de l'app : {BASE_DIR}\nPDF attendu : {PDF_NAME}\n"
             f"PDF trouvé : {trouve}\n\nContenu du dossier :\n{fichiers}")
    return texte, 200, {"Content-Type": "text/plain; charset=utf-8"}


@app.errorhandler(404)
def non_trouve(_):
    return "Page introuvable.", 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
