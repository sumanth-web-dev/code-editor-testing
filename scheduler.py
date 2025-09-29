from datetime import datetime, timedelta
from io import StringIO
import csv

from extensions import db
from models import Interview, HR, Student, QuestionAnswer
from email_utils import send_email, send_email_with_attachment
from flask import current_app
from sqlalchemy.orm import joinedload

def delete_old_interviews():
    with current_app.app_context():
        print("[Scheduler] Starting interview export & deletion job...")

        threshold_time = datetime.utcnow() - timedelta(days=180)

        # Fetch HRs with their interviews (using eager loading)
        hrs_with_old_interviews = (
            db.session.query(HR)
            .options(joinedload(HR.interviews))
            .join(Interview)
            .filter(Interview.created_at <= threshold_time)
            .distinct()
            .all()
        )

        print(f"[Scheduler] Found {len(hrs_with_old_interviews)} HR(s) with old interviews.")

        if not hrs_with_old_interviews:
            print("[Scheduler] No old interviews found for any HR. Job done.")
            return

        for hr in hrs_with_old_interviews:
            # Filter only old interviews for this HR
            old_interviews = [i for i in hr.interviews if i.created_at <= threshold_time]

            if not old_interviews:
                continue

            si = StringIO()
            writer = csv.writer(si)

            writer.writerow([
                'Interview ID', 'Company Name', 'Job Title', 'Student Name',
                'Student Email', 'Student Phone', 'No. of Questions',
                'Question', 'Candidate Answer', 'LLM Answer', 'Score'
            ])

            total_rows = 0

            for interview in old_interviews:
                company_name = interview.company_name or 'N/A'
                job_title = interview.job_title or 'N/A'

                student_ids = {qa.student_id for qa in interview.qa_pairs if qa.student_id}

                for student_id in student_ids:
                    student = Student.query.get(student_id)
                    if not student:
                        continue

                    student_qas = [
                        qa for qa in interview.qa_pairs if qa.student_id == student_id
                    ]
                    num_questions = len(student_qas)

                    for qa in student_qas:
                        writer.writerow([
                            interview.id, company_name, job_title,
                            student.name, student.email, student.phone or '',
                            num_questions,
                            qa.text, qa.answer_text or '',
                            qa.llm_answer_text or '',
                            qa.score if qa.score is not None else ''
                        ])
                        total_rows += 1

            if total_rows > 0:
                csv_content = si.getvalue()
                try:
                    send_email_with_attachment(
                        to_email=hr.email,
                        subject="Naventra AI | Old Interview Data Export & Deletion Notice",
                        body_text=f"""
                                    <html>
                                        <body style="font-family: 'Segoe UI', sans-serif; background-color: #f4f6f8; padding: 30px; margin: 0;">
                                            <div style="max-width: 620px; margin: auto; background: #ffffff; border-radius: 12px; padding: 40px 35px; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">
                                            <div style="text-align: center; margin-bottom: 30px;">
                                                <h1 style="color: #185adb; margin: 0; font-size: 28px;">Naventra AI</h1>
                                                <p style="color: #555; margin-top: 8px; font-size: 14px;">Interview Data Cleanup Notification</p>
                                            </div>

                                            <p style="font-size: 16px; color: #333; line-height: 1.7; margin-bottom: 20px;">
                                                Dear <strong>{hr.email}</strong>,
                                            </p>

                                            <p style="font-size: 16px; color: #333; line-height: 1.7; margin-bottom: 20px;">
                                                We’d like to inform you that we have successfully exported and securely deleted your interview records that were older than <strong>6 months</strong> as part of our routine data retention policy.
                                            </p>

                                            <div style="background-color: #f0f4ff; padding: 15px 20px; border-radius: 8px; margin-bottom: 25px;">
                                                <p style="margin: 0; font-size: 16px; color: #333;">
                                                📊 <strong>Total records exported and deleted:</strong> 
                                                <span style="color: #185adb; font-weight: bold;">{total_rows}</span>
                                                </p>
                                            </div>

                                            <p style="font-size: 16px; color: #333; line-height: 1.7; margin-bottom: 20px;">
                                                You can find the exported data attached to this email for your reference. If you have any concerns, questions, or require assistance, please don’t hesitate to reach out to our support team.
                                            </p>

                                            <p style="font-size: 16px; color: #333; line-height: 1.7; margin-bottom: 30px;">
                                                Thank you for trusting <strong>Naventra AI</strong> for your interview management needs.
                                            </p>

                                            <p style="font-size: 16px; color: #333; margin-bottom: 0;">
                                                Best regards,<br>
                                                <strong>Naventra AI Team</strong>
                                            </p>

                                            <hr style="margin: 35px 0 20px; border: none; border-top: 1px solid #e0e0e0;">

                                            <p style="font-size: 12px; color: #999; text-align: center; margin: 0;">
                                                This is an automated message. Please do not reply to this email.
                                            </p>
                                            </div>
                                        </body>
                                        </html>

                        """.strip(),
                        attachment_content=csv_content.encode('utf-8'),
                        attachment_filename="old_interviews_export.csv"
                    )
                    print(f"[Scheduler] Export email sent to {hr.email} with {total_rows} record(s).")
                except Exception as e:
                    print(f"[Scheduler] Failed to send export email to {hr.email}: {e}")

            # Now delete interviews
            for interview in old_interviews:
                db.session.delete(interview)

            db.session.commit()

            try:
                send_email(
                    to_email=hr.email,
                    subject="Naventra AI | Interview Data Deleted",
                    content=f"""
                                    <html>
                                    <body style="font-family: 'Segoe UI', sans-serif; background-color: #f4f6f8; padding: 30px; margin: 0;">
                                        <div style="max-width: 600px; margin: auto; background: #ffffff; border-radius: 12px; padding: 35px; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">
                                        <div style="text-align: center; margin-bottom: 25px;">
                                            <h1 style="color: #185adb; margin: 0; font-size: 26px;">Naventra AI</h1>
                                            <p style="color: #555; margin-top: 8px; font-size: 14px;">Data Deletion Confirmation</p>
                                        </div>

                                        <p style="font-size: 16px; color: #333; line-height: 1.7; margin-bottom: 20px;">
                                            Dear <strong>{hr.email}</strong>,
                                        </p>

                                        <p style="font-size: 16px; color: #333; line-height: 1.7; margin-bottom: 20px;">
                                            This is to confirm that <strong>{len(old_interviews)}</strong> of your interviews, older than <strong>6 Months ago</strong>, have been securely and permanently deleted from our system as part of the scheduled data cleanup process.
                                        </p>

                                        <div style="background-color: #f0f4ff; padding: 15px 20px; border-radius: 8px; margin-bottom: 25px;">
                                            <p style="margin: 0; font-size: 16px; color: #333;">
                                            🗑️ <strong>Records Deleted:</strong>
                                            <span style="color: #185adb; font-weight: bold;">{len(old_interviews)}</span>
                                            </p>
                                        </div>

                                        <p style="font-size: 16px; color: #333; line-height: 1.7; margin-bottom: 20px;">
                                            No further action is required from your side. If you have any questions or need assistance, feel free to contact our support team.
                                        </p>

                                        <p style="font-size: 16px; color: #333; margin-bottom: 30px;">
                                            Thank you for using <strong>Naventra AI</strong>.
                                        </p>

                                        <p style="font-size: 16px; color: #333; margin-bottom: 0;">
                                            Warm regards,<br>
                                            <strong>Naventra AI Team</strong>
                                        </p>

                                        <hr style="margin: 35px 0 20px; border: none; border-top: 1px solid #e0e0e0;">

                                        <p style="font-size: 12px; color: #999; text-align: center; margin: 0;">
                                            This is an automated message. Please do not reply to this email.
                                        </p>
                                        </div>
                                    </body>
                                    </html>

                                    """
                )
                print(f"[Scheduler] Deletion confirmation sent to {hr.email}.")
            except Exception as e:
                print(f"[Scheduler] Failed to send deletion email to {hr.email}: {e}")

        print("[Scheduler] Interview export & deletion job completed.")



def run_delete_old_interviews_job(app):
    with app.app_context():
        delete_old_interviews()


# def delete_old_interviews():
#     with current_app.app_context():
#         six_months_ago = datetime.utcnow() - timedelta(days=180)
#         old_interviews = Interview.query.filter(Interview.created_at <= six_months_ago).all()

#         for interview in old_interviews:
#             db.session.delete(interview)
#         db.session.commit()

#         print(f"[Scheduler] Deleted {len(old_interviews)} old interview(s).")