import sqlite3
import hashlib
import os
import pickle
import base64
import subprocess
from flask import (Flask, request, render_template, redirect,
                   url_for, session, Markup, render_template_string,
                   send_file)

app = Flask(__name__)
app.secret_key = "SuperSecret123!"  # hardcoded secret key

DB_PATH = os.path.join(os.path.dirname(__file__), 'shop.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()
    c.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email TEXT,
            is_admin INTEGER DEFAULT 0,
            balance REAL DEFAULT 100.0
        );
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            price REAL NOT NULL,
            category TEXT,
            stock INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            product_id INTEGER,
            quantity INTEGER,
            total REAL,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            user_id INTEGER,
            content TEXT,
            rating INTEGER
        );
    ''')

    admin_pw = hashlib.md5(b'admin123').hexdigest()
    c.execute(
        "INSERT OR IGNORE INTO users (id, username, password, email, is_admin) "
        "VALUES (1, 'admin', ?, 'admin@juiceshop.com', 1)",
        (admin_pw,)
    )

    sample_products = [
        ('Apple Juice 1L',      'Fresh squeezed apple juice',   1.99, 'juice',       50),
        ('Orange Juice 1L',     'Pulp-free orange juice',        2.49, 'juice',       30),
        ('Banana Smoothie 0.5L','Creamy banana blend',           2.99, 'juice',       20),
        ('Lemon Juice 0.3L',    'Sour lemon concentrate',        3.49, 'juice',       15),
        ('Strawberry Mix 1L',   'Mixed berry delight',           3.99, 'juice',       25),
        ('Green Detox 0.5L',    'Kale, spinach and cucumber',    4.49, 'juice',       18),
        ('T-Shirt (M)',         'JuiceShop branded tee',        12.99, 'apparel',     10),
        ('Hoodie (L)',          'JuiceShop logo hoodie',        24.99, 'apparel',      5),
        ('Water Bottle 750ml',  'BPA-free reusable bottle',      8.99, 'accessories', 40),
        ('Tote Bag',            'Canvas shopping bag',           6.99, 'accessories', 35),
        ('Sticker Pack',        '10 x JuiceShop stickers',       2.99, 'accessories', 80),
        ('Gift Card $25',       'Digital gift card',            25.00, 'gift',       100),
    ]
    c.executemany(
        "INSERT OR IGNORE INTO products (name, description, price, category, stock) VALUES (?,?,?,?,?)",
        sample_products
    )
    conn.commit()
    conn.close()


# ── Auth ──────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    conn = get_db()
    featured = conn.execute("SELECT * FROM products ORDER BY RANDOM() LIMIT 4").fetchall()
    conn.close()
    return render_template('index.html', products=featured)


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        password_hash = hashlib.md5(password.encode()).hexdigest()

        conn = get_db()
        # SQL Injection: user input concatenated directly into query
        query = "SELECT * FROM users WHERE username='" + username + "' AND password='" + password_hash + "'"
        user = conn.execute(query).fetchone()
        conn.close()

        if user:
            session['user_id']  = user['id']
            session['username'] = user['username']
            session['is_admin'] = bool(user['is_admin'])
            return redirect(url_for('store'))
        error = 'Invalid username or password'

    return render_template('login.html', error=error)


@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        email    = request.form.get('email', '')

        password_hash = hashlib.md5(password.encode()).hexdigest()

        conn = get_db()
        try:
            # SQL Injection: user input concatenated directly into query
            query = (
                f"INSERT INTO users (username, password, email) "
                f"VALUES ('{username}', '{password_hash}', '{email}')"
            )
            conn.execute(query)
            conn.commit()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            error = 'Username already taken'
        finally:
            conn.close()

    return render_template('register.html', error=error)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


# ── Store ─────────────────────────────────────────────────────────────────────

@app.route('/store')
def store():
    category = request.args.get('category', '')
    conn = get_db()
    if category:
        # SQL Injection: category param injected into query
        products = conn.execute(
            f"SELECT * FROM products WHERE category='{category}'"
        ).fetchall()
    else:
        products = conn.execute("SELECT * FROM products").fetchall()
    conn.close()
    return render_template('store.html', products=products, category=category)


@app.route('/product/<int:product_id>')
def product_detail(product_id):
    conn = get_db()
    product = conn.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
    reviews = conn.execute(
        "SELECT r.*, u.username FROM reviews r "
        "JOIN users u ON r.user_id = u.id WHERE r.product_id=?",
        (product_id,)
    ).fetchall()
    conn.close()
    if not product:
        return "Product not found", 404
    return render_template('product.html', product=product, reviews=reviews)


@app.route('/search')
def search():
    q = request.args.get('q', '')
    conn = get_db()
    # SQL Injection: search term injected into LIKE query
    results = conn.execute(
        f"SELECT * FROM products WHERE name LIKE '%{q}%' OR description LIKE '%{q}%'"
    ).fetchall()
    conn.close()
    # XSS: user-supplied input marked as safe HTML via Markup()
    search_header = Markup(f'<em>Results for "{q}"</em>')
    return render_template('store.html', products=results, search_header=search_header)


@app.route('/welcome')
def welcome():
    name = request.args.get('name', 'Guest')
    # XSS: user input embedded directly in render_template_string
    return render_template_string(f'<h1>Welcome back, {name}!</h1><p><a href="/">Home</a></p>')


# ── Cart ──────────────────────────────────────────────────────────────────────

@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    product_id = int(request.form.get('product_id', 0))
    quantity   = int(request.form.get('quantity', 1))

    cart_cookie = request.cookies.get('cart', '')
    if cart_cookie:
        # Insecure deserialization: attacker-controlled cookie passed to pickle.loads
        cart = pickle.loads(base64.b64decode(cart_cookie))
    else:
        cart = {}

    cart[product_id] = cart.get(product_id, 0) + quantity

    response = redirect(url_for('cart'))
    response.set_cookie('cart', base64.b64encode(pickle.dumps(cart)).decode())
    return response


@app.route('/cart')
def cart():
    cart_cookie = request.cookies.get('cart', '')
    items, total = [], 0.0
    if cart_cookie:
        try:
            # Insecure deserialization: attacker-controlled cookie passed to pickle.loads
            cart = pickle.loads(base64.b64decode(cart_cookie))
            conn = get_db()
            for pid, qty in cart.items():
                p = conn.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
                if p:
                    sub = p['price'] * qty
                    items.append({'product': p, 'quantity': qty, 'subtotal': sub})
                    total += sub
            conn.close()
        except Exception:
            pass
    return render_template('cart.html', items=items, total=round(total, 2))


@app.route('/checkout', methods=['POST'])
def checkout():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    cart_cookie = request.cookies.get('cart', '')
    if not cart_cookie:
        return redirect(url_for('cart'))

    # Insecure deserialization: attacker-controlled cookie passed to pickle.loads
    cart = pickle.loads(base64.b64decode(cart_cookie))
    conn = get_db()
    for pid, qty in cart.items():
        p = conn.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
        if p:
            conn.execute(
                "INSERT INTO orders (user_id, product_id, quantity, total) VALUES (?,?,?,?)",
                (session['user_id'], pid, qty, round(p['price'] * qty, 2))
            )
    conn.commit()
    conn.close()

    resp = redirect(url_for('order_history'))
    resp.delete_cookie('cart')
    return resp


# ── Orders / Profile ──────────────────────────────────────────────────────────

@app.route('/orders')
def order_history():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # IDOR: user_id accepted from query param rather than enforced from session
    user_id = request.args.get('user_id', session['user_id'])
    conn = get_db()
    orders = conn.execute(
        "SELECT o.*, p.name AS product_name FROM orders o "
        "JOIN products p ON o.product_id = p.id WHERE o.user_id=?",
        (user_id,)
    ).fetchall()
    conn.close()
    return render_template('orders.html', orders=orders)


@app.route('/review', methods=['POST'])
def add_review():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    product_id = request.form.get('product_id', '')
    content    = request.form.get('content', '')
    rating     = request.form.get('rating', '5')

    conn = get_db()
    # SQL Injection + Stored XSS: content injected directly into query
    query = (
        f"INSERT INTO reviews (product_id, user_id, content, rating) "
        f"VALUES ({product_id}, {session['user_id']}, '{content}', {rating})"
    )
    conn.execute(query)
    conn.commit()
    conn.close()
    return redirect(url_for('product_detail', product_id=product_id))


@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id=?", (session['user_id'],)).fetchone()
    conn.close()
    return render_template('profile.html', user=user)


# ── Admin ─────────────────────────────────────────────────────────────────────

@app.route('/admin')
def admin_panel():
    if not session.get('is_admin'):
        return redirect(url_for('index'))
    conn = get_db()
    users  = conn.execute("SELECT * FROM users").fetchall()
    orders = conn.execute(
        "SELECT o.*, u.username, p.name AS product_name FROM orders o "
        "JOIN users u ON o.user_id=u.id JOIN products p ON o.product_id=p.id"
    ).fetchall()
    conn.close()
    return render_template('admin.html', users=users, orders=orders)


@app.route('/admin/ping', methods=['POST'])
def admin_ping():
    host = request.form.get('host', 'localhost')
    # Command injection: user-supplied host passed directly to shell
    output = subprocess.check_output(f"ping -c 2 {host}", shell=True, stderr=subprocess.STDOUT)
    return render_template_string(f"<pre>{output.decode()}</pre>")


@app.route('/download')
def download_file():
    filename = request.args.get('file', '')
    # Path traversal: filename not validated before joining with base path
    filepath = os.path.join(os.path.dirname(__file__), 'static', filename)
    return send_file(filepath)


if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)  # debug mode exposes interactive debugger
