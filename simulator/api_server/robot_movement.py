#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
import time
import sys
import signal
import os
import argparse
import json
import base64

# --- Global variables ---
actions_completed = False
current_action_index = 0
actions_list = []

# --- Signal handler for force exit ---
def signal_handler(signum, frame):
    print(f"\nReceived signal {signum}. Force exiting...")
    os._exit(0)

# --- ROS 2 Node ---
class RobotController(Node):
    def __init__(self, actions):
        super().__init__('robot_controller')
        
        self.actions = actions
        self.current_index = 0
        
        # Create publisher for cmd_vel
        self.publisher = self.create_publisher(
            Twist,
            '/cmd_vel',
            10)  # QoS profile depth
        
        self.get_logger().info('ROS 2 Robot Controller has been started. Ready to execute actions...')
        
    def execute_next_action(self):
        global actions_completed, current_action_index
        
        if self.current_index >= len(self.actions):
            self.get_logger().info('All actions completed!')
            actions_completed = True
            return
            
        action = self.actions[self.current_index]
        current_action_index = self.current_index
        
        self.get_logger().info(f'Executing action {self.current_index + 1}/{len(self.actions)}: {action}')
        
        # Create Twist message
        twist = Twist()
        
        # Set linear and angular velocities based on action type
        if action['type'] == 'move_forward':
            twist.linear.x = action.get('speed', 0.5)
            twist.angular.z = 0.0
        elif action['type'] == 'move_backward':
            twist.linear.x = -action.get('speed', 0.5)
            twist.angular.z = 0.0
        elif action['type'] == 'turn_left':
            twist.linear.x = 0.0
            twist.angular.z = action.get('speed', 1.0)
        elif action['type'] == 'turn_right':
            twist.linear.x = 0.0
            twist.angular.z = -action.get('speed', 1.0)
        elif action['type'] == 'stop':
            twist.linear.x = 0.0
            twist.angular.z = 0.0
        else:
            self.get_logger().warning(f'Unknown action type: {action["type"]}')
            self.current_index += 1
            return
            
        # Publish the command
        self.publisher.publish(twist)
        self.get_logger().info(f'Published: linear.x={twist.linear.x}, angular.z={twist.angular.z}')
        
        # Schedule stop after duration
        duration = action.get('duration', 1.0)
        if duration > 0:
            self.get_logger().info(f'Action will run for {duration} seconds')
            self.create_timer(duration, self.stop_and_continue)
        else:
            self.current_index += 1
            if self.current_index < len(self.actions):
                self.create_timer(0.1, self.execute_next_action)
            else:
                actions_completed = True
                
    def stop_and_continue(self):
        # Stop the robot
        twist = Twist()
        twist.linear.x = 0.0
        twist.angular.z = 0.0
        self.publisher.publish(twist)
        self.get_logger().info('Robot stopped')
        
        # Move to next action
        self.current_index += 1
        if self.current_index < len(self.actions):
            self.create_timer(0.5, self.execute_next_action)  # Small delay between actions
        else:
            actions_completed = True

def parse_actions_from_string(action_string):
    """Parse action string into list of actions"""
    actions = []
    
    # Simple format: "type1,speed1,duration1;type2,speed2,duration2"
    for action_str in action_string.split(';'):
        parts = action_str.strip().split(',')
        if len(parts) >= 1:
            action = {'type': parts[0].strip()}
            if len(parts) >= 2:
                try:
                    action['speed'] = float(parts[1].strip())
                except ValueError:
                    pass
            if len(parts) >= 3:
                try:
                    action['duration'] = float(parts[2].strip())
                except ValueError:
                    pass
            actions.append(action)
    
    return actions

def main(args=None):
    # Set up signal handlers for force exit
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Robot Movement Controller')
    parser.add_argument('actions', nargs='?', help='Actions string or JSON file path')
    parser.add_argument('--file', '-f', help='JSON file containing actions')
    parser.add_argument('--json', '-j', help='JSON string containing actions')
    parser.add_argument('--base64', '-b', help='Base64 encoded JSON string containing actions')
    
    parsed_args = parser.parse_args()
    
    # Parse actions
    actions = []
    
    if parsed_args.base64:
        # Parse base64 encoded JSON string
        try:
            decoded_json = base64.b64decode(parsed_args.base64.encode('utf-8')).decode('utf-8')
            actions = json.loads(decoded_json)
        except Exception as e:
            print(f"Error parsing base64 JSON: {e}")
            return 1
    elif parsed_args.file:
        # Read from JSON file
        try:
            with open(parsed_args.file, 'r') as f:
                actions = json.load(f)
        except Exception as e:
            print(f"Error reading JSON file: {e}")
            return 1
    elif parsed_args.json:
        # Parse JSON string
        try:
            actions = json.loads(parsed_args.json)
        except Exception as e:
            print(f"Error parsing JSON string: {e}")
            return 1
    elif parsed_args.actions:
        # Check if it's a JSON string or simple format
        if parsed_args.actions.startswith('['):
            try:
                actions = json.loads(parsed_args.actions)
            except Exception as e:
                print(f"Error parsing JSON: {e}")
                return 1
        else:
            # Simple string format
            actions = parse_actions_from_string(parsed_args.actions)
    else:
        # Default actions
        actions = [
            {'type': 'move_forward', 'speed': 0.5, 'duration': 2.0},
            {'type': 'turn_left', 'speed': 1.0, 'duration': 1.0},
            {'type': 'move_forward', 'speed': 0.5, 'duration': 2.0},
            {'type': 'turn_right', 'speed': 1.0, 'duration': 1.0},
            {'type': 'stop', 'duration': 0.5}
        ]
    
    print(f"Robot will execute {len(actions)} actions:")
    for i, action in enumerate(actions):
        print(f"  {i+1}. {action}")
    
    # Initialize ROS 2
    rclpy.init(args=args)
    
    # Create the ROS 2 node
    robot_controller = RobotController(actions)
    
    # Start executing actions
    robot_controller.create_timer(1.0, robot_controller.execute_next_action)
    
    print("Waiting for actions to complete...")
    
    try:
        # Spin until all actions are completed
        while not actions_completed:
            rclpy.spin_once(robot_controller, timeout_sec=0.1)
            
        print("All actions completed successfully!")
            
    except KeyboardInterrupt:
        print("Interrupted by user")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1
    finally:
        # Ensure robot is stopped
        twist = Twist()
        twist.linear.x = 0.0
        twist.angular.z = 0.0
        robot_controller.publisher.publish(twist)
        
        # Cleanup
        try:
            print("Destroying ROS 2 node...")
            robot_controller.destroy_node()
            print("shutting down...")
            rclpy.shutdown()
        except Exception as e:
            print(f"Error during cleanup: {e}")
            print("Force exiting...")
            os._exit(1)
    
    return 0

if __name__ == '__main__':
    exit(main())