import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2
from flask import Flask, Response
import time
import io
import threading
import argparse

app = Flask(__name__)

current_image = None

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
        global current_image
        cv_image = self.bridge.imgmsg_to_cv2(msg, "bgr8")
        _, buffer = cv2.imencode('.jpg', cv_image)
        current_image = buffer.tobytes()

def generate():
    while True:
        if current_image is not None:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + current_image + b'\r\n')
        else:
            yield (b'--frame\r\n'
                   b'Content-Type: text/plain\r\n\r\nNo image available\r\n')
        time.sleep(0.2)
@app.route('/video_stream')
def video_stream():
    return Response(generate(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

def run_ros_node(topic_name):
    rclpy.init()
    image_subscriber = ImageSubscriber(topic_name)
    rclpy.spin(image_subscriber)
    image_subscriber.destroy_node()
    rclpy.shutdown()

def main(args=None):
    parser = argparse.ArgumentParser(description="Subscribe to a ROS2 image topic and serve it as a video stream.")
    parser.add_argument('topic_name', type=str, help="The name of the ROS2 topic to subscribe to.")
    args = parser.parse_args()

    ros_thread = threading.Thread(target=run_ros_node, args=(args.topic_name,))
    ros_thread.start()

    try:
        app.run(host='0.0.0.0', port=5000, threaded=True)
    except KeyboardInterrupt:
        pass
    finally:
        ros_thread.join()

if __name__ == '__main__':
    main()