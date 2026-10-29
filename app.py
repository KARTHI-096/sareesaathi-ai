import os
import json
import sqlite3
from datetime import datetime
from pathlib import Path

import streamlit as st

APP_DIR = Path(__file__).parent
DB_PATH = APP_DIR / "sareesaathi.db"
CURRENCY = "₹"

st.set_page_config(page_title="SareeSaathi AI", page_icon="🪷", layout="wide")

# ---------- Database ----------
def db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                color TEXT NOT NULL,
                price REAL NOT NULL,
                stock INTEGER NOT NULL DEFAULT 0,
                description TEXT DEFAULT ''
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                product_name TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                unit_price REAL NOT NULL,
                customer_name TEXT NOT NULL,
                phone TEXT NOT NULL,
                address TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Demo order - payment not processed',
                created_at TEXT NOT NULL
            )
        """)
        count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        if count == 0:
            conn.executemany("""
                INSERT INTO products (name, category, color, price, stock, description)
                VALUES (?, ?, ?, ?, ?, ?)
            """, [
                ("Kanchipuram Silk Saree", "Silk", "Maroon", 6499, 5, "Traditional zari border; festive and wedding wear."),
                ("Soft Cotton Saree", "Cotton", "Mustard", 1299, 12, "Lightweight everyday wear with a simple woven border."),
                ("Banarasi Style Saree", "Festive", "Royal Blue", 3899, 4, "Rich brocade-inspired design for celebrations."),
                ("Printed Daily Wear Saree", "Printed", "Teal", 899, 15, "Comfortable printed saree for everyday use."),
                ("Organza Party Wear Saree", "Party Wear", "Lavender", 2799, 6, "Lightweight sheer-look fabric with decorative detailing."),
            ])

def get_products():
    with db() as conn:
        return conn.execute("SELECT * FROM products ORDER BY id DESC").fetchall()

def get_orders():
    with db() as conn:
        return conn.execute("SELECT * FROM orders ORDER BY id DESC").fetchall()

def create_order(product, quantity, customer_name, phone, address):
    with db() as conn:
        row = conn.execute("SELECT * FROM products WHERE id = ?", (int(product["id"]),)).fetchone()
        if not row:
            return False, "That product could not be found."
        if int(quantity) < 1:
            return False, "Quantity must be at least 1."
        if row["stock"] < int(quantity):
            return False, f"Only {row['stock']} item(s) are currently in demo stock."
        conn.execute("""
            INSERT INTO orders
            (product_id, product_name, quantity, unit_price, customer_name, phone, address, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            row["id"], row["name"], int(quantity), row["price"], customer_name.strip(),
            phone.strip(), address.strip(), "Demo order - payment not processed",
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
        conn.execute("UPDATE products SET stock = stock - ? WHERE id = ?", (int(quantity), row["id"]))
    return True, "Demo order created. No payment was taken."

init_db()

# ---------- AI intent helper ----------
def configured_api_key():
    # Streamlit Cloud secrets are supported; environment variables work locally.
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if key:
        return key
    try:
        return str(st.secrets.get("OPENAI_API_KEY", "")).strip()
    except Exception:
        return ""

def ai_reply(user_text, role, products, orders):
    api_key = configured_api_key()
    try:
        if not api_key:
            return demo_reply(user_text, role, products, orders), "Demo mode"
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        product_data = [
            {"id": p["id"], "name": p["name"], "category": p["category"],
             "color": p["color"], "price": p["price"], "stock": p["stock"],
             "description": p["description"]} for p in products
        ]
        order_data = [
            {"id": o["id"], "product": o["product_name"], "quantity": o["quantity"],
             "customer": o["customer_name"], "status": o["status"], "created_at": o["created_at"]}
            for o in orders[:20]
        ]
        system = f"""
You are SareeSaathi, a helpful conversational assistant for a small saree business.
Current role: {role}.
Users can speak naturally; do not demand special commands.
Explain products and help the user decide what to do. Be concise and friendly.
This prototype can show products, create demo orders through the UI, and let vendors manage stock through the UI.
Never claim you changed stock, created an order, charged money, or sent a WhatsApp message unless the UI actually did it.
Payments are NOT integrated. Do not request card details, UPI PINs, passwords, or OTPs.
Only use this product data and order summary; do not invent stock, prices, or order records.
Product data: {json.dumps(product_data, ensure_ascii=False)}
Recent orders: {json.dumps(order_data, ensure_ascii=False)}
"""
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_text[:2000]},
            ],
            temperature=0.4,
            max_tokens=350,
        )
        return response.choices[0].message.content.strip(), "OpenAI mode"
    except Exception as exc:
        # Keep the app usable if API key/config is wrong; avoid exposing internals.
        return demo_reply(user_text, role, products, orders) + "\n\n(Using demo fallback because AI service is unavailable.)", "Demo fallback"


def demo_reply(user_text, role, products, orders):
    # Lightweight multilingual/transliterated keyword matching for safe demo mode.
    text = user_text.lower().strip()
    normalized = (
        text.replace("sarees", "saree")
            .replace("saris", "saree")
            .replace("irukka", " available ")
            .replace("irukku", " available ")
            .replace("irukkா", " available ")
            .replace("stock la", " stock ")
            .replace("enna enna", " which ")
            .replace("evlo", " price ")
            .replace("vilai", " price ")
            .replace("kaamikka", " show ")
            .replace("kaatu", " show ")
    )

    # Stock/inventory requests should summarize the current catalog.
    stock_intent = any(w in normalized for w in [
        "stock", "inventory", "available", "what do we have", "which saree", "all saree"
    ])
    if role == "Vendor" and any(w in normalized for w in ["order", "sales", "customer"]):
        return (
            f"You have **{len(orders)} demo order(s)** recorded.\n\n"
            "Open the Vendor dashboard to review orders and update inventory. "
            "In demo mode, I won't modify records based only on chat."
        )

    # Detect an explicit color/product/category request.
    color_terms = {
        "blue": ["blue"],
        "maroon": ["maroon"],
        "mustard": ["mustard", "yellow"],
        "teal": ["teal", "green"],
        "lavender": ["lavender", "purple"],
    }
    requested_colors = [color for color, terms in color_terms.items()
                        if any(term in normalized for term in terms)]
    category_terms = {
        "silk": ["silk", "kanchipuram"],
        "cotton": ["cotton"],
        "festive": ["festive", "banarasi"],
        "printed": ["printed", "print"],
        "party wear": ["party wear", "organza"],
    }
    requested_categories = [cat for cat, terms in category_terms.items()
                            if any(term in normalized for term in terms)]

    # Recognize simple budget phrasing, including "under 5000" / "below 2000".
    import re
    budget = None
    match = re.search(r"(?:under|below|less than|within|budget(?: of)?|under rs\.?|under ₹)\s*₹?\s*([0-9,]+)", normalized)
    if match:
        try:
            budget = float(match.group(1).replace(",", ""))
        except ValueError:
            budget = None
    if budget is None:
        match = re.search(r"(?:₹|rs\.?\s*)([0-9,]+)", normalized)
        if match and any(w in normalized for w in ["under", "below", "budget", "less than", "within"]):
            try:
                budget = float(match.group(1).replace(",", ""))
            except ValueError:
                pass

    matches = list(products)
    if requested_colors:
        matches = [p for p in matches if any(c in p["color"].lower() for c in requested_colors)]
    if requested_categories:
        matches = [p for p in matches if any(c in p["category"].lower() or c in p["name"].lower()
                                               for c in requested_categories)]
    if budget is not None:
        matches = [p for p in matches if float(p["price"]) <= budget]

    product_intent = any(w in normalized for w in [
        "saree", "product", "show", "catalog", "price", "silk", "cotton",
        "blue", "maroon", "mustard", "teal", "lavender", "available", "stock",
        "under", "budget", "organza", "banarasi", "printed"
    ])

    if product_intent or stock_intent:
        if not matches:
            return "I couldn't find a matching saree in the current demo catalog. Try asking for blue, maroon, silk, cotton, or a budget such as 'under ₹3000'."
        if not stock_intent and not requested_colors and not requested_categories and budget is None:
            matches = matches[:5]
        lines = ["Here are the matching sarees in the current demo catalog:"]
        for p in matches[:10]:
            stock_label = "In stock" if int(p["stock"]) > 0 else "Out of stock"
            lines.append(
                f"- **{p['name']}** — ₹{p['price']:,.0f} | Color: {p['color']} | "
                f"Stock: {p['stock']} ({stock_label})"
            )
        lines.append("\nTo book one, open **Place demo order** and select the product. No payment is processed.")
        return "\n\n".join(lines)

    if any(w in normalized for w in ["buy", "order", "purchase", "delivery", "address"]):
        return "I can help you choose a saree. Open **Product catalog**, then **Place demo order** to enter delivery details and create a demo order. Payment is not enabled."
    return (
        "Vanakkam! I'm SareeSaathi, your demo sales assistant. You can ask in simple English or Tamil-English, "
        "for example:\n\n"
        "- Which sarees are in stock?\n"
        "- Blue saree irukka?\n"
        "- Show silk sarees under ₹5000\n\n"
        "This is rule-based demo mode; add an OpenAI API key to enable AI-powered intent understanding."
    )

# ---------- UI ----------
st.markdown("""
<style>
.block-container {padding-top: 1.8rem; max-width: 1200px;}
.hero {padding: 1.4rem 1.6rem; border-radius: 18px; background: linear-gradient(120deg, #fff1f2, #fff7ed); border: 1px solid #f3d7d9;}
.small-muted {color: #6b7280; font-size: 0.92rem;}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="hero"><h1>🪷 SareeSaathi AI</h1><p>Natural conversations for local saree businesses — from product discovery to demo order booking.</p><p class="small-muted">MVP prototype • Sample catalog • No real payments or WhatsApp messages</p></div>', unsafe_allow_html=True)
st.write("")

products = get_products()
orders = get_orders()

col1, col2 = st.columns([1, 2])
with col1:
    role = st.radio("Who are you today?", ["Customer", "Vendor"], horizontal=True)
with col2:
    st.info("Talk naturally. For example: “Show me silk sarees under ₹5,000” or “How many orders have we received?”")

tabs = st.tabs(["💬 Assistant chat", "🛍️ Product catalog", "📦 Place demo order", "🧵 Vendor dashboard"])

with tabs[0]:
    st.subheader("Chat with SareeSaathi")
    mode = "OpenAI API" if configured_api_key() else "Safe demo mode"
    st.caption(f"Current mode: {mode}. Chat does not execute transactions; use the controls in the other tabs.")
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = [
            {"role": "assistant", "content": "Vanakkam! I can help you explore sarees or manage a shop. Try asking naturally — no special commands needed."}
        ]
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
    prompt = st.chat_input("Type a message in your own words…")
    if prompt:
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        # Refresh latest state before answering
        products_now = get_products()
        orders_now = get_orders()
        answer, source = ai_reply(prompt, role, products_now, orders_now)
        st.session_state.chat_history.append({"role": "assistant", "content": answer})
        with st.chat_message("assistant"):
            st.markdown(answer)
            st.caption(source)

with tabs[1]:
    st.subheader("Available sarees")
    cols = st.columns(3)
    for idx, p in enumerate(products):
        with cols[idx % 3]:
            st.markdown(f"### {p['name']}")
            st.markdown(f"**{CURRENCY}{p['price']:,.0f}**")
            st.write(f"Color: {p['color']}  ")
            st.write(f"Category: {p['category']}")
            st.write(f"Available: {p['stock']}")
            st.caption(p["description"])
            st.divider()

with tabs[2]:
    st.subheader("Book a demo order")
    st.warning("Demo only: this records an order and reduces sample stock. It does not process payment, dispatch products, or send WhatsApp messages.")
    if not products:
        st.info("No products available.")
    else:
        product_options = {f"{p['name']} — {CURRENCY}{p['price']:,.0f} (stock: {p['stock']})": p for p in products}
        selected_label = st.selectbox("Choose a saree", list(product_options.keys()))
        selected_product = product_options[selected_label]
        qty = st.number_input("Quantity", min_value=1, max_value=max(1, int(selected_product["stock"]) or 1), value=1, step=1)
        with st.form("order_form"):
            customer_name = st.text_input("Customer name")
            phone = st.text_input("Contact number", help="Use a demo number for testing.")
            address = st.text_area("Delivery address")
            consent = st.checkbox("I confirm this is a test order using sample data.")
            submitted = st.form_submit_button("Create demo order", type="primary")
        if submitted:
            if not customer_name.strip() or not phone.strip() or not address.strip():
                st.error("Please fill in the name, contact number, and delivery address.")
            elif not consent:
                st.error("Please confirm this is a test order.")
            else:
                ok, message = create_order(selected_product, qty, customer_name, phone, address)
                if ok:
                    st.success(message)
                    st.info("Payment status: Not processed. Do not send real payment details.")
                    st.rerun()
                else:
                    st.error(message)

with tabs[3]:
    st.subheader("Vendor dashboard")
    if role != "Vendor":
        st.info("Switch the role selector at the top to Vendor to use this dashboard.")
    else:
        st.markdown("#### Inventory")
        inv = get_products()
        for p in inv:
            with st.expander(f"{p['name']} · {p['stock']} in stock"):
                with st.form(f"stock_{p['id']}"):
                    new_price = st.number_input("Price (₹)", min_value=0.0, value=float(p["price"]), step=50.0, key=f"price_{p['id']}")
                    new_stock = st.number_input("Stock quantity", min_value=0, value=int(p["stock"]), step=1, key=f"stockqty_{p['id']}")
                    new_description = st.text_input("Description", value=p["description"], key=f"desc_{p['id']}")
                    save = st.form_submit_button("Save product")
                if save:
                    with db() as conn:
                        conn.execute("UPDATE products SET price=?, stock=?, description=? WHERE id=?",
                                     (float(new_price), int(new_stock), new_description.strip(), int(p["id"])))
                    st.success("Product updated in the demo database.")
                    st.rerun()
        st.markdown("#### Recent orders")
        current_orders = get_orders()
        if not current_orders:
            st.write("No demo orders yet.")
        else:
            st.dataframe([{
                "Order ID": o["id"], "Product": o["product_name"], "Qty": o["quantity"],
                "Customer": o["customer_name"], "Phone": o["phone"], "Address": o["address"],
                "Status": o["status"], "Created": o["created_at"]
            } for o in current_orders], use_container_width=True, hide_index=True)

st.divider()
st.caption("SareeSaathi AI is an early-stage demonstration. Use fictional customer details. It is not connected to WhatsApp Business, a payment gateway, or a shipping provider.")
