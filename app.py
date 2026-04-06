from flask import Flask, render_template, request, redirect, session, url_for, flash
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import os

app = Flask(__name__)
app.secret_key = "quizforge_secret_key_2026"

# -------------------------------
# DATABASE CONFIGURATION
# -------------------------------
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "1234567890", # Using password from original code
}
DB_NAME = "quiz_app"

def get_db_connection(database=DB_NAME):
    """Establish database connection."""
    try:
        return mysql.connector.connect(
            **DB_CONFIG,
            database=database
        )
    except mysql.connector.Error as err:
        if err.errno == 1049: # Unknown database
            # Attempt to create database if it doesn't exist
            conn = mysql.connector.connect(**DB_CONFIG)
            cursor = conn.cursor()
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
            conn.close()
            return mysql.connector.connect(**DB_CONFIG, database=DB_NAME)
        raise err

def init_db():
    """Initialize the database and create tables if they don't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create Users Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL
        )
    """)
    
    # Ensure password column is long enough (in case table already exists with small length)
    try:
        cursor.execute("ALTER TABLE users MODIFY COLUMN password VARCHAR(255) NOT NULL")
    except mysql.connector.Error:
        pass # Handle case where column already has the right length or another issue
    
    # Create Quizzes Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quizzes (
            id INT AUTO_INCREMENT PRIMARY KEY,
            title VARCHAR(100) NOT NULL,
            created_by VARCHAR(50) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create Questions Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            quiz_id INT NOT NULL,
            question TEXT NOT NULL,
            option1 VARCHAR(255) NOT NULL,
            option2 VARCHAR(255) NOT NULL,
            option3 VARCHAR(255) NOT NULL,
            option4 VARCHAR(255) NOT NULL,
            correct_answer VARCHAR(50) NOT NULL,
            FOREIGN KEY (quiz_id) REFERENCES quizzes(id) ON DELETE CASCADE
        )
    """)
    
    conn.commit()
    conn.close()

# Initialize DB on start
init_db()

# -------------------------------
# AUTH DECORATOR
# -------------------------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash("Please log in first!", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# -------------------------------
# ROUTES
# -------------------------------

@app.route('/')
def home():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return render_template('home.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = request.form.get('password').strip()

        if not username or not password:
            flash("Username and password are required!", "danger")
            return redirect(url_for('register'))

        hashed_pw = generate_password_hash(password)

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, hashed_pw))
            conn.commit()
            conn.close()
            flash("Registration successful! Please login.", "success")
            return redirect(url_for('login'))
        except mysql.connector.IntegrityError:
            flash("Username already exists! Choose another one.", "danger")
            return redirect(url_for('register'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = request.form.get('password').strip()

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username=%s", (username,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['username'] = username
            flash(f"Welcome back, {username}!", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid credentials! Try again.", "danger")
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM quizzes ORDER BY created_at DESC")
    quizzes = cursor.fetchall()
    conn.close()
    return render_template('dashboard.html', quizzes=quizzes)

@app.route('/create_quiz', methods=['GET', 'POST'])
@login_required
def create_quiz():
    if request.method == 'POST':
        title = request.form.get('title').strip()
        if not title:
            flash("Quiz title is required!", "danger")
            return redirect(url_for('create_quiz'))

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO quizzes (title, created_by) VALUES (%s, %s)", (title, session['username']))
        quiz_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        flash("Quiz created! Now add some questions.", "success")
        return redirect(url_for('add_question', quiz_id=quiz_id))

    return render_template('create_quiz.html')

@app.route('/add_question/<int:quiz_id>', methods=['GET', 'POST'])
@login_required
def add_question(quiz_id):
    if request.method == 'POST':
        question = request.form.get('question').strip()
        option1 = request.form.get('option1').strip()
        option2 = request.form.get('option2').strip()
        option3 = request.form.get('option3').strip()
        option4 = request.form.get('option4').strip()
        correct = request.form.get('correct').strip()

        if not all([question, option1, option2, option3, option4, correct]):
            flash("All fields are required!", "danger")
            return redirect(url_for('add_question', quiz_id=quiz_id))

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO questions 
            (quiz_id, question, option1, option2, option3, option4, correct_answer)
            VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (quiz_id, question, option1, option2, option3, option4, correct)
        )
        conn.commit()
        conn.close()

        flash("Question added successfully!", "success")
        if 'add_another' in request.form:
            return redirect(url_for('add_question', quiz_id=quiz_id))
        return redirect(url_for('dashboard'))

    return render_template('add_question.html', quiz_id=quiz_id)

@app.route('/quiz/<int:quiz_id>')
@login_required
def attempt_quiz(quiz_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get quiz title
    cursor.execute("SELECT title FROM quizzes WHERE id=%s", (quiz_id,))
    quiz = cursor.fetchone()
    
    if not quiz:
        conn.close()
        flash("Quiz not found!", "danger")
        return redirect(url_for('dashboard'))

    cursor.execute("SELECT * FROM questions WHERE quiz_id=%s", (quiz_id,))
    questions = cursor.fetchall()
    conn.close()

    if not questions:
        flash("This quiz has no questions yet!", "warning")
        return redirect(url_for('dashboard'))

    return render_template('quiz.html', questions=questions, quiz_id=quiz_id, title=quiz['title'])

@app.route('/submit/<int:quiz_id>', methods=['POST'])
@login_required
def submit_quiz(quiz_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM questions WHERE quiz_id=%s", (quiz_id,))
    questions = cursor.fetchall()
    
    cursor.execute("SELECT title FROM quizzes WHERE id=%s", (quiz_id,))
    quiz = cursor.fetchone()
    
    conn.close()

    score = 0
    results = []

    for q in questions:
        user_answer = request.form.get(str(q['id']))
        is_correct = (user_answer == q['correct_answer'])
        if is_correct:
            score += 1
        
        results.append({
            'question': q['question'],
            'user_answer': q[user_answer] if user_answer else "No answer",
            'correct_answer': q[q['correct_answer']],
            'is_correct': is_correct
        })

    return render_template('result.html', score=score, total=len(questions), quiz_title=quiz['title'], results=results)

if __name__ == '__main__':
    app.run(debug=True)
