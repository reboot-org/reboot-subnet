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

import pytest
import numpy as np
import sys
import os
from unittest.mock import Mock, MagicMock, patch

# Add the project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from reboot.validator.forward import apply_vault_reward_distribution


class MockValidator:
    """Mock validator class for testing"""
    def __init__(self, vault_hotkey=None, metagraph_hotkeys=None):
        self.vault_hotkey = vault_hotkey or "5D4qQYr5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z"
        self.metagraph = Mock()
        
        # Set up metagraph hotkeys
        if metagraph_hotkeys is None:
            metagraph_hotkeys = [
                "5D4qQYr5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z",  # vault
                "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY",  # miner1
                "5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty",  # miner2
                "5FLSigC9K7N1zqzP1n2V6Y4wJjHh1QN2WXwLsEfXqjKj2gXW",  # miner3
            ]
        
        self.metagraph.hotkeys = metagraph_hotkeys


class TestVaultRewardDistribution:
    """Test suite for vault reward distribution logic"""
    
    @pytest.fixture
    def mock_validator(self):
        """Create a mock validator with default configuration"""
        return MockValidator()
    
    @pytest.fixture
    def sample_rewards(self):
        """Sample rewards for testing"""
        return np.array([0.8, 0.6, 0.4, 0.2])
    
    @pytest.fixture
    def sample_uids(self):
        """Sample UIDs for testing"""
        return [0, 1, 2, 3]
    
    def test_vault_reward_distribution_basic(self, mock_validator, sample_rewards, sample_uids):
        """Test basic vault reward distribution functionality"""
        # Apply vault reward distribution
        adjusted_rewards = apply_vault_reward_distribution(
            mock_validator, sample_rewards, sample_uids
        )
        
        # Calculate expected values
        total_reward = np.sum(sample_rewards)  # 0.8 + 0.6 + 0.4 + 0.2 = 2.0
        expected_vault_reward = total_reward * 0.2  # 2.0 * 0.2 = 0.4
        expected_remaining_pool = total_reward * 0.8  # 2.0 * 0.8 = 1.6
        
        # Verify vault gets 20% of total rewards
        assert adjusted_rewards[0] == pytest.approx(expected_vault_reward, rel=1e-6)
        
        # Verify total rewards remain the same
        assert np.sum(adjusted_rewards) == pytest.approx(total_reward, rel=1e-6)
        
        # Verify remaining rewards are distributed among other miners
        non_vault_rewards = adjusted_rewards[1:]
        assert np.sum(non_vault_rewards) == pytest.approx(expected_remaining_pool, rel=1e-6)
    
    def test_vault_reward_distribution_proportional(self, mock_validator, sample_rewards, sample_uids):
        """Test that non-vault rewards are distributed proportionally"""
        # Apply vault reward distribution
        adjusted_rewards = apply_vault_reward_distribution(
            mock_validator, sample_rewards, sample_uids
        )
        
        # Calculate expected proportional distribution
        total_reward = np.sum(sample_rewards)
        remaining_pool = total_reward * 0.8  # 1.6
        
        # Original non-vault rewards: [0.6, 0.4, 0.2] = 1.2
        non_vault_original = sample_rewards[1:]
        non_vault_original_sum = np.sum(non_vault_original)  # 1.2
        
        # Expected proportional rewards:
        # miner1: (0.6 / 1.2) * 1.6 = 0.8
        # miner2: (0.4 / 1.2) * 1.6 ≈ 0.5333
        # miner3: (0.2 / 1.2) * 1.6 ≈ 0.2667
        expected_miner1 = (0.6 / non_vault_original_sum) * remaining_pool
        expected_miner2 = (0.4 / non_vault_original_sum) * remaining_pool
        expected_miner3 = (0.2 / non_vault_original_sum) * remaining_pool
        
        assert adjusted_rewards[1] == pytest.approx(expected_miner1, rel=1e-6)
        assert adjusted_rewards[2] == pytest.approx(expected_miner2, rel=1e-6)
        assert adjusted_rewards[3] == pytest.approx(expected_miner3, rel=1e-6)
    
    def test_vault_not_found_in_metagraph(self, sample_rewards, sample_uids):
        """Test behavior when vault hotkey is not in metagraph"""
        # Create validator with vault hotkey not in metagraph
        validator = MockValidator(
            vault_hotkey="nonexistent_hotkey",
            metagraph_hotkeys=[
                "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY",  # miner1
                "5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty",  # miner2
            ]
        )
        
        # Should return original rewards unchanged
        adjusted_rewards = apply_vault_reward_distribution(
            validator, sample_rewards, sample_uids
        )
        
        np.testing.assert_array_equal(adjusted_rewards, sample_rewards)
    
    def test_vault_not_in_miner_uids(self, mock_validator, sample_rewards):
        """Test behavior when vault UID is not in miner_uids"""
        # Use miner_uids that don't include the vault
        miner_uids = [1, 2, 3]  # Missing vault UID 0
        
        # Should return original rewards unchanged
        adjusted_rewards = apply_vault_reward_distribution(
            mock_validator, sample_rewards, miner_uids
        )
        
        np.testing.assert_array_equal(adjusted_rewards, sample_rewards)
    
    def test_zero_rewards_distribution(self, mock_validator, sample_uids):
        """Test behavior when all rewards are zero"""
        zero_rewards = np.array([0.0, 0.0, 0.0, 0.0])
        
        adjusted_rewards = apply_vault_reward_distribution(
            mock_validator, zero_rewards, sample_uids
        )
        
        # Vault should get 0 (20% of 0)
        assert adjusted_rewards[0] == 0.0
        
        # Other miners should get 0 (equal distribution of 0)
        np.testing.assert_array_equal(adjusted_rewards[1:], [0.0, 0.0, 0.0])
    
    def test_single_vault_only(self, mock_validator):
        """Test behavior when only vault is present"""
        rewards = np.array([1.0])
        uids = [0]
        
        adjusted_rewards = apply_vault_reward_distribution(
            mock_validator, rewards, uids
        )
        
        # Vault should get the full reward (20% of 1.0 = 0.2, but no other miners to distribute remaining 80%)
        # In this case, vault gets the full reward
        assert adjusted_rewards[0] == 1.0
    
    def test_non_vault_zero_rewards(self, mock_validator, sample_uids):
        """Test behavior when non-vault miners have zero rewards"""
        rewards = np.array([0.5, 0.0, 0.0, 0.0])  # Only vault has reward
        
        adjusted_rewards = apply_vault_reward_distribution(
            mock_validator, rewards, sample_uids
        )
        
        total_reward = np.sum(rewards)  # 0.5
        expected_vault_reward = total_reward * 0.2  # 0.1
        expected_remaining_pool = total_reward * 0.8  # 0.4
        
        # Vault gets 20%
        assert adjusted_rewards[0] == pytest.approx(expected_vault_reward, rel=1e-6)
        
        # Remaining 80% should be distributed equally among non-vault miners
        expected_equal_share = expected_remaining_pool / 3  # 3 non-vault miners
        np.testing.assert_array_almost_equal(
            adjusted_rewards[1:], 
            [expected_equal_share, expected_equal_share, expected_equal_share]
        )
    
    def test_different_vault_positions(self):
        """Test vault reward distribution with vault in different positions"""
        # Test vault at position 1
        validator = MockValidator(
            vault_hotkey="5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"
        )
        rewards = np.array([0.3, 0.7, 0.4, 0.6])
        uids = [0, 1, 2, 3]
        
        adjusted_rewards = apply_vault_reward_distribution(validator, rewards, uids)
        
        total_reward = np.sum(rewards)  # 2.0
        expected_vault_reward = total_reward * 0.2  # 0.4
        
        # Vault at position 1 should get 0.4
        assert adjusted_rewards[1] == pytest.approx(expected_vault_reward, rel=1e-6)
    
    def test_large_rewards_scaling(self, mock_validator, sample_uids):
        """Test with large reward values to ensure proper scaling"""
        large_rewards = np.array([100.0, 80.0, 60.0, 40.0])
        
        adjusted_rewards = apply_vault_reward_distribution(
            mock_validator, large_rewards, sample_uids
        )
        
        total_reward = np.sum(large_rewards)  # 280.0
        expected_vault_reward = total_reward * 0.2  # 56.0
        expected_remaining_pool = total_reward * 0.8  # 224.0
        
        assert adjusted_rewards[0] == pytest.approx(expected_vault_reward, rel=1e-6)
        assert np.sum(adjusted_rewards) == pytest.approx(total_reward, rel=1e-6)
        assert np.sum(adjusted_rewards[1:]) == pytest.approx(expected_remaining_pool, rel=1e-6)
    
    def test_negative_rewards(self, mock_validator, sample_uids):
        """Test behavior with negative rewards (should handle gracefully)"""
        mixed_rewards = np.array([0.5, -0.1, 0.3, -0.2])
        
        # Should not crash and should handle negative values appropriately
        adjusted_rewards = apply_vault_reward_distribution(
            mock_validator, mixed_rewards, sample_uids
        )
        
        # Total reward calculation should handle negative values
        total_reward = np.sum(mixed_rewards)  # 0.5
        expected_vault_reward = total_reward * 0.2  # 0.1
        
        assert adjusted_rewards[0] == pytest.approx(expected_vault_reward, rel=1e-6)
    
    def test_floating_point_precision(self, mock_validator, sample_uids):
        """Test floating point precision with very small values"""
        small_rewards = np.array([1e-10, 2e-10, 3e-10, 4e-10])
        
        adjusted_rewards = apply_vault_reward_distribution(
            mock_validator, small_rewards, sample_uids
        )
        
        total_reward = np.sum(small_rewards)  # 1e-9
        expected_vault_reward = total_reward * 0.2  # 2e-10
        
        assert adjusted_rewards[0] == pytest.approx(expected_vault_reward, rel=1e-6)
        assert np.sum(adjusted_rewards) == pytest.approx(total_reward, rel=1e-6)
    
    def test_empty_arrays(self):
        """Test behavior with empty arrays"""
        validator = MockValidator()
        empty_rewards = np.array([])
        empty_uids = []
        
        # Should handle empty arrays gracefully
        adjusted_rewards = apply_vault_reward_distribution(
            validator, empty_rewards, empty_uids
        )
        
        assert len(adjusted_rewards) == 0
        assert isinstance(adjusted_rewards, np.ndarray)
    
    def test_mismatched_lengths(self, mock_validator):
        """Test behavior when rewards and uids have different lengths"""
        rewards = np.array([0.5, 0.3, 0.2])
        uids = [0, 1, 2, 3]  # Different length
        
        # Should handle mismatched lengths gracefully
        adjusted_rewards = apply_vault_reward_distribution(
            mock_validator, rewards, uids
        )
        
        # Should return original rewards if lengths don't match
        np.testing.assert_array_equal(adjusted_rewards, rewards)
    
    def test_reward_preservation_total(self, mock_validator, sample_rewards, sample_uids):
        """Test that total reward sum is preserved after distribution"""
        original_total = np.sum(sample_rewards)
        
        adjusted_rewards = apply_vault_reward_distribution(
            mock_validator, sample_rewards, sample_uids
        )
        
        adjusted_total = np.sum(adjusted_rewards)
        
        # Total should be preserved (within floating point precision)
        assert adjusted_total == pytest.approx(original_total, rel=1e-10)
    
    @patch('reboot.validator.forward.bt.logging')
    def test_logging_behavior(self, mock_logging, mock_validator, sample_rewards, sample_uids):
        """Test that proper logging occurs during distribution"""
        apply_vault_reward_distribution(
            mock_validator, sample_rewards, sample_uids
        )
        
        # Verify that logging methods were called
        assert mock_logging.info.called
        # Check that some expected log messages were present
        log_calls = [call[0][0] for call in mock_logging.info.call_args_list]
        assert any("Vault reward distribution applied" in call for call in log_calls)
        assert any("Total reward:" in call for call in log_calls)
        assert any("Vault reward (20%):" in call for call in log_calls)
    
    def test_vault_hotkey_attribute_missing(self, sample_rewards, sample_uids):
        """Test behavior when vault_hotkey attribute is missing"""
        validator = MockValidator()
        delattr(validator, 'vault_hotkey')  # Remove the attribute
        
        # Should return original rewards unchanged
        adjusted_rewards = apply_vault_reward_distribution(
            validator, sample_rewards, sample_uids
        )
        
        np.testing.assert_array_equal(adjusted_rewards, sample_rewards)


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])