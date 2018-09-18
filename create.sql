-- create users table
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR UNIQUE NOT NULL,
    password_hash VARCHAR NOT NULL
);

-- create books table
CREATE TABLE books (
    id SERIAL PRIMARY KEY,
    isbn INTEGER UNIQUE NOT NULL,
    author VARCHAR NOT NULL,
    title VARCHAR NOT NULL,
    pub_year INTEGER NOT NULL
);

-- create reviews table
CREATE TABLE reviews (
    id SERIAL PRIMARY KEY,
    book_id INTEGER NOT NULL REFERENCES books,
    review_text VARCHAR NOT NULL,
    rating INTEGER NOT NULL,
    reviewer INTEGER NOT NULL REFERENCES users
);