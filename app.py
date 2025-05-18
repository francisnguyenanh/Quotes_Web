from flask import Flask, render_template, request, redirect, url_for, flash, session, make_response
import sqlite3
import random
from jinja2 import Environment
from markupsafe import Markup
import difflib
from itsdangerous import URLSafeTimedSerializer as Serializer, BadSignature, SignatureExpired
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Khóa bí mật để mã hóa token
app.config['JSON_AS_ASCII'] = False

ADMIN_PASSWORD = "1"

def nl2br(value):
    return Markup(value.replace('\n', '<br>'))

app.jinja_env.filters['nl2br'] = nl2br

def init_db():
    conn = sqlite3.connect('quotes.db')
    conn.execute('PRAGMA encoding = "UTF-8"')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS quotes 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  content TEXT NOT NULL,
                  category TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS tokens 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  token TEXT NOT NULL,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

def check_password(password):
    return password == ADMIN_PASSWORD

def generate_token(expiration=180*24*3600):  # 180 ngày
    s = Serializer(app.secret_key)
    return s.dumps({'authenticated': True})

def verify_token(token, expiration=180*24*3600):
    s = Serializer(app.secret_key)
    try:
        s.loads(token, max_age=expiration)
        conn = sqlite3.connect('quotes.db')
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM tokens WHERE token = ?", (token,))
        exists = c.fetchone()[0] > 0
        conn.close()
        return exists
    except (BadSignature, SignatureExpired):
        return False

@app.route('/', methods=['GET', 'POST'])
def quotes():
    conn = sqlite3.connect('quotes.db')
    conn.execute('PRAGMA encoding = "UTF-8"')
    c = conn.cursor()

    c.execute("SELECT DISTINCT category FROM quotes")
    categories = [row[0] for row in c.fetchall()]

    quote = None
    selected_category = None

    c.execute("SELECT * FROM quotes")
    all_quotes = c.fetchall()

    if request.method == 'POST':
        if 'category' in request.form and request.form['category']:
            selected_category = request.form['category']
            c.execute("SELECT * FROM quotes WHERE category = ?", (selected_category,))
            quotes_list = c.fetchall()
            if quotes_list:
                quote = random.choice(quotes_list)
        else:
            if all_quotes:
                quote = random.choice(all_quotes)

    if not quote and all_quotes:
        quote = random.choice(all_quotes)

    conn.close()
    return render_template('quotes.html', quote=quote, categories=categories, selected_category=selected_category)

@app.route('/manage', methods=['GET', 'POST'])
def manage():
    conn = sqlite3.connect('quotes.db')
    conn.execute('PRAGMA encoding = "UTF-8"')
    c = conn.cursor()

    # Kiểm tra token từ cookie
    auth_token = request.cookies.get('auth_token')
    is_authenticated = auth_token and verify_token(auth_token)

    # Khởi tạo response
    response = None

    if request.method == 'POST':
        password = request.form.get('password')
        if not is_authenticated and not check_password(password):
            flash("Mật khẩu không đúng!", "error")
            c.execute("SELECT * FROM quotes ORDER BY content")
            quotes = c.fetchall()
            c.execute("SELECT DISTINCT category FROM quotes")
            categories = [row[0] for row in c.fetchall()]
            c.execute("SELECT category, COUNT(*) as count FROM quotes GROUP BY category")
            category_counts = c.fetchall()
            conn.close()
            return render_template('index.html', quotes=quotes, categories=categories, category_counts=category_counts, require_password=True)

        if not is_authenticated and check_password(password):
            # Tạo token và lưu vào cookie + database
            token = generate_token()
            c.execute("INSERT INTO tokens (token) VALUES (?)", (token,))
            conn.commit()
            response = make_response(redirect(url_for('manage')))
            response.set_cookie('auth_token', token, max_age=180*24*3600, httponly=True, secure=True, samesite='Strict')
            flash("Xác thực thành công! Thiết bị này sẽ không cần nhập mật khẩu trong 180 ngày.", "success")

        if 'content' in request.form and 'category' in request.form:
            content = request.form['content'].strip()
            category = request.form['category'].strip()

            # Kiểm tra độ tương đồng với các trích dẫn hiện có
            c.execute("SELECT content FROM quotes")
            existing_quotes = [row[0] for row in c.fetchall()]
            for existing_content in existing_quotes:
                similarity = difflib.SequenceMatcher(None, content.lower(), existing_content.lower()).ratio()
                if similarity >= 0.8:
                    flash("Trích dẫn này quá giống (≥95%) với một trích dẫn đã tồn tại! Vui lòng nhập trích dẫn khác.", "error")
                    c.execute("SELECT * FROM quotes ORDER BY content")
                    quotes = c.fetchall()
                    c.execute("SELECT DISTINCT category FROM quotes")
                    categories = [row[0] for row in c.fetchall()]
                    c.execute("SELECT category, COUNT(*) as count FROM quotes GROUP BY category")
                    category_counts = c.fetchall()
                    conn.close()
                    return render_template('index.html', quotes=quotes, categories=categories, category_counts=category_counts, require_password=not is_authenticated)

            # Nếu không trùng, chèn trích dẫn mới
            c.execute("INSERT INTO quotes (content, category) VALUES (?, ?)", (content, category))
            conn.commit()
            flash("Trích dẫn đã được thêm thành công!", "success")

    c.execute("SELECT * FROM quotes ORDER BY content")
    quotes = c.fetchall()
    c.execute("SELECT DISTINCT category FROM quotes")
    categories = [row[0] for row in c.fetchall()]
    c.execute("SELECT category, COUNT(*) as count FROM quotes GROUP BY category")
    category_counts = c.fetchall()

    conn.close()
    return response or render_template('index.html', quotes=quotes, categories=categories, category_counts=category_counts, require_password=not is_authenticated)

@app.route('/edit/<int:id>', methods=['POST'])
def edit(id):
    auth_token = request.cookies.get('auth_token')
    is_authenticated = auth_token and verify_token(auth_token)

    response = None
    if request.method == 'POST':
        password = request.form.get('password')
        if not is_authenticated and not check_password(password):
            flash("Mật khẩu không đúng!", "error")
            return redirect(url_for('manage'))

        if not is_authenticated and check_password(password):
            # Tạo token và lưu vào cookie + database
            conn = sqlite3.connect('quotes.db')
            c = conn.cursor()
            token = generate_token()
            c.execute("INSERT INTO tokens (token) VALUES (?)", (token,))
            conn.commit()
            response = make_response(redirect(url_for('manage')))
            response.set_cookie('auth_token', token, max_age=180*24*3600, httponly=True, secure=True, samesite='Strict')
            flash("Xác thực thành công! Thiết bị này sẽ không cần nhập mật khẩu trong 180 ngày.", "success")

        content = request.form['content']
        category = request.form['category']

        conn = sqlite3.connect('quotes.db')
        conn.execute('PRAGMA encoding = "UTF-8"')
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM quotes WHERE id = ?", (id,))
        if c.fetchone()[0] == 0:
            flash("Trích dẫn không tồn tại!", "error")
            conn.close()
            return response or redirect(url_for('manage'))

        c.execute("UPDATE quotes SET content = ?, category = ? WHERE id = ?", (content, category, id))
        conn.commit()
        conn.close()
        flash("Trích dẫn đã được sửa thành công!", "success")

    return response or redirect(url_for('manage'))

@app.route('/delete/<int:id>')
def delete(id):
    auth_token = request.cookies.get('auth_token')
    is_authenticated = auth_token and verify_token(auth_token)

    response = None
    password = request.args.get('password')
    if not is_authenticated and not check_password(password):
        flash("Mật khẩu không đúng!", "error")
        return redirect(url_for('manage'))

    if not is_authenticated and check_password(password):
        # Tạo token và lưu vào cookie + database
        conn = sqlite3.connect('quotes.db')
        c = conn.cursor()
        token = generate_token()
        c.execute("INSERT INTO tokens (token) VALUES (?)", (token,))
        conn.commit()
        response = make_response(redirect(url_for('manage')))
        response.set_cookie('auth_token', token, max_age=180*24*3600, httponly=True, secure=True, samesite='Strict')
        flash("Xác thực thành công! Thiết bị này sẽ không cần nhập mật khẩu trong 180 ngày.", "success")

    conn = sqlite3.connect('quotes.db')
    conn.execute('PRAGMA encoding = "UTF-8"')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM quotes WHERE id = ?", (id,))
    if c.fetchone()[0] == 0:
        flash("Trích dẫn không tồn tại!", "error")
        conn.close()
        return response or redirect(url_for('manage'))

    c.execute("DELETE FROM quotes WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    flash("Trích dẫn đã được xóa thành công!", "success")
    return response or redirect(url_for('manage'))

@app.route('/delete_category/<category>')
def delete_category(category):
    auth_token = request.cookies.get('auth_token')
    is_authenticated = auth_token and verify_token(auth_token)

    response = None
    password = request.args.get('password')
    if not is_authenticated and not check_password(password):
        flash("Mật khẩu không đúng!", "error")
        return redirect(url_for('manage'))

    if not is_authenticated and check_password(password):
        # Tạo token và lưu vào cookie + database
        conn = sqlite3.connect('quotes.db')
        c = conn.cursor()
        token = generate_token()
        c.execute("INSERT INTO tokens (token) VALUES (?)", (token,))
        conn.commit()
        response = make_response(redirect(url_for('manage')))
        response.set_cookie('auth_token', token, max_age=180*24*3600, httponly=True, secure=True, samesite='Strict')
        flash("Xác thực thành công! Thiết bị này sẽ không cần nhập mật khẩu trong 180 ngày.", "success")

    conn = sqlite3.connect('quotes.db')
    conn.execute('PRAGMA encoding = "UTF-8"')
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM quotes WHERE category = ?", (category,))
    quote_count = c.fetchone()[0]

    if quote_count > 0:
        flash(
            f"Không thể xóa nguồn '{category}' vì đang chứa {quote_count} trích dẫn. Vui lòng xóa hết trích dẫn trong nguồn này trước.",
            "error")
    else:
        flash(f"Nguồn '{category}' đã được xóa thành công.", "success")

    conn.close()
    return response or redirect(url_for('manage'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)