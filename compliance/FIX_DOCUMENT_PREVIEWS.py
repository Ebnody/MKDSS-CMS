from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
services = ROOT / "compliance" / "services.py"

text = services.read_text(encoding="utf-8")

start = text.index("def create_version(")
end = text.index("\ndef file_sha256(", start)

replacement = r'''def create_version(document, uploaded_file, version, user, status=DocumentVersion.Status.DRAFT):
    name, mime = validate_document_file(uploaded_file)

    if DocumentVersion.objects.filter(document=document, version=version).exists():
        raise ValueError("That version number already exists for this document.")

    v = DocumentVersion.objects.create(
        document=document,
        version=version,
        original_name=name,
        original_file=uploaded_file,
        mime_type=mime,
        uploaded_by=user,
        status=status,
    )

    try:
        generate_version_preview(v)
    except Exception as exc:
        try:
            if v.original_file:
                v.original_file.delete(save=False)
        finally:
            v.delete()
        raise ValueError(f"Document preview generation failed: {exc}") from exc

    document.current_version = v
    document.save(update_fields=["current_version"])

    return v


def _save_pdf_preview(version, pdf_path):
    pdf_path = Path(pdf_path)

    if not pdf_path.exists() or pdf_path.stat().st_size == 0:
        raise ValueError("LibreOffice did not produce a valid PDF preview.")

    preview_name = f"{version.document_id}_{version.pk}.pdf"

    with pdf_path.open("rb") as fh:
        version.preview_file.save(
            preview_name,
            File(fh),
            save=True,
        )

    version.refresh_from_db()

    if not version.preview_file:
        raise ValueError("The generated preview could not be stored.")

    try:
        if not Path(version.preview_file.path).exists():
            raise ValueError("The stored preview file could not be found.")
    except ValueError:
        raise ValueError("The stored preview path is invalid.")

    return version.preview_file


def convert_office_to_pdf(version):
    ext = safe_extension(version.original_name)

    if ext not in {"doc", "docx", "xls", "xlsx", "ppt", "pptx"}:
        return None

    source = Path(version.original_file.path)

    if not source.exists():
        raise ValueError("The uploaded Office file could not be found.")

    libreoffice = str(getattr(settings, "LIBREOFFICE_PATH", "") or "").strip()

    if not libreoffice:
        raise ValueError("LibreOffice is not configured.")

    if not Path(libreoffice).exists():
        raise ValueError(f"LibreOffice executable was not found: {libreoffice}")

    with tempfile.TemporaryDirectory() as tmp:
        temp = Path(tmp)

        copied = temp / get_valid_filename(source.name)
        shutil.copy2(source, copied)

        home = temp / "home"
        home.mkdir()

        profile = temp / "profile"
        profile.mkdir()

        cmd = [
            libreoffice,
            "--headless",
            "--nologo",
            "--nodefault",
            "--nofirststartwizard",
            "--norestore",
            "--nolockcheck",
            f"-env:UserInstallation={profile.as_uri()}",
            "--convert-to",
            "pdf",
            "--outdir",
            str(temp),
            str(copied),
        ]

        env = os.environ.copy()
        env["HOME"] = str(home)
        env["USERPROFILE"] = str(home)

        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=120,
                check=False,
                env=env,
                shell=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ValueError("LibreOffice preview generation timed out.") from exc
        except OSError as exc:
            raise ValueError(f"LibreOffice could not be started: {exc}") from exc

        pdf = temp / f"{copied.stem}.pdf"

        if result.returncode != 0:
            details = (result.stderr or result.stdout or "").strip()
            raise ValueError(
                f"LibreOffice failed to convert the document."
                + (f" {details}" if details else "")
            )

        if not pdf.exists() or pdf.stat().st_size == 0:
            details = (result.stderr or result.stdout or "").strip()
            raise ValueError(
                "LibreOffice completed but did not create a valid PDF preview."
                + (f" {details}" if details else "")
            )

        return _save_pdf_preview(version, pdf)


def convert_image_to_pdf(version):
    ext = safe_extension(version.original_name)

    if ext not in {"png", "jpg", "jpeg"}:
        return None

    try:
        from PIL import Image
    except ImportError as exc:
        raise ValueError("Pillow is required for image previews.") from exc

    source = Path(version.original_file.path)

    if not source.exists():
        raise ValueError("The uploaded image could not be found.")

    with tempfile.TemporaryDirectory() as tmp:
        pdf = Path(tmp) / "preview.pdf"

        try:
            with Image.open(source) as image:
                image = image.convert("RGB")
                image.save(pdf, "PDF", resolution=150.0)
        except Exception as exc:
            raise ValueError(f"Image preview generation failed: {exc}") from exc

        return _save_pdf_preview(version, pdf)


def generate_version_preview(version):
    ext = safe_extension(version.original_name)

    if ext == "pdf":
        source = Path(version.original_file.path)

        if not source.exists():
            raise ValueError("The uploaded PDF could not be found.")

        with source.open("rb") as fh:
            version.preview_file.save(
                f"{version.document_id}_{version.pk}.pdf",
                File(fh),
                save=True,
            )

        version.refresh_from_db()

        if not version.preview_file:
            raise ValueError("The PDF preview could not be stored.")

        return version.preview_file

    if ext in {"doc", "docx", "xls", "xlsx", "ppt", "pptx"}:
        return convert_office_to_pdf(version)

    if ext in {"png", "jpg", "jpeg"}:
        return convert_image_to_pdf(version)

    raise ValueError("Unsupported document type for preview generation.")


def version_preview(version):
    if not version.preview_file:
        return None

    try:
        if Path(version.preview_file.path).exists():
            return version.preview_file
    except (ValueError, FileNotFoundError):
        return None

    return None
'''

backup = services.with_suffix(".py.preview_backup")
shutil.copy2(services, backup)

services.write_text(text[:start] + replacement + text[end:], encoding="utf-8")

print("Preview code updated successfully.")
print(f"Backup created: {backup}")