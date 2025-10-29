from langchain_community.document_loaders import PDFMinerLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
# from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_openai.embeddings import OpenAIEmbeddings
from langchain_community.retrievers import BM25Retriever
from langchain_milvus import Milvus, BM25BuiltInFunction
from dotenv import load_dotenv, find_dotenv
from typing import List, Literal, Optional
from pydantic import BaseModel
import uuid

find_dotenv()
load_dotenv()

# model = ChatGoogleGenerativeAI(model="models/gemini-2.5-flash-lite")
# emb_model = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001", output_dimensionality=1536)
model = ChatOpenAI(model="gpt-5-mini")
emb_model = OpenAIEmbeddings(model="text-embedding-3-small", dimensions=1536)

MILVUS_URI = "./rag_task.db"


def get_vectorstore(collection_name: str) -> Milvus:
    vectorstore = Milvus(
        embedding_function=emb_model,
        collection_name=collection_name,
        connection_args={"uri": MILVUS_URI},
        # builtin_function=BM25BuiltInFunction(output_field_names="sparse"),
        # text_field="text",
        # vector_field=["dense", "sparse"],
        index_params={"index_type": "FLAT", "metric_type": "L2"},
    )
    print(f"vectorstore successfully initialized for {collection_name}")
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

def reranker(query:str, docs:List[Document])-> List[Document]:
    print(f"Retrieved {len(docs)} documents")
    retriever = BM25Retriever.from_documents(docs)
    result = retriever.invoke(query)
    print("RERANKER Result: ", len(result), result[0])
    return result

def retrieval(query: str, collection_name: str, filter_data: FilterData)-> List[tuple[Document, float]]:
    vectorstore = get_vectorstore(collection_name)
    
    filters = [f'language == "{filter_data.language}"']
    if filter_data.doc_type:
        filters.append(f'doc_type == "{filter_data.doc_type}"')
    if filter_data.domain:
        filters.append(f'domain == "{filter_data.domain}"')
    if filter_data.section:
        filters.append(f'section == "{filter_data.section}"')
    if filter_data.topic:
        filters.append(f'topic == "{filter_data.topic}"')
    
    expr = " and ".join(filters) if filters else None
    
    results = vectorstore.similarity_search_with_relevance_scores(query, k=5, expr=expr)
    docs = []
    for doc,score in results:
        doc.metadata['similarity_score'] = score
        docs.append(doc)
    # docs = reranker(query, docs)
    return docs

def generate(query: str, ctx_docs: List[Document])->str:
    context = "\n".join([doc.page_content for doc in ctx_docs])
    prompt = f"""Answer shortly to the user question according to the given context. Only answer if the context is given to you.
    question: {query}
    context: {context}
"""
    output = model.invoke(prompt)
    return output.content
