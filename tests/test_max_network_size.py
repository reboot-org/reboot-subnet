#!/usr/bin/env python3
"""
Maximum Network Size Test for Vault Reward Distribution
Tests the system with the maximum of 255 miners to ensure scalability and correctness.
"""

import numpy as np
import sys
import os
import time
from typing import List, Dict, Tuple

# Add the project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock implementation for testing
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
    """Mock validator for testing"""
    def __init__(self, vault_hotkey: str, hotkeys: List[str]):
        self.vault_hotkey = vault_hotkey
        self.metagraph = type('obj', (object,), {'hotkeys': hotkeys})()


class MaxNetworkTester:
    """Test vault reward distribution with maximum network size (255 miners)"""
    
    def __init__(self):
        self.MAX_MINERS = 255
        self.results = []
    
    def generate_hotkeys(self, num_miners: int, vault_position: int = 0) -> List[str]:
        """Generate hotkeys for miners"""
        hotkeys = [f"miner_hotkey_{i:03d}" for i in range(num_miners)]
        hotkeys[vault_position] = "vault_hotkey"
        return hotkeys
    
    def generate_rewards(self, distribution_type: str, num_miners: int, seed: int = 42) -> np.ndarray:
        """Generate rewards based on distribution type"""
        np.random.seed(seed)
        
        if distribution_type == 'uniform':
            return np.ones(num_miners) * np.random.uniform(0.5, 1.0)
        elif distribution_type == 'random':
            return np.random.uniform(0.1, 2.0, num_miners)
        elif distribution_type == 'exponential':
            return np.random.exponential(1.0, num_miners)
        elif distribution_type == 'normal':
            return np.abs(np.random.normal(1.0, 0.5, num_miners))
        elif distribution_type == 'power_law':
            # Power law distribution favoring early miners
            return np.random.pareto(2.0, num_miners) + 0.1
        elif distribution_type == 'zero_most':
            rewards = np.zeros(num_miners)
            # Only 10% of miners get non-zero rewards
            non_zero_count = max(1, num_miners // 10)
            non_zero_indices = np.random.choice(num_miners, non_zero_count, replace=False)
            rewards[non_zero_indices] = np.random.uniform(0.5, 2.0, non_zero_count)
            return rewards
        elif distribution_type == 'high_variance':
            return np.random.uniform(0.01, 10.0, num_miners)
        else:
            return np.random.uniform(0.1, 1.0, num_miners)
    
    def test_single_scenario(self, num_miners: int, vault_position: int, 
                           distribution_type: str, scenario_name: str) -> Dict:
        """Test a single scenario"""
        print(f"\nTesting {scenario_name}...")
        print(f"  Network size: {num_miners} miners")
        print(f"  Vault position: {vault_position}")
        print(f"  Distribution: {distribution_type}")
        
        # Generate test data
        hotkeys = self.generate_hotkeys(num_miners, vault_position)
        validator = MockValidator("vault_hotkey", hotkeys)
        rewards = self.generate_rewards(distribution_type, num_miners)
        uids = list(range(num_miners))
        
        # Apply vault distribution
        start_time = time.time()
        adjusted_rewards = apply_vault_reward_distribution(validator, rewards, uids)
        execution_time = time.time() - start_time
        
        # Calculate metrics
        total_original = np.sum(rewards)
        total_adjusted = np.sum(adjusted_rewards)
        vault_reward = adjusted_rewards[vault_position]
        expected_vault_reward = total_original * 0.2 if num_miners > 1 else total_original
        non_vault_rewards = np.sum(adjusted_rewards) - vault_reward
        expected_non_vault_rewards = total_original * 0.8 if num_miners > 1 else 0.0
        
        # Verify correctness
        total_preserved = abs(total_original - total_adjusted) < 1e-10
        vault_correct = abs(vault_reward - expected_vault_reward) < 1e-10
        non_vault_correct = abs(non_vault_rewards - expected_non_vault_rewards) < 1e-10
        
        # Calculate additional statistics
        non_vault_indices = [i for i in range(num_miners) if i != vault_position]
        original_non_vault_sum = np.sum(rewards[non_vault_indices])
        
        result = {
            'scenario_name': scenario_name,
            'num_miners': num_miners,
            'vault_position': vault_position,
            'distribution_type': distribution_type,
            'total_original': total_original,
            'total_adjusted': total_adjusted,
            'vault_reward': vault_reward,
            'expected_vault_reward': expected_vault_reward,
            'non_vault_rewards': non_vault_rewards,
            'expected_non_vault_rewards': expected_non_vault_rewards,
            'execution_time': execution_time,
            'total_preserved': total_preserved,
            'vault_correct': vault_correct,
            'non_vault_correct': non_vault_correct,
            'all_correct': total_preserved and vault_correct and non_vault_correct,
            'original_non_vault_sum': original_non_vault_sum,
            'max_reward': np.max(rewards),
            'min_reward': np.min(rewards),
            'avg_reward': np.mean(rewards),
            'reward_std': np.std(rewards)
        }
        
        # Print results
        status = "✅ PASS" if result['all_correct'] else "❌ FAIL"
        print(f"  Result: {status}")
        print(f"  Execution time: {execution_time*1000:.3f}ms")
        print(f"  Total: {total_original:.6f} → {total_adjusted:.6f}")
        print(f"  Vault: {vault_reward:.6f} (expected: {expected_vault_reward:.6f})")
        print(f"  Non-vault: {non_vault_rewards:.6f} (expected: {expected_non_vault_rewards:.6f})")
        print(f"  Reward stats: min={result['min_reward']:.3f}, max={result['max_reward']:.3f}, avg={result['avg_reward']:.3f}")
        
        return result
    
    def test_maximum_network_size(self):
        """Test maximum network size with various configurations"""
        print("MAXIMUM NETWORK SIZE TEST (255 MINERS)")
        print("=" * 70)
        print(f"Testing vault reward distribution with maximum network size of {self.MAX_MINERS} miners")
        
        test_scenarios = [
            # Basic configurations
            (self.MAX_MINERS, 0, 'random', 'Vault at beginning - Random distribution'),
            (self.MAX_MINERS, 127, 'random', 'Vault at middle - Random distribution'),
            (self.MAX_MINERS, 254, 'random', 'Vault at end - Random distribution'),
            
            # Different distribution types
            (self.MAX_MINERS, 0, 'uniform', 'Uniform distribution'),
            (self.MAX_MINERS, 0, 'exponential', 'Exponential distribution'),
            (self.MAX_MINERS, 0, 'normal', 'Normal distribution'),
            (self.MAX_MINERS, 0, 'power_law', 'Power law distribution'),
            (self.MAX_MINERS, 0, 'zero_most', 'Mostly zero rewards'),
            (self.MAX_MINERS, 0, 'high_variance', 'High variance rewards'),
        ]
        
        results = []
        for num_miners, vault_pos, dist_type, scenario_name in test_scenarios:
            result = self.test_single_scenario(num_miners, vault_pos, dist_type, scenario_name)
            results.append(result)
            self.results.append(result)
        
        return results
    
    def test_performance_scaling(self):
        """Test performance scaling across different network sizes"""
        print(f"\nPERFORMANCE SCALING TEST")
        print("=" * 70)
        print("Testing execution time scaling from 1 to 255 miners")
        
        # Test different network sizes
        network_sizes = [1, 10, 50, 100, 200, 255]
        performance_results = []
        
        for size in network_sizes:
            print(f"\nTesting {size} miners...")
            
            # Run multiple iterations for better timing
            iterations = 10
            times = []
            
            for i in range(iterations):
                hotkeys = self.generate_hotkeys(size, 0)
                validator = MockValidator("vault_hotkey", hotkeys)
                rewards = self.generate_rewards('random', size, seed=i)
                uids = list(range(size))
                
                start_time = time.time()
                adjusted_rewards = apply_vault_reward_distribution(validator, rewards, uids)
                execution_time = time.time() - start_time
                times.append(execution_time)
            
            avg_time = np.mean(times)
            std_time = np.std(times)
            
            perf_result = {
                'network_size': size,
                'avg_time_ms': avg_time * 1000,
                'std_time_ms': std_time * 1000,
                'min_time_ms': min(times) * 1000,
                'max_time_ms': max(times) * 1000
            }
            
            performance_results.append(perf_result)
            
            print(f"  Average time: {avg_time*1000:.3f}ms (±{std_time*1000:.3f}ms)")
            print(f"  Range: {min(times)*1000:.3f}ms - {max(times)*1000:.3f}ms")
        
        return performance_results
    
    def test_edge_cases_max_size(self):
        """Test edge cases with maximum network size"""
        print(f"\nEDGE CASES TEST (255 MINERS)")
        print("=" * 70)
        
        edge_cases = [
            (self.MAX_MINERS, 0, 'zero_most', 'Almost all zero rewards'),
            (self.MAX_MINERS, 0, 'high_variance', 'Extreme reward variance'),
            (self.MAX_MINERS, 0, 'uniform', 'All rewards exactly equal'),
        ]
        
        results = []
        for num_miners, vault_pos, dist_type, scenario_name in edge_cases:
            result = self.test_single_scenario(num_miners, vault_pos, dist_type, scenario_name)
            results.append(result)
            self.results.append(result)
        
        return results
    
    def run_comprehensive_max_test(self):
        """Run comprehensive maximum network size test"""
        print("COMPREHENSIVE MAXIMUM NETWORK SIZE TEST")
        print("=" * 70)
        print(f"Testing vault reward distribution at maximum scale ({self.MAX_MINERS} miners)")
        
        # Run all test suites
        max_results = self.test_maximum_network_size()
        perf_results = self.test_performance_scaling()
        edge_results = self.test_edge_cases_max_size()
        
        # Summary
        print(f"\n{'='*70}")
        print("MAXIMUM NETWORK SIZE TEST SUMMARY")
        print(f"{'='*70}")
        
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r['all_correct'])
        failed_tests = total_tests - passed_tests
        
        print(f"Total tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Success rate: {passed_tests/total_tests*100:.1f}%")
        
        if failed_tests > 0:
            print(f"\nFailed tests:")
            for result in self.results:
                if not result['all_correct']:
                    print(f"  {result['scenario_name']}: {result['num_miners']} miners")
        
        # Performance summary
        print(f"\nPerformance Summary:")
        max_size_result = perf_results[-1]  # 255 miners result
        print(f"  255 miners: {max_size_result['avg_time_ms']:.3f}ms average")
        print(f"  Time per miner: {max_size_result['avg_time_ms']/255:.6f}ms")
        print(f"  Theoretical max (1000 miners): ~{max_size_result['avg_time_ms']*1000/255:.1f}ms")
        
        return {
            'test_results': self.results,
            'performance_results': perf_results,
            'passed_tests': passed_tests,
            'total_tests': total_tests,
            'success_rate': passed_tests/total_tests*100
        }


def main():
    """Main test runner"""
    tester = MaxNetworkTester()
    results = tester.run_comprehensive_max_test()
    
    # Return exit code based on test results
    return 0 if results['success_rate'] == 100 else 1


if __name__ == "__main__":
    exit_code = main()
    exit(exit_code)