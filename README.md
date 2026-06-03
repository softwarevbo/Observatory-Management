# IIAP PM — Project Management System
## Module 1: Task Management

A professional Django-based project management system designed for engineering teams
across Electronics, Mechanical, Optics, Simulation, and Software modules.

---

## Features (Module 1)

- **Authentication** — Login/logout with role-based access. Users created only by Admin.
- **Dashboard** — Live stats, recent tasks, project progress, notifications
- **Projects** — Full CRUD with module filter, status tracking, progress bar
- **Tasks** — List & Kanban views, subtasks, filtering, inline status change
- **Calendar** — FullCalendar.js integration with event management
- **Bug Reports** — Severity tracking, assignment, status lifecycle
- **Notifications** — Auto-generated on task assign/comment/update
- **Reports** — Chart.js dashboards with task/project analytics
- **User Management** — Admin-only user creation, role/team assignment

---

## Tech Stack

- **Backend**: Django 4.2, SQLite (swap to PostgreSQL for production)
- **Frontend**: Vanilla HTML/CSS/JS — dark theme, Space Grotesk + DM Sans fonts
- **Charts**: Chart.js 4.4
- **Calendar**: FullCalendar.js 6.1
- **Icons**: Font Awesome 6.5

---

## Quick Start

### 1. Clone / Extract the project
```bash
cd IIAP_pm
```

### 2. Create virtual environment
```bash
python -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Run migrations
```bash
python manage.py makemigrations accounts
python manage.py makemigrations tasks
python manage.py migrate
```

### 5. Seed demo data (optional but recommended)
```bash
python manage.py seed_data
```

### 6. Start development server
```bash
python manage.py runserver
```

### 7. Open browser
```
http://127.0.0.1:8000/
```

---

## Demo Credentials

| Role            | Username      | Password  |
|-----------------|---------------|-----------|
| Admin           | admin         | admin123  |
| Project Manager | pm_raj        | pass123   |
| Project Manager | pm_sara       | pass123   |
| Member          | arjun_elec    | pass123   |
| Member          | priya_sw      | pass123   |
| Member          | vikram_mech   | pass123   |
| Member          | ananya_opt    | pass123   |
| Member          | suresh_sim    | pass123   |

---

## Role Permissions

| Feature              | Admin | Project Manager | Member  |
|----------------------|-------|-----------------|---------|
| Create users         | ✅    | ❌              | ❌      |
| Create projects      | ✅    | ✅              | ❌      |
| Edit/delete projects | ✅    | ✅ (own)        | ❌      |
| Create tasks         | ✅    | ✅              | ❌      |
| Edit tasks           | ✅    | ✅              | ❌      |
| View all tasks       | ✅    | ✅ (team)       | ✅ (own)|
| Report bugs          | ✅    | ✅              | ✅      |
| View reports         | ✅    | ✅              | ❌      |
| Update task status   | ✅    | ✅              | ✅      |
| Add comments         | ✅    | ✅              | ✅      |

---

## Project Structure

```
IIAP_pm/
├── core/                   # Django project config
│   ├── settings.py
│   └── urls.py
├── accounts/               # User management app
│   ├── models.py           # Custom User model
│   ├── views.py
│   ├── forms.py
│   └── urls.py
├── tasks/                  # Task management app (Module 1)
│   ├── models.py           # Project, Task, Comment, Notification, BugReport, CalendarEvent
│   ├── views.py
│   ├── forms.py
│   ├── urls.py
│   ├── decorators.py
│   ├── context_processors.py
│   └── management/
│       └── commands/
│           └── seed_data.py
├── templates/
│   ├── base.html           # Master layout with sidebar
│   ├── accounts/           # Login, user list, profile
│   └── tasks/              # Dashboard, projects, tasks, bugs, calendar, reports
├── static/                 # CSS, JS, images
├── manage.py
└── requirements.txt
```

---

## Production Notes

- Change `SECRET_KEY` in `settings.py`
- Set `DEBUG = False`
- Switch to PostgreSQL: update `DATABASES` in settings
- Set `ALLOWED_HOSTS` to your domain
- Run `python manage.py collectstatic`
- Use Gunicorn + Nginx for deployment

---

## Future Modules (Roadmap)

- **Module 2**: File Management — Version control, CI/CD, release management
- **Module 3**: Inventory Management — Stock levels, item tracking
- **Module 4**: User Management (extended) — Teams, credentials
- **Module 5**: Finance — Expense tracking, budgets
