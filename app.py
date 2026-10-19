from datetime import timedelta
from dbm import error
import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session  # type: ignore[reportMissingImports]
import matplotlib  # type: ignore[reportMissingModuleSource]
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # type: ignore[reportMissingModuleSource]
from argon2.exceptions import VerifyMismatchError
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

# Import database tools and models from the other files
from extensions import db, ph
from models import User, UserProfile


app = Flask(__name__)
app.secret_key = "temporary-development-secret-change-me"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# CRUCIAL: Set a secret key. In production, use an environment variable.
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a_very_secret_and_complex_random_string_12345')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)
app.config['SESSION_REFRESH_EACH_REQUEST'] = True

db.init_app(app)

with app.app_context():
    db.create_all()
    TEST_EMAIL = "cash@gmail.com"
    TEST_USERNAME = "cash"
    TEST_PASSWORD = "cash"
    seed_check = User.query.filter_by(email=TEST_EMAIL).first()

    if not seed_check:
        print("🌱 Seeding database with default test user...")
        try:
            hashed_test_password = ph.hash(TEST_PASSWORD)
            
            test_user = User(
                email=TEST_EMAIL,
                password_hash=hashed_test_password
            )
            
            test_profile = UserProfile(
                username=TEST_USERNAME,
                user=test_user,
                first_name="Cash",
                last_name="Cache"
            )
            
            db.session.add(test_user)
            db.session.add(test_profile)
            db.session.commit()
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
    if request.method == "POST":
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password')

        # Basic input validation
        if not username or not email or not password:
            flash("All fields are required.", "error")
            return render_template('register.html')
        
        if len(password) < 4:
            flash("Password must be at least 4 characters long.", "error")
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

            # SECURELY HASH THE PASSWORD: Argon2 automatically handles unique salts
            hashed_password = ph.hash(password)

            # Create the core authentication record
            new_user = User(
                email=email,
                password_hash=hashed_password
            )

            # Create the separate profile record and link it via the foreign key relationship
            new_profile = UserProfile(
                username=username,
                user=new_user
            )

            # Save both records to the database transactionally
            db.session.add(new_user)
            db.session.add(new_profile)
            db.session.commit()

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
