import os
from datetime import date, datetime
from io import BytesIO

import pandas as pd
import streamlit as st
from sqlalchemy import (create_engine, Column, Integer, String, Text, Date, DateTime,
                        Float, ForeignKey, func)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

st.set_page_config(page_title="Viking Power | Solar CRM", page_icon="☀️", layout="wide")

# --------------------------- Database setup ---------------------------
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///viking_power.db")
try:
    if "DATABASE_URL" in st.secrets:
        DATABASE_URL = st.secrets["DATABASE_URL"]
except Exception:
    pass
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
engine_kwargs = {"pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
engine = create_engine(DATABASE_URL, **engine_kwargs)
Base = declarative_base()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

STAGES = ["New Enquiries", "Contacted", "Survey Booked", "Survey Done", "Quote Sent", "Negotiation", "Won", "Lost"]
ROOF_TYPES = ["RCC", "Sheet Roof", "Tile Roof"]

class Lead(Base):
    __tablename__ = "leads"
    id = Column(Integer, primary_key=True)
    full_name = Column(String(160), nullable=False)
    phone = Column(String(40), nullable=False)
    site_address = Column(Text, default="")
    city = Column(String(100), default="")
    state = Column(String(100), default="Karnataka")
    lead_source = Column(String(100), default="")
    assigned_to = Column(String(120), default="")
    roof_type = Column(String(40), default="RCC")
    system_kw = Column(Float, default=0)
    stage = Column(String(50), default="New Enquiries")
    remarks = Column(Text, default="")
    next_follow_up = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    proposals = relationship("Proposal", back_populates="lead", cascade="all, delete-orphan")
    invoices = relationship("Invoice", back_populates="lead")

class Proposal(Base):
    __tablename__ = "proposals"
    id = Column(Integer, primary_key=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)
    proposal_date = Column(Date, default=date.today)
    system_kw = Column(Float, default=0)
    panel_details = Column(String(200), default="")
    inverter_details = Column(String(200), default="")
    battery_details = Column(String(200), default="")
    description = Column(Text, default="Solar rooftop installation")
    base_amount = Column(Float, default=0)
    discount = Column(Float, default=0)
    gst_rate = Column(Float, default=0)
    terms = Column(Text, default="")
    status = Column(String(40), default="Draft")
    lead = relationship("Lead", back_populates="proposals")
    invoices = relationship("Invoice", back_populates="proposal")

    @property
    def taxable(self): return max(0, self.base_amount - self.discount)
    @property
    def gst_amount(self): return self.taxable * self.gst_rate / 100
    @property
    def total(self): return self.taxable + self.gst_amount

class Invoice(Base):
    __tablename__ = "invoices"
    id = Column(Integer, primary_key=True)
    invoice_number = Column(String(50), unique=True, nullable=False)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)
    proposal_id = Column(Integer, ForeignKey("proposals.id"), nullable=True)
    invoice_date = Column(Date, default=date.today)
    due_date = Column(Date, nullable=True)
    description = Column(Text, default="Solar rooftop installation")
    base_amount = Column(Float, default=0)
    discount = Column(Float, default=0)
    gst_rate = Column(Float, default=0)
    status = Column(String(40), default="Unpaid")
    lead = relationship("Lead", back_populates="invoices")
    proposal = relationship("Proposal", back_populates="invoices")
    payments = relationship("Payment", back_populates="invoice", cascade="all, delete-orphan")

    @property
    def taxable(self): return max(0, self.base_amount - self.discount)
    @property
    def gst_amount(self): return self.taxable * self.gst_rate / 100
    @property
    def total(self): return self.taxable + self.gst_amount
    @property
    def paid(self): return sum(p.amount for p in self.payments)
    @property
    def balance(self): return max(0, self.total - self.paid)

class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    payment_date = Column(Date, default=date.today)
    amount = Column(Float, nullable=False)
    mode = Column(String(50), default="Bank Transfer")
    reference = Column(String(120), default="")
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    invoice = relationship("Invoice", back_populates="payments")

Base.metadata.create_all(engine)

# --------------------------- Helpers ---------------------------
def money(value):
    return f"₹{value:,.2f}"

def pdf_bytes(title, rows, footer_lines=None):
    buff = BytesIO()
    doc = SimpleDocTemplate(buff, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    story = [Paragraph("VIKING POWER", styles["Title"]), Paragraph(title, styles["Heading2"]), Spacer(1, 12)]
    table = Table(rows, colWidths=[170, 330], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#9E1B32")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(table)
    for line in (footer_lines or []):
        story.extend([Spacer(1, 8), Paragraph(str(line).replace("&", "&amp;"), styles["BodyText"])])
    doc.build(story)
    return buff.getvalue()

def lead_label(lead):
    return f"#{lead.id} — {lead.full_name} ({lead.phone})"

def update_invoice_status(invoice):
    if invoice.balance <= 0.01:
        invoice.status = "Paid"
    elif invoice.paid > 0.01:
        invoice.status = "Partially Paid"
    else:
        invoice.status = "Overdue" if invoice.due_date and invoice.due_date < date.today() else "Unpaid"

def setting(name, default=""):
    value = os.getenv(name, default)
    try:
        if name in st.secrets:
            value = st.secrets[name]
    except Exception:
        pass
    return value

def require_login():
    expected = setting("APP_PASSWORD", "")
    if not expected:
        st.error("Application locked: configure APP_PASSWORD in your environment or hosting secrets before using this application.")
        return False
    if st.session_state.get("authenticated"):
        return True
    st.title("Viking Power — Sign in")
    password = st.text_input("Application password", type="password")
    if st.button("Sign in", type="primary"):
        if password == expected:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Incorrect password")
    return False

if not require_login():
    st.stop()

# --------------------------- Sidebar ---------------------------
st.sidebar.title("☀️ Viking Power")
st.sidebar.caption("Solar Business Management")
page = st.sidebar.radio("Navigate", ["Dashboard", "CRM Pipeline", "Proposals", "Invoices", "Payments", "Settings & Data"])
st.sidebar.divider()
st.sidebar.caption("MVP build • Back up your database regularly")

with SessionLocal() as db:
    leads = db.query(Lead).order_by(Lead.created_at.desc()).all()
    proposals = db.query(Proposal).order_by(Proposal.id.desc()).all()
    invoices = db.query(Invoice).order_by(Invoice.id.desc()).all()
    payments = db.query(Payment).order_by(Payment.payment_date.desc()).all()

    if page == "Dashboard":
        st.title("Business Dashboard")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Leads", len(leads))
        c2.metric("Active Leads", sum(1 for x in leads if x.stage not in ["Won", "Lost"]))
        c3.metric("Won Deals", sum(1 for x in leads if x.stage == "Won"))
        c4.metric("Proposals", len(proposals))
        total_invoiced = sum(x.total for x in invoices)
        total_paid = sum(x.paid for x in invoices)
        outstanding = sum(x.balance for x in invoices)
        a, b, c = st.columns(3)
        a.metric("Total Invoiced", money(total_invoiced))
        b.metric("Payments Received", money(total_paid))
        c.metric("Outstanding Balance", money(outstanding))
        st.subheader("Pipeline Overview")
        stage_counts = pd.DataFrame([{"Stage": s, "Leads": sum(1 for x in leads if x.stage == s)} for s in STAGES])
        st.bar_chart(stage_counts.set_index("Stage"))
        st.subheader("Follow-ups Due")
        due = [x for x in leads if x.next_follow_up and x.next_follow_up <= date.today() and x.stage not in ["Won", "Lost"]]
        if due:
            st.dataframe(pd.DataFrame([{"Lead": lead_label(x), "Stage": x.stage, "Follow-up": x.next_follow_up, "Assigned to": x.assigned_to} for x in due]), use_container_width=True)
        else:
            st.info("No follow-ups due today or earlier.")
        st.subheader("Recent Invoices")
        if invoices:
            st.dataframe(pd.DataFrame([{"Invoice": x.invoice_number, "Customer": x.lead.full_name, "Date": x.invoice_date, "Total": x.total, "Paid": x.paid, "Balance": x.balance, "Status": x.status} for x in invoices[:8]]), use_container_width=True)

    elif page == "CRM Pipeline":
        st.title("CRM Pipeline")
        with st.expander("＋ Add New Enquiry", expanded=not bool(leads)):
            with st.form("new_lead", clear_on_submit=True):
                col1, col2 = st.columns(2)
                full_name = col1.text_input("Customer Full Name *")
                phone = col2.text_input("Phone Number *")
                site_address = st.text_area("Site Address")
                col3, col4, col5 = st.columns(3)
                city = col3.text_input("City")
                state = col4.text_input("State", value="Karnataka")
                lead_source = col5.selectbox("Lead Source", ["Referral", "Website", "Google", "Social Media", "Walk-in", "BNI", "Channel Partner", "Repeat Customer", "Other"])
                col6, col7, col8 = st.columns(3)
                assigned_to = col6.text_input("Assigned To")
                roof_type = col7.selectbox("Roof Type", ROOF_TYPES)
                system_kw = col8.number_input("Estimated System (kW)", min_value=0.0, step=0.5)
                col9, col10 = st.columns(2)
                stage = col9.selectbox("Pipeline Stage", STAGES)
                next_follow_up = col10.date_input("Next Follow-up", value=None)
                remarks = st.text_area("Remarks")
                submitted = st.form_submit_button("Save Enquiry", type="primary")
                if submitted:
                    if not full_name.strip() or not phone.strip():
                        st.error("Customer name and phone number are required.")
                    else:
                        db.add(Lead(full_name=full_name.strip(), phone=phone.strip(), site_address=site_address, city=city, state=state, lead_source=lead_source, assigned_to=assigned_to, roof_type=roof_type, system_kw=system_kw, stage=stage, next_follow_up=next_follow_up, remarks=remarks))
                        db.commit(); st.success("Enquiry saved."); st.rerun()
        if leads:
            search = st.text_input("Search by customer, phone, city or address")
            stage_filter = st.multiselect("Filter stages", STAGES, default=STAGES)
            filtered = [x for x in leads if x.stage in stage_filter and (not search or search.lower() in f"{x.full_name} {x.phone} {x.city} {x.site_address}".lower())]
            st.caption(f"Showing {len(filtered)} of {len(leads)} leads")
            st.dataframe(pd.DataFrame([{"ID": x.id, "Customer": x.full_name, "Phone": x.phone, "City": x.city, "Roof": x.roof_type, "kW": x.system_kw, "Source": x.lead_source, "Assigned To": x.assigned_to, "Stage": x.stage, "Follow-up": x.next_follow_up, "Remarks": x.remarks} for x in filtered]), use_container_width=True, hide_index=True)
            st.subheader("Open / Update Lead")
            chosen_id = st.selectbox("Choose lead", [x.id for x in filtered], format_func=lambda i: lead_label(db.get(Lead, i))) if filtered else None
            if chosen_id:
                item = db.get(Lead, chosen_id)
                with st.form("edit_lead"):
                    x1, x2, x3 = st.columns(3)
                    new_stage = x1.selectbox("Stage", STAGES, index=STAGES.index(item.stage))
                    new_assigned = x2.text_input("Assigned To", value=item.assigned_to or "")
                    new_follow = x3.date_input("Next Follow-up", value=item.next_follow_up)
                    new_remarks = st.text_area("Remarks", value=item.remarks or "")
                    if st.form_submit_button("Update Lead", type="primary"):
                        item.stage = new_stage; item.assigned_to = new_assigned; item.next_follow_up = new_follow; item.remarks = new_remarks
                        db.commit(); st.success("Lead updated."); st.rerun()
                with st.expander("Lead details"):
                    st.write({"Customer": item.full_name, "Phone": item.phone, "Site address": item.site_address, "City": item.city, "State": item.state, "Lead source": item.lead_source, "Roof type": item.roof_type, "Estimated kW": item.system_kw, "Created": item.created_at})
        else:
            st.info("Add your first enquiry above.")

    elif page == "Proposals":
        st.title("Solar Proposals")
        if not leads:
            st.info("Create a CRM lead before making a proposal.")
        else:
            with st.expander("＋ Create Proposal", expanded=not bool(proposals)):
                with st.form("new_proposal"):
                    lead_id = st.selectbox("Customer / CRM Lead", [x.id for x in leads], format_func=lambda i: lead_label(db.get(Lead, i)))
                    lead_obj = db.get(Lead, lead_id)
                    p1, p2, p3 = st.columns(3)
                    proposal_date = p1.date_input("Proposal Date", value=date.today())
                    system_kw = p2.number_input("System Size (kW)", min_value=0.0, value=float(lead_obj.system_kw or 0), step=0.5)
                    status = p3.selectbox("Status", ["Draft", "Sent", "Accepted", "Rejected", "Expired"])
                    panel_details = st.text_input("Solar Panels / Brand / Wattage", placeholder="e.g. EVVO 640Wp TOPCon")
                    inverter_details = st.text_input("Inverter Details", placeholder="e.g. 10kW 3-phase hybrid inverter")
                    battery_details = st.text_input("Battery Details", placeholder="e.g. 10kWh LiFePO4 or Not Applicable")
                    description = st.text_input("Description", value="Supply, installation and commissioning of rooftop solar system")
                    p4, p5, p6 = st.columns(3)
                    base_amount = p4.number_input("Base Amount (₹)", min_value=0.0, step=1000.0)
                    discount = p5.number_input("Discount (₹)", min_value=0.0, step=500.0)
                    gst_rate = p6.number_input("GST Rate (%)", min_value=0.0, max_value=100.0, value=0.0, step=1.0)
                    terms = st.text_area("Payment Terms / Notes", value="Subject to final site survey and approved scope. GST rate to be verified before issuing customer documents.")
                    if st.form_submit_button("Save Proposal", type="primary"):
                        if base_amount <= 0:
                            st.error("Enter a base amount greater than zero.")
                        elif discount > base_amount:
                            st.error("Discount cannot exceed base amount.")
                        else:
                            p = Proposal(lead_id=lead_id, proposal_date=proposal_date, system_kw=system_kw, panel_details=panel_details, inverter_details=inverter_details, battery_details=battery_details, description=description, base_amount=base_amount, discount=discount, gst_rate=gst_rate, terms=terms, status=status)
                            db.add(p)
                            if status == "Sent": lead_obj.stage = "Quote Sent"
                            if status == "Accepted": lead_obj.stage = "Won"
                            db.commit(); st.success("Proposal saved and linked to CRM lead."); st.rerun()
            if proposals:
                st.dataframe(pd.DataFrame([{"Proposal ID": p.id, "Customer": p.lead.full_name, "Date": p.proposal_date, "kW": p.system_kw, "Base": p.base_amount, "Discount": p.discount, "GST %": p.gst_rate, "Total": p.total, "Status": p.status} for p in proposals]), use_container_width=True, hide_index=True)
                st.subheader("View / Download Proposal")
                pid = st.selectbox("Select proposal", [p.id for p in proposals], format_func=lambda i: f"Proposal #{i} — {db.get(Proposal, i).lead.full_name}")
                p = db.get(Proposal, pid); l = p.lead
                st.write(f"**{l.full_name}** • {l.phone} • {l.city}, {l.state}")
                st.write(f"System: **{p.system_kw:g} kW** | Total: **{money(p.total)}** | Status: **{p.status}**")
                rows = [["Item", "Details"], ["Customer", f"{l.full_name} | {l.phone}"], ["Site", f"{l.site_address}, {l.city}, {l.state}"], ["System size", f"{p.system_kw:g} kW"], ["Panels", p.panel_details or "—"], ["Inverter", p.inverter_details or "—"], ["Battery", p.battery_details or "—"], ["Scope", p.description], ["Base amount", money(p.base_amount)], ["Discount", money(p.discount)], ["Taxable amount", money(p.taxable)], [f"GST ({p.gst_rate:g}%)", money(p.gst_amount)], ["TOTAL", money(p.total)], ["Terms", p.terms or "—"]]
                st.download_button("Download Proposal PDF", pdf_bytes(f"Solar Proposal #{p.id}", rows), file_name=f"VikingPower_Proposal_{p.id}.pdf", mime="application/pdf")

    elif page == "Invoices":
        st.title("Invoices")
        if not leads:
            st.info("Create a CRM lead first.")
        else:
            with st.expander("＋ Create Invoice", expanded=not bool(invoices)):
                with st.form("new_invoice"):
                    lead_id = st.selectbox("Customer / CRM Lead", [x.id for x in leads], format_func=lambda i: lead_label(db.get(Lead, i)))
                    customer_proposals = [p for p in proposals if p.lead_id == lead_id]
                    proposal_options = [None] + [p.id for p in customer_proposals]
                    proposal_id = st.selectbox("Copy details from proposal (optional)", proposal_options, format_func=lambda i: "No proposal selected" if i is None else f"Proposal #{i} — {db.get(Proposal, i).status}")
                    inv_date = st.date_input("Invoice Date", value=date.today())
                    due_date = st.date_input("Payment Due Date", value=date.today())
                    default_base = db.get(Proposal, proposal_id).base_amount if proposal_id else 0.0
                    default_discount = db.get(Proposal, proposal_id).discount if proposal_id else 0.0
                    default_gst = db.get(Proposal, proposal_id).gst_rate if proposal_id else 0.0
                    default_desc = db.get(Proposal, proposal_id).description if proposal_id else "Solar rooftop installation"
                    description = st.text_input("Invoice Description", value=default_desc)
                    i1, i2, i3 = st.columns(3)
                    base_amount = i1.number_input("Base Amount (₹)", min_value=0.0, value=float(default_base), step=1000.0, key="inv_base")
                    discount = i2.number_input("Discount (₹)", min_value=0.0, value=float(default_discount), step=500.0, key="inv_discount")
                    gst_rate = i3.number_input("GST Rate (%)", min_value=0.0, max_value=100.0, value=float(default_gst), step=1.0, key="inv_gst")
                    if st.form_submit_button("Create Invoice", type="primary"):
                        if base_amount <= 0 or discount > base_amount:
                            st.error("Enter a valid base amount and discount.")
                        else:
                            next_num = (db.query(func.count(Invoice.id)).scalar() or 0) + 1
                            inv = Invoice(invoice_number=f"VP-{date.today().year}-{next_num:04d}", lead_id=lead_id, proposal_id=proposal_id, invoice_date=inv_date, due_date=due_date, description=description, base_amount=base_amount, discount=discount, gst_rate=gst_rate)
                            db.add(inv); db.commit(); st.success(f"Invoice {inv.invoice_number} created."); st.rerun()
            if invoices:
                for inv in invoices: update_invoice_status(inv)
                db.commit()
                st.dataframe(pd.DataFrame([{"Invoice": x.invoice_number, "Customer": x.lead.full_name, "Date": x.invoice_date, "Due": x.due_date, "Total": x.total, "Paid": x.paid, "Balance": x.balance, "Status": x.status} for x in invoices]), use_container_width=True, hide_index=True)
                st.subheader("View / Download Invoice")
                iid = st.selectbox("Select invoice", [x.id for x in invoices], format_func=lambda i: f"{db.get(Invoice, i).invoice_number} — {db.get(Invoice, i).lead.full_name}")
                inv = db.get(Invoice, iid); l = inv.lead
                rows = [["Item", "Details"], ["Invoice number", inv.invoice_number], ["Invoice date", str(inv.invoice_date)], ["Due date", str(inv.due_date or "—")], ["Customer", f"{l.full_name} | {l.phone}"], ["Site", f"{l.site_address}, {l.city}, {l.state}"], ["Description", inv.description], ["Base amount", money(inv.base_amount)], ["Discount", money(inv.discount)], ["Taxable amount", money(inv.taxable)], [f"GST ({inv.gst_rate:g}%)", money(inv.gst_amount)], ["Invoice total", money(inv.total)], ["Amount paid", money(inv.paid)], ["Balance due", money(inv.balance)], ["Status", inv.status]]
                st.download_button("Download Invoice PDF", pdf_bytes(f"Tax Invoice {inv.invoice_number}", rows, ["Please verify GST details, statutory invoice requirements and tax rates before issuing this document."]), file_name=f"{inv.invoice_number}.pdf", mime="application/pdf")

    elif page == "Payments":
        st.title("Payment Tracking")
        if not invoices:
            st.info("Create an invoice before recording payments.")
        else:
            for inv in invoices: update_invoice_status(inv)
            db.commit()
            unpaid = [x for x in invoices if x.balance > 0.01]
            with st.expander("＋ Record Payment", expanded=bool(unpaid)):
                if unpaid:
                    with st.form("new_payment"):
                        invoice_id = st.selectbox("Invoice", [x.id for x in unpaid], format_func=lambda i: f"{db.get(Invoice, i).invoice_number} — {db.get(Invoice, i).lead.full_name} — Balance {money(db.get(Invoice, i).balance)}")
                        pay_date = st.date_input("Payment Date", value=date.today())
                        amount = st.number_input("Amount Received (₹)", min_value=1.0, step=500.0)
                        mode = st.selectbox("Payment Mode", ["Bank Transfer", "UPI", "Cash", "Cheque", "Card", "Other"])
                        reference = st.text_input("Transaction / UTR / Cheque Reference")
                        notes = st.text_area("Notes")
                        if st.form_submit_button("Save Payment", type="primary"):
                            inv = db.get(Invoice, invoice_id)
                            if amount > inv.balance + 0.01:
                                st.error(f"Payment exceeds outstanding balance of {money(inv.balance)}.")
                            else:
                                db.add(Payment(invoice_id=invoice_id, payment_date=pay_date, amount=amount, mode=mode, reference=reference, notes=notes))
                                db.flush(); update_invoice_status(inv); db.commit(); st.success("Payment recorded and invoice balance updated."); st.rerun()
                else:
                    st.success("All invoices are fully paid.")
            st.subheader("Invoice Balances")
            st.dataframe(pd.DataFrame([{"Invoice": x.invoice_number, "Customer": x.lead.full_name, "Invoice Total": x.total, "Paid": x.paid, "Balance": x.balance, "Due Date": x.due_date, "Status": x.status} for x in invoices]), use_container_width=True, hide_index=True)
            st.subheader("Payment History")
            if payments:
                st.dataframe(pd.DataFrame([{"Date": x.payment_date, "Invoice": x.invoice.invoice_number, "Customer": x.invoice.lead.full_name, "Amount": x.amount, "Mode": x.mode, "Reference": x.reference, "Notes": x.notes} for x in payments]), use_container_width=True, hide_index=True)
            else:
                st.info("No payments recorded yet.")
            st.caption("Reminder workflow: this version highlights overdue invoices in status. Automatic email/WhatsApp reminders require a configured messaging provider and are a later integration.")

    elif page == "Settings & Data":
        st.title("Settings & Data Export")
        st.warning("GST rates and invoice compliance should be verified with your accountant before using generated PDFs as official tax invoices. Configure company GSTIN, registered address, state code, logo and bank details before production use.")
        st.subheader("Export your records")
        for label, data in [
            ("CRM Leads", [{"id": x.id, "full_name": x.full_name, "phone": x.phone, "site_address": x.site_address, "city": x.city, "state": x.state, "lead_source": x.lead_source, "assigned_to": x.assigned_to, "roof_type": x.roof_type, "system_kw": x.system_kw, "stage": x.stage, "remarks": x.remarks, "next_follow_up": str(x.next_follow_up or "")} for x in leads]),
            ("Proposals", [{"id": x.id, "lead_id": x.lead_id, "customer": x.lead.full_name, "date": str(x.proposal_date), "system_kw": x.system_kw, "base_amount": x.base_amount, "discount": x.discount, "gst_rate": x.gst_rate, "total": x.total, "status": x.status} for x in proposals]),
            ("Invoices", [{"id": x.id, "invoice_number": x.invoice_number, "lead_id": x.lead_id, "customer": x.lead.full_name, "date": str(x.invoice_date), "due_date": str(x.due_date or ""), "total": x.total, "paid": x.paid, "balance": x.balance, "status": x.status} for x in invoices]),
            ("Payments", [{"id": x.id, "invoice_id": x.invoice_id, "invoice_number": x.invoice.invoice_number, "customer": x.invoice.lead.full_name, "date": str(x.payment_date), "amount": x.amount, "mode": x.mode, "reference": x.reference, "notes": x.notes} for x in payments]),
        ]:
            csv = pd.DataFrame(data).to_csv(index=False).encode("utf-8")
            st.download_button(f"Download {label} CSV", csv, file_name=f"viking_power_{label.lower().replace(' ', '_')}.csv", mime="text/csv")
        st.subheader("Deployment notes")
        st.markdown("- Set `DATABASE_URL` to a persistent PostgreSQL database for cloud deployment.\n- Set `APP_PASSWORD` in your hosting provider's secrets.\n- Do not commit passwords or database credentials to GitHub.\n- Back up the database regularly.")

st.sidebar.caption("Viking Power • Internal business tool")
