import { useEffect, useState } from "react";
import "./App.css";

const API = "http://127.0.0.1:8000";

async function api(path, options = {}, token = localStorage.getItem("sms_token") || "") {
  const response = await fetch(`${API}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
  return data;
}

const blankStudent = { name: "", email: "", phone: "", department: "", course: "" };
const blankCourse = { name: "", code: "", department: "", description: "" };
const blankBranch = { name: "", code: "", location: "", description: "" };
const blankAttendance = { student_id: "", student_name: "", attendance_date: new Date().toLocaleDateString("en-CA"), status: "Present", remarks: "" };
const blankFee = { student_id: "", student_name: "", academic_year: "2026-2027", total_fee: "", amount_paid: "0", due_date: new Date().toLocaleDateString("en-CA"), payment_method: "Cash", remarks: "" };

export default function App() {
  const [token, setToken] = useState(localStorage.getItem("sms_token") || "");
  const [user, setUser] = useState(null);
  const [page, setPage] = useState("dashboard");
  const [mode, setMode] = useState("login");
  const [auth, setAuth] = useState({ name: "", email: "", password: "" });
  const [students, setStudents] = useState([]);
  const [courses, setCourses] = useState([]);
  const [branches, setBranches] = useState([]);
  const [attendanceRecords, setAttendanceRecords] = useState([]);
  const [allAttendanceRecords, setAllAttendanceRecords] = useState([]);
  const [attendanceFilterDate, setAttendanceFilterDate] = useState("");
  const [reportMonth, setReportMonth] = useState("10");
  const [reportYear, setReportYear] = useState("2026");
  const [student, setStudent] = useState(blankStudent);
  const [course, setCourse] = useState(blankCourse);
  const [editStudent, setEditStudent] = useState(null);
  const [editCourse, setEditCourse] = useState(null);
  const [branch, setBranch] = useState(blankBranch);
  const [editBranch, setEditBranch] = useState(null);
  const [attendance, setAttendance] = useState(blankAttendance);
  const [editAttendance, setEditAttendance] = useState(null);
  const [feeRecords, setFeeRecords] = useState([]);
  const [fee, setFee] = useState(blankFee);
  const [editFee, setEditFee] = useState(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const todayDate = new Date().toLocaleDateString("en-CA");
  const todayAttendance = attendanceRecords.filter(
    r => r.attendance_date === todayDate
  );
  const todayPresent = todayAttendance.filter(r => r.status === "Present").length;
  const todayAbsent = todayAttendance.filter(r => r.status === "Absent").length;
  const todayLate = todayAttendance.filter(r => r.status === "Late").length;
  const todayMarkedStudentIds = new Set(
    todayAttendance.map(r => String(r.student_id))
  );
  const todayNotMarked = students.filter(
    st => !todayMarkedStudentIds.has(String(st.id))
  ).length;
  const todayAttendancePercentage = todayAttendance.length
    ? ((todayPresent / todayAttendance.length) * 100).toFixed(1)
    : "0.0";


  function notify(text = "", isError = false) {
    setMessage(isError ? "" : text);
    setError(isError ? text : "");
  }

  async function refreshData() {
    const [s, c, b, a, f] = await Promise.all([
      api("/students"),
      api("/courses"),
      api("/branches"),
      api("/attendance"),
      api("/fees"),
    ]);
    setStudents(Array.isArray(s) ? s : []);
    setCourses(Array.isArray(c) ? c : []);
    setBranches(Array.isArray(b) ? b : []);
    setAttendanceRecords(Array.isArray(a) ? a : []);
    setAllAttendanceRecords(Array.isArray(a) ? a : []);
    setFeeRecords(Array.isArray(f) ? f : []);
  }

  useEffect(() => {
    if (!token) return;
    let active = true;

    api("/auth/me", {}, token)
      .then(async profile => {
        if (!active) return;
        setUser(profile);
        try {
          await refreshData();
        } catch (e) {
          if (active) notify(`Could not load records: ${e.message}`, true);
        }
      })
      .catch(() => {
        if (!active) return;
        localStorage.removeItem("sms_token");
        setToken("");
        setUser(null);
      });

    return () => { active = false; };
  }, [token]);

  async function submitAuth(e) {
    e.preventDefault();
    setBusy(true);
    notify();

    try {
      if (mode === "register") {
        await api("/auth/register", {
          method: "POST",
          body: JSON.stringify(auth),
        });
        notify("Account created! Please sign in.");
        setMode("login");
        setAuth({ ...auth, password: "" });
      } else {
        const result = await api("/auth/login", {
          method: "POST",
          body: JSON.stringify({ email: auth.email, password: auth.password }),
        });
        localStorage.setItem("sms_token", result.access_token);
        setUser(await api("/auth/me", {}, result.access_token));
        setToken(result.access_token);
      }
    } catch (e) {
      notify(e.message, true);
    } finally {
      setBusy(false);
    }
  }

  function logout() {
    localStorage.removeItem("sms_token");
    setToken("");
    setUser(null);
    setPage("dashboard");
    notify("Signed out.");
  }

  async function saveStudent(e) {
    e.preventDefault();
    setBusy(true);
    notify();

    try {
      await api(editStudent ? `/students/${editStudent}` : "/students", {
        method: editStudent ? "PUT" : "POST",
        body: JSON.stringify(student),
      });
      setStudent(blankStudent);
      setEditStudent(null);
      await refreshData();
      notify("Student saved successfully.");
    } catch (e) {
      notify(e.message, true);
    } finally {
      setBusy(false);
    }
  }

  async function removeStudent(id) {
    if (!window.confirm("Delete this student record?")) return;
    try {
      await api(`/students/${id}`, { method: "DELETE" });
      await refreshData();
      notify("Student deleted.");
    } catch (e) {
      notify(e.message, true);
    }
  }

  async function saveCourse(e) {
    e.preventDefault();
    setBusy(true);
    notify();

    try {
      await api(editCourse ? `/courses/${editCourse}` : "/courses", {
        method: editCourse ? "PUT" : "POST",
        body: JSON.stringify(course),
      });
      setCourse(blankCourse);
      setEditCourse(null);
      await refreshData();
      notify("Course saved successfully.");
    } catch (e) {
      notify(e.message, true);
    } finally {
      setBusy(false);
    }
  }

  async function removeCourse(id) {
    if (!window.confirm("Delete this course?")) return;
    try {
      await api(`/courses/${id}`, { method: "DELETE" });
      await refreshData();
      notify("Course deleted.");
    } catch (e) {
      notify(e.message, true);
    }
  }

  async function saveBranch(e) {
    e.preventDefault();
    setBusy(true);
    notify();

    try {
      await api(editBranch ? `/branches/${editBranch}` : "/branches", {
        method: editBranch ? "PUT" : "POST",
        body: JSON.stringify(branch),
      });
      setBranch(blankBranch);
      setEditBranch(null);
      await refreshData();
      notify("Branch saved successfully.");
    } catch (e) {
      notify(e.message, true);
    } finally {
      setBusy(false);
    }
  }

  async function removeBranch(id) {
    if (!window.confirm("Delete this branch?")) return;

    try {
      await api(`/branches/${id}`, { method: "DELETE" });
      await refreshData();
      notify("Branch deleted.");
    } catch (e) {
      notify(e.message, true);
    }
  }

  function exportAttendanceCSV() {
    if (!attendanceRecords.length) {
      notify("No attendance records to export.", true);
      return;
    }

    const columns = [
      "Student ID",
      "Student Name",
      "Attendance Date",
      "Status",
      "Remarks",
    ];

    const escapeCSV = value =>
      '"' + String(value ?? "").replace(/"/g, '""') + '"';

    const rows = attendanceRecords.map(r => [
      r.student_id,
      r.student_name,
      r.attendance_date,
      r.status,
      r.remarks || "",
    ]);

    const csv = [columns, ...rows]
      .map(row => row.map(escapeCSV).join(","))
      .join("\\r\\n");

    const blob = new Blob(["\\uFEFF", csv], {
      type: "text/csv;charset=utf-8;",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "attendance_report.csv";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);

    notify("Attendance CSV exported successfully.");
  }

  async function filterAttendance() {
    try {
      const path = attendanceFilterDate
        ? `/attendance?attendance_date=${encodeURIComponent(attendanceFilterDate)}`
        : "/attendance";
      const records = await api(path);
      setAttendanceRecords(Array.isArray(records) ? records : []);
      notify(attendanceFilterDate ? "Attendance filtered by date." : "Showing all attendance records.");
    } catch (e) {
      notify(e.message, true);
    }
  }

  async function saveAttendance(e) {
    e.preventDefault();
    setBusy(true);
    notify();

    try {
      const payload = {
        ...attendance,
        student_id: Number(attendance.student_id),
      };

      await api(
        editAttendance ? `/attendance/${editAttendance}` : "/attendance",
        {
          method: editAttendance ? "PUT" : "POST",
          body: JSON.stringify(payload),
        }
      );

      setAttendance(blankAttendance);
      setEditAttendance(null);
      await refreshData();
      notify("Attendance saved successfully.");
    } catch (e) {
      notify(e.message, true);
    } finally {
      setBusy(false);
    }
  }

  async function removeAttendance(id) {
    if (!window.confirm("Delete this attendance record?")) return;

    try {
      await api(`/attendance/${id}`, { method: "DELETE" });
      await refreshData();
      notify("Attendance record deleted.");
    } catch (e) {
      notify(e.message, true);
    }
  }


  async function saveFee(e) {
    e.preventDefault();
    setBusy(true);
    notify();

    try {
      const payload = {
        ...fee,
        student_id: Number(fee.student_id),
        total_fee: Number(fee.total_fee),
        amount_paid: Number(fee.amount_paid),
      };

      await api(editFee ? `/fees/${editFee}` : "/fees", {
        method: editFee ? "PUT" : "POST",
        body: JSON.stringify(payload),
      });

      setFee(blankFee);
      setEditFee(null);
      await refreshData();
      notify("Fee record saved successfully.");
    } catch (e) {
      notify(e.message, true);
    } finally {
      setBusy(false);
    }
  }

  async function removeFee(id) {
    if (!window.confirm("Delete this fee record?")) return;

    try {
      await api(`/fees/${id}`, { method: "DELETE" });
      await refreshData();
      notify("Fee record deleted.");
    } catch (e) {
      notify(e.message, true);
    }
  }

  if (!token || !user) {
    return (
      <main className="auth-screen">
        <section className="auth-card">
          <div className="logo">S</div>
          <p className="eyebrow">STUDENT MANAGEMENT SYSTEM</p>
          <h1>{mode === "login" ? "Welcome back" : "Create your account"}</h1>
          <p className="subtitle">Sign in to your academic workspace.</p>
          <form onSubmit={submitAuth}>
            {mode === "register" && (
              <label>Full name
                <input required minLength="2" value={auth.name}
                  onChange={e => setAuth({ ...auth, name: e.target.value })}
                  placeholder="Enter your name" />
              </label>
            )}
            <label>Email address
              <input required type="email" value={auth.email}
                onChange={e => setAuth({ ...auth, email: e.target.value })}
                placeholder="you@example.com" />
            </label>
            <label>Password
              <input required minLength="8" maxLength="72" type="password"
                value={auth.password}
                onChange={e => setAuth({ ...auth, password: e.target.value })}
                placeholder="At least 8 characters" />
            </label>
            {error && <p className="error">{error}</p>}
            {message && <p className="success">{message}</p>}
            <button className="primary full" disabled={busy}>
              {busy ? "Please wait..." : mode === "login" ? "Sign in →" : "Create account →"}
            </button>
          </form>
          <p className="switch">
            {mode === "login" ? "Don't have an account?" : "Already registered?"}
            <button onClick={() => { setMode(mode === "login" ? "register" : "login"); notify(); }}>
              {mode === "login" ? " Register" : " Sign in"}
            </button>
          </p>
        </section>
      </main>
    );
  }

  return (
    <main className="dashboard">
      <aside className="sidebar">
        <h2>Campus<span>Desk</span></h2>
        <p>STUDENT MANAGEMENT</p>
        {[
          ["dashboard", "▦", "Dashboard"],
          ["students", "♙", "Students"],
          ["courses", "▤", "Courses"],
          ["branches", "⌂", "Branches"],
          ["attendance", "✓", "Attendance"],
 ["fees", "$", "Fee Payment"],
        ].map(([id, icon, label]) => (
          <button key={id}
            className={page === id ? "selected nav-button" : "nav-button"}
            onClick={() => { setPage(id); notify(); }}>
            {icon} &nbsp; {label}
          </button>
        ))}
        <button className="logout" onClick={logout}>↪ &nbsp; Sign out</button>
      </aside>

      <section className="main">
        <header>
          <div><small>CAMPUS WORKSPACE</small>
            <h1>{page === "dashboard" ? "Dashboard" : page === "students" ? "Students" : page === "courses" ? "Courses" : page === "branches" ? "Branches" : page === "fees" ? "Fee Payment" : "Attendance"}</h1>
          </div>
          <span className="badge">{user.name}</span>
        </header>

        {error && <p className="error">{error}</p>}
        {message && <p className="success">{message}</p>}

        {page === "dashboard" && <>
          <div className="welcome">
            <small>YOUR ACADEMIC WORKSPACE</small>
            <h2>Welcome, {user.name} 👋</h2>
            <p>Manage student records and courses in one place.</p>
          </div>
          <div className="cards">
            <article><span>♙</span><p>Total students</p><h2>{students.length}</h2></article>
            <article><span>▤</span><p>Available courses</p><h2>{courses.length}</h2></article>
            <article><span>▦</span><p>Microservices</p><h2>5</h2></article>
            <article><span>✓</span><p>Present</p><h2>{todayPresent}</h2></article>
            <article><span>−</span><p>Absent</p><h2>{todayAbsent}</h2></article>
            <article><span>◷</span><p>Late</p><h2>{todayLate}</h2></article>
            <article><span>%</span><p>Today's attendance</p><h2>{todayAttendancePercentage}%</h2></article>
            <article><span>○</span><p>Not marked today</p><h2>{todayNotMarked}</h2></article>
          </div>
          <article className="info">
            <h3>Recent students</h3>
            <RecordTable type="student" items={students.slice(0, 5)} />
            <button className="primary" onClick={() => setPage("students")}>Manage students</button>
          </article>
        </>}

        {page === "students" && <div className="manage-grid">
          <form className="info" onSubmit={saveStudent}>
            <h3>{editStudent ? "Edit student" : "Add student"}</h3>
            {[
              ["name", "Full name"],
              ["email", "Email address"],
              ["phone", "Phone number"],
              ["department", "Department"],
              ["course", "Course"],
            ].map(([key, label]) => (
              <label key={key}>{label}
                <input required type={key === "email" ? "email" : "text"}
                  value={student[key]}
                  onChange={e => setStudent({ ...student, [key]: e.target.value })}
                  placeholder={label} />
              </label>
            ))}
            <button className="primary" disabled={busy}>{editStudent ? "Save changes" : "Add student"}</button>
            {editStudent && <button type="button" className="secondary"
              onClick={() => { setEditStudent(null); setStudent(blankStudent); }}>Cancel</button>}
          </form>
          <article className="info">
            <h3>Student records ({students.length})</h3>
            <RecordTable type="student" items={students}
              onEdit={s => {
                setStudent({ name: s.name, email: s.email, phone: s.phone,
                  department: s.department, course: s.course });
                setEditStudent(s.id);
              }}
              onDelete={removeStudent} />
          </article>
        </div>}

        {page === "courses" && <div className="manage-grid">
          <form className="info" onSubmit={saveCourse}>
            <h3>{editCourse ? "Edit course" : "Add course"}</h3>
            {[
              ["name", "Course name"],
              ["code", "Course code"],
              ["department", "Department"],
            ].map(([key, label]) => (
              <label key={key}>{label}
                <input required value={course[key]}
                  onChange={e => setCourse({ ...course, [key]: e.target.value })}
                  placeholder={label} />
              </label>
            ))}
            <label>Description
              <input value={course.description}
                onChange={e => setCourse({ ...course, description: e.target.value })}
                placeholder="Course description (optional)" />
            </label>
            <button className="primary" disabled={busy}>{editCourse ? "Save changes" : "Add course"}</button>
            {editCourse && <button type="button" className="secondary"
              onClick={() => { setEditCourse(null); setCourse(blankCourse); }}>Cancel</button>}
          </form>
          <article className="info">
            <h3>Available courses ({courses.length})</h3>
            <RecordTable type="course" items={courses}
              onEdit={c => {
                setCourse({ name: c.name, code: c.code, department: c.department,
                  description: c.description || "" });
                setEditCourse(c.id);
              }}
              onDelete={removeCourse} />
          </article>
        </div>}
        {page === "branches" && <div className="manage-grid">
          <form className="info" onSubmit={saveBranch}>
            <h3>{editBranch ? "Edit branch" : "Add branch"}</h3>
            {[
              ["name", "Branch name"],
              ["code", "Branch code"],
              ["location", "Location"],
            ].map(([key, label]) => (
              <label key={key}>{label}
                <input required value={branch[key]}
                  onChange={e => setBranch({ ...branch, [key]: e.target.value })}
                  placeholder={label} />
              </label>
            ))}
            <label>Description
              <input value={branch.description}
                onChange={e => setBranch({ ...branch, description: e.target.value })}
                placeholder="Description (optional)" />
            </label>
            <button className="primary" disabled={busy}>
              {editBranch ? "Save changes" : "Add branch"}
            </button>
            {editBranch && <button type="button" className="secondary"
              onClick={() => { setEditBranch(null); setBranch(blankBranch); }}>
              Cancel
            </button>}
          </form>

          <article className="info">
            <h3>Branches ({branches.length})</h3>
            {!branches.length ? <p className="subtitle">No branches yet.</p> : (
              <div style={{ overflowX: "auto" }}>
                <table>
                  <thead><tr>
                    <th>BRANCH</th><th>CODE</th><th>LOCATION</th>
                    <th>DESCRIPTION</th><th>ACTIONS</th>
                  </tr></thead>
                  <tbody>
                    {branches.map(b => <tr key={b.id}>
                      <td>{b.name}</td><td>{b.code}</td><td>{b.location}</td>
                      <td>{b.description || "—"}</td>
                      <td>
                        <button type="button" className="secondary" onClick={() => {
                          setBranch({ name: b.name, code: b.code,
                            location: b.location, description: b.description || "" });
                          setEditBranch(b.id);
                        }}>Edit</button>{" "}
                        <button type="button" className="danger"
                          onClick={() => removeBranch(b.id)}>Delete</button>
                      </td>
                    </tr>)}
                  </tbody>
                </table>
              </div>
            )}
          </article>
        </div>}

      
        {page === "fees" && <div className="fee-page">
          <div className="stats-grid">
            <div className="stat-card"><span>Total Records</span><strong>{feeRecords.length}</strong></div>
            <div className="stat-card"><span>Total Fees</span><strong>₹{feeRecords.reduce((sum, r) => sum + Number(r.total_fee || 0), 0).toLocaleString("en-IN")}</strong></div>
            <div className="stat-card"><span>Amount Collected</span><strong>₹{feeRecords.reduce((sum, r) => sum + Number(r.amount_paid || 0), 0).toLocaleString("en-IN")}</strong></div>
            <div className="stat-card"><span>Balance Due</span><strong>₹{feeRecords.reduce((sum, r) => sum + Number(r.balance_due || 0), 0).toLocaleString("en-IN")}</strong></div>
          </div>

          <div className="manage-grid">
            <section className="panel">
              <h2>{editFee ? "Edit Fee Record" : "Add Fee Record"}</h2>
              <form onSubmit={saveFee} className="form-grid">
                <label>Student
                  <select required value={fee.student_id} onChange={e => {
                    const selected = students.find(s => String(s.id) === e.target.value);
                    setFee({ ...fee, student_id: e.target.value, student_name: selected ? selected.name : "" });
                  }}>
                    <option value="">Select student</option>
                    {students.map(s => <option key={s.id} value={s.id}>{s.name} (ID: {s.id})</option>)}
                  </select>
                </label>
                <label>Academic Year
                  <input required value={fee.academic_year} onChange={e => setFee({ ...fee, academic_year: e.target.value })} placeholder="2026-2027" />
                </label>
                <label>Total Fee (₹)
                  <input required type="number" min="0.01" step="0.01" value={fee.total_fee} onChange={e => setFee({ ...fee, total_fee: e.target.value })} />
                </label>
                <label>Amount Paid (₹)
                  <input required type="number" min="0" step="0.01" value={fee.amount_paid} onChange={e => setFee({ ...fee, amount_paid: e.target.value })} />
                </label>
                <label>Due Date
                  <input required type="date" value={fee.due_date} onChange={e => setFee({ ...fee, due_date: e.target.value })} />
                </label>
                <label>Payment Method
                  <select value={fee.payment_method} onChange={e => setFee({ ...fee, payment_method: e.target.value })}>
                    {["Cash", "UPI", "Card", "Bank Transfer", "Cheque", "Other"].map(method => <option key={method} value={method}>{method}</option>)}
                  </select>
                </label>
                <label className="full-width">Remarks
                  <textarea value={fee.remarks} onChange={e => setFee({ ...fee, remarks: e.target.value })} placeholder="Optional notes" />
                </label>
                <div className="form-actions">
                  <button type="submit" disabled={busy}>{busy ? "Saving..." : editFee ? "Update Fee" : "Save Fee"}</button>
                  {editFee && <button type="button" className="secondary-button" onClick={() => { setFee(blankFee); setEditFee(null); }}>Cancel</button>}
                </div>
              </form>
            </section>

            <section className="panel">
              <h2>Fee Payment Records</h2>
              {feeRecords.length === 0 ? <p className="subtitle">No fee records yet. Add a fee record using the form.</p> : (
                <div className="table-container">
                  <table>
                    <thead><tr><th>Student</th><th>Academic Year</th><th>Total Fee</th><th>Paid</th><th>Balance</th><th>Due Date</th><th>Status</th><th>Method</th><th>Actions</th></tr></thead>
                    <tbody>{feeRecords.map(r => (
                      <tr key={r.id}>
                        <td>{r.student_name || `Student ${r.student_id}`}</td>
                        <td>{r.academic_year}</td>
                        <td>₹{Number(r.total_fee || 0).toLocaleString("en-IN")}</td>
                        <td>₹{Number(r.amount_paid || 0).toLocaleString("en-IN")}</td>
                        <td>₹{Number(r.balance_due || 0).toLocaleString("en-IN")}</td>
                        <td>{r.due_date}</td>
                        <td><span className="status-badge">{r.payment_status}</span></td>
                        <td>{r.payment_method}</td>
                        <td>
                          <button type="button" onClick={() => {
                            setFee({
                              student_id: String(r.student_id),
                              student_name: r.student_name || "",
                              academic_year: r.academic_year || "",
                              total_fee: String(r.total_fee ?? ""),
                              amount_paid: String(r.amount_paid ?? "0"),
                              due_date: r.due_date || "",
                              payment_method: r.payment_method || "Cash",
                              remarks: r.remarks || ""
                            });
                            setEditFee(r.id);
                          }}>Edit</button>
                          <button type="button" className="danger-button" onClick={() => removeFee(r.id)}>Delete</button>
                        </td>
                      </tr>
                    ))}</tbody>
                  </table>
                </div>
              )}
            </section>
          </div>
        </div>}

        {page === "attendance" && <div className="attendance-page">
          <article className="info attendance-summary">
            <h3>Monthly attendance report</h3>
            <div className="attendance-filters">
              <label>Month
                <select value={reportMonth}
                  onChange={e => setReportMonth(e.target.value)}>
                  {[
                    ["01", "January"], ["02", "February"],
                    ["03", "March"], ["04", "April"],
                    ["05", "May"], ["06", "June"],
                    ["07", "July"], ["08", "August"],
                    ["09", "September"], ["10", "October"],
                    ["11", "November"], ["12", "December"]
                  ].map(([value, label]) => (
                    <option key={value} value={value}>{label}</option>
                  ))}
                </select>
              </label>
              <label>Year
                <select value={reportYear}
                  onChange={e => setReportYear(e.target.value)}>
                  {Array.from(
                    { length: 7 },
                    (_, i) => new Date().getFullYear() - 5 + i
                  ).map(year => (
                    <option key={year} value={String(year)}>{year}</option>
                  ))}
                </select>
              </label>
            </div>
            {(() => {
              const monthlyRecords = allAttendanceRecords.filter(r =>
                r.attendance_date.startsWith(`${reportYear}-${reportMonth}-`)
              );
              const groups = Object.values(monthlyRecords.reduce((acc, r) => {
                const key = String(r.student_id);
                if (!acc[key]) {
                  acc[key] = {
                    student_id: r.student_id,
                    student_name: r.student_name,
                    total: 0, present: 0, absent: 0, late: 0
                  };
                }
                acc[key].total++;
                if (r.status === "Present") acc[key].present++;
                if (r.status === "Absent") acc[key].absent++;
                if (r.status === "Late") acc[key].late++;
                return acc;
              }, {}));
              return monthlyRecords.length === 0 ? (
                <p className="subtitle">No attendance records for this month in the currently loaded records.</p>
              ) : (
                <div style={{ overflowX: "auto" }}>
                  <table>
                    <thead><tr>
                      <th>STUDENT</th><th>TOTAL</th><th>PRESENT</th>
                      <th>ABSENT</th><th>LATE</th><th>ATTENDANCE %</th>
                    </tr></thead>
                    <tbody>
                      {groups.map(r => (
                        <tr key={r.student_id}>
                          <td>{r.student_name}</td>
                          <td>{r.total}</td><td>{r.present}</td>
                          <td>{r.absent}</td><td>{r.late}</td>
                          <td>{(r.present / r.total * 100).toFixed(1)}%</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              );
            })()}
            <p className="subtitle">
              This monthly report uses all attendance records for the selected month and year, independently of the date filter below.
            </p>
          </article>
          <div className="attendance-page">
          <article className="info attendance-summary">
            <h3>Student attendance report</h3>
            {!attendanceRecords.length ? (
              <p className="subtitle">No attendance data available for this report.</p>
            ) : (
              <div style={{ overflowX: "auto" }}>
                <table>
                  <thead>
                    <tr>
                      <th>STUDENT</th>
                      <th>TOTAL RECORDS</th>
                      <th>PRESENT</th>
                      <th>ABSENT</th>
                      <th>LATE</th>
                      <th>ATTENDANCE %</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.values(attendanceRecords.reduce((groups, r) => {
                      const key = String(r.student_id);
                      if (!groups[key]) {
                        groups[key] = {
                          student_id: r.student_id,
                          student_name: r.student_name,
                          total: 0,
                          present: 0,
                          absent: 0,
                          late: 0
                        };
                      }
                      groups[key].total += 1;
                      if (r.status === "Present") groups[key].present += 1;
                      if (r.status === "Absent") groups[key].absent += 1;
                      if (r.status === "Late") groups[key].late += 1;
                      return groups;
                    }, {})).map(r => (
                      <tr key={r.student_id}>
                        <td>{r.student_name}</td>
                        <td>{r.total}</td>
                        <td>{r.present}</td>
                        <td>{r.absent}</td>
                        <td>{r.late}</td>
                        <td>{((r.present / r.total) * 100).toFixed(1)}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <p className="subtitle">
              Percentage = Present records ÷ Total records × 100.
              This report uses the attendance records currently displayed, including any active date filter.
            </p>
          </article>
          <div className="attendance-workspace">
          <form className="info" onSubmit={saveAttendance}>
            <h3>{editAttendance ? "Edit attendance" : "Record attendance"}</h3>
            <p className="subtitle">Students loaded: {students.length}</p>

            <label>Student
              <select required value={attendance.student_id}
                onChange={e => {
                  const selected = students.find(
                    x => String(x.id) === e.target.value
                  );
                  setAttendance({
                    ...attendance,
                    student_id: e.target.value,
                    student_name: selected ? selected.name : ""
                  });
                }}>
                <option value="">Select a student</option>
                {students.map(st => (
                  <option key={st.id} value={st.id}>{st.name}</option>
                ))}
              </select>
            </label>

            <label>Date
              <input type="date" required
                value={attendance.attendance_date}
                onChange={e => setAttendance({
                  ...attendance, attendance_date: e.target.value
                })} />
            </label>

            <label>Status
              <select required value={attendance.status}
                onChange={e => setAttendance({
                  ...attendance, status: e.target.value
                })}>
                <option value="Present">Present</option>
                <option value="Absent">Absent</option>
                <option value="Late">Late</option>
              </select>
            </label>

            <label>Remarks
              <input value={attendance.remarks}
                onChange={e => setAttendance({
                  ...attendance, remarks: e.target.value
                })}
                placeholder="Optional remarks" />
            </label>

            <button className="primary" disabled={busy || !students.length}>
              {editAttendance ? "Save changes" : "Record attendance"}
            </button>

            {!students.length &&
              <p className="subtitle">Add students before recording attendance.</p>}

            {editAttendance && <button type="button" className="secondary"
              onClick={() => {
                setEditAttendance(null);
                setAttendance(blankAttendance);
              }}>
              Cancel
            </button>}
          </form>

          <article className="info">
            <h3>Attendance records ({attendanceRecords.length})</h3>
            <button type="button" className="primary"
              onClick={exportAttendanceCSV}>
              Export CSV
            </button>
            <div className="attendance-filters">
              <label>Filter by date
                <input
                  type="date"
                  value={attendanceFilterDate}
                  onChange={e => setAttendanceFilterDate(e.target.value)}
                />
              </label>
              <button type="button" className="primary"
                onClick={filterAttendance}>
                Filter
              </button>
              <button type="button" className="secondary"
                onClick={() => {
                  setAttendanceFilterDate("");
                  (async () => {
                    try {
                      const records = await api("/attendance");
                      setAttendanceRecords(Array.isArray(records) ? records : []);
                      notify("Showing all attendance records.");
                    } catch (e) {
                      notify(e.message, true);
                    }
                  })();
                }}>
                Clear
              </button>
            </div>
            {!attendanceRecords.length
              ? <p className="subtitle">No attendance records yet.</p>
              : <div style={{ overflowX: "auto" }}>
                  <table>
                    <thead><tr>
                      <th>STUDENT</th><th>DATE</th><th>STATUS</th>
                      <th>REMARKS</th><th>ACTIONS</th>
                    </tr></thead>
                    <tbody>
                      {attendanceRecords.map(r => (
                        <tr key={r.id}>
                          <td>{r.student_name}</td>
                          <td>{r.attendance_date}</td>
                          <td>{r.status}</td>
                          <td>{r.remarks || "—"}</td>
                          <td>
                            <button type="button" className="secondary"
                              onClick={() => {
                                setAttendance({
                                  student_id: String(r.student_id),
                                  student_name: r.student_name,
                                  attendance_date: r.attendance_date,
                                  status: r.status,
                                  remarks: r.remarks || ""
                                });
                                setEditAttendance(r.id);
                              }}>Edit</button>{" "}
                            <button type="button" className="danger"
                              onClick={() => removeAttendance(r.id)}>
                              Delete
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>}
          </article>
          </div>
          </div>
        </div>}

        </section>
    </main>
  );
}

function RecordTable({ type, items, onEdit, onDelete }) {
  if (!items.length) return <p className="subtitle">No {type} records yet.</p>;

  return (
    <div style={{ overflowX: "auto" }}>
      <table>
        <thead>
          <tr>
            <th>{type === "student" ? "STUDENT" : "COURSE"}</th>
            <th>{type === "student" ? "DEPARTMENT" : "CODE"}</th>
            <th>{type === "student" ? "COURSE" : "DEPARTMENT"}</th>
            {(onEdit || onDelete) && <th>ACTIONS</th>}
          </tr>
        </thead>
        <tbody>
          {items.map(item => (
            <tr key={item.id}>
              <td>{type === "student" ? <>{item.name}<br /><small>{item.email}</small></> : item.name}</td>
              <td>{type === "student" ? item.department : item.code}</td>
              <td>{type === "student" ? item.course : item.department}</td>
              {(onEdit || onDelete) && <td>
                {onEdit && <button className="secondary" onClick={() => onEdit(item)}>Edit</button>}{" "}
                {onDelete && <button className="danger" onClick={() => onDelete(item.id)}>Delete</button>}
              </td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
