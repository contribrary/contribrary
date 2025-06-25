from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
import sqlite3
import uvicorn
from pathlib import Path

app = FastAPI()

# Load HTML template and replace placeholders
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

# Fetch an article from SQLite
@app.get("/article", response_class=HTMLResponse)
async def get_article(request: Request):
    article_id = request.query_params.get("id")

    if not article_id or not article_id.isdigit():
        return error_page()

    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, content, author, date FROM articles WHERE id=?", (int(article_id),))
        row = cursor.fetchone()
        conn.close()

        if row:
            article = {
                "id": row[0],
                "title": row[1],
                "content": row[2],
                "author": row[3],
                "date": row[4],
            }
            return HTMLResponse(load_template("public/article.html", article))
        else:
            return error_page()
    except Exception as e:
        print("Database error:", e)
        return error_page()

# Serve static files (like index.html)
@app.get("/", response_class=HTMLResponse)
async def serve_home():
    try:
        return HTMLResponse(Path("public/index.html").read_text())
    except FileNotFoundError:
        return HTMLResponse("<h1>Home page not found</h1>", status_code=404)

# Handle unknown URLs with error.html
@app.exception_handler(404)
async def not_found(request: Request, exc: HTTPException):
    return error_page()

# Load error page
def error_page():
    try:
        return HTMLResponse(Path("public/error.html").read_text(), status_code=404)
    except FileNotFoundError:
        return HTMLResponse("<h1>Page not found</h1>", status_code=404)

# Run the server
if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, workers=4)