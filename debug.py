# debug.py
import os
from app.services.ingest import ingest_text
from app.services.retrieval import retrieve_chunks
from app.knowledge.fetcher import fetch_from_file

# 1. Test PDF Extraction directly
pdf_path = r"C:\Users\jjama\Downloads\Sample-Pdf-invoices-main\Sample-Pdf-invoices-main\1000+ PDF_Invoice_Folder\1000+ PDF_Invoice_Folder\invoice_Victoria Wilson_30489.pdf"  # Make sure this file is in the ReAct Agent folder!

if not os.path.exists(pdf_path):
    print(f"❌ ERROR: Could not find {pdf_path} in this folder.")
    exit()

print("--- 1. EXTRACTING TEXT FROM PDF ---")
raw_text = fetch_from_file(pdf_path)
print(f"✅ Extracted {len(raw_text)} characters.")
print(f"Preview: {raw_text[:300]}\n")

# 2. Test Ingestion (Chunking + Embedding)
print("--- 2. CHUNKING & EMBEDDING ---")
result = ingest_text(raw_text, 20000, label="Victoria Invoice")
print(f"✅ Created {len(result['chunks'])} chunks.")

# 3. Test Retrieval directly
print("\n--- 3. TESTING FAISS SEARCH ---")
query = "What product did Victoria Wilson buy?"
hits = retrieve_chunks({"chunks": result["chunks"], "index": result["index"]}, query)

if not hits:
    print("❌ ERROR: FAISS search returned 0 chunks.")
else:
    print(f"✅ FAISS found {len(hits)} chunks.")
    for h in hits:
        print(f"Score: {h.get('score'):.3f} | Text: {h.get('chunk')[:150]}...")