"""Resume text: extract the words from a candidate's resume so candidates can be searched by them.

PDF (pypdf, already a Frappe dependency), Word .docx (read directly from the file, no extra
package) and plain text are supported. Anything else, or a file that cannot be read, simply
gives no text: a resume is never rejected because it could not be searched.
"""

import io
import re
import zipfile
from xml.etree import ElementTree

import frappe

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_TEXT_CHARS = 200_000
WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def extract_text(content: bytes | str, filename: str) -> str:
	"""Text of a resume file, or an empty string when the type is unsupported or unreadable."""
	if isinstance(content, str):  # File.get_content() gives text for text files, bytes for the rest
		content = content.encode("utf-8")
	if not content or len(content) > MAX_FILE_BYTES:
		return ""
	extension = (filename or "").rsplit(".", 1)[-1].lower()
	readers = {"pdf": _pdf_text, "docx": _docx_text, "txt": _plain_text}
	reader = readers.get(extension)
	if not reader:
		return ""
	try:
		text = reader(content)
	except Exception:
		frappe.log_error(title=f"Resume text could not be read ({filename})")
		return ""
	return re.sub(r"\s+", " ", text).strip()[:MAX_TEXT_CHARS]


def _pdf_text(content: bytes) -> str:
	from pypdf import PdfReader

	reader = PdfReader(io.BytesIO(content))
	return " ".join((page.extract_text() or "") for page in reader.pages)


def _docx_text(content: bytes) -> str:
	with zipfile.ZipFile(io.BytesIO(content)) as archive:
		root = ElementTree.fromstring(archive.read("word/document.xml"))
	paragraphs = []
	for paragraph in root.iter(f"{WORD_NS}p"):
		paragraphs.append("".join(node.text or "" for node in paragraph.iter(f"{WORD_NS}t")))
	return " ".join(paragraphs)


def _plain_text(content: bytes) -> str:
	return content.decode("utf-8", errors="ignore")


def get_resume_file(candidate_resume: str | None):
	"""The File record behind a Candidate's resume field, or None."""
	if not candidate_resume:
		return None
	name = frappe.db.get_value("File", {"file_url": candidate_resume}, "name")
	return frappe.get_doc("File", name) if name else None


def refresh_resume_text(candidate: str) -> str:
	"""Read the candidate's resume and store its text for search. Returns the text stored."""
	resume = frappe.db.get_value("Candidate", candidate, "resume")
	text = ""
	file = get_resume_file(resume)
	if file:
		try:
			text = extract_text(file.get_content(), file.file_name)
		except Exception:
			frappe.log_error(title=f"Resume file could not be opened ({candidate})")
	frappe.db.set_value("Candidate", candidate, "resume_text", text, update_modified=False)
	return text


def queue_resume_text(doc, method=None):
	"""Candidate on_update hook: when the resume changes, read it in the background."""
	before = doc.get_doc_before_save()
	if doc.resume == (before.resume if before else None):
		return
	frappe.enqueue(
		"hrms.ats.resume.refresh_resume_text",
		candidate=doc.name,
		queue="short",
		enqueue_after_commit=True,
	)


def extract_missing_resume_text() -> int:
	"""Read the resume of every candidate that has one but no text yet. For existing data."""
	count = 0
	for name in frappe.get_all(
		"Candidate", filters={"resume": ["is", "set"], "resume_text": ["in", ["", None]]}, pluck="name"
	):
		if refresh_resume_text(name):
			count += 1
	return count


# ---- search


def search_words(text: str) -> list[str]:
	"""The words typed, at least two letters or digits each, lower-cased. Anything else
	(including the wildcard characters % and _) only separates words."""
	return [w.lower() for w in re.split(r"[\W_]+", text or "") if len(w) >= 2]


@frappe.whitelist()
def search_candidates(text: str) -> list[str]:
	"""Names of candidates whose resume contains every word typed (partial words match too).

	Needs read access to Candidate, and permission rules still decide what the user sees."""
	frappe.has_permission("Candidate", "read", throw=True)
	words = search_words(text)
	if not words:
		return []

	filters = [["Candidate", "resume_text", "like", f"%{word}%"] for word in words]
	return frappe.get_list("Candidate", filters=filters, pluck="name", limit_page_length=500)
