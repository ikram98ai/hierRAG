from langchain_community.document_loaders import PDFMinerLoader,TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv, find_dotenv
from typing import List
import uuid
from .index import get_vectorstore, MetaData
from .utils import mask_pii

find_dotenv()
load_dotenv()

model = ChatOpenAI(model="gpt-5-nano")


def ingest(file_paths: List[str], collection_name: str, metadata: MetaData):
    documents: list[Document] = []
    for file_path in file_paths:
        if file_path.endswith(".txt"):
            docs = TextLoader(file_path, encoding="utf-8").load()
        elif file_path.endswith(".pdf"):
            docs = PDFMinerLoader(file_path).load()
        documents.extend(docs)
        for doc in docs:
            doc.metadata["source"] = file_path.split("/")[-1]
          
    print(f"loaded {len(documents)} documents from {len(file_paths)} files.")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1200,  # chunk size (characters)
        chunk_overlap=200,  # chunk overlap (characters)
        add_start_index=True,  # track index in original document
    )
    chunks = text_splitter.split_documents(documents)
    print(f"generated {len(chunks)} chunks.")

    doc_id = str(uuid.uuid4())
    docs = [
        Document(
            page_content=mask_pii(chunk.page_content),
            metadata={
                "doc_id": doc_id,
                "chunk_id": str(uuid.uuid4()),
                "source_name": chunk.metadata["source"],
                "start_index": chunk.metadata["start_index"],
                **metadata.model_dump(),
            },
        )
        for chunk in chunks
    ]

    vectorstore = get_vectorstore(collection_name)
    ids = [str(uuid.uuid4()) for _ in range(len(docs))]
    vectorstore.add_documents(docs, ids=ids)
    success_message = f"Ingested {len(docs)} documents into {collection_name} index."
    print(success_message)
    return success_message
