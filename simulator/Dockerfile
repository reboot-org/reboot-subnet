FROM ros:humble

WORKDIR /root/ros2_ws

RUN apt-get update && apt-get install -y curl lsb-release gnupg
RUN apt-get install -y xvfb python3-pip ros-humble-irobot-create-nodes ros-humble-teleop-twist-keyboard ros-dev-tools ros-humble-ros-gz

RUN mkdir -p src
RUN cd src && git clone https://github.com/turtlebot/turtlebot4.git -b humble
RUN cd src && git clone https://github.com/turtlebot/turtlebot4_simulator.git -b humble
RUN rosdep install --from-path src -yi
RUN . /opt/ros/humble/setup.sh && colcon build --symlink-install

RUN echo "source /root/ros2_ws/install/setup.bash" >> ~/.bashrc

RUN pip3 install --ignore-installed flask

RUN apt-get install -y screen vim

RUN  apt-get install -y --no-install-recommends \
        libxau6 \
        libxdmcp6 \
        libxcb1 \
        libxext6 \
        libx11-6 

RUN echo "/usr/local/nvidia/lib" >> /etc/ld.so.conf.d/nvidia.conf && \
    echo "/usr/local/nvidia/lib64" >> /etc/ld.so.conf.d/nvidia.conf

ENV LD_LIBRARY_PATH /usr/lib/x86_64-linux-gnu:/usr/lib/i386-linux-gnu${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}:/usr/local/nvidia/lib:/usr/local/nvidia/lib64
RUN apt-get install -y --no-install-recommends \
        pkg-config \
        libglvnd-dev \
        libgl1-mesa-dev \
        libegl1-mesa-dev \
        libgles2-mesa-dev
        
RUN apt-get install -y --no-install-recommends \
        ffmpeg

RUN pip3 install --ignore-installed numpy==1.26.4 opencv-python ffmpeg-python

ENV QT_QPA_PLATFORM xcb
ENV DISPLAY :0

RUN apt-get install -y ros-humble-gazebo-* ros-humble-cartographer ros-humble-cartographer-ros ros-humble-navigation2 ros-humble-nav2-bringup

RUN cd src && git clone -b humble https://github.com/ROBOTIS-GIT/DynamixelSDK.git
RUN cd src && git clone -b humble https://github.com/ROBOTIS-GIT/turtlebot3_msgs.git
RUN cd src && git clone -b humble https://github.com/ROBOTIS-GIT/turtlebot3.git
RUN cd src && git clone -b humble https://github.com/ROBOTIS-GIT/turtlebot3_simulations.git
RUN rosdep install --from-path src -yi
RUN . /opt/ros/humble/setup.sh && colcon build --symlink-install

RUN cd src && git clone https://github.com/robo-friends/m-explore-ros2.git
RUN rosdep install --from-path src -yi
RUN . /opt/ros/humble/setup.sh && colcon build --symlink-install

RUN cd src && git clone https://github.com/dheera/rosboard.git
RUN pip3 install --ignore-installed tornado simplejpeg
RUN rosdep install --from-path src -yi
RUN . /opt/ros/humble/setup.sh && colcon build --symlink-install

RUN pip3 install --upgrade --ignore-installed  numpy==1.26.4 scipy==1.10.1 tensorflow==2.19.0 keras==3.9.2 pyqtgraph
RUN cd src && git clone -b humble https://github.com/ROBOTIS-GIT/turtlebot3_machine_learning.git
RUN python3 -m pip install --upgrade setuptools==58.2.0
RUN rosdep install --from-path src -yi
RUN . /opt/ros/humble/setup.sh && colcon build --symlink-install

ENV TURTLEBOT3_MODEL waffle_pi
ENV ROS_DOMAIN_ID 30
RUN echo 'source /usr/share/gazebo/setup.bash' >> /root/.bashrc
RUN echo 'source /opt/ros/humble/setup.bash' >> /root/.bashrc

COPY api_server /root/ros2_ws/src/api_server

COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]