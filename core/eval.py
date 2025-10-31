"""
Retrieval Evaluation Script for Base RAG vs Hierarchical RAG
Generates synthetic test data, evaluates retrieval performance, and produces reports.
"""

import json
import csv
import time
import uuid
from pathlib import Path
from typing import List, Dict
from datetime import datetime
from dataclasses import dataclass, asdict
import numpy as np
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from dotenv import load_dotenv, find_dotenv
from .index import MetaData, get_vectorstore
from .retrieval import retrieval, generate
from .synthetic_data import SYNTHETIC_DOCUMENTS, EVAL_QUERIES, EvalQuery

find_dotenv()
load_dotenv()

# Embedding model for semantic similarity
emb_model = OpenAIEmbeddings(model="text-embedding-3-small", dimensions=1536)


@dataclass
class EvalResult:
    """Evaluation result for a single query"""
    query_id: str
    collection: str
    query: str
    rag_type: str  # "base" or "hierarchical"
    
    # Retrieval metrics
    retrieved_docs: int
    hit_at_1: bool
    hit_at_3: bool
    hit_at_5: bool
    mrr: float
    avg_similarity_score: float
    
    # Latency
    retrieval_latency_ms: float
    generation_latency_ms: float
    total_latency_ms: float
    
    # Semantic similarity
    avg_semantic_similarity: float
    
    # Generated answer
    generated_answer: str
    
    # Metadata
    filters_used: Dict
    timestamp: str


# ============================================================================
# EVALUATION FUNCTIONS
# ============================================================================

def calculate_semantic_similarity(query: str, documents: List[Document]) -> float:
    """Calculate average semantic similarity between query and retrieved documents"""
    if not documents:
        return 0.0
    
    query_embedding = emb_model.embed_query(query)
    doc_embeddings = emb_model.embed_documents([doc.page_content for doc in documents])
    
    similarities = []
    for doc_emb in doc_embeddings:
        # Cosine similarity
        similarity = np.dot(query_embedding, doc_emb) / (
            np.linalg.norm(query_embedding) * np.linalg.norm(doc_emb)
        )
        similarities.append(similarity)
    
    return float(np.mean(similarities))


def calculate_mrr(ground_truth: List[str], retrieved_docs: List[Document]) -> float:
    """Calculate Mean Reciprocal Rank"""
    for rank, doc in enumerate(retrieved_docs, start=1):
        # Check if any ground truth snippet appears in the document
        for truth in ground_truth:
            if truth.lower() in doc.page_content.lower():
                return 1.0 / rank
    return 0.0


def calculate_hit_at_k(ground_truth: List[str], retrieved_docs: List[Document], k: int) -> bool:
    """Check if any ground truth appears in top-k results"""
    for doc in retrieved_docs[:k]:
        for truth in ground_truth:
            if truth.lower() in doc.page_content.lower():
                return True
    return False


def evaluate_single_query(
    eval_query: EvalQuery,
    rag_type: str = "base"
) -> EvalResult:
    """Evaluate a single query with either base or hierarchical RAG"""
    
    # Set up filters based on RAG type
    if rag_type == "base":
        filters = MetaData(language=eval_query.language)
        filters_dict = {"language": eval_query.language}
    else:  # hierarchical
        filters = MetaData(
            language=eval_query.language,
            domain=eval_query.domain,
            section=eval_query.section,
            topic=eval_query.topic,
            doc_type=eval_query.doc_type
        )
        filters_dict = {
            "language": eval_query.language,
            "domain": eval_query.domain,
            "section": eval_query.section,
            "topic": eval_query.topic,
            "doc_type": eval_query.doc_type
        }
    
    # Retrieval
    ret_start = time.time()
    docs = retrieval(eval_query.query, eval_query.collection, filters)
    ret_end = time.time()
    ret_latency = (ret_end - ret_start) * 1000  # Convert to ms
    
    # Generation
    gen_start = time.time()
    answer = generate(eval_query.query, docs) if docs else "No relevant documents found."
    gen_end = time.time()
    gen_latency = (gen_end - gen_start) * 1000  # Convert to ms
    
    total_latency = ret_latency + gen_latency
    
    # Calculate metrics
    hit_1 = calculate_hit_at_k(eval_query.ground_truth_chunks, docs, 1)
    hit_3 = calculate_hit_at_k(eval_query.ground_truth_chunks, docs, 3)
    hit_5 = calculate_hit_at_k(eval_query.ground_truth_chunks, docs, 5)
    mrr = calculate_mrr(eval_query.ground_truth_chunks, docs)
    
    avg_sim_score = np.mean([doc.metadata.get('similarity_score', 0) for doc in docs]) if docs else 0.0
    semantic_sim = calculate_semantic_similarity(eval_query.query, docs)
    
    query_id = f"{eval_query.collection}_{rag_type}_{hash(eval_query.query) % 10000}"
    
    return EvalResult(
        query_id=query_id,
        collection=eval_query.collection,
        query=eval_query.query,
        rag_type=rag_type,
        retrieved_docs=len(docs),
        hit_at_1=hit_1,
        hit_at_3=hit_3,
        hit_at_5=hit_5,
        mrr=mrr,
        avg_similarity_score=float(avg_sim_score),
        retrieval_latency_ms=ret_latency,
        generation_latency_ms=gen_latency,
        total_latency_ms=total_latency,
        avg_semantic_similarity=semantic_sim,
        generated_answer=answer,
        filters_used=filters_dict,
        timestamp=datetime.now().isoformat()
    )


def run_full_evaluation(
    collections: List[str] = None,
    output_dir: str = "reports"
) -> Dict[str, List[EvalResult]]:
    """Run complete evaluation on all queries"""
    
    if collections is None:
        collections = ["hospital", "bank", "fluid_simulation"]
    
    Path(output_dir).mkdir(exist_ok=True)
    
    all_results = {
        "base": [],
        "hierarchical": []
    }
    
    # Filter queries by requested collections
    queries_to_eval = [q for q in EVAL_QUERIES if q.collection in collections]
    
    print(f"\n{'='*70}")
    print(f"Starting Evaluation: {len(queries_to_eval)} queries across {len(collections)} collections")
    print(f"{'='*70}\n")
    
    for i, eval_query in enumerate(queries_to_eval, 1):
        print(f"[{i}/{len(queries_to_eval)}] Evaluating: {eval_query.description}")
        print(f"  Collection: {eval_query.collection}")
        print(f"  Query: {eval_query.query[:60]}...")
        
        # Evaluate with base RAG
        print("  - Running Base RAG...")
        base_result = evaluate_single_query(eval_query, "base")
        all_results["base"].append(base_result)
        
        # Evaluate with hierarchical RAG
        print("  - Running Hierarchical RAG...")
        hier_result = evaluate_single_query(eval_query, "hierarchical")
        all_results["hierarchical"].append(hier_result)
        
        print(f"  ✓ Complete (Base: {base_result.total_latency_ms:.0f}ms, Hier: {hier_result.total_latency_ms:.0f}ms)\n")
    
    return all_results


def save_results(results: Dict[str, List[EvalResult]], output_dir: str = "reports"):
    """Save evaluation results to CSV and JSON"""
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    Path(output_dir).mkdir(exist_ok=True)
    
    # Combine all results
    all_results = results["base"] + results["hierarchical"]
    
    # Save as CSV
    csv_path = Path(output_dir) / f"eval_results_{timestamp}.csv"
    with open(csv_path, 'w', newline='') as f:
        if all_results:
            fieldnames = list(asdict(all_results[0]).keys())
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for result in all_results:
                row = asdict(result)
                # Convert complex types to strings
                row['filters_used'] = json.dumps(row['filters_used'])
                writer.writerow(row)
    
    print(f"✓ Saved CSV report: {csv_path}")
    
    # Save as JSON
    json_path = Path(output_dir) / f"eval_results_{timestamp}.json"
    json_data = {
        "metadata": {
            "timestamp": timestamp,
            "total_queries": len(all_results),
            "collections_tested": list(set(r.collection for r in all_results))
        },
        "results": {
            "base": [asdict(r) for r in results["base"]],
            "hierarchical": [asdict(r) for r in results["hierarchical"]]
        }
    }
    with open(json_path, 'w') as f:
        json.dump(json_data, f, indent=2)
    
    print(f"✓ Saved JSON report: {json_path}")
    
    return csv_path, json_path


def generate_summary_report(results: Dict[str, List[EvalResult]], output_dir: str = "reports"):
    """Generate markdown summary report with comparative analysis"""
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    md_path = Path(output_dir) / f"eval_summary_{timestamp}.md"
    
    base_results = results["base"]
    hier_results = results["hierarchical"]
    
    # Calculate aggregate metrics
    def calc_metrics(result_list):
        return {
            "total_queries": len(result_list),
            "avg_hit_at_1": np.mean([r.hit_at_1 for r in result_list]) * 100,
            "avg_hit_at_3": np.mean([r.hit_at_3 for r in result_list]) * 100,
            "avg_hit_at_5": np.mean([r.hit_at_5 for r in result_list]) * 100,
            "avg_mrr": np.mean([r.mrr for r in result_list]),
            "avg_similarity": np.mean([r.avg_similarity_score for r in result_list]),
            "avg_semantic_sim": np.mean([r.avg_semantic_similarity for r in result_list]),
            "avg_retrieval_latency": np.mean([r.retrieval_latency_ms for r in result_list]),
            "avg_generation_latency": np.mean([r.generation_latency_ms for r in result_list]),
            "avg_total_latency": np.mean([r.total_latency_ms for r in result_list]),
        }
    
    base_metrics = calc_metrics(base_results)
    hier_metrics = calc_metrics(hier_results)
    
    # Calculate per-collection metrics
    collections = list(set(r.collection for r in base_results))
    collection_metrics = {}
    
    for collection in collections:
        collection_metrics[collection] = {
            "base": calc_metrics([r for r in base_results if r.collection == collection]),
            "hierarchical": calc_metrics([r for r in hier_results if r.collection == collection])
        }
    
    # Generate markdown report
    with open(md_path, 'w') as f:
        f.write("# RAG Retrieval Evaluation Report\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("---\n\n")
        
        # Executive Summary
        f.write("## Executive Summary\n\n")
        f.write(f"This report compares **Base RAG** (language-only filtering) against ")
        f.write(f"**Hierarchical RAG** (domain/section/topic/doc_type filtering) across ")
        f.write(f"{base_metrics['total_queries']} evaluation queries.\n\n")
        
        # Overall Performance Comparison
        f.write("## Overall Performance Comparison\n\n")
        f.write("| Metric | Base RAG | Hierarchical RAG | Δ (Improvement) |\n")
        f.write("|--------|----------|------------------|------------------|\n")
        
        metrics_to_show = [
            ("Hit@1", "avg_hit_at_1", "%", True),
            ("Hit@3", "avg_hit_at_3", "%", True),
            ("Hit@5", "avg_hit_at_5", "%", True),
            ("MRR", "avg_mrr", "", True),
            ("Avg Similarity Score", "avg_similarity", "", True),
            ("Semantic Similarity", "avg_semantic_sim", "", True),
            ("Retrieval Latency", "avg_retrieval_latency", "ms", False),
            ("Generation Latency", "avg_generation_latency", "ms", False),
            ("Total Latency", "avg_total_latency", "ms", False),
        ]
        
        for label, key, unit, higher_better in metrics_to_show:
            base_val = base_metrics[key]
            hier_val = hier_metrics[key]
            
            if higher_better:
                delta = hier_val - base_val
                delta_pct = (delta / base_val * 100) if base_val > 0 else 0
                delta_str = f"+{delta:.2f}{unit} ({delta_pct:+.1f}%)" if delta >= 0 else f"{delta:.2f}{unit} ({delta_pct:.1f}%)"
            else:
                delta = base_val - hier_val
                delta_pct = (delta / base_val * 100) if base_val > 0 else 0
                delta_str = f"-{delta:.2f}{unit} ({delta_pct:.1f}% faster)" if delta >= 0 else f"+{abs(delta):.2f}{unit} ({abs(delta_pct):.1f}% slower)"
            
            f.write(f"| {label} | {base_val:.2f}{unit} | {hier_val:.2f}{unit} | {delta_str} |\n")
        
        f.write("\n")
        
        # Per-Collection Analysis
        f.write("## Per-Collection Analysis\n\n")
        
        for collection in sorted(collections):
            f.write(f"### {collection.replace('_', ' ').title()}\n\n")
            
            base_coll = collection_metrics[collection]["base"]
            hier_coll = collection_metrics[collection]["hierarchical"]
            
            f.write("| Metric | Base RAG | Hierarchical RAG |\n")
            f.write("|--------|----------|------------------|\n")
            f.write(f"| Hit@1 | {base_coll['avg_hit_at_1']:.1f}% | {hier_coll['avg_hit_at_1']:.1f}% |\n")
            f.write(f"| Hit@5 | {base_coll['avg_hit_at_5']:.1f}% | {hier_coll['avg_hit_at_5']:.1f}% |\n")
            f.write(f"| MRR | {base_coll['avg_mrr']:.3f} | {hier_coll['avg_mrr']:.3f} |\n")
            f.write(f"| Total Latency | {base_coll['avg_total_latency']:.0f}ms | {hier_coll['avg_total_latency']:.0f}ms |\n")
            f.write("\n")
        
        # Key Findings
        f.write("## Key Findings\n\n")
        
        # Accuracy improvement
        hit5_improvement = hier_metrics['avg_hit_at_5'] - base_metrics['avg_hit_at_5']
        mrr_improvement = hier_metrics['avg_mrr'] - base_metrics['avg_mrr']
        
        f.write(f"1. **Accuracy:** Hierarchical RAG achieved {hier_metrics['avg_hit_at_5']:.1f}% Hit@5 ")
        f.write(f"compared to {base_metrics['avg_hit_at_5']:.1f}% for Base RAG ")
        f.write(f"({hit5_improvement:+.1f}% improvement).\n\n")
        
        f.write(f"2. **Ranking Quality:** Mean Reciprocal Rank improved from {base_metrics['avg_mrr']:.3f} ")
        f.write(f"to {hier_metrics['avg_mrr']:.3f} ({mrr_improvement:+.3f}).\n\n")
        
        # Latency analysis
        latency_change = hier_metrics['avg_total_latency'] - base_metrics['avg_total_latency']
        latency_pct = (latency_change / base_metrics['avg_total_latency'] * 100)
        
        f.write(f"3. **Latency:** Hierarchical RAG ")
        if latency_change < 0:
            f.write(f"was faster by {abs(latency_change):.0f}ms ({abs(latency_pct):.1f}% reduction)")
        else:
            f.write(f"added {latency_change:.0f}ms ({latency_pct:.1f}% increase)")
        f.write(f" compared to Base RAG.\n\n")
        
        # Best performing collection
        best_collection = max(collections, 
                            key=lambda c: collection_metrics[c]["hierarchical"]["avg_hit_at_5"])
        f.write(f"4. **Best Performance:** The '{best_collection}' collection showed ")
        f.write(f"strongest results with {collection_metrics[best_collection]['hierarchical']['avg_hit_at_5']:.1f}% Hit@5.\n\n")
        
        # Recommendations
        f.write("## Recommendations\n\n")
        
        if hier_metrics['avg_hit_at_5'] > base_metrics['avg_hit_at_5'] + 5:
            f.write("- ✅ **Use Hierarchical RAG** for production deployments where metadata filtering is available.\n")
        else:
            f.write("- ⚠️ **Limited benefit** from hierarchical filtering detected. Consider reviewing metadata quality.\n")
        
        if hier_metrics['avg_total_latency'] < base_metrics['avg_total_latency'] * 1.2:
            f.write("- ✅ Latency impact is acceptable for the accuracy gains.\n")
        else:
            f.write("- ⚠️ Consider optimizing index structure to reduce latency overhead.\n")
        
        f.write("\n---\n\n")
        f.write("## Detailed Query Results\n\n")
        
        # Sample queries with comparison
        for i, (base_r, hier_r) in enumerate(zip(base_results[:5], hier_results[:5]), 1):
            f.write(f"### Query {i}: {base_r.query}\n\n")
            f.write(f"**Collection:** {base_r.collection}\n\n")
            
            f.write("| Aspect | Base RAG | Hierarchical RAG |\n")
            f.write("|--------|----------|------------------|\n")
            f.write(f"| Hit@5 | {'✓' if base_r.hit_at_5 else '✗'} | {'✓' if hier_r.hit_at_5 else '✗'} |\n")
            f.write(f"| MRR | {base_r.mrr:.3f} | {hier_r.mrr:.3f} |\n")
            f.write(f"| Retrieved Docs | {base_r.retrieved_docs} | {hier_r.retrieved_docs} |\n")
            f.write(f"| Total Latency | {base_r.total_latency_ms:.0f}ms | {hier_r.total_latency_ms:.0f}ms |\n")
            f.write(f"| Semantic Sim | {base_r.avg_semantic_similarity:.3f} | {hier_r.avg_semantic_similarity:.3f} |\n")
            f.write("\n")
    
    print(f"✓ Saved summary report: {md_path}")
    return md_path


def setup_test_data(collections: List[str] = None):
    """Ingest synthetic test documents into vector stores"""
    
    print("\n" + "="*70)
    print("Setting up test data for evaluation")
    print("="*70 + "\n")
    
    for collection_name in collections:
        if collection_name not in SYNTHETIC_DOCUMENTS:
            print(f"⚠️  No synthetic data available for '{collection_name}', skipping...")
            continue
        
        docs = SYNTHETIC_DOCUMENTS[collection_name]
        print(f"\n📚 Ingesting {len(docs)} documents into '{collection_name}' collection...")
        documents = []
        for i, doc_data in enumerate(docs, 1):
        
            metadata = doc_data["metadata"]
            metadata['source_name'] = collection_name+"_eval"
            doc = Document(page_content=doc_data["content"], metadata=metadata)
            documents.append(doc)

        vectorstore = get_vectorstore(collection_name)
        ids = [str(uuid.uuid4()) for _ in range(len(documents))]
        vectorstore.add_documents(documents, ids=ids)

        print(f"✓ Completed '{collection_name}' collection")
    
    print("\n" + "="*70)
    print("Test data setup complete!")
    print("="*70 + "\n")

    return len(documents)