from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, abort
from models import db, User, UserType, Student
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.utils import secure_filename
import os, logging
import pdfplumber, docx
from llm_model import model, evaluate_answer
from email_utils import send_email


student_bp = Blueprint('student', __name__)

# Setup Flask-Login
login_manager = LoginManager()
login_manager.login_view = 'student'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@student_bp.route('/student')
def student():
    return render_template('student/student_login.html')



# Student Registration
@student_bp.route('/student/register', methods=['GET', 'POST'])
def student_register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        if not email:
            flash('Email is required.')
        if not password:
            flash('Password is requried.')
        elif User.query.filter_by(email=email).first():
            flash('Email already registered.')
        else:
            user = User(email=email, user_type=UserType.STUDENT)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            return redirect(url_for('student.login'))
    return render_template('student/register.html')

# Student Login
@student_bp.route('/student/login', methods=['GET', 'POST'])
def login():
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email, user_type=UserType.STUDENT).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('student.student_home'))
        else:
            flash('Invalid email or not registered.')
    return render_template('student/login.html')



# Logout
@student_bp.route('/student/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('student.login'))

# Student Dashboard
@student_bp.route('/student/student_home')
@login_required
def student_home():
    if not current_user.is_student():
        abort(403)
    return render_template('base/student_home.html')



# Resume Upload + Question Generation
@student_bp.route('/student/interview', methods=['GET', 'POST'])
@login_required
def student_interview():
    if not current_user.is_student():
        abort(403)

    if request.method == 'POST':
        num_questions = int(request.form.get('num_questions', 5))
        print(f'Requested {num_questions} questions.')
        file = request.files.get('resume_file')

        if not file:
            flash('Resume file required.', 'error')
            return render_template('student/resume_interview.html')

        filename = secure_filename(file.filename)
        ext = os.path.splitext(filename)[1].lower()
        temp_dir = os.path.join('temp_resumes')
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = os.path.join(temp_dir, filename)
        file.save(temp_path)

        # Extract resume text
        resume_text = ''
        try:
            if ext == '.pdf':
                with pdfplumber.open(temp_path) as pdf:
                    resume_text = "\n".join([page.extract_text() or '' for page in pdf.pages])
            elif ext in ['.docx', '.doc']:
                doc = docx.Document(temp_path)
                resume_text = "\n".join([para.text for para in doc.paragraphs])
            else:
                flash('Unsupported file type.', 'error')
                os.remove(temp_path)
                return render_template('student/resume_interview.html')
        except Exception as e:
            logging.error(f'Resume parse error: {e}')
            flash('Error reading resume: {e}')
        finally:
            os.remove(temp_path)

        # Generate Questions using LLM
        prompt = f"""
        Generate exactly {num_questions} technical interview questions based on this resume text:
        {resume_text}
        Return only the questions in a numbered list.
        """
        try:
            response = model.generate_content(prompt)
            questions = []
            for line in response.text.strip().splitlines():
                if line.strip() and (line[0].isdigit() and (line[1] in ['.', ')'])):
                    questions.append(line.split(' ', 1)[-1].strip())
            while len(questions) < num_questions:
                questions.append("Technical question based on resume.")
            print(f'Generated Questions: {questions}')
            session['questions'] = questions
            session['answers'] = []
            session['current_index'] = 0
            session['job_description'] = resume_text[:300]
            return redirect(url_for('student.meeting'))
        except Exception as e:
            logging.error(f'Question generation error: {e}')
            flash(f'Error generating questions: {e}')

    return render_template('student/resume_interview.html')

# Interview Meeting Page
@student_bp.route('/student/meeting')
@login_required
def meeting():
    if not current_user.is_student():
        abort(403)
    if 'questions' not in session:
        return redirect(url_for('student.student_home'))
    return render_template('student/student_meeting.html', is_hr_session=False, job_description=current_user.email)

# Fetch Next Question (AJAX)
@student_bp.route('/student/get_next_question', methods=['POST'])
@login_required
def get_next_question():
    if not current_user.is_student():
        abort(403)
    index = session.get('current_index', 0)
    questions = session.get('questions', [])
    if index >= len(questions):
        return jsonify({"status": "complete"})
    
    response = jsonify({
        "status": "question",
        "question": questions[index],
        "index": index,
        "total": len(questions)
    }) 
    session['current_index'] = index + 1
    return response

# Submit User Answer (AJAX)
@student_bp.route('/student/submit_answer', methods=['POST'])
@login_required
def submit_answer():
    if not current_user.is_student():
        abort(403)
    data = request.json
    answer = data.get("answer", "")
    index = data.get("index", 0)
    answers = session.get("answers", [])
    if index < len(answers):
        answers[index] = answer
        
    else:
        answers.append(answer)
    session["answers"] = answers
    session["current_index"] = index + 1
    
    return jsonify({"status": "complete"})



# Final Interview Report
@student_bp.route('/student/final_report', methods=['POST'])
@login_required
def final_report():
    if not current_user.is_student():
        abort(403)

    questions = session.get('questions', [])
    answers = session.get('answers', [])

    if not questions or not answers:
        return jsonify({"status": "error", "message": "No completed interview found."})

    report_lines = ""
    total_score = 0

    for i, (question, answer) in enumerate(zip(questions, answers)):
        ideal_answer, score = evaluate_answer(question, answer)
        total_score += score

        report_lines += f"""
        <tr>
            <td style="padding:10px; border:1px solid #ddd;">{i+1}</td>
            <td style="padding:10px; border:1px solid #ddd;">{question}</td>
            <td style="padding:10px; border:1px solid #ddd;">{answer}</td>
            <td style="padding:10px; border:1px solid #ddd;">{ideal_answer}</td>
            <td style="padding:10px; border:1px solid #ddd; text-align:center;">{score}/100</td>
        </tr>
        """

    avg_score = total_score / len(questions) if questions else 0

    final_report_html = f"""
<html>
<body style="font-family: 'Lato', sans-serif; background-color: #eef5f9; padding: 20px; line-height: 1.6;">
    <div style="max-width: 780px; margin: auto; background: #ffffff; padding: 30px; border-radius: 15px; box-shadow: 0 8px 25px rgba(0,0,0,0.15);">
        <div style="background: linear-gradient(to right, #007bff, #0056b3); padding: 25px; border-radius: 10px 10px 0 0; text-align: center; color: #ffffff; margin: -30px -30px 30px -30px;">
            <h1 style="margin: 0; font-size: 2.2em; font-weight: 700;">AI Interview Results</h1>
        </div>

        <p style="font-size: 17px; color: #333; margin-bottom: 25px;">Dear <strong style="color: #007bff;">{current_user.email}</strong>,</p>
        <p style="font-size: 16px; color: #555; margin-bottom: 30px;">Please find your detailed AI Interview Evaluation Report below:</p>
        
        <table style="width: 100%; border-collapse: collapse; margin-top: 25px;">
            <thead>
                <tr style="background-color: #f2f2f2; color: #333;">
                    <th style="padding: 12px 15px; border: 1px solid #ddd; text-align: left; font-weight: 600;">#</th>
                    <th style="padding: 12px 15px; border: 1px solid #ddd; text-align: left; font-weight: 600;">Question</th>
                    <th style="padding: 12px 15px; border: 1px solid #ddd; text-align: left; font-weight: 600;">Your Answer</th>
                    <th style="padding: 12px 15px; border: 1px solid #ddd; text-align: left; font-weight: 600;">Ideal Answer</th>
                    <th style="padding: 12px 15px; border: 1px solid #ddd; text-align: left; font-weight: 600;">Score</th>
                </tr>
            </thead>
            <tbody>
                {report_lines}
            </tbody>
        </table>

        <div style="background-color: #e8f0fe; padding: 20px; border-radius: 8px; margin-top: 40px; text-align: center;">
            <h3 style="color: #0056b3; margin-bottom: 10px;">Your Overall Performance:</h3>
            <span style="font-size: 2.5em; font-weight: 800; color: #007bff;">{avg_score:.2f}<small style="font-size: 0.6em;">/100</small></span>
        </div>

        <p style="font-size: 15px; color: #666; margin-top: 40px; text-align: center;">Thank you for taking the time to complete your interview.</p>
        <p style="font-size: 15px; color: #666; text-align: center;">Sincerely,<br><span style="font-weight: 600; color: #007bff;">Naventra AI HR Team</span></p>
    </div>
</body>
</html>
    """

    try:
        send_email(current_user.email, "Your AI Interview Report", final_report_html)
        return jsonify({"status": "success", "message": "Report generated and emailed successfully."})
    except Exception as e:
        logging.error(f"Failed to send report email: {e}")
        return jsonify({"status": "error", "message": "Failed to send report email."})
