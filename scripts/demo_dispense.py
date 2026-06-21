#!/usr/bin/env python3
"""Demo: board view -> scan prescription -> pick pills -> place in patient boxes."""

import os
import sys
from datetime import datetime

import cv2
import numpy as np
import rospy
import rospkg
from sensor_msgs.msg import CompressedImage

from dosify.medications import load_demo_placement, load_medication_map
from dosify.poses_loader import (
    load_medications_config, load_poses,
    patient_joints, pill_joints, scan_view_joints)
from dosify.prescription_scan import scan_prescription_image
from dosify.robot_arm import ArmController


def capture_frame(topic, timeout=10):
    frame = {}

    def cb(msg):
        arr = np.frombuffer(msg.data, np.uint8)
        frame['img'] = cv2.imdecode(arr, cv2.IMREAD_COLOR)

    sub = rospy.Subscriber(topic, CompressedImage, cb, queue_size=1)
    deadline = rospy.Time.now() + rospy.Duration(timeout)
    rate = rospy.Rate(20)
    while not rospy.is_shutdown() and rospy.Time.now() < deadline:
        if 'img' in frame and frame['img'] is not None:
            sub.unregister()
            return frame['img']
        rate.sleep()
    sub.unregister()
    return None


def save_scan_image(img):
    out_dir = os.path.join(rospkg.RosPack().get_path('dosify'), 'ocr', 'scans')
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, 'scan_{}.jpg'.format(
        datetime.now().strftime('%Y%m%d_%H%M%S')))
    cv2.imwrite(path, img)
    return path


def main():
    rospy.init_node('dosify_demo')

    board_pose = rospy.get_param('~board_view_pose', 'tictactoe-vision')
    scan_pose = rospy.get_param('~scan_view_pose', 'scan-view')
    camera_topic = rospy.get_param(
        '~camera_topic', '/niryo_robot_vision/compressed_video_stream')
    settle = float(rospy.get_param('~observation_settle_sec', 0.5))

    poses = load_poses()
    med_cfg = load_medications_config()
    med_map = load_medication_map(med_cfg.get('medications'))
    placement = load_demo_placement(med_cfg.get('demo_placement'))

    arm = ArmController()

    rospy.loginfo('Step 1: board view (%s)', board_pose)
    if not arm.move_joints(arm.fetch_pose_joints(board_pose), 'board view'):
        return 1
    rospy.sleep(settle)

    rospy.loginfo('Step 2: prescription scan view (%s)', scan_pose)
    if not arm.move_joints(scan_view_joints(poses), 'scan view'):
        return 1
    rospy.sleep(settle)

    rospy.loginfo('Step 3: capture prescription')
    img = capture_frame(camera_topic)
    if img is None:
        rospy.logerr('No camera frame on %s', camera_topic)
        return 1
    scan_path = save_scan_image(img)
    rospy.loginfo('Saved %s', scan_path)

    rospy.loginfo('Step 4: prescription scan (CMU OpenAI gateway)')
    try:
        result = scan_prescription_image(scan_path, med_map=med_map)
    except Exception as exc:
        rospy.logerr('Scan failed: %s', exc)
        return 1

    rospy.loginfo('Raw names: %s', result['raw_names'])
    plan = result['plan']
    if not plan:
        rospy.logerr('No mapped meds (need ProcrastiNol, Debugitol, or Sleepn\'t)')
        return 1

    for item in plan:
        pill = item['pill']
        weekday = placement[pill]
        rospy.loginfo('  %s -> %s -> %s', item['medication'], pill, weekday)

    rospy.loginfo('Step 5: pick and place')
    for item in plan:
        pill = item['pill']
        weekday = placement[pill]
        if not arm.pick_at(
                pill_joints(poses, pill, 'above'),
                pill_joints(poses, pill, 'pick')):
            rospy.logerr('Pick failed: %s', pill)
            return 1
        if not arm.place_at(patient_joints(poses, weekday)):
            rospy.logerr('Place failed: %s -> %s', pill, weekday)
            return 1

    rospy.loginfo('Step 6: return to board view')
    arm.move_joints(arm.fetch_pose_joints(board_pose), 'board view')
    rospy.loginfo('Demo complete')
    return 0


if __name__ == '__main__':
    sys.exit(main() or 0)
