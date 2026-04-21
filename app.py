# app.py
from flask import Flask, render_template, redirect, url_for, request, session, flash
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

mysql = MySQL(app)

# ---------- Helpers ----------

def get_db_cursor():
    return mysql.connection.cursor()

def current_user():
    if "user_id" not in session:
        return None
    cur = get_db_cursor()
    cur.execute("SELECT id, first_name, last_name, email, is_admin FROM users WHERE id = %s", (session["user_id"],))
    user = cur.fetchone()
    cur.close()
    return user

def is_admin():
    user = current_user()
    return user and user[4] == 1  # is_admin

# ---------- Auth routes ----------

@app.route("/")
def home():
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        cur = get_db_cursor()
        cur.execute("SELECT id, password_hash, is_admin FROM users WHERE email = %s", (email,))
        user = cur.fetchone()
        cur.close()

        if user and check_password_hash(user[1], password):
            session["user_id"] = user[0]
            if user[2] == 1:
                return redirect(url_for("admin_dashboard"))
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid credentials", "danger")

    return render_template("login.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        first_name = request.form["first_name"]
        last_name = request.form["last_name"]
        email = request.form["email"]
        phone = request.form["phone"]
        address = request.form["address"]
        password = request.form["password"]

        password_hash = generate_password_hash(password)

        cur = get_db_cursor()
        try:
            cur.execute("""
                INSERT INTO users (first_name, last_name, email, phone, address, password_hash)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (first_name, last_name, email, phone, address, password_hash))
            mysql.connection.commit()
            flash("Account created! Please log in.", "success")
            return redirect(url_for("login"))
        except Exception as e:
            mysql.connection.rollback()
            flash("Error creating account. Maybe email already exists.", "danger")
        finally:
            cur.close()

    return render_template("signup.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ---------- User dashboard & categories ----------

CATEGORIES = [
    "seeds",
    "pots",
    "pre-potted plants",
    "succulents",
    "gardening tools",
    "soil",
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
    cur.execute("SELECT id, name, description, price, stock, image_url FROM products WHERE category = %s", (category_name,))
    products = cur.fetchall()
    cur.close()

    return render_template("category.html", user=user, category=category_name, products=products)

# ---------- Cart & checkout ----------

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
                subtotal = product[2] * qty
                total += subtotal
                items.append({
                    "id": product[0],
                    "name": product[1],
                    "price": product[2],
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
    if not cart:
        flash("Your cart is empty.", "warning")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        pickup_option = request.form.get("pickup_option", "delivery")

        cur = get_db_cursor()
        try:
            # Create order
            cur.execute("""
                INSERT INTO orders (user_id, status, pickup_option)
                VALUES (%s, 'pending', %s)
            """, (user[0], pickup_option))
            order_id = cur.lastrowid

            # Add items
            for pid, qty in cart.items():
                cur.execute("SELECT price FROM products WHERE id = %s", (pid,))
                price = cur.fetchone()[0]
                cur.execute("""
                    INSERT INTO order_items (order_id, product_id, quantity, price_each)
                    VALUES (%s, %s, %s, %s)
                """, (order_id, pid, qty, price))

                # Decrease stock
                cur.execute("UPDATE products SET stock = stock - %s WHERE id = %s", (qty, pid))

            mysql.connection.commit()
            session["cart"] = {}
            flash("Order placed! You’ll be notified when it’s approved or shipped.", "success")
            return redirect(url_for("dashboard"))
        except Exception as e:
            mysql.connection.rollback()
            flash("Error placing order.", "danger")
        finally:
            cur.close()

    return render_template("checkout.html", user=user)

# ---------- Admin routes ----------

@app.route("/admin")
def admin_dashboard():
    if not is_admin():
        return redirect(url_for("login"))

    cur = get_db_cursor()
    cur.execute("SELECT id, first_name, last_name, email FROM users")
    users = cur.fetchall()

    cur.execute("SELECT id, name, category, price, stock FROM products")
    products = cur.fetchall()

    cur.close()
    return render_template("admin_dashboard.html", users=users, products=products)

@app.route("/admin/orders")
def admin_orders():
    if not is_admin():
        return redirect(url_for("login"))

    cur = get_db_cursor()
    cur.execute("""
        SELECT o.id, u.first_name, u.last_name, o.status, o.pickup_option, o.created_at
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

    new_status = request.form["status"]  # 'approved', 'declined', 'shipped'

    cur = get_db_cursor()
    try:
        cur.execute("UPDATE orders SET status = %s WHERE id = %s", (new_status, order_id))
        mysql.connection.commit()
        flash(f"Order {order_id} updated to {new_status}.", "success")
    except:
        mysql.connection.rollback()
        flash("Error updating order.", "danger")
    finally:
        cur.close()

    return redirect(url_for("admin_orders"))

# ---------- BloomyBot ----------

@app.route("/bloomybot")
def bloomybot():
    user = current_user()
    return render_template("bloomybot.html", user=user)

if __name__ == "__main__":
    app.run(debug=True, port=5001)

