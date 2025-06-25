from fastapi import FastAPI, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
import sqlite3
import secrets
import aiosmtplib
from email.message import EmailMessage
from email_validator import validate_email, EmailNotValidError
from pathlib import Path
from detoxify import Detoxify

app = FastAPI()

# Store pending verifications {email: token}
pending_verifications = {}

# ✅ Async function to send email
async def send_email(sender, password, receiver, subject, body):
    try:
        # Create the email message
        message = EmailMessage()
        message["From"] = sender
        message["To"] = receiver
        message["Subject"] = subject
        message.set_content(body)

        # Send email asynchronously using the correct SMTP configuration
        async with aiosmtplib.SMTP(hostname="smtp.gmail.com", port=587, start_tls=True) as smtp:
            await smtp.connect()
            await smtp.login(sender, password)
            await smtp.send_message(message)

        print("✅ Email sent successfully!")

    except aiosmtplib.SMTPAuthenticationError:
        print("❌ Authentication failed! Check your email/password (App Password required).")
        raise HTTPException(status_code=401, detail="Invalid email/password (App Password required)")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")

# ✅ Database setup
def get_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS article (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            content TEXT,
            author TEXT,
            email TEXT,
            date TEXT
        )"""
    )
    conn.commit()
    return conn, cursor

# ✅ Load HTML template
def load_template(template_path: str, article: dict) -> str:
    try:
        html = Path(template_path).read_text()
        return (
            html.replace("${title}", article["title"])
                .replace("${title_article}", article["title"])
                .replace("${content}", article["content"])
                .replace("${author}", article["author"])
                .replace("${date}", article["date"])
        )
    except FileNotFoundError:
        return "<h1>Template file not found</h1>"

# ✅ Handle Article Submission & Send Verification Email
@app.post("/submit")
async def handle_form(
    title: str = Form(...),
    content: str = Form(...),
    author: str = Form(...),
    email: str = Form(...),
):
    # Validate email format
    try:
        email_info = validate_email(email, check_deliverability=True)
        email = email_info.normalized
        print(f"✅ Valid email: {email}")
    except EmailNotValidError:
        raise HTTPException(status_code=400, detail="Invalid email address")

    # Check for toxicity
    toxicity = Detoxify("original").predict(content)
    if toxicity["toxicity"] > 0.6:
        return JSONResponse(content={"error": "Your content is too toxic"}, status_code=400)

    # Generate a unique verification token
    token = secrets.token_urlsafe(16)
    pending_verifications[email] = {"token": token, "title": title, "content": content, "author": author}

    # Send verification email
    verification_link = f"http://localhost:8000/verify?email={email}&token={token}"
    email_content = f"Click <a href='{verification_link}'>here</a> to verify your email and publish your article."

    try:
        await send_email(
            sender="uke2539@gmail.com",
            password="ttlck vkzmqn snjug",  # Use an App Password
            receiver=email,
            subject="Verify Your Email to Publish Your Article",
            body=email_content
        )
    except HTTPException as e:
        return JSONResponse(content={"error": e.detail}, status_code=e.status_code)

    return {"message": "Verification email sent. Please check your inbox."}

# ✅ Verify Email & Store Article in Database
@app.get("/verify")
async def verify_email(email: str, token: str):
    if email not in pending_verifications or pending_verifications[email]["token"] != token:
        return HTMLResponse("<h1>Invalid or expired verification link.</h1>", status_code=400)

    article = pending_verifications.pop(email)

    # Save to database
    conn, cursor = get_db()
    cursor.execute(
        "INSERT INTO article (title, content, author, email, date) VALUES (?, ?, ?, ?, DATE('now'))",
        (article["title"], article["content"], article["author"], email),
    )
    conn.commit()
    conn.close()

    return HTMLResponse("<h1>Email Verified! Your article has been published.</h1>")

# ✅ Retrieve an Article
@app.get("/article", response_class=HTMLResponse)
async def get_article(request: Request):
    article_id = request.query_params.get("id")
    if not article_id or not article_id.isdigit():
        return HTMLResponse("<h1>Article not found</h1>", status_code=404)

    conn, cursor = get_db()
    cursor.execute("SELECT id, title, content, author, date FROM article WHERE id=?", (int(article_id),))
    row = cursor.fetchone()
    conn.close()

    if row:
        article = {"id": row[0], "title": row[1], "content": row[2], "author": row[3], "date": row[4]}
        return HTMLResponse(load_template("public/article.html", article))
    else:
        return HTMLResponse("<h1>Article not found</h1>", status_code=404)

# ✅ Serve Upload Page
@app.get("/upload", response_class=HTMLResponse)
async def serve_upload():
    try:
        return HTMLResponse(Path("public/article_parth.html").read_text())
    except FileNotFoundError:
        return HTMLResponse("<h1>Upload page not found</h1>", status_code=404)

# ✅ Serve Homepage
@app.get("/", response_class=HTMLResponse)
async def serve_home():
    try:
        html_content = Path("public/index.html").read_text()
        conn, cursor = get_db()
        cursor.execute("SELECT COUNT(*) FROM article")
        row_count = cursor.fetchone()[0]
        conn.close()

        return HTMLResponse(content=html_content.replace("{{ row_count }}", str(row_count)))
    except FileNotFoundError:
        return HTMLResponse("<h1>Home page not found</h1>", status_code=404)

# ✅ Handle 404 Errors
@app.exception_handler(404)
async def not_found(request: Request, exc: HTTPException):
    return HTMLResponse("<h1>Page not found</h1>", status_code=404)

# ✅ Run the Server
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
