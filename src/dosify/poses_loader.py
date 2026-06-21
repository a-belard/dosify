import os

import rospkg
import yaml


def _pkg_path(*parts):
    base = rospkg.RosPack().get_path('dosify')
    return os.path.join(base, *parts)


def load_poses():
    path = _pkg_path('config', 'poses.yaml')
    with open(path) as f:
        return yaml.safe_load(f) or {}


def load_medications_config():
    path = _pkg_path('config', 'medications.yaml')
    with open(path) as f:
        return yaml.safe_load(f) or {}


def pill_joints(poses, pill_key, stage):
    return list(poses['pills'][pill_key][stage]['joints'])


def board_view_joints(poses):
    return list(poses['board_view']['joints'])


def scan_view_joints(poses):
    return list(poses['scan_view']['joints'])


def patient_joints(poses, weekday):
    patients = poses['patients']['person_1']
    if weekday in patients.get('anchors', {}):
        return list(patients['anchors'][weekday]['joints'])
    return list(patients['computed'][weekday]['joints'])
