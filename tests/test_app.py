
import pytest
from unittest.mock import Mock, patch
from langchain_core.documents import Document
import tempfile
from pathlib import Path

class TestAPIBehaviors:
    """Tests for API behaviors and error handling"""
    
    def test_process_files_empty_input(self):
        """Test process_files with no files"""
        from src.app import ingest_files
        
        result = ingest_files([], "hospital", "en", None, None, None, None)
        
        assert "Please upload at least one file" in result
    
    def test_process_files_no_index(self):
        """Test process_files without index selection"""
        from src.app import ingest_files
        
        result = ingest_files(["file.pdf"], None, "en", None, None, None, None)
        
        assert "Please select an index" in result
    
    @patch('src.app.load_documents')
    @patch('src.app.get_chunks')
    @patch('src.app.ingest_documents')
    def test_process_files_success(self, mock_ingest, mock_get_chunks, mock_load_documents):
        """Test successful file processing"""
        from src.app import ingest_files
        mock_load_documents.return_value = [Document(page_content="Test content", metadata={})]
        mock_get_chunks.return_value = [Document(page_content="chunk", metadata={})]
        mock_ingest.return_value = "Successfully ingested 5 documents"
        
        result = ingest_files(
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
        from src.app import _load_yaml_config
        
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
            
            config = _load_yaml_config(mock_file)
            
            assert config is not None
            assert 'hospital' in config
            assert 'Healthcare' in config['hospital']['domains']
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    def test_load_yaml_config_invalid(self):
        """Test loading invalid YAML configuration"""
        from src.app import _load_yaml_config
        
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
            
            config = _load_yaml_config(mock_file)
            
            assert config is None
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    def test_load_yaml_config_none(self):
        """Test loading YAML with None input"""
        from src.app import _load_yaml_config
        
        config = _load_yaml_config(None)
        
        assert config is None
    
    def test_update_filters_for_index(self):
        """Test filter dropdown updates"""
        from src.app import _update_filters_for_index_chat
        
        config = {
            'hospital': {
                'domains': ['Healthcare', 'Policy'],
                'sections': ['Patient Care', 'Emergency'],
                'topics': ['Diagnostics', 'Treatment']
            }
        }
        
        domain_update, section_update, topic_update = _update_filters_for_index_chat(
            'hospital', config
        )
        
        assert 'Healthcare' in domain_update['choices']
        assert 'Patient Care' in section_update['choices']
        assert 'Diagnostics' in topic_update['choices']
        assert None in domain_update['choices']  # Should include None option
    
    def test_update_filters_no_config(self):
        """Test filter updates with no config"""
        from src.app import _update_filters_for_index_chat
        
        domain_update, section_update, topic_update = _update_filters_for_index_chat(
            'hospital', None
        )
        
        assert domain_update['choices'] == [None]
        assert section_update['choices'] == [None]
