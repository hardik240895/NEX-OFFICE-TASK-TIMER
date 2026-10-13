import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date
import time

# --- Page Configuration ---
st.set_page_config(
    page_title="WebLedger Office - Task & Timer Manager",
    page_icon="⏱️",
    layout="wide"
)

# --- Database Setup (SQLite) ---
DB_NAME = "office_tasks.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Tasks table
    c.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            client_name TEXT NOT NULL,
            category TEXT NOT NULL,
            assigned_to TEXT NOT NULL,
            priority TEXT NOT NULL,
            status TEXT NOT NULL,
            due_date TEXT NOT NULL,
            total_seconds INTEGER DEFAULT 0,
            is_timer_running INTEGER DEFAULT 0,
            timer_start_epoch REAL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Task Notes table
    c.execute('''
        CREATE TABLE IF NOT EXISTS task_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER,
            note_text TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
        )
    ''')
    # Timer Logs table (for WebLedger style reports)
    c.execute('''
        CREATE TABLE IF NOT EXISTS time_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER,
            staff_name TEXT,
            client_name TEXT,
            task_title TEXT,
            log_date TEXT,
            duration_seconds INTEGER,
            remarks TEXT,
            FOREIGN KEY (task_id) REFERENCES tasks(id)
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- Helper Functions ---
def get_db_connection():
    return sqlite3.connect(DB_NAME)

def format_seconds(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}h {m:02d}m {s:02d}s"

# --- Sidebar Navigation ---
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/3281/3281329.png", width=60)
st.sidebar.title("Office Manager")
menu = st.sidebar.radio("Navigation", ["📋 Task List & Timers", "➕ Add New Task", "📊 Task Timer Reports"])

# --- SECTION 1: Add New Task ---
if menu == "➕ Add New Task":
    st.subheader("➕ Create New Compliance / Office Task")
    with st.form("new_task_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            title = st.text_input("Task Title *", placeholder="e.g. GSTR-3B Filing for Sept")
            client_name = st.text_input("Client / Company Name *", placeholder="e.g. ABC Pvt Ltd")
            category = st.selectbox("Service Category", [
                "GST Compliance", "Income Tax / ITR", "TDS Filing", 
                "Bookkeeping & Accounting", "ROC & MCA", "Audit & Assurance", "Other"
            ])
        with col2:
            assigned_to = st.text_input("Assigned Staff / Article *", placeholder="e.g. Staff 1")
            priority = st.selectbox("Priority", ["Medium", "High", "Urgent", "Low"])
            due_date = st.date_input("Due Date", min_value=date.today())
        
        initial_note = st.text_area("Initial Task Note / Instructions (Optional)", placeholder="Login details, pending invoices, client remarks...")
        
        submitted = st.form_submit_button("Save & Assign Task", use_container_width=True)
        if submitted:
            if not title or not client_name or not assigned_to:
                st.error("Please fill in Task Title, Client Name, and Assigned Staff.")
            else:
                conn = get_db_connection()
                cur = conn.cursor()
                cur.execute('''
                    INSERT INTO tasks (title, client_name, category, assigned_to, priority, status, due_date)
                    VALUES (?, ?, ?, ?, ?, 'Pending', ?)
                ''', (title, client_name, category, assigned_to, priority, str(due_date)))
                task_id = cur.lastrowid
                
                if initial_note.strip():
                    cur.execute('''
                        INSERT INTO task_notes (task_id, note_text, created_at)
                        VALUES (?, ?, ?)
                    ''', (task_id, initial_note.strip(), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                
                conn.commit()
                conn.close()
                st.success(f"Task '{title}' created successfully!")

# --- SECTION 2: Task List & Timers ---
elif menu == "📋 Task List & Timers":
    st.title("📋 Office Tasks & Live Timers")

    conn = get_db_connection()
    tasks_df = pd.read_sql_query("SELECT * FROM tasks ORDER BY id DESC", conn)
    conn.close()

    # Metrics Summary
    if not tasks_df.empty:
        pending_count = len(tasks_df[tasks_df['status'] == 'Pending'])
        in_prog_count = len(tasks_df[tasks_df['status'] == 'In Progress'])
        review_count = len(tasks_df[tasks_df['status'] == 'Under Review'])
        done_count = len(tasks_df[tasks_df['status'] == 'Completed'])
        total_time = tasks_df['total_seconds'].sum()

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Pending", pending_count)
        m2.metric("In Progress", in_prog_count)
        m3.metric("Under Review", review_count)
        m4.metric("Completed", done_count)
        m5.metric("Total Time Tracked", format_seconds(total_time))
    
    st.divider()

    # Search and Filter
    c_f1, c_f2 = st.columns([2, 1])
    search_query = c_f1.text_input("🔍 Search by Client, Task Title, or Staff", "")
    status_filter = c_f2.selectbox("Filter Status", ["All", "Pending", "In Progress", "Under Review", "Completed"])

    if tasks_df.empty:
        st.info("No tasks recorded yet. Click 'Add New Task' in the sidebar to create your first task.")
    else:
        filtered_df = tasks_df.copy()
        if status_filter != "All":
            filtered_df = filtered_df[filtered_df['status'] == status_filter]
        if search_query:
            query = search_query.lower()
            filtered_df = filtered_df[
                filtered_df['title'].str.lower().str.contains(query) |
                filtered_df['client_name'].str.lower().str.contains(query) |
                filtered_df['assigned_to'].str.lower().str.contains(query)
            ]

        # Display Each Task Card
        for _, row in filtered_df.iterrows():
            task_id = row['id']
            with st.container(border=True):
                top_col1, top_col2, top_col3 = st.columns([3, 2, 2])
                with top_col1:
                    st.markdown(f"### {row['title']}")
                    st.caption(f"🏢 **Client:** {row['client_name']} | 📁 **Category:** {row['category']}")
                with top_col2:
                    st.write(f"👤 **Staff:** {row['assigned_to']}")
                    st.write(f"📅 **Due Date:** {row['due_date']} | **Priority:** `{row['priority']}`")
                with top_col3:
                    # Status dropdown
                    new_status = st.selectbox(
                        "Status", 
                        ["Pending", "In Progress", "Under Review", "Completed"],
                        index=["Pending", "In Progress", "Under Review", "Completed"].index(row['status']),
                        key=f"status_{task_id}"
                    )
                    if new_status != row['status']:
                        conn = get_db_connection()
                        conn.execute("UPDATE tasks SET status = ? WHERE id = ?", (new_status, task_id))
                        conn.commit()
                        conn.close()
                        st.rerun()

                st.write("")
                btn_col1, btn_col2, btn_col3 = st.columns([2, 2, 3])
                
                # Live Timer Controls
                with btn_col1:
                    current_seconds = row['total_seconds']
                    if row['is_timer_running'] == 1:
                        elapsed = int(time.time() - row['timer_start_epoch'])
                        st.markdown(f"⏱️ **Running:** `{format_seconds(current_seconds + elapsed)}`")
                        if st.button("🛑 Stop Timer", key=f"stop_{task_id}", type="primary"):
                            session_duration = int(time.time() - row['timer_start_epoch'])
                            new_total = current_seconds + session_duration
                            conn = get_db_connection()
                            conn.execute('''
                                UPDATE tasks 
                                SET is_timer_running = 0, timer_start_epoch = 0, total_seconds = ?
                                WHERE id = ?
                            ''', (new_total, task_id))
                            # Insert into time_logs for reporting
                            conn.execute('''
                                INSERT INTO time_logs (task_id, staff_name, client_name, task_title, log_date, duration_seconds, remarks)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            ''', (task_id, row['assigned_to'], row['client_name'], row['title'], 
                                  datetime.now().strftime("%Y-%m-%d"), session_duration, "Timer session logged"))
                            conn.commit()
                            conn.close()
                            st.rerun()
                    else:
                        st.markdown(f"⏱️ **Logged:** `{format_seconds(current_seconds)}`")
                        if st.button("▶️ Start Timer", key=f"start_{task_id}"):
                            conn = get_db_connection()
                            # Stop any other running timer
                            running_tasks = conn.execute("SELECT id, total_seconds, timer_start_epoch FROM tasks WHERE is_timer_running = 1").fetchall()
                            for r_id, r_tot, r_start in running_tasks:
                                dur = int(time.time() - r_start)
                                conn.execute("UPDATE tasks SET is_timer_running = 0, total_seconds = ? WHERE id = ?", (r_tot + dur, r_id))
                            # Start timer for this task
                            conn.execute('''
                                UPDATE tasks 
                                SET is_timer_running = 1, timer_start_epoch = ?, status = CASE WHEN status = 'Pending' THEN 'In Progress' ELSE status END
                                WHERE id = ?
                            ''', (time.time(), task_id))
                            conn.commit()
                            conn.close()
                            st.rerun()

                # Additional Notes Section
                with st.expander(f"📝 Notes & Activity Log for #{task_id}"):
                    conn = get_db_connection()
                    notes_cur = conn.cursor()
                    notes = notes_cur.execute("SELECT note_text, created_at FROM task_notes WHERE task_id = ? ORDER BY id DESC", (task_id,)).fetchall()
                    conn.close()

                    if notes:
                        for n_text, n_date in notes:
                            st.markdown(f"- **[{n_date}]** {n_text}")
                    else:
                        st.caption("No notes added yet.")

                    # Add new note
                    col_n1, col_n2 = st.columns([4, 1])
                    new_note_val = col_n1.text_input("Add remark/note", key=f"input_note_{task_id}", placeholder="Client sent OTP / documents checked...")
                    if col_n2.button("Add Note", key=f"btn_note_{task_id}"):
                        if new_note_val.strip():
                            conn = get_db_connection()
                            conn.execute("INSERT INTO task_notes (task_id, note_text, created_at) VALUES (?, ?, ?)",
                                         (task_id, new_note_val.strip(), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                            conn.commit()
                            conn.close()
                            st.rerun()

# --- SECTION 3: Task Timer Reports ---
elif menu == "📊 Task Timer Reports":
    st.title("📊 Task Timer & Productivity Report")
    st.caption("Timesheet report showing staff work hours per client and task (WebLedger Style)")

    conn = get_db_connection()
    logs_df = pd.read_sql_query("SELECT * FROM time_logs ORDER BY id DESC", conn)
    conn.close()

    if logs_df.empty:
        st.info("No time records generated yet. Run the timer on any task to create timesheet entries.")
    else:
        # Filters
        f1, f2, f3 = st.columns(3)
        staff_list = ["All"] + list(logs_df['staff_name'].dropna().unique())
        client_list = ["All"] + list(logs_df['client_name'].dropna().unique())

        selected_staff = f1.selectbox("Filter by Staff", staff_list)
        selected_client = f2.selectbox("Filter by Client", client_list)

        filtered_logs = logs_df.copy()
        if selected_staff != "All":
            filtered_logs = filtered_logs[filtered_logs['staff_name'] == selected_staff]
        if selected_client != "All":
            filtered_logs = filtered_logs[filtered_logs['client_name'] == selected_client]

        # Add formatted hours column
        filtered_logs['Duration (Formatted)'] = filtered_logs['duration_seconds'].apply(format_seconds)
        filtered_logs['Hours (Decimal)'] = (filtered_logs['duration_seconds'] / 3600).round(2)

        # Summary KPIs
        st.write("")
        total_sec = filtered_logs['duration_seconds'].sum()
        kpi1, kpi2, kpi3 = st.columns(3)
        kpi1.metric("Total Billable Hours", format_seconds(total_sec))
        kpi2.metric("Total Sessions Logged", len(filtered_logs))
        kpi3.metric("Decimal Total Hours", f"{(total_sec / 3600):.2f} hrs")

        st.divider()

        # Display Report Table
        display_cols = ['log_date', 'staff_name', 'client_name', 'task_title', 'Duration (Formatted)', 'Hours (Decimal)', 'remarks']
        st.dataframe(filtered_logs[display_cols].rename(columns={
            'log_date': 'Date',
            'staff_name': 'Staff Member',
            'client_name': 'Client Name',
            'task_title': 'Task Name',
            'remarks': 'Remarks'
        }), use_container_width=True)

        # Excel/CSV Download Button
        csv_data = filtered_logs[display_cols].to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Export Report to Excel (CSV)",
            data=csv_data,
            file_name=f"WebLedger_Timer_Report_{date.today()}.csv",
            mime="text/csv",
            type="primary"
        )
