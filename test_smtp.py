# test_smtp.py
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv() # Load environment variables from .env

SENDER_EMAIL = os.environ.get('MAIL_USERNAME')
SENDER_PASSWORD = os.environ.get('MAIL_PASSWORD')
RECEIVER_EMAIL = SENDER_EMAIL # Send to yourself for testing
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587

if not SENDER_EMAIL or not SENDER_PASSWORD:
    print("Error: MAIL_USERNAME or MAIL_PASSWORD not set in environment.")
    print("Please ensure your .env file is correct and loaded.")
    exit()

print(f"Attempting to send email from: {SENDER_EMAIL}")
print(f"Using SMTP server: {SMTP_SERVER}:{SMTP_PORT}")

msg = MIMEMultipart()
msg['From'] = SENDER_EMAIL
msg['To'] = RECEIVER_EMAIL
msg['Subject'] = "Test Email from Standalone Script"

body = "This is a test email sent from a standalone Python script. If you received this, your SMTP settings are correct!"
msg.attach(MIMEText(body, 'plain'))

try:
    server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
    server.starttls() # Upgrade the connection to a secure encrypted SSL/TLS connection
    server.login(SENDER_EMAIL, SENDER_PASSWORD)
    text = msg.as_string()
    server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, text)
    server.quit()
    print("SUCCESS: Test email sent!")
except smtplib.SMTPAuthenticationError as e:
    print(f"ERROR: SMTP Authentication Failed. Check your username/password (especially App Password for Gmail). Details: {e}")
except smtplib.SMTPConnectError as e:
    print(f"ERROR: SMTP Connection Failed. Check server address, port, or network/firewall. Details: {e}")
except Exception as e:
    print(f"AN UNEXPECTED ERROR OCCURRED: {e}")