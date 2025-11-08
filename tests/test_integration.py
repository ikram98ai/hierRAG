
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from langchain_core.documents import Document
from src.core.index import MetaData, get_vectorstore
from src.core.ingest import load_documents, get_chunks, ingest_documents
from src.core.retrieval import retrieval

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
            
            docs = load_documents([temp_path])
            chunks = get_chunks(docs, metadata)
            vectorstore = get_vectorstore('test_collection', drop_old=True)
            result = ingest_documents(chunks, vectorstore)

            
            assert "Ingested" in result
            assert mock_vs.add_documents.called
            
            # Step 2: Retrieve
            filter_data = MetaData(language="en", domain="Healthcare")
            results = retrieval("hospital policies", filter_data, vectorstore)
            
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
