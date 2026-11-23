from flask import Flask, render_template, request, redirect, url_for, session
import matplotlib 
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import calendar
from datetime import date
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

supabase_url = os.environ["SUPABASE_URL"]
supabase_key = os.environ["SUPABASE_KEY"]

supabase = create_client(supabase_url, supabase_key)

app = Flask(__name__)
app.secret_key = "temporary-development-secret-change-me"

TEST_USERNAME = "cash"
TEST_EMAIL = "cash@gmail.com"
TEST_PASSWORD = "cash"

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

def get_supabase():
    return create_client(supabase_url, supabase_key)

@app.before_request
def require_login():
    protected_pages = ["home", "subscriptions", "budgeting", "reminders", "social"]

    if request.endpoint in protected_pages:
        if not session.get("logged_in"):
            return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    error = ""

    if request.method == "POST":
        username_or_email = request.form.get("username_or_email", "").strip()
        password = request.form.get("password", "")

        if not username_or_email or not password:
            error = "Please fill out all fields."

        else:
            try:
                supabase = get_supabase()

                response = supabase.auth.sign_in_with_password({
                    "email": username_or_email,
                    "password": password
                })

                if response.get("user") and response.session:
                    session.clear()
                    session["logged_in"] = True
                    session["username"] = response.username
                    session["email"] = response.user.email

                    return redirect(url_for("home"))

                error = "Invalid username/email or password."

            except Exception:
                app.logger.exception("Error during login")
                error = "An error occurred during login. Please try again."

    return render_template("login.html", error=error)   



@app.route("/")
def home():

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

@app.route("/reminders")
def reminders():
    return render_template("reminders.html")


@app.route("/social")
def social():
    friends = [
        {"username": "Laurence", "points": 1250, "level": 6},
        {"username": "Adam", "points": 980, "level": 5},
        {"username": "Michael", "points": 875, "level": 3}
    ]

    current_user = {
        "username": "cash",
        "points": 1250,
        "level": 4
    }

    leaderboard = friends + [current_user]
    leaderboard.sort(key=lambda user: user["points"], reverse=True)

    return render_template(
        "social.html",
        friends=friends,
        current_user=current_user,
        leaderboard=leaderboard
    )

@app.route("/register", methods=["GET", "POST"])
def register():
    error = ""
    success = ""

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not username or not email or not password or not confirm_password:
            error = "Please fill out all fields."

        elif password != confirm_password:
            error = "Passwords do not match."

        elif len(password) < 6:
            error = "Password must contain at least 6 characters."

        else:
            try:
                response = supabase.auth.sign_up({
                    "email": email,
                    "password": password,
                    "options": {
                        "data": {
                            "username": username
                        }
                    }
                })

                success = "Registration submitted! Please check your email for a confirmation link."

            except Exception as e:
                error = f"Registration failed: {str(e)}"

    return render_template("register.html", error=error, success=success)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(debug=True)
