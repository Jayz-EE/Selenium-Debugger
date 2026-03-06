# RMS Roles, Endpoints, and API Inventory

This document lists:

- Roles supported by the system (as used by the UI permissions)
- Authentication-related routes (web + API)
- Major web endpoints (per app/module)
- API endpoints under `/api/` (DRF)

Notes:

- Many “API” endpoints in this project are still server-rendered HTML pages (ex: `/api/monitor/` renders a template).
- DRF `DefaultRouter`-generated routes are marked as **(router)** and may expose multiple HTTP methods.
- Some apps include empty `urls.py` files in this repo snapshot (`room`, `schedule`, `backup`) and therefore have no routes listed here.

---

## Roles

Roles appear as string values on `accounts.User.role` and are used by decorators like `allowed_roles([...])`.

Credential placeholders (fill in with your own accounts):

- **Admin**

  ```json
  {
    "email": "",
    "username": "",
    "password": ""
  }
  ```

- **Admission**

  ```json
  {
    "email": "",
    "username": "",
    "password": ""
  }
  ```

- **Pre Admission**

  ```json
  {
    "email": "",
    "username": "",
    "password": ""
  }
  ```

- **Academic Director**

  ```json
  {
    "email": "",
    "username": "",
    "password": ""
  }
  ```

- **Program Head**

  ```json
  {
    "email": "",
    "username": "",
    "password": ""
  }
  ```

- **Registrar**

  ```json
  {
    "email": "",
    "username": "",
    "password": ""
  }
  ```

- **Teacher**

  ```json
  {
    "email": "",
    "username": "",
    "password": ""
  }
  ```

- **Cashier**

  ```json
  {
    "email": "",
    "username": "",
    "password": ""
  }
  ```

- **Finance**

  ```json
  {
    "email": "",
    "username": "",
    "password": ""
  }
  ```

- **Guidance**

  ```json
  {
    "email": "",
    "username": "",
    "password": ""
  }
  ```

- **Clinic**

  ```json
  {
    "email": "",
    "username": "",
    "password": ""
  }
  ```

- **IT Staff**

  ```json
  {
    "email": "",
    "username": "",
    "password": ""
  }
  ```

- **Scholarship Officer**

  ```json
  {
    "email": "",
    "username": "",
    "password": ""
  }
  ```

- **Librarian**

  ```json
  {
    "email": "",
    "username": "",
    "password": ""
  }
  ```

---

## Project Root URL Includes

From `rms/rms/urls.py`:

- `GET /`

  - Accounts module routes (login + account management)

- `GET /api/`

  - DRF API features (authentication, monitoring, academic, students, teachers, finance, courses, registrar, sync, print)

- `GET /academic_director/`

- `GET /admission/`

- `GET /preadmission/`

- `GET /cashier/`

- `GET /finance/`

- `GET /guidance/`

- `GET /clinic/`

- `GET /it_staff/`

- `GET /program_head/`

- `GET /registrar/`

- `GET /scholarship/`

- `GET /teacher/`

- `GET /classify/`

- `GET /administrator/`

- `GET /library/`

- `GET /school/`

- `GET /auth/`

  - Social auth (`social_django`)

---

## Authentication

### Web (Accounts app)

From `accounts/urls.py`:

- `GET /`

  - Login page

- `POST /`

  - Login form submit

- `POST /logout/`

  - Logout

- `GET /role_based_redirect/`

  - Redirect user based on role

- `POST /check_email_existence/`

  - Check email for password reset / account lookup

- `POST /verify_otp/`

  - Verify OTP for password reset

- `POST /reset_password/`

  - Reset password

- `POST /change_password_verification/`

  - Password change flow verification

- `POST /change_password_update/`

  - Update password

### API (`/api/*`)

From `api/features/authentication/urls.py`:

- `GET /api/monitor/`

  - API monitor dashboard (HTML)

- `GET /api/key-status/`

  - Returns API key status (accepts API key auth)

---

## API Inventory (`/api/*`)

These are DRF endpoints mounted under `/api/` via `api/urls.py`.

### Monitoring

- `GET /api/traffic-monitor/`

  - API traffic monitoring (view)

### Academic

- `GET /api/academic-terms/`

  - List academic terms

- `GET /api/academic-terms/active/`

  - List active academic terms

- `GET /api/academic-terms/<pk>/`

  - Academic term details

- `GET /api/program-head/`

  - List program head departments

- `GET /api/program-head/<id>/`

  - Program head department details

### Courses

- `GET /api/courses/`

  - List/filter courses

- `GET /api/courses/<pk>/`

  - Course details

- `GET /api/course-subjects/`

  - List/filter course-subject mappings

- `GET /api/course-subjects/<pk>/`

  - Course-subject detail

- `GET /api/subjects/`

  - List all subjects

- `GET /api/terms/`

  - List terms

- `GET /api/terms/<pk>/`

  - Term details

- `GET /api/class-schedules/`

  - List class schedules

- `GET /api/class-schedules/<pk>/`

  - Class schedule detail

- `GET /api/grouped-class-schedules/`

  - List grouped class schedules

### Students

- `GET /api/students/`

  - Student full list

- `GET /api/students/<pk>/`

  - Student full detail

- `GET /api/student-schedules/`

  - Student schedule list

- `GET /api/student-schedules/<pk>/`

  - Student schedule detail

- `GET /api/student-schedules/student/<student_id>/`

  - Student schedules for a specific student

- `GET /api/academic-history/` **(router)**

  - Academic history (ViewSet)

- `GET /api/academic-history/<id>/` **(router)**

  - Academic history record detail

### Teachers

- `GET /api/teachers/`

  - Teacher list

- `GET /api/teachers/<pk>/`

  - Teacher detail

### Finance

- `GET /api/student-finances/`

  - Finance list

- `GET /api/student-finances/<pk>/`

  - Finance detail

- `GET /api/student-finances/student/<student_id>/`

  - Finance records by student

### Registrar

- `/api/grading-schedules/` **(router)**

  - Grading schedules (ViewSet)

### Sync

- `POST /api/import_lms_grades/`

  - LMS grade import

### Print

- `GET /api/print/exit-interview/<pk>/html/`

  - Exit interview print HTML

- `GET /api/print/exit-interview/<pk>/pdf/`

  - Exit interview export PDF

---

## Web Endpoints (by app)

These are server routes mounted under their app prefixes (ex: `/academic_director/...`).

### Academic Director (`/academic_director/`)

Dashboard:

- `GET /academic_director/`

  - Academic Director dashboard

- `GET /academic_director/academic_director_stats/`

  - Dashboard stats JSON

- `GET /academic_director/academic_director_enrollment_trends/`

  - Enrollment trends JSON

- `GET /academic_director/ad_grade_stats/`

  - Grade stats JSON

- `GET /academic_director/ad_subject_search/`

  - Subject search

Prospectus:

- `GET /academic_director/prospectus/`

  - Prospectus list / overview

- `GET /academic_director/prospectus/add/`

  - Manage prospectus page

- `POST /academic_director/prospectus/create/`

  - Create prospectus (API)

- `POST /academic_director/prospectus/update/`

  - Update prospectus (API)

- `POST /academic_director/prospectus/rename-template/`

  - Rename template

- `GET /academic_director/prospectus/template-sources/`

  - List template sources (API)

- `GET /academic_director/prospectus/templates-for-term/`

  - Templates for term (API)

- `GET /academic_director/prospectus/templates-by-course/`

  - Templates by course (API)

- `GET /academic_director/prospectus/detail-for-year/`

  - Prospectus detail for year (API)

- `POST /academic_director/prospectus/delete-template/`

  - Delete prospectus template

- `GET /academic_director/prospectus/enrolled-students/`

  - Enrolled students list (active term)

- `POST /academic_director/prospectus/assign-to-students/`

  - Assign prospectus template to students

- `POST /academic_director/prospectus/unassign-student/`

  - Unassign a student from a template

Schedules / grouping:

- `GET /academic_director/manage_schedules/`

- `GET|POST /academic_director/group_class_schedules/`

- `POST /academic_director/group_class_schedules/process/`

- `POST /academic_director/ungroup_class_schedules/`

- `POST /academic_director/update_group_name/`

- `GET /academic_director/get_group_members/<group_id>/`

- `POST /academic_director/remove_from_group/`

- `POST /academic_director/add_to_group/`

- `GET /academic_director/get_available_schedules/<group_id>/`

Student schedules:

- `GET /academic_director/student_schedules/`

- `POST /academic_director/add_student_schedule/<pk>/`

- `POST /academic_director/unfinalize_student_subject/<student_subject_id>/`

- `POST /academic_director/delete_student_schedule/<pk>/`

- `GET /academic_director/api/eligible_students/`

Other management endpoints (Subjects/Teachers/Rooms/Terms/Courses):

- `/academic_director/manage_subjects/`, `/academic_director/manage_teachers/`, `/academic_director/manage_rooms/`, `/academic_director/manage_academic_terms/`, `/academic_director/course/`, etc.

### Program Head (`/program_head/`)

- `GET /program_head/`

  - Program Head dashboard

Student subjects:

- `GET /program_head/student_subjects/`

- `GET /program_head/student-subjects-json/`

- `GET /program_head/student-subjects-json/<pk>/`

- `POST /program_head/update_student_subject/`

  - Enroll/Drop/Update student subjects

Prospectus assignment:

- `GET /program_head/prospectus/enrolled-students/`

- `POST /program_head/prospectus/assign-to-students/`

- `POST /program_head/prospectus/unassign-student/`

Transfers:

- `GET /program_head/get-target-schedules/`

- `POST /program_head/check-transfer-conflicts/`

- `POST /program_head/transfer-student-schedule/`

- `POST /program_head/bulk-transfer-students/`

### Registrar (`/registrar/`)

- `GET /registrar/`

  - Registrar dashboard

Includes multiple reporting endpoints under `/registrar/report/*` and several JSON endpoints under `/registrar/api/*`.

### Admission (`/admission/`)

- `GET /admission/`

  - Admission dashboard

- `GET /admission/api/daily-applications/`

  - Daily applications chart data

### Finance (`/finance/`)

- `GET /finance/finance_dashboard/`

- `GET /finance/api/dashboard/stats/`

- `GET /finance/api/dashboard/monthly-collections/`

- `GET /finance/api/dashboard/revenue-breakdown/`

- `GET /finance/api/dashboard/outstanding-balances/`

- `GET /finance/api/dashboard/recent-payments/`

### Cashier (`/cashier/`)

- `GET /cashier/`

  - Cashier dashboard

- `POST /cashier/process_payment_ajax/`

  - Process payment

- `GET /cashier/api/student/<student_id>/subjects/`

  - Student subjects API for cashier

### Teacher (`/teacher/`)

- `GET /teacher/`

- `GET /teacher/teacher_grade_stats/`

  - Teacher grade stats

- `GET /teacher/teacher_subject_performance/`

  - Teacher subject performance

### Guidance (`/guidance/`)

- `GET /guidance/`

  - Guidance dashboard

- Multiple forms + print endpoints:

  - exit interview, case conference, incident report, call slip, counseling, etc.

### Clinic (`/clinic/`)

- `GET /clinic/`

  - Clinic dashboard

### IT Staff (`/it_staff/`)

- `GET /it_staff/`

  - IT Staff dashboard

### Scholarship (`/scholarship/`)

- `GET /scholarship/`

  - Scholarship dashboard

### Library (`/library/`)

- `GET /library/`

  - Library dashboard

### School (`/school/`)

- `GET /school/`

  - School settings

---

## TODO / Gaps

If you need a truly exhaustive endpoint list (including every single registrar report route, and DRF router method mappings), we can add a script to enumerate Django URL resolver output at runtime.
