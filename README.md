# Vulnerable Python Webapp

A deliberately vulnerable Juice Shop-style Flask web application for practicing application security concepts and tooling.

## Features

- User registration and login
- Product store with categories (juices, apparel, accessories, gift cards)
- Shopping cart and checkout
- Product reviews
- Order history
- Admin panel with user management and network diagnostics

## Intentional Vulnerabilities

This application contains **20 intentional security issues** spanning 8 vulnerability classes. Do not deploy this in any real environment.

| # | Severity | CWE | Location | Description |
|---|----------|-----|----------|-------------|
| 1–5 | High | CWE-89 | `login`, `register`, `store`, `search`, `review` routes | SQL Injection via string-concatenated queries |
| 6–8 | High | CWE-502 | `add_to_cart`, `cart`, `checkout` routes | Insecure Deserialization — cookie value passed directly to `pickle.loads()` |
| 9–11 | High | CWE-79 / CWE-96 | `search`, `welcome`, `admin_ping` routes | XSS and Server-Side Template Injection via `Markup()` and `render_template_string()` |
| 12 | High | CWE-78 | `admin_ping` route | Command Injection — host input passed to `subprocess.check_output(..., shell=True)` |
| 13 | High | CWE-23 | `download` route | Path Traversal — filename parameter joined unsanitized before `send_file()` |
| 14 | High | CWE-547 | `app.py:12` | Hardcoded Secret — `app.secret_key` set to a literal string |
| 15 | Medium | CWE-489 | `app.py:367` | Debug Mode Enabled — `app.run(debug=True)` exposes interactive debugger |
| 16–18 | Low | CWE-916 | `init_db`, `login`, `register` | Weak Password Hashing — `hashlib.md5()` used instead of a slow hash like bcrypt |
| 19–20 | — | — | `orders` route | IDOR — `user_id` accepted from query param instead of enforced from session |

## Setup

```bash
cd ~/snyk_demo/vulnerable_python_webapp
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

The app runs at `http://localhost:8888`.

Default admin credentials: `admin` / `admin123`

## Project Structure

```
.
├── app.py              # Flask application (all vulnerability surface)
├── requirements.txt    # Python dependencies
├── shop.db             # SQLite database (auto-created on first run)
└── templates/
    ├── base.html
    ├── index.html
    ├── login.html
    ├── register.html
    ├── store.html
    ├── product.html
    ├── cart.html
    ├── orders.html
    ├── profile.html
    └── admin.html
```

## Disclaimer

This application is **intentionally insecure** and intended for security education only. Never expose it to a network or use real credentials.
