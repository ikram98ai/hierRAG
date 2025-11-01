from unittest.mock import patch
import pytest
import tempfile
import shutil
from pathlib import Path
from langchain_core.documents import Document
from src.core.eval import (
    calculate_mrr,
    calculate_hit_at_k,
    calculate_semantic_similarity,
    evaluate_single_query,
    EvalQuery,
)

@pytest.fixture(scope="session")
def test_db_path():
    """Create temporary database for testing"""
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test_rag.db"
    yield str(db_path)
    # Cleanup after all tests
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def sample_documents():
    """Sample documents for retrieval tests"""
    return [
        Document(
            page_content="The hospital uses advanced MRI and CT scanning equipment.",
            metadata={
                "language": "en",
                "domain": "Healthcare",
                "section": "Patient Care",
                "topic": "Diagnostics",
                "similarity_score": 0.95
            }
        ),
        Document(
            page_content="Emergency cardiac treatment follows the ABCDE protocol.",
            metadata={
                "language": "en",
                "domain": "Healthcare",
                "section": "Emergency",
                "topic": "Treatment",
                "similarity_score": 0.75
            }
        ),
        Document(
            page_content="HIPAA compliance requires annual staff training.",
            metadata={
                "language": "en",
                "domain": "Policy",
                "section": "Administrative",
                "topic": "Compliance",
                "similarity_score": 0.60
            }
        )
    ]

# ============================================================================
# EVALUATION METRICS TESTS
# ============================================================================

class TestEvaluationMetrics:
    """Tests for evaluation metric calculations"""
    
    def test_calculate_mrr_first_position(self, sample_documents):
        """Test MRR calculation when answer is in first position"""
        ground_truth = ["MRI and CT scanning"]
        
        mrr = calculate_mrr(ground_truth, sample_documents)
        
        assert mrr == 1.0, "MRR should be 1.0 for first position"
    
    def test_calculate_mrr_third_position(self, sample_documents):
        """Test MRR calculation when answer is in third position"""
        ground_truth = ["HIPAA compliance"]
        
        mrr = calculate_mrr(ground_truth, sample_documents)
        
        assert abs(mrr - 1/3) < 0.01, "MRR should be 1/3 for third position"
    
    def test_calculate_mrr_not_found(self, sample_documents):
        """Test MRR calculation when answer is not found"""
        ground_truth = ["nonexistent content"]
        
        mrr = calculate_mrr(ground_truth, sample_documents)
        
        assert mrr == 0.0, "MRR should be 0.0 when not found"
    
    def test_hit_at_k_found(self, sample_documents):
        """Test Hit@k when answer is within k documents"""
        ground_truth = ["HIPAA compliance"]
        
        hit_at_5 = calculate_hit_at_k(ground_truth, sample_documents, k=5)
        
        assert hit_at_5 is True
    
    def test_hit_at_k_not_found(self, sample_documents):
        """Test Hit@k when answer is not within k documents"""
        ground_truth = ["HIPAA compliance"]
        
        hit_at_1 = calculate_hit_at_k(ground_truth, sample_documents, k=1)
        
        assert hit_at_1 is False
    
    def test_hit_at_k_multiple_ground_truths(self, sample_documents):
        """Test Hit@k with multiple ground truth options"""
        ground_truth = ["nonexistent", "MRI and CT", "also nonexistent"]
        
        hit_at_1 = calculate_hit_at_k(ground_truth, sample_documents, k=1)
        
        assert hit_at_1 is True, "Should find match from multiple options"
    
    @patch('src.core.index.emb_model')
    def test_semantic_similarity_calculation(self, mock_emb, sample_documents):
        """Test semantic similarity calculation"""
        # Mock embeddings
        mock_emb.embed_query.return_value = [0.5] * 1536
        mock_emb.embed_documents.return_value = [
            [0.6] * 1536,
            [0.4] * 1536,
            [0.5] * 1536
        ]
        
        similarity = calculate_semantic_similarity("test query", sample_documents)
        
        assert isinstance(similarity, float)
        assert 0 <= similarity <= 1
    
    def test_semantic_similarity_empty_docs(self):
        """Test semantic similarity with empty document list"""
        similarity = calculate_semantic_similarity("test query", [])
        
        assert similarity == 0.0


# ============================================================================
# EVALUATION WORKFLOW TESTS
# ============================================================================

class TestEvaluationWorkflow:
    """Tests for end-to-end evaluation workflows"""
    
    @patch('src.core.eval.retrieval')
    @patch('src.core.eval.generate')
    @patch('src.core.eval.calculate_semantic_similarity')
    def test_evaluate_single_query_base_rag(self, mock_sem_sim, mock_gen, mock_ret):
        """Test single query evaluation for base RAG"""
        # Setup mocks
        mock_docs = [
            Document(
                page_content="Test content",
                metadata={'similarity_score': 0.9}
            )
        ]
        mock_ret.return_value = mock_docs
        mock_gen.return_value = "Test answer"
        mock_sem_sim.return_value = 0.85
        
        eval_query = EvalQuery(
            query="What is the policy?",
            collection="test_collection",
            language="en",
            domain=None,
            section=None,
            topic=None,
            doc_type=None,
            ground_truth_chunks=["policy", "test"],
            description="Test query"
        )
        
        result = evaluate_single_query(eval_query, rag_type="base")
        
        assert result.rag_type == "base"
        assert result.retrieved_docs == 1
        assert result.generated_answer == "Test answer"
        assert result.retrieval_latency_ms > 0
        assert result.total_latency_ms > 0
    
    @patch('src.core.eval.retrieval')
    @patch('src.core.eval.generate')
    def test_evaluate_single_query_hierarchical_rag(self, mock_gen, mock_ret):
        """Test single query evaluation for hierarchical RAG"""
        mock_ret.return_value = []
        mock_gen.return_value = "No relevant documents found."
        
        eval_query = EvalQuery(
            query="What is the policy?",
            collection="test_collection",
            language="en",
            domain="Healthcare",
            section="Patient Care",
            topic="Diagnostics",
            doc_type="policy",
            ground_truth_chunks=["policy"],
            description="Test query"
        )
        
        result = evaluate_single_query(eval_query, rag_type="hierarchical")
        
        assert result.rag_type == "hierarchical"
        assert result.retrieved_docs == 0
        assert result.hit_at_5 is False
        assert result.mrr == 0.0
    
 