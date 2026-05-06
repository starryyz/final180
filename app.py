# app.py
from flask import Flask, render_template, redirect, url_for, request, session, flash
import pymysql
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config
from flask import request, jsonify
import random
import datetime

app = Flask(__name__)
app.config.from_object(Config)

# db helpers

def get_db_connection():
    return pymysql.connect(
        host=Config.MYSQL_HOST,
        user=Config.MYSQL_USER,
        password=Config.MYSQL_PASSWORD,
        database=Config.MYSQL_DB,
        port=Config.MYSQL_PORT,
        cursorclass=pymysql.cursors.DictCursor
    )

def get_db_cursor(dictionary=False):
    conn = get_db_connection()

    if dictionary:
        return conn.cursor(pymysql.cursors.DictCursor)

    return conn.cursor()

def get_db_connection_for_commit():
    conn = get_db_connection()
    return conn

def current_user():
    if "user_id" not in session:
        return None

    cur = get_db_cursor(dictionary=True)
    cur.execute(
        "SELECT id, first_name, last_name, email, is_admin FROM users WHERE id = %s",
        (session["user_id"],)
    )
    user = cur.fetchone()
    cur.close()
    return user

def is_admin():
    user = current_user()
    return user and user["is_admin"] == 1


# login/sign up routes

@app.route("/")
def home():
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        cur = get_db_cursor()
        cur.execute("SELECT id, first_name, password_hash, is_admin FROM users WHERE email = %s", (email,))
        user = cur.fetchone()
        cur.close()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]  # revised
            session["user_name"] = user["first_name"]  # revised
            session["is_admin"] = user["is_admin"]  # revised

            if user["is_admin"] == 1:  # revised
                return redirect(url_for("admin_dashboard"))

            return redirect(url_for("dashboard"))
        else:
            flash("Invalid credentials", "danger")

    return render_template("login.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]          # NEW
        first_name = request.form["first_name"]
        last_name = request.form["last_name"]
        email = request.form["email"]
        phone = request.form["phone"]
        address = request.form["address"]
        password = request.form["password"]

        password_hash = generate_password_hash(password)

        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO users (username, first_name, last_name, email, phone, address, password_hash)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (username, first_name, last_name, email, phone, address, password_hash))  # UPDATED
            conn.commit()
            flash("Account created! Please log in.", "success")
            return redirect(url_for("login"))
        except Exception as e:
            conn.rollback()
            flash("Error creating account. Maybe username or email already exists.", "danger")
        finally:
            cur.close()
            conn.close()

    return render_template("signup.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# user optionns/categories routes
CATEGORIES = [
    "seeds",
    "succulents",
    "pre-potted plants",
    "soil",
    "gardening tools",
    "pots",
    "watering cans"
]

@app.route("/dashboard")
def dashboard():
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    return render_template("dashboard.html", user=user, categories=CATEGORIES)


@app.route("/category/<category_name>")
def category_page(category_name):
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    if category_name not in CATEGORIES:
        return redirect(url_for("dashboard"))

    cur = get_db_cursor()
    cur.execute("""
        SELECT id, name, description, price, stock, image_url 
        FROM products 
        WHERE category = %s
    """, (category_name,))
    products = cur.fetchall()
    cur.close()

    return render_template(
        "category.html",
        user=user,
        category_name=category_name,
        categories=CATEGORIES,
        products=products
    )

# cart and checkout routes

@app.route("/add_to_cart/<int:product_id>", methods=["POST"])
def add_to_cart(product_id):
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    quantity = int(request.form.get("quantity", 1))

    if "cart" not in session:
        session["cart"] = {}

    cart = session["cart"]
    cart[str(product_id)] = cart.get(str(product_id), 0) + quantity
    session["cart"] = cart

    flash("Item added to cart!", "success")
    return redirect(request.referrer or url_for("dashboard"))

@app.route("/cart")
def cart():
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    cart = session.get("cart", {})
    items = []
    total = 0

    if cart:
        cur = get_db_cursor()
        for pid, qty in cart.items():
            cur.execute("SELECT id, name, price FROM products WHERE id = %s", (pid,))
            product = cur.fetchone()
            if product:
                subtotal = product["price"] * qty  # revised
                items.append({
                    "id": product["id"],  # revised
                    "name": product["name"],  # revised
                    "price": product["price"],  # revised
                    "quantity": qty,
                    "subtotal": subtotal
                })
        cur.close()

    return render_template("cart.html", user=user, items=items, total=total)

@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    cart = session.get("cart", {})

    # Allow checkout page to load even if cart is empty
    if request.method == "GET":
        if not cart:
            flash("Your cart is empty.", "warning")
        return render_template("checkout.html", user=user)

    # POST — placing the order
    pickup_option = request.form.get("pickup_option", "delivery")

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    try:
        # Calculate total price
        total_price = 0
        for pid, qty in cart.items():
            cur.execute("SELECT price FROM products WHERE id = %s", (pid,))
            product = cur.fetchone()
            if product:
                total_price += product["price"] * qty

        # Insert order
        cur.execute("""
            INSERT INTO orders (user_id, status, pickup_option, total)
            VALUES (%s, 'pending', %s, %s)
        """, (user["id"], pickup_option, total_price))
        order_id = cur.lastrowid

        # Insert order items
        for pid, qty in cart.items():
            cur.execute("SELECT price FROM products WHERE id = %s", (pid,))
            price = cur.fetchone()["price"]

            cur.execute("""
                INSERT INTO order_items (order_id, product_id, quantity, price_each)
                VALUES (%s, %s, %s, %s)
            """, (order_id, pid, qty, price))

            # Reduce stock
            cur.execute("""
                UPDATE products
                SET stock = stock - %s
                WHERE id = %s
            """, (qty, pid))

        conn.commit()

        # Clear cart
        session["cart"] = {}

        flash("Order placed! You'll be notified when it's approved or shipped.", "success")
        return redirect(url_for("dashboard"))

    except Exception as e:
        conn.rollback()
        flash("Error placing order.", "danger")

    finally:
        cur.close()
        conn.close()

    return render_template("checkout.html", user=user)


# my orders page
@app.route("/my_orders")
def my_orders():
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    cur = get_db_cursor(dictionary=True)
    cur.execute("""
        SELECT 
            id,
            status,
            total,
            pickup_option,
            created_at
        FROM orders
        WHERE user_id = %s
        ORDER BY created_at DESC
    """, (user["id"],))
    orders = cur.fetchall()
    cur.close()

    return render_template("my_orders.html", user=user, orders=orders)


# update order status 
@app.route("/admin/update_order_status", methods=["POST"])
def update_order_status():
    order_id = request.form['order_id']
    new_status = request.form['status']

    cursor = db.cursor()
    cursor.execute("""
        UPDATE orders
        SET status = %s
        WHERE id = %s
    """, (new_status, order_id))
    db.commit()

    return redirect(url_for("admin_orders"))

# admin routes

@app.route("/admin")
def admin_dashboard():
    if not is_admin():
        return redirect(url_for("login"))

    cur = get_db_cursor(dictionary=True)

    # Fetch users
    cur.execute("SELECT id, first_name, last_name, email FROM users")
    users = cur.fetchall()

    # Fetch products
    cur.execute("SELECT id, name, category, price, stock FROM products")
    products = cur.fetchall()

    cur.close()
    return render_template("admin_dashboard.html", users=users, products=products)


@app.route("/admin/orders")
def admin_orders():
    if not is_admin():
        return redirect(url_for("login"))

    cur = get_db_cursor(dictionary=True)

    # Fetch orders with user info + item count
    cur.execute("""
        SELECT 
            o.id,
            o.status,
            o.pickup_option,
            o.total,
            o.created_at,
            u.first_name,
            u.last_name,
            (SELECT COUNT(*) FROM order_items WHERE order_id = o.id) AS item_count
        FROM orders o
        JOIN users u ON o.user_id = u.id
        ORDER BY o.created_at DESC
    """)
    orders = cur.fetchall()

    cur.close()
    return render_template("admin_orders.html", orders=orders)


@app.route("/admin/order/<int:order_id>/status", methods=["POST"])
def admin_update_order_status(order_id):
    if not is_admin():
        return redirect(url_for("login"))

    new_status = request.form["status"]

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            UPDATE orders
            SET status = %s
            WHERE id = %s
        """, (new_status, order_id))

        conn.commit()
        flash(f"Order {order_id} updated to {new_status}.", "success")

    except Exception as e:
        conn.rollback()
        flash("Error updating order.", "danger")

    finally:
        cur.close()
        conn.close()

    return redirect(url_for("admin_orders"))


# bloomy bot

@app.route("/bloomybot")
def bloomybot():
    user = current_user()
    return render_template("bloomybot.html", user=user)

@app.route("/chatbot_api", methods=["POST"])
def chatbot_api():
    data = request.get_json()
    user_message = data.get("message", "").strip()

    if not user_message:
        return jsonify({"response": "I didn’t catch that. Could you repeat it?"})

    # 🌱 Simple placeholder logic (we will upgrade this)
    if "refund" in user_message.lower():
        bot_reply = "I can help with refunds! Please provide your order number."
    else:
        bot_reply = "I'm BloomyBot! I’ll soon be able to process refunds and notify admins."

    return jsonify({"response": bot_reply})


# ⭐⭐⭐ CUSTOMER SERVICE PAGE ⭐⭐⭐
@app.route("/customer_service")
def customer_service():
    user = current_user()
    return render_template("customer_service.html", user=user)


# user profile

import os
from werkzeug.utils import secure_filename

PROFILE_FOLDER = "static/profile_pics"
os.makedirs(PROFILE_FOLDER, exist_ok=True)

@app.route("/profile", methods=["GET", "POST"])
def profile():
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    if request.method == "POST":
        first_name = request.form.get("first_name")
        last_name = request.form.get("last_name")
        phone = request.form.get("phone")
        address = request.form.get("address")

        # update info
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE users
            SET first_name=%s, last_name=%s, phone=%s, address=%s
            WHERE id=%s
        """, (first_name, last_name, phone, address, user["id"]))  # revised
        conn.commit()
        cur.close()
        conn.close()
        

        # session update
        session["user_name"] = first_name

        # pfp upload
        if "profile_pic" in request.files:
            file = request.files["profile_pic"]
            if file and file.filename != "":
                filename = secure_filename(f"user_{user['id']}.png")  # revised
                filepath = os.path.join(PROFILE_FOLDER, filename)
                file.save(filepath)

                conn = get_db_connection()
                cur = conn.cursor()
                cur.execute("UPDATE users SET profile_pic=%s WHERE id=%s", (filename, user["id"]))  # revised
                conn.commit()
                cur.close()
                conn.close()

                session["profile_pic"] = url_for("static", filename=f"profile_pics/{filename}")

        flash("Profile updated successfully!", "success")

        # updated info
        cur = get_db_cursor()
        cur.execute("SELECT id, first_name, last_name, email, phone, address, profile_pic FROM users WHERE id=%s", (user["id"],))  # revised
        updated_user = cur.fetchone()
        cur.close()

        return render_template("profile.html", user=updated_user)

    # loading pfp
    cur = get_db_cursor()
    cur.execute("SELECT profile_pic FROM users WHERE id=%s", (user["id"],))  # revised
    pic = cur.fetchone()["profile_pic"]
    cur.close()

    if pic:
        session["profile_pic"] = url_for("static", filename=f"profile_pics/{pic}")
    else:
        session["profile_pic"] = url_for("static", filename="images/default-profile.png")

    return render_template("profile.html", user=user)


# admin revision-- dont touch
# @app.route("/create_admin")
# def create_admin():
#     from werkzeug.security import generate_password_hash
#
#     password_hash = generate_password_hash("admin123")
#
#     conn = get_db_connection()
#     cur = conn.cursor()
#     cur.execute("""
#         INSERT INTO users (username, first_name, last_name, email, phone, address, password_hash, is_admin)
#         VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
#     """, (
#         "admin",
#         "Admin",
#         "User",
#         "admin@example.com",
#         "000-000-0000",
#         "123 Admin Street",
#         password_hash,
#         True
#     ))
#     conn.commit()
#     cur.close()
#     conn.close()
#
#     return "Admin user created. You can now log in."



print("hello world")

if __name__ == "__main__":
    app.run(debug=True, port=5001)
