#!/usr/bin/env python3
"""Print all 7 person-1 box poses (Mon/Tue anchors + computed Wed-Sun)."""

import os
import sys

import rospy
import yaml

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))

from dosify.patient_poses import WEEKDAYS, build_patient_week  # noqa: E402


def load_monday():
    cfg_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'config', 'poses.yaml')
    with open(cfg_path) as f:
        data = yaml.safe_load(f) or {}
    monday = data['patients']['person_1']['anchors']['monday']
    if not monday.get('joints'):
        raise RuntimeError('Monday anchor missing joints in poses.yaml')
    return monday


def main():
    rospy.init_node('print_patient_week', anonymous=True)
    monday = load_monday()
    tuesday_name = rospy.get_param(
        '~patients/person_1/anchors/tuesday/name', 'person-1-tuesday')

    week = build_patient_week(monday, tuesday_name=tuesday_name)
    print('person-1 weekday poses (Mon/Tue measured, Wed-Sun extrapolated):\n')
    for day in WEEKDAYS:
        p = week[day]
        tag = 'computed' if p['computed'] else 'saved'
        pos = p['position']
        print('  {} ({})'.format(p['name'], tag))
        print('    joints: {}'.format(p['joints']))
        print('    xyz:    x={:+.4f}  y={:+.4f}  z={:+.4f}'.format(
            pos['x'], pos['y'], pos['z']))
        print()


if __name__ == '__main__':
    main()
