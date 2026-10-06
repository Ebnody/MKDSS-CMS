import csv
from io import StringIO

from django.http import HttpResponse
from django.utils import timezone

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def _row_value(row, key, default=""):
    value = row.get(key, default) if isinstance(row, dict) else default
    return default if value is None else value


def _user_name(user):
    return user.get_full_name().strip() or user.username


def _department_name(user):
    profile = getattr(user, "profile", None)
    department = getattr(profile, "department", None) if profile else None
    return department.name if department else ""


def _status(record):
    if record is None:
        return "NOT_STARTED"
    return record.status


def _status_label(record):
    if record is None:
        return "Not Started"
    return record.get_status_display()


def _percent(completed, total):
    return round(completed * 100 / total, 1) if total else 0.0


def _normalise_rows(rows):
    """
    Convert the dashboard/report row structure into a stable list.

    Expected row shape:
        {
            "user": User,
            "version": DocumentVersion,
            "record": ReadingRecord | None,
        }

    A small amount of tolerance is retained so report generation fails
    gracefully if an empty/partial result set is supplied.
    """
    return list(rows or [])


def reading_csv(rows, filename=None):
    """
    Generate an authenticated CSV reading-compliance report.

    The view is responsible for authentication/authorization and filtering.
    This function only renders the already-filtered result set.
    """
    rows = _normalise_rows(rows)

    output = StringIO()
    writer = csv.writer(output)

    writer.writerow(["MKDSS COMPLIANCE MANAGEMENT SYSTEM"])
    writer.writerow(["Official Document Reading Compliance Report"])
    writer.writerow(["Generated", timezone.localtime().strftime("%Y-%m-%d %H:%M:%S")])
    writer.writerow([])

    completed = sum(
        _status(row.get("record")) == "COMPLETED"
        for row in rows
    )
    in_progress = sum(
        _status(row.get("record")) == "IN_PROGRESS"
        for row in rows
    )
    not_started = len(rows) - completed - in_progress

    writer.writerow(["Summary"])
    writer.writerow(["Total Expected", len(rows)])
    writer.writerow(["Completed", completed])
    writer.writerow(["In Progress", in_progress])
    writer.writerow(["Not Started", not_started])
    writer.writerow(["Completion %", _percent(completed, len(rows))])
    writer.writerow([])

    writer.writerow([
        "User",
        "Username",
        "Department",
        "Document Number",
        "Document Title",
        "Version",
        "Reading Status",
        "Started At",
        "Completed At",
    ])

    for row in rows:
        user = row.get("user")
        version = row.get("version")
        record = row.get("record")

        writer.writerow([
            _user_name(user) if user else "",
            getattr(user, "username", ""),
            _department_name(user) if user else "",
            getattr(version.document, "document_number", "") if version else "",
            getattr(version.document, "title", "") if version else "",
            getattr(version, "version", "") if version else "",
            _status_label(record),
            timezone.localtime(record.started_at).strftime("%Y-%m-%d %H:%M:%S")
            if record and record.started_at else "",
            timezone.localtime(record.completed_at).strftime("%Y-%m-%d %H:%M:%S")
            if record and record.completed_at else "",
        ])

    response = HttpResponse(
        output.getvalue(),
        content_type="text/csv; charset=utf-8",
    )
    response["Content-Disposition"] = (
        f'attachment; filename="{filename or "MKDSS_Reading_Compliance_Report.csv"}"'
    )
    response["Cache-Control"] = "no-store, private"
    response["X-Content-Type-Options"] = "nosniff"
    return response


def reading_pdf(rows, generated_by, date_range="All"):
    """
    Generate the official PDF reading-compliance report.

    The report is generated in memory and returned as an authenticated
    response by the calling view. No report is written to public media.
    """
    rows = _normalise_rows(rows)

    completed = sum(
        _status(row.get("record")) == "COMPLETED"
        for row in rows
    )
    in_progress = sum(
        _status(row.get("record")) == "IN_PROGRESS"
        for row in rows
    )
    not_started = len(rows) - completed - in_progress

    buffer = StringIO()
    # SimpleDocTemplate accepts a binary file-like object, so use BytesIO
    # below rather than returning the StringIO directly.
    from io import BytesIO
    pdf_buffer = BytesIO()

    document = SimpleDocTemplate(
        pdf_buffer,
        pagesize=landscape(A4),
        rightMargin=10 * mm,
        leftMargin=10 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
        title="MKDSS Official Document Reading Compliance Report",
        author=_user_name(generated_by),
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "MKDSSReportTitle",
        parent=styles["Title"],
        alignment=TA_CENTER,
        fontSize=16,
        leading=19,
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "MKDSSReportSubtitle",
        parent=styles["Normal"],
        alignment=TA_CENTER,
        fontSize=10,
        leading=13,
        spaceAfter=8,
    )
    small_style = ParagraphStyle(
        "MKDSSReportSmall",
        parent=styles["Normal"],
        fontSize=7,
        leading=9,
    )
    header_style = ParagraphStyle(
        "MKDSSReportHeader",
        parent=small_style,
        fontName="Helvetica-Bold",
        alignment=TA_CENTER,
    )
    cell_style = ParagraphStyle(
        "MKDSSReportCell",
        parent=small_style,
        alignment=TA_LEFT,
    )

    story = [
        Paragraph("MKDSS COMPLIANCE MANAGEMENT SYSTEM", title_style),
        Paragraph(
            "Official Document Reading Compliance Report",
            subtitle_style,
        ),
        Paragraph(
            f"Reporting Period: {date_range} &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"Generated: {timezone.localtime().strftime('%Y-%m-%d %H:%M:%S')} "
            f"&nbsp;&nbsp;|&nbsp;&nbsp; Generated By: {_user_name(generated_by)}",
            small_style,
        ),
        Spacer(1, 5 * mm),
    ]

    summary_data = [
        ["Total Expected", "Completed", "In Progress", "Not Started", "Completion"],
        [
            str(len(rows)),
            str(completed),
            str(in_progress),
            str(not_started),
            f"{_percent(completed, len(rows))}%",
        ],
    ]

    summary_table = Table(
        summary_data,
        colWidths=[45 * mm] * 5,
        repeatRows=1,
    )
    summary_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e9ecef")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ])
    )
    story.extend([summary_table, Spacer(1, 6 * mm)])

    table_data = [[
        Paragraph("User", header_style),
        Paragraph("Department", header_style),
        Paragraph("Document", header_style),
        Paragraph("Version", header_style),
        Paragraph("Status", header_style),
        Paragraph("Started", header_style),
        Paragraph("Completed", header_style),
    ]]

    for row in rows:
        user = row.get("user")
        version = row.get("version")
        record = row.get("record")

        document_name = ""
        if version:
            number = getattr(version.document, "document_number", "")
            title = getattr(version.document, "title", "")
            document_name = f"{number} - {title}" if number else title

        table_data.append([
            Paragraph(_user_name(user) if user else "", cell_style),
            Paragraph(_department_name(user) if user else "", cell_style),
            Paragraph(document_name, cell_style),
            Paragraph(getattr(version, "version", "") if version else "", cell_style),
            Paragraph(_status_label(record), cell_style),
            Paragraph(
                timezone.localtime(record.started_at).strftime("%Y-%m-%d %H:%M")
                if record and record.started_at else "",
                cell_style,
            ),
            Paragraph(
                timezone.localtime(record.completed_at).strftime("%Y-%m-%d %H:%M")
                if record and record.completed_at else "",
                cell_style,
            ),
        ])

    detail_table = Table(
        table_data,
        colWidths=[35 * mm, 30 * mm, 80 * mm, 20 * mm, 28 * mm, 35 * mm, 35 * mm],
        repeatRows=1,
    )
    detail_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e9ecef")),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ])
    )
    story.append(detail_table)

    document.build(story)

    response = HttpResponse(
        pdf_buffer.getvalue(),
        content_type="application/pdf",
    )
    response["Content-Disposition"] = (
        'attachment; filename="MKDSS_Reading_Compliance_Report.pdf"'
    )
    response["Cache-Control"] = "no-store, private"
    response["X-Content-Type-Options"] = "nosniff"
    return response
