# from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_openai.embeddings import OpenAIEmbeddings
from langchain_milvus import Milvus, BM25BuiltInFunction
from typing import Literal, Optional
from pydantic import BaseModel
from dotenv import load_dotenv, find_dotenv

find_dotenv()
load_dotenv()


class MetaData(BaseModel):
    language: Literal["ja", "en"]
    domain: Optional[str] = None
    section: Optional[str] = None
    topic: Optional[str] = None
    doc_type: Optional[Literal["policy", "manual", "faq"]] = None


# model = ChatGoogleGenerativeAI(model="models/gemini-2.5-flash-lite")
# emb_model = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001", output_dimensionality=1536)
model = ChatOpenAI(model="gpt-5-nano")
emb_model = OpenAIEmbeddings(model="text-embedding-3-small", dimensions=1536)

MILVUS_URI = "./data/rag_task.db"


def get_vectorstore(collection_name: str) -> Milvus:
    vectorstore = Milvus(
        embedding_function=emb_model,
        collection_name=collection_name,
        connection_args={"uri": MILVUS_URI},
        index_params={"index_type": "FLAT", "metric_type": "L2"},
    )
    # builtin_function=BM25BuiltInFunction(output_field_names="sparse"),
    # text_field="text",
    # vector_field=["dense", "sparse"],
    print(f"vectorstore successfully initialized for {collection_name}")
    return vectorstore
