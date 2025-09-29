# from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from extensions import db
from werkzeug.security import generate_password_hash, check_password_hash




# db = SQLAlchemy()

# UserType Enum for role-based access
from enum import Enum
class UserType(Enum):
    ADMIN = 'admin'
    STUDENT = 'student'
    HR = 'hr'

class User(db.Model, UserMixin):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    user_type = db.Column(db.Enum(UserType), nullable=False)
    student_profile = db.relationship('Student', backref='user', uselist=False)
    hr_profile = db.relationship('HR', backref='user', uselist=False)


    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password) 


    def __repr__(self):
        return f'<User {self.email} ({self.user_type.value})>'

    def is_admin(self):
        return self.user_type == UserType.ADMIN
    def is_student(self):
        return self.user_type == UserType.STUDENT
    def is_hr(self):
        return self.user_type == UserType.HR

class Student(db.Model, UserMixin):
    __tablename__ = 'student'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20))
    resume = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    interviews = db.relationship('Interview', backref='student', lazy=True, cascade="all, delete-orphan")
    qa_pairs = db.relationship('QuestionAnswer', backref='student', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Student {self.name}>'

class HR(db.Model, UserMixin):
    __tablename__ = 'hr'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20))
    company_name = db.Column(db.String(100))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    interviews = db.relationship('Interview', backref='hr', lazy=True)

    def __repr__(self):
        return f'<HR {self.email}>'

class Interview(db.Model):
    __tablename__ = 'interview'
    id = db.Column(db.Integer, primary_key=True)
    link_id = db.Column(db.String(36), unique=True, nullable=False)
    type = db.Column(db.String(50))
    job_title = db.Column(db.String(100))  # New: Job Position/Title
    company_name = db.Column(db.String(100))  # New: Company Name
    job_desc = db.Column(db.Text)
    custom_questions = db.Column(db.Text)
    created_at = db.Column(db.DateTime)
    used = db.Column(db.Boolean, default=False)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'))
    hr_id = db.Column(db.Integer, db.ForeignKey('hr.id'))
    qa_pairs = db.relationship('QuestionAnswer', backref='interview', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Interview {self.link_id} | {self.job_title} at {self.company_name}>'


class QuestionAnswer(db.Model):
    __tablename__ = 'question_answer'
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    answer_text = db.Column(db.Text)
    llm_answer_text = db.Column(db.Text)
    score = db.Column(db.Float)
    interview_id = db.Column(db.Integer, db.ForeignKey('interview.id'))
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'))

    def __repr__(self):
        return f'<QA Q:{self.text[:30]}... A:{(self.answer_text or "")[:30]}...>'
