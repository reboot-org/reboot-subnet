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

    def run_job(self):
        home_path = os.getenv("HOME")
        self.controller.start_container(environment={"TURTLEBOT3_MODE": "waffle_pi"}, ports={"5000": 5000, "8888": 8888}, volumes={f'{home_path}/.gz': {'bind': '/root/.gz', 'mode': 'rw'}}, command="sleep infinity", clean_existing=True)
        self.controller.start_process(process_name="gazebo", command='bash -c "/usr/local/bin/docker-entrypoint.sh xvfb-run -a ros2 launch turtlebot3_gazebo turtlebot3_dqn_stage1.launch.py > /root/ros2_ws/gz.log"')
        time.sleep(10)
        self.controller.start_process(process_name="rosboard", command='bash -c "/usr/local/bin/docker-entrypoint.sh ros2 run rosboard rosboard_node > /root/ros2_ws/rosboard.log"')
        time.sleep(10)
        self.controller.start_process(process_name="cartographer", command='bash -c "/usr/local/bin/docker-entrypoint.sh xvfb-run -a ros2 launch turtlebot3_cartographer cartographer.launch.py use_sim_time:=True > /root/ros2_ws/cartographer.log"')
        time.sleep(20)
        self.controller.execute_command(command='bash -c "/usr/local/bin/docker-entrypoint.sh python3 /root/ros2_ws/src/api_server/get_map.py /tmp/map.png"')
        mapbytes = self.controller.download_file_content(container_path="/tmp/map.png")
        b64data = base64.b64encode(mapbytes).decode('utf-8')
        print("received map", mapbytes[:20])
        return b64data
    
    async def forward(
        self, synapse: RobotSynapse
    ) -> RobotSynapse:
        result = self.run_job()
        synapse.output = RobotOutput(map_b64=result)
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
