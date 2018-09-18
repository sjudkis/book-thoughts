import csv
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

def main():
    f = open("books.csv")
    reader = csv.reader(f)
    next(reader)
    for isbn, title, author, year in reader:
        db.execute("INSERT INTO books (isbn, author, title, pub_year) VALUES (:isbn, :author, :title,  :pub_year)", {"isbn": isbn, "author": author, "title": title, "pub_year":year})
        print(f"{isbn}, {author}, {title}, {year}")
    db.commit()
    
if __name__ == "__main__":
    main()