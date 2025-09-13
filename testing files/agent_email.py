import pandas as pd
import smtplib
from email.mime.text import MIMEText

# Gmail credentials
EMAIL = "zuberipersonal@gmail.com"           
PASSWORD = "lavfqbdauszbjuxp"      

# Read client data from Excel
df = pd.read_excel("customers.xlsx")

# Subject and body for SELLERS (property owners)
SUBJECT = "Let Us Help You Sell Your Property"
BODY = """
Dear Property Owner,

We would be honored to work with you in selling your property. 
Our automated system connects you with serious buyers quickly and efficiently. 
With our support, you can get the best value for your plot, house, or commercial property 
without the usual hassle.

Please feel free to reply to this email or contact us directly. 
We are here to assist you throughout the entire process.

Best Regards,
Real Estate Automation Team
"""

def send_email(to_email, subject, body):
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL
    msg["To"] = to_email

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL, PASSWORD)
            server.sendmail(EMAIL, to_email, msg.as_string())
        print(f"✅ Email sent to {to_email}")
    except Exception as e:
        print(f"❌ Failed to send email to {to_email} - {e}")

# Loop through emails in Excel
for email in df["Email"]:
    if pd.notna(email): 
        send_email(email, SUBJECT, BODY)
