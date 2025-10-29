import gradio as gr
import time
from core.rag import ingest, generate, retrieval, retrieval_filter, FilterData


def process_files(files, index_name, lang, domain, section, topic, doc_type):
    """
    Loading, chunking, embedding, and storing in a vector DB.
    """
    print("files uploaded", files)
    if not files:
        return "Please upload at least one file."
    if not index_name:
        return "Please select an index."
    # Add checks for new inputs

    print(f"--- Starting Ingestion for Index: {index_name} ---")
    print(
        f"With Metadata: lang={lang}, domain={domain}, section={section}, topic={topic}, doc_type={doc_type}"
    )

    filter_data = FilterData(
        language=lang, domain=domain, section=section, topic=topic, doc_type=doc_type
    )
    result = ingest(files, index_name, filter_data)
    return {"status": "success", "message": result}

def _simulate_rag_query(
    question, index_name, active_filters: FilterData, query_type_label
):
    """
    Helper function to simulate a single RAG query.
    """
    start_time = time.time()

    print(f"--- Querying Index: {index_name} ({query_type_label}) ---")
    print(f"Question: {question}")
    print(f"Active Filters: {active_filters.model_dump()}")

    ret_start_time = time.time()
    if query_type_label == "Hierarchical":
        docs = retrieval_filter(question, index_name, active_filters)
    else:
        docs = retrieval(question, index_name, active_filters.language)
    ret_end_time = time.time()
    ret_latency = f"{ret_end_time - ret_start_time:.2f}s"
    answer = generate(question, docs)
    retrieval_results = [doc.page_content + f"\n### source: {doc.metadata.get("source_name","None")}" for doc in docs]

    snippets_md = "\n\n---\n\n".join(retrieval_results)

    end_time = time.time()
    latency = f"{end_time - start_time:.2f}s"
    answer = f"### Total Latency: {latency}\n### Retrieval Latency: {ret_latency}\n" + answer 
    snippets_md = f"\n\n## Retrieval results:\n"  + snippets_md 
    print(f"--- {query_type_label} Query Complete ({latency}) ---")

    return answer, snippets_md


def run_rag_comparison(question, index_name, lang, domain, section, topic, doc_type):
    """
    Function to Runs two RAG simulations side-by-side.
    This version is a generator: it yields a loading state first so the UI shows
    a loading animation/text immediately, then yields final results.
    """
    # Early validation -> yield immediate error states so the UI updates right away
    if not index_name:
        error_msg = "Please select an index to query."
        yield error_msg, "", error_msg, ""
        return
    if not question:
        error_msg = "Please enter a question."
        yield error_msg, "", error_msg, ""
        return

    # Yield initial loading placeholders so the UI shows "loading" while work runs
    loading_answer = "Loading… generating answer (this may take a few seconds)…"
    loading_snips = "Loading… retrieving supporting snippets…"
    yield loading_answer, loading_snips, loading_answer, loading_snips

    base_filter = FilterData(language=lang)
    base_answer, base_snippets = _simulate_rag_query(
        question, index_name, base_filter, "Base"
    )

    hier_filters = FilterData(
        language=lang, domain=domain, section=section, topic=topic, doc_type=doc_type
    )
    hier_answer, hier_snippets = _simulate_rag_query(
        question, index_name, hier_filters, "Hierarchical"
    )

    # Final yield with actual results
    yield base_answer, base_snippets, hier_answer, hier_snippets


# --- Dummy data for filters ---
INDEX_CHOICES = ["hospital", "bank", "fluid_simulation"]
LANG_CHOICES = ["en", "ja"]
DOMAIN_CHOICES = ["Any", "Healthcare", "Finance", "Engineering", "Policy", "HR"]
SECTION_CHOICES = [
    "Any",
    "Onboarding",
    "Patient Care",
    "Risk Assessment",
    "Simulation_Parameters",
]
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
        gr.Markdown(
            "Upload PDF/TXT files, select metadata, and choose an index to store them in."
        )
        with gr.Row():
            with gr.Column(scale=2):
                file_uploader = gr.File(
                    label="Upload Files",
                    file_count="multiple",
                    file_types=[".pdf", ".txt"],
                )
                index_select_ingest = gr.Dropdown(
                    label="Select Index", choices=INDEX_CHOICES
                )

                gr.Markdown("#### Set Document Metadata")
                lang_select_ingest = gr.Dropdown(
                    label="Language", choices=LANG_CHOICES, value=LANG_CHOICES[0]
                )
                domain_select_ingest = gr.Dropdown(
                    label="Domain",
                    choices=INGEST_DOMAIN_CHOICES,
                    value=INGEST_DOMAIN_CHOICES[0],
                )
                section_select_ingest = gr.Dropdown(
                    label="Section",
                    choices=INGEST_SECTION_CHOICES,
                    value=INGEST_SECTION_CHOICES[0],
                )
                topic_select_ingest = gr.Dropdown(
                    label="Topic",
                    choices=INGEST_TOPIC_CHOICES,
                    value=INGEST_TOPIC_CHOICES[0],
                )
                doc_type_select_ingest = gr.Dropdown(
                    label="Doc Type",
                    choices=INGEST_DOC_TYPE_CHOICES,
                    value=INGEST_DOC_TYPE_CHOICES[0],
                )

                ingest_button = gr.Button("Process and Ingest Files", variant="primary")

            with gr.Column(scale=1):
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
                doc_type_select_ingest,
            ],
            outputs=[ingest_output],
        )

    with gr.Tab("Chat with Data"):
        gr.Markdown(
            "Select an index and filters to chat with your data. Results will appear side-by-side."
        )

        with gr.Row():
            with gr.Column(scale=1, min_width=300):
                gr.Markdown("### 1. Select Index & Filters")
                index_select_chat = gr.Dropdown(
                    label="Select Index", choices=INDEX_CHOICES
                )
                lang_select = gr.Dropdown(
                    label="Language", choices=LANG_CHOICES, value="en"
                )

                gr.Markdown("#### Optional Filters")
                domain_select = gr.Dropdown(
                    label="Domain", choices=DOMAIN_CHOICES, value=None
                )
                section_select = gr.Dropdown(
                    label="Section", choices=SECTION_CHOICES, value=None
                )
                topic_select = gr.Dropdown(
                    label="Topic", choices=TOPIC_CHOICES, value=None
                )
                doc_type_select = gr.Dropdown(
                    label="Doc Type", choices=DOC_TYPE_CHOICES, value=None
                )


            with gr.Column(scale=3):
                gr.Markdown("### 2. Ask a Question")
                question_box = gr.Textbox(
                    label="Question",
                    placeholder="e.g., What is the policy on patient data?",
                )
                chat_button = gr.Button("Get Answer", variant="primary")

                gr.Markdown("### 3. Results (Side-by-Side)")
                with gr.Row():
                    with gr.Column():
                        gr.Markdown("#### Base RAG Results")
                        base_answer_output = gr.Markdown(container= True)
                        base_snippets_output = gr.Markdown(container= True)
                    with gr.Column():
                        gr.Markdown("#### Hierarchical RAG Results")
                        hier_answer_output = gr.Markdown(container= True)
                        hier_snippets_output = gr.Markdown(container= True)
                  

        chat_button.click(
            fn=run_rag_comparison,
            inputs=[
                question_box,
                index_select_chat,
                lang_select,
                domain_select,
                section_select,
                topic_select,
                doc_type_select,
            ],
            outputs=[
                base_answer_output,
                base_snippets_output,
                hier_answer_output,
                hier_snippets_output,
            ],
        )

if __name__ == "__main__":
    demo.launch()
