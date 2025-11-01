# Hierarchical Metadata RAG vs Standard RAG

This project implements and compares two Retrieval-Augmented Generation (RAG) approaches:
- **Standard RAG:** A baseline RAG system that retrieves documents based on semantic similarity alone.
- **Hierarchical RAG:** An advanced RAG system that leverages hierarchical metadata (language, domain, section, topic, document type) to improve retrieval accuracy and efficiency.

The project includes a Gradio application for interactive testing and a comprehensive evaluation suite for generating performance reports.

## Setup

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/ikram98ai/hierRAG.git
    cd hier-rag
    ```

2.  **Install dependencies:**
    This project uses `uv` for package management.
    ```bash
    uv sync
    ```

3.  **Set up environment variables:**
    Create a `.env` file in the root of the project and add the following environment variables. You can copy the `.env.example` file.
    ```bash
    cp .env.example .env
    ```
    Update the `.env` file with your credentials:
    ```
    HF_TOKEN=your_hugging_face_token
    OPENAI_API_KEY=your_openai_api_key
    GRADIO_MCP_SERVER=True
    ```

## Usage

To run the Gradio application for interactive testing and evaluation:

```bash
uv run gradio src/app.py
```
or using the makefile:
```bash
make dev
```

This will launch a web interface with the following tabs:
- **Document Ingestion:** Upload documents and assign metadata.
- **Chat with Data:** Compare the performance of Standard RAG and Hierarchical RAG side-by-side.
- **Evaluation:** Run a full evaluation on synthetic data and generate performance reports.

## Deployment to Hugging Face Spaces

To deploy this application to Hugging Face Spaces, you can push the repository to a new Space.

1.  **Create a new Hugging Face Space.**
2.  **Push the repository to the Space:**
    ```bash
    git remote add space https://huggingface.co/spaces/your-username/your-space-name
    git push --force space main
    ```
3.  **Set the environment variables** in the Space's settings.

## Evaluation

The evaluation process can be triggered from the **Evaluation** tab in the Gradio application.

1.  **Navigate to the Evaluation tab.**
2.  **Select the collections** you want to evaluate.
3.  **Click "Setup Synthetic Test Data"** to ingest the synthetic data for the selected collections.
4.  **Click "Run Full Evaluation"** to start the evaluation.

The evaluation process will:
- Ingest synthetic test data.
- Run a series of predefined queries against both the Standard and Hierarchical RAG systems.
- Generate and display a summary report with key performance metrics (Hit@1, Hit@3, Hit@5, MRR, Latency).
- Provide download links for the full evaluation results in CSV and JSON formats.
- Display a detailed summary report in Markdown format.

You can also run the evaluation programmatically by calling the functions in `src/core/eval.py`.
