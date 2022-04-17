import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    holding = []
    s_total = 0
    # Get the user's holdings from the database
    holdings = db.execute("SELECT * FROM holdings WHERE userid = ?", session['user_id'])
    for i in holdings:
        holding.append(i)

    # Adds price and total to variable that is to be passed
    for row in holding:
        stock = lookup(row['symbol'])
        row['price'] = stock['price']
        row['total'] = stock['price'] * row['shares']
        s_total += row['total']

    # Looks up user's total cash
    cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
    user_cash = cash[0]['cash']
    total = s_total + user_cash
    return render_template("index.html", holding = holding, cash = user_cash, total = total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # User submits the form
    if request.method == "POST":
        symbol = request.form.get("symbol")
        try:
            float(request.form.get("shares"))
        except ValueError:
            return apology("Enter correct no. of share", 400)
        else:
            nshares = float(request.form.get("shares"))

        # Checks if the user entered a valid amount of shares
        if nshares < 1 or not nshares.is_integer():
            return apology("Enter a valid amount of shares", 400)

        # Makes the API call
        stock =  lookup(symbol)

        # Checks if it is a valid symbol
        if not stock:
            return apology("Symbol doesn't exist", 400)

        # Looks up user's total cash
        cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        user_cash = cash[0]['cash']

        # Checks if user have enough cash
        if (nshares * stock['price']) < user_cash:

            # Checks if user already has shares of the required symbol
            if not db.execute("SELECT userid FROM holdings WHERE symbol = ? AND userid = ?", symbol, session["user_id"]):

                # Enter purchase info to the table
                db.execute("INSERT INTO holdings (userid, symbol, shares, price, name) VALUES (?, ?, ?, ?, ?)", session["user_id"], symbol, nshares, nshares * stock['price'], stock['name'])
                # Update user database: price
                db.execute("UPDATE users SET cash = cash - ? WHERE id = ?", nshares * stock['price'], session['user_id'])
                # Enter transaction details into the table
                db.execute("INSERT INTO transactions (userid, sshares, symbol, price, t_time) VALUES (?, ?, ?, ?, datetime('now'))", session['user_id'], nshares, symbol, nshares*stock['price'])
                return redirect("/")

            # if user already has the selected symbol
            else:
                # Updates the database
                db.execute("UPDATE holdings SET shares = shares + ?, price = price + (?) WHERE userid = ? AND symbol = ?", nshares, nshares * stock['price'], session['user_id'], symbol)
                # Update user database: price
                db.execute("UPDATE users SET cash = cash - ? WHERE id = ? ", nshares * stock['price'], session['user_id'] )
                # Enters transaction details into table
                db.execute("INSERT INTO transactions (userid, sshares, symbol, price, t_time) VALUES (?, ?, ?, ?, datetime('now'))", session['user_id'], nshares, symbol, nshares*stock['price'])

                # Redirects to homepage
                return redirect("/")
        else:
            return apology("Not enough cash", 400)


    elif request.method == "GET":
        return render_template("buy.html")



@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    transaction = []

    # Getting the data from the database
    transactions = db.execute("SELECT * FROM transactions WHERE userid = ?", session['user_id'])
    for i in transactions:
        transaction.append(i)
    return render_template("history.html", transaction = transaction)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 400)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    # Renders qoute page
    if request.method == "GET":
        return render_template("quote.html")

    # When the form is submitted
    elif request.method == "POST":
        symbol = request.form.get("symbol")
        # Makes the API call
        stock =  lookup(symbol)
        if not stock:
            return apology("Symbol doesn't exist", 400)
        else:
            return render_template("quoted.html", name = stock['name'], price = stock['price'], symbol = stock['symbol'])




@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "GET":
        return render_template("register.html")

    # Checks if user enters valid information
    elif request.method == "POST":
        if not request.form.get("username"):
            return apology("must provide username", 400)
        elif not request.form.get("password"):
            return apology("must provide password", 400)
        elif not request.form.get("password") == request.form.get("confirmation"):
            return apology("re-enter the same password", 400)

        # Checks if username already exists
        userlist = db.execute("SELECT username FROM users WHERE username is ?", request.form.get("username"))
        if not userlist:
            db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", request.form.get("username"), generate_password_hash(request.form.get("password")))
            return redirect("/login")
        else:
            return apology("Username already exists", 400)

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    # Getting the symbols user currently pocess
    usymbol = []
    sym = db.execute("SELECT symbol FROM holdings WHERE userid = ?", session['user_id'])
    for i in sym:
            usymbol.append(i['symbol'])

    #If the user submits the form
    if request.method == "POST":

        # Get form details
        symbol = request.form.get("symbol")
        # No. of shares
        try:
            float(request.form.get("shares"))
        except ValueError:
            return apology("Enter correct no. of share", 400)
        else:
            nshares = float(request.form.get("shares"))

        # If the user doesn't have the symbol
        if symbol not in usymbol:
            return apology("Enter correct symbol", 400)

        # If the user does not enter the amount of shares required
        if not nshares:
            return apology("Enter amount of shares", 400)

        # Gets user's shares
        ushares = db.execute("SELECT shares FROM holdings WHERE userid = ? AND symbol = ?", session['user_id'], symbol)
        ushares = ushares[0]['shares']

        # Checks if user has enough shares
        if nshares > ushares:
            return apology("Not enough shares", 400)

        if nshares < 1 or not nshares.is_integer():
            return apology("Enter a positive integer", 400)

        # Update holdings and users table

        # Getting stock price
        price = lookup(symbol)
        price = price['price']

        # If user sells all shares from the given symbol
        if ushares - nshares == 0:
            db.execute("DELETE FROM holdings WHERE userid = ? AND symbol = ?", session['user_id'], symbol)
            db.execute("UPDATE users SET cash = cash + ? WHERE id = ?", price*nshares, session['user_id'])
            # Enters transaction history into table
            db.execute("INSERT INTO transactions (userid, sshares, symbol, price, t_time) VALUES (?, ?, ?, ?, datetime('now'))", session['user_id'], -nshares, symbol, nshares*price)
            return redirect("/")

        # User sells his shares
        else:
            print(nshares)
            db.execute("UPDATE holdings SET shares = shares - ? , price = price - ? WHERE userid = ? AND symbol = ?", nshares, price*nshares, session['user_id'], symbol)
            db.execute("UPDATE users SET cash = cash + ? WHERE id = ?", price*nshares, session['user_id'])
            # Enters transaction history into table
            db.execute("INSERT INTO transactions (userid, sshares, symbol, price, t_time) VALUES (?, ?, ?, ?, datetime('now'))", session['user_id'], -nshares, symbol, nshares*price)
            return redirect("/")

    else:
        return render_template("sell.html", symbol = usymbol)


@app.route("/money", methods=["GET", "POST"])
@login_required
def money():
    if request.method == "GET":
        return render_template("money.html")

    else:
        # Gets the user entered values
        action = request.form.get('action')
        amount = int(request.form.get('amount'))

        # Checks if the amount is a positive integer
        if not amount > 0:
            return apology("Enter a positive integer", 403)

        if action == "Add":
            db.execute("UPDATE users SET cash = cash + ? WHERE id = ?", amount, session['user_id'])

        if action == "Withdraw":
            db.execute("UPDATE users SET cash = cash - ? WHERE id = ?", amount, session['user_id'])

        return redirect("/")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
