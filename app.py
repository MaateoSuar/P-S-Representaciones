import os
from datetime import datetime, date
from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, flash, jsonify, send_file
import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from io import BytesIO
import json
import smtplib
from email.message import EmailMessage

APP_SECRET = os.environ.get("APP_SECRET", "dev-secret-change-me")
DATA_CSV_PATH = os.environ.get("PRODUCTS_CSV", os.path.join(os.path.dirname(__file__), "data", "products.csv"))
REMOTE_CSV_URL = None
GOOGLE_SHEETS_URL = "https://docs.google.com/spreadsheets/d/1qhlOeGUZioluGrGX8WoOnN2PxklVQJ-aU6_9DFMI-hs/edit?gid=1541872518#gid=1541872518"

app = Flask(__name__)
app.secret_key = APP_SECRET

BASE_DIR = os.path.dirname(__file__)
PDF_DIR = os.path.join(BASE_DIR, "pdfs")
ORDERS_DIR = os.path.join(BASE_DIR, "orders")
os.makedirs(PDF_DIR, exist_ok=True)
os.makedirs(ORDERS_DIR, exist_ok=True)

# Simple JSON persistence for clients
CLIENTS_PATH = os.path.join(BASE_DIR, "data", "clients.json")
os.makedirs(os.path.join(BASE_DIR, "data"), exist_ok=True)

def load_clients():
    if not os.path.exists(CLIENTS_PATH):
        return []
    try:
        with open(CLIENTS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_clients(clients):
    with open(CLIENTS_PATH, "w", encoding="utf-8") as f:
        json.dump(clients, f, ensure_ascii=False, indent=2)


def _safe_filename(text: str) -> str:
    allowed = "-_. ()abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return "".join(ch if ch in allowed else "_" for ch in text).strip()

# Single-user login credentials (can be overridden via environment variables)
LOGIN_USER = os.environ.get("APP_LOGIN_USER", "representaciones@gmail.com")
LOGIN_PASS = os.environ.get("APP_LOGIN_PASS", "representaciones")


@app.before_request
def require_login():
    # Allow access to login page and static files without authentication
    if request.endpoint in ("login", "static"):
        return
    if not session.get("logged_in"):
        return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if username == LOGIN_USER and password == LOGIN_PASS:
            session.clear()
            session["logged_in"] = True
            session["user"] = username
            return redirect(url_for("dashboard"))
        else:
            flash("Usuario o contraseña incorrectos", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


def load_products() -> pd.DataFrame:
    """Load products either from remote URL or local CSV. Expected columns: name, cost, vencimiento"""
    if REMOTE_CSV_URL:
        df = pd.read_csv(REMOTE_CSV_URL)
    elif GOOGLE_SHEETS_URL:
        # Convert a Google Sheets edit URL to a CSV export URL preserving gid
        try:
            url = GOOGLE_SHEETS_URL
            # Extract doc id between /d/ and next '/'
            doc_id = None
            if "/d/" in url:
                part = url.split("/d/", 1)[1]
                doc_id = part.split("/", 1)[0]
            # Extract gid
            import urllib.parse as _up
            parsed = _up.urlparse(url)
            qs = _up.parse_qs(parsed.query)
            gid = (qs.get("gid", ["0"]) or ["0"])[0]
            if doc_id:
                export_url = f"https://docs.google.com/spreadsheets/d/{doc_id}/export?format=csv&gid={gid}"
                df = pd.read_csv(export_url)
            else:
                # Fallback: try direct
                df = pd.read_csv(url)
        except Exception:
            # Fallback to local if conversion fails
            if not os.path.exists(DATA_CSV_PATH):
                return pd.DataFrame(columns=["name", "cost", "vencimiento"]).astype({"name": str, "cost": float, "vencimiento": str})
            df = pd.read_csv(DATA_CSV_PATH)
    else:
        if not os.path.exists(DATA_CSV_PATH):
            return pd.DataFrame(columns=["name", "cost", "vencimiento"]).astype({"name": str, "cost": float, "vencimiento": str})
        df = pd.read_csv(DATA_CSV_PATH)
    # Normalize columns in case of mixed names
    cols = {c.lower().strip(): c for c in df.columns}
    name_col = cols.get("name") or cols.get("producto")
    # Accept custom cost header '-3%'
    cost_col = cols.get("cost") or cols.get("precio") or cols.get("costo") or cols.get("-3%") or cols.get("- 3%")
    # Accept typo 'fecha vencimeinto' and broader variants
    venc_col = (
        cols.get("vencimiento")
        or cols.get("fecha vencimiento")
        or cols.get("fecha_vencimiento")
        or cols.get("fecha vencimeinto")
        or cols.get("vto")
        or cols.get("fecha vto")
    )
    if not venc_col:
        # Fallback: pick first column whose lowercase contains 'venc' or 'vto'
        for c in df.columns:
            lc = str(c).strip().lower()
            if ("venc" in lc) or ("vto" in lc) or ("venci" in lc):
                venc_col = c
                break
    rename_map = {}
    if name_col and name_col != "name":
        rename_map[name_col] = "name"
    if cost_col and cost_col != "cost":
        rename_map[cost_col] = "cost"
    if venc_col and venc_col != "vencimiento":
        rename_map[venc_col] = "vencimiento"
    if rename_map:
        df = df.rename(columns=rename_map)
    # Coerce types and normalize values
    if "name" in df:
        df["name"] = df["name"].astype(str).str.strip()
    if "cost" in df:
        # Normalize common LATAM formats: "$ 1.234,56" -> "1234.56"
        cost_s = df["cost"].astype(str).str.strip()
        # Keep only digits, separators and sign
        cost_s = cost_s.str.replace(r"[^0-9,.-]", "", regex=True)
        # If there is a comma, treat '.' as thousands separator and remove it
        has_comma = cost_s.str.contains(",")
        cost_s = cost_s.where(~has_comma, cost_s.str.replace(r"\.(?=\d{3}(\D|$))", "", regex=True))
        # Replace comma decimal with dot
        cost_s = cost_s.str.replace(",", ".", regex=False)
        df["cost"] = pd.to_numeric(cost_s, errors="coerce")
    if "vencimiento" in df:
        # Normalize NaN to empty and keep as string
        df["vencimiento"] = df["vencimiento"].fillna("").astype(str)
    else:
        # Ensure column exists for downstream consumers
        df["vencimiento"] = ""
    # Drop rows without name or cost not parsed
    df = df.dropna(subset=["name", "cost"]).reset_index(drop=True)
    df["id"] = df.index.astype(int)
    return df[["id", "name", "cost", "vencimiento"]]


def get_cart():
    return session.setdefault("cart", [])


def save_cart(cart):
    session["cart"] = cart
    session.modified = True


@app.context_processor
def inject_globals():
    cart = session.get("cart", [])
    return {
        "cart_count": sum(int(i.get("qty", 0)) for i in cart),
        "current_client_name": session.get("current_client_name"),
        "current_client_email": session.get("current_client_email"),
        "sales_responsible": session.get("sales_responsible"),
        "editing_order_id": session.get("edit_order_id"),
    }


@app.route("/")
def dashboard():
    df = load_products()
    clients = load_clients()
    # Compute stats and time series from orders directory
    from collections import defaultdict
    today_str = date.today().isoformat()
    ventas_hoy = 0.0
    clientes_hoy_set = set()
    # Per-day aggregations
    sales_by_day = defaultdict(float)
    clients_by_day = defaultdict(set)  # sets of client names per day
    margin_val_by_day = defaultdict(float)  # absolute margin value per day
    sales_val_by_day = defaultdict(float)   # absolute sales value per day
    if os.path.isdir(ORDERS_DIR):
        for fname in os.listdir(ORDERS_DIR):
            if not fname.endswith(".json"):
                continue
            try:
                with open(os.path.join(ORDERS_DIR, fname), "r", encoding="utf-8") as f:
                    order = json.load(f)
                created = order.get("created_at", "")
                client_name = (order.get("client_name") or "").strip()
                if len(created) >= 10:
                    day = created[:10]
                    total = float(order.get("total", 0.0))
                    sales_by_day[day] += total
                    if client_name:
                        clients_by_day[day].add(client_name)
                if created.startswith(today_str):
                    ventas_hoy += float(order.get("total", 0.0))
                    if client_name:
                        clientes_hoy_set.add(client_name)
                # Margin computation per item by day
                for it in order.get("items", []):
                    qty = float(it.get("qty", 0))
                    price = float(it.get("final_price", 0))
                    cost = float(it.get("cost", 0))
                    margin_val = max(price - cost, 0) * qty
                    created_day = created[:10] if len(created) >= 10 else None
                    if created_day:
                        margin_val_by_day[created_day] += margin_val
                        sales_val_by_day[created_day] += price * qty
            except Exception:
                continue
    # Today's KPI values
    clientes_hoy = len(clientes_hoy_set)
    sales_today_val = ventas_hoy
    sales_today_base = sales_val_by_day.get(today_str, 0.0)
    margin_today_val = margin_val_by_day.get(today_str, 0.0)
    margen_prom_hoy = (margin_today_val / sales_today_base * 100) if sales_today_base > 0 else 0.0
    stats = {
        "productos": len(df),  # productos en stock
        "clientes_dia": clientes_hoy,
        "ventas_hoy": round(sales_today_val, 2),
        "margen_prom_hoy": round(margen_prom_hoy, 1),
    }
    # Compose chronological labels and values for last 30 days
    last_30 = [date.fromordinal(date.today().toordinal() - i) for i in range(29, -1, -1)]
    sales_labels = [f"{d.day}/{d.month}" for d in last_30]
    iso_labels = [d.isoformat() for d in last_30]
    sales_values = [round(sales_by_day.get(k, 0.0), 2) for k in iso_labels]
    clients_values = [len(clients_by_day.get(k, set())) for k in iso_labels]
    margin_values = []
    for k in iso_labels:
        base = sales_val_by_day.get(k, 0.0)
        mv = margin_val_by_day.get(k, 0.0)
        margin_values.append(round((mv / base * 100) if base > 0 else 0.0, 1))
    return render_template("dashboard.html", stats=stats, sales_labels=sales_labels, sales_values=sales_values, clients_values=clients_values, margin_values=margin_values)


 


@app.route("/api/products")
def api_products():
    df = load_products()
    q = request.args.get("q", "").strip().lower()
    # If a client name is provided, set it as active in session (name/email/margin)
    client_name_param = request.args.get("client", "").strip()
    if client_name_param:
        try:
            clients = load_clients()
            # case-insensitive match by name
            target = next((c for c in clients if c.get("name", "").strip().lower() == client_name_param.lower()), None)
            if target:
                # If client changed, clear cart
                prev_id = session.get("current_client_id")
                prev_name = session.get("current_client_name")
                new_id = target.get("id")
                new_name = target.get("name")
                if prev_id != new_id or (prev_id is None and prev_name and prev_name != new_name):
                    session["cart"] = []
                session["current_client_id"] = new_id
                session["current_client_name"] = new_name
                session["current_client_email"] = target.get("email", "")
                # update default margin from client if present
                if target.get("default_margin") is not None:
                    session["current_client_margin"] = float(target.get("default_margin", 20.0))
                session.modified = True
        except Exception:
            pass
    margin = request.args.get("margin")
    if margin is None:
        margin = session.get("current_client_margin", 20.0)
    margin = float(margin or 0)
    if q:
        df = df[df["name"].str.lower().str.contains(q)]
    df = df.copy()
    df["final_price"] = (df["cost"] * (1 + margin / 100)).round(2)
    return jsonify({
        "products": df.to_dict(orient="records"),
        "margin": margin,
        "current_client_name": session.get("current_client_name"),
        "current_client_email": session.get("current_client_email"),
        "cart_count": sum(int(i.get("qty", 0)) for i in session.get("cart", [])),
    })


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
    # AJAX support: if client expects JSON, return cart status
    wants_json = (
        "application/json" in (request.headers.get("Accept", ""))
        or request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or request.form.get("ajax") == "1"
        or (request.headers.get("Referer") and "/products" in request.headers.get("Referer"))
    )
    if wants_json:
        count = sum(int(i.get("qty", 0)) for i in cart)
        return jsonify({"ok": True, "cart_count": count})
    return redirect(url_for("cart_view"))


@app.route("/cart/update", methods=["POST"])
def cart_update():
    try:
        idx = int(request.form.get("index", "-1"))
        qty = int(request.form.get("qty", "0"))
    except ValueError:
        flash("Datos inválidos", "error")
        return redirect(url_for("cart_view"))
    cart = get_cart()
    if 0 <= idx < len(cart):
        if qty <= 0:
            cart.pop(idx)
            flash("Item eliminado", "success")
        else:
            cart[idx]["qty"] = qty
            flash("Cantidad actualizada", "success")
        save_cart(cart)
    else:
        flash("No se pudo actualizar el item", "error")
    return redirect(url_for("cart_view"))

@app.route("/cart/clear", methods=["POST"])
def cart_clear():
    save_cart([])
    return redirect(url_for("cart_view"))


@app.route("/cart/remove", methods=["POST"])
def cart_remove():
    try:
        idx = int(request.form.get("index", "-1"))
    except ValueError:
        idx = -1
    cart = get_cart()
    if 0 <= idx < len(cart):
        cart.pop(idx)
        save_cart(cart)
        flash("Item eliminado", "success")
    else:
        flash("No se pudo eliminar el item", "error")
    return redirect(url_for("cart_view"))

@app.route("/checkout", methods=["POST"]) 
def checkout():
    cart = get_cart()
    if not cart:
        flash("El carrito está vacío", "error")
        return redirect(url_for("products"))
    client_name = request.form.get("client_name", "Cliente")
    client_email = request.form.get("client_email", "")
    responsible = request.form.get("responsible", "").strip()
    if not responsible:
        flash("Debe seleccionar el responsable de la venta", "error")
        return redirect(url_for("cart_view"))
    now = datetime.now()
    total = sum(item["final_price"] * item["qty"] for item in cart)

    edit_id = session.get("edit_order_id")
    if edit_id:
        # Overwrite existing order
        fpath = os.path.join(ORDERS_DIR, f"{edit_id}.json")
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            existing = {"order_id": edit_id, "created_at": now.isoformat(), "state": "Pedido"}
        # Preserve created_at and state and pdf filename if present
        order = {
            "order_id": existing.get("order_id", edit_id),
            "client_name": client_name,
            "client_email": client_email,
            "responsible": responsible,
            "created_at": existing.get("created_at", now.isoformat()),
            "items": cart,
            "total": round(total, 2),
            "state": existing.get("state", "Pedido"),
            "pdf_filename": existing.get("pdf_filename"),
        }
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(order, f, ensure_ascii=False, indent=2)
        # Regenerate PDF using stored or new filename
        client_part = _safe_filename(client_name) or "Cliente"
        pdf_filename = order.get("pdf_filename") or f"Remito - {client_part} - {order['order_id']}.pdf"
        pdf_path = os.path.join(PDF_DIR, pdf_filename)
        generate_pdf_remito(pdf_path, order)
        # Save filename back
        order["pdf_filename"] = pdf_filename
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(order, f, ensure_ascii=False, indent=2)
        # Clear edit flag after saving
        session.pop("edit_order_id", None)
    else:
        # Create new order
        order_id = now.strftime("%Y%m%d-%H%M%S")
        order = {
            "order_id": order_id,
            "client_name": client_name,
            "client_email": client_email,
            "responsible": responsible,
            "created_at": now.isoformat(),
            "items": cart,
            "total": round(total, 2),
            "state": "Pedido",
        }
        with open(os.path.join(ORDERS_DIR, f"{order_id}.json"), "w", encoding="utf-8") as f:
            json.dump(order, f, ensure_ascii=False, indent=2)
        # Generate PDF remito
        client_part = _safe_filename(client_name) or "Cliente"
        pdf_filename = f"Remito - {client_part} - {order_id}.pdf"
        pdf_path = os.path.join(PDF_DIR, pdf_filename)
        generate_pdf_remito(pdf_path, order)
        # update order with pdf filename for later use
        try:
            ofile = os.path.join(ORDERS_DIR, f"{order_id}.json")
            with open(ofile, "r", encoding="utf-8") as f:
                saved = json.load(f)
            saved["pdf_filename"] = pdf_filename
            with open(ofile, "w", encoding="utf-8") as f:
                json.dump(saved, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # Optional email automation if SMTP configured and email provided
    if client_email and os.environ.get("SMTP_HOST"):
        try:
            send_remito_email(client_email, pdf_path, order)
            flash("Remito enviado por email", "success")
        except Exception:
            flash("No se pudo enviar el email del remito", "error")

    # Clear cart
    save_cart([])
    # Remember last chosen responsible for convenience
    if responsible:
        session["sales_responsible"] = responsible
        session.modified = True

    return redirect(url_for("history"))


@app.route("/history/<order_id>/to-cart")
def history_to_cart(order_id: str):
    fpath = os.path.join(ORDERS_DIR, f"{order_id}.json")
    if not os.path.exists(fpath):
        flash("Pedido no encontrado", "error")
        return redirect(url_for("history"))
    try:
        with open(fpath, "r", encoding="utf-8") as f:
            order = json.load(f)
        # Load items into cart
        items = order.get("items", [])
        session["cart"] = items
        # Set client context
        session["current_client_name"] = order.get("client_name", "")
        session["current_client_email"] = order.get("client_email", "")
        # Set edit flag
        session["edit_order_id"] = order.get("order_id", order_id)
        # Preselect responsible
        if order.get("responsible"):
            session["sales_responsible"] = order.get("responsible")
        session.modified = True
        flash("Pedido cargado en el carrito para edición", "success")
        return redirect(url_for("cart_view"))
    except Exception:
        flash("No se pudo cargar el pedido al carrito", "error")
        return redirect(url_for("history"))


def generate_pdf_remito(pdf_path: str, order: dict):
    c = canvas.Canvas(pdf_path, pagesize=A4)
    width, height = A4
    margin = 15 * mm

    # Column positions (right-aligned from the right margin)
    x_cant = width - margin
    x_punit = x_cant - 60  # P.Unit
    x_venc = x_punit - 80  # Venc.
    x_prod = margin        # Producto starts at left margin

    y = height - margin
    c.setFont("Helvetica-Bold", 14)
    c.drawString(margin, y, f"Remito: {order.get('client_name','')} - Nº {order['order_id']}")
    y -= 10 * mm

    c.setFont("Helvetica", 10)
    c.drawString(margin, y, "Pablo y Sergio Representaciones")
    y -= 6 * mm
    c.drawString(margin, y, f"Fecha: {order['created_at'][:19].replace('T', ' ')}")
    y -= 6 * mm
    c.drawString(margin, y, f"Cliente: {order['client_name']}")
    y -= 10 * mm

    def draw_header(current_y: float) -> float:
        c.setFont("Helvetica-Bold", 10)
        c.drawString(x_prod, current_y, "Producto")
        c.drawRightString(x_venc, current_y, "Venc.")
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
        venc = str(item.get("vencimiento", "")).strip()
        if not venc:
            venc = "-"
        c.drawRightString(x_venc, y, venc)
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


def send_remito_email(to_email: str, pdf_path: str, order: dict):
    host = os.environ.get("SMTP_HOST")
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASS")
    sender = os.environ.get("SMTP_FROM", user)
    if not (host and user and password and sender):
        raise RuntimeError("SMTP no configurado correctamente")

    msg = EmailMessage()
    msg["Subject"] = f"Remito {order['order_id']}"
    msg["From"] = sender
    msg["To"] = to_email
    body = (
        f"Hola {order.get('client_name','')},\n\n"
        f"Adjuntamos el remito {order['order_id']} por un total de ${order['total']:.2f}.\n\n"
        f"Saludos."
    )
    msg.set_content(body)
    with open(pdf_path, "rb") as f:
        data = f.read()
    msg.add_attachment(data, maintype="application", subtype="pdf", filename=os.path.basename(pdf_path))

    with smtplib.SMTP(host, port) as s:
        s.starttls()
        s.login(user, password)
        s.send_message(msg)


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
                # Build display date as DD/MM/AAAA
                created_display = ""
                try:
                    if created_at:
                        dt = datetime.fromisoformat(created_at)
                        created_display = dt.strftime("%d/%m/%Y")
                except Exception:
                    created_display = created_at[:10]
                client_name = data.get("client_name", "")
                total = data.get("total", 0)
                responsible = data.get("responsible", "")
                # Prefer stored filename, else fallback to old naming
                pdf_name = data.get("pdf_filename")
                if pdf_name:
                    pdf_exists = os.path.exists(os.path.join(PDF_DIR, pdf_name))
                else:
                    legacy = f"remito-{order_id}.pdf"
                    pdf_exists = os.path.exists(os.path.join(PDF_DIR, legacy))
                    pdf_name = legacy if pdf_exists else None
                orders.append({
                    "order_id": order_id,
                    "created_at": created_at,
                    "created_display": created_display,
                    "client_name": client_name,
                    "responsible": responsible,
                    "total": total,
                    "pdf_name": pdf_name if pdf_exists else None,
                    "filename": fname,
                })
            except Exception:
                continue
    # Optional filter by client name substring (case-insensitive)
    q = request.args.get("q", "").strip().lower()
    if q:
        orders = [o for o in orders if q in (o.get("client_name", "").lower())]
    # Sort by created_at/order_id desc
    orders.sort(key=lambda x: (x.get("created_at", ""), x.get("order_id", "")), reverse=True)
    return render_template("history.html", orders=orders, q=q)


@app.route("/history/delete", methods=["POST"])
def history_delete():
    filename = request.form.get("filename", "").strip()
    if not filename or not filename.endswith(".json"):
        flash("Archivo inválido", "error")
        return redirect(url_for("history"))
    import json as _json
    fpath = os.path.join(ORDERS_DIR, filename)
    try:
        pdf_to_remove = None
        if os.path.isfile(fpath):
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = _json.load(f)
                pdf_name = data.get("pdf_filename")
                if not pdf_name:
                    # legacy fallback
                    order_id = data.get("order_id", os.path.splitext(filename)[0])
                    legacy = f"remito-{order_id}.pdf"
                    legacy_path = os.path.join(PDF_DIR, legacy)
                    if os.path.isfile(legacy_path):
                        pdf_to_remove = legacy
                else:
                    pdf_to_remove = pdf_name
            except Exception:
                pass
            os.remove(fpath)
        if pdf_to_remove:
            pdf_path = os.path.join(PDF_DIR, pdf_to_remove)
            if os.path.isfile(pdf_path):
                try:
                    os.remove(pdf_path)
                except Exception:
                    pass
        flash("Remito eliminado", "success")
    except Exception:
        flash("No se pudo eliminar el remito", "error")
    return redirect(url_for("history"))




# Clients CRUD (simple JSON backend)
@app.route("/clients")
def clients_list():
    q = request.args.get("q", "").strip().lower()
    clients = load_clients()
    if q:
        clients = [c for c in clients if q in c.get("name", "").lower() or q in c.get("zone", "").lower()]
    return render_template("clients_list.html", clients=clients, q=q)


@app.route("/clients/new", methods=["GET", "POST"])
def clients_new():
    if request.method == "POST":
        clients = load_clients()
        new_id = (max([c.get("id", 0) for c in clients]) + 1) if clients else 1
        client = {
            "id": new_id,
            "name": request.form.get("name", "").strip(),
            "zone": request.form.get("zone", "").strip(),
            "email": request.form.get("email", "").strip(),
            "phone": request.form.get("phone", "").strip(),
            "default_margin": float(request.form.get("default_margin", "20") or 20),
            "notes": request.form.get("notes", "").strip(),
            "created_at": datetime.now().isoformat(),
        }
        clients.append(client)
        save_clients(clients)
        flash("Cliente creado", "success")
        return redirect(url_for("clients_list"))
    return render_template("clients_form.html", client=None)


@app.route("/clients/<int:cid>/edit", methods=["GET", "POST"])
def clients_edit(cid: int):
    clients = load_clients()
    client = next((c for c in clients if c.get("id") == cid), None)
    if not client:
        flash("Cliente no encontrado", "error")
        return redirect(url_for("clients_list"))
    if request.method == "POST":
        client["name"] = request.form.get("name", client["name"]).strip()
        client["zone"] = request.form.get("zone", client.get("zone", "")).strip()
        client["email"] = request.form.get("email", client.get("email", "")).strip()
        client["phone"] = request.form.get("phone", client.get("phone", "")).strip()
        client["default_margin"] = float(request.form.get("default_margin", client.get("default_margin", 20)))
        client["notes"] = request.form.get("notes", client.get("notes", "")).strip()
        save_clients(clients)
        flash("Cliente actualizado", "success")
        return redirect(url_for("clients_list"))
    return render_template("clients_form.html", client=client)


@app.route("/clients/<int:cid>/use", methods=["POST"]) 
def clients_use(cid: int):
    clients = load_clients()
    client = next((c for c in clients if c.get("id") == cid), None)
    if not client:
        flash("Cliente no encontrado", "error")
        return redirect(url_for("clients_list"))
    # If client changed, clear cart
    prev_id = session.get("current_client_id")
    if prev_id != cid:
        session["cart"] = []
    session["current_client_id"] = cid
    session["current_client_name"] = client.get("name")
    session["current_client_margin"] = client.get("default_margin", 20.0)
    session["current_client_email"] = client.get("email", "")
    session.modified = True
    flash(f"Cliente activo: {client.get('name')}", "success")
    return redirect(url_for("products"))


@app.route("/clients/<int:cid>/delete", methods=["POST"])
def clients_delete(cid: int):
    clients = load_clients()
    before = len(clients)
    clients = [c for c in clients if c.get("id") != cid]
    if len(clients) == before:
        flash("Cliente no encontrado", "error")
        return redirect(url_for("clients_list"))
    save_clients(clients)
    # If deleted client was active, clear selection and cart
    if session.get("current_client_id") == cid:
        for key in ("current_client_id", "current_client_name", "current_client_margin", "current_client_email"):
            session.pop(key, None)
        session["cart"] = []
        session.modified = True
    flash("Cliente eliminado", "success")
    return redirect(url_for("clients_list"))

# Apply client default margin on products list if available
@app.route("/products")
def products():
    df = load_products()
    q = request.args.get("q", "").strip().lower()
    client_query = request.args.get("client", "").strip()
    # Prefer margin from query, else from current client, else 20
    margin = request.args.get("margin")
    if margin is None:
        margin = session.get("current_client_margin", 20.0)
    margin = float(margin or 0)
    if q:
        df = df[df["name"].str.lower().str.contains(q)]
    df = df.copy()
    df["final_price"] = (df["cost"] * (1 + margin / 100)).round(2)
    current_client_name = session.get("current_client_name")
    return render_template(
        "products.html",
        products=df.to_dict(orient="records"),
        margin=margin,
        q=q,
        current_client_name=current_client_name,
        clients=load_clients(),
        client=client_query,
    )


@app.route("/order/new")
def order_new():
    # Clear current client context for a fresh order
    for key in ("current_client_id", "current_client_name", "current_client_margin", "current_client_email"):
        session.pop(key, None)
    session.modified = True
    return redirect(url_for("products"))


# Simple pipeline view from saved orders
@app.route("/pipeline")
def pipeline_view():
    columns = {"Pedido": [], "Enviado": [], "Entregado (A cobrar)": [], "Cobrado": []}
    # Optional filters
    month_q = request.args.get("month", "").strip()
    day_q = request.args.get("day", "").strip()
    try:
        month_sel = int(month_q) if month_q else None
    except ValueError:
        month_sel = None
    try:
        day_sel = int(day_q) if day_q else None
    except ValueError:
        day_sel = None
    if os.path.isdir(ORDERS_DIR):
        for fname in os.listdir(ORDERS_DIR):
            if not fname.endswith(".json"):
                continue
            try:
                with open(os.path.join(ORDERS_DIR, fname), "r", encoding="utf-8") as f:
                    order = json.load(f)
                state = order.get("state", "Pedido")
                # Map legacy states to current pipeline
                if state in ("Oportunidad", "Remito"):
                    state = "Pedido"
                if state not in columns:
                    state = "Pedido"
                # Apply date filters ONLY to 'Cobrado'
                if state == "Cobrado" and (month_sel or day_sel):
                    created_at = order.get("created_at", "")
                    try:
                        dt = datetime.fromisoformat(created_at)
                        if month_sel and dt.month != month_sel:
                            continue
                        if day_sel and dt.day != day_sel:
                            continue
                    except Exception:
                        # If cannot parse date and filtering requested, skip only for Cobrado
                        continue
                columns[state].append(order)
            except Exception:
                continue
    # Sort each column by created_at desc
    for k in columns:
        columns[k].sort(key=lambda o: o.get("created_at", ""), reverse=True)
    return render_template("pipeline.html", columns=columns, month_sel=month_sel, day_sel=day_sel)


@app.route("/pipeline/<order_id>/state", methods=["POST"])
def pipeline_set_state(order_id: str):
    new_state = request.form.get("state", "")
    fpath = os.path.join(ORDERS_DIR, f"{order_id}.json")
    if not os.path.exists(fpath):
        flash("Pedido no encontrado", "error")
        return redirect(url_for("pipeline_view"))
    try:
        with open(fpath, "r", encoding="utf-8") as f:
            order = json.load(f)
        order["state"] = new_state
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(order, f, ensure_ascii=False, indent=2)
        flash("Estado actualizado", "success")
    except Exception:
        flash("No se pudo actualizar el estado", "error")
    return redirect(url_for("pipeline_view"))


# Exportar listado de productos a PDF con margen elegido
@app.route("/products/export-pdf")
def products_export_pdf():
    df = load_products()
    q = request.args.get("q", "").strip().lower()
    margin = request.args.get("margin")
    if margin is None:
        margin = session.get("current_client_margin", 20.0)
    margin = float(margin or 0)
    if q:
        df = df[df["name"].str.lower().str.contains(q)]
    df = df.copy()
    df["final_price"] = (df["cost"] * (1 + margin / 100)).round(2)

    buf = _generate_pdf_product_list(df.to_dict(orient="records"), margin)
    filename = f"Catalogo - {datetime.now().strftime('%Y%m%d-%H%M')}.pdf"
    return send_file(buf, mimetype="application/pdf", as_attachment=True, download_name=filename)


def _generate_pdf_product_list(products: list, margin: float) -> BytesIO:
    cbuf = BytesIO()
    c = canvas.Canvas(cbuf, pagesize=A4)
    width, height = A4
    margin_mm = 15 * mm

    x_name = margin_mm
    x_venc = width - margin_mm - 160
    x_cost = width - margin_mm - 100
    x_price = width - margin_mm - 40

    y = height - margin_mm
    c.setFont("Helvetica-Bold", 14)
    c.drawString(margin_mm, y, f"Lista de productos (margen {margin:.1f}%)")
    y -= 10 * mm
    c.setFont("Helvetica", 10)
    c.drawString(margin_mm, y, f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    y -= 8 * mm

    def draw_header(cur_y):
        c.setFont("Helvetica-Bold", 10)
        c.drawString(x_name, cur_y, "Producto")
        c.drawRightString(x_venc, cur_y, "Venc.")
        c.drawRightString(x_cost, cur_y, "Costo")
        c.drawRightString(x_price, cur_y, "P.Final")
        cur_y -= 5 * mm
        c.line(margin_mm, cur_y, width - margin_mm, cur_y)
        return cur_y - 5 * mm

    y = draw_header(y)
    c.setFont("Helvetica", 9)
    for p in products:
        if y < 25 * mm:
            c.showPage()
            y = height - margin_mm
            y = draw_header(y)
            c.setFont("Helvetica", 9)
        name = str(p.get("name", ""))
        # truncate if needed
        avail = x_venc - x_name - 6
        if stringWidth(name, "Helvetica", 9) > avail:
            ell = "…"
            while name and stringWidth(name + ell, "Helvetica", 9) > avail:
                name = name[:-1]
            name += ell
        c.drawString(x_name, y, name)
        venc = str(p.get("vencimiento", "")).strip()
        if not venc:
            venc = "-"
        c.drawRightString(x_venc, y, venc)
        c.drawRightString(x_cost, y, f"{float(p.get('cost',0)):.2f}")
        c.drawRightString(x_price, y, f"{float(p.get('final_price',0)):.2f}")
        y -= 6 * mm

    c.showPage()
    c.save()
    cbuf.seek(0)
    return cbuf


# Editar pedidos del historial
@app.route("/history/<order_id>/edit", methods=["GET", "POST"])
def history_edit(order_id: str):
    fpath = os.path.join(ORDERS_DIR, f"{order_id}.json")
    if not os.path.exists(fpath):
        flash("Pedido no encontrado", "error")
        return redirect(url_for("history"))
    try:
        with open(fpath, "r", encoding="utf-8") as f:
            order = json.load(f)
    except Exception:
        flash("No se pudo cargar el pedido", "error")
        return redirect(url_for("history"))

    if request.method == "POST":
        try:
            # Require responsible selection similar to checkout
            resp_in = (request.form.get("responsible") or "").strip()
            if not resp_in:
                flash("Debe seleccionar el responsable de la venta", "error")
                return render_template("order_edit.html", order=order, items=order.get("items", []))
            # collect items arrays
            names = request.form.getlist("name[]")
            costs = request.form.getlist("cost[]")
            vtos = request.form.getlist("vencimiento[]")
            margins = request.form.getlist("margin[]")
            finals = request.form.getlist("final_price[]")
            qtys = request.form.getlist("qty[]")
            items = []
            for i in range(len(names)):
                try:
                    qty = int(qtys[i])
                except Exception:
                    qty = 0
                if qty <= 0:
                    continue
                try:
                    cost = float(costs[i])
                except Exception:
                    cost = 0.0
                try:
                    margin_v = float(margins[i])
                except Exception:
                    margin_v = 0.0
                # compute final price if not provided or invalid
                try:
                    fprice = float(finals[i]) if finals[i] else round(cost * (1 + margin_v/100), 2)
                except Exception:
                    fprice = round(cost * (1 + margin_v/100), 2)
                items.append({
                    "id": i,  # no reliable id; keep index
                    "name": names[i],
                    "cost": cost,
                    "vencimiento": vtos[i] if i < len(vtos) else "",
                    "margin": margin_v,
                    "final_price": float(fprice),
                    "qty": qty,
                })
            order["client_name"] = request.form.get("client_name", order.get("client_name", ""))
            order["client_email"] = request.form.get("client_email", order.get("client_email", ""))
            order["responsible"] = resp_in or order.get("responsible", "")
            order["items"] = items
            order["total"] = round(sum((it.get("final_price",0)*it.get("qty",0)) for it in items), 2)

            # overwrite PDF
            client_part = _safe_filename(order.get("client_name") or "Cliente")
            pdf_filename = order.get("pdf_filename") or f"Remito - {client_part} - {order['order_id']}.pdf"
            pdf_path = os.path.join(PDF_DIR, pdf_filename)
            generate_pdf_remito(pdf_path, order)
            order["pdf_filename"] = os.path.basename(pdf_filename)

            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(order, f, ensure_ascii=False, indent=2)
            flash("Pedido actualizado", "success")
            return redirect(url_for("history"))
        except Exception:
            flash("No se pudo actualizar el pedido", "error")
            return redirect(url_for("history"))

    return render_template("order_edit.html", order=order, items=order.get("items", []))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
