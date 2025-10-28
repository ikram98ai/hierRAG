from langchain_community.document_loaders import PDFMinerLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_milvus import Milvus
from dotenv import load_dotenv, find_dotenv
from typing import List, Literal, Optional
from pydantic import BaseModel
import uuid

find_dotenv()
load_dotenv()

model = ChatGoogleGenerativeAI(model="models/gemini-2.5-flash-lite")
emb_model = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")

MILVUS_URI = "./rag_task.db"


def get_vectorstore(collection_name: str) -> Milvus:
    vectorstore = Milvus(
        embedding_function=emb_model,
        collection_name=collection_name,
        connection_args={"uri": MILVUS_URI},
        index_params={"index_type": "FLAT", "metric_type": "L2"},
    )
    print(f"vector store successfully initialized for {collection_name}")
    return vectorstore


class FilterData(BaseModel):
    language: Literal["ja", "en"]
    domain: Optional[str] = None
    section: Optional[str] = None
    topic: Optional[str] = None
    doc_type: Optional[Literal["policy", "manual", "faq"]] = None


def ingest(file_paths: List[str], collection_name: str, filter_data: FilterData):
    documents: list[Document] = []
    for file_path in file_paths:
        docs = PDFMinerLoader(file_path).load()
        documents.extend(docs)
        for doc in docs:
            doc.metadata["source"] = file_path.split("/")[-1]
    print(f"loaded {len(documents)} documents from {len(file_paths)} files.")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,  # chunk size (characters)
        chunk_overlap=200,  # chunk overlap (characters)
        add_start_index=True,  # track index in original document
    )
    chunks = text_splitter.split_documents(documents)
    print(f"generated {len(chunks)} chunks.")

    doc_id = str(uuid.uuid4())
    docs = [
        Document(
            page_content=chunk.page_content,
            metadata={
                "doc_id": doc_id, "chunk_id": str(uuid.uuid4()),
                "source_name": chunk.metadata["source"],
                "total_pages": chunk.metadata["total_pages"],
                "start_index": chunk.metadata["start_index"],
                **filter_data.model_dump(),
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


def retrieval_filter(query: str, collection_name: str, filter_data: FilterData):
    vectorstore = get_vectorstore(collection_name)
    expr = f'language == "{filter_data.language}" and domain == "{filter_data.domain}" and \
               section == "{filter_data.section}" and topic == "{filter_data.topic}" and doc_type == "{filter_data.doc_type}"'
    docs = vectorstore.similarity_search(query, k=5, expr=expr)
    return docs


def retrieval(query: str, collection_name: str, language: str):
    vectorstore = get_vectorstore(collection_name)
    expr = f'language == "{language}"'
    docs = vectorstore.similarity_search(query, k=5, expr=expr)
    return docs


def generate(query: str, ctx_docs: List[Document]):
    context = "\n".join([doc.page_content for doc in ctx_docs])
    prompt = f"""Answer the user query according to the given context.
    query: {query}
    context: {context}
"""
    output = model.invoke(prompt)
    return output.content
