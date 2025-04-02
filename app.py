from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
import random

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Cần cho flash messages
app.config['JSON_AS_ASCII'] = False  # Đảm bảo JSON không mã hóa ASCII

def init_db():
    conn = sqlite3.connect('quotes.db')
    conn.execute('PRAGMA encoding = "UTF-8"')  # Đặt encoding UTF-8 cho SQLite
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS quotes 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  content TEXT NOT NULL,
                  category TEXT NOT NULL)''')
    conn.commit()
    conn.close()

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

    if request.method == 'POST':
        if 'content' in request.form and 'category' in request.form:
            content = request.form['content']
            category = request.form['category']
            c.execute("INSERT INTO quotes (content, category) VALUES (?, ?)", (content, category))
            conn.commit()

    c.execute("SELECT * FROM quotes")
    quotes = c.fetchall()
    c.execute("SELECT DISTINCT category FROM quotes")
    categories = [row[0] for row in c.fetchall()]

    c.execute("SELECT category, COUNT(*) as count FROM quotes GROUP BY category")
    category_counts = c.fetchall()

    conn.close()
    return render_template('index.html', quotes=quotes, categories=categories, category_counts=category_counts)

@app.route('/edit/<int:id>', methods=['POST'])
def edit(id):
    if request.method == 'POST':
        content = request.form['content']
        category = request.form['category']

        conn = sqlite3.connect('quotes.db')
        conn.execute('PRAGMA encoding = "UTF-8"')
        c = conn.cursor()
        c.execute("UPDATE quotes SET content = ?, category = ? WHERE id = ?", (content, category, id))
        conn.commit()
        conn.close()

    return redirect(url_for('manage'))

@app.route('/delete/<int:id>')
def delete(id):
    conn = sqlite3.connect('quotes.db')
    conn.execute('PRAGMA encoding = "UTF-8"')
    c = conn.cursor()
    c.execute("DELETE FROM quotes WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('manage'))

@app.route('/delete_category/<category>')
def delete_category(category):
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
    return redirect(url_for('manage'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)