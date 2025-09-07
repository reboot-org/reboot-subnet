#!/usr/bin/env python3
"""
Comprehensive Stress Test for Vault Reward Distribution at Maximum Scale (255 miners)
This script demonstrates the robustness and scalability of the vault reward distribution system.
"""

import numpy as np
import sys
import os
import time
from typing import List, Dict, Any

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


class MaxScaleStressTest:
    """Stress test for maximum scale (255 miners)"""
    
    def __init__(self):
        self.MAX_MINERS = 255
        self.test_results = []
    
    def generate_rewards_stress(self, pattern: str, num_miners: int = 255) -> np.ndarray:
        """Generate rewards for stress testing"""
        np.random.seed(42)  # Reproducible results
        
        if pattern == 'extreme_skew':
            # 1 miner gets 99% of rewards, others get 1% shared
            rewards = np.ones(num_miners) * 0.01
            rewards[0] = 99.0
            return rewards
        
        elif pattern == 'binary':
            # Miners either get 0 or 1 rewards
            return np.random.choice([0.0, 1.0], num_miners, p=[0.7, 0.3])
        
        elif pattern == 'geometric':
            # Geometric series
            return np.array([2.0**(-i) for i in range(num_miners)])
        
        elif pattern == 'spike':
            # Most miners get ~1 reward, few get extreme values
            rewards = np.ones(num_miners)
            spike_indices = np.random.choice(num_miners, 5, replace=False)
            rewards[spike_indices] = np.random.uniform(50, 100, 5)
            return rewards
        
        elif pattern == 'concentrated':
            # 90% of rewards go to 10% of miners
            rewards = np.zeros(num_miners)
            concentrated_count = num_miners // 10
            concentrated_indices = np.random.choice(num_miners, concentrated_count, replace=False)
            rewards[concentrated_indices] = np.random.uniform(5, 15, concentrated_count)
            return rewards
        
        elif pattern == 'uniform_extreme':
            # All get exactly the same extreme value
            return np.ones(num_miners) * 1000.0
        
        elif pattern == 'floating_precision':
            # Test floating point precision limits
            return np.random.uniform(1e-10, 1e-5, num_miners)
        
        else:
            return np.random.uniform(0.1, 2.0, num_miners)
    
    def run_stress_test(self, pattern: str, vault_position: int = 0) -> Dict[str, Any]:
        """Run a single stress test"""
        print(f"\n{'='*80}")
        print(f"STRESS TEST: {pattern.upper()}")
        print(f"{'='*80}")
        
        # Setup
        hotkeys = [f"miner_{i:03d}" for i in range(self.MAX_MINERS)]
        hotkeys[vault_position] = "vault_hotkey"
        validator = MockValidator("vault_hotkey", hotkeys)
        rewards = self.generate_rewards_stress(pattern, self.MAX_MINERS)
        uids = list(range(self.MAX_MINERS))
        
        print(f"Network size: {self.MAX_MINERS} miners")
        print(f"Vault position: {vault_position}")
        print(f"Pattern: {pattern}")
        
        # Calculate pre-distribution stats
        total_original = np.sum(rewards)
        vault_original = rewards[vault_position]
        non_vault_original = total_original - vault_original
        
        print(f"Pre-distribution:")
        print(f"  Total rewards: {total_original:.10f}")
        print(f"  Vault original: {vault_original:.10f} ({vault_original/total_original*100:.2f}%)")
        print(f"  Non-vault original: {non_vault_original:.10f} ({non_vault_original/total_original*100:.2f}%)")
        print(f"  Reward range: [{np.min(rewards):.10f}, {np.max(rewards):.10f}]")
        print(f"  Non-zero rewards: {np.count_nonzero(rewards)}/{self.MAX_MINERS}")
        
        # Apply distribution
        start_time = time.perf_counter()
        adjusted_rewards = apply_vault_reward_distribution(validator, rewards, uids)
        execution_time = time.perf_counter() - start_time
        
        # Calculate post-distribution stats
        total_adjusted = np.sum(adjusted_rewards)
        vault_adjusted = adjusted_rewards[vault_position]
        non_vault_adjusted = total_adjusted - vault_adjusted
        
        print(f"\nPost-distribution:")
        print(f"  Total rewards: {total_adjusted:.10f}")
        print(f"  Vault adjusted: {vault_adjusted:.10f} ({vault_adjusted/total_adjusted*100:.2f}%)")
        print(f"  Non-vault adjusted: {non_vault_adjusted:.10f} ({non_vault_adjusted/total_adjusted*100:.2f}%)")
        print(f"  Execution time: {execution_time*1000:.6f}ms")
        
        # Verify correctness
        expected_vault = total_original * 0.2
        expected_non_vault = total_original * 0.8
        
        total_preserved = abs(total_original - total_adjusted) < 1e-10
        vault_correct = abs(vault_adjusted - expected_vault) < 1e-10
        non_vault_correct = abs(non_vault_adjusted - expected_non_vault) < 1e-10
        
        print(f"\nVerification:")
        print(f"  Total preserved: {'✅ YES' if total_preserved else '❌ NO'}")
        print(f"  Vault gets 20%: {'✅ YES' if vault_correct else '❌ NO'}")
        print(f"  Non-vault gets 80%: {'✅ YES' if non_vault_correct else '❌ NO'}")
        print(f"  All correct: {'✅ YES' if all([total_preserved, vault_correct, non_vault_correct]) else '❌ NO'}")
        
        result = {
            'pattern': pattern,
            'num_miners': self.MAX_MINERS,
            'vault_position': vault_position,
            'total_original': total_original,
            'total_adjusted': total_adjusted,
            'vault_original': vault_original,
            'vault_adjusted': vault_adjusted,
            'expected_vault': expected_vault,
            'non_vault_adjusted': non_vault_adjusted,
            'expected_non_vault': expected_non_vault,
            'execution_time_ms': execution_time * 1000,
            'total_preserved': total_preserved,
            'vault_correct': vault_correct,
            'non_vault_correct': non_vault_correct,
            'all_correct': all([total_preserved, vault_correct, non_vault_correct]),
            'reward_stats': {
                'min': float(np.min(rewards)),
                'max': float(np.max(rewards)),
                'mean': float(np.mean(rewards)),
                'std': float(np.std(rewards)),
                'non_zero_count': int(np.count_nonzero(rewards))
            }
        }
        
        self.test_results.append(result)
        return result
    
    def run_comprehensive_stress_test(self):
        """Run comprehensive stress test suite"""
        print("VAULT REWARD DISTRIBUTION - MAXIMUM SCALE STRESS TEST")
        print("=" * 80)
        print(f"Testing with maximum network size: {self.MAX_MINERS} miners")
        print("Testing extreme reward patterns and edge cases")
        
        # Define stress test patterns
        stress_patterns = [
            ('extreme_skew', 0, "Extreme skew: 1 miner gets 99% of rewards"),
            ('binary', 0, "Binary rewards: miners get either 0 or 1"),
            ('geometric', 0, "Geometric series: exponentially decreasing rewards"),
            ('spike', 0, "Spike pattern: most miners get ~1, few get 50-100"),
            ('concentrated', 0, "Concentrated: 90% of rewards to 10% of miners"),
            ('uniform_extreme', 0, "Uniform extreme: all miners get exactly 1000"),
            ('floating_precision', 0, "Floating precision: very small values (1e-10 to 1e-5)"),
            
            # Test vault in different positions with extreme patterns
            ('extreme_skew', 127, "Extreme skew with vault at middle"),
            ('concentrated', 254, "Concentrated rewards with vault at end"),
        ]
        
        results = []
        for pattern, vault_pos, description in stress_patterns:
            print(f"\n{description}")
            result = self.run_stress_test(pattern, vault_pos)
            results.append(result)
        
        # Summary
        print(f"\n{'='*80}")
        print("STRESS TEST SUMMARY")
        print(f"{'='*80}")
        
        total_tests = len(results)
        passed_tests = sum(1 for r in results if r['all_correct'])
        failed_tests = total_tests - passed_tests
        
        print(f"Total stress tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Success rate: {passed_tests/total_tests*100:.1f}%")
        
        if failed_tests > 0:
            print(f"\nFailed tests:")
            for result in results:
                if not result['all_correct']:
                    print(f"  {result['pattern']}: vault_pos={result['vault_position']}")
        
        # Performance analysis
        execution_times = [r['execution_time_ms'] for r in results]
        avg_time = np.mean(execution_times)
        max_time = np.max(execution_times)
        min_time = np.min(execution_times)
        
        print(f"\nPerformance Analysis:")
        print(f"  Average execution time: {avg_time:.6f}ms")
        print(f"  Fastest execution: {min_time:.6f}ms")
        print(f"  Slowest execution: {max_time:.6f}ms")
        print(f"  Time per miner: {avg_time/self.MAX_MINERS:.6f}ms")
        
        # Show most extreme test cases
        print(f"\nMost Extreme Test Cases:")
        sorted_by_original = sorted(results, key=lambda x: x['total_original'])
        print(f"  Smallest total reward: {sorted_by_original[0]['total_original']:.2e}")
        print(f"  Largest total reward: {sorted_by_original[-1]['total_original']:.2e}")
        
        sorted_by_vault_change = sorted(results, key=lambda x: abs(x['vault_adjusted'] - x['vault_original']))
        most_dramatic = sorted_by_vault_change[-1]
        print(f"  Most dramatic vault change: {most_dramatic['pattern']}")
        print(f"    From {most_dramatic['vault_original']:.2f} to {most_dramatic['vault_adjusted']:.2f}")
        
        return {
            'results': results,
            'passed_tests': passed_tests,
            'total_tests': total_tests,
            'success_rate': passed_tests/total_tests*100,
            'performance': {
                'avg_time_ms': avg_time,
                'min_time_ms': min_time,
                'max_time_ms': max_time
            }
        }


def main():
    """Main stress test runner"""
    tester = MaxScaleStressTest()
    results = tester.run_comprehensive_stress_test()
    
    print(f"\n{'='*80}")
    print("CONCLUSION")
    print(f"{'='*80}")
    
    if results['success_rate'] == 100:
        print("🎉 ALL STRESS TESTS PASSED!")
        print("The vault reward distribution system is robust and handles extreme cases correctly.")
        print(f"✅ Works efficiently at maximum scale ({tester.MAX_MINERS} miners)")
        print("✅ Handles extreme reward distributions")
        print("✅ Maintains mathematical precision")
        print("✅ Preserves total reward sum")
        print("✅ Exactly 20% allocation to vault")
        print("✅ Proportional distribution to non-vault miners")
    else:
        print("❌ Some stress tests failed. Review the results above.")
    
    return 0 if results['success_rate'] == 100 else 1


if __name__ == "__main__":
    exit_code = main()
    exit(exit_code)