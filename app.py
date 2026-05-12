# app.py
from flask import Flask, render_template, redirect, url_for, request, session, flash
import pymysql
from models import db, Product
from werkzeug.utils import secure_filename
import os
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config
from flask import request, jsonify

import random
import datetime

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

with app.app_context():
    db.create_all()

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
    return get_db_connection()


@app.route("/")
def home():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("is_admin") == 1:
        return redirect(url_for("admin_dashboard"))
    elif session.get("role") == "vendor":
        return redirect(url_for("dashboard"))
    else:
        return redirect(url_for("dashboard"))


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

# login
@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        cur = get_db_cursor()

        cur.execute("""
            SELECT 
                id,
                first_name,
                password_hash,
                is_admin,
                role,
                vendor_approved
            FROM users
            WHERE email = %s
        """, (email,))

        user = cur.fetchone()

        cur.close()

        if user and check_password_hash(user["password_hash"], password):

            # Prevent unapproved vendors from logging in
            if (
                user["role"] == "vendor"
                and user["vendor_approved"] == 0
            ):

                flash(
                    "Your vendor account is pending admin approval.",
                    "warning"
                )

                return redirect(url_for("login"))

            session["user_id"] = user["id"]
            session["user_name"] = user["first_name"]
            session["is_admin"] = user["is_admin"]
            session["role"] = user["role"]

            # Admin redirect
            if user["is_admin"] == 1:
                return redirect(url_for("admin_dashboard"))

            # Vendor redirect
            if user["role"] == "vendor":
                return redirect(url_for("dashboard"))

            # Normal customer redirect
            return redirect(url_for("dashboard"))

        else:

            flash("Invalid credentials", "danger")

    return render_template("login.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]          
        first_name = request.form["first_name"]
        last_name = request.form["last_name"]
        email = request.form["email"]
        phone = request.form["phone"]
        address = request.form["address"]
        password = request.form["password"]
        role = request.form["role"]
        password_hash = generate_password_hash(password)
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO users (username, first_name, last_name, email, phone, address, password_hash, role)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (username, first_name, last_name, email, phone, address, password_hash, role))
            conn.commit()
            flash("Account created!", "success")
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
        session.clear()   # <--- FIX
        return redirect(url_for("login"))
    return render_template("dashboard.html", user=user, categories=CATEGORIES)



@app.route("/category/<category_name>")
def category_page(category_name):
    user = current_user()

    if not user:
        return redirect(url_for("login"))

    category_name = category_name.strip().lower()

    if category_name not in CATEGORIES:
        return redirect(url_for("dashboard"))

    # FIXED: dictionary=True so product.id works in HTML
    cur = get_db_cursor(dictionary=True)

    cur.execute("""
        SELECT id, name, description, price, stock, image_url, vendor_id 
        FROM products 
        WHERE category = %s
    """, (category_name,))

    products = cur.fetchall()
    cur.close()

    admin_mode = is_admin()

    category_reviews = {
        "seeds": [
            {
                'rating': 5,
                'comment': "The Tomato Seeds I purchased sprouted quickly and produced amazing fruit. Highly recommend!",
                'reviewer': 'Alice G.',
                'product': 'Tomato Seeds'
            },
            {
                'rating': 5,
                'comment': "Basil Seeds were fresh and easy to grow. My herb garden is thriving!",
                'reviewer': 'Bob H.',
                'product': 'Basil Seeds'
            },
            {
                'rating': 4,
                'comment': "Carrot Seeds took a bit longer but the yield was worth it. Good quality.",
                'reviewer': 'Charlie I.',
                'product': 'Carrot Seeds'
            },
            {
                'rating': 5,
                'comment': "Lettuce Seeds germinated perfectly. Fast shipping and great packaging.",
                'reviewer': 'Diana J.',
                'product': 'Lettuce Seeds'
            }
        ],

        "succulents": [
            {
                'rating': 5,
                'comment': "The Jade Succulent I bought is so vibrant and healthy. Love the low maintenance!",
                'reviewer': 'Frank L.',
                'product': 'Jade Succulent'
            },
            {
                'rating': 5,
                'comment': "Aloe Vera Succulent arrived in perfect condition. Great for my windowsill.",
                'reviewer': 'Grace M.',
                'product': 'Aloe Vera Succulent'
            },
            {
                'rating': 4,
                'comment': "Echeveria Succulent has beautiful colors. A bit pricey but worth it.",
                'reviewer': 'Henry N.',
                'product': 'Echeveria Succulent'
            },
            {
                'rating': 5,
                'comment': "Cactus Succulent is thriving in my home. Easy care and stunning.",
                'reviewer': 'Ivy O.',
                'product': 'Cactus Succulent'
            }
        ],

        "pre-potted plants": [
            {
                'rating': 5,
                'comment': "The Lavender Pre-Potted Plant smells amazing and is blooming beautifully.",
                'reviewer': 'Kate Q.',
                'product': 'Lavender Pre-Potted Plant'
            },
            {
                'rating': 5,
                'comment': "Rosemary Pre-Potted Plant is perfect for cooking. Healthy and strong.",
                'reviewer': 'Liam R.',
                'product': 'Rosemary Pre-Potted Plant'
            },
            {
                'rating': 4,
                'comment': "Mint Pre-Potted Plant grew quickly. Great addition to my garden.",
                'reviewer': 'Mia S.',
                'product': 'Mint Pre-Potted Plant'
            },
            {
                'rating': 5,
                'comment': "Thyme Pre-Potted Plant is thriving. Excellent quality soil.",
                'reviewer': 'Noah T.',
                'product': 'Thyme Pre-Potted Plant'
            }
        ],

        "soil": [
            {
                'rating': 5,
                'comment': "Organic Potting Soil is nutrient-rich. My plants love it!",
                'reviewer': 'Paul V.',
                'product': 'Organic Potting Soil'
            },
            {
                'rating': 5,
                'comment': "Garden Soil Blend improved my vegetable patch immensely.",
                'reviewer': 'Quinn W.',
                'product': 'Garden Soil Blend'
            },
            {
                'rating': 4,
                'comment': "Seed Starting Soil worked wonders for germination.",
                'reviewer': 'Riley X.',
                'product': 'Seed Starting Soil'
            },
            {
                'rating': 5,
                'comment': "Compost-Enriched Soil boosted my plant growth.",
                'reviewer': 'Sophia Y.',
                'product': 'Compost-Enriched Soil'
            }
        ],

        "gardening tools": [
            {
                'rating': 5,
                'comment': "The Pruning Shears are sharp and durable. Essential for my garden.",
                'reviewer': 'Uma A.',
                'product': 'Pruning Shears'
            },
            {
                'rating': 5,
                'comment': "Garden Trowel is ergonomic and comfortable to use.",
                'reviewer': 'Victor B.',
                'product': 'Garden Trowel'
            },
            {
                'rating': 4,
                'comment': "Watering Can has a great spout. Easy to control flow.",
                'reviewer': 'Wendy C.',
                'product': 'Watering Can'
            },
            {
                'rating': 5,
                'comment': "Garden Gloves are tough and protect my hands well.",
                'reviewer': 'Xander D.',
                'product': 'Garden Gloves'
            }
        ],

        "pots": [
            {
                'rating': 5,
                'comment': "Ceramic Plant Pot is beautiful and sturdy. Perfect for indoors.",
                'reviewer': 'Zane F.',
                'product': 'Ceramic Plant Pot'
            },
            {
                'rating': 5,
                'comment': "Plastic Pot Set is lightweight and affordable.",
                'reviewer': 'Anna G.',
                'product': 'Plastic Pot Set'
            },
            {
                'rating': 4,
                'comment': "Terracotta Pots drain well but need protection in winter.",
                'reviewer': 'Ben H.',
                'product': 'Terracotta Pots'
            },
            {
                'rating': 5,
                'comment': "Hanging Planter Basket adds charm to my porch.",
                'reviewer': 'Clara I.',
                'product': 'Hanging Planter Basket'
            }
        ],

        "watering cans": [
            {
                'rating': 5,
                'comment': "Metal Watering Can is stylish and functional. Lasts forever.",
                'reviewer': 'Ella K.',
                'product': 'Metal Watering Can'
            },
            {
                'rating': 5,
                'comment': "Plastic Watering Can is lightweight and easy to carry.",
                'reviewer': 'Finn L.',
                'product': 'Plastic Watering Can'
            },
            {
                'rating': 4,
                'comment': "Long-Spout Watering Can reaches deep into plants.",
                'reviewer': 'Gina M.',
                'product': 'Long-Spout Watering Can'
            },
            {
                'rating': 5,
                'comment': "Small Watering Can is perfect for seedlings.",
                'reviewer': 'Hugo N.',
                'product': 'Small Watering Can'
            }
        ]
    }

    reviews = category_reviews.get(category_name, [])

    return render_template(
        "category.html",
        user=user,
        category_name=category_name,
        categories=CATEGORIES,
        products=products,
        reviews=reviews,
        admin_mode=admin_mode
    )


# cart and checkout routes
@app.route("/add_to_cart/<int:product_id>", methods=["POST"])
def add_to_cart(product_id):
    user = current_user()
    if not user:
        return jsonify({"success": False, "message": "Please log in."}), 401

    quantity = int(request.form.get("quantity", 1))

    product = Product.query.get(product_id)
    if not product:
        return jsonify({"success": False, "message": "Product not found."}), 404

    if "cart" not in session or not isinstance(session["cart"], list):
        session["cart"] = []

    cart = session["cart"]
    normalized_category = product.category.replace(" ", "_").title()

    for item in cart:
        if item["id"] == product.id:
            item["quantity"] += quantity
            session["cart"] = cart
            session.modified = True

            return jsonify({
                "success": True,
                "message": "Item quantity updated!",
                "cart_count": sum(i["quantity"] for i in cart)
            })

    cart.append({
        "id": product.id,
        "name": product.name,
        "price": float(product.price),
        "image_url": product.image_url,
        "category": normalized_category,
        "quantity": quantity
    })

    session["cart"] = cart
    session.modified = True

    return jsonify({
        "success": True,
        "message": "Item added to cart!",
        "cart_count": sum(i["quantity"] for i in cart)
    })


@app.route("/cart")
def cart():
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    cart = session.get("cart", [])
    items = []
    total = 0

    for item in cart:
        subtotal = item["price"] * item["quantity"]
        total += subtotal

        items.append({
            "id": item["id"],
            "name": item["name"],
            "price": item["price"],
            "quantity": item["quantity"],
            "subtotal": subtotal,
            "image_url": item["image_url"],
            "category": item["category"]
        })

    return render_template("cart.html", user=user, items=items, total=total)

@app.route("/remove_from_cart/<int:product_id>", methods=["POST"])
def remove_from_cart(product_id):
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    cart = session.get("cart", [])

    updated_cart = [item for item in cart if item["id"] != product_id]

    session["cart"] = updated_cart

    return ("", 204)  


@app.route("/update_quantity/<int:product_id>", methods=["POST"])
def update_quantity(product_id):
    new_qty = int(request.form.get("quantity", 1))

    cart = session.get("cart", [])

    for item in cart:
        if item["id"] == product_id:
            item["quantity"] = new_qty

    session["cart"] = cart
    return ("", 204)



@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    cart = session.get("cart", [])

    if request.method == "GET":
        if not cart:
            flash("Your cart is empty.", "warning")
        return render_template("checkout.html", user=user)

    pickup_option = request.form.get("pickup_option", "delivery")

    order_number = random.randint(10000, 99999)

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        total_price = sum(item["price"] * item["quantity"] for item in cart)

    
        cur.execute("""
            INSERT INTO orders (user_id, status, pickup_option, total, order_number)
            VALUES (%s, %s, %s, %s, %s)
        """, (user["id"], "pending", pickup_option, total_price, order_number))

        order_id = conn.insert_id()

        # Insert each item
        for item in cart:
            cur.execute("""
                INSERT INTO order_items (order_id, product_id, quantity, price_each)
                VALUES (%s, %s, %s, %s)
            """, (order_id, item["id"], item["quantity"], item["price"]))

            # Reduce stock
            cur.execute("""
                UPDATE products
                SET stock = stock - %s
                WHERE id = %s
            """, (item["quantity"], item["id"]))

        conn.commit()

        # Save order number for confirmation page
        session["order_number"] = order_number

        # Clear cart
        session["cart"] = []

        return redirect(url_for("order_confirmation"))

    except Exception as e:
        conn.rollback()
        print("Checkout error:", e)
        flash("Error placing order.", "danger")

    finally:
        cur.close()
        conn.close()




#order confirmation page
@app.route("/order_confirmation")
def order_confirmation():
    order_number = session.get("order_number")
    return render_template("order_confirmation.html", order_number=order_number)



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

    cur = get_db_cursor(dictionary=True)

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


# editing products
@app.route("/edit_product", methods=["GET"])
def edit_product_page():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") not in ["vendor"] and session.get("is_admin") != 1:
        return "Unauthorized", 403

    conn = get_db_connection()
    cur = conn.cursor(pymysql.cursors.DictCursor)

    cur.execute("SELECT * FROM products")
    products = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("edit_product.html", products=products)



@app.route("/edit_product", methods=["POST"])
def edit_product():

    if "user_id" not in session:
        return jsonify({
            "success": False,
            "message": "Not logged in"
        })

    if session.get("role") not in ["vendor"] and session.get("is_admin") != 1:
        return jsonify({
            "success": False,
            "message": "Unauthorized"
        })

    try:

        product_id = request.form.get("id")

        name = request.form.get("name")
        description = request.form.get("description")
        price = request.form.get("price")
        stock = request.form.get("stock")

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            UPDATE products
            SET
                name=%s,
                description=%s,
                price=%s,
                stock=%s
            WHERE id=%s
        """, (
            name,
            description,
            price,
            stock,
            product_id
        ))

        conn.commit()

        cur.close()
        conn.close()

        return jsonify({
            "success": True
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "message": str(e)
        })

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
@app.route("/request_refund", methods=["POST"])
def request_refund():

    user = current_user()

    if not user:
        return jsonify({
            "success": False,
            "message": "Please log in first."
        })

    data = request.get_json()

    order_number = data.get("order_number")
    reason = data.get("reason", "Refund requested through BloomyBot.")

    cur = get_db_cursor(dictionary=True)

    cur.execute("""
        SELECT 
            refund_requests.id,
            refund_requests.status,
            orders.total
        FROM refund_requests
        JOIN orders
            ON refund_requests.order_id = orders.id
        WHERE orders.order_number = %s
    """, (order_number,))

    existing_refund = cur.fetchone()

    if existing_refund and existing_refund["status"] == "approved":

        amount = existing_refund["total"]

        cur.close()

        return jsonify({
            "success": True,
            "message": f"${amount:.2f} will be credited back to your account shortly."
        })

    if existing_refund and existing_refund["status"] == "denied":

        cur.close()

        return jsonify({
            "success": False,
            "message": "Unfortunately your refund request was denied."
        })

    if existing_refund and existing_refund["status"] == "pending":

        cur.close()

        return jsonify({
            "success": True,
            "message": "Your refund request is still pending admin approval."
        })

    cur.execute("""
        SELECT id, user_id, total
        FROM orders
        WHERE order_number = %s
        AND user_id = %s
    """, (order_number, user["id"]))

    order = cur.fetchone()

    if not order:

        cur.close()

        return jsonify({
            "success": False,
            "message": "I could not find that order number under your account."
        })

    cur.execute("""
        INSERT INTO refund_requests
        (order_id, user_id, reason)
        VALUES (%s, %s, %s)
    """, (
        order["id"],
        user["id"],
        reason
    ))

    cur.connection.commit()
    cur.close()

    return jsonify({
        "success": True,
        "message": "Your refund request has been submitted. An admin will review it soon."
    })

@app.route("/update_refund_status/<int:refund_id>", methods=["POST"])
def update_refund_status(refund_id):

    if session.get("is_admin") != 1:
        return redirect(url_for("login"))

    status = request.form.get("status")

    cur = get_db_cursor()

    cur.execute("""
        UPDATE refund_requests
        SET status = %s
        WHERE id = %s
    """, (status, refund_id))

    cur.connection.commit()
    cur.close()

    flash("Refund request updated successfully!", "success")

    return redirect(url_for("admin_refunds"))
    return redirect(url_for("my_orders"))

@app.route("/admin/refunds")
def admin_refunds():

    if session.get("is_admin") != 1:
        return redirect(url_for("login"))

    cur = get_db_cursor(dictionary=True)

    cur.execute("""
        SELECT 
            refund_requests.id,
            refund_requests.reason,
            refund_requests.status,
            refund_requests.created_at,

            orders.order_number,
            orders.total,

            users.first_name,
            users.last_name,
            users.email

        FROM refund_requests

        JOIN orders 
            ON refund_requests.order_id = orders.id

        JOIN users 
            ON refund_requests.user_id = users.id

        ORDER BY refund_requests.created_at DESC
    """)

    refunds = cur.fetchall()
    cur.close()

    return render_template(
        "admin_refunds.html",
        refunds=refunds
    )

# customer service
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
        """, (first_name, last_name, phone, address, user["id"])) 
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


# delete product
@app.route("/delete_product/<int:product_id>", methods=["POST"])
def delete_product(product_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    if session.get("is_admin") != 1 and session.get("role") != "vendor":
        flash("Unauthorized", "danger")
        return redirect(request.referrer or url_for("dashboard"))
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        if session.get("role") == "vendor" and session.get("is_admin") != 1:
            cur.execute("SELECT vendor_id FROM products WHERE id = %s", (product_id,))
            product = cur.fetchone()
            if not product or product["vendor_id"] != session["user_id"]:
                flash("You cannot delete this product.", "danger")
                return redirect(request.referrer or url_for("dashboard"))
        cur.execute("DELETE FROM products WHERE id = %s", (product_id,))
        conn.commit()
        flash("Product deleted successfully.", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error deleting product: {str(e)}", "danger")
    finally:
        cur.close()
        conn.close()
    return redirect(request.referrer or url_for("dashboard"))



# admin revision-- dont touch
@app.route("/create_admin")
def create_admin():
    from werkzeug.security import generate_password_hash

    password_hash = generate_password_hash("admin123")

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO users 
    (username, first_name, last_name, email, phone, address, password_hash, is_admin, role)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
""", (
    "admin",
    "Admin",
    "User",
    "admin@example.com",
    "000-000-0000",
    "123 Admin Street",
    password_hash,
    True,
    "admin"
))

    conn.commit()
    cur.close()
    conn.close()

    return "Admin user created. You can now log in."


# Admin update products view
@app.route("/admin/store")
def admin_store_view():
    if not is_admin():
        return redirect(url_for("login"))

    user = current_user()

    return render_template(
        "dashboard.html",
        user=user,
        categories=CATEGORIES,
        admin_mode=True
    )


# review submissions
@app.route("/submit_review/<int:order_id>", methods=["POST"])
def submit_review(order_id):

    user = current_user()

    if not user:
        return redirect(url_for("login"))

    rating = request.form.get("rating")
    comment = request.form.get("comment")

    cur = get_db_cursor()

    cur.execute("""
        INSERT INTO reviews (user_id, order_id, rating, comment)
        VALUES (%s, %s, %s, %s)
    """, (
        user["id"],
        order_id,
        rating,
        comment
    ))

    cur.connection.commit()
    cur.close()

    flash("Review submitted successfully!", "success")

    return redirect(url_for("my_orders"))

# vendor authentication page
@app.route("/admin/vendor-authentication")
def vendor_authentication():

    if session.get("is_admin") != 1:
        flash("Admin access only.", "danger")
        return redirect(url_for("dashboard"))

    cur = get_db_cursor()

    cur.execute("""
        SELECT *
        FROM users
        WHERE role = 'vendor'
        AND vendor_approved = 0
    """)

    pending_vendors = cur.fetchall()

    cur.close()

    return render_template(
        "vendor_authentication.html",
        pending_vendors=pending_vendors
    )

@app.route("/approve-vendor/<int:vendor_id>", methods=["POST"])
def approve_vendor(vendor_id):

    if session.get("is_admin") != 1:
        flash("Admin access only.", "danger")
        return redirect(url_for("dashboard"))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE users
        SET vendor_approved = 1
        WHERE id = %s
    """, (vendor_id,))

    conn.commit()

    cursor.close()
    conn.close()

    flash("Vendor approved successfully.", "success")

    return redirect(url_for("vendor_authentication"))



# create product 
@app.route("/create_product", methods=["POST"])
def create_product():
    if "user_id" not in session:
        return jsonify({"success": False, "message": "Not logged in"})

    if session.get("role") != "vendor" and session.get("is_admin") != 1:
        return jsonify({"success": False, "message": "Unauthorized"})

    try:
        name = request.form.get("name")
        description = request.form.get("description")
        price = request.form.get("price")
        stock = request.form.get("stock")
        category = request.form.get("category")
        image = request.files.get("image")

        if not name or not price or not stock or not category:
            return jsonify({"success": False, "message": "Missing required fields"})

        image_filename = None

        if image and image.filename:
            image_filename = secure_filename(image.filename)

            folder_name = category.replace(" ", "_")
            upload_folder = os.path.join(
                app.root_path,
                "static",
                "Garden_Catalog",
                folder_name
            )

            os.makedirs(upload_folder, exist_ok=True)

            image.save(os.path.join(upload_folder, image_filename))
        else:
            image_filename = "default.png"

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO products
            (name, category, description, price, stock, image_url, vendor_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            name,
            category,
            description,
            price,
            stock,
            image_filename,
            session.get("user_id")
        ))

        conn.commit()

        cur.close()
        conn.close()

        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route("/get_product/<int:product_id>")
def get_product(product_id):
    if "user_id" not in session:
        return jsonify({"success": False, "message": "Not logged in"}), 401

    if session.get("role") != "vendor" and session.get("is_admin") != 1:
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    conn = get_db_connection()
    cur = conn.cursor(pymysql.cursors.DictCursor)

    cur.execute("""
        SELECT id, name, description, price, stock
        FROM products
        WHERE id = %s
    """, (product_id,))

    product = cur.fetchone()

    cur.close()
    conn.close()

    if not product:
        return jsonify({"success": False, "message": "Product not found"}), 404

    return jsonify(product)




if __name__ == "__main__":
    app.run(debug=True, port=5001)
