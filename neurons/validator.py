# The MIT License (MIT)
# Copyright © 2025 Reboot SN Dev

# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the "Software"), to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all copies or substantial portions of
# the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
# THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.


import time
import os
import random
import json
import asyncio
import threading
import uuid
from enum import Enum
from dataclasses import dataclass, asdict
from typing import Dict, Optional, Any, List
import base64

# FastAPI imports
from fastapi import FastAPI, HTTPException, Depends, Header, BackgroundTasks
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field
from fastapi.responses import JSONResponse
import uvicorn

# Bittensor
import bittensor as bt
from controller import DockerController

from reboot.base.validator import BaseValidatorNeuron
from reboot.protocol import RobotSynapse, RobotInput
from reboot.utils.uids import get_random_uids

# Bittensor Validator Template:
from reboot.validator import forward


class TaskStatus(Enum):
    """Task status enumeration"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TaskResult:
    """Task result data class"""
    task_id: str
    status: TaskStatus
    created_at: float
    updated_at: float
    ttl: float  # Time to live in seconds
    selected_miners: Optional[List[int]] = None
    results: Optional[List[Dict]] = None
    error: Optional[str] = None
    total_miners: Optional[int] = None


class TaskManager:
    """Task manager"""
    
    def __init__(self):
        self.tasks: Dict[str, TaskResult] = {}
        self.lock = threading.Lock()
        self.default_ttl = 3600  # Default TTL: 1 hour in seconds
    
    def create_task(self, ttl: Optional[float] = None) -> str:
        """Create new task and return task ID"""
        task_id = str(uuid.uuid4())
        task_ttl = ttl if ttl is not None else self.default_ttl
        with self.lock:
            self.tasks[task_id] = TaskResult(
                task_id=task_id,
                status=TaskStatus.PENDING,
                created_at=time.time(),
                updated_at=time.time(),
                ttl=task_ttl
            )
        bt.logging.info(f"Created new task: {task_id} with TTL: {task_ttl}s")
        return task_id
    
    def update_task_status(self, task_id: str, status: TaskStatus, **kwargs):
        """Update task status"""
        with self.lock:
            if task_id in self.tasks:
                task = self.tasks[task_id]
                task.status = status
                task.updated_at = time.time()
                
                # Update other fields
                for key, value in kwargs.items():
                    if hasattr(task, key):
                        setattr(task, key, value)
                
                bt.logging.info(f"Updated task {task_id} status to {status.value}")
    
    def get_task(self, task_id: str) -> Optional[TaskResult]:
        """Get task information"""
        with self.lock:
            task = self.tasks.get(task_id)
            if task and self._is_task_expired(task):
                self._remove_task(task_id)
                return None
            return task
    
    def _is_task_expired(self, task: TaskResult) -> bool:
        """Check if task has expired"""
        current_time = time.time()
        return (current_time - task.created_at) > task.ttl
    
    def _remove_task(self, task_id: str):
        """Remove task from tasks dictionary"""
        if task_id in self.tasks:
            del self.tasks[task_id]
            bt.logging.info(f"Removed expired task: {task_id}")
    
    def cleanup_expired_tasks(self):
        """Clean up all expired tasks"""
        with self.lock:
            current_time = time.time()
            expired_tasks = []
            
            for task_id, task in self.tasks.items():
                if (current_time - task.created_at) > task.ttl:
                    expired_tasks.append(task_id)
            
            for task_id in expired_tasks:
                self._remove_task(task_id)
            
            if expired_tasks:
                bt.logging.info(f"Cleaned up {len(expired_tasks)} expired tasks")
    
    def task_to_dict(self, task: TaskResult) -> dict:
        """Convert task result to dictionary"""
        result = asdict(task)
        # Convert enum to string
        result['status'] = task.status.value
        return result


# Pydantic models for FastAPI
class ActionModel(BaseModel):
    """Action model for robot actions"""
    type: str = Field(..., description="Type of action (move_forward, move_backward, turn_left, turn_right, stop)")
    speed: float = Field(default=0.5, ge=0.0, le=1.0, description="Speed of the action")
    duration: float = Field(default=1.0, gt=0.0, description="Duration of the action in seconds")


class RobotActionRequest(BaseModel):
    """Robot action request model"""
    actions: List[ActionModel] = Field(..., description="List of robot actions to execute")


class HealthResponse(BaseModel):
    """Health check response model"""
    status: str = Field(..., description="Health status")
    timestamp: float = Field(..., description="Current timestamp")


class TaskResponse(BaseModel):
    """Task response model"""
    task_id: str = Field(..., description="Task ID")
    status: str = Field(..., description="Task status")
    created_at: float = Field(..., description="Task creation timestamp")
    updated_at: float = Field(..., description="Task update timestamp")
    ttl: float = Field(..., description="Time to live in seconds")
    selected_miners: Optional[List[int]] = Field(None, description="List of selected miner UIDs")
    results: Optional[List[Dict]] = Field(None, description="Task results")
    error: Optional[str] = Field(None, description="Error message if task failed")
    total_miners: Optional[int] = Field(None, description="Total number of miners")


class RobotActionResponse(BaseModel):
    """Robot action response model"""
    success: bool = Field(..., description="Whether task creation was successful")
    task_id: str = Field(..., description="Created task ID")
    message: str = Field(..., description="Response message")


class FastAPIValidator:
    """FastAPI validator wrapper"""
    
    def __init__(self, validator_instance):
        self.validator = validator_instance
        self.app = FastAPI(
            title="Reboot Subnet Validator API",
            description="FastAPI implementation for Reboot Subnet Validator",
            version="1.0.0"
        )
        self.api_key_header = APIKeyHeader(name="Authorization", auto_error=False)
        self.setup_routes()
    
    def verify_token(self, authorization: str = Header(None)) -> bool:
        """Verify API token from request headers"""
        # If no token is configured, allow all requests
        if not self.validator.api_token:
            return True
        
        if not authorization:
            raise HTTPException(
                status_code=401,
                detail="Missing Authorization header",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Support Bearer token format
        if authorization.startswith('Bearer '):
            token = authorization[7:]  # Remove 'Bearer ' prefix
        else:
            # Support direct token in header
            token = authorization
        
        # Verify token
        if token == self.validator.api_token:
            return True
        else:
            raise HTTPException(
                status_code=401,
                detail="Invalid API token",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    def setup_routes(self):
        """Setup FastAPI routes"""
        
        @self.app.get("/api/health", response_model=HealthResponse)
        async def health_check(authorization: str = Depends(self.verify_token)):
            """Health check endpoint"""
            return HealthResponse(status="healthy", timestamp=time.time())
        
        @self.app.post("/api/robot_action", response_model=RobotActionResponse)
        async def robot_action(
            request: RobotActionRequest,
            background_tasks: BackgroundTasks,
            authorization: str = Depends(self.verify_token)
        ):
            """Handle robot action request"""
            try:
                # Convert Pydantic models to dictionaries
                actions = [action.dict() for action in request.actions]
                
                # Create new task
                task_id = self.validator.task_manager.create_task()
                
                # Add background task
                background_tasks.add_task(
                    self.run_robot_action_task,
                    task_id,
                    actions
                )
                
                return RobotActionResponse(
                    success=True,
                    task_id=task_id,
                    message="Task created successfully. Use /api/task/{task_id} to check status."
                )
                
            except Exception as e:
                bt.logging.error(f"Error handling robot action request: {e}")
                raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
        
        @self.app.get("/api/task/{task_id}", response_model=TaskResponse)
        async def task_status(
            task_id: str,
            authorization: str = Depends(self.verify_token)
        ):
            """Handle task status query"""
            try:
                # Get task information
                task = self.validator.task_manager.get_task(task_id)
                if task is None:
                    raise HTTPException(status_code=404, detail="Task not found")
                
                # Convert task to dictionary format
                task_dict = self.validator.task_manager.task_to_dict(task)
                
                return TaskResponse(**task_dict)
                
            except HTTPException:
                raise
            except Exception as e:
                bt.logging.error(f"Error handling task status request: {e}")
                raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
        
        @self.app.exception_handler(HTTPException)
        async def http_exception_handler(request, exc):
            """Custom HTTP exception handler"""
            return JSONResponse(
                status_code=exc.status_code,
                content={"error": exc.detail, "message": str(exc.detail)}
            )
    
    async def run_robot_action_task(self, task_id: str, actions: List[Dict]):
        """Run robot action task in background"""
        try:
            # Update task status to running
            self.validator.task_manager.update_task_status(task_id, TaskStatus.RUNNING)
            
            # Execute async processing
            result = await self.process_robot_action(actions)
            
            # Update task status based on result
            if result.get('success', False):
                self.validator.task_manager.update_task_status(
                    task_id, 
                    TaskStatus.COMPLETED,
                    selected_miners=result.get('selected_miners'),
                    results=result.get('results'),
                    total_miners=result.get('total_miners')
                )
            else:
                self.validator.task_manager.update_task_status(
                    task_id,
                    TaskStatus.FAILED,
                    error=result.get('error', 'Unknown error')
                )
                
        except Exception as e:
            bt.logging.error(f"Error in robot action task {task_id}: {e}")
            self.validator.task_manager.update_task_status(
                task_id,
                TaskStatus.FAILED,
                error=str(e)
            )
    
    async def process_robot_action(self, actions: List[Dict]):
        """Core logic for processing robot actions"""
        try:
            # Get vault UID to exclude it from selection
            vault_uid = None
            if hasattr(self.validator, 'vault_hotkey') and self.validator.vault_hotkey:
                try:
                    if self.validator.vault_hotkey in self.validator.metagraph.hotkeys:
                        vault_uid = self.validator.metagraph.hotkeys.index(self.validator.vault_hotkey)
                        bt.logging.info(f"Found vault UID to exclude: {vault_uid}")
                except Exception as e:
                    bt.logging.warning(f"Error finding vault UID: {e}")
            
            # Get available miner UIDs and their scores, excluding vault
            available_uids = []
            uid_scores = []
            
            for uid in range(self.validator.metagraph.n.item()):
                # Skip vault UID
                if uid == vault_uid:
                    continue
                    
                if self.validator.metagraph.axons[uid].is_serving:
                    available_uids.append(uid)
                    # Get the score for this UID from our validator's local scores
                    uid_scores.append(self.validator.scores[uid])
            
            if len(available_uids) < 3:
                return {
                    "success": False,
                    "error": f"Not enough available miners (excluding vault). Found {len(available_uids)}, need 3"
                }
            
            # Sort UIDs by score in descending order and select top 3
            uid_score_pairs = list(zip(available_uids, uid_scores))
            uid_score_pairs.sort(key=lambda x: x[1], reverse=True)
            selected_uids = [uid for uid, score in uid_score_pairs[:3]]
            
            bt.logging.info(f"Selected top-scored miner UIDs (excluding vault): {selected_uids}")
            bt.logging.info(f"Selected miner scores: {[score for uid, score in uid_score_pairs[:3]]}")
            
            # Convert actions to string format
            action_strings = []
            for action in actions:
                if isinstance(action, dict):
                    action_type = action.get('type')
                    speed = action.get('speed')
                    duration = action.get('duration')
                    action_strings.append(f"{action_type},{speed},{duration}")
                else:
                    action_strings.append(str(action))
            
            # Create synapse
            synapse = RobotSynapse(input=RobotInput(action_seqs=action_strings))
            
            # Send requests to selected miners
            responses = await self.validator.dendrite(
                axons=[self.validator.metagraph.axons[uid] for uid in selected_uids],
                synapse=synapse,
                deserialize=False,
                timeout=120,
            )
            
            # Collect results
            results = []
            for i, response in enumerate(responses):
                try:
                    if response and hasattr(response, 'output') and response.output:
                        img_b64 = response.output.img_b64 if hasattr(response.output, 'img_b64') else ""
                        results.append({
                            "miner_uid": selected_uids[i],
                            "success": True,
                            "image_b64": img_b64,
                            "image_size": len(img_b64) if img_b64 else 0
                        })
                    else:
                        results.append({
                            "miner_uid": selected_uids[i],
                            "success": False,
                            "error": "No valid response from miner"
                        })
                except Exception as e:
                    results.append({
                        "miner_uid": selected_uids[i],
                        "success": False,
                        "error": str(e)
                    })
            
            return {
                "success": True,
                "selected_miners": selected_uids,
                "results": results,
                "total_miners": len(results)
            }
            
        except Exception as e:
            bt.logging.error(f"Error processing robot action: {e}")
            return {
                "success": False,
                "error": str(e)
            }


class Validator(BaseValidatorNeuron):
    def __init__(self, config=None):
        super(Validator, self).__init__(config=config)
        bt.logging.info("load_state()")
        self.load_state()
        self.controller = DockerController(container_name="ros2-sn-vali", image="reboot-subnet-simulator:latest")
        
        # Configure vault hotkey
        self.vault_hotkey = "5GHLKYW6kFaVAmHwwws4xZYsAgDu9uc8kVJHmUFAD3qEF53o"
        
        bt.logging.info(f"Vault hotkey configured: {self.vault_hotkey}")
        
        # FastAPI server configuration
        self.fastapi_app = None
        self.uvicorn_server = None
        self.enable_api = getattr(self.config, 'enable_api', False) if self.config else False
        self.http_port = getattr(self.config, 'api_port', 8080) if self.config else 8080
        self.http_host = getattr(self.config, 'api_host', '0.0.0.0') if self.config else '0.0.0.0'
        self.api_token = getattr(self.config, 'api_token', None) if self.config else None
        
        # Task manager
        self.task_manager = TaskManager()
        
    def start_fastapi_server(self):
        """Start FastAPI server"""
        if not self.enable_api:
            bt.logging.info("FastAPI server is disabled. Use --enable_api flag to enable.")
            return
            
        try:
            # Create FastAPI app
            self.fastapi_app = FastAPIValidator(self)
            
            # Configure uvicorn
            config = uvicorn.Config(
                app=self.fastapi_app.app,
                host=self.http_host,
                port=self.http_port,
                log_level="info"
            )
            
            # Create and start server
            self.uvicorn_server = uvicorn.Server(config)
            
            # Run server in separate thread
            server_thread = threading.Thread(target=self.uvicorn_server.run, daemon=True)
            server_thread.start()
            
            bt.logging.info(f"FastAPI server started on {self.http_host}:{self.http_port}")
            bt.logging.info("Available endpoints:")
            bt.logging.info("  GET  /api/health - Health check")
            bt.logging.info("  POST /api/robot_action - Process robot actions")
            bt.logging.info("  GET  /api/task/{task_id} - Check task status")
            bt.logging.info("API documentation available at:")
            bt.logging.info(f"  http://{self.http_host}:{self.http_port}/docs")
            
        except Exception as e:
            bt.logging.error(f"Failed to start FastAPI server: {e}")
            raise
    
    def stop_fastapi_server(self):
        """Stop FastAPI server"""
        if self.uvicorn_server:
            try:
                self.uvicorn_server.should_exit = True
                bt.logging.info("FastAPI server stopped")
            except Exception as e:
                bt.logging.error(f"Error stopping FastAPI server: {e}")
    
    def find_vault_uid(self):
        """Find the vault UID in the metagraph"""
        try:
            if self.vault_hotkey in self.metagraph.hotkeys:
                vault_uid = self.metagraph.hotkeys.index(self.vault_hotkey)
                bt.logging.info(f"Found vault UID: {vault_uid} for hotkey: {self.vault_hotkey}")
                return vault_uid
            else:
                bt.logging.warning(f"Vault hotkey {self.vault_hotkey} not found in metagraph")
                return None
        except Exception as e:
            bt.logging.error(f"Error finding vault UID: {e}")
            return None
    
    def generate_random_movement_sequence(self, num_actions=5):
        """Generate a random movement sequence"""
        action_types = ['move_forward', 'move_backward', 'turn_left', 'turn_right', 'stop']
        actions = []
        
        for _ in range(num_actions):
            action_type = random.choice(action_types)
            speed = random.uniform(0.3, 0.8) if action_type != 'stop' else 0.0
            duration = random.uniform(0.5, 2.0)
            
            actions.append({
                'type': action_type,
                'speed': speed,
                'duration': duration
            })
        
        return actions

    def run_job(self, actions=None):
        home_path = os.getenv("HOME")
        self.controller.start_container(environment={"TURTLEBOT3_MODE": "waffle_pi"}, volumes={f'{home_path}/.gz_validator': {'bind': '/root/.gz', 'mode': 'rw'}}, command="sleep infinity", clean_existing=True)
        time.sleep(10)
        self.controller.start_process(process_name="gazebo", command='bash -c "/usr/local/bin/docker-entrypoint.sh xvfb-run -a ros2 launch turtlebot3_gazebo turtlebot3_world.launch.py > /root/ros2_ws/gz.log"')
        time.sleep(10)
        self.controller.start_process(process_name="rosboard", command='bash -c "/usr/local/bin/docker-entrypoint.sh ros2 run rosboard rosboard_node > /root/ros2_ws/rosboard.log"')
        time.sleep(10)
        self.controller.start_process(process_name="cartographer", command='bash -c "/usr/local/bin/docker-entrypoint.sh xvfb-run -a ros2 launch turtlebot3_cartographer cartographer.launch.py use_sim_time:=True > /root/ros2_ws/cartographer.log"')
        time.sleep(30)

        # Execute robot movement if actions are provided
        if actions:
            actions_json = json.dumps(actions)
            actions_b64 = base64.b64encode(actions_json.encode('utf-8')).decode('utf-8')
            result = self.controller.execute_command(
                command=f'bash -c "/usr/local/bin/docker-entrypoint.sh python3 /root/ros2_ws/src/api_server/robot_movement.py --base64 \'{actions_b64}\'"'
            )
            bt.logging.info(f"Robot movement executed: {result}")
            time.sleep(5)

        image_path="/tmp/camera_image.png"
        result = self.controller.execute_command(
            command=f'bash -c "/usr/local/bin/docker-entrypoint.sh python3 /root/ros2_ws/src/api_server/get_camera_image.py {image_path}"'
        )
        # bt.logging.info(f"Camera capture result: {result}")
        
        try:
            image_bytes = self.controller.download_file_content(container_path=image_path)
            bt.logging.info(f"Camera image downloaded: {len(image_bytes)} bytes")
            return image_bytes
        except Exception as e:
            bt.logging.error(f"Failed to download camera image: {e}")
            return None
        

    async def forward(self):
        return await forward(self)
    
    def __enter__(self):
        """Start FastAPI server when entering context manager"""
        super().__enter__()
        self.start_fastapi_server()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop FastAPI server when exiting context manager"""
        self.stop_fastapi_server()
        super().__exit__(exc_type, exc_val, exc_tb)


# The main function parses the configuration and runs the validator.
if __name__ == "__main__":
    with Validator() as validator:
        bt.logging.info("Validator started with FastAPI server")
        last_cleanup_time = time.time()
        cleanup_interval = 300  # Clean up every 5 minutes (300 seconds)
        
        try:
            while True:
                current_time = time.time()
                
                # Clean up expired tasks periodically
                if current_time - last_cleanup_time > cleanup_interval:
                    validator.task_manager.cleanup_expired_tasks()
                    last_cleanup_time = current_time
                
                bt.logging.info(f"Validator running... {current_time}")
                time.sleep(5)
        except KeyboardInterrupt:
            bt.logging.info("Validator shutting down...")
        except Exception as e:
            bt.logging.error(f"Validator error: {e}")
        finally:
            # Final cleanup on shutdown
            validator.task_manager.cleanup_expired_tasks()
            bt.logging.info("Validator stopped")
