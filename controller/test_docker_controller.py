#!/usr/bin/env python3
"""
Integration tests for DockerController class (requires real Docker environment)
"""

import pytest
import tempfile
import time
import docker
from pathlib import Path

from docker_controller import DockerController


class TestDockerController:
    """DockerController integration test class (requires Docker)"""
    
    @pytest.fixture(scope="function")
    def controller(self):
        """Create controller for testing"""
        container_name = f"test_container_{int(time.time())}"
        controller = DockerController(container_name, "alpine:latest")
        yield controller
        # Cleanup
        try:
            controller.cleanup()
        except Exception:
            pass
    
    @pytest.fixture(scope="function")
    def temp_dir(self):
        """Create temporary directory for testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    def test_docker_connection(self):
        """Test Docker connection"""
        client = docker.from_env()
        info = client.info()
        assert info is not None
    
    def test_controller_initialization(self):
        """Test controller initialization"""
        controller = DockerController("test", "alpine:latest")
        assert controller.container_name == "test"
        assert controller.image == "alpine:latest"
        assert controller.container is None
        assert len(controller.processes) == 0
    
    def test_container_lifecycle(self, controller):
        """Test container lifecycle"""
        # Start container
        success = controller.start_container(command="tail -f /dev/null")
        assert success is True
        assert controller.container is not None
        
        # Check status
        status = controller.get_container_status()
        assert status is not None
        assert status['status'] == 'running'
        
        # Stop container
        success = controller.stop_container()
        assert success is True
    
    def test_execute_command(self, controller):
        """Test command execution"""
        controller.start_container(command="tail -f /dev/null")
        
        # Execute simple command
        result = controller.execute_command("echo 'Hello World'")
        assert result is not None
        assert result.exit_code == 0
        assert b'Hello World' in result.output
    
    def test_process_management(self, controller):
        """Test process management"""
        controller.start_container(command="tail -f /dev/null")
        
        # Start process
        success = controller.start_process("test_process", "sleep 30")
        assert success is True
        
        # Check process status
        status = controller.get_process_status("test_process")
        assert status is not None
        assert status['running'] is True
        
        # List processes
        processes = controller.list_processes()
        assert "test_process" in processes
        
        # Stop process
        success = controller.stop_process("test_process")
        assert success is True
        assert "test_process" not in controller.processes
    
    def test_file_upload_and_download(self, controller, temp_dir):
        """Test file upload and download"""
        controller.start_container(command="tail -f /dev/null")
        
        # Create test file
        test_file = temp_dir / "test.txt"
        test_content = "Hello, Docker!"
        test_file.write_text(test_content)
        
        # Upload file
        success = controller.upload_file(test_file, "/tmp/uploaded.txt")
        assert success is True
        
        # Verify file exists
        assert controller.file_exists("/tmp/uploaded.txt") is True
        
        # Download file
        downloaded_file = temp_dir / "downloaded.txt"
        success = controller.download_file("/tmp/uploaded.txt", downloaded_file)
        assert success is True
        
        # Verify content
        assert downloaded_file.read_text() == test_content
    
    def test_upload_file_content(self, controller):
        """Test uploading file content"""
        controller.start_container(command="tail -f /dev/null")
        
        # Upload content
        content = "Test content"
        success = controller.upload_file_content(content, "/tmp/content.txt")
        assert success is True
        
        # Verify content
        downloaded_content = controller.download_file_content("/tmp/content.txt")
        assert downloaded_content is not None
        assert downloaded_content.decode('utf-8') == content
    
    def test_file_management(self, controller):
        """Test file management operations"""
        controller.start_container(command="tail -f /dev/null")
        
        # Create directory
        success = controller.create_directory("/tmp/test_dir")
        assert success is True
        
        # Verify directory exists
        assert controller.file_exists("/tmp/test_dir") is True
        
        # Create file in directory
        controller.upload_file_content("Test file", "/tmp/test_dir/test.txt")
        
        # List files
        files = controller.list_files("/tmp/test_dir")
        assert files is not None
        assert len(files) > 0
        
        # Find our file
        test_file_found = False
        for file_info in files:
            if file_info['name'] == 'test.txt':
                test_file_found = True
                assert file_info['is_file'] is True
                break
        assert test_file_found is True
        
        # Remove file
        success = controller.remove_file("/tmp/test_dir/test.txt")
        assert success is True
        assert controller.file_exists("/tmp/test_dir/test.txt") is False
        
        # Remove directory
        success = controller.remove_file("/tmp/test_dir", recursive=True)
        assert success is True
        assert controller.file_exists("/tmp/test_dir") is False
    
    def test_context_manager(self):
        """Test context manager functionality"""
        container_name = f"test_context_{int(time.time())}"
        
        with DockerController(container_name, "alpine:latest") as controller:
            success = controller.start_container(command="tail -f /dev/null")
            assert success is True
        
        # Context exit should clean up resources
        # Note: Due to async cleanup, we mainly test that no exceptions are thrown
    
    def test_error_handling_no_container(self, controller):
        """Test error handling when no container is started"""
        # Command execution should fail
        result = controller.execute_command("echo test")
        assert result is None
        
        # File upload should fail
        success = controller.upload_file_content("test", "/tmp/test.txt")
        assert success is False
        
        # Process start should fail
        success = controller.start_process("test", "echo test")
        assert success is False


# Test runner
if __name__ == "__main__":
    pytest.main([__file__, "-v"])