#!/usr/bin/env python3
"""Print weekday box poses (Mon/Tue from Ned, Wed-Sun extrapolated)."""

import os
import sys

import rospy
import yaml

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))

from dosify.patient_poses import WEEKDAYS, build_patient_week  # noqa: E402


def load_poses():
    cfg_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'config', 'poses.yaml')
    with open(cfg_path) as f:
        return yaml.safe_load(f) or {}


def print_week(person_key, pdata):
    monday = pdata['anchors']['monday']
    tuesday_name = pdata['anchors']['tuesday']['name']
    prefix = pdata.get('prefix', person_key.replace('_', '-'))
    week = build_patient_week(monday, tuesday_name=tuesday_name, prefix=prefix)
    print('{} weekday poses (Mon/Tue saved, Wed-Sun extrapolated):\n'.format(person_key))
    for day in WEEKDAYS:
        p = week[day]
        tag = 'computed' if p['computed'] else 'saved'
        pos = p['position']
        print('  {} ({})'.format(p['name'], tag))
        print('    joints: {}'.format(p['joints']))
        print('    xyz:    x={:+.4f}  y={:+.4f}  z={:+.4f}'.format(
            pos['x'], pos['y'], pos['z']))
        print()


def main():
    rospy.init_node('print_patient_week', anonymous=True)
    poses = load_poses()
    for person_key, pdata in poses.get('patients', {}).items():
        print_week(person_key, pdata)


if __name__ == '__main__':
    main()
