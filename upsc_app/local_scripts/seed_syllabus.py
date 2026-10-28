import sqlite3
from pathlib import Path

# Import the existing hardcoded syllabus data
# Change "your_app" to your Django app name.
# from syllabus.views import SYLLABUS


# --------------------------------------------------
# DATABASE
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "db.sqlite3"


# --------------------------------------------------
# CREATE DATABASE TABLES
# --------------------------------------------------

def create_tables(cursor):

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS syllabus_papers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code VARCHAR(50) NOT NULL UNIQUE,
            track VARCHAR(30) NOT NULL,
            name VARCHAR(255) NOT NULL,
            subtitle TEXT,
            color VARCHAR(30),

            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS syllabus_sections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            paper_id INTEGER NOT NULL,
            name VARCHAR(255) NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,

            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (paper_id)
                REFERENCES syllabus_papers(id)
                ON DELETE CASCADE,

            UNIQUE(paper_id, name)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS syllabus_points (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            section_id INTEGER NOT NULL,
            point TEXT NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,

            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (section_id)
                REFERENCES syllabus_sections(id)
                ON DELETE CASCADE
        )
    """)


# --------------------------------------------------
# CREATE INDEXES
# --------------------------------------------------

def create_indexes(cursor):

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_papers_track
        ON syllabus_papers(track)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_sections_paper
        ON syllabus_sections(paper_id)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_sections_paper_order
        ON syllabus_sections(paper_id, sort_order)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_points_section
        ON syllabus_points(section_id)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_points_section_order
        ON syllabus_points(section_id, sort_order)
    """)


# --------------------------------------------------
# INSERT SYLLABUS
# --------------------------------------------------

def insert_syllabus(cursor):

    papers_inserted = 0
    sections_inserted = 0
    points_inserted = 0

    for paper in SYLLABUS:

        # ------------------------------------------
        # PAPER
        # ------------------------------------------

        cursor.execute("""
            INSERT OR IGNORE INTO syllabus_papers
                (code, track, name, subtitle, color)
            VALUES
                (?, ?, ?, ?, ?)
        """, (
            paper["id"],
            paper["track"],
            paper["name"],
            paper.get("subtitle"),
            paper.get("color"),
        ))

        # Get paper ID
        cursor.execute("""
            SELECT id
            FROM syllabus_papers
            WHERE code = ?
        """, (paper["id"],))

        paper_id = cursor.fetchone()[0]

        papers_inserted += 1

        # ------------------------------------------
        # SECTIONS
        # ------------------------------------------

        for section_order, section in enumerate(
            paper["topics"],
            start=1
        ):

            cursor.execute("""
                INSERT OR IGNORE INTO syllabus_sections
                    (paper_id, name, sort_order)
                VALUES
                    (?, ?, ?)
            """, (
                paper_id,
                section["name"],
                section_order,
            ))

            # Get section ID
            cursor.execute("""
                SELECT id
                FROM syllabus_sections
                WHERE paper_id = ?
                  AND name = ?
            """, (
                paper_id,
                section["name"],
            ))

            section_id = cursor.fetchone()[0]

            sections_inserted += 1

            # --------------------------------------
            # POINTS
            # --------------------------------------

            for point_order, point in enumerate(
                section["points"],
                start=1
            ):

                cursor.execute("""
                    INSERT OR IGNORE INTO syllabus_points
                        (section_id, point, sort_order)
                    VALUES
                        (?, ?, ?)
                """, (
                    section_id,
                    point,
                    point_order,
                ))

                points_inserted += 1

    return (
        papers_inserted,
        sections_inserted,
        points_inserted,
    )


# --------------------------------------------------
# MAIN
# --------------------------------------------------

def main():

    print("=" * 60)
    print("UPSC SYLLABUS DATABASE SEEDER")
    print("=" * 60)

    print(f"\nDatabase: {DB_PATH}")

    connection = sqlite3.connect(DB_PATH)

    # Enable foreign keys
    connection.execute("PRAGMA foreign_keys = ON")

    try:

        cursor = connection.cursor()

        # cursor.execute("""
        #         drop table pyq_questions""")

        # # Create tables
        # print("\nCreating tables...")
        # create_tables(cursor)

        # # Create indexes
        # print("Creating indexes...")
        # create_indexes(cursor)

        # # Insert data
        # print("Inserting syllabus data...")

        # (
        #     papers,
        #     sections,
        #     points,
        # ) = insert_syllabus(cursor)

        connection.commit()

        print("\nSUCCESS")
        # print("-" * 60)
        # print(f"Papers inserted   : {papers}")
        # print(f"Sections inserted : {sections}")
        # print(f"Points inserted   : {points}")
        # print("-" * 60)

    except Exception as e:

        connection.rollback()

        print("\nERROR")
        print("-" * 60)
        print(e)
        print("-" * 60)

        raise

    finally:
        connection.close()


if __name__ == "__main__":
    main()