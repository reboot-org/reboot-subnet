# The MIT License (MIT)
# Copyright © 2025 Reboot SN Dev

# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the “Software”), to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all copies or substantial portions of
# the Software.

# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
# THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.


import time
import os
import random
import json
# Bittensor
import bittensor as bt
from controller import DockerController

from reboot.base.validator import BaseValidatorNeuron
import base64

# Bittensor Validator Template:
from reboot.validator import forward


class Validator(BaseValidatorNeuron):
    def __init__(self, config=None):
        super(Validator, self).__init__(config=config)

        bt.logging.info("load_state()")
        self.load_state()
        self.controller = DockerController(container_name="ros2-sn-vali", image="reboot-subnet-simulator:latest")
        
        # Configure vault hotkey
        self.vault_hotkey = "5GHLKYW6kFaVAmHwwws4xZYsAgDu9uc8kVJHmUFAD3qEF53o"
        
        bt.logging.info(f"Vault hotkey configured: {self.vault_hotkey}")
        
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
        self.controller.start_container(environment={"TURTLEBOT3_MODE": "waffle_pi"}, ports={"5000": 5001, "8888": 8889}, volumes={f'{home_path}/.gz_validator': {'bind': '/root/.gz', 'mode': 'rw'}}, command="sleep infinity", clean_existing=True)
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


# The main function parses the configuration and runs the validator.
if __name__ == "__main__":
    with Validator() as validator:
        while True:
            bt.logging.info(f"Validator running... {time.time()}")
            time.sleep(5)
