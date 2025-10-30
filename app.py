import gradio as gr
import time
from core.rag import ingest, generate, retrieval, FilterData
import yaml


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

def add_metric(doc):
    return (f"\n### source: {doc.metadata.get('source_name','None')}"
            f"\n### similarity_score: {doc.metadata.get('similarity_score','None'):.4f}"
        )

def _rag_query(
    question, index_name, active_filters: FilterData, query_type_label
):
    """
    Helper function for a single RAG query.
    """
    start_time = time.time()

    print(f"--- Querying Index: {index_name} ({query_type_label}) ---")
    print(f"Question: {question}")
    print(f"Active Filters: {active_filters.model_dump()}")

    ret_start_time = time.time()
    
    docs = retrieval(question, index_name, active_filters)
    retrieval_results = [doc.page_content + add_metric(doc) for doc in docs]
    snippets_md = "\n\n---\n\n".join(retrieval_results)

    ret_end_time = time.time()
    ret_latency = f"{ret_end_time - ret_start_time:.2f}s"

    answer = generate(question, docs)
    

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
    base_answer, base_snippets = _rag_query(
        question, index_name, base_filter, "Base"
    )

    if all([domain==None, section==None, topic==None, doc_type==None]):
        hier_answer = hier_snippets = "Please select at least one filter for hierarchical RAG"
        
    else:
        hier_filters = FilterData(
            language=lang, domain=domain, section=section, topic=topic, doc_type=doc_type
        )
        hier_answer, hier_snippets = _rag_query(
            question, index_name, hier_filters, "Hierarchical"
        )

    # Final yield with actual results
    yield base_answer, base_snippets, hier_answer, hier_snippets


def load_yaml_config(yaml_file):
    """
    Parses the uploaded YAML file and returns the config dictionary.
    This dictionary is stored in a hidden gr.State() component.
    """
    if yaml_file is None:
        gr.Warning("No YAML file provided.")
        return None
    try:
        with open(yaml_file.name, 'r') as f:
            config = yaml.safe_load(f)
        
        if not isinstance(config, dict):
            raise ValueError("YAML content must be a top-level dictionary.")
        
        gr.Info("Configuration loaded successfully!")
        return config  # This will be stored in config_state

    except Exception as e:
        print(f"Error processing YAML: {e}")
        gr.Warning(f"Failed to load YAML config: {e}")
        return None

def update_filters_for_index_ingest(index, config):
    """
    Updates the Ingestion filter dropdowns based on the selected index and loaded config.
    """
    if config is None or index is None:
        empty_update = gr.update(choices=[], value=None)
        return empty_update, empty_update, empty_update

    index_data = config.get(index, {})
    
    domains = sorted(index_data.get('domains', []))
    sections = sorted(index_data.get('sections', []))
    topics = sorted(index_data.get('topics', []))
    
    return (
        gr.update(choices=domains, value=domains[0] if domains else None),
        gr.update(choices=sections, value=sections[0] if sections else None),
        gr.update(choices=topics, value=topics[0] if topics else None)
    )

def update_filters_for_index_chat(index, config):
    """
    Updates the Chat filter dropdowns based on the selected index and loaded config.
    """
    if config is None or index is None:
        empty_update = gr.update(choices=[None], value=None)
        return empty_update, empty_update, empty_update

    index_data = config.get(index, {})

    domains = [None] + sorted(index_data.get('domains', []))
    sections = [None] + sorted(index_data.get('sections', []))
    topics = [None] + sorted(index_data.get('topics', []))

    return (
        gr.update(choices=domains, value=None),
        gr.update(choices=sections, value=None),
        gr.update(choices=topics, value=None)
    )


# --- Static choices (not from YAML) ---
LANG_CHOICES = ["en", "ja"]
DOC_TYPE_CHOICES = [None, "policy", "manual", "faq"]
INGEST_DOC_TYPE_CHOICES = [c for c in DOC_TYPE_CHOICES if c is not None]
INDEX_CHOICES = ["hospital", "bank", "fluid_simulation"]


# --- Build the Gradio UI ---

with gr.Blocks(theme=gr.themes.Soft()) as demo:
    gr.Markdown("# Document Ingestion and RAG Chat UI")
    
    # Hidden state to store the parsed YAML config
    config_state = gr.State()

    with gr.Column(variant="panel"):
        gr.Markdown(
            "⬆️ **START HERE:** Upload your `config.yaml` file to enable the Domain, Section, and Topic filters below.", 
            # scale=2, 
            label="Instructions"
        )
        yaml_uploader = gr.File(
            label="Upload Configuration YAML",
            file_types=[".yaml", ".yml"],
            scale=2
        )


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
                    label="Select Index", 
                    choices=INDEX_CHOICES,
                    value=INDEX_CHOICES[0]
                )

                gr.Markdown("### Set Document Metadata")
                lang_select_ingest = gr.Dropdown(
                    label="Language", choices=LANG_CHOICES, value=LANG_CHOICES[0]
                )
                doc_type_select_ingest = gr.Dropdown(
                    label="Doc Type",
                    choices=INGEST_DOC_TYPE_CHOICES,
                    value=INGEST_DOC_TYPE_CHOICES[0],
                )
                gr.Markdown("##### Optional Filters (from YAML)")

                domain_select_ingest = gr.Dropdown(
                    label="Domain",
                    choices=[],  # Populated dynamically
                    info="Upload YAML and select an index to populate."
                )
                section_select_ingest = gr.Dropdown(
                    label="Section",
                    choices=[],  # Populated dynamically
                    info="Upload YAML and select an index to populate."
                )
                topic_select_ingest = gr.Dropdown(
                    label="Topic",
                    choices=[],  # Populated dynamically
                    info="Upload YAML and select an index to populate."
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
                    label="Select Index", 
                    choices=INDEX_CHOICES,
                    value=INDEX_CHOICES[0]
                )
                lang_select = gr.Dropdown(
                    label="Language", choices=LANG_CHOICES, value="en"
                )
                doc_type_select = gr.Dropdown(
                    label="Doc Type", choices=DOC_TYPE_CHOICES, value=None
                )

                gr.Markdown("#### Optional Filters (from YAML)")
                domain_select = gr.Dropdown(
                    label="Domain", 
                    choices=[None], 
                    value=None,  # Populated dynamically
                    info="Upload YAML and select an index to populate."
                )
                section_select = gr.Dropdown(
                    label="Section", 
                    choices=[None], 
                    value=None,  # Populated dynamically
                    info="Upload YAML and select an index to populate."
                )
                topic_select = gr.Dropdown(
                    label="Topic", 
                    choices=[None], 
                    value=None,  # Populated dynamically
                    info="Upload YAML and select an index to populate."
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

    # --- Event Handlers ---

    # 1. When YAML is uploaded, store its content in config_state
    #    .then() chain:
    #    a) Update the Ingest dropdowns based on the default selected index
    #    b) Update the Chat dropdowns based on the default selected index
    yaml_uploader.upload(
        fn=load_yaml_config,
        inputs=[yaml_uploader],
        outputs=[config_state]
    ).then(
        fn=update_filters_for_index_ingest,
        inputs=[index_select_ingest, config_state],
        outputs=[domain_select_ingest, section_select_ingest, topic_select_ingest]
    ).then(
        fn=update_filters_for_index_chat,
        inputs=[index_select_chat, config_state],
        outputs=[domain_select, section_select, topic_select]
    )

    # 2. When the Ingest index changes, update its filters
    index_select_ingest.change(
        fn=update_filters_for_index_ingest,
        inputs=[index_select_ingest, config_state],
        outputs=[domain_select_ingest, section_select_ingest, topic_select_ingest]
    )

    # 3. When the Chat index changes, update its filters
    index_select_chat.change(
        fn=update_filters_for_index_chat,
        inputs=[index_select_chat, config_state],
        outputs=[domain_select, section_select, topic_select]
    )


if __name__ == "__main__":
    demo.launch()