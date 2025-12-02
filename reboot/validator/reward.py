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
import numpy as np
from typing import List
import bittensor as bt
from reboot.protocol import RobotSynapse
from PIL import Image
import io
import time
import base64
from pixelmatch.contrib.PIL import pixelmatch

def calculate_image_similarity(img1_bytes: bytes, img2_bytes: bytes) -> float:
    """
    Calculate similarity between two images using structural similarity index (SSIM).
    
    Args:
        img1_bytes: First image as bytes
        img2_bytes: Second image as bytes
        
    Returns:
        float: Similarity score between 0 and 1, where 1 is identical
    """
    try:
        # Convert bytes to PIL Images
        img1 = Image.open(io.BytesIO(img1_bytes))
        img2 = Image.open(io.BytesIO(img2_bytes))
        
        # Resize to same dimensions (use the smaller size)
        min_width = min(img1.width, img2.width)
        min_height = min(img1.height, img2.height)
        
        img1_resized = img1.resize((min_width, min_height))
        img2_resized = img2.resize((min_width, min_height))
        img_diff = Image.new("RGBA", img1_resized.size)

        mismatch = pixelmatch(img1_resized, img2_resized, img_diff)

        score = float(1-(mismatch/(min_width*min_height)))
        
        if score < 0.95:
            score = 0
        return score
        
    except Exception as e:
        bt.logging.warning(f"Error calculating image similarity: {e}")
        return 0.0

def reward(validator_image_bytes: bytes, synapse: RobotSynapse) -> float:
    """
    Reward the miner response based on camera image similarity. This method returns a reward
    value for the miner, which is used to update the miner's score.

    Args:
        validator_image_bytes: The validator's camera image bytes
        synapse: The synapse containing the miner's response
        
    Returns:
        float: The reward value for the miner (0.0 to 1.0).
    """
    # Get the miner's response
    if synapse.output is None or synapse.output.img_b64 is None:
        bt.logging.warning("No output or img_b64 in synapse")
        return 0.0
    
    try:
        validator_camera_bytes = validator_image_bytes
        miner_camera_bytes = base64.b64decode(synapse.output.img_b64)
    except Exception as e:
        bt.logging.warning(f"Error decoding images: {e}")
        return 0.0
    
    # Calculate image similarity (0.0 to 1.0)
    similarity_score = calculate_image_similarity(validator_camera_bytes, miner_camera_bytes)
    
    # Get processing time from dendrite
    processing_time = getattr(synapse.dendrite, 'process_time', 100000)
    

    final_reward = similarity_score
    
    bt.logging.info(f"Similarity: {similarity_score:.3f}, Final reward: {final_reward:.3f}")
    
    return float(final_reward)


def get_rewards(
    self,
    query: int,
    responses: List[RobotSynapse],
    validator_image: bytes = None,
) -> np.ndarray:
    """
    Returns an array of rewards for the given query and responses.

    Args:
    - query (int): The query sent to the miner.
    - responses (List[RobotSynapse]): A list of responses from the miners.
    - validator_image (bytes): The validator's camera image for comparison.

    Returns:
    - np.ndarray: An array of rewards for the given query and responses.
    """
    # Get all the reward results by iteratively calling your reward() function.

    return np.array([reward(validator_image, response) for response in responses])
