import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path

import streamlit as st

APP_DIR = Path(__file__).parent
DB_PATH = APP_DIR / "sareesaathi.db"

st.set_page_config(page_title="SareeSaathi AI", page_icon="🪷", layout="centered")

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
        if conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
            conn.executemany("""
                INSERT INTO products (name, category, color, price, stock, description)
                VALUES (?, ?, ?, ?, ?, ?)
            """, [
                ("Kanchipuram Silk Saree", "Silk", "Maroon", 6499, 5, "Traditional zari border; festive and wedding wear."),
                ("Soft Cotton Saree", "Cotton", "Mustard", 1299, 12, "Lightweight everyday wear with a woven border."),
                ("Banarasi Style Saree", "Festive", "Royal Blue", 3899, 4, "Rich brocade-inspired design for celebrations."),
                ("Printed Daily Wear Saree", "Printed", "Teal", 899, 15, "Comfortable printed saree for everyday use."),
                ("Organza Party Wear Saree", "Party Wear", "Lavender", 2799, 6, "Lightweight party wear with decorative detailing."),
            ])

def products_all():
    with db() as conn:
        return conn.execute("SELECT * FROM products ORDER BY id").fetchall()

def orders_all(limit=50):
    with db() as conn:
        return conn.execute("SELECT * FROM orders ORDER BY id DESC LIMIT ?", (limit,)).fetchall()

def get_product(product_id):
    with db() as conn:
        return conn.execute("SELECT * FROM products WHERE id=?", (int(product_id),)).fetchone()

def save_order(product, qty, name, phone, address):
    with db() as conn:
        current = conn.execute("SELECT * FROM products WHERE id=?", (int(product["id"]),)).fetchone()
        if not current:
            return False, "I couldn't find that product anymore."
        if int(qty) < 1 or int(current["stock"]) < int(qty):
            return False, f"Sorry, only {current['stock']} item(s) are in stock right now."
        cur = conn.execute("""
            INSERT INTO orders
            (product_id, product_name, quantity, unit_price, customer_name, phone, address, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (current["id"], current["name"], int(qty), current["price"], name, phone, address,
              "Demo order - payment not processed", datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        order_id = cur.lastrowid
        conn.execute("UPDATE products SET stock=stock-? WHERE id=?", (int(qty), current["id"]))
    return True, f"Your demo order #{order_id} is booked for **{current['name']}**. Total: ₹{current['price'] * int(qty):,.0f}. No payment was taken."

def norm(s):
    s = (s or "").lower().strip()
    replacements = {
        "sarees": "saree", "saris": "saree", "irukka": " available ",
        "irukku": " available ", "irukkா": " available ", "stock la": " stock ",
        "enna enna": " which ", "kaamikka": " show ", "kaatu": " show ",
        "vilai": " price ", "evlo": " price ", "venum": " want ",
        "vaanguren": " buy ", "order pannunga": " order ",
    }
    for a, b in replacements.items():
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s)

def detect_role(text):
    t = norm(text)
    if any(x in t for x in ["i am vendor", "i'm vendor", "vendor", "shop owner", "seller", "my shop", "naan vendor", "kadaikaar"]):
        return "Vendor"
    if any(x in t for x in ["customer", "buyer", "shopping", "i want to buy", "i am customer", "naan customer"]):
        return "Customer"
    return None

def money(n):
    return f"₹{float(n):,.0f}"

def find_products(text):
    t = norm(text)
    ps = list(products_all())
    color_map = {
        "blue": ["blue"], "maroon": ["maroon"], "mustard": ["mustard", "yellow"],
        "teal": ["teal", "green"], "lavender": ["lavender", "purple"],
        "red": ["red", "maroon"], "pink": ["pink"],
    }
    colors = [c for c, terms in color_map.items() if any(x in t for x in terms)]
    category_map = {
        "silk": ["silk", "kanchipuram"], "cotton": ["cotton"],
        "festive": ["festive", "banarasi"], "printed": ["printed", "print"],
        "party": ["party", "organza"],
    }
    cats = [c for c, terms in category_map.items() if any(x in t for x in terms)]
    budget = None
    m = re.search(r"(?:under|below|less than|within|budget(?: of)?)\s*₹?\s*([0-9,]+)", t)
    if not m:
        m = re.search(r"(?:₹|rs\.?\s*)([0-9,]+)", t)
        if m and any(w in t for w in ["under", "below", "budget", "less than", "within"]):
            pass
        else:
            m = None
    if m:
        try:
            budget = float(m.group(1).replace(",", ""))
        except ValueError:
            pass
    if colors:
        ps = [p for p in ps if any(c in p["color"].lower() for c in colors)]
    if cats:
        ps = [p for p in ps if any(c in p["category"].lower() or c in p["name"].lower() for c in cats)]
    if budget is not None:
        ps = [p for p in ps if float(p["price"]) <= budget]
    return ps

def product_lines(ps):
    if not ps:
        return "I couldn't find a matching saree in our current sample catalog. You can ask for blue, maroon, silk, cotton, or a budget like 'under ₹3000'."
    lines = ["Here are the matching options:"]
    for i, p in enumerate(ps[:8], 1):
        stock = f"{p['stock']} in stock" if p["stock"] > 0 else "currently out of stock"
        lines.append(f"{i}. **{p['name']}** — {money(p['price'])} · {p['color']} · {stock}")
    lines.append("If you'd like one, just say **“I want the blue one”** or **“Order the Banarasi saree”**. I'll guide you here in the chat.")
    return "\n\n".join(lines)

def openai_assist(user_text, role):
    # Optional conversational explanation. Database actions are handled separately and validated in Python.
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        try:
            key = str(st.secrets.get("OPENAI_API_KEY", "")).strip()
        except Exception:
            key = ""
    if not key:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=key)
        catalog = [{"name": p["name"], "color": p["color"], "price": p["price"], "stock": p["stock"], "category": p["category"]} for p in products_all()]
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": (
                    "You are SareeSaathi, a warm, concise conversational sales assistant for local saree vendors. "
                    f"The current role is {role}. Reply in the user's language style when possible, including Tamil-English transliteration. "
                    "This prototype has sample products and demo orders only. Do not claim to have performed a database action, booked an order, taken payment, or sent WhatsApp messages. "
                    "Never request OTPs, UPI PINs, card numbers, or passwords. If an action is needed, guide them naturally in this same chat. "
                    f"Current sample catalog: {catalog}"
                )},
                {"role": "user", "content": user_text[:1500]}
            ],
            temperature=0.4,
            max_tokens=220,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return None

def handle_message(raw):
    text = norm(raw)
    role = st.session_state.role
    state = st.session_state.flow

    # Role selection through conversation, not a separate screen.
    if role is None:
        detected = detect_role(raw)
        if detected:
            st.session_state.role = detected
            return f"Great, I'll help you as a **{detected.lower()}**. You can tell me what you need in your own words."
        return "Vanakkam! I'm SareeSaathi. Are you here as a **customer** looking for sarees, or a **vendor** managing your shop? Just reply naturally — for example, “I'm a customer” or “I manage the shop.”"

    # Continue an order conversation.
    if state and state.get("kind") == "order":
        step = state.get("step")
        if any(x in text for x in ["cancel", "stop order", "never mind"]):
            st.session_state.flow = None
            return "No problem — I've cancelled this demo order flow. What else can I help with?"
        if step == "confirm_product":
            candidates = state.get("candidates", [])
            chosen = None
            if text.isdigit():
                idx = int(text) - 1
                if 0 <= idx < len(candidates):
                    chosen = get_product(candidates[idx])
            else:
                for pid in candidates:
                    p = get_product(pid)
                    if p and (p["name"].lower() in text or any(word in text for word in p["name"].lower().split() if len(word) > 4)):
                        chosen = p
                        break
                if not chosen and len(candidates) == 1:
                    chosen = get_product(candidates[0])
            if not chosen:
                return "Which one would you like? Reply with the product name or its number from the list. You can also say 'cancel'."
            if chosen["stock"] <= 0:
                st.session_state.flow = None
                return f"Sorry, **{chosen['name']}** is currently out of stock. Would you like me to find a similar option?"
            state["product_id"] = chosen["id"]
            state["step"] = "quantity"
            st.session_state.flow = state
            return f"Great choice — **{chosen['name']}** is {money(chosen['price'])}. How many would you like?"
        if step == "quantity":
            m = re.search(r"\d+", text)
            if not m:
                return "How many would you like? Please tell me a quantity, such as 1 or 2."
            qty = int(m.group())
            p = get_product(state["product_id"])
            if not p or qty < 1 or qty > int(p["stock"]):
                return f"That quantity isn't available. Current stock is {p['stock'] if p else 0}. How many would you like?"
            state["quantity"] = qty
            state["step"] = "name"
            st.session_state.flow = state
            return "Sure. What name should I put on the demo order?"
        if step == "name":
            if len(raw.strip()) < 2:
                return "Could you tell me the name for the order?"
            state["customer_name"] = raw.strip()[:100]
            state["step"] = "phone"
            st.session_state.flow = state
            return "Thanks. What's a contact number for this demo order? Please use fictional details while testing."
        if step == "phone":
            digits = re.sub(r"\D", "", raw)
            if len(digits) < 6:
                return "That number seems too short. Please enter a test contact number with at least 6 digits."
            state["phone"] = raw.strip()[:40]
            state["step"] = "address"
            st.session_state.flow = state
            return "What's the delivery address for this demo order? Use a fictional address for testing."
        if step == "address":
            if len(raw.strip()) < 5:
                return "Please provide a little more detail for the delivery address."
            state["address"] = raw.strip()[:400]
            state["step"] = "confirm"
            st.session_state.flow = state
            p = get_product(state["product_id"])
            total = float(p["price"]) * int(state["quantity"])
            return (
                f"Please confirm your demo order:\\n\\n**{p['name']}** × {state['quantity']}\\n\\n"
                f"Total: **{money(total)}**\\n\\nDelivery to: {state['address']}\\n\\n"
                "Reply **confirm** to book this test order, or **cancel** to stop. **No payment will be taken.**"
            )
        if step == "confirm":
            if any(x in text for x in ["confirm", "yes", "ok", "okay", "book it", "proceed"]):
                p = get_product(state["product_id"])
                ok, result = save_order(p, state["quantity"], state["customer_name"], state["phone"], state["address"])
                st.session_state.flow = None
                return result if ok else result
            return "I haven't booked it yet. Reply **confirm** to create the demo order, or **cancel** to stop."

    # Vendor commands: only explicit, validated edits mutate the database.
    if role == "Vendor":
        stock_match = re.search(r"(?:add|increase|update|set|change)\s+(\d+)\s+.*?(?:stock|to stock)\s+(?:of\s+)?(.+)", text)
        if not stock_match:
            stock_match = re.search(r"(?:set|change|update)\s+stock\s+(?:of\s+)?(.+?)\s+(?:to|as)\s+(\d+)", text)
            if stock_match:
                product_phrase, amount = stock_match.group(1), int(stock_match.group(2))
            else:
                product_phrase, amount = None, None
        else:
            amount, product_phrase = int(stock_match.group(1)), stock_match.group(2)
        if product_phrase:
            ps = list(products_all())
            matches = [p for p in ps if product_phrase.strip() in p["name"].lower() or product_phrase.strip() in p["color"].lower()]
            if len(matches) == 1:
                p = matches[0]
                with db() as conn:
                    conn.execute("UPDATE products SET stock=? WHERE id=?", (max(0, amount), p["id"]))
                return f"Done — I've set **{p['name']}** stock to **{max(0, amount)}** in the demo database."
            if len(matches) > 1:
                return "I found more than one match: " + ", ".join(p["name"] for p in matches) + ". Which product do you mean?"
        price_match = re.search(r"(?:change|set|update)\s+(?:the\s+)?price\s+(?:of\s+)?(.+?)\s+(?:to|at)\s*₹?\s*([0-9,]+)", text)
        if price_match:
            phrase, amount = price_match.group(1).strip(), float(price_match.group(2).replace(",", ""))
            matches = [p for p in products_all() if phrase in p["name"].lower() or phrase in p["color"].lower()]
            if len(matches) == 1:
                p = matches[0]
                with db() as conn:
                    conn.execute("UPDATE products SET price=? WHERE id=?", (amount, p["id"]))
                return f"Done — **{p['name']}** is now listed at **{money(amount)}** in the demo database."
            if len(matches) > 1:
                return "I found multiple products matching that. Please include more of the product name."
        if any(x in text for x in ["orders", "sales", "customer", "order list", "how many order"]):
            os_ = list(orders_all())
            if not os_:
                return "There are no demo orders yet. Once a customer completes an order in this chat, I'll be able to show it here."
            lines = [f"I found **{len(os_)} recent demo order(s)**:"]
            for o in os_[:8]:
                lines.append(f"- Order #{o['id']}: {o['product_name']} × {o['quantity']} — {o['customer_name']} — {o['status']}")
            return "\n".join(lines)
        if any(x in text for x in ["stock", "inventory", "available", "saree", "catalog", "product"]):
            return product_lines(list(products_all()))
        if any(x in text for x in ["customer", "vendor", "help", "what can you do"]):
            return "You can ask me to check stock, change a product price, update stock, or review demo orders. For example: “Set stock of blue saree to 10” or “Change price of Banarasi saree to ₹3499.”"

    # Customer product discovery.
    if any(x in text for x in ["saree", "show", "blue", "maroon", "silk", "cotton", "price", "available", "stock", "under", "budget", "organza", "banarasi", "printed", "purple", "lavender", "green", "red"]):
        ps = find_products(raw)
        st.session_state.last_product_ids = [p["id"] for p in ps]
        if any(x in text for x in ["buy", "order", "want", "book", "purchase"]):
            if not ps:
                return product_lines(ps)
            if len(ps) == 1:
                p = ps[0]
                if p["stock"] <= 0:
                    return f"Sorry, **{p['name']}** is out of stock. Would you like another option?"
                st.session_state.flow = {"kind": "order", "step": "quantity", "product_id": p["id"]}
                return f"Of course! **{p['name']}** costs {money(p['price'])} and has {p['stock']} in stock. How many would you like?"
            st.session_state.flow = {"kind": "order", "step": "confirm_product", "candidates": [p["id"] for p in ps[:8]]}
            return product_lines(ps) + "\n\nTell me the product name or number to start your order."
        return product_lines(ps)

    if any(x in text for x in ["buy", "order", "purchase", "i want one"]):
        last_ids = st.session_state.get("last_product_ids", [])
        available = [get_product(pid) for pid in last_ids]
        available = [p for p in available if p]
        if len(available) == 1:
            p = available[0]
            st.session_state.flow = {"kind": "order", "step": "quantity", "product_id": p["id"]}
            return f"Let's order **{p['name']}** at {money(p['price'])}. How many would you like?"
        return "Of course. Which saree would you like to order? Tell me its color or name, and I'll guide you through the order here."

    ai = openai_assist(raw, role)
    if ai:
        return ai
    return (
        "I can help with that. Tell me a little more in your own words. "
        "For example, a customer can ask for a color, style, or budget; a vendor can ask about stock, prices, or orders. "
        "This demo uses sample data and doesn't process real payments or send WhatsApp messages."
    )

init_db()

# ---------- Chat-only interface ----------
st.markdown("""
<style>
.block-container {max-width: 900px; padding-top: 1.4rem; padding-bottom: 2rem;}
.hero {padding: 1.35rem 1.5rem; border-radius: 18px; background: linear-gradient(120deg,#fff1f2,#fff7ed); border: 1px solid #f0d3d7; margin-bottom: 1rem;}
.hero h1 {color:#6d2138 !important; margin:0; font-size:2rem;}
.hero p {color:#55333c !important; margin-top:.45rem;}
div[data-testid="stChatMessage"] {border-radius: 14px;}
div[data-testid="stChatInput"] textarea {font-size: 1rem;}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero">
  <h1>🪷 SareeSaathi AI</h1>
  <p>Your conversational sales assistant for local saree businesses.</p>
  <p><b>Just tell me what you need.</b> No menus, special commands, or separate dashboards.</p>
</div>
""", unsafe_allow_html=True)

if "role" not in st.session_state:
    st.session_state.role = None
if "flow" not in st.session_state:
    st.session_state.flow = None
if "last_product_ids" not in st.session_state:
    st.session_state.last_product_ids = []
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [{
        "role": "assistant",
        "content": "Vanakkam! I'm SareeSaathi. Are you here as a **customer** looking for sarees, or a **vendor** managing your shop? Just tell me naturally."
    }]

if st.session_state.role:
    st.caption(f"Current conversation: {st.session_state.role} · You can say “switch to customer” or “switch to vendor” at any time.")
    # Allow conversational role switching.
    if st.session_state.chat_history:
        last_user = next((m["content"] for m in reversed(st.session_state.chat_history) if m["role"] == "user"), "")
        switch = detect_role(last_user)
        if switch and any(x in norm(last_user) for x in ["switch", "change role", "i am", "i'm", "now as"]):
            if switch != st.session_state.role:
                st.session_state.role = switch
                st.session_state.flow = None

for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"], avatar="🪷" if msg["role"] == "assistant" else "🙂"):
        st.markdown(msg["content"])

prompt = st.chat_input("Say what you need in your own words…")
if prompt:
    st.session_state.chat_history.append({"role": "user", "content": prompt})
    detected = detect_role(prompt)
    if st.session_state.role is None and detected:
        st.session_state.role = detected
        answer = f"Great, I'll help you as a **{detected.lower()}**. Tell me what you'd like to do, in your own words."
    elif st.session_state.role and detected and detected != st.session_state.role and any(x in norm(prompt) for x in ["switch", "change role", "i am", "i'm", "now as"]):
        st.session_state.role = detected
        st.session_state.flow = None
        answer = f"Done — we're now in **{detected.lower()}** mode. What would you like me to help with?"
    else:
        answer = handle_message(prompt)
    st.session_state.chat_history.append({"role": "assistant", "content": answer})
    st.rerun()

with st.expander("About this prototype"):
    st.write("This is an early-stage demo with sample sarees and demo orders. Payment processing and WhatsApp messaging are not connected. Use fictional customer details.")
