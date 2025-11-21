from flask import Flask, request, jsonify, render_template, redirect, url_for, session, flash
from pymongo import MongoClient
from datetime import datetime
from sklearn.linear_model import LinearRegression
import numpy as np
import requests

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # For session management

client = MongoClient('mongodb://localhost:27017')
db = client['crypto_app']
users = db['users']
activity_log = db['activity_log']


def log_activity(username, action, details=None):
    activity_log.insert_one({
        'username': username,
        'action': action,
        'details': details,
        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })


@app.route("/check_login")
def check_login():
    return jsonify({"logged_in": "user" in session})


def get_binance_data(symbol="BTCUSDT", interval="1d", limit=100):
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    response = requests.get(url, params=params)
    data = response.json()
    prices = []
    for i, entry in enumerate(data):
        close = float(entry[4])
        prices.append((i, close))
    return prices


def train_model(symbol="BTCUSDT"):
    data = get_binance_data(symbol)
    X = np.array([[d[0]] for d in data])
    y = np.array([d[1] for d in data])
    model = LinearRegression().fit(X, y)
    return model


@app.route('/')
def home():
    user = session.get('user')
    return render_template('index.html', user=user)

from lstm_model import predict_future_price

@app.route('/predict', methods=['POST'])
def predict():
    if 'user' not in session:
        return jsonify({"error": "Please log in to use the prediction feature."}), 401

    data = request.get_json()
    try:
        day = int(data.get("day", 0))
        symbol = data.get("symbol", "BTCUSDT").upper()

        if day <= 0:
            return jsonify({"error": "Please enter a valid future day number."}), 400

        # Use LSTM Prediction
        prediction = predict_future_price(symbol, day)

        # Log user activity
        activity_log.insert_one({
            "username": session['user']['username'],
            "action": f"Predicted {symbol} for {day} days ahead",
            "symbol": symbol,
            "day": day,
            "predicted_price": float(prediction),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

        return jsonify({"symbol": symbol, "day": day, "prediction": float(prediction)})

    except Exception as e:
        return jsonify({"error": str(e)}), 500



@app.route('/trade', methods=['POST'])
def trade():
    if 'user' not in session:
        return jsonify({"message": "You must be logged in to trade!"}), 401

    data = request.get_json()
    action = data.get("action")  # 'buy' or 'sell'
    symbol = data.get("symbol")
    quantity = float(data.get("quantity", 1))

    if action not in ['buy', 'sell']:
        return jsonify({"error": "Invalid trade action."}), 400
    if quantity <= 0:
        return jsonify({"error": "Quantity must be positive."}), 400

    # get latest price from Binance
    try:
        price_resp = requests.get("https://api.binance.com/api/v3/ticker/price", params={"symbol": symbol})
        price_json = price_resp.json()
        current_price = float(price_json.get("price"))
    except Exception as e:
        return jsonify({"error": "Failed to fetch current price."}), 500

    user_db = users.find_one({"username": session['user']['username']})
    if not user_db:
        return jsonify({"error": "User not found."}), 404

    balance = float(user_db.get('balance', 0.0))
    holdings = user_db.get('holdings', {}) or {}

    # perform buy
    if action == 'buy':
        cost = current_price * quantity
        if balance < cost:
            return jsonify({"error": "Insufficient balance."}), 400

        # update holdings
        holdings[symbol] = float(holdings.get(symbol, 0.0)) + quantity
        balance -= cost

        users.update_one({"username": user_db['username']},
                         {"$set": {"balance": balance, "holdings": holdings}})

        log_activity(user_db['username'], f"Bought {quantity} {symbol} at {current_price}", {"symbol": symbol, "price": current_price, "quantity": quantity})

        # update session copy
        session['user']['balance'] = balance
        session['user']['holdings'] = holdings

        return jsonify({"message": f"Bought {quantity} {symbol} for ${cost:.2f}.", "balance": balance, "holdings": holdings})

    # perform sell
    if action == 'sell':
        owned = float(holdings.get(symbol, 0.0))
        if owned < quantity:
            return jsonify({"error": f"Not enough {symbol} to sell."}), 400

        proceeds = current_price * quantity
        holdings[symbol] = owned - quantity
        # remove key if zero
        if holdings[symbol] <= 0:
            holdings.pop(symbol, None)

        balance += proceeds

        users.update_one({"username": user_db['username']},
                         {"$set": {"balance": balance, "holdings": holdings}})

        log_activity(user_db['username'], f"Sold {quantity} {symbol} at {current_price}", {"symbol": symbol, "price": current_price, "quantity": quantity})

        session['user']['balance'] = balance
        session['user']['holdings'] = holdings

        return jsonify({"message": f"Sold {quantity} {symbol} for ${proceeds:.2f}.", "balance": balance, "holdings": holdings})

    return jsonify({"error": "Unhandled trade action."}), 400


@app.route('/account')
def account():
    if 'user' not in session:
        return jsonify({"logged_in": False}), 401

    user_db = users.find_one({"username": session['user']['username']})
    if not user_db:
        return jsonify({"error": "User not found"}), 404

    return jsonify({
        "username": user_db['username'],
        "email": user_db.get('email'),
        "balance": float(user_db.get('balance', 0.0)),
        "holdings": user_db.get('holdings', {}) or {}
    })


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user_db = users.find_one({'username': username, 'password': password})

        if user_db:
            session['user'] = {
                'username': user_db['username'],
                'email': user_db.get('email'),
                'balance': float(user_db.get('balance', 0.0)),
                'holdings': user_db.get('holdings', {}) or {}
            }
            flash("Login successful!", "success")
            return redirect(url_for('home'))
        else:
            flash("Invalid credentials!", "danger")
            return redirect(url_for('login'))
    return render_template('login.html')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        if users.find_one({'username': username}):
            flash("User already exists!")
            return redirect(url_for('signup'))

        # create demo account: starting balance and empty holdings
        users.insert_one({
            'username': username,
            'email': email,
            'password': password,
            'balance': 10000.0,        # demo money
            'holdings': {}             # symbol -> quantity
        })
        flash("Account created successfully. Please log in.")
        return redirect(url_for('login'))

    return render_template('signup.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully!', 'info')
    return redirect(url_for('login'))


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/profile')
def profile():
    if 'user' not in session:
        return redirect(url_for('login'))

    username = session['user']['username']
    # get fresh user object
    user_db = users.find_one({'username': username})
    user_activities = list(activity_log.find({'username': username}))
    return render_template('profile.html', user=user_db, activities=user_activities)


if __name__ == '__main__':
    app.run(debug=True,use_reloader=False)
