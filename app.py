from flask import Flask, render_template, request, redirect, url_for, session  # type: ignore[reportMissingImports]
import matplotlib  # type: ignore[reportMissingModuleSource]
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # type: ignore[reportMissingModuleSource]

app = Flask(__name__)
app.secret_key = "temporary-development-secret-change-me"

TEST_EMAIL = "test@cashcache.com"
TEST_PASSWORD = "CashCache123!"

@app.before_request
def require_login():
    protected_pages = ["home", "subscriptions", "budgeting"]

    if request.endpoint in protected_pages:
        if not session.get("logged_in"):
            return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    error = ""

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if email == TEST_EMAIL and password == TEST_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("home"))

        error = "Invalid email or password."

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

@app.route("/subscriptions")
def subscriptions():
    return render_template("subscriptions.html")

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
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(debug=True)
