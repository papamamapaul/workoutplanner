from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'deine_secret_key_hier')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///workout.db')
if app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgres://'):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace('postgres://', 'postgresql://', 1)

db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Datenbankmodelle
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    workouts = db.relationship('Workout', backref='user', lazy=True)
    
class Exercise(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    workout_exercises = db.relationship('WorkoutExercise', backref='exercise', lazy=True)

class WorkoutPlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    exercises = db.relationship('Exercise', secondary='workout_plan_exercise')
    workouts = db.relationship('Workout', backref='workout_plan', lazy=True)

class WorkoutPlanExercise(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    workout_plan_id = db.Column(db.Integer, db.ForeignKey('workout_plan.id'), nullable=False)
    exercise_id = db.Column(db.Integer, db.ForeignKey('exercise.id'), nullable=False)

class Workout(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    workout_plan_id = db.Column(db.Integer, db.ForeignKey('workout_plan.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    exercises = db.relationship('WorkoutExercise', backref='workout', lazy=True)

class WorkoutExercise(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    workout_id = db.Column(db.Integer, db.ForeignKey('workout.id'), nullable=False)
    exercise_id = db.Column(db.Integer, db.ForeignKey('exercise.id'), nullable=False)
    sets = db.relationship('ExerciseSet', backref='workout_exercise', lazy=True)

class ExerciseSet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    workout_exercise_id = db.Column(db.Integer, db.ForeignKey('workout_exercise.id'), nullable=False)
    reps = db.Column(db.Integer, nullable=False)
    weight = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routen für User Management
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if User.query.filter_by(username=username).first():
            flash('Username bereits vergeben')
            return redirect(url_for('register'))
        
        user = User(username=username, password_hash=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        
        flash('Ungültige Anmeldedaten')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html')

# Routen für Übungen
@app.route('/exercises', methods=['GET', 'POST'])
@login_required
def exercises():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        exercise = Exercise(name=name, description=description)
        db.session.add(exercise)
        db.session.commit()
        return redirect(url_for('exercises'))
    
    exercises = Exercise.query.all()
    return render_template('exercises.html', exercises=exercises)

# Routen für Trainingspläne
@app.route('/workout_plans', methods=['GET', 'POST'])
@login_required
def workout_plans():
    if request.method == 'POST':
        name = request.form.get('name')
        plan = WorkoutPlan(name=name, user_id=current_user.id)
        db.session.add(plan)
        db.session.commit()
        return redirect(url_for('workout_plans'))
    
    plans = WorkoutPlan.query.filter_by(user_id=current_user.id).all()
    return render_template('workout_plans.html', plans=plans)

@app.route('/workout_plan/<int:plan_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_workout_plan(plan_id):
    plan = WorkoutPlan.query.get_or_404(plan_id)
    if plan.user_id != current_user.id:
        flash('Zugriff verweigert')
        return redirect(url_for('workout_plans'))
    
    if request.method == 'POST':
        exercise_id = request.form.get('exercise_id')
        if exercise_id:
            exercise = Exercise.query.get(exercise_id)
            if exercise and exercise not in plan.exercises:
                plan.exercises.append(exercise)
                db.session.commit()
                flash('Übung hinzugefügt')
        return redirect(url_for('edit_workout_plan', plan_id=plan.id))
    
    available_exercises = Exercise.query.all()
    return render_template('edit_workout_plan.html', plan=plan, exercises=available_exercises)

@app.route('/workout_plan/<int:plan_id>/remove_exercise/<int:exercise_id>')
@login_required
def remove_exercise_from_plan(plan_id, exercise_id):
    plan = WorkoutPlan.query.get_or_404(plan_id)
    if plan.user_id != current_user.id:
        flash('Zugriff verweigert')
        return redirect(url_for('workout_plans'))
    
    exercise = Exercise.query.get_or_404(exercise_id)
    if exercise in plan.exercises:
        plan.exercises.remove(exercise)
        db.session.commit()
        flash('Übung entfernt')
    
    return redirect(url_for('edit_workout_plan', plan_id=plan.id))

@app.route('/start_workout/<int:plan_id>', methods=['GET', 'POST'])
@login_required
def start_workout(plan_id):
    plan = WorkoutPlan.query.get_or_404(plan_id)
    if plan.user_id != current_user.id:
        flash('Zugriff verweigert')
        return redirect(url_for('workout_plans'))
    
    if request.method == 'POST':
        workout = Workout(
            date=datetime.now(),
            workout_plan_id=plan.id,
            user_id=current_user.id
        )
        db.session.add(workout)
        
        # Erstelle WorkoutExercise-Einträge für jede Übung im Plan
        for exercise in plan.exercises:
            workout_exercise = WorkoutExercise(
                workout=workout,
                exercise_id=exercise.id
            )
            db.session.add(workout_exercise)
        
        db.session.commit()
        return redirect(url_for('execute_workout', workout_id=workout.id))
    
    return render_template('start_workout.html', plan=plan)

def get_exercise_history(exercise_id, user_id, limit=3):
    # Finde die letzten 3 Workouts mit dieser Übung
    workout_exercises = WorkoutExercise.query.join(Workout).filter(
        WorkoutExercise.exercise_id == exercise_id,
        Workout.user_id == user_id
    ).order_by(Workout.date.desc()).limit(limit).all()
    return workout_exercises

@app.route('/execute_workout/<int:workout_id>', methods=['GET', 'POST'])
@login_required
def execute_workout(workout_id):
    workout = Workout.query.get_or_404(workout_id)
    if workout.user_id != current_user.id:
        flash('Zugriff verweigert')
        return redirect(url_for('workout_plans'))
    
    if request.method == 'POST':
        if 'add_exercise' in request.form:
            exercise_id = request.form.get('exercise_id')
            if exercise_id:
                workout_exercise = WorkoutExercise(
                    workout=workout,
                    exercise_id=exercise_id
                )
                db.session.add(workout_exercise)
                db.session.commit()
                return redirect(url_for('execute_workout', workout_id=workout_id))
        
        elif 'remove_exercise' in request.form:
            exercise_id = request.form.get('workout_exercise_id')
            if exercise_id:
                workout_exercise = WorkoutExercise.query.get_or_404(exercise_id)
                if not workout_exercise.sets:  # Nur löschen wenn keine Sets vorhanden
                    db.session.delete(workout_exercise)
                    db.session.commit()
                return redirect(url_for('execute_workout', workout_id=workout_id))
        
        else:
            workout_exercise_id = request.form.get('workout_exercise_id')
            reps = request.form.get('reps')
            weight = request.form.get('weight')
            
            if workout_exercise_id and reps and weight:
                exercise_set = ExerciseSet(
                    workout_exercise_id=workout_exercise_id,
                    reps=reps,
                    weight=weight
                )
                db.session.add(exercise_set)
                db.session.commit()
                
                if 'finish_exercise' in request.form:
                    return redirect(url_for('execute_workout', workout_id=workout_id))
                return redirect(url_for('execute_workout', workout_id=workout_id, 
                                      active_exercise_id=workout_exercise_id))
    
    active_exercise_id = request.args.get('active_exercise_id')
    if active_exercise_id:
        active_exercise = WorkoutExercise.query.get(active_exercise_id)
    else:
        active_exercise = workout.exercises[0] if workout.exercises else None
    
    # Hole alle verfügbaren Übungen für das Hinzufügen
    available_exercises = Exercise.query.all()
    
    # Hole die Historie für die aktuelle Übung
    exercise_history = []
    if active_exercise:
        exercise_history = get_exercise_history(active_exercise.exercise_id, current_user.id)
    
    return render_template('execute_workout.html', 
                         workout=workout,
                         active_exercise=active_exercise,
                         available_exercises=available_exercises,
                         exercise_history=exercise_history)

# Route für das Dashboard
@app.route('/')
@app.route('/dashboard')
@login_required
def dashboard():
    # Hole die letzten 5 Workouts für die Dashboard-Anzeige
    recent_workouts = Workout.query.filter_by(user_id=current_user.id)\
        .order_by(Workout.date.desc())\
        .limit(5)\
        .all()
    return render_template('dashboard.html', workouts=recent_workouts)

@app.route('/workouts')
@login_required
def workout_history():
    # Hole alle Workouts des Benutzers
    workouts = Workout.query.filter_by(user_id=current_user.id)\
        .order_by(Workout.date.desc())\
        .all()
    return render_template('workout_history.html', workouts=workouts)

@app.route('/workout/<int:workout_id>')
@login_required
def workout_detail(workout_id):
    workout = Workout.query.get_or_404(workout_id)
    if workout.user_id != current_user.id:
        flash('Zugriff verweigert')
        return redirect(url_for('dashboard'))
    return render_template('workout_detail.html', workout=workout)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Ensure all models are registered with SQLAlchemy
        from app import User, Exercise, WorkoutPlan, WorkoutPlanExercise, Workout, WorkoutExercise, ExerciseSet
    app.run(debug=True, port=5001)
