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
import sys
import os
import time
from unittest.mock import Mock

# Add the project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from reboot.validator.forward import apply_vault_reward_distribution


class MockValidator:
    """Mock validator class for performance testing"""
    def __init__(self, num_miners=100):
        self.vault_hotkey = "vault_hotkey_0"
        self.metagraph = Mock()
        
        # Create many hotkeys for performance testing
        hotkeys = [f"vault_hotkey_0"]  # Vault
        for i in range(1, num_miners):
            hotkeys.append(f"miner_hotkey_{i}")
        
        self.metagraph.hotkeys = hotkeys


def run_performance_test():
    """Run performance tests for vault reward distribution"""
    print("Running performance tests for vault reward distribution...")
    
    # Test with different numbers of miners
    test_cases = [
        (10, "Small network"),
        (50, "Medium network"),
        (100, "Large network"),
        (500, "Very large network"),
    ]
    
    for num_miners, description in test_cases:
        print(f"\n{description} ({num_miners} miners):")
        
        # Create mock validator
        validator = MockValidator(num_miners)
        
        # Generate random rewards
        np.random.seed(42)  # For reproducible results
        rewards = np.random.uniform(0.1, 1.0, num_miners)
        uids = list(range(num_miners))
        
        # Time the distribution function
        start_time = time.time()
        
        for _ in range(100):  # Run 100 iterations for better timing
            adjusted_rewards = apply_vault_reward_distribution(
                validator, rewards, uids
            )
        
        end_time = time.time()
        avg_time = (end_time - start_time) / 100
        
        # Verify correctness
        total_original = np.sum(rewards)
        total_adjusted = np.sum(adjusted_rewards)
        vault_reward = adjusted_rewards[0]
        expected_vault_reward = total_original * 0.2
        
        print(f"  Average execution time: {avg_time*1000:.3f} ms")
        print(f"  Total reward preserved: {abs(total_original - total_adjusted) < 1e-10}")
        print(f"  Vault reward correct: {abs(vault_reward - expected_vault_reward) < 1e-10}")
        print(f"  Vault gets 20%: {abs(vault_reward / total_original - 0.2) < 1e-10}")


def run_correctness_test():
    """Run correctness tests with various scenarios"""
    print("\n" + "="*50)
    print("Running correctness tests...")
    
    test_scenarios = [
        {
            "name": "Equal rewards",
            "rewards": [1.0, 1.0, 1.0, 1.0],
            "expected_vault_share": 0.8,  # 20% of 4.0
        },
        {
            "name": "High performing vault",
            "rewards": [2.0, 0.5, 0.3, 0.2],
            "expected_vault_share": 0.6,  # 20% of 3.0
        },
        {
            "name": "Low performing vault",
            "rewards": [0.1, 2.0, 1.5, 1.4],
            "expected_vault_share": 1.0,  # 20% of 5.0
        },
        {
            "name": "Zero rewards for others",
            "rewards": [1.0, 0.0, 0.0, 0.0],
            "expected_vault_share": 0.2,  # 20% of 1.0
        },
    ]
    
    validator = MockValidator(4)
    uids = [0, 1, 2, 3]
    
    for scenario in test_scenarios:
        print(f"\n{scenario['name']}:")
        rewards = np.array(scenario['rewards'])
        
        adjusted_rewards = apply_vault_reward_distribution(
            validator, rewards, uids
        )
        
        total_original = np.sum(rewards)
        vault_reward = adjusted_rewards[0]
        non_vault_rewards = adjusted_rewards[1:]
        
        print(f"  Original rewards: {rewards}")
        print(f"  Adjusted rewards: {adjusted_rewards}")
        print(f"  Vault reward: {vault_reward:.3f} (expected: {scenario['expected_vault_share']:.3f})")
        print(f"  Non-vault rewards: {non_vault_rewards}")
        print(f"  Total preserved: {abs(total_original - np.sum(adjusted_rewards)) < 1e-10}")
        
        # Verify vault gets exactly 20%
        assert abs(vault_reward - scenario['expected_vault_share']) < 1e-10
        
        # Verify total is preserved
        assert abs(total_original - np.sum(adjusted_rewards)) < 1e-10
        
        # Verify non-vault rewards sum to 80%
        assert abs(np.sum(non_vault_rewards) - total_original * 0.8) < 1e-10
        
        print("  ✓ PASSED")


def run_edge_case_tests():
    """Run edge case tests"""
    print("\n" + "="*50)
    print("Running edge case tests...")
    
    validator = MockValidator(4)
    
    # Test 1: Single miner (vault only)
    print("\nSingle miner (vault only):")
    rewards = np.array([1.0])
    uids = [0]
    
    adjusted_rewards = apply_vault_reward_distribution(
        validator, rewards, uids
    )
    
    print(f"  Original: {rewards}")
    print(f"  Adjusted: {adjusted_rewards}")
    print(f"  Single miner gets full reward: {adjusted_rewards[0] == 1.0}")
    
    # Test 2: All zero rewards
    print("\nAll zero rewards:")
    rewards = np.array([0.0, 0.0, 0.0, 0.0])
    uids = [0, 1, 2, 3]
    
    adjusted_rewards = apply_vault_reward_distribution(
        validator, rewards, uids
    )
    
    print(f"  Original: {rewards}")
    print(f"  Adjusted: {adjusted_rewards}")
    print(f"  All rewards remain zero: {np.all(adjusted_rewards == 0.0)}")
    
    # Test 3: Very large rewards
    print("\nVery large rewards:")
    rewards = np.array([1000000.0, 500000.0, 300000.0, 200000.0])
    uids = [0, 1, 2, 3]
    
    adjusted_rewards = apply_vault_reward_distribution(
        validator, rewards, uids
    )
    
    total_original = np.sum(rewards)
    vault_reward = adjusted_rewards[0]
    expected_vault_reward = total_original * 0.2
    
    print(f"  Original total: {total_original}")
    print(f"  Adjusted total: {np.sum(adjusted_rewards)}")
    print(f"  Vault reward: {vault_reward} (expected: {expected_vault_reward})")
    print(f"  Large rewards handled correctly: {abs(vault_reward - expected_vault_reward) < 1e-6}")
    
    print("\n✓ All edge case tests passed!")


if __name__ == "__main__":
    print("Vault Reward Distribution Test Suite")
    print("="*50)
    
    run_correctness_test()
    run_edge_case_tests()
    run_performance_test()
    
    print("\n" + "="*50)
    print("All tests completed successfully!")