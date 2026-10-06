# MKDSS Compliance Management System v1.0.0

Production-oriented internal LAN controlled-document and compliance workflow application for MK Digital Security Solutions PLC.

## Roles
System Admin, Compliance, Approver, User. Application permissions are enforced server-side through `UserProfile.role`; System Admin does not inherit the other workflow roles.

## Core workflows
- Controlled document: Draft -> Under Review -> Revision Required / Review Accepted -> Published -> Archived.
- Requests: User/Compliance -> Pending Approval -> Approved/Rejected -> Compliance Queue -> In Progress -> Under Review -> Document Pending Approval -> Document Approved -> Completed.
- Reading: exact published version -> In Progress -> Finished Reading -> Completed.
- Historical document versions, review decisions, request history, reading records, and audit logs are retained.

## Security model
Controlled files are stored below `data/documents` and are never served by Django's static/media URL. Users receive documents only through authenticated authorization routes. Normal users have no download button. The system does not claim to defeat screenshots, screen recording, photography, or browser developer tools.

Office previews use local LibreOffice headless conversion when installed. No CDN, cloud authentication, external conversion service, or runtime Internet dependency is required.

## Windows installation
1. Install Python 3.12+.
2. Run `scripts\setup_windows.bat`.
3. Edit `.env` and set a real `DJANGO_SECRET_KEY` and deployment host values.
4. Run `python manage.py migrate` if setup did not already do so.
5. Create an initial user securely and assign the explicit `SYSTEM_ADMIN` profile role.
6. Run `python manage.py collectstatic --noinput`.
7. Set `MKDSS_PORT` and run `scripts\start_waitress.bat`.

For a LAN HTTP deployment, leave `DJANGO_SECURE_SSL_REDIRECT=False`. If HTTPS is configured at a trusted reverse proxy, enable the corresponding secure settings in `.env`.

## Backup / restore
System Admin can create and restore ZIP backups. CLI backup is also available with `python manage.py backup_system`. Restore always creates a pre-restore backup first.

## Clean deployment
The package contains no production database, user accounts, passwords, demo documents, or production secrets.
