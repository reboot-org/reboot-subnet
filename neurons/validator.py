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


    def run_job(self):
        home_path = os.getenv("HOME")
        self.controller.start_container(environment={"TURTLEBOT3_MODE": "waffle_pi"}, ports={"5000": 5001, "8888": 8889}, volumes={f'{home_path}/.gz': {'bind': '/root/.gz', 'mode': 'rw'}}, command="sleep infinity", clean_existing=True)
        time.sleep(10)
        self.controller.start_process(process_name="gazebo", command='bash -c "/usr/local/bin/docker-entrypoint.sh xvfb-run -a ros2 launch turtlebot3_gazebo turtlebot3_dqn_stage1.launch.py > /root/ros2_ws/gz.log"')
        time.sleep(10)
        self.controller.start_process(process_name="rosboard", command='bash -c "/usr/local/bin/docker-entrypoint.sh ros2 run rosboard rosboard_node > /root/ros2_ws/rosboard.log"')
        time.sleep(10)
        self.controller.start_process(process_name="cartographer", command='bash -c "/usr/local/bin/docker-entrypoint.sh xvfb-run -a ros2 launch turtlebot3_cartographer cartographer.launch.py use_sim_time:=True > /root/ros2_ws/cartographer.log"')
        time.sleep(30)
        self.controller.execute_command(command='bash -c "/usr/local/bin/docker-entrypoint.sh python3 /root/ros2_ws/src/api_server/get_map.py /tmp/map.png"')
        mapbytes = self.controller.download_file_content(container_path="/tmp/map.png")
        b64data = base64.b64encode(mapbytes).decode('utf-8')
        print("received map", mapbytes[:20])
        return b64data
        

    async def forward(self):
        return await forward(self)


# The main function parses the configuration and runs the validator.
if __name__ == "__main__":
    with Validator() as validator:
        while True:
            bt.logging.info(f"Validator running... {time.time()}")
            time.sleep(5)
