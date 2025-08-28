# DockerController 测试指南

本文档说明如何测试DockerController类的功能。

## 测试文件概述

### 1. `test_docker_controller_unit.py`
- **单元测试**：使用Mock对象，不需要实际的Docker环境
- **优点**：运行快速，无需Docker环境
- **测试内容**：API调用逻辑、错误处理、参数验证等

### 2. `test_docker_controller.py`
- **集成测试**：使用真实的Docker环境
- **优点**：测试真实功能，包括Docker交互
- **要求**：需要Docker守护进程运行
- **测试内容**：完整的容器生命周期、文件传输、进程管理等

## 运行测试

### 安装测试依赖

```bash
pip install pytest pytest-cov pytest-mock docker
```

### 使用测试运行器

我们提供了便捷的测试运行器 `run_tests.py`：

```bash
# 检查Docker是否可用
python run_tests.py --check-docker

# 运行单元测试（推荐，无需Docker）
python run_tests.py unit

# 运行集成测试（需要Docker）
python run_tests.py integration

# 运行慢速测试
python run_tests.py slow

# 运行所有测试
python run_tests.py all

# 运行特定测试
python run_tests.py -k "test_container_lifecycle"

# 生成测试覆盖率报告
python run_tests.py coverage
```

### 直接使用pytest

```bash
# 单元测试
pytest test_docker_controller_unit.py -v

# 集成测试
pytest test_docker_controller.py -v

# 排除慢测试
pytest test_docker_controller.py -m "not slow" -v

# 只运行慢测试
pytest test_docker_controller.py -m "slow" -v

# 运行特定测试
pytest -k "test_file_upload" -v

# 生成覆盖率报告
pytest --cov=docker_controller --cov-report=html
```

## 测试环境要求

### 单元测试
- Python 3.7+
- pytest
- pytest-mock

### 集成测试
- Python 3.7+
- Docker CE/EE
- pytest
- docker Python库
- 网络连接（用于拉取镜像）

## 测试覆盖的功能

### ✅ 容器管理
- [x] 容器启动和停止
- [x] 容器状态查询
- [x] 容器日志获取
- [x] 容器删除
- [x] 端口映射和卷挂载

### ✅ 进程管理
- [x] 进程启动和停止
- [x] 进程状态监控
- [x] 自动重启功能
- [x] 进程生命周期管理
- [x] 重复进程名处理

### ✅ 命令执行
- [x] 同步命令执行
- [x] 命令结果获取
- [x] 错误处理

### ✅ 文件传输
- [x] 文件上传（单个文件和目录）
- [x] 文件下载
- [x] 直接写入文件内容
- [x] 读取文件内容
- [x] 大文件传输

### ✅ 文件管理
- [x] 文件存在性检查
- [x] 目录创建
- [x] 文件和目录删除
- [x] 目录内容列表

### ✅ 错误处理
- [x] 容器未启动时的错误处理
- [x] 网络异常处理
- [x] 文件操作异常处理
- [x] Docker API异常处理

### ✅ 资源管理
- [x] 上下文管理器
- [x] 资源清理
- [x] 内存管理

## 测试结果解读

### 成功输出示例
```
============================= test session starts ==============================
collecting ... collected 25 items

test_docker_controller_unit.py::TestDockerControllerUnit::test_initialization PASSED
test_docker_controller_unit.py::TestDockerControllerUnit::test_start_container_success PASSED
...
============================== 25 passed in 2.34s ===============================
```

### 跳过测试
如果Docker不可用，集成测试会被自动跳过：
```
test_docker_controller.py::TestDockerController::test_docker_connection SKIPPED
```

### 测试覆盖率
运行覆盖率测试后，会生成HTML报告在 `htmlcov/` 目录中。

## 故障排除

### 常见问题

1. **Docker连接失败**
   ```
   docker.errors.DockerException: Error while fetching server API version
   ```
   - 解决：确保Docker守护进程正在运行
   - 检查：`docker ps` 命令是否可用

2. **权限问题**
   ```
   PermissionError: [Errno 13] Permission denied
   ```
   - 解决：确保当前用户在docker组中，或使用sudo

3. **镜像拉取失败**
   ```
   docker.errors.ImageNotFound: 404 Client Error
   ```
   - 解决：检查网络连接，或预先拉取测试镜像：`docker pull alpine:latest`

4. **端口占用**
   ```
   docker.errors.APIError: port is already allocated
   ```
   - 解决：停止占用端口的容器，或使用不同的端口

### 调试技巧

1. **增加日志详细程度**
   ```bash
   pytest -v --tb=long --log-cli-level=DEBUG
   ```

2. **运行单个测试**
   ```bash
   pytest test_docker_controller.py::TestDockerController::test_container_lifecycle -v
   ```

3. **保留测试容器（调试用）**
   修改测试代码，注释掉cleanup部分

4. **检查Docker状态**
   ```bash
   docker ps -a  # 查看所有容器
   docker images  # 查看镜像
   docker system df  # 查看磁盘使用
   ```

## 持续集成

测试已配置为适合CI/CD环境：

- 单元测试始终运行（无需Docker）
- 集成测试仅在Docker可用时运行
- 支持测试并行化
- 生成XML和HTML格式的测试报告

### GitHub Actions示例
```yaml
name: Test
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: 3.9
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
    - name: Run tests
      run: |
        python controller/run_tests.py all
```

## 性能测试

对于性能敏感的操作，我们提供了专门的性能测试：

```bash
# 运行包括性能测试的完整测试套件
pytest test_docker_controller.py::TestDockerController::test_large_file_transfer -v
```

## 贡献测试

如果您想为项目贡献测试代码：

1. 遵循现有的测试模式
2. 为新功能添加相应的单元测试和集成测试
3. 确保测试覆盖率不下降
4. 添加适当的文档和注释 