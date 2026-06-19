# -*- coding: utf-8 -*-
"""Database migration: add new columns to existing tables"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "app", "static", "qa_database.db")


def migrate():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}, will be created on startup.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get existing columns
    cursor.execute("PRAGMA table_info(pdf_files)")
    pdf_cols = [row[1] for row in cursor.fetchall()]

    cursor.execute("PRAGMA table_info(questions)")
    q_cols = [row[1] for row in cursor.fetchall()]

    # Add new columns to pdf_files
    if "pdf_type" not in pdf_cols:
        cursor.execute("ALTER TABLE pdf_files ADD COLUMN pdf_type VARCHAR(20) DEFAULT 'combined'")
        print("Added pdf_files.pdf_type")
    if "linked_pdf_id" not in pdf_cols:
        cursor.execute("ALTER TABLE pdf_files ADD COLUMN linked_pdf_id INTEGER REFERENCES pdf_files(id)")
        print("Added pdf_files.linked_pdf_id")

    # Add new columns to questions
    if "question_number" not in q_cols:
        cursor.execute("ALTER TABLE questions ADD COLUMN question_number VARCHAR(50) DEFAULT ''")
        print("Added questions.question_number")
    if "chapter" not in q_cols:
        cursor.execute("ALTER TABLE questions ADD COLUMN chapter VARCHAR(200) DEFAULT ''")
        print("Added questions.chapter")
    if "section" not in q_cols:
        cursor.execute("ALTER TABLE questions ADD COLUMN section VARCHAR(200) DEFAULT ''")
        print("Added questions.section")

    # Add async parsing status columns to pdf_files (for background parse progress)
    if "parse_status" not in pdf_cols:
        cursor.execute("ALTER TABLE pdf_files ADD COLUMN parse_status VARCHAR(20) DEFAULT 'pending'")
        print("Added pdf_files.parse_status")
    if "parse_progress" not in pdf_cols:
        cursor.execute("ALTER TABLE pdf_files ADD COLUMN parse_progress INTEGER DEFAULT 0")
        print("Added pdf_files.parse_progress")
    if "parsed_questions" not in pdf_cols:
        cursor.execute("ALTER TABLE pdf_files ADD COLUMN parsed_questions INTEGER DEFAULT 0")
        print("Added pdf_files.parsed_questions")
    if "parse_error" not in pdf_cols:
        cursor.execute("ALTER TABLE pdf_files ADD COLUMN parse_error TEXT DEFAULT ''")
        print("Added pdf_files.parse_error")

    conn.commit()
    conn.close()
    print("Migration completed successfully!")


if __name__ == "__main__":
    migrate()
