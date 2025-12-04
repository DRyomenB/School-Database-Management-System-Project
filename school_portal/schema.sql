-- =========================================
--   DROP EXISTING TABLES (RESET DATABASE)
-- =========================================
DROP TABLE IF EXISTS UserAccount;
DROP TABLE IF EXISTS Attendance;
DROP TABLE IF EXISTS Enrollment;
DROP TABLE IF EXISTS CourseSelection;
DROP TABLE IF EXISTS Course;
DROP TABLE IF EXISTS Student;
DROP TABLE IF EXISTS Employee;
DROP TABLE IF EXISTS Department;
DROP TABLE IF EXISTS Room;
DROP TABLE IF EXISTS Building;


-- =========================================
--   DATABASE STRUCTURE
-- =========================================

CREATE TABLE Department (
    department_id INTEGER PRIMARY KEY AUTOINCREMENT,
    department_name TEXT NOT NULL UNIQUE
);

CREATE TABLE Building (
    building_id INTEGER PRIMARY KEY AUTOINCREMENT,
    building_name TEXT NOT NULL UNIQUE
);

CREATE TABLE Room (
    room_id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_number TEXT NOT NULL,
    building_id INTEGER,
    FOREIGN KEY (building_id) REFERENCES Building(building_id)
);

CREATE TABLE Student (
    student_id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT UNIQUE,
    major TEXT,
    status TEXT,
    gpa REAL DEFAULT NULL
);

CREATE TABLE Employee (
    employee_id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT UNIQUE,
    position_title TEXT,
    department_id INTEGER,
    salary REAL,
    office_id INTEGER,
    FOREIGN KEY (department_id) REFERENCES Department(department_id),
    FOREIGN KEY (office_id) REFERENCES Room(room_id)
);

CREATE TABLE Course (
    course_id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_code TEXT NOT NULL UNIQUE,
    course_name TEXT NOT NULL,
    credit INTEGER,
    department_id INTEGER,
    FOREIGN KEY (department_id) REFERENCES Department(department_id)
);

CREATE TABLE CourseSelection (
    selection_id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER NOT NULL,
    instructor_id INTEGER,
    room_id INTEGER,
    meeting_time TEXT,
    capacity INTEGER DEFAULT 30, -- NEW capacity
    FOREIGN KEY (course_id) REFERENCES Course(course_id),
    FOREIGN KEY (instructor_id) REFERENCES Employee(employee_id),
    FOREIGN KEY (room_id) REFERENCES Room(room_id)
);

CREATE TABLE Enrollment (
    enrollment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    selection_id INTEGER NOT NULL,
    enrollment_date TEXT,
    grade REAL,
    FOREIGN KEY (student_id) REFERENCES Student(student_id),
    FOREIGN KEY (selection_id) REFERENCES CourseSelection(selection_id)
);

CREATE TABLE Attendance (
    attendance_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    selection_id INTEGER NOT NULL,
    date TEXT,
    status TEXT CHECK(status IN ('Present', 'Absent', 'Late')),
    FOREIGN KEY (student_id) REFERENCES Student(student_id),
    FOREIGN KEY (selection_id) REFERENCES CourseSelection(selection_id)
);

CREATE TABLE UserAccount (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('admin', 'student', 'instructor')),
    student_id INTEGER,
    employee_id INTEGER,
    FOREIGN KEY (student_id) REFERENCES Student(student_id),
    FOREIGN KEY (employee_id) REFERENCES Employee(employee_id)
);


-- =========================================
--   SEED SAMPLE DATA FOR DEMO
-- =========================================

INSERT INTO Department (department_name) VALUES
('Computer Science'),
('Mathematics'),
('Business'),
('Biology');

INSERT INTO Building (building_name) VALUES
('Science Hall'),
('Main Hall'),
('Business Center');

INSERT INTO Room (room_number, building_id) VALUES
('S101', 1),
('S202', 1),
('M110', 2),
('M205', 2),
('B215', 3);

-- Sample Students
INSERT INTO Student (first_name, last_name, email, major, status, gpa) VALUES
('Nathan', 'Henry', 'nhenry@example.edu', 'Computer Science', 'Full-time', 3.50),
('Sarah', 'Johnson', 'sjohnson@example.edu', 'Computer Science', 'Full-time', 3.70),
('Evan', 'Ramirez', 'eramirez@example.edu', 'Mathematics', 'Full-time', 3.10),
('Jasmine', 'Lee', 'jlee@example.edu', 'Business', 'Part-time', 3.90),
('Marcus', 'Wright', 'mwright@example.edu', 'Biology', 'Full-time', 2.80);

-- Sample Instructors
INSERT INTO Employee (first_name, last_name, email, position_title, department_id, salary, office_id) VALUES
('Alice', 'Smith', 'asmith@example.edu', 'Professor', 1, 90000, 1),
('Bob', 'Williams', 'bwilliams@example.edu', 'Associate Prof', 2, 85000, 2),
('Carla', 'Young', 'cyoung@example.edu', 'Lecturer', 3, 60000, 3);

-- Courses
INSERT INTO Course (course_code, course_name, credit, department_id) VALUES
('CS101', 'Intro to Programming', 3, 1),
('CS201', 'Data Structures', 4, 1),
('MATH110', 'College Algebra', 3, 2),
('BUS205', 'Business Management', 3, 3);

-- Class Sections (with updated Thursday abbreviation)
INSERT INTO CourseSelection (course_id, instructor_id, room_id, meeting_time, capacity) VALUES
(1, 1, 1, 'MW 10:00-11:30', 25),
(1, 1, 2, 'TTh 13:00-14:30', 25),
(2, 1, 1, 'MW 14:00-15:30', 20),
(3, 2, 3, 'TTh 10:00-11:15', 30),
(4, 3, 5, 'F 09:00-12:00', 35);

-- Enrollment Example Data
INSERT INTO Enrollment (student_id, selection_id, enrollment_date, grade) VALUES
(1, 1, DATE('now'), 95),
(1, 3, DATE('now'), 88),
(2, 1, DATE('now'), 92),
(3, 4, DATE('now'), 70),
(4, 5, DATE('now'), 99),
(5, 4, DATE('now'), 76);

-- Attendance Example Data
INSERT INTO Attendance (student_id, selection_id, date, status) VALUES
(1, 1, DATE('now'), 'Present'),
(1, 3, DATE('now'), 'Late'),
(2, 1, DATE('now'), 'Absent'),
(3, 4, DATE('now'), 'Present');

-- System Accounts
INSERT INTO UserAccount (username, password, role)
VALUES ('admin', 'password', 'admin');

INSERT INTO UserAccount (username, password, role, student_id) VALUES
('nathan', 'password', 'student', 1),
('sarah', 'password', 'student', 2);

INSERT INTO UserAccount (username, password, role, employee_id) VALUES
('alice', 'password', 'instructor', 1),
('bob', 'password', 'instructor', 2);