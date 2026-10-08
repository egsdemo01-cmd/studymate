# StudyMate – Class 12 CBSE Student Study & Exam Management Portal
Flask + SQLite + HTML/CSS/JS web app: login/registration, dashboard with charts, subjects, marks calculator, timetable, tasks, exam countdown, notes (with search), study progress, profile, teacher demo panel, dark mode.

## Run on Windows
1. Install Python 3 from python.org (tick "Add Python to PATH").
2. Open Command Prompt in the `studymate` folder:
   ```
   pip install -r requirements.txt
   python app.py
   ```
3. Open http://127.0.0.1:5000 → Register a student. Teacher demo login: `teacher` / `teacher123`.
(The database `studymate.db` is created automatically. Charts need internet for Chart.js.)

## Database (SQLite)
users(id, username, password_hash, role) · profiles(user_id→users, name, class, school, roll, email, about) · subjects(id, user_id, name, teacher) · marks(subject_id, exam, obtained, total) · tasks(title, priority, deadline, done) · timetable(subject_id, date, start, end, topic) · exams(name, subject_id, date) · notes(subject_id, title, content) · study_progress(subject_id, done, remaining, hours). Every table has `user_id` (foreign key) so each student sees only their own data.

## Code idea (for viva)
`MODULES` dictionary describes each section's fields; three generic routes (`module`, `save`, `delete`) perform CRUD for all of them using SQL SELECT / INSERT / UPDATE / DELETE. Passwords are hashed (werkzeug); login uses Flask `session`; `@login_required` protects pages.

## Objectives & Future scope
Objectives: organise studies, track marks, never miss exams. Future: email reminders, PDF report cards, real teacher–student linking, MySQL.
