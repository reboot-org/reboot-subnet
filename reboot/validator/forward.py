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
import random
import json
import base64
import numpy as np
import bittensor as bt

from reboot.protocol import RobotSynapse, RobotInput
from reboot.utils.uids import get_random_uids, get_all_uids


async def forward(self):
    miner_uids = get_all_uids(self)

    # Create new rewards array with all zeros
    rewards = np.zeros(len(miner_uids), dtype=np.float32)
    bt.logging.info(f"Initialized all miner rewards to zero: {rewards}")
    
    # Try to get subnet owner and set their score to 1
    subnet_owner_address = "5D5Yw1NzfxLDQDP8D9jthkTNnJRKBfKSRTwnVBvg6RQymonx"
    subnet_owner_uid = None
    try:
        # Find the UID corresponding to the subnet owner address
        if subnet_owner_address in self.metagraph.hotkeys:
            subnet_owner_uid = self.metagraph.hotkeys.index(subnet_owner_address)
            bt.logging.info(f"Found subnet owner address {subnet_owner_address} at UID {subnet_owner_uid}")
            
            # Check if the subnet owner UID is in our miner list
            if subnet_owner_uid in miner_uids:
                owner_index = miner_uids.index(subnet_owner_uid)
                rewards[owner_index] = 1000
                bt.logging.info(f"Set subnet owner UID {subnet_owner_uid} (address: {subnet_owner_address}) score to 1.0")
            else:
                bt.logging.warning(f"Subnet owner UID {subnet_owner_uid} not found in miner UIDs")
        else:
            bt.logging.warning(f"Subnet owner address {subnet_owner_address} not found in metagraph hotkeys")
            
    except Exception as e:
        bt.logging.error(f"Error setting subnet owner score: {e}")
    
    bt.logging.info(f"Final rewards: {rewards}")
    
    # Update the scores based on the new rewards.
    self.update_scores(rewards, miner_uids)
    time.sleep(random.randint(60, 120))
