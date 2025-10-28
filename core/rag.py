from langchain_community.document_loaders import PDFMinerLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_milvus import Milvus
from dotenv import load_dotenv, find_dotenv
from typing import List
import uuid

find_dotenv()
load_dotenv()

model = ChatGoogleGenerativeAI(model="models/gemini-2.5-flash-lite")
emb_model = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")

MILVUS_URI = "./rag_task.db"


def get_vectorstore(collection_name:str)->Milvus:
    vectorstore = Milvus(
        embedding_function=emb_model,
        collection_name=collection_name,
        connection_args={"uri": MILVUS_URI},
        index_params={"index_type": "FLAT", "metric_type": "L2"},
    )
    return vectorstore


def load_docs_from_file(file_path:str)-> List[Document]:
    documents:list[Document] = PDFMinerLoader(file_path).load()
    for doc in documents:
        doc.metadata['source'] = file_path.split("/")[-1] 
    return documents


def get_chunks(docs:List[Document], language, domain, section, topic, doc_type)-> List[Document]:
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,  # chunk size (characters)
        chunk_overlap=200,  # chunk overlap (characters)
        add_start_index=True,  # track index in original document
    )
    doc_id = str(uuid.uuid4())
    chunks = text_splitter.split_documents(docs)
    chunks = [Document(page_content=chunk.page_content, 
                     metadata={
                        "source_name": chunk.metadata['source'],
                        'total_pages': chunk.metadata['total_pages'], 
                        'start_index': chunk.metadata['start_index'],
                        "domain_l1": domain,"section_l2": section,
                        "topic_l3": topic,"doc_type": doc_type, "lang": language,
                        "doc_id": doc_id, "chunk_id":str(uuid.uuid4()) 
                    }
    ) for chunk in chunks]
    return chunks


def add_document(collection_name:str, docs:List[Document]):
    vectorstore = get_vectorstore(collection_name)
    vectorstore.add_documents(docs)


