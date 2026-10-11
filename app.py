from flask import Flask, render_template
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

app = Flask(__name__)


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

if __name__ == "__main__":
    app.run(debug=True)