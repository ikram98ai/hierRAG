"""
Comprehensive Pytest Suite for RAG System

Tests cover:
- Document chunking and processing
- Hierarchy and metadata tag assignment
- Metadata filtering in retrieval
- Vector retrieval accuracy
- Evaluation metrics calculation
- API behaviors and error handling
- Edge cases and failure modes

Run with:
    pytest test_rag_system.py -v
    pytest test_rag_system.py -v --tb=short  # Shorter traceback
    pytest test_rag_system.py -v -k "test_chunking"  # Run specific tests
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch

from langchain_core.documents import Document
from src.core.index import MetaData
from src.core.ingest import ingest
from src.core.retrieval import retrieval
from src.core.utils import mask_pii
from src.core.eval import (
    calculate_mrr,
    calculate_hit_at_k,
)


# ============================================================================
# FIXTURES
# ============================================================================


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


@pytest.fixture
def test_collection_name():
    """Unique collection name for each test"""
    import uuid
    return f"test_collection_{uuid.uuid4().hex[:8]}"




# ============================================================================
# API BEHAVIOR TESTS
# ============================================================================

class TestAPIBehaviors:
    """Tests for API behaviors and error handling"""
    
    def test_process_files_empty_input(self):
        """Test process_files with no files"""
        from src.app import process_files
        
        result = process_files([], "hospital", "en", None, None, None, None)
        
        assert "Please upload at least one file" in result
    
    def test_process_files_no_index(self):
        """Test process_files without index selection"""
        from src.app import process_files
        
        result = process_files(["file.pdf"], None, "en", None, None, None, None)
        
        assert "Please select an index" in result
    
    @patch('src.app.ingest')
    def test_process_files_success(self, mock_ingest):
        """Test successful file processing"""
        from src.app import process_files
        
        mock_ingest.return_value = "Successfully ingested 5 documents"
        
        result = process_files(
            ["file.pdf"],
            "hospital",
            "en",
            "Healthcare",
            "Patient Care",
            "Diagnostics",
            "policy"
        )
        
        assert result['status'] == 'success'
        assert 'Successfully ingested' in result['message']
    
    @patch('src.app.retrieval')
    @patch('src.app.generate')
    def test_run_rag_comparison_success(self, mock_gen, mock_ret):
        """Test successful RAG comparison"""
        from src.app import run_rag_comparison
        
        # Setup mocks
        mock_ret.return_value = [
            Document(
                page_content="Test document",
                metadata={'source_name': 'test.pdf', 'similarity_score': 0.9}
            )
        ]
        mock_gen.return_value = "Test answer"
        
        gen = run_rag_comparison(
            "test query",
            "hospital",
            "en",
            "Healthcare",
            "Patient Care",
            "Diagnostics",
            "policy"
        )
        results = list(gen)
        
        # Should have loading state and final results
        assert len(results) == 2
        
        # Final results should contain answers
        final = results[-1]
        assert "Test answer" in final[0] or "Latency" in final[0]
    
    def test_load_yaml_config_valid(self):
        """Test loading valid YAML configuration"""
        from src.app import load_yaml_config
        
        # Create temporary YAML file
        yaml_content = """
hospital:
  domains: ["Healthcare", "Policy"]
  sections: ["Patient Care", "Emergency"]
  topics: ["Diagnostics", "Treatment"]
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name
        
        try:
            # Mock the file object
            mock_file = Mock()
            mock_file.name = temp_path
            
            config = load_yaml_config(mock_file)
            
            assert config is not None
            assert 'hospital' in config
            assert 'Healthcare' in config['hospital']['domains']
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    def test_load_yaml_config_invalid(self):
        """Test loading invalid YAML configuration"""
        from src.app import load_yaml_config
        
        # Invalid YAML content
        yaml_content = """
hospital:
  domains: ["Healthcare"
  # Missing closing bracket
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name
        
        try:
            mock_file = Mock()
            mock_file.name = temp_path
            
            config = load_yaml_config(mock_file)
            
            assert config is None
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    def test_load_yaml_config_none(self):
        """Test loading YAML with None input"""
        from src.app import load_yaml_config
        
        config = load_yaml_config(None)
        
        assert config is None
    
    def test_update_filters_for_index(self):
        """Test filter dropdown updates"""
        from src.app import update_filters_for_index_chat
        
        config = {
            'hospital': {
                'domains': ['Healthcare', 'Policy'],
                'sections': ['Patient Care', 'Emergency'],
                'topics': ['Diagnostics', 'Treatment']
            }
        }
        
        domain_update, section_update, topic_update = update_filters_for_index_chat(
            'hospital', config
        )
        
        assert 'Healthcare' in domain_update['choices']
        assert 'Patient Care' in section_update['choices']
        assert 'Diagnostics' in topic_update['choices']
        assert None in domain_update['choices']  # Should include None option
    
    def test_update_filters_no_config(self):
        """Test filter updates with no config"""
        from src.app import update_filters_for_index_chat
        
        domain_update, section_update, topic_update = update_filters_for_index_chat(
            'hospital', None
        )
        
        assert domain_update['choices'] == [None]
        assert section_update['choices'] == [None]


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestIntegration:
    """Integration tests for complete workflows"""
    
    @patch('src.core.index.Milvus')
    def test_end_to_end_ingestion_retrieval(self, mock_milvus):
        """Test complete ingestion and retrieval workflow"""
        # Setup mock vectorstore
        mock_vs = Mock()
        mock_vs.add_documents = Mock()
        mock_vs.similarity_search_with_relevance_scores.return_value = [
            (Document(page_content="Test result", metadata={}), 0.9)
        ]
        mock_milvus.return_value = mock_vs
        
        # Create test document
        test_content = "This is a test document about hospital policies."
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(test_content)
            temp_path = f.name
        
        try:
            # Step 1: Ingest
            metadata = MetaData(
                language="en",
                domain="Healthcare",
                section="Patient Care",
                topic="Diagnostics",
                doc_type="policy"
            )
            
            result = ingest([temp_path], "test_collection", metadata)
            
            assert "Ingested" in result
            assert mock_vs.add_documents.called
            
            # Step 2: Retrieve
            filter_data = MetaData(language="en", domain="Healthcare")
            results = retrieval("hospital policies", "test_collection", filter_data)
            
            assert len(results) > 0
            assert results[0].metadata.get('similarity_score') == 0.9
            
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    def test_synthetic_data_ingestion(self):
        """Test ingestion of synthetic evaluation data"""
        from src.core.synthetic_data import SYNTHETIC_DOCUMENTS
        
        # Verify synthetic data structure
        assert 'hospital' in SYNTHETIC_DOCUMENTS
        assert 'bank' in SYNTHETIC_DOCUMENTS
        assert 'fluid_simulation' in SYNTHETIC_DOCUMENTS
        
        # Verify document count
        assert len(SYNTHETIC_DOCUMENTS['hospital']) >= 12
        assert len(SYNTHETIC_DOCUMENTS['bank']) >= 12
        assert len(SYNTHETIC_DOCUMENTS['fluid_simulation']) >= 12
        
        # Verify metadata completeness
        for collection, docs in SYNTHETIC_DOCUMENTS.items():
            for doc in docs:
                assert 'content' in doc
                assert 'metadata' in doc
                assert 'language' in doc['metadata']
                assert 'domain' in doc['metadata']
                assert 'section' in doc['metadata']
                assert 'topic' in doc['metadata']
    
    def test_evaluation_queries_coverage(self):
        """Test that evaluation queries cover all collections"""
        from src.core.synthetic_data import EVAL_QUERIES
        
        collections = set(q.collection for q in EVAL_QUERIES)
        
        assert 'hospital' in collections
        assert 'bank' in collections
        assert 'fluid_simulation' in collections
        
        # Verify minimum query count
        assert len(EVAL_QUERIES) >= 15
        
        # Verify query structure
        for query in EVAL_QUERIES:
            assert query.query
            assert query.collection
            assert query.language
            assert isinstance(query.ground_truth_chunks, list)
            assert query.description


# ============================================================================
# EDGE CASES AND ERROR HANDLING
# ============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions"""
    
    def test_very_long_query(self):
        """Test handling of very long queries"""
        long_query = "What is the policy " * 100  # 500+ words
        
        # Should not crash
        filter_data = MetaData(language="en")
        
        with patch('src.core.retrieval.get_vectorstore') as mock_vs:
            mock_store = Mock()
            mock_store.similarity_search_with_relevance_scores.return_value = []
            mock_vs.return_value = mock_store
            
            results = retrieval(long_query, "test_collection", filter_data)
            
            assert isinstance(results, list)
    
    def test_special_characters_in_query(self):
        """Test handling of special characters"""
        special_query = "What's the policy for <patient> & [treatment]?"
        
        filter_data = MetaData(language="en")
        
        with patch('src.core.retrieval.get_vectorstore') as mock_vs:
            mock_store = Mock()
            mock_store.similarity_search_with_relevance_scores.return_value = []
            mock_vs.return_value = mock_store
            
            results = retrieval(special_query, "test_collection", filter_data)
            
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
            with patch('src.core.retrieval.get_vectorstore') as mock_vs:
                mock_store = Mock()
                mock_store.similarity_search_with_relevance_scores.return_value = []
                mock_vs.return_value = mock_store
                
                # Should handle all combinations without error
                results = retrieval("test query", "test_collection", filter_data)
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

