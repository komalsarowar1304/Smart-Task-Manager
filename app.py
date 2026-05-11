from flask import Flask, render_template, redirect, url_for, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_socketio import SocketIO, emit
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Task
import pandas as pd
import numpy as np

app = Flask(__name__)

# --- Configurations ---
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:admin123@localhost:5432/smart_task_db'
app.config['SECRET_KEY'] = 'smart_task_key_99'

# --- Initialization ---
db.init_app(app)
socketio = SocketIO(app, cors_allowed_origins="*")
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# --- Authentication ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        hashed_pw = generate_password_hash(password, method='pbkdf2:sha256')
        if not User.query.filter_by(username=username).first():
            new_user = User(username=username, password=hashed_pw)
            db.session.add(new_user)
            db.session.commit()
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
    return render_template('login.html')

# --- Dashboard & Analytics ---
@app.route('/dashboard')
@login_required
def dashboard():
    user_tasks = Task.query.filter_by(user_id=current_user.id).all()
    total, completed, pending, percent = 0, 0, 0, 0
    if user_tasks:
        df = pd.DataFrame([{'status': t.status} for t in user_tasks])
        total = len(df)
        completed = len(df[df['status'] == 'Completed'])
        pending = total - completed
        percent = np.round((completed / total) * 100, 2)
    return render_template('dashboard.html', tasks=user_tasks, total=total, 
                           completed=completed, pending=pending, percent=percent)

# --- REST APIs (CRUD) ---

@app.route('/api/add_task', methods=['GET', 'POST'])
@login_required
def add_task_api():
    if request.method == 'POST':
        data = request.form
        new_task = Task(
            title=data['title'], 
            description=data.get('description'), 
            priority=data['priority'], 
            user_id=current_user.id
        )
        db.session.add(new_task)
        db.session.commit()
        # Fixed SocketIO (Removed broadcast=True to avoid TypeError)
        socketio.emit('task_added', {'message': f'New task "{data["title"]}" added!'})
        return redirect(url_for('dashboard'))
    return redirect(url_for('dashboard'))

@app.route('/api/update_task/<int:id>', methods=['GET', 'POST', 'PUT'])
@login_required
def update_task_api(id):
    task = db.session.get(Task, id)
    if task and task.user_id == current_user.id:
        task.status = 'Completed'
        db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/api/delete_task/<int:id>', methods=['GET', 'DELETE'])
@login_required
def delete_task_api(id):
    task = db.session.get(Task, id)
    if task and task.user_id == current_user.id:
        db.session.delete(task)
        db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    socketio.run(app, debug=True)