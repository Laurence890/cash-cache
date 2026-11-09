from datetime import datetime, timezone, timedelta
from dbm import error
import os
import uuid

from flask import Flask, render_template, render_template_string, request, jsonify, redirect, url_for, flash, session  # type: ignore[reportMissingImports]
from flask_api import FlaskAPI, status
from flask_api.exceptions import APIException

import matplotlib  # type: ignore[reportMissingModuleSource]
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # type: ignore[reportMissingModuleSource]
from argon2.exceptions import VerifyMismatchError

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

import resend

import plaid
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequest_User
from plaid.model.products import Products
from plaid.model.country_code import CountryCode
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest

# Import database tools and models from the other files
from extensions import db, ph, plaid_client
from models import User, UserProfile


app = Flask(__name__)
app.secret_key = "temporary-development-secret-change-me"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# CRUCIAL: Set a secret key. In production, use an environment variable.
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a_very_secret_and_complex_random_string_12345')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)
app.config['SESSION_REFRESH_EACH_REQUEST'] = True

resend.api_key = os.environ.get("RESEND_API_KEY")

db.init_app(app)

def _create_user(email, password, username, first_name="", last_name=""):
    user = User(
        email=email,
        password_hash=ph.hash(password)
    )
    profile = UserProfile(
        username=username,
        user=user,
        first_name=first_name,
        last_name=last_name
    )

    db.session.add(user)
    db.session.add(profile)
    db.session.commit()
    return user

def _send_verification_email(user):
    token = uuid.uuid4().hex
    user.verification_token = token
    user.token_expiry = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=24)
    db.session.commit()
    verification_url = f"" + f"verify-email?token={user.verification_token}"
    try:
        resend.Emails.send({
            "from": "onboarding@resend.dev", # Or your verified domain
            "to": user.email,
            "subject": "Verify your email address",
            "html": f"<p>Welcome! Please verify your email by clicking <a href='{verification_url}'>here</a>.</p>"
        })
    except Exception as e:
        return jsonify({"error": "Failed to send email"}), 500
    return jsonify({"message": "User registered. Please check your email to verify."}), 201


with app.app_context():
    db.create_all()
    TEST_EMAIL = "cash@gmail.com"
    TEST_USERNAME = "cash"
    TEST_PASSWORD = "cash"
    seed_check = User.query.filter_by(email=TEST_EMAIL).first()

    if not seed_check:
        print("🌱 Seeding database with default test user...")
        try:
            _create_user(
                email=TEST_EMAIL,
                password=TEST_PASSWORD,
                username=TEST_USERNAME,
                first_name="Cash",
                last_name="Cache"
            )
            print("✅ Default test user created successfully!")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Failed to seed automatic test user: {e}")

subscriptions_data = [
    {
        "name": "Netflix",
        "cost": 15.49,
        "billing_date": "Renews October 15",
        "color": "netflix-card"
    },
    {
        "name": "Spotify",
        "cost": 11.99,
        "billing_date": "Renews October 18",
        "color": "spotify-card"
    },
    {
        "name": "iCloud+",
        "cost": 2.99,
        "billing_date": "Renews October 20",
        "color": "icloud-card"
    },
    {
        "name": "Gym Membership",
        "cost": 44.49,
        "billing_date": "Renews October 25",
        "color": "gym-card"
    }
]

@app.before_request
def require_login():
    protected_pages = ["home", "subscriptions", "budgeting"]

    if request.endpoint in protected_pages:
        if not session.get("logged_in"):
            return redirect(url_for("login"))

@app.route('/register', methods=['GET', 'POST'])
def register():
    data = request.form
    if request.method == "POST":
        username = data.get('username', '').strip()
        email = data.get('email', '').strip().lower()
        password = data.get('password')

        # Basic input validation
        if not username or not email or not password:
            flash("All fields are required.", "error")
            return render_template('register.html')
        
        if (
            len(password) < 8
            or not any(character.islower() for character in password)
            or not any(character.isupper() for character in password)
            or not any(
                not character.isalnum() and not character.isspace()
                for character in password
            )
        ):
            flash(
                "Password must be at least 8 characters long and include at least "
                "one lowercase letter, one uppercase letter, and one special character.",
                "error"
            )
            return render_template('register.html')

        try:
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                flash("That email address is already registered.", "error")
                return render_template('register.html')

            existing_profile = UserProfile.query.filter_by(username=username).first()
            if existing_profile:
                flash("That username is already taken.", "error")
                return render_template('register.html')

            _create_user(email=email, password=password, username=username)

            flash("Registration successful! Please log in.", "success")
            return redirect(url_for('login'))

        except IntegrityError:
            db.session.rollback()
            flash("A database conflict occurred. Please try a different username or email.", "error")
            return render_template('register.html')

        except Exception as e:
            db.session.rollback()
            print(f"DATABASE ERROR ON REGISTRATION: {e}")
            flash("An unexpected error occurred on our end. Please try again later.", "error")
            return render_template('register.html'), 500

    return render_template('register.html')

@app.route('/send-verification', methods=['POST'])
def send_verification():
    email = request.form.get('email', '').strip()
    user = User.query.filter_by(email=email).first()

    if not user:
        return jsonify({"message": "If that email exists, a new link has been sent."}), 200

    if user.is_verified:
        return jsonify({"error": "This account is already verified."}), 400

    user.verification_token = uuid.uuid4().hex
    db.session.commit()

    try:
        _send_verification_email(user)
        return jsonify({"message": "If that email exists, a new link has been sent."}), 200
    except Exception as e:
        return jsonify({"error": "Failed to send email"}), 500

@app.route('/verify-email', methods=['GET'])
def verify_email():
    token = request.args.get('token')

    if not token:
        flash("Invalid verification token.", "error")
        return redirect(url_for('login'))

    user = User.query.filter_by(verification_token=token).first()
    if not user:
        flash("Invalid verification token.", "error")
        return redirect(url_for('login'))

    if user.is_verified:
        flash("Email is already verified.", "error")
        #return redirect(f"{FRONTEND_URL}/login?msg=already_verified")
        return redirect(url_for('login'))

    current_time = datetime.now(timezone.utc).replace(tzinfo=None)
    if user.token_expiry < current_time:
        flash("Verification token has expired.", "error")
        #return redirect(f"{FRONTEND_URL}/verify-expired?email={user.email}")
        return redirect(url_for('login'))

    user.is_verified = True
    user.verification_token = None
    user.token_expiry = None
    db.session.commit()

    flash("Email verified successfully!", "success")
    #return redirect(f"{FRONTEND_URL}/verify-success")
    return redirect(url_for('login'))

@app.route("/login", methods=["GET", "POST"])
def login():
    error = ""

    if request.method == "POST":

        username_or_email = request.form.get("username_or_email", "").strip()
        email = request.form.get('email')
        password = request.form.get("password", "")

        generic_error = "Invalid username or password"

        try:
            user = User.query.filter(or_(
                User.email == username_or_email,
                UserProfile.username == username_or_email)
                ).join(UserProfile).first()

            if not user:
                # Run dummy verification to prevent timing attacks
                try:
                    ph.verify("$argon2id$v=19$m=65536,t=3,p=4$dummyhashdummyhash$dummyhash", password)
                except VerifyMismatchError:
                    pass
                flash(generic_error, "error") # Sends error message to the HTML page
                return render_template('login.html') # Reload page with the error

            ph.verify(user.password_hash, password)
            
            if not user.is_active:
                flash("This account has been deactivated.", "error")
                return render_template('login.html') 

            session.clear()
            session.permanent = True 
            session['user_id'] = user.id
            flash("Welcome back!", "success")
            return redirect(url_for("home"))
            
        except VerifyMismatchError:
            flash(generic_error, "error")
            return render_template('login.html')

        except Exception as e:
            print(f"DATABASE ERROR ON LOGIN: {e}") 
            
            flash("An unexpected internal server error occurred. Please try again later.", "error")
            return render_template('login.html'), 500
        
    # If GET request, display the clean login screen
    return render_template('login.html', error=error)

@app.route("/auth/verify-email-success/<int:user_id>", methods=["GET"])
def verify_email_and_trigger_plaid(user_id):

    try:
        # 1. Prepare request details for Plaid
        plaid_request = LinkTokenCreateRequest(
            products=[Products('auth'), Products('transactions')],
            client_name="College Project Web App",
            country_codes=[CountryCode('US')],
            language='en',
            user=LinkTokenCreateRequest_User(
                client_user_id=str(user_id) # Plaid needs a unique string identifier
            )
        )
        
        # 2. Generate the short-lived Link Token
        response = plaid_client.link_token_create(plaid_request)
        link_token = response['link_token']
        
        # 3. Use render_template_string to inject the link token cleanly into our test DOM
        html_template = """
        <!DOCTYPE html>
        <html>
        <head><title>Plaid Test Interface</title></head>
        <body style="font-family: Arial, sans-serif; padding: 50px; text-align: center;">
            <h2>🎉 Email Verified Successfully!</h2>
            <p>Test your Plaid backend integration before the front-end pages are built.</p>
            <button id="link-button" style="padding: 12px 24px; font-size: 16px; cursor: pointer; background:#00c08b; color:white; border:none; border-radius:5px;">
                Link Mock Bank Account
            </button>

            <script src="https://plaid.com"></script>
            <script>
                const handler = Plaid.create({
                    token: '{{ link_token }}',
                    onSuccess: (public_token, metadata) => {
                        // Automatically push the public token back to your Flask backend
                        fetch('/api/plaid/exchange', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ 
                                public_token: public_token,
                                user_id: {{ user_id }}
                            })
                        })
                        .then(res => res.json())
                        .then(data => alert('Success! Plaid Access Token saved to database.'))
                        .catch(err => alert('Error executing backend token exchange.'));
                    },
                    onExit: (err, metadata) => { if (err != null) console.error(err); }
                });

                document.getElementById('link-button').onclick = () => handler.open();
            </script>
        </body>
        </html>
        """
        return render_template_string(html_template, link_token=link_token, user_id=user_id)

    except plaid.ApiException as e:
        return jsonify({"error": f"Plaid Link Generation Failed: {e.body}"}), 400

@app.route("/api/plaid/exchange", methods=["POST"])
def exchange_public_token():
    """
    Receives public_token from client, requests permanent access_token 
    from Plaid, and commits it into the database via Flask-SQLAlchemy.
    """
    data = request.get_json()
    public_token = data.get("public_token")
    user_id = data.get("user_id")

    if not public_token or not user_id:
        return jsonify({"error": "Missing payload fields"}), 400

    try:
        # 1. Trade the public token for the permanent access token
        exchange_request = ItemPublicTokenExchangeRequest(public_token=public_token)
        exchange_response = plaid_client.item_public_token_exchange(exchange_request)
        
        access_token = exchange_response['access_token']
        item_id = exchange_response['item_id']
        
        # 2. Update your database using standard Flask-SQLAlchemy syntax
        profile = UserProfile.query.filter_by(user_id=user_id).first()
        
        if profile:
            profile.plaid_access_token = access_token
            profile.plaid_item_id = item_id
            db.session.commit()
            
            print(f"--- SUCCESS: DB Entry Updated for User {user_id} ---")
            print(f"Access Token Saved: {access_token}")
            
            return jsonify({"status": "success", "message": "Tokens saved successfully."})
        else:
            return jsonify({"error": "UserProfile matching user_id not found"}), 404

    except plaid.ApiException as e:
        return jsonify({"error": f"Plaid Exchange Failed: {e.body}"}), 400

@app.route("/")
def home():
    user_id = session.get('user_id')
    if not user_id:
        flash("Please log in to access this page.", "error")
        return redirect(url_for('login'))
    try:
        user = User.query.get(user_id)
        if not user or not user.is_active:
            session.clear()
            flash("Your session is invalid or has expired.", "error")
            return redirect(url_for('login'))
        

        months = ["May", "June", "July", "August", "September", "October"]
        spending = [250, 300, 220, 400, 350, 275]

        plt.figure(figsize=(8, 4))
        plt.plot(months, spending, marker="o")
        plt.title("Spending Over Time")
        plt.xlabel("Date")
        plt.ylabel("Amount Spent ($)")
        plt.grid(True)

        plt.savefig("static/spending.png", bbox_inches="tight")
        plt.close()

        return render_template("dashboard.html")

    except Exception as e:
        print(f"Error loading dashboard: {e}")
        flash("An error occurred loading your dashboard.", "error")
        return redirect(url_for('login'))

@app.route("/subscriptions", methods=["GET", "POST"])
def subscriptions():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        cost = request.form.get("cost", "").strip()
        billing_date = request.form.get("billing_date", "")

        try:
            cost = float(cost)

            if name and cost > 0 and billing_date:
                date_parts = billing_date.split("-")
                month = int(date_parts[1])
                day = int(date_parts[2])

                month_names = [
                    "January", "February", "March", "April",
                    "May", "June", "July", "August",
                    "September", "October", "November", "December"
                ]

                subscriptions_data.append({
                    "name": name,
                    "cost": cost,
                    "billing_date": f"Renews {month_names[month - 1]} {day}",
                    "color": "new-subscription-card"
                })

        except (ValueError, IndexError):
            pass

        return redirect(url_for("subscriptions"))

    total_cost = sum(item["cost"] for item in subscriptions_data)

    return render_template(
        "subscriptions.html",
        subscriptions=subscriptions_data,
        total_cost=total_cost
    )


@app.route("/subscriptions/remove/<int:subscription_index>", methods=["POST"])
def remove_subscription(subscription_index):
    if 0 <= subscription_index < len(subscriptions_data):
        subscriptions_data.pop(subscription_index)

    return redirect(url_for("subscriptions"))

budgets_data = [
    {"category": "Food", "limit": 400, "spent": 250},
    {"category": "Transportation", "limit": 200, "spent": 100},
    {"category": "Entertainment", "limit": 150, "spent": 90}
]

@app.route("/budgeting", methods=["GET", "POST"])
def budgeting():
    if request.method == "POST":
        category = request.form.get("category", "").strip()

        try:
            limit = float(request.form.get("limit", ""))

            if category and limit > 0:
                budgets_data.append({
                    "category": category,
                    "limit": limit,
                    "spent": 0
                })
        except ValueError:
            pass

        return redirect(url_for("budgeting"))

    total_limit = sum(item["limit"] for item in budgets_data)
    total_spent = sum(item["spent"] for item in budgets_data)

    for item in budgets_data:
        item["percentage"] = min(item["spent"] / item["limit"] * 100, 100)

    return render_template(
        "budgeting.html",
        budgets=budgets_data,
        total_limit=total_limit,
        total_spent=total_spent,
        remaining=total_limit - total_spent
    )

@app.route("/budgeting/remove/<int:budget_index>", methods=["POST"])
def remove_budget(budget_index):
    if 0 <= budget_index < len(budgets_data):
        budgets_data.pop(budget_index)

    return redirect(url_for("budgeting"))

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been successfully logged out.", "success")
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(debug=True)
