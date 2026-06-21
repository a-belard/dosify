#!/usr/bin/env python3
"""Niryo arm control node for dosify — handles all physical robot motion."""

import rospy
from std_srvs.srv import Trigger, TriggerResponse
from dosify.patient_poses import WEEKDAYS, build_patient_week


class RobotControlNode:
    def __init__(self):
        rospy.init_node('robot_control')
        self.robot_ip = rospy.get_param('~robot_ip', '172.20.85.100')

        monday = rospy.get_param('~patients/person_1/anchors/monday')
        tuesday_name = rospy.get_param(
            '~patients/person_1/anchors/tuesday/name', 'person-1-tuesday')
        prefix = rospy.get_param('~patients/person_1/prefix', 'person-1')

        self.patient_week = build_patient_week(
            monday, tuesday_name=tuesday_name, prefix=prefix)
        for day in WEEKDAYS:
            p = self.patient_week[day]
            src = 'computed' if p['computed'] else 'saved'
            pos = p['position']
            rospy.loginfo(
                'Patient box %s (%s): x=%.4f y=%.4f z=%.4f',
                p['name'], src, pos['x'], pos['y'], pos['z'])

        rospy.Service('/dosify/go_observation', Trigger, self._go_observation)
        rospy.loginfo('robot_control_node ready (%d weekday poses loaded)',
                      len(self.patient_week))

    def _go_observation(self, req):
        # TODO: move arm to pill-view pose
        return TriggerResponse(success=True, message='ok')

    def run(self):
        rospy.spin()


if __name__ == '__main__':
    RobotControlNode().run()
