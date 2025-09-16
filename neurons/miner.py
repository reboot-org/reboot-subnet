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
import os
import time
import typing
import json
import bittensor as bt
from controller.docker_controller import DockerController
from reboot.protocol import RobotSynapse, RobotOutput
import base64

import reboot

# import base miner class which takes care of most of the boilerplate
from reboot.base.miner import BaseMinerNeuron


class Miner(BaseMinerNeuron):
    def __init__(self, config=None):
        super(Miner, self).__init__(config=config)
        self.controller = DockerController(container_name="ros2-sn", image="reboot-subnet-simulator:latest")

    def parse_action_strings(self, action_strings):
        """Parse action strings into action dictionaries"""
        actions = []
        for action_str in action_strings:
            parts = action_str.split(',')
            if len(parts) >= 1:
                action = {'type': parts[0].strip()}
                if len(parts) >= 2:
                    try:
                        action['speed'] = float(parts[1].strip())
                    except ValueError:
                        action['speed'] = 0.5
                if len(parts) >= 3:
                    try:
                        action['duration'] = float(parts[2].strip())
                    except ValueError:
                        action['duration'] = 1.0
                actions.append(action)
        return actions

    def execute_movement_sequence(self, actions):
        """Execute movement sequence in the container"""
        # Convert actions to JSON string for robot_movement.py
        actions_json = json.dumps(actions)
        
        # Execute the movement sequence
        result = self.controller.execute_command(
            command=f'bash -c "/usr/local/bin/docker-entrypoint.sh python3 /root/ros2_ws/src/api_server/robot_movement.py \'{actions_json}\'"'
        )
        
        bt.logging.info(f"Movement sequence executed: {result}")
        return result

    def capture_camera_image(self, image_path="/tmp/camera_image.png"):
        """Capture camera image from the container"""
        # Execute get_camera_image.py
        result = self.controller.execute_command(
            command=f'bash -c "/usr/local/bin/docker-entrypoint.sh python3 /root/ros2_ws/src/api_server/get_camera_image.py {image_path}"'
        )
        
        bt.logging.info(f"Camera capture result: {result}")
        
        # Download the captured image
        try:
            image_bytes = self.controller.download_file_content(container_path=image_path)
            bt.logging.info(f"Camera image downloaded: {len(image_bytes)} bytes")
            return image_bytes
        except Exception as e:
            bt.logging.error(f"Failed to download camera image: {e}")
            return None

    def run_job(self, actions=None):
        home_path = os.getenv("HOME")
        self.controller.start_container(environment={"TURTLEBOT3_MODE": "waffle_pi"}, ports={"5000": 5000, "8888": 8888}, volumes={f'{home_path}/.gz_miner': {'bind': '/root/.gz', 'mode': 'rw'}}, command="sleep infinity", clean_existing=True)
        self.controller.start_process(process_name="gazebo", command='bash -c "/usr/local/bin/docker-entrypoint.sh xvfb-run -a ros2 launch turtlebot3_gazebo turtlebot3_world.launch.py > /root/ros2_ws/gz.log"')
        time.sleep(10)
        self.controller.start_process(process_name="rosboard", command='bash -c "/usr/local/bin/docker-entrypoint.sh ros2 run rosboard rosboard_node > /root/ros2_ws/rosboard.log"')
        time.sleep(10)
        self.controller.start_process(process_name="cartographer", command='bash -c "/usr/local/bin/docker-entrypoint.sh xvfb-run -a ros2 launch turtlebot3_cartographer cartographer.launch.py use_sim_time:=True > /root/ros2_ws/cartographer.log"')
        time.sleep(20)

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

    
    async def forward(
        self, synapse: RobotSynapse
    ) -> RobotSynapse:
        # 打印收到的action_seqs
        if hasattr(synapse.input, 'action_seqs') and synapse.input.action_seqs:
            bt.logging.info(f"Received action_seqs: {synapse.input.action_seqs}")
            
            # Parse action strings into movement sequence
            actions = self.parse_action_strings(synapse.input.action_seqs)
            bt.logging.info(f"Parsed actions: {actions}")            
            
            # Run job with actions
            miner_image_bytes = self.run_job(actions=actions)
            
            if miner_image_bytes:
                # Convert to base64 for response
                miner_image_b64 = base64.b64encode(miner_image_bytes).decode('utf-8')
                bt.logging.info(f"Miner camera image captured: {len(miner_image_bytes)} bytes")
            else:
                miner_image_b64 = ""
                bt.logging.warning("Failed to capture miner camera image")
                
        else:
            print("No action_seqs received")
            bt.logging.info("No action_seqs received")
            miner_image_b64 = ""
        
        synapse.output = RobotOutput(img_b64=miner_image_b64)
        return synapse

    async def blacklist(
        self, synapse: RobotSynapse
    ) -> typing.Tuple[bool, str]:
        if synapse.dendrite is None or synapse.dendrite.hotkey is None:
            bt.logging.warning(
                "Received a request without a dendrite or hotkey."
            )
            return True, "Missing dendrite or hotkey"

        uid = self.metagraph.hotkeys.index(synapse.dendrite.hotkey)
        if (
            not self.config.blacklist.allow_non_registered
            and synapse.dendrite.hotkey not in self.metagraph.hotkeys
        ):
            # Ignore requests from un-registered entities.
            bt.logging.trace(
                f"Blacklisting un-registered hotkey {synapse.dendrite.hotkey}"
            )
            return True, "Unrecognized hotkey"

        if self.config.blacklist.force_validator_permit:
            # If the config is set to force validator permit, then we should only allow requests from validators.
            if not self.metagraph.validator_permit[uid]:
                bt.logging.warning(
                    f"Blacklisting a request from non-validator hotkey {synapse.dendrite.hotkey}"
                )
                return True, "Non-validator hotkey"

        bt.logging.trace(
            f"Not Blacklisting recognized hotkey {synapse.dendrite.hotkey}"
        )
        return False, "Hotkey recognized!"

    async def priority(self, synapse: reboot.protocol.RobotSynapse) -> float:
        if synapse.dendrite is None or synapse.dendrite.hotkey is None:
            bt.logging.warning(
                "Received a request without a dendrite or hotkey."
            )
            return 0.0

        caller_uid = self.metagraph.hotkeys.index(
            synapse.dendrite.hotkey
        )  # Get the caller index.
        priority = float(
            self.metagraph.S[caller_uid]
        )  # Return the stake as the priority.
        bt.logging.trace(
            f"Prioritizing {synapse.dendrite.hotkey} with value: {priority}"
        )
        return priority


# This is the main function, which runs the miner.
if __name__ == "__main__":
    with Miner() as miner:
        while True:
            bt.logging.info(f"Miner running... {time.time()}")
            time.sleep(5)
