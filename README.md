# Interview Management System

A full-stack Flask-based interview management system with role-based access (student, HR, admin), database-backed storage, dashboards, resume-based and HR-generated interviews, question-by-question flow, CSV export, and modern UI.

## Features

- Role-based authentication (Student, HR, Admin)
- Resume-based and HR-generated interview flows
- Question-by-question interview experience
- Interview analytics and CSV export for HR
- Modern, responsive UI
- Secure authentication and error handling
- Database migrations with Flask-Migrate

## Project Structure

```
InterView_Qestions/
│   app.py                # Main Flask app setup (entry point)
│   models.py             # SQLAlchemy models
│   student.py            # Student blueprint (routes & logic)
│   hr.py                 # HR blueprint (routes & logic)
│   Questions_for_interview.py # (Legacy, move logic to blueprints)
│   requirements.txt      # Python dependencies
│
├── templates/            # Jinja2 HTML templates
├── static/               # CSS, JS, images
├── utils/                # Utility modules (e.g., email)
└── migrations/           # Database migration scripts
```

## Setup Instructions

1. **Clone the repository**

2. **Create and activate a virtual environment**

   ```powershell
   python -m venv env
   ./env/Scripts/activate
   ```

3. **Install dependencies**

   ```powershell
   pip install -r requirements.txt
   ```

4. **Set environment variables**

   Create a `.env` file in the root folder with:

   ```
   FLASK_SECRET_KEY=your_secret_key
   GEMINI_API_KEY=your_gemini_api_key
   EMAIL_SENDER=your_email@gmail.com
   EMAIL_PASSWORD=your_email_password
   ```

5. **Initialize the database**

   ```powershell
   $env:FLASK_APP = "app.py"
   flask db init           # Only once, if migrations/ does not exist
   flask db migrate -m "Initial migration"
   flask db upgrade
   ```

6. **Run the application**

   ```powershell
   python app.py
   ```

7. **Access the app**

   Open [http://localhost:5000](http://localhost:5000) in your browser.

## Developer Notes

- All business logic and HTML rendering is in `student.py` and `hr.py` blueprints.
- `app.py` is only for app setup and blueprint registration.
- Use Flask-Migrate for all database schema changes.
- For production, set `debug=False` in `app.py`.

## License

MIT