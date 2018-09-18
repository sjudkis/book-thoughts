# Goodreads API
goodreads_key = 'dzKzUUNf1nLuROZbNZPBVw'
#secret: wxIctgIQG6eOMFV5W7vHqbbY3QZCzxcHiCHLROtVqn0
#test
import os, requests

from flask import Flask, session, render_template, request
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))


@app.route("/", methods=["GET", "POST"])
def index():
    message = ''
    # for GET requests
    if request.method == "GET":
        # user not logged in
        if not session.get('current_user'):
            return render_template('sign_in.html', message = message)
        # user is logged in
        else:
            return render_template('home.html', username=session.get('current_user'))
    
    # for POST requests
    if request.method == "POST":
        username = request.form.get('username')

        # get password hash for given username
        get_hash = db.execute("SELECT password_hash FROM users WHERE username=:username", {"username":username}).fetchone()

        # check if username exists
        if get_hash is None:
            # username is invalid
            message = "Invalid Username"
            return render_template("sign_in.html", message=message)
        
        # check for correct password
        password = request.form.get('password')
        check_hash = check_password_hash(get_hash.password_hash, password)

        if not check_hash:
            # incorrect password
            message = "Invalid Password"
            return render_template("sign_in.html", message=message)
        
        # correct password
        session['current_user'] = username
        return render_template("home.html", username=username)



@app.route("/create_account", methods=["POST", "GET"])
def create_account():
    
    if request.method == "GET":
        return render_template('create_account.html', message = '')
    
    # for POST requests:
    #get form data
    create_username = request.form.get("username")
    create_password = request.form.get("password")
    
    #check username availability
    check_username = db.execute("SELECT id FROM users WHERE username=:username", {"username":create_username}).fetchone()
    
    # username is taken
    if check_username is not None:
        message = "Username is not available"
        return render_template('create_account.html', message = message)
    
    # username available
    password_hash = generate_password_hash(create_password)
    db.execute("INSERT INTO users (username, password_hash) VALUES (:username, :password_hash)", {"username":create_username, "password_hash":password_hash})
    db.commit()
    
    # add user to current session
    session['current_user'] = create_username

    return render_template('create_success.html')


@app.route("/log_out", methods=["GET"])
def log_out(): 
    session['current_user'] = None
    return render_template('logged_out.html')