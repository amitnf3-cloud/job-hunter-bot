#!/usr/bin/env python3
"""Build and send the daily job digest email via Gmail SMTP."""

import smtplib
import ssl
from email.message import EmailMessage
from html import escape

GMAIL_SMTP_HOST = "smtp.gmail.com"
GMAIL_SMTP_PORT = 587


def _render_row(score, reason, job):
    company_description = job.get("company_description")
    description_html = (
        f'<span style="color:#555;font-size:0.9em;font-style:italic;">'
        f'{escape(company_description)}</span><br>'
        if company_description
        else ""
    )
    return f"""
    <tr>
      <td style="padding:8px 12px;border-bottom:1px solid #ddd;
                 font-weight:bold;font-size:1.1em;vertical-align:top;">
        {score}/10
      </td>
      <td style="padding:8px 12px;border-bottom:1px solid #ddd;">
        <a href="{escape(job.get("link", "N/A"))}" style="font-weight:bold;
           text-decoration:none;color:#1a73e8;">
          {escape(job.get("title", "N/A"))}
        </a><br>
        <span style="color:#555;">
          {escape(job.get("company_name", "N/A"))}
          &middot; {escape(job.get("location", "N/A"))}
        </span><br>
        {description_html}
        <span style="color:#777;font-size:0.9em;">{escape(reason)}</span>
      </td>
    </tr>
    """


def build_email_html(track_results, min_score):
    """track_results: list of (track_name, scored_jobs) tuples, where each
    scored_jobs entry is (score, reason, job). Only jobs scoring >= min_score
    are included, sorted highest first. Returns (html_body, included_count).
    """
    sections = []
    included_count = 0

    for track_name, scored_jobs in track_results:
        included = sorted(
            (entry for entry in scored_jobs if entry[0] >= min_score),
            key=lambda entry: entry[0],
            reverse=True,
        )
        included_count += len(included)

        if included:
            rows = "".join(_render_row(score, reason, job) for score, reason, job in included)
            table = f"""
            <h2 style="margin-top:32px;">{escape(track_name)}</h2>
            <table style="width:100%;border-collapse:collapse;">
              {rows}
            </table>
            """
        else:
            table = f"""
            <h2 style="margin-top:32px;">{escape(track_name)}</h2>
            <p style="color:#777;">No new jobs scoring {min_score}+ today.</p>
            """

        sections.append(table)

    body = f"""
    <html>
      <body style="font-family:Arial,Helvetica,sans-serif;color:#222;max-width:640px;">
        <h1>Job Hunter Daily Digest</h1>
        <p>{included_count} new job(s) scoring {min_score}+ today.</p>
        {"".join(sections)}
      </body>
    </html>
    """
    return body, included_count


def send_email(subject, html_body, gmail_address, gmail_app_password, email_to):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = gmail_address
    msg["To"] = email_to
    msg.set_content("This email requires an HTML-capable client to view.")
    msg.add_alternative(html_body, subtype="html")

    context = ssl.create_default_context()
    with smtplib.SMTP(GMAIL_SMTP_HOST, GMAIL_SMTP_PORT) as server:
        server.starttls(context=context)
        server.login(gmail_address, gmail_app_password)
        server.send_message(msg)
