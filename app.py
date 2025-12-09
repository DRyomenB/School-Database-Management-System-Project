from flask import Flask, request, redirect, url_for, flash
from flask_mail import Mail, Message
import os, sqlite3

app = Flask(__name__)
app.secret_key = "test"

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')
db_path = os.getenv("DB_PATH")

# MAILTRAP CONFIG BLOCK ↓
app.config['MAIL_SERVER'] = 'sandbox.smtp.mailtrap.io'
app.config['MAIL_PORT'] = 2525
app.config['MAIL_USE_TLS'] = True
# app.config['MAIL_USERNAME'] = os.getenv('MAILTRAP_USERNAME')
# app.config['MAIL_PASSWORD'] = os.getenv('MAILTRAP_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = 'admissions@benjamin.edu'
# REPLACE os.getenv lines with:
app.config['MAIL_USERNAME'] = '6d1165f1a82404'
app.config['MAIL_PASSWORD'] = '621a71f570893c'

# ↑ END MAILTRAP BLOCK

mail = Mail(app)

# Dummy functions
def get_pending_applications(): return {"success": True, "applications": []}
def get_application_by_id(id): return {"success": True, "application": {"id": id}}
def approve_application(id, r, n): return {"success": True, "school_email": "test@school.edu"}

mail = Mail(app)

@app.route("/debug-env")
def debug_env():
    username = os.getenv('MAILTRAP_USERNAME')
    password = os.getenv('MAILTRAP_PASSWORD')
    return f"""
    <h1>Debug .env</h1>
    <p>MAILTRAP_USERNAME: {username or '❌ MISSING!'}</p>
    <p>MAILTRAP_PASSWORD: {'✅ LOADED' if password else '❌ MISSING!'}</p>
    """


@app.route("/test")
def test():
    return "✅ ALL WORKING!"

@app.route("/")
def home():
    return """
    <h1>🎓 Benjamin University Portal</h1>
    <a href="/applications/pending" class="btn btn-primary">View Pending Applications</a>
    <a href="/submit" class="btn btn-success">Submit Application</a>
    """

@app.route("/submit", methods=["GET", "POST"])
def submit():
    if request.method == "POST":
        return "Application submitted!"
    return """
    <h1>Submit Application</h1>
    <form method="POST">
        Name: <input name="first_name"><br>
        Email: <input name="email"><br>
        <button>Submit</button>
    </form>
    """

db_path = os.getenv("DB_PATH", "student_app.db")  # ADD THIS

@app.route("/applications/pending")
def pending():
    conn = sqlite3.connect(db_path)  # Now works!
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM StudentApplication')
    apps = []
    for row in cursor.fetchall():
        apps.append({
            "id": row[0], 
            "first_name": row[1], 
            "last_name": row[2], 
            "email": row[3], 
            "phone": row[4],
            "major": row[5],
            "status": row[6] if len(row) > 6 else "unknown"
        })
    conn.close()
    
    html = f"<h1>All Applications ({len(apps)})</h1>"
    for app in apps:
        html += f"""
        <div style="border:1px solid #ccc; padding:15px; margin:10px; background:#f9f9f9;">
            <strong>{app['first_name']} {app['last_name']}</strong><br>
            Email: {app['email']}<br>
            Major: {app['major']} | Status: <span style="color:blue;">{app['status']}</span><br>
            <form method="POST" action="/applications/approve/{app['id']}" style="display:inline;">
                <button style="background:green;color:white;padding:5px 10px;border:none;border-radius:3px;">✅ Approve</button>
            </form>
            <form method="POST" action="/applications/reject/{app['id']}" style="display:inline;">
                <button style="background:red;color:white;padding:5px 10px;border:none;border-radius:3px;">❌ Reject</button>
            </form>
        </div>
        """
    return html

@app.route("/applications/approve/<int:application_id>", methods=["POST"])
def approve_app(application_id):
    try:
        print(f"🔍 Approving app {application_id}")
        
        # Get app data
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM StudentApplication WHERE id = ?', (application_id,))
        row = cursor.fetchone()
        conn.close()
        
        application = {
            'id': row[0], 'first_name': row[1], 'last_name': row[2], 'email': row[3]
        }
        
        # Generate school email
        import time
        timestamp = str(int(time.time()))
        school_email = f"{application['first_name'].lower()}.{application['last_name'].lower()}{timestamp}@benjamin.edu"
        
        # Update status
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('UPDATE StudentApplication SET status = "approved" WHERE id = ?', (application_id,))
        conn.commit()
        conn.close()
        
        msg = Message(
            subject="🎉 APPROVED! Welcome!",
            recipients=[application['email']],
            html=f"<h1>{school_email}</h1>"
        )
        mail.send(msg)  # REAL!
        print(f"✅ REAL MAILTRAP to {application['email']}")
        flash(f"✅ Approved + Email sent!", "success")
        
    except Exception as e:
        print(f"Error: {e}")
        flash("Error", "error")
    
    return redirect(url_for("pending"))

@app.route("/test-mailtrap")
def test_mailtrap():
    """Test Mailtrap connection"""
    try:
        msg = Message(
            subject="🧪 Mailtrap Test", 
            recipients=["test@example.com"],
            body="✅ If you see this in Mailtrap, connection WORKS!"
        )
        mail.send(msg)
        return "<h1 style='color:green; text-align:center;'>✅ **MAILTRAP LIVE!**<br><br>Check your Mailtrap inbox now!</h1>"
    except Exception as e:
        return f"<h1 style='color:red; text-align:center;'>❌ Mailtrap FAILED:<br><br><code>{str(e)}</code></h1>"

@app.route("/applications/reject/<int:application_id>", methods=["POST"])
def reject_app(application_id):
    """Reject application - sends Mailtrap rejection email"""
    try:
        result = update_application_status(application_id, "rejected")
        flash(result["message"], "success")
    except Exception as e:
        flash(f"Error: {str(e)}", "error")
    
    return redirect(url_for("pending"))


if __name__ == "__main__":
    app.run(debug=True)