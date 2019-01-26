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
        
        # delete last search data
        session['last_search_text'] = None
        session['last_search_type'] = None

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
    return render_template('create_success.html', 
        id=session['current_user_id'],
        username=session.get('current_user'))


@app.route("/log_out", methods=["GET"])
def log_out(): 
    session['current_user'] = None
    session['current_user_id'] = None
    session['last_search_text'] = None
    session['last_search_type'] = None
    return render_template('logged_out.html')

@app.route("/search", methods=["GET"])
def search():
    
    # make sure user is logged in
    if not session.get('current_user'):
        return redirect(url_for('index'))

    search_text = request.args.get('search_text')
    search_type = request.args.get('search_type')

    session['last_search_text'] = search_text
    session['last_search_type'] = search_type

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
        return render_template('error.html', 
            error_message="No books found",
            username=session.get('current_user'))
    else:
        return render_template('search.html', 
            all_books=all_books, 
            search_type=search_type.upper(), 
            search_text=search_text,
            username=session.get('current_user'))

@app.route("/book/<string:book_id>")
def display_book(book_id):
    # make sure user is logged in
    if not session.get('current_user'):
        return redirect(url_for('index'))

    # get book info based on id from url string
    book = db.execute("SELECT * FROM books WHERE id = :book_id", {"book_id": book_id}).fetchone()
    if not book:
        return render_template('error.html', 
            error_message='Sorry, we can\'t find that book!',
            username=session.get('current_user'))
    
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

    # if no reviews found
    if not reviews:
        review_data = False

    # if reviews found
    else:
        #review_data = reviews
        review_data = [{'id': review[0],
                        'book_id': review[1],
                        'review_text': review[2],
                        'rating': review[3],
                        'user_id': review[4],
                        'username': review[5],
                        'by_current_user': review[6]
                        } for review in reviews]      
    

    if session.get('last_search_text'):
        last_search = {
            'text': session.get('last_search_text'),
            'type': session.get('last_search_type')
        }
    else:
        last_search = None

    return render_template('display_book.html', 
        book=book, 
        rating_data=rating_data, 
        review_data=review_data,
        last_search=last_search,
        username=session.get('current_user')
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
        return render_template('error.html', 
            error_message='Sorry, we can\'t find that book!',
            username=session.get('current_user'))
    
    book = {
        'title': title[0],
        'id': book_id
    }
    # GET request and user is logged in
    if request.method == "GET":

        existing_text = db.execute("SELECT review_text FROM reviews " 
                        "WHERE book_id=:book_id AND reviewer=:current_user",
                        {
                            'book_id': book_id, 
                            'current_user': session.get('current_user_id')
                        }).fetchone()
        
        # if the user has already reviewed this book
        if existing_text:
            existing_text = existing_text[0]
            header = 'Edit your review'

        # if user has not reviewed book yet
        else:
            existing_text = ''
            header = 'Write a Review'

        return render_template('write_review.html', 
                                book = book,
                                existing_text=existing_text,
                                error='',
                                header = header,
                                username=session.get('current_user'))

    # submit new review to database
    elif request.method == "POST":
        review_text = request.form.get('review_text').strip()
        rating = request.form.get('rate')
        review_type = request.form.get('review_type')

        if review_type == 'new':
            header = 'Write a Review'
        else:
            header = "Edit your review"
        if not rating or not review_text:
            
            return render_template('write_review.html', 
                                    book = book,
                                    existing_text=review_text,
                                    error="Please select a rating and write a review",
                                    username=session.get('current_user'),
                                    header=header)
        

        if review_type == 'new':
            # user is submitting an initial review for the book
            db.execute('INSERT INTO reviews (book_id, review_text, rating, reviewer) VALUES (:book_id, :review_text, :rating, :reviewer)',
                {
                    'book_id': book_id,
                    'review_text': review_text,
                    'rating': rating,
                    'reviewer': session.get('current_user_id')
                })
            db.commit()

        else:
            # user is editing the review they have already written
            db.execute('UPDATE reviews '
                'SET review_text = :review_text, rating = :rating '
                'WHERE reviewer = :current_user_id AND book_id = :book_id',
                {
                    'review_text': review_text,
                    'rating': rating,
                    'current_user_id': session.get('current_user_id'),
                    'book_id': book_id
                })
            db.commit()        

        return redirect(url_for('display_book', book_id=book_id))


#create API route
@app.route("/api/<string:isbn>")
def api(isbn):
    book = db.execute("SELECT id, title, author, pub_year "
            "FROM books WHERE isbn = :isbn",
            {'isbn':isbn}).fetchone()
    
    if not book:
        error = {'message': 'No book found with that ISBN'}
        return jsonify({'error':'No book found with that ISBN'}), 404

    data = {
        'title': book[1],
        'author': book[2],
        'year': book[3],
        'isbn': isbn
    }
    reviews = db.execute("SELECT COUNT(rating), ROUND(AVG(rating), 1) FROM reviews "
            "WHERE book_id=:book_id", {'book_id': book[0]}).fetchone()
    
    
    # else:
    data['review_count'] = reviews[0]
    if reviews[0]:
        data['average_score'] = float(reviews[1]) 
    else:
        data['average_score'] = None

    return jsonify(data), 200


if __name__ == "__main__":
    app.run()