-- RESET DATABASE --
DROP TABLE IF EXISTS UserAccount;
DROP TABLE IF EXISTS Attendance;
DROP TABLE IF EXISTS Enrollment;
DROP TABLE IF EXISTS CourseSchedule;
DROP TABLE IF EXISTS CourseSelection;
DROP TABLE IF EXISTS CoursePrerequisite;
DROP TABLE IF EXISTS Course;
DROP TABLE IF EXISTS PerformanceReview;
DROP TABLE IF EXISTS Payroll;
DROP TABLE IF EXISTS EmployeeDepartmentAssignment;
DROP TABLE IF EXISTS Employee;
DROP TABLE IF EXISTS Student;
DROP TABLE IF EXISTS DepartmentBudget;
DROP TABLE IF EXISTS Department;
DROP TABLE IF EXISTS Room;
DROP TABLE IF EXISTS Building;

--   DATABASE STRUCTURE --
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
    building_id INTEGER NOT NULL,
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
    hire_date TEXT,
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

-- Course prerequisites --
CREATE TABLE CoursePrerequisite (
    prereq_id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER NOT NULL,
    prereq_course_id INTEGER NOT NULL,
    FOREIGN KEY (course_id) REFERENCES Course(course_id),
    FOREIGN KEY (prereq_course_id) REFERENCES Course(course_id)
);

-- Sections --
CREATE TABLE CourseSelection (
    selection_id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER NOT NULL,
    instructor_id INTEGER,
    room_id INTEGER,
    capacity INTEGER DEFAULT 30,
    FOREIGN KEY (course_id) REFERENCES Course(course_id),
    FOREIGN KEY (instructor_id) REFERENCES Employee(employee_id),
    FOREIGN KEY (room_id) REFERENCES Room(room_id)
);

-- Normalized schedule for each section --
-- One row per day-of-week per section --
CREATE TABLE CourseSchedule (
    schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
    selection_id INTEGER NOT NULL,
    day_code TEXT NOT NULL,    -- 'M', 'T', 'W', 'Th', 'F'
    start_time TEXT NOT NULL,  -- 'HH:MM'
    end_time TEXT NOT NULL,    -- 'HH:MM'
    FOREIGN KEY (selection_id) REFERENCES CourseSelection(selection_id)
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

-- Department budgets --
CREATE TABLE DepartmentBudget (
    budget_id INTEGER PRIMARY KEY AUTOINCREMENT,
    department_id INTEGER NOT NULL,
    fiscal_year TEXT NOT NULL,
    allocated_amount REAL NOT NULL,
    spent_amount REAL DEFAULT 0,
    FOREIGN KEY (department_id) REFERENCES Department(department_id)
);

-- Performance reviews --
CREATE TABLE PerformanceReview (
    review_id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL,
    review_date TEXT NOT NULL,
    rating INTEGER CHECK (rating BETWEEN 1 AND 5),
    comments TEXT,
    FOREIGN KEY (employee_id) REFERENCES Employee(employee_id)
);

-- Department assignment history for employees --
CREATE TABLE EmployeeDepartmentAssignment (
    assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL,
    department_id INTEGER NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT,
    FOREIGN KEY (employee_id) REFERENCES Employee(employee_id),
    FOREIGN KEY (department_id) REFERENCES Department(department_id)
);

-- Payroll table --
CREATE TABLE Payroll (
    payroll_id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL,
    pay_date TEXT NOT NULL,
    gross_amount REAL NOT NULL,
    deductions REAL DEFAULT 0,
    net_amount REAL NOT NULL,
    notes TEXT,
    FOREIGN KEY (employee_id) REFERENCES Employee(employee_id)
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

-- SAMPLE DATA FOR DEMO --
-- Departments --
INSERT INTO Department (department_name) VALUES
('Computer Science'),
('Mathematics'),
('Business'),
('Biology');

-- Buildings --
INSERT INTO Building (building_name) VALUES
('Science Hall'),
('Main Hall'),
('Business Center');

-- Rooms --
INSERT INTO Room (room_number, building_id) VALUES
('S101', 1),
('S202', 1),
('M110', 2),
('M205', 2),
('B215', 3);

-- Students --
INSERT INTO Student (first_name, last_name, email, major, status, gpa) VALUES
('Nathan', 'Henry', 'nhenry@example.edu', 'Computer Science', 'Full-time', 3.50),
('Sarah', 'Johnson', 'sjohnson@example.edu', 'Computer Science', 'Full-time', 3.70),
('Evan', 'Ramirez', 'eramirez@example.edu', 'Mathematics', 'Full-time', 3.10),
('Jasmine', 'Lee', 'jlee@example.edu', 'Business', 'Part-time', 3.90),
('Marcus', 'Wright', 'mwright@example.edu', 'Biology', 'Full-time', 2.80);

-- Employees / Instructors --
INSERT INTO Employee (first_name, last_name, email, position_title, department_id, salary, office_id, hire_date) VALUES
('Alice', 'Smith', 'asmith@example.edu', 'Professor',      1, 90000, 1, '2015-08-15'),
('Bob',   'Williams', 'bwilliams@example.edu', 'Associate Prof', 2, 85000, 2, '2017-01-10'),
('Carla', 'Young', 'cyoung@example.edu', 'Lecturer',       3, 60000, 3, '2020-09-01');

-- Department assignment history --
INSERT INTO EmployeeDepartmentAssignment (employee_id, department_id, start_date, end_date) VALUES
(1, 1, '2015-08-15', NULL),
(2, 2, '2017-01-10', NULL),
(3, 3, '2020-09-01', NULL);

-- Courses --
INSERT INTO Course (course_code, course_name, credit, department_id) VALUES
('CS101',   'Intro to Programming', 3, 1),
('CS201',   'Data Structures',      4, 1),
('MATH110', 'College Algebra',      3, 2),
('BUS205',  'Business Management',  3, 3);

-- CS201 requires CS101 as prerequisite --
INSERT INTO CoursePrerequisite (course_id, prereq_course_id) VALUES
((SELECT course_id FROM Course WHERE course_code = 'CS201'),
 (SELECT course_id FROM Course WHERE course_code = 'CS101'));

-- Sections (NO meeting_time column now) --
INSERT INTO CourseSelection (course_id, instructor_id, room_id, capacity) VALUES
((SELECT course_id FROM Course WHERE course_code='CS101'),   1, 1, 25),
((SELECT course_id FROM Course WHERE course_code='CS101'),   1, 2, 25),
((SELECT course_id FROM Course WHERE course_code='CS201'),   1, 1, 20),
((SELECT course_id FROM Course WHERE course_code='MATH110'), 2, 3, 30),
((SELECT course_id FROM Course WHERE course_code='BUS205'),  3, 5, 35);

-- Normalized CourseSchedule rows per section/day --
-- (selection_id 1–5 match inserts above in order) --
INSERT INTO CourseSchedule (selection_id, day_code, start_time, end_time) VALUES
(1, 'M',  '10:00', '11:30'),
(1, 'W',  '10:00', '11:30'),
(2, 'T',  '13:00', '14:30'),
(2, 'Th', '13:00', '14:30'),
(3, 'M',  '14:00', '15:30'),
(3, 'W',  '14:00', '15:30'),
(4, 'T',  '10:00', '11:15'),
(4, 'Th', '10:00', '11:15'),
(5, 'F',  '09:00', '12:00');

-- Enrollment with grades --
INSERT INTO Enrollment (student_id, selection_id, enrollment_date, grade) VALUES
(1, 1, DATE('now'), 95),
(1, 3, DATE('now'), 88),
(2, 1, DATE('now'), 92),
(3, 4, DATE('now'), 70),
(4, 5, DATE('now'), 99),
(5, 4, DATE('now'), 76);

-- Attendance --
INSERT INTO Attendance (student_id, selection_id, date, status) VALUES
(1, 1, DATE('now'), 'Present'),
(1, 3, DATE('now'), 'Late'),
(2, 1, DATE('now'), 'Absent'),
(3, 4, DATE('now'), 'Present');

-- Budgets --
INSERT INTO DepartmentBudget (department_id, fiscal_year, allocated_amount, spent_amount) VALUES
(1, '2024-2025', 250000, 120000),
(2, '2024-2025', 180000,  90000),
(3, '2024-2025', 150000,  60000),
(4, '2024-2025', 130000,  50000);

-- Performance Reviews --
INSERT INTO PerformanceReview (employee_id, review_date, rating, comments) VALUES
(1, '2024-03-01', 5, 'Outstanding teaching evaluations and research output.'),
(2, '2024-03-05', 4, 'Strong performance, recommended for promotion consideration.'),
(3, '2024-03-10', 3, 'Meets expectations; suggested to increase student engagement.');

-- Payroll sample data --
INSERT INTO Payroll (employee_id, pay_date, gross_amount, deductions, net_amount, notes) VALUES
(1, '2024-04-30', 7500, 500, 7000, 'Monthly salary'),
(2, '2024-04-30', 7000, 400, 6600, 'Monthly salary'),
(3, '2024-04-30', 5000, 300, 4700, 'Monthly salary');

-- Accounts --
INSERT INTO UserAccount (username, password, role)
VALUES ('admin', 'password', 'admin');

INSERT INTO UserAccount (username, password, role, student_id) VALUES
('nathan', 'password', 'student', 1),
('sarah',  'password', 'student', 2);

INSERT INTO UserAccount (username, password, role, employee_id) VALUES
('alice', 'password', 'instructor', 1),
('bob',   'password', 'instructor', 2);