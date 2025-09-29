# import smtplib
# from email.mime.text import MIMEText

# def send_email(to_email, subject, body):
#     msg = MIMEText(body)
#     msg['Subject'] = subject
#     msg['From'] = 'your_email@example.com'
#     msg['To'] = to_email
#     with smtplib.SMTP('smtp.gmail.com', 587) as server:
#         server.starttls()
#         server.login('your_email@example.com', 'your_app_password')
#         server.send_message(msg)