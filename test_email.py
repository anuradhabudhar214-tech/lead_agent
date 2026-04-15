import smtplib
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def test_email():
    with open("config.json", "r") as f:
        config = json.load(f)
    
    try:
        msg = MIMEMultipart()
        msg['From'] = config['SENDER_EMAIL']
        msg['To'] = config['RECIPIENT_EMAIL']
        msg['Subject'] = "Crunchbase Agent Test Email"
        msg.attach(MIMEText("This is a test to verify email alerting works.", 'plain'))

        server = smtplib.SMTP(config['SMTP_SERVER'], config['SMTP_PORT'])
        server.starttls()
        server.login(config['SENDER_EMAIL'], config['SENDER_PASSWORD'])
        server.send_message(msg)
        server.quit()
        print("SUCCESS: Test email sent successfully!")
    except Exception as e:
        print(f"FAILED: Email Test Failed: {e}")

if __name__ == "__main__":
    test_email()
