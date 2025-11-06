from langchain_community.document_loaders import PDFMinerLoader,TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv, find_dotenv
from typing import List
import uuid

from src.core.index import get_vectorstore
from .index import MetaData
from .utils import mask_pii

find_dotenv()
load_dotenv()

model = ChatOpenAI(model="gpt-5-nano")


def load_documents(file_paths: List[str]):
    """Ingest files into vectorstore after processing and chunking."""
    documents: list[Document] = []
    for file_path in file_paths:
        if file_path.endswith(".txt"):
            docs = TextLoader(file_path, encoding="utf-8").load()
        elif file_path.endswith(".pdf"):
            docs = PDFMinerLoader(file_path).load()
        else:
            print(f"Unsupported file format: {file_path}")
            continue
        documents.extend(docs)

    print(f"loaded {len(documents)} documents from {len(file_paths)} files.")
    return documents

def get_chunks(documents: List[Document], metadata: MetaData):
    """Split documents into chunks and mask PII."""
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1200,  # chunk size (characters)
        chunk_overlap=200,  # chunk overlap (characters)
        add_start_index=True,  # track index in original document
    )
    chunks = text_splitter.split_documents(documents)
    print(f"generated {len(chunks)} chunks.")

    doc_id = str(uuid.uuid4())
    chunks = [
        Document(
            page_content=mask_pii(chunk.page_content),
            metadata={
                "doc_id": doc_id,
                "chunk_id": str(uuid.uuid4()),
                "source_name": chunk.metadata.get("source",'Not Available').split("/")[-1],
                "start_index": chunk.metadata.get("start_index",0),
                **metadata.model_dump(),
            },
        )
        for chunk in chunks
    ]
    return chunks


def ingest_documents(docs: List[Document], collection_name: str):
    """Ingest documents into the specified vectorstore collection."""
    vectorstore = get_vectorstore(collection_name)
    ids = [str(uuid.uuid4()) for _ in range(len(docs))]
    vectorstore.add_documents(docs, ids=ids)
    success_message = f"Ingested {len(docs)} documents into {collection_name} index."
    print(success_message)
    return success_message

