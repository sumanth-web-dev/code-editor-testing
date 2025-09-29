from flask import Flask, redirect, url_for, request, render_template, flash
from dotenv import load_dotenv
import os, secrets
from extensions import db, scheduler
from flask_login import LoginManager
from flask_migrate import Migrate
from student import student_bp
from hr import hr_bp

# Load environment variables
load_dotenv()

def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///interview_app.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.secret_key = os.getenv("FLASK_SECRET_KEY", secrets.token_hex(16))

    # Initialize extensions
    db.init_app(app)
    scheduler.init_app(app)

    # Blueprints
    app.register_blueprint(student_bp)
    app.register_blueprint(hr_bp)

    # Login manager
    login_manager = LoginManager()
    login_manager.init_app(app)

    from models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    @login_manager.unauthorized_handler
    def unauthorized_callback():
        if '/student' in request.path:
            return redirect(url_for('student.login'))
        elif '/hr' in request.path:
            return redirect(url_for('hr.hr_login'))
        else:
            return redirect(url_for('student.login'))

    # Migrate
    Migrate(app, db)

    # Scheduler jobs
    from scheduler import delete_old_interviews

    # ✅ Wrapper job that uses app context
    def run_delete_old_interviews_job():
        with app.app_context():
            delete_old_interviews()

    # ✅ Add job
    scheduler.add_job(
        id='DemoJob',
        func=run_delete_old_interviews_job,
        trigger='interval',
        days=180  # Run every day
    )

    scheduler.start()

    return app

app = create_app()

@app.route('/')
def index():
    return render_template('hr_student.html')

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=5000, debug=True)
