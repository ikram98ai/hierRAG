
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from src.core.index import MetaData
from src.core.ingest import load_documents, get_chunks, ingest_documents
from src.core.retrieval import retrieval

@pytest.fixture
def sample_text():
    """Sample text for chunking tests"""
    return """
    Patient Care Guidelines for Radiology Department
    
    All diagnostic imaging requests must be submitted through the electronic 
    health record system. The attending physician must approve all requests 
    before scheduling can occur.
    
    MRI Scanning Protocols:
    - Patient must fast for 4 hours before contrast studies
    - Remove all metal objects before entering scanner room
    - Scan time ranges from 30-60 minutes depending on body area
    
    CT Scan Procedures:
    - Obtain informed consent for contrast administration
    - Check kidney function (eGFR) before contrast
    - Results typically available within 24 hours
    
    Emergency Imaging:
    - STAT orders processed immediately
    - Radiologist on-call 24/7 for critical findings
    - Direct communication with ordering physician required
    """


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

# ============================================================================
# CHUNKING TESTS
# ============================================================================

class TestChunking:
    """Tests for document chunking functionality"""
    
    def test_chunking_produces_multiple_chunks(self, sample_text):
        """Test that long text is split into multiple chunks"""
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=200,
            chunk_overlap=50,
            add_start_index=True
        )
        
        chunks = splitter.split_text(sample_text)
        
        assert len(chunks) > 1, "Long text should produce multiple chunks"
        assert all(len(chunk) <= 250 for chunk in chunks), "Chunks should respect size limit"
    
    def test_chunking_preserves_overlap(self, sample_text):
        """Test that chunk overlap works correctly"""
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=200,
            chunk_overlap=50,
            add_start_index=True
        )
        
        chunks = splitter.split_text(sample_text)
        
        # Check that consecutive chunks have some overlap
        if len(chunks) > 1:
            # Some words from end of first chunk should appear in second chunk
            first_chunk_words = set(chunks[0].split()[-10:])
            second_chunk_words = set(chunks[1].split()[:20])
            overlap = first_chunk_words & second_chunk_words
            
            assert len(overlap) > 0, "Chunks should have overlapping content"
    
    def test_chunking_tracks_start_index(self, sample_text):
        """Test that start_index metadata is tracked"""
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=200,
            chunk_overlap=50,
            add_start_index=True
        )
        
        docs = splitter.create_documents([sample_text])
        
        assert all('start_index' in doc.metadata for doc in docs), \
            "All chunks should have start_index metadata"
        
        # Start indices should be increasing
        indices = [doc.metadata['start_index'] for doc in docs]
        assert indices == sorted(indices), "Start indices should be in order"
    
    def test_empty_document_handling(self):
        """Test handling of empty documents"""
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=200,
            chunk_overlap=50
        )
        
        chunks = splitter.split_text("")
        
        assert len(chunks) == 0, "Empty text should produce no chunks"


# ============================================================================
# METADATA & HIERARCHY TESTS
# ============================================================================

class TestMetadataAndHierarchy:
    """Tests for metadata tagging and hierarchical organization"""
    
    def test_metadata_model_validation(self):
        """Test that MetaData model validates correctly"""
        # Valid metadata
        valid_meta = MetaData(
            language="en",
            domain="Healthcare",
            section="Patient Care",
            topic="Diagnostics",
            doc_type="policy"
        )
        
        assert valid_meta.language == "en"
        assert valid_meta.domain == "Healthcare"
        assert valid_meta.doc_type == "policy"
    
    def test_metadata_optional_fields(self):
        """Test that optional metadata fields work"""
        # Minimal metadata (only language required)
        minimal_meta = MetaData(language="en")
        
        assert minimal_meta.language == "en"
        assert minimal_meta.domain is None
        assert minimal_meta.section is None
        assert minimal_meta.topic is None
        assert minimal_meta.doc_type is None
    
    def test_metadata_language_validation(self):
        """Test that only valid languages are accepted"""
        # Valid languages
        MetaData(language="en")
        MetaData(language="ja")
        
        # Invalid language should fail
        with pytest.raises(Exception):  # Pydantic ValidationError
            MetaData(language="invalid_lang")
    
    def test_metadata_doc_type_validation(self):
        """Test that only valid doc types are accepted"""
        # Valid doc types
        MetaData(language="en", doc_type="policy")
        MetaData(language="en", doc_type="manual")
        MetaData(language="en", doc_type="faq")
        MetaData(language="en", doc_type=None)
        
        # Invalid doc type should fail
        with pytest.raises(Exception):  # Pydantic ValidationError
            MetaData(language="en", doc_type="invalid_type")
    
    def test_hierarchy_assignment_in_ingestion(self, sample_metadata):
        """Test that metadata is correctly assigned during ingestion"""
        # Create a temporary test document
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Test document content for metadata assignment.")
            temp_path = f.name
        
        try:
            # Mock the vectorstore to avoid actual DB operations
            with patch('src.core.index.get_vectorstore') as mock_vs:
                mock_vs.return_value.add_documents = Mock()
                
                # Run ingestion
                docs = load_documents([temp_path])
                chunks = get_chunks(docs, sample_metadata)
                vectorstore = mock_vs.return_value
                ingest_documents(chunks, vectorstore)
                
                # Verify add_documents was called
                assert mock_vs.return_value.add_documents.called, "add_documents should be called during ingestion"
                
                # Get the documents that were added
                call_args = mock_vs.return_value.add_documents.call_args
                added_docs = call_args[0][0]  # First positional argument
                
                # Check that metadata was applied
                for doc in added_docs:
                    assert doc.metadata['language'] == "en"
                    assert doc.metadata['domain'] == "Healthcare"
                    assert doc.metadata['section'] == "Patient Care"
                    assert doc.metadata['topic'] == "Diagnostics"
                    assert doc.metadata['doc_type'] == "policy"
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    def test_metadata_serialization(self, sample_metadata):
        """Test that metadata can be serialized/deserialized"""
        # Convert to dict
        meta_dict = sample_metadata.model_dump()
        
        assert meta_dict['language'] == "en"
        assert meta_dict['domain'] == "Healthcare"
        
        # Recreate from dict
        reconstructed = MetaData(**meta_dict)
        
        assert reconstructed.language == sample_metadata.language
        assert reconstructed.domain == sample_metadata.domain


# ============================================================================
# METADATA FILTERING TESTS
# ============================================================================

class TestMetadataFiltering:
    """Tests for metadata-based filtering in retrieval"""
    
    def test_filter_construction_base_rag(self):
        """Test filter construction for base RAG (language only)"""
        filter_data = MetaData(language="en")
        
        filters = [f'language == "{filter_data.language}"']
        expr = " and ".join(filters)
        
        assert expr == 'language == "en"'
    
    def test_filter_construction_hierarchical_rag(self):
        """Test filter construction for hierarchical RAG"""
        filter_data = MetaData(
            language="en",
            domain="Healthcare",
            section="Patient Care",
            topic="Diagnostics",
            doc_type="policy"
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
        
        expr = " and ".join(filters)
        
        assert 'language == "en"' in expr
        assert 'domain == "Healthcare"' in expr
        assert 'section == "Patient Care"' in expr
        assert 'topic == "Diagnostics"' in expr
        assert 'doc_type == "policy"' in expr
    
    def test_filter_construction_partial_hierarchy(self):
        """Test filter with only some hierarchical fields"""
        filter_data = MetaData(
            language="en",
            domain="Healthcare",
            section=None,
            topic=None,
            doc_type=None
        )
        
        filters = [f'language == "{filter_data.language}"']
        if filter_data.domain:
            filters.append(f'domain == "{filter_data.domain}"')
        if filter_data.section:
            filters.append(f'section == "{filter_data.section}"')
        
        expr = " and ".join(filters)
        
        assert 'language == "en"' in expr
        assert 'domain == "Healthcare"' in expr
        assert 'section' not in expr
    
    @patch('src.core.index.get_vectorstore')
    def test_retrieval_applies_filters(self, mock_vs):
        """Test that retrieval actually applies filters"""
        # Setup mock
        mock_store = Mock()
        mock_store.similarity_search_with_relevance_scores.return_value = []
        mock_vs.return_value = mock_store
        
        # Run retrieval with filters
        filter_data = MetaData(
            language="en",
            domain="Healthcare"
        )
        vectorstore = mock_vs.return_value
        retrieval("test query", filter_data, vectorstore)
        
        # Check that similarity_search was called with expr
        call_args = mock_store.similarity_search_with_relevance_scores.call_args
        
        assert call_args is not None
        assert 'expr' in call_args[1]
        assert 'language == "en"' in call_args[1]['expr']
        assert 'domain == "Healthcare"' in call_args[1]['expr']
    
    @patch('src.core.index.get_vectorstore')
    def test_retrieval_handles_no_results(self, mock_vs):
        """Test that retrieval handles empty results gracefully"""
        # Setup mock to return empty results
        mock_store = Mock()
        mock_store.similarity_search_with_relevance_scores.return_value = []
        mock_vs.return_value = mock_store
        
        filter_data = MetaData(language="en")
        vectorstore = mock_vs.return_value
        results = retrieval("test query", filter_data, vectorstore)
        
        assert results == []