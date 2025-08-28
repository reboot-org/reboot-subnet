# Docker控制器

这个模块提供了一个强大的Docker容器控制器类，用于管理Docker容器的生命周期以及容器内进程的管理。

## 功能特性

- 🐳 **容器管理**: 启动、停止、移除Docker容器
- 🔄 **进程管理**: 在容器内启动、停止、监控进程
- 🔁 **自动重启**: 支持进程异常退出后自动重启
- 📊 **状态监控**: 实时监控容器和进程状态
- 📋 **日志管理**: 获取容器日志和进程输出
- 📁 **文件传输**: 向容器内上传文件或从容器内下载文件
- 📝 **文件管理**: 创建、删除、列出容器内的文件和目录
- 🛡️ **资源清理**: 自动清理资源，支持上下文管理器

## 安装依赖

```bash
pip install docker>=6.0.0
```

确保Docker守护进程正在运行，并且当前用户有权限访问Docker。

## 基本使用

### 1. 导入和初始化

```python
from controller import DockerController

# 创建控制器实例
controller = DockerController(
    container_name="my_container",
    image="ubuntu:20.04"
)
```

### 2. 启动容器

```python
# 启动容器，配置端口映射、卷挂载和环境变量
success = controller.start_container(
    ports={'8080/tcp': 8080},
    volumes={'/host/path': {'bind': '/container/path', 'mode': 'rw'}},
    environment={'ENV_VAR': 'value'},
    command="tail -f /dev/null"  # 保持容器运行
)
```

### 3. 执行命令

```python
# 在容器中执行单个命令
result = controller.execute_command("ls -la /")
if result:
    print(result.output.decode('utf-8'))
```

### 4. 启动和管理进程

```python
# 启动一个长期运行的进程
controller.start_process(
    process_name="web_server",
    command="python3 -m http.server 8000",
    auto_restart=True,      # 自动重启
    restart_delay=5         # 重启延迟
)

# 启动另一个进程
controller.start_process(
    process_name="monitor",
    command="while true; do date; sleep 10; done",
    auto_restart=False
)
```

### 5. 监控状态

```python
# 查看容器状态
container_status = controller.get_container_status()
print(f"容器状态: {container_status['status']}")

# 查看所有进程状态
processes = controller.list_processes()
for name, status in processes.items():
    print(f"进程 {name}: {'运行中' if status['running'] else '已停止'}")

# 查看特定进程状态
process_status = controller.get_process_status("web_server")
if process_status:
    print(f"运行时间: {process_status['uptime']:.1f}秒")
    print(f"重启次数: {process_status['restart_count']}")
```

### 6. 文件传输和管理

```python
# 上传本地文件到容器
controller.upload_file("/local/path/file.txt", "/container/path/file.txt")

# 上传目录到容器
controller.upload_file("/local/directory", "/container/directory")

# 直接写入文件内容到容器
controller.upload_file_content("文件内容", "/container/path/file.txt")

# 从容器下载文件到本地
controller.download_file("/container/path/file.txt", "/local/path/file.txt")

# 读取容器内文件内容
content = controller.download_file_content("/container/path/file.txt")
if content:
    print(content.decode('utf-8'))

# 检查文件是否存在
if controller.file_exists("/container/path/file.txt"):
    print("文件存在")

# 列出目录内容
files = controller.list_files("/container/path")
for file_info in files:
    print(f"{file_info['name']}: {file_info['size']} bytes")

# 创建目录
controller.create_directory("/container/new_directory")

# 删除文件或目录
controller.remove_file("/container/path/file.txt")
controller.remove_file("/container/directory", recursive=True)
```

### 7. 停止和清理

```python
# 停止特定进程
controller.stop_process("monitor")

# 停止容器
controller.stop_container()

# 移除容器
controller.remove_container()

# 清理所有资源
controller.cleanup()
```

## 高级使用

### 使用上下文管理器

```python
# 使用上下文管理器自动管理资源
with DockerController("my_container", "python:3.9") as controller:
    controller.start_container(command="tail -f /dev/null")
    
    # 启动应用程序
    controller.start_process(
        process_name="app",
        command="python app.py",
        auto_restart=True
    )
    
    # 做一些工作...
    time.sleep(30)
    
# 自动清理资源
```

### 自定义日志记录器

```python
import logging

# 创建自定义日志记录器
logger = logging.getLogger("my_docker_controller")
logger.setLevel(logging.DEBUG)

# 使用自定义日志记录器
controller = DockerController(
    container_name="my_container",
    image="ubuntu:20.04",
    logger=logger
)
```

## API参考

### DockerController类

#### 构造函数
```python
DockerController(container_name: str, image: str, logger: Optional[logging.Logger] = None)
```

#### 主要方法

**容器管理**
- `start_container(**kwargs) -> bool`: 启动容器
- `stop_container(timeout: int = 10) -> bool`: 停止容器
- `remove_container(force: bool = False) -> bool`: 移除容器
- `get_container_status() -> Optional[Dict]`: 获取容器状态
- `get_container_logs(tail: int = 100) -> str`: 获取容器日志

**进程管理**
- `execute_command(command: str, **kwargs) -> Optional[Any]`: 执行命令
- `start_process(process_name: str, command: str, auto_restart: bool = False, **kwargs) -> bool`: 启动进程
- `stop_process(process_name: str) -> bool`: 停止进程
- `get_process_status(process_name: str) -> Optional[Dict]`: 获取进程状态
- `list_processes() -> Dict`: 列出所有进程

**文件传输**
- `upload_file(local_path: Union[str, Path], container_path: str, **kwargs) -> bool`: 上传文件
- `upload_file_content(content: Union[str, bytes], container_path: str, mode: int = 0o644) -> bool`: 写入文件内容
- `download_file(container_path: str, local_path: Union[str, Path], **kwargs) -> bool`: 下载文件
- `download_file_content(container_path: str) -> Optional[bytes]`: 读取文件内容

**文件管理**
- `file_exists(container_path: str) -> bool`: 检查文件是否存在
- `list_files(container_path: str = "/") -> Optional[List[Dict]]`: 列出文件
- `create_directory(container_path: str, parents: bool = True) -> bool`: 创建目录
- `remove_file(container_path: str, recursive: bool = False, force: bool = False) -> bool`: 删除文件

**资源管理**
- `cleanup()`: 清理资源

## 使用示例

查看 `example_usage.py` 文件获取完整的使用示例，包括：

- 基本的容器启动和管理
- 进程生命周期管理
- 自动重启配置
- 状态监控
- 资源清理

运行示例：

```bash
python controller/example_usage.py
```

## 注意事项

1. **Docker权限**: 确保运行用户有Docker访问权限
2. **镜像可用性**: 确保指定的Docker镜像已下载或可从仓库获取
3. **端口冲突**: 注意端口映射时避免冲突
4. **资源清理**: 使用完毕后记得调用`cleanup()`或使用上下文管理器
5. **进程监控**: 自动重启功能依赖于进程状态检查，确保命令能正确执行

## 故障排除

### 常见问题

1. **容器启动失败**
   - 检查Docker守护进程是否运行
   - 检查镜像是否存在
   - 检查端口是否被占用

2. **进程无法启动**
   - 检查容器是否正在运行
   - 检查命令语法是否正确
   - 检查容器内是否有所需的程序

3. **进程监控异常**
   - 检查Docker API连接
   - 检查进程是否正常退出
   - 查看日志获取详细错误信息

### 调试建议

- 设置日志级别为DEBUG获取详细信息
- 使用`get_container_logs()`查看容器日志
- 使用`execute_command("ps aux")`检查容器内进程状态 