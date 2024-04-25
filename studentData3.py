import os
import sqlite3
import streamlit as st
from dotenv import load_dotenv
import google.generativeai as genai
import logging
import re
import numpy as np

# Set up logging for debugging
logging.basicConfig(level=logging.INFO)

# Load environment variables
load_dotenv()  # Ensure .env file with the API key is present
genai.configure(api_key=os.getenv("MY_API_KEY"))

def extract_student_info(content_text):
    # Helper function to extract a specific field using a pattern
    def extract_field(pattern, text, default=None):
        match = re.search(pattern, text)
        return match.group(1).strip() if match else default

    # Extract basic fields
    student_info = {}
    student_info["name"] = extract_field(r"\*\*Name:\*\* (.+)", content_text, default="Unknown")
    student_info["age"] = int(extract_field(r"\*\*Age:\*\* (\d+)", content_text, default="0"))
    student_info["marks"] = int(extract_field(r"\*\*Marks:\*\* (\d+)", content_text, default="0"))
    student_info["department"] = extract_field(r"\*\*Department:\*\* (.+)", content_text, default="Unknown")

    # Extract hobbies and sports
    try:
        hobbies_section = content_text.split("**Hobbies:**")[1].split("**Sport:**")[0]
        hobbies = [item.strip("* ").strip() for item in hobbies_section.split("\n") if item.strip()]
    except (IndexError, AttributeError):
        hobbies = []

    try:
        sports_section = content_text.split("**Sport:**")[1]
        sports = [item.strip("* ").strip() for item in sports_section.split("\n") if item.strip()]
    except (IndexError, AttributeError):
        sports = []

    # Store the extracted hobbies and sports as comma-separated strings
    student_info["hobbies"] = ", ".join(hobbies)
    student_info["sport"] = ", ".join(sports)

    return student_info

# Function to generate a random student profile
def generate_student_profile():
    prompt = (
        "Generate a student profile with the following information: "
        "1. Name "
        "2. Age (between 18 and 30) "
        "3. Marks (between 50 and 100) "
        "4. Department (from a list of common departments like Computer Science,Electrical, Mechanical, Aeronautical Physics, Electronics and Communication, Artificial Intelligence, Cyber Security etc.) "
        "5. Hobbies (like reading, swimming, cooking, etc.) "
        "6. Sport (like football, cricket, basketball, etc.)"
    )
    
    model = genai.GenerativeModel("gemini-pro")
    response = model.generate_content([prompt])
    try:
        candidates = response.candidates
        if candidates and len(candidates) > 0:
            candidate = candidates[0]
            parts = candidate.content.parts if hasattr(candidate.content, "parts") else []
            if parts and len(parts) > 0:
                student_text = parts[0].text.strip()  # The raw generated text
                student_info = extract_student_info(student_text)  # Extract information
                return student_info
        else:
            logging.warning("No valid candidates found in the response.")
            return None

    except Exception as e:
        logging.error("Error generating student profile: %s", str(e))
        return None

# Function to insert generated records into the SQLite database
def insert_generated_records(db_path, num_records):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Ensure the table exists with additional fields
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS student (
            ID INTEGER PRIMARY KEY,
            NAME TEXT,
            AGE INTEGER,
            MARKS INTEGER,
            DEPARTMENT TEXT,
            HOBBY TEXT,
            SPORT TEXT
        )
        """
    )

    # Insert generated records into the database
    for _ in range(num_records):
        student = generate_student_profile()  # Get a generated student profile
        if not student:
            st.warning("Could not generate a student profile. Skipping record.")
            continue

        cur.execute(
            "INSERT INTO student (NAME, AGE, MARKS, DEPARTMENT, HOBBY, SPORT) VALUES (?, ?, ?, ?, ?, ?)",
            (
                student["name"],
                student["age"],
                student["marks"],
                student["department"],
                student["hobbies"],
                student["sport"],
            ),
        )

    conn.commit()
    conn.close()

# Function to fetch records from the SQLite database
def fetch_records(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT * FROM student")
    records = cur.fetchall()
    conn.close()
    return records

# Function to answer questions based on student data
def answer_question(question, records):
    if "average age" in question.lower():
        ages = [record[2] for record in records]
        average_age = np.mean(ages)
        return f"The average age of the students is {average_age:.2f} years."

    elif "highest marks" in question.lower():
        marks = [record[3] for record in records]
        highest_marks = max(marks)
        return f"The highest marks achieved is {highest_marks}."

    elif "students in the computer science department" in question.lower():
        computer_science_students = sum(1 for record in records if "computer science" in record[4].lower())
        return f"There are {computer_science_students} students in the Computer Science department."

    elif "common hobbies" in question.lower():
        hobbies = [record[5] for record in records]
        all_hobbies = [hobby.strip() for sublist in hobbies for hobby in sublist.split(",")]
        common_hobbies = max(set(all_hobbies), key=all_hobbies.count)
        return f"The most common hobby among students is {common_hobbies}."

    elif "distribution of marks" in question.lower():
        marks = [record[3] for record in records]
        mark_distribution = dict()
        for mark in marks:
            mark_distribution[mark] = mark_distribution.get(mark, 0) + 1
        return mark_distribution

    elif "highest average marks" in question.lower():
        departments = set(record[4] for record in records)
        marks_by_department = {department: [] for department in departments}
        for record in records:
            marks_by_department[record[4]].append(record[3])
        highest_average_marks_department = max(marks_by_department, key=lambda x: np.mean(marks_by_department[x]))
        return f"The department with the highest average marks is {highest_average_marks_department}."

    elif "all student names" in question.lower():
        names = set(record[1] for record in records)
        return list(names)
    
    elif "all student ages" in question.lower():
        ages = set(record[2] for record in records)
        return list(ages)
    
    elif "all student hobbies" in question.lower():
        hobbies = [hobby.strip() for record in records for hobby in record[5].split(",")]
        return list(set(hobbies))
    
    elif "all student departments" in question.lower():
        departments = set(record[4] for record in records)
        return list(departments)
    
    elif "all student sports" in question.lower():
        sports = [sport.strip() for record in records for sport in record[6].split(",")]
        return list(set(sports))

    else:
        return "Sorry, I couldn't understand the question."

# Streamlit app setup
st.set_page_config(page_title="Generate Student Profiles with Google Gemini")
st.header("Generate Student Profiles")

# User input for the number of random records to generate
num_records = st.number_input("Enter the number of random records to generate:", min_value=1, step=1)

# Button to generate records
if st.button("Generate Student Profiles"):
    insert_generated_records("student.db", num_records)
    st.success(f"Inserted {num_records} generated student records into the SQLite database.")

# Button to display records
if st.button("Display Records"):
    records = fetch_records("student.db")
    if records:
        st.subheader("Student Records")
        st.table(records[:num_records])  # Display only the specified number of records
    else:
        st.warning("No records found in the database.")

# Input box to ask a question
question = st.text_input("Ask a question about the student data:")

# Answer to the asked question
if question:
    records = fetch_records("student.db")
    answer = answer_question(question, records)
    st.subheader("Answer")
    if isinstance(answer, list):
        st.write("Student Names:")
        for name in answer:
            st.write(name)
    elif isinstance(answer, dict):
        st.write("Distribution of marks:")
        for mark, count in answer.items():
            st.write(f"Mark: {mark}, Count: {count}")
    else:
        st.write(answer)

