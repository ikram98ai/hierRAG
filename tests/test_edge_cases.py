
import pytest
from unittest.mock import Mock, patch

from langchain_core.documents import Document
from src.core.index import MetaData, get_vectorstore
from src.core.retrieval import retrieval
from src.core.utils import mask_pii
from src.core.eval import (
    calculate_mrr,
    calculate_hit_at_k,
)

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

class TestEdgeCases:
    """Tests for edge cases and boundary conditions"""
    
    def test_very_long_query(self):
        """Test handling of very long queries"""
        long_query = "What is the policy " * 100  # 500+ words
        
        # Should not crash
        filter_data = MetaData(language="en")
        
        with patch('src.core.index.get_vectorstore') as mock_vs:
            mock_store = Mock()
            mock_store.similarity_search_with_relevance_scores.return_value = []
            mock_vs.return_value = mock_store
            vectorstore = get_vectorstore("test_collection")
            results = retrieval(long_query, filter_data, vectorstore)
            
            assert isinstance(results, list)
    
    def test_special_characters_in_query(self):
        """Test handling of special characters"""
        special_query = "What's the policy for <patient> & [treatment]?"
        
        filter_data = MetaData(language="en")
        
        with patch('src.core.index.get_vectorstore') as mock_vs:
            mock_store = Mock()
            mock_store.similarity_search_with_relevance_scores.return_value = []
            mock_vs.return_value = mock_store
            vectorstore = get_vectorstore("test_collection")
            results = retrieval(special_query, filter_data, vectorstore)
            
            assert isinstance(results, list)
    
    def test_unicode_characters(self):
        """Test handling of unicode characters"""
        unicode_text = "患者のケア方針について教えてください。"
        
        masked = mask_pii(unicode_text)
        
        assert isinstance(masked, str)
    
    def test_empty_ground_truth(self):
        """Test metrics with empty ground truth"""
        ground_truth = []
        docs = [Document(page_content="Test")]
        
        mrr = calculate_mrr(ground_truth, docs)
        hit = calculate_hit_at_k(ground_truth, docs, 5)
        
        assert mrr == 0.0
        assert hit is False
    
    def test_duplicate_documents(self, sample_documents):
        """Test handling of duplicate documents in results"""
        # Duplicate the first document
        duplicated = sample_documents + [sample_documents[0]]
        
        ground_truth = ["MRI and CT scanning"]
        mrr = calculate_mrr(ground_truth, duplicated)
        
        # Should still find it in first position
        assert mrr == 1.0
    
    def test_metadata_with_null_values(self):
        """Test document with null metadata values"""
        doc = Document(
            page_content="Test content",
            metadata={
                'domain': None,
                'section': None,
                'topic': None
            }
        )
        
        # Should not crash when accessing metadata
        assert doc.metadata.get('domain') is None
        assert doc.metadata.get('section') is None
    
    def test_concurrent_filter_combinations(self):
        """Test multiple filter combinations"""
        test_cases = [
            MetaData(language="en"),
            MetaData(language="en", domain="Healthcare"),
            MetaData(language="en", domain="Healthcare", section="Patient Care"),
            MetaData(language="en", doc_type="policy"),
            MetaData(language="ja", domain="Finance", section="Loans", topic="Interest Rates")
        ]
        
        for filter_data in test_cases:
            with patch('src.core.index.get_vectorstore') as mock_vs:
                mock_store = Mock()
                mock_store.similarity_search_with_relevance_scores.return_value = []
                mock_vs.return_value = mock_store
                
                # Should handle all combinations without error
                vectorstore = get_vectorstore("test_collection")
                results = retrieval("test query", filter_data, vectorstore)
                assert isinstance(results, list)
    
    def test_large_batch_evaluation(self):
        """Test evaluation with many queries"""
        from src.core.eval import EvalQuery, evaluate_single_query
        
        # Create many queries
        queries = [
            EvalQuery(
                query=f"Query {i}",
                collection="hospital",
                language="en",
                domain=None,
                section=None,
                topic=None,
                doc_type=None,
                ground_truth_chunks=["test"],
                description=f"Test query {i}"
            )
            for i in range(50)
        ]
        
        # Should handle batch without issues
        with patch('src.core.eval.retrieval') as mock_ret:
            with patch('src.core.eval.generate') as mock_gen:
                mock_ret.return_value = []
                mock_gen.return_value = "Test"
                
                results = [evaluate_single_query(q, "base") for q in queries[:5]]
                
                assert len(results) == 5
                assert all(r.query_id for r in results)
