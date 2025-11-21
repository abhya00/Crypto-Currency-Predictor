import numpy as np
import requests
from tensorflow.keras.models import Sequential, load_model
from tensorflow.keras.layers import LSTM, Dense
from sklearn.preprocessing import MinMaxScaler
import os

scaler = MinMaxScaler(feature_range=(0, 1))

def get_binance_data(symbol="BTCUSDT", interval="1d", limit=100):
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    data = requests.get(url, params=params).json()
    closes = [float(entry[4]) for entry in data]
    return np.array(closes).reshape(-1, 1)

def train_model(symbol="BTCUSDT"):
    prices = get_binance_data(symbol)
    scaled = scaler.fit_transform(prices)

    X, y = [], []
    window = 30
    for i in range(window, len(scaled)):
        X.append(scaled[i-window:i])
        y.append(scaled[i])

    X, y = np.array(X), np.array(y)

    model = Sequential()
    model.add(LSTM(50, return_sequences=True, input_shape=(X.shape[1], 1)))
    model.add(LSTM(50))
    model.add(Dense(1))
    model.compile(optimizer="adam", loss="mse")
    model.fit(X, y, epochs=8, batch_size=16, verbose=1)

    os.makedirs("models", exist_ok=True)
    model.save(f"models/{symbol}.h5")
    print(f"✅ Model saved for {symbol}")

def predict_future_price(symbol="BTCUSDT", days=1):
    model_path = f"models/{symbol}.h5"
    if not os.path.exists(model_path):
        train_model(symbol)

    model = load_model(model_path)
    prices = get_binance_data(symbol)
    scaled = scaler.fit_transform(prices)

    last_window = scaled[-30:]
    for _ in range(days):
        prediction = model.predict(last_window.reshape(1, 30, 1))[0][0]
        last_window = np.append(last_window[1:], prediction)
    predicted_price = scaler.inverse_transform([[prediction]])[0][0]
    return float(predicted_price)
