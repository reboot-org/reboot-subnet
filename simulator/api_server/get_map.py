#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from nav_msgs.msg import OccupancyGrid
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Use a non-interactive backend for Matplotlib
import matplotlib.pyplot as plt
import time
import sys
import signal
import os

# --- Global variables ---
map_received = False
map_image_path = None

# --- Signal handler for force exit ---
def signal_handler(signum, frame):
    print(f"\nReceived signal {signum}. Force exiting...")
    os._exit(0)

# --- ROS 2 Node ---
class MapSubscriber(Node):
    def __init__(self, output_path):
        super().__init__('map_subscriber')
        self.output_path = output_path
        self.subscription = self.create_subscription(
            OccupancyGrid,
            '/map',
            self.map_callback,
            10) # QoS profile depth
        self.get_logger().info('ROS 2 Map Subscriber has been started. Waiting for /map topic...')

    def map_callback(self, msg):
        global map_received, map_image_path
        self.get_logger().info('OccupancyGrid received! Generating map image...')

        # Extract map metadata
        height = msg.info.height
        width = msg.info.width
        
        # Convert the 1D map data to a 2D numpy array.
        map_data = np.array(msg.data).reshape((height, width))
        
        # Create a visual representation
        # -1 (unknown) -> gray (127)
        # 0 (free) -> white (255)
        # 100 (occupied) -> black (0)
        vis_data = np.full_like(map_data, 127, dtype=np.uint8)
        vis_data[map_data==0] = 255
        vis_data[map_data==100] = 0

        # Generate the plot
        fig, ax = plt.subplots(figsize=(10, 10))
        ax.imshow(vis_data, cmap='gray', origin='lower')
        ax.axis('off')  # Hide the coordinate axes
        plt.grid(False)

        # Save the plot to file
        plt.savefig(self.output_path, format='png', bbox_inches='tight', pad_inches=0.1, dpi=300)
        plt.close(fig) # Close the figure to free up memory
        
        map_image_path = self.output_path
        map_received = True
        
        self.get_logger().info(f'Map image has been saved to: {self.output_path}')
    

# --- Main execution ---
def main(args=None):
    # Set up signal handlers for force exit
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Check command line arguments
    if len(sys.argv) > 1:
        output_path = sys.argv[1]
    else:
        output_path = 'map.png'
    
    print(f"Map will be saved to: {output_path}")
    
    # Initialize ROS 2
    rclpy.init(args=args)
    
    # Create the ROS 2 node
    map_subscriber = MapSubscriber(output_path)

    # Set a timeout for waiting for the map
    timeout = 30  # seconds
    start_time = time.time()
    
    print(f"Waiting for /map topic (timeout: {timeout} seconds)...")
    
    try:
        # Spin until we receive the map or timeout
        while not map_received and (time.time() - start_time) < timeout:
            rclpy.spin_once(map_subscriber, timeout_sec=1.0)
            
        if not map_received:
            print(f"Timeout: No map received within {timeout} seconds")
            print("Make sure the /map topic is being published by your ROS 2 system")
            return 1
            
    except KeyboardInterrupt:
        print("Interrupted by user")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1
    finally:
        # Cleanup with force exit if needed
        try:
            print("Destroying ROS 2 node...")
            map_subscriber.destroy_node()
            print("shutting down...")
            rclpy.shutdown()
        except Exception as e:
            print(f"Error during cleanup: {e}")
            print("Force exiting...")
            os._exit(1)
    
    print(f"Successfully exported map to: {map_image_path}")
    return 0

if __name__ == '__main__':
    exit(main())