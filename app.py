import gradio as gr
import time
from pathlib import Path
from core.ingest import ingest
from core.retrieval import generate, retrieval
from core.index import MetaData
import yaml

# Import evaluation functions
from core.eval import (
    run_full_evaluation, 
    save_results, 
    generate_summary_report,
    setup_test_data,
    EVAL_QUERIES
)


def process_files(files, index_name, lang, domain, section, topic, doc_type):
    """
    Loading, chunking, embedding, and storing in a vector DB.
    """
    print("files uploaded", files)
    if not files:
        return "Please upload at least one file."
    if not index_name:
        return "Please select an index."

    print(f"--- Starting Ingestion for Index: {index_name} ---")
    print(
        f"With Metadata: lang={lang}, domain={domain}, section={section}, topic={topic}, doc_type={doc_type}"
    )

    filter_data = MetaData(
        language=lang, domain=domain, section=section, topic=topic, doc_type=doc_type
    )
    result = ingest(index_name, filter_data, files)
    return {"status": "success", "message": result}

def add_metric(doc):
    return (f"\n### source: {doc.metadata.get('source_name','None')}"
            f"\n### similarity_score: {doc.metadata.get('similarity_score','None'):.4f}"
        )

def _rag_query(
    question, index_name, active_filters: MetaData, query_type_label
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
    snippets_md = "\n\n## Retrieval results:\n"  + snippets_md 
    print(f"--- {query_type_label} Query Complete ({latency}) ---")

    return answer, snippets_md


def run_rag_comparison(question, index_name, lang, domain, section, topic, doc_type):
    """
    Function to Runs two RAG simulations side-by-side.
    This version is a generator: it yields a loading state first so the UI shows
    a loading animation/text immediately, then yields final results.
    """
    if not index_name:
        error_msg = "Please select an index to query."
        yield error_msg, "", error_msg, ""
        return
    if not question:
        error_msg = "Please enter a question."
        yield error_msg, "", error_msg, ""
        return

    loading_answer = "Loading… generating answer (this may take a few seconds)…"
    loading_snips = "Loading… retrieving supporting snippets…"
    yield loading_answer, loading_snips, loading_answer, loading_snips

    base_filter = MetaData(language=lang)
    base_answer, base_snippets = _rag_query(
        question, index_name, base_filter, "Base"
    )

    if all([domain==None, section==None, topic==None, doc_type==None]):
        hier_answer = hier_snippets = "Please select at least one filter for hierarchical RAG"
        
    else:
        hier_filters = MetaData(
            language=lang, domain=domain, section=section, topic=topic, doc_type=doc_type
        )
        hier_answer, hier_snippets = _rag_query(
            question, index_name, hier_filters, "Hierarchical"
        )

    yield base_answer, base_snippets, hier_answer, hier_snippets


def load_yaml_config(yaml_file):
    """
    Parses the uploaded YAML file and returns the config dictionary.
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
        return config

    except Exception as e:
        print(f"Error processing YAML: {e}")
        gr.Warning(f"Failed to load YAML config: {e}")
        return None

def update_metadata_for_index_ingest(index, config):
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


def setup_synthetic_data(collections):
    """Setup synthetic test data for evaluation"""
    if not collections:
        return "⚠️ Please select at least one collection"
    
    try:
        docs_length = setup_test_data(collections)
        return f"✅ Successfully ingested {docs_length} synthetic test data for each: {', '.join(collections)}"
    except Exception as e:
        return f"❌ Error setting up test data: {str(e)}"


def run_evaluation_batch(collections, output_dir):
    """Run full batch evaluation"""
    if not collections:
        return (
            "⚠️ Please select at least one collection",
            None,
            None,
            None,
            "No evaluation run"
        )
    
    try:
        # Create output directory
        Path(output_dir).mkdir(exist_ok=True, parents=True)
        
        # Run evaluation
        results = run_full_evaluation(collections, output_dir)
        
        # Save results
        csv_path, json_path = save_results(results, output_dir)
        md_path = generate_summary_report(results, output_dir)
        
        # Create summary statistics
        import numpy as np
        base_results = results["base"]
        hier_results = results["hierarchical"]
        
        summary_stats = {
            "Total Queries": len(base_results),
            "Collections": ", ".join(collections),
            "Base Hit@5": f"{np.mean([r.hit_at_5 for r in base_results]) * 100:.1f}%",
            "Hier Hit@5": f"{np.mean([r.hit_at_5 for r in hier_results]) * 100:.1f}%",
            "Base MRR": f"{np.mean([r.mrr for r in base_results]):.3f}",
            "Hier MRR": f"{np.mean([r.mrr for r in hier_results]):.3f}",
            "Base Avg Latency": f"{np.mean([r.total_latency_ms for r in base_results]):.0f}ms",
            "Hier Avg Latency": f"{np.mean([r.total_latency_ms for r in hier_results]):.0f}ms",
        }
        
        # Load markdown summary
        with open(md_path, 'r') as f:
            summary_md = f.read()
        
        # Prepare download files
        return (
            f"✅ Evaluation complete! Results saved to {output_dir}/",
            summary_stats,
            str(csv_path),
            str(json_path),
            summary_md
        )
        
    except Exception as e:
        return (
            f"❌ Error during evaluation: {str(e)}",
            None,
            None,
            None,
            f"Error: {str(e)}"
        )

def get_predefined_queries_list():
    """Get list of predefined queries for dropdown"""
    return [""] + [f"{i}: {q.model_dump()}" for i, q in enumerate(EVAL_QUERIES)]


# --- Static choices (not from YAML) ---
LANG_CHOICES = ["en", "ja"]
DOC_TYPE_CHOICES = [None, "policy", "manual", "faq"]
INGEST_DOC_TYPE_CHOICES = [c for c in DOC_TYPE_CHOICES if c is not None]
INDEX_CHOICES = ["hospital", "bank", "fluid_simulation"]


# ============================================================================
# BUILD THE GRADIO UI
# ============================================================================

with gr.Blocks(theme=gr.themes.Soft(), title="RAG Evaluation System") as demo:
    gr.Markdown("# 📊 Document Ingestion and RAG Evaluation System")
    
    # Hidden state to store the parsed YAML config
    config_state = gr.State()

    with gr.Column(variant="panel"):
        gr.Markdown(
            "⬆️ **START HERE:** Upload your `config.yaml` file to enable the Domain, Section, and Topic filters below."
        )
        yaml_uploader = gr.File(
            label="Upload Configuration YAML",
            file_types=[".yaml", ".yml"]
        )

    with gr.Tab("📄 Document Ingestion"):
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

    with gr.Tab("💬 Chat with Data"):
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

    with gr.Tab("🧪 Evaluation"):
       
    
        gr.Markdown("""
        ### Run Complete Evaluation
        
        This will:
        1. Initial ingest synthetic test data (60 documents)
        2. Run 15 predefined evaluation queries
        3. Generate comprehensive reports (CSV, JSON, Markdown)
        4. Compare Base RAG vs Hierarchical RAG
        """)
        
        with gr.Row():
            with gr.Column():
                eval_collections = gr.CheckboxGroup(
                    label="Select Collections to Evaluate",
                    choices=INDEX_CHOICES,
                    value=INDEX_CHOICES,
                    info="Choose which collections to include in evaluation"
                )
                
                eval_output_dir = gr.Textbox(
                    label="Output Directory",
                    value="reports",
                    info="Directory where evaluation reports will be saved"
                )
                
                with gr.Row():
                    setup_data_btn = gr.Button(
                        "📦 Setup Synthetic Test Data",
                        variant="secondary"
                    )
                    run_eval_btn = gr.Button(
                        "▶️ Run Full Evaluation",
                        variant="primary"
                    )
            
            with gr.Column():
                eval_status = gr.Textbox(
                    label="Status",
                    lines=3,
                    interactive=False
                )
                eval_summary_stats = gr.JSON(
                    label="Summary Statistics",
                    visible=True
                )
        
        with gr.Row():
            csv_download = gr.File(
                label="📊 Download CSV Results",
                visible=True
            )
            json_download = gr.File(
                label="📋 Download JSON Results",
                visible=True
            )
        
        gr.Markdown("### 📄 Detailed Summary Report")
        eval_summary_md = gr.Markdown(
            value="*Run evaluation to see detailed results*",
            line_breaks=True
        )
        
        # Event handlers for batch evaluation
        setup_data_btn.click(
            fn=setup_synthetic_data,
            inputs=[eval_collections],
            outputs=[eval_status]
        )
        
        run_eval_btn.click(
            fn=run_evaluation_batch,
            inputs=[eval_collections, eval_output_dir],
            outputs=[
                eval_status,
                eval_summary_stats,
                csv_download,
                json_download,
                eval_summary_md
            ]
        )
    
    # --- Event Handlers ---

    # 1. When YAML is uploaded, store its content in config_state
    yaml_uploader.upload(
        fn=load_yaml_config,
        inputs=[yaml_uploader],
        outputs=[config_state]
    ).then(
        fn=update_metadata_for_index_ingest,
        inputs=[index_select_ingest, config_state],
        outputs=[domain_select_ingest, section_select_ingest, topic_select_ingest]
    ).then(
        fn=update_filters_for_index_chat,
        inputs=[index_select_chat, config_state],
        outputs=[domain_select, section_select, topic_select]
    )

    # 2. When the Ingest index changes, update its metadata
    index_select_ingest.change(
        fn=update_metadata_for_index_ingest,
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