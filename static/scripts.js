// fetch and show account info (balance) if logged in
async function loadAccount() {
    try {
        const res = await fetch('/account');
        if (!res.ok) return;
        const data = await res.json();
        const el = document.getElementById('account-balance');
        if (el && data.balance !== undefined) {
            el.innerText = `$${parseFloat(data.balance).toFixed(2)}`;
        }
    } catch (e) {
        console.error('Account load error', e);
    }
}

// call on page load
document.addEventListener('DOMContentLoaded', function() {
    loadAccount();
});

function predictPrice() {
    const day = document.getElementById("day").value.trim();
    const symbol = document.getElementById("symbol").value;
    if (!day || day <= 0) {
        Swal.fire({
            icon: "error",
            title: "Invalid Input",
            text: "Please enter a valid day number!",
        });
        return;
    }

    // Check login
    fetch("/check_login")
        .then(res => res.json())
        .then(loginData => {
            if (!loginData.logged_in) {
                // alert("⚠️ Please log in to make a prediction!");
                        Swal.fire({
                        icon: "warning",
                        title: "Login Required",
                        text: "Please log in to make a prediction!",
                        confirmButtonColor: "#3085d6",
                        });

                return;
            }

            fetch("/predict", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ day: day, symbol: symbol })
            })
            .then(async (response) => {
                if (!response.ok) {
                    const err = await response.json();
                    alert(err.error || "Something went wrong!");
                    return;
                }
                return response.json();
            })
            .then(data => {
                if (!data) return;
                document.getElementById("result").innerText =
                    `Predicted price for ${data.symbol} on day ${data.day} is $${parseFloat(data.prediction).toFixed(2)}`;

                // Load chart and show trade buttons when done
                loadChart(symbol, () => {
                    const tradeBtns = document.getElementById("trade-buttons");
                    if (tradeBtns) {
                        tradeBtns.style.display = "flex";
                        tradeBtns.style.justifyContent = "center";
                        tradeBtns.style.marginTop = "20px";
                    }
                });
            })
            .catch(err => {
                console.error(err);
                alert("Something went wrong while predicting!");
            });
        });
}

function loadChart(symbol, callback) {
    const tvSymbol = `BINANCE:${symbol}`;
    const chartContainer = document.getElementById("tv_chart_container");
    chartContainer.innerHTML = "";

    new TradingView.widget({
        "width": "95%",
        "height": 500,
        "symbol": tvSymbol,
        "interval": "30",
        "timezone": "Etc/UTC",
        "theme": "dark",
        "style": "1",
        "locale": "en",
        "toolbar_bg": "#f1f3f6",
        "enable_publishing": false,
        "hide_top_toolbar": false,
        "save_image": false,
        "container_id": "tv_chart_container"
    });

    // small delay to let widget initialize before showing buttons
    setTimeout(() => { if (callback) callback(); }, 1500);
}

function placeOrder(type) {
    // ask user for quantity
    let qty = prompt(`Enter quantity to ${type} (numeric):`, "1");
    if (qty === null) return; // user cancelled
    qty = parseFloat(qty);
    if (isNaN(qty) || qty <= 0) {
        alert("Enter a valid positive quantity.");
        return;
    }

    const symbol = document.getElementById("symbol").value;

    fetch('/trade', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: type, symbol: symbol, quantity: qty })
    })
    .then(async res => {
        const data = await res.json();
        if (!res.ok) {
            alert(data.error || "Trade failed");
            return;
        }
        alert(data.message);
        // refresh account balance shown in navbar
        loadAccount();
    })
    .catch(err => {
        console.error('Trade error', err);
        alert('Trade failed. See console for details.');
    });
}

// Live prices code (unchanged)...
const coins = [
    { symbol: "BTCUSDT", name: "Bitcoin", logo: "/static/btc.png" },
    { symbol: "ETHUSDT", name: "Ethereum", logo: "/static/eth.png" },
    { symbol: "BNBUSDT", name: "BNB", logo: "/static/bnb.png" },
    { symbol: "XRPUSDT", name: "XRP", logo: "/static/xrp.png" },
    { symbol: "ADAUSDT", name: "Cardano", logo: "/static/car.jpg" },
    { symbol: "DOGEUSDT", name: "Dogecoin", logo:"/static/doge.png" },
    { symbol: "SOLUSDT", name: "Solana", logo: "/static/sol.webp" },
    { symbol: "MATICUSDT", name: "Polygon", logo:"/static/mac.jpeg" },
    { symbol: "DOTUSDT", name: "Polkadot", logo: "/static/dot.png" },
    { symbol: "LTCUSDT", name: "Litecoin", logo:"/static/lite.webp" }
];

async function fetchPrices() {
    const list = document.getElementById("coin-list");
    if (!list) return;
    list.innerHTML = "";

    for (let coin of coins) {
        try {
            const res = await fetch(`https://api.binance.com/api/v3/ticker/24hr?symbol=${coin.symbol}`);
            const data = await res.json();
            const changeClass = parseFloat(data.priceChangePercent) >= 0 ? 'up' : 'down';
            list.innerHTML += `
                <div class="coin-row">
                    <div class="coin-info">
                        <img src="${coin.logo}" alt="${coin.name}" />
                        <span><strong>${coin.symbol.replace("USDT", "")}</strong> ${coin.name}</span>
                    </div>
                    <div class="coin-price">$${parseFloat(data.lastPrice).toFixed(2)}</div>
                    <div class="coin-change ${changeClass}">${parseFloat(data.priceChangePercent).toFixed(2)}%</div>
                </div>
            `;
        } catch (e) {
            console.error('Binance fetch error for', coin.symbol, e);
        }
    }
}

fetchPrices();
setInterval(fetchPrices, 15000);
