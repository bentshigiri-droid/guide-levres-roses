import os
import sqlite3
from flask import Flask, render_template_string, request, send_file, redirect, url_for

app = Flask(__name__)

# Dossier de base de l'application
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'ventes.db')
PDF_FILENAME = "Levres_Roses_Naturelles_Guide.pdf"

# Initialisation de la base de données SQLite
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ventes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telephone TEXT NOT NULL,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Code HTML de la landing page (design propre et optimisé mobile)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Guide Ultime - Lèvres Roses Naturelles</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #faf5f5; color: #333; margin: 0; padding: 20px; }
        .container { max-width: 600px; margin: 0 auto; background: #fff; padding: 25px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.08); }
        h1 { color: #d63384; font-size: 24px; text-align: center; margin-bottom: 10px; }
        p { line-height: 1.6; color: #555; }
        .price { font-size: 22px; font-weight: bold; color: #28a745; text-align: center; margin: 20px 0; }
        .steps { background: #fff3f3; padding: 15px; border-left: 4px solid #d63384; border-radius: 4px; margin: 20px 0; }
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; font-weight: bold; }
        input[type="text"] { width: 100%; padding: 12px; border: 1px solid #ccc; border-radius: 6px; box-sizing: border-box; font-size: 16px; }
        button { background-color: #d63384; color: white; border: none; padding: 12px 20px; width: 100%; font-size: 18px; border-radius: 6px; cursor: pointer; font-weight: bold; }
        button:hover { background-color: #b02a6b; }
        .footer { text-align: center; margin-top: 25px; font-size: 12px; color: #888; }
    </style>
</head>
<body>
    <div class="container">
        <h1>💋 Guide Ultime : Avoir des Lèvres Roses et Naturelles</h1>
        <p>Découvrez la méthode secrète 100% naturelle pour éliminer les taches sombres, hydrater en profondeur et retrouver des lèvres douces et éclatantes.</p>
        
        <div class="price">Prix unique : 100 FCFA</div>

        <div class="steps">
            <strong>Comment ça marche ?</strong>
            <ol>
                <li>Payez 100 FCFA par <b>Airtel Money</b> au numéro : <b style="color: #d63384;">077 45 41 32</b></li>
                <li>Entrez votre numéro de téléphone ci-dessous pour valider.</li>
                <li>Téléchargez instantanément votre guide PDF !</li>
            </ol>
        </div>

        <form method="POST" action="/valider">
            <div class="form-group">
                <label for="telephone">Votre numéro Airtel Money utilisé pour le paiement :</label>
                <input type="text" id="telephone" name="telephone" placeholder="Ex: 077XXXXXX" required>
            </div>
            <button type="submit">Valider et Télécharger le Guide</button>
        </form>

        <div class="footer">
            Service sécurisé - Gabon 🇬🇦
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/valider', methods=['POST'])
def valider():
    telephone = request.form.get('telephone')
    if telephone:
        # Enregistrement de la vente dans SQLite
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO ventes (telephone) VALUES (?)", (telephone,))
        conn.commit()
        conn.close()
    
    # Redirection vers la page de téléchargement sécurisée
    return redirect(url_for('telecharger_fic', tel=telephone))

@app.route('/telecharger/<tel>')
def telecharger_fic(tel):
    pdf_path = os.path.join(BASE_DIR, PDF_FILENAME)
    if os.path.exists(pdf_path):
        return send_file(pdf_path, as_attachment=True)
    else:
        return "Erreur : Le fichier PDF est introuvable sur le serveur.", 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
