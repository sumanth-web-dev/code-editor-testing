from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, abort
import uuid
import datetime
from models import db, User, UserType, HR, Interview, QuestionAnswer, Student
from llm_model import model, evaluate_answer
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from sqlalchemy.orm import joinedload
from email_utils import send_confirmation_email

hr_bp = Blueprint('hr', __name__)
login_manager = LoginManager()
login_manager.login_view = 'hr'


def get_or_create_hr(current_user):
    """Helper function to get or create HR record for current user"""
    hr = HR.query.filter_by(email=current_user.email).first()
    if not hr:
        # Create HR record if it doesn't exist
        hr = HR(email=current_user.email, user_id=current_user.id)
        db.session.add(hr)
        db.session.commit()
        print(f"Created missing HR record for {current_user.email}")
    return hr



# HR registration
@hr_bp.route('/hr/register', methods=['GET', 'POST'])
def hr_register():
    msg = ''
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        if not email:
            flash('Email is required.')
            msg = 'Email is required.'
        if not password:
            msg = "Password is required."
            flash("Password is required.")
        elif User.query.filter_by(email=email).first():
            msg = 'Email already registered.'
            flash('Email already registered.')
        else:
            # Create User record
            user = User(email=email, user_type=UserType.HR)
            user.set_password(password)
            db.session.add(user)
            db.session.flush()  # Get user.id
            
            # Create corresponding HR record
            hr = HR(email=email, user_id=user.id)
            db.session.add(hr)
            db.session.commit()
            return redirect(url_for('hr.hr_login'))
    return render_template('hr/register.html', msg=msg)

# HR login
@hr_bp.route('/hr/login', methods=['GET', 'POST'])
def hr_login():
    msg = ''
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email, user_type=UserType.HR).first()
        if user and user.check_password(password):
            login_user(user)
            flash('Login successful!', 'success')
            return redirect(url_for('hr.hr_home'))
        else:   
            msg = 'Invalid email or not registered.'
    return render_template('hr/login.html', msg=msg)

@hr_bp.route('/hr/logout')
@login_required
def hr_logout():
    logout_user()
    return redirect(url_for('hr.hr_login'))


@hr_bp.route('/hr_login')
def hr():
    return render_template('hr/hr_login.html')


@hr_bp.route('/hr')
@login_required
def hr_home():
    if not current_user.is_hr():
        abort(403)
    return render_template('base/hr.html')

# @hr_bp.route('/hr/home')
# @login_required
# def hr_home():
#     if not current_user.is_hr():
#         abort(403)
#     return render_template('hr/hr_home.html')

# Dashboard — create interview
@hr_bp.route('/hr/hr_create_Interview', methods=['GET', 'POST'])
@login_required
def hr_dashboard():
    if not current_user.is_hr():
        abort(403)

    if request.method == 'POST':
        interview_type = request.form.get('interview_type')
        job_desc = request.form.get('job_desc')
        custom_questions = request.form.get('custom_questions')

        job_title = request.form.get('job_title')
        company_name = request.form.get('company_name')
        link_id = str(uuid.uuid4())

        # Get or create HR record
        hr = get_or_create_hr(current_user)

        interview = Interview(
            link_id=link_id,
            type=interview_type,
            job_desc=job_desc,
            custom_questions=custom_questions,
            job_title=job_title,
            company_name=company_name,
            hr_id=hr.id,
            created_at=datetime.datetime.utcnow(),
            used=False
        )
        db.session.add(interview)
        db.session.commit()

        # Add custom questions
        if custom_questions:
            for q_text in [q.strip() for q in custom_questions.split(',') if q.strip()]:
                qa = QuestionAnswer(text=q_text, interview_id=interview.id)
                db.session.add(qa)
            db.session.commit()

        link = url_for('hr.start_interview', link_id=link_id, _external=True)
        flash(f'Interview created successfully! Share this link with candidates: {link}', 'success')
        return render_template('hr/hr_dashboard.html')

    return render_template('hr/hr_dashboard.html')


# AI question generation
def generate_ai_questions(job_desc, num=5):
    prompt = f"""
    Generate exactly {num} technical interview questions based on this job description:
    {job_desc}

    Return only the questions in a numbered list format without any extra text.
    Example:
    1. What is object-oriented programming?
    2. Explain the concept of inheritance.
    """
    try:
        response = model.generate_content(prompt)
        return [line.split(' ', 1)[-1].strip() for line in response.text.strip().splitlines() if line]
    except Exception as e:
        print("LLM error:", str(e))
        return ["Error generating questions."]

# Start interview
@hr_bp.route('/hr/interview/<link_id>', methods=['GET', 'POST'])
def start_interview(link_id):
    interview = Interview.query.filter_by(link_id=link_id).first_or_404()

    if request.method == 'POST':
        name, email, phone = request.form.get('name'), request.form.get('email'), request.form.get('phone')
        if not all([name, email, phone]):
            flash('All fields required.', 'warning')
            return render_template('hr/student_form.html', link_id=link_id)

        existing_student = Student.query.filter_by(email=email).first()

        if existing_student:
            # Check if student has already attended this interview (by checking QuestionAnswer)
            attended = QuestionAnswer.query.filter_by(interview_id=interview.id, student_id=existing_student.id).first()
            if attended:
                flash('This student has already attended this interview.', 'error')
                return render_template('hr/student_form.html', link_id=link_id)

            student = existing_student  # reuse student
        else:
            # Create new student record
            student = Student(name=name, email=email, phone=phone)
            db.session.add(student)
            db.session.flush()  # get student.id

        interview.student_id = student.id
        db.session.commit()

        # Prepare questions as before
        questions = []
        if interview.type in ['jd', 'both']:
            questions += generate_ai_questions(interview.job_desc, num=interview.num_questions)
        if interview.type in ['custom', 'both']:
            questions += [qa.strip() for qa in interview.custom_questions.split(',') if qa.strip()]

        qa_ids = []
        for q_text in questions:
            qa = QuestionAnswer(text=q_text, interview_id=interview.id, student_id=student.id)
            db.session.add(qa)
            db.session.flush()
            qa_ids.append(qa.id)

        db.session.commit()

        session.clear()
        session['qa_ids'] = qa_ids
        session['current_index'] = 0
        session['link_id'] = link_id

        return redirect(url_for('hr.hr_meeting', link_id=link_id))

    return render_template('hr/student_form.html', link_id=link_id)


# Meeting page
@hr_bp.route('/hr/meeting/<link_id>', methods=['GET'])
def hr_meeting(link_id):
    inteview = Interview.query.filter_by(link_id=link_id).first_or_404()
    return render_template('hr/meeting.html', interview = inteview)

# Next question API
@hr_bp.route('/hr/get_next_question', methods=['POST'])
def get_next_question():
    qa_ids = session.get('qa_ids')
    index = session.get('current_index', 0)

    # Check if session data exists
    if not qa_ids:
        return jsonify({"status": "error", "message": "No questions found in session."}), 400

    # Check if interview is complete
    if index >= len(qa_ids):
        return jsonify({"status": "complete"})

    # Fetch question by id
    qa = QuestionAnswer.query.get(qa_ids[index])

    if not qa:
        return jsonify({"status": "error", "message": f"Question ID {qa_ids[index]} not found."}), 404

    # Increment index for next call
    # print(f"get_next_question: Current index {index}, Total questions {len(qa_ids)}")

    response = {
        "status": "question",
        "question": qa.text,
        "index": index,
        "total": len(qa_ids)
    }
    session['current_index'] = index + 1  # Update index in session


    # Return the question
    return jsonify(response)


# Submit answer
@hr_bp.route('/hr/submit_answer', methods=['POST'])
def submit_answer():
    data = request.get_json()
    qa_ids = session.get('qa_ids', [])
    index = data.get('index')

    if index >= len(qa_ids):
        return jsonify({'status': 'error', 'message': 'Invalid question index.'}), 400

    qa = QuestionAnswer.query.get(qa_ids[index])
    qa.answer_text = data.get('answer')
    db.session.commit()

    # If this was the last answer — trigger evaluation
    # print(f"submit_answer: Current index {index}, Total questions {len(qa_ids)}")
    if index == len(qa_ids) - 1:
        interview = Interview.query.filter_by(link_id=session.get('link_id')).first()
        interview.used = True
        print(f"submit_answer: Evaluating answers for interview {qa.interview_id} and student {qa.student_id}")
        evaluate_all_answers(qa.interview_id, qa.student_id)
        student = Student.query.get(qa.student_id)

        # Send confirmation email
        try:
            send_confirmation_email(student.email, student.name, interview)
        except Exception as e:
            print(f"Failed to send confirmation email: {e}")

    return jsonify({'status': 'success'})


# Analytics
@hr_bp.route('/hr/analytics')
@login_required
def hr_analytics():
    if not current_user.is_hr():
        abort(403)

    # Get or create HR record
    hr = get_or_create_hr(current_user)

    total_interviews = Interview.query.count()
    completed_interviews = Interview.query.filter_by(hr_id=hr.id).count()
    pending_interviews = total_interviews - completed_interviews
    unique_hrs = HR.query.count()

    # Collect student interview details
    interviews = Interview.query.filter_by(hr_id=hr.id).all()

    student_interviews = []
    for interview in interviews:
        student = interview.student
        if not student:
            continue
        qa_pairs = []
        for qa in interview.qa_pairs:
            qa_pairs.append({
                'question': qa.text,
                'answer': qa.answer_text or '—',
                'llm_answer': qa.llm_answer_text or '—',
                'score': qa.score if qa.score is not None else '—'
            })

        student_interviews.append({
            'student_name': student.name,
            'student_email': student.email,
            'student_phone': student.phone,
            'qa_pairs': qa_pairs
        })

    return render_template(
        'hr/hr_analytics.html',
        total_interviews=total_interviews,
        completed_interviews=completed_interviews,
        pending_interviews=pending_interviews,
        unique_hrs=unique_hrs,
        student_interviews=student_interviews
    )


# Student statistics
@hr_bp.route('/hr/student_stats')
@login_required
def student_stats():
    if not current_user.is_hr():
        abort(403)

    total_students = Student.query.count()
    total_interviews = Interview.query.count()

    return render_template('hr/student_stats.html',
                           total_students=total_students,
                           total_interviews=total_interviews)

# Score graph
@hr_bp.route('/hr/score_graph')
@login_required
def score_graph():
    if not current_user.is_hr():
        abort(403)

    # Get or create HR record
    hr = get_or_create_hr(current_user)

    # Fetch scores from this HR's interviews
    interviews = Interview.query.filter_by(hr_id=hr.id).all()

    # Collect all scores
    all_scores = []
    for interview in interviews:
        for qa in interview.qa_pairs:
            if qa.score is not None:
                all_scores.append(qa.score)

    # Count frequency of each score (0–10 range)
    from collections import Counter
    score_counts = Counter(all_scores)

    # Prepare data: for scores 0–10
    labels = list(range(0, 11))
    counts = [score_counts.get(score, 0) for score in labels]

    return render_template('hr/score_graph.html', labels=labels, counts=counts)





# Export CSV
@hr_bp.route('/hr/export')
@login_required
def hr_export():
    if not current_user.is_hr():
        abort(403)

    import csv
    from io import StringIO

    si = StringIO()
    cw = csv.writer(si)

    # CSV headers
    cw.writerow([
        'Interview ID',
        'Company Name',
        'Job Title',
        'Student Name',
        'Student Email',
        'Student Phone',
        'No. of Questions',
        'Question',
        'Candidate Answer',
        'LLM Answer',
        'Score'
    ])

    # Get or create HR record
    hr = get_or_create_hr(current_user)

    # Fetch Interviews for this HR
    interviews = Interview.query.filter_by(hr_id=hr.id).all()

    if not interviews:
        flash("No interviews found for export.", "info")
        return redirect(url_for('hr.hr_analytics'))

    for interview in interviews:
        company_name = interview.company_name or 'N/A'
        job_title = interview.job_title or 'N/A'

        # Find unique students in this interview
        student_ids = {qa.student_id for qa in interview.qa_pairs if qa.student_id}

        for student_id in student_ids:
            student = Student.query.get(student_id)
            if not student:
                continue

            # Total no. of questions answered by this student in this interview
            student_qas = [qa for qa in interview.qa_pairs if qa.student_id == student_id]
            num_questions = len(student_qas)

            for qa in student_qas:
                cw.writerow([
                    interview.id,
                    company_name,
                    job_title,
                    student.name,
                    student.email,
                    student.phone or '',
                    num_questions,
                    qa.text,
                    qa.answer_text or '',
                    qa.llm_answer_text or '',
                    qa.score if qa.score is not None else ''
                ])

    output = si.getvalue()

    return (output, 200, {
        'Content-Type': 'text/csv',
        'Content-Disposition': 'attachment; filename="interview_export.csv"'
    })



# Summary view
@hr_bp.route('/hr/summary')
@login_required
def hr_summary():
    # Authorization - HR only
    if not current_user.is_hr():
        return redirect(url_for('main_bp.home'))
    
    # Get HR profile
    hr = HR.query.filter_by(user_id=current_user.id).first()
    if not hr:
        flash("HR profile not found.", "warning")
        return render_template('hr/hr_summary.html', interviews=[])

    # Fetch interviews with eager loading
    interviews = Interview.query.options(
        joinedload(Interview.student),
        joinedload(Interview.qa_pairs)
    ).filter_by(hr_id=hr.id).order_by(Interview.created_at.desc()).all()

    return render_template('hr/hr_summary.html', 
        interviews=[{
            'interview': interview,
            'q_and_a': interview.qa_pairs,
            'student': interview.student
        } for interview in interviews]
    )



# Custom 403 page
@hr_bp.app_errorhandler(403)
def forbidden(e):
    return render_template('403.html', description=getattr(e, 'description', None)), 403



# HR links page
@hr_bp.route('/hr/links')
@login_required
def hr_links():
    if not current_user.is_hr():
        abort(403)

    # Get or create HR record
    hr = get_or_create_hr(current_user)

    # Now fetch interviews associated with this HR
    interviews = Interview.query.filter_by(hr_id=hr.id).all()

    return render_template('hr/hr_link.html', interviews=interviews)



# Edit interview form
@hr_bp.route('/hr/edit_interview/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_interview(id):
    if not current_user.is_hr():
        abort(403)

    interview = Interview.query.get_or_404(id)

    if request.method == 'POST':
        interview.level = request.form.get('level')
        interview.type = request.form.get('interview_type')
        interview.num_questions = request.form.get('num_questions')
        interview.custom_questions = request.form.get('custom_questions')
        interview.job_title = request.form.get('job_title')
        interview.company_name = request.form.get('company_name')
        interview.job_desc = request.form.get('job_desc')
        db.session.commit()

        flash("Interview updated successfully!", "success")
        return redirect(url_for('hr.hr_links'))

    return render_template('hr/edit_interview.html', interview=interview)


# Delete interview
@hr_bp.route('/hr/delete_interview/<int:id>')
@login_required
def delete_interview(id):
    if not current_user.is_hr():
        abort(403)

    interview = Interview.query.get_or_404(id)
    db.session.delete(interview)
    db.session.commit()
    flash("Interview deleted successfully!", "success")
    return redirect(url_for('hr.hr_links'))


def evaluate_all_answers(interview_id, student_id):
    print(f"Evaluating answers for interview {interview_id} and student {student_id}")
    interview = Interview.query.get(interview_id)
    if not interview:
        return "Interview not found"

    for qa in interview.qa_pairs:
        if qa.student_id != student_id:
            continue

        if qa.answer_text and (qa.llm_answer_text is None or qa.score is None):
            ideal_answer, score = evaluate_answer(qa.text, qa.answer_text)
            qa.llm_answer_text = ideal_answer
            qa.score = score
            db.session.commit()  # Can be optimized with bulk commit later

    return "Evaluation completed"



@hr_bp.route('/hr/evaluate_answer', methods=['POST'])
@login_required
def evaluate_answer_api():
    if not current_user.is_hr():
        return jsonify({'error': 'Unauthorized access'}), 403

    data = request.get_json()

    question_id = data.get('question_id')
    candidate_answer = data.get('candidate_answer')

    if not question_id or candidate_answer is None:
        return jsonify({'error': 'Missing question_id or candidate_answer'}), 400

    # Fetch the QA pair from DB
    qa = QuestionAnswer.query.get(question_id)
    if not qa:
        return jsonify({'error': 'Question not found'}), 404

    # If LLM answer already exists, return it directly
    if qa.llm_answer_text and qa.score is not None:
        return jsonify({
            'message': 'LLM already evaluated this answer.',
            'ideal_answer': qa.llm_answer_text,
            'score': qa.score
        }), 200

    # Else — run evaluation via LLM
    ideal_answer, score = evaluate_answer(qa.text, candidate_answer)

    # Update DB record
    qa.answer_text = candidate_answer
    qa.llm_answer_text = ideal_answer
    qa.score = score
    db.session.commit()

    return jsonify({
        'ideal_answer': ideal_answer,
        'score': score
    }), 200


@hr_bp.route('/hr/view_interview_details')
@login_required
def view_interview_details():
    if not current_user.is_hr():
        abort(403)

    # Get or create HR record
    hr = get_or_create_hr(current_user)

    interviews = Interview.query.filter_by(hr_id=hr.id).all()

    interview_data = []
    for interview in interviews:
        student_count = len({qa.student_id for qa in interview.qa_pairs if qa.student_id})
        interview_data.append({
            'id': interview.id,
            'company': interview.company_name or 'N/A',
            'job_title': interview.job_title or 'N/A',
            'created': interview.created_at.strftime('%d-%m-%Y') if interview.created_at else 'N/A',
            'student_count': student_count
        })

    return render_template('hr/view_interview_details.html', interviews=interview_data)


@hr_bp.route('/hr/view_interview_students/<int:interview_id>')
@login_required
def view_interview_students(interview_id):
    if not current_user.is_hr():
        abort(403)

    interview = Interview.query.get_or_404(interview_id)
    if interview.hr.email != current_user.email:
        abort(403)

    qa_data = []
    for qa in interview.qa_pairs:
        student = qa.student
        if not student:
            continue
        qa_data.append({
            'student_name': student.name,
            'student_email': student.email,
            'student_phone': student.phone,
            'question': qa.text,
            'answer': qa.answer_text or '—',
            'llm_answer': qa.llm_answer_text or '—',
            'score': qa.score if qa.score is not None else '—'
        })

    return render_template('hr/view_students_of_interview.html', interview=interview, qa_data=qa_data)


@hr_bp.route('/hr/view_interview_student_summary/<int:interview_id>')
@login_required
def view_interview_student_summary(interview_id):
    if not current_user.is_hr():
        abort(403)

    interview = Interview.query.get_or_404(interview_id)
    if interview.hr.email != current_user.email:
        abort(403)

    students = Student.query.join(QuestionAnswer).filter(
        QuestionAnswer.interview_id == interview.id
    ).distinct().all()

    student_data = []
    for student in students:
        qa_pairs = QuestionAnswer.query.filter_by(interview_id=interview.id, student_id=student.id).all()
        scores = [qa.score for qa in qa_pairs if qa.score is not None]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 'N/A'
        student_data.append({
            'id': student.id,
            'name': student.name,
            'email': student.email,
            'phone': student.phone,
            'total_questions': len(qa_pairs),
            'avg_score': avg_score
        })

    return render_template('hr/view_students_of_interview_summary.html',
                           interview=interview, student_data=student_data)
@hr_bp.route('/hr/view_student_qas/<int:interview_id>/<int:student_id>')
@login_required
def view_student_qas(interview_id, student_id):
    if not current_user.is_hr():
        abort(403)

    interview = Interview.query.get_or_404(interview_id)
    if interview.hr.email != current_user.email:
        abort(403)

    student = Student.query.get_or_404(student_id)
    qa_pairs = QuestionAnswer.query.filter_by(interview_id=interview.id, student_id=student.id).all()

    return render_template('hr/view_student_qas.html', interview=interview, student=student, qa_pairs=qa_pairs)

@hr_bp.route('/hr/settings', methods=['GET', 'POST'])
@login_required
def hr_settings():
    if not current_user.is_hr():
        abort(403)

    # Get or create HR record
    hr = get_or_create_hr(current_user)

    if request.method == 'POST':
        hr.phone = request.form.get('phone')
        hr.company_name = request.form.get('company_name')
        db.session.commit()
        flash("Settings updated successfully.", "success")
        return redirect(url_for('hr.hr_settings'))

    return render_template('hr/settings.html', hr=hr)



@hr_bp.route('/hr/demo_meeting')
def demo_meeting():
    if not current_user.is_hr():
        abort(403)

    return render_template('hr/demo_meeting.html')


