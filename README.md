# School-Database-Management-System-Project

<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>School Portal</title>
    <link rel="stylesheet" href="styles.css">
</head>
<body>
    <div class="container"
        <h1> School Registration Portal</h1>
        <p>Select a registration form below:</p>
        <a class="btn" href="student_regristration.html">Student Regirstration</a>
        <a class="btn" href="professor_registration.html">Professor Regirstration</a>
    </div>
</body>
</html>

<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Student Registration</title>
</head>
<body>
    <div class="container">
        <h2>Student Registration</h2>
       <form>
            <label>First Name</label>
            <input type="text" required>
            <label>Last Name</label>
            <input type="text" required>
            <label>Email</label>
            <input type="email" required>
            <label>Phone</label>
            <input type="text">
            <label>Major</label>
            <input type="text">
            <label>Status</label>
            <select>
                <option value="Full-time">Full-time</option>
                <option value="Part-time">Part-time</option>
            </select>
            <button type="submit">Register Student</button>
         </form>
        <a href="index.html" class="back"> Back to Homepage</a>
    </div>
</body>
</html>


#Employee Regristration
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Employee Registration</title>
    <link rel="stylesheet" href="styles.css">
</head>
<body>
    <div class="container">
        <h2>Employee Registration</h2>
        <form>
            <label>First Name</label>
            <input type="text" required>
            <label>Last Name</label>
            <input type="text" required>
            <label>Email</label>
            <input type="email" required>
            <label>Phone</label>
            <input type="text">
            <label>Department</label>
            <select>
                <option>Computer Science</option>
                <option>Mathematics</option>
                <option>Business</option>
                <option>Humanities</option>
            </select>
            <label>Position Title</label>
            <input type="text" placeholder="Employee, Class, etc.">
            <label>Hire Date</label>
            <input type="date">
            <button type="submit">Register Employee</button>
        </form>
        <a href="index.html" class="back"> Back to Homepage</a>
    </div>
</body>
</html>
