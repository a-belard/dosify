#!/usr/bin/env python3
"""Dispense orchestration node — drives the dispensing sequence."""

import rospy
from std_srvs.srv import Trigger, TriggerResponse


class DispenseNode:
    def __init__(self):
        rospy.init_node('dispense_node')
        # TODO: define services/topics for dispensing logic

        rospy.Service('/dosify/dispense', Trigger, self._dispense)
        rospy.loginfo('dispense_node ready')

    def _dispense(self, req):
        # TODO: implement dispensing sequence
        return TriggerResponse(success=True, message='ok')

    def run(self):
        rospy.spin()


if __name__ == '__main__':
    DispenseNode().run()
