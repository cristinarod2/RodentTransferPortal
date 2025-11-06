#!/usr/bin/env python3
import streamlit as st
from datetime import date
from PIL import Image
from fpdf import FPDF
import smtplib
from email.message import EmailMessage
import os
from pathlib import Path
import base64
from email.mime.text import MIMEText


	
# Date formatting helper
def fmt_date(d):
	if not d:
		return "-"
	return d.strftime("%b %d, %Y")  # e.g., "Nov 10, 2025"

# =========================================================
# CONFIG
# =========================================================
SENDER_EMAIL = st.secrets["SENDER_EMAIL"]          # << fill later
APP_PASSWORD = st.secrets["APP_PASSWORD"]             # << fill later
DEFAULT_EMAIL = st.secrets["DEFAULT_EMAIL"]     # << fill later
USERS_FILE = None
ALLOWED_USERS = st.secrets.get("USERS")   # fallback list

# ─────────────────────────────
# Utility functions
# ─────────────────────────────

def load_allowed_users():
	"""Load list of allowed users from Streamlit secrets."""
	return list(ALLOWED_USERS)

def save_allowed_users(users):
	"""Stub kept for compatibility (no file writing needed)."""
	pass		
# ─────────────────────────────
# Streamlit app setup
# ─────────────────────────────
st.set_page_config(page_title="Rodent Transfer to CCM", layout="centered")


logo = Image.open("LOGO2.png")
st.sidebar.image(logo, width="content")


# =========================================================
# SESSION STATE INIT
# =========================================================
if "locked" not in st.session_state:
	st.session_state.locked = False
if "form_data" not in st.session_state:
	st.session_state.form_data = None
if "filename" not in st.session_state:
	st.session_state.filename = None
if "attachments" not in st.session_state:
	st.session_state.attachments = None
	
	
# =============================
# PDF Styling (Modern Layout)
# =============================
	
PRIMARY_COLOR = (29, 41, 61)   
SECTION_BG = (245, 245, 245)
TEXT_GREY = (70, 70, 70)
TEXT_BLACK = (0, 0, 0)


# Define a reliable absolute path to the logo
LOGO_PATH = Path(__file__).parent / "LOGO2_flat.png"

	
class TransferPDF(FPDF):
	def header(self):
		# Draw dark header background
		self.set_fill_color(*PRIMARY_COLOR)
		self.rect(0, 0, 210, 35, "F")
		
		# --- Draw logo centered ---
		try:
			logo_width = 42
			page_width = 210
			x_pos = (page_width - logo_width) / 2
			self.image(str(LOGO_PATH), x=x_pos, y=5, w=logo_width)
			print(f"✅ Logo drawn at {LOGO_PATH}")
		except Exception as e:
			print(f"⚠️ Logo draw failed: {e}")
			
			# --- Title text centered under logo ---
		self.set_xy(0, 23)
		self.set_text_color(255, 255, 255)
		self.set_font("Arial", "", 20)
		self.cell(210, 10, "Rodent Transfer Request to CCM", align="C")
		self.ln(12)
		
	def section_title(self, title):
		self.set_draw_color(220, 220, 220)
		self.ln(2)
		#self.line(10, self.get_y(), 200, self.get_y())
		#self.ln(1)
		self.set_fill_color(*SECTION_BG)
		self.set_text_color(*PRIMARY_COLOR)
		self.set_font("Arial", "B", 11)
		self.cell(0, 8, f"  {title}", ln=True, fill=True)
		self.ln(3)
		
	def field(self, label, value):
		"""Write one label/value row, cleaning unsupported Unicode."""
		label = str(label) if label else "-"
		value = "-" if not value else str(value)
		
		# Replace problematic Unicode
		replacements = {
			"—": "-", "–": "-", "•": "-",
			"·": "-", "‒": "-",
			"“": '"', "”": '"', "‘": "'", "’": "'",
			"…": "...", "µ": "u", "²": "2", "³": "3", "⁴": "4",
		}
		for bad, good in replacements.items():
			label = label.replace(bad, good)
			value = value.replace(bad, good)
			
		# Force to Latin-1 compatible bytes then back
		value = value.encode("latin-1", "replace").decode("latin-1")
		
		# Label
		self.set_font("Arial", "B", 10)
		self.set_text_color(*PRIMARY_COLOR)
		self.cell(48, 5, f"{label}:", 0, 0)
		
		# Value
		self.set_font("Arial", "", 10)
		self.set_text_color(*TEXT_BLACK)
		self.multi_cell(0, 5, value)
		self.ln(0.5)
		
		
def create_pdf(form_data, attachments, filename):
	"""Generate PDF safely using TransferPDF class."""
	pdf = TransferPDF()
	pdf.set_margins(12, 15, 12)
	pdf.add_page()
	
	# Render sections
	for section, fields in form_data.items():
		pdf.section_title(section)
		for label, value in fields.items():
			pdf.field(label, value)
		pdf.ln(2)
		
	# Attachment list
	pdf.section_title("Attachments")
	if not attachments:
		pdf.field("Files", "No attachments uploaded.")
	else:
		pdf.set_font("Arial", "B", 10)
		pdf.cell(135, 7, "Filename", border=1)
		pdf.cell(40, 7, "Type", border=1, ln=True)
		pdf.set_font("Arial", "", 10)
		for f in attachments:
			name = f.name
			ext = name.split(".")[-1].upper()
			pdf.cell(135, 7, name.encode("latin-1", "replace").decode("latin-1"), border=1)
			pdf.cell(40, 7, ext, border=1, ln=True)
			
	pdf.output(filename)
	return filename


# =========================================================
# EMAIL
# =========================================================
def send_email(recipient, subject, body, file_path, cc=None):
	msg = EmailMessage()
	msg["Subject"] = subject
	msg["From"] = SENDER_EMAIL
	msg["To"] = recipient
	if cc:
		msg["Cc"] = cc
		
	# Detect HTML body
	if "<html>" in body:
		msg.add_alternative(body, subtype="html")
	else:
		msg.set_content(body)
		
	# Attach main PDF
	with open(file_path, "rb") as f:
		msg.add_attachment(
			f.read(),
			maintype="application",
			subtype="pdf",
			filename=os.path.basename(file_path)
		)
		
	# Attach any uploaded files
	if st.session_state.attachments:
		for f in st.session_state.attachments:
			data = f.read()
			ext = f.name.split(".")[-1].lower()
			subtype = {
				"pdf": "pdf",
				"docx": "vnd.openxmlformats-officedocument.wordprocessingml.document",
				"xlsx": "vnd.openxmlformats-officedocument.spreadsheetml.sheet"
			}.get(ext, "octet-stream")
			msg.add_attachment(
				data,
				maintype="application",
				subtype=subtype,
				filename=f.name
			)
			
	# Send through Gmail
	with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
		smtp.login(SENDER_EMAIL, APP_PASSWORD)
		smtp.send_message(msg)
		
		
# =========================================================
# UI — SIDEBAR UPLOAD + CHECKLIST
# =========================================================
#st.sidebar.image(logo, width='stretch')
st.sidebar.write("📎 Mandatory attachments:")
# Sidebar branding

# Checkboxes for suggested documents
st.sidebar.checkbox("Monitoring sheets", key="chk_monitor")

st.sidebar.write("📎 Recommended attachments:")

st.sidebar.checkbox("Cage map / IDs", key="chk_cage")
st.sidebar.checkbox("Tumour Growth Curves", key="chk_tumour")
#st.sidebar.checkbox("ACC amendment", key="chk_acc")
#st.sidebar.checkbox("Vet notes", key="chk_vet")

st.sidebar.markdown(
	"""
	<div style="
		background-color:rgba(0,122,255,0.15);
		border-left: 4px solid #007AFF;
		border-radius:6px;
		padding:8px 10px;
		font-size:13px;
		color:#e5e8ef;
		line-height:1.4;
		margin-top:10px;
	">
	💡 You can also include any other documents relevant to your animals that may be important for this study or transfer.
	</div>
	""",
	unsafe_allow_html=True
)
#uploaded_files = st.sidebar.file_uploader("Upload Documents", type=["pdf","docx","xlsx"], accept_multiple_files=True, key="file_uploader")


uploaded_files = st.sidebar.file_uploader(
	"Upload attachments",
	type=["pdf","docx","xlsx"],
	accept_multiple_files=True,
	key="file_uploader"
)


st.markdown(
	"""
	<style>
	
	/* Sidebar base look */
	section[data-testid="stSidebar"] {
		background-color: #1d293d !important;
	}
	section[data-testid="stSidebar"] * {
		color: #a6b1c5 !important;
	}
	
	/* Modern Streamlit file uploader structure */
	div[data-testid="stFileUploader"] {
		background-color: rgba(45, 60, 85, 0.9) !important;
		border: 1px dashed rgba(255, 255, 255, 0.4) !important;
		border-radius: 8px !important;
		padding: 12px !important;
		color: #ffffff !important;
		transition: all 0.3s ease-in-out;
	}
	
	/* keep icon and text aligned and visible */
	div[data-testid="stFileUploader"] svg {
		fill: #ffffff !important;
		opacity: 0.9 !important;
	}
	
	div[data-testid="stFileUploader"] div[data-testid="stFileUploaderDropzone"] {
		background-color: transparent !important;
		color: #ffffff !important;
		font-size: 11px !important;
		font-weight: 400 !important;
	}
	
	/* Hover effect */
	div[data-testid="stFileUploader"]:hover {
		border-color: #007AFF !important;
		box-shadow: 0 0 8px rgba(0, 122, 255, 0.25);
	}
	
	/* Button text (Browse files) */
	div[data-testid="stFileUploader"] button {
		background-color: #007AFF !important;
		color: white !important;
		border: none !important;
		border-radius: 4px !important;
		font-size: 13px !important;
		font-weight: 500 !important;
	}
	
	div[data-testid="stFileUploader"] button:hover {
		background-color: #339CFF !important;
	}
	
	</style>
	""", 
	unsafe_allow_html=True)

# -------------------------------------------------------
# Access control with persistent user list
# -------------------------------------------------------
# =========================================================
# 🔒 Modern Access Verification (Streamlined + Styled)
# =========================================================

# Load allowed users (from secrets or fallback)
if "allowed_users" not in st.session_state:
	st.session_state.allowed_users = load_allowed_users()
	
# ---- Stylish card header ----
st.sidebar.markdown(
	"""
	<div style="
		background: linear-gradient(145deg, rgba(38,52,74,0.9), rgba(27,40,60,0.9));
		border: 1px solid rgba(255,255,255,0.1);
		border-radius: 10px;
		padding: 14px 16px 10px 16px;
		margin-top: 16px;
		color: #e5e8ef;
		box-shadow: 0 2px 8px rgba(0,0,0,0.25);
		font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
	">
		<h5 style="
			color:#BBD4FF; 
			margin: 2px 0 8px 0; 
			font-weight:600; 
			font-size:14px; 
			letter-spacing:0.2px;">
			🔒 Access Verification
		</h5>
		<p style="
			font-size:12.5px; 
			line-height:1.4; 
			color:#c7ccdb; 
			margin-bottom:8px;">
			Please enter your <strong>access key</strong> below to continue.
		</p>
	</div>
	""",
	unsafe_allow_html=True
)

# ---- Password input ----
password = st.sidebar.text_input(
	type="password",
	placeholder="Enter access key",
	label="Access key",
	label_visibility="hidden",
)

# ---- Custom style for password field ----
st.markdown("""
<style>
/* Password field styling to match sidebar theme */
section[data-testid="stSidebar"] input[type="password"] {
	background-color: rgba(255,255,255,0.07);
	border: 1px solid rgba(255,255,255,0.18);
	border-radius: 6px;
	color: #e8ecf3;
	font-size: 13px;
	padding: 7px 10px;
	width: 100%;
	transition: all 0.2s ease-in-out;
}

section[data-testid="stSidebar"] input[type="password"]:focus {
	border-color: #007AFF;
	box-shadow: 0 0 6px rgba(0,122,255,0.4);
	background-color: rgba(255,255,255,0.10);
	outline: none;
}
</style>
""", unsafe_allow_html=True)

# ---- Access validation ----
if password.lower().strip() not in [u.lower() for u in st.session_state.allowed_users]:
	st.warning("Access restricted. Please enter a valid key to continue.")
	st.stop()
st.sidebar.success(f"✅ Access granted to {password.strip()}")	

# =========================================================
# MAIN FORM
# =========================================================


st.title("Rodent Transfer Request to CCM")

def disable():
	return st.session_state.locked

# General
requester = st.text_input("Requester Name", placeholder="e.g., Your Name", key="req", disabled=disable())
requester_email = st.text_input("Requester Email", placeholder="e.g., your.name@ubc.ca", key="req_email", disabled=disable())
facility_email = st.text_input("Facility Manager Email", placeholder="e.g., ccm@ubc.ca", key="fac_email", disabled=disable())
lab_group = st.text_input("Lab Group", placeholder="e.g., PI Lab", key="lab", disabled=disable())
protocol = st.text_input("ACC Protocol", placeholder="e.g., A25-0001", key="prot", disabled=disable())
Facility = st.text_input("Facility", placeholder="e.g., BC Cancer", key="inst", disabled=disable())
transfer_date = st.date_input("Requested Transfer Date", disabled=disable())
# Format transfer date nicely for display
transfer_date_str = transfer_date.strftime("%b %d, %Y")  # e.g. "Nov 10, 2025"

comments = st.text_area("Additional Comments", placeholder=(
	"Add any relevant notes about the animals, scheduling, or experimental context. "
	"e.g., 'After 10 days no tumours are yet visible but expected to appear soon.' "
	"You may also note logistical details such as 'Transfer timing may vary ±1 day "
	"depending on facility staff availability.'"
), key="com", disabled=disable())

# Animal info
strain = st.text_input("Strain", placeholder="e.g., C57BL/6J", key="strain", disabled=disable())
quantity = st.number_input("Number of Animals", min_value=1, step=1, key="qty", disabled=disable())
gender = st.selectbox("Sex", ["Male", "Female", "Both"], key="sex", disabled=disable())

# ======= Animal Age Section =======
st.subheader("Animal Age")

# Track how many DOB fields are shown
if "dob_fields" not in st.session_state:
	st.session_state.dob_fields = 1
	
# Function to add one more DOB input
def add_dob_field():
	if st.session_state.dob_fields < 3:
		st.session_state.dob_fields += 1
		
# DOB inputs based on how many active fields
dob_inputs = []
for i in range(st.session_state.dob_fields):
	dob = st.date_input(
		f"DOB (Group {i+1})",
		key=f"dob{i+1}",
		disabled=disable()
	)
	dob_inputs.append(dob)
	
# Button to add another DOB
if st.session_state.dob_fields < 3 and not disable():
	st.button("➕ Add another DOB", on_click=add_dob_field)
	
# --- Calculate ages ---
def calc_age_weeks(dob):
	if dob:
		return round((transfer_date - dob).days / 7, 1)
	return None

ages = list(filter(None, [calc_age_weeks(d) for d in dob_inputs]))

# Create age text
age_range = ""
if ages:
	if len(ages) == 1:
		age_range = f"{ages[0]} weeks"
	else:
		age_range = f"{min(ages)} – {max(ages)} weeks"
		
# Display age range
if age_range:
	st.info(f"Estimated Age at Transfer: **{age_range}**")
else:
	st.warning("Please enter at least one DOB to calculate age.")
############	
cage_numbers = st.text_area("Cage Numbers", placeholder="e.g., 563742, 563735, 563559", key="cages", disabled=disable())

# ===============================
# Tumour Section (if applicable)
# ===============================

tumour = st.checkbox("Tumour-bearing animals?", key="tumour_toggle", disabled=disable())
tumour_info = {}

if tumour:
	with st.expander("⚠️ Tumour-bearing Animals (required)", expanded=True):
		st.caption(
			"Provide tumour details as per your **ACC protocol**. "
			"These guidelines will be followed at CCM; please be as accurate as possible so monitoring can continue seamlessly."
		)
		
		
		tumour_cellline = st.text_input(
			"Cell Line",
			placeholder="e.g., AR42J - rat pancreatic tumor cell line - https://www.atcc.org/products/crl-1492",
			key="t_cellline",
			disabled=disable()
		)
		
		tumour_location = st.text_input(
			"Via / Tumour Location",
			placeholder="e.g., SQ / Left flank",
			key="t_location",
			disabled=disable(),
			help="Enter both the inoculation route and anatomical site (e.g., SQ / Left flank, IV / Lungs)."

		)
		
		tumour_inoc_date = st.date_input(
			"Inoculation Date",
			key="t_inocdate",
			disabled=disable()
		)
		
		tumour_volume = st.text_input(
			"Current Tumour Volume (mm³)",
			placeholder="e.g., ~325 mm³ (range 280–390 mm³)",
			key="t_volume",
			disabled=disable(),
			help="If multiple animals, include a range."
		
		)
		
		tumour_monitor = st.text_input(
			"Monitoring Frequency",
			placeholder="e.g., Twice weekly (Mon/Thu); increase to daily if rapid tumour growth observed",
			key="t_monitor",
			disabled=disable(),
			help="Specify the monitoring schedule (e.g., Mon/Thu). Include any adjustments when tumour growth accelerates or approaches the humane endpoint."
		)
		
		tumour_notes = st.text_area(
			"Tumour-related Notes",
			placeholder=(
				"Include tumour growth rate (e.g., doubling every 24 h), condition, grooming, mobility, "
				"ulceration status, or any signs of distress."
			),
			key="t_notes",
			disabled=disable(),
			help=(
				"Describe tumour progression and general health observations, including growth rate, behaviour, "
				"and ulceration status. If ulceration is permitted under your approved protocol, specify the "
				"corresponding humane endpoints (e.g., immediate monitoring and euthanasia criteria)."
			)
		)
		
		# ---- Calculate tumour duration ----
		tumour_duration = "-"
		if tumour_inoc_date:
			tumour_duration_days = (transfer_date - tumour_inoc_date).days
			tumour_duration = f"{tumour_duration_days} days"
			
		# ---- Package tumour info for PDF/email ----
		tumour_info = {
			"Cell Line": tumour_cellline,
			"Tumour Location": tumour_location,
			"Inoculation Date": fmt_date(tumour_inoc_date) if tumour_inoc_date else "-",
			"Tumour Duration": tumour_duration,
			"Current Tumour Volume": tumour_volume,
			"Monitoring Frequency": tumour_monitor,
			"Notes": tumour_notes,
         }	
# Humane endpoints
with st.expander("🩺 Humane Endpoints", expanded=False):
	weight_loss = st.text_input("Weight Loss Limit (%)", placeholder="e.g., ≥ 20%", key="wloss", disabled=disable())
	tumour_volume_limit = st.text_input("Tumour Vol Limit (mm³)", placeholder="e.g., max 1500 mm³", key="tlimit", disabled=disable())
	distress_signs=st.text_area(
		"Signs of Distress",
		placeholder=(
			"e.g., ruffled fur, reduced mobility, hunched posture, lack of grooming, weight loss, "
			"decreased food or water intake, laboured breathing, lethargy, isolation from cage mates, "
			"abnormal vocalization, self-mutilation, or ulceration."
		),
		key="distress",
		disabled=disable(),
		help=(
			"List any clinical or behavioural signs that may indicate pain, discomfort, or distress. "
			"Examples: ruffled fur, hunched posture, reduced mobility, lack of grooming, "
			"weight loss, laboured breathing, dehydration, isolation, abnormal vocalization, "
			"self-mutilation, or ulceration at the tumour site."
		)
)

# 💡 Recommendation box (AFTER Humane Endpoints)
st.info(
"💡 **Recommendation:** Summarize key points from your approved animal-use protocol relevant to tumour monitoring "
"and humane endpoints. Include only essential instructions that help CCM staff act appropriately — such as "
"criteria for ulceration, intervention thresholds, and when to contact the clinical veterinarians immediately."
)


	
	
send_copy = st.checkbox("Send requester a copy", key="copy", disabled=disable())

# =========================================================
# PREVIEW & SUBMIT WORKFLOW
# =========================================================

# -------------------------
# Generate PDF Preview
# -------------------------
if st.button("📄 Preview PDF", disabled=disable()):
	
	# 1️⃣ Collect uploaded and checked attachments
	uploaded_names = [f.name for f in uploaded_files] if uploaded_files else []

	checked_items = []
	if st.session_state.get("chk_monitoring"): checked_items.append("Monitoring sheet")
	if st.session_state.get("chk_cages"): checked_items.append("Cage map / IDs")
	if st.session_state.get("chk_tumour"): checked_items.append("Tumour log")
	if st.session_state.get("chk_protocol"): checked_items.append("ACC amendment")
	if st.session_state.get("chk_vet"): checked_items.append("Vet notes")

	all_attachments = uploaded_names + checked_items
	
	# Package form data
	form_data = {
		"General Info": {
			"Requester": requester,
			"Requester Email": requester_email,
			"Facility": Facility,
			"Lab Group": lab_group,
			"ACC Protocol": protocol,
			"Requested Transfer Date": fmt_date(transfer_date),
			"Comments": comments,
		},
		"Animal Info": {
			"Strain": strain,
			"Number of Animals": quantity,
			"Sex": gender,
			"Age at Transfer": age_range,
			"DOB Entries": ", ".join([fmt_date(d) for d in dob_inputs if d]),
			"Cages": cage_numbers,
			"Tumour-bearing": "Yes" if tumour else "No",
		},
		"Tumour Info": tumour_info if tumour else {},
		"Humane Endpoints": {
			"Weight Loss Limit (%)": weight_loss,
			"Tumour V Limit (mm³)": tumour_volume_limit,
			"Signs of Distress": distress_signs,
		},
#		"Attachments": {"Files and Notes": all_attachments},
	}
	
	timestamp = date.today().strftime("%Y%m%d")
	filename = f"CCM_Transfer_{requester.replace(' ','_')}_{timestamp}.pdf"
	
	st.session_state.form_data = form_data
	st.session_state.filename = filename
	st.session_state.attachments = uploaded_files
	
	# =========================================================
	# Create standardized filename and email subject
	# =========================================================
		
	# Clean up and shorten text fields
	safe_req = "".join([part[0].upper() + part[1:] for part in requester.split() if part])[:15]
	safe_strain = strain.replace("/", "").replace(" ", "")
	safe_facility = Facility.replace("/", "").replace(" ", "")
	date_str = transfer_date.strftime("%b%d")
	
	# Compose name and subject
	base_name = f"[TransferToCCM]_{quantity}{gender[0]}_{safe_strain}_{safe_facility}_{safe_req}_{date_str}"
	subject = base_name
	filename = f"{base_name}.pdf"

		
	
	create_pdf(form_data, uploaded_files, filename)
	st.success("✅ PDF preview generated")
	
	with open(filename, "rb") as f:
		st.download_button("⬇️ Download PDF", f, file_name=filename, mime="application/pdf")
		
# =========================================================
# EMAIL — HTML + Attachments
# =========================================================


def send_email(recipient, subject, html_body, file_path, cc=None):
		"""
		Send an HTML-formatted email with attachments (PDF + user uploads).
		Works with Gmail SMTP (SSL on port 465).
		"""
		msg = EmailMessage()
		msg["Subject"] = subject
		msg["From"] = SENDER_EMAIL
		msg["To"] = recipient
		if cc:
				msg["Cc"] = cc
			
		# Add HTML body
		msg.add_alternative(html_body, subtype="html")
	
		# Attach the main PDF
		with open(file_path, "rb") as f:
				msg.add_attachment(
						f.read(),
						maintype="application",
						subtype="pdf",
						filename=os.path.basename(file_path),
				)
			
		# Attach any uploaded files from sidebar
		if st.session_state.attachments:
				for f in st.session_state.attachments:
						data = f.read()
						ext = f.name.split(".")[-1].lower()
						subtype = {
								"pdf": "pdf",
								"docx": "vnd.openxmlformats-officedocument.wordprocessingml.document",
								"xlsx": "vnd.openxmlformats-officedocument.spreadsheetml.sheet",
						}.get(ext, "octet-stream")
						msg.add_attachment(
								data,
								maintype="application",
								subtype=subtype,
								filename=f.name,
						)
					
		with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
				smtp.login(SENDER_EMAIL, APP_PASSWORD)
				smtp.send_message(msg)
				print(f"✅ Email sent to {recipient}")
			
			
# =========================================================
# HELPER — Build Beautiful HTML Email Body
# =========================================================

def build_email_html(
		transfer_date,
		tumour,
		tumour_info,
		weight_loss,
		tumour_volume_limit,
		distress_signs,
		form_data,
		attachments=None   
):
		"""
		Build a complete HTML email summary of the mouse transfer,
		including general info, animal info, tumour, and humane endpoints.
		"""
	
		# Convert logo to base64 (inline image)
		logo_b64 = ""
		logo_path = Path(__file__).parent / "LOGO_dark.png"
		if logo_path.exists():
				with open(logo_path, "rb") as f:
						logo_b64 = base64.b64encode(f.read()).decode("utf-8")
					
		gen = form_data.get("General Info", {})
		animal = form_data.get("Animal Info", {})
		attach_list = [f.name for f in attachments] if attachments else []
	
		return f"""
<html>
<head>
<style>
	body {{
		font-family: 'Segoe UI', Helvetica, Arial, sans-serif;
		background-color: #f9fafc;
		color: #333;
		line-height: 1.5;
	}}
	.container {{
		max-width: 700px;
		margin: auto;
		background: white;
		border-radius: 8px;
		padding: 25px 30px;
		box-shadow: 0 2px 6px rgba(0,0,0,0.1);
	}}
	h2 {{
		color: #002145;
		border-bottom: 2px solid #0055a4;
		padding-bottom: 4px;
	}}
	h3 {{
		color: #002145;
		margin-top: 24px;
	}}
	p, li {{ font-size: 15px; }}
	ul {{ margin: 0; padding-left: 20px; }}
	.footer {{
		margin-top: 25px;
		font-size: 13px;
		color: #666;
	}}
</style>
</head>

<body>
<div class="container">
	<div style="text-align:center;">
		{"<img src='data:image/png;base64," + logo_b64 + "' width='120' style='margin-bottom:15px;'/>" if logo_b64 else ""}
		<h2>Animal Transfer Form — From {gen.get("Facility","-")} to CCM</h2>
		<p><strong>Date Submitted:</strong> {fmt_date(transfer_date)}</p>
	</div>

	<h3>📋 General Information</h3>
	<ul>
		<li><strong>Requester:</strong> {gen.get("Requester","-")}</li>
		<li><strong>Requester Email:</strong> {gen.get("Requester Email","-")}</li>
		<li><strong>Lab Group:</strong> {gen.get("Lab Group","-")}</li>
		<li><strong>ACC Protocol:</strong> {gen.get("ACC Protocol","-")}</li>
		<li><strong>Facility:</strong> {gen.get("Facility","-")}</li>
		<li><strong>Requested Transfer Date:</strong> {gen.get("Requested Transfer Date","-")}</li>
		<li><strong>Comments:</strong> {gen.get("Comments","-")}</li>
	</ul>

	<h3>🐁 Animal Information</h3>
	<ul>
		<li><strong>Strain:</strong> {animal.get("Strain","-")}</li>
		<li><strong>Number of Animals:</strong> {animal.get("Number of Animals","-")}</li>
		<li><strong>Sex:</strong> {animal.get("Sex","-")}</li>
		<li><strong>Age at Transfer:</strong> {animal.get("Age at Transfer","-")}</li>
		<li><strong>DOB Entries:</strong> {animal.get("DOB Entries","-")}</li>
		<li><strong>Cages:</strong> {animal.get("Cages","-")}</li>
		<li><strong>Tumour-bearing:</strong> {animal.get("Tumour-bearing","-")}</li>
	</ul>

	<h3>⚠️ Tumour Information</h3>
	<ul>
		<li><strong>Cell Line:</strong> {tumour_info.get("Cell Line","-")}</li>
		<li><strong>Tumour Location:</strong> {tumour_info.get("Tumour Location","-")}</li>
		<li><strong>Inoculation Date:</strong> {tumour_info.get("Inoculation Date","-")}</li>
		<li><strong>Tumour Duration:</strong> {tumour_info.get("Tumour Duration","-")}</li>
		<li><strong>Current Tumour Volume:</strong> {tumour_info.get("Current Tumour Volume","-")}</li>
		<li><strong>Monitoring Frequency:</strong> {tumour_info.get("Monitoring Frequency","-")}</li>
		<li><strong>Tumour-related Notes:</strong> {tumour_info.get("Notes","-")}</li>
	</ul>

	<h3>🩺 Humane Endpoints</h3>
	<ul>
		<li><strong>Weight Loss Limit (%):</strong> {weight_loss}</li>
		<li><strong>Tumour V Limit (mm³):</strong> {tumour_volume_limit}</li>
		<li><strong>Signs of Distress:</strong> {distress_signs}</li>
	</ul>

	<h3>📎 Attachments Summary</h3>
	<ul class="attachment-list">
		{''.join(f'<li>{f}</li>' for f in attach_list) if attach_list else '<li>No attachments uploaded.</li>'}
	</ul>
	
		
	<div class="footer">
		<p>
			This form was automatically generated by the
			<em>Animal Transfer Portal</em> — Preclinical Imaging Research Facility @ UBC.<br><br>
			We have received the submitted form and will process the transfer as soon as possible.<br>
			We will contact you directly in case of any questions or clarifications.<br><br>
			{"A copy has been sent to the requester." if st.session_state.get("copy") else ""}
		</p>
	</div>
	
</div>
</body>
</html>
"""

	
	
# -------------------------
# Submit + Email
# -------------------------
if st.session_state.form_data and not st.session_state.locked:
		if st.button("✅ Submit Request"):
			
				form_data = st.session_state.form_data
				filename = st.session_state.filename
				attachments = st.session_state.attachments
				create_pdf(form_data, attachments, filename)
			
				# =========================================================
				# FILE AND SUBJECT NAMING
				# =========================================================
			
				# Clean up and shorten fields for filename
				safe_req = "".join([part[0].upper() + part[1:] for part in requester.split() if part])[:15]
				safe_strain = strain.replace("/", "").replace(" ", "")
				safe_facility = Facility.replace("/", "").replace(" ", "")
				date_str = transfer_date.strftime("%b%d")
			
				# Create standardized PDF + email subject name
				base_name = f"[TransferToCCM]_{quantity}{gender[0]}_{safe_strain}_{safe_facility}_{safe_req}_{date_str}"
			
				# Use the same base name for both PDF and email subject
				subject = base_name
				filename = f"{base_name}.pdf"
			
				# Build HTML email
				email_html = build_email_html(
					transfer_date,
					tumour,
					tumour_info,
					weight_loss,
					tumour_volume_limit,
					distress_signs,
					st.session_state.form_data,  # all form fields
					uploaded_files               # list of attached files
				)
				try:
					# Always send to facility
					main_recipient = DEFAULT_EMAIL
					cc_list = [requester_email] if send_copy and requester_email else None
					
					send_email(
						recipient=main_recipient,
						subject=subject,
						html_body=email_html,
						file_path=filename,
						cc=cc_list,
					)
					
					# Optional auto-send receipt to requester
					if send_copy and requester_email:
						receipt_name = f"Receipt_{subject}.pdf"
						create_pdf(form_data, attachments, receipt_name)
						send_email(
							recipient=requester_email,
							subject=f"Receipt: Rodent Transfer Request ({subject})",
							html_body=email_html,
							file_path=receipt_name,
						)
						
					# ✅ Visual + text feedback
					st.session_state.locked = True
					st.success("✅ Transfer request successfully submitted!")
					if send_copy and requester_email:
						st.info("📩 Confirmation emails were sent to the requester and facility.")
					else:
						st.info("📩 Confirmation email was sent to the facility only.")
						
					# ⚠️ Extra warning if no monitoring sheets were attached
					if not any("monitor" in f.name.lower() for f in attachments):
						st.warning(
							"⚠️ Monitoring sheets were not attached. "
									"Please send them to the Facility Manager at "
									"{DEFAULT_EMAIL} **at least 24 hours before the transfer**, "
									"and no later than the time the animals arrive at CCM."						)
						
					#st.balloons()
					st.stop()
					
				except Exception as e:
					st.error(f"❌ An error occurred while sending emails - please contact {DEFAULT_EMAIL}: {e}")
					
			
	
# -------------------------
# Reset for new request
# -------------------------
if st.session_state.locked:
	st.divider()
	st.write("✅ This request is complete.")
	
	if st.button("🔄 Start New Submission"):
		st.session_state.clear()
		if hasattr(st, "rerun"):
			st.rerun()
		else:
			st.experimental_rerun()		