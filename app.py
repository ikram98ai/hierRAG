# Instructions:
# step 1: build simple gradio app that let user upload pdf/txt files and select one of the three the vector db indexes (hospital, bank, fluid_simulation).
# step 2: the files should convert to chunks and then embedding and finally store in the selected index with metadata of {
#   "doc_id": "uuid",
#   "chunk_id": "uuid",
#   "source_name": "filename.pdf",
#   "lang": "ja|en",
#   "domain": "...",
#   "section": "...",
#   "topic": "...",
#   "doc_type": "policy|manual|faq"
# }

# step 3: now to chat with data user first select the one of three index, language, and optionally for heirarchical select domain, section, topic and doc_type
# step 4 The UI should present side‑by‑side results (answers, supporting snippets, latency).
import gradio as gr
import time
import uuid
import os
import random

# --- Mock Backend Functions ---

def get_mock_metadata(filename, lang, domain, section, topic, doc_type):
    """Generates metadata for a file based on user input."""
    
    return {
        "doc_id": str(uuid.uuid4()), # doc_id should be per document, not chunk
        "chunk_id": str(uuid.uuid4()), # this is fine per chunk
        "source_name": filename,
        "lang": lang,
        "domain": domain,
        "section": section,
        "topic": topic,
        "doc_type": doc_type
    }

def process_files(files, index_name, lang, domain, section, topic, doc_type):
    """
    Mock function for Step 2: Ingestion.
    Simulates chunking, embedding, and storing in a vector DB.
    """
    if not files:
        return "Please upload at least one file."
    if not index_name:
        return "Please select an index."
    # Add checks for new inputs
    if not all([lang, domain, section, topic, doc_type]):
        return "Please select a value for all metadata fields (lang, domain, etc.)."

    print(f"--- Starting Ingestion for Index: {index_name} ---")
    print(f"With Metadata: lang={lang}, domain={domain}, section={section}, topic={topic}, doc_type={doc_type}")
    
    processing_results = []
    
    for file_obj in files:
        filename = os.path.basename(file_obj.name)
        print(f"Processing file: {filename}")
        
        # Simulate reading and chunking
        num_chunks = random.randint(5, 20)
        print(f"Simulating... found {num_chunks} chunks.")
        
        doc_id = str(uuid.uuid4()) # Create one doc_id for the entire file
        
        # Simulate embedding and storing with metadata
        for i in range(num_chunks):
            # Pass user-selected metadata to the function
            metadata = get_mock_metadata(filename, lang, domain, section, topic, doc_type)
            metadata["doc_id"] = doc_id # Use same doc_id for all chunks of this file
            metadata["chunk_id"] = str(uuid.uuid4()) # Unique ID for each chunk
            
            # 1. chunk_text = ... (get text for chunk i)
            # 2. embedding = model.embed(chunk_text)
            # 3. vector_db[index_name].add(embedding, metadata)
            
            if i == 0: # Only show metadata for the first chunk to keep output clean
                processing_results.append({
                    "file": filename,
                    "status": "processing...",
                    "simulated_chunks": num_chunks,
                    "sample_metadata": metadata
                })

        print(f"Successfully processed {filename}.")
    
    print("--- Ingestion Complete ---")
    return processing_results

def _simulate_rag_query(question, index_name, active_filters, query_type_label):
    """
    Helper mock function to simulate a single RAG query.
    """
    start_time = time.time()
    
    print(f"--- Querying Index: {index_name} ({query_type_label}) ---")
    print(f"Question: {question}")
    print(f"Active Filters: {active_filters}")

    # 1. query_embedding = model.embed(question)
    # 2. search_results = vector_db[index_name].search(
    #        query_embedding, 
    #        k=3, 
    #        filters=active_filters
    #    )
    # 3. context_snippets = [res.snippet for res in search_results]
    # 4. answer = llm.generate(question, context_snippets)
    
    # Simulate delay (making hierarchical slightly faster to show a difference)
    if query_type_label == "Hierarchical":
        time.sleep(random.uniform(0.5, 1.5))
    else:
        time.sleep(random.uniform(1.0, 2.5))

    # Mock results
    mock_answer = f"This is a mock answer for '{question}' from the **{query_type_label}** pipeline on the **'{index_name}'** index. "
    if query_type_label == "Hierarchical":
        mock_answer += "This result was found using all your filters, leading to a more relevant answer."
    else:
        mock_answer += "This result used minimal filters and may be less specific."
    
    mock_snippets = [
        f"Snippet 1 ({query_type_label}, from source: file_{random.randint(1,3)}.pdf): ...Lorem ipsum dolor sit amet, consectetur adipiscing elit. Nullam in dui mauris...",
        f"Snippet 2 ({query_type_label}, from source: file_{random.randint(4,6)}.pdf): ...Vivamus luctus eros aliquet convallis ultricies. Mauris augue massa, ultricies non ligula...",
        f"Snippet 3 ({query_type_label}, from source: file_{random.randint(7,9)}.pdf): ...Pellentesque vel dui sed orci faucibus iaculis. Interdum et malesuada fames ac ante ipsum..."
    ]
    
    snippets_md = "\n\n---\n\n".join(mock_snippets)
    
    end_time = time.time()
    latency = f"{end_time - start_time:.2f}s"
    
    print(f"--- {query_type_label} Query Complete ({latency}) ---")
    
    return mock_answer, snippets_md, latency

def run_rag_comparison(question, index_name, lang, domain, section, topic, doc_type):
    """
    Mock function for Step 4: Runs two RAG simulations side-by-side.
    """
    if not index_name:
        error_msg = "Please select an index to query."
        return error_msg, "", "0.00s", error_msg, "", "0.00s"
    if not question:
        error_msg = "Please enter a question."
        return error_msg, "", "0.00s", error_msg, "", "0.00s"

    # --- 1. Base RAG Simulation ---
    # Only uses the language filter
    base_filters = {"language": lang}
    base_answer, base_snippets, base_latency = _simulate_rag_query(
        question, index_name, base_filters, "Base"
    )

    # --- 2. Hierarchical RAG Simulation ---
    # Uses all filters (except "Any")
    all_filters = {
        "language": lang,
        "domain": domain,
        "section": section,
        "topic": topic,
        "doc_type": doc_type
    }
    hier_filters = {k: v for k, v in all_filters.items() if v != "Any"}
    hier_answer, hier_snippets, hier_latency = _simulate_rag_query(
        question, index_name, hier_filters, "Hierarchical"
    )

    return base_answer, base_snippets, base_latency, hier_answer, hier_snippets, hier_latency

# --- Dummy data for filters ---
INDEX_CHOICES = ["hospital", "bank", "fluid_simulation"]
LANG_CHOICES = ["en", "ja"]
DOMAIN_CHOICES = ["Any", "Healthcare", "Finance", "Engineering", "Policy", "HR"]
SECTION_CHOICES = ["Any", "Onboarding", "Patient Care", "Risk Assessment", "Simulation_Parameters"]
TOPIC_CHOICES = ["Any", "Diagnostics", "Loans", "CFD_Models", "Compliance"]
DOC_TYPE_CHOICES = ["Any", "policy", "manual", "faq"]

# --- New: Create choice lists for ingestion (without "Any") ---
INGEST_DOMAIN_CHOICES = [c for c in DOMAIN_CHOICES if c != "Any"]
INGEST_SECTION_CHOICES = [c for c in SECTION_CHOICES if c != "Any"]
INGEST_TOPIC_CHOICES = [c for c in TOPIC_CHOICES if c != "Any"]
INGEST_DOC_TYPE_CHOICES = [c for c in DOC_TYPE_CHOICES if c != "Any"]


# --- Build the Gradio UI ---

with gr.Blocks(theme=gr.themes.Soft()) as demo:
    gr.Markdown("# Document Ingestion and RAG Chat UI")

    with gr.Tab("Document Ingestion"):
        gr.Markdown("Upload PDF/TXT files, select metadata, and choose an index to store them in.")
        with gr.Row():
            with gr.Column(scale=1):
                file_uploader = gr.File(
                    label="Upload Files",
                    file_count="multiple",
                    file_types=[".pdf", ".txt"]
                )
                index_select_ingest = gr.Dropdown(
                    label="Select Index",
                    choices=INDEX_CHOICES
                )
                
                gr.Markdown("#### Set Document Metadata")
                lang_select_ingest = gr.Dropdown(
                    label="Language", 
                    choices=LANG_CHOICES, 
                    value=LANG_CHOICES[0]
                )
                domain_select_ingest = gr.Dropdown(
                    label="Domain", 
                    choices=INGEST_DOMAIN_CHOICES, 
                    value=INGEST_DOMAIN_CHOICES[0]
                )
                section_select_ingest = gr.Dropdown(
                    label="Section", 
                    choices=INGEST_SECTION_CHOICES, 
                    value=INGEST_SECTION_CHOICES[0]
                )
                topic_select_ingest = gr.Dropdown(
                    label="Topic", 
                    choices=INGEST_TOPIC_CHOICES, 
                    value=INGEST_TOPIC_CHOICES[0]
                )
                doc_type_select_ingest = gr.Dropdown(
                    label="Doc Type", 
                    choices=INGEST_DOC_TYPE_CHOICES, 
                    value=INGEST_DOC_TYPE_CHOICES[0]
                )
                
                ingest_button = gr.Button("Process and Ingest Files", variant="primary")
            
            with gr.Column(scale=2):
                ingest_output = gr.JSON(label="Ingestion Status and Sample Metadata")
        
        ingest_button.click(
            fn=process_files,
            inputs=[
                file_uploader, 
                index_select_ingest,
                lang_select_ingest,
                domain_select_ingest,
                section_select_ingest,
                topic_select_ingest,
                doc_type_select_ingest
            ],
            outputs=[ingest_output]
        )

    with gr.Tab("Chat with Data"):
        gr.Markdown("Select an index and filters to chat with your data. Results will appear side-by-side.")
        
        with gr.Row():
            with gr.Column(scale=1, min_width=300):
                gr.Markdown("### 1. Select Index & Filters")
                index_select_chat = gr.Dropdown(label="Select Index", choices=INDEX_CHOICES)
                lang_select = gr.Dropdown(label="Language", choices=LANG_CHOICES, value="en")
                
                gr.Markdown("#### Optional Filters")
                domain_select = gr.Dropdown(label="Domain", choices=DOMAIN_CHOICES, value="Any")
                section_select = gr.Dropdown(label="Section", choices=SECTION_CHOICES, value="Any")
                topic_select = gr.Dropdown(label="Topic", choices=TOPIC_CHOICES, value="Any")
                doc_type_select = gr.Dropdown(label="Doc Type", choices=DOC_TYPE_CHOICES, value="Any")
                
                gr.Markdown("### 2. Ask a Question")
                question_box = gr.Textbox(label="Question", placeholder="e.g., What is the policy on patient data?")
                chat_button = gr.Button("Get Answer", variant="primary")
            
            with gr.Column(scale=3):
                gr.Markdown("### 3. Results (Side-by-Side)")
                with gr.Row():
                    with gr.Column():
                        gr.Markdown("#### Base RAG Results")
                        base_answer_output = gr.Markdown(label="Answer")
                        base_snippets_output = gr.Markdown(label="Supporting Snippets")
                        base_latency_output = gr.Textbox(label="Latency")
                    with gr.Column():
                        gr.Markdown("#### Hierarchical RAG Results")
                        hier_answer_output = gr.Markdown(label="Answer")
                        hier_snippets_output = gr.Markdown(label="Supporting Snippets")
                        hier_latency_output = gr.Textbox(label="Latency")

        chat_button.click(
            fn=run_rag_comparison,
            inputs=[
                question_box, 
                index_select_chat, 
                lang_select, 
                domain_select, 
                section_select, 
                topic_select, 
                doc_type_select
            ],
            outputs=[
                base_answer_output, 
                base_snippets_output, 
                base_latency_output,
                hier_answer_output,
                hier_snippets_output,
                hier_latency_output
            ]
        )

if __name__ == "__main__":
    demo.launch()
