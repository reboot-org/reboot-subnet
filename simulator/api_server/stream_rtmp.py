import cv2
import subprocess
import numpy as np
import os

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2
import time
import io
import threading
import argparse

import time

global_image_data = None

# --- Configuration ---
# Camera settings
frame_width = 320
frame_height = 240
fps = 30  # Desired frames per second

# RTMP server URL
rtmp_url = os.getenv("RTMP_URL", "rtmp://10.4.0.10:1935/live/abc123")

# --- FFmpeg Command (Corrected for BGR8) ---
# This command is now configured to receive raw video data in bgr24 format.
ffmpeg_command = [
    'ffmpeg',
    '-y',  # Overwrite output file if it exists
    '-f', 'rawvideo',
    '-vcodec', 'rawvideo',
    '-pix_fmt', 'bgr24',  # CORRECTED: Set pixel format to bgr24 for BGR8 input
    '-s', f'{frame_width}x{frame_height}',
    '-r', str(fps),
    '-i', '-',  # Input from stdin

    '-f', 'lavfi',
    '-i', 'anullsrc=channel_layout=stereo:sample_rate=44100',
    '-c:a', 'aac',      
    '-b:a', '128k',       
    '-shortest',
    '-c:v', 'libx264',
    '-pix_fmt', 'yuv420p',
    '-preset', 'ultrafast',
    '-f', 'flv',
    rtmp_url
]

class ImageSubscriber(Node):
    def __init__(self, topic_name):
        super().__init__('image_subscriber')
        self.subscription = self.create_subscription(
            Image,
            topic_name,
            self.image_callback,
            10)
        self.subscription
        self.bridge = CvBridge()

    def image_callback(self, msg):
        global global_image_data
        global_image_data = self.bridge.imgmsg_to_cv2(msg, "bgr8")
        
        
def run_ros_node(topic_name):
    print("start ros node")
    rclpy.init()
    image_subscriber = ImageSubscriber(topic_name)
    rclpy.spin(image_subscriber)
    image_subscriber.destroy_node()
    rclpy.shutdown()

def start_camera_subscribe(args=None):
    parser = argparse.ArgumentParser(description="Subscribe to a ROS2 image topic and serve it as a video stream.")
    parser.add_argument('topic_name', type=str, help="The name of the ROS2 topic to subscribe to.")
    args = parser.parse_args()

    ros_thread = threading.Thread(target=run_ros_node, args=(args.topic_name,))
    ros_thread.start()
    ros_thread.join()

def push_to_rtmp():
    ffmpeg_process = subprocess.Popen(ffmpeg_command, stdin=subprocess.PIPE)
    while True:
        global global_image_data
        try:
            if global_image_data is not None:
                ffmpeg_process.stdin.write(global_image_data)
        except Exception as e:
            print(e)
        finally:
            time.sleep(0.03)
            
if __name__ == '__main__':
    camera_subscribe_thread = threading.Thread(target=start_camera_subscribe, daemon=True)
    camera_subscribe_thread.start()
    push_thread = threading.Thread(target=push_to_rtmp, daemon=True)
    push_thread.start()
    push_thread.join()
