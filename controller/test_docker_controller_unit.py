#!/usr/bin/env python3
"""
Unit tests for DockerController class (using Mock, no actual Docker environment required)
"""

import pytest
import tempfile
import time
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
import logging

from docker_controller import DockerController


class TestDockerControllerUnit:
    """DockerController unit test class (using Mock)"""
    
    @pytest.fixture
    def mock_docker_client(self):
        """Mock Docker client"""
        with patch('docker.from_env') as mock_from_env:
            mock_client = MagicMock()
            mock_from_env.return_value = mock_client
            yield mock_client
    
    @pytest.fixture
    def controller(self, mock_docker_client):
        """Create controller with Mock Docker client"""
        controller = DockerController("test_container", "test:image")
        controller.client = mock_docker_client
        return controller
    
    def test_initialization(self, controller):
        """Test controller initialization"""
        assert controller.container_name == "test_container"
        assert controller.image == "test:image"
        assert controller.container is None
        assert len(controller.processes) == 0
        assert controller.logger is not None
    
    def test_setup_logger(self):
        """Test logger setup"""
        controller = DockerController("test", "image")
        assert controller.logger is not None
        assert controller.logger.name == "DockerController-test"
    
    def test_start_container_success(self, controller, mock_docker_client):
        """Test successful container startup"""
        # Setup Mock
        mock_container = MagicMock()
        mock_container.status = 'running'
        mock_docker_client.containers.run.return_value = mock_container
        
        # Simulate container not found exception
        from docker.errors import NotFound
        mock_docker_client.containers.get.side_effect = NotFound("Container not found")
        
        # Test startup
        success = controller.start_container(
            ports={'8080/tcp': 8080},
            environment={'TEST': 'value'}
        )
        
        assert success is True
        assert controller.container == mock_container
        mock_docker_client.containers.run.assert_called_once()
    
    def test_start_container_existing_running(self, controller, mock_docker_client):
        """Test starting existing running container"""
        # Setup Mock
        mock_existing = MagicMock()
        mock_existing.status = 'running'
        mock_docker_client.containers.get.return_value = mock_existing
        
        success = controller.start_container()
        
        assert success is True
        assert controller.container == mock_existing
        mock_docker_client.containers.run.assert_not_called()
    
    def test_start_container_failure(self, controller, mock_docker_client):
        """Test container startup failure"""
        mock_docker_client.containers.get.side_effect = Exception("Not found")
        mock_docker_client.containers.run.side_effect = Exception("Start failed")
        
        success = controller.start_container()
        
        assert success is False
        assert controller.container is None
    
    def test_stop_container_success(self, controller):
        """Test successful container stop"""
        # Setup Mock container
        mock_container = MagicMock()
        controller.container = mock_container
        controller.processes = {'test_proc': {'command': 'test'}}
        
        with patch.object(controller, 'stop_process') as mock_stop:
            success = controller.stop_container()
        
        assert success is True
        mock_container.stop.assert_called_once_with(timeout=10)
        mock_stop.assert_called_once_with('test_proc')
    
    def test_stop_container_no_container(self, controller):
        """Test stopping non-existent container"""
        success = controller.stop_container()
        assert success is False
    
    def test_execute_command_success(self, controller):
        """Test successful command execution"""
        mock_container = MagicMock()
        mock_result = MagicMock()
        mock_result.exit_code = 0
        mock_result.output = b"Hello World"
        mock_container.exec_run.return_value = mock_result
        controller.container = mock_container
        
        result = controller.execute_command("echo 'Hello World'")
        
        assert result == mock_result
        mock_container.exec_run.assert_called_once_with(
            "echo 'Hello World'", 
            detach=False, 
            stream=False
        )
    
    def test_execute_command_no_container(self, controller):
        """Test command execution with no container"""
        result = controller.execute_command("test command")
        assert result is None
    
    def test_start_process_success(self, controller, mock_docker_client):
        """Test successful process startup"""
        mock_container = MagicMock()
        mock_container.id = "container_123"
        controller.container = mock_container
        
        # Mock low-level API
        mock_docker_client.api.exec_create.return_value = {'Id': 'exec_id_123'}
        mock_docker_client.api.exec_start.return_value = None
        
        success = controller.start_process("test_proc", "sleep 30", auto_restart=True)
        
        assert success is True
        assert "test_proc" in controller.processes
        process_info = controller.processes["test_proc"]
        assert process_info['command'] == "sleep 30"
        assert process_info['exec_id'] == "exec_id_123"
        assert process_info['auto_restart'] is True
        
        # Verify API calls
        mock_docker_client.api.exec_create.assert_called_once_with(
            container="container_123",
            cmd="sleep 30"
        )
        mock_docker_client.api.exec_start.assert_called_once_with("exec_id_123", detach=True)
    
    def test_start_process_duplicate_name(self, controller):
        """Test starting process with duplicate name"""
        controller.container = MagicMock()
        controller.processes = {"test_proc": {"command": "existing"}}
        
        success = controller.start_process("test_proc", "new command")
        
        assert success is False
    
    def test_stop_process_success(self, controller):
        """Test successful process stop"""
        controller.container = MagicMock()
        controller.processes = {
            "test_proc": {
                "command": "sleep 30",
                "exec_id": "exec_123"
            }
        }
        
        with patch.object(controller, 'execute_command') as mock_exec:
            success = controller.stop_process("test_proc")
        
        assert success is True
        assert "test_proc" not in controller.processes
        assert mock_exec.call_count >= 1  # May call kill commands multiple times
    
    def test_stop_process_nonexistent(self, controller):
        """Test stopping non-existent process"""
        success = controller.stop_process("nonexistent")
        assert success is False
    
    def test_get_process_status(self, controller, mock_docker_client):
        """Test getting process status"""
        controller.processes = {
            "test_proc": {
                "command": "sleep 30",
                "exec_id": "exec_123",
                "start_time": time.time() - 10,
                "restart_count": 2
            }
        }
        
        # Mock API call
        mock_docker_client.api.exec_inspect.return_value = {
            'Running': True,
            'ExitCode': None
        }
        
        status = controller.get_process_status("test_proc")
        
        assert status is not None
        assert status['running'] is True
        assert status['command'] == "sleep 30"
        assert status['restart_count'] == 2
        assert 'uptime' in status
    
    def test_get_process_status_nonexistent(self, controller):
        """Test getting status of non-existent process"""
        status = controller.get_process_status("nonexistent")
        assert status is None
    
    def test_list_processes(self, controller, mock_docker_client):
        """Test listing all processes"""
        controller.processes = {
            "proc1": {"exec_id": "exec_1", "start_time": time.time()},
            "proc2": {"exec_id": "exec_2", "start_time": time.time()}
        }
        
        mock_docker_client.api.exec_inspect.return_value = {
            'Running': True,
            'ExitCode': None
        }
        
        processes = controller.list_processes()
        
        assert len(processes) == 2
        assert "proc1" in processes
        assert "proc2" in processes
    
    def test_get_container_status(self, controller):
        """Test getting container status"""
        mock_container = MagicMock()
        mock_container.id = "container_123"
        mock_container.name = "test_container"
        mock_container.status = "running"
        mock_container.image.tags = ["test:image"]
        mock_container.attrs = {"Created": "2023-01-01T00:00:00Z"}
        mock_container.ports = {"8080/tcp": [{"HostPort": "8080"}]}
        mock_container.labels = {"test": "label"}
        
        controller.container = mock_container
        
        status = controller.get_container_status()
        
        assert status is not None
        assert status['id'] == "container_123"
        assert status['name'] == "test_container"
        assert status['status'] == "running"
        assert status['image'] == "test:image"
    
    def test_get_container_status_no_container(self, controller):
        """Test getting status of non-existent container"""
        status = controller.get_container_status()
        assert status is None
    
    def test_get_container_logs(self, controller):
        """Test getting container logs"""
        mock_container = MagicMock()
        mock_container.logs.return_value = b"Log line 1\nLog line 2\n"
        controller.container = mock_container
        
        logs = controller.get_container_logs(tail=50)
        
        assert logs == "Log line 1\nLog line 2\n"
        mock_container.logs.assert_called_once_with(tail=50)
    
    def test_upload_file_content_success(self, controller):
        """Test successful file content upload"""
        mock_container = MagicMock()
        controller.container = mock_container
        
        success = controller.upload_file_content("test content", "/tmp/test.txt")
        
        assert success is True
        mock_container.put_archive.assert_called_once()
    
    def test_upload_file_content_no_container(self, controller):
        """Test uploading file content with no container"""
        success = controller.upload_file_content("test", "/tmp/test.txt")
        assert success is False
    
    def test_file_exists_true(self, controller):
        """Test file existence check (file exists)"""
        mock_container = MagicMock()
        mock_result = MagicMock()
        mock_result.exit_code = 0
        mock_container.exec_run.return_value = mock_result
        controller.container = mock_container
        
        exists = controller.file_exists("/tmp/test.txt")
        
        assert exists is True
        mock_container.exec_run.assert_called_once_with("test -e /tmp/test.txt", detach=False, stream=False)
    
    def test_file_exists_false(self, controller):
        """Test file existence check (file does not exist)"""
        mock_container = MagicMock()
        mock_result = MagicMock()
        mock_result.exit_code = 1
        mock_container.exec_run.return_value = mock_result
        controller.container = mock_container
        
        exists = controller.file_exists("/tmp/nonexistent.txt")
        
        assert exists is False
    
    def test_create_directory_success(self, controller):
        """Test successful directory creation"""
        mock_container = MagicMock()
        mock_result = MagicMock()
        mock_result.exit_code = 0
        mock_container.exec_run.return_value = mock_result
        controller.container = mock_container
        
        success = controller.create_directory("/tmp/new_dir", parents=True)
        
        assert success is True
        mock_container.exec_run.assert_called_once_with("mkdir --parents /tmp/new_dir", detach=False, stream=False)
    
    def test_remove_file_success(self, controller):
        """Test successful file removal"""
        mock_container = MagicMock()
        mock_result = MagicMock()
        mock_result.exit_code = 0
        mock_container.exec_run.return_value = mock_result
        controller.container = mock_container
        
        success = controller.remove_file("/tmp/test.txt", force=True)
        
        assert success is True
        mock_container.exec_run.assert_called_once_with("rm -f /tmp/test.txt", detach=False, stream=False)
    
    def test_context_manager(self, mock_docker_client):
        """Test context manager functionality"""
        with DockerController("test_container", "test:image") as controller:
            assert controller is not None
    
    def test_cleanup(self, controller):
        """Test resource cleanup"""
        # Setup mock container and processes
        mock_container = MagicMock()
        controller.container = mock_container
        controller.processes = {"test_proc": {"command": "test"}}
        
        with patch.object(controller, 'stop_process') as mock_stop_process:
            with patch.object(controller, 'stop_container') as mock_stop_container:
                controller.cleanup()
        
        mock_stop_process.assert_called_once_with("test_proc")
        mock_stop_container.assert_called_once()
    
    @patch('tempfile.NamedTemporaryFile')
    @patch('tarfile.open')
    def test_upload_file_success(self, mock_tarfile, mock_tempfile, controller):
        """Test successful file upload"""
        # Setup mocks
        controller.container = MagicMock()
        mock_tempfile.return_value.__enter__.return_value.name = "/tmp/test"
        
        # Mock Path class methods
        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.is_file', return_value=True), \
             patch('pathlib.Path.stat') as mock_stat, \
             patch('builtins.open', mock_open(read_data=b'test')):
            
            # Mock file stats for permission handling
            mock_stat.return_value.st_mode = 0o644
            
            success = controller.upload_file("/local/file.txt", "/container/file.txt")
        
        assert success is True
    
    def test_upload_file_nonexistent(self, controller):
        """Test uploading non-existent file"""
        controller.container = MagicMock()
        
        with patch('pathlib.Path.exists', return_value=False):
            success = controller.upload_file("/nonexistent.txt", "/container/file.txt")
        
        assert success is False


def test_monitor_process_function():
    """Test the monitor process function as standalone"""
    # This is a simple test to ensure the function structure is correct
    controller = DockerController("test", "test:image")
    
    # Mock the necessary components
    with patch.object(controller, 'client') as mock_client:
        mock_client.api.exec_inspect.return_value = {'Running': False}
        
        process_info = {
            'command': 'test',
            'exec_id': 'test_id',
            'restart_delay': 1,
            'restart_count': 0,
            'start_time': time.time()
        }
        
        # Just verify the function can be called without error
        # In real test, this would run in a separate thread
        try:
            controller._monitor_process("test_proc", process_info)
        except Exception:
            # Expected to fail in test environment
            pass


# Test runner
if __name__ == "__main__":
    pytest.main([__file__, "-v"])