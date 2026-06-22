"""Extrapolate weekday box poses from Monday + Tuesday anchors."""

WEEKDAYS = (
    'monday', 'tuesday', 'wednesday', 'thursday',
    'friday', 'saturday', 'sunday',
)


def _lerp(anchor_a, anchor_b, index_a, index_b, index):
    span = float(index_b - index_a)
    t = 0.0 if span == 0.0 else (index - index_a) / span
    return [anchor_a[i] + t * (anchor_b[i] - anchor_a[i]) for i in range(len(anchor_a))]


def _pose_dict(name, joints, position, computed=False):
    return {
        'name': name,
        'joints': [round(j, 4) for j in joints],
        'position': {
            'x': round(position[0], 4),
            'y': round(position[1], 4),
            'z': round(position[2], 4),
        },
        'computed': computed,
    }


def compute_week_poses(monday, tuesday, prefix='person-1'):
    mon_j = list(monday['joints'])
    tue_j = list(tuesday['joints'])
    mon_p = [
        monday['position']['x'],
        monday['position']['y'],
        monday['position']['z'],
    ]
    tue_p = [
        tuesday['position']['x'],
        tuesday['position']['y'],
        tuesday['position']['z'],
    ]

    week = {}
    for i, day in enumerate(WEEKDAYS):
        joints = _lerp(mon_j, tue_j, 0, 1, i)
        pos = _lerp(mon_p, tue_p, 0, 1, i)
        week[day] = _pose_dict(
            '{}-{}'.format(prefix, day),
            joints, pos,
            computed=day not in ('monday', 'tuesday'),
        )
    return week


def pose_from_ros_msg(pose_msg):
    p = pose_msg
    return {
        'name': p.name,
        'joints': list(p.joints),
        'position': {
            'x': p.position.x,
            'y': p.position.y,
            'z': p.position.z,
        },
    }


def fetch_pose_from_ros(name, timeout=10):
    import rospy
    from niryo_robot_poses_handlers.srv import GetPose

    rospy.wait_for_service('/niryo_robot_poses_handlers/get_pose', timeout)
    get_pose = rospy.ServiceProxy('/niryo_robot_poses_handlers/get_pose', GetPose)
    resp = get_pose(name)
    if not resp.pose.joints or len(resp.pose.joints) != 6:
        raise RuntimeError("Pose '{}' has no joint data".format(name))
    return pose_from_ros_msg(resp.pose)


def build_patient_week(monday, tuesday=None, tuesday_name='person-1-tuesday',
                       prefix='person-1'):
    if tuesday is None:
        tuesday = fetch_pose_from_ros(tuesday_name)
    return compute_week_poses(monday, tuesday, prefix=prefix)
