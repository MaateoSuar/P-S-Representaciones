import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, flash
import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from io import BytesIO

APP_SECRET = os.environ.get("APP_SECRET", "dev-secret-change-me")
DATA_CSV_PATH = os.environ.get("PRODUCTS_CSV", os.path.join(os.path.dirname(__file__), "data", "products.csv"))
REMOTE_CSV_URL = os.environ.get("PRODUCTS_CSV_URL")  # Optional URL (e.g., Apps Script publish URL)

app = Flask(__name__)
app.secret_key = APP_SECRET

BASE_DIR = os.path.dirname(__file__)
PDF_DIR = os.path.join(BASE_DIR, "pdfs")
ORDERS_DIR = os.path.join(BASE_DIR, "orders")
os.makedirs(PDF_DIR, exist_ok=True)
os.makedirs(ORDERS_DIR, exist_ok=True)


def load_products() -> pd.DataFrame:
    """Load products either from remote URL or local CSV. Expected columns: name, cost, vencimiento"""
    if REMOTE_CSV_URL:
        df = pd.read_csv(REMOTE_CSV_URL)
    else:
        if not os.path.exists(DATA_CSV_PATH):
            return pd.DataFrame(columns=["name", "cost", "vencimiento"]).astype({"name": str, "cost": float, "vencimiento": str})
        df = pd.read_csv(DATA_CSV_PATH)
    # Normalize columns in case of mixed names
    cols = {c.lower().strip(): c for c in df.columns}
    name_col = cols.get("name") or cols.get("producto")
    cost_col = cols.get("cost") or cols.get("precio") or cols.get("costo")
    venc_col = cols.get("vencimiento") or cols.get("fecha vencimiento") or cols.get("fecha_vencimiento")
    rename_map = {}
    if name_col and name_col != "name":
        rename_map[name_col] = "name"
    if cost_col and cost_col != "cost":
        rename_map[cost_col] = "cost"
    if venc_col and venc_col != "vencimiento":
        rename_map[venc_col] = "vencimiento"
    if rename_map:
        df = df.rename(columns=rename_map)
    # Coerce types
    if "cost" in df:
        df["cost"] = pd.to_numeric(df["cost"], errors="coerce")
    if "vencimiento" in df:
        df["vencimiento"] = df["vencimiento"].astype(str)
    df = df.dropna(subset=["name", "cost"]).reset_index(drop=True)
    df["id"] = df.index.astype(int)
    return df[["id", "name", "cost", "vencimiento"]]


def get_cart():
    return session.setdefault("cart", [])


def save_cart(cart):
    session["cart"] = cart
    session.modified = True


@app.route("/")
def dashboard():
    df = load_products()
    stats = {
        "productos": len(df),
        "clientes": 0,
        "ventas_hoy": 0,
        "margen_prom": 0,
    }
    return render_template("dashboard.html", stats=stats)


@app.route("/products")
def products():
    df = load_products()
    q = request.args.get("q", "").strip().lower()
    margin = float(request.args.get("margin", "20") or 0)
    if q:
        df = df[df["name"].str.lower().str.contains(q)]
    df = df.copy()
    df["final_price"] = (df["cost"] * (1 + margin / 100)).round(2)
    return render_template("products.html", products=df.to_dict(orient="records"), margin=margin, q=q)


@app.route("/cart")
def cart_view():
    cart = get_cart()
    total = sum(item["final_price"] * item["qty"] for item in cart)
    return render_template("cart.html", cart=cart, total=round(total, 2))


@app.route("/cart/add", methods=["POST"])
def cart_add():
    df = load_products()
    pid = int(request.form.get("id"))
    qty = max(1, int(request.form.get("qty", 1)))
    margin = float(request.form.get("margin", 20.0))
    row = df[df["id"] == pid]
    if row.empty:
        flash("Producto no encontrado", "error")
        return redirect(url_for("products"))
    r = row.iloc[0]
    final_price = round(float(r["cost"]) * (1 + margin / 100), 2)
    item = {
        "id": int(r["id"]),
        "name": str(r["name"]),
        "cost": float(r["cost"]),
        "vencimiento": str(r.get("vencimiento", "")),
        "margin": margin,
        "final_price": final_price,
        "qty": qty,
    }
    cart = get_cart()
    # Merge if same product and margin
    merged = False
    for c in cart:
        if c["id"] == item["id"] and abs(c["margin"] - item["margin"]) < 1e-6:
            c["qty"] += item["qty"]
            merged = True
            break
    if not merged:
        cart.append(item)
    save_cart(cart)
    return redirect(url_for("cart_view"))


@app.route("/cart/clear", methods=["POST"])
def cart_clear():
    save_cart([])
    return redirect(url_for("cart_view"))


@app.route("/checkout", methods=["POST"]) 
def checkout():
    cart = get_cart()
    if not cart:
        flash("El carrito está vacío", "error")
        return redirect(url_for("products"))
    client_name = request.form.get("client_name", "Cliente")
    client_email = request.form.get("client_email", "")
    now = datetime.now()
    order_id = now.strftime("%Y%m%d-%H%M%S")
    total = sum(item["final_price"] * item["qty"] for item in cart)

    # Save a simple order record
    order = {
        "order_id": order_id,
        "client_name": client_name,
        "client_email": client_email,
        "created_at": now.isoformat(),
        "items": cart,
        "total": round(total, 2),
    }
    import json
    with open(os.path.join(ORDERS_DIR, f"{order_id}.json"), "w", encoding="utf-8") as f:
        json.dump(order, f, ensure_ascii=False, indent=2)

    # Generate PDF remito
    pdf_path = os.path.join(PDF_DIR, f"remito-{order_id}.pdf")
    generate_pdf_remito(pdf_path, order)

    # Clear cart
    save_cart([])

    return redirect(url_for("download_remito", filename=os.path.basename(pdf_path)))


def generate_pdf_remito(pdf_path: str, order: dict):
    c = canvas.Canvas(pdf_path, pagesize=A4)
    width, height = A4
    margin = 15 * mm

    # Column positions (right-aligned from the right margin)
    x_cant = width - margin
    x_punit = x_cant - 50  # P.Unit
    x_pct = x_punit - 40   # %
    x_cost = x_pct - 60    # Costo
    x_venc = x_cost - 70   # Venc.
    x_prod = margin        # Producto starts at left margin

    y = height - margin
    c.setFont("Helvetica-Bold", 14)
    c.drawString(margin, y, "Remito / Presupuesto - Pablo y Sergio Representaciones")
    y -= 10 * mm

    c.setFont("Helvetica", 10)
    c.drawString(margin, y, f"Nº: {order['order_id']}")
    y -= 6 * mm
    c.drawString(margin, y, f"Fecha: {order['created_at'][:19].replace('T', ' ')}")
    y -= 6 * mm
    c.drawString(margin, y, f"Cliente: {order['client_name']}")
    y -= 10 * mm

    def draw_header(current_y: float) -> float:
        c.setFont("Helvetica-Bold", 10)
        c.drawString(x_prod, current_y, "Producto")
        c.drawRightString(x_venc, current_y, "Venc.")
        c.drawRightString(x_cost, current_y, "Costo")
        c.drawRightString(x_pct, current_y, "%")
        c.drawRightString(x_punit, current_y, "P.Unit")
        c.drawRightString(x_cant, current_y, "Cant")
        current_y -= 5 * mm
        c.line(margin, current_y, width - margin, current_y)
        current_y -= 5 * mm
        return current_y

    y = draw_header(y)

    c.setFont("Helvetica", 9)
    for item in order["items"]:
        if y < 30 * mm:
            c.showPage()
            y = height - margin
            y = draw_header(y)
            c.setFont("Helvetica", 9)

        # Ensure product name fits before Venc.
        available_w = x_venc - x_prod - 6  # small padding
        name = str(item["name"]) if item.get("name") else ""
        # Truncate with ellipsis if too wide
        max_w = available_w
        if stringWidth(name, "Helvetica", 9) > max_w:
            ell = "…"
            while name and stringWidth(name + ell, "Helvetica", 9) > max_w:
                name = name[:-1]
            name = name + ell

        c.drawString(x_prod, y, name)
        c.drawRightString(x_venc, y, str(item.get("vencimiento", "")))
        c.drawRightString(x_cost, y, f"{item['cost']:.2f}")
        c.drawRightString(x_pct, y, f"{item['margin']:.1f}")
        c.drawRightString(x_punit, y, f"{item['final_price']:.2f}")
        c.drawRightString(x_cant, y, str(item['qty']))
        y -= 7 * mm  # slightly taller rows to avoid visual overlap

    y -= 6 * mm
    c.line(margin, y, width - margin, y)
    y -= 8 * mm

    c.setFont("Helvetica-Bold", 12)
    total = order["total"]
    c.drawRightString(width - margin, y, f"TOTAL: ${total:.2f}")

    c.showPage()
    c.save()


@app.route("/remitos/<path:filename>")
def download_remito(filename):
    return send_from_directory(PDF_DIR, filename, as_attachment=True)


@app.route("/history")
def history():
    """List saved orders for demo purposes."""
    import json
    orders = []
    if os.path.isdir(ORDERS_DIR):
        for fname in os.listdir(ORDERS_DIR):
            if not fname.endswith(".json"):
                continue
            fpath = os.path.join(ORDERS_DIR, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                order_id = data.get("order_id", os.path.splitext(fname)[0])
                created_at = data.get("created_at", "")
                client_name = data.get("client_name", "")
                total = data.get("total", 0)
                pdf_name = f"remito-{order_id}.pdf"
                pdf_exists = os.path.exists(os.path.join(PDF_DIR, pdf_name))
                orders.append({
                    "order_id": order_id,
                    "created_at": created_at,
                    "client_name": client_name,
                    "total": total,
                    "pdf_name": pdf_name if pdf_exists else None,
                })
            except Exception:
                continue
    # Sort by created_at/order_id desc
    orders.sort(key=lambda x: (x.get("created_at", ""), x.get("order_id", "")), reverse=True)
    return render_template("history.html", orders=orders)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
