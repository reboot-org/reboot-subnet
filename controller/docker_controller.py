import docker
import subprocess
import threading
import time
import logging
import os
import tarfile
import tempfile
from io import BytesIO
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
from docker.models.containers import Container


class DockerController:
    """
    Docker Container Controller Class
    Used to control Docker container startup, shutdown, and manage process lifecycle within containers
    """
    
    def __init__(self, container_name: str, image: str, logger: Optional[logging.Logger] = None):
        """
        Initialize Docker Controller
        
        Args:
            container_name: Container name
            image: Docker image name
            logger: Logger instance, optional
        """
        self.container_name = container_name
        self.image = image
        self.client = docker.from_env()
        self.container: Optional[Container] = None
        self.processes: Dict[str, Dict[str, Any]] = {}  # Process management dictionary
        self.logger = logger or self._setup_logger()
        
    def _setup_logger(self) -> logging.Logger:
        """Setup logger"""
        logger = logging.getLogger(f"DockerController-{self.container_name}")
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            
        return logger
    
    def start_container(self, 
                       ports: Optional[Dict[str, int]] = None,
                       volumes: Optional[Dict[str, Dict[str, str]]] = None,
                       environment: Optional[Dict[str, str]] = None,
                       command: Optional[str] = None,
                       detach: bool = True,
                       clean_existing: bool = False,
                       **kwargs) -> bool:
        """
        Start Docker container
        
        Args:
            ports: Port mapping, format: {'container_port/protocol': host_port}
            volumes: Volume mounting, format: {'host_path': {'bind': 'container_path', 'mode': 'rw'}}
            environment: Environment variables
            command: Startup command
            detach: Whether to run in background
            clean_existing: Whether to remove existing container with same name before starting
            **kwargs: Other docker.containers.run parameters
            
        Returns:
            bool: Whether startup was successful
        """
        try:    
            # Try to remove existing container with same name
            try:
                existing_container = self.client.containers.get(self.container_name)
                if clean_existing or existing_container.status != 'running':
                    self.remove_container(force=True)
                    self.logger.info(f"Removed existing container {self.container_name}")
                else:
                    self.container = existing_container
                    self.logger.info(f"Using existing running container {self.container_name}")
                    return True
            except docker.errors.NotFound:
                pass
            
            # Start new container
            self.logger.info(f"Starting container {self.container_name}, image: {self.image}")
            
            self.container = self.client.containers.run(
                self.image,
                name=self.container_name,
                ports=ports,
                volumes=volumes,
                environment=environment,
                command=command,
                detach=detach,
                **kwargs
            )
            
            self.logger.info(f"Container {self.container_name} started successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start container: {e}")
            return False
    
    def stop_container(self, timeout: int = 10) -> bool:
        """
        Stop container
        
        Args:
            timeout: Stop timeout in seconds
            
        Returns:
            bool: Whether stop was successful
        """
        try:
            self.processes.clear()
            if not self.container:
                self.logger.warning("Container not initialized")
                return False
                
            self.logger.info(f"Stopping container {self.container_name}")
            self.container.stop(timeout=timeout)
            
            # Stop all managed processes
            for process_name in list(self.processes.keys()):
                self.stop_process(process_name)
                
            
            self.logger.info(f"Container {self.container_name} stopped")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to stop container: {e}")
            return False
    
    def remove_container(self, force: bool = False) -> bool:
        """
        Remove container
        
        Args:
            force: Whether to force removal
            
        Returns:
            bool: Whether removal was successful
        """
        try:
            self.logger.info(f"Removing container {self.container_name}")
            self.processes.clear()
            # Try to get and remove container by name
            try:
                container_to_remove = self.client.containers.get(self.container_name)
                container_to_remove.remove(force=force)
                self.logger.info(f"Container {self.container_name} removed")
            except docker.errors.NotFound:
                self.logger.warning(f"Container {self.container_name} not found")
            except Exception as e:
                self.logger.error(f"Failed to remove container {self.container_name}: {e}")
                return False
            
            # Clear local references
            self.container = None
            self.processes.clear()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to remove container: {e}")
            return False
    
    def execute_command(self, 
                       command: str, 
                       detach: bool = False,
                       stream: bool = False,
                       **kwargs) -> Optional[Any]:
        """
        Execute command in container
        
        Args:
            command: Command to execute
            detach: Whether to run in background
            stream: Whether to stream output
            **kwargs: Other exec_run parameters
            
        Returns:
            Execution result or None
        """
        try:
            if not self.container:
                self.logger.error("Container not started")
                return None
                
            self.logger.info(f"Executing command in container: {command}")
            result = self.container.exec_run(
                command, 
                detach=detach, 
                stream=stream,
                **kwargs
            )
            
            if not detach:
                self.logger.info(f"Command execution completed, exit code: {result.exit_code}")
                
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to execute command: {e}")
            return None
    
    def start_process(self, 
                     process_name: str, 
                     command: str,
                     auto_restart: bool = False,
                     restart_delay: int = 5,
                     **kwargs) -> bool:
        """
        Start a managed process in container
        
        Args:
            process_name: Process name
            command: Command to execute
            auto_restart: Whether to auto restart on failure
            restart_delay: Delay between restarts in seconds
            **kwargs: Other exec parameters
            
        Returns:
            bool: Whether startup was successful
        """
        try:
            if not self.container:
                self.logger.error("Container not started")
                return False
            
            if process_name in self.processes:
                self.logger.warning(f"Process {process_name} already exists")
                return False
            
            self.logger.info(f"Starting process {process_name}: {command}")
            
            # Use low-level API to create and start exec, to get exec ID
            exec_config = self.client.api.exec_create(
                container=self.container.id,
                cmd=command,
                **kwargs
            )
            exec_id = exec_config['Id']
            
            # Start exec
            self.client.api.exec_start(exec_id, detach=True)
            
            # Record process information
            process_info = {
                'command': command,
                'exec_id': exec_id,
                'auto_restart': auto_restart,
                'restart_delay': restart_delay,
                'start_time': time.time(),
                'restart_count': 0,
                'monitor_thread': None
            }
            
            # Start monitoring thread
            if auto_restart:
                monitor_thread = threading.Thread(
                    target=self._monitor_process,
                    args=(process_name, process_info),
                    daemon=True
                )
                monitor_thread.start()
                process_info['monitor_thread'] = monitor_thread
            
            self.processes[process_name] = process_info
            self.logger.info(f"Process {process_name} started successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start process: {e}")
            return False
    
    def _monitor_process(self, process_name: str, process_info: Dict[str, Any]):
        """
        Monitor process status and implement auto restart
        
        Args:
            process_name: Process name
            process_info: Process information
        """
        while process_name in self.processes:
            try:
                # Check process status
                exec_inspect = self.client.api.exec_inspect(process_info['exec_id'])
                
                if not exec_inspect['Running']:
                    self.logger.warning(f"Process {process_name} stopped, preparing to restart")
                    
                    # Wait for restart delay
                    time.sleep(process_info['restart_delay'])
                    
                    # Restart process
                    exec_config = self.client.api.exec_create(
                        container=self.container.id,
                        cmd=process_info['command']
                    )
                    new_exec_id = exec_config['Id']
                    self.client.api.exec_start(new_exec_id, detach=True)
                    
                    process_info['exec_id'] = new_exec_id
                    process_info['restart_count'] += 1
                    process_info['start_time'] = time.time()
                    
                    self.logger.info(f"Process {process_name} restarted, restart count: {process_info['restart_count']}")
                
                time.sleep(5)  # Check interval
                
            except Exception as e:
                self.logger.error(f"Error monitoring process {process_name}: {e}")
                break
    
    def stop_process(self, process_name: str) -> bool:
        """
        Stop process
        
        Args:
            process_name: Process name
            
        Returns:
            bool: Whether stop was successful
        """
        try:
            if process_name not in self.processes:
                self.logger.warning(f"Process {process_name} does not exist")
                return False
            
            process_info = self.processes[process_name]
            self.logger.info(f"Stopping process {process_name}")
            
            # Try to gracefully stop process
            try:
                # Send TERM signal
                self.execute_command(f"kill -TERM $(ps aux | grep '{process_info['command']}' | grep -v grep | awk '{{print $2}}')")
                time.sleep(2)
                
                # If still running, send KILL signal
                self.execute_command(f"kill -KILL $(ps aux | grep '{process_info['command']}' | grep -v grep | awk '{{print $2}}')")
            except Exception:
                pass
            
            # Remove from management dictionary
            del self.processes[process_name]
            self.logger.info(f"Process {process_name} stopped")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to stop process: {e}")
            return False
    
    def get_process_status(self, process_name: str) -> Optional[Dict[str, Any]]:
        """
        Get process status
        
        Args:
            process_name: Process name
            
        Returns:
            Process status information or None
        """
        if process_name not in self.processes:
            return None
        
        process_info = self.processes[process_name].copy()
        
        try:
            # Check if process is still running
            exec_inspect = self.client.api.exec_inspect(process_info['exec_id'])
            process_info['running'] = exec_inspect['Running']
            process_info['exit_code'] = exec_inspect.get('ExitCode')
            
            # Calculate uptime
            process_info['uptime'] = time.time() - process_info['start_time']
            
        except Exception as e:
            self.logger.error(f"Failed to get process status: {e}")
            process_info['running'] = False
            process_info['error'] = str(e)
        
        return process_info
    
    def list_processes(self) -> Dict[str, Dict[str, Any]]:
        """
        List all managed processes
        
        Returns:
            Process status dictionary
        """
        result = {}
        for process_name in self.processes.keys():
            result[process_name] = self.get_process_status(process_name)
        return result
    
    def get_container_status(self) -> Optional[Dict[str, Any]]:
        """
        Get container status
        
        Returns:
            Container status information or None
        """
        try:
            if not self.container:
                return None
            
            self.container.reload()
            return {
                'id': self.container.id,
                'name': self.container.name,
                'status': self.container.status,
                'image': self.container.image.tags[0] if self.container.image.tags else 'unknown',
                'created': self.container.attrs['Created'],
                'ports': self.container.ports,
                'labels': self.container.labels
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get container status: {e}")
            return None
    
    def get_container_logs(self, tail: int = 100) -> str:
        """
        Get container logs
        
        Args:
            tail: Get last N lines of logs
            
        Returns:
            Log content
        """
        try:
            if not self.container:
                return "Container not started"
            
            logs = self.container.logs(tail=tail).decode('utf-8')
            return logs
            
        except Exception as e:
            self.logger.error(f"Failed to get container logs: {e}")
            return f"Failed to get logs: {e}"
    
    def upload_file(self, 
                   local_path: Union[str, Path], 
                   container_path: str,
                   preserve_permissions: bool = True) -> bool:
        """
        Upload file or directory to container
        
        Args:
            local_path: Local file or directory path
            container_path: Target path in container
            preserve_permissions: Whether to preserve file permissions
            
        Returns:
            bool: Whether upload was successful
        """
        try:
            if not self.container:
                self.logger.error("Container not started")
                return False
            
            local_path = Path(local_path)
            if not local_path.exists():
                self.logger.error(f"Local path does not exist: {local_path}")
                return False
            
            self.logger.info(f"Uploading {local_path} to container path {container_path}")
            
            # Create tar archive
            with tempfile.NamedTemporaryFile() as temp_file:
                with tarfile.open(temp_file.name, 'w') as tar:
                    if local_path.is_file():
                        # Single file
                        tar.add(local_path, arcname=Path(container_path).name)
                    else:
                        # Directory
                        for item in local_path.rglob('*'):
                            relative_path = item.relative_to(local_path)
                            tar.add(item, arcname=relative_path)
                
                # Read tar file content
                with open(temp_file.name, 'rb') as f:
                    tar_data = f.read()
            
            # Upload to container
            if local_path.is_file():
                # For files, upload to parent directory
                target_dir = str(Path(container_path).parent)
            else:
                # For directories, upload to target path
                target_dir = container_path
                
            self.container.put_archive(target_dir, tar_data)
            
            # Set permissions if needed
            if preserve_permissions and local_path.is_file():
                mode = oct(local_path.stat().st_mode)[-3:]
                self.execute_command(f"chmod {mode} {container_path}")
            
            self.logger.info(f"File upload completed: {local_path} -> {container_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to upload file: {e}")
            return False
    
    def upload_file_content(self, 
                           content: Union[str, bytes], 
                           container_path: str,
                           mode: int = 0o644) -> bool:
        """
        Upload content as file to container
        
        Args:
            content: File content (string or bytes)
            container_path: Target file path in container
            mode: File permissions (octal)
            
        Returns:
            bool: Whether upload was successful
        """
        try:
            if not self.container:
                self.logger.error("Container not started")
                return False
            
            # Convert content to bytes
            if isinstance(content, str):
                content = content.encode('utf-8')
            
            self.logger.info(f"Uploading content to container file {container_path}")
            
            # Create tar archive
            tar_stream = BytesIO()
            with tarfile.open(fileobj=tar_stream, mode='w') as tar:
                # Create file info
                file_info = tarfile.TarInfo(name=Path(container_path).name)
                file_info.size = len(content)
                file_info.mode = mode
                
                # Add file to tar
                tar.addfile(file_info, BytesIO(content))
            
            # Get parent directory
            parent_dir = str(Path(container_path).parent)
            
            # Upload to container
            tar_stream.seek(0)
            self.container.put_archive(parent_dir, tar_stream.getvalue())
            
            self.logger.info(f"Content upload completed: {container_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to upload content: {e}")
            return False
    
    def download_file(self, 
                     container_path: str, 
                     local_path: Union[str, Path],
                     extract_tar: bool = True) -> bool:
        """
        Download file or directory from container
        
        Args:
            container_path: Source path in container
            local_path: Target local path
            extract_tar: Whether to extract tar archive
            
        Returns:
            bool: Whether download was successful
        """
        try:
            if not self.container:
                self.logger.error("Container not started")
                return False
            
            local_path = Path(local_path)
            self.logger.info(f"Downloading {container_path} from container to {local_path}")
            
            # Get archive from container
            archive_stream, _ = self.container.get_archive(container_path)
            
            # Write archive data
            archive_data = b''.join(archive_stream)
            
            if extract_tar:
                # Extract tar archive
                with tarfile.open(fileobj=BytesIO(archive_data), mode='r') as tar:
                    # Create parent directory if it doesn't exist
                    local_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Extract all files
                    for member in tar.getmembers():
                        if member.isfile():
                            # Extract file
                            file_data = tar.extractfile(member).read()
                            
                            # Determine target path
                            if len(tar.getmembers()) == 1:
                                # Single file, use specified local path
                                target_path = local_path
                            else:
                                # Multiple files, create directory structure
                                target_path = local_path / member.name
                            
                            # Create parent directory
                            target_path.parent.mkdir(parents=True, exist_ok=True)
                            
                            # Write file
                            with open(target_path, 'wb') as f:
                                f.write(file_data)
                            
                            # Set permissions
                            os.chmod(target_path, member.mode)
                            
                        elif member.isdir():
                            # Create directory
                            dir_path = local_path / member.name
                            dir_path.mkdir(parents=True, exist_ok=True)
                            os.chmod(dir_path, member.mode)
            else:
                # Save as tar file
                with open(local_path, 'wb') as f:
                    f.write(archive_data)
            
            self.logger.info(f"File download completed: {container_path} -> {local_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to download file: {e}")
            return False
    
    def download_file_content(self, container_path: str) -> Optional[bytes]:
        """
        Download file content from container
        
        Args:
            container_path: Source file path in container
            
        Returns:
            File content as bytes or None
        """
        try:
            if not self.container:
                self.logger.error("Container not started")
                return None
            
            self.logger.info(f"Downloading content from container file {container_path}")
            
            # Get archive from container
            archive_stream, _ = self.container.get_archive(container_path)
            archive_data = b''.join(archive_stream)
            
            # Extract file content from tar
            with tarfile.open(fileobj=BytesIO(archive_data), mode='r') as tar:
                # Get first file
                for member in tar.getmembers():
                    if member.isfile():
                        file_data = tar.extractfile(member).read()
                        self.logger.info(f"Content download completed: {container_path}")
                        return file_data
            
            self.logger.warning(f"No file found in archive: {container_path}")
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to download content: {e}")
            return None
    
    def list_files(self, container_path: str = "/") -> Optional[List[Dict[str, Any]]]:
        """
        List files and directories in container path
        
        Args:
            container_path: Directory path in container
            
        Returns:
            List of file information or None
        """
        try:
            if not self.container:
                self.logger.error("Container not started")
                return None
            
            # Use ls command to list files
            result = self.execute_command(f"ls -la {container_path}")
            
            if not result or result.exit_code != 0:
                self.logger.error(f"Failed to list directory: {container_path}")
                return None
            
            # Parse ls output
            lines = result.output.decode('utf-8').strip().split('\n')
            files = []
            
            for line in lines[1:]:  # Skip first line (total)
                if not line.strip():
                    continue
                    
                parts = line.split()
                if len(parts) >= 9:
                    permissions = parts[0]
                    size = parts[4]
                    name = ' '.join(parts[8:])  # Handle filenames with spaces
                    
                    # Skip . and .. entries
                    if name in ['.', '..']:
                        continue
                    
                    file_info = {
                        'name': name,
                        'permissions': permissions,
                        'size': size,
                        'is_file': permissions.startswith('-'),
                        'is_directory': permissions.startswith('d'),
                        'is_link': permissions.startswith('l')
                    }
                    files.append(file_info)
            
            return files
            
        except Exception as e:
            self.logger.error(f"Failed to list files: {e}")
            return None
    
    def file_exists(self, container_path: str) -> bool:
        """
        Check if file or directory exists in container
        
        Args:
            container_path: Path to check in container
            
        Returns:
            bool: Whether file exists
        """
        try:
            if not self.container:
                self.logger.error("Container not started")
                return False
            
            # Use test command to check existence
            result = self.execute_command(f"test -e {container_path}")
            return result is not None and result.exit_code == 0
            
        except Exception as e:
            self.logger.error(f"Failed to check file existence: {e}")
            return False
    
    def create_directory(self, container_path: str, parents: bool = True) -> bool:
        """
        Create directory in container
        
        Args:
            container_path: Directory path to create
            parents: Whether to create parent directories
            
        Returns:
            bool: Whether creation was successful
        """
        try:
            if not self.container:
                self.logger.error("Container not started")
                return False
            
            # Build mkdir command
            cmd = "mkdir"
            if parents:
                cmd += " --parents"
            cmd += f" {container_path}"
            
            result = self.execute_command(cmd)
            
            if result and result.exit_code == 0:
                self.logger.info(f"Directory created successfully: {container_path}")
                return True
            else:
                self.logger.error(f"Failed to create directory: {container_path}")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to create directory: {e}")
            return False
    
    def remove_file(self, container_path: str, recursive: bool = False, force: bool = False) -> bool:
        """
        Remove file or directory in container
        
        Args:
            container_path: Path to remove
            recursive: Whether to remove recursively
            force: Whether to force removal
            
        Returns:
            bool: Whether removal was successful
        """
        try:
            if not self.container:
                self.logger.error("Container not started")
                return False
            
            # Build rm command
            cmd = "rm"
            if recursive:
                cmd += " -r"
            if force:
                cmd += " -f"
            cmd += f" {container_path}"
            
            result = self.execute_command(cmd)
            
            if result and result.exit_code == 0:
                self.logger.info(f"File deleted successfully: {container_path}")
                return True
            else:
                self.logger.error(f"Failed to delete file: {container_path}")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to remove file: {e}")
            return False
    
    def cleanup(self):
        """
        Clean up resources
        """
        self.logger.info("Cleaning up resources")
        
        # Stop all processes
        for process_name in list(self.processes.keys()):
            self.stop_process(process_name)
        
        # Stop container
        if self.container:
            try:
                self.stop_container()
            except Exception as e:
                self.logger.error(f"Error stopping container during cleanup: {e}")
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.cleanup()