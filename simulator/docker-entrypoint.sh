#!/bin/bash
set -ex
export ROS_DOMAIN_ID=30
source /opt/ros/humble/setup.bash
source /usr/share/gazebo/setup.bash
source /root/ros2_ws/install/setup.bash
exec "$@"