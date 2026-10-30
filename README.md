# Viking Power Solar Management MVP

A Streamlit + SQLAlchemy application for CRM pipeline management, solar proposals, invoices and payment tracking.

## Run locally

1. Install Python 3.10 or newer.
2. Open a terminal in this folder.
3. Create and activate a virtual environment (optional but recommended).
4. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

5. Set an application password before using real customer data:

   **Windows PowerShell**
   ```powershell
   $env:APP_PASSWORD="choose-a-long-unique-password"
   ```

   **macOS/Linux**
   ```bash
   export APP_PASSWORD="choose-a-long-unique-password"
   ```

6. Start the app:

   ```bash
   streamlit run app.py
   ```

SQLite is used locally by default. For cloud deployment, configure `DATABASE_URL` to a persistent PostgreSQL database.

## Deploy on GitHub + Streamlit Community Cloud

1. Create a GitHub repository (for example `viking-power-solar-software`).
2. Upload `app.py`, `requirements.txt`, `.gitignore` and `README.md`. Do not upload `.env`, database files, passwords or secrets.
3. Create a persistent PostgreSQL database with a provider such as Supabase or Neon and copy its connection string. Use the provider's recommended connection/pooler URL and ensure it supports SQLAlchemy/psycopg2.
4. Sign in to Streamlit Community Cloud, connect GitHub and deploy the repository's `app.py`.
5. In the app's **Advanced settings / Secrets** area, set environment secrets. Streamlit Cloud secrets are TOML, for example:

   ```toml
   APP_PASSWORD = "choose-a-long-unique-password"
   DATABASE_URL = "postgresql://USER:PASSWORD@HOST:PORT/DATABASE?sslmode=require"
   ```

   Replace the sample connection string with the exact one provided by your database host. Do not commit this file to GitHub.
6. Deploy/redeploy the app and test with dummy data first.
7. Export CSV backups regularly and configure database backups at your database provider.

## Included

- CRM stages: New Enquiries, Contacted, Survey Booked, Survey Done, Quote Sent, Negotiation, Won, Lost.
- Lead details: name, phone, site address, city, state, source, assigned person, roof type, estimated kW, remarks and next follow-up.
- Proposals linked to CRM leads with solar equipment fields, amounts, discount, GST, terms and PDF export.
- Invoices linked to customers and optionally proposals, with PDF export.
- Multiple payments per invoice, automatic paid/balance calculations and status updates.
- Dashboard, overdue/follow-up view and CSV exports.

## Important limitations before production use

This is a usable MVP, not yet a fully audited ERP. It currently has a single shared-password login, basic PDF layouts, no user roles/audit trail, no automatic email/WhatsApp reminders, no payment gateway, and no configured company GSTIN/logo/bank details. Confirm GST treatment and statutory invoice fields with your accountant. Add role-based authentication, database backups, audit logging and a tested restore process before using it as the sole source of business records.
