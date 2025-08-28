#!/usr/bin/env python3
"""
Test Runner Script
Provides different test execution options
"""

import sys
import subprocess
import argparse
import docker


def check_docker_available():
    """Check if Docker is available"""
    try:
        client = docker.from_env()
        client.ping()
        return True
    except Exception as e:
        print(f"Docker not available: {e}")
        return False


def run_unit_tests():
    """Run unit tests (using Mock, no Docker required)"""
    print("Running unit tests (Mock)...")
    cmd = [
        sys.executable, "-m", "pytest", 
        "test_docker_controller_unit.py", 
        "-v", "--tb=short"
    ]
    return subprocess.run(cmd).returncode


def run_integration_tests():
    """运行集成测试（需要Docker环境）"""
    if not check_docker_available():
        print("Skipping integration tests: Docker not available")
        return 0
    
    print("Running integration tests (real Docker environment)...")
    cmd = [
        sys.executable, "-m", "pytest", 
        "test_docker_controller.py", 
        "-v", "--tb=short",
        "-m", "not slow"  # Exclude slow tests
    ]
    return subprocess.run(cmd).returncode


def run_slow_tests():
    """运行慢速测试"""
    if not check_docker_available():
        print("跳过慢速测试：Docker不可用")
        return 0
    
    print("运行慢速测试...")
    cmd = [
        sys.executable, "-m", "pytest", 
        "test_docker_controller.py", 
        "-v", "--tb=short",
        "-m", "slow"
    ]
    return subprocess.run(cmd).returncode


def run_all_tests():
    """运行所有测试"""
    print("Running all tests...")
    
    # Run unit tests first
    unit_result = run_unit_tests()
    if unit_result != 0:
        print("Unit tests failed")
        return unit_result
    
    # Then run integration tests
    integration_result = run_integration_tests()
    if integration_result != 0:
        print("Integration tests failed")
        return integration_result
    
    print("All tests passed!")
    return 0


def run_coverage():
    """运行测试覆盖率分析"""
    print("运行测试覆盖率分析...")
    
    # 检查是否安装了pytest-cov
    try:
        import pytest_cov
    except ImportError:
        print("请安装pytest-cov: pip install pytest-cov")
        return 1
    
    cmd = [
        sys.executable, "-m", "pytest",
        "test_docker_controller_unit.py",
        "--cov=docker_controller",
        "--cov-report=html",
        "--cov-report=term-missing",
        "-v"
    ]
    
    if check_docker_available():
        cmd.append("test_docker_controller.py")
        cmd.extend(["-m", "not slow"])
    
    return subprocess.run(cmd).returncode


def run_specific_test(test_name):
    """运行特定的测试"""
    print(f"运行特定测试: {test_name}")
    
    # 先在单元测试中查找
    cmd = [
        sys.executable, "-m", "pytest",
        "test_docker_controller_unit.py",
        "-k", test_name,
        "-v"
    ]
    result = subprocess.run(cmd)
    
    # 如果Docker可用，也在集成测试中查找
    if check_docker_available():
        cmd = [
            sys.executable, "-m", "pytest",
            "test_docker_controller.py",
            "-k", test_name,
            "-v"
        ]
        integration_result = subprocess.run(cmd)
        return max(result.returncode, integration_result.returncode)
    
    return result.returncode


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="DockerController测试运行器")
    parser.add_argument(
        "test_type",
        choices=["unit", "integration", "slow", "all", "coverage"],
        nargs="?",
        default="unit",
        help="测试类型 (默认: unit)"
    )
    parser.add_argument(
        "-k", "--keyword",
        help="运行包含特定关键字的测试"
    )
    parser.add_argument(
        "--check-docker",
        action="store_true",
        help="检查Docker是否可用"
    )
    
    args = parser.parse_args()
    
    if args.check_docker:
        available = check_docker_available()
        print(f"Docker availability: {'Yes' if available else 'No'}")
        return 0 if available else 1
    
    if args.keyword:
        return run_specific_test(args.keyword)
    
    if args.test_type == "unit":
        return run_unit_tests()
    elif args.test_type == "integration":
        return run_integration_tests()
    elif args.test_type == "slow":
        return run_slow_tests()
    elif args.test_type == "all":
        return run_all_tests()
    elif args.test_type == "coverage":
        return run_coverage()


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code) 