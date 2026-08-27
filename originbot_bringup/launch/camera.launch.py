#!/usr/bin/python3

# Copyright (c) 2024, www.guyuehome.com
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
import os

# 相机参数使用 -p 内联传参（params 文件方式会导致 hobot_usb_cam
# 无法识别 video_device，退化为逐个探测 /dev/video0..8 并崩溃）
# 出图链路：hobot_usb_cam(mjpeg, zero_copy=True) -> /hbmem_img
#           -> hobot_codec_republish -> /image (bgr8)

def generate_launch_description():
    return LaunchDescription([
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(
                    get_package_share_directory('hobot_shm'),
                    'launch/hobot_shm.launch.py'))
        ),
        Node(
            package='hobot_usb_cam',
            executable='hobot_usb_cam',
            name='hobot_usb_cam',
            arguments=['--ros-args',
                       '-p', 'video_device:=/dev/video8',
                       '-p', 'pixel_format:=mjpeg',
                       '-p', 'image_width:=640',
                       '-p', 'image_height:=480',
                       '-p', 'framerate:=30',
                       '-p', 'io_method:=mmap',
                       '-p', 'zero_copy:=True'],
        ),
        Node(
            package='hobot_codec',
            executable='hobot_codec_republish',
            output='screen',
            parameters=[
                    {"channel": 1},
                    {"in_mode": "shared_mem"},
                    {"in_format": "jpeg"},
                    {"out_mode": "ros"},
                    {"out_format": "bgr8"},
                    {"sub_topic": "/hbmem_img"},
                    {"pub_topic": "/image"}
            ],
            arguments=['--ros-args', '--log-level', 'warn']
        )
    ])