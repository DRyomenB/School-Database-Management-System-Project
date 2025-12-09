import os 
import sqlite3
from dotenv import load_dotenv
import requests

load_dotenv()

db_path = os.getenv("DB_PATH")

def insert_student(first_name, last_name, email, phone, major, status, graduation_date=None, gpa=None):
    if not os.path.isfile(db_path):
        print(f"Error: Database file not found at {db_path}")
        return
    try:
        connection = sqlite3.connect(db_path)
        cursor = connection.cursor()
        cursor.execute('PRAGMA foreign_keys = ON;')
        cursor.execute(
            """INSERT INTO Student (first_name, last_name, email, phone, major, status, graduation_date, gpa)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (first_name, last_name, email, phone, major, status, graduation_date, gpa)
        )
        connection.commit()
        connection.close()
    except sqlite3.Error as e:
        print(f"A SQLite error occurred during insertion: {e}")
