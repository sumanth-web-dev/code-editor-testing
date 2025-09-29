import os
from email.message import EmailMessage
import smtplib
from dotenv import load_dotenv
load_dotenv()

# This function sends an email with the specified subject and content to the given recipient.
def send_email(to_email, subject, content, html_content=None):
    email_user = os.getenv("EMAIL_ADDRESS")
    email_password = os.getenv("EMAIL_PASSWORD")
    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = int(os.getenv("SMTP_PORT", 587))

    if not all([email_user, email_password, smtp_server]):
        raise ValueError("Email config variables not set")

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = email_user
    msg['To'] = to_email
    msg.add_alternative(content, subtype='html')

    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        server.login(email_user, email_password)
        server.send_message(msg)


# This function sends a confirmation email to the student after they complete their interview.
def send_confirmation_email(to_email, student_name, interview):
    email_user = os.getenv("EMAIL_ADDRESS")
    email_password = os.getenv("EMAIL_PASSWORD")
    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = int(os.getenv("SMTP_PORT", 587))

    if not all([email_user, email_password, smtp_server]):
        raise ValueError("Email config missing")

    msg = EmailMessage()
    msg['Subject'] = f"Confirmation: {interview.job_title} Interview Completed"
    msg['From'] = email_user
    msg['To'] = to_email

    html_content = f"""
<html>
<body style="font-family: 'Roboto', sans-serif; line-height: 1.6; color: #444444; background-color: #eef2f6; padding: 25px;">
    <div style="max-width: 650px; margin: 25px auto; background: #ffffff; padding: 35px 40px; border-radius: 12px; box-shadow: 0 6px 20px rgba(0,0,0,0.1);">
        <div style="text-align: center; margin-bottom: 30px;">
            <h1 style="color: #1c315f; font-size: 28px; margin-bottom: 10px;">Interview Confirmation</h1>
            <p style="color: #666666; font-size: 17px;">Your application matters to us!</p>
        </div>

        <h2 style="color: #333333; margin-bottom: 20px;">Dear {student_name},</h2>
        
        <p style="font-size: 16px; margin-bottom: 25px;">We want to extend our sincere thanks for completing your interview for the <strong>{interview.job_title}</strong> position at <strong>{interview.company_name}</strong>.</p>

        <p style="font-size: 16px; margin-bottom: 35px;">Your commitment to the process is highly valued. Our team is now diligently reviewing all responses, and we'll be in touch very soon with an update on your application status.</p>

        <div style="border: 1px solid #dcdcdc; border-radius: 8px; padding: 25px; background-color: #ffffff;">
            <h4 style="color: #1c315f; margin-top: 0; margin-bottom: 18px; font-size: 18px;">✨ Interview Summary:</h4>
            <ul style="list-style-type: none; padding: 0; margin: 0;">
                <li style="margin-bottom: 12px; font-size: 16px;"><strong style="color: #555;">Company:</strong> <span style="color: #007bff;">{interview.company_name}</span></li>
                <li style="font-size: 16px;"><strong style="color: #555;">Job Title:</strong> <span style="color: #007bff;">{interview.job_title}</span></li>
            </ul>
        </div>

        <p style="font-size: 16px; text-align: center; margin-top: 40px; color: #555;">We appreciate your interest and wish you all the very best!</p>

        <p style="margin-top: 45px; font-size: 15px; color: #666; text-align: center;">Kind regards,<br>
        <strong style="color: #1c315f; font-size: 16px;">Naventra AI HR Team</strong></p>
    </div>
</body>
</html>
    """

    msg.add_alternative(html_content, subtype='html')

    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        server.login(email_user, email_password)
        server.send_message(msg)


# It includes the email address, subject, body text, attachment content, and filename.
def send_email_with_attachment(to_email, subject, body_text, attachment_content, attachment_filename):
    email_user = os.getenv("EMAIL_ADDRESS")
    email_password = os.getenv("EMAIL_PASSWORD")
    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = int(os.getenv("SMTP_PORT", 587))

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = email_user
    msg['To'] = to_email
    msg.set_content("This is a HTML email. Please view it in an HTML compatible email client.")
    msg.add_alternative(body_text, subtype='html')

    msg.add_attachment(attachment_content, maintype='text', subtype='csv', filename=attachment_filename)

    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        server.login(email_user, email_password)
        server.send_message(msg)