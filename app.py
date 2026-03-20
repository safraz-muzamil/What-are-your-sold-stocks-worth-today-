from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import pandas as pd
import yfinance as yf
import io, os

app = Flask(__name__)
CORS(app)

def safe_float(val):
    try: return float(val)
    except: return 0.0

def read_zerodha_excel(raw):
    try:
        df_raw = pd.read_excel(io.BytesIO(raw), engine="openpyxl", header=None)
        keywords = {"symbol","trade_type","instrument","quantity","price","isin"}
        header_row = 0
        for i, row in df_raw.iterrows():
            vals = set(str(v).strip().lower() for v in row if pd.notna(v))
            if len(keywords & vals) >= 2:
                header_row = i
                break
        df = pd.read_excel(io.BytesIO(raw), engine="openpyxl", header=header_row)
        df = df.dropna(how="all").reset_index(drop=True)
        df.columns = [str(c).strip().lower().replace(" ","_") for c in df.columns]
        return df, ""
    except Exception as e:
        return None, str(e)

def get_split_ratio(splits, since_date):
    if splits is None or splits.empty or pd.isna(since_date): return 1.0
    try:
        idx = splits.index.tz_localize(None) if splits.index.tzinfo else splits.index
        sd  = since_date.tz_localize(None)   if since_date.tzinfo   else since_date
        post = splits[idx > sd]
        return float(post.prod()) if not post.empty else 1.0
    except: return 1.0

@app.route("/")
def index():
    return send_from_directory(os.path.dirname(os.path.abspath(__file__)), "index.html")

@app.route("/analyze", methods=["POST"])
def analyze():
    files = request.files.getlist("tradebooks")
    if not files:
        return jsonify({"error": "Please upload at least one tradebook file."}), 400

    all_frames = []
    for f in files:
        raw = f.read()
        df, err = read_zerodha_excel(raw)
        if df is None:
            return jsonify({"error": f"Could not read '{f.filename}'. {err}"}), 400
        all_frames.append(df)

    trades = pd.concat(all_frames, ignore_index=True)

    required = {"symbol","trade_type","segment","quantity","price"}
    missing  = required - set(trades.columns)
    if missing:
        return jsonify({"error": f"Columns found: {list(trades.columns[:10])}. Missing: {list(missing)}"}), 400

    if "trade_id" in trades.columns:
        trades = trades.drop_duplicates(subset=["trade_id"])

    trades = trades[trades["segment"].astype(str).str.strip().str.upper() == "EQ"].copy()
    trades["symbol"]     = trades["symbol"].astype(str).str.strip().str.upper()
    trades["quantity"]   = trades["quantity"].apply(safe_float)
    trades["price"]      = trades["price"].apply(safe_float)
    trades["_value"]     = trades["quantity"] * trades["price"]
    trades["trade_type"] = trades["trade_type"].astype(str).str.strip().str.lower()
    trades["trade_date"] = pd.to_datetime(trades["trade_date"], errors="coerce")

    sells = trades[trades["trade_type"] == "sell"]
    buys  = trades[trades["trade_type"] == "buy"]

    sell_agg = (sells.groupby("symbol")
        .agg(qty_sold=("quantity","sum"), total_sell_val=("_value","sum"),
             earliest_sell=("trade_date","min"))
        .reset_index())
    sell_agg["avg_sell_price"] = sell_agg["total_sell_val"] / sell_agg["qty_sold"]

    buy_agg = (buys.groupby("symbol")
        .agg(total_buy_qty=("quantity","sum"), total_buy_val=("_value","sum"),
             earliest_buy=("trade_date","min"))
        .reset_index())
    buy_agg["avg_buy_price"] = buy_agg["total_buy_val"] / buy_agg["total_buy_qty"]

    agg = sell_agg.merge(buy_agg, on="symbol", how="left")
    if agg.empty:
        return jsonify({"error": "No equity sell trades found."}), 400

    results = []
    for _, row in agg.iterrows():
        sym  = row["symbol"]
        price = None
        sell_sr = buy_sr = 1.0

        try:
            ticker = yf.Ticker(sym + ".NS")
            hist   = ticker.history(period="2d", auto_adjust=True)
            if not hist.empty:
                price = float(hist["Close"].iloc[-1])
            sp      = ticker.splits
            sell_sr = get_split_ratio(sp, row["earliest_sell"])
            if pd.notna(row.get("earliest_buy")):
                buy_sr = get_split_ratio(sp, row["earliest_buy"])
        except: pass

        avg_sell     = float(row["avg_sell_price"])
        orig_qty     = float(row["qty_sold"])
        adj_qty      = round(orig_qty * sell_sr, 4)
        sell_value   = round(orig_qty * avg_sell, 2)

        buy_qty      = float(row["total_buy_qty"])   if pd.notna(row.get("total_buy_qty"))  else orig_qty
        buy_invested = float(row["total_buy_val"])   if pd.notna(row.get("total_buy_val"))  else sell_value
        avg_buy      = float(row["avg_buy_price"])   if pd.notna(row.get("avg_buy_price"))  else avg_sell
        adj_buy_qty  = round(buy_qty * buy_sr, 4)

        if price is not None:
            cp          = round(price, 2)
            whatif      = round(adj_qty * cp, 2)
            gl          = round(whatif - sell_value, 2)
            gl_pct      = round((gl / sell_value) * 100, 2) if sell_value else 0.0
            nt_value    = round(adj_buy_qty * cp, 2)
            nt_gain     = round(nt_value - buy_invested, 2)
            nt_gain_pct = round((nt_gain / buy_invested) * 100, 2) if buy_invested else 0.0
        else:
            cp = whatif = gl = gl_pct = None
            nt_value = nt_gain = nt_gain_pct = None

        # Dates
        buy_date_str  = row["earliest_buy"].strftime("%d %b %Y")  if pd.notna(row.get("earliest_buy"))  else "N/A"
        sell_date_str = row["earliest_sell"].strftime("%d %b %Y") if pd.notna(row["earliest_sell"])     else "N/A"
        days_held = None
        if pd.notna(row.get("earliest_buy")) and pd.notna(row["earliest_sell"]):
            diff = row["earliest_sell"] - row["earliest_buy"]
            days_held = max(int(diff.days), 0)

        results.append({
            "symbol":         sym,
            "qty_sold":       orig_qty,
            "adj_qty":        adj_qty,
            "split_ratio":    sell_sr,
            "buy_date":       buy_date_str,
            "sell_date":      sell_date_str,
            "days_held":      days_held,
            "avg_sell_price": round(avg_sell, 2),
            "avg_buy_price":  round(avg_buy, 2),
            "current_price":  cp,
            "whatif_value":   whatif,
            "sell_value":     sell_value,
            "gain_loss":      gl,
            "gain_loss_pct":  gl_pct,
            "total_buy_qty":  buy_qty,
            "adj_buy_qty":    adj_buy_qty,
            "buy_invested":   round(buy_invested, 2),
            "nt_value":       nt_value,
            "nt_gain":        nt_gain,
            "nt_gain_pct":    nt_gain_pct,
        })

    return jsonify({"data": results})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)