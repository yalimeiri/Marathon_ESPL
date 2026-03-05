import smtplib
import os

# Recreate exactly what Django would do
host = os.environ.get("EMAIL_HOST", "")
port = int(os.environ.get("EMAIL_PORT", 587))
user = os.environ.get("EMAIL_HOST_USER", "")
password = os.environ.get("EMAIL_HOST_PASSWORD", "").replace(" ", "")
to_email = user  # send test email to yourself

print(f"EMAIL_HOST: {host}")
print(f"EMAIL_PORT: {port}")
print(f"EMAIL_HOST_USER: {user}")
print(f"EMAIL_HOST_PASSWORD length: {len(password)} chars")
print(f"Sending to: {to_email}")
print("---")

try:
    print("Connecting to SMTP server...")
    server = smtplib.SMTP(host, port, timeout=10)
    server.set_debuglevel(1)
    server.ehlo()
    print("Starting TLS...")
    server.starttls()
    server.ehlo()
    print("Logging in...")
    server.login(user, password)
    print("Sending email...")
    msg = f"Subject: Marathon Test\n\nThis is a test email from Marathon ESPL."
    server.sendmail(user, to_email, msg)
    server.quit()
    print("SUCCESS! Email sent.")
except Exception as e:
    print(f"FAILED: {type(e).__name__}: {e}")
