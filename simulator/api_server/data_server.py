import flask
from flask import Flask, jsonify
import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
import threading
import signal
import sys
import atexit
import collections # For OrderedDict checking

# --- 1. ROS Message Imports ---
# Import standard message types
from nav_msgs.msg import Odometry
from sensor_msgs.msg import Imu, JointState, BatteryState

# Import message types from irobot_create_msgs
# These are specific to robots like the Create 3 / TurtleBot 4 base
IROBOT_MSGS_AVAILABLE = False
try:
    from irobot_create_msgs.msg import WheelVels, DockStatus, HazardDetectionVector
    IROBOT_MSGS_AVAILABLE = True
except ImportError:
    print("WARNING: Could not import one or more messages from 'irobot_create_msgs' (WheelVels, DockStatus, HazardDetectionVector).", file=sys.stderr)
    print("         Subscriptions to related topics like /wheel_vels, /dock, /hazard_detection will be skipped.", file=sys.stderr)
    # Define placeholders if the import fails, so the rest of the script doesn't break
    # if somehow referenced, though the config will try to avoid this.
    class WheelVels: pass
    class DockStatus: pass
    class HazardDetectionVector: pass

# --- 2. ROS Message to Dictionary Conversion Utility ---
from rosidl_runtime_py.convert import message_to_ordereddict

def ordered_dict_to_plain_dict(data):
    if isinstance(data, collections.OrderedDict) or isinstance(data, dict):
        return {k: ordered_dict_to_plain_dict(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [ordered_dict_to_plain_dict(item) for item in data]
    else:
        return data

# --- 3. ROS Data Subscriber Class ---
class RosDataSubscriber:
    def __init__(self, node: Node, topic_name: str, msg_type: type):
        self.node = node
        self.latest_msg_dict = None
        self.lock = threading.Lock()
        self.msg_type = msg_type
        self.topic_name = topic_name
        self.active = True
        self.subscription = None

        # Check if this specific message type is a placeholder because of import failure
        is_placeholder_type = False
        if not IROBOT_MSGS_AVAILABLE:
            if (msg_type == WheelVels and topic_name == '/wheel_vels') or \
               (msg_type == DockStatus and topic_name == '/dock') or \
               (msg_type == HazardDetectionVector and topic_name == '/hazard_detection'):
                is_placeholder_type = True
        
        if is_placeholder_type:
            self.node.get_logger().error(f"Cannot subscribe to {self.topic_name}: Message type {msg_type.__name__} not available due to import failure.")
            return # Do not create subscription if message type is just a placeholder

        self.subscription = self.node.create_subscription(
            self.msg_type,
            self.topic_name,
            self.listener_callback,
            10  # QoS depth
        )
        if self.subscription:
            self.node.get_logger().info(f"Successfully subscribed to {self.topic_name}")
        else:
            self.node.get_logger().error(f"Failed to subscribe to {self.topic_name}")

    def listener_callback(self, msg):
        if not self.active:
            return
        with self.lock:
            try:
                self.latest_msg_dict = message_to_ordereddict(msg)
            except Exception as e:
                self.node.get_logger().error(f"Error converting message to dict on {self.topic_name}: {e}")
                self.latest_msg_dict = None

    def get_latest_message_as_dict(self):
        if not self.active:
            return {"error": f"Subscription to {self.topic_name} is not active."}
        # If subscription was never created (e.g. due to placeholder type)
        if not self.subscription and self.node: # Check self.node as well to avoid error if node itself failed
             self.node.get_logger().warn(f"Attempted to get data for {self.topic_name}, but subscription was never established.")
             return {"error": f"Subscription for {self.topic_name} was not established (likely missing message types)."}

        with self.lock:
            if self.latest_msg_dict:
                return ordered_dict_to_plain_dict(self.latest_msg_dict)
            return None

    def destroy(self):
        self.active = False
        if self.subscription and self.node and rclpy.ok() and self.node.handle:
            try:
                self.node.destroy_subscription(self.subscription)
                self.node.get_logger().info(f"Subscription to {self.topic_name} destroyed.")
            except Exception as e:
                self.node.get_logger().error(f"Error destroying subscription to {self.topic_name}: {e}")
        self.subscription = None

# --- 4. Flask App Setup ---
app = Flask(__name__)
ros_executor = None
ros_executor_thread = None
ros_global_node = None
subscribers_dict = {}

# --- 5. ROS Initialization and Shutdown Logic ---
def initialize_ros_components():
    global ros_executor, ros_executor_thread, ros_global_node, subscribers_dict

    if not rclpy.ok():
        try:
            rclpy.init()
            app.logger.info("RCLPY initialized.")
        except Exception as e:
            app.logger.error(f"Failed to initialize RCLPY: {e}")
            return False
    else:
        app.logger.info("RCLPY already initialized.")

    try:
        ros_global_node = Node("flask_api_ros_node")
        app.logger.info(f"Global ROS Node '{ros_global_node.get_name()}' created.")
    except Exception as e:
        app.logger.error(f"Failed to create global ROS node: {e}")
        if rclpy.ok():
            rclpy.shutdown()
        return False

    topics_to_subscribe_config = {
        'odom': ('/odom', Odometry),
        'imu': ('/imu', Imu),
        'joint_states': ('/joint_states', JointState),
        'battery_state': ('/battery_state', BatteryState),
    }

    if IROBOT_MSGS_AVAILABLE:
        topics_to_subscribe_config['wheel_vels'] = ('/wheel_vels', WheelVels)
        topics_to_subscribe_config['dock_status'] = ('/dock', DockStatus) # Common topic name for iRobot Create 3
        topics_to_subscribe_config['hazard_detection'] = ('/hazard_detection', HazardDetectionVector)
        app.logger.info("iRobot Create message types available. Will attempt to subscribe to /wheel_vels, /dock, /hazard_detection.")
    else:
        app.logger.warning("iRobot Create message types (WheelVels, DockStatus, HazardDetectionVector) not available. "
                           "Skipping subscriptions for /wheel_vels, /dock, /hazard_detection.")

    for key, (topic_name, msg_type) in topics_to_subscribe_config.items():
        try:
            # Check if msg_type is a placeholder and IROBOT_MSGS_AVAILABLE is False
            # This specific check here might be redundant if RosDataSubscriber handles placeholder types well.
            if not IROBOT_MSGS_AVAILABLE and msg_type in [WheelVels, DockStatus, HazardDetectionVector]:
                ros_global_node.get_logger().info(f"Skipping subscription for '{key}' ({topic_name}) as its message type is a placeholder.")
                continue

            subscriber_instance = RosDataSubscriber(ros_global_node, topic_name, msg_type)
            if subscriber_instance.subscription: # Only add if subscription was successfully created
                 subscribers_dict[key] = subscriber_instance
            else:
                ros_global_node.get_logger().warning(f"Subscriber instance for '{key}' ({topic_name}) did not establish a subscription.")
        except Exception as e:
            ros_global_node.get_logger().error(f"Failed to create subscriber instance for '{key}' ({topic_name}): {e}")

    if not subscribers_dict:
        ros_global_node.get_logger().warning("No subscribers were successfully initialized or configured!")

    ros_executor = MultiThreadedExecutor()
    ros_executor.add_node(ros_global_node)
    ros_executor_thread = threading.Thread(target=ros_executor.spin, daemon=True)
    ros_executor_thread.start()
    app.logger.info("ROS executor thread started.")

    atexit.register(shutdown_ros_components)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    return True

def shutdown_ros_components():
    global ros_executor, ros_executor_thread, ros_global_node, subscribers_dict
    app.logger.info("ROS Shutdown initiated...")

    for key, sub_instance in list(subscribers_dict.items()):
        if sub_instance:
            sub_instance.destroy()
    subscribers_dict.clear()

    if ros_executor:
        if rclpy.ok() and ros_global_node and ros_global_node.handle:
            app.logger.info("Shutting down ROS executor...")
            try:
                ros_executor.shutdown(timeout_sec=5.0)
            except Exception as e:
                app.logger.error(f"Error shutting down ROS executor: {e}")
        ros_executor = None

    if ros_executor_thread and ros_executor_thread.is_alive():
        app.logger.info("Joining ROS executor thread...")
        ros_executor_thread.join(timeout=5)
        if ros_executor_thread.is_alive():
            app.logger.warning("ROS executor thread did not terminate gracefully.")
    ros_executor_thread = None

    if ros_global_node:
        if rclpy.ok() and ros_global_node.handle:
             app.logger.info(f"Destroying global ROS node '{ros_global_node.get_name()}'...")
             try:
                 ros_global_node.destroy_node()
             except Exception as e:
                 app.logger.error(f"Error destroying global ROS node: {e}")
        ros_global_node = None

    if rclpy.ok():
        app.logger.info("Shutting down RCLPY context.")
        try:
            rclpy.shutdown()
        except Exception as e:
            app.logger.error(f"Error shutting down RCLPY: {e}")
    app.logger.info("ROS Shutdown complete.")

def signal_handler(sig, frame):
    app.logger.info(f'Signal {sig} received, initiating graceful shutdown...')
    shutdown_ros_components()
    sys.exit(0)

# --- 6. Flask API Endpoints ---
@app.route('/api/topic/<string:topic_key>', methods=['GET'])
def get_topic_data_endpoint(topic_key):
    if topic_key in subscribers_dict:
        subscriber_instance = subscribers_dict[topic_key]
        if not subscriber_instance.active or not subscriber_instance.subscription:
             return jsonify({"error": f"Subscription for topic key '{topic_key}' (Topic: {subscriber_instance.topic_name}) is not active or failed."}), 503

        data = subscriber_instance.get_latest_message_as_dict()
        if data:
            if "error" in data:
                 return jsonify(data), 503 if "not established" in data["error"] else 404 # Distinguish permanent vs temporary
            return jsonify(data)
        else:
            # This means latest_msg_dict is None, which implies no data received yet or an issue.
            return jsonify({"error": f"No data received yet for topic key '{topic_key}' (Topic: {subscriber_instance.topic_name}). Ensure the topic is publishing."}), 404
    else:
        return jsonify({"error": f"Topic key '{topic_key}' is not configured or not found."}), 404

@app.route('/api/status', methods=['GET'])
def get_api_status():
    ros_is_ok = rclpy.ok()
    subscribed_topics_status = {}
    # Also list topics that were configured but couldn't be subscribed to
    all_configured_topic_keys = {
        'odom', 'imu', 'joint_states', 'battery_state',
        'wheel_vels', 'dock_status', 'hazard_detection' # All potentially configured keys
    }

    for key in all_configured_topic_keys:
        if key in subscribers_dict:
            sub = subscribers_dict[key]
            latest_data = sub.get_latest_message_as_dict()
            has_data = False
            if latest_data and not ("error" in latest_data): # Check for actual data, not an error message from get_latest_message_as_dict
                has_data = True
            
            subscribed_topics_status[key] = {
                "topic_name": sub.topic_name,
                "msg_type": str(sub.msg_type.__name__),
                "subscribed_successfully": sub.subscription is not None,
                "active": sub.active,
                "has_data_currently": has_data,
                "status_note": "Subscribed" if sub.subscription else "Subscription failed or not attempted"
            }
        else:
            # This key was in topics_to_subscribe_config initially but no subscriber was created
            # (likely due to IROBOT_MSGS_AVAILABLE being False for those specific topics)
            original_config_entry = None
            temp_config = { # Rebuild a temporary config to get topic_name and msg_type for logging
                'odom': ('/odom', Odometry), 'imu': ('/imu', Imu),
                'joint_states': ('/joint_states', JointState), 'battery_state': ('/battery_state', BatteryState),
                'wheel_vels': ('/wheel_vels', WheelVels), 'dock_status': ('/dock', DockStatus),
                'hazard_detection': ('/hazard_detection', HazardDetectionVector)
            }
            if key in temp_config:
                original_config_entry = temp_config[key]

            status_note = "Not subscribed (likely message type unavailable)"
            if original_config_entry and original_config_entry[1] not in [WheelVels, DockStatus, HazardDetectionVector] and not IROBOT_MSGS_AVAILABLE:
                status_note = "Not subscribed (unknown reason, check logs)"


            subscribed_topics_status[key] = {
                "topic_name": original_config_entry[0] if original_config_entry else "N/A",
                "msg_type": original_config_entry[1].__name__ if original_config_entry else "N/A",
                "subscribed_successfully": False,
                "active": False,
                "has_data_currently": False,
                "status_note": status_note
            }


    node_name = "N/A"
    if ros_global_node and ros_is_ok:
        try:
            node_name = ros_global_node.get_name()
        except Exception: # Catch any exception if node is in a bad state
            node_name = "Error retrieving node name"

    return jsonify({
        "ros_context_status": "ok" if ros_is_ok else "shutdown",
        "ros_node_name": node_name,
        "ros_executor_thread_alive": ros_executor_thread.is_alive() if ros_executor_thread else False,
        "irobot_msgs_package_available": IROBOT_MSGS_AVAILABLE,
        "configured_subscribers_status": subscribed_topics_status
    })

# --- 7. Main Execution ---
if __name__ == '__main__':
    flask_run_kwargs = {'host': '0.0.0.0', 'port': 7000, 'debug': True, 'use_reloader': False}

    if initialize_ros_components():
        app.logger.info(f"Starting Flask server on http://{flask_run_kwargs['host']}:{flask_run_kwargs['port']}")
        try:
            app.run(**flask_run_kwargs)
        except KeyboardInterrupt:
            app.logger.info("Flask server interrupted by user (KeyboardInterrupt).")
    else:
        app.logger.error("Failed to initialize ROS components. Flask server will not start.")
    
    # Ensure cleanup, especially if initialize_ros_components failed partway or app.run exited abruptly
    # atexit and signal_handler should cover most cases, but this is a final check.
    if rclpy.ok():
        app.logger.info("Ensuring ROS components are shut down post-Flask execution...")
        shutdown_ros_components()