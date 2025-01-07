import logging
import os
from flask import current_app
import requests
from cryptography.fernet import Fernet
from dotenv import load_dotenv
from flask import (Flask, current_app, flash, make_response, redirect,
                   render_template, request, url_for)
from flask_mail import Mail, Message
from flask_sqlalchemy import SQLAlchemy

# Charger les variables d'environnement
load_dotenv()

app = Flask(__name__)

# Configuration de l'application
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///phishing_simulator.db'
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default_secret_key')

# Configuration Flask-Mail
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')

# Initialisation des services
mail = Mail(app)
db = SQLAlchemy(app)

# Logger pour suivre les erreurs et les événements
# logging.basicConfig(filename='app.log', level=logging.ERROR)

# Génération d'une clé de chiffrement pour sécuriser les clés API
encryption_key = os.getenv('ENCRYPTION_KEY', Fernet.generate_key())
cipher = Fernet(encryption_key)

@app.before_request
def add_global_variables():
    # Ajoute show_analytics à tous les templates
    current_app.jinja_env.globals.update(show_analytics=True)

# Modèles de base de données
class Campaign(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(300), nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.now())

class Contact(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=True)
    phone = db.Column(db.String(15), nullable=True)

class Interaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaign.id'), nullable=False)
    contact_id = db.Column(db.Integer, db.ForeignKey('contact.id'), nullable=False)
    action = db.Column(db.String(100), nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.now())

key = Fernet.generate_key()
print(key)
class ApiConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    api_type = db.Column(db.String(50), nullable=False)
    api_key = db.Column(db.String(255), nullable=False)
    api_secret = db.Column(db.String(255), nullable=False)
    api_url = db.Column(db.String(255), nullable=False)

    # Méthodes pour chiffrer et déchiffrer la clé API et le secret
    def set_api_key(self, key):
        self.api_key = cipher.encrypt(key.encode()).decode()

    def set_api_secret(self, secret):
        self.api_secret = cipher.encrypt(secret.encode()).decode()

    def get_api_key(self):
        return cipher.decrypt(self.api_key.encode()).decode()

    def get_api_secret(self):
        return cipher.decrypt(self.api_secret.encode()).decode()

# Fonction pour envoyer un email
def send_phishing_email(to_email, subject, content, campaign_id, contact_id, api=None):
    try:
        pixel_url = f"http://127.0.0.1:5001/track/{campaign_id}/{contact_id}"
        link_url = f"http://127.0.0.1:5001/click/{campaign_id}/{contact_id}"

        html_content = f"""
        {content}<br><br>
        <a href="{link_url}" style="color:blue; text-decoration:underline;">Cliquez ici pour plus d'informations</a><br>
        <img src="{pixel_url}" alt="" style="display:none;">
        """

        if api and api.api_type == 'email':
            url = api.api_url
            payload = {
                "from": {"email": "sender@example.com", "name": "Simulation"},
                "to": [{"email": to_email}],
                "subject": subject,
                "html": html_content
            }
            headers = {
                "Authorization": f"Bearer {api.get_api_key()}",
                "Content-Type": "application/json"
            }
            response = requests.post(url, headers=headers, json=payload)
            if response.status_code != 200:
                raise Exception(f"Erreur API : {response.text}")
        else:
            msg = Message(subject=subject, sender=app.config['MAIL_USERNAME'], recipients=[to_email])
            msg.body = content
            msg.html = html_content
            mail.send(msg)

        interaction = Interaction(campaign_id=campaign_id, contact_id=contact_id, action="email_sent")
        db.session.add(interaction)
        db.session.commit()
    except Exception as e:
        logging.error(f"Erreur d'envoi de l'email : {e}")




def send_sms_via_api(phone_number, message, api_id):
    try:
        # Récupérer l'API sélectionnée depuis la base de données
        api = ApiConfig.query.get(api_id)
        if not api:
            print("Aucune API trouvée.")
            return
        
        print(f"Utilisation de l'API {api.name} à l'URL {api.api_url}")
        print(f"Envoi du SMS à {phone_number} avec le message : {message}")

        if api.api_type == 'sms':
            url = f"{api.api_url}?to={phone_number}&body={message}"
            print(f"URL de l'API : {url}")  # Vérification de l'URL

            response = requests.post(url)

            # Logue la réponse de l'API
            if response.status_code == 200:
                print(f"SMS envoyé avec succès à {phone_number}: {response.text}")
            else:
                print(f"Erreur API SMS : {response.status_code} - {response.text}")

    except requests.exceptions.RequestException as e:
        print(f"Erreur lors de l'appel API SMS : {e}")




# Routes principales
@app.route('/')
def index():
    return redirect(url_for('dashboard'))

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if request.method == 'POST':
        campaign_id = request.form.get('campaign_id')
        contact_id = request.form.get('contact_id')
        if campaign_id:
            campaign = db.session.get(Campaign, campaign_id)
            campaign.name = request.form['name']
            campaign.description = request.form['description']
            db.session.commit()
        if contact_id:
            contact = db.session.get(Contact, contact_id)
            contact.name = request.form['name']
            contact.email = request.form['email']
            contact.phone = request.form['phone']
            db.session.commit()

    campaigns = Campaign.query.all()
    contacts = Contact.query.all()
    apis = ApiConfig.query.all()
    return render_template('dashboard.html', campaigns=campaigns, contacts=contacts, apis=apis)

@app.route('/create_campaign', methods=['GET', 'POST'])
def create_campaign():
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        new_campaign = Campaign(name=name, description=description)
        db.session.add(new_campaign)
        db.session.commit()
        return redirect(url_for('dashboard'))
    return render_template('create_campaign.html')

@app.route('/manage_contacts', methods=['GET', 'POST'])
def manage_contacts():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        new_contact = Contact(name=name, email=email, phone=phone)
        db.session.add(new_contact)
        db.session.commit()
        return redirect(url_for('dashboard'))
    return render_template('manage_contacts.html')

@app.route('/simulate_phishing', methods=['GET', 'POST'])
def simulate_phishing():
    campaigns = Campaign.query.all()
    contacts = Contact.query.all()
    apis = ApiConfig.query.all()

    success = False
    if request.method == 'POST':
        campaign_id = request.form['campaign_id']
        contact_type = request.form['contact_type']
        api_id = request.form.get('api_id')  # API sélectionnée

        # Récupérer la campagne
        campaign = db.session.get(Campaign, campaign_id)

        # Vérifier le type de contact et récupérer l'ID du contact
        if contact_type == 'email':
            contact_id = request.form['email_contact_id']
            contact = db.session.get(Contact, contact_id)
            if contact and contact.email:
                send_phishing_email(contact.email, f"Simulation : {campaign.name}", campaign.description, campaign_id, contact_id, api_id)
                success = True
        elif contact_type == 'phone':
            contact_id = request.form['phone_contact_id']
            contact = db.session.get(Contact, contact_id)
            if contact and contact.phone:
                sms_message = f"Bonjour, ceci est un test de phishing (avec la plateforme) lié à la campagne : {campaign.name}"

                # Appel de l'API pour envoyer le SMS
                send_sms_via_api(contact.phone, sms_message, api_id)
                success = True

        # Ajouter une interaction si le succès
        if success:
            interaction = Interaction(
                campaign_id=campaign_id,
                contact_id=contact_id,
                action="email_sent" if contact_type == 'email' else "sms_sent"
            )
            db.session.add(interaction)
            db.session.commit()

    return render_template('simulate_phishing.html', campaigns=campaigns, contacts=contacts, apis=apis, success=success)

@app.route('/analytics', methods=['GET'])
def analytics():
    campaigns = Campaign.query.all()
    contacts = Contact.query.all()
    interactions = Interaction.query.all()

    interaction_summary = {
        'email_sent': 0,
        'email_opened': 0,
        'clicked': 0
    }

    for interaction in interactions:
        if interaction.action in interaction_summary:
            interaction_summary[interaction.action] += 1

    return render_template('analytics.html', campaigns=campaigns, contacts=contacts, interactions=interactions,
                           interaction_summary=interaction_summary)

@app.route('/manage_apis', methods=['GET', 'POST'])
def manage_apis():
    if request.method == 'POST':
        # Récupérer les valeurs du formulaire
        name = request.form['name']
        api_type = request.form['api_type']
        api_key = request.form['api_key']
        api_secret = request.form['api_secret']
        api_url = request.form['api_url']

        # Créer un nouvel objet ApiConfig avec les données
        new_api = ApiConfig(name=name, api_type=api_type, api_key=api_key, api_secret=api_secret, api_url=api_url)

        # Ajouter à la session de la base de données
        db.session.add(new_api)
        db.session.commit()

        # Rediriger vers une autre page ou afficher un message de succès
        return redirect(url_for('success'))

    return render_template('manage_apis.html')  # Assurez-vous que le fichier HTML est bien accessible

@app.route('/success')
def success():
    return "API ajoutée avec succès!"


@app.route('/delete_campaign/<int:campaign_id>', methods=['POST'])
def delete_campaign(campaign_id):
    campaign = db.session.get(Campaign, campaign_id)
    if campaign:
        db.session.delete(campaign)
        db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/delete_contact/<int:contact_id>', methods=['POST'])
def delete_contact(contact_id):
    contact = db.session.get(Contact, contact_id)
    if contact:
        db.session.delete(contact)
        db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/delete_api/<int:api_id>', methods=['POST'])
def delete_api(api_id):
    api = db.session.get(ApiConfig, api_id)
    if api:
        db.session.delete(api)
        db.session.commit()
    return redirect(url_for('manage_apis'))

@app.route('/click/<int:campaign_id>/<int:contact_id>', methods=['GET'])
def track_link_click(campaign_id, contact_id):
    interaction = Interaction(campaign_id=campaign_id, contact_id=contact_id, action="clicked")
    db.session.add(interaction)
    db.session.commit()
    return redirect("https://example.com")

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5001)
