from unittest.mock import Mock, patch
import pytest

from langchain_core.documents import Document
from src.core.index import MetaData
from src.core.retrieval import retrieval, generate, reranker

@pytest.fixture
def sample_metadata():
    """Sample metadata for testing"""
    return MetaData(
        language="en",
        domain="Healthcare",
        section="Patient Care",
        topic="Diagnostics",
        doc_type="policy"
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
# ============================================================================
# RETRIEVAL TESTS
# ============================================================================

class TestRetrieval:
    """Tests for vector retrieval functionality"""
    
    @patch('src.core.retrieval.get_vectorstore')
    def test_retrieval_returns_k_documents(self, mock_vs):
        """Test that retrieval returns requested number of documents"""
        # Setup mock with 5 results
        mock_docs = [
            (Document(page_content=f"Doc {i}"), 0.9 - i*0.1)
            for i in range(5)
        ]
        mock_store = Mock()
        mock_store.similarity_search_with_relevance_scores.return_value = mock_docs
        mock_vs.return_value = mock_store
        
        filter_data = MetaData(language="en")
        results = retrieval("test query", "test_collection", filter_data)
        
        assert len(results) == 5
    
    @patch('src.core.retrieval.get_vectorstore')
    def test_retrieval_adds_similarity_scores(self, mock_vs):
        """Test that similarity scores are added to metadata"""
        mock_docs = [
            (Document(page_content="Test doc", metadata={}), 0.85)
        ]
        mock_store = Mock()
        mock_store.similarity_search_with_relevance_scores.return_value = mock_docs
        mock_vs.return_value = mock_store
        
        filter_data = MetaData(language="en")
        results = retrieval("test query", "test_collection", filter_data)
        
        assert 'similarity_score' in results[0].metadata
        assert results[0].metadata['similarity_score'] == 0.85
    
    @patch('src.core.retrieval.get_vectorstore')
    def test_retrieval_error_handling(self, mock_vs):
        """Test that retrieval handles errors gracefully"""
        mock_store = Mock()
        mock_store.similarity_search_with_relevance_scores.side_effect = ValueError("Invalid filter")
        mock_vs.return_value = mock_store
        
        filter_data = MetaData(language="en")
        results = retrieval("test query", "test_collection", filter_data)
        
        assert results == [], "Should return empty list on error"
    
    def test_reranker_preserves_documents(self, sample_documents):
        """Test that BM25 reranker preserves document information"""
        query = "MRI CT scanning equipment"
        
        reranked = reranker(query, sample_documents)
        
        assert len(reranked) <= len(sample_documents)
        assert all(isinstance(doc, Document) for doc in reranked)
    
    def test_reranker_with_empty_list(self):
        """Test reranker handles empty document list"""
        query = "test query"
        
        reranked = reranker(query, [])
        
        assert reranked == []
    
    @patch('src.core.retrieval.model')
    def test_generate_with_context(self, mock_model):
        """Test answer generation with context"""
        mock_model.invoke.return_value.content = "Generated answer"
        
        docs = [
            Document(page_content="Context document 1"),
            Document(page_content="Context document 2")
        ]
        
        answer = generate("What is the policy?", docs)
        
        assert answer == "Generated answer"
        assert mock_model.invoke.called
        
        # Check that context was included in prompt
        call_args = mock_model.invoke.call_args[0][0]
        assert "Context document 1" in call_args
        assert "Context document 2" in call_args
    
    @patch('src.core.retrieval.model')
    def test_generate_with_empty_context(self, mock_model):
        """Test answer generation with no context"""
        mock_model.invoke.return_value.content = "No context available"
        
        answer = generate("What is the policy?", [])
        
        assert mock_model.invoke.called

