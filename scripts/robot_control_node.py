#!/usr/bin/env python3
"""Niryo arm control node for dosify — handles all physical robot motion."""

import rospy
from std_srvs.srv import Trigger, TriggerResponse


class RobotControlNode:
    def __init__(self):
        rospy.init_node('robot_control')
        self.robot_ip = rospy.get_param('~robot_ip', '172.20.85.100')
        # TODO: connect to Niryo and load saved poses (see tictactoe robot_control_node.py)

        rospy.Service('/dosify/go_observation', Trigger, self._go_observation)
        rospy.loginfo('robot_control_node ready')

    def _go_observation(self, req):
        # TODO: move arm to observation pose
        return TriggerResponse(success=True, message='ok')

    def run(self):
        rospy.spin()


if __name__ == '__main__':
    RobotControlNode().run()
