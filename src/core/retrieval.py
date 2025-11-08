from langchain_core.documents import Document
from langchain_community.retrievers import BM25Retriever
from langchain_openai import ChatOpenAI
from langchain_milvus import Milvus
from dotenv import load_dotenv, find_dotenv
from typing import List
from .index import MetaData
find_dotenv()
load_dotenv()

model = ChatOpenAI(model="gpt-5-nano")


def reranker(query: str, docs: List[Document]) -> List[Document]:
    """Rerank documents using BM25Retriever"""
    print(f"Retrieved {len(docs)} documents")
    if len(docs) <= 1:
        return docs
    retriever = BM25Retriever.from_documents(docs)
    docs = retriever.invoke(query)
    print("RERANKER Result: ", len(docs))
    return docs


def retrieval(
    query: str, filter_data: MetaData, vectorstore: Milvus
) -> List[tuple[Document, float]]:
    """Retrieve relevant documents from the vector store based on the query and filters."""
    print(
        f"RETRIEVAL query: {query[:40]}, for {vectorstore.collection_name} collection, with filters: {filter_data}"
    )

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
    try:
        results = vectorstore.similarity_search_with_relevance_scores(
            query, k=5, expr=expr
        )
    except ValueError as e:
        print(f"Error in retrieval: {str(e)}")
        return []
    docs = []
    for doc, score in results:
        doc.metadata["similarity_score"] = score
        docs.append(doc)
    # docs = reranker(query, docs)
    print("RETRIEVED DOCS: ", len(docs))
    return docs


def generate(query: str, ctx_docs: List[Document]) -> str:
    """Generate answer using the language model based on the query and context documents."""
    context = "\n".join([doc.page_content for doc in ctx_docs])
    prompt = f"""Answer shortly to the user question according to the given context. Only answer if the context is given to you.
    question: {query}
    context: {context}
"""
    output = model.invoke(prompt)
    return output.content
