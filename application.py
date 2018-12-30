# Goodreads API
goodreads_key = 'dzKzUUNf1nLuROZbNZPBVw'
#secret: wxIctgIQG6eOMFV5W7vHqbbY3QZCzxcHiCHLROtVqn0

import os, requests

from flask import Flask, session, render_template, request, jsonify, redirect, url_for
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__, static_url_path="", static_folder="static")


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
        
        # correct password, add username and id to session
        session['current_user'] = username
        current_user_id = db.execute("SELECT id FROM users WHERE username = :username", {'username': username}).fetchone()[0]
        session['current_user_id'] = current_user_id
        
        return render_template("home.html", username=username)



@app.route("/create_account", methods=["POST", "GET"])
def create_account():
    
    if request.method == "GET" and not session.get('current_user'):
        return render_template('create_account.html', message = '')

    elif request.method == "GET" and session.get('current_user'):
        return redirect(url_for('index'))

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
    # inserts user into database, returns id of new user
    new_user_id = db.execute("INSERT INTO users (username, password_hash) VALUES (:username, :password_hash) RETURNING id", 
        {
            "username":create_username, 
            "password_hash":password_hash
        }).fetchone()['id']
    db.commit()
    

    # add user to current session
    session['current_user'] = create_username
    session['current_user_id'] = new_user_id
    return render_template('create_success.html', id=session['current_user_id'])


@app.route("/log_out", methods=["GET"])
def log_out(): 
    session['current_user'] = None
    session['current_user_id'] = None
    return render_template('logged_out.html')

@app.route("/search", methods=["GET"])
def search():
    
    # make sure user is logged in
    if not session.get('current_user'):
        return redirect(url_for('index'))

    search_text = request.args.get('search_text')
    search_type = request.args.get('search_type')

    # search by title
    if search_type == "title":
        all_books = db.execute("SELECT * FROM books WHERE title ILIKE :search_text", {"search_text":'%' + search_text + '%'}).fetchall()    
    # search by author
    elif search_type == "author":
        all_books = db.execute("SELECT * FROM books WHERE author ILIKE :search_text", {"search_text":'%' + search_text + '%'}).fetchall()
    # search by author
    else:
        all_books = db.execute("SELECT * FROM books WHERE isbn ILIKE :search_text", {"search_text":'%' + search_text + '%'}).fetchall()
    
    # check if matching books found
    if all_books == []:
        return render_template('search_error.html', error_message="No books found")
    else:
        return render_template('search.html', all_books=all_books, search_type=search_type.upper(), search_text=search_text)

@app.route("/book/<string:book_id>")
def display_book(book_id):
    # make sure user is logged in
    if not session.get('current_user'):
        return redirect(url_for('index'))

    # get book info based on id from url string
    book = db.execute("SELECT * FROM books WHERE id = :book_id", {"book_id": book_id}).fetchone()
    if not book:
        return render_template('error.html', error_message='Sorry, we can\'t find that book!')
    
    # get goodreads rating data from API
    goodreads_url = 'https://www.goodreads.com/book/review_counts.json'
    res = requests.get(goodreads_url, 
        headers={'Accept': 'application/json'},
        params={'key': goodreads_key, 'isbns': book.isbn, 'format': 'json'}
        )
    # extract book data from json
    book_data = res.json()['books'][0]
    if res.status_code == 200:
        rating_data = {
            'avg': book_data['average_rating'],
            'count': book_data['work_ratings_count'],
            'found': True
        }
    else:
        rating_data = {'found': False}


    # get user reviews from database
    reviews = db.execute("SELECT reviews.id, book_id, review_text,  \
                        rating, reviewer, username, (reviewer = :current_user_id) \
                        FROM reviews JOIN users ON reviews.reviewer = users.id  \
                        WHERE book_id = :book_id \
                        ORDER BY (reviewer = :current_user_id) DESC",
                        {'book_id': book_id, 'current_user_id':session.get('current_user_id')}).fetchall()
    print(reviews)
    # if no reviews found
    if not reviews:
        review_data = False

    # if reviews found
    else:
        review_data = reviews

    return render_template('display_book.html', 
        book=book, 
        rating_data=rating_data, 
        review_data=review_data
        )


@app.route('/book/<string:book_id>/write_review', methods=['GET', 'POST'])
def write_review(book_id):

    # if no user logged in
    if not session.get('current_user'):
        return redirect(url_for('index'))


    title = db.execute('SELECT title FROM books WHERE id = :book_id', 
            {'book_id': book_id}).fetchone()
    
    #if book_id is invalid
    if not title:
        return render_template('error.html', error_message='Sorry, we can\'t find that book!')
    
    book = {
        'title': title[0],
        'id': book_id
    }
    # GET request and user is logged in
    if request.method == "GET":
        return render_template('write_review.html', 
                                book = book,
                                existing_text='',
                                error='')

    # submit new review to database
    elif request.method == "POST":
        review_text = request.form.get('review_text').strip()
        rating = request.form.get('rate')

        if not rating or not review_text:
            
            return render_template('write_review.html', 
                                    book = book,
                                    existing_text=review_text,
                                    error="Please select a rating and write a review")
        db.execute('INSERT INTO reviews (book_id, review_text, rating, reviewer) VALUES (:book_id, :review_text, :rating, :reviewer)',
            {
                'book_id': book_id,
                'review_text': review_text,
                'rating': rating,
                'reviewer': session.get('current_user_id')
            })
        db.commit()
        return f"rating: {rating} \n review: {review_text}"
