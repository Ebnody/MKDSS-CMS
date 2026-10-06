# Security Notes
- Server-side authorization is used for role-protected routes.
- CSRF middleware remains enabled.
- Passwords are handled by Django authentication and are never stored in application tables as plaintext.
- Protected originals are not served as `/media/...` public URLs.
- Upload extensions are restricted to the supported controlled-document types.
- Office conversion does not pass filenames/content as shell commands.
- Audit records are append-only from the normal application UI.
- Screenshots, screen recording, photography and browser developer tools cannot be reliably prevented by a normal web application.
