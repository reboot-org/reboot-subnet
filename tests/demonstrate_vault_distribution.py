#!/usr/bin/env python3
"""
Demonstration script showing vault reward distribution across different network configurations.
This script showcases the vault reward distribution logic in various scenarios.
"""

import numpy as np
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock implementation for demonstration
def apply_vault_reward_distribution(self, rewards, miner_uids):
    """Vault reward distribution implementation"""
    vault_uid = None
    try:
        if hasattr(self, 'vault_hotkey') and self.vault_hotkey in self.metagraph.hotkeys:
            vault_uid = self.metagraph.hotkeys.index(self.vault_hotkey)
        else:
            return rewards
    except Exception:
        return rewards
    
    if vault_uid is None or vault_uid not in miner_uids:
        return rewards
    
    total_reward = np.sum(rewards)
    vault_reward = total_reward * 0.2
    remaining_reward_pool = total_reward * 0.8
    
    adjusted_rewards = np.copy(rewards)
    vault_index = miner_uids.index(vault_uid)
    adjusted_rewards[vault_index] = vault_reward
    
    non_vault_indices = [i for i, uid in enumerate(miner_uids) if uid != vault_uid]
    
    if non_vault_indices:
        non_vault_original_sum = np.sum(rewards[non_vault_indices])
        
        if non_vault_original_sum > 0:
            for idx in non_vault_indices:
                proportion = rewards[idx] / non_vault_original_sum
                adjusted_rewards[idx] = remaining_reward_pool * proportion
        else:
            equal_share = remaining_reward_pool / len(non_vault_indices)
            for idx in non_vault_indices:
                adjusted_rewards[idx] = equal_share
    else:
        # If there are no non-vault miners (only vault exists), 
        # give the remaining 80% back to the vault to preserve total
        adjusted_rewards[vault_index] = total_reward
    
    return adjusted_rewards


class MockValidator:
    """Mock validator for demonstration"""
    def __init__(self, vault_hotkey, hotkeys):
        self.vault_hotkey = vault_hotkey
        self.metagraph = type('obj', (object,), {'hotkeys': hotkeys})()


def demonstrate_scenario(name, rewards, vault_position=0):
    """Demonstrate a specific scenario"""
    print(f"\n{'='*60}")
    print(f"SCENARIO: {name}")
    print(f"{'='*60}")
    
    # Create validator
    num_miners = len(rewards)
    hotkeys = [f"miner_{i}" for i in range(num_miners)]
    hotkeys[vault_position] = "vault_hotkey"
    validator = MockValidator("vault_hotkey", hotkeys)
    uids = list(range(num_miners))
    
    # Apply distribution
    adjusted = apply_vault_reward_distribution(validator, rewards, uids)
    
    # Display results
    total_original = np.sum(rewards)
    total_adjusted = np.sum(adjusted)
    
    print(f"Network size: {num_miners} miners")
    print(f"Vault position: {vault_position}")
    print(f"\nOriginal rewards:")
    for i, reward in enumerate(rewards):
        marker = " (VAULT)" if i == vault_position else ""
        print(f"  Miner {i}: {reward:.3f}{marker}")
    
    print(f"\nAdjusted rewards:")
    for i, reward in enumerate(adjusted):
        marker = " (VAULT)" if i == vault_position else ""
        print(f"  Miner {i}: {reward:.3f}{marker}")
    
    print(f"\nSummary:")
    print(f"  Total original: {total_original:.3f}")
    print(f"  Total adjusted: {total_adjusted:.3f}")
    print(f"  Total preserved: {'✅ YES' if abs(total_original - total_adjusted) < 1e-10 else '❌ NO'}")
    
    vault_reward = adjusted[vault_position]
    expected_vault = total_original * 0.2 if num_miners > 1 else total_original
    print(f"  Vault reward: {vault_reward:.3f} (expected: {expected_vault:.3f})")
    print(f"  Vault gets 20%: {'✅ YES' if num_miners == 1 or abs(vault_reward - expected_vault) < 1e-10 else '❌ NO'}")
    
    if num_miners > 1:
        non_vault_total = np.sum(adjusted) - vault_reward
        expected_non_vault = total_original * 0.8
        print(f"  Non-vault total: {non_vault_total:.3f} (expected: {expected_non_vault:.3f})")
        print(f"  Non-vault gets 80%: {'✅ YES' if abs(non_vault_total - expected_non_vault) < 1e-10 else '❌ NO'}")


def main():
    """Main demonstration"""
    print("VAULT REWARD DISTRIBUTION DEMONSTRATION")
    print("="*60)
    print("This demonstrates how vault reward distribution works across")
    print("different network configurations and scenarios.")
    
    # Scenario 1: Single miner (vault only)
    demonstrate_scenario(
        "Single Miner - Only Vault Exists",
        rewards=np.array([1.0]),
        vault_position=0
    )
    
    # Scenario 2: Small network with equal rewards
    demonstrate_scenario(
        "Small Network - Equal Rewards",
        rewards=np.array([1.0, 1.0, 1.0, 1.0, 1.0]),
        vault_position=0
    )
    
    # Scenario 3: Medium network with varying rewards
    demonstrate_scenario(
        "Medium Network - Varying Performance",
        rewards=np.array([2.0, 0.8, 1.5, 0.3, 1.2, 0.9, 1.8, 0.6, 1.1, 0.4]),
        vault_position=0
    )
    
    # Scenario 4: Large network with vault in middle
    large_rewards = np.random.uniform(0.1, 2.0, 20)
    demonstrate_scenario(
        "Large Network - Vault in Middle",
        rewards=large_rewards,
        vault_position=10
    )
    
    # Scenario 5: High-performing vault
    demonstrate_scenario(
        "High-Performing Vault",
        rewards=np.array([5.0, 0.5, 0.3, 0.2, 0.1]),
        vault_position=0
    )
    
    # Scenario 6: Low-performing vault
    demonstrate_scenario(
        "Low-Performing Vault",
        rewards=np.array([0.1, 2.0, 1.8, 1.5, 1.2]),
        vault_position=0
    )
    
    # Scenario 7: Zero rewards for non-vault miners
    demonstrate_scenario(
        "Zero Rewards for Non-Vault Miners",
        rewards=np.array([1.0, 0.0, 0.0, 0.0, 0.0]),
        vault_position=0
    )
    
    # Scenario 8: Very large network
    np.random.seed(42)  # For reproducible results
    very_large_rewards = np.random.exponential(1.0, 50)
    demonstrate_scenario(
        "Very Large Network (50 miners)",
        rewards=very_large_rewards,
        vault_position=25
    )
    
    print(f"\n{'='*60}")
    print("KEY OBSERVATIONS")
    print(f"{'='*60}")
    print("1. SINGLE MINER: Vault gets 100% (no other miners to distribute to)")
    print("2. MULTIPLE MINERS: Vault gets exactly 20% of total rewards")
    print("3. TOTAL PRESERVED: Sum of rewards always remains the same")
    print("4. PROPORTIONAL: Non-vault miners get rewards proportional to performance")
    print("5. ZERO HANDLING: If non-vault miners have zero rewards, remaining 80% is distributed equally")
    print("6. POSITION INDEPENDENT: Vault position doesn't affect distribution logic")
    print("7. SCALABILITY: Works efficiently from 1 to 1000+ miners")
    
    print(f"\n{'='*60}")
    print("IMPLEMENTATION FEATURES")
    print(f"{'='*60}")
    print("✅ Mathematical correctness (total reward preservation)")
    print("✅ Exact 20% allocation to vault (when multiple miners exist)")
    print("✅ Proportional distribution for non-vault miners")
    print("✅ Edge case handling (single miner, zero rewards, etc.)")
    print("✅ Efficient O(n) time complexity")
    print("✅ Configurable vault hotkey")
    print("✅ Comprehensive logging")
    print("✅ Robust error handling")


if __name__ == "__main__":
    main()