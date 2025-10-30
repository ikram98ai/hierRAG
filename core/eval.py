from langchain.evaluation import RetrievalEvaluator
from .rag import get_vectorstore, model


def evaluate(collection_name, eval_dataset):
    vectorstore = get_vectorstore(collection_name)
    retriever = vectorstore.as_retriever(search_kwargs={"k": 5})
    # Create an evaluator instance
    retrieval_evaluator = RetrievalEvaluator.from_llm(
        llm=model, # You can use a model to help generate questions and contexts
        retriever=retriever,
        k=5, # Evaluate at k=5
    )

    # Run the evaluation over the dataset
    results = retrieval_evaluator.evaluate_retrieval(eval_dataset)

    # The results will include the computed metrics
    print(f"Results: {results}")

    # You can now analyze the metrics
    mrr_score = results["mean_reciprocal_rank"]
    hit_rate_score = results["hit_rate"]

    print(f"Mean Reciprocal Rank (MRR@5): {mrr_score:.4f}")
    print(f"Hit Rate (Hit@5): {hit_rate_score:.4f}")
