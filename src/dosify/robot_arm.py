import rospy
import actionlib
from control_msgs.msg import FollowJointTrajectoryAction, FollowJointTrajectoryGoal
from trajectory_msgs.msg import JointTrajectoryPoint
from sensor_msgs.msg import JointState
from niryo_robot_poses_handlers.srv import GetPose
from std_srvs.srv import Trigger

from dosify.patient_poses import build_patient_week
from dosify.poses_loader import pill_pose_name


class ArmController:
    NED2_JOINT_LIMITS = [
        (-2.99, 2.99), (-1.83, 0.61), (-1.34, 1.57),
        (-2.09, 2.09), (-1.92, 1.92), (-2.53, 2.53),
    ]

    def __init__(self, poses_cfg=None):
        self.tool_id = int(rospy.get_param('~tool_id', 31))
        self.move_speed = float(rospy.get_param('~safe_speed_factor', 1.0))
        self.min_duration = float(rospy.get_param('~min_duration', 1.5))
        self.default_move_duration = float(
            rospy.get_param('~default_move_duration', 3.0))
        self.pick_dwell = float(rospy.get_param('~pick_dwell_sec', 0.35))
        self.lock_j6 = rospy.get_param('~lock_j6', True)
        self.at_target_tol = float(rospy.get_param('~at_target_tol', 0.04))
        self.current_joints = None

        self.hub_pose = None
        self.scan_view_pose = None
        self.pill_poses = {}
        self.patient_poses = {}

        rospy.Subscriber('/joint_states', JointState, self._joint_cb, queue_size=1)
        self.traj = actionlib.SimpleActionClient(
            '/niryo_robot_follow_joint_trajectory_controller/follow_joint_trajectory',
            FollowJointTrajectoryAction)
        rospy.loginfo('Waiting for trajectory server...')
        if not self.traj.wait_for_server(timeout=rospy.Duration(10)):
            raise RuntimeError('Trajectory action server unavailable')

        if poses_cfg is not None:
            self._load_poses(poses_cfg)

        self.j6_reference = self._resolve_j6_reference()
        self._apply_j6_to_computed_patients()
        self._update_tool()

    @staticmethod
    def _anchor_from_saved(saved):
        p = saved['pose']
        return {
            'joints': saved['joints'],
            'position': {'x': p[0], 'y': p[1], 'z': p[2]},
        }

    @classmethod
    def from_config(cls, poses, hub_name, scan_name):
        pills = {
            key: {
                'above': pill_pose_name(poses, key, 'above'),
                'pick': pill_pose_name(poses, key, 'pick'),
            }
            for key in poses.get('pills', {})
        }
        patients = {}
        for person_key, pdata in poses.get('patients', {}).items():
            patients[person_key] = {
                'monday_name': pdata['anchors']['monday']['name'],
                'tuesday_name': pdata['anchors']['tuesday']['name'],
                'prefix': pdata.get('prefix', person_key.replace('_', '-')),
            }
        cfg = {
            'hub': hub_name,
            'scan_view': scan_name,
            'pills': pills,
            'patients': patients,
        }
        return cls(cfg)

    @staticmethod
    def _action_succeeded(result, state, label):
        if state != actionlib.GoalStatus.SUCCEEDED:
            rospy.logerr('%s failed: action state=%s', label, state)
            return False
        if result is None:
            rospy.logerr('%s failed: empty result', label)
            return False
        error_code = getattr(result, 'error_code', 0)
        if error_code not in (0, None):
            rospy.logerr('%s failed: error_code=%s', label, error_code)
            return False
        return True

    @staticmethod
    def _load_saved_pose(name):
        srv_name = '/niryo_robot_poses_handlers/get_pose'
        rospy.wait_for_service(srv_name, timeout=10)
        get_pose = rospy.ServiceProxy(srv_name, GetPose)
        resp = get_pose(name)
        p = resp.pose
        pose = [p.position.x, p.position.y, p.position.z,
                p.rpy.roll, p.rpy.pitch, p.rpy.yaw]
        joints = None
        if hasattr(p, 'joints') and len(p.joints) == 6:
            joints = list(p.joints)
        orientation = None
        if hasattr(p, 'orientation'):
            orientation = p.orientation
        return {
            'name': name,
            'pose': pose,
            'joints': joints,
            'orientation': orientation,
        }

    def _load_all_patients(self, patients_cfg):
        for person_key, cfg in patients_cfg.items():
            self._load_patient_week(person_key, cfg)

    def _load_poses(self, cfg):
        self.hub_pose = self._load_saved_pose(cfg['hub'])
        self.scan_view_pose = self._load_saved_pose(cfg['scan_view'])
        rospy.loginfo('Loaded hub: %s', cfg['hub'])
        rospy.loginfo('Loaded scan view: %s', cfg['scan_view'])

        for pill_key, names in cfg.get('pills', {}).items():
            self.pill_poses[pill_key] = {
                'above': self._load_saved_pose(names['above']),
                'pick': self._load_saved_pose(names['pick']),
            }

        self._load_all_patients(cfg.get('patients', {}))

    def _load_patient_week(self, person_key, cfg):
        monday = self._anchor_from_saved(
            self._load_saved_pose(cfg['monday_name']))
        tuesday = self._anchor_from_saved(
            self._load_saved_pose(cfg['tuesday_name']))
        week = build_patient_week(
            monday, tuesday,
            tuesday_name=cfg['tuesday_name'],
            prefix=cfg.get('prefix', person_key.replace('_', '-')))
        for day, pdata in week.items():
            pos = pdata['position']
            key = '{}/{}'.format(person_key, day)
            self.patient_poses[key] = {
                'name': pdata['name'],
                'joints': pdata['joints'],
                'pose': [pos['x'], pos['y'], pos['z'], 0.0, 0.0, 0.0],
                'computed': pdata.get('computed', False),
                'person': person_key,
                'weekday': day,
            }
            if pdata.get('computed'):
                rospy.loginfo('Computed patient pose: %s', pdata['name'])

    def _apply_j6_to_computed_patients(self):
        if not self.lock_j6 or self.j6_reference is None:
            return
        for pdata in self.patient_poses.values():
            if pdata.get('computed'):
                pdata['joints'] = self._apply_j6_lock(pdata['joints'])

    def _resolve_j6_reference(self):
        explicit = rospy.get_param('~j6_reference', None)
        if explicit is not None:
            return float(explicit)
        for pose, label in ((self.hub_pose, 'hub'),
                            (self.scan_view_pose, 'scan view')):
            joints = pose.get('joints') if pose else None
            if joints and len(joints) == 6:
                rospy.loginfo('J6 locked to %s value %.3f rad', label, joints[5])
                return float(joints[5])
        return None

    def _apply_j6_lock(self, joints):
        if not joints or not self.lock_j6 or self.j6_reference is None:
            return joints
        locked = list(joints)
        locked[5] = self.j6_reference
        return locked

    def _joint_cb(self, msg):
        try:
            idx = [msg.name.index('joint_{}'.format(i)) for i in range(1, 7)]
            self.current_joints = [msg.position[i] for i in idx]
        except ValueError:
            if len(msg.position) >= 6:
                self.current_joints = list(msg.position[:6])

    def _wait_for_joints(self, timeout=5.0):
        deadline = rospy.Time.now() + rospy.Duration(timeout)
        rate = rospy.Rate(20)
        while not rospy.is_shutdown() and rospy.Time.now() < deadline:
            if self.current_joints is not None:
                return True
            rate.sleep()
        rospy.logwarn('No joint states after %.1fs', timeout)
        return False

    def _update_tool(self):
        try:
            rospy.wait_for_service('/niryo_robot/tools/update_tool', timeout=2.0)
            rospy.ServiceProxy('/niryo_robot/tools/update_tool', Trigger)()
        except rospy.ROSException:
            rospy.logwarn('update_tool unavailable; continuing')

    def _check_limits(self, joints, margin=0.02):
        for i, q in enumerate(joints):
            lo, hi = self.NED2_JOINT_LIMITS[i]
            if q < lo + margin or q > hi - margin:
                rospy.logerr('joint_%d=%.3f out of range', i + 1, q)
                return False
        return True

    def _already_at(self, target):
        joints = target.get('joints') if target else None
        if not joints or not self.current_joints:
            return False
        return all(
            abs(self.current_joints[i] - joints[i]) < self.at_target_tol
            for i in range(6))

    def move_joints_blind(self, joints, label='move', duration_scale=1.0):
        joints = list(joints)
        if not self._check_limits(joints):
            return False

        duration = self.default_move_duration
        if self.current_joints:
            diff = max(abs(joints[i] - self.current_joints[i]) for i in range(6))
            duration = max(diff / self.move_speed, self.min_duration)
            duration *= duration_scale
            rospy.loginfo('%s (%.1fs, max diff %.2f): %s',
                          label, duration, diff, [round(j, 3) for j in joints])
        else:
            rospy.logwarn('%s: no joint states; using default duration', label)
            duration *= duration_scale

        goal = FollowJointTrajectoryGoal()
        goal.trajectory.joint_names = [
            'joint_{}'.format(i) for i in range(1, 7)]
        pt = JointTrajectoryPoint()
        pt.positions = joints
        pt.time_from_start = rospy.Duration(duration)
        goal.trajectory.points = [pt]

        self.traj.send_goal(goal)
        self.traj.wait_for_result()
        return self._action_succeeded(
            self.traj.get_result(), self.traj.get_state(), label)

    def move_smart(self, target, duration_scale=1.0):
        joints = target.get('joints') if isinstance(target, dict) else None
        if not joints:
            name = target.get('name', 'target') if isinstance(target, dict) else 'target'
            rospy.logerr("Move target '%s' has no joints", name)
            return False
        if self._already_at(target):
            rospy.loginfo('Already at %s', target.get('name', 'target'))
            return True
        label = target.get('name', 'move')
        return self.move_joints_blind(joints, label, duration_scale)

    def prepare(self):
        self._wait_for_joints()
        self._update_tool()
        self.vacuum(pull=False)
        rospy.sleep(0.2)

    def move_hub(self):
        return self.move_smart(self.hub_pose)

    def move_scan_view(self):
        return self.move_smart(self.scan_view_pose)

    def vacuum(self, pull=True):
        try:
            from tools_interface.srv import ToolCommand
        except ImportError:
            rospy.logerr('tools_interface not available')
            return False

        if pull:
            params = dict(
                id=self.tool_id, position=0, speed=1000,
                hold_torque=0, max_torque=1000)
        else:
            params = dict(
                id=self.tool_id, position=10000, speed=10000,
                hold_torque=1000, max_torque=1000)

        srv_name = '/niryo_robot/tools/pull_air_vacuum_pump'
        try:
            rospy.wait_for_service(srv_name, timeout=3.0)
            proxy = rospy.ServiceProxy(srv_name, ToolCommand)
            proxy(**params)
            return True
        except rospy.ServiceException as exc:
            rospy.logerr('Vacuum failed: %s', exc)
            return False

    def pick_pill(self, pill_key):
        poses = self.pill_poses.get(pill_key)
        if not poses:
            rospy.logerr('Unknown pill type: %s', pill_key)
            return False
        if not self.move_smart(self.hub_pose):
            return False
        if not self.move_smart(poses['above']):
            return False
        if not self.move_smart(poses['pick']):
            return False
        if not self.vacuum(pull=True):
            return False
        rospy.sleep(self.pick_dwell)
        return self.move_smart(poses['above'])

    def place_patient(self, weekday, person='person_1'):
        key = '{}/{}'.format(person, weekday)
        target = self.patient_poses.get(key)
        if not target:
            rospy.logerr('Unknown patient box: %s', key)
            return False
        if not self.move_smart(self.hub_pose):
            return False
        if not self.move_smart(target):
            return False
        rospy.sleep(0.1)
        if not self.vacuum(pull=False):
            return False
        rospy.sleep(0.1)
        return self.move_smart(self.hub_pose)
