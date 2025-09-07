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
import random
import json
import base64
import numpy as np
import bittensor as bt

from reboot.protocol import RobotSynapse, RobotInput
from reboot.validator.reward import get_rewards
from reboot.utils.uids import get_random_uids, get_all_uids


def apply_vault_reward_distribution(self, rewards, miner_uids):
    """
    Apply vault reward distribution: allocate 20% of total rewards to vault,
    distribute remaining 80% among other miners based on their performance.
    
    Args:
        rewards: numpy array of original rewards for each miner
        miner_uids: list of miner UIDs corresponding to rewards
        
    Returns:
        numpy array of adjusted rewards
    """
    # Find vault UID
    vault_uid = None
    try:
        if hasattr(self, 'vault_hotkey') and self.vault_hotkey in self.metagraph.hotkeys:
            vault_uid = self.metagraph.hotkeys.index(self.vault_hotkey)
            bt.logging.info(f"Found vault UID: {vault_uid} for hotkey: {self.vault_hotkey}")
        else:
            bt.logging.warning(f"Vault hotkey not found in metagraph")
            return rewards
    except Exception as e:
        bt.logging.error(f"Error finding vault UID: {e}")
        return rewards
    
    if vault_uid is None or vault_uid not in miner_uids:
        bt.logging.warning("Vault not found in miner UIDs, returning original rewards")
        return rewards
    
    # Calculate total reward pool
    total_reward = np.sum(rewards)
    
    # Calculate vault reward (20% of total)
    vault_reward = total_reward * 0.2
    
    # Calculate remaining reward pool for other miners (80% of total)
    remaining_reward_pool = total_reward * 0.8
    
    # Create adjusted rewards array
    adjusted_rewards = np.copy(rewards)
    
    # Find the index of vault in miner_uids
    vault_index = miner_uids.index(vault_uid)
    
    # Set vault reward
    adjusted_rewards[vault_index] = vault_reward
    
    # Calculate rewards for other miners
    non_vault_indices = [i for i, uid in enumerate(miner_uids) if uid != vault_uid]
    
    if non_vault_indices:
        # Calculate sum of original rewards for non-vault miners
        non_vault_original_sum = np.sum(rewards[non_vault_indices])
        
        if non_vault_original_sum > 0:
            # Distribute remaining rewards proportionally
            for idx in non_vault_indices:
                proportion = rewards[idx] / non_vault_original_sum
                adjusted_rewards[idx] = remaining_reward_pool * proportion
        else:
            # If all non-vault miners have 0 rewards, distribute equally
            equal_share = remaining_reward_pool / len(non_vault_indices)
            for idx in non_vault_indices:
                adjusted_rewards[idx] = equal_share
    else:
        # If there are no non-vault miners (only vault exists), 
        # give the remaining 80% back to the vault to preserve total
        adjusted_rewards[vault_index] = total_reward
    
    bt.logging.info(f"Vault reward distribution applied:")
    bt.logging.info(f"  Total reward: {total_reward:.6f}")
    bt.logging.info(f"  Vault reward (20%): {vault_reward:.6f}")
    bt.logging.info(f"  Remaining pool (80%): {remaining_reward_pool:.6f}")
    bt.logging.info(f"  Vault UID: {vault_uid}, Index: {vault_index}")
    
    return adjusted_rewards


async def forward(self):
    miner_uids = get_all_uids(self)
    bt.logging.info(f"Miner UIDs: {miner_uids}")
    
    # Generate random movement sequence
    movement_sequence = self.generate_random_movement_sequence(num_actions=5)
    bt.logging.info(f"Generated movement sequence: {movement_sequence}")
    
    validator_image_bytes = self.run_job()

    validator_image_b64 = base64.b64encode(validator_image_bytes).decode('utf-8') if validator_image_bytes else ""
    
    # Convert movement sequence to action strings for miners
    action_strings = [f"{action['type']},{action['speed']},{action['duration']}" for action in movement_sequence]
    
    # Create synapse with movement sequence and validator's camera image
    input = RobotSynapse(input=RobotInput(action_seqs=action_strings))
    
    # The dendrite client queries the network.
    responses = await self.dendrite(
        axons=[self.metagraph.axons[uid] for uid in miner_uids],
        synapse=input,
        deserialize=False,
        timeout=120,
    )

    # Log the results for monitoring purposes.
    bt.logging.info(f"Received responses: {responses}")

    rewards = get_rewards(self, query=self.step, responses=responses, validator_image=validator_image_bytes)

    bt.logging.info(f"Original rewards: {rewards}")
    
    # Apply vault reward distribution
    adjusted_rewards = apply_vault_reward_distribution(self, rewards, miner_uids)
    
    bt.logging.info(f"Adjusted rewards after vault distribution: {adjusted_rewards}")
    # Update the scores based on the adjusted rewards.
    self.update_scores(adjusted_rewards, miner_uids)
    time.sleep(5)
