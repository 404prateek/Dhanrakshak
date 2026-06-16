import sqlite3
from datetime import datetime, timedelta

def seed():
    conn = sqlite3.connect('dhanrakshak.db')
    cursor = conn.cursor()
    
    # Clear existing data
    tables = ['cases', 'documents', 'investigation_notes', 'fraud_reports', 'audit_logs']
    for t in tables:
        cursor.execute(f"DELETE FROM {t}")
        # Reset auto-increment
        try:
            cursor.execute(f"DELETE FROM sqlite_sequence WHERE name='{t}'")
        except sqlite3.OperationalError:
            pass
        
    cases_data = [
        (1, 'CASE-1', 'Rajesh Kumar', 'Bandra West, Mumbai', 'FRAUD_CONFIRMED', 85.0),
        (2, 'CASE-2', 'Priya Sharma', 'Noida Sector 62', 'Open', 42.0),
        (3, 'CASE-3', 'Amit Verma', 'Indiranagar, Bengaluru', 'Investigation', 73.0),
        (4, 'CASE-4', 'Sneha Gupta', 'Pune Baner', 'APPROVED', 18.0),
        (5, 'CASE-5', 'Rohit Mehta', 'Ahmedabad Satellite', 'FRAUD_CONFIRMED', 91.0),
        (6, 'CASE-6', 'Neha Kapoor', 'Gurugram DLF Phase 5', 'Open', 37.0),
        (7, 'CASE-7', 'Arjun Singh', 'Hyderabad Gachibowli', 'Investigation', 65.0),
        (8, 'CASE-8', 'Kavya Nair', 'Kochi Marine Drive', 'APPROVED', 24.0),
        (9, 'CASE-9', 'Manish Jain', 'Jaipur Malviya Nagar', 'Investigation', 78.0),
        (10, 'CASE-10', 'Ananya Rao', 'Chennai OMR', 'Open', 55.0)
    ]
    
    # Notes pool
    notes_pool = [
        "Income mismatch detected.",
        "Address verification pending.",
        "Bank statement requires manual review.",
        "Property valuation differs from submitted records.",
        "Applicant unreachable on registered phone.",
        "Field agent dispatched for physical verification."
    ]
    
    # Docs pool
    docs_pool = [
        ("PAN Card.pdf", "application/pdf"),
        ("Aadhaar Card.pdf", "application/pdf"),
        ("Salary Slip.pdf", "application/pdf"),
        ("Bank Statement.pdf", "application/pdf"),
        ("Property Registry.pdf", "application/pdf")
    ]
    
    num_notes = 0
    num_docs = 0
    num_logs = 0
    
    base_date = datetime.now() - timedelta(days=30)
    
    for case in cases_data:
        case_id, ref, name, address, status, risk = case
        cursor.execute(
            "INSERT INTO cases (id, case_ref, applicant_name, property_address, status, risk_score, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (case_id, ref, name, address, status, risk, base_date, base_date + timedelta(days=10))
        )
        
        # Insert 3 notes per case
        for i in range(3):
            note = notes_pool[(case_id + i) % len(notes_pool)]
            cursor.execute(
                "INSERT INTO investigation_notes (case_id, user_id, note, created_at) VALUES (?, ?, ?, ?)",
                (case_id, 1, note, base_date + timedelta(days=i))
            )
            num_notes += 1
            
        # Insert 3 docs per case
        for i in range(3):
            dname, dtype = docs_pool[(case_id + i) % len(docs_pool)]
            cursor.execute(
                "INSERT INTO documents (case_id, file_name, file_type, file_path, uploaded_by, upload_date) VALUES (?, ?, ?, ?, ?, ?)",
                (case_id, dname, dtype, f'./storage/mock_{case_id}_{dname}', 1, base_date + timedelta(days=i))
            )
            num_docs += 1
            
        # Add timeline audit logs
        cursor.execute("INSERT INTO audit_logs (user_id, action, case_ref, result, timestamp) VALUES (?, ?, ?, ?, ?)", (1, 'Admin viewed case', ref, 'Success', base_date))
        cursor.execute("INSERT INTO audit_logs (user_id, action, case_ref, result, timestamp) VALUES (?, ?, ?, ?, ?)", (1, 'Officer uploaded document', ref, 'Success', base_date + timedelta(days=1)))
        cursor.execute("INSERT INTO audit_logs (user_id, action, case_ref, result, timestamp) VALUES (?, ?, ?, ?, ?)", (1, 'Investigation note added', ref, 'Success', base_date + timedelta(days=2)))
        num_logs += 3
        
        if status == 'APPROVED':
            cursor.execute("INSERT INTO audit_logs (user_id, action, case_ref, result, timestamp) VALUES (?, ?, ?, ?, ?)", (1, 'Case approved', ref, 'Success', base_date + timedelta(days=10)))
            num_logs += 1

    # Fraud reports
    reports = [
        (1, 85.0, "High Risk Identified", "Multiple indicators of fraud detected.", "Reject application."),
        (5, 91.0, "Critical Fraud", "Document forgery confirmed.", "Escalate to legal.")
    ]
    
    for r in reports:
        case_id, score, cat, find, rec = r
        cursor.execute(
            "INSERT INTO fraud_reports (case_id, risk_score, fraud_category, findings, recommendation, generated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (case_id, score, cat, find, rec, base_date + timedelta(days=5))
        )
        cursor.execute("INSERT INTO audit_logs (user_id, action, case_ref, result, timestamp) VALUES (?, ?, ?, ?, ?)", (1, 'Fraud report generated', f'CASE-{case_id}', 'Success', base_date + timedelta(days=5)))
        num_logs += 1
        
    conn.commit()
    conn.close()
    
    print(f"Cases: {len(cases_data)}")
    print(f"Reports: {len(reports)}")
    print(f"Notes: {num_notes}")
    print(f"Documents: {num_docs}")
    print(f"Audit Logs: {num_logs}")

if __name__ == "__main__":
    seed()
