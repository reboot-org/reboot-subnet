#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
import cv2
import numpy as np
import time
import sys
import signal
import os

try:
    from PIL import Image as PILImage
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    from cv_bridge import CvBridge, CvBridgeError
    CV_BRIDGE_AVAILABLE = True
except ImportError:
    CV_BRIDGE_AVAILABLE = False

# --- Global variables ---
image_received = False
image_saved = False
image_path = None

# --- Signal handler for force exit ---
def signal_handler(signum, frame):
    print(f"\nReceived signal {signum}. Force exiting...")
    os._exit(0)

# --- ROS 2 Node ---
class CameraSubscriber(Node):
    def __init__(self, output_path):
        super().__init__('camera_subscriber')
        self.output_path = output_path
        
        if CV_BRIDGE_AVAILABLE:
            self.bridge = CvBridge()
            self.get_logger().info('Using cv_bridge for image conversion')
        else:
            self.get_logger().warning('cv_bridge not available, using manual conversion')
        
        self.subscription = self.create_subscription(
            Image,
            '/camera/image_raw',  # Common topic for camera images
            self.camera_callback,
            10) # QoS profile depth
        self.get_logger().info('ROS 2 Camera Subscriber has been started. Waiting for /camera/image_raw topic...')

    def camera_callback(self, msg):
        global image_received, image_saved, image_path
        
        if image_saved:
            return  # Only save the first image
            
        self.get_logger().info('Camera image received! Saving image...')
        
        try:
            # Use manual conversion directly to avoid cv_bridge issues
            cv_image = self.manual_convert(msg)
            
            # Save the image
            self.get_logger().info(f'Attempting to save image to: {self.output_path}')
            
            # Use PIL to save the image as PNG
            if PIL_AVAILABLE:
                try:
                    self.get_logger().info(f'Final image array shape: {cv_image.shape}, dtype: {cv_image.dtype}')
                    
                    # Create PIL image based on format
                    if len(cv_image.shape) == 3:
                        if cv_image.shape[2] == 3:
                            # RGB or BGR image
                            if msg.encoding == 'bgr8':
                                # Convert BGR to RGB for PIL
                                rgb_array = cv_image[:, :, ::-1]  # Reverse channels
                            else:
                                # Already RGB
                                rgb_array = cv_image
                            pil_image = PILImage.fromarray(rgb_array, 'RGB')
                        elif cv_image.shape[2] == 4:
                            # RGBA image
                            pil_image = PILImage.fromarray(cv_image, 'RGBA')
                        else:
                            raise Exception(f'Unsupported channel count: {cv_image.shape[2]}')
                    else:
                        # Grayscale image
                        pil_image = PILImage.fromarray(cv_image, 'L')
                    
                    pil_image.save(self.output_path, 'PNG')
                    self.get_logger().info(f'Image saved successfully using PIL as PNG')
                except Exception as e:
                    self.get_logger().error(f'PIL save failed: {e}')
                    raise Exception(f"Failed to save image as PNG: {e}")
            else:
                raise Exception("PIL not available for saving image")
            image_path = self.output_path
            image_received = True
            image_saved = True
            
            self.get_logger().info(f'Camera image has been saved to: {self.output_path}')
            self.get_logger().info(f'Image dimensions: {msg.width}x{msg.height}, Encoding: {msg.encoding}')
            
        except Exception as e:
            self.get_logger().error(f'Error processing image: {e}')

    def manual_convert(self, msg):
        """Manual conversion of ROS2 Image message to OpenCV format"""
        self.get_logger().info(f'Image info: {msg.width}x{msg.height}, encoding: {msg.encoding}, step: {msg.step}')
        self.get_logger().info(f'Data length: {len(msg.data)}, Expected: {msg.step * msg.height}')
        
        # Convert the image data to numpy array
        img_array = np.frombuffer(msg.data, dtype=np.uint8)
        self.get_logger().info(f'Initial array shape: {img_array.shape}')
        
        if msg.encoding == 'rgb8':
            # Reshape for RGB image (3 channels)
            img_array = img_array.reshape((msg.height, msg.step // 3, 3))
            # Crop to actual width if there's padding
            if img_array.shape[1] > msg.width:
                img_array = img_array[:, :msg.width, :]
            # Keep as RGB for PIL (no need to convert to BGR)
            self.get_logger().info(f'RGB array shape: {img_array.shape}')
        elif msg.encoding == 'bgr8':
            # Reshape for BGR image (3 channels)
            img_array = img_array.reshape((msg.height, msg.step // 3, 3))
            # Crop to actual width if there's padding
            if img_array.shape[1] > msg.width:
                img_array = img_array[:, :msg.width, :]
            self.get_logger().info(f'BGR array shape: {img_array.shape}')
        elif msg.encoding == 'mono8':
            # Reshape for grayscale image (1 channel)
            img_array = img_array.reshape((msg.height, msg.step))
            # Crop to actual width if there's padding
            if img_array.shape[1] > msg.width:
                img_array = img_array[:, :msg.width]
            self.get_logger().info(f'Grayscale array shape: {img_array.shape}')
        elif msg.encoding == 'rgba8':
            # Reshape for RGBA image (4 channels)
            img_array = img_array.reshape((msg.height, msg.step // 4, 4))
            # Crop to actual width if there's padding
            if img_array.shape[1] > msg.width:
                img_array = img_array[:, :msg.width, :]
            # Convert RGBA to RGB
            img_array = img_array[:, :, :3]  # Drop alpha channel
            self.get_logger().info(f'RGBA array shape: {img_array.shape}')
        else:
            raise Exception(f'Unsupported encoding: {msg.encoding}')
        
        self.get_logger().info(f'Final array shape: {img_array.shape}, dtype: {img_array.dtype}')
        return img_array


# --- Main execution ---
def main(args=None):
    # Set up signal handlers for force exit
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Check command line arguments
    if len(sys.argv) > 1:
        output_path = sys.argv[1]
        # Ensure it has .png extension
        if not output_path.lower().endswith('.png'):
            output_path = os.path.splitext(output_path)[0] + '.png'
    else:
        output_path = 'camera_image.png'
    
    print(f"Camera image will be saved to: {output_path}")
    
    # Initialize ROS 2
    rclpy.init(args=args)
    
    # Create the ROS 2 node
    camera_subscriber = CameraSubscriber(output_path)

    # Set a timeout for waiting for the camera image
    timeout = 30  # seconds
    start_time = time.time()
    
    print(f"Waiting for /camera/image_raw topic (timeout: {timeout} seconds)...")
    
    try:
        # Spin until we receive the image or timeout
        while not image_received and (time.time() - start_time) < timeout:
            rclpy.spin_once(camera_subscriber, timeout_sec=1.0)
            
        if not image_received:
            print(f"Timeout: No camera image received within {timeout} seconds")
            print("Make sure the /camera/image_raw topic is being published by your ROS 2 system")
            print("You may need to start a camera node or Gazebo simulation with camera")
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
            camera_subscriber.destroy_node()
            print("shutting down...")
            rclpy.shutdown()
        except Exception as e:
            print(f"Error during cleanup: {e}")
            print("Force exiting...")
            os._exit(1)
    
    print(f"Successfully exported camera image to: {image_path}")
    return 0

if __name__ == '__main__':
    exit(main())