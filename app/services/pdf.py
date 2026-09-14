"""ReportLab renderer for compliance evidence packages.

Templates are jurisdiction-aware: ``JURISDICTION_TEMPLATES`` supplies the regulation
name, the section ordering, and the closing attestation text per regime.
"""

from __future__ import annotations

import io
from datetime import UTC, datetime
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

BRAND = colors.HexColor("#1F3A5F")
MUTED = colors.HexColor("#5B6B7F")
FAIL_COLOR = colors.HexColor("#B00020")
WARN_COLOR = colors.HexColor("#B26A00")
PASS_COLOR = colors.HexColor("#1B7F4B")

RESULT_COLORS = {
    "pass": PASS_COLOR,
    "fail": FAIL_COLOR,
    "warning": WARN_COLOR,
    "error": FAIL_COLOR,
}

JURISDICTION_TEMPLATES: dict[str, dict[str, Any]] = {
    "EU": {
        "title": "EU AI Act Conformity Evidence Package",
        "regulation": "Regulation (EU) 2024/1689 (AI Act)",
        "attestation": (
            "This package is compiled to support the provider's technical documentation "
            "obligations under Articles 11 and 18 of the EU AI Act. It is not a "
            "substitute for a notified-body conformity assessment where one is required."
        ),
    },
    "CA": {
        "title": "California AI Compliance Evidence Package",
        "regulation": "California AI Transparency Act / CCPA-CPRA ADMT rules",
        "attestation": (
            "Compiled to support disclosure, opt-out and risk-assessment obligations for "
            "automated decision-making technology under California law."
        ),
    },
    "CN": {
        "title": "PRC AI Compliance Evidence Package",
        "regulation": "Interim Measures for Generative AI Services; PIPL; Algorithm Filing rules",
        "attestation": (
            "Compiled to support algorithm filing, security assessment and data "
            "localisation obligations under PRC law."
        ),
    },
    "IN": {
        "title": "India AI Governance Evidence Package",
        "regulation": "DPDP Act 2023 and MeitY AI governance guidelines",
        "attestation": (
            "Compiled to support consent, data-fiduciary and grievance-redressal "
            "obligations under the DPDP Act 2023."
        ),
    },
}

DEFAULT_TEMPLATE = {
    "title": "AI Compliance Evidence Package",
    "regulation": "Applicable AI and data-protection law",
    "attestation": "Compiled from the organisation's AI governance records.",
}


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "TitleX", parent=base["Title"], textColor=BRAND, fontSize=20, spaceAfter=6
        ),
        "subtitle": ParagraphStyle(
            "SubtitleX", parent=base["Normal"], textColor=MUTED, fontSize=10, spaceAfter=14
        ),
        "h2": ParagraphStyle(
            "H2X", parent=base["Heading2"], textColor=BRAND, fontSize=13, spaceBefore=14
        ),
        "h3": ParagraphStyle("H3X", parent=base["Heading3"], fontSize=11, spaceBefore=8),
        "body": ParagraphStyle(
            "BodyX", parent=base["BodyText"], fontSize=9, leading=13, alignment=TA_LEFT
        ),
        "small": ParagraphStyle(
            "SmallX", parent=base["BodyText"], fontSize=8, leading=11, textColor=MUTED
        ),
    }


def _kv_table(rows: list[tuple[str, str]], width: float = 165 * mm) -> Table:
    st = _styles()
    data = [
        [Paragraph(f"<b>{k}</b>", st["body"]), Paragraph(v or "—", st["body"])] for k, v in rows
    ]
    table = Table(data, colWidths=[55 * mm, width - 55 * mm])
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D6DCE4")),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F3F6FA")),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _footer(canvas: Any, doc: Any) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(MUTED)
    canvas.drawString(20 * mm, 12 * mm, "AI Governance Console — confidential compliance evidence")
    canvas.drawRightString(A4[0] - 20 * mm, 12 * mm, f"Page {doc.page}")
    canvas.restoreState()


def _fmt_list(values: list[str] | None) -> str:
    return ", ".join(values) if values else "—"


def render_evidence_pdf(package: dict[str, Any]) -> bytes:
    """Render the canonical evidence JSON document into a PDF."""
    st = _styles()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=20 * mm,
        title=f"Evidence Package — {package['system']['name']}",
        author="AI Governance Console",
    )

    system = package["system"]
    meta = package.get("metadata") or {}
    jurisdictions: list[str] = package.get("jurisdictions") or []
    primary = jurisdictions[0] if jurisdictions else None
    template = JURISDICTION_TEMPLATES.get(primary or "", DEFAULT_TEMPLATE)

    story: list[Any] = [
        Paragraph(template["title"], st["title"]),
        Paragraph(
            f"{system['name']} &nbsp;·&nbsp; {template['regulation']} &nbsp;·&nbsp; "
            f"generated {package['generated_at']}",
            st["subtitle"],
        ),
        _kv_table(
            [
                ("Package ID", str(package.get("package_id", "—"))),
                ("System ID", str(system["id"])),
                ("Status", str(system.get("status"))),
                ("Owner", str(system.get("owner", "—"))),
                ("Metadata version", str(system.get("metadata_version"))),
                ("Jurisdictions", _fmt_list(jurisdictions)),
                ("Generated by", str(package.get("generated_by", "—"))),
            ]
        ),
        Paragraph("1. System description", st["h2"]),
        Paragraph(system.get("description") or "No description recorded.", st["body"]),
        Spacer(1, 6),
        _kv_table(
            [
                ("Purpose", meta.get("purpose") or "—"),
                ("Use case", meta.get("use_case") or "—"),
                ("Industry", meta.get("industry") or "—"),
                ("Autonomy level", meta.get("autonomy_level") or "—"),
                ("Data categories", _fmt_list(meta.get("data_categories"))),
                ("Deployment regions", _fmt_list(meta.get("deployment_regions"))),
                ("Data subject regions", _fmt_list(meta.get("data_subject_regions"))),
                ("Data residency", _fmt_list(meta.get("data_residency"))),
                ("Third-party models", _fmt_list(meta.get("third_party_models"))),
            ]
        ),
        Paragraph("2. Governance controls", st["h2"]),
        _kv_table(
            [
                ("Human oversight documented", _yn(meta.get("human_oversight_documented"))),
                ("Conformity assessment", _yn(meta.get("conformity_assessment_done"))),
                (
                    "Technical documentation",
                    meta.get("technical_documentation_url") or "Not provided",
                ),
                ("Training data documented", _yn(meta.get("training_data_documented"))),
                ("Incident response plan", _yn(meta.get("incident_response_plan"))),
                ("Automated decisions", _yn(meta.get("makes_automated_decisions"))),
                ("Biometric processing", _yn(meta.get("uses_biometrics"))),
                ("Generative AI", _yn(meta.get("uses_generative_ai"))),
            ]
        ),
        Paragraph("3. Risk classification", st["h2"]),
    ]

    class_rows = [["Jurisdiction", "Risk tier", "Score", "Evaluated at", "Applicable"]]
    for c in package.get("classifications", []):
        class_rows.append(
            [
                c["jurisdiction_code"],
                str(c["risk_tier"]).upper(),
                f"{c['score']:.1f}",
                c["evaluated_at"][:19].replace("T", " "),
                "Yes" if c.get("is_applicable", True) else "No",
            ]
        )
    story.append(_grid(class_rows))

    for c in package.get("classifications", []):
        reasons = c.get("applicability_reasons") or []
        notes = ((c.get("details") or {}).get("overlay") or {}).get("notes") or []
        signals = ((c.get("details") or {}).get("baseline") or {}).get("signals") or []
        bullets = (
            [f"• Scope: {r}" for r in reasons]
            + [f"• Overlay: {n}" for n in notes]
            + [f"• Signal: {s.get('rationale')} (+{s.get('weight')})" for s in signals]
        )
        story.append(
            KeepTogether(
                [
                    Paragraph(f"3.{c['jurisdiction_code']} — rationale", st["h3"]),
                    Paragraph("<br/>".join(bullets) or "No rationale recorded.", st["body"]),
                ]
            )
        )

    checks = package.get("policy_checks", [])
    if checks:
        story.append(PageBreak())
        story.append(Paragraph("4. Policy check results", st["h2"]))
        summary = package.get("summary", {})
        story.append(
            _kv_table(
                [
                    ("Total checks", str(summary.get("total", len(checks)))),
                    ("Passed", str(summary.get("passed", 0))),
                    ("Failed", str(summary.get("failed", 0))),
                    ("Warnings", str(summary.get("warnings", 0))),
                    ("Errors", str(summary.get("errors", 0))),
                    ("Overall", "COMPLIANT" if summary.get("compliant") else "NON-COMPLIANT"),
                ]
            )
        )
        story.append(Spacer(1, 8))
        for check in checks:
            color = RESULT_COLORS.get(str(check["result"]), MUTED)
            header = (
                f'<font color="#{color.hexval()[2:]}"><b>{str(check["result"]).upper()}</b></font>'
                f" — {check['policy_key']} v{check['policy_version']} "
                f"({check['jurisdiction_code']}, severity {check['severity']})"
            )
            body = [Paragraph(header, st["h3"]), Paragraph(check["explanation"], st["body"])]
            remediation = check.get("remediation") or []
            if remediation:
                body.append(
                    Paragraph(
                        "<b>Remediation:</b><br/>" + "<br/>".join(f"• {r}" for r in remediation),
                        st["body"],
                    )
                )
            body.append(Spacer(1, 6))
            story.append(KeepTogether(body))

    if package.get("history"):
        story.append(PageBreak())
        story.append(Paragraph("5. Change history", st["h2"]))
        hist_rows = [["Version", "Changed at", "Summary"]]
        for h in package["history"]:
            hist_rows.append(
                [
                    str(h["version"]),
                    h["created_at"][:19].replace("T", " "),
                    h.get("change_summary") or "—",
                ]
            )
        story.append(_grid(hist_rows, col_widths=[20 * mm, 40 * mm, 105 * mm]))

    story.append(Paragraph("Attestation", st["h2"]))
    story.append(Paragraph(template["attestation"], st["body"]))
    story.append(Spacer(1, 6))
    story.append(
        Paragraph(
            f"Package checksum is recorded alongside the JSON manifest. "
            f"Rendered {datetime.now(UTC).isoformat(timespec='seconds')}.",
            st["small"],
        )
    )

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()


def _yn(value: Any) -> str:
    return "Yes" if value else "No"


def _grid(rows: list[list[str]], col_widths: list[float] | None = None) -> Table:
    table = Table(rows, colWidths=col_widths or [33 * mm] * len(rows[0]), repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), BRAND),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D6DCE4")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F9FC")]),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table
