from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from .models import User, Exercise, WorkoutPlan, WorkoutPlanExercise, Workout, WorkoutExercise, ExerciseSet
from . import db

main = Blueprint('main', __name__)

@main.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if User.query.filter_by(username=username).first():
            flash('Username bereits vergeben')
            return redirect(url_for('main.register'))
        
        user = User(username=username, password_hash=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()
        return redirect(url_for('main.login'))
    
    return render_template('register.html')

@main.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('main.dashboard'))
        
        flash('Invalid username or password')
    return render_template('login.html')

@main.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.login'))

@main.route('/profile')
@login_required
def profile():
    # Hole nur abgeschlossene Workouts
    completed_workouts = Workout.query.filter_by(
        user_id=current_user.id,
        completed=True
    ).all()
    
    # Hole alle Trainingspläne des Benutzers
    workout_plans = WorkoutPlan.query.filter_by(
        user_id=current_user.id
    ).all()
    
    return render_template(
        'profile.html',
        workouts=completed_workouts,
        plans=workout_plans
    )

@main.route('/exercises', methods=['GET', 'POST'])
@login_required
def exercises():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        exercise = Exercise(name=name, description=description)
        db.session.add(exercise)
        db.session.commit()
        return redirect(url_for('main.exercises'))
    
    exercises = Exercise.query.all()
    return render_template('exercises.html', exercises=exercises)

@main.route('/workout-plans', methods=['GET', 'POST'])
@login_required
def workout_plans():
    if request.method == 'POST':
        name = request.form.get('name')
        plan = WorkoutPlan(name=name, user_id=current_user.id)
        db.session.add(plan)
        db.session.commit()
        return redirect(url_for('main.workout_plans'))
    
    plans = WorkoutPlan.query.filter_by(user_id=current_user.id).all()
    return render_template('workout_plans.html', plans=plans)

@main.route('/workout-plan/<int:plan_id>', methods=['GET', 'POST'])
@login_required
def edit_workout_plan(plan_id):
    plan = WorkoutPlan.query.get_or_404(plan_id)
    if request.method == 'POST':
        exercise_id = request.form.get('exercise_id')
        exercise = Exercise.query.get(exercise_id)
        if exercise and exercise not in plan.exercises:
            plan.exercises.append(exercise)
            db.session.commit()
        return redirect(url_for('main.edit_workout_plan', plan_id=plan_id))
    
    available_exercises = Exercise.query.all()
    return render_template('edit_workout_plan.html', plan=plan, exercises=available_exercises)

@main.route('/workout-plan/<int:plan_id>/remove/<int:exercise_id>')
@login_required
def remove_exercise_from_plan(plan_id, exercise_id):
    plan = WorkoutPlan.query.get_or_404(plan_id)
    exercise = Exercise.query.get_or_404(exercise_id)
    if exercise in plan.exercises:
        plan.exercises.remove(exercise)
        db.session.commit()
    return redirect(url_for('main.edit_workout_plan', plan_id=plan_id))

@main.route('/start-workout/<int:plan_id>')
@login_required
def start_workout(plan_id):
    plan = WorkoutPlan.query.get_or_404(plan_id)
    workout = Workout(workout_plan_id=plan.id, user_id=current_user.id)
    db.session.add(workout)
    
    for exercise in plan.exercises:
        workout_exercise = WorkoutExercise(workout=workout, exercise=exercise)
        db.session.add(workout_exercise)
    
    db.session.commit()
    return redirect(url_for('main.execute_workout', workout_id=workout.id))

def get_exercise_history(exercise_id, user_id, limit=3):
    return ExerciseSet.query.join(WorkoutExercise).join(Workout).filter(
        Workout.user_id == user_id,
        WorkoutExercise.exercise_id == exercise_id
    ).order_by(ExerciseSet.created_at.desc()).limit(limit).all()

@main.route('/workout/<int:workout_id>', methods=['GET', 'POST'])
@login_required
def execute_workout(workout_id):
    workout = Workout.query.get_or_404(workout_id)
    active_exercise_id = request.args.get('active_exercise_id', type=int)
    active_exercise = None
    
    if active_exercise_id:
        active_exercise = WorkoutExercise.query.filter_by(
            workout_id=workout.id,
            id=active_exercise_id
        ).first_or_404()
    
    if request.method == 'POST':
        if 'exercise_id' in request.form:
            # Neue Übung zum Workout hinzufügen
            exercise_id = int(request.form.get('exercise_id'))
            exercise = Exercise.query.get_or_404(exercise_id)
            workout_exercise = WorkoutExercise(workout=workout, exercise=exercise)
            db.session.add(workout_exercise)
            db.session.commit()
            return redirect(url_for('main.execute_workout', workout_id=workout_id))
            
        elif 'workout_exercise_id' in request.form and 'reps' in request.form and 'weight' in request.form:
            # Neues Set hinzufügen
            workout_exercise_id = int(request.form.get('workout_exercise_id'))
            workout_exercise = WorkoutExercise.query.get_or_404(workout_exercise_id)
            
            if workout_exercise.workout_id != workout.id:
                flash('Ungültige Anfrage', 'error')
                return redirect(url_for('main.execute_workout', workout_id=workout_id))
            
            reps = int(request.form.get('reps'))
            weight = float(request.form.get('weight'))
            
            exercise_set = ExerciseSet(
                workout_exercise=workout_exercise,
                reps=reps,
                weight=weight
            )
            db.session.add(exercise_set)
            db.session.commit()
            
            return redirect(url_for('main.execute_workout', 
                                  workout_id=workout_id, 
                                  active_exercise_id=workout_exercise_id))
        
        elif 'remove_exercise' in request.form:
            # Übung aus Workout entfernen
            workout_exercise_id = int(request.form.get('workout_exercise_id'))
            workout_exercise = WorkoutExercise.query.get_or_404(workout_exercise_id)
            
            if workout_exercise.workout_id != workout.id:
                flash('Ungültige Anfrage', 'error')
                return redirect(url_for('main.execute_workout', workout_id=workout_id))
            
            if not workout_exercise.sets:  # Nur löschen wenn keine Sets vorhanden
                db.session.delete(workout_exercise)
                db.session.commit()
            
            return redirect(url_for('main.execute_workout', workout_id=workout_id))
        
        elif 'remove_set' in request.form:
            # Set aus Übung entfernen
            set_id = int(request.form.get('set_id'))
            exercise_set = ExerciseSet.query.get_or_404(set_id)
            workout_exercise = exercise_set.workout_exercise
            
            if workout_exercise.workout_id != workout.id:
                flash('Ungültige Anfrage', 'error')
                return redirect(url_for('main.execute_workout', workout_id=workout_id))
            
            db.session.delete(exercise_set)
            db.session.commit()
            
            return redirect(url_for('main.execute_workout', 
                                  workout_id=workout_id,
                                  active_exercise_id=workout_exercise.id))
        
        elif 'finish_workout' in request.form:
            # Workout beenden
            if workout.exercises:
                workout.completed = True
                db.session.commit()
                flash('Workout erfolgreich beendet!', 'success')
                return redirect(url_for('main.workout_plans'))
    
    # Verfügbare Übungen für das Modal
    available_exercises = Exercise.query.filter(
        ~Exercise.workout_exercises.any(WorkoutExercise.workout_id == workout.id)
    ).all()
    
    # Übungshistorie
    exercise_history = {}
    if active_exercise:
        exercise_history = WorkoutExercise.query.join(Workout).filter(
            WorkoutExercise.exercise_id == active_exercise.exercise_id,
            Workout.user_id == current_user.id,
            Workout.id != workout.id,
            Workout.completed == True
        ).order_by(Workout.date.desc()).limit(5).all()
    
    return render_template(
        'execute_workout.html',
        workout=workout,
        active_exercise=active_exercise,
        available_exercises=available_exercises,
        exercise_history=exercise_history
    )

@main.route('/')
@login_required
def dashboard():
    workouts = Workout.query.filter_by(user_id=current_user.id, completed=True).order_by(Workout.date.desc()).limit(5).all()
    workout_plans = WorkoutPlan.query.filter_by(user_id=current_user.id).all()
    return render_template('dashboard.html', workouts=workouts, workout_plans=workout_plans)

@main.route('/workout-history')
@login_required
def workout_history():
    workouts = Workout.query.filter_by(user_id=current_user.id).order_by(Workout.date.desc()).all()
    return render_template('workout_history.html', workouts=workouts)

@main.route('/workout/<int:workout_id>')
@login_required
def workout_detail(workout_id):
    workout = Workout.query.get_or_404(workout_id)
    if workout.user_id != current_user.id:
        return redirect(url_for('main.dashboard'))
    return render_template('workout_detail.html', workout=workout)
