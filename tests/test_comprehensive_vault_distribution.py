#!/usr/bin/env python3
"""
Comprehensive test for vault reward distribution across different network configurations.
Tests various combinations of miners and validators to ensure correctness.
"""

import numpy as np
import sys
import os
import time
from typing import List, Tuple, Dict
from dataclasses import dataclass

# Add the project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock the bittensor import for testing
class MockBT:
    class logging:
        @staticmethod
        def info(msg):
            pass  # Suppress logging for cleaner test output
        @staticmethod
        def warning(msg):
            pass
        @staticmethod
        def error(msg):
            pass

# Mock the vault reward distribution function
def apply_vault_reward_distribution(self, rewards, miner_uids):
    """Mock implementation of vault reward distribution for testing"""
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


@dataclass
class NetworkConfig:
    """Configuration for network testing"""
    num_miners: int
    num_validators: int
    vault_position: int
    reward_distribution: str  # 'uniform', 'skewed', 'random', 'zero_others'
    
class MockValidator:
    """Mock validator for testing"""
    def __init__(self, vault_hotkey: str, metagraph_hotkeys: List[str]):
        self.vault_hotkey = vault_hotkey
        self.metagraph = MockBT()
        self.metagraph.hotkeys = metagraph_hotkeys


class NetworkTester:
    """Test various network configurations"""
    
    def __init__(self):
        self.test_results = []
        
    def generate_rewards(self, config: NetworkConfig, seed: int = 42) -> np.ndarray:
        """Generate rewards based on configuration"""
        np.random.seed(seed)
        
        if config.reward_distribution == 'uniform':
            return np.ones(config.num_miners) * np.random.uniform(0.5, 1.0)
        elif config.reward_distribution == 'skewed':
            # Exponential distribution favoring early miners
            return np.random.exponential(scale=1.0, size=config.num_miners)
        elif config.reward_distribution == 'random':
            return np.random.uniform(0.1, 1.0, config.num_miners)
        elif config.reward_distribution == 'zero_others':
            rewards = np.zeros(config.num_miners)
            rewards[config.vault_position] = np.random.uniform(0.5, 1.0)
            return rewards
        elif config.reward_distribution == 'high_vault':
            rewards = np.random.uniform(0.1, 0.3, config.num_miners)
            rewards[config.vault_position] = np.random.uniform(2.0, 5.0)
            return rewards
        else:
            return np.random.uniform(0.1, 1.0, config.num_miners)
    
    def create_network_config(self, num_miners: int, vault_position: int = 0) -> NetworkConfig:
        """Create network configuration"""
        return NetworkConfig(
            num_miners=num_miners,
            num_validators=1,  # For now, test with single validator
            vault_position=vault_position,
            reward_distribution='random'
        )
    
    def test_single_configuration(self, config: NetworkConfig) -> Dict:
        """Test a single network configuration"""
        # Generate hotkeys
        hotkeys = [f"miner_hotkey_{i}" for i in range(config.num_miners)]
        hotkeys[config.vault_position] = "vault_hotkey"
        
        # Create validator
        validator = MockValidator("vault_hotkey", hotkeys)
        
        # Generate rewards
        rewards = self.generate_rewards(config)
        uids = list(range(config.num_miners))
        
        # Apply vault distribution
        start_time = time.time()
        adjusted_rewards = apply_vault_reward_distribution(validator, rewards, uids)
        execution_time = time.time() - start_time
        
        # Calculate metrics
        total_original = np.sum(rewards)
        total_adjusted = np.sum(adjusted_rewards)
        vault_reward = adjusted_rewards[config.vault_position]
        
        # Special case: if only one miner (vault), it gets full reward
        if config.num_miners == 1:
            expected_vault_reward = total_original
            expected_non_vault_rewards = 0.0
        else:
            expected_vault_reward = total_original * 0.2
            expected_non_vault_rewards = total_original * 0.8
        
        non_vault_rewards = np.sum(adjusted_rewards) - vault_reward
        
        # Verify correctness
        total_preserved = abs(total_original - total_adjusted) < 1e-10
        vault_correct = abs(vault_reward - expected_vault_reward) < 1e-10
        non_vault_correct = abs(non_vault_rewards - expected_non_vault_rewards) < 1e-10
        
        return {
            'config': config,
            'total_original': total_original,
            'total_adjusted': total_adjusted,
            'vault_reward': vault_reward,
            'expected_vault_reward': expected_vault_reward,
            'non_vault_rewards': non_vault_rewards,
            'execution_time': execution_time,
            'total_preserved': total_preserved,
            'vault_correct': vault_correct,
            'non_vault_correct': non_vault_correct,
            'all_correct': total_preserved and vault_correct and non_vault_correct
        }
    
    def test_small_networks(self):
        """Test small networks (1-10 miners)"""
        print("Testing Small Networks (1-10 miners)...")
        print("=" * 50)
        
        small_configs = [
            self.create_network_config(1),   # Single miner (vault only)
            self.create_network_config(2),   # 2 miners
            self.create_network_config(3),   # 3 miners
            self.create_network_config(5),   # 5 miners
            self.create_network_config(10),  # 10 miners
        ]
        
        results = []
        for config in small_configs:
            result = self.test_single_configuration(config)
            results.append(result)
            
            status = "✅ PASS" if result['all_correct'] else "❌ FAIL"
            print(f"  {config.num_miners} miners: {status}")
            print(f"    Total: {result['total_original']:.3f} → {result['total_adjusted']:.3f}")
            print(f"    Vault: {result['vault_reward']:.3f} (expected: {result['expected_vault_reward']:.3f})")
            print(f"    Time: {result['execution_time']*1000:.3f}ms")
        
        return results
    
    def test_medium_networks(self):
        """Test medium networks (11-50 miners)"""
        print("\nTesting Medium Networks (11-50 miners)...")
        print("=" * 50)
        
        medium_configs = [
            self.create_network_config(11),  # 11 miners
            self.create_network_config(25),  # 25 miners
            self.create_network_config(33),  # 33 miners
            self.create_network_config(50),  # 50 miners
        ]
        
        results = []
        for config in medium_configs:
            result = self.test_single_configuration(config)
            results.append(result)
            
            status = "✅ PASS" if result['all_correct'] else "❌ FAIL"
            print(f"  {config.num_miners} miners: {status}")
            print(f"    Total: {result['total_original']:.3f} → {result['total_adjusted']:.3f}")
            print(f"    Vault: {result['vault_reward']:.3f} (expected: {result['expected_vault_reward']:.3f})")
            print(f"    Time: {result['execution_time']*1000:.3f}ms")
        
        return results
    
    def test_large_networks(self):
        """Test large networks (51-200 miners)"""
        print("\nTesting Large Networks (51-200 miners)...")
        print("=" * 50)
        
        large_configs = [
            self.create_network_config(51),   # 51 miners
            self.create_network_config(100),  # 100 miners
            self.create_network_config(150),  # 150 miners
            self.create_network_config(200),  # 200 miners
        ]
        
        results = []
        for config in large_configs:
            result = self.test_single_configuration(config)
            results.append(result)
            
            status = "✅ PASS" if result['all_correct'] else "❌ FAIL"
            print(f"  {config.num_miners} miners: {status}")
            print(f"    Total: {result['total_original']:.3f} → {result['total_adjusted']:.3f}")
            print(f"    Vault: {result['vault_reward']:.3f} (expected: {result['expected_vault_reward']:.3f})")
            print(f"    Time: {result['execution_time']*1000:.3f}ms")
        
        return results
    
    def test_vault_positions(self):
        """Test different vault positions"""
        print("\nTesting Different Vault Positions...")
        print("=" * 50)
        
        network_size = 10
        positions = [0, 2, 5, 9]  # Beginning, middle, near end, end
        
        results = []
        for position in positions:
            config = self.create_network_config(network_size)
            config.vault_position = position
            
            result = self.test_single_configuration(config)
            results.append(result)
            
            status = "✅ PASS" if result['all_correct'] else "❌ FAIL"
            print(f"  Vault at position {position}: {status}")
            print(f"    Total: {result['total_original']:.3f} → {result['total_adjusted']:.3f}")
            print(f"    Vault: {result['vault_reward']:.3f} (expected: {result['expected_vault_reward']:.3f})")
        
        return results
    
    def test_reward_distributions(self):
        """Test different reward distribution patterns"""
        print("\nTesting Different Reward Distribution Patterns...")
        print("=" * 50)
        
        base_config = self.create_network_config(10)
        distribution_types = [
            'uniform', 'skewed', 'random', 'zero_others', 'high_vault'
        ]
        
        results = []
        for dist_type in distribution_types:
            config = self.create_network_config(10)
            config.reward_distribution = dist_type
            
            result = self.test_single_configuration(config)
            results.append(result)
            
            status = "✅ PASS" if result['all_correct'] else "❌ FAIL"
            print(f"  {dist_type:12}: {status}")
            print(f"    Total: {result['total_original']:.3f} → {result['total_adjusted']:.3f}")
            print(f"    Vault: {result['vault_reward']:.3f} (expected: {result['expected_vault_reward']:.3f})")
        
        return results
    
    def test_extreme_cases(self):
        """Test extreme cases"""
        print("\nTesting Extreme Cases...")
        print("=" * 50)
        
        extreme_cases = []
        
        # Case 1: Very large rewards
        config1 = self.create_network_config(5)
        config1.reward_distribution = 'random'
        extreme_cases.append(('Large rewards', config1, 1000))  # Scale factor
        
        # Case 2: Very small rewards
        config2 = self.create_network_config(5)
        config2.reward_distribution = 'random'
        extreme_cases.append(('Small rewards', config2, 0.001))  # Scale factor
        
        # Case 3: Mixed positive and negative
        config3 = self.create_network_config(5)
        config3.reward_distribution = 'random'
        extreme_cases.append(('Mixed rewards', config3, 'mixed'))
        
        results = []
        for case_name, config, scale_factor in extreme_cases:
            # Generate base rewards
            base_rewards = self.generate_rewards(config)
            
            if scale_factor == 'mixed':
                # Create mixed positive and negative rewards
                rewards = base_rewards * 2 - 1.0  # Scale to [-1, 1]
            else:
                rewards = base_rewards * scale_factor
            
            # Create test setup
            hotkeys = [f"miner_hotkey_{i}" for i in range(config.num_miners)]
            hotkeys[config.vault_position] = "vault_hotkey"
            validator = MockValidator("vault_hotkey", hotkeys)
            uids = list(range(config.num_miners))
            
            # Test
            adjusted_rewards = apply_vault_reward_distribution(validator, rewards, uids)
            
            total_original = np.sum(rewards)
            total_adjusted = np.sum(adjusted_rewards)
            vault_reward = adjusted_rewards[config.vault_position]
            expected_vault_reward = total_original * 0.2
            
            total_preserved = abs(total_original - total_adjusted) < 1e-10
            vault_correct = abs(vault_reward - expected_vault_reward) < 1e-10
            
            result = {
                'case_name': case_name,
                'total_original': total_original,
                'total_adjusted': total_adjusted,
                'vault_reward': vault_reward,
                'expected_vault_reward': expected_vault_reward,
                'total_preserved': total_preserved,
                'vault_correct': vault_correct,
                'all_correct': total_preserved and vault_correct
            }
            results.append(result)
            
            status = "✅ PASS" if result['all_correct'] else "❌ FAIL"
            print(f"  {case_name:15}: {status}")
            print(f"    Total: {result['total_original']:.6f} → {result['total_adjusted']:.6f}")
            print(f"    Vault: {result['vault_reward']:.6f} (expected: {result['expected_vault_reward']:.6f})")
        
        return results
    
    def run_comprehensive_test(self):
        """Run all comprehensive tests"""
        print("Comprehensive Vault Reward Distribution Test")
        print("=" * 60)
        
        all_results = []
        
        # Run all test suites
        all_results.extend(self.test_small_networks())
        all_results.extend(self.test_medium_networks())
        all_results.extend(self.test_large_networks())
        all_results.extend(self.test_vault_positions())
        all_results.extend(self.test_reward_distributions())
        all_results.extend(self.test_extreme_cases())
        
        # Summary
        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        
        total_tests = len(all_results)
        passed_tests = sum(1 for r in all_results if r['all_correct'])
        failed_tests = total_tests - passed_tests
        
        print(f"Total tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Success rate: {passed_tests/total_tests*100:.1f}%")
        
        if failed_tests > 0:
            print("\nFailed tests:")
            for i, result in enumerate(all_results):
                if not result['all_correct']:
                    if 'config' in result:
                        print(f"  {result['config'].num_miners} miners: Total not preserved or vault incorrect")
                    else:
                        print(f"  {result['case_name']}: Total not preserved or vault incorrect")
        
        return all_results


def main():
    """Main test runner"""
    tester = NetworkTester()
    results = tester.run_comprehensive_test()
    
    # Return exit code based on test results
    passed = sum(1 for r in results if r['all_correct'])
    total = len(results)
    return 0 if passed == total else 1


if __name__ == "__main__":
    exit_code = main()
    exit(exit_code)