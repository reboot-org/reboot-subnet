#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.action import ActionClient # Added for action client
from geometry_msgs.msg import TwistStamped, Twist
from std_msgs.msg import Header
from irobot_create_msgs.action import Undock as UndockAction # Added for Undock action type
from flask import Flask, request, jsonify
import threading
import time

# Global variables for ROS2 node, publisher, and action client
ros2_node = None
cmd_vel_publisher = None
undock_action_client = None # Added for undock action client
app = Flask(__name__)

class RobotControllerNode(Node):
    """
    ROS2 Node to create the /cmd_vel publisher and /undock action client.
    """
    def __init__(self):
        super().__init__('flask_robot_controller_stamped')
        global cmd_vel_publisher, undock_action_client # Ensure globals are assigned
        # set the use_sim_time parameter
        param_to_set = Parameter('use_sim_time', Parameter.Type.BOOL, True)
        self.set_parameters([param_to_set])
        
        # Create a publisher for TwistStamped messages
        cmd_vel_publisher = self.create_publisher(TwistStamped, '/cmd_vel', 10)
        self.get_logger().info('ROS2 node for Flask robot controller initialized and /cmd_vel (TwistStamped) publisher created.')

        # Create an action client for the /undock action
        undock_action_client = ActionClient(self, UndockAction, '/undock')
        self.get_logger().info('Action client for /undock created.')

def init_ros2_node():
    """
    Initializes the ROS2 node and spins it in a separate thread.
    """
    global ros2_node
    rclpy.init()
    ros2_node = RobotControllerNode()
    # Spin rclpy in a separate daemon thread so it automatically shuts down when the main thread exits
    ros_spin_thread = threading.Thread(target=lambda: rclpy.spin(ros2_node), daemon=True)
    ros_spin_thread.start()
    ros2_node.get_logger().info("ROS2 node spinning in a separate thread.")

@app.route('/control_robot', methods=['POST'])
def control_robot():
    """
    Flask route to receive movement commands and publish them as TwistStamped to /cmd_vel.
    Expected JSON data format: {"linear_x": float, "angular_z": float}
    """
    global cmd_vel_publisher, ros2_node
    if cmd_vel_publisher is None or ros2_node is None:
        return jsonify({"status": "error", "message": "ROS2 publisher or node not initialized."}), 503

    try:
        data = request.get_json()
        if data is None:
            return jsonify({"status": "error", "message": "Invalid JSON data."}), 400

        linear_x = float(data.get('linear_x', 0.0))
        angular_z = float(data.get('angular_z', 0.0))

        twist_stamped_msg = TwistStamped()
        twist_stamped_msg.header = Header()
        twist_stamped_msg.header.stamp = ros2_node.get_clock().now().to_msg()
        twist_stamped_msg.header.frame_id = "base_link" 

        twist_stamped_msg.twist.linear.x = linear_x
        twist_stamped_msg.twist.linear.y = 0.0
        twist_stamped_msg.twist.linear.z = 0.0
        twist_stamped_msg.twist.angular.x = 0.0
        twist_stamped_msg.twist.angular.y = 0.0
        twist_stamped_msg.twist.angular.z = angular_z

        cmd_vel_publisher.publish(twist_stamped_msg)
        ros2_node.get_logger().info(f"Published to /cmd_vel (TwistStamped): linear.x={linear_x}, angular.z={angular_z}, stamp={twist_stamped_msg.header.stamp.sec}.{twist_stamped_msg.header.stamp.nanosec}")
        return jsonify({"status": "success", "message": "Command sent to robot."}), 200

    except TypeError as e:
        if ros2_node:
            ros2_node.get_logger().error(f"Type error processing request: {e}. Data received: {request.data}")
        return jsonify({"status": "error", "message": f"Invalid data type in JSON: {e}"}), 400
    except ValueError as e:
        if ros2_node:
            ros2_node.get_logger().error(f"Value error processing request: {e}. Data received: {data}")
        return jsonify({"status": "error", "message": f"Invalid value in JSON: {e}"}), 400
    except Exception as e:
        if ros2_node:
            ros2_node.get_logger().error(f"Error processing request: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/stop_robot', methods=['POST'])
def stop_robot():
    """
    Flask route to send a stop command (TwistStamped) to /cmd_vel.
    """
    global cmd_vel_publisher, ros2_node
    if cmd_vel_publisher is None or ros2_node is None:
        return jsonify({"status": "error", "message": "ROS2 publisher or node not initialized."}), 503

    try:
        twist_stamped_msg = TwistStamped()
        twist_stamped_msg.header = Header()
        twist_stamped_msg.header.stamp = ros2_node.get_clock().now().to_msg()
        twist_stamped_msg.header.frame_id = "base_link" # Set frame_id for consistency

        twist_stamped_msg.twist.linear.x = 0.0
        twist_stamped_msg.twist.angular.z = 0.0
        # All other fields default to 0.0

        cmd_vel_publisher.publish(twist_stamped_msg)
        ros2_node.get_logger().info(f"Published stop command to /cmd_vel (TwistStamped), stamp={twist_stamped_msg.header.stamp.sec}.{twist_stamped_msg.header.stamp.nanosec}")
        return jsonify({"status": "success", "message": "Stop command sent to robot."}), 200
    except Exception as e:
        if ros2_node:
            ros2_node.get_logger().error(f"Error sending stop command: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/undock', methods=['POST'])
def undock_robot():
    """
    Flask route to send an undock command via ROS2 action /undock.
    """
    global ros2_node, undock_action_client
    if ros2_node is None or undock_action_client is None:
        return jsonify({"status": "error", "message": "ROS2 node or undock action client not initialized."}), 503

    # Check if action server is available
    server_wait_timeout = 3.0 # seconds
    if not undock_action_client.wait_for_server(timeout_sec=server_wait_timeout):
        msg = f'/undock action server not available after waiting {server_wait_timeout}s.'
        ros2_node.get_logger().error(msg)
        return jsonify({"status": "error", "message": msg}), 503

    goal_msg = UndockAction.Goal() # Empty goal for Undock
    ros2_node.get_logger().info('Sending goal to /undock action server...')

    try:
        # Send the goal and wait for acceptance
        goal_handle_future = undock_action_client.send_goal_async(goal_msg)
        
        # Wait for goal acceptance (future to be done)
        # This loop allows the background rclpy.spin() to process the future.
        # Timeout for goal acceptance
        goal_acceptance_timeout_sec = 10.0 
        start_time = time.time()
        while not goal_handle_future.done():
            if time.time() - start_time > goal_acceptance_timeout_sec:
                ros2_node.get_logger().error(f"Timeout waiting for undock goal acceptance after {goal_acceptance_timeout_sec}s.")
                return jsonify({"status": "error", "message": "Timeout waiting for undock goal acceptance."}), 504
            time.sleep(0.01) # Yield control to allow other threads (like rclpy spin) to run

        goal_handle = goal_handle_future.result()
        if not goal_handle.accepted:
            ros2_node.get_logger().info('Undock goal rejected by server.')
            return jsonify({"status": "error", "message": "Undock goal rejected."}), 400
        
        ros2_node.get_logger().info('Undock goal accepted by server. Waiting for result...')

        # Wait for the action result
        result_future = goal_handle.get_result_async()
        
        # Timeout for action completion
        action_completion_timeout_sec = 60.0 # Undocking might take some time
        start_time_result = time.time()
        while not result_future.done():
            if time.time() - start_time_result > action_completion_timeout_sec:
                ros2_node.get_logger().error(f"Timeout waiting for undock action result after {action_completion_timeout_sec}s.")
                # Optionally, attempt to cancel the goal if timeout occurs
                # cancel_future = goal_handle.cancel_goal_async()
                # rclpy.spin_until_future_complete(ros2_node, cancel_future, timeout_sec=1.0) # Example cancel
                return jsonify({"status": "error", "message": "Timeout waiting for undock action result."}), 504
            time.sleep(0.01) # Yield control

        action_response = result_future.result() # This object contains 'status' and 'result' (the Undock.Result message)

        if action_response.status == rclpy.action.GoalStatus.STATUS_SUCCEEDED:
            ros2_node.get_logger().info('Undock action succeeded.')
            # action_response.result is the Undock.Result message, which is empty for this action type.
            return jsonify({"status": "success", "message": "Undock action succeeded."}), 200
        else:
            # Log other statuses like ABORTED, CANCELED, etc.
            status_name = rclpy.action.GoalStatus.to_string(action_response.status) # Helper to get string name
            ros2_node.get_logger().info(f'Undock action failed with status: {status_name} ({action_response.status})')
            return jsonify({"status": "error", "message": f"Undock action failed with status: {status_name}"}), 500

    except Exception as e:
        if ros2_node:
            ros2_node.get_logger().error(f"Exception during /undock action call: {e}")
        return jsonify({"status": "error", "message": f"An unexpected error occurred: {str(e)}"}), 500

def shutdown_ros2():
    """
    Cleanly shuts down the ROS2 node.
    """
    global ros2_node
    if ros2_node:
        ros2_node.get_logger().info("Shutting down ROS2 node...")
        ros2_node.destroy_node()
    if rclpy.ok(): # Check if rclpy is initialized
        rclpy.shutdown()
    print("ROS2 shutdown complete.")


if __name__ == '__main__':
    try:
        init_ros2_node()
        # Wait a bit for the ROS2 node, publisher, and action client to initialize
        time.sleep(2) # Adjust as needed, or implement more robust checks

        initialization_ok = True
        missing_components = []
        if cmd_vel_publisher is None:
            missing_components.append("/cmd_vel publisher")
            initialization_ok = False
        if undock_action_client is None: # Check for undock client
            missing_components.append("/undock action client")
            initialization_ok = False
            
        if not initialization_ok:
            error_msg = f"Error: The following ROS2 components failed to initialize: {', '.join(missing_components)}. Flask server will not start."
            print(error_msg)
            if ros2_node: # Log to ROS logger if node managed to partially initialize
                 ros2_node.get_logger().error(error_msg)
        else:
            print("ROS2 components initialized successfully.")
            print(f"Starting Flask server on http://0.0.0.0:6000")
            print("Available routes:")
            print("  POST /control_robot  (JSON: {\"linear_x\": float, \"angular_z\": float})")
            print("  POST /stop_robot")
            print("  POST /undock")
            # use_reloader=False is important as Flask's reloader can conflict with rclpy's signal handling.
            app.run(host='0.0.0.0', port=6000, debug=True, use_reloader=False)

    except KeyboardInterrupt:
        print("Keyboard interrupt received, shutting down...")
    except Exception as e:
        print(f"An error occurred during startup: {e}")
    finally:
        shutdown_ros2()