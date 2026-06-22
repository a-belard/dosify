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


def pill_pose_name(poses, pill_key, stage):
    return poses['pills'][pill_key][stage]['name']


def hub_pose_name(poses):
    return poses['hub']['name']


def scan_view_name(poses):
    return poses['scan_view']['name']


def patient_pose_name(poses, person_key, weekday):
    patients = poses['patients'][person_key]
    if weekday in patients.get('anchors', {}):
        return patients['anchors'][weekday]['name']
    return patients['computed'][weekday]['name']


def patient_person_keys(poses):
    return list(poses.get('patients', {}).keys())
